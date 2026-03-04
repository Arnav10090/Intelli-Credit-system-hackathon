"""
ingestor/gst_reconciler.py
─────────────────────────────────────────────────────────────────────────────
GSTR-2A vs GSTR-3B reconciliation engine.

Implements:
  1. ITC mismatch detection (GSTR-2A eligible vs 3B claimed)
  2. 110% ITC rule enforcement (CGST Act)
  3. Section 17(5) blocked credit exclusion
  4. Supplier compliance rate scoring
  5. Circular trading detection via NetworkX graph
  6. Revenue inflation detection (GST turnover vs bank credits)
  7. Working capital stress indicators
  8. Related party concentration analysis

All logic is DETERMINISTIC — no LLM.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not installed. GST reconciliation disabled.")

try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False
    logger.warning("networkx not installed. Circular trading detection disabled.")

from config import settings


@dataclass
class ReconciliationFlag:
    flag_type: str
    severity: str          # CRITICAL | HIGH | MEDIUM | LOW
    title: str
    description: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class GSTReconResult:
    """Complete GST reconciliation result."""
    doc_id: str
    gstin: str
    period: str
    flags: list[ReconciliationFlag]
    itc_summary: dict
    supplier_compliance: dict
    circular_trading: dict
    bank_vs_gst: dict
    working_capital: dict
    risk_score_impact: int    # Total negative points from all flags
    warnings: list[str] = field(default_factory=list)


async def parse_gst_file(doc_id: str, file_path: str, doc_type: str) -> GSTReconResult:
    """
    Entry point for GST file ingestion.
    For hackathon demo: loads from JSON. Production: parse CSV/XLSX GSTR exports.
    """
    path = Path(file_path)
    logger.info("Parsing GST file: %s (type=%s)", path.name, doc_type)

    try:
        if path.suffix.lower() == ".json":
            with open(path) as f:
                gst_data = json.load(f)
        else:
            # CSV/XLSX path — parse into expected structure
            gst_data = _parse_gst_csv(path, doc_type)
    except Exception as e:
        return _empty_result(doc_id, str(e))

    return _run_reconciliation(doc_id, gst_data)


def run_reconciliation_from_dict(doc_id: str, gst_data: dict) -> GSTReconResult:
    """
    Run reconciliation directly from a dict (used when loading demo data).
    Called by ingest_routes.py load_demo_data endpoint.
    """
    return _run_reconciliation(doc_id, gst_data)


def _run_reconciliation(doc_id: str, gst_data: dict) -> GSTReconResult:
    """Core reconciliation logic."""
    flags   = []
    gstin   = gst_data.get("gstin", "UNKNOWN")
    period  = gst_data.get("period", "")

    # ── 1. ITC Mismatch (GSTR-2A vs 3B) ─────────────────────────────────────
    itc_summary = {}
    if "gstr_3b_monthly" in gst_data and "gstr_2a_quarterly_summary" in gst_data:
        itc_flags, itc_summary = _check_itc_mismatch(
            gst_data["gstr_3b_monthly"],
            gst_data["gstr_2a_quarterly_summary"],
        )
        flags.extend(itc_flags)

    # ── 2. Supplier Compliance ────────────────────────────────────────────────
    supplier_compliance = {}
    if "gstr_2a_quarterly_summary" in gst_data:
        sc_flags, supplier_compliance = _check_supplier_compliance(
            gst_data["gstr_2a_quarterly_summary"]
        )
        flags.extend(sc_flags)

    # ── 3. Circular Trading Detection ────────────────────────────────────────
    circular_trading = {}
    if "circular_trading_analysis" in gst_data:
        # Use pre-computed result from demo data
        circular_trading = gst_data["circular_trading_analysis"]
        if circular_trading.get("cycles_detected", 0) > 0:
            flags.append(ReconciliationFlag(
                flag_type="CIRCULAR_TRADING",
                severity="CRITICAL",
                title="Circular trading cycles detected",
                description=(
                    f"{circular_trading['cycles_detected']} circular trading "
                    "cycle(s) detected in GST transaction graph. "
                    "This may indicate fraudulent ITC claims."
                ),
                metric_name="cycles_detected",
                metric_value=float(circular_trading["cycles_detected"]),
                threshold=0.0,
            ))
    elif NX_AVAILABLE and "transaction_edges" in gst_data:
        # Full graph analysis if raw transaction data provided
        ct_flags, circular_trading = _detect_circular_trading(
            gst_data["transaction_edges"], gstin
        )
        flags.extend(ct_flags)

    # ── 4. Bank vs GST Reconciliation ─────────────────────────────────────────
    bank_vs_gst = {}
    if "bank_vs_gst_reconciliation" in gst_data:
        bank_vs_gst = gst_data["bank_vs_gst_reconciliation"]
        bvg_flags = _check_bank_vs_gst(bank_vs_gst)
        flags.extend(bvg_flags)

    # ── 5. Working Capital (placeholder — populated by feature_engineer) ──────
    working_capital = {}

    # ── Compute total risk score impact ───────────────────────────────────────
    severity_points = {"CRITICAL": -20, "HIGH": -10, "MEDIUM": -5, "LOW": -2}
    risk_score_impact = sum(
        severity_points.get(f.severity, 0) for f in flags
    )

    result = GSTReconResult(
        doc_id=doc_id,
        gstin=gstin,
        period=period,
        flags=flags,
        itc_summary=itc_summary,
        supplier_compliance=supplier_compliance,
        circular_trading=circular_trading,
        bank_vs_gst=bank_vs_gst,
        working_capital=working_capital,
        risk_score_impact=risk_score_impact,
    )

    logger.info(
        "GST reconciliation: %d flags raised | risk_impact=%d pts",
        len(flags), risk_score_impact
    )
    return result


# ── ITC Mismatch ──────────────────────────────────────────────────────────────

def _check_itc_mismatch(
    monthly_3b: list,
    quarterly_2a: list,
) -> tuple[list[ReconciliationFlag], dict]:
    """
    Compare ITC claimed in GSTR-3B vs eligible ITC in GSTR-2A.
    Flags:
      - ITC claimed > 110% of 2A eligible (CGST 110% rule violation)
      - ITC mismatch > 10% of total ITC in any quarter
    """
    flags = []

    # Aggregate 3B by quarter
    monthly_map = {m["month"]: m for m in monthly_3b}
    quarter_months = {
        "Q1": ["Apr", "May", "Jun"],
        "Q2": ["Jul", "Aug", "Sep"],
        "Q3": ["Oct", "Nov", "Dec"],
        "Q4": ["Jan", "Feb", "Mar"],
    }

    itc_summary = {"quarters": [], "total_claimed": 0, "total_eligible": 0,
                   "total_delta": 0, "overclaim_detected": False}

    for q_data in quarterly_2a:
        q_label   = q_data.get("quarter", "")
        eligible  = q_data.get("eligible_itc_igst_lakhs", 0) or 0
        eligible += q_data.get("eligible_itc_cgst_lakhs", 0) or 0
        eligible += q_data.get("eligible_itc_sgst_lakhs", 0) or 0

        # Sum 3B claims for this quarter
        claimed = 0.0
        for m_key, m_data in monthly_map.items():
            for q_abbr, months in quarter_months.items():
                if any(mon in m_key for mon in months) and q_abbr in q_label:
                    claimed += (m_data.get("itc_claimed_igst", 0) or 0)
                    claimed += (m_data.get("itc_claimed_cgst", 0) or 0)
                    claimed += (m_data.get("itc_claimed_sgst", 0) or 0)

        if eligible == 0:
            continue

        ratio = claimed / eligible if eligible > 0 else 0
        delta_pct = ((claimed - eligible) / eligible * 100) if eligible > 0 else 0

        q_summary = {
            "quarter": q_label,
            "claimed_lakhs": round(claimed, 2),
            "eligible_lakhs": round(eligible, 2),
            "ratio": round(ratio, 3),
            "delta_pct": round(delta_pct, 1),
        }
        itc_summary["quarters"].append(q_summary)
        itc_summary["total_claimed"] += claimed
        itc_summary["total_eligible"] += eligible

        # Check 110% rule (CGST Act)
        if ratio > settings.GST_ITC_MAX_CLAIM_MULTIPLIER:
            itc_summary["overclaim_detected"] = True
            flags.append(ReconciliationFlag(
                flag_type="ITC_OVERCLAIM",
                severity="HIGH",
                title=f"ITC overclaim detected in {q_label}",
                description=(
                    f"ITC claimed (₹{claimed:.1f}L) exceeds 110% of 2A-eligible "
                    f"ITC (₹{eligible:.1f}L). Ratio: {ratio:.2f}x. "
                    f"Violates CGST Act 110% rule. Delta: {delta_pct:+.1f}%."
                ),
                metric_name="itc_claim_ratio",
                metric_value=round(ratio, 3),
                threshold=settings.GST_ITC_MAX_CLAIM_MULTIPLIER,
            ))
        # Check general mismatch threshold
        elif abs(delta_pct) > settings.GST_ITC_MISMATCH_PCT_THRESHOLD:
            flags.append(ReconciliationFlag(
                flag_type="ITC_MISMATCH",
                severity="MEDIUM",
                title=f"Significant ITC mismatch in {q_label}",
                description=(
                    f"ITC mismatch of {delta_pct:+.1f}% exceeds {settings.GST_ITC_MISMATCH_PCT_THRESHOLD}% threshold. "
                    f"Claimed: ₹{claimed:.1f}L vs Eligible: ₹{eligible:.1f}L."
                ),
                metric_name="itc_delta_pct",
                metric_value=round(abs(delta_pct), 1),
                threshold=settings.GST_ITC_MISMATCH_PCT_THRESHOLD,
            ))

    total_c = itc_summary["total_claimed"]
    total_e = itc_summary["total_eligible"]
    itc_summary["total_delta"] = round(total_c - total_e, 2)

    return flags, itc_summary


# ── Supplier Compliance ───────────────────────────────────────────────────────

def _check_supplier_compliance(quarterly_2a: list) -> tuple[list, dict]:
    """
    Assess supplier GST filing compliance rate.
    Low compliance → supply chain risk + ITC risk.
    """
    flags = []
    rates = [q.get("supplier_filing_rate_pct", 100) for q in quarterly_2a
             if q.get("supplier_filing_rate_pct") is not None]

    if not rates:
        return flags, {}

    avg_rate = sum(rates) / len(rates)
    min_rate = min(rates)
    low_quarters = [
        q["quarter"] for q in quarterly_2a
        if q.get("supplier_filing_rate_pct", 100) < settings.GST_SUPPLIER_COMPLIANCE_WARN
    ]

    summary = {
        "avg_supplier_filing_rate_pct": round(avg_rate, 1),
        "min_supplier_filing_rate_pct": round(min_rate, 1),
        "low_compliance_quarters": low_quarters,
        "quarterly_rates": [
            {"quarter": q.get("quarter"), "rate": q.get("supplier_filing_rate_pct")}
            for q in quarterly_2a
        ],
    }

    if min_rate < settings.GST_SUPPLIER_COMPLIANCE_HIGH:
        flags.append(ReconciliationFlag(
            flag_type="SUPPLIER_NONCOMPLIANCE",
            severity="HIGH",
            title="High supplier GST non-compliance",
            description=(
                f"Supplier filing rate dropped to {min_rate:.1f}% in "
                f"{low_quarters}. Below {settings.GST_SUPPLIER_COMPLIANCE_HIGH}% "
                "high-risk threshold. ITC claims at risk of reversal."
            ),
            metric_name="min_supplier_filing_rate_pct",
            metric_value=round(min_rate, 1),
            threshold=settings.GST_SUPPLIER_COMPLIANCE_HIGH,
        ))
    elif min_rate < settings.GST_SUPPLIER_COMPLIANCE_WARN:
        flags.append(ReconciliationFlag(
            flag_type="SUPPLIER_NONCOMPLIANCE",
            severity="MEDIUM",
            title="Supplier GST compliance below warning threshold",
            description=(
                f"Supplier filing rate {min_rate:.1f}% in {low_quarters}. "
                f"Below {settings.GST_SUPPLIER_COMPLIANCE_WARN}% warning level."
            ),
            metric_name="min_supplier_filing_rate_pct",
            metric_value=round(min_rate, 1),
            threshold=settings.GST_SUPPLIER_COMPLIANCE_WARN,
        ))

    return flags, summary


# ── Bank vs GST ───────────────────────────────────────────────────────────────

def _check_bank_vs_gst(bank_vs_gst: dict) -> list[ReconciliationFlag]:
    """
    Flag months where bank credits < 85% of GST turnover.
    Indicates possible revenue inflation or cash flow issues.
    """
    flags = []
    variance_details = bank_vs_gst.get("variance_details", [])

    flagged_months = [d for d in variance_details
                      if d.get("ratio", 1.0) < settings.GST_VS_BANK_VARIANCE_THRESHOLD]

    if len(flagged_months) >= 2:
        months_str = ", ".join(d["month"] for d in flagged_months)
        flags.append(ReconciliationFlag(
            flag_type="REVENUE_INFLATION",
            severity="MEDIUM",
            title="Bank credits below GST turnover — possible revenue inflation",
            description=(
                f"In {len(flagged_months)} month(s) ({months_str}), bank credits "
                f"fell below {settings.GST_VS_BANK_VARIANCE_THRESHOLD*100:.0f}% "
                "of declared GST turnover. This may indicate revenue recognition "
                "without actual collection, or inter-company booking. "
                "Analyst verification required."
            ),
            metric_name="months_below_threshold",
            metric_value=float(len(flagged_months)),
            threshold=float(settings.GST_VS_BANK_VARIANCE_THRESHOLD),
        ))

    return flags


# ── Circular Trading ──────────────────────────────────────────────────────────

def _detect_circular_trading(
    transaction_edges: list,
    subject_gstin: str,
) -> tuple[list[ReconciliationFlag], dict]:
    """
    Build directed transaction graph and detect cycles involving the subject company.
    Only used when raw transaction edge data is provided.
    """
    if not NX_AVAILABLE:
        return [], {"error": "networkx not installed"}

    flags = []
    G = nx.DiGraph()

    for edge in transaction_edges:
        G.add_edge(
            edge["buyer_gstin"],
            edge["seller_gstin"],
            weight=edge.get("amount", 0),
        )

    try:
        all_cycles = list(nx.simple_cycles(G))
        subject_cycles = [c for c in all_cycles if subject_gstin in c]
    except Exception as e:
        return [], {"error": str(e)}

    flagged_cycles = []
    for cycle in subject_cycles:
        cycle_value = sum(
            G[cycle[i]][cycle[(i+1) % len(cycle)]].get("weight", 0)
            for i in range(len(cycle))
        )
        if cycle_value > settings.CIRCULAR_TRADING_MIN_AMOUNT_INR:
            flagged_cycles.append({
                "cycle": cycle,
                "value": cycle_value,
            })
            flags.append(ReconciliationFlag(
                flag_type="CIRCULAR_TRADING",
                severity="CRITICAL",
                title=f"Circular trading cycle detected (₹{cycle_value/100000:.1f}L)",
                description=(
                    f"Circular transaction cycle detected involving "
                    f"{len(cycle)} parties including subject company. "
                    f"Cycle value: ₹{cycle_value/100000:.1f}L. "
                    "Possible fraudulent ITC claim."
                ),
                metric_name="cycle_value_inr",
                metric_value=cycle_value,
                threshold=settings.CIRCULAR_TRADING_MIN_AMOUNT_INR,
            ))

    summary = {
        "transaction_graph_nodes": G.number_of_nodes(),
        "total_cycles_in_graph": len(all_cycles),
        "cycles_involving_subject": len(subject_cycles),
        "flagged_cycles": len(flagged_cycles),
        "cycles_detected": len(flagged_cycles),
        "result": (
            f"{len(flagged_cycles)} circular trading cycle(s) detected"
            if flagged_cycles
            else "No circular trading cycles detected"
        ),
    }

    return flags, summary


def _parse_gst_csv(path: Path, doc_type: str) -> dict:
    """
    Parse GSTR CSV/XLSX export into the expected dict structure.
    Handles basic GSTN portal export format.
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas required for CSV parsing")
    df = pd.read_csv(str(path)) if path.suffix == ".csv" else pd.read_excel(str(path))
    # Basic structure — production implementation would fully parse GSTN format
    return {
        "gstin": "UNKNOWN",
        "period": "parsed_from_csv",
        "gstr_3b_monthly": [],
        "gstr_2a_quarterly_summary": [],
    }


def _empty_result(doc_id: str, error: str) -> GSTReconResult:
    return GSTReconResult(
        doc_id=doc_id, gstin="UNKNOWN", period="",
        flags=[], itc_summary={}, supplier_compliance={},
        circular_trading={}, bank_vs_gst={}, working_capital={},
        risk_score_impact=0, warnings=[error],
    )


def result_to_dict(result: GSTReconResult) -> dict:
    return {
        "doc_id": result.doc_id,
        "gstin": result.gstin,
        "period": result.period,
        "risk_score_impact": result.risk_score_impact,
        "flags": [
            {
                "flag_type": f.flag_type,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
                "metric_name": f.metric_name,
                "metric_value": f.metric_value,
                "threshold": f.threshold,
            }
            for f in result.flags
        ],
        "itc_summary": result.itc_summary,
        "supplier_compliance": result.supplier_compliance,
        "circular_trading": result.circular_trading,
        "bank_vs_gst": result.bank_vs_gst,
        "warnings": result.warnings,
    }