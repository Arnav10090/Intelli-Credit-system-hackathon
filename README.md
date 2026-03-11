# Intelli-Credit — AI Credit Appraisal Engine

**End-to-end credit decisioning for Indian NBFC corporate lending — 
from financial documents to banker-grade CAM in under 60 seconds.**

Built for Tinkerers' Lab Hackathon by Team AI Apex · March 2026

---

## Live Demo

Two pre-loaded scenarios demonstrate the full pipeline:

| Company | Decision | Score | Key Signal |
|---|---|---|---|
| Surya Pharmaceuticals Ltd | ✅ APPROVE | 87/100 · Grade A+ | DSCR 3.09x · Zero pledge · USFDA certified |
| Acme Textiles Ltd | ❌ REJECT | 50/100 · Grade B | KNOCKOUT: Active NCLT IBC petition |

---

## Quick Start

### Option 1: Docker (Recommended)
```bash
git clone https://github.com/Arnav10090/Intelli-credit-system-hackathon
cd Intelli-credit-system-hackathon
cp .env.example .env
# Add your Groq API key to .env (free at console.groq.com)
docker-compose up --build
```

Open **http://localhost:5173**

### Option 2: Manual Setup
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# ML Model (first time only)
cd ml
python generate_data.py
python train_model.py

# Frontend
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## Architecture
```
Financial Documents (Annual Report, GST, Bank Statements)
                    │
                    ▼
          ┌─────────────────┐
          │  Data Ingestor  │
          │  GST Reconciler │
          │  RP Detector    │
          └────────┬────────┘
                   │
                   ▼
       ┌───────────────────────┐
       │   Feature Engineer    │
       │   16 features across  │
       │   Five Cs pillars     │
       └───────────┬───────────┘
                   │
                   ▼
       ┌───────────────────────┐
       │  Five Cs Scorer       │
       │  230 pts → 0-100      │
       │  Deterministic Python │
       └─────┬─────────┬───────┘
             │         │
             ▼         ▼
    ┌──────────────┐  ┌──────────────────┐
    │ Research     │  │ ML Validator     │
    │ Agent        │  │ sklearn HGBC     │
    │ News/Legal   │  │ ROC-AUC: 0.96    │
    │ MCA/eCourts  │  │ Calibrated probs │
    └──────┬───────┘  └────────┬─────────┘
           │                   │
           └─────────┬─────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  LLM Narrator        │
          │  llama-3.3-70b via   │
          │  Groq API            │
          │  Narrative only —    │
          │  zero number touch   │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  CAM Document        │
          │  10-section .docx    │
          │  + Audit Trail       │
          └──────────────────────┘
```

---

## Five Cs Scorecard

| Pillar | Max | Key Features |
|---|---|---|
| Character | 60 | Litigation risk, promoter track record, GST compliance, management quality |
| Capacity | 60 | DSCR, EBITDA margin trend, revenue CAGR vs sector, plant utilisation |
| Capital | 45 | D/E ratio, net worth trend, promoter equity % |
| Collateral | 30 | Security cover, collateral encumbrance |
| Conditions | 35 | Sector outlook, customer concentration, regulatory environment |
| **Total** | **230** | **Normalised to 0–100** |

**Decision Logic:**
- Score ≥ 55 AND no knockout flag → **APPROVE**
- Score 35–54 OR recoverable knockout → **PARTIAL**
- Score < 35 OR critical knockout → **REJECT**

**Knockout Triggers (auto-REJECT regardless of score):**
- DSCR < 1.0x
- Active NCLT / IBC petition
- GST circular trading detected
- Security cover < 0.8x

---

## Key Design Principle
```
All scoring is 100% deterministic Python.
The LLM only writes narrative prose — it never touches a number.
```

This ensures full auditability and RBI-defensible decisions.

---

## Hackathon Evaluation Coverage

| Criterion | Feature |
|---|---|
| Operational Excellence | FastAPI + React + SQLite · Docker one-command deploy |
| Extraction Accuracy | Pre-structured financial data · GST reconciler · RP detector |
| Analytical Depth | News crawler · eCourts check · MCA compliance · T1/T2 risk classification |
| Explainability | Feature contribution waterfall · rejection counter-factual · audit trail |
| Final Report | 10-section .docx CAM · LLM narrative · downloadable |
| ML Validation | HistGradientBoosting · ROC-AUC 0.96 · F1 0.83 · Calibrated probabilities |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · Python 3.11 · SQLite |
| Frontend | React 19 · Vite · Tailwind CSS · Recharts |
| ML | scikit-learn HistGradientBoostingClassifier · Platt scaling |
| LLM | llama-3.3-70b-versatile via Groq API |
| Document | Node.js · docx library · 10-section Word output |
| Research | httpx web crawler · Google News RSS · eCourts · MCA21 |

---

## Environment Setup

Copy `.env.example` to `.env` and set:
```
LLM_API_KEY=your_groq_api_key     # Free at console.groq.com
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

CAM narrative generation requires the Groq key.
All scoring, ML validation, and research work without it.

---

## ML Model

Trained on 5,000 synthetic Indian corporate loan cases:
```bash
cd ml
python generate_data.py   # Generate training data
python train_model.py     # Train and save model
```

Model saved to `ml/models/credit_validator.joblib`

**Performance:** ROC-AUC 0.9627 · AP 0.8939 · F1@0.45: 0.8259

---

## Running Tests
```bash
cd backend
pytest tests/ --tb=short
```

---

## Contributors

Built at National AI/ML Hackathon by Vivriti Capital Hackathon · March 2026  by Team : Team AI Apex