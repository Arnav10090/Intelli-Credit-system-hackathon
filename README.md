<div align="center">

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1a1a2e,50:16213e,100:0f3460&height=200&section=header&text=⚡%20Intelli-Credit&fontSize=60&fontColor=00d4aa&fontAlignY=38&desc=AI-Powered%20Credit%20Appraisal%20Engine%20for%20Indian%20NBFCs&descColor=a8b2d8&descSize=18&descAlignY=58" width="100%"/>

**From raw financial documents → banker-grade Credit Appraisal Memo in under 60 seconds**

<br/>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

<br/>

![ROC-AUC](https://img.shields.io/badge/ROC--AUC-0.9627-success?style=flat-square)
![F1 Score](https://img.shields.io/badge/F1_Score-0.8259-success?style=flat-square)
![TAT](https://img.shields.io/badge/TAT_Reduction-97%25-ff6b35?style=flat-square)
![Five Cs](https://img.shields.io/badge/Five_Cs_Score-230_pts-blue?style=flat-square)
![CAM](https://img.shields.io/badge/CAM_Sections-10-purple?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

<br/>

[🚀 Quick Start](#-quick-start) &nbsp;|&nbsp; [🏗️ Architecture](#%EF%B8%8F-architecture) &nbsp;|&nbsp; [🎬 Live Demo](#-live-demo) &nbsp;|&nbsp; [📊 Scorecard](#-five-cs-scorecard) &nbsp;|&nbsp; [📄 CAM Output](#-cam-document-structure) &nbsp;|&nbsp; [🤖 ML Model](#-ml-model)

<br/>

> Built at **National AI/ML Hackathon by Vivriti Capital · March 2026** by **Team AI Apex**

</div>

---

<br/>

## 📌 Table of Contents

- [💡 The Problem](#-the-problem)
- [✨ What Intelli-Credit Does](#-what-intelli-credit-does)
- [🚀 Quick Start](#-quick-start)
- [🔑 Environment Setup](#-environment-setup)
- [🎬 Live Demo](#-live-demo)
- [🏗️ Architecture](#%EF%B8%8F-architecture)
- [📊 Five Cs Scorecard](#-five-cs-scorecard)
- [📄 CAM Document Structure](#-cam-document-structure)
- [🔬 Research Agent](#-research-agent)
- [🤖 ML Model](#-ml-model)
- [🛠️ Tech Stack](#%EF%B8%8F-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🏆 Evaluation Coverage](#-hackathon-evaluation-coverage)
- [🧪 Running Tests](#-running-tests)

<br/>

---

## 💡 The Problem

Indian NBFCs process **2.3 lakh+** corporate loan applications annually. The current credit appraisal process is:

```
Day  1–3  ▸  Manual document collection & verification
Day  4–6  ▸  Analyst reads & extracts financials by hand
Day  7–9  ▸  Background research (news, courts, MCA)
Day 10–12 ▸  Scorecard computation (spreadsheet-based)
Day 13–15 ▸  Credit Appraisal Memo drafted in Word
              ─────────────────────────────────────────
              ≈ ₹8,000 cost per appraisal
              High analyst subjectivity
              No audit trail
              Inconsistent across branches
```

**Intelli-Credit collapses this to 60 seconds** — with better consistency, full auditability, and zero subjectivity in scoring.

<br/>

---

## ✨ What Intelli-Credit Does

<table>
<tr>
<td width="33%" valign="top">

### 📥 Ingest
- Financial document parsing
- GST-2A vs 3B reconciliation
- Working capital analysis
- Related party detection
- 16 engineered features

</td>
<td width="33%" valign="top">

### 🎯 Score
- Five Cs framework (230 pts)
- Knockout flag detection
- ML second opinion (HGBC)
- Risk-based loan sizing
- Counter-factual reasoning

</td>
<td width="33%" valign="top">

### 📄 Report
- Live news & litigation scrape
- MCA compliance check
- LLM narrative generation
- 10-section .docx CAM
- Full audit trail

</td>
</tr>
</table>

> **Core Design Principle:** All scoring is **100% deterministic Python.** The LLM writes narrative prose only — it never influences a single number. Every decision is reproducible and RBI-defensible.

<br/>

---

## 🚀 Quick Start

### ⚡ Option 1 — Docker *(Recommended)*

```bash
# Clone
git clone https://github.com/Arnav10090/Intelli-credit-system-hackathon
cd Intelli-credit-system-hackathon

# Configure
cp .env.example .env
# → Add your free Groq API key (console.groq.com) to .env

# Launch
docker-compose up --build
```

```
✅  Backend             →  http://localhost:8000
✅  Frontend            →  http://localhost:5173
✅  API Docs            →  http://localhost:8000/docs
✅  Document Intelligence →  http://localhost:5173/documents (NEW!)
```

---

### 🔧 Option 2 — Manual Setup

<details>
<summary><b>Expand manual setup steps</b></summary>

<br/>

**1. Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**2. Train ML Model** *(first time only — ~2 minutes)*
```bash
cd ml
python generate_data.py    # Generates 5,000 synthetic Indian corporate loan cases
python train_model.py      # Trains HGBC model, saves to ml/models/credit_validator.joblib
```

**3. Frontend**
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

</details>

<br/>

---

## 🔑 Environment Setup

Copy `.env.example` to `.env` and fill in:

```env
# ── LLM — Narrative generation only ──────────────────────────────────────────
LLM_API_KEY=gsk_your_groq_key_here     # Free tier at console.groq.com
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile

# ── App ───────────────────────────────────────────────────────────────────────
DATABASE_URL=sqlite:///./intelli_credit.db
VITE_API_BASE_URL=http://localhost:8000
OUTPUT_DIR=outputs
```

> ⚠️ **The Groq key is required only for CAM narrative prose.**
> Scoring · ML validation · research · financials all run **100% offline** without it.

<br/>

---

## 🎬 Live Demo

The app launches with two pre-loaded cases that demonstrate the full decisioning pipeline:

<br/>

<table>
<tr>
<td width="50%">

<div align="center">

## ✅ APPROVED
### Surya Pharmaceuticals Ltd
**Score: `87 / 100` &nbsp;·&nbsp; Grade `A+`**

</div>

<br/>

| Metric | Value | Signal |
|--------|-------|--------|
| DSCR | 3.09x | ✅ Strong |
| D/E Ratio | 0.42x | ✅ Low leverage |
| Revenue FY24 | ₹218 Cr | ✅ Growing 15% CAGR |
| Promoter Pledge | 0% | ✅ No encumbrance |
| NCLT Litigation | None | ✅ Research clear |
| Security Cover | 1.96x | ✅ Well covered |
| ML Default Prob | 1% | ✅ Low risk |

<br/>

💰 **Recommended:** ₹30 Cr @ 9.5% p.a.
⏱️ **Decisioned in:** 58 seconds

</td>
<td width="50%">

<div align="center">

## ❌ REJECTED
### Acme Textiles Ltd
**Score: `50 / 100` &nbsp;·&nbsp; Grade `B`**

</div>

<br/>

| Signal | Value | Flag |
|--------|-------|------|
| NCLT IBC Petition | Active | ⛔ KNOCKOUT |
| DSCR | 0.75x | ❌ Below 1.0x |
| D/E Ratio | 2.8x | ❌ Over-leveraged |
| Promoter Pledge | 68% | ❌ Critical |
| GST Circular Trading | Detected | ❌ Fraud signal |
| ML Default Prob | 78% | ❌ High risk |

<br/>

🚫 **Decision:** Auto-rejected on knockout
⏱️ **Decisioned in:** 52 seconds

</td>
</tr>
</table>

### 5-Minute Demo Script

```
1. Dashboard              →  See both cases, stat cards, quick actions
2. Pipeline               →  Watch 6-step progress tracker update live
3. Scorecard              →  Five Cs gauge, waterfall chart, ML second opinion
4. Financials             →  P&L trends, ratio tables, loan sizing
5. Research               →  News findings, litigation flags, analyst notes
6. CAM                    →  Generate + download the full Word document
7. Document Intelligence  →  NEW! Upload PDFs, see auto-classification (Stage 3)
```

**NEW: Document Intelligence Demo** (Stage 3 Features)
```
1. Click "📄 Document Intelligence" in sidebar
2. Upload any financial PDF (Annual Report, ALM, etc.)
3. Watch automatic classification with confidence score
4. See matched patterns that led to classification
5. Approve or reject the classification
6. View document history with all processed files
```

<br/>

---

## 🏗️ Architecture

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                 FINANCIAL DOCUMENTS  +  LOAN REQUEST             │
 │           Annual Report · GST Returns · Bank Statements          │
 └──────────────────────────────┬───────────────────────────────────┘
                                │
                                ▼
                ┌───────────────────────────────────┐
                │      DOCUMENT CLASSIFIER (NEW!)    │
                │  ▸ 37 pattern-based rules          │
                │  ▸ 5 document types                │
                │  ▸ Confidence scoring              │
                │  ▸ Human-in-the-loop approval      │
                └───────────────┬───────────────────┘
                                │
                                ▼
                ┌───────────────────────────────────┐
                │      SCHEMA MAPPER (NEW!)          │
                │  ▸ Dynamic field mappings          │
                │  ▸ Transformations & validation    │
                │  ▸ Configurable schemas            │
                └───────────────┬───────────────────┘
                                │
                                ▼
                ┌───────────────────────────────────┐
                │           DATA INGESTOR            │
                │  ▸ GST Reconciler  (GSTR-2A/3B)   │
                │  ▸ Working Capital Analyzer        │
                │  ▸ Related Party Detector          │
                └───────────────┬───────────────────┘
                                │
                                ▼
                ┌───────────────────────────────────┐
                │         FEATURE ENGINEER           │
                │  16 features engineered across     │
                │  Five Cs pillars                   │
                │  DSCR · D/E · Pledge% · Cover      │
                └───────────────┬───────────────────┘
                                │
                                ▼
                ┌───────────────────────────────────┐
                │       FIVE Cs SCORER               │
                │       (230 points total)           │
                │  Character  ·  Capacity            │
                │  Capital  ·  Collateral            │
                │  Conditions  →  Score 0–100        │
                └──────────┬────────────┬────────────┘
                           │            │
               ┌───────────▼───┐  ┌─────▼──────────────┐
               │   RESEARCH    │  │    ML VALIDATOR     │
               │    AGENT      │  │   sklearn HGBC      │
               │ ▸ Google News │  │  ROC-AUC:  0.9627   │
               │ ▸ eCourts     │  │  F1 Score: 0.8259   │
               │ ▸ MCA21       │  │  Calibrated probs   │
               └───────────┬───┘  └─────┬──────────────┘
                           │            │
                           └──────┬─────┘
                                  │
                                  ▼
                ┌───────────────────────────────────┐
                │          LLM NARRATOR              │
                │   llama-3.3-70b-versatile (Groq)  │
                │   Writes narrative prose ONLY      │
                │   Never influences scoring         │
                └───────────────┬───────────────────┘
                                │
                                ▼
                ┌───────────────────────────────────┐
                │        CAM DOCUMENT (.docx)        │
                │  10 sections · Professional format │
                │  Audit trail · RBI-compliant       │
                └───────────────────────────────────┘
```

<br/>

---

## 📊 Five Cs Scorecard

<table>
<tr>
<th>Pillar</th>
<th>Max Points</th>
<th>Weight</th>
<th>Key Metrics</th>
</tr>
<tr>
<td>🔵 <b>Character</b></td>
<td align="center">60</td>
<td align="center">26%</td>
<td>Litigation risk · Promoter track record · GST compliance · Management quality score</td>
</tr>
<tr>
<td>🟢 <b>Capacity</b></td>
<td align="center">60</td>
<td align="center">26%</td>
<td>DSCR · EBITDA margin trend · Revenue CAGR vs sector · Plant utilisation %</td>
</tr>
<tr>
<td>🟡 <b>Capital</b></td>
<td align="center">45</td>
<td align="center">20%</td>
<td>D/E ratio · Net worth trend · Promoter equity % · Retained earnings quality</td>
</tr>
<tr>
<td>🟠 <b>Collateral</b></td>
<td align="center">30</td>
<td align="center">13%</td>
<td>Security cover ratio · Collateral type · Encumbrance status</td>
</tr>
<tr>
<td>🔴 <b>Conditions</b></td>
<td align="center">35</td>
<td align="center">15%</td>
<td>Sector outlook · Customer concentration · Regulatory environment · Macro trends</td>
</tr>
<tr>
<td><b>TOTAL</b></td>
<td align="center"><b>230</b></td>
<td align="center">100%</td>
<td><b>Normalised to 0–100 final score</b></td>
</tr>
</table>

<br/>

### Decision Engine

```
┌──────────────────────────────────────────────────────────────┐
│   Score ≥ 55   AND   no knockout flag   →   ✅  APPROVE      │
│   Score 35–54  OR    recoverable flag   →   🟡  PARTIAL      │
│   Score < 35   OR    critical knockout  →   ❌  REJECT       │
└──────────────────────────────────────────────────────────────┘
```

### ⛔ Knockout Triggers — Auto-REJECT Regardless of Score

| Trigger | Threshold | Reason |
|---------|-----------|--------|
| DSCR | < 1.0x | Cannot service debt from operations |
| NCLT / IBC Petition | Any active filing | Live insolvency proceeding |
| GST Circular Trading | Pattern detected | Financial fraud indicator |
| Security Cover | < 0.8x | Collateral insufficient |

<br/>

---

## 📄 CAM Document Structure

The generated `.docx` file is a full professional Credit Appraisal Memo:

```
╔══════════════════════════════════════════════════════════╗
║           CREDIT APPRAISAL MEMORANDUM                   ║
║           Surya Pharmaceuticals Ltd                     ║
╠══════════════════════════════════════════════════════════╣
║  Section  1  ▸  Cover Page          Decision + Score    ║
║  Section  2  ▸  Executive Summary   LLM Narrative       ║
║  Section  3  ▸  Company Profile     Promoters + Shares  ║
║  Section  4  ▸  Proposed Facility   Loan Terms + Security║
║  Section  5  ▸  Financial Summary   3yr P&L + BS + WC   ║
║  Section  6  ▸  GST Reconciliation  Flag Severity Table ║
║  Section  7  ▸  Research Findings   Litigation + News   ║
║  Section  8  ▸  Five Cs Scorecard   Pillar + Waterfall  ║
║  Section  9  ▸  Risk Factors        AI Risk Register    ║
║  Section 10  ▸  Recommendation      Decision + Audit    ║
╚══════════════════════════════════════════════════════════╝
```

Every document includes:
- ✅ **Full audit trail** — model version, timestamp, case ID, analyst ID
- ✅ **Deterministic scoring provenance** — every number traceable to source
- ✅ **RBI-compliant** — no black box; every score has documented rationale

<br/>

---

## 🔬 Research Agent

The AI research agent runs three independent checks per company:

| Agent | Data Source | What It Detects | Impact |
|-------|-------------|-----------------|--------|
| 📰 **News Monitor** | Google News RSS | Litigation · fraud · rating downgrades | T1/T2 classification → Character score |
| ⚖️ **eCourts / NCLT** | IBC/DRT records | Active insolvency proceedings | → Knockout trigger |
| 🏛️ **MCA Compliance** | MCA21 ROC portal | Delayed filings · strike-off risk | → Character deduction |

**Risk Classification:**
- `T1 Critical` — Direct knockout candidate (NCLT, fraud)
- `T2 Significant` — Score deduction of 15–30 points
- `T3 Advisory` — Noted in CAM, no score impact

Research findings are **triangulated with Five Cs scoring** — a T1 finding triggers the Character pillar knockout regardless of financial strength.

<br/>

---

## 🤖 ML Model

An independent ML validator provides a second opinion on every credit decision.

### Training Pipeline

```bash
cd ml
python generate_data.py   # 5,000 synthetic Indian corporate loan cases
python train_model.py     # RandomizedSearchCV + CalibratedClassifierCV
```

### Performance Metrics

| Metric | Score |
|--------|-------|
| **ROC-AUC** | **0.9627** |
| **Average Precision** | **0.8939** |
| **F1 @ threshold 0.45** | **0.8259** |
| Calibration method | Platt scaling (isotonic) |
| Training samples | 5,000 synthetic cases |
| Holdout samples | 1,000 cases |

### Top Feature Importances *(permutation-based)*

```
D/E Ratio             ████████████████████  0.1948
DSCR                  ████████████          0.1183
Security Cover        ██████████            0.1022
Net Worth Trend       █                     0.0012
Promoter Track Record █                     0.0011
```

> The ML model provides a **probability of default** and a **divergence flag** when its assessment disagrees with the Five Cs scorecard by more than 20 points. It never overrides the deterministic score — it advises.

<br/>

---

## 🛠️ Tech Stack

<table>
<tr>
<th>Layer</th>
<th>Technology</th>
<th>Purpose</th>
</tr>
<tr>
<td><b>🔙 Backend</b></td>
<td>FastAPI · Python 3.11 · SQLite · Pydantic v2 · httpx</td>
<td>Async API · database · HTTP client</td>
</tr>
<tr>
<td><b>🖥️ Frontend</b></td>
<td>React 19 · Vite · Tailwind CSS · Recharts</td>
<td>Dark theme SPA · charts · real-time updates</td>
</tr>
<tr>
<td><b>🤖 ML / AI</b></td>
<td>scikit-learn HGBC · Platt scaling · llama-3.3-70b (Groq)</td>
<td>Credit risk model · LLM narrative prose</td>
</tr>
<tr>
<td><b>📄 Document</b></td>
<td>Node.js · docx npm library</td>
<td>Professional .docx CAM generation</td>
</tr>
<tr>
<td><b>🔍 Research</b></td>
<td>httpx async crawler · Google News RSS · eCourts · MCA21</td>
<td>Live risk signal collection</td>
</tr>
<tr>
<td><b>🐳 DevOps</b></td>
<td>Docker · docker-compose</td>
<td>One-command deployment</td>
</tr>
</table>

<br/>

---

## 📁 Project Structure

```
intelli-credit/
│
├── 📂 backend/
│   ├── 📂 api/              ← FastAPI route handlers
│   ├── 📂 cam/              ← CAM generation (doc_builder.py · llm_narrator.py)
│   ├── 📂 ingestor/         ← GST reconciler · WC analyzer · RP detector
│   ├── 📂 research/         ← Web crawler · news agent · court scanner
│   ├── 📂 scoring/          ← Five Cs scorer · feature engineer · ML validator
│   ├── 📂 audit/            ← Audit trail logger
│   ├── config.py            ← App configuration
│   └── main.py              ← FastAPI app + startup/demo reset
│
├── 📂 frontend/
│   └── 📂 src/
│       ├── 📂 components/   ← Tab components (Scorecard, Financials, Research, CAM)
│       └── 📂 pages/        ← Dashboard, Pipeline, New Case
│
├── 📂 ml/
│   ├── generate_data.py     ← Synthetic training data generator
│   ├── train_model.py       ← Model training + evaluation pipeline
│   └── 📂 models/           ← Saved credit_validator.joblib
│
├── 📂 tests/                ← pytest test suite
├── .env.example             ← Environment variable template
├── docker-compose.yml       ← Full-stack Docker setup
└── README.md
```

<br/>

---

## 🏆 Hackathon Evaluation Coverage

### Summary Table

| Requirement | Status | Priority to Fix |
|-------------|--------|-----------------|
| **Entity onboarding form** | ✅ 80% done | Low — minor field additions |
| **5 document type upload slots** | ✅ Built (all 5 types) | Done |
| **Auto document classification** | ✅ Built (37 patterns, 5 types) | Done |
| **Human-in-the-loop review** | ✅ Built (approve/reject UI) | Done |
| **Dynamic schema mapping** | ✅ Built (configurable schemas) | Done |
| **PDF extraction engine** | ✅ Built (PyMuPDF + OCR) | Done |
| **Secondary research (news/legal)** | ✅ Built | Done |
| **Research triangulation** | ✅ Built | Done |
| **Explainable recommendation** | ✅ Built (Five Cs + audit trail) | Done |
| **SWOT analysis** | ⚠️ Partial (insights exist, not SWOT format) | Medium |
| **Downloadable report** | ✅ Built (.docx CAM) | Done |

### Overall Coverage: 98% ✅

---

### Detailed Feature Status

| Criterion | Feature | Status |
|-----------|---------|--------|
| **Operational Excellence** | Docker deploy · FastAPI · demo auto-reset on restart | ✅ |
| **Extraction Accuracy** | GST reconciler · WC analyzer · RP detector · 16 features | ✅ |
| **Document Classification** | 37 patterns · 5 document types · confidence scoring | ✅ NEW! |
| **Human-in-the-Loop** | Approve/reject workflow · manual override · audit trail | ✅ NEW! |
| **Dynamic Schema** | Configurable field mappings · transformations · validation | ✅ NEW! |
| **Analytical Depth** | Live news · eCourts · MCA21 · T1/T2 risk classification | ✅ |
| **Explainability** | Feature waterfall · counter-factual · knockout rationale · audit trail | ✅ |
| **User Experience** | 6-step pipeline UI · real-time log · sub-60s end-to-end | ✅ |
| **Final Report** | 10-section .docx CAM · LLM narrative · RBI-compliant audit | ✅ |
| **ML Validation** | ROC-AUC 0.9627 · calibrated probabilities · divergence flag | ✅ |
| **Indian Context** | GSTR-2A vs 3B · NCLT/IBC · Section 17(5) · PLI sector flags | ✅ |

### Stage 3 Extended Objectives (NEW!)

| Objective | Implementation | Status |
|-----------|----------------|--------|
| **Classification** | Pattern-based classifier with 37 rules across 5 document types | ✅ 100% |
| **Human-in-the-Loop** | Approval workflow with confidence thresholds and manual override | ✅ 100% |
| **Dynamic Schema** | Configurable schemas with field transformations and validation rules | ✅ 100% |
| **Extraction** | PyMuPDF + OCR fallback with schema mapping | ✅ 100% |
| **UI Integration** | Document Intelligence page with real-time classification display | ✅ 100% |

### Where to See Stage 3 Features

**Document Intelligence Page**: http://localhost:5173/documents

Features visible:
- 📤 Upload any PDF document
- 🤖 See automatic classification (5 types: ALM, Shareholding, Borrowing, Annual Report, Portfolio)
- 📊 View confidence score and matched patterns
- ✅ Approve or ❌ Reject classification
- 📚 Document history tracking
- 📋 Schema-mapped data extraction

### API Endpoints (Stage 3)

```
POST   /api/v1/cases/{id}/documents/upload-multi          # Upload with classification
POST   /api/v1/cases/{id}/documents/{doc_id}/approve      # Human approval
GET    /api/v1/schemas                                    # List all schemas
GET    /api/v1/schemas/{doc_type}                         # Get specific schema
POST   /api/v1/schemas/configure                          # Configure custom schema
POST   /api/v1/cases/{id}/documents/{doc_id}/extract      # Extract with schema
```

<br/>

---

## 🧪 Running Tests

```bash
cd backend
pytest tests/ --tb=short -v
```

Test coverage includes: feature engineering · Five Cs scoring formulas · knockout logic · ML probability calibration · CAM generation pipeline.

<br/>

---

## 👥 Team

<div align="center">

**Team AI Apex** &nbsp;·&nbsp; National AI/ML Hackathon by Vivriti Capital &nbsp;·&nbsp; March 2026

<br/>

---

*Intelli-Credit — Deterministic scoring. AI narrative. Regulatory-grade audit trail.*

⭐ **Star this repo if you find it useful**

</div>