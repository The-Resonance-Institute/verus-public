"""Evidence Ledger schemas — cryptographic chain of custody for all Verus findings."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from packages.core.enums import LedgerEntryType, CASAVerdict


class LedgerEntry(BaseModel):
    ledger_id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    entry_type: LedgerEntryType
    object_id: UUID                      # chunk_id | query_id | finding_id | report_id
    object_hash: str                     # SHA-256 hex (64 chars)
    parent_hash: Optional[str] = None   # hash of parent evidence object
    prev_entry_hash: Optional[str] = None  # hash of previous ledger entry (chain)
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_by: str                     # service name: ingestion | connector | reasoning

    model_config = {"use_enum_values": True}


class VerificationResult(BaseModel):
    engagement_id: UUID
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chain_intact: bool
    total_entries: int
    entries_by_type: dict[str, int] = Field(default_factory=dict)
    report_hash: Optional[str] = None
    first_broken_link: Optional[str] = None   # ledger_id of first failure
    verification_certificate: str = ""         # base64-encoded signed JSON


class CASAVerdictEntry(BaseModel):
    """CASA verdict record written to evidence ledger."""
    query_id: UUID
    engagement_id: UUID
    verdict: CASAVerdict
    rationale: str
    primitive_triggered: Optional[str] = None
    connector_type: str
    query_intent: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"use_enum_values": True}
