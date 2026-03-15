================================================================================
INTELLI-CREDIT — ROUND 2 REMAINING FEATURES BUILD PROMPT
================================================================================
PROJECT: AI Credit Decisioning Engine for Indian NBFC Corporate Lending
STACK: FastAPI + React 19 + SQLite + scikit-learn + Groq API + Node.js docx
REPO: https://github.com/Arnav10090/Intelli-credit-system-hackathon
DATE: March 15, 2026
================================================================================

CONTEXT — WHAT IS ALREADY BUILT
--------------------------------------------------------------------------------
Intelli-Credit is a fully working credit appraisal system. The following
features are confirmed built and working — do NOT rebuild or modify them:

CORE ENGINE (built, tested, working):
- Five Cs deterministic scorecard (230 pts → 0-100 normalised)
- ML validator (sklearn HGBC, ROC-AUC 0.9627)
- Research agent (news/litigation/MCA async crawler)
- CAM generator (10-section Word .docx via Node.js docx library)
- Working capital analyzer (DSCR, D/E, CCC, debtor/creditor days)
- GST reconciler (GSTR-2A vs 3B, circular trading detection)
- Related party detector (pledge%, RP concentration, mgmt scoring)
- Feature engineer (16 normalized features across Five Cs pillars)
- Loan calculator (DSCR-based + collateral-based sizing, risk pricing)

STAGE 3 FEATURES (built this session by teammate):
- Document classifier (37 pattern-based rules, 5 document types)
- Schema mapper (dynamic field mappings, transformations, validation)
- Human-in-the-loop approval workflow (approve/reject UI + API)
- PDF extraction (PyMuPDF + OCR fallback — claimed 100% in README)
- Research triangulation (claimed built in README)
- Document Intelligence page at /documents route
- 6 new API endpoints in document_routes.py

UI/UX FIXES (done this session):
- Clock ticking fix (useState + useEffect interval in Topbar.jsx)
- Logo light mode fix (fixed gradient colors)
- Demo cases auto-reset on server startup (demo_reset.py)
- Audit logger score display fixed (200/200 → 200/230)

DEMO CASES (working, must stay working):
- Surya Pharmaceuticals Ltd: APPROVE, 87/100, Grade A+, ₹30Cr @ 9.5%
- Acme Textiles Ltd: REJECT, 50/100, Grade B, NCLT knockout

--------------------------------------------------------------------------------
VERIFY BEFORE STARTING — RUN THESE CHECKS FIRST
--------------------------------------------------------------------------------

Before building anything, verify the claimed-complete features actually work:

CHECK 1 — pdfplumber installation:
  cd backend
  python -c "import pdfplumber; print('pdfplumber OK')"
  python -c "import pytesseract; print('pytesseract OK')"

CHECK 2 — PDF extractor module:
  python -c "from ingestor.pdf_extractor import PDFExtractor; print('extractor OK')"

CHECK 3 — Triangulator module:
  python -c "from research.triangulator import DataTriangulator; print('triangulator OK')"

CHECK 4 — Document routes registered:
  python -c "from api.document_routes import router; print('routes OK')"

CHECK 5 — Both servers start cleanly:
  uvicorn main:app --reload --port 8000
  Verify in logs: "Demo cases reset complete" appears on startup
  Verify no import errors

If ANY check fails, fix that module first before proceeding to
the features below. Do not proceed with broken imports.

IF pdfplumber is not actually installed or pdf_extractor.py does not exist,
build Feature 2 (PDF Extraction) from the full spec in APPENDIX A at the
bottom of this prompt before building Features 1, 3, and 4.

IF triangulator.py does not exist or is a stub/placeholder,
build Feature 5 (Triangulation) from the full spec in APPENDIX B at the
bottom of this prompt after building Features 1, 3, and 4.

================================================================================
FEATURE 1 — SWOT ANALYSIS
================================================================================
PRIORITY: HIGHEST — explicitly required by hackathon evaluation criteria
The email states: "SWOT & GenAI: Generate a comprehensive SWOT analysis
and a downloadable final investment report"

README currently shows: "SWOT analysis ⚠️ Partial (insights exist, not SWOT format)"
This must become: "SWOT analysis ✅ Built (AI-generated 2×2 in CAM)"

--------------------------------------------------------------------------------
1A. BACKEND: backend/cam/llm_narrator.py
--------------------------------------------------------------------------------

STEP 1 — Add swot field to CAMNarrative dataclass:
The existing CAMNarrative dataclass has fields:
  executive_summary, company_background, financial_analysis,
  risk_factors, recommendation, model_used

Add one new field:
  swot: str = ""   # JSON string — parsed later by doc_builder

STEP 2 — Add generate_swot() method to the LLM narrator class:

def generate_swot(self, context: dict) -> str:
    """
    Makes a SEPARATE LLM API call to generate SWOT as JSON string.
    Kept separate from the main narrative call intentionally —
    different temperature, different output format.
    Returns JSON string. Falls back to deterministic template if LLM fails.
    """

The SWOT prompt must:
- Instruct the LLM to return ONLY valid JSON with zero preamble
- Use this exact schema:
  {
    "strengths": ["point 1", "point 2", "point 3"],
    "weaknesses": ["point 1", "point 2", "point 3"],
    "opportunities": ["point 1", "point 2", "point 3"],
    "threats": ["point 1", "point 2", "point 3"]
  }
- Each list must have exactly 3-4 items
- Each item: 1 concise sentence, maximum 20 words
- Must be SPECIFIC to this company — no generic statements
- Must reference actual numbers from context (DSCR, D/E, margins, etc.)

Content guidance for prompt:
  Strengths: metrics above threshold (DSCR > 2.0, pledge = 0%, 
             USFDA certified, revenue CAGR > 10%)
  Weaknesses: metrics below threshold or areas of concern
              (high D/E, low margins, customer concentration)
  Opportunities: sector tailwinds, PLI schemes if applicable,
                 expansion potential, export market growth
  Threats: knockout flags, litigation, market risks,
           input cost volatility, regulatory changes

STEP 3 — Call generate_swot() inside generate_narrative():
After generating the main 5-section narrative, call generate_swot()
and assign the result to the narrative.swot field before returning.

STEP 4 — Deterministic SWOT fallback (if LLM unavailable):
If LLM API call fails OR api_key is empty, generate SWOT from data:

