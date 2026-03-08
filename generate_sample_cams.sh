#!/bin/bash

# ─────────────────────────────────────────────────────────────────────────────
# generate_sample_cams.sh
# Helper script to generate sample CAM documents for both demo companies
# ─────────────────────────────────────────────────────────────────────────────

set -e

API_BASE="http://localhost:8000/api/v1"
OUTPUT_DIR="sample_outputs"

echo "════════════════════════════════════════════════════════════════════════"
echo "  Intelli-Credit — Sample CAM Generator"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Check if backend is running
echo "→ Checking backend health..."
if ! curl -sf "$API_BASE/../health" > /dev/null; then
    echo "❌ Backend is not running!"
    echo "   Please start the backend first:"
    echo "   cd backend && uvicorn main:app --reload --port 8000"
    exit 1
fi
echo "✅ Backend is healthy"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Generate Acme Textiles CAM (REJECT case)
# ─────────────────────────────────────────────────────────────────────────────

echo "→ Creating case for Acme Textiles Ltd (REJECT case)..."
ACME_RESPONSE=$(curl -s -X POST "$API_BASE/cases" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Textiles Ltd",
    "cin": "U17110MH2010PLC123456",
    "loan_amount": 50000000,
    "loan_purpose": "Term loan for capacity expansion"
  }')

ACME_CASE_ID=$(echo "$ACME_RESPONSE" | grep -o '"case_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$ACME_CASE_ID" ]; then
    echo "❌ Failed to create Acme Textiles case"
    echo "   Response: $ACME_RESPONSE"
    exit 1
fi

echo "✅ Case created: $ACME_CASE_ID"
echo ""

echo "→ Generating CAM for Acme Textiles..."
curl -s -X POST "$API_BASE/cases/$ACME_CASE_ID/generate-cam" > /dev/null
echo "✅ CAM generated"
echo ""

echo "→ Downloading CAM document..."
curl -s -o "$OUTPUT_DIR/CreditAppraisalMemo_AcmeTextiles.docx" \
  "http://localhost:8000/outputs/CreditAppraisalMemo_$ACME_CASE_ID.docx"
echo "✅ Saved to $OUTPUT_DIR/CreditAppraisalMemo_AcmeTextiles.docx"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Generate Surya Pharmaceuticals CAM (APPROVE case)
# ─────────────────────────────────────────────────────────────────────────────

echo "→ Creating case for Surya Pharmaceuticals Ltd (APPROVE case)..."
SURYA_RESPONSE=$(curl -s -X POST "$API_BASE/cases" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Surya Pharmaceuticals Ltd",
    "cin": "U24230KA2015PLC234567",
    "loan_amount": 30000000,
    "loan_purpose": "Working capital facility"
  }')

SURYA_CASE_ID=$(echo "$SURYA_RESPONSE" | grep -o '"case_id":"[^"]*"' | cut -d'"' -f4)

if [ -z "$SURYA_CASE_ID" ]; then
    echo "❌ Failed to create Surya Pharmaceuticals case"
    echo "   Response: $SURYA_RESPONSE"
    exit 1
fi

echo "✅ Case created: $SURYA_CASE_ID"
echo ""

echo "→ Generating CAM for Surya Pharmaceuticals..."
curl -s -X POST "$API_BASE/cases/$SURYA_CASE_ID/generate-cam" > /dev/null
echo "✅ CAM generated"
echo ""

echo "→ Downloading CAM document..."
curl -s -o "$OUTPUT_DIR/CreditAppraisalMemo_SuryaPharma.docx" \
  "http://localhost:8000/outputs/CreditAppraisalMemo_$SURYA_CASE_ID.docx"
echo "✅ Saved to $OUTPUT_DIR/CreditAppraisalMemo_SuryaPharma.docx"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

echo "════════════════════════════════════════════════════════════════════════"
echo "  ✅ Sample CAM documents generated successfully!"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "Files created:"
echo "  1. $OUTPUT_DIR/CreditAppraisalMemo_AcmeTextiles.docx (REJECT)"
echo "  2. $OUTPUT_DIR/CreditAppraisalMemo_SuryaPharma.docx (APPROVE)"
echo ""
echo "These files are ready for submission to judges."
echo ""
