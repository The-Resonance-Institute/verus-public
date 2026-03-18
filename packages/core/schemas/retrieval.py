"""Retrieval schemas — hybrid search results returned to the reasoning and chat engines."""
from __future__ import annotations
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    engagement_id: UUID
    text: str
    source_citation: str                 # MUST be non-empty — enforced at retrieval layer
    score: float                         # reranked relevance score
    section_path: list[str] = Field(default_factory=list)
    chunk_type: str = "text"
    page_number: Optional[int] = None

    def is_valid(self) -> bool:
        """A retrieval result is only valid if it has a source citation.
        Results without citations are dropped before reaching reasoning or chat engines.
        """
        return bool(self.source_citation and self.source_citation.strip())