def _deterministic_swot(self, context: dict) -> str:
    sc = context.get("scorecard", {})
    pillars = sc.get("pillar_scores", {})
    contribs = sc.get("contributions", {})
    knockouts = sc.get("knockout_flags", [])
    research = context.get("research_summary", {})
    sector = context.get("sector", "")
    
    strengths = []
    weaknesses = []
    opportunities = []
    threats = []
    
    # Strengths: features scoring >= 70%
    for feature, data in contribs.items():
        if data.get("pct", 0) >= 70:
            strengths.append(
                f"{feature.replace('_', ' ').title()}: "
                f"{data['points_awarded']}/{data['max_points']} pts — above benchmark"
            )
    
    # Weaknesses: features scoring < 40%
    for feature, data in contribs.items():
        if data.get("pct", 0) < 40:
            weaknesses.append(
                f"{feature.replace('_', ' ').title()}: "
                f"below benchmark at {data['pct']:.0f}% of maximum"
            )
    
    # Opportunities: sector outlook + revenue trend
    opportunities = [
        f"{sector} sector showing positive macro trends",
        "Revenue growth trajectory supports expansion",
        "Strong collateral position enables additional facility if needed",
    ]
    
    # Threats: knockouts + T1/T2 research findings
    for ko in knockouts:
        threats.append(f"Knockout flag: {ko}")
    if research.get("label") in ["HIGH", "CRITICAL"]:
        threats.append("Research findings indicate elevated external risk")
    if not threats:
        threats = [
            "Macro interest rate environment may increase borrowing costs",
            "Sector competition could pressure margins over medium term",
        ]
    
    # Ensure minimum 3 items each
    while len(strengths) < 3:
        strengths.append("Consistent financial reporting and disclosure standards")
    while len(weaknesses) < 3:
        weaknesses.append("Further data needed for comprehensive assessment")
    
    return json.dumps({
        "strengths": strengths[:4],
        "weaknesses": weaknesses[:4],
        "opportunities": opportunities[:4],
        "threats": threats[:4],
    })

--------------------------------------------------------------------------------
1B. BACKEND: backend/cam/doc_builder.py
--------------------------------------------------------------------------------

PART 1 — Add _parse_swot() helper in Python section:

def _parse_swot(swot_json_str: str) -> dict:
    """Parse SWOT JSON string to dict. Returns safe fallback if invalid."""
    try:
        if not swot_json_str:
            raise ValueError("empty")
        parsed = json.loads(swot_json_str)
        # Validate structure
        for key in ["strengths", "weaknesses", "opportunities", "threats"]:
            if key not in parsed or not isinstance(parsed[key], list):
                raise ValueError(f"missing key: {key}")
        return parsed
    except Exception:
        return {
            "strengths": ["Financial data analysis complete"],
            "weaknesses": ["Full SWOT analysis requires LLM configuration"],
            "opportunities": ["Refer to Research Findings section for details"],
            "threats": ["Refer to Risk Factors section for details"],
        }

PART 2 — Add "swot" to the payload in _build_payload():
In the return dict of _build_payload(), add:
  "swot": _parse_swot(narrative.swot) if narrative.swot else _parse_swot(""),

PART 3 — Add swotSection() function inside _NODE_SCRIPT:

Find the _NODE_SCRIPT JavaScript string constant.
Add this function AFTER the riskSection() function
and BEFORE the recommendationSection() function:

function swotSection() {
  const sw = data.swot;
  if (!sw) return [];

  const SWOT_GREEN  = '375623';  // Strengths header
  const SWOT_AMBER  = 'C65911';  // Weaknesses header
  const SWOT_BLUE   = '2E75B6';  // Opportunities header
  const SWOT_RED    = 'C00000';  // Threats header
  const CELL_BG     = 'F9F9F9';

  function swotCell(items, headerText, headerColor) {
    const children = [
      new Paragraph({
        children: [new TextRun({
          text: headerText,
          font: 'Arial', size: 22, bold: true, color: WHITE,
        })],
        shading: { fill: headerColor, type: ShadingType.CLEAR },
        spacing: { before: 80, after: 80 },
      })
    ];
    (items || []).forEach(function(item) {
      children.push(new Paragraph({
        spacing: { before: 60, after: 60 },
        indent: { left: 120 },
        children: [new TextRun({
          text: '\u2022 ' + sanitizeDashes(String(item || '')),
          font: 'Arial', size: 18, color: BLACK,
        })]
      }));
    });
    return new TableCell({
      borders: BORDERS,
      width: { size: 4680, type: WidthType.DXA },
      shading: { fill: CELL_BG, type: ShadingType.CLEAR },
      margins: { top: 0, bottom: 120, left: 0, right: 0 },
      children: children,
    });
  }

  return [
    h1('10. SWOT Analysis'),
    para(
      'AI-generated strategic assessment based on financial data, ' +
      'research findings, and Five Cs scorecard outputs.',
      { italic: true, size: 16, color: '666666' }
    ),
    spacer(),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [4680, 4680],
      rows: [
        new TableRow({ children: [
          swotCell(sw.strengths,     'S \u2014 STRENGTHS',     SWOT_GREEN),
          swotCell(sw.weaknesses,    'W \u2014 WEAKNESSES',    SWOT_AMBER),
        ]}),
        new TableRow({ children: [
          swotCell(sw.opportunities, 'O \u2014 OPPORTUNITIES', SWOT_BLUE),
          swotCell(sw.threats,       'T \u2014 THREATS',       SWOT_RED),
        ]}),
      ]
    }),
  ];
}

PART 4 — Update section numbering in _NODE_SCRIPT:

In the scorecardSection() function, change heading from:
  h1('8. Five Cs Scorecard')
to:
  h1('7. Five Cs Scorecard')
  (keeping section 7 for scorecard — check current numbering and
  ensure sections flow as: 7=Scorecard, 8=Risk, 9=Research,
  then 10=SWOT, 11=Recommendation)

Actually — preserve the existing section numbers for sections 1-9.
Only insert SWOT as section 10 and move Recommendation to section 11:

Find in recommendationSection():
  h1('10. Recommendation & Audit Trail')
Change to:
  h1('11. Recommendation & Audit Trail')

PART 5 — Add swotSection() to allChildren array:

