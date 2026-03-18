import { useState, useEffect, useRef, useCallback } from "react";

const FONT_LINK = document.createElement("link");
FONT_LINK.rel = "stylesheet";
FONT_LINK.href = "https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Instrument+Serif:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap";
document.head.appendChild(FONT_LINK);

const ENGAGEMENT = {
  name: "Project Meridian",
  target: "Atlas Climate Systems",
  sponsor: "Ridgeline Capital → Apex Industrial Partners",
  dealSize: "$148.0M",
  statedEBITDA: "$22.4M",
  verusEBITDA: "$20.2M",
  statedMultiple: "6.6x",
  verusMultiple: "7.3x",
  stage: "Confirmatory Diligence — Week 3 of 6",
  window: "Jan 6 – Feb 14, 2026",
  products: "Commercial RTUs (5–150 ton) · Custom AHUs · Process Chillers",
  markets: "Commercial construction 44% · Healthcare 31% · Data centers 18% · Industrial 7%",
  plants: "Atlanta GA (flagship RTU) · Charlotte NC (custom AHUs) · Memphis TN (chillers)",
  employees: "847",
  connectors: ["Dynamics 365 F&O", "Salesforce CRM", "Fiix CMMS", "SQL Data Warehouse"],
};

const FINDINGS = [
  {
    id: "COM-001", domain: "Commercial", verdict: "DIVERGENT", materiality: "HIGH", confidence: 0.93,
    title: "Revenue Recognition — Pull-Forward & Reclassification",
    claim: "Net revenue grew 21.4% YoY from $39.6M to $48.1M in FY2025, driven by healthcare vertical expansion (Atlas MediCool line) and new data center customer acquisitions. Growth was broad-based across all three facilities.",
    claimSource: "CIM p.14, §3.2 Revenue Analysis",
    evidence: "Unit shipments: 2,847 units FY2025 vs 2,610 FY2024 (+9.1%). Avg selling price +4.2%. Implied organic revenue: ~$45.0M. Gap to stated $48.1M: $3.1M. Four distinct components identified in Dynamics 365.",
    evidenceSource: "Dynamics 365 F&O — production orders, shipment log, service contract ledger, warranty claims DB — queried Jan 14, 2026",
    divergence: "Stated revenue includes: (1) $4.1M service contract pull-forward — Q3 FY2025 billing date change moved FY2026 renewals into FY2025; (2) $2.8M warranty replacement reclassification — warranty units shifted from cost to revenue; (3) $1.6M BuildRight distributor stocking with 90-day return window open at deal signing; (4) 4 additional distributor orders ($3.6M) with open return windows not disclosed.",
    financialImpact: "FY2026 Q1 contract billings running 61% below prior year Q1 — pull-forward already depleting forward revenue. Total open return window exposure: $5.2M. Organic unit growth 9.1%, not 21.4%.",
    valuationImpact: "True LTM revenue: $39.6M–$43.9M. EBITDA margin on true revenue: 28.4%–31.1%. Growth story supporting 6.6x is built on non-recurring items. Multiple not supportable on 9% organic unit growth.",
    threads: [
      "Service contract ledger: FY2026 Q1 billings $1.8M vs $4.6M prior year Q1 — pull-forward already consuming forward revenue at deal signing",
      "BuildRight HVAC Distributors: $1.6M stocking order Nov 2025, 90-day return window expires Feb 15, 2026 — one day after diligence window closes. Not disclosed in data room",
      "4 additional distributor stocking orders placed Q3–Q4 FY2025 totaling $3.6M — all with open return windows. Verus queried CRM for all orders with return provisions and found these",
      "Warranty reclassification memo (CMMS WO-2025-0847 attachment): CFO memo dated Q2 FY2025 directing reclassification. Found in CMMS work order system, not in financial disclosures",
    ],
    ledgerHash: "a3f7e2b1c9d4f8e6a2b5c8d1e4f7a3b6c9d2e5f8a1b4c7d0e3f6a9b2c5d8e1f4",
  },
  {
    id: "COM-002", domain: "Commercial", verdict: "DIVERGENT", materiality: "HIGH", confidence: 0.91,
    title: "Customer Concentration — Meridian Healthcare & DataVault",
    claim: "Atlas serves a diversified customer base of 847 active accounts. No single customer represents more than 12% of LTM revenue. Top 10 customers represent 38% of revenue, consistent with prior years.",
    claimSource: "CIM p.31, §7.1 Customer Analysis",
    evidence: "Salesforce CRM closed_won_history: Meridian Healthcare Systems $13.1M LTM = 27.3% of stated $48.1M. DataVault Centers $6.8M = 14.1%. Combined top-2: 41.4%. Management's 12% figure counts only shipped Meridian projects ($5.2M = 10.8%) — excludes $7.9M in permit-hold and engineering-phase projects shown as 90%-probability in CRM.",
    evidenceSource: "Salesforce CRM — closed_won_history, opportunity pipeline, account records, call logs — queried Jan 14, 2026",
    divergence: "Meridian Children's Pavilion ($4.8M): Cook County environmental permit filed June 2025, average review 14 months — does not ship 2026. DataVault Phoenix ($5.4M): site requires 480V 3-phase utility upgrade, 9-month lead time quoted — cannot accept equipment on DataVault's timeline. Combined 2026 revenue at risk: $10.2M.",
    financialImpact: "Meridian CFO James Whitmore departed Nov 2025. Dec 2025 CRM call notes: 'capital uncertainty at Meridian, recommend we stay close.' Not disclosed in data room. Meridian full-loss scenario: EBITDA -$3.7M at current margin, enterprise value -$24.4M at 6.6x.",
    valuationImpact: "12% concentration claim is technically defensible only if LOI-stage projects are excluded. Management knew about the permit hold when the CIM was written (CIM dated Oct 2025, permit filed June 2025). The omission is not an oversight.",
    threads: [
      "Meridian CFO James Whitmore: departed Nov 2025, joined Mercy Regional Health. CRM call log Dec 2025: 'capital uncertainty at Meridian' — not surfaced in data room. Verus found this in CRM account notes, not financial disclosures",
      "Cook County environmental review: Meridian Children's Pavilion permit filed June 2025. County records show environmental review averaging 14 months in this district. Project realistically ships Q3 2027 at earliest",
      "DataVault Phoenix: Atlas project notes confirm 480V service upgrade required. Utility company quoted 9-month lead time. DataVault's project schedule assumed equipment delivery Q2 2026 — impossible without the service upgrade",
      "DataVault Centers ($6.8M, 14.1%): one Phoenix project represents $5.4M of that = 11.2% of revenue from a single data center. CIM's diversification claim requires excluding both Meridian and DataVault concentrations simultaneously",
    ],
    ledgerHash: "b4e8f3c2d7a1e5f9b3c6d0e4f8a2b7c1d5e9f3a7b2c6d1e5f9a4b8c3d7e2f6a1",
  },
  {
    id: "OPS-003", domain: "Operations", verdict: "DIVERGENT", materiality: "HIGH", confidence: 0.94,
    title: "Backlog Quality — $41.2M Gross vs $19.4M Firm",
    claim: "$41.2M firm backlog as of December 31, 2025, representing 10.2 months of forward revenue at LTM run rate. Backlog has grown 34% year-over-year, reflecting strong market demand and Atlas's competitive positioning.",
    claimSource: "CIM p.22, §5.1 Backlog Analysis",
    evidence: "Dynamics 365 gross order book: $41.2M confirmed. Salesforce CRM contract terms and deposit records: firm (deposited, unconditional, no return provisions) = $19.4M. Conditional or at-risk: $21.8M across four categories.",
    evidenceSource: "Dynamics 365 F&O order book + Salesforce CRM contract terms + credit ledger — queried Jan 14–15, 2026",
    divergence: "Breakdown of $41.2M: Firm deposited unconditional $19.4M | Meridian permit-hold $8.3M | Distributor stocking w/ return rights $5.2M | Cornerstone Commercial GC-conditional $4.1M | LOI-only no PO $4.2M. True firm backlog: $19.4M = 4.8 months, not 10.2.",
    financialImpact: "Year-over-year backlog growth of 34% is real in gross terms — but FY2024 had $0 in distributor stocking orders. The growth is almost entirely from a new category with return provisions that did not previously exist. Backlog mix has deteriorated significantly.",
    valuationImpact: "At $41.2M gross backlog, Atlas trades at 0.28x (reasonable for sector). At $19.4M firm backlog, 0.59x — high end of industrial HVAC comparables. Revenue certainty in Q3–Q4 FY2026 that underpins the deal thesis is not present.",
    threads: [
      "Cornerstone Commercial Development ($4.1M, 3 orders): entered by regional sales manager AFTER Atlas credit team placed Cornerstone on credit hold Oct 2025. Credit hold not visible in Salesforce sales module — appears orders entered to hit Q4 pipeline targets",
      "Cornerstone existing project (Charlotte AHU installation, $880K): 90 days past due on progress payment. Dynamics 365 collections memo Oct 2025 not cross-referenced in data room",
      "LOI-only backlog ($4.2M, 6 opportunities): 3 of 6 are in hospitality and retail sectors where construction lending has tightened materially Q4 2025. CRM probability ratings unchanged since Q3 — not updated to reflect market conditions",
      "34% backlog growth: FY2024 backlog composition was 94% firm deposited. FY2025 backlog composition is 47% firm deposited. Quality of growth has been masked by the gross number",
    ],
    ledgerHash: "c5f9a4d8b3e7f2a6c1d5e0f4b8a3c7d2e6f1a5b0c4d8e3f7a2b6c0d4e8f3a7b1",
  },
  {
    id: "FIN-004", domain: "Financial", verdict: "PARTIAL", materiality: "MEDIUM", confidence: 0.88,
    title: "EBITDA Quality — Warranty Pattern & Adjustment Characterization",
    claim: "Adjusted EBITDA of $22.4M representing a 31.0% margin. Adjustments include $1.8M one-time facility consolidation costs (Charlotte expansion) and $0.6M non-recurring legal settlement. Underlying EBITDA margin has expanded 280bps over three years.",
    claimSource: "CIM p.18, §4.2 Financial Performance",
    evidence: "Dynamics 365 warranty claims DB: FY2025 $2.3M, FY2024 $2.1M, FY2023 $1.9M. Three-year average $2.1M. Excluded from adjusted EBITDA in all three years as 'non-recurring quality remediation.' Charlotte consolidation: $1.1M genuine one-time, $0.7M capitalized maintenance expensed (same treatment FY2024: $0.6M).",
    evidenceSource: "Dynamics 365 F&O — warranty claims database, EBITDA bridge, cost center detail — queried Jan 15, 2026",
    divergence: "FY2023 compressor supplier defect ($890K) was genuinely non-recurring. The remaining $1.2M–$1.4M annual warranty is structural — refrigerant fitting specification issue in FY2020–2022 production (approx 4,200 units in field). Atlas engineering documented this in CMMS WO-2023-1842. Known for 3 years, never disclosed.",
    financialImpact: "True recurring EBITDA: $19.6M–$20.8M (midpoint $20.2M) = 27.9% margin. Margin expansion of 280bps is real mathematically but driven by warranty reclassification and one-time add-backs — clean underlying expansion approximately 60bps.",
    valuationImpact: "$2.2M EBITDA restatement at 6.6x = $14.5M valuation impact. True deal multiple on recurring EBITDA: 7.3x. At the high end of industrial HVAC comparable transactions (sector range 5.5x–7.5x).",
    threads: [
      "CMMS WO-2023-1842: 'Refrigerant Line Fitting Specification — Fleet Impact Assessment' Aug 2023. Identifies FY2020–2022 vintage units (est. 4,200 in field) with elevated leak risk. Estimated warranty exposure $1.1M–$1.6M annually through FY2028. Filed as CMMS attachment, not in data room financials",
      "Charlotte consolidation pattern: FY2024 EBITDA bridge shows $0.6M 'one-time' capitalized maintenance. FY2025 shows $0.7M same treatment. This is how Atlas manages maintenance expense timing — not genuine non-recurring items",
      "Margin expansion of 280bps: FY2023 base includes the $890K genuine non-recurring compressor issue. Remove that from the base and expansion is approximately 60bps. The 280bps figure is driven by comparing against an artificially depressed FY2023",
    ],
    ledgerHash: "d6a0b5e9c4f8d3a7e2b6f1c5d9a4e8b3f7c2d6a1e5f0b4c8d3e7f2a6b1c5d9e4",
  },
  {
    id: "OPS-005", domain: "Operations", verdict: "DIVERGENT", materiality: "HIGH", confidence: 0.89,
    title: "Charlotte OEE, OSHA Exposure & $1.8M Deferred Maintenance",
    claim: "OEE of 81% across all facilities, up from 74% in FY2023. Charlotte facility expansion completed Q2 FY2025, adding 23% capacity. Capital investment program complete — no material capex required in the near term.",
    claimSource: "CIM p.28, §6.3 Operations & Capacity",
    evidence: "Fiix CMMS OEE dashboard: Atlanta 84.2% (confirmed), Memphis 79.3% (confirmed), Charlotte 67.1% (vs 81% claimed). Charlotte Line 2 manifold press in OSHA hold since Sep 14, 2025 — 147 days at query date, no inspection completed, no closure documented.",
    evidenceSource: "Fiix CMMS — OEE dashboard, work order history, OSHA 300 log, PM compliance tracker, asset health records — queried Jan 16, 2026",
    divergence: "Charlotte OEE: 67.1% vs claimed 81% — 13.9 point gap. Root cause: refrigerant manifold assembly cell (Line 2) taken offline after OSHA recordable Sep 14, 2025. Press in 'pending inspection' 147 days. $1.8M deferred maintenance across 14 work orders marked 'deferred pending budget approval' dating Q1 FY2025. 3 assets past manufacturer service interval.",
    financialImpact: "Charlotte OEE gap = $3.2M annual revenue capacity unavailable. Effective capacity from 'expansion': 8%, not 23% — Line 2 constraint limits throughput of new floor space. OSHA recordable rate: 1.5/100 employees vs industry avg 0.8. Workers comp reserve: $180K vs estimated liability $490K–$520K.",
    valuationImpact: "Near-term capex not in plan: $85K–$120K OSHA remediation, $1.8M deferred maintenance, $310K–$340K WC reserve top-up. Total: $2.2M–$2.3M. 'No material capex required' is false. Charlotte OEE recovery to 81%: 12+ months on corrected plan, not 6 months as 100-day plan assumes.",
    threads: [
      "OSHA recordable Sep 14, 2025: technician hand laceration on Line 2 manifold press (non-standard operation). Press offline 147 days. No OSHA inspection completed. No closure. Atlas has not disclosed this incident or the press status to Apex",
      "Charlotte OSHA recordable rate: 3 recordables in prior 24 months = 1.5/100 employees vs 0.8 industry average. Elevated safety profile predates September — systemic issue, not isolated event",
      "Refrigerant recovery system: 7 months past manufacturer-recommended service interval. EPA Section 608 compliance requires annual certified inspection. Non-compliance risk: EPA fine up to $44,539/day/violation",
      "Overhead crane: load-rated inspection overdue 6 months. OSHA 29 CFR 1910.179 requires annual qualified engineer inspection. Last inspection March 2025. Operating uninspected overhead crane is citable OSHA violation",
      "Workers comp reserve: Dynamics 365 current reserve $180K. Cross-reference CMMS incident log + industry settlement patterns: estimated liability $490K–$520K. Reserve underfunded $310K–$340K. Not disclosed",
      "Charlotte '23% capacity expansion': confirmed floor space and equipment installed. But 23% assumes Line 2 at full throughput. With Line 2 constrained by press outage, effective new capacity: ~8%. CIM capacity claim is 2.9x operating reality",
    ],
    ledgerHash: "e7b1c6f0d5a9e4b8f3c7d2a6e1b5f9c4d8a3e7b2f6c1d5a0e4b9f3c8d2a7e1b6",
  },
  {
    id: "FIN-006", domain: "Financial", verdict: "DIVERGENT", materiality: "MEDIUM", confidence: 0.82,
    title: "Commodity Exposure — Steel, Copper & Refrigerant Headwinds",
    claim: "Atlas actively manages commodity exposure through a forward purchasing program. Copper and steel costs are locked for Q1–Q2 FY2026 at favorable rates, providing cost visibility and margin protection through the near term.",
    claimSource: "CIM p.19, §4.4 Cost Structure",
    evidence: "Dynamics 365 purchase contracts: Copper locked $3.84/lb through Jun 2026 (spot $4.71/lb — genuinely favorable). Steel locked $847/ton through Mar 2026 only — not Q2. Steel spot $934/ton. Refrigerant R-410A: no hedging program, +34% YoY (EPA AIM Act phasedown). R-32 transition not in product roadmap.",
    evidenceSource: "Dynamics 365 F&O — purchase contracts, commodity purchase history — LME copper spot Jan 14, 2026 — EPA AIM Act filings — queried Jan 16, 2026",
    divergence: "Steel contracts expire March 2026 (Q1), not Q2 as stated in CIM. Atlas_Steel_Supply_Agreement_2025.pdf p.3 in data room shows termination date March 31, 2026 — CIM description is inaccurate. 100% of steel becomes spot in Q2 at $934/ton vs locked $847/ton. Copper 38% unhedged ($2.4M annualized at spot). Refrigerant 8% of direct material cost, no hedge, $680K annual headwind.",
    financialImpact: "Combined unhedged commodity headwind hitting Q2–Q4 FY2026: Steel $1.1M annualized | Copper unhedged portion $420K | Refrigerant $680K. Total: $2.2M not in management FY2026 projections. FY2026 EBITDA at risk of 10%–15% H2 shortfall.",
    valuationImpact: "$2.2M commodity headwind at 6.6x = $14.5M. Compound with FIN-004 warranty restatement ($14.5M): combined $29M valuation consideration. Steel contract discrepancy (CIM vs actual contract document) suggests the CIM was not reviewed against source documents before distribution.",
    threads: [
      "Steel contract discrepancy: CIM states 'Q1–Q2 FY2026' coverage. Actual contract in data room (Atlas_Steel_Supply_Agreement_2025.pdf, p.3) shows termination date March 31, 2026. CIM description does not match the document it references — this was findable with basic data room review",
      "R-410A phasedown: EPA AIM Act reducing production allowances 40% in 2026. Atlas equipment line includes R-410A units through FY2026 model year. Refrigerant supply tightening into a price spike. No transition timeline in product roadmap documents found in data room",
      "Copper 38% unhedged: purchase history shows spot copper purchases for custom and short-run orders. The forward contracts cover standard production volumes — custom work is structurally always spot-priced. This is not a risk management failure, it is a permanent structural exposure",
    ],
    ledgerHash: "f8c2d7a1e6b0f5c9d4a8e3b7f2c6d1a5e0b4f9c3d7a2e6b1f5c0d4a9e3b8f2c7",
  },
];

