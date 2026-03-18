"""
Test: packages/core/utils/

Utilities are used everywhere. Wrong utility output propagates silently.
These tests verify correctness of every utility function, including
edge cases and boundary conditions.
"""

import hashlib
import pytest
from datetime import datetime, timezone
from uuid import uuid4, UUID

from packages.core.utils.tokens import count_tokens, truncate_to_tokens, fits_in_tokens
from packages.core.utils.citations import (
    build_document_citation, build_system_citation, citation_is_valid,
)
from packages.core.utils.s3_keys import (
    raw_document_key, normalized_document_key, chunks_key,
    deliverable_key, plan_key, engagement_prefix,
    validate_key_belongs_to_engagement,
)
from packages.core.utils.hashing import (
    generate_chunk_hash, generate_query_hash, generate_parameters_hash,
    generate_finding_hash, generate_report_hash, generate_casa_verdict_hash,
    truncate_hash_for_display, _sha256,
)
from packages.core.utils.finding_codes import build_finding_code
from packages.core.enums import ClaimDomain, CASAVerdict


# ── Token Utilities ───────────────────────────────────────────────────────────
class TestTokenUtilities:
    def test_empty_string_is_zero(self):
        assert count_tokens("") == 0

    def test_single_word_is_positive(self):
        assert count_tokens("hello") > 0

    def test_longer_text_has_more_tokens(self):
        short = count_tokens("hello world")
        long  = count_tokens("hello world " * 50)
        assert long > short

    def test_token_count_is_deterministic(self):
        text = "Revenue grew 23% year over year in FY2024."
        assert count_tokens(text) == count_tokens(text)

    def test_truncate_short_text_unchanged(self):
        text = "hello world"
        result = truncate_to_tokens(text, 1000)
        assert result == text

    def test_truncate_long_text_is_shorter(self):
        text = "the quick brown fox jumps over the lazy dog " * 100
        original_tokens = count_tokens(text)
        result = truncate_to_tokens(text, 50)
        result_tokens = count_tokens(result)
        assert result_tokens <= 50
        assert result_tokens < original_tokens

    def test_truncate_to_exact_limit(self):
        text = "word " * 200
        result = truncate_to_tokens(text, 100)
        assert count_tokens(result) <= 100

    def test_fits_in_tokens_true(self):
        assert fits_in_tokens("hello", 100) is True

    def test_fits_in_tokens_false(self):
        long_text = "word " * 500
        assert fits_in_tokens(long_text, 10) is False


# ── Citation Utilities ────────────────────────────────────────────────────────
class TestCitationUtilities:
    def test_pdf_citation_with_page_and_section(self):
        citation = build_document_citation(
            "Q3 CIM.pdf",
            page_number=14,
            section_path=["Section 3", "Pipeline Performance"],
        )
        assert "Q3 CIM.pdf" in citation
        assert "p.14" in citation
        assert "Pipeline Performance" in citation

    def test_pdf_citation_without_section_path(self):
        citation = build_document_citation("Report.pdf", page_number=5)
        assert "p.5" in citation
        assert "Report.pdf" in citation

    def test_pptx_citation_uses_slide_not_page(self):
        citation = build_document_citation("Deck.pptx", slide_number=12)
        assert "Slide 12" in citation
        assert "p." not in citation

    def test_xlsx_citation_uses_sheet_name(self):
        citation = build_document_citation(
            "Model.xlsx", sheet_name="P&L Summary"
        )
        assert "Sheet: P&L Summary" in citation

    def test_section_path_uses_last_two_levels(self):
        # Deep section paths truncated to last 2 levels for readability
        citation = build_document_citation(
            "CIM.pdf",
            page_number=14,
            section_path=["Part 1", "Chapter 3", "Section 3.2", "Revenue Detail"],
        )
        # Should contain last 2: Section 3.2 > Revenue Detail
        assert "Section 3.2" in citation
        assert "Revenue Detail" in citation
        # Should NOT contain outer levels
        assert "Part 1" not in citation
        assert "Chapter 3" not in citation

    def test_salesforce_system_citation(self):
        citation = build_system_citation(
            "salesforce",
            "pipeline summary",
            date_from="Jan 2024",
            date_to="Mar 2026",
            executed_at="2026-03-16",
        )
        assert "Salesforce CRM" in citation
        assert "pipeline summary" in citation
        assert "Jan 2024" in citation
        assert "2026-03-16" in citation

    def test_dynamics_ax_citation(self):
        citation = build_system_citation("dynamics_ax", "revenue by period")
        assert "Microsoft Dynamics AX" in citation

    def test_unknown_connector_uses_raw_name(self):
        citation = build_system_citation("custom_erp_v2", "revenue query")
        assert "custom_erp_v2" in citation

    def test_citation_without_dates(self):
        citation = build_system_citation("hubspot", "pipeline_velocity")
        assert "HubSpot CRM" in citation
        # No date range — should not have en-dash
        assert "\u2013" not in citation

    def test_citation_is_valid_non_empty(self):
        assert citation_is_valid("CIM.pdf, p.14") is True

    def test_citation_is_valid_empty_string(self):
        assert citation_is_valid("") is False

    def test_citation_is_valid_whitespace(self):
        assert citation_is_valid("   ") is False


