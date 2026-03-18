"""
Semantic Chunking Engine.

Converts a NormalizedDocument into a list of DocumentChunks suitable
for embedding and vector store insertion.

Design decisions and their rationale:

  CHUNK SIZE
    Target: CHUNK_TARGET_TOKENS (512). Min: CHUNK_MIN_TOKENS (80).
    Overlap: CHUNK_OVERLAP_TOKENS (64).

    The 512-token target matches the optimal context window for
    text-embedding-3-large. Shorter chunks lose context; longer chunks
    dilute signal.

  TEXT BLOCK CHUNKING
    Each TextBlock is split into sentences first (by period/question/
    exclamation followed by whitespace or end of string). Sentences are
    then accumulated into chunks that stay below the token target.
    When a chunk reaches the target, it closes, overlapping text from
    the end of the current chunk is prepended to the next chunk.

    This preserves sentence boundaries, which is critical for claim
    extraction — a claim split mid-sentence produces incomplete extractions.

  TABLE CHUNKING
    Tables are handled separately from text because they have fixed
    structure. A table with N rows is split into row groups:
      - If the whole table fits within CHUNK_MAX_TABLE_TOKENS (2048),
        it becomes one chunk.
      - Otherwise, it is split into groups of TABLE_ROW_GROUP_SIZE (20)
        rows each, with the header row prepended to every group.

    The header is always included in every table chunk because the
    reasoning engine needs column names to interpret cell values.

  HEADING INTEGRATION
    When a TextBlock has heading_level is not None, its text is used as
    the heading_text for all subsequent chunks from that block and any
    body blocks that follow, until the next heading of equal or higher
    level is encountered. This builds the section_path correctly.

  CITATION INTEGRITY
    Every DocumentChunk must have a non-empty source_citation.
    The citation is built from the source document metadata:
      - For PDF/DOCX: filename + page_number (if available) + section_path
      - For PPTX: filename + slide_number + section_path
      - For XLSX: filename + sheet_name
    The `citation_is_valid` check is run on every chunk before it is
    added to the output. A chunk with an invalid citation is logged as
    an error and skipped — it cannot enter the evidence chain.

  OVERLAP
    Overlap is implemented by retaining the last CHUNK_OVERLAP_TOKENS
    worth of text from the closed chunk and prepending it to the next
    chunk. Overlap is marked with overlap_with_prev=True on the new
    chunk and overlap_with_next=True on the closed chunk.

    Overlap is NOT applied across heading boundaries — a new heading
    starts a fresh chunk with no overlap from the previous section.

  MINIMUM CHUNK SIZE
    Chunks with fewer than CHUNK_MIN_TOKENS tokens are merged forward
    into the next chunk rather than emitted as standalone chunks. If
    there is no next chunk (end of document), short trailing chunks
    are emitted as-is to preserve completeness.

Output: list[DocumentChunk] — ordered by document position.
        Every chunk has a non-empty source_citation.
        chunk_id is a fresh UUID for every chunk.
        embedding_vector is None — set by the embedding service.
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import UUID, uuid4

from packages.core.constants import (
    CHUNK_MAX_TABLE_TOKENS,
    CHUNK_MIN_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    TABLE_ROW_GROUP_SIZE,
)
from packages.core.enums import ChunkType
from packages.core.schemas.document import (
    DocumentChunk,
    ExtractedTable,
    NormalizedDocument,
    TextBlock,
)
from packages.core.utils.citations import (
    build_document_citation,
    build_system_citation,
    citation_is_valid,
)
from packages.core.utils.tokens import count_tokens, truncate_to_tokens

logger = logging.getLogger(__name__)

# Sentence boundary pattern: split after . ! ? followed by whitespace or end
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_document(document: NormalizedDocument) -> list[DocumentChunk]:
    """
    Convert a NormalizedDocument into a list of DocumentChunks.

    Args:
        document: NormalizedDocument produced by any normalizer.

    Returns:
        Ordered list of DocumentChunks ready for embedding.
        Every chunk has a valid source_citation.
        embedding_vector is None on all chunks.
    """
    chunks: list[DocumentChunk] = []

    # ── Text block chunking ───────────────────────────────────────────────────
    section_path: list[str] = []
    pending_text: str = ""          # accumulated text for current chunk
    pending_tokens: int = 0
    pending_page: Optional[int] = None
    pending_slide: Optional[int] = None
    pending_heading: Optional[str] = None
    overlap_text: str = ""          # tail of previous chunk for overlap
    prev_chunk_idx: Optional[int] = None  # index in chunks[] of last emitted chunk

    def _flush(is_heading_boundary: bool = False) -> None:
        """Emit the pending text as a chunk if it has content."""
        nonlocal pending_text, pending_tokens, overlap_text, prev_chunk_idx

        text_to_emit = pending_text.strip()
        if not text_to_emit:
            return

        # Build citation
        citation = _build_text_citation(
            document.metadata.filename,
            document.metadata.file_type,
            pending_page,
            pending_slide,
            section_path,
        )
        if not citation_is_valid(citation):
            logger.error(
                "Chunk skipped — invalid citation for document_id=%s file=%s",
                document.document_id,
                document.metadata.filename,
            )
            pending_text = ""
            pending_tokens = 0
            overlap_text = ""
            return

        # Mark overlap on previous chunk
        if prev_chunk_idx is not None and not is_heading_boundary:
            chunks[prev_chunk_idx] = DocumentChunk(
                **{
                    **chunks[prev_chunk_idx].model_dump(),
                    "overlap_with_next": True,
                }
            )

        # Build the new chunk
        has_overlap = bool(overlap_text) and not is_heading_boundary
        chunk = DocumentChunk(
            chunk_id=uuid4(),
            document_id=document.document_id,
            engagement_id=document.engagement_id,
            text=text_to_emit,
            token_count=count_tokens(text_to_emit),
            chunk_type=ChunkType.TEXT,
            page_number=pending_page,
            slide_number=pending_slide,
            section_path=list(section_path),
            heading_text=pending_heading,
            overlap_with_prev=has_overlap,
            overlap_with_next=False,
            source_citation=citation,
            embedding_vector=None,
        )
        chunks.append(chunk)
        prev_chunk_idx = len(chunks) - 1

        # Compute overlap tail for next chunk
        if not is_heading_boundary:
            overlap_text = _extract_overlap_tail(text_to_emit)
        else:
            overlap_text = ""

        pending_text = ""
        pending_tokens = 0

    def _start_chunk(seed_text: str = "") -> None:
        """Start a new chunk, optionally seeded with overlap text."""
        nonlocal pending_text, pending_tokens
        if overlap_text and seed_text:
            combined = overlap_text + " " + seed_text
            pending_text = combined
            pending_tokens = count_tokens(combined)
        elif overlap_text:
            pending_text = overlap_text
            pending_tokens = count_tokens(overlap_text)
        else:
            pending_text = seed_text
            pending_tokens = count_tokens(seed_text)

    for block in document.text_blocks:
        # Skip placeholders and speaker notes for chunking
        # (notes are extracted separately as claim candidates,
        #  placeholders signal OCR-required pages)
        if block.is_placeholder or block.is_speaker_notes:
            continue

        # Update section path on heading blocks
        if block.heading_level is not None:
            # Flush current chunk at heading boundary (no overlap across sections)
            if pending_text.strip():
                _flush(is_heading_boundary=True)

            # Update section path
            level = block.heading_level
            if level == 1:
                section_path = [block.text]
            elif level == 2:
                section_path = [section_path[0]] + [block.text] if section_path else [block.text]
            else:  # level 3+
                section_path = section_path[:2] + [block.text] if len(section_path) >= 2 else section_path + [block.text]
            pending_heading = block.text

            # Heading text itself becomes a very short chunk or prepended
            # to the next body chunk. We add it to pending_text as a seed.
            overlap_text = ""
            _start_chunk(block.text)
            pending_page = block.page_number
            pending_slide = block.slide_number
            continue

        # Update location tracking
        if block.page_number is not None:
            pending_page = block.page_number
        if block.slide_number is not None:
            pending_slide = block.slide_number

        # Split block text into sentences and accumulate
        sentences = _split_sentences(block.text)
        for sentence in sentences:
            sentence_tokens = count_tokens(sentence)

            # Single sentence larger than target — emit it alone
            if sentence_tokens >= CHUNK_TARGET_TOKENS:
                if pending_text.strip():
                    _flush()
                    _start_chunk()
                pending_text = (overlap_text + " " + sentence).strip() if overlap_text else sentence
                pending_tokens = count_tokens(pending_text)
                _flush()
                _start_chunk()
                continue

            # Adding this sentence would exceed target — flush first
            if pending_tokens + sentence_tokens > CHUNK_TARGET_TOKENS and pending_tokens >= CHUNK_MIN_TOKENS:
                _flush()
                _start_chunk(sentence)
                pending_page = block.page_number
                pending_slide = block.slide_number
            else:
                # Accumulate
                if pending_text:
                    pending_text = pending_text + " " + sentence
                else:
                    pending_text = (overlap_text + " " + sentence).strip() if overlap_text else sentence
                pending_tokens = count_tokens(pending_text)

    # Flush any remaining text
    if pending_text.strip():
        _flush()

    # ── Table chunking ────────────────────────────────────────────────────────
    for table in document.tables:
        table_chunks = _chunk_table(
            table,
            document.document_id,
            document.engagement_id,
            document.metadata.filename,
            document.metadata.file_type,
        )
        chunks.extend(table_chunks)

    return chunks


# ─── Table chunking ───────────────────────────────────────────────────────────

def _chunk_table(
    table: ExtractedTable,
    document_id: UUID,
    engagement_id: UUID,
    filename: str,
    file_type: str,
) -> list[DocumentChunk]:
    """
    Convert an ExtractedTable into one or more DocumentChunks.

    If the full table fits within CHUNK_MAX_TABLE_TOKENS, one chunk.
    Otherwise split into row groups of TABLE_ROW_GROUP_SIZE rows each,
    with the header prepended to every group.
    """
    if not table.rows and not table.headers:
        return []

    citation = _build_table_citation(filename, file_type, table)
    if not citation_is_valid(citation):
        logger.error(
            "Table chunk skipped — invalid citation for %s sheet=%s",
            filename,
            table.sheet_name,
        )
        return []

    full_text = _table_to_text(table.headers, table.rows)
    full_tokens = count_tokens(full_text)

    if full_tokens <= CHUNK_MAX_TABLE_TOKENS:
        # Entire table fits in one chunk
        return [DocumentChunk(
            chunk_id=uuid4(),
            document_id=document_id,
            engagement_id=engagement_id,
            text=full_text,
            token_count=full_tokens,
            chunk_type=ChunkType.TABLE,
            page_number=table.page_number,
            slide_number=None,
            section_path=[],
            heading_text=None,
            overlap_with_prev=False,
            overlap_with_next=False,
            parent_table_id=table.table_id,
            source_citation=citation,
            embedding_vector=None,
        )]

    # Split into row groups
    chunks: list[DocumentChunk] = []
    row_groups = _split_into_groups(table.rows, TABLE_ROW_GROUP_SIZE)

    for group_idx, row_group in enumerate(row_groups):
        group_text = _table_to_text(table.headers, row_group)
        group_tokens = count_tokens(group_text)

        group_citation = citation + f", rows {group_idx * TABLE_ROW_GROUP_SIZE + 1}–{group_idx * TABLE_ROW_GROUP_SIZE + len(row_group)}"

        chunks.append(DocumentChunk(
            chunk_id=uuid4(),
            document_id=document_id,
            engagement_id=engagement_id,
            text=group_text,
            token_count=group_tokens,
            chunk_type=ChunkType.TABLE,
            page_number=table.page_number,
            slide_number=None,
            section_path=[],
            heading_text=None,
            overlap_with_prev=False,
            overlap_with_next=False,
            parent_table_id=table.table_id,
            source_citation=group_citation,
            embedding_vector=None,
        ))

    return chunks


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences on . ! ? followed by whitespace.
    Returns a list with at least one element.
    Filters out empty strings.
    """
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _extract_overlap_tail(text: str) -> str:
    """
    Extract the last CHUNK_OVERLAP_TOKENS worth of text from a chunk.
    Used to seed the next chunk for overlap.
    Returns empty string if text is shorter than CHUNK_OVERLAP_TOKENS.
    """
    total_tokens = count_tokens(text)
    if total_tokens <= CHUNK_OVERLAP_TOKENS:
        return ""
    words = text.split()
    # Take words from the end until we have approximately CHUNK_OVERLAP_TOKENS
    tail_words: list[str] = []
    tail_tokens = 0
    for word in reversed(words):
        word_tokens = count_tokens(word)
        if tail_tokens + word_tokens > CHUNK_OVERLAP_TOKENS:
            break
        tail_words.insert(0, word)
        tail_tokens += word_tokens
    return " ".join(tail_words)