Find the allChildren array construction at the bottom of _NODE_SCRIPT:
  const allChildren = [].concat(
    coverPage(),
    execSummary(),
    companyProfile(),
    proposedFacility(),
    financialSummary(),
    gstSection(),
    researchSection(),
    insightsSection(),
    scorecardSection(),
    riskSection(),
    recommendationSection()
  );

Change to:
  const allChildren = [].concat(
    coverPage(),
    execSummary(),
    companyProfile(),
    proposedFacility(),
    financialSummary(),
    gstSection(),
    researchSection(),
    insightsSection(),
    scorecardSection(),
    riskSection(),
    swotSection(),          // ← ADD HERE
    recommendationSection()
  );

--------------------------------------------------------------------------------
1C. FRONTEND: CAM Tab in CaseDetail
--------------------------------------------------------------------------------

File: frontend/src/pages/CaseDetail.jsx
(or wherever the CAM tab content is rendered)

After CAM is generated, add a SWOT Preview panel ABOVE the download button.

The panel is a 2x2 grid of cards:

Layout:
┌─────────────────────┬─────────────────────┐
│ 💪 Strengths        │ ⚠️ Weaknesses       │
│ (green left border) │ (amber left border) │
│ • point 1           │ • point 1           │
│ • point 2           │ • point 2           │
│ • point 3           │ • point 3           │
├─────────────────────┼─────────────────────┤
│ 🚀 Opportunities    │ ⛔ Threats          │
│ (blue left border)  │ (red left border)   │
│ • point 1           │ • point 1           │
│ • point 2           │ • point 2           │
│ • point 3           │ • point 3           │
└─────────────────────┴─────────────────────┘

Styling:
- Each card: dark background matching app theme
- Left border: 3px solid colored border
  Strengths: #375623 (green)
  Weaknesses: #C65911 (amber)
  Opportunities: #2E75B6 (blue)
  Threats: #C00000 (red)
- Card header: bold, 14px
- Bullet points: 13px, muted color var(--text-muted)
- Grid: CSS grid 2x2, gap 12px

Data source:
The CAM generation API response (POST /cam) must include swot in its JSON.
Update the cam_routes.py POST endpoint to include:
  "swot": cam_data.get("swot", {})
in the response body.

Parse swot from the response and store in component state:
  const [swotData, setSwotData] = useState(null)
  // After CAM generation succeeds:
  setSwotData(response.data.swot)

Only show the SWOT panel if swotData is not null.

Also update the section count in the CAM tab:
- Change "10 sections" to "11 sections" wherever it appears
- Add "11. SWOT Analysis — AI-generated 2×2 strategic matrix"
  to the section list shown in the CAM tab

--------------------------------------------------------------------------------
1D. README UPDATE — Do This Last, After SWOT Works
--------------------------------------------------------------------------------

File: README.md — make these 4 changes:

Change 1 — Badge:
  FROM: ![CAM](https://img.shields.io/badge/CAM_Sections-10-purple?style=flat-square)
  TO:   ![CAM](https://img.shields.io/badge/CAM_Sections-11-purple?style=flat-square)

Change 2 — CAM Document Structure section:
  Add before Recommendation:
    ║  Section 10  ▸  SWOT Analysis      AI-generated 2×2 matrix    ║
  Change Recommendation from Section 10 to Section 11:
    ║  Section 11  ▸  Recommendation     Decision + Audit Trail      ║

Change 3 — Evaluation Coverage table:
  FROM: | SWOT analysis | ⚠️ Partial (insights exist, not SWOT format) | Medium |
  TO:   | SWOT analysis | ✅ Built (AI-generated 2×2 matrix in CAM) | Done |

Change 4 — Overall Coverage line:
  FROM: ### Overall Coverage: 98% ✅
  TO:   ### Overall Coverage: 100% ✅

================================================================================
FEATURE 3 — TURNOVER & TENURE FIELDS IN ENTITY ONBOARDING
================================================================================
PRIORITY: MEDIUM
EFFORT: ~30 minutes
REASON: Hackathon Stage 1 explicitly requires:
"basic entity details (CIN, PAN, Sector, Turnover, etc.) and
specific Loan Details (Type, Amount, Tenure, Interest)"

--------------------------------------------------------------------------------
3A. FRONTEND: New Case Form
--------------------------------------------------------------------------------

Find the new case creation form. It is in one of:
  frontend/src/pages/Dashboard.jsx
  frontend/src/components/NewCaseModal.jsx
  frontend/src/pages/NewCase.jsx

Search for the existing fields: Company Name, CIN/GSTIN, Loan Amount,
Loan Purpose. Add these two new fields:

FIELD 1 — Annual Turnover:
  Label:       "Annual Turnover (₹ Cr)"
  Type:        number input
  Placeholder: "e.g. 150"
  Position:    After "Sector" field, before "Loan Amount"
  Validation:  Must be > 0
  Helper text: "Latest audited revenue from operations"
  State key:   annualTurnover

FIELD 2 — Loan Tenure:
  Label:    "Loan Tenure (Years)"
  Type:     dropdown (select element)
  Options:  1, 2, 3, 5, 7, 10
  Default:  7
  Position: After "Loan Amount" field
  State key: loanTenure

Include both fields in the form submission payload:
  annual_turnover_cr: parseFloat(annualTurnover) || null,
  loan_tenure_yr: parseInt(loanTenure) || 7,

--------------------------------------------------------------------------------
3B. BACKEND: Database Model
--------------------------------------------------------------------------------

File: backend/db/models.py

Add to Case model:
  annual_turnover_cr = Column(Float, nullable=True)
  loan_tenure_yr = Column(Integer, default=7)

After adding fields, handle the SQLite migration:
Since the app uses SQLite with create_all(), the new columns will be
added automatically if the database is fresh. If the database already
exists, add this to demo_reset.py or main.py startup:

try:
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE cases ADD COLUMN annual_turnover_cr REAL"
        ))
        conn.execute(text(
            "ALTER TABLE cases ADD COLUMN loan_tenure_yr INTEGER DEFAULT 7"
        ))
        conn.commit()
except Exception:
    pass  # Columns already exist — ignore

File: backend/api/case_routes.py OR ingest_routes.py

In the POST /cases endpoint (create new case), accept:
  annual_turnover_cr: Optional[float] = None
  loan_tenure_yr: Optional[int] = 7

Store both on the Case model instance before db.commit().

In the GET /cases/{id} response, include both fields.

File: backend/scoring/feature_engineer.py