# ── S3 Key Utilities ──────────────────────────────────────────────────────────
class TestS3KeyUtilities:
    def test_raw_key_structure(self):
        eid = uuid4()
        did = uuid4()
        key = raw_document_key(eid, did, "CIM Draft.pdf")
        assert key == f"{eid}/raw/{did}/CIM Draft.pdf"

    def test_normalized_key_structure(self):
        eid = uuid4()
        did = uuid4()
        key = normalized_document_key(eid, did)
        assert key == f"{eid}/normalized/{did}/output.json"

    def test_chunks_key_structure(self):
        eid = uuid4()
        did = uuid4()
        key = chunks_key(eid, did)
        assert key == f"{eid}/chunks/{did}/chunks.json"

    def test_deliverable_key_structure(self):
        eid = uuid4()
        key = deliverable_key(eid, "countercheck_report.docx")
        assert key == f"{eid}/deliverables/countercheck_report.docx"

    def test_plan_key_structure(self):
        eid = uuid4()
        pid = uuid4()
        key = plan_key(eid, pid, "100-day-plan.docx")
        assert key == f"{eid}/plan/{pid}/100-day-plan.docx"

    def test_engagement_prefix(self):
        eid = uuid4()
        prefix = engagement_prefix(eid)
        assert prefix == f"{eid}/"

    def test_all_keys_start_with_engagement_id(self):
        eid = uuid4()
        did = uuid4()
        pid = uuid4()
        keys = [
            raw_document_key(eid, did, "doc.pdf"),
            normalized_document_key(eid, did),
            chunks_key(eid, did),
            deliverable_key(eid, "report.docx"),
            plan_key(eid, pid, "plan.docx"),
        ]
        for key in keys:
            assert key.startswith(str(eid)), (
                f"Key does not start with engagement_id: {key}"
            )

    def test_validate_key_belongs_to_engagement_true(self):
        eid = uuid4()
        key = raw_document_key(eid, uuid4(), "doc.pdf")
        assert validate_key_belongs_to_engagement(key, eid) is True

    def test_validate_key_belongs_to_engagement_false(self):
        eid_a = uuid4()
        eid_b = uuid4()
        key = raw_document_key(eid_a, uuid4(), "doc.pdf")
        assert validate_key_belongs_to_engagement(key, eid_b) is False

    def test_keys_for_different_engagements_dont_share_prefix(self):
        eid_a = uuid4()
        eid_b = uuid4()
        key_a = raw_document_key(eid_a, uuid4(), "doc.pdf")
        key_b = raw_document_key(eid_b, uuid4(), "doc.pdf")
        # No key from engagement A should be accessible via engagement B's prefix
        assert not key_a.startswith(str(eid_b))
        assert not key_b.startswith(str(eid_a))