const PLAN_ITEMS = [
  {
    id: "P-03", title: "Charlotte OEE Recovery — Process Engineering", finding: "OPS-005",
    assumption: "Hire 2 process engineers Q1, implement lean manufacturing program Q2, target OEE improvement from current 74% to 85% by month 6. Projected throughput recovery: $3.8M annualized. Investment: $380K.",
    planTarget: "85% OEE by Month 6", verdict: "INVALID", risk: "HIGH",
    assessment: "The Charlotte OEE gap is not a process problem. It is a physical constraint — a manifold press in OSHA hold 147 days, 3 critical assets past service interval, and an elevated safety culture (1.5 recordable rate vs 0.8 industry). Process engineers and lean consultants cannot fix an OSHA-held press or catch up $1.8M deferred maintenance. The plan's OEE baseline of 74% is also wrong — Verus found 67.1% in Fiix. The gap is 13.9 points, not 7.",
    correctedSequence: "Month 1–3: OSHA inspection and press safety remediation ($85K–$120K). Month 3–9: Deferred maintenance program ($1.8M). Month 6+: Safety culture intervention, OSHA VPP pathway. Month 9+: Process improvement investment. Realistic Month 6 OEE: 73%–76%. Month 12 OEE of 85% achievable on corrected sequence.",
    yearOne: "$1.4M vs plan $3.8M", yearTwo: "$3.6M (achievable on corrected plan)",
  },
  {
    id: "P-07", title: "Healthcare Vertical Expansion — Meridian Pipeline", finding: "COM-002",
    assumption: "Convert Meridian Children's Pavilion ($4.8M) and Meridian Oncology Center ($3.1M) in H1 2026. Healthcare grows from 31% to 38% of revenue. Investment: $220K dedicated healthcare resources.",
    planTarget: "$7.9M Meridian revenue H1 2026", verdict: "AT RISK", risk: "HIGH",
    assessment: "Meridian Children's Pavilion is in Cook County environmental review — 14-month average timeline from June 2025 filing. Does not ship H1 2026. Meridian CFO departed Nov 2025, capital freeze concern in CRM notes. Oncology Center ($3.1M) is engineering phase only — no PO, 18-month horizon. Plan's $7.9M H1 Meridian assumption is not achievable.",
    correctedSequence: "Meridian Pavilion: H2 2026 at earliest, more likely Q1 2027. Oncology Center: pipeline only, 18-month horizon. Immediately qualify replacement healthcare accounts. H1 2026 healthcare revenue: $5.2M (Meridian Regional shipped only).",
    yearOne: "$5.2M vs plan $7.9M", yearTwo: "Recoverable if Pavilion permits Q1 2027",
  },
  {
    id: "P-11", title: "Commodity Cost Management — FY2026 Stability", finding: "FIN-006",
    assumption: "Raw material costs stable through FY2026 based on existing forward contracts. No incremental commodity cost pressure in financial projections. No hedging budget allocated.",
    planTarget: "FY2026 COGS consistent with FY2025", verdict: "INVALID", risk: "MEDIUM",
    assessment: "Steel contracts expire March 2026 (Q1), not Q2 as plan assumes. 100% of steel becomes spot in Q2 at $934/ton vs $847/ton locked — $1.1M annualized headwind starting Q2. Copper 38% unhedged at current spot ($420K). Refrigerant R-410A +34% YoY, no hedging program, $680K annual headwind. Combined $2.2M commodity cost pressure not in FY2026 projections.",
    correctedSequence: "Immediately extend steel contracts or execute Q2–Q4 hedges. Evaluate R-410A to R-32 transition in FY2027 model year. Budget $2.2M commodity headwind in H2 FY2026 financial plan. Assign commodity risk management to CFO as immediate priority.",
    yearOne: "-$2.2M vs plan (headwind not recovery)", yearTwo: "Manageable with hedging program in place",
  },
];

