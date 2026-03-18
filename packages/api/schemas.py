"""
API Schemas.

Typed Pydantic request and response models for every Verus API endpoint.

Design principles:
  - No endpoint returns a raw dict or Any. Every response is typed.
  - Every error response uses ErrorResponse — no naked exception messages.
  - Request IDs propagate through the full call chain for traceability.
  - Engagement scoping is reflected in every schema — every resource
    carries its engagement_id to make cross-engagement leakage obvious.

Error codes:
  AUTHENTICATION_REQUIRED   — no or invalid credentials
  AUTHORIZATION_DENIED      — authenticated but not authorised for this resource
  ENGAGEMENT_NOT_FOUND      — engagement_id does not exist or is not accessible
  VALIDATION_ERROR          — request body failed schema validation
  RATE_LIMIT_EXCEEDED       — per-engagement or per-user rate limit hit
  RUN_NOT_FOUND             — reasoning or plan run ID does not exist
  SESSION_NOT_FOUND         — chat session ID does not exist
  RESOURCE_CONFLICT         — e.g. duplicate run for same document set
  INTERNAL_ERROR            — unhandled server error (correlation_id only; no detail)

Versioning:
  All routes are under /v1/. The API version is embedded in every response
  envelope so clients can detect version drift.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Error codes ────────────────────────────────────────────────────────────────

class ErrorCode(str, Enum):
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHORIZATION_DENIED    = "AUTHORIZATION_DENIED"
    ENGAGEMENT_NOT_FOUND    = "ENGAGEMENT_NOT_FOUND"
    VALIDATION_ERROR        = "VALIDATION_ERROR"
    RATE_LIMIT_EXCEEDED     = "RATE_LIMIT_EXCEEDED"
    RUN_NOT_FOUND           = "RUN_NOT_FOUND"
    SESSION_NOT_FOUND       = "SESSION_NOT_FOUND"
    RESOURCE_CONFLICT       = "RESOURCE_CONFLICT"
    INTERNAL_ERROR          = "INTERNAL_ERROR"


# ── Standard envelope ─────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code:           ErrorCode
    message:        str
    correlation_id: str
    field:          Optional[str] = None  # For VALIDATION_ERROR — which field


class ErrorResponse(BaseModel):
    """Standard error envelope. Never includes stack traces or internal detail."""
    error:          ErrorDetail
    request_id:     str
    timestamp:      datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SuccessEnvelope(BaseModel):
    """Wraps every successful response."""
    request_id:     str
    api_version:    str = "v1"
    timestamp:      datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Authentication / identity ─────────────────────────────────────────────────

class AuthenticatedUser(BaseModel):
    """
    The validated identity extracted from a JWT by the auth middleware.
    Injected into route handlers via FastAPI dependency injection.
    """
    user_id:              str
    email:                str
    organisation_id:      str
    # Engagements this user is authorised to access
    accessible_engagement_ids: list[UUID] = Field(default_factory=list)
    # Roles for RBAC checks
    roles:                list[str]       = Field(default_factory=list)
    token_expires_at:     Optional[datetime] = None


# ── Engagement schemas ────────────────────────────────────────────────────────

class EngagementStatus(str, Enum):
    SETUP     = "setup"     # Initial state before diligence window opens
    ACTIVE    = "active"
    CLOSED    = "closed"
    ARCHIVED  = "archived"


class EngagementSummary(BaseModel):
    engagement_id:    UUID
    name:             str
    target_company:   str
    status:           EngagementStatus
    created_at:       datetime
    document_count:   int = 0
    finding_count:    int = 0


class EngagementListResponse(SuccessEnvelope):
    engagements:      list[EngagementSummary]
    total:            int


class EngagementDetailResponse(SuccessEnvelope):
    engagement_id:    UUID
    name:             str
    target_company:   str
    status:           EngagementStatus
    created_at:       datetime
    document_count:   int
    finding_count:    int
    available_connectors: list[str]
    last_reasoning_run:   Optional[datetime] = None
    last_plan_run:        Optional[datetime] = None


# ── Reasoning run schemas ─────────────────────────────────────────────────────

class ReasoningRunRequest(BaseModel):
    document_ids:    list[UUID] = Field(
        min_length=1,
        description="One or more ingested document IDs to run reasoning over.",
    )
    connector_types: list[str] = Field(
        default_factory=list,
        description="Connector types to query. Empty = use all registered connectors.",
    )


class FindingSummarySchema(BaseModel):
    """Compact finding for list endpoints."""
    finding_id:               UUID
    finding_code:             str
    domain:                   str
    verdict:                  str
    materiality:              str
    confidence:               float
    management_claim:         str
    divergence_summary:       str
    management_claim_citation: str
    system_evidence_citation:  str


class ReasoningRunResponse(SuccessEnvelope):
    run_id:           UUID
    engagement_id:    UUID
    status:           str
    documents_processed:  int
    chunks_loaded:        int
    claims_extracted:     int
    findings_produced:    int
    high_priority_findings: list[FindingSummarySchema]
    all_findings:         list[FindingSummarySchema]
    report_hash:          Optional[str]
    started_at:           datetime
    completed_at:         Optional[datetime]
    duration_secs:        Optional[float]
    error_summary:        Optional[str]


class FindingListResponse(SuccessEnvelope):
    engagement_id:    UUID
    findings:         list[FindingSummarySchema]
    total:            int


# ── Chat session schemas ──────────────────────────────────────────────────────

class ChatSessionCreateRequest(BaseModel):
    connector_types: list[str] = Field(
        default_factory=list,
        description="Connectors available in this session.",
    )


class ChatSessionCreateResponse(SuccessEnvelope):
    session_id:       UUID
    engagement_id:    UUID
    status:           str
    available_connectors: list[str]
    created_at:       datetime


class ChatMessageRequest(BaseModel):
    message:          str = Field(
        min_length=1,
        max_length=4000,
        description="The analyst's message to the Intelligence Chat engine.",
    )


class ChatMessageResponse(SuccessEnvelope):
    session_id:       UUID
    message_id:       UUID
    engagement_id:    UUID
    response:         str
    tool_calls_made:  int
    tool_calls_refused: int
    findings_cited:   list[UUID]
    latency_ms:       int


class ChatSessionStatusResponse(SuccessEnvelope):
    session_id:       UUID
    engagement_id:    UUID
    status:           str
    message_count:    int
    tool_calls_total: int
    created_at:       datetime
    last_active:      datetime


# ── Plan stress-test schemas ──────────────────────────────────────────────────

class PlanStressTestRequest(BaseModel):
    plan_document_ids: list[UUID] = Field(
        min_length=1,
        description="Document IDs of the 100-Day Plan document(s) to stress-test.",
    )
    include_prior_findings: bool = Field(
        default=True,
        description="Whether to reference prior reasoning findings as evidence.",
    )
    max_initiatives: int = Field(
        default=30,
        ge=1,
        le=50,
        description="Maximum number of initiatives to stress-test.",
    )


class InitiativeSummarySchema(BaseModel):
    initiative_id:    UUID
    title:            str
    category:         str
    target_day:       int
    verdict:          str
    confidence:       float
    source_citation:  str
    key_risks:        list[str]
    cited_findings:   list[str]


class PlanStressTestResponse(SuccessEnvelope):
    run_id:           UUID
    engagement_id:    UUID
    status:           str
    plans_processed:  int
    initiatives_extracted: int
    assumptions_tested:    int
    red_flag_count:        int
    at_risk_count:         int
    infeasible_count:      int
    initiative_summaries:  list[InitiativeSummarySchema]
    red_flag_summaries:    list[InitiativeSummarySchema]
    report_hash:           Optional[str]
    started_at:            datetime
    completed_at:          Optional[datetime]
    duration_secs:         Optional[float]
    error_summary:         Optional[str]


# ── Health check ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:     str   # "ok" | "degraded" | "down"
    version:    str
    timestamp:  datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    checks:     dict[str, str] = Field(default_factory=dict)
