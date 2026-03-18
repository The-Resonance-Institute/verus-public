"""
PDF Normalization.

Handles three PDF categories:
  1. Native PDF  — text layer present, extracted with pdfplumber
  2. Scanned PDF — image-only pages, requires OCR (Textract in prod, stub here)
  3. Mixed PDF   — some pages native, some scanned

Output: NormalizedDocument with TextBlocks and ExtractedTables.

Heading detection: font size >= 14pt is a heading candidate.
  >= 18pt → H1, >= 16pt → H2, >= 14pt → H3, else body

Table validation: after extraction, every table must have consistent
column counts. Malformed tables (inconsistent column counts) are
converted to raw text and passed as TextBlocks rather than ExtractedTables.
"""
from __future__ import annotations

import io
import logging
from typing import Optional
from uuid import UUID, uuid4

import pdfplumber
from pdfplumber.page import Page

from packages.core.schemas.document import (
    DocumentChunk,
    DocumentMetadata,
    ExtractedTable,
    NormalizedDocument,
    TextBlock,
)
from packages.core.utils.citations import build_document_citation

logger = logging.getLogger(__name__)

# Font size thresholds for heading detection
_H1_PT = 18.0
_H2_PT = 16.0
_H3_PT = 14.0


def normalize_pdf(
    content: bytes,
    document_id: UUID,
    engagement_id: UUID,
    filename: str,
    vdr_folder_path: Optional[str] = None,
) -> NormalizedDocument:
    """
    Normalize a PDF file to a NormalizedDocument.

    Args:
        content:          Raw PDF bytes.
        document_id:      UUID of the document record.
        engagement_id:    UUID of the engagement.
        filename:         Original filename (used in citations).
        vdr_folder_path:  Optional VDR folder path for metadata.

    Returns:
        NormalizedDocument with all TextBlocks and ExtractedTables.
    """
    text_blocks: list[TextBlock] = []
    tables: list[ExtractedTable] = []
    page_count = 0

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        page_count = len(pdf.pages)

        for page in pdf.pages:
            page_num = page.page_number  # 1-based

            if _page_has_text(page):
                # Native page — extract with pdfplumber
                blocks, page_tables = _extract_native_page(
                    page, document_id, page_num, filename
                )
                text_blocks.extend(blocks)
                tables.extend(page_tables)
            else:
                # Image-only page — OCR stub
                # In production: route to AWS Textract
                # Here: insert placeholder TextBlock
                text_blocks.append(
                    TextBlock(
                        block_id=uuid4(),
                        document_id=document_id,
                        page_number=page_num,
                        heading_level=None,
                        text="[Image-only page — OCR required]",
                        ocr_confidence=None,
                        is_placeholder=True,
                    )
                )
                logger.info(
                    "Page %d of %s is image-only, OCR placeholder inserted",
                    page_num,
                    filename,
                )

    metadata = DocumentMetadata(
        filename=filename,
        file_type="pdf",
        page_count=page_count,
        vdr_folder_path=vdr_folder_path,
        section_path=[],
    )

    return NormalizedDocument(
        document_id=document_id,
        engagement_id=engagement_id,
        text_blocks=text_blocks,
        tables=tables,
        metadata=metadata,
    )


# ─── Private helpers ──────────────────────────────────────────────────────────

def _page_has_text(page: Page) -> bool:
    """Return True if the page has a text layer (not image-only)."""
    text = page.extract_text()
    return bool(text and text.strip())


