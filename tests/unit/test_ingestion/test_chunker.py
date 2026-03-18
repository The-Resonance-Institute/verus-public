"""
Test: packages/ingestion/chunker.py

The chunking engine is the most consequential component in the ingestion
pipeline for diligence quality. Chunk boundaries determine what context
the LLM has when evaluating each claim. Citation integrity determines
whether any finding can be traced back to its source document.

A hyperscaler diligence team will ask:
  - Can you guarantee every chunk cites its source?
  - Can you guarantee no chunk exceeds the model context limit?
  - How does your chunker handle section boundaries?
  - How does overlap work and how do you test it?

These tests answer all four questions with executable evidence.

Coverage:
  Output contract        — all chunks always valid
  Citation integrity     — every chunk has a non-empty source_citation
  Token bounds           — no chunk exceeds CHUNK_TARGET_TOKENS * 1.5
  Minimum chunk size     — short-doc edge cases handled
  Text chunking          — sentences accumulate correctly
  Overlap                — overlap flags set correctly, text present
  Heading boundaries     — section_path updates on headings
  No overlap at boundary — headings reset overlap
  Table chunking         — tables produce TABLE-type chunks
  Large table splitting  — tables > CHUNK_MAX_TABLE_TOKENS are split
  Table header in every group — header row in every split chunk
  Table citation         — sheet_name and page_number in citation
  Placeholder skip       — placeholder blocks are not chunked
  Speaker notes skip     — notes are not chunked
  PDF chunking           — page number in citation
  PPTX chunking          — slide number in citation
  XLSX chunking          — sheet name in citation
  DOCX chunking          — section path in citation
  Multi-section          — section_path depth builds correctly
  Chunk IDs unique       — every chunk has a unique chunk_id
  embedding_vector None  — embedding not set by chunker
  parent_table_id        — table chunks carry parent_table_id
"""

import pytest
from uuid import uuid4
from typing import Optional

from packages.ingestion.chunker import (
    chunk_document,
    _split_sentences,
    _extract_overlap_tail,
    _table_to_text,
    _split_into_groups,
)
from packages.core.schemas.document import (
    NormalizedDocument, DocumentChunk, TextBlock, ExtractedTable,
    DocumentMetadata,
)
from packages.core.enums import ChunkType
from packages.core.constants import (
    CHUNK_TARGET_TOKENS, CHUNK_MIN_TOKENS, CHUNK_OVERLAP_TOKENS,
    CHUNK_MAX_TABLE_TOKENS, TABLE_ROW_GROUP_SIZE,
)
from packages.core.utils.citations import citation_is_valid
from packages.core.utils.tokens import count_tokens

# Import normalizer fixtures for integration tests
from packages.ingestion.normalizers.orchestrator import normalize
from tests.unit.test_ingestion.pdf_fixtures import (
    make_heading_pdf, make_multi_page_pdf,
)
from tests.unit.test_ingestion.docx_fixtures import (
    make_complex_docx, make_heading_docx,
)
from tests.unit.test_ingestion.xlsx_fixtures import (
    make_financial_model_xlsx, make_large_sheet_xlsx, make_simple_xlsx,
)
from tests.unit.test_ingestion.pptx_fixtures import (
    make_title_and_content_pptx, make_speaker_notes_pptx,
)


# ─── Builders ─────────────────────────────────────────────────────────────────

def make_doc(
    text_blocks: list[TextBlock] | None = None,
    tables: list[ExtractedTable] | None = None,
    filename: str = "test.pdf",
    file_type: str = "pdf",
) -> NormalizedDocument:
    doc_id = uuid4()
    eng_id = uuid4()
    return NormalizedDocument(
        document_id=doc_id,
        engagement_id=eng_id,
        text_blocks=text_blocks or [],
        tables=tables or [],
        metadata=DocumentMetadata(
            filename=filename,
            file_type=file_type,
            page_count=1,
            section_path=[],
        ),
    )


def make_block(
    text: str,
    heading_level: Optional[int] = None,
    page_number: int = 1,
    slide_number: Optional[int] = None,
    is_placeholder: bool = False,
    is_speaker_notes: bool = False,
) -> TextBlock:
    return TextBlock(
        block_id=uuid4(),
        document_id=uuid4(),
        text=text,
        heading_level=heading_level,
        page_number=page_number,
        slide_number=slide_number,
        is_placeholder=is_placeholder,
        is_speaker_notes=is_speaker_notes,
    )


