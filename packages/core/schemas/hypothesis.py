"""Hypothesis schemas — testable predictions formed from data room claims."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from packages.core.enums import ClaimDomain


class Hypothesis(BaseModel):
    hypothesis_id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    source_claim_id: UUID
    hypothesis_text: str
    domain: ClaimDomain
    required_connector_types: list[str] = Field(default_factory=list)
    required_query_types: list[str] = Field(default_factory=list)
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    materiality: float
    status: str = "pending"
    # pending | investigating | confirmed | divergent | unverifiable | abandoned
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True}


class HypothesisFormation(BaseModel):
    """LLM instructor output for a single hypothesis."""
    hypothesis_text: str
    required_connector_types: list[str]
    required_query_types: list[str]
    query_parameters: dict[str, Any] = Field(default_factory=dict)


class HypothesisFormationResponse(BaseModel):
    """Top-level instructor output for hypothesis formation."""
    hypotheses: list[HypothesisFormation]
    formation_notes: Optional[str] = None


class InvestigationResult(BaseModel):
    hypothesis_id: UUID
    verdict: str                         # confirmed | divergent | unverifiable
    confidence: float = 0.0
    explanation: str = ""
    divergence_summary: Optional[str] = None
    divergence_magnitude: Optional[str] = None
    supporting_data_points: list[str] = Field(default_factory=list)
    conflicting_data_points: list[str] = Field(default_factory=list)
    data_limitations: Optional[str] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    thread_candidates: list[dict[str, Any]] = Field(default_factory=list)
