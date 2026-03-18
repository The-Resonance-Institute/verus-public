"""
Test: packages/core/enums.py

Every enum must be importable, have the correct values, and be complete.
Enums are contracts — if a value is wrong here, it propagates to the
database, the API, the frontend, and the LLM prompts.
"""

import pytest
from packages.core.enums import (
    ClaimDomain, ClaimType, FindingVerdict, FindingMateriality,
    FindingDomain, FindingConfidenceTier, EngagementStatus,
    ConnectorType, ConnectorHealthStatus, DataQualityRecommendation,
    LedgerEntryType, CASAVerdict, InitiativeType, DocumentStatus,
    ChunkType, AlignmentType, AssessmentConfidence, RecommendedAction,
)


class TestClaimDomain:
    def test_all_four_domains_present(self):
        values = {d.value for d in ClaimDomain}
        assert values == {"commercial", "operational", "financial", "human_capital"}

    def test_string_comparison_works(self):
        # use_enum_values=True in schemas means DB returns strings
        assert ClaimDomain.COMMERCIAL == "commercial"
        assert ClaimDomain.FINANCIAL == "financial"


class TestClaimType:
    def test_all_eight_types_present(self):
        assert len(list(ClaimType)) == 8

    def test_values(self):
        assert ClaimType.EXPLICIT_NUMERIC == "explicit_numeric"
        assert ClaimType.TREND_CLAIM == "trend_claim"
        assert ClaimType.RISK_CLAIM == "risk_claim"
        assert ClaimType.CAPABILITY_CLAIM == "capability_claim"


class TestFindingVerdict:
    def test_four_verdicts(self):
        assert len(list(FindingVerdict)) == 4

    def test_values_uppercase(self):
        # Frontend and report use these values directly — must be uppercase
        assert FindingVerdict.CONFIRMED    == "CONFIRMED"
        assert FindingVerdict.DIVERGENT    == "DIVERGENT"
        assert FindingVerdict.UNVERIFIABLE == "UNVERIFIABLE"
        assert FindingVerdict.INCONCLUSIVE == "INCONCLUSIVE"


class TestFindingConfidenceTier:
    def test_three_tiers(self):
        assert len(list(FindingConfidenceTier)) == 3

    def test_values(self):
        assert FindingConfidenceTier.VERIFIED == "VERIFIED"
        assert FindingConfidenceTier.PROBABLE == "PROBABLE"
        assert FindingConfidenceTier.INDICATIVE == "INDICATIVE"


class TestEngagementStatus:
    def test_all_eight_statuses(self):
        assert len(list(EngagementStatus)) == 8

    def test_progression_order_values_exist(self):
        # These specific strings are stored in the DB and checked by the API
        statuses = {s.value for s in EngagementStatus}
        for expected in ["setup", "ingesting", "ready", "reasoning",
                         "report_ready", "chat_active", "closed", "failed"]:
            assert expected in statuses, f"Missing status: {expected}"


class TestConnectorType:
    def test_all_nine_connectors_present(self):
        assert len(list(ConnectorType)) == 9

    def test_required_connectors_present(self):
        types = {ct.value for ct in ConnectorType}
        for required in ["salesforce", "dynamics_ax", "dynamics_365", "sap_erp",
                         "hubspot", "fiix_cmms", "generic_rest", "sql_odbc",
                         "file_based"]:
            assert required in types, f"Missing connector type: {required}"


class TestLedgerEntryType:
    def test_all_six_types(self):
        assert len(list(LedgerEntryType)) == 6

    def test_critical_types_present(self):
        types = {t.value for t in LedgerEntryType}
        for required in ["chunk", "query", "finding", "report", "casa_verdict"]:
            assert required in types, f"Missing ledger type: {required}"


class TestCASAVerdict:
    def test_three_verdicts(self):
        assert len(list(CASAVerdict)) == 3

    def test_values_uppercase(self):
        assert CASAVerdict.ACCEPT == "ACCEPT"
        assert CASAVerdict.GOVERN == "GOVERN"
        assert CASAVerdict.REFUSE == "REFUSE"


class TestInitiativeType:
    def test_all_ten_types(self):
        assert len(list(InitiativeType)) == 10

    def test_key_types_present(self):
        types = {t.value for t in InitiativeType}
        for required in ["revenue_growth", "margin_improvement",
                         "operational_fix", "talent_retention"]:
            assert required in types


class TestDocumentStatus:
    def test_all_seven_statuses(self):
        assert len(list(DocumentStatus)) == 7

    def test_pipeline_order_values_exist(self):
        statuses = {s.value for s in DocumentStatus}
        for expected in ["queued", "normalizing", "chunking",
                         "extracting", "embedding", "complete", "failed"]:
            assert expected in statuses


class TestDataQualityRecommendation:
    def test_three_recommendations(self):
        assert len(list(DataQualityRecommendation)) == 3

    def test_values(self):
        assert DataQualityRecommendation.PROCEED == "proceed"
        assert DataQualityRecommendation.PROCEED_WITH_CAUTION == "proceed_with_caution"
        assert DataQualityRecommendation.UNVERIFIABLE == "unverifiable"


class TestRecommendedAction:
    def test_five_actions(self):
        assert len(list(RecommendedAction)) == 5

    def test_values(self):
        assert RecommendedAction.REPRICING_CONSIDERATION == "repricing_consideration"
        assert RecommendedAction.STRUCTURAL_PROTECTION == "structural_protection"
        assert RecommendedAction.GO_NO_GO_FLAG == "go_no_go_flag"
