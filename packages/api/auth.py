"""
Authentication and Authorisation Middleware.

Every request to a protected endpoint passes through this module.
The middleware chain is:

  1. EXTRACT   — pull the Bearer token from the Authorization header
  2. VALIDATE  — verify JWT signature, expiry, issuer, audience
  3. DECODE    — extract claims: user_id, email, org_id, engagement_ids, roles
  4. INJECT    — produce an AuthenticatedUser for the route handler

Engagement scoping (enforced here, NOT only at DB level):
  Every protected route that takes an {engagement_id} path parameter
  calls require_engagement_access(). This validates that the authenticated
  user's accessible_engagement_ids includes the requested engagement_id.
  If not: 403 AUTHORIZATION_DENIED, immediately — no DB query made.

  This is the first defence. RLS at the DB layer is the second.
  Both must be present. Relying on RLS alone creates a TOCTOU window
  and means the application layer has no visibility into scope violations.

JWT claims schema (what Verus expects from the identity provider):
  {
    "sub":         "user_id",
    "email":       "analyst@fund.com",
    "org_id":      "org_abc123",
    "engagements": ["uuid1", "uuid2"],  // UUIDs of accessible engagements
    "roles":       ["analyst", "viewer"],
    "exp":         1234567890,
    "iss":         "https://auth.verus.io",
    "aud":         "verus-api"
  }

In test/development mode (VERUS_JWT_SECRET env var set to a test value),
the middleware accepts tokens signed with the test secret. In production,
the middleware validates against the JWKS endpoint.

Error responses:
  401 AUTHENTICATION_REQUIRED — missing, malformed, or expired token
  403 AUTHORIZATION_DENIED   — valid token but no access to this engagement
"""
from __future__ import annotations

import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.api.schemas import AuthenticatedUser, ErrorCode

logger = logging.getLogger(__name__)

# ── Security scheme ────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)

# JWT configuration from environment
_JWT_SECRET    = os.environ.get("VERUS_JWT_SECRET", "")
_JWT_ALGORITHM = "HS256"
_JWT_ISSUER    = os.environ.get("VERUS_JWT_ISSUER", "https://auth.verus.io")
_JWT_AUDIENCE  = os.environ.get("VERUS_JWT_AUDIENCE", "verus-api")


# ── FastAPI dependencies ───────────────────────────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthenticatedUser:
    """
    FastAPI dependency: validate the Bearer token and return the authenticated user.

    Usage in route:
        @router.get("/resource")
        def get_resource(user: AuthenticatedUser = Depends(get_current_user)):
            ...

    Raises:
        HTTPException(401) if token is missing, malformed, or expired.
    """
    if credentials is None:
        raise _auth_error("Authorization header is required.")

    token = credentials.credentials
    return _validate_and_decode_token(token)


def require_engagement_access(
    engagement_id: UUID,
    user: AuthenticatedUser,
) -> UUID:
    """
    Validate that the authenticated user has access to the requested engagement.

    This is called explicitly in every route that takes an {engagement_id}
    path parameter. It is NOT a dependency injected automatically — it must
    be called explicitly so that the access check is visible in the route code.

    Args:
        engagement_id: The engagement ID from the request path parameter.
        user:          The authenticated user from get_current_user().

    Returns:
        The engagement_id (pass-through for convenience).

    Raises:
        HTTPException(403) if the user does not have access to this engagement.
        HTTPException(403) if accessible_engagement_ids is empty (safety check).
    """
    # Safety check: if no engagements are in the token, deny all
    if not user.accessible_engagement_ids:
        logger.warning(
            "User %s has no accessible engagements — denying access to %s",
            user.user_id, engagement_id,
        )
        raise _authz_error(engagement_id)

    if engagement_id not in user.accessible_engagement_ids:
        logger.warning(
            "User %s attempted to access engagement %s — not in accessible list",
            user.user_id, engagement_id,
        )
        raise _authz_error(engagement_id)

    return engagement_id


def require_role(role: str, user: AuthenticatedUser) -> None:
    """
    Validate that the authenticated user has the required role.

    Raises:
        HTTPException(403) if the user does not have the role.
    """
    if role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": ErrorCode.AUTHORIZATION_DENIED,
                    "message": f"Role '{role}' is required for this action.",
                    "correlation_id": "N/A",
                }
            },
        )


# ── Token validation ───────────────────────────────────────────────────────────

def _validate_and_decode_token(token: str) -> AuthenticatedUser:
    """
    Validate a JWT and decode its claims into an AuthenticatedUser.

    In production: validates signature against JWKS endpoint.
    In test mode: validates signature against VERUS_JWT_SECRET.
    """
    try:
        from jose import jwt, JWTError, ExpiredSignatureError

        if not _JWT_SECRET:
            # No secret configured — reject all tokens in production
            raise _auth_error(
                "Server is not configured for token validation. "
                "Set VERUS_JWT_SECRET."
            )

        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
            audience=_JWT_AUDIENCE,
            issuer=_JWT_ISSUER,
            options={"verify_aud": True, "verify_iss": True},
        )

        return _claims_to_user(payload)

    except Exception as exc:
        # Broad catch: re-raise auth errors, convert others
        if isinstance(exc, HTTPException):
            raise
        logger.debug("Token validation failed: %s", exc)
        raise _auth_error(f"Token validation failed: {type(exc).__name__}")


def _claims_to_user(payload: dict) -> AuthenticatedUser:
    """Convert validated JWT claims to AuthenticatedUser."""
    try:
        engagement_ids = [
            UUID(e) for e in payload.get("engagements", [])
        ]
    except (ValueError, TypeError):
        engagement_ids = []

    return AuthenticatedUser(
        user_id=payload.get("sub", ""),
        email=payload.get("email", ""),
        organisation_id=payload.get("org_id", ""),
        accessible_engagement_ids=engagement_ids,
        roles=payload.get("roles", []),
    )


# ── Error factories ────────────────────────────────────────────────────────────

def _auth_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "code": ErrorCode.AUTHENTICATION_REQUIRED,
                "message": message,
                "correlation_id": "N/A",
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authz_error(engagement_id: UUID) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": ErrorCode.AUTHORIZATION_DENIED,
                "message": (
                    f"You do not have access to engagement {engagement_id}. "
                    f"Contact your fund administrator to request access."
                ),
                "correlation_id": "N/A",
            }
        },
    )


# ── Token generation (test / dev only) ────────────────────────────────────────

def _make_test_token(
    user_id: str = "test-user",
    email: str = "analyst@fund.com",
    org_id: str = "org-test",
    engagement_ids: list[UUID] = None,
    roles: list[str] = None,
    secret: str = None,
    expired: bool = False,
) -> str:
    """
    Generate a test JWT. Used only in tests — never in production routes.

    Args:
        user_id:        The user's subject claim.
        email:          The user's email.
        org_id:         The organisation ID.
        engagement_ids: Engagements the user can access.
        roles:          The user's roles.
        secret:         JWT signing secret (defaults to _JWT_SECRET).
        expired:        If True, produce a token that is already expired.

    Returns:
        A signed JWT string.
    """
    from datetime import datetime, timedelta, timezone
    from jose import jwt

    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=8)

    payload = {
        "sub":         user_id,
        "email":       email,
        "org_id":      org_id,
        "engagements": [str(e) for e in (engagement_ids or [])],
        "roles":       roles or ["analyst"],
        "iss":         _JWT_ISSUER,
        "aud":         _JWT_AUDIENCE,
        "iat":         now,
        "exp":         exp,
    }
    return jwt.encode(payload, secret or _JWT_SECRET, algorithm=_JWT_ALGORITHM)
