"""
BaseConnector — the interface contract every connector must implement.

Every connector in Verus is a Python class that:
  1. Inherits from BaseConnector
  2. Implements the four abstract methods below
  3. Passes the connector compliance test harness in tests/

Design principles:

  READ-ONLY BY CONTRACT
    Connectors are permitted to call only query/read operations on the
    source system. The BaseConnector enforces this at two levels:
      - The abstract `execute_query` method receives a ConnectorQuery
        whose intent and parameters are validated before dispatch.
      - The CASA governance runtime wraps every execute_query call with
        the `read_only_enforcement` primitive before it runs.
    There is no write method on BaseConnector. Adding one requires a
    deliberate change to this file and a corresponding CASA primitive update.

  CREDENTIAL ISOLATION
    Connectors never hold credentials directly. They receive a
    CredentialBundle (username + token + expiry) from the Vault credential
    service at query time. The bundle is cached for the token lifetime and
    revoked when the engagement closes.

  CANONICAL SCHEMA
    Every connector returns a QueryResult with a list of records
    (list[dict[str, Any]]). The record schema is connector-specific but
    must include at minimum the fields documented in required_fields().
    The reasoning engine works exclusively with this canonical schema —
    it never sees raw API responses.

  HEALTH AND DATA QUALITY
    Every connector implements health_check() and assess_data_quality().
    Health check is called at engagement setup. Data quality assessment
    runs before the reasoning engine starts — its output gates whether
    a domain's claims can be verified (PROCEED/PROCEED_WITH_CAUTION/UNVERIFIABLE).

  AUDIT LOG
    The BaseConnector does not write the audit log itself. It returns a
    QueryResult and the connector worker writes the audit log entry and
    ledger hash. This keeps the connector stateless and testable.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from packages.core.enums import ConnectorType, DataQualityRecommendation
from packages.core.schemas.connector import (
    ConnectorHealthReport,
    ConnectorQuery,
    DataQualityReport,
    QueryResult,
)

logger = logging.getLogger(__name__)


# ─── Credential types ──────────────────────────────────────────────────────────

class CredentialBundle:
    """
    Ephemeral credential set retrieved from Vault.

    Never stored to disk. Never logged. Always cleared after use.
    Callers should not hold references to CredentialBundles longer
    than a single query execution.

    Attributes:
        username:   Service account username or client ID.
        token:      OAuth access token, API key, or password.
        instance_url: Base URL for the connected system (e.g. Salesforce org URL).
        expires_at: When the token expires. None = does not expire.
        extra:      Additional connector-specific fields (e.g. org_id).
    """
    __slots__ = ("username", "token", "instance_url", "expires_at", "extra")

    def __init__(
        self,
        username: str,
        token: str,
        instance_url: str,
        expires_at: Optional[datetime] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        self.username = username
        self.token = token
        self.instance_url = instance_url
        self.expires_at = expires_at
        self.extra = extra or {}

    def is_expired(self) -> bool:
        """Return True if the token has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def __repr__(self) -> str:
        # Token is never included in repr — prevent accidental logging
        return (
            f"CredentialBundle(username={self.username!r}, "
            f"instance_url={self.instance_url!r}, "
            f"expires_at={self.expires_at!r})"
        )


# ─── Connector errors ──────────────────────────────────────────────────────────

class ConnectorError(Exception):
    """Base class for all connector errors."""
    pass


class ConnectorAuthError(ConnectorError):
    """
    Authentication or authorisation failure.
    The credential bundle may be expired or insufficient.
    The connector worker should request a fresh bundle from Vault and retry once.
    """
    pass


class ConnectorQueryError(ConnectorError):
    """
    Query execution failed due to a system-side error.
    Includes API errors, query syntax errors, and timeout errors.
    """
    def __init__(self, message: str, query_intent: str, cause: Optional[Exception] = None) -> None:
        self.query_intent = query_intent
        self.cause = cause
        super().__init__(message)


class ConnectorWriteAttemptError(ConnectorError):
    """
    Raised if connector code attempts a write operation.
    This should never occur in production — it means a connector
    implementation has a bug. The CASA primitive also catches this
    at the intent level before execution.
    """
    pass


# ─── BaseConnector ─────────────────────────────────────────────────────────────