# ── Hashing Utilities ─────────────────────────────────────────────────────────
class TestHashingUtilities:
    def test_sha256_returns_64_char_hex(self):
        h = _sha256("test payload")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_sha256_is_deterministic(self):
        payload = "engagement_id|chunk_id|text|citation"
        assert _sha256(payload) == _sha256(payload)

    def test_sha256_different_inputs_produce_different_hashes(self):
        h1 = _sha256("payload A")
        h2 = _sha256("payload B")
        assert h1 != h2

    def test_chunk_hash_is_64_chars(self):
        h = generate_chunk_hash(
            chunk_id=uuid4(),
            document_id=uuid4(),
            engagement_id=uuid4(),
            text="Revenue grew 23% YoY.",
            source_citation="CIM.pdf, p.14",
        )
        assert len(h) == 64

    def test_chunk_hash_deterministic_same_inputs(self):
        cid = uuid4()
        did = uuid4()
        eid = uuid4()
        text = "Revenue grew 23%"
        cite = "CIM.pdf, p.14"
        h1 = generate_chunk_hash(cid, did, eid, text, cite)
        h2 = generate_chunk_hash(cid, did, eid, text, cite)
        assert h1 == h2

    def test_chunk_hash_changes_with_text(self):
        cid, did, eid = uuid4(), uuid4(), uuid4()
        cite = "CIM.pdf, p.14"
        h1 = generate_chunk_hash(cid, did, eid, "text A", cite)
        h2 = generate_chunk_hash(cid, did, eid, "text B", cite)
        assert h1 != h2

    def test_chunk_hash_changes_with_citation(self):
        cid, did, eid = uuid4(), uuid4(), uuid4()
        text = "Revenue grew 23%"
        h1 = generate_chunk_hash(cid, did, eid, text, "CIM.pdf, p.14")
        h2 = generate_chunk_hash(cid, did, eid, text, "CIM.pdf, p.15")
        assert h1 != h2

    def test_parameters_hash_is_deterministic(self):
        params = {"date_from": "2024-01-01", "limit": 1000, "include_closed": True}
        h1 = generate_parameters_hash(params)
        h2 = generate_parameters_hash(params)
        assert h1 == h2

    def test_parameters_hash_key_order_doesnt_matter(self):
        params_a = {"b": "2", "a": "1"}
        params_b = {"a": "1", "b": "2"}
        assert generate_parameters_hash(params_a) == generate_parameters_hash(params_b)

    def test_query_hash_64_chars(self):
        h = generate_query_hash(
            query_id=uuid4(),
            engagement_id=uuid4(),
            connector_type="salesforce",
            intent="pipeline_summary",
            parameters_hash="a" * 64,
            record_count=47,
            executed_at=datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc),
            records=[{"amount": 100000, "stage": "Closed Won"}],
        )
        assert len(h) == 64

    def test_query_hash_changes_with_record_count(self):
        args = dict(
            query_id=uuid4(),
            engagement_id=uuid4(),
            connector_type="salesforce",
            intent="pipeline_summary",
            parameters_hash="a" * 64,
            executed_at=datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc),
            records=[],
        )
        h1 = generate_query_hash(**args, record_count=47)
        h2 = generate_query_hash(**args, record_count=48)
        assert h1 != h2

    def test_finding_hash_64_chars(self):
        h = generate_finding_hash(
            finding_id=uuid4(),
            engagement_id=uuid4(),
            finding_code="COM-001",
            management_claim_citation="CIM.pdf, p.14",
            system_evidence_citation="Salesforce CRM, queried 2026-03-16",
            verdict="DIVERGENT",
            divergence_summary="11% growth vs 23% claimed",
            confidence=0.88,
        )
        assert len(h) == 64

    def test_finding_hash_changes_with_verdict(self):
        args = dict(
            finding_id=uuid4(),
            engagement_id=uuid4(),
            finding_code="COM-001",
            management_claim_citation="CIM.pdf, p.14",
            system_evidence_citation="Salesforce CRM",
            divergence_summary=None,
            confidence=0.88,
        )
        h1 = generate_finding_hash(**args, verdict="DIVERGENT")
        h2 = generate_finding_hash(**args, verdict="CONFIRMED")
        assert h1 != h2

    def test_report_hash_64_chars(self):
        h = generate_report_hash(
            engagement_id=uuid4(),
            finding_hashes=["a" * 64, "b" * 64, "c" * 64],
            assembled_at=datetime(2026, 3, 16, 14, 0, 0, tzinfo=timezone.utc),
            report_s3_key="abc/deliverables/report.docx",
        )
        assert len(h) == 64

    def test_report_hash_order_independent(self):
        eid = uuid4()
        ts = datetime(2026, 3, 16, 14, 0, 0, tzinfo=timezone.utc)
        key = "abc/deliverables/report.docx"
        hashes = ["aaa" * 21 + "a", "bbb" * 21 + "b", "ccc" * 21 + "c"]

        h1 = generate_report_hash(eid, hashes, ts, key)
        h2 = generate_report_hash(eid, list(reversed(hashes)), ts, key)
        assert h1 == h2, "Report hash must be order-independent"

    def test_casa_verdict_hash_64_chars(self):
        h = generate_casa_verdict_hash(
            query_id=uuid4(),
            verdict="GOVERN",
            primitive_triggered="pii_access_control",
            timestamp=datetime(2026, 3, 16, 12, 30, 0, tzinfo=timezone.utc),
        )
        assert len(h) == 64

    def test_truncate_hash_for_display_format(self):
        full_hash = "a" * 64
        truncated = truncate_hash_for_display(full_hash)
        assert truncated == f"{'a'*16}...{'a'*8}"
        assert "..." in truncated
        assert len(truncated) < len(full_hash)

    def test_truncate_short_hash_unchanged(self):
        short = "abc123"
        assert truncate_hash_for_display(short) == short


# ── Finding Code Utilities ────────────────────────────────────────────────────
class TestFindingCodeUtilities:
    def test_commercial_code(self):
        assert build_finding_code(ClaimDomain.COMMERCIAL, 1) == "COM-001"

    def test_operational_code(self):
        assert build_finding_code(ClaimDomain.OPERATIONAL, 3) == "OPS-003"

    def test_financial_code(self):
        assert build_finding_code(ClaimDomain.FINANCIAL, 7) == "FIN-007"

    def test_human_capital_code(self):
        assert build_finding_code(ClaimDomain.HUMAN_CAP, 2) == "HCM-002"

    def test_string_domain_value_works(self):
        # use_enum_values=True means DB returns strings
        assert build_finding_code("commercial", 1) == "COM-001"
        assert build_finding_code("operational", 5) == "OPS-005"

    def test_sequence_zero_padded_to_three_digits(self):
        assert build_finding_code(ClaimDomain.COMMERCIAL, 1) == "COM-001"
        assert build_finding_code(ClaimDomain.COMMERCIAL, 10) == "COM-010"
        assert build_finding_code(ClaimDomain.COMMERCIAL, 100) == "COM-100"

    def test_unknown_domain_uses_unk_prefix(self):
        code = build_finding_code("unknown_domain", 1)
        assert code == "UNK-001"
