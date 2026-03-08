# Sample CAM Outputs

This directory contains pre-generated Credit Appraisal Memo (CAM) documents for the two demo companies. These are provided for judges to review offline if the live demo encounters any issues.

## Files

1. **CreditAppraisalMemo_AcmeTextiles.docx** — REJECT case
   - Company: Acme Textiles Ltd
   - Decision: REJECT
   - Five Cs Score: 98/200 (High Risk)
   - Key Issues: DSCR stress (0.8x), NCLT litigation, high promoter pledge (68%)

2. **CreditAppraisalMemo_SuryaPharma.docx** — APPROVE case
   - Company: Surya Pharmaceuticals Ltd
   - Decision: APPROVE
   - Five Cs Score: 168/200 (Low Risk)
   - Strengths: Strong DSCR (2.6x), zero pledge, USFDA approved facilities

## How to Generate These Files

If you need to regenerate these CAM documents, follow these steps:

### Prerequisites

1. Start the backend server:
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

2. Ensure the demo company data exists in `backend/data/demo_company/` and `backend/data/demo_company2/`

### Generate CAM for Acme Textiles (REJECT case)

```bash
# Create a case and get the case_id
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Textiles Ltd",
    "cin": "U17110MH2010PLC123456",
    "loan_amount": 50000000,
    "loan_purpose": "Term loan for capacity expansion"
  }'

# Note the case_id from the response (e.g., "abc123")

# Generate CAM document
curl -X POST http://localhost:8000/api/v1/cases/{case_id}/generate-cam

# Download the generated CAM
curl -O http://localhost:8000/outputs/CreditAppraisalMemo_{case_id}.docx

# Rename to standard name
mv CreditAppraisalMemo_{case_id}.docx sample_outputs/CreditAppraisalMemo_AcmeTextiles.docx
```

### Generate CAM for Surya Pharmaceuticals (APPROVE case)

```bash
# Create a case and get the case_id
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Surya Pharmaceuticals Ltd",
    "cin": "U24230KA2015PLC234567",
    "loan_amount": 30000000,
    "loan_purpose": "Working capital facility"
  }'

# Note the case_id from the response (e.g., "xyz789")

# Generate CAM document
curl -X POST http://localhost:8000/api/v1/cases/{case_id}/generate-cam

# Download the generated CAM
curl -O http://localhost:8000/outputs/CreditAppraisalMemo_{case_id}.docx

# Rename to standard name
mv CreditAppraisalMemo_{case_id}.docx sample_outputs/CreditAppraisalMemo_SuryaPharma.docx
```

### Alternative: Use the Frontend UI

1. Open http://localhost:5173
2. Click "New Case"
3. Enter company details (use demo company names above)
4. Upload documents (or use pre-loaded demo data)
5. Click "Generate CAM"
6. Download the .docx file from the UI
7. Save to `sample_outputs/` with the appropriate filename

## Notes

- The CAM generation requires the LLM API key (Grok) to be set in `.env` for full narrative generation
- If the API key is not set, a template-based CAM will be generated instead
- The demo company data is pre-cached in `backend/data/demo_company/` and `backend/data/demo_company2/`
- Research results (MCA, news, litigation) are also pre-cached for instant retrieval

## Troubleshooting

**Issue:** CAM generation fails with "Model not found"
**Solution:** Ensure the ML model is trained:
```bash
cd ml
python generate_data.py
python train_model.py
```

**Issue:** CAM generation returns empty document
**Solution:** Check that the case has been scored first:
```bash
curl http://localhost:8000/api/v1/cases/{case_id}/score
```

**Issue:** LLM narrative is missing
**Solution:** Either set `LLM_API_KEY` in `.env` or accept the template-based fallback
