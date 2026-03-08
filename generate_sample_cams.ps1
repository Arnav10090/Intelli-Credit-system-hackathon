# ─────────────────────────────────────────────────────────────────────────────
# generate_sample_cams.ps1
# Helper script to generate sample CAM documents for both demo companies
# Windows PowerShell version
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

$API_BASE = "http://localhost:8000/api/v1"
$OUTPUT_DIR = "sample_outputs"

Write-Host "════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Intelli-Credit — Sample CAM Generator" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check if backend is running
Write-Host "→ Checking backend health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -Method Get
    Write-Host "✅ Backend is healthy" -ForegroundColor Green
} catch {
    Write-Host "❌ Backend is not running!" -ForegroundColor Red
    Write-Host "   Please start the backend first:" -ForegroundColor Red
    Write-Host "   cd backend && uvicorn main:app --reload --port 8000" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# Generate Acme Textiles CAM (REJECT case)
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "→ Creating case for Acme Textiles Ltd (REJECT case)..." -ForegroundColor Yellow
$acmeBody = @{
    company_name = "Acme Textiles Ltd"
    cin = "U17110MH2010PLC123456"
    loan_amount = 50000000
    loan_purpose = "Term loan for capacity expansion"
} | ConvertTo-Json

$acmeResponse = Invoke-RestMethod -Uri "$API_BASE/cases" -Method Post -Body $acmeBody -ContentType "application/json"
$acmeCaseId = $acmeResponse.case_id

if (-not $acmeCaseId) {
    Write-Host "❌ Failed to create Acme Textiles case" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Case created: $acmeCaseId" -ForegroundColor Green
Write-Host ""

Write-Host "→ Generating CAM for Acme Textiles..." -ForegroundColor Yellow
Invoke-RestMethod -Uri "$API_BASE/cases/$acmeCaseId/generate-cam" -Method Post | Out-Null
Write-Host "✅ CAM generated" -ForegroundColor Green
Write-Host ""

Write-Host "→ Downloading CAM document..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "http://localhost:8000/outputs/CreditAppraisalMemo_$acmeCaseId.docx" `
    -OutFile "$OUTPUT_DIR/CreditAppraisalMemo_AcmeTextiles.docx"
Write-Host "✅ Saved to $OUTPUT_DIR/CreditAppraisalMemo_AcmeTextiles.docx" -ForegroundColor Green
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# Generate Surya Pharmaceuticals CAM (APPROVE case)
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "→ Creating case for Surya Pharmaceuticals Ltd (APPROVE case)..." -ForegroundColor Yellow
$suryaBody = @{
    company_name = "Surya Pharmaceuticals Ltd"
    cin = "U24230KA2015PLC234567"
    loan_amount = 30000000
    loan_purpose = "Working capital facility"
} | ConvertTo-Json

$suryaResponse = Invoke-RestMethod -Uri "$API_BASE/cases" -Method Post -Body $suryaBody -ContentType "application/json"
$suryaCaseId = $suryaResponse.case_id

if (-not $suryaCaseId) {
    Write-Host "❌ Failed to create Surya Pharmaceuticals case" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Case created: $suryaCaseId" -ForegroundColor Green
Write-Host ""

Write-Host "→ Generating CAM for Surya Pharmaceuticals..." -ForegroundColor Yellow
Invoke-RestMethod -Uri "$API_BASE/cases/$suryaCaseId/generate-cam" -Method Post | Out-Null
Write-Host "✅ CAM generated" -ForegroundColor Green
Write-Host ""

Write-Host "→ Downloading CAM document..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "http://localhost:8000/outputs/CreditAppraisalMemo_$suryaCaseId.docx" `
    -OutFile "$OUTPUT_DIR/CreditAppraisalMemo_SuryaPharma.docx"
Write-Host "✅ Saved to $OUTPUT_DIR/CreditAppraisalMemo_SuryaPharma.docx" -ForegroundColor Green
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ Sample CAM documents generated successfully!" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files created:" -ForegroundColor White
Write-Host "  1. $OUTPUT_DIR/CreditAppraisalMemo_AcmeTextiles.docx (REJECT)" -ForegroundColor White
Write-Host "  2. $OUTPUT_DIR/CreditAppraisalMemo_SuryaPharma.docx (APPROVE)" -ForegroundColor White
Write-Host ""
Write-Host "These files are ready for submission to judges." -ForegroundColor Green
Write-Host ""
