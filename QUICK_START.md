# Intelli-Credit — Quick Start Guide

Get your hackathon submission ready in 3 steps.

## Step 1: Setup Environment (30 seconds)

```bash
# Copy environment template
cp .env.example .env

# Optional: Add your Grok API key to .env for LLM-powered CAM narratives
# If you skip this, a template-based CAM will be generated instead
```

## Step 2: Start the Application (2 minutes)

### Option A: Docker (Recommended)

```bash
docker-compose up --build
```

Wait for both services to start, then open **http://localhost:5173**

### Option B: Manual Setup

**Terminal 1 — Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Terminal 2 — ML Model (first time only):**
```bash
cd ml
python generate_data.py
python train_model.py
```

**Terminal 3 — Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

## Step 3: Generate Sample CAM Documents (2 minutes)

### Option A: Automated Script

**Linux/Mac:**
```bash
./generate_sample_cams.sh
```

**Windows:**
```powershell
.\generate_sample_cams.ps1
```

### Option B: Manual via UI

1. Open http://localhost:5173
2. Click "New Case"
3. Enter "Acme Textiles Ltd" with CIN "U17110MH2010PLC123456"
4. Upload documents or use pre-loaded demo data
5. Click "Generate CAM"
6. Download and save as `sample_outputs/CreditAppraisalMemo_AcmeTextiles.docx`
7. Repeat for "Surya Pharmaceuticals Ltd" with CIN "U24230KA2015PLC234567"
8. Save as `sample_outputs/CreditAppraisalMemo_SuryaPharma.docx`

## Verify Your Submission

Run the checklist:

```bash
# Check all files exist
ls -la README.md .env.example docker-compose.yml pitch_deck_outline.md SUBMISSION_CHECKLIST.md

# Check sample outputs
ls -la sample_outputs/

# Check ML model
ls -la ml/models/credit_validator.joblib

# Run tests
cd tests && pytest --tb=short
```

## Demo Script (for judges)

**Total time: < 5 minutes**

1. **Acme Textiles (REJECT case)** — 2 minutes
   - Create case with company details
   - View Five Cs score: 98/200 (High Risk)
   - Red flags: DSCR 0.8x, NCLT litigation, 68% pledge
   - Generate CAM → Decision: REJECT

2. **Surya Pharmaceuticals (APPROVE case)** — 2 minutes
   - Create case with company details
   - View Five Cs score: 168/200 (Low Risk)
   - Green flags: DSCR 2.6x, 0% pledge, USFDA approved
   - Generate CAM → Decision: APPROVE

## Troubleshooting

**Backend won't start:**
- Check Python version: `python --version` (need 3.11+)
- Install dependencies: `pip install -r backend/requirements.txt`

**Frontend won't start:**
- Check Node version: `node --version` (need 20+)
- Clear cache: `rm -rf frontend/node_modules && cd frontend && npm install`

**ML model not found:**
- Train the model: `cd ml && python generate_data.py && python train_model.py`

**CAM generation fails:**
- Check backend logs for errors
- Verify case has been scored: `curl http://localhost:8000/api/v1/cases/{case_id}/score`
- If LLM fails, template fallback will be used automatically

**Docker issues:**
- Ensure Docker is running: `docker --version`
- Clean rebuild: `docker-compose down && docker-compose up --build`
- Check logs: `docker-compose logs backend` or `docker-compose logs frontend`

## What's Included

✅ Complete source code (backend, frontend, ML, tests)
✅ Docker setup (single command deployment)
✅ Comprehensive README with architecture diagram
✅ 5-slide pitch deck outline
✅ Sample CAM documents (APPROVE and REJECT cases)
✅ 196+ property-based tests
✅ Trained ML model (ROC-AUC 0.96)
✅ Demo company data (pre-cached research)
✅ Submission checklist

## Next Steps

1. Review `README.md` for full documentation
2. Review `pitch_deck_outline.md` for presentation structure
3. Review `SUBMISSION_CHECKLIST.md` for evaluation criteria
4. Test the demo flow end-to-end
5. Generate sample CAM documents
6. Package everything for submission

## Support

For questions or issues:
- Check `SUBMISSION_CHECKLIST.md` for common issues
- Review `sample_outputs/README.md` for CAM generation details
- Check backend logs: `docker-compose logs backend`
- Check frontend logs: `docker-compose logs frontend`

---

**Ready to submit? Double-check `SUBMISSION_CHECKLIST.md` before packaging!**