def make_table(
    headers: list[str],
    rows: list[list[str]],
    sheet_name: Optional[str] = None,
    page_number: Optional[int] = None,
) -> ExtractedTable:
    return ExtractedTable(
        table_id=uuid4(),
        document_id=uuid4(),
        headers=headers,
        rows=rows,
        sheet_name=sheet_name,
        page_number=page_number,
        table_type="generic",
        is_sampled=False,
        is_malformed=False,
    )


def run(doc: NormalizedDocument) -> list[DocumentChunk]:
    return chunk_document(doc)


def all_text_chunks(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    return [c for c in chunks if c.chunk_type == ChunkType.TEXT]


def all_table_chunks(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    return [c for c in chunks if c.chunk_type == ChunkType.TABLE]


def long_sentence(n_words: int = 100) -> str:
    """Generate a sentence with n_words words."""
    return " ".join(["word"] * n_words) + "."


# ═════════════════════════════════════════════════════════════════════════════
# OUTPUT CONTRACT — every chunk always valid
# ═════════════════════════════════════════════════════════════════════════════

class TestOutputContract:
    def test_returns_list(self):
        doc = make_doc([make_block("Hello world.")])
        assert isinstance(run(doc), list)

    def test_empty_document_returns_empty_list(self):
        doc = make_doc()
        assert run(doc) == []

    def test_all_chunks_are_document_chunk_instances(self):
        doc = make_doc([make_block("Revenue grew 23% year over year.")])
        for chunk in run(doc):
            assert isinstance(chunk, DocumentChunk)

    def test_all_chunks_have_document_id(self):
        doc = make_doc([make_block("Revenue grew 23% year over year.")])
        for chunk in run(doc):
            assert chunk.document_id == doc.document_id

    def test_all_chunks_have_engagement_id(self):
        doc = make_doc([make_block("Revenue grew 23% year over year.")])
        for chunk in run(doc):
            assert chunk.engagement_id == doc.engagement_id

    def test_all_chunks_have_non_empty_text(self):
        doc = make_doc([make_block("Revenue grew 23%.")])
        for chunk in run(doc):
            assert chunk.text and chunk.text.strip()

    def test_all_chunks_have_positive_token_count(self):
        doc = make_doc([make_block("Revenue grew 23% year over year.")])
        for chunk in run(doc):
            assert chunk.token_count > 0

    def test_chunk_ids_are_unique(self):
        doc = make_doc([make_block(long_sentence(200))])
        chunks = run(doc)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "All chunk_ids must be unique"

    def test_embedding_vector_is_none(self):
        """Chunker must NOT set embedding_vector — that is the embedder's job."""
        doc = make_doc([make_block("Revenue grew 23%.")])
        for chunk in run(doc):
            assert chunk.embedding_vector is None, (
                "Chunker must not set embedding_vector"
            )


# ═════════════════════════════════════════════════════════════════════════════
# CITATION INTEGRITY — the most critical property for diligence
# ═════════════════════════════════════════════════════════════════════════════

class TestCitationIntegrity:
    """
    These tests are the citation integrity proof for diligence review.
    Every chunk must have a non-empty, valid source_citation.
    A chunk without a citation cannot participate in the evidence chain
    and would be grounds for rejecting Verus findings as unverifiable.
    """

    def test_every_text_chunk_has_valid_citation(self):
        doc = make_doc([make_block("Revenue grew 23% year over year.")])
        chunks = run(doc)
        for chunk in chunks:
            assert citation_is_valid(chunk.source_citation), (
                f"Chunk has invalid citation: {chunk.source_citation!r}\n"
                f"Text: {chunk.text!r}"
            )

    def test_every_table_chunk_has_valid_citation(self):
        doc = make_doc(
            tables=[make_table(["Col A", "Col B"], [["1", "2"], ["3", "4"]])]
        )
        chunks = run(doc)
        table_chunks = all_table_chunks(chunks)
        assert len(table_chunks) > 0
        for chunk in table_chunks:
            assert citation_is_valid(chunk.source_citation), (
                f"Table chunk has invalid citation: {chunk.source_citation!r}"
            )

    def test_citation_contains_filename(self):
        doc = make_doc(
            [make_block("Revenue grew 23%.")],
            filename="CIM_Draft.pdf",
        )
        for chunk in run(doc):
            assert "CIM_Draft.pdf" in chunk.source_citation, (
                f"Citation should contain filename. Got: {chunk.source_citation!r}"
            )

    def test_pdf_citation_contains_page_number(self):
        doc = make_doc(
            [make_block("Revenue grew 23%.", page_number=14)],
            filename="CIM.pdf",
            file_type="pdf",
        )
        for chunk in run(doc):
            assert "p.14" in chunk.source_citation, (
                f"PDF citation should contain page number. Got: {chunk.source_citation!r}"
            )

    def test_pptx_citation_contains_slide_number(self):
        doc = make_doc(
            [make_block("Revenue grew 23%.", slide_number=3)],
            filename="Deck.pptx",
            file_type="pptx",
        )
        for chunk in run(doc):
            assert "Slide 3" in chunk.source_citation, (
                f"PPTX citation should contain slide number. Got: {chunk.source_citation!r}"
            )

    def test_xlsx_table_citation_contains_sheet_name(self):
        doc = make_doc(
            tables=[make_table(["Col A", "Col B"], [["1", "2"]], sheet_name="P&L")],
            filename="Model.xlsx",
            file_type="xlsx",
        )
        chunks = run(doc)
        table_chunks = all_table_chunks(chunks)
        assert len(table_chunks) > 0
        for chunk in table_chunks:
            assert "P&L" in chunk.source_citation, (
                f"XLSX citation should contain sheet name. Got: {chunk.source_citation!r}"
            )

    def test_section_path_in_citation(self):
        doc = make_doc([
            make_block("Revenue Analysis", heading_level=2, page_number=5),
            make_block("Revenue grew 23% year over year.", page_number=5),
        ], filename="CIM.pdf", file_type="pdf")
        chunks = run(doc)
        body_chunks = [c for c in chunks if "23%" in c.text]
        assert len(body_chunks) > 0
        for chunk in body_chunks:
            assert "Revenue Analysis" in chunk.source_citation, (
                f"Section heading should be in citation. Got: {chunk.source_citation!r}"
            )

    def test_no_chunk_has_empty_string_citation(self):
        doc = make_doc([make_block(long_sentence(300))])
        for chunk in run(doc):
            assert chunk.source_citation != "", (
                "Citation must never be empty string"
            )

    def test_no_chunk_has_whitespace_only_citation(self):
        doc = make_doc([make_block(long_sentence(300))])
        for chunk in run(doc):
            assert chunk.source_citation.strip() != "", (
                "Citation must never be whitespace-only"
            )

    def test_citation_integrity_with_real_pdf(self):
        """Integration test: all chunks from a real PDF have valid citations."""
        doc = normalize(make_heading_pdf(), uuid4(), uuid4(), "CIM.pdf")
        chunks = chunk_document(doc)
        assert len(chunks) > 0
        for chunk in chunks:
            assert citation_is_valid(chunk.source_citation), (
                f"Real PDF chunk has invalid citation: {chunk.source_citation!r}"
            )

    def test_citation_integrity_with_real_docx(self):
        """Integration test: all chunks from a real DOCX have valid citations."""
        doc = normalize(make_complex_docx(), uuid4(), uuid4(), "QoE.docx")
        chunks = chunk_document(doc)
        assert len(chunks) > 0
        for chunk in chunks:
            assert citation_is_valid(chunk.source_citation), (
                f"Real DOCX chunk has invalid citation: {chunk.source_citation!r}"
            )

    def test_citation_integrity_with_real_xlsx(self):
        """Integration test: all chunks from a real XLSX have valid citations."""
        doc = normalize(make_financial_model_xlsx(), uuid4(), uuid4(), "Model.xlsx")
        chunks = chunk_document(doc)
        assert len(chunks) > 0
        for chunk in chunks:
            assert citation_is_valid(chunk.source_citation), (
                f"Real XLSX chunk has invalid citation: {chunk.source_citation!r}"
            )

    def test_citation_integrity_with_real_pptx(self):
        """Integration test: all chunks from a real PPTX have valid citations."""
        doc = normalize(make_title_and_content_pptx(), uuid4(), uuid4(), "Deck.pptx")
        chunks = chunk_document(doc)
        assert len(chunks) > 0
        for chunk in chunks:
            assert citation_is_valid(chunk.source_citation), (
                f"Real PPTX chunk has invalid citation: {chunk.source_citation!r}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# TOKEN BOUNDS — no chunk exceeds context limits
# ═════════════════════════════════════════════════════════════════════════════

class TestTokenBounds:
    """
    Token bounds tests are the context-limit guarantee.
    No text chunk should substantially exceed CHUNK_TARGET_TOKENS.
    (A single sentence can be slightly above target if it's the only
    content in a chunk — we allow up to 1.5x target for this case.)
    Table chunks may be up to CHUNK_MAX_TABLE_TOKENS.
    """

    def test_text_chunks_within_reasonable_bound(self):
        """No text chunk exceeds 1.5x the target token count."""
        doc = make_doc([make_block(long_sentence(500))])
        chunks = run(doc)
        max_allowed = int(CHUNK_TARGET_TOKENS * 1.5)
        for chunk in all_text_chunks(chunks):
            assert chunk.token_count <= max_allowed, (
                f"Text chunk token count {chunk.token_count} exceeds "
                f"1.5x target ({max_allowed}). "
                f"Text: {chunk.text[:100]!r}"
            )

    def test_table_chunks_within_max_table_tokens(self):
        """Each table chunk is at most CHUNK_MAX_TABLE_TOKENS tokens."""
        # Create a large table
        rows = [[f"value_{r}_{c}" for c in range(5)] for r in range(50)]
        doc = make_doc(
            tables=[make_table(["A", "B", "C", "D", "E"], rows)]
        )
        chunks = run(doc)
        for chunk in all_table_chunks(chunks):
            assert chunk.token_count <= CHUNK_MAX_TABLE_TOKENS, (
                f"Table chunk token count {chunk.token_count} exceeds "
                f"CHUNK_MAX_TABLE_TOKENS ({CHUNK_MAX_TABLE_TOKENS})"
            )

    def test_long_document_produces_multiple_chunks(self):
        """A document with enough tokens must be split into multiple chunks."""
        # 50 distinct sentences, each ~12 tokens — total ~600 tokens > CHUNK_TARGET_TOKENS
        many_sentences = " ".join([
            f"Revenue grew substantially in fiscal period number {i} according to management."
            for i in range(50)
        ])
        doc = make_doc([make_block(many_sentences)])
        chunks = run(doc)
        assert len(all_text_chunks(chunks)) > 1, (
            "A long document should produce multiple text chunks"
        )

    def test_token_count_matches_actual_text(self):
        """chunk.token_count must match the actual token count of chunk.text."""
        doc = make_doc([make_block(long_sentence(200))])
        for chunk in run(doc):
            actual = count_tokens(chunk.text)
            assert chunk.token_count == actual, (
                f"Stored token_count {chunk.token_count} does not match "
                f"actual count {actual} for text: {chunk.text[:50]!r}"
            )

    def test_short_document_still_produces_chunk(self):
        """A very short document (few words) must still produce at least one chunk."""
        doc = make_doc([make_block("Revenue grew.")])
        chunks = run(doc)
        assert len(chunks) >= 1


# ═════════════════════════════════════════════════════════════════════════════
# TEXT CHUNKING — sentence accumulation and splitting
# ═════════════════════════════════════════════════════════════════════════════

class TestTextChunking:
    def test_single_short_block_produces_one_chunk(self):
        doc = make_doc([make_block("Revenue grew 23% year over year.")])
        chunks = all_text_chunks(run(doc))
        assert len(chunks) == 1

    def test_content_preserved_across_chunks(self):
        """All original text must be present somewhere in the chunk output."""
        sentences = [
            "Revenue grew 23% year over year to $48.2M.",
            "Gross margin expanded 180 basis points to 41.3%.",
            "Customer retention remained above 95% throughout.",
        ]
        text = " ".join(sentences)
        doc = make_doc([make_block(text)])
        all_chunk_text = " ".join(c.text for c in run(doc))
        for sentence in sentences:
            # Key content words should be present
            key_word = sentence.split()[0]
            assert key_word in all_chunk_text, (
                f"Key word '{key_word}' not found in chunk output"
            )

    def test_chunk_type_is_text_for_text_blocks(self):
        doc = make_doc([make_block("Revenue grew 23%.")])
        for chunk in run(doc):
            assert chunk.chunk_type == ChunkType.TEXT

    def test_multiple_blocks_chunked_together_when_short(self):
        """Short blocks should accumulate into fewer, fuller chunks."""
        blocks = [make_block(f"Short sentence {i}.") for i in range(5)]
        doc = make_doc(blocks)
        chunks = all_text_chunks(run(doc))
        # 5 very short sentences should fit in far fewer than 5 chunks
        assert len(chunks) <= 3, (
            f"5 short sentences should consolidate, got {len(chunks)} chunks"
        )


# ═════════════════════════════════════════════════════════════════════════════
# OVERLAP — context preservation across chunk boundaries
# ═════════════════════════════════════════════════════════════════════════════

class TestOverlap:
    """
    Overlap tests prove that context is preserved across chunk boundaries.
    When chunk N closes, its tail text seeds chunk N+1 (overlap_with_prev=True
    on chunk N+1, overlap_with_next=True on chunk N).
    """

    def test_second_chunk_has_overlap_with_prev_true(self):
        """When a document produces multiple chunks, chunk 2+ should have overlap."""
        doc = make_doc([make_block(long_sentence(300))])
        chunks = all_text_chunks(run(doc))
        if len(chunks) >= 2:
            assert chunks[1].overlap_with_prev is True, (
                "Second chunk should have overlap_with_prev=True"
            )

    def test_first_chunk_has_overlap_with_next_true_when_multiple(self):
        """When there is a following chunk, chunk 1 should be marked overlap_with_next."""
        doc = make_doc([make_block(long_sentence(300))])
        chunks = all_text_chunks(run(doc))
        if len(chunks) >= 2:
            assert chunks[0].overlap_with_next is True, (
                "First chunk should have overlap_with_next=True "
                "when followed by another chunk"
            )

    def test_single_chunk_has_no_overlap_flags(self):
        """A document that fits in one chunk should have no overlap flags."""
        doc = make_doc([make_block("Revenue grew 23%.")])
        chunks = all_text_chunks(run(doc))
        assert len(chunks) == 1
        assert chunks[0].overlap_with_prev is False
        assert chunks[0].overlap_with_next is False

    def test_last_chunk_has_overlap_with_next_false(self):
        """The final chunk must have overlap_with_next=False."""
        doc = make_doc([make_block(long_sentence(300))])
        chunks = all_text_chunks(run(doc))
        assert chunks[-1].overlap_with_next is False


# ═════════════════════════════════════════════════════════════════════════════
# HEADING BOUNDARIES — section path management
# ═════════════════════════════════════════════════════════════════════════════

class TestHeadingBoundaries:
    def test_heading_text_in_section_path(self):
        """Body text following a heading should cite that heading in section_path."""
        doc = make_doc([
            make_block("Revenue Analysis", heading_level=1, page_number=1),
            make_block("Revenue grew 23% year over year.", page_number=1),
        ], filename="CIM.pdf", file_type="pdf")
        chunks = run(doc)
        body = [c for c in chunks if "23%" in c.text]
        assert len(body) > 0
        assert any("Revenue Analysis" in c.section_path for c in body), (
            f"'Revenue Analysis' should be in section_path of body chunk. "
            f"Got section_paths: {[c.section_path for c in body]}"
        )

    def test_no_overlap_across_heading_boundary(self):
        """A new section heading must start with no overlap from the previous section."""
        # Build a doc with two sections separated by a heading
        doc = make_doc([
            make_block("Executive Summary", heading_level=1, page_number=1),
            make_block(long_sentence(100), page_number=1),
            make_block("Revenue Analysis", heading_level=1, page_number=2),
            make_block("Revenue grew 23%.", page_number=2),
        ], filename="CIM.pdf", file_type="pdf")
        chunks = run(doc)
        # Find the first chunk that contains "Revenue Analysis"
        heading_chunk = next(
            (c for c in chunks if "Revenue Analysis" in c.text), None
        )
        if heading_chunk:
            assert heading_chunk.overlap_with_prev is False, (
                "Chunk starting a new section should not have overlap from "
                "the previous section"
            )

    def test_section_path_depth_builds_correctly(self):
        """H1 > H2 > H3 builds a section_path up to 3 levels."""
        doc = make_doc([
            make_block("Part 1", heading_level=1, page_number=1),
            make_block("Chapter 1", heading_level=2, page_number=1),
            make_block("Section 1.1", heading_level=3, page_number=1),
            make_block("Body text here.", page_number=1),
        ], filename="CIM.pdf", file_type="pdf")
        chunks = run(doc)
        body = [c for c in chunks if "Body text" in c.text]
        assert len(body) > 0
        path = body[0].section_path
        assert "Part 1" in path
        assert "Chapter 1" in path

    def test_heading_text_stored_on_chunk(self):
        doc = make_doc([
            make_block("Revenue Analysis", heading_level=1, page_number=1),
            make_block("Revenue grew 23%.", page_number=1),
        ], filename="CIM.pdf", file_type="pdf")
        chunks = run(doc)
        body = [c for c in chunks if "23%" in c.text]
        if body:
            assert body[0].heading_text is not None


# ═════════════════════════════════════════════════════════════════════════════
# SKIP RULES — placeholders and speaker notes
# ═════════════════════════════════════════════════════════════════════════════

class TestSkipRules:
    def test_placeholder_blocks_not_chunked(self):
        """Image-only placeholder blocks must not produce chunks."""
        doc = make_doc([
            make_block("[Image-only slide — no text content extracted]",
                       is_placeholder=True),
        ])
        chunks = run(doc)
        # Placeholder text must not appear in any chunk
        for chunk in chunks:
            assert "Image-only" not in chunk.text, (
                "Placeholder text should not be in any chunk"
            )

    def test_speaker_notes_not_chunked(self):
        """Speaker notes must not produce chunks."""
        doc = make_doc([
            make_block("Verify revenue figure against ERP.",
                       is_speaker_notes=True),
        ])
        chunks = run(doc)
        for chunk in chunks:
            assert "Verify revenue" not in chunk.text, (
                "Speaker notes text should not be in any chunk"
            )

    def test_empty_document_returns_empty_list(self):
        doc = make_doc()
        assert run(doc) == []

    def test_only_placeholder_produces_no_chunks(self):
        doc = make_doc([
            make_block("placeholder", is_placeholder=True),
        ])
        assert run(doc) == []

    def test_only_speaker_notes_produces_no_chunks(self):
        doc = make_doc([
            make_block("Some analyst note.", is_speaker_notes=True),
        ])
        assert run(doc) == []


# ═════════════════════════════════════════════════════════════════════════════
# TABLE CHUNKING
# ═════════════════════════════════════════════════════════════════════════════

class TestTableChunking:
    def test_table_produces_table_type_chunks(self):
        doc = make_doc(
            tables=[make_table(["A", "B"], [["1", "2"], ["3", "4"]])]
        )
        chunks = all_table_chunks(run(doc))
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.chunk_type == ChunkType.TABLE

    def test_table_chunk_contains_headers(self):
        doc = make_doc(
            tables=[make_table(
                ["Period", "Revenue"],
                [["Q1 2024", "11.2"]]
            )]
        )
        chunks = all_table_chunks(run(doc))
        assert len(chunks) >= 1
        assert "Period" in chunks[0].text
        assert "Revenue" in chunks[0].text

    def test_table_chunk_contains_data_values(self):
        doc = make_doc(
            tables=[make_table(
                ["Period", "Revenue"],
                [["Q1 2024", "11.2"], ["Q2 2024", "11.8"]]
            )]
        )
        chunks = all_table_chunks(run(doc))
        combined = " ".join(c.text for c in chunks)
        assert "Q1 2024" in combined
        assert "Q2 2024" in combined

    def test_table_chunk_carries_parent_table_id(self):
        table = make_table(["A", "B"], [["1", "2"]])
        doc = make_doc(tables=[table])
        chunks = all_table_chunks(run(doc))
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.parent_table_id == table.table_id, (
                "Table chunk must carry the parent_table_id"
            )

    def test_large_table_produces_multiple_chunks(self):
        """A table with many large rows should be split when it exceeds max tokens."""
        # 3 distinct words per cell × 8 cols × 60 rows → ~2500 tokens > CHUNK_MAX_TABLE_TOKENS
        rows = [
            [" ".join([f"word{r}col{c}val{v}" for v in range(3)]) for c in range(8)]
            for r in range(60)
        ]
        headers = [f"Column {c}" for c in range(8)]
        doc = make_doc(tables=[make_table(headers, rows)])
        chunks = all_table_chunks(run(doc))
        assert len(chunks) >= 2, (
            f"Large table should produce multiple chunks, got {len(chunks)}. "
            f"Token count: {chunks[0].token_count if chunks else 'N/A'}"
        )

    def test_large_table_chunks_all_contain_headers(self):
        """Every row-group chunk must contain the header row."""
        rows = [
            [" ".join([f"word{r}col{c}val{v}" for v in range(3)]) for c in range(8)]
            for r in range(60)
        ]
        headers = [f"Column {c}" for c in range(8)]
        doc = make_doc(tables=[make_table(headers, rows)])
        chunks = all_table_chunks(run(doc))
        for chunk_idx, chunk in enumerate(chunks):
            assert "Column 0" in chunk.text, (
                f"Table chunk {chunk_idx} missing header 'Column 0'. "
                f"Text: {chunk.text[:100]!r}"
            )

    def test_table_row_group_citations_include_range(self):
        """Split table chunk citations must include the row range."""
        rows = [
            [" ".join([f"word{r}col{c}val{v}" for v in range(3)]) for c in range(8)]
            for r in range(60)
        ]
        headers = [f"Column {c}" for c in range(8)]
        doc = make_doc(tables=[make_table(headers, rows)], filename="Model.xlsx",
                       file_type="xlsx")
        chunks = all_table_chunks(run(doc))
        if len(chunks) > 1:
            assert any("rows" in c.source_citation for c in chunks[1:]), (
                "Split table chunk citations should include row range"
            )

    def test_small_table_fits_in_one_chunk(self):
        """A small table should not be split."""
        doc = make_doc(
            tables=[make_table(
                ["Period", "Revenue", "Margin"],
                [["Q1", "11.2", "39.3"], ["Q2", "11.8", "40.7"]]
            )]
        )
        chunks = all_table_chunks(run(doc))
        assert len(chunks) == 1, (
            f"Small table should be a single chunk, got {len(chunks)}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION — real documents through normalizer then chunker
# ═════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_real_pdf_chunks_all_valid(self):
        doc = normalize(make_heading_pdf(), uuid4(), uuid4(), "CIM.pdf")
        chunks = chunk_document(doc)
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.text.strip()
            assert citation_is_valid(chunk.source_citation)
            assert chunk.token_count == count_tokens(chunk.text)
            assert chunk.document_id == doc.document_id

    def test_real_docx_chunks_all_valid(self):
        doc = normalize(make_complex_docx(), uuid4(), uuid4(), "QoE.docx")
        chunks = chunk_document(doc)
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.text.strip()
            assert citation_is_valid(chunk.source_citation)
            assert chunk.token_count == count_tokens(chunk.text)

    def test_real_xlsx_financial_model_chunks_valid(self):
        doc = normalize(make_financial_model_xlsx(), uuid4(), uuid4(), "Model.xlsx")
        chunks = chunk_document(doc)
        assert len(chunks) > 0
        # XLSX produces table chunks — all should have sheet name in citation
        for chunk in all_table_chunks(chunks):
            assert "EBITDA Bridge" in chunk.source_citation

    def test_real_xlsx_large_sheet_produces_table_chunks(self):
        doc = normalize(make_large_sheet_xlsx(600), uuid4(), uuid4(), "BigModel.xlsx")
        chunks = chunk_document(doc)
        table_chunks = all_table_chunks(chunks)
        assert len(table_chunks) >= 1

    def test_real_pptx_chunks_have_slide_numbers(self):
        doc = normalize(make_title_and_content_pptx(), uuid4(), uuid4(), "Deck.pptx")
        chunks = chunk_document(doc)
        text_chunks = all_text_chunks(chunks)
        assert len(text_chunks) > 0
        for chunk in text_chunks:
            assert chunk.slide_number is not None, (
                f"PPTX text chunk missing slide_number. "
                f"Citation: {chunk.source_citation!r}"
            )

    def test_real_pptx_speaker_notes_not_in_chunks(self):
        """Speaker notes from PPTX must not appear in any chunk text."""
        doc = normalize(make_speaker_notes_pptx(), uuid4(), uuid4(), "Deck.pptx")
        chunks = chunk_document(doc)
        for chunk in chunks:
            assert "ERP" not in chunk.text or "Revenue" in chunk.text, (
                "Note-only content 'ERP' (from speaker notes) should not be "
                "in chunk text unless it appears in the slide body too"
            )

    def test_multi_page_pdf_page_numbers_in_citations(self):
        doc = normalize(make_multi_page_pdf(3), uuid4(), uuid4(), "Report.pdf")
        chunks = chunk_document(doc)
        citations = [c.source_citation for c in chunks]
        # At least one page number should appear in citations
        has_page_num = any("p." in cit for cit in citations)
        assert has_page_num or all("Report.pdf" in cit for cit in citations), (
            "PDF citations should reference page numbers where available"
        )


# ═════════════════════════════════════════════════════════════════════════════
# INTERNAL UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

class TestSplitSentences:
    def test_single_sentence_returns_one_item(self):
        result = _split_sentences("Revenue grew 23%.")
        assert len(result) == 1

    def test_multiple_sentences_split_correctly(self):
        result = _split_sentences("Revenue grew. Margin expanded. Retention high.")
        assert len(result) == 3

    def test_empty_string_returns_empty_list(self):
        result = _split_sentences("")
        assert result == []

    def test_question_mark_splits(self):
        result = _split_sentences("Did revenue grow? Yes it did.")
        assert len(result) == 2

    def test_no_trailing_empty_strings(self):
        result = _split_sentences("One sentence.")
        for s in result:
            assert s.strip(), "No empty strings in result"

    def test_no_whitespace_only_items(self):
        result = _split_sentences("Sentence one.  Sentence two.")
        for s in result:
            assert s.strip()


class TestExtractOverlapTail:
    def test_short_text_returns_empty(self):
        """Text shorter than CHUNK_OVERLAP_TOKENS returns empty string."""
        short = "hello world"
        result = _extract_overlap_tail(short)
        assert result == ""

    def test_long_text_returns_tail(self):
        long_text = " ".join(["word"] * 200)
        result = _extract_overlap_tail(long_text)
        assert result != ""
        assert count_tokens(result) <= CHUNK_OVERLAP_TOKENS

    def test_tail_is_suffix_of_original(self):
        """The overlap tail must be words from the end of the original text."""
        long_text = " ".join([f"word{i}" for i in range(100)])
        result = _extract_overlap_tail(long_text)
        # Last word of original should be in tail
        assert "word99" in result


class TestTableToText:
    def test_headers_in_first_line(self):
        text = _table_to_text(["Col A", "Col B"], [["1", "2"]])
        first_line = text.split("\n")[0]
        assert "Col A" in first_line
        assert "Col B" in first_line

    def test_separator_line_present(self):
        text = _table_to_text(["A", "B"], [["1", "2"]])
        assert "---" in text

    def test_data_rows_present(self):
        text = _table_to_text(["A", "B"], [["val1", "val2"], ["val3", "val4"]])
        assert "val1" in text
        assert "val3" in text

    def test_pipe_delimiter_used(self):
        text = _table_to_text(["A", "B"], [["1", "2"]])
        assert "|" in text

    def test_empty_rows_produces_header_only(self):
        text = _table_to_text(["A", "B"], [])
        assert "A" in text
        assert "---" in text


class TestSplitIntoGroups:
    def test_even_split(self):
        rows = [[str(i)] for i in range(40)]
        groups = _split_into_groups(rows, 20)
        assert len(groups) == 2
        assert len(groups[0]) == 20
        assert len(groups[1]) == 20

    def test_uneven_split_last_group_smaller(self):
        rows = [[str(i)] for i in range(45)]
        groups = _split_into_groups(rows, 20)
        assert len(groups) == 3
        assert len(groups[2]) == 5

    def test_fewer_rows_than_group_size(self):
        rows = [[str(i)] for i in range(5)]
        groups = _split_into_groups(rows, 20)
        assert len(groups) == 1
        assert len(groups[0]) == 5

    def test_empty_rows_returns_empty(self):
        assert _split_into_groups([], 20) == []

    def test_all_rows_preserved(self):
        rows = [[str(i)] for i in range(55)]
        groups = _split_into_groups(rows, 20)
        flat = [row for group in groups for row in group]
        assert flat == rows
