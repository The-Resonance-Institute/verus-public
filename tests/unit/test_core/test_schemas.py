"""
Test: packages/core/schemas/

Schemas are interface contracts between every component in Verus.
Tests verify:
  1. Valid inputs produce correct objects
  2. Invalid inputs raise ValidationError
  3. Required fields are actually required
  4. Default values are correct
  5. Cross-field logic (e.g., confidence_tier derived from confidence)
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from pydantic import ValidationError

from packages.core.schemas.engagement import Engagement, EngagementCreate
from packages.core.schemas.document import (
    DocumentIntake, TextBlock, ExtractedTable,
    NormalizedDocument, DocumentMetadata, DocumentChunk,
)
from packages.core.schemas.claim import Claim, ClaimExtraction, ExtractedClaimsResponse
from packages.core.schemas.connector import (
    ConnectorQuery, QueryResult, ConnectorHealthReport, DataQualityReport,
)
from packages.core.schemas.finding import (
    Finding, FinancialImplication, ValidationResult, ValidationFailure,
)
from packages.core.schemas.hypothesis import (
    Hypothesis, HypothesisFormation, InvestigationResult,
)
from packages.core.schemas.ledger import LedgerEntry, VerificationResult
from packages.core.schemas.chat import ChatMessage, ChatSession
from packages.core.schemas.plan import Initiative, PlanDocument, StressTestAssessment
from packages.core.schemas.retrieval import RetrievalResult
from packages.core.enums import (
    ClaimDomain, ClaimType, FindingVerdict, FindingMateriality,
    ConnectorType, DocumentStatus, LedgerEntryType, FindingConfidenceTier,
)
from packages.core.constants import CONFIDENCE_VERIFIED, CONFIDENCE_PROBABLE


# ── Helpers ───────────────────────────────────────────────────────────────────
def make_engagement(**kwargs):
    defaults = dict(
        deal_name="Project Apex",
        target_company_name="Acme Corp",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc) + timedelta(days=28),
        created_by=uuid4(),
    )
    defaults.update(kwargs)
    return Engagement(**defaults)


def make_finding(**kwargs):
    defaults = dict(
        engagement_id=uuid4(),
        finding_code="COM-001",
        domain=ClaimDomain.COMMERCIAL,
        verdict=FindingVerdict.DIVERGENT,
        materiality=FindingMateriality.HIGH,
        confidence=0.88,
        management_claim="Revenue grew 23% YoY in FY2024",
        management_claim_citation="CIM.pdf, p.14, Section 3 > Revenue",
        system_evidence_summary="Salesforce CRM shows 11% growth over same period",
        system_evidence_citation=(
            "Salesforce CRM, closed_won_history, Jan 2023 – Dec 2024, queried 2026-03-16"
        ),
    )
    defaults.update(kwargs)
    return Finding(**defaults)


# ── Engagement Schema ─────────────────────────────────────────────────────────
class TestEngagementSchema:
    def test_valid_engagement_creates(self):
        eng = make_engagement()
        assert eng.deal_name == "Project Apex"
        assert eng.status == "setup"  # use_enum_values=True returns string

    def test_engagement_id_auto_generated(self):
        eng1 = make_engagement()
        eng2 = make_engagement()
        assert eng1.engagement_id != eng2.engagement_id

    def test_optional_deal_params_default_none(self):
        eng = make_engagement()
        assert eng.deal_size_estimate is None
        assert eng.ebitda_estimate is None
        assert eng.acquisition_multiple_estimate is None

    def test_optional_deal_params_accepted(self):
        eng = make_engagement(
            deal_size_estimate=50_000_000,
            ebitda_estimate=8_000_000,
            acquisition_multiple_estimate=6.5,
        )
        assert eng.deal_size_estimate == 50_000_000
        assert eng.acquisition_multiple_estimate == 6.5

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Engagement(
                target_company_name="Acme",
                window_start=datetime.now(timezone.utc),
                window_end=datetime.now(timezone.utc) + timedelta(days=28),
                created_by=uuid4(),
                # missing deal_name
            )


# ── Document Schemas ──────────────────────────────────────────────────────────
class TestDocumentSchemas:
    def test_document_intake_defaults(self):
        intake = DocumentIntake(
            engagement_id=uuid4(),
            source="direct_upload",
            original_filename="CIM_Draft.pdf",
            file_extension="pdf",
            file_size_bytes=4_200_000,
            s3_key="abc/raw/def/CIM_Draft.pdf",
        )
        assert intake.status == "queued"
        assert intake.error_message is None
        assert intake.chunk_count is None

    def test_text_block_optional_fields(self):
        block = TextBlock(
            document_id=uuid4(),
            text="Revenue grew 23% year over year.",
        )
        assert block.heading_level is None
        assert block.page_number is None
        assert block.is_comment is False

    def test_extracted_table_defaults(self):
        table = ExtractedTable(
            document_id=uuid4(),
            headers=["Period", "Revenue", "Margin"],
            rows=[["Q1 2024", "$12.4M", "38%"]],
        )
        assert table.table_type == "generic"
        assert table.is_sampled is False
        assert table.is_malformed is False

    def test_document_chunk_requires_citation(self):
        # source_citation is required — no default
        with pytest.raises(ValidationError):
            DocumentChunk(
                document_id=uuid4(),
                engagement_id=uuid4(),
                text="Some text",
                token_count=10,
                # missing source_citation
            )

    def test_document_chunk_with_all_fields(self):
        chunk = DocumentChunk(
            document_id=uuid4(),
            engagement_id=uuid4(),
            text="Revenue grew 23% YoY in FY2024.",
            token_count=12,
            chunk_type="text",
            page_number=14,
            section_path=["Section 3", "Revenue Analysis"],
            heading_text="Revenue Analysis",
            source_citation="CIM.pdf, p.14, Section 3 > Revenue Analysis",
        )
        assert chunk.source_citation == "CIM.pdf, p.14, Section 3 > Revenue Analysis"
        assert chunk.embedding_vector is None
        assert chunk.overlap_with_prev is False


# ── Claim Schemas ─────────────────────────────────────────────────────────────
class TestClaimSchemas:
    def test_claim_creates_with_required_fields(self):
        claim = Claim(
            engagement_id=uuid4(),
            chunk_id=uuid4(),
            document_id=uuid4(),
            claim_text="Revenue grew 23% YoY in FY2024",
            claim_type=ClaimType.EXPLICIT_NUMERIC,
            domain=ClaimDomain.COMMERCIAL,
            materiality=0.9,
            source_citation="CIM.pdf, p.14",
        )
        assert claim.status == "active"
        assert claim.canonical_id is None

    def test_claim_extraction_response_empty_list_valid(self):
        # Chunks with no qualifying claims return empty list — not an error
        response = ExtractedClaimsResponse(claims=[])
        assert response.claims == []
        assert response.extraction_notes is None

    def test_claim_extraction_validates_domain(self):
        with pytest.raises(ValidationError):
            ClaimExtraction(
                claim_text="Some claim",
                claim_type=ClaimType.TREND_CLAIM,
                domain="invalid_domain",  # not a valid ClaimDomain
                materiality=0.5,
            )


# ── Connector Schemas ─────────────────────────────────────────────────────────
class TestConnectorSchemas:
    def test_connector_query_defaults(self):
        q = ConnectorQuery(
            engagement_id=uuid4(),
            connector_type=ConnectorType.SALESFORCE,
            domain="commercial",
            intent="pipeline_summary",
        )
        assert q.parameters == {}
        assert q.date_from is None

    def test_query_result_defaults(self):
        r = QueryResult(
            query_id=uuid4(),
            engagement_id=uuid4(),
            connector_type=ConnectorType.SALESFORCE,
            success=True,
        )
        assert r.records == []
        assert r.is_partial is False
        assert r.error_message is None

    def test_query_result_failure_with_message(self):
        r = QueryResult(
            query_id=uuid4(),
            engagement_id=uuid4(),
            connector_type=ConnectorType.DYNAMICS_365,
            success=False,
            error_message="OAuth token expired",
        )
        assert not r.success
        assert r.error_message == "OAuth token expired"

    def test_data_quality_report_recommendation_required(self):
        from packages.core.enums import DataQualityRecommendation
        report = DataQualityReport(
            connector_type=ConnectorType.SALESFORCE,
            engagement_id=uuid4(),
            completeness_score=0.85,
            historical_depth_months=18,
            consistency_score=0.92,
            recommendation=DataQualityRecommendation.PROCEED,
        )
        assert report.recommendation == "proceed"


# ── Finding Schemas ───────────────────────────────────────────────────────────
class TestFindingSchemas:
    def test_divergent_finding_creates(self):
        finding = make_finding()
        assert finding.verdict == "DIVERGENT"
        assert finding.thread_depth == 0
        assert finding.parent_finding_id is None

    def test_confidence_tier_property_verified(self):
        finding = make_finding(confidence=0.90)
        assert finding.confidence_tier == FindingConfidenceTier.VERIFIED

    def test_confidence_tier_property_probable(self):
        finding = make_finding(confidence=0.72)
        assert finding.confidence_tier == FindingConfidenceTier.PROBABLE

    def test_confidence_tier_property_indicative(self):
        finding = make_finding(confidence=0.55)
        assert finding.confidence_tier == FindingConfidenceTier.INDICATIVE

    def test_confidence_tier_boundary_verified(self):
        # Exactly at CONFIDENCE_VERIFIED threshold → VERIFIED
        finding = make_finding(confidence=CONFIDENCE_VERIFIED)
        assert finding.confidence_tier == FindingConfidenceTier.VERIFIED

    def test_confidence_tier_boundary_probable(self):
        # Just below CONFIDENCE_VERIFIED → PROBABLE
        finding = make_finding(confidence=CONFIDENCE_VERIFIED - 0.001)
        assert finding.confidence_tier == FindingConfidenceTier.PROBABLE

    def test_confidence_tier_boundary_indicative(self):
        # Just below CONFIDENCE_PROBABLE → INDICATIVE
        finding = make_finding(confidence=CONFIDENCE_PROBABLE - 0.001)
        assert finding.confidence_tier == FindingConfidenceTier.INDICATIVE

    def test_validated_finding_without_system_citation(self):
        # UNVERIFIABLE findings have no system evidence
        finding = make_finding(
            verdict=FindingVerdict.UNVERIFIABLE,
            system_evidence_summary=None,
            system_evidence_citation=None,
        )
        assert finding.verdict == "UNVERIFIABLE"

    def test_validation_result_all_pass(self):
        result = ValidationResult(
            finding_id=uuid4(),
            passed=True,
            failures=[],
        )
        assert result.passed is True
        assert result.failures == []

    def test_validation_result_with_failures(self):
        result = ValidationResult(
            finding_id=uuid4(),
            passed=False,
            failures=[
                ValidationFailure(
                    requirement="system_citation",
                    detail="system_evidence_citation does not match any audit log entry",
                ),
                ValidationFailure(
                    requirement="no_speculation",
                    detail="Evidence summary contains 'might indicate'",
                ),
            ],
        )
        assert result.passed is False
        assert len(result.failures) == 2
        requirements = {f.requirement for f in result.failures}
        assert "system_citation" in requirements
        assert "no_speculation" in requirements


# ── Hypothesis Schemas ────────────────────────────────────────────────────────
class TestHypothesisSchemas:
    def test_hypothesis_defaults(self):
        h = Hypothesis(
            engagement_id=uuid4(),
            source_claim_id=uuid4(),
            hypothesis_text="Salesforce CRM will show 20-25% YoY pipeline growth.",
            domain=ClaimDomain.COMMERCIAL,
            required_connector_types=["salesforce"],
            required_query_types=["pipeline_velocity"],
            materiality=0.9,
        )
        assert h.status == "pending"
        assert h.query_parameters == {}

    def test_investigation_result_defaults(self):
        result = InvestigationResult(
            hypothesis_id=uuid4(),
            verdict="divergent",
        )
        assert result.confidence == 0.0
        assert result.evidence == []
        assert result.thread_candidates == []


# ── Ledger Schemas ────────────────────────────────────────────────────────────
class TestLedgerSchemas:
    def test_ledger_entry_creates(self):
        entry = LedgerEntry(
            engagement_id=uuid4(),
            entry_type=LedgerEntryType.CHUNK,
            object_id=uuid4(),
            object_hash="a" * 64,  # SHA-256 is 64 hex chars
            recorded_by="ingestion-worker",
        )
        assert entry.parent_hash is None
        assert entry.prev_entry_hash is None
        assert entry.metadata == {}

    def test_verification_result_intact(self):
        result = VerificationResult(
            engagement_id=uuid4(),
            chain_intact=True,
            total_entries=42,
            entries_by_type={"chunk": 30, "query": 8, "finding": 3, "report": 1},
            report_hash="b" * 64,
        )
        assert result.chain_intact is True
        assert result.first_broken_link is None
        assert result.total_entries == 42

    def test_verification_result_broken_chain(self):
        broken_id = str(uuid4())
        result = VerificationResult(
            engagement_id=uuid4(),
            chain_intact=False,
            total_entries=42,
            first_broken_link=broken_id,
        )
        assert result.chain_intact is False
        assert result.first_broken_link == broken_id


# ── Chat Schemas ──────────────────────────────────────────────────────────────
class TestChatSchemas:
    def test_chat_message_creates(self):
        msg = ChatMessage(
            session_id=uuid4(),
            engagement_id=uuid4(),
            role="user",
            content="What is the pipeline conversion rate?",
        )
        assert msg.citations == []
        assert msg.tools_called == []
        assert msg.token_count is None

    def test_chat_session_defaults(self):
        session = ChatSession(
            engagement_id=uuid4(),
            user_id=uuid4(),
        )
        assert session.message_count == 0
        assert session.queries_executed == 0
        assert session.ended_at is None


# ── Plan Schemas ──────────────────────────────────────────────────────────────
class TestPlanSchemas:
    def test_initiative_creates(self):
        from packages.core.enums import InitiativeType
        initiative = Initiative(
            plan_id=uuid4(),
            initiative_type=InitiativeType.REVENUE_GROWTH,
            domain=ClaimDomain.COMMERCIAL,
            title="Implement CRM pipeline discipline",
            description="Establish weekly pipeline review with sales team.",
            stated_assumption="CRM data is actively maintained and reliable.",
            source_citation="100-Day Plan, p.4, Commercial Initiatives",
            materiality=0.85,
        )
        assert initiative.is_applicable is True
        assert initiative.stated_target is None

    def test_plan_document_defaults(self):
        plan = PlanDocument(
            engagement_id=uuid4(),
            original_filename="100-day-plan.docx",
            s3_key="abc/plan/def/100-day-plan.docx",
        )
        assert plan.status == "uploaded"
        assert plan.total_initiatives == 0
        assert plan.plan_horizon_days == 100


# ── Retrieval Schema ──────────────────────────────────────────────────────────
class TestRetrievalSchema:
    def test_valid_retrieval_result(self):
        result = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            engagement_id=uuid4(),
            text="Revenue grew 23% YoY",
            source_citation="CIM.pdf, p.14",
            score=0.87,
        )
        assert result.is_valid() is True

    def test_empty_citation_is_invalid(self):
        result = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            engagement_id=uuid4(),
            text="Some text",
            source_citation="",
            score=0.9,
        )
        assert result.is_valid() is False

    def test_whitespace_citation_is_invalid(self):
        result = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            engagement_id=uuid4(),
            text="Some text",
            source_citation="   ",
            score=0.9,
        )
        assert result.is_valid() is False
