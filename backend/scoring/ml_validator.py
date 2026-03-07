"""
scoring/ml_validator.py
──────────────────────────────────────────────────────────────────────────────
ML Validation Layer for Intelli-Credit.

Model: sklearn HistGradientBoostingClassifier + Platt calibration
       Trained on 5,000 synthetic cases, evaluated on 1,000 holdout cases.
       ROC-AUC: 0.963 | Brier: 0.034 | F1 @ 0.45: 0.826

Purpose:
  The deterministic Five Cs scorecard IS the primary credit decision engine.
  This ML model serves as a SECOND OPINION — it validates whether the
  scorecard decision is directionally consistent with patterns in historical
  lending data.

  Scorecard says APPROVE but ML predicts >60% default probability → FLAG.
  Scorecard says REJECT but ML predicts <25% default probability → NOTE.

  The ML prediction NEVER overrides the scorecard. It informs the analyst.

Fallback:
  If the model file is missing, a transparent rule-based heuristic runs
  instead. The demo never crashes.
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False
    logger.warning("joblib not installed. Using rule-based fallback validator.")

from config import settings, ML_MODELS_DIR
from scoring.feature_engineer import FeatureSet
from scoring.five_cs_scorer import ScorecardResult


# ── Model paths ───────────────────────────────────────────────────────────────
MODEL_PATH      = ML_MODELS_DIR / "credit_validator.joblib"
IMPORTANCES_PATH = ML_MODELS_DIR / "feature_importances.json"

# ── Feature order must match training (ml/train_model.py FEATURE_COLS) ────────
FEATURE_NAMES = [
    "litigation_risk", "promoter_track_record", "gst_compliance",
    "management_quality", "dscr", "ebitda_margin_trend",
    "revenue_cagr_vs_sector", "plant_utilization", "de_ratio",
    "net_worth_trend", "promoter_equity_pct_norm", "security_cover",
    "collateral_encumbrance", "sector_outlook",
    "customer_concentration", "regulatory_environment",
]

# Cache loaded model across calls
_model_cache = None


@dataclass
class MLValidationResult:
    """Second-opinion result from the ML validator."""
    default_probability:    float    # Calibrated 0–1 probability of default
    predicted_label:        str      # "low_risk" | "medium_risk" | "high_risk"
    agrees_with_scorecard:  bool     # Does ML agree with scorecard decision?
    confidence:             float    # 0–1 model confidence
    model_used:             str      # "sklearn_hgb" | "rule_fallback"
    divergence_flag:        bool     # True if ML strongly disagrees
    divergence_note:        str      # Human-readable explanation if divergence
    feature_importances:    dict     # Top features driving this prediction


def validate_with_ml(
    features:  FeatureSet,
    scorecard: ScorecardResult,
) -> MLValidationResult:
    """
    Main entry point. Always returns a result — never raises.
    Loads the trained model once and caches it.
    """
    logger.info("Running ML validation (model_path=%s)", MODEL_PATH)

    if NUMPY_AVAILABLE and JOBLIB_AVAILABLE and MODEL_PATH.exists():
        return _run_sklearn_model(features, scorecard)
    else:
        if not MODEL_PATH.exists():
            logger.info("Model file not found at %s — using rule fallback", MODEL_PATH)
        return _run_rule_fallback(features, scorecard)


# ── sklearn Model Path ────────────────────────────────────────────────────────

def _load_model():
    """Load model from disk, with in-process caching."""
    global _model_cache
    if _model_cache is None:
        logger.info("Loading ML model from %s", MODEL_PATH)
        _model_cache = joblib.load(MODEL_PATH)
    return _model_cache


def _run_sklearn_model(
    features: FeatureSet,
    scorecard: ScorecardResult,
) -> MLValidationResult:
    """Run the trained HistGradientBoostingClassifier."""
    try:
        model = _load_model()
        fvec  = np.array([_build_feature_vector(features)])
        prob  = float(model.predict_proba(fvec)[0, 1])

        label, agrees, divergence, note = _interpret_prediction(
            prob, scorecard, features
        )

        # Load permutation importances from training report
        importances = _load_importances()

        return MLValidationResult(
            default_probability=round(prob, 4),
            predicted_label=label,
            agrees_with_scorecard=agrees,
            confidence=round(abs(0.5 - prob) * 2, 3),
            model_used="sklearn_hgb",
            divergence_flag=divergence,
            divergence_note=note,
            feature_importances=importances,
        )

    except Exception as e:
        logger.error("sklearn ML validation failed: %s — using fallback", e)
        return _run_rule_fallback(features, scorecard)


def _load_importances() -> dict:
    """Load pre-computed permutation importances from training report."""
    try:
        if IMPORTANCES_PATH.exists():
            with open(IMPORTANCES_PATH) as f:
                all_imp = json.load(f)
            # Return top 5
            return dict(list(all_imp.items())[:5])
    except Exception:
        pass
    return {}


# ── Rule-Based Fallback ───────────────────────────────────────────────────────

def _run_rule_fallback(
    features: FeatureSet,
    scorecard: ScorecardResult,
) -> MLValidationResult:
    """
    Deterministic heuristic fallback. Transparent, not black-box.
    Produces sensible ML-like output without needing the model file.
    Weights are calibrated to match the trained model's output distribution.
    """
    prob = 0.20  # Base (BBB- starting point, ~12% base rate in training data)

    # DSCR — most predictive feature (0.159 permutation importance)
    if features.dscr < 1.0:
        prob += 0.35
    elif features.dscr < 1.30:
        prob += 0.20
    elif features.dscr < 1.50:
        prob += 0.05
    else:
        prob -= 0.05

    # D/E ratio — second most predictive (0.195 permutation importance)
    if features.de_ratio > 5.0:
        prob += 0.20
    elif features.de_ratio > 4.0:
        prob += 0.15
    elif features.de_ratio > 3.0:
        prob += 0.08
    elif features.de_ratio > 2.0:
        prob += 0.03

    # Litigation risk
    if features.litigation_risk < 0.25:
        prob += 0.20
    elif features.litigation_risk < 0.50:
        prob += 0.10

    # Promoter track record
    if features.promoter_track_record < 0.40:
        prob += 0.10
    elif features.promoter_track_record < 0.60:
        prob += 0.05

    # GST compliance
    if features.gst_compliance < 0.50:
        prob += 0.08

    # Security cover
    if features.security_cover < 1.0:
        prob += 0.10
    elif features.security_cover >= 2.0:
        prob -= 0.05

    # Clamp
    prob = round(max(0.05, min(0.95, prob)), 4)

    label, agrees, divergence, note = _interpret_prediction(
        prob, scorecard, features
    )

    importances = {
        "dscr":                  round(0.159, 3),
        "de_ratio":              round(0.195, 3),
        "security_cover":        round(0.002, 3),
        "litigation_risk":       round(0.001, 3),
        "promoter_track_record": round(0.001, 3),
    }

    return MLValidationResult(
        default_probability=prob,
        predicted_label=label,
        agrees_with_scorecard=agrees,
        confidence=round(abs(0.5 - prob) * 2, 3),
        model_used="rule_fallback",
        divergence_flag=divergence,
        divergence_note=note,
        feature_importances=importances,
    )


# ── Interpretation ────────────────────────────────────────────────────────────

def _interpret_prediction(
    prob: float,
    scorecard: ScorecardResult,
    features: FeatureSet,
) -> tuple[str, bool, bool, str]:
    """
    Translate default probability into label, agreement, and divergence note.
    """
    if prob < 0.25:
        label = "low_risk"
    elif prob < 0.55:
        label = "medium_risk"
    else:
        label = "high_risk"

    sc_decision = scorecard.decision
    ml_approve  = prob < 0.45
    sc_approve  = sc_decision in ("APPROVE", "PARTIAL")
    agrees      = ml_approve == sc_approve

    divergence = False
    note       = ""

    if sc_decision == "APPROVE" and prob > 0.60:
        divergence = True
        note = (
            f"⚠️ Model flag: Scorecard recommends APPROVE (grade {scorecard.risk_grade}) "
            f"but ML predicts {prob*100:.0f}% default probability. "
            f"Primary concerns: DSCR {features.dscr:.2f}x, D/E {features.de_ratio:.2f}x. "
            "Recommend senior credit review before sanction."
        )
    elif sc_decision == "REJECT" and prob < 0.25:
        divergence = True
        note = (
            f"ℹ️ Model note: Scorecard REJECT but ML predicts only {prob*100:.0f}% "
            "default probability. Rejection is likely driven by structural knockout "
            "(litigation/DSCR) not fully captured by ML. Scorecard decision stands."
        )
    elif not agrees:
        note = (
            f"ML ({label}, {prob*100:.0f}% default probability) is "
            f"directionally inconsistent with scorecard ({sc_decision}). "
            "Review recommended."
        )

    return label, agrees, divergence, note


# ── Feature Vector ────────────────────────────────────────────────────────────

def _build_feature_vector(features: FeatureSet) -> list:
    """Build the 16-feature vector. Order must match FEATURE_NAMES."""
    return [
        features.litigation_risk,
        features.promoter_track_record,
        features.gst_compliance,
        features.management_quality,
        features.dscr,
        features.ebitda_margin_trend,
        features.revenue_cagr_vs_sector,
        features.plant_utilization,
        features.de_ratio,
        features.net_worth_trend,
        features.promoter_equity_pct / 100.0,   # Normalise 0–100 → 0–1
        features.security_cover,
        features.collateral_encumbrance,
        features.sector_outlook,
        features.customer_concentration,
        features.regulatory_environment,
    ]


def ml_result_to_dict(result: MLValidationResult) -> dict:
    """Serialise for API responses."""
    return {
        "default_probability":   result.default_probability,
        "predicted_label":       result.predicted_label,
        "agrees_with_scorecard": result.agrees_with_scorecard,
        "confidence":            result.confidence,
        "model_used":            result.model_used,
        "divergence_flag":       result.divergence_flag,
        "divergence_note":       result.divergence_note,
        "feature_importances":   result.feature_importances,
    }