If annual_turnover_cr is provided for a non-demo case and
financial_data does not have 3 years of P&L yet, use it as
a proxy for the Capacity pillar revenue feature:

  if not full_financials_available and annual_turnover_cr:
      revenue_proxy = annual_turnover_cr * 100  # convert Cr to Lakhs
      # Use as single-year revenue estimate in capacity scoring
      features["revenue_cagr"] = 0.5  # neutral score — no trend data
      features["ebitda_margin"] = 0.5  # neutral — no margin data

This allows partial scoring for new cases before PDF extraction.

================================================================================
FEATURE 4 — SECTOR MACRO OUTLOOK
================================================================================
PRIORITY: MEDIUM
EFFORT: ~1 hour
REASON: Hackathon requires "360-degree view of entity/sector/subsector/
macro trends" — currently research covers company-specific data only.
This adds sector-level intelligence with zero external API calls.

--------------------------------------------------------------------------------
4A. NEW FILE: backend/research/sector_outlook.py
--------------------------------------------------------------------------------

Create this file from scratch. Pure static data — no API calls needed.

SECTOR_OUTLOOK = {
    "pharmaceuticals": {
        "outlook": "POSITIVE",
        "outlook_score": 0.85,
        "drivers": [
            "PLI scheme providing ₹15,000 Cr incentive over 6 years for API/formulations",
            "USFDA approvals driving US generics exports — market USD 100Bn+",
            "Domestic formulations growing 8-10% annually (IQVIA data FY2024)",
            "API import substitution reducing China dependency post-COVID"
        ],
        "risks": [
            "US FDA import alerts and warning letters on Indian manufacturing facilities",
            "Drug price control orders (DPCO) capping margins on essential medicines",
            "Currency risk — export players have 30-40% USD revenue exposure",
            "R&D intensity required for USFDA bioequivalence compliance raising opex"
        ],
        "rbi_sector_cap": None,
        "npa_trend": "STABLE",
        "avg_sector_dscr": 2.1,
        "avg_sector_de": 0.8,
        "regulatory_risk": "MEDIUM",
        "macro_trend": (
            "India pharma market projected to reach USD 65Bn by 2024 (IBEF). "
            "PLI scheme and USFDA approvals driving export-led growth."
        ),
        "last_updated": "Mar 2026"
    },

    "textiles": {
        "outlook": "NEUTRAL",
        "outlook_score": 0.55,
        "drivers": [
            "PLI scheme for man-made fibre (MMF) and technical textiles (₹10,683 Cr)",
            "China+1 sourcing strategy driving global buyer shift to Indian suppliers",
            "ROSL and RoSCTL export rebate schemes improving competitiveness"
        ],
        "risks": [
            "Cotton price volatility — raw material is 40-60% of production cost",
            "Export slowdown to EU and US due to consumer demand recession",
            "Bangladesh and Vietnam competition intensifying in garments segment",
            "Power and water intensive operations attracting increasing ESG scrutiny"
        ],
        "rbi_sector_cap": None,
        "npa_trend": "RISING",
        "avg_sector_dscr": 1.4,
        "avg_sector_de": 1.8,
        "regulatory_risk": "LOW",
        "macro_trend": (
            "India textile exports USD 44Bn FY24, national target USD 100Bn by 2030. "
            "MMF segment growing faster than cotton; technical textiles high potential."
        ),
        "last_updated": "Mar 2026"
    },

    "real_estate": {
        "outlook": "CAUTIOUS",
        "outlook_score": 0.50,
        "drivers": [
            "Housing demand strong in tier-1 cities post-pandemic",
            "RERA compliance improving buyer confidence and project completion",
            "Affordable housing segment supported by PMAY scheme"
        ],
        "risks": [
            "Interest rate sensitivity — EMI increases dampening demand",
            "Inventory overhang in commercial segment (WFH trend)",
            "Developer leverage levels elevated — refinancing risk",
            "RBI tightening LTV norms for developer lending"
        ],
        "rbi_sector_cap": None,
        "npa_trend": "ELEVATED",
        "avg_sector_dscr": 1.3,
        "avg_sector_de": 2.5,
        "regulatory_risk": "HIGH",
        "macro_trend": (
            "Residential demand resilient in metro cities. "
            "Commercial real estate under pressure from remote work trends."
        ),
        "last_updated": "Mar 2026"
    },

    "infrastructure": {
        "outlook": "POSITIVE",
        "outlook_score": 0.80,
        "drivers": [
            "Government capex ₹11.1 Lakh Cr in Union Budget FY2024-25",
            "National Infrastructure Pipeline (NIP) — 9,000+ projects worth ₹111 Lakh Cr",
            "PM Gati Shakti reducing logistics costs and improving connectivity",
            "Roads, railways, ports seeing record order books"
        ],
        "risks": [
            "Land acquisition delays causing project cost and time overruns",
            "Working capital intensive — long payment cycles from government",
            "Commodity price inflation (steel, cement) squeezing project margins",
            "Execution risk for large-scale projects requiring multi-year commitment"
        ],
        "rbi_sector_cap": None,
        "npa_trend": "STABLE",
        "avg_sector_dscr": 1.6,
        "avg_sector_de": 2.0,
        "regulatory_risk": "MEDIUM",
        "macro_trend": (
            "India infrastructure spend among highest globally as % of GDP. "
            "Strong order pipeline visibility for FY2025-26 and beyond."
        ),
        "last_updated": "Mar 2026"
    },

    "nbfc": {
        "outlook": "STABLE",
        "outlook_score": 0.65,
        "drivers": [
            "Strong credit demand from MSME and retail segments",
            "Digital lending enabling reach in under-banked geographies",
            "Co-lending model with banks reducing cost of funds"
        ],
        "risks": [
            "RBI tightening norms — higher capital adequacy and provisioning requirements",
            "Liquidity risk — ALM mismatch in wholesale-funded NBFCs",
            "Competition from fintechs and banks in retail lending segment",
            "Asset quality deterioration risk in unsecured segments"
        ],
        "rbi_sector_cap": "As per RBI NBFC Master Directions",
        "npa_trend": "WATCH",
        "avg_sector_dscr": 1.5,
        "avg_sector_de": 4.0,
        "regulatory_risk": "HIGH",
        "macro_trend": (
            "NBFC credit growth 14-16% YoY. RBI increasing regulatory oversight. "
            "Scale-based regulation framework separating large and small NBFCs."
        ),
        "last_updated": "Mar 2026"
    },

    "steel_metals": {
        "outlook": "NEUTRAL",
        "outlook_score": 0.58,
        "drivers": [
            "Infrastructure spending driving domestic steel demand",
            "PLI scheme for specialty steel (₹6,322 Cr over 5 years)",
            "Import duty protection supporting domestic producers"
        ],
        "risks": [
            "China steel dumping keeping global prices suppressed",
            "Coking coal import dependency — price and currency exposure",
            "Cyclical commodity — revenue and margins highly volatile",
            "Carbon emission regulations increasing compliance capex"
        ],
        "rbi_sector_cap": None,
        "npa_trend": "STABLE",
        "avg_sector_dscr": 1.5,
        "avg_sector_de": 1.5,
        "regulatory_risk": "MEDIUM",
        "macro_trend": (
            "India to become world's 2nd largest steel producer by 2030. "
            "Domestic demand robust; export realisation under pressure from China supply."
        ),
        "last_updated": "Mar 2026"
    },

    "fmcg": {
        "outlook": "POSITIVE",
        "outlook_score": 0.75,
        "drivers": [
            "Rural demand recovery driven by normal monsoon and MSP increases",
            "Premiumisation trend in urban markets supporting margin expansion",
            "Modern trade and quick commerce channels growing 25-30% annually",
            "Raw material (palm oil, crude derivatives) prices moderating"
        ],
        "risks": [
            "Input cost inflation risk if commodity prices spike",
            "D2C brands disrupting established players in urban markets",
            "Rural demand still volatile — dependent on agricultural income",
            "GST rate rationalisation uncertainty for some product categories"
        ],
        "rbi_sector_cap": None,
        "npa_trend": "LOW",
        "avg_sector_dscr": 3.5,
        "avg_sector_de": 0.5,
        "regulatory_risk": "LOW",
        "macro_trend": (
            "India FMCG market USD 220Bn projected by 2025. "
            "Volume growth recovering after 2 years of value-led growth."
        ),
        "last_updated": "Mar 2026"
    },

    "it_technology": {
        "outlook": "STABLE",
        "outlook_score": 0.65,
        "drivers": [
            "Global digital transformation spend sustaining IT services demand",
            "AI/ML and cloud migration creating new revenue streams",
            "India GCC (Global Capability Centre) expansion accelerating",
            "Rupee depreciation benefiting export-oriented IT revenues"
        ],
        "risks": [
            "US and EU discretionary IT spend slowdown affecting deal sizes",
            "Visa restrictions and protectionism impacting onsite delivery",
            "Talent attrition and wage inflation compressing margins",
            "GenAI disruption risk to traditional IT services business model"
        ],
        "rbi_sector_cap": None,
        "npa_trend": "LOW",
        "avg_sector_dscr": 4.0,
        "avg_sector_de": 0.3,
        "regulatory_risk": "LOW",
        "macro_trend": (
            "India IT exports USD 254Bn FY2024. "
            "Slowdown in BFSI vertical; recovery expected H2 FY2025."
        ),
        "last_updated": "Mar 2026"
    },

    "default": {
        "outlook": "NEUTRAL",
        "outlook_score": 0.60,
        "drivers": [
            "India GDP growth 6.5-7% projected FY2025 (IMF estimate)",
            "Domestic consumption resilient — urban demand above pre-COVID trend",
            "Government infrastructure spending providing demand floor"
        ],
        "risks": [
            "Global macro uncertainty — US/EU recession risk affecting exports",
            "Elevated interest rate environment increasing debt service cost",
            "Geopolitical risks impacting supply chains and commodity prices"
        ],
        "rbi_sector_cap": None,
        "npa_trend": "STABLE",
        "avg_sector_dscr": 1.5,
        "avg_sector_de": 1.5,
        "regulatory_risk": "MEDIUM",
        "macro_trend": (
            "India remains world's fastest-growing major economy. "
            "Domestic demand-led growth providing resilience to global headwinds."
        ),
        "last_updated": "Mar 2026"
    }
}

