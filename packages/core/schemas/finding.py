"""Finding schemas — the primary output of the Countercheck Reasoning Engine."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from packages.core.enums import (
    FindingVerdict, FindingMateriality, FindingDomain,
    FindingConfidenceTier, RecommendedAction, ClaimDomain,
)
from packages.core.constants import (
    CONFIDENCE_VERIFIED, CONFIDENCE_PROBABLE,
)


class FinancialImplication(BaseModel):
    finding_id: UUID
    impact_domain: str                   # revenue | ebitda | valuation | deal_structure | ...
    conservative_impact: str             # e.g. "$800K - $1.2M EBITDA reduction"
    base_case_impact: str
    severe_impact: str
    valuation_adjustment: Optional[str] = None
    basis_of_calculation: str            # how the numbers were derived
    recommended_action: RecommendedAction

    model_config = {"use_enum_values": True}


class Finding(BaseModel):
    finding_id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    finding_code: str                    # COM-001, OPS-003, FIN-007, HCM-002
    domain: ClaimDomain
    verdict: FindingVerdict
    materiality: FindingMateriality
    confidence: float                    # 0.0 - 1.0

    # Evidence sources
    management_claim: str
    management_claim_citation: str       # document source_citation
    system_evidence_summary: Optional[str] = None
    system_evidence_citation: Optional[str] = None
    raw_system_data: list[dict] = Field(default_factory=list)

    # Divergence details (DIVERGENT only)
    divergence_summary: Optional[str] = None
    divergence_magnitude: Optional[str] = None
    financial_implication: Optional[FinancialImplication] = None
    recommended_action: Optional[str] = None

    # Thread metadata
    thread_depth: int = 0
    parent_finding_id: Optional[UUID] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True}

    @property
    def confidence_tier(self) -> FindingConfidenceTier:
        if self.confidence >= CONFIDENCE_VERIFIED:
            return FindingConfidenceTier.VERIFIED
        elif self.confidence >= CONFIDENCE_PROBABLE:
            return FindingConfidenceTier.PROBABLE
        return FindingConfidenceTier.INDICATIVE


class ValidationFailure(BaseModel):
    requirement: str                     # document_citation | system_citation | financial_implication | no_speculation
    detail: str


class ValidationResult(BaseModel):
    finding_id: UUID
    passed: bool
    failures: list[ValidationFailure] = Field(default_factory=list)
