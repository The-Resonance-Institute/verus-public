"""Plan schemas — 100-Day Plan Stress Test Engine contracts."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from packages.core.enums import (
    InitiativeType, ClaimDomain, AlignmentType, AssessmentConfidence,
)


class Initiative(BaseModel):
    initiative_id: UUID = Field(default_factory=uuid4)
    plan_id: UUID
    initiative_type: InitiativeType
    domain: ClaimDomain
    title: str
    description: str
    stated_assumption: str
    stated_target: Optional[str] = None
    stated_timeline_days: Optional[int] = None
    stated_resource: Optional[str] = None
    source_citation: str                 # plan section/page
    materiality: float                   # 0.0 - 1.0
    is_applicable: bool = True           # deal team can mark not-applicable

    model_config = {"use_enum_values": True}


class AssumptionMapping(BaseModel):
    initiative_id: UUID
    related_finding_ids: list[UUID] = Field(default_factory=list)
    alignment: AlignmentType
    alignment_explanation: str
    relevant_system_signals: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class StressTestAssessment(BaseModel):
    initiative_id: UUID
    plan_id: UUID

    # Dimension 1
    assumption_validity: str             # sound | questionable | unsound
    assumption_validity_explanation: str
    assumption_validity_citations: list[str] = Field(default_factory=list)

    # Dimension 2
    execution_risk: str                  # low | medium | high | critical
    execution_risk_explanation: str
    specific_obstacles: list[str] = Field(default_factory=list)

    # Dimension 3
    outcome_calibration: str             # on_track | optimistic | unrealistic | conservative
    outcome_calibration_explanation: str
    evidence_based_forecast: Optional[str] = None

    # Dimension 4
    identified_gaps: list[str] = Field(default_factory=list)

    confidence_rating: AssessmentConfidence
    recommended_adjustment: Optional[str] = None
    adjustment_citations: list[str] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class PlanDocument(BaseModel):
    plan_id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    original_filename: str
    s3_key: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "uploaded"             # uploaded | extracting | extracted | evaluating | complete | failed
    author: Optional[str] = None
    plan_horizon_days: int = 100
    total_initiatives: int = 0
    initiatives: list[Initiative] = Field(default_factory=list)
    error_message: Optional[str] = None
