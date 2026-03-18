"""Engagement schemas — the top-level container for a Verus diligence engagement."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from packages.core.enums import EngagementStatus


class Engagement(BaseModel):
    engagement_id: UUID = Field(default_factory=uuid4)
    deal_name: str
    target_company_name: str
    status: EngagementStatus = EngagementStatus.SETUP
    window_start: datetime
    window_end: datetime
    deal_team_user_ids: list[UUID] = Field(default_factory=list)
    deal_size_estimate: Optional[float] = None
    ebitda_estimate: Optional[float] = None
    acquisition_multiple_estimate: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: UUID
    closed_at: Optional[datetime] = None
    closure_reason: Optional[str] = None
    retention_delete_at: Optional[datetime] = None

    model_config = {"use_enum_values": True}


class EngagementCreate(BaseModel):
    deal_name: str
    target_company_name: str
    window_start: datetime
    window_end: datetime
    deal_team_user_ids: list[UUID] = Field(default_factory=list)
    deal_size_estimate: Optional[float] = None
    ebitda_estimate: Optional[float] = None
    acquisition_multiple_estimate: Optional[float] = None


class EngagementStatusResponse(BaseModel):
    engagement_id: UUID
    status: EngagementStatus
    ingestion_progress: dict[str, int] = Field(default_factory=dict)
    connector_health: list[dict] = Field(default_factory=list)
    reasoning_progress: Optional[dict] = None
