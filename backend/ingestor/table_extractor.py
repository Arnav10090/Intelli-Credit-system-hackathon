"""
ingestor/table_extractor.py
─────────────────────────────────────────────────────────────────────────────
Financial table extraction from PDFs using pdfplumber.
Targets: P&L, Balance Sheet, Cash Flow, Key Ratios tables.

Strategy:
  1. pdfplumber detects table bounding boxes and cell content.
  2. Post-processing normalises Indian number formats (lakhs, crores, commas).
  3. Header detection maps columns to known financial line items.
  4. Output: structured dict ready for feature_engineer.py to consume.

LLM is NOT used. Pure rule-based table parsing.
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
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber not installed. Table extraction disabled.")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# ── Known financial line item aliases ─────────────────────────────────────────
# Maps messy PDF text → canonical field name used in feature_engineer.py

LINE_ITEM_MAP = {
    # Revenue
    "revenue from operations":     "revenue",
    "net revenue":                  "revenue",
    "turnover":                     "revenue",
    "gross revenue":                "revenue",
    "total income from operations": "revenue",

    # EBITDA / Operating Profit
    "ebitda":                       "ebitda",
    "operating profit":             "ebitda",
    "earnings before interest":     "ebitda",

    # Depreciation
    "depreciation":                 "depreciation",
    "depreciation and amortisation":"depreciation",
    "d&a":                          "depreciation",

    # EBIT
    "ebit":                         "ebit",
    "operating profit after dep":   "ebit",

    # Interest
    "finance costs":                "interest_expense",
    "interest expense":             "interest_expense",
    "interest and finance charges": "interest_expense",
    "finance charges":              "interest_expense",

    # PBT / PAT
    "profit before tax":            "pbt",
    "pbt":                          "pbt",
    "profit after tax":             "pat",
    "pat":                          "pat",
    "profit for the year":          "pat",
    "net profit":                   "pat",

    # Balance Sheet — Assets
    "total assets":                 "total_assets",
    "net fixed assets":             "net_fixed_assets",
    "gross block":                  "gross_fixed_assets",
    "trade receivables":            "trade_receivables",
    "debtors":                      "trade_receivables",
    "inventories":                  "inventory",
    "inventory":                    "inventory",
    "cash and cash equivalents":    "cash_and_bank",
    "cash and bank":                "cash_and_bank",
    "total current assets":         "total_current_assets",

    # Balance Sheet — Liabilities
    "share capital":                "share_capital",
    "reserves and surplus":         "reserves_and_surplus",
    "shareholders equity":          "tangible_net_worth",
    "net worth":                    "tangible_net_worth",
    "tangible net worth":           "tangible_net_worth",
    "total borrowings":             "total_debt",
    "total debt":                   "total_debt",
    "long term borrowings":         "long_term_borrowings",
    "short term borrowings":        "short_term_borrowings",
    "trade payables":               "trade_payables",
    "creditors":                    "trade_payables",
    "total current liabilities":    "total_current_liabilities",

    # Cash Flow
    "cash flow from operations":    "cfo",
    "net cash from operating":      "cfo",
    "capital expenditure":          "capex",
    "purchase of fixed assets":     "capex",
}

# Year patterns to identify columns
YEAR_PATTERN = re.compile(r"\b(FY\s*\d{2,4}|20\d{2}[-–]\d{2,4}|20\d{2})\b", re.IGNORECASE)

# Number normalisation: handles Indian format (1,00,000.00)
NUMBER_PATTERN = re.compile(r"^[₹Rs\.\s]*[-–]?\s*([\d,]+\.?\d*)\s*$")


@dataclass
class ExtractedTable:
    """A single extracted financial table."""
    table_type: str        # "pnl" | "balance_sheet" | "cash_flow" | "ratios" | "unknown"
    years: list[str]       # e.g. ["FY2022", "FY2023", "FY2024"]
    data: dict             # {canonical_field: {year: value}}
    raw_rows: list         # Original rows for audit
    page_num: int
    confidence: float      # 0-1 based on how many rows were successfully mapped


@dataclass
class TableExtractionResult:
    """All tables extracted from a PDF."""
    doc_id: str
    filename: str
    tables_found: int
    tables: list[ExtractedTable]
    merged_financials: dict   # Best attempt to merge all tables into one dict
    warnings: list[str] = field(default_factory=list)


def extract_tables(doc_id: str, file_path: str) -> TableExtractionResult:
    """
    Extract all financial tables from a PDF.
    Synchronous — called from pdf_parser or directly.
    """
    path = Path(file_path)
    logger.info("Extracting tables from: %s", path.name)

    if not PDFPLUMBER_AVAILABLE:
        return TableExtractionResult(
            doc_id=doc_id, filename=path.name,
            tables_found=0, tables=[], merged_financials={},
            warnings=["pdfplumber not installed"],
        )

    tables = []
    warnings = []

    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy":   "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance":       3,
                        "join_tolerance":       3,
                        "edge_min_length":      3,
                    }
                )

                if not page_tables:
                    # Try text-based fallback for borderless tables
                    page_tables = page.extract_tables(
                        table_settings={
                            "vertical_strategy":   "text",
                            "horizontal_strategy": "text",
                        }
                    )

                for raw_table in (page_tables or []):
                    if not raw_table or len(raw_table) < 3:
                        continue

                    extracted = _parse_table(raw_table, page_num)
                    if extracted:
                        tables.append(extracted)

    except Exception as e:
        logger.error("Table extraction failed for %s: %s", path.name, e)
        warnings.append(f"Table extraction error: {str(e)}")

    merged = _merge_tables(tables)

    logger.info("Tables extracted: %d from %s | merged fields: %d",
                len(tables), path.name, len(merged))

    return TableExtractionResult(
        doc_id=doc_id,
        filename=path.name,
        tables_found=len(tables),
        tables=tables,
        merged_financials=merged,
        warnings=warnings,
    )


def _parse_table(raw_table: list, page_num: int) -> Optional[ExtractedTable]:
    """
    Parse a raw pdfplumber table into a structured ExtractedTable.
    Returns None if the table doesn't look like a financial table.
    """
    if not raw_table:
        return None

    # Clean all cells
    cleaned = []
    for row in raw_table:
        cleaned.append([_clean_cell(cell) for cell in (row or [])])

    # Try to find header row with years
    years, header_row_idx = _find_year_row(cleaned)

    # If no year columns found, this might not be a financial table
    if len(years) < 1:
        # Still try to parse — some tables don't have year headers
        years = []
        header_row_idx = 0

    # Determine value column indices
    if years and header_row_idx >= 0:
        header_row = cleaned[header_row_idx]
        value_col_indices = []
        for i, cell in enumerate(header_row):
            if YEAR_PATTERN.search(cell) or (years and cell in years):
                value_col_indices.append(i)
    else:
        # Assume last N columns are values
        if len(cleaned[0]) >= 2:
            value_col_indices = list(range(1, len(cleaned[0])))
        else:
            return None

    # Parse data rows
    data = {}
    raw_rows = []
    mapped_count = 0

    data_start = header_row_idx + 1 if header_row_idx >= 0 else 0

    for row in cleaned[data_start:]:
        if not row or not row[0]:
            continue

        label_raw = row[0].lower().strip()
        canonical = _map_line_item(label_raw)

        values = {}
        for i, col_idx in enumerate(value_col_indices):
            if col_idx < len(row):
                num = _parse_number(row[col_idx])
                if num is not None:
                    year_key = years[i] if i < len(years) else f"col_{i+1}"
                    values[year_key] = num

        if values:
            raw_rows.append({"label": row[0], "values": values})
            if canonical:
                data[canonical] = values
                mapped_count += 1

    if not data and not raw_rows:
        return None

    # Classify table type
    table_type = _classify_table(data)

    # Confidence: ratio of mapped rows to total data rows
    total_rows = len(raw_rows)
    confidence = mapped_count / total_rows if total_rows > 0 else 0.0

    return ExtractedTable(
        table_type=table_type,
        years=years,
        data=data,
        raw_rows=raw_rows,
        page_num=page_num,
        confidence=round(confidence, 2),
    )


def _find_year_row(cleaned: list) -> tuple[list, int]:
    """Find the row containing year headers. Returns (years_list, row_index)."""
    for i, row in enumerate(cleaned[:5]):  # Check first 5 rows
        years = []
        for cell in row:
            match = YEAR_PATTERN.search(cell)
            if match:
                years.append(match.group(0).strip())
        if len(years) >= 1:
            return years, i
    return [], -1


def _map_line_item(label: str) -> Optional[str]:
    """Map a raw label string to a canonical field name."""
    label_clean = re.sub(r"\s+", " ", label.lower().strip())
    label_clean = re.sub(r"[()₹\*#]", "", label_clean).strip()

    # Direct match
    if label_clean in LINE_ITEM_MAP:
        return LINE_ITEM_MAP[label_clean]

    # Partial match
    for key, canonical in LINE_ITEM_MAP.items():
        if key in label_clean or label_clean in key:
            return canonical

    return None


def _classify_table(data: dict) -> str:
    """Classify table type based on which fields are present."""
    pnl_fields = {"revenue", "ebitda", "pat", "pbt", "interest_expense"}
    bs_fields   = {"total_assets", "total_debt", "tangible_net_worth",
                   "trade_receivables", "inventory"}
    cf_fields   = {"cfo", "capex"}

    if len(data.keys() & pnl_fields) >= 2:
        return "pnl"
    if len(data.keys() & bs_fields) >= 2:
        return "balance_sheet"
    if len(data.keys() & cf_fields) >= 1:
        return "cash_flow"
    return "unknown"


def _merge_tables(tables: list[ExtractedTable]) -> dict:
    """
    Merge all extracted tables into a single unified financial data dict.
    Later tables of the same type override earlier ones (usually more complete).
    Format: {field_name: {year: value}}
    """
    merged = {}
    for table in sorted(tables, key=lambda t: t.confidence):
        for field_name, year_values in table.data.items():
            if field_name not in merged:
                merged[field_name] = {}
            merged[field_name].update(year_values)
    return merged


def _clean_cell(cell) -> str:
    """Clean a raw pdfplumber cell value."""
    if cell is None:
        return ""
    text = str(cell).strip()
    # Remove extra whitespace and newlines
    text = re.sub(r"\s+", " ", text)
    return text


def _parse_number(cell: str) -> Optional[float]:
    """
    Parse an Indian-format number from a cell string.
    Handles: 1,00,000 / 1,00,000.00 / (1,00,000) [negative] / - [nil]
    """
    if not cell or cell.strip() in ("", "-", "–", "nil", "N/A", "na"):
        return None

    text = cell.strip()

    # Check for negative (brackets or minus)
    is_negative = text.startswith("(") and text.endswith(")")
    if is_negative:
        text = text[1:-1]

    # Remove currency symbols and spaces
    text = re.sub(r"[₹Rs\.\s]", "", text)
    text = text.replace(",", "")

    try:
        value = float(text)
        return -value if is_negative else value
    except ValueError:
        return None


def result_to_dict(result: TableExtractionResult) -> dict:
    """Serialise TableExtractionResult for API / database storage."""
    return {
        "doc_id": result.doc_id,
        "filename": result.filename,
        "tables_found": result.tables_found,
        "merged_financials": result.merged_financials,
        "warnings": result.warnings,
        "tables_summary": [
            {
                "table_type": t.table_type,
                "page_num": t.page_num,
                "years": t.years,
                "fields_mapped": list(t.data.keys()),
                "confidence": t.confidence,
            }
            for t in result.tables
        ],
    }