def get_sector_outlook(sector: str) -> dict:
    """
    Returns sector outlook dict.
    Normalises sector string before lookup.
    Falls back to 'default' if no match found.
    """
    if not sector:
        return SECTOR_OUTLOOK["default"]
    sector_norm = sector.lower().strip()
    # Direct match
    if sector_norm in SECTOR_OUTLOOK:
        return SECTOR_OUTLOOK[sector_norm]
    # Partial match — sector string contains key or key contains sector string
    for key in SECTOR_OUTLOOK:
        if key == "default":
            continue
        if key in sector_norm or sector_norm in key:
            return SECTOR_OUTLOOK[key]
    return SECTOR_OUTLOOK["default"]

def get_sector_score(sector: str) -> float:
    """Returns outlook_score float for use in feature engineering."""
    return get_sector_outlook(sector)["outlook_score"]

def compare_to_sector(
    company_dscr: float,
    company_de: float,
    sector: str
) -> dict:
    """
    Returns comparison of company metrics vs sector averages.
    Used for Research tab UI display.
    """
    outlook = get_sector_outlook(sector)
    return {
        "dscr_vs_sector": {
            "company": round(company_dscr, 2),
            "sector_avg": outlook["avg_sector_dscr"],
            "above_benchmark": company_dscr > outlook["avg_sector_dscr"],
        },
        "de_vs_sector": {
            "company": round(company_de, 2),
            "sector_avg": outlook["avg_sector_de"],
            "below_benchmark": company_de < outlook["avg_sector_de"],
        },
        "outlook": outlook["outlook"],
        "outlook_score": outlook["outlook_score"],
        "npa_trend": outlook["npa_trend"],
        "regulatory_risk": outlook["regulatory_risk"],
    }

--------------------------------------------------------------------------------
4B. UPDATE: backend/scoring/feature_engineer.py
--------------------------------------------------------------------------------

Add import at top:
  from research.sector_outlook import get_sector_score

In the Conditions pillar feature computation, find where
sector_outlook feature is currently set (likely hardcoded or minimal).
Replace with:

  company_sector = financial_data.get("company", {}).get("sector", "")
  features["sector_outlook"] = get_sector_score(company_sector)

--------------------------------------------------------------------------------
4C. UPDATE: backend/research/web_crawler.py
--------------------------------------------------------------------------------

