"""
ingestor/bank_parser.py
─────────────────────────────────────────────────────────────────────────────
Parses bank statement CSV/XLSX files for Intelli-Credit.

Outputs per month:
  - Total credits (inflows)
  - Total debits (outflows)
  - Adjusted credits (excluding contra entries, loan drawdowns, FD maturities)
  - Closing balance
  - Monthly credit vs GST turnover (for reconciliation)

Contra entry detection: large round-number same-day credit+debit pairs.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not installed. Bank statement parsing disabled.")


# ── Column name aliases across different bank formats ─────────────────────────
DATE_ALIASES    = ["date", "txn date", "transaction date", "value date",
                   "posting date", "trans date"]
DEBIT_ALIASES   = ["debit", "debit amount", "withdrawal", "withdrawal amt",
                   "dr", "dr amount", "amount(dr)"]
CREDIT_ALIASES  = ["credit", "credit amount", "deposit", "deposit amt",
                   "cr", "cr amount", "amount(cr)"]
BALANCE_ALIASES = ["balance", "closing balance", "running balance",
                   "available balance", "ledger balance"]
NARRATION_ALIASES = ["narration", "description", "particulars", "remarks",
                     "transaction remarks", "cheque / ref no"]

# Patterns in narration that indicate NON-OPERATING credits (exclude from revenue)
EXCLUDE_NARRATION_PATTERNS = [
    r"\bterm loan\b", r"\btl disbursement\b", r"\bloan disbursed\b",
    r"\bfd maturity\b", r"\bfixed deposit\b", r"\bfd proceeds\b",
    r"\binter.?bank transfer\b", r"\bneft from own\b", r"\bimps from own\b",
    r"\bself transfer\b", r"\bown account\b",
    r"\bcapital infusion\b", r"\bshare capital\b",
    r"\brefund\b",
]

# Patterns indicating SALARY / WAGES outflows (for employee cost validation)
SALARY_PATTERNS = [r"\bsalary\b", r"\bwages\b", r"\bpayroll\b", r"\bstaff\b"]


@dataclass
class MonthlyBankSummary:
    """Bank account summary for one calendar month."""
    month: str                  # "YYYY-MM" format
    total_credits: float
    total_debits: float
    adjusted_credits: float     # Excluding non-operating credits
    excluded_credits: float     # Amount excluded (loans, FDs, etc.)
    salary_outflow: float
    closing_balance: float
    transaction_count: int
    contra_entries_detected: int
    contra_amount: float


@dataclass
class BankParseResult:
    """Full bank statement parse result."""
    doc_id: str
    filename: str
    account_number: Optional[str]
    bank_name: Optional[str]
    period_from: Optional[str]
    period_to: Optional[str]
    monthly_summaries: list[MonthlyBankSummary]
    total_credits_annual: float
    total_adjusted_credits_annual: float
    avg_monthly_credits: float
    avg_closing_balance: float
    warnings: list[str] = field(default_factory=list)


async def parse_bank_statement(doc_id: str, file_path: str) -> BankParseResult:
    """
    Main entry point. Parses a bank statement CSV or XLSX file.
    Called as a background task from ingest_routes.py.
    """
    path = Path(file_path)
    logger.info("Parsing bank statement: %s (doc_id=%s)", path.name, doc_id)

    if not PANDAS_AVAILABLE:
        return _empty_result(doc_id, path.name, "pandas not installed")

    try:
        df = _load_file(path)
    except Exception as e:
        return _empty_result(doc_id, path.name, str(e))

    # Standardise column names
    df, warnings = _standardise_columns(df)
    if df is None:
        return _empty_result(doc_id, path.name,
                             "Could not identify required columns (Date/Credit/Debit)")

    # Parse dates
    df = _parse_dates(df)
    df = df.dropna(subset=["_date"])

    if df.empty:
        return _empty_result(doc_id, path.name, "No valid date rows found")

    # Fill NaN amounts with 0
    df["_credit"] = pd.to_numeric(df["_credit"], errors="coerce").fillna(0.0)
    df["_debit"]  = pd.to_numeric(df["_debit"],  errors="coerce").fillna(0.0)
    df["_balance"]= pd.to_numeric(df.get("_balance", pd.Series([0.0]*len(df))),
                                   errors="coerce").fillna(0.0)

    # Detect and flag non-operating credits
    df["_is_excluded"] = df.apply(_is_excluded_credit, axis=1)
    df["_is_salary"]   = df.apply(_is_salary_debit, axis=1)
    df["_is_contra"]   = _detect_contra_entries(df)

    # Group by month
    df["_month"] = df["_date"].dt.to_period("M").astype(str)
    monthly = _compute_monthly_summaries(df)

    # Account-level metadata
    account_number = _extract_account_number(df)
    bank_name      = _detect_bank_name(path.name, df)
    period_from    = str(df["_date"].min().date()) if not df.empty else None
    period_to      = str(df["_date"].max().date()) if not df.empty else None

    total_credits  = sum(m.total_credits for m in monthly)
    total_adj      = sum(m.adjusted_credits for m in monthly)
    avg_monthly    = total_adj / len(monthly) if monthly else 0.0
    avg_balance    = (sum(m.closing_balance for m in monthly) / len(monthly)
                      if monthly else 0.0)

    result = BankParseResult(
        doc_id=doc_id,
        filename=path.name,
        account_number=account_number,
        bank_name=bank_name,
        period_from=period_from,
        period_to=period_to,
        monthly_summaries=monthly,
        total_credits_annual=round(total_credits, 2),
        total_adjusted_credits_annual=round(total_adj, 2),
        avg_monthly_credits=round(avg_monthly, 2),
        avg_closing_balance=round(avg_balance, 2),
        warnings=warnings,
    )

    logger.info(
        "Bank parsed: %s | months=%d | total_credits=%.2f | adj_credits=%.2f",
        path.name, len(monthly), total_credits, total_adj
    )
    return result


# ── File Loading ──────────────────────────────────────────────────────────────

def _load_file(path: Path) -> "pd.DataFrame":
    """Load CSV or XLSX into a DataFrame, trying multiple encodings."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(str(path), header=None)
    # CSV: try UTF-8 then latin-1
    try:
        return pd.read_csv(str(path), header=None, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(str(path), header=None, encoding="latin-1")


def _standardise_columns(df: "pd.DataFrame") -> tuple:
    """
    Find the header row and map columns to standard names.
    Returns (standardised_df, warnings) or (None, warnings) on failure.
    """
    warnings = []
    # Find header row (first row where cells look like column headers)
    header_row_idx = 0
    for i, row in df.iterrows():
        row_lower = [str(v).lower().strip() for v in row.values]
        if any(alias in row_lower for alias in DATE_ALIASES):
            header_row_idx = i
            break

    # Set header
    df.columns = [str(v).lower().strip() for v in df.iloc[header_row_idx].values]
    df = df.iloc[header_row_idx + 1:].reset_index(drop=True)

    # Map to standard names
    col_map = {}
    for col in df.columns:
        if col in DATE_ALIASES:
            col_map[col] = "_date"
        elif col in CREDIT_ALIASES:
            col_map[col] = "_credit"
        elif col in DEBIT_ALIASES:
            col_map[col] = "_debit"
        elif col in BALANCE_ALIASES:
            col_map[col] = "_balance"
        elif col in NARRATION_ALIASES:
            col_map[col] = "_narration"

    df = df.rename(columns=col_map)

    # Check required columns
    if "_date" not in df.columns:
        warnings.append("Could not identify date column")
        return None, warnings
    if "_credit" not in df.columns and "_debit" not in df.columns:
        # Some banks use a single "amount" column with Dr/Cr indicator
        df, w = _handle_single_amount_column(df)
        warnings.extend(w)

    # Ensure credit/debit columns exist
    for col in ["_credit", "_debit", "_balance"]:
        if col not in df.columns:
            df[col] = 0.0

    if "_narration" not in df.columns:
        df["_narration"] = ""

    return df, warnings


def _handle_single_amount_column(df: "pd.DataFrame") -> tuple:
    """Handle bank statements with a single Amount + Dr/Cr indicator column."""
    warnings = ["Single amount column format detected"]
    amount_cols = [c for c in df.columns if "amount" in c]
    type_cols   = [c for c in df.columns if any(k in c for k in ["type", "dr/cr", "txn type"])]

    if amount_cols and type_cols:
        df["_credit"] = df.apply(
            lambda r: float(str(r[amount_cols[0]]).replace(",", "") or 0)
            if "cr" in str(r[type_cols[0]]).lower() else 0.0, axis=1
        )
        df["_debit"]  = df.apply(
            lambda r: float(str(r[amount_cols[0]]).replace(",", "") or 0)
            if "dr" in str(r[type_cols[0]]).lower() else 0.0, axis=1
        )
    else:
        df["_credit"] = 0.0
        df["_debit"]  = 0.0

    return df, warnings


def _parse_dates(df: "pd.DataFrame") -> "pd.DataFrame":
    """Parse date column to datetime, trying multiple formats."""
    date_formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y",
        "%d-%b-%Y", "%d/%b/%Y", "%d.%m.%Y", "%m/%d/%Y",
    ]
    for fmt in date_formats:
        try:
            df["_date"] = pd.to_datetime(df["_date"], format=fmt, errors="coerce")
            if df["_date"].notna().sum() > len(df) * 0.5:
                return df
        except Exception:
            continue
    df["_date"] = pd.to_datetime(df["_date"], infer_datetime_format=True, errors="coerce")
    return df


