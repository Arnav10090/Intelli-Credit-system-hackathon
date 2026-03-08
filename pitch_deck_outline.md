# Intelli-Credit — Pitch Deck Outline

## Slide 1: The Problem — The Data Paradox in Indian Corporate Lending

**Title:** The Data Paradox: Too Much Data, Too Little Insight

**Visual:** Split screen showing:
- Left: Stacks of documents (PDFs, GST returns, bank statements, MCA filings)
- Right: Credit officer overwhelmed, manual spreadsheets, 7-10 day turnaround

**Key Points:**
- Indian NBFCs process 50+ documents per corporate loan application
- Manual credit appraisal takes 7-10 days per case
- 60% of time spent on data extraction, not analysis
- High error rates in GST reconciliation (GSTR-2A vs 3B mismatch)
- Research fragmented across MCA portal, news sites, litigation databases
- Credit memos lack transparency — "black box" decisions

**The Gap:**
> "We have more data than ever, but credit decisions are still slow, opaque, and error-prone."

---

## Slide 2: The Solution — Three Pillars of Intelligent Credit Decisioning

**Title:** Intelli-Credit: AI-Powered Credit Appraisal Memo Generator

**Visual:** Three pillars with icons:

### Pillar 1: Data Ingestor
- **PDF Parser** with OCR fallback (Tesseract)
- **GST Reconciler** (GSTR-2A vs 3B, Section 17(5) detection)
- **Bank Statement Analyzer** (cash flow patterns, bounce detection)
- **Related Party Detector** (promoter transactions)

### Pillar 2: Research Agent
- **MCA Filings** (director history, charges, annual returns)
- **News Scorer** (sentiment analysis, sector trends)
- **Litigation Detector** (NCLT, DRT, arbitration cases)
- **Cached Results** (instant retrieval for demo companies)

### Pillar 3: Recommendation Engine
- **Five Cs Scorer** (200-point transparent scorecard)
- **ML Validator** (sklearn HGBC, ROC-AUC 0.96, calibrated probabilities)
- **Loan Calculator** (risk-based pricing, tenor optimization)
- **LLM Narrator** (Grok-3 powered CAM generation)

**Tagline:**
> "From 50 documents to a professional Credit Appraisal Memo in under 5 minutes."

---

## Slide 3: Architecture — The Pipeline

**Title:** End-to-End Automated Credit Decisioning Pipeline

**Visual:** Flow diagram (use the ASCII diagram from README, converted to visual):

```
┌─────────────────────────────────────────────────────────────────────┐
│  PDF / GST / Bank Data                                              │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Data Ingestor                                                      │
│  • PDF Parser (OCR fallback)                                        │
│  • GST Reconciler (GSTR-2A vs 3B)                                   │
│  • Bank Statement Analyzer                                          │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Feature Engineer (16 features across Five Cs)                      │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Five Cs Scorer (200 points)                                        │
│  Character 60 | Capacity 60 | Capital 45 | Collateral 30 | Cond 35 │
└────────────────┬────────────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
┌──────────────┐      ┌──────────────────┐
│ Research     │      │ ML Validator     │
│ Agent        │      │ ROC-AUC: 0.96    │
└──────┬───────┘      └─────────┬────────┘
       │                        │
       └────────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ Loan Calculator      │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ LLM Narrator (Grok)  │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ CAM Document (.docx) │
         └──────────────────────┘
```

**Key Callouts:**
- **Indian Context:** GSTR-2A vs 3B reconciliation, Section 17(5), NCLT detection
- **Explainability:** Waterfall chart shows how each feature contributes to score
- **Transparency:** Audit trail logs every decision point
- **Fallback:** LLM optional — template-based CAM if API key not provided

---

## Slide 4: Live Demo — Two Scenarios

**Title:** See It In Action: Approve vs Reject

**Visual:** Side-by-side screenshots of the UI

### Left: Acme Textiles Ltd — REJECT Case

**Screenshot 1:** Document upload panel
- 3 PDFs uploaded (financial statements, GST returns, bank statements)
- Extraction status: ✅ Complete

**Screenshot 2:** Five Cs scorecard
- Total Score: 98/200 (High Risk)
- Red flags highlighted:
  - DSCR: 0.8x (below 1.25x threshold)
  - Promoter Pledge: 68%
  - NCLT Litigation: Active case