Add import at top of file:
  from research.sector_outlook import get_sector_outlook, compare_to_sector

At the END of the crawl_company() async function, after all findings
are collected and BEFORE returning, append sector macro data:

  # Append sector macro intelligence
  company_sector = company_data.get("sector", "")
  sector_data = get_sector_outlook(company_sector)
  
  # Get company DSCR for comparison (if available from context)
  company_dscr = context.get("avg_dscr", 0)
  company_de = context.get("avg_de", 0)
  
  sector_item = {
      "title": f"Sector Macro: {company_sector} — {sector_data['outlook']}",
      "source_name": "Intelli-Credit Macro Intelligence",
      "risk_tier": None,
      "risk_score_delta": int((sector_data["outlook_score"] - 0.5) * 20),
      "type": "sector_macro",
      "drivers": sector_data["drivers"],
      "risks": sector_data["risks"],
      "macro_trend": sector_data["macro_trend"],
      "avg_sector_dscr": sector_data["avg_sector_dscr"],
      "avg_sector_de": sector_data["avg_sector_de"],
      "npa_trend": sector_data["npa_trend"],
      "regulatory_risk": sector_data["regulatory_risk"],
      "last_updated": sector_data["last_updated"],
  }
  
  findings.append(sector_item)  # adjust variable name to match actual code

--------------------------------------------------------------------------------
4D. FRONTEND: Research Tab — Sector Macro Panel
--------------------------------------------------------------------------------

File: frontend/src/pages/CaseDetail.jsx
(Research tab section)

Add a "Sector Intelligence" panel at the TOP of the Research tab,
ABOVE the research findings table. Only show if research data is loaded.

The panel has two parts:

PART 1 — Sector Outlook Header Card:
┌──────────────────────────────────────────────────────────────┐
│ 🏭 Sector: Pharmaceuticals                                   │
│ Outlook: [POSITIVE] (green badge)    NPA Trend: STABLE       │
│ Regulatory Risk: MEDIUM                                      │
│                                                              │
│ "India pharma market projected to reach USD 65Bn by 2024..." │
└──────────────────────────────────────────────────────────────┘

PART 2 — Benchmark Comparison Row:
┌────────────────────┬────────────────────┐
│ DSCR Benchmark     │ D/E Benchmark      │
│ Your: 3.09x        │ Your: 0.42x        │
│ Sector avg: 2.1x   │ Sector avg: 0.8x   │
│ ↑ Above benchmark  │ ✅ Well below avg  │
└────────────────────┴────────────────────┘

PART 3 — Drivers & Risks (collapsible, collapsed by default):
▶ Sector Drivers (click to expand)
▶ Sector Risks (click to expand)

Data source:
Find the sector_macro item in the research findings array
(type === "sector_macro") and render it separately in this panel.
Remove it from the main findings table — it should only show in this panel.

Styling:
- Panel background: slightly lighter than page background
- Outlook badge: POSITIVE=green, NEUTRAL=amber, CAUTIOUS/NEGATIVE=red
- Benchmark comparison: above = green arrow ↑, below = red arrow ↓
  For DSCR: above sector avg is good (green)
  For D/E: below sector avg is good (green)

================================================================================
CRITICAL CONSTRAINTS — DO NOT BREAK THESE
================================================================================

1. DEMO CASES MUST STILL WORK PERFECTLY
   - Surya Pharmaceuticals: 87/100, Grade A+, APPROVE, ₹30Cr @ 9.5%
   - Acme Textiles: 50/100, Grade B, REJECT, NCLT knockout
   - Demo reset on server start must still run cleanly
   - Static demo data in data/demo_company/ must never be deleted
   - Demo cases must NOT go through PDF extraction pipeline
   - "Load Demo Scenario" for analyst notes must still work

2. SCORING FORMULA IS SACRED — NEVER CHANGE:
   - ACTUAL_MAX = 230
   - normalised = round((total_raw / 230) * 100)
   - APPROVE >= 55, PARTIAL 35-54, REJECT < 35
   - Knockout triggers unchanged
   - SWOT and Sector Macro add information only — they never
     modify the Five Cs score or decision

3. LLM CALLS:
   - Model: llama-3.3-70b-versatile
   - Endpoint: https://api.groq.com/openai/v1
   - SWOT LLM call is SEPARATE from the main narrative call
   - Every LLM feature must have offline template fallback
   - Do NOT modify the existing 5-section narrative prompt

4. CAM DOCUMENT:
   - Existing 10 sections stay intact, same order
   - SWOT is inserted as section 10
   - Recommendation becomes section 11
   - Node.js docx builder must not break for cases without swot data
   - Test full CAM generation for BOTH Surya and Acme after changes

5. EXISTING API ROUTES:
   - Do not change paths or response shapes of existing endpoints
   - Only ADD new fields to existing responses (backward compatible)
   - All 6 document_routes endpoints must still work

6. NODE.JS DOCX BUILDER:
   - The ]; vs } bug fix is already applied — do not reintroduce it
   - Test that the JS script has no syntax errors after adding swotSection()
   - Run: node -e "require('./temp_builder.js')" to verify no syntax errors

================================================================================
IMPLEMENTATION ORDER
================================================================================

Execute in this exact sequence to avoid dependency issues:

STEP 1 — Verify checks (see VERIFY section at top)
  If any check fails, fix it before proceeding.

STEP 2 — Feature 3: Turnover + Tenure fields
  Reason: Isolated change, no dependencies, quick win
  Time: ~30 minutes
  Test: Submit new case form, verify fields stored in DB

STEP 3 — Feature 4: Sector Macro Outlook
  Reason: Pure backend, no external APIs, no dependencies
  Time: ~1 hour
  Test: get_sector_outlook("pharmaceuticals") returns dict with all keys
  Test: Research tab shows Sector Intelligence panel for Surya

STEP 4 — Feature 1: SWOT Analysis
  Reason: Depends on llm_narrator.py and doc_builder.py
  Time: ~2-3 hours
  Test: generate_swot() returns valid JSON with 4 keys, 3+ items each
  Test: Surya SWOT — Strengths contains "DSCR" or "3.09" reference
  Test: Acme SWOT — Threats contains "NCLT" or "litigation" reference
  Test: CAM .docx has 11 sections including 2x2 SWOT table
  Test: README updated with correct counts