def _table_to_text(headers: list[str], rows: list[list[str]]) -> str:
    """
    Convert table headers and rows to a pipe-delimited text representation.

    Format:
        col1 | col2 | col3
        ---
        val1 | val2 | val3
        val4 | val5 | val6

    The header separator line (---) helps the embedding model distinguish
    the header row from data rows.
    """
    lines: list[str] = []
    if headers:
        lines.append(" | ".join(str(h) for h in headers))
        lines.append("---")
    for row in rows:
        lines.append(" | ".join(str(c) for c in row))
    return "\n".join(lines)


def _split_into_groups(
    rows: list[list[str]],
    group_size: int,
) -> list[list[list[str]]]:
    """Split a list of rows into groups of at most group_size rows."""
    return [rows[i:i + group_size] for i in range(0, len(rows), group_size)]


def _build_text_citation(
    filename: str,
    file_type: str,
    page_number: Optional[int],
    slide_number: Optional[int],
    section_path: list[str],
) -> str:
    """Build a source citation for a text block chunk."""
    return build_document_citation(
        filename=filename,
        page_number=page_number if file_type in ("pdf", "docx") else None,
        slide_number=slide_number if file_type == "pptx" else None,
        section_path=section_path if section_path else None,
    )


def _build_table_citation(
    filename: str,
    file_type: str,
    table: ExtractedTable,
) -> str:
    """Build a source citation for a table chunk."""
    return build_document_citation(
        filename=filename,
        page_number=table.page_number,
        sheet_name=table.sheet_name if file_type == "xlsx" else None,
        section_path=None,
    )
