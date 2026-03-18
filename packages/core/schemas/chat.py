"""Chat schemas — Intelligence Chat session and message contracts."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class ChatCitation(BaseModel):
    source: str                          # filename or system name
    citation_text: str                   # verbatim citation string
    citation_type: str                   # "document" | "system"
    finding_code: Optional[str] = None  # linked finding if applicable


class ChatMessage(BaseModel):
    message_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    engagement_id: UUID
    role: str                            # "user" | "assistant"
    content: str
    citations: list[ChatCitation] = Field(default_factory=list)
    tools_called: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    token_count: Optional[int] = None


class ChatSession(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)
    engagement_id: UUID
    user_id: UUID
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    message_count: int = 0
    queries_executed: int = 0


class ChatContext(BaseModel):
    """Assembled context passed to LLM for each chat request."""
    engagement_id: UUID
    session_id: UUID
    engagement_summary: dict[str, Any]
    findings_summary: list[dict[str, Any]]   # finding_code + one-line summaries
    connected_systems: list[str]
    relevant_chunks: list[dict[str, Any]]    # retrieved from vector store
    conversation_history: list[dict[str, Any]]
    total_tokens: int = 0
