# Verus

**AI-driven investigative reasoning across represented narratives and live operating systems.**

Every organization operates on two surfaces simultaneously. The first is the represented surface — management reports, board presentations, CIMs, investor updates, location summaries. The second is the operating reality — what is actually in the live systems that run the business.

Verus reads both surfaces simultaneously. It extracts every material claim from the represented narrative, forms testable hypotheses about what the live systems should show if those claims are accurate, investigates each hypothesis against actual retrieved system data, and follows threads wherever the evidence leads. The output is a structured finding for every claim it can reach — with sources, with financial implications, and with a cryptographic chain of custody that makes every conclusion verifiable.

---

## The Problem

Every person in a position of authority receives representations they cannot independently verify. The seller controls the data room. Management controls the board package. Regional leadership controls the location report.

Data reconciliation tools exist. ETL validation systems exist. Financial audit software exists. What does not exist is an AI reasoning system that performs genuine investigation across both surfaces — one that forms hypotheses, follows threads, identifies the second-order implications of a divergence, and produces findings that are as specific to this company and this moment as the divergence itself.

The difference between data reconciliation and investigative reasoning is the difference between "these two numbers do not match" and "the CIM claims customer concentration is below 20% — the CRM shows the top customer represents 34% of revenue — here is the financial implication for the deal thesis and here is what we found when we followed that thread."

---

## Use Cases

### Sell-Side Preparation

Investment banks preparing a CIM need confidence the numbers they are putting in front of buyers will hold up under scrutiny. Running Verus before going to market surfaces divergences between the narrative and the live systems before a buyer finds them. That is the cleanest commercial entry point for the product — the sell-side has full system access, strong incentive to avoid credibility problems in diligence, and a direct line to the deal fees that make the engagement fee irrelevant.

**The question Verus answers:** *Will these numbers hold up when a buyer connects to the live systems?*

### Board-Level Management Verification

Boards receive quarterly management reports. They ask questions. They get answers prepared by management. They have no independent window into the operating reality those reports describe. Verus gives boards the same verification capability used in diligence — applied to ongoing governance rather than a one-time transaction. Independent verification tools reduce board liability. That makes this a natural second market.

**The question Verus answers:** *Does the operating system confirm what management reported to the board?*

### Private Equity Confirmatory Diligence

A deal team has 2–4 weeks to validate an acquisition thesis against a data room that management prepared. Post-acquisition surprises are the primary driver of PE underperformance. One missed issue in a deal can cost tens of millions. Verus connects to the target's live operating systems and validates every material claim in the data room against actual system evidence before close.

**The question Verus answers:** *Does the live system confirm what the CIM says?*

### Multi-Location Operations Verification

A CEO or COO receives location performance reports from regional managers. Verus connects to the actual systems at each location and validates each location's reported performance against its actual system data. Operates alongside Huckle — Huckle provides continuous signal monitoring, Verus provides the periodic countercheck.

**The question Verus answers:** *Does the location system confirm what the regional manager reported?*

### Institutional Investor Portfolio Monitoring

A PE firm managing 10 portfolio companies receives monthly performance packages from each. Verus validates those packages against each company's operating systems, creating an independent signal layer on top of management reporting across the entire portfolio.

**The question Verus answers:** *Across the portfolio, where does the reported narrative diverge from operating reality?*

---

## What Verus Does

### Act 1 — The Countercheck Report

Verus ingests the represented narrative and connects to the underlying operating systems simultaneously. The AI reasoning engine operates in five phases:

1. **Claim extraction** — reads every document and extracts explicit and implicit operating claims, classified by domain and scored for materiality
2. **Hypothesis formation** — for each material claim, forms a testable hypothesis about what live system data should show if the claim is accurate
3. **System investigation** — queries the live systems to test each hypothesis, constructing queries from the specific evidence available rather than running fixed templates
4. **Thread following** — when a divergence is found, asks what could explain it, forms secondary hypotheses, and goes back into both surfaces for corroborating or contradicting evidence
5. **Financial implication** — for every Divergent finding, calculates the impact on the deal thesis or operating plan

**Example finding:**

> **COM-001 — Customer Concentration**
> Claim: "No single customer represents more than 20% of revenue" *(CIM p.31, §7)*
> Evidence: Salesforce CRM closed_won_history — top customer: $16.4M of $48.2M LTM revenue (34.0%)
> Verdict: **DIVERGENT**
> Implication: Revenue concentration risk not disclosed. Single-customer loss scenario: –34% revenue, EBITDA moves from $22.4M to approximately $6.8M at current margin structure.
> Thread: Secondary investigation found two additional customers at 18% and 14% combined — effective top-3 concentration of 66%.

Every finding shows:

| Field | Content |
|---|---|
| Claim | Exact assertion as stated, with source citation |
| Evidence | What the live system actually shows, with query details |
| Verdict | Confirmed / Divergent / Unverifiable |
| Implication | Financial or operational impact where Divergent |
| Evidence chain | Cryptographic hash linking document source → system query → finding |