STEP 5 (if needed) — Appendix A: PDF Extraction (if not working)
STEP 6 (if needed) — Appendix B: Triangulation (if not working)

================================================================================
FINAL TESTING CHECKLIST
================================================================================

Run through this entire checklist after all features are built:

SERVER START:
□ uvicorn main:app --reload starts without errors
□ "Demo cases reset complete" appears in startup logs
□ No import errors for any module

DEMO CASES:
□ Dashboard loads showing Surya (87/100) and Acme (50/100)
□ Surya full pipeline: Load Data → Analyze → Score → Research → CAM
□ Acme full pipeline: Load Data → Analyze → Score → Research → REJECT
□ Both demo cases show correct scores after server restart

FEATURE 1 — SWOT:
□ Generate CAM for Surya — SWOT panel visible in CAM tab
□ Surya SWOT Strengths: contains pharma-specific content and DSCR reference
□ Acme SWOT Threats: contains "NCLT" or "litigation"
□ Download CAM for Surya — Word doc opens, Section 10 is SWOT 2x2 table
□ Download CAM for Acme — Word doc opens, Section 10 is SWOT 2x2 table
□ CAM tab shows "11 sections" and SWOT in section list
□ README badge shows CAM_Sections-11
□ SWOT evaluation row in README shows ✅

FEATURE 3 — FIELDS:
□ New Case form shows "Annual Turnover (₹ Cr)" field
□ New Case form shows "Loan Tenure (Years)" dropdown
□ Submit form — fields appear in GET /cases/{id} response
□ Demo cases unaffected (no new required fields on demo load flow)

FEATURE 4 — SECTOR MACRO:
□ Research tab shows "Sector Intelligence" panel for Surya (pharmaceuticals)
□ Panel shows: POSITIVE outlook badge, sector avg DSCR 2.1x
□ Benchmark comparison: "Your DSCR: 3.09x vs Sector avg: 2.1x ↑"
□ Research tab shows panel for Acme (textiles) with NEUTRAL outlook
□ Drivers and Risks sections expand on click

CAM GENERATION:
□ CAM generates .docx file (NOT .txt)
□ File downloads and opens in Microsoft Word
□ 11 sections present in document
□ SWOT section has 2x2 table with colored headers

EXISTING TESTS:
□ pytest tests/ --tb=short — all existing tests still pass
□ pdfplumber import: python -c "import pdfplumber; print('OK')"

================================================================================
APPENDIX A — FEATURE 2: PDF EXTRACTION (BUILD ONLY IF CHECK 1/2 FAILED)
================================================================================

Only build this if the verification checks at the top showed that
pdfplumber is not installed or pdf_extractor.py does not exist/work.

--- A1. Install dependencies ---

Add to backend/requirements.txt:
  pdfplumber>=0.10.0
  pytesseract>=0.3.10

Run: pip install pdfplumber pytesseract --break-system-packages

--- A2. NEW FILE: backend/ingestor/pdf_extractor.py ---

import pdfplumber
import re
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class PDFExtractor:

    DOCUMENT_EXTRACTORS = {
        "annual_report":    "_extract_annual_report",
        "alm":              "_extract_alm",
        "shareholding":     "_extract_shareholding",
        "borrowing_profile":"_extract_borrowing_profile",
        "portfolio":        "_extract_portfolio",
    }

    def extract(self, pdf_path: str, doc_type: str) -> dict:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                method_name = self.DOCUMENT_EXTRACTORS.get(
                    doc_type, "_extract_annual_report"
                )
                method = getattr(self, method_name)
                result = method(pdf)
                result["confidence"] = self._compute_confidence(result)
                result["needs_ocr"] = result["confidence"] < 0.6
                result["doc_type"] = doc_type
                result["pages_processed"] = len(pdf.pages)
                return result
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return {
                "error": str(e),
                "confidence": 0.0,
                "needs_ocr": True,
                "doc_type": doc_type,
                "pages_processed": 0,
            }

    def _extract_annual_report(self, pdf) -> dict:
        result = {
            "years": [],
            "revenue_from_operations": [],
            "ebitda": [],
            "pat": [],
            "total_debt": [],
            "tangible_net_worth": [],
            "current_assets": [],
            "current_liabilities": [],
            "interest_expense": [],
            "extraction_warnings": [],
        }
        
        # Extract all tables from all pages
        all_tables = []
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)
        
        # Find financial statement tables
        revenue_keywords = ["revenue", "turnover", "operations", "income from"]
        pat_keywords = ["profit after tax", "pat", "net profit"]
        balance_keywords = ["total debt", "net worth", "borrowings"]
        
        for table in all_tables:
            if not table:
                continue
            table_text = " ".join([
                str(cell).lower()
                for row in table for cell in row if cell
            ])
            
            if any(kw in table_text for kw in revenue_keywords):
                self._parse_financial_table(table, result)
        
        return result

    def _extract_shareholding(self, pdf) -> dict:
        result = {
            "promoter_names": [],
            "promoter_holdings_pct": [],
            "promoter_pledged_pct": [],
            "total_promoter_pct": None,
            "total_pledged_pct": None,
            "public_pct": None,
            "extraction_warnings": [],
        }
        
        for page in pdf.pages:
            text = page.extract_text() or ""
            # Extract promoter % using regex
            promoter_match = re.search(
                r'promoter[s]?\s*[\:\-]?\s*([\d\.]+)\s*%',
                text, re.IGNORECASE
            )
            if promoter_match:
                result["total_promoter_pct"] = float(promoter_match.group(1))
            
            pledge_match = re.search(
                r'pledge[d]?\s*[\:\-]?\s*([\d\.]+)\s*%',
                text, re.IGNORECASE
            )
            if pledge_match:
                result["total_pledged_pct"] = float(pledge_match.group(1))
        
        return result

    def _extract_alm(self, pdf) -> dict:
        return {
            "total_assets_cr": None,
            "total_liabilities_cr": None,
            "short_term_assets_cr": None,
            "long_term_assets_cr": None,
            "short_term_liabilities_cr": None,
            "long_term_liabilities_cr": None,
            "asset_liability_gap_cr": None,
            "extraction_warnings": ["ALM extraction requires structured table format"],
        }

    def _extract_borrowing_profile(self, pdf) -> dict:
        return {
            "total_borrowings_cr": None,
            "bank_loans_cr": None,
            "ncd_cr": None,
            "weighted_avg_cost_pct": None,
            "extraction_warnings": [],
        }

    def _extract_portfolio(self, pdf) -> dict:
        return {
            "total_aum_cr": None,
            "gross_npa_pct": None,
            "net_npa_pct": None,
            "collection_efficiency_pct": None,
            "extraction_warnings": [],
        }

    def _parse_indian_number(self, text: str) -> Optional[float]:
        if not text:
            return None
        text = str(text).strip()
        
        # Remove currency symbols
        text = re.sub(r'[₹Rs\.]', '', text, flags=re.IGNORECASE).strip()
        
        is_crore = bool(re.search(r'cr|crore', text, re.IGNORECASE))
        is_lakh = bool(re.search(r'l|lakh|lac', text, re.IGNORECASE))
        
        # Remove unit words
        text = re.sub(r'crore[s]?|cr|lakh[s]?|lac[s]?|lakhs', '',
                      text, flags=re.IGNORECASE).strip()
        
        # Remove commas
        text = text.replace(',', '').strip()
        
        try:
            value = float(text)
            if is_crore:
                return value * 100  # Convert to Lakhs
            return value  # Already in Lakhs
        except ValueError:
            return None

    def _parse_financial_table(self, table: list, result: dict) -> None:
        if not table or len(table) < 2:
            return
        
        header_row = table[0]
        for row in table[1:]:
            if not row or not row[0]:
                continue
            label = str(row[0]).lower().strip()
            
            if any(kw in label for kw in ["revenue", "turnover", "operations"]):
                values = [self._parse_indian_number(cell) for cell in row[1:]]
                result["revenue_from_operations"] = [v for v in values if v]
            elif "pat" in label or "profit after tax" in label:
                values = [self._parse_indian_number(cell) for cell in row[1:]]
                result["pat"] = [v for v in values if v]
            elif "total debt" in label or "borrowings" in label:
                values = [self._parse_indian_number(cell) for cell in row[1:]]
                result["total_debt"] = [v for v in values if v]

    def _compute_confidence(self, result: dict) -> float:
        required_fields = [
            "revenue_from_operations", "pat", "total_debt"
        ]
        filled = sum(
            1 for f in required_fields
            if result.get(f) and len(result[f]) > 0
        )
        return filled / len(required_fields)