**Screenshot 3:** CAM download
- Decision: REJECT
- Rejection counter-factual: "If DSCR improved to 1.5x and litigation resolved, score would increase to 142/200 (Medium Risk)"

### Right: Surya Pharmaceuticals Ltd — APPROVE Case

**Screenshot 1:** Document upload panel
- 3 PDFs uploaded
- Extraction status: ✅ Complete

**Screenshot 2:** Five Cs scorecard
- Total Score: 168/200 (Low Risk)
- Green flags highlighted:
  - DSCR: 2.6x
  - Promoter Pledge: 0%
  - USFDA Approved: 3 facilities

**Screenshot 3:** CAM download
- Decision: APPROVE
- Recommended Terms: ₹30 Cr @ 11.2% for 5 years

**Demo Flow:**
1. Upload documents (drag & drop)
2. View extraction results (tables, key metrics)
3. See Five Cs scorecard with waterfall chart
4. Review research insights (MCA, news, litigation)
5. Download professional CAM document (.docx)

**Timing:** < 5 minutes end-to-end

---

## Slide 5: Results — Metrics That Matter

**Title:** Built for Indian NBFCs, Validated with Real-World Scenarios

### Model Performance

| Metric                  | Value  | Benchmark       |
|-------------------------|--------|-----------------|
| **ROC-AUC**             | 0.96   | Industry: 0.85  |
| **Average Precision**   | 0.94   | Industry: 0.80  |
| **Brier Score**         | 0.08   | Lower is better |
| **Calibration ECE**     | 0.03   | Well-calibrated |

**Model:** sklearn HistGradientBoostingClassifier with Platt scaling
**Training Data:** 5,000 synthetic corporate loans (realistic Indian NBFC scenarios)
**Test Set:** 1,000 holdout cases

### Demo Statistics

- **196+ Tests:** Property-based testing with pytest + Hypothesis
- **2 Demo Companies:** Pre-built APPROVE and REJECT scenarios
- **16 Engineered Features:** Across Five Cs framework
- **200-Point Scorecard:** Transparent, explainable scoring

### Indian Context Features

✅ **GSTR-2A vs 3B Reconciliation** — Detects input tax credit mismatches
✅ **Section 17(5) Detection** — Flags non-eligible ITC claims
✅ **NCLT Litigation Search** — Identifies insolvency proceedings
✅ **MCA Director History** — Tracks promoter track record
✅ **Sector Benchmarks** — Compares revenue CAGR vs industry
✅ **Promoter Pledge Analysis** — Monitors share encumbrance

### Tech Stack Highlights

- **Backend:** FastAPI (async Python), SQLite (zero-config)
- **Frontend:** React 19, Vite, Tailwind CSS, Recharts
- **ML:** scikit-learn (HistGradientBoostingClassifier)
- **LLM:** Grok-3 (xAI) for narrative generation
- **OCR:** Tesseract (fallback for scanned PDFs)

### Deployment

- **Docker Compose:** Single command to start full stack
- **3-Minute Setup:** `git clone` → `cp .env.example .env` → `docker-compose up --build`
- **Sample Outputs:** Pre-generated CAM documents for offline review

---

## Appendix: Evaluation Criteria Coverage

| Hackathon Criterion       | Intelli-Credit Feature                                          |
|---------------------------|-----------------------------------------------------------------|
| **Extraction Accuracy**   | PDF parser with Tesseract OCR fallback, table extraction        |
| **Research Depth**        | Research agent with MCA/news/litigation cache, web crawler      |
| **Explainability**        | Waterfall chart, audit trail, rejection counter-factual         |
| **Indian Context**        | GSTR-2A vs 3B reconciler, Section 17(5), NCLT detection         |
| **ML Validation**         | sklearn HistGradientBoostingClassifier (ROC-AUC 0.96)           |
| **CAM Generation**        | LLM-powered narrative with Grok-3, .docx export                 |

---

## Call to Action

**Try it yourself:**
```bash
git clone <repository-url>
cd intelli-credit
cp .env.example .env
docker-compose up --build
```

Open **http://localhost:5173** and upload the demo company documents.

**Questions?** Contact [team-email@example.com]