# ── Exclusion & Detection Logic ───────────────────────────────────────────────

def _is_excluded_credit(row) -> bool:
    """Return True if this credit entry should be excluded from operating revenue."""
    narration = str(row.get("_narration", "")).lower()
    credit    = float(row.get("_credit", 0) or 0)
    if credit <= 0:
        return False
    return any(re.search(p, narration) for p in EXCLUDE_NARRATION_PATTERNS)


def _is_salary_debit(row) -> bool:
    """Return True if this debit is a salary/wages payment."""
    narration = str(row.get("_narration", "")).lower()
    debit     = float(row.get("_debit", 0) or 0)
    if debit <= 0:
        return False
    return any(re.search(p, narration) for p in SALARY_PATTERNS)


def _detect_contra_entries(df: "pd.DataFrame") -> "pd.Series":
    """
    Detect contra entries: same-day credit+debit of same amount.
    Returns a boolean Series.
    """
    contra = pd.Series(False, index=df.index)
    try:
        grouped = df.groupby(["_date", "_credit"])
        for (date, amount), group in grouped:
            if amount <= 0:
                continue
            debit_matches = df[
                (df["_date"] == date) &
                (df["_debit"] == amount)
            ]
            if not debit_matches.empty:
                contra[group.index] = True
    except Exception:
        pass
    return contra


