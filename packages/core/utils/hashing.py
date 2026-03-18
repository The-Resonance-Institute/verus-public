"""
Evidence ledger hash functions.

These are the cryptographic heart of the Verus evidence chain.
Every hash is deterministic: same inputs always produce same hash.
Every hash is content-addressed: the hash covers only immutable identity fields.

Hash chain:
    chunk_hash  -> written by ingestion-worker after Qdrant upsert
    query_hash  -> written by connector-worker after audit log entry
    finding_hash -> written by reasoning-worker after EvidenceIntegrityEnforcer passes
    report_hash -> written by reasoning-worker after report assembled (root of chain)

Any hash written to the evidence_ledger table is proof that:
    - chunk_hash:   this exact text from this exact document was embedded
    - query_hash:   this exact query ran against this system at this time
    - finding_hash: this finding existed at this time and passed integrity check
    - report_hash:  this set of findings constituted the report at this time
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

SEP = "|"  # Field separator in hash payloads


def _sha256(payload: str) -> str:
    """SHA-256 of a UTF-8 string. Returns lowercase hex digest (64 chars)."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_chunk_hash(
    chunk_id: UUID,
    document_id: UUID,
    engagement_id: UUID,
    text: str,
    source_citation: str,
) -> str:
    """SHA-256 of the chunk's immutable identity fields.

    Does NOT hash embedding_vector — floats are not stable across model versions.
    Does NOT hash token_count — a re-chunking would change it.
    Covers the fields that identify this specific piece of evidence.
    """
    payload = SEP.join([
        str(chunk_id),
        str(document_id),
        str(engagement_id),
        text,
        source_citation,
    ])
    return _sha256(payload)


def generate_query_hash(
    query_id: UUID,
    engagement_id: UUID,
    connector_type: str,
    intent: str,
    parameters_hash: str,
    record_count: int,
    executed_at: datetime,
    records: list[dict[str, Any]],
) -> str:
    """SHA-256 of the query's identity and result fingerprint.

    result_fingerprint hashes the record VALUES (not keys) in sorted order.
    This proves the result set without retaining raw data indefinitely.
    """
    record_values = sorted([
        str(sorted(str(v) for v in r.values()))
        for r in records
    ])
    result_fingerprint = _sha256(json.dumps(record_values))

    payload = SEP.join([
        str(query_id),
        str(engagement_id),
        connector_type,
        intent,
        parameters_hash,
        str(record_count),
        executed_at.isoformat(),
        result_fingerprint,
    ])
    return _sha256(payload)


def generate_parameters_hash(parameters: dict[str, Any]) -> str:
    """Stable SHA-256 of a parameters dict.
    Keys sorted for determinism. Values cast to str.
    """
    stable = json.dumps(
        {k: str(v) for k, v in sorted(parameters.items())},
        sort_keys=True,
    )
    return _sha256(stable)


def generate_finding_hash(
    finding_id: UUID,
    engagement_id: UUID,
    finding_code: str,
    management_claim_citation: str,
    system_evidence_citation: Optional[str],
    verdict: str,
    divergence_summary: Optional[str],
    confidence: float,
) -> str:
    """SHA-256 of the finding's evidence identity.

    Does NOT hash financial_implication — that is a calculated field, not evidence.
    Covers the fields that prove this finding existed with this verdict at this time.
    """
    payload = SEP.join([
        str(finding_id),
        str(engagement_id),
        finding_code,
        management_claim_citation,
        system_evidence_citation or "",
        verdict,
        divergence_summary or "",
        str(round(confidence, 6)),
    ])
    return _sha256(payload)


def generate_report_hash(
    engagement_id: UUID,
    finding_hashes: list[str],
    assembled_at: datetime,
    report_s3_key: str,
) -> str:
    """SHA-256 root hash covering all finding hashes in canonical order.

    sorted(finding_hashes) ensures deterministic output regardless of
    the order findings were written to the database.
    This is the root of the evidence chain for the entire engagement.
    """
    payload = SEP.join([
        str(engagement_id),
        ",".join(sorted(finding_hashes)),
        assembled_at.isoformat(),
        report_s3_key,
    ])
    return _sha256(payload)


def generate_casa_verdict_hash(
    query_id: UUID,
    verdict: str,
    primitive_triggered: Optional[str],
    timestamp: datetime,
) -> str:
    """SHA-256 of a CASA verdict record."""
    payload = SEP.join([
        str(query_id),
        verdict,
        primitive_triggered or "",
        timestamp.isoformat(),
    ])
    return _sha256(payload)


def truncate_hash_for_display(hash_str: str) -> str:
    """Return a human-readable truncated hash for UI display.
    Format: first 16 chars + '...' + last 8 chars.
    Full hash always stored in the ledger.
    """
    if len(hash_str) < 24:
        return hash_str
    return f"{hash_str[:16]}...{hash_str[-8:]}"