--- A3. UPDATE document_routes.py extract endpoint ---

In POST /api/v1/cases/{id}/documents/{doc_id}/extract:

from ingestor.pdf_extractor import PDFExtractor

@router.post("/cases/{case_id}/documents/{doc_id}/extract")
async def extract_document(case_id: str, doc_id: str, db: AsyncSession = Depends(get_db)):
    # Get document from DB
    # Get file path
    extractor = PDFExtractor()
    result = extractor.extract(file_path, doc_type)
    
    # Store extracted data in case
    # Return structured response
    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "extracted_fields": result,
        "confidence": result.get("confidence", 0),
        "needs_review": result.get("confidence", 0) < 0.7,
        "extraction_warnings": result.get("extraction_warnings", []),
        "pages_processed": result.get("pages_processed", 0),
    }

================================================================================
APPENDIX B — FEATURE 5: TRIANGULATION (BUILD ONLY IF CHECK 3 FAILED)
================================================================================

Only build this if triangulator.py does not exist or is a stub.

--- B1. NEW FILE: backend/research/triangulator.py ---

class DataTriangulator:

    def triangulate(
        self,
        extracted_financials: dict,
        research_findings: list,
        scorecard: dict
    ) -> dict:
        corroborations = []
        contradictions = []
        risk_adjustments = []

        corroborations += self._check_revenue_consistency(
            extracted_financials, research_findings
        )
        corroborations += self._check_debt_mentions(
            extracted_financials, research_findings
        )
        contradictions += self._check_management_consistency(
            extracted_financials, research_findings, scorecard
        )

        confidence = self._compute_confidence(corroborations, contradictions)

        return {
            "corroborations": corroborations,
            "contradictions": contradictions,
            "risk_adjustments": risk_adjustments,
            "confidence_score": confidence,
            "flags": [
                "DATA_TRIANGULATION_WARNING: Manual review recommended"
            ] if confidence < 0.6 else [],
        }

    def _check_revenue_consistency(self, financials, research) -> list:
        findings = []
        revenue_list = financials.get("revenue_from_operations", [])
        if len(revenue_list) >= 2:
            growing = revenue_list[-1] > revenue_list[0]
            for item in research:
                title = (item.get("title") or "").lower()
                if growing and any(
                    kw in title for kw in ["strong", "growth", "expansion"]
                ):
                    findings.append(
                        "Revenue growth in documents corroborated by positive news"
                    )
                elif not growing and any(
                    kw in title for kw in ["decline", "stress", "loss"]
                ):
                    findings.append(
                        "Revenue decline in documents corroborated by negative news"
                    )
        return findings

    def _check_debt_mentions(self, financials, research) -> list:
        findings = []
        for item in research:
            title = (item.get("title") or "").lower()
            if item.get("risk_tier") == 1:
                findings.append(
                    f"Critical research finding corroborated by score knockout flags"
                )
        return findings

    def _check_management_consistency(
        self, financials, research, scorecard
    ) -> list:
        contradictions = []
        knockouts = scorecard.get("knockout_flags", [])
        clean_research = all(
            item.get("risk_tier") != 1 for item in research
        )
        if knockouts and clean_research:
            contradictions.append(
                "Scorecard shows knockout flags but research found no critical issues"
            )
        return contradictions

    def _compute_confidence(
        self, corroborations: list, contradictions: list
    ) -> float:
        if not corroborations and not contradictions:
            return 0.75  # Neutral — insufficient data
        total = len(corroborations) + len(contradictions)
        if total == 0:
            return 0.75
        return min(0.95, 0.5 + (len(corroborations) / total) * 0.5)

--- B2. Wire triangulation into score_routes.py ---

In POST /cases/{id}/score, after scoring is complete:

from research.triangulator import DataTriangulator

# Only run if extracted document data exists (non-demo cases)
if case.financial_data and not case.is_demo:
    triangulator = DataTriangulator()
    research_items = case.research_items or []
    triangulation = triangulator.triangulate(
        case.financial_data,
        research_items,
        scorecard_result
    )
    score_response["triangulation"] = triangulation
else:
    score_response["triangulation"] = None

================================================================================
END OF PROMPT
================================================================================