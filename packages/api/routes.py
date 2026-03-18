"""
API Routes.

All Verus API endpoints under /v1/.

Route groups:
  /v1/health                    — liveness probe (unauthenticated)
  /v1/engagements               — list and detail engagements
  /v1/engagements/{id}/reasoning — trigger and retrieve reasoning runs
  /v1/engagements/{id}/findings  — list findings from reasoning runs
  /v1/engagements/{id}/chat      — create sessions and send messages
  /v1/engagements/{id}/plan      — trigger and retrieve plan stress-tests

Authentication:
  All routes except /v1/health require a valid Bearer token.
  All routes that take an engagement_id path parameter call
  require_engagement_access() explicitly before doing any work.

Error handling:
  All routes catch exceptions and return typed ErrorResponse objects.
  Stack traces are logged internally but never returned to the caller.
  Every error includes a correlation_id for support ticket correlation.

Rate limiting:
  POST /v1/engagements/{id}/reasoning/runs — 5/hour per engagement
  POST /v1/engagements/{id}/plan/runs      — 3/hour per engagement
  POST /v1/engagements/{id}/chat/sessions  — 10/hour per engagement
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from packages.api.schemas import (
    AuthenticatedUser,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionCreateResponse,
    ChatSessionStatusResponse,
    EngagementDetailResponse,
    EngagementListResponse,
    EngagementStatus,
    EngagementSummary,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    FindingListResponse,
    FindingSummarySchema,
    HealthResponse,
    InitiativeSummarySchema,
    PlanStressTestRequest,
    PlanStressTestResponse,
    ReasoningRunRequest,
    ReasoningRunResponse,
)
from packages.api.auth import (
    get_current_user,
    require_engagement_access,
)
from packages.api.rate_limiter import (
    InMemoryRateLimiter,
    RateLimitedAction,
    enforce_rate_limit,
    get_rate_limiter,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _new_request_id() -> str:
    return str(uuid.uuid4())


def _correlation_id(request: Request) -> str:
    """Extract or generate a correlation ID for this request."""
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _error_response(
    request: Request,
    code: ErrorCode,
    message: str,
    http_status: int,
    field: Optional[str] = None,
) -> HTTPException:
    corr_id = _correlation_id(request)
    return HTTPException(
        status_code=http_status,
        detail=ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                correlation_id=corr_id,
                field=field,
            ),
            request_id=_new_request_id(),
        ).model_dump(mode="json"),
    )


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Liveness probe",
    description="Returns 200 OK when the API is running. No authentication required.",
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="1.0.0",
        checks={"api": "ok"},
    )


# ── Engagements ────────────────────────────────────────────────────────────────

@router.get(
    "/engagements",
    response_model=EngagementListResponse,
    tags=["engagements"],
    summary="List accessible engagements",
)
def list_engagements(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    engagement_store=Depends(lambda: _get_engagement_store()),
) -> EngagementListResponse:
    """
    List all engagements the authenticated user has access to.
    Results are filtered to user.accessible_engagement_ids — no full-table scan.
    """
    engagements = engagement_store.list_for_user(user.accessible_engagement_ids)
    return EngagementListResponse(
        request_id=_new_request_id(),
        engagements=engagements,
        total=len(engagements),
    )


@router.get(
    "/engagements/{engagement_id}",
    response_model=EngagementDetailResponse,
    tags=["engagements"],
    summary="Get engagement detail",
)
def get_engagement(
    request: Request,
    engagement_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    engagement_store=Depends(lambda: _get_engagement_store()),
) -> EngagementDetailResponse:
    require_engagement_access(engagement_id, user)

    engagement = engagement_store.get(engagement_id)
    if engagement is None:
        raise _error_response(
            request, ErrorCode.ENGAGEMENT_NOT_FOUND,
            f"Engagement {engagement_id} not found.",
            status.HTTP_404_NOT_FOUND,
        )
    return EngagementDetailResponse(request_id=_new_request_id(), **engagement)


# ── Reasoning runs ─────────────────────────────────────────────────────────────

@router.post(
    "/engagements/{engagement_id}/reasoning/runs",
    response_model=ReasoningRunResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["reasoning"],
    summary="Trigger a reasoning run",
)
def create_reasoning_run(
    request: Request,
    engagement_id: UUID,
    body: ReasoningRunRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
    reasoning_service=Depends(lambda: _get_reasoning_service()),
) -> ReasoningRunResponse:
    """
    Trigger a Verus reasoning run for an engagement.

    The run extracts management claims from the specified documents,
    queries connected operating systems, and produces findings with
    deterministic verdicts (DIVERGENT, CONFIRMED, UNVERIFIABLE, INCONCLUSIVE).

    Rate limit: 5 runs per engagement per hour.
    """
    require_engagement_access(engagement_id, user)
    enforce_rate_limit(engagement_id, RateLimitedAction.REASONING_RUN, limiter)

    try:
        result = reasoning_service.run(
            engagement_id=engagement_id,
            document_ids=body.document_ids,
            connector_types=body.connector_types,
        )
        return ReasoningRunResponse(
            request_id=_new_request_id(),
            run_id=result.run_id,
            engagement_id=result.engagement_id,
            status=result.status.value,
            documents_processed=result.documents_processed,
            chunks_loaded=result.chunks_loaded,
            claims_extracted=result.claims_extracted,
            findings_produced=result.findings_produced,
            high_priority_findings=[
                _finding_to_schema(f) for f in result.high_priority_findings
            ],
            all_findings=[
                _finding_to_schema(f) for f in result.all_findings
            ],
            report_hash=result.report_hash,
            started_at=result.started_at,
            completed_at=result.completed_at,
            duration_secs=result.duration_secs,
            error_summary=result.error_summary,
        )
    except Exception as exc:
        logger.exception(
            "Reasoning run failed: engagement=%s user=%s",
            engagement_id, user.user_id,
        )
        raise _error_response(
            request, ErrorCode.INTERNAL_ERROR,
            "Reasoning run failed. Use the correlation ID for support.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/engagements/{engagement_id}/findings",
    response_model=FindingListResponse,
    tags=["reasoning"],
    summary="List findings for an engagement",
)
def list_findings(
    request: Request,
    engagement_id: UUID,
    verdict: Optional[str] = None,
    materiality: Optional[str] = None,
    user: AuthenticatedUser = Depends(get_current_user),
    finding_store=Depends(lambda: _get_finding_store()),
) -> FindingListResponse:
    """
    List all findings produced by reasoning runs for this engagement.
    Optionally filter by verdict or materiality.
    """
    require_engagement_access(engagement_id, user)

    findings = finding_store.list(
        engagement_id=engagement_id,
        verdict=verdict,
        materiality=materiality,
    )
    return FindingListResponse(
        request_id=_new_request_id(),
        engagement_id=engagement_id,
        findings=[_finding_to_schema(f) for f in findings],
        total=len(findings),
    )


# ── Chat sessions ──────────────────────────────────────────────────────────────

@router.post(
    "/engagements/{engagement_id}/chat/sessions",
    response_model=ChatSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["chat"],
    summary="Create an Intelligence Chat session",
)
def create_chat_session(
    request: Request,
    engagement_id: UUID,
    body: ChatSessionCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
    chat_service=Depends(lambda: _get_chat_service()),
) -> ChatSessionCreateResponse:
    """
    Create a new Intelligence Chat session for an engagement.

    The session is scoped to this engagement — cross-engagement queries
    are impossible by construction. All connector queries made during the
    session pass through the CASA governance gate.

    Rate limit: 10 new sessions per engagement per hour.
    """
    require_engagement_access(engagement_id, user)
    enforce_rate_limit(engagement_id, RateLimitedAction.CHAT_SESSION, limiter)

    session = chat_service.create_session(
        engagement_id=engagement_id,
        analyst_id=user.user_id,
        connector_types=body.connector_types,
    )
    return ChatSessionCreateResponse(
        request_id=_new_request_id(),
        session_id=session.session_id,
        engagement_id=session.engagement_id,
        status=session.status.value,
        available_connectors=session.available_connectors,
        created_at=session.created_at,
    )


@router.post(
    "/engagements/{engagement_id}/chat/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    tags=["chat"],
    summary="Send a message to the Intelligence Chat engine",
)
def send_chat_message(
    request: Request,
    engagement_id: UUID,
    session_id: UUID,
    body: ChatMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    chat_service=Depends(lambda: _get_chat_service()),
) -> ChatMessageResponse:
    """
    Send a message to an Intelligence Chat session.

    The engine may use tools (connector queries, finding lookups) to
    produce a grounded response. All tool calls pass through CASA governance.

    Returns the assistant's response along with tool call counts and
    CASA verdict summaries for audit purposes.
    """
    require_engagement_access(engagement_id, user)

    try:
        response = chat_service.send_message(
            engagement_id=engagement_id,
            session_id=session_id,
            analyst_id=user.user_id,
            message=body.message,
        )
        return ChatMessageResponse(
            request_id=_new_request_id(),
            session_id=response.session_id,
            message_id=response.message_id,
            engagement_id=response.engagement_id,
            response=response.response,
            tool_calls_made=response.tool_calls_made,
            tool_calls_refused=response.tool_calls_refused,
            findings_cited=response.findings_cited,
            latency_ms=response.latency_ms,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Chat message failed: engagement=%s session=%s user=%s",
            engagement_id, session_id, user.user_id,
        )
        raise _error_response(
            request, ErrorCode.INTERNAL_ERROR,
            "Message processing failed. Use the correlation ID for support.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get(
    "/engagements/{engagement_id}/chat/sessions/{session_id}",
    response_model=ChatSessionStatusResponse,
    tags=["chat"],
    summary="Get chat session status",
)
def get_chat_session(
    request: Request,
    engagement_id: UUID,
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    chat_service=Depends(lambda: _get_chat_service()),
) -> ChatSessionStatusResponse:
    require_engagement_access(engagement_id, user)

    session = chat_service.get_session(
        engagement_id=engagement_id,
        session_id=session_id,
    )
    if session is None:
        raise _error_response(
            request, ErrorCode.SESSION_NOT_FOUND,
            f"Session {session_id} not found.",
            status.HTTP_404_NOT_FOUND,
        )
    return ChatSessionStatusResponse(
        request_id=_new_request_id(),
        session_id=session.session_id,
        engagement_id=session.engagement_id,
        status=session.status.value,
        message_count=session.message_count,
        tool_calls_total=len(session.tool_calls),
        created_at=session.created_at,
        last_active=session.last_active,
    )


# ── Plan stress-tests ──────────────────────────────────────────────────────────

@router.post(
    "/engagements/{engagement_id}/plan/runs",
    response_model=PlanStressTestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["plan"],
    summary="Trigger a 100-Day Plan stress-test",
)
def create_plan_run(
    request: Request,
    engagement_id: UUID,
    body: PlanStressTestRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
    plan_service=Depends(lambda: _get_plan_service()),
) -> PlanStressTestResponse:
    """
    Trigger a 100-Day Plan stress-test for an engagement.

    The engine extracts initiatives from the plan document(s), tests each
    initiative's assumptions against connected operating systems and prior
    Verus findings, and produces deterministic verdicts
    (FEASIBLE, FEASIBLE_WITH_RISK, AT_RISK, INFEASIBLE, ASSUMPTION_UNVERIFIABLE).

    Rate limit: 3 runs per engagement per hour.
    """
    require_engagement_access(engagement_id, user)
    enforce_rate_limit(engagement_id, RateLimitedAction.PLAN_STRESS_TEST, limiter)

    try:
        result = plan_service.run(
            engagement_id=engagement_id,
            plan_document_ids=body.plan_document_ids,
            include_prior_findings=body.include_prior_findings,
            max_initiatives=body.max_initiatives,
        )
        return PlanStressTestResponse(
            request_id=_new_request_id(),
            run_id=result.run_id,
            engagement_id=result.engagement_id,
            status=result.status.value,
            plans_processed=result.plans_processed,
            initiatives_extracted=result.initiatives_extracted,
            assumptions_tested=result.assumptions_tested,
            red_flag_count=result.red_flag_count,
            at_risk_count=result.at_risk_count,
            infeasible_count=result.infeasible_count,
            initiative_summaries=[
                _initiative_to_schema(s) for s in result.initiative_summaries
            ],
            red_flag_summaries=[
                _initiative_to_schema(s) for s in result.red_flag_summaries
            ],
            report_hash=result.report_hash,
            started_at=result.started_at,
            completed_at=result.completed_at,
            duration_secs=result.duration_secs,
            error_summary=result.error_summary,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Plan stress-test failed: engagement=%s user=%s",
            engagement_id, user.user_id,
        )
        raise _error_response(
            request, ErrorCode.INTERNAL_ERROR,
            "Plan stress-test failed. Use the correlation ID for support.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ── Schema converters ─────────────────────────────────────────────────────────

def _finding_to_schema(f) -> FindingSummarySchema:
    """
    Convert a finding to the API FindingSummarySchema.

    Handles both:
      - FindingSummary objects (from reasoning worker — attribute access)
      - dicts (from DbFindingStore — key access, with DB column names)

    DB column mapping:
      claim_citation  → management_claim_citation
      system_citation → system_evidence_citation
    """
    if isinstance(f, dict):
        fid_raw = f.get("finding_id")
        return FindingSummarySchema(
            finding_id=UUID(str(fid_raw)) if fid_raw else UUID(int=0),
            finding_code=f.get("finding_code", ""),
            domain=f.get("domain", ""),
            verdict=f.get("verdict", ""),
            materiality=f.get("materiality", ""),
            confidence=float(f.get("confidence", 0.0)),
            management_claim=f.get("management_claim", ""),
            divergence_summary=f.get("divergence_summary") or "",
            management_claim_citation=(
                f.get("management_claim_citation")        # shaped by DbFindingStore
                or f.get("claim_citation")                # raw DB column name
                or ""
            ),
            system_evidence_citation=(
                f.get("system_evidence_citation")         # shaped by DbFindingStore
                or f.get("system_citation")               # raw DB column name
                or ""
            ),
        )
    # FindingSummary object from reasoning worker
    return FindingSummarySchema(
        finding_id=getattr(f, "finding_id", UUID(int=0)),
        finding_code=getattr(f, "finding_code", ""),
        domain=getattr(f, "domain", ""),
        verdict=getattr(f, "verdict", ""),
        materiality=getattr(f, "materiality", ""),
        confidence=float(getattr(f, "confidence", 0.0)),
        management_claim=getattr(f, "management_claim", ""),
        divergence_summary=getattr(f, "divergence_summary") or "",
        management_claim_citation=getattr(f, "management_claim_citation") or "",
        system_evidence_citation=getattr(f, "system_evidence_citation") or "",
    )


def _initiative_to_schema(s) -> InitiativeSummarySchema:
    """Convert an InitiativeSummary (from worker) to the API schema."""
    return InitiativeSummarySchema(
        initiative_id=s.initiative_id,
        title=s.title,
        category=s.category,
        target_day=s.target_day,
        verdict=s.verdict,
        confidence=s.confidence,
        source_citation=s.source_citation,
        key_risks=s.key_risks,
        cited_findings=s.cited_findings,
    )


# ── Service locators (injected by app.py in production, mocked in tests) ──────

def _get_engagement_store():
    """Returns the engagement store. Replaced by DI in app.py and tests."""
    from packages.api.dependencies import get_engagement_store
    return get_engagement_store()


def _get_finding_store():
    """Returns the finding store. Replaced by DI in app.py and tests."""
    from packages.api.dependencies import get_finding_store
    return get_finding_store()


def _get_reasoning_service():
    """Returns the reasoning service. Replaced by DI in app.py and tests."""
    from packages.api.dependencies import get_reasoning_service
    return get_reasoning_service()


def _get_chat_service():
    """Returns the chat service. Replaced by DI in app.py and tests."""
    from packages.api.dependencies import get_chat_service
    return get_chat_service()


def _get_plan_service():
    """Returns the plan service. Replaced by DI in app.py and tests."""
    from packages.api.dependencies import get_plan_service
    return get_plan_service()
