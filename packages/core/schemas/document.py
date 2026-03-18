"""Document schemas — from raw intake through normalized output and chunks."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from packages.core.enums import DocumentStatus, ChunkType


class DocumentIntake(BaseModel):
    document_id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    source: str                          # "vdr_api" | "direct_upload"
    original_filename: str
    file_extension: str                  # pdf | docx | xlsx | pptx | csv | txt
    file_size_bytes: int
    s3_key: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: DocumentStatus = DocumentStatus.QUEUED
    error_message: Optional[str] = None
    page_count: Optional[int] = None
    chunk_count: Optional[int] = None
    claim_count: Optional[int] = None

    model_config = {"use_enum_values": True}


class TextBlock(BaseModel):
    block_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    heading_level: Optional[int] = None   # 1/2/3 or None for body
    text: str
    ocr_confidence: Optional[float] = None
    is_comment: bool = False
    is_speaker_notes: bool = False
    is_placeholder: bool = False          # image-only slide placeholder


class ExtractedTable(BaseModel):
    table_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    headers: list[str]
    rows: list[list[str]]
    table_type: str = "generic"           # financial_model | schedule | generic
    is_sampled: bool = False
    is_malformed: bool = False


class DocumentMetadata(BaseModel):
    filename: str
    file_type: str
    page_count: Optional[int] = None
    vdr_folder_path: Optional[str] = None
    section_path: list[str] = Field(default_factory=list)


class NormalizedDocument(BaseModel):
    document_id: UUID
    engagement_id: UUID
    text_blocks: list[TextBlock]
    tables: list[ExtractedTable]
    metadata: DocumentMetadata


class DocumentChunk(BaseModel):
    chunk_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    engagement_id: UUID
    text: str
    token_count: int
    chunk_type: ChunkType = ChunkType.TEXT
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    section_path: list[str] = Field(default_factory=list)
    heading_text: Optional[str] = None
    overlap_with_prev: bool = False
    overlap_with_next: bool = False
    parent_table_id: Optional[UUID] = None
    source_citation: str                  # human-readable citation string
    embedding_vector: Optional[list[float]] = None

    model_config = {"use_enum_values": True}