const CHAT_CONTEXT = `You are the Verus Intelligence Chat engine for Project Meridian — confirmatory diligence on Atlas Climate Systems, a commercial HVAC manufacturer. $148M acquisition by Apex Industrial Partners from Ridgeline Capital.

FULL FINDINGS:

COM-001 DIVERGENT HIGH (confidence 0.93): Revenue $48.1M stated. True organic revenue $45.0M based on 9.1% unit volume growth and 4.2% ASP increase. $3.1M gap from: (1) $4.1M service contract pull-forward — Q3 FY2025 billing date change moved FY2026 renewals into FY2025, FY2026 Q1 billings running 61% below prior year; (2) $2.8M warranty replacement reclassification — warranty units moved from cost to revenue; (3) $1.6M BuildRight distributor stocking with 90-day return window expires Feb 15, 2026 (one day after diligence window); (4) 4 additional distributor stocking orders $3.6M with open return windows. Total open return exposure $5.2M.

COM-002 DIVERGENT HIGH (confidence 0.91): Customer concentration claimed 12% max. Actual: Meridian Healthcare 27.3% ($13.1M LTM), DataVault Centers 14.1% ($6.8M). Meridian counted as 10.8% by management (shipped projects only, excluded permit-hold). Meridian Children's Pavilion $4.8M in Cook County environmental review, 14-month average timeline from June 2025 filing — does not ship 2026. DataVault Phoenix $5.4M blocked by 9-month utility service upgrade. Meridian CFO James Whitmore departed Nov 2025, Dec 2025 CRM notes flagged "capital uncertainty at Meridian." Combined 2026 revenue at risk $10.2M.

OPS-003 DIVERGENT HIGH (confidence 0.94): Backlog $41.2M claimed "firm" = 10.2 months. True firm (deposited, unconditional, no return rights): $19.4M = 4.8 months. Breakdown: firm $19.4M | Meridian permit-hold $8.3M | distributor stocking w/ returns $5.2M | Cornerstone Commercial GC-conditional $4.1M (on Atlas credit hold, orders entered after hold by sales manager hitting pipeline targets; existing Cornerstone project $880K 90 days past due) | LOI-only $4.2M. YoY growth of 34% is almost entirely new distributor stocking category that did not exist in FY2024.

FIN-004 PARTIAL MEDIUM (confidence 0.88): EBITDA $22.4M confirmed at stated level. Adjustments problematic: warranty costs $2.3M FY2025, $2.1M FY2024, $1.9M FY2023 excluded all three years as "non-recurring" — structural issue from refrigerant fitting specification in FY2020-2022 vintage (4,200 units in field), documented in CMMS WO-2023-1842, known 3 years, never disclosed. Charlotte "one-time" consolidation $0.7M is recurring capitalized maintenance pattern (same $0.6M in FY2024). True recurring EBITDA: $20.2M midpoint, 27.9% margin. True multiple: 7.3x.

OPS-005 DIVERGENT HIGH (confidence 0.89): OEE claimed 81% blended. Actual: Atlanta 84.2%, Memphis 79.3%, Charlotte 67.1%. Charlotte Line 2 manifold press OSHA hold since Sep 14, 2025 (147 days, no inspection, no closure, not disclosed to Apex). Charlotte OSHA recordable rate 1.5/100 vs 0.8 industry. $1.8M deferred maintenance across 14 work orders. 3 assets past service interval: Line 2 press (OSHA hold), refrigerant recovery system (EPA 608 compliance risk), overhead crane (OSHA 29 CFR 1910.179 annual inspection overdue). Workers comp reserve underfunded $310K-$340K. "23% capacity expansion" = 8% effective with Line 2 constrained. "No material capex required" is false — $2.2M-$2.3M near-term required.

FIN-006 DIVERGENT MEDIUM (confidence 0.82): Steel contracts expire March 31, 2026 (Q1 only — CIM says Q1-Q2, actual contract document says March 31). 100% steel spot in Q2 at $934/ton vs $847/ton locked = $1.1M annualized headwind. Copper 38% unhedged ($420K). Refrigerant R-410A +34% YoY EPA AIM Act phasedown, no hedging program ($680K). Combined $2.2M commodity headwind not in projections.

COMBINED VALUATION: Stated 6.6x. On $20.2M recurring EBITDA: 7.3x. Warranty restatement + commodity headwind at 6.6x = $29M valuation consideration.

100-DAY PLAN: P-03 Charlotte OEE invalid (process engineers can't fix OSHA hold/deferred maintenance, wrong baseline 74% vs actual 67.1%, year 1 recovery $1.4M not $3.8M). P-07 Meridian expansion at risk (Pavilion in permit hold, Oncology engineering phase only, $5.2M not $7.9M achievable H1). P-11 commodity stability invalid ($2.2M headwind not budgeted, steel contracts expire Q1 not Q2).

RULES: Answer with specific numbers. Cite which finding and which system. 2-4 sentences unless more detail requested. If data is unavailable say so explicitly. No deal recommendations. No speculation beyond evidence.`;

