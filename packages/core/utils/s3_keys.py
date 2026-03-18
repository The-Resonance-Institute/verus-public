"""
S3 key construction utilities.

All S3 keys for Verus follow a strict engagement-prefixed convention.
These functions are the single source of truth.
No other code constructs S3 keys — it imports from here.
"""
from __future__ import annotations
from uuid import UUID


def raw_document_key(engagement_id: UUID, document_id: UUID, filename: str) -> str:
    """s3://bucket/{engagement_id}/raw/{document_id}/{filename}"""
    return f"{engagement_id}/raw/{document_id}/{filename}"


def normalized_document_key(engagement_id: UUID, document_id: UUID) -> str:
    """s3://bucket/{engagement_id}/normalized/{document_id}/output.json"""
    return f"{engagement_id}/normalized/{document_id}/output.json"


def chunks_key(engagement_id: UUID, document_id: UUID) -> str:
    """s3://bucket/{engagement_id}/chunks/{document_id}/chunks.json"""
    return f"{engagement_id}/chunks/{document_id}/chunks.json"


def deliverable_key(engagement_id: UUID, filename: str) -> str:
    """s3://bucket/{engagement_id}/deliverables/{filename}"""
    return f"{engagement_id}/deliverables/{filename}"


def plan_key(engagement_id: UUID, plan_id: UUID, filename: str) -> str:
    """s3://bucket/{engagement_id}/plan/{plan_id}/{filename}"""
    return f"{engagement_id}/plan/{plan_id}/{filename}"


def engagement_prefix(engagement_id: UUID) -> str:
    """Prefix for all objects belonging to an engagement."""
    return f"{engagement_id}/"


def validate_key_belongs_to_engagement(key: str, engagement_id: UUID) -> bool:
    """Every S3 key for an engagement must start with the engagement_id.
    This is a belt-and-suspenders check — IAM policies enforce this at AWS level.
    """
    return key.startswith(str(engagement_id))
