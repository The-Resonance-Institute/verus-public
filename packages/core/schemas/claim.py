"""Claim schemas — extracted operating assertions from data room documents."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from packages.core.enums import ClaimDomain, ClaimType


class Claim(BaseModel):
    claim_id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    chunk_id: UUID
    document_id: UUID
    claim_text: str
    claim_type: ClaimType
    domain: ClaimDomain
    specific_metric: Optional[str] = None
    stated_value: Optional[str] = None
    time_reference: Optional[str] = None
    materiality: float                    # 0.0 - 1.0
    source_citation: str
    status: str = "active"               # active | deduplicated
    canonical_id: Optional[UUID] = None  # points to canonical if deduplicated
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True}


class ClaimExtraction(BaseModel):
    """Schema returned by the LLM claim extraction service (via instructor)."""
    claim_text: str
    claim_type: ClaimType
    domain: ClaimDomain
    specific_metric: Optional[str] = None
    stated_value: Optional[str] = None
    time_reference: Optional[str] = None
    materiality: float


class ExtractedClaimsResponse(BaseModel):
    """Top-level instructor output schema for claim extraction."""
    claims: list[ClaimExtraction]
    extraction_notes: Optional[str] = None