def _compute_monthly_summaries(df: "pd.DataFrame") -> list[MonthlyBankSummary]:
    """Aggregate transactions by month into MonthlyBankSummary objects."""
    summaries = []

    for month, group in df.groupby("_month"):
        total_credits  = group["_credit"].sum()
        total_debits   = group["_debit"].sum()
        excl_credits   = group.loc[group["_is_excluded"], "_credit"].sum()
        adj_credits    = total_credits - excl_credits
        salary_out     = group.loc[group["_is_salary"], "_debit"].sum()
        contra_count   = int(group["_is_contra"].sum())
        contra_amount  = group.loc[group["_is_contra"], "_credit"].sum()
        closing_bal    = (group["_balance"].iloc[-1]
                          if "_balance" in group.columns and not group.empty
                          else 0.0)

        summaries.append(MonthlyBankSummary(
            month=str(month),
            total_credits=round(float(total_credits), 2),
            total_debits=round(float(total_debits), 2),
            adjusted_credits=round(float(adj_credits), 2),
            excluded_credits=round(float(excl_credits), 2),
            salary_outflow=round(float(salary_out), 2),
            closing_balance=round(float(closing_bal), 2),
            transaction_count=len(group),
            contra_entries_detected=contra_count,
            contra_amount=round(float(contra_amount), 2),
        ))

    return sorted(summaries, key=lambda m: m.month)


# ── Metadata Extraction ───────────────────────────────────────────────────────

def _extract_account_number(df: "pd.DataFrame") -> Optional[str]:
    """Try to find account number in narration column."""
    if "_narration" not in df.columns:
        return None
    for narr in df["_narration"].head(20).astype(str):
        match = re.search(r"\b(\d{9,18})\b", narr)
        if match:
            return match.group(1)
    return None


def _detect_bank_name(filename: str, df: "pd.DataFrame") -> Optional[str]:
    """Detect bank name from filename."""
    banks = {
        "sbi": "State Bank of India",
        "hdfc": "HDFC Bank",
        "icici": "ICICI Bank",
        "axis": "Axis Bank",
        "kotak": "Kotak Mahindra Bank",
        "pnb": "Punjab National Bank",
        "bob": "Bank of Baroda",
        "idbi": "IDBI Bank",
        "yes": "Yes Bank",
        "indusind": "IndusInd Bank",
    }
    name_lower = filename.lower()
    for key, full_name in banks.items():
        if key in name_lower:
            return full_name
    return None


def _empty_result(doc_id: str, filename: str, error: str) -> BankParseResult:
    return BankParseResult(
        doc_id=doc_id, filename=filename, account_number=None,
        bank_name=None, period_from=None, period_to=None,
        monthly_summaries=[], total_credits_annual=0.0,
        total_adjusted_credits_annual=0.0, avg_monthly_credits=0.0,
        avg_closing_balance=0.0, warnings=[error],
    )


def result_to_dict(result: BankParseResult) -> dict:
    return {
        "doc_id": result.doc_id,
        "filename": result.filename,
        "account_number": result.account_number,
        "bank_name": result.bank_name,
        "period_from": result.period_from,
        "period_to": result.period_to,
        "total_credits_annual": result.total_credits_annual,
        "total_adjusted_credits_annual": result.total_adjusted_credits_annual,
        "avg_monthly_credits": result.avg_monthly_credits,
        "avg_closing_balance": result.avg_closing_balance,
        "monthly_summaries": [
            {
                "month": m.month,
                "total_credits": m.total_credits,
                "adjusted_credits": m.adjusted_credits,
                "excluded_credits": m.excluded_credits,
                "total_debits": m.total_debits,
                "salary_outflow": m.salary_outflow,
                "closing_balance": m.closing_balance,
                "transaction_count": m.transaction_count,
                "contra_entries_detected": m.contra_entries_detected,
                "contra_amount": m.contra_amount,
            }
            for m in result.monthly_summaries
        ],
        "warnings": result.warnings,
    }