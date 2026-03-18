"""Finding code generation — COM-001, OPS-003, FIN-007, HCM-002."""
from __future__ import annotations
from packages.core.enums import ClaimDomain


_DOMAIN_PREFIX: dict[str, str] = {
    ClaimDomain.COMMERCIAL:  "COM",
    ClaimDomain.OPERATIONAL: "OPS",
    ClaimDomain.FINANCIAL:   "FIN",
    ClaimDomain.HUMAN_CAP:   "HCM",
    # String values (when use_enum_values=True)
    "commercial":   "COM",
    "operational":  "OPS",
    "financial":    "FIN",
    "human_capital": "HCM",
}


def build_finding_code(domain: str | ClaimDomain, sequence: int) -> str:
    """Build a finding code like COM-001, OPS-003.

    Args:
        domain: ClaimDomain enum or its string value.
        sequence: 1-based sequence number within the domain for this engagement.

    Returns:
        Finding code string e.g. 'COM-001'
    """
    prefix = _DOMAIN_PREFIX.get(domain, "UNK")  # type: ignore[arg-type]
    return f"{prefix}-{sequence:03d}"