const SUGGESTED_QUESTIONS = [
  "Walk me through the Meridian Healthcare revenue piece by piece — what's actually at risk in 2026?",
  "The distributor stocking orders — how many, which distributors, what's the total exposure if they all come back?",
  "Charlotte — give me the straight answer. Is this a buy-and-fix or a structural problem?",
  "Run me the EBITDA scenario where warranty is recurring, Meridian Children's doesn't close, and commodity hits Q3.",
  "The Cornerstone credit hold — how did $4.1M in orders get entered after a credit hold?",
  "Strip the backlog to firm, deposited, unconditional only — what's the real number and what's the coverage?",
];

// ─── Styles ───────────────────────────────────────────────────────────────────
const C = {
  bg: "#0d0f12", bg2: "#141720", bg3: "#1a1d24",
  border: "#2a2d35", border2: "#1e2128",
  text: "#e8e6e1", textMuted: "#8a8880", textDim: "#4a5060",
  gold: "#c8a96e", red: "#e74c3c", green: "#27ae60", blue: "#4a7ab0",
  redBg: "#3a1a1a", goldBg: "#2a2a1a", greenBg: "#1a2a1a",
  redBorder: "#5a2a2a", goldBorder: "#4a4a2a", greenBorder: "#2a4a2a",
  mono: "'DM Mono', monospace", serif: "'Instrument Serif', serif", sans: "'DM Sans', sans-serif",
};