Findings that cannot meet the three-source evidence requirement are classified **Unverifiable** and surfaced as data gaps — never as evidence findings. No speculation beyond what the evidence directly supports.

### Act 2 — Intelligence Chat

A finding catches your attention. Instead of scheduling another call or waiting for another memo, you ask. The system has access to the complete ingested narrative and the complete live system dataset. Every answer is grounded in retrieved evidence. Every answer cites its source.

Intelligence Chat refuses to speculate beyond what the evidence supports. When it does not know, it says so and tells you where the gap is.

### Act 3 — Plan Stress Test

Upload any forward-looking plan — a 100-day integration plan, an annual operating plan, a board-approved initiative list. Verus reads it against the operating reality it found in the live systems and produces a structured assessment of each initiative: assumption validity, execution risk, upside calibration, and gap identification.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│             Represented Narrative (Any Format)                   │
│  CIM · Board package · Management report · Investor update       │
│  PDF · Excel · PowerPoint · Word · Scanned documents             │
└────────────────────────────┬────────────────────────────────────┘
                             │ Ingestion Pipeline
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Knowledge Base                                │
│      Semantic chunks · Claims index · Hybrid vector search        │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
┌─────────────────────┐       ┌─────────────────────────────────┐
│  Countercheck        │       │      Live System Connectors      │
│  Reasoning Engine    │◄─────►│                                  │
│  (proprietary)       │       │  Canonical schema · Normalizer   │
│                      │       │  CRM · ERP · CMMS · SQL · REST   │
│  Claim extraction    │       │  Read-only · Time-bounded        │
│  Hypothesis forming  │       │  Credential revocation on close  │
│  System investigation│       │  Full query audit log            │
│  Thread following    │       └─────────────────────────────────┘
│  Finding formatting  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Evidence Ledger (proprietary)                  │
│  Cryptographic chain of custody · Hash-linked entries            │
│  Document source → System query → Finding → Report root hash     │
│  INSERT-only · Tamper-evident · Verifiable post-engagement       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
   │  Countercheck │  │ Intelligence │  │  Plan Stress     │
   │  Report       │  │ Chat         │  │  Test            │
   └──────────────┘  └──────────────┘  └──────────────────┘
```

### Connector Architecture

The hardest engineering problem in this product is not AI reasoning. It is reliable integration with heterogeneous enterprise systems — different schemas, custom fields, inconsistent data quality, and varied permission models.

Every connector implements a two-method interface contract:

```python
class BaseConnector:
    def fetch(self, query_type: str, params: QueryParams) -> RawResult:
        """Retrieve raw data from the source system."""

    def normalize(self, raw: RawResult) -> list[CanonicalRecord]:
        """Convert system-native format to the Verus canonical schema."""
