"""
scoring/ml_validator.py
─────────────────────────────────────────────────────────────────────────────
XGBoost ML Validation Layer for Intelli-Credit.

Purpose:
  The deterministic scorecard IS the primary credit decision engine.
  The ML model serves as a SECOND OPINION only — it validates whether the
  scorecard decision is directionally consistent with patterns in historical
  lending data.

  If scorecard says APPROVE but ML predicts high default probability → FLAG.
  If scorecard says REJECT but ML predicts low default probability → NOTE.

  The ML prediction NEVER overrides the scorecard. It informs the analyst.

Demo Strategy:
  For the hackathon, we use a pre-trained XGBoost model from ml/models/.
  If the model file is not present, we use a deterministic rule-based fallback
  that mimics what the model would predict (based on the same features).

  The fallback ensures the demo NEVER crashes due to missing model files.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

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
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    logger.warning("XGBoost not installed. Using rule-based fallback validator.")

from config import settings, ML_MODELS_DIR
from scoring.feature_engineer import FeatureSet
from scoring.five_cs_scorer import ScorecardResult


# ── Model path ────────────────────────────────────────────────────────────────
MODEL_PATH = ML_MODELS_DIR / "credit_validator.json"


@dataclass
class MLValidationResult:
    """XGBoost second-opinion result."""
    default_probability:    float    # 0–1 probability of default
    predicted_label:        str      # "low_risk" | "medium_risk" | "high_risk"
    agrees_with_scorecard:  bool     # Does ML agree with scorecard decision?
    confidence:             float    # 0–1 model confidence
    model_used:             str      # "xgboost" | "rule_fallback"
    divergence_flag:        bool     # True if ML strongly disagrees
    divergence_note:        str      # Human-readable explanation if divergence
    feature_importances:    dict     # Top 5 features driving ML prediction


def validate_with_ml(
    features:  FeatureSet,
    scorecard: ScorecardResult,
) -> MLValidationResult:
    """
    Main entry point. Runs ML validation on the scorecard result.
    Always returns a result — never raises. Falls back gracefully.
    """
    logger.info("Running ML validation (model_available=%s)", XGB_AVAILABLE)

    if XGB_AVAILABLE and MODEL_PATH.exists():
        return _run_xgboost(features, scorecard)
    else:
        return _run_rule_fallback(features, scorecard)


# ── XGBoost Path ──────────────────────────────────────────────────────────────

def _run_xgboost(features: FeatureSet, scorecard: ScorecardResult) -> MLValidationResult:
    """Run the trained XGBoost model if available."""
    try:
        model   = xgb.Booster()
        model.load_model(str(MODEL_PATH))

        feature_vector = _build_feature_vector(features)
        dmatrix = xgb.DMatrix(
            np.array([feature_vector]),
            feature_names=_feature_names(),
        )
        prob = float(model.predict(dmatrix)[0])

        label, agrees, divergence, note = _interpret_prediction(
            prob, scorecard, features
        )

        # Feature importances from model
        importance_raw = model.get_score(importance_type="gain")
        importances    = dict(sorted(
            importance_raw.items(), key=lambda x: x[1], reverse=True
        )[:5])

        return MLValidationResult(
            default_probability=round(prob, 4),
            predicted_label=label,
            agrees_with_scorecard=agrees,
            confidence=round(abs(0.5 - prob) * 2, 3),
            model_used="xgboost",
            divergence_flag=divergence,
            divergence_note=note,
            feature_importances=importances,
        )

    except Exception as e:
        logger.error("XGBoost validation failed: %s — using fallback", e)
        return _run_rule_fallback(features, scorecard)


# ── Rule-Based Fallback ───────────────────────────────────────────────────────

def _run_rule_fallback(
    features: FeatureSet, scorecard: ScorecardResult
) -> MLValidationResult:
    """
    Deterministic rule-based fallback that produces sensible ML-like output.
    Uses the same features as the XGBoost model would.

    This is NOT a black-box — it's a transparent heuristic that:
      1. Weights DSCR, D/E, litigation, and pledge most heavily (per literature)
      2. Produces a default probability consistent with the scorecard grade
      3. Always agrees with clear approve/reject — flags ambiguous cases
    """
    # Build a weighted default probability
    # Higher probability = higher default risk
    prob = 0.20  # Base (BBB- grade starting point)

    # DSCR (most predictive of default — literature consensus)
    if features.dscr < 1.0:
        prob += 0.35
    elif features.dscr < 1.30:
        prob += 0.20
    elif features.dscr < 1.50:
        prob += 0.05
    else:
        prob -= 0.05

    # D/E ratio
    if features.de_ratio > 4.0:
        prob += 0.15
    elif features.de_ratio > 3.0:
        prob += 0.08
    elif features.de_ratio > 2.0:
        prob += 0.03

    # Litigation risk
    if features.litigation_risk < 0.3:
        prob += 0.20
    elif features.litigation_risk < 0.6:
        prob += 0.10

    # Promoter pledge
    if features.promoter_track_record < 0.4:
        prob += 0.10
    elif features.promoter_track_record < 0.6:
        prob += 0.05

    # GST compliance
    if features.gst_compliance < 0.5:
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

    # Mock feature importances (representative of XGBoost output)
    importances = {
        "dscr":                   round(0.28 * (1 + prob), 3),
        "de_ratio":               round(0.18 * (1 + prob * 0.5), 3),
        "litigation_risk":        round(0.16, 3),
        "security_cover":         round(0.14, 3),
        "promoter_track_record":  round(0.12, 3),
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


# ── Interpretation ─────────────────────────────────────────────────────────────

def _interpret_prediction(
    prob: float,
    scorecard: ScorecardResult,
    features: FeatureSet,
) -> tuple[str, bool, bool, str]:
    """
    Interpret the default probability and compare with scorecard decision.
    Returns (label, agrees, divergence_flag, note).
    """
    # Label
    if prob < 0.25:
        label = "low_risk"
    elif prob < 0.55:
        label = "medium_risk"
    else:
        label = "high_risk"

    # Does ML agree with scorecard decision?
    sc_decision = scorecard.decision
    ml_approve  = prob < 0.45
    sc_approve  = sc_decision in ("APPROVE", "PARTIAL")
    agrees      = ml_approve == sc_approve

    # Divergence: ML strongly disagrees
    divergence = False
    note       = ""

    if sc_decision == "APPROVE" and prob > 0.60:
        divergence = True
        note = (
            f"⚠️ Model flag: Scorecard recommends APPROVE (grade {scorecard.risk_grade}) "
            f"but ML predicts {prob*100:.0f}% default probability. "
            f"Primary ML concerns: DSCR {features.dscr:.2f}x, "
            f"D/E {features.de_ratio:.2f}x. "
            "Recommend senior credit review before sanction."
        )
    elif sc_decision == "REJECT" and prob < 0.25:
        divergence = True
        note = (
            f"ℹ️ Model note: Scorecard REJECT but ML predicts only {prob*100:.0f}% "
            f"default probability. The rejection is likely driven by structural "
            f"factors (litigation/knockout) not fully captured by ML features. "
            f"Scorecard decision stands — this is informational only."
        )
    elif not agrees and not divergence:
        note = (
            f"ML prediction ({label}, {prob*100:.0f}% default) is "
            f"directionally {'consistent' if agrees else 'inconsistent'} "
            f"with scorecard ({sc_decision})."
        )

    return label, agrees, divergence, note


# ── Feature Vector ────────────────────────────────────────────────────────────

def _build_feature_vector(features: FeatureSet) -> list:
    """
    Build the 16-feature vector in the same order as model training.
    Order MUST match the training script in ml/train_model.py.
    """
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
        features.promoter_equity_pct / 100,  # Normalise 0-100 → 0-1
        features.security_cover,
        features.collateral_encumbrance,
        features.sector_outlook,
        features.customer_concentration,
        features.regulatory_environment,
    ]


def _feature_names() -> list:
    return [
        "litigation_risk", "promoter_track_record", "gst_compliance",
        "management_quality", "dscr", "ebitda_margin_trend",
        "revenue_cagr_vs_sector", "plant_utilization", "de_ratio",
        "net_worth_trend", "promoter_equity_pct_norm", "security_cover",
        "collateral_encumbrance", "sector_outlook",
        "customer_concentration", "regulatory_environment",
    ]


def ml_result_to_dict(result: MLValidationResult) -> dict:
    """Serialise MLValidationResult for API responses."""
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