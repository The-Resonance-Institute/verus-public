"""
Database Connection Layer.

Manages psycopg2 connection pools, request-scoped sessions, and
Row Level Security (RLS) enforcement for all application queries.

Architecture:
  - Two pools: one for the application role (verus_app), one for migrations
  - verus_app is a non-superuser — RLS policies are enforced for it
  - The superuser (verus) bypasses RLS — never used for application queries
  - Every application query must run through get_session() which sets the
    RLS context variable before the query and clears it after

RLS enforcement:
  Every engagement-scoped table has a policy:
    USING (engagement_id = current_setting('app.engagement_id', TRUE)::uuid
           OR current_setting('app.is_admin', TRUE) = 'true')

  Before every application query the session calls:
    SET LOCAL app.engagement_id = '{engagement_id}'

  SET LOCAL is transaction-scoped — it is automatically cleared when
  the transaction ends. This prevents cross-engagement leakage even
  if a connection is returned to the pool without explicit cleanup.

Connection strings:
  DATABASE_URL         — verus_app role, used for all application queries
  DATABASE_MIGRATION_URL — verus superuser, used only for migrations

Usage:
  # In route handlers (via FastAPI dependency injection):
  with get_session(engagement_id) as conn:
      repo = FindingRepo(conn)
      findings = repo.list_for_engagement(engagement_id)

  # For admin/migration operations (bypasses RLS):
  with get_admin_session() as conn:
      ...
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional
from uuid import UUID

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)

# ── Environment-driven configuration ──────────────────────────────────────────

_APP_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://verus_app:verus_app@127.0.0.1:5432/verus_test",
)

_ADMIN_DATABASE_URL = os.environ.get(
    "DATABASE_MIGRATION_URL",
    "postgresql://verus:verus@127.0.0.1:5432/verus_test",
)

# Pool configuration
_MIN_CONNECTIONS = 1
_MAX_CONNECTIONS = 10

# Singleton pools — initialised lazily on first use
_app_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
_admin_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


# ── Pool management ────────────────────────────────────────────────────────────

def _get_app_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Return the application connection pool, initialising it if needed."""
    global _app_pool
    if _app_pool is None or _app_pool.closed:
        logger.info(
            "Initialising application connection pool (verus_app role)"
        )
        _app_pool = psycopg2.pool.ThreadedConnectionPool(
            _MIN_CONNECTIONS,
            _MAX_CONNECTIONS,
            _APP_DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _app_pool


def _get_admin_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Return the admin connection pool (superuser — bypasses RLS)."""
    global _admin_pool
    if _admin_pool is None or _admin_pool.closed:
        logger.info(
            "Initialising admin connection pool (verus superuser role)"
        )
        _admin_pool = psycopg2.pool.ThreadedConnectionPool(
            _MIN_CONNECTIONS,
            _MAX_CONNECTIONS,
            _ADMIN_DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _admin_pool


def close_pools() -> None:
    """Close all connection pools. Call on application shutdown."""
    global _app_pool, _admin_pool
    if _app_pool and not _app_pool.closed:
        _app_pool.closeall()
        logger.info("Application connection pool closed")
    if _admin_pool and not _admin_pool.closed:
        _admin_pool.closeall()
        logger.info("Admin connection pool closed")


# ── Session contexts ───────────────────────────────────────────────────────────

@contextmanager
def get_session(
    engagement_id: UUID,
) -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Provide a request-scoped database connection with RLS enforced.

    Sets app.engagement_id for the duration of the transaction.
    Commits on success, rolls back on any exception.
    Returns the connection to the pool on exit (whether success or error).

    Args:
        engagement_id: The engagement to scope all queries to.
                       Every engagement-scoped table enforces this via RLS.

    Usage:
        with get_session(engagement_id) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM findings WHERE ...")

    Security contract:
        The SET LOCAL is transaction-scoped. Even if a connection is
        returned to the pool without explicit cleanup, the RLS context
        is cleared when the transaction ends. A subsequent caller using
        the same connection cannot inherit the previous engagement's context.
    """
    pool = _get_app_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        set_rls_engagement_id(conn, engagement_id)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        # Clear RLS context before returning to pool
        try:
            with conn.cursor() as cur:
                cur.execute("RESET app.engagement_id")
            conn.commit()
        except Exception:
            pass
        pool.putconn(conn)


@contextmanager
def get_admin_session() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Provide an admin database connection that bypasses RLS.

    Use ONLY for:
      - Running migrations
      - Creating/deleting engagements (which don't have an engagement_id yet)
      - Admin health checks

    Never use for application queries that should be engagement-scoped.
    """
    pool = _get_admin_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_raw_connection(
    database_url: str = None,
) -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Provide a direct connection outside the pool.
    Used in tests and for single-use operations.
    """
    url = database_url or _APP_DATABASE_URL
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── RLS helpers ────────────────────────────────────────────────────────────────

def set_rls_engagement_id(
    conn: psycopg2.extensions.connection,
    engagement_id: UUID,
    local: bool = True,
) -> None:
    """
    Set the RLS context variable.

    Args:
        conn:          Active psycopg2 connection.
        engagement_id: The engagement to scope to.
        local:         If True (default), use SET LOCAL — transaction-scoped.
                       Correct for production where one transaction = one request.
                       If False, use SET — session-scoped. Used in tests where
                       multiple commits happen within a single test and the RLS
                       context must persist across them.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.engagement_id', %s, %s)",
            [str(engagement_id), local],
        )


def set_admin_mode(
    conn: psycopg2.extensions.connection,
) -> None:
    """
    Set app.is_admin = 'true' to bypass RLS for admin operations.
    Transaction-scoped (TRUE = local).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.is_admin', 'true', TRUE)",
        )


def clear_rls_context(
    conn: psycopg2.extensions.connection,
) -> None:
    """Explicitly clear the RLS context variables."""
    with conn.cursor() as cur:
        try:
            cur.execute("RESET app.engagement_id")
        except Exception:
            pass


def get_current_engagement_id(
    conn: psycopg2.extensions.connection,
) -> Optional[str]:
    """
    Read the current app.engagement_id setting from the connection.
    Used in tests to verify RLS context is set correctly.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_setting('app.engagement_id', TRUE) AS eid"
        )
        row = cur.fetchone()
        if row:
            return row["eid"] or None
        return None


# ── Test helpers ───────────────────────────────────────────────────────────────

def get_test_connection() -> psycopg2.extensions.connection:
    """
    Return a direct psycopg2 connection to the test database.
    Caller is responsible for closing. Used in test fixtures.
    """
    return psycopg2.connect(
        _APP_DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def get_admin_test_connection() -> psycopg2.extensions.connection:
    """
    Return a direct admin connection to the test database.
    Used in test fixtures for setup/teardown.
    """
    return psycopg2.connect(
        _ADMIN_DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
