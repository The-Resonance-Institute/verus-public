"""
DOCX Normalization.

Handles Microsoft Word documents (.docx format).

Processing rules:
  1. Paragraphs extracted in document order by iterating body XML elements.
  2. Heading levels derived from paragraph pStyle XML element:
       Heading 1 -> level 1,  Heading 2 -> level 2,  Heading 3 -> level 3
  3. Tracked changes resolved to ACCEPTED state:
     - Text inside <w:del> elements is EXCLUDED (deleted text).
     - Text inside <w:ins> elements IS included (accepted insertion).
  4. Tables extracted as ExtractedTable objects.
  5. Comments extracted as TextBlocks with is_comment=True.
  6. Empty paragraphs skipped.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID, uuid4

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table as DocxTable

from packages.core.schemas.document import (
    DocumentMetadata,
    ExtractedTable,
    NormalizedDocument,
    TextBlock,
)

logger = logging.getLogger(__name__)

_TAG_P      = qn("w:p")
_TAG_TBL    = qn("w:tbl")
_TAG_T      = qn("w:t")
_TAG_DEL    = qn("w:del")
_TAG_PPR    = qn("w:pPr")
_TAG_PSTYLE = qn("w:pStyle")
_TAG_VAL    = qn("w:val")

_HEADING_LEVELS: dict[str, int] = {
    "heading1": 1, "heading 1": 1,
    "heading2": 2, "heading 2": 2,
    "heading3": 3, "heading 3": 3,
}


def normalize_docx(
    content: bytes,
    document_id: UUID,
    engagement_id: UUID,
    filename: str,
    vdr_folder_path: Optional[str] = None,
) -> NormalizedDocument:
    """Normalize a DOCX file to a NormalizedDocument."""
    import io
    doc = Document(io.BytesIO(content))

    text_blocks: list[TextBlock] = []
    tables: list[ExtractedTable] = []

    for child in doc.element.body:
        tag = child.tag
        if tag == _TAG_P:
            block = _extract_paragraph(child, document_id)
            if block is not None:
                text_blocks.append(block)
        elif tag == _TAG_TBL:
            table = DocxTable(child, doc.element.body)
            extracted = _extract_table(table, document_id)
            if extracted is not None:
                tables.append(extracted)

    text_blocks.extend(_extract_comments(doc, document_id))

    return NormalizedDocument(
        document_id=document_id,
        engagement_id=engagement_id,
        text_blocks=text_blocks,
        tables=tables,
        metadata=DocumentMetadata(
            filename=filename,
            file_type="docx",
            page_count=None,
            vdr_folder_path=vdr_folder_path,
            section_path=[],
        ),
    )


def _extract_paragraph(p_elem, document_id: UUID) -> Optional[TextBlock]:
    """Extract a TextBlock from a paragraph XML element."""
    text = _get_accepted_text(p_elem)
    if not text:
        return None
    return TextBlock(
        block_id=uuid4(),
        document_id=document_id,
        page_number=None,
        heading_level=_get_heading_level(p_elem),
        text=text,
    )


def _get_accepted_text(p_elem) -> str:
    """
    Return paragraph text after tracked changes are accepted.
    Walks all <w:t> descendants, excluding any inside <w:del> ancestors.
    """
    parts: list[str] = []
    for el in p_elem.iter():
        if el.tag != _TAG_T:
            continue
        if _has_del_ancestor(el, p_elem):
            continue
        if el.text:
            parts.append(el.text)
    return "".join(parts).strip()


def _has_del_ancestor(el, stop_at) -> bool:
    """Return True if el has a <w:del> ancestor before reaching stop_at."""
    parent = el.getparent()
    while parent is not None and parent is not stop_at:
        if parent.tag == _TAG_DEL:
            return True
        parent = parent.getparent()
    return False


def _get_heading_level(p_elem) -> Optional[int]:
    """Derive heading level from paragraph pStyle XML attribute."""
    pPr = p_elem.find(_TAG_PPR)
    if pPr is None:
        return None
    pStyle = pPr.find(_TAG_PSTYLE)
    if pStyle is None:
        return None
    style_val = pStyle.get(_TAG_VAL, "")
    return _HEADING_LEVELS.get(style_val.lower().strip())


def _extract_table(table: DocxTable, document_id: UUID) -> Optional[ExtractedTable]:
    """Extract an ExtractedTable from a python-docx Table object."""
    if not table.rows:
        return None

    raw_rows: list[list[str]] = []
    for row in table.rows:
        raw_rows.append([cell.text.strip() for cell in row.cells])

    if not raw_rows:
        return None

    expected_cols = len(raw_rows[0])
    if expected_cols == 0:
        return None

    clean_rows = [r for r in raw_rows if len(r) == expected_cols]
    if not clean_rows:
        return None

    headers = clean_rows[0]
    if not any(h.strip() for h in headers):
        return None

    return ExtractedTable(
        table_id=uuid4(),
        document_id=document_id,
        page_number=None,
        headers=headers,
        rows=clean_rows[1:],
        table_type="generic",
        is_sampled=False,
        is_malformed=False,
    )


def _extract_comments(doc: Document, document_id: UUID) -> list[TextBlock]:
    """Extract Word comments as TextBlocks with is_comment=True."""
    blocks: list[TextBlock] = []
    try:
        comments_part = doc.part.comments_part
        if comments_part is None:
            return []
        for comment_el in comments_part._element.findall(qn("w:comment")):
            parts = [
                t.text for p in comment_el.findall(f".//{qn('w:p')}")
                for t in p.findall(f".//{qn('w:t')}")
                if t.text
            ]
            text = " ".join(parts).strip()
            if text:
                blocks.append(TextBlock(
                    block_id=uuid4(),
                    document_id=document_id,
                    page_number=None,
                    heading_level=None,
                    text=text,
                    is_comment=True,
                ))
    except Exception as exc:
        logger.debug("Could not extract comments: %s", exc)
    return blocks
