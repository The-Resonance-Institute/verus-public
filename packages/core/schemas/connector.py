"""Connector schemas — the interface contract between connectors and the reasoning engine."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from packages.core.enums import ConnectorType, ConnectorHealthStatus, DataQualityRecommendation


class ConnectorQuery(BaseModel):
    query_id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    connector_type: ConnectorType
    domain: str                          # commercial | operational | financial | human_capital
    intent: str                          # human-readable description of query purpose
    parameters: dict[str, Any] = Field(default_factory=dict)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    model_config = {"use_enum_values": True}


class QueryResult(BaseModel):
    query_id: UUID
    engagement_id: UUID
    connector_type: ConnectorType
    success: bool
    records: list[dict[str, Any]] = Field(default_factory=list)
    raw_record_count: int = 0            # total in system before filtering
    returned_record_count: int = 0       # records in this result
    query_executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    query_duration_ms: int = 0
    system_citation: str = ""
    error_message: Optional[str] = None
    is_partial: bool = False             # True if truncated at record limit

    model_config = {"use_enum_values": True}


class ConnectorHealthReport(BaseModel):
    connector_type: ConnectorType
    is_healthy: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    available_query_types: list[str] = Field(default_factory=list)
    record_count_estimate: Optional[int] = None

    model_config = {"use_enum_values": True}


class DataQualityReport(BaseModel):
    connector_type: ConnectorType
    engagement_id: UUID
    completeness_score: float            # 0.0 - 1.0
    historical_depth_months: int
    consistency_score: float             # 0.0 - 1.0
    field_coverage: dict[str, float] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)
    recommendation: DataQualityRecommendation
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True}
