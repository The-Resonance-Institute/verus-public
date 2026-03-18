"""
All shared enums for Verus.
Single file — prevents circular imports.
Every other module imports enums from here. Never define enums inline elsewhere.
"""
from enum import Enum


class ClaimDomain(str, Enum):
    COMMERCIAL  = "commercial"
    OPERATIONAL = "operational"
    FINANCIAL   = "financial"
    HUMAN_CAP   = "human_capital"


class ClaimType(str, Enum):
    EXPLICIT_NUMERIC     = "explicit_numeric"
    EXPLICIT_COMPARATIVE = "explicit_comparative"
    EXPLICIT_ABSOLUTE    = "explicit_absolute"
    IMPLICIT_PROJECTION  = "implicit_projection"
    IMPLICIT_ASSUMPTION  = "implicit_assumption"
    CAPABILITY_CLAIM     = "capability_claim"
    TREND_CLAIM          = "trend_claim"
    RISK_CLAIM           = "risk_claim"


class FindingVerdict(str, Enum):
    CONFIRMED    = "CONFIRMED"
    DIVERGENT    = "DIVERGENT"
    UNVERIFIABLE = "UNVERIFIABLE"
    INCONCLUSIVE = "INCONCLUSIVE"


class FindingMateriality(str, Enum):
    HIGH       = "HIGH"
    MEDIUM     = "MEDIUM"
    LOW        = "LOW"
    IMMATERIAL = "IMMATERIAL"


class FindingDomain(str, Enum):
    COM = "COM"   # Commercial
    OPS = "OPS"   # Operational
    FIN = "FIN"   # Financial
    HCM = "HCM"   # Human Capital


class FindingConfidenceTier(str, Enum):
    VERIFIED   = "VERIFIED"    # confidence >= 0.85
    PROBABLE   = "PROBABLE"    # confidence 0.65-0.84
    INDICATIVE = "INDICATIVE"  # confidence < 0.65


class EngagementStatus(str, Enum):
    SETUP        = "setup"
    INGESTING    = "ingesting"
    READY        = "ready"
    REASONING    = "reasoning"
    REPORT_READY = "report_ready"
    CHAT_ACTIVE  = "chat_active"
    CLOSED       = "closed"
    FAILED       = "failed"


class ConnectorType(str, Enum):
    SALESFORCE   = "salesforce"
    DYNAMICS_AX  = "dynamics_ax"
    DYNAMICS_365 = "dynamics_365"
    SAP_ERP      = "sap_erp"
    HUBSPOT      = "hubspot"
    FIIX_CMMS    = "fiix_cmms"
    GENERIC_REST = "generic_rest"
    SQL_ODBC     = "sql_odbc"
    FILE_BASED   = "file_based"


class ConnectorHealthStatus(str, Enum):
    HEALTHY           = "healthy"
    UNHEALTHY         = "unhealthy"
    DATA_QUALITY_WARN = "data_quality_warn"
    DATA_QUALITY_FAIL = "data_quality_fail"


class DataQualityRecommendation(str, Enum):
    PROCEED              = "proceed"
    PROCEED_WITH_CAUTION = "proceed_with_caution"
    UNVERIFIABLE         = "unverifiable"


class LedgerEntryType(str, Enum):
    CHUNK        = "chunk"
    QUERY        = "query"
    FINDING      = "finding"
    REPORT       = "report"
    CASA_VERDICT = "casa_verdict"
    VERIFICATION = "verification"


class CASAVerdict(str, Enum):
    ACCEPT = "ACCEPT"
    GOVERN = "GOVERN"
    REFUSE = "REFUSE"


class InitiativeType(str, Enum):
    REVENUE_GROWTH      = "revenue_growth"
    MARGIN_IMPROVEMENT  = "margin_improvement"
    OPERATIONAL_FIX     = "operational_fix"
    COST_REDUCTION      = "cost_reduction"
    TALENT_RETENTION    = "talent_retention"
    SYSTEM_UPGRADE      = "system_upgrade"
    CUSTOMER_FOCUS      = "customer_focus"
    CAPEX               = "capex"
    INTEGRATION         = "integration"
    PROCESS_IMPROVEMENT = "process_improvement"


class DocumentStatus(str, Enum):
    QUEUED      = "queued"
    NORMALIZING = "normalizing"
    CHUNKING    = "chunking"
    EXTRACTING  = "extracting"
    EMBEDDING   = "embedding"
    COMPLETE    = "complete"
    FAILED      = "failed"


class ChunkType(str, Enum):
    TEXT  = "text"
    TABLE = "table"


class AlignmentType(str, Enum):
    SUPPORTED    = "supported"
    CHALLENGED   = "challenged"
    CONTRADICTED = "contradicted"
    SILENT       = "silent"


class AssessmentConfidence(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class RecommendedAction(str, Enum):
    REPRICING_CONSIDERATION = "repricing_consideration"
    STRUCTURAL_PROTECTION   = "structural_protection"
    HUNDRED_DAY_PRIORITY    = "100_day_priority"
    FURTHER_INVESTIGATION   = "further_investigation"
    GO_NO_GO_FLAG           = "go_no_go_flag"