```

The canonical schema insulates the reasoning engine from system-specific data formats. A revenue record from Salesforce and a revenue record from Dynamics 365 arrive at the reasoning engine in identical structure. The connector absorbs the translation complexity so the reasoning engine never needs to know which system it is looking at.

Field mapping is configuration-driven, not hardcoded. Each deployment specifies the mapping from source system field names to canonical field names, handling the custom field reality of every enterprise ERP. Data quality scoring runs at normalization time — the reasoning engine knows the confidence level of every data point it uses.

Supported system categories:
- **CRM:** Salesforce, HubSpot, Dynamics CRM
- **ERP:** Dynamics 365 F&O, SAP (documented stub), generic REST
- **CMMS:** Fiix, MaintainX
- **SQL:** Direct connection via ODBC/psycopg2
- **REST:** Configuration-driven generic connector for any JSON API

### Evidence Ledger

Every piece of evidence used in every finding is committed to a cryptographic hash chain before the finding is included in the report.

```
chunk_hash   = SHA-256(chunk_id | document_id | engagement_id | text | citation)
query_hash   = SHA-256(query_id | engagement_id | connector | intent | params_hash | records)
finding_hash = SHA-256(finding_id | engagement_id | code | claim_citation | evidence_citation | verdict)
report_hash  = SHA-256(engagement_id | sorted(finding_hashes) | assembled_at | s3_key)
```

Each entry stores the hash of the preceding entry (`prev_entry_hash`), forming a chain. The `evidence_ledger` table enforces INSERT-only at the database level — UPDATE and DELETE operations are rejected by database rules, not application logic. The report root hash is embedded in the delivered report. Any party with the hash can verify the chain was intact at delivery.

### CASA Governance

Every system query the AI reasoning engine proposes passes through the CASA governance gate before execution. CASA produces an audit-grade record of every governed action and enforces the read-only constraint at the governance layer — not just the application layer.

---

## The Three-Product Stack

| Product | Function | When |
|---|---|---|
| **CASA** | AI governance — govern any AI agents operating in your systems | Ongoing |
| **Huckle** | Signal intelligence — continuous operational monitoring and decision support | Ongoing |
| **Verus** | Institutional verification — validate any represented narrative against live system reality | Periodic |

These three products form a coherent operating intelligence architecture. CASA governs AI actions. Huckle monitors operational signals continuously. Verus verifies reported narratives periodically. A PE firm that uses Verus to validate a target before acquisition, deploys Huckle to monitor the portfolio company after close, and governs AI agents with CASA has complete operating intelligence across the full deal lifecycle.

**Verus and Huckle are complementary, not redundant.** Huckle tells you what is happening. Verus tells you whether the story you were told matches what happened.

---

## Repository Structure

```
verus-public/
├── packages/
│   ├── api/                    # FastAPI application and route definitions
│   │   ├── app.py              # Application factory
│   │   ├── auth.py             # JWT authentication
│   │   ├── routes.py           # All API endpoints under /v1/
│   │   └── schemas.py          # Typed request/response models
│   ├── connectors/
│   │   └── base.py             # BaseConnector interface contract
│   ├── core/
│   │   ├── enums.py            # All shared enums
│   │   ├── constants.py        # All shared constants
│   │   └── schemas/            # Pydantic domain models
│   │       ├── finding.py      # Finding · verdict · materiality · confidence
│   │       ├── engagement.py   # Engagement lifecycle
│   │       ├── document.py     # Document and chunk models
│   │       ├── ledger.py       # Evidence ledger entry schemas
│   │       └── connector.py    # Connector health and query models
│   ├── db/
│   │   └── connection.py       # Connection pool with RLS enforcement
│   └── ingestion/
│       ├── chunker.py          # Semantic chunking with citation preservation
│       └── normalizers/        # PDF · DOCX · XLSX · PPTX processors
├── tests/
│   └── unit/
│       ├── test_core/          # Schema validation · enum coverage · utilities
│       └── test_ingestion/     # Chunker contract tests
├── demo/
│   └── VerusDemo.jsx           # Interactive React demo
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pyproject.toml
```

**The reasoning engine, evidence ledger implementation, plan stress-test engine, and connector implementations are proprietary and not included in this repository.**

---

## Data Model

### Finding

```python
class Finding(BaseModel):
    finding_id: UUID
    engagement_id: UUID
    finding_code: str                    # e.g. "COM-001", "OPS-003"
    domain: ClaimDomain                  # COMMERCIAL | OPERATIONAL | FINANCIAL | ...
    verdict: FindingVerdict              # CONFIRMED | DIVERGENT | UNVERIFIABLE
    materiality: FindingMateriality      # HIGH | MEDIUM | LOW | IMMATERIAL
    confidence: float                    # 0.0 – 1.0

    management_claim: str
    management_claim_citation: str       # Document · section · page
    system_evidence_summary: str
    system_evidence_citation: str        # System · query · date range
    divergence_summary: str | None       # DIVERGENT findings only

    created_at: datetime
```

### Evidence Ledger Entry

```python
class LedgerEntry(BaseModel):
    ledger_id: UUID
    engagement_id: UUID
    entry_type: LedgerEntryType          # CHUNK | QUERY | FINDING | REPORT | CASA_VERDICT
    object_id: UUID
    object_hash: str                     # SHA-256 of immutable identity fields
    prev_entry_hash: str | None          # Chain link to preceding entry
    recorded_at: datetime
    recorded_by: str
```

### Claim Domains

```python
class ClaimDomain(str, Enum):
    COMMERCIAL    = "commercial"
    OPERATIONAL   = "operational"
    FINANCIAL     = "financial"
    HUMAN_CAPITAL = "human_capital"
    TECHNOLOGY    = "technology"
    MARKET        = "market"
```

---

## API Surface

```
GET  /v1/health
GET  /v1/engagements
GET  /v1/engagements/{id}
POST /v1/engagements/{id}/reasoning/runs
GET  /v1/engagements/{id}/findings
POST /v1/engagements/{id}/chat/sessions
POST /v1/engagements/{id}/chat/{sid}/messages
GET  /v1/engagements/{id}/chat/{sid}
POST /v1/engagements/{id}/plan/runs
```

---

## Running Locally

```bash
git clone https://github.com/The-Resonance-Institute/verus-public.git
cd verus-public
pip install -r requirements.txt -r requirements-dev.txt

# Unit tests — no database required
python -m pytest tests/ -m "not integration" -q

# Full test suite — requires Docker
docker compose up -d
python -m pytest tests/ -m "integration" -q
```

---

## Intellectual Property

Verus is a product of The Resonance Institute, LLC. The reasoning engine, evidence ledger chain-of-custody implementation, plan stress-test engine, and CASA governance integration are proprietary and not included in this repository.

CASA (Constitutional AI Safety Architecture) is covered by USPTO Provisional Patent #63/987,813.

---

## Contact

**The Resonance Institute, LLC** · Huntington Beach, California

[GitHub](https://github.com/The-Resonance-Institute) · [Verus](https://github.com/The-Resonance-Institute/verus-public) · [Huckle](https://github.com/The-Resonance-Institute/huckleberry-public) · [CASA](https://the-resonance-institute.github.io/casa-runtime)

For pilot engagement inquiries, acquirer conversations, or technical diligence: contact via GitHub.