class BaseConnector(ABC):
    """
    Abstract base class for all Verus connectors.

    Subclasses must implement: connector_type, supported_query_types,
    execute_query, health_check, assess_data_quality, required_fields.

    Subclasses must NOT implement any write/mutate operations.
    Subclasses must NOT store credentials as instance attributes.
    """

    @property
    @abstractmethod
    def connector_type(self) -> ConnectorType:
        """The ConnectorType enum value for this connector."""
        ...

    @abstractmethod
    def supported_query_types(self) -> list[str]:
        """
        List of query intent strings this connector supports.
        Used by health_check and by the hypothesis formation agent
        to determine which systems can satisfy a given hypothesis.

        Example: ['pipeline_summary', 'pipeline_velocity', 'closed_won_history']
        """
        ...

    @abstractmethod
    def execute_query(
        self,
        query: ConnectorQuery,
        credentials: CredentialBundle,
    ) -> QueryResult:
        """
        Execute a read-only query against the connected system.

        Args:
            query:       The ConnectorQuery describing what to retrieve.
            credentials: Fresh CredentialBundle from Vault.

        Returns:
            QueryResult with records, counts, and system citation.

        Raises:
            ConnectorAuthError:        If credentials are invalid or expired.
            ConnectorQueryError:       If the query fails on the system side.
            ConnectorWriteAttemptError: If the query attempts a write operation.
            UnsupportedQueryTypeError: If the query intent is not in
                                       supported_query_types().

        IMPORTANT: This method must NEVER modify data in the source system.
        Any connector that calls a write/mutate API endpoint is in violation
        of the connector contract and must be rejected in code review.
        """
        ...

    @abstractmethod
    def health_check(
        self,
        credentials: CredentialBundle,
    ) -> ConnectorHealthReport:
        """
        Verify connectivity and basic access to the system.

        Called at engagement setup before any reasoning queries run.
        Must be fast (< CONNECTOR_HEALTH_CHECK_SECS timeout).
        Must not retrieve any data — only connectivity test.

        Returns:
            ConnectorHealthReport with is_healthy, latency_ms, and
            available_query_types (the subset of supported_query_types
            that are accessible with these credentials).
        """
        ...

    @abstractmethod
    def assess_data_quality(
        self,
        credentials: CredentialBundle,
        engagement_id: UUID,
    ) -> DataQualityReport:
        """
        Assess the quality and completeness of the connected system's data.

        Called after health_check passes. Runs lightweight aggregate
        queries to determine:
          - completeness_score: fraction of expected fields with data
          - historical_depth_months: how far back historical data goes
          - consistency_score: internal consistency of records

        The DataQualityReport.recommendation gates claim verification:
          PROCEED              — data quality sufficient for verification
          PROCEED_WITH_CAUTION — data has gaps, findings will be flagged
          UNVERIFIABLE         — data quality too poor, claims unverifiable

        Returns:
            DataQualityReport for this connector in this engagement.
        """
        ...

    @abstractmethod
    def required_fields(self) -> dict[str, list[str]]:
        """
        Define the minimum required fields for each query type's records.

        Returns a dict mapping query_intent → list of required field names.
        Records missing required fields are flagged in the QueryResult.

        Example:
            {
                'pipeline_summary': ['opportunity_id', 'amount', 'stage'],
                'closed_won_history': ['opportunity_id', 'amount', 'close_date'],
            }

        Used by the reasoning engine to validate record completeness
        before forming hypotheses.
        """
        ...

    # ── Concrete methods ───────────────────────────────────────────────────────

    def validate_query_type(self, query: ConnectorQuery) -> None:
        """
        Validate that the query intent is supported by this connector.
        Raises UnsupportedQueryTypeError if not.
        Called by execute_query implementations at the top of every method.
        """
        if query.intent not in self.supported_query_types():
            raise UnsupportedQueryTypeError(
                intent=query.intent,
                connector_type=str(self.connector_type),
                supported=self.supported_query_types(),
            )

    def validate_read_only(self, query: ConnectorQuery) -> None:
        """
        Assert that the query intent is a read operation.
        Raises ConnectorWriteAttemptError if any write keyword is detected.
        Called by execute_query implementations as a belt-and-suspenders check.
        """
        write_keywords = {
            "create", "update", "delete", "insert", "patch", "put",
            "write", "modify", "remove", "upsert", "set",
        }
        intent_lower = query.intent.lower()
        for keyword in write_keywords:
            if keyword in intent_lower:
                raise ConnectorWriteAttemptError(
                    f"Query intent '{query.intent}' contains write keyword "
                    f"'{keyword}'. Connector is read-only."
                )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(connector_type={self.connector_type})"


# ─── Additional error types ────────────────────────────────────────────────────

class UnsupportedQueryTypeError(ConnectorError):
    """
    The query intent is not in the connector's supported_query_types().
    The reasoning engine should not have dispatched this query.
    """
    def __init__(
        self,
        intent: str,
        connector_type: str,
        supported: list[str],
    ) -> None:
        self.intent = intent
        self.connector_type = connector_type
        self.supported = supported
        super().__init__(
            f"Query intent '{intent}' is not supported by {connector_type}. "
            f"Supported: {supported}"
        )
