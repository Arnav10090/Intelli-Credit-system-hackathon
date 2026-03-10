# Intelli-Credit — Hackathon Submission Checklist

## ✅ Documentation

- [x] **README.md** — Complete project documentation with:
  - Quick start guide (Docker + manual setup)
  - Architecture diagram
  - Demo scenarios (Acme Textiles, Surya Pharmaceuticals)
  - Five Cs scorecard breakdown
  - Evaluation criteria coverage
  - Test instructions

- [x] **.env.example** — Environment variable template with:
  - Grok API configuration (optional)
  - Backend settings (database, secret key, log level)
  - Frontend settings (API base URL)

- [x] **pitch_deck_outline.md** — 5-slide pitch deck structure:
  - Slide 1: Problem (Data Paradox in Indian lending)
  - Slide 2: Solution (Three pillars)
  - Slide 3: Architecture (Pipeline diagram)
  - Slide 4: Live Demo (Screenshots, flow)
  - Slide 5: Results (Model metrics, Indian context features)

## ✅ Configuration

- [x] **docker-compose.yml** — Updated with:
  - Backend service with ML model volume mount (`./ml/models:/app/ml/models`)
  - Frontend service with proper dependencies
  - Environment variable support via `.env` file
  - Health checks for backend
  - Data persistence volumes

- [x] **backend/Dockerfile** — Updated with:
  - ML models directory creation
  - Volume mount support for trained models
  - All system dependencies (Tesseract, Poppler, etc.)

- [x] **frontend/Dockerfile** — Created with:
  - Node.js 20 base image
  - Vite dev server configuration
  - Host binding for Docker access

## ✅ Sample Outputs

- [x] **sample_outputs/README.md** — Instructions for generating CAM documents:
  - curl commands for both demo companies
  - Alternative UI-based generation steps
  - Troubleshooting guide

- [ ] **sample_outputs/CreditAppraisalMemo_AcmeTextiles.docx** — REJECT case CAM
  - **Action Required:** Generate this file by running the demo
  - See `sample_outputs/README.md` for instructions

- [ ] **sample_outputs/CreditAppraisalMemo_SuryaPharma.docx** — APPROVE case CAM
  - **Action Required:** Generate this file by running the demo
  - See `sample_outputs/README.md` for instructions

## 📋 Pre-Submission Tasks

### 1. Train ML Model (if not already done)

```bash
cd ml
python generate_data.py
python train_model.py
```

**Expected Output:**
- `ml/models/credit_validator.joblib`
- `ml/models/feature_importances.json`
- `ml/models/training_report.json`

### 2. Test Docker Setup

```bash
# Copy environment template
cp .env.example .env

# Start services
docker-compose up --build

# Verify backend health
curl http://localhost:8000/api/health

# Verify frontend
# Open http://localhost:5173 in browser
```

### 3. Generate Sample CAM Documents

Follow instructions in `sample_outputs/README.md` to generate:
1. CreditAppraisalMemo_AcmeTextiles.docx (REJECT case)
2. CreditAppraisalMemo_SuryaPharma.docx (APPROVE case)

### 4. Run Tests

```bash
cd tests
pytest --tb=short
```

**Expected:** 196+ tests passing

### 5. Verify Demo Companies

Check that demo data exists:
- `backend/data/demo_company/financial_data.json`
- `backend/data/demo_company/gst_data.json`
- `backend/data/demo_company/research_cache.json`
- `backend/data/demo_company2/financial_data.json`
- `backend/data/demo_company2/gst_data.json`
- `backend/data/demo_company2/research_cache.json`

## 🎯 Hackathon Evaluation Criteria

### Extraction Accuracy
- ✅ PDF parser with Tesseract OCR fallback
- ✅ Table extraction for financial statements
- ✅ GST reconciliation (GSTR-2A vs 3B)
- ✅ Bank statement analysis