def _extract_native_page(
    page: Page,
    document_id: UUID,
    page_num: int,
    filename: str,
) -> tuple[list[TextBlock], list[ExtractedTable]]:
    """
    Extract TextBlocks and ExtractedTables from a native (text-layer) PDF page.

    Strategy:
    1. Extract tables first (pdfplumber table detection).
    2. Extract words with font size to detect headings.
    3. Assemble text into lines, classify each line as heading or body.
    """
    text_blocks: list[TextBlock] = []
    tables: list[ExtractedTable] = []

    # ── Tables ────────────────────────────────────────────────────────────────
    raw_tables = page.extract_tables()
    for raw_table in (raw_tables or []):
        table = _build_extracted_table(raw_table, document_id, page_num)
        if table is not None:
            tables.append(table)
        else:
            # Malformed table — convert to raw text block
            flat = _flatten_table_to_text(raw_table)
            if flat:
                text_blocks.append(
                    TextBlock(
                        block_id=uuid4(),
                        document_id=document_id,
                        page_number=page_num,
                        heading_level=None,
                        text=flat,
                    )
                )

    # ── Text (headings + body) ────────────────────────────────────────────────
    # Use extract_words to get font size per word for heading detection
    words = page.extract_words(extra_attrs=["size", "fontname"])
    if not words:
        return text_blocks, tables

    # Group words into lines by their top-y coordinate (within 2pt tolerance)
    lines = _group_words_into_lines(words)
    for line_words in lines:
        text = " ".join(w["text"] for w in line_words)
        if not text.strip():
            continue
        avg_size = _average_font_size(line_words)
        heading_level = _classify_heading(avg_size)
        text_blocks.append(
            TextBlock(
                block_id=uuid4(),
                document_id=document_id,
                page_number=page_num,
                heading_level=heading_level,
                text=text.strip(),
            )
        )

    return text_blocks, tables


def _build_extracted_table(
    raw_table: list[list[Optional[str]]],
    document_id: UUID,
    page_num: int,
) -> Optional[ExtractedTable]:
    """
    Convert a raw pdfplumber table to ExtractedTable.

    Returns None if the table is malformed (inconsistent column counts).
    A table is malformed if any row has a different number of cells
    than the first non-empty row.
    """
    if not raw_table:
        return None

    # Filter out completely empty rows
    non_empty = [row for row in raw_table if any(c for c in row)]
    if not non_empty:
        return None

    expected_cols = len(non_empty[0])

    # Validate consistency
    for row in non_empty[1:]:
        if len(row) != expected_cols:
            logger.debug(
                "Malformed table on page %d: inconsistent column counts", page_num
            )
            return None  # Caller will convert to text

    # Clean cells: None → ""
    cleaned = [[str(c) if c is not None else "" for c in row] for row in non_empty]

    headers = cleaned[0]
    rows = cleaned[1:]

    return ExtractedTable(
        table_id=uuid4(),
        document_id=document_id,
        page_number=page_num,
        headers=headers,
        rows=rows,
        table_type="generic",
        is_sampled=False,
        is_malformed=False,
    )


def _flatten_table_to_text(
    raw_table: list[list[Optional[str]]]
) -> str:
    """Convert a malformed table to a flat text representation."""
    lines = []
    for row in raw_table:
        cells = [str(c) if c is not None else "" for c in row]
        line = "  |  ".join(c for c in cells if c)
        if line:
            lines.append(line)
    return "\n".join(lines)


def _group_words_into_lines(
    words: list[dict],
    tolerance: float = 2.0,
) -> list[list[dict]]:
    """
    Group words into lines by their vertical (top) position.
    Words within `tolerance` points of each other are on the same line.
    Returns lines sorted top-to-bottom, words sorted left-to-right within each line.
    """
    if not words:
        return []

    # Sort words by top position, then left position
    sorted_words = sorted(words, key=lambda w: (w.get("top", 0), w.get("x0", 0)))

    lines: list[list[dict]] = []
    current_line: list[dict] = [sorted_words[0]]
    current_top = sorted_words[0].get("top", 0)

    for word in sorted_words[1:]:
        word_top = word.get("top", 0)
        if abs(word_top - current_top) <= tolerance:
            current_line.append(word)
        else:
            lines.append(current_line)
            current_line = [word]
            current_top = word_top

    if current_line:
        lines.append(current_line)

    return lines


def _average_font_size(line_words: list[dict]) -> float:
    """Compute average font size across words in a line."""
    sizes = [w.get("size", 0) for w in line_words if w.get("size")]
    if not sizes:
        return 0.0
    return sum(sizes) / len(sizes)


def _classify_heading(avg_size: float) -> Optional[int]:
    """
    Classify a line's heading level based on average font size.
    Returns 1, 2, 3, or None (body text).
    """
    if avg_size >= _H1_PT:
        return 1
    if avg_size >= _H2_PT:
        return 2
    if avg_size >= _H3_PT:
        return 3
    return None
