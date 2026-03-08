"""
config.py
─────────────────────────────────────────────────────────────────────────────
Central configuration for Intelli-Credit.
Every threshold, weight, and constant lives here.
Loaded once at startup; never hardcoded elsewhere in the codebase.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


# ── Path constants (relative to this file) ────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DEMO_DIR  = DATA_DIR / "demo_company"
DEMO_DIR2 = DATA_DIR / "demo_company2"
LEXICON_PATH = DATA_DIR / "litigation_lexicon.json"
BENCHMARKS_PATH = DATA_DIR / "sector_benchmarks.json"
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
CAM_TEMPLATES_DIR = BASE_DIR / "cam" / "templates"
ML_MODELS_DIR = BASE_DIR.parent / "ml" / "models"

# Ensure runtime directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """
    All settings can be overridden via environment variables or a .env file.
    Naming convention: INTELLI_<SETTING_NAME> (e.g. INTELLI_LLM_MODEL).
    """

    model_config = {"env_prefix": "INTELLI_", "env_file": ".env", "extra": "ignore"}

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "Intelli-Credit"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/intelli_credit.db"

    # ── LLM ───────────────────────────────────────────────────────────────────
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.x.ai/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "grok-3")
    LLM_MAX_TOKENS: int = 1000
    LLM_TEMPERATURE: float = 0.3          # Low temperature for consistent banking tone

    # ── File Upload ───────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: set[str] = {"pdf", "csv", "xlsx", "xls", "xml", "json"}

    # ── OCR ───────────────────────────────────────────────────────────────────
    TESSERACT_CMD: str = "/usr/bin/tesseract"
    OCR_CONFIDENCE_THRESHOLD: float = 70.0    # Pages below this are flagged
    OCR_LANG: str = "eng"                     # Add +hin for Hindi support

    # ── Research Agent ────────────────────────────────────────────────────────
    RESEARCH_REQUEST_DELAY_SEC: float = 2.0   # Polite delay between scrape calls
    RESEARCH_CACHE_TTL_HOURS: int = 24
    NEWS_LOOKBACK_DAYS: int = 90
    USE_CACHED_RESEARCH: bool = True          # Always True during demo

    # ── GSTR Reconciliation Thresholds ────────────────────────────────────────
    GST_ITC_MISMATCH_PCT_THRESHOLD: float = 10.0    # Flag if >10% mismatch in any quarter
    GST_SUPPLIER_COMPLIANCE_WARN: float = 85.0      # Warn if supplier filing rate <85%
    GST_SUPPLIER_COMPLIANCE_HIGH: float = 70.0      # High risk if <70%
    GST_ITC_MAX_CLAIM_MULTIPLIER: float = 1.10      # 110% rule (CGST Act)
    GST_VS_BANK_VARIANCE_THRESHOLD: float = 0.85    # Flag if bank credits < 85% of GST turnover
    CIRCULAR_TRADING_MIN_AMOUNT_INR: float = 500_000.0   # Min cycle value to flag (₹5L)

    # ── Working Capital Thresholds ────────────────────────────────────────────
    DEBTOR_DAYS_HIGH_RISK: float = 120.0
    CREDITOR_DAYS_UNSUSTAINABLE: float = 180.0
    CASH_CONVERSION_CYCLE_WARN: float = 90.0
    RELATED_PARTY_REVENUE_PCT_HIGH: float = 30.0
    RELATED_PARTY_RECEIVABLES_PCT_HIGH: float = 25.0

    # ── Scoring Engine ────────────────────────────────────────────────────────
    # Maximum points per feature (must sum to 200)
    SCORE_WEIGHTS: dict[str, int] = {
        # CHARACTER (60 pts)
        "litigation_risk":        20,
        "promoter_track_record":  15,
        "gst_compliance":         10,
        "management_quality":     15,
        # CAPACITY (60 pts)
        "dscr":                   25,
        "ebitda_margin_trend":    15,
        "revenue_cagr_vs_sector": 10,
        "plant_utilization":      10,
        # CAPITAL (45 pts)
        "de_ratio":               20,
        "net_worth_trend":        15,
        "promoter_equity_pct":    10,
        # COLLATERAL (30 pts)
        "security_cover":         20,
        "collateral_encumbrance": 10,
        # CONDITIONS (35 pts)
        "sector_outlook":         15,
        "customer_concentration": 10,
        "regulatory_environment": 10,
    }
    SCORE_MAX: int = 200

    # Risk band thresholds (normalised 0-100)
    RISK_BANDS: dict[str, dict] = {
        "A_PLUS": {"min": 85, "max": 100, "grade": "A+",  "label": "Excellent",          "interest_premium_bps_min": 0,   "interest_premium_bps_max": 50},
        "A":      {"min": 70, "max": 84,  "grade": "A",   "label": "Strong",              "interest_premium_bps_min": 50,  "interest_premium_bps_max": 100},
        "B_PLUS": {"min": 55, "max": 69,  "grade": "B+",  "label": "Acceptable",          "interest_premium_bps_min": 100, "interest_premium_bps_max": 200},
        "B":      {"min": 45, "max": 54,  "grade": "B",   "label": "Marginal",            "interest_premium_bps_min": 200, "interest_premium_bps_max": 350},
        "C":      {"min": 35, "max": 44,  "grade": "C",   "label": "Watch",               "interest_premium_bps_min": 350, "interest_premium_bps_max": 500},
        "D":      {"min": 0,  "max": 34,  "grade": "D",   "label": "Decline",             "interest_premium_bps_min": 0,   "interest_premium_bps_max": 0},
    }

    # ── Loan Calculation ──────────────────────────────────────────────────────
    MIN_ACCEPTABLE_DSCR: float = 1.30             # Minimum DSCR for full approval
    DSCR_PARTIAL_APPROVAL_THRESHOLD: float = 1.10
    LTV_LAND: float = 0.60                         # Land LTV cap
    LTV_PLANT_MACHINERY: float = 0.50             # Plant & machinery LTV cap
    LTV_RECEIVABLES: float = 0.75                 # Receivables LTV cap (drawing power)
    DRAWING_POWER_MARGIN: float = 0.75            # Standard NBFC drawing power margin
    POLICY_MAX_SINGLE_BORROWER_CR: float = 100.0  # ₹100 Cr single borrower cap (mock)

    # ── Interest Rate ──────────────────────────────────────────────────────────
    RBI_REPO_RATE: float = 6.50                   # Update this at demo time
    NBFC_BASE_SPREAD: float = 2.50                # NBFC spread over repo
    LONG_TENOR_PREMIUM_BPS: int = 25              # Extra bps for tenor > 5 years
    STRONG_COLLATERAL_DISCOUNT_BPS: int = 25      # Discount for security cover > 2.0x
    STRONG_COLLATERAL_THRESHOLD: float = 2.0

    # ── Promoter Pledge Risk ──────────────────────────────────────────────────
    PROMOTER_PLEDGE_WARN_PCT: float = 50.0        # -20 pts
    PROMOTER_PLEDGE_HIGH_PCT: float = 75.0        # -35 pts + mandatory annotation

    # ── Audit ─────────────────────────────────────────────────────────────────
    AUDIT_HASH_ALGORITHM: str = "sha256"
    OVERRIDE_MAX_DELTA_WITHOUT_COUNTERSIGN: int = 15   # Points

    # ── Demo Company ──────────────────────────────────────────────────────────
    DEMO_COMPANY_NAME: str = "Acme Textiles Ltd"
    DEMO_COMPANY_CIN: str = "U17100MH2010PLC201234"
    DEMO_COMPANY_PAN: str = "AAACA1234B"


settings = Settings()