### Research Depth
- ✅ MCA filings integration
- ✅ News sentiment analysis
- ✅ Litigation detection (NCLT, DRT)
- ✅ Cached results for demo

### Explainability
- ✅ Waterfall chart showing feature contributions
- ✅ Audit trail for all decisions
- ✅ Rejection counter-factual ("What if" scenarios)
- ✅ Transparent Five Cs scorecard

### Indian Context
- ✅ GSTR-2A vs 3B reconciliation
- ✅ Section 17(5) ITC detection
- ✅ NCLT litigation search
- ✅ MCA director history
- ✅ Sector benchmarks (Indian industries)
- ✅ Promoter pledge analysis

### ML Validation
- ✅ sklearn HistGradientBoostingClassifier
- ✅ ROC-AUC: 0.96
- ✅ Calibrated probabilities (Platt scaling)
- ✅ Permutation feature importance

### CAM Generation
- ✅ LLM-powered narrative (Grok-3)
- ✅ Template fallback (no API key required)
- ✅ .docx export
- ✅ Professional formatting

## 📦 Final Submission Package

Your submission should include:

1. **Source Code**
   - All files in the repository
   - `.env.example` (NOT `.env` with real API keys)
   - `docker-compose.yml`
   - `README.md`

2. **Documentation**
   - `README.md` — Project overview and setup
   - `pitch_deck_outline.md` — Presentation structure
   - `SUBMISSION_CHECKLIST.md` — This file

3. **Sample Outputs**
   - `sample_outputs/CreditAppraisalMemo_AcmeTextiles.docx`
   - `sample_outputs/CreditAppraisalMemo_SuryaPharma.docx`
   - `sample_outputs/README.md` — Generation instructions

4. **Trained Model**
   - `ml/models/credit_validator.joblib`
   - `ml/models/feature_importances.json`
   - `ml/models/training_report.json`

5. **Demo Data**
   - `backend/data/demo_company/` — Acme Textiles
   - `backend/data/demo_company2/` — Surya Pharmaceuticals

## 🚀 Quick Demo Script (for judges)

```bash
# 1. Clone and setup (30 seconds)
git clone <repository-url>
cd intelli-credit
cp .env.example .env
docker-compose up --build

# 2. Open browser (5 seconds)
# Navigate to http://localhost:5173

# 3. Demo Acme Textiles — REJECT case (2 minutes)
# - Click "New Case"
# - Enter: Acme Textiles Ltd, CIN: U17110MH2010PLC123456
# - Upload documents or use pre-loaded demo data
# - View Five Cs scorecard (98/200 — High Risk)
# - Review red flags (DSCR 0.8x, NCLT litigation, 68% pledge)
# - Generate and download CAM document
# - Decision: REJECT

# 4. Demo Surya Pharmaceuticals — APPROVE case (2 minutes)
# - Click "New Case"
# - Enter: Surya Pharmaceuticals Ltd, CIN: U24230KA2015PLC234567
# - Upload documents or use pre-loaded demo data
# - View Five Cs scorecard (168/200 — Low Risk)
# - Review green flags (DSCR 2.6x, 0% pledge, USFDA approved)
# - Generate and download CAM document
# - Decision: APPROVE

# Total demo time: < 5 minutes
```

## 📧 Support

For questions or issues during evaluation, contact:
- **Team:** [Team Name]
- **Email:** [team-email@example.com]
- **GitHub:** [repository-url]

## ✨ Key Differentiators

1. **Indian Context:** Only solution with GSTR-2A vs 3B reconciliation and Section 17(5) detection
2. **Explainability:** Waterfall chart + rejection counter-factual + audit trail
3. **Speed:** < 5 minutes from documents to CAM (vs 7-10 days manual)
4. **Transparency:** 200-point Five Cs scorecard (not a black box)
5. **Production-Ready:** 196+ tests, Docker deployment, calibrated ML model

---

**Good luck with your submission! 🚀**
