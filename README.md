# Intelli-Credit — AI Credit Decisioning Engine

**AI-powered Credit Appraisal Memo generator for Indian NBFC corporate lending.**

Intelli-Credit automates the end-to-end credit decisioning workflow by ingesting multi-source financial data (PDFs, GST returns, bank statements), conducting deep research (MCA filings, news, litigation), scoring borrowers using the Five Cs framework, and generating professional Credit Appraisal Memos (CAMs) with LLM-powered narratives.

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone <repository-url>
cd intelli-credit
cp .env.example .env
docker-compose up --build
```

Then open **http://localhost:5173** in your browser.

### Option 2: Manual Setup

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**ML Model:**
```bash
cd ml
python generate_data.py
python train_model.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Architecture

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
│  • Related Party Detector                                           │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Feature Engineer                                                   │
│  • 16 engineered features across Five Cs                            │
│  • DSCR, DE Ratio, Promoter Equity %, Security Cover                │
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
│ Agent        │      │ (sklearn HGBC)   │
│ • MCA        │      │ ROC-AUC: 0.96    │
│ • News       │      │ Calibrated probs │
│ • Litigation │      └─────────┬────────┘
└──────┬───────┘                │
       │                        │
       └────────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ Loan Calculator      │
         │ • Risk-based pricing │
         │ • Tenor optimization │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ LLM Narrator (Grok)  │
         │ • Executive Summary  │
         │ • Risk Analysis      │
         │ • Recommendation     │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ CAM Document (.docx) │
         └──────────────────────┘
```

---

## Demo Scenarios

Intelli-Credit includes two pre-built demo companies to showcase the full decisioning workflow:

### 1. Acme Textiles Ltd — REJECT Case

**Profile:**
- Sector: Textiles (export-oriented)
- Loan Request: ₹50 Cr term loan for capacity expansion
- Revenue: ₹180 Cr (FY24)

**Red Flags:**
- DSCR: 0.8x (below 1.25x threshold)
- Promoter Pledge: 68% of shares pledged
- NCLT Litigation: Ongoing insolvency case against subsidiary
- GST Compliance: 2 missed filings in last 12 months
- Working Capital: Negative cash conversion cycle

**Decision:** REJECT (Five Cs Score: 98/200)

### 2. Surya Pharmaceuticals Ltd — APPROVE Case

**Profile:**
- Sector: Pharmaceuticals (domestic + export)
- Loan Request: ₹30 Cr working capital facility
- Revenue: ₹220 Cr (FY24)

**Strengths:**
- DSCR: 2.6x (strong debt servicing capacity)
- Promoter Pledge: 0% (no encumbrance)
- USFDA Approved: 3 manufacturing facilities
- GST Compliance: 100% on-time filings
- Sector Outlook: Positive (PLI scheme beneficiary)

**Decision:** APPROVE (Five Cs Score: 168/200)

---

## Five Cs Scorecard (200 points)

| Category      | Max Points | Key Metrics                                                    |
|---------------|------------|----------------------------------------------------------------|
| **Character** | 60         | Litigation risk, promoter track record, GST compliance         |
| **Capacity**  | 60         | DSCR, EBITDA margin trend, revenue CAGR vs sector              |
| **Capital**   | 45         | D/E ratio, net worth trend, promoter equity %                  |
| **Collateral**| 30         | Security cover, collateral encumbrance                         |
| **Conditions**| 35         | Sector outlook, customer concentration, regulatory environment |

**Scoring Bands:**
- 160-200: Low Risk (Approve)
- 120-159: Medium Risk (Conditional Approve)
- 80-119: High Risk (Reject with Conditions)
- 0-79: Very High Risk (Reject)

---

## Evaluation Criteria Coverage

| Hackathon Criterion       | Intelli-Credit Feature                                          |
|---------------------------|-----------------------------------------------------------------|
| **Extraction Accuracy**   | PDF parser with Tesseract OCR fallback, table extraction        |
| **Research Depth**        | Research agent with MCA/news/litigation cache, web crawler      |
| **Explainability**        | Waterfall chart, audit trail, rejection counter-factual         |
| **Indian Context**        | GSTR-2A vs 3B reconciler, Section 17(5), NCLT detection         |
| **ML Validation**         | sklearn HistGradientBoostingClassifier (ROC-AUC 0.96)           |
| **CAM Generation**        | LLM-powered narrative with Grok-3, .docx export                 |

---

## Running Tests

Intelli-Credit includes 196+ property-based tests using pytest and Hypothesis:

```bash
cd tests
pytest --tb=short
```

**Test Coverage:**
- Data ingestion (PDF parsing, GST reconciliation, bank statement analysis)
- Feature engineering (DSCR, D/E ratio, promoter equity %)
- Five Cs scoring (all 16 features)
- ML model validation (calibration, feature importance)
- CAM generation (template rendering, LLM fallback)

---

## Tech Stack

**Backend:**
- FastAPI (async Python web framework)
- SQLite (zero-config database)
- Tesseract OCR (PDF text extraction)
- scikit-learn (ML model)

**Frontend:**
- React 19
- Vite (build tool)
- Tailwind CSS
- Recharts (data visualization)

**ML:**
- HistGradientBoostingClassifier (sklearn)
- Platt scaling for probability calibration
- Permutation feature importance

**LLM:**
- Grok-3 (xAI) for CAM narrative generation
- Fallback template if API key not provided

---

## API Endpoints

**Data Ingestion:**
- `POST /api/v1/cases` — Create new case
- `POST /api/v1/cases/{id}/upload` — Upload documents

**Scoring:**
- `GET /api/v1/cases/{id}/score` — Get Five Cs score
- `GET /api/v1/cases/{id}/features` — Get engineered features

**Research:**
- `POST /api/v1/research/company` — Fetch MCA/news/litigation data

**CAM Generation:**
- `POST /api/v1/cases/{id}/generate-cam` — Generate CAM document
- `GET /outputs/{filename}.docx` — Download CAM

---

## Environment Variables

See `.env.example` for all configuration options. Key variables:

- `LLM_API_KEY` — Grok API key (optional, fallback template used if blank)
- `DATABASE_URL` — SQLite or PostgreSQL connection string
- `VITE_API_BASE_URL` — Backend URL for frontend

---

## License

MIT License — see LICENSE file for details.

---

## Contributors

Built for National AI/ML Hackathon by Vivriti Capital by Team AI Apex.