const verdictColor = (v) => v === "DIVERGENT" ? C.red : v === "PARTIAL" ? C.gold : C.green;
const verdictBg = (v) => v === "DIVERGENT" ? C.redBg : v === "PARTIAL" ? C.goldBg : C.greenBg;
const verdictBorder = (v) => v === "DIVERGENT" ? C.redBorder : v === "PARTIAL" ? C.goldBorder : C.greenBorder;

// ─── Components ───────────────────────────────────────────────────────────────
function Mono({ children, color, size = 10 }) {
  return <span style={{ fontFamily: C.mono, fontSize: size, color: color || C.textDim, letterSpacing: "1px" }}>{children}</span>;
}

function Label({ children }) {
  return (
    <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 6, marginTop: 16 }}>
      {children}
    </div>
  );
}

function ConfBar({ v }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 80, height: 3, borderRadius: 2, background: `linear-gradient(90deg, ${C.green} ${v * 100}%, ${C.border2} ${v * 100}%)` }} />
      <Mono color={C.textDim}>{Math.round(v * 100)}%</Mono>
    </div>
  );
}

function FindingCard({ f }) {
  const [open, setOpen] = useState(false);
  const vc = verdictColor(f.verdict);

  return (
    <div style={{ background: C.bg2, border: `1px solid ${verdictBorder(f.verdict)}`, borderLeft: `3px solid ${vc}`, borderRadius: 8, marginBottom: 16, overflow: "hidden" }}>
      <div style={{ padding: "16px 20px", cursor: "pointer", display: "flex", gap: 16, alignItems: "flex-start" }} onClick={() => setOpen(!open)}>
        <div style={{ flex: 1 }}>
          <Mono color={C.textDim}>{f.id} · {f.domain}</Mono>
          <div style={{ fontSize: 15, fontWeight: 500, color: C.text, marginTop: 4, lineHeight: 1.3 }}>{f.title}</div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
            <ConfBar v={f.confidence} />
            <span style={{ padding: "3px 8px", borderRadius: 3, fontFamily: C.mono, fontSize: 9, letterSpacing: 1, background: f.materiality === "HIGH" ? "#2a1a1a" : C.bg3, color: f.materiality === "HIGH" ? C.red : C.textDim, border: `1px solid ${f.materiality === "HIGH" ? "#4a2a2a" : C.border}` }}>{f.materiality}</span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8, flexShrink: 0 }}>
          <span style={{ padding: "4px 10px", borderRadius: 4, fontFamily: C.mono, fontSize: 10, letterSpacing: 1, background: verdictBg(f.verdict), color: vc, border: `1px solid ${verdictBorder(f.verdict)}` }}>{f.verdict}</span>
          <Mono color="#3a4050">{open ? "▲" : "▼"}</Mono>
        </div>
      </div>

      {open && (
        <div style={{ padding: "0 20px 20px", borderTop: `1px solid ${C.border2}` }}>
          <Label>Management Claim</Label>
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>{f.claim}</div>
          <div style={{ fontFamily: C.mono, fontSize: 11, color: "#4a7a9b", background: "#0a1520", padding: "6px 10px", borderRadius: 4, marginTop: 4 }}>↗ {f.claimSource}</div>

          <Label>System Evidence</Label>
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>{f.evidence}</div>
          <div style={{ fontFamily: C.mono, fontSize: 11, color: "#4a7a9b", background: "#0a1520", padding: "6px 10px", borderRadius: 4, marginTop: 4 }}>⊡ {f.evidenceSource}</div>

          <Label>Divergence</Label>
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>{f.divergence}</div>

          <Label>Financial Impact</Label>
          <div style={{ fontSize: 13, color: "#e8c87e", lineHeight: 1.6 }}>{f.financialImpact}</div>

          <Label>Valuation Consideration</Label>
          <div style={{ fontSize: 13, color: "#e87e7e", lineHeight: 1.6 }}>{f.valuationImpact}</div>

          {f.threads.length > 0 && (
            <>
              <Label>Thread Findings ({f.threads.length})</Label>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {f.threads.map((t, i) => (
                  <div key={i} style={{ display: "flex", gap: 10, padding: "8px 12px", background: C.bg, borderRadius: 4, border: `1px solid ${C.border2}` }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.gold, marginTop: 5, flexShrink: 0 }} />
                    <div style={{ fontSize: 12, color: "#8a8880", lineHeight: 1.5 }}>{t}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 16, padding: "8px 12px", background: "#0a0c0f", borderRadius: 4, border: `1px solid ${C.border2}` }}>
            <Mono color="#3a4050">LEDGER HASH</Mono>
            <span style={{ fontFamily: C.mono, fontSize: 10, color: "#2a5a3a", wordBreak: "break-all", flex: 1 }}>{f.ledgerHash}</span>
            <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "2px 6px", background: "#0a1a0a", borderRadius: 3, border: "1px solid #1a3a1a", flexShrink: 0 }}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.green }} />
              <Mono color={C.green} size={9}>INTACT</Mono>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanCard({ item }) {
  const [open, setOpen] = useState(false);
  const vc = item.verdict === "INVALID" ? C.red : item.verdict === "AT RISK" ? C.gold : C.green;
  const vb = item.verdict === "INVALID" ? C.redBorder : item.verdict === "AT RISK" ? C.goldBorder : C.greenBorder;

  return (
    <div style={{ background: C.bg2, border: `1px solid ${vb}`, borderLeft: `3px solid ${vc}`, borderRadius: 8, marginBottom: 16, overflow: "hidden" }}>
      <div style={{ padding: "16px 20px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }} onClick={() => setOpen(!open)}>
        <div style={{ flex: 1 }}>
          <Mono color={C.textDim}>{item.id} · {item.finding}</Mono>
          <div style={{ fontSize: 15, fontWeight: 500, color: C.text, marginTop: 4 }}>{item.title}</div>
          <div style={{ fontSize: 12, color: C.textDim, marginTop: 6, lineHeight: 1.4 }}>{item.assumption.substring(0, 100)}...</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0, marginLeft: 16 }}>
          <span style={{ padding: "4px 10px", borderRadius: 4, fontFamily: C.mono, fontSize: 10, letterSpacing: 1, background: verdictBg(item.verdict === "INVALID" ? "DIVERGENT" : item.verdict === "AT RISK" ? "PARTIAL" : "CONFIRMED"), color: vc, border: `1px solid ${vb}` }}>{item.verdict}</span>
          <Mono color={C.textDim} size={9}>RISK: {item.risk}</Mono>
        </div>
      </div>

      {open && (
        <div style={{ padding: "0 20px 20px", borderTop: `1px solid ${C.border2}` }}>
          <Label>Plan Assumption</Label>
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>{item.assumption}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
            <div><Label>Plan Target</Label><div style={{ fontSize: 13, color: C.textMuted }}>{item.planTarget}</div></div>
            <div><Label>Verdict</Label><div style={{ fontSize: 13, color: vc, fontWeight: 500 }}>{item.verdict}</div></div>
          </div>
          <Label>Verus Assessment</Label>
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>{item.assessment}</div>
          <Label>Corrected Sequence</Label>
          <div style={{ fontSize: 13, color: "#8ab8d0", lineHeight: 1.6 }}>{item.correctedSequence}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
            <div style={{ padding: 12, background: C.bg, borderRadius: 4, border: "1px solid #2a1a1a" }}>
              <Mono color={C.textDim} size={9}>YEAR 1 OUTCOME</Mono>
              <div style={{ fontSize: 13, color: "#e87e7e", fontWeight: 500, marginTop: 6 }}>{item.yearOne}</div>
            </div>
            <div style={{ padding: 12, background: C.bg, borderRadius: 4, border: `1px solid ${C.border}` }}>
              <Mono color={C.textDim} size={9}>YEAR 2 OUTLOOK</Mono>
              <div style={{ fontSize: 13, color: "#8ab8d0", fontWeight: 500, marginTop: 6 }}>{item.yearTwo}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ChatTab() {
  const [messages, setMessages] = useState([{ role: "assistant", content: "Intelligence Chat is live. I have full access to all six findings, the evidence ledger, and every system query Verus executed on Project Meridian. Ask me anything about Atlas Climate Systems." }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = useCallback(async (text) => {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");
    const updated = [...messages, { role: "user", content: msg }];
    setMessages(updated);
    setLoading(true);
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "claude-sonnet-4-20250514", max_tokens: 600, system: CHAT_CONTEXT, messages: updated.filter((_, i) => i > 0).map(m => ({ role: m.role, content: m.content })) }),
      });
      const data = await res.json();
      setMessages(m => [...m, { role: "assistant", content: data.content?.[0]?.text || "Error retrieving response." }]);
    } catch { setMessages(m => [...m, { role: "assistant", content: "Connection error." }]); }
    setLoading(false);
  }, [input, loading, messages]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 24, height: "calc(100vh - 200px)", minHeight: 500 }}>
      <div style={{ display: "flex", flexDirection: "column", background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, overflow: "hidden" }}>
        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border2}`, display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.green, boxShadow: `0 0 6px ${C.green}66` }} />
          <Mono color={C.textDim}>INTELLIGENCE CHAT · PROJECT MERIDIAN · ATLAS CLIMATE SYSTEMS</Mono>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
          {messages.map((m, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start", gap: 4 }}>
              <Mono color="#3a4050">{m.role === "user" ? "DEAL TEAM" : "VERUS"}</Mono>
              <div style={{ maxWidth: "85%", padding: "12px 16px", borderRadius: m.role === "user" ? "12px 12px 4px 12px" : "12px 12px 12px 4px", background: m.role === "user" ? "#1e2840" : C.bg3, border: `1px solid ${m.role === "user" ? "#2a3850" : C.border}`, fontSize: 13, color: m.role === "user" ? "#a8b4d0" : C.textMuted, lineHeight: 1.6 }}>{m.content}</div>
            </div>
          ))}
          {loading && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
              <Mono color="#3a4050">VERUS</Mono>
              <div style={{ padding: "12px 16px", borderRadius: "12px 12px 12px 4px", background: C.bg3, border: `1px solid ${C.border}`, fontSize: 13, color: "#3a4050" }}>Querying evidence...</div>
            </div>
          )}
          <div ref={endRef} />
        </div>
        <div style={{ padding: "14px 20px", borderTop: `1px solid ${C.border2}`, display: "flex", gap: 12, alignItems: "flex-end" }}>
          <textarea style={{ flex: 1, background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: "10px 14px", color: C.text, fontSize: 13, fontFamily: C.sans, outline: "none", resize: "none", lineHeight: 1.5 }} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="Ask anything about this engagement..." rows={2} />
          <button style={{ background: loading ? C.bg3 : "#1e2840", border: `1px solid ${loading ? C.border : "#2a3850"}`, borderRadius: 6, padding: "10px 20px", color: loading ? C.textDim : C.blue, fontSize: 12, fontFamily: C.mono, letterSpacing: "0.5px", cursor: loading ? "not-allowed" : "pointer", whiteSpace: "nowrap" }} onClick={() => send()} disabled={loading}>{loading ? "..." : "SEND"}</button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 16 }}>
          <Mono color={C.textDim} size={9}>SUGGESTED QUESTIONS</Mono>
          <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            {SUGGESTED_QUESTIONS.map((q, i) => (
              <div key={i} onClick={() => send(q)} style={{ padding: "10px 12px", background: C.bg, border: `1px solid ${C.border2}`, borderRadius: 4, fontSize: 12, color: C.textDim, cursor: "pointer", lineHeight: 1.4, transition: "all 0.15s" }}
                onMouseEnter={e => { e.currentTarget.style.color = C.textMuted; e.currentTarget.style.borderColor = C.border; }}
                onMouseLeave={e => { e.currentTarget.style.color = C.textDim; e.currentTarget.style.borderColor = C.border2; }}>{q}</div>
            ))}
          </div>
        </div>
        <div style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 16 }}>
          <Mono color={C.textDim} size={9}>CHAT RULES</Mono>
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
            {["All answers grounded in retrieved evidence", "Every answer cites its source finding", "No speculation beyond available data", "No acquisition recommendations", "Data gaps identified explicitly"].map((r, i) => (
              <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <div style={{ width: 4, height: 4, borderRadius: "50%", background: "#2a5060", marginTop: 5, flexShrink: 0 }} />
                <div style={{ fontSize: 11, color: C.textDim, lineHeight: 1.4 }}>{r}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("overview");
  const divergent = FINDINGS.filter(f => f.verdict === "DIVERGENT").length;
  const partial = FINDINGS.filter(f => f.verdict === "PARTIAL").length;

  return (
    <div style={{ background: C.bg, minHeight: "100vh", fontFamily: C.sans, color: C.text, fontSize: 14 }}>
      {/* Header */}
      <div style={{ background: "linear-gradient(180deg, #141720 0%, #0d0f12 100%)", borderBottom: `1px solid ${C.border}`, padding: "0 32px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 0 16px", borderBottom: `1px solid ${C.border2}` }}>
          <div>
            <div style={{ fontFamily: C.serif, fontSize: 26, color: C.text, letterSpacing: "-0.5px" }}>Verus</div>
            <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, letterSpacing: 2, marginTop: 2 }}>CONFIRMATORY DILIGENCE · THE RESONANCE INSTITUTE</div>
          </div>
          <div style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 6, padding: "10px 20px", display: "flex", gap: 24, alignItems: "center" }}>
            {[
              ["Engagement", ENGAGEMENT.name],
              ["Target", ENGAGEMENT.target],
              ["Deal Size", ENGAGEMENT.dealSize],
              ["Stage", ENGAGEMENT.stage],
              ["Status", "● ACTIVE", C.green],
            ].map(([label, value, color], i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <Mono color={C.textDim} size={9}>{label}</Mono>
                <span style={{ fontSize: 13, color: color || "#c8c4bc", fontWeight: 500 }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: "flex" }}>
          {[
            { id: "overview", label: "Overview" },
            { id: "findings", label: `Findings (${FINDINGS.length})` },
            { id: "plan", label: "100-Day Stress Test" },
            { id: "chat", label: "Intelligence Chat" },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{ padding: "14px 24px", fontFamily: C.mono, fontSize: 11, letterSpacing: 1, textTransform: "uppercase", color: tab === t.id ? C.text : C.textDim, background: "none", border: "none", borderBottom: `2px solid ${tab === t.id ? C.gold : "transparent"}`, cursor: "pointer", transition: "all 0.15s" }}>{t.label}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: "32px", maxWidth: 1280, margin: "0 auto" }}>

        {/* Overview */}
        {tab === "overview" && (
          <div>
            {/* Summary cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 32 }}>
              {[
                { num: divergent, label: "Divergent Findings", detail: "Material gaps between narrative and system data", color: C.red },
                { num: partial, label: "Partial Findings", detail: "Confirmed with material qualifications", color: C.gold },
                { num: "$29M", label: "Valuation Consideration", detail: "Warranty + commodity at 6.6x multiple", color: "#e87e3e" },
                { num: "7.3x", label: "Verus-Adjusted Multiple", detail: `On ${ENGAGEMENT.verusEBITDA} recurring EBITDA`, color: C.blue },
              ].map((c, i) => (
                <div key={i} style={{ background: C.bg2, border: `1px solid ${c.color}22`, borderTop: `2px solid ${c.color}`, borderRadius: 8, padding: 20 }}>
                  <div style={{ fontFamily: C.serif, fontSize: 38, color: c.color, lineHeight: 1 }}>{c.num}</div>
                  <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, letterSpacing: "1.5px", textTransform: "uppercase", marginTop: 6 }}>{c.label}</div>
                  <div style={{ fontSize: 12, color: "#6a7080", marginTop: 8 }}>{c.detail}</div>
                </div>
              ))}
            </div>

            {/* Engagement + Systems */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
              <div style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
                <Mono color={C.textDim} size={10}>ENGAGEMENT</Mono>
                {[
                  ["Target", ENGAGEMENT.target], ["Sponsor", ENGAGEMENT.sponsor],
                  ["Deal Size", ENGAGEMENT.dealSize], ["Stated EBITDA", ENGAGEMENT.statedEBITDA],
                  ["Verus-Adjusted EBITDA", ENGAGEMENT.verusEBITDA],
                  ["Products", ENGAGEMENT.products], ["Markets", ENGAGEMENT.markets],
                  ["Plants", ENGAGEMENT.plants], ["Employees", ENGAGEMENT.employees],
                  ["Diligence Window", ENGAGEMENT.window],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: "flex", gap: 12, marginTop: 10, alignItems: "flex-start" }}>
                    <div style={{ fontFamily: C.mono, fontSize: 10, color: "#3a4050", width: 120, flexShrink: 0, paddingTop: 1 }}>{k}</div>
                    <div style={{ fontSize: 12, color: C.textMuted, lineHeight: 1.4 }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20 }}>
                <Mono color={C.textDim} size={10}>CONNECTED SYSTEMS</Mono>
                <div style={{ marginTop: 12 }}>
                  {ENGAGEMENT.connectors.map(c => (
                    <div key={c} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, padding: "10px 12px", background: C.bg, borderRadius: 4, border: `1px solid ${C.border2}` }}>
                      <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.green, boxShadow: `0 0 4px ${C.green}66` }} />
                      <span style={{ fontFamily: C.mono, fontSize: 11, color: "#6a8060" }}>{c}</span>
                      <span style={{ marginLeft: "auto", fontFamily: C.mono, fontSize: 9, color: C.green }}>CONNECTED · READ-ONLY</span>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 16, padding: "12px 16px", background: "#0a1a0a", borderRadius: 4, border: "1px solid #1a3a1a" }}>
                  <Mono color={C.green} size={9}>EVIDENCE CHAIN</Mono>
                  <div style={{ fontFamily: C.mono, fontSize: 10, color: "#2a5a3a", marginTop: 4 }}>{FINDINGS.length} findings cryptographically committed · All chains verified intact</div>
                  <div style={{ fontFamily: C.mono, fontSize: 10, color: "#2a5a3a", marginTop: 2 }}>Report root hash generated · INSERT-only ledger enforced</div>
                </div>
              </div>
            </div>

            {/* EBITDA Bridge */}
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, letterSpacing: 2, textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
              <span>EBITDA BRIDGE</span>
              <div style={{ flex: 1, height: 1, background: C.border2 }} />
            </div>
            <div style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20, marginBottom: 24 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 0 }}>
                {[
                  { label: "Stated Adj. EBITDA", value: "$22.4M", color: C.blue },
                  { label: "Warranty restatement", value: "−$2.2M", color: C.red },
                  { label: "Charlotte one-time reclass", value: "−$0.7M", color: C.red },
                  { label: "Commodity H2 headwind", value: "−$2.2M", color: C.red },
                  { label: "Other adjustments", value: "+$0.7M", color: C.gold },
                  { label: "Verus Recurring EBITDA", value: "$20.2M", color: C.gold },
                ].map((item, i) => (
                  <div key={i} style={{ textAlign: "center", padding: "16px 8px", borderRight: i < 5 ? `1px solid ${C.border2}` : "none" }}>
                    <div style={{ fontFamily: C.serif, fontSize: 24, color: item.color, marginBottom: 8 }}>{item.value}</div>
                    <div style={{ fontFamily: C.mono, fontSize: 9, color: C.textDim, lineHeight: 1.5 }}>{item.label}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 16, padding: "10px 16px", background: C.bg, borderRadius: 4, display: "flex", gap: 32 }}>
                {[
                  ["Stated Multiple", "6.6x", C.blue],
                  ["Verus-Adjusted Multiple", "7.3x", C.gold],
                  ["Combined Valuation Consideration", "$29M at deal multiple", "#e87e3e"],
                ].map(([label, value, color]) => (
                  <div key={label} style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim }}>
                    {label} <span style={{ color }}>{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Findings */}
        {tab === "findings" && (
          <div>
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, letterSpacing: 2, textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
              <span>{divergent} DIVERGENT · {partial} PARTIAL · {FINDINGS.filter(f => f.verdict === "CONFIRMED").length} CONFIRMED</span>
              <div style={{ flex: 1, height: 1, background: C.border2 }} />
              <span style={{ whiteSpace: "nowrap" }}>ALL CHAINS VERIFIED INTACT</span>
            </div>
            {FINDINGS.map(f => <FindingCard key={f.id} f={f} />)}
          </div>
        )}

        {/* Plan */}
        {tab === "plan" && (
          <div>
            <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textDim, letterSpacing: 2, textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
              <span>100-DAY PLAN STRESS TEST · 3 OF 11 INITIATIVES ASSESSED</span>
              <div style={{ flex: 1, height: 1, background: C.border2 }} />
            </div>
            <div style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: "16px 20px", marginBottom: 24 }}>
              <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>
                Apex Industrial Partners' 100-day plan uploaded January 17, 2026. Verus evaluated each initiative against operating evidence from 4 connected systems. 11 total initiatives. 3 flagged for material concern based on findings in this engagement. 8 initiatives clear — no conflict with system evidence found.
              </div>
            </div>
            {PLAN_ITEMS.map(item => <PlanCard key={item.id} item={item} />)}
            <div style={{ background: "#0a1a0a", border: "1px solid #1a3a1a", borderRadius: 8, padding: "16px 20px" }}>
              <Mono color={C.green} size={10}>8 INITIATIVES NOT FLAGGED</Mono>
              <div style={{ fontSize: 12, color: "#4a6040", marginTop: 8, lineHeight: 1.6 }}>
                P-01 (Memphis chiller capacity) · P-02 (Atlanta RTU line optimization) · P-04 (ERP integration) · P-05 (service contract renewal program) · P-06 (Atlanta workforce training) · P-08 (data center vertical sales) · P-09 (distributor network rationalization) · P-10 (management incentive alignment) — no material conflict with system evidence found in this engagement.
              </div>
            </div>
          </div>
        )}

        {/* Chat */}
        {tab === "chat" && <ChatTab />}
      </div>
    </div>
  );
}
