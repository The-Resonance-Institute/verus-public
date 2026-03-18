"""
Citation formatting utilities.

Every piece of evidence in Verus carries a human-readable citation.
These functions are the single source of truth for citation format.
Both the ingestion pipeline and the connector layer use these —
so all citations across the entire system are consistently formatted.
"""
from __future__ import annotations
from typing import Optional


# Canonical system display names
_SYSTEM_NAMES: dict[str, str] = {
    "salesforce":   "Salesforce CRM",
    "dynamics_ax":  "Microsoft Dynamics AX (ERP)",
    "dynamics_365": "Microsoft Dynamics 365 F&O (ERP)",
    "sap_erp":      "SAP ERP",
    "hubspot":      "HubSpot CRM",
    "fiix_cmms":    "Fiix CMMS",
    "generic_rest": "External System (REST API)",
    "sql_odbc":     "Direct Database (SQL)",
    "file_based":   "File Export",
}


def build_document_citation(
    filename: str,
    page_number: Optional[int] = None,
    slide_number: Optional[int] = None,
    sheet_name: Optional[str] = None,
    section_path: Optional[list[str]] = None,
) -> str:
    """Build a human-readable document source citation.

    Examples:
        'Q3 CIM.pdf, p.14, Section 3 > Pipeline Performance'
        'Management Presentation.pptx, Slide 12, Revenue Overview > Pipeline'
        'Financial Model FY2024.xlsx, Sheet: P&L Summary'
    """
    parts: list[str] = [filename]

    if page_number is not None:
        parts.append(f"p.{page_number}")
    elif slide_number is not None:
        parts.append(f"Slide {slide_number}")
    elif sheet_name is not None:
        parts.append(f"Sheet: {sheet_name}")

    if section_path:
        # Use last 2 levels of hierarchy for readability
        readable = " > ".join(section_path[-2:])
        parts.append(readable)

    return ", ".join(parts)


def build_system_citation(
    connector_type: str,
    query_intent: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    executed_at: Optional[str] = None,
) -> str:
    """Build a human-readable system source citation.

    Examples:
        'Salesforce CRM, pipeline summary, Jan 2024 – Mar 2026, queried 2026-03-16'
        'Microsoft Dynamics AX (ERP), revenue by period, Jan 2023 – Dec 2025'
    """
    name = _SYSTEM_NAMES.get(connector_type, connector_type)

    date_range = ""
    if date_from and date_to:
        date_range = f", {date_from} \u2013 {date_to}"
    elif date_from:
        date_range = f", from {date_from}"

    queried = f", queried {executed_at}" if executed_at else ""

    return f"{name}, {query_intent}{date_range}{queried}"


def citation_is_valid(citation: str) -> bool:
    """A citation is valid if it is a non-empty, non-whitespace string."""
    return bool(citation and citation.strip())
