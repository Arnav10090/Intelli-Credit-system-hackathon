"""
tests/test_ml_validator.py
──────────────────────────────────────────────────────────────────────────────
Tests for the ML validation layer (ml_validator.py) and training pipeline.

Covers:
  - Rule fallback (always works, no model file needed)
  - Trained model inference (loads credit_validator.joblib)
  - MLValidationResult structure and invariants
  - Divergence detection logic
  - Feature vector construction
  - Training report sanity checks (AUC, Brier, features)

Run:
  cd backend && pytest ../tests/test_ml_validator.py -v
──────────────────────────────────────────────────────────────────────────────
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from pathlib import Path

from scoring.ml_validator import (
    validate_with_ml,
    _run_rule_fallback,
    _build_feature_vector,
    ml_result_to_dict,
    MLValidationResult,
    MODEL_PATH,
    FEATURE_NAMES,
)
from scoring.feature_engineer import FeatureSet
from scoring.five_cs_scorer import compute_score


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_features(**overrides) -> FeatureSet:
    defaults = dict(
        litigation_risk=0.85, promoter_track_record=0.80,
        gst_compliance=0.90, management_quality=0.75,
        dscr=1.8, ebitda_margin_trend=0.70, revenue_cagr_vs_sector=0.65,
        plant_utilization=0.75, de_ratio=1.5, net_worth_trend=0.70,
        promoter_equity_pct=60.0, security_cover=1.8,
        collateral_encumbrance=0.85, sector_outlook=0.65,
        customer_concentration=0.70, regulatory_environment=0.70,
    )
    defaults.update(overrides)
    return FeatureSet(**defaults)


def make_scorecard(features: FeatureSet):
    return compute_score(features)


# ─────────────────────────────────────────────────────────────────────────────
# MLValidationResult structure
# ─────────────────────────────────────────────────────────────────────────────

class TestMLValidationResultStructure:

    def test_has_all_required_fields(self):
        f = make_features()
        sc = make_scorecard(f)
        result = validate_with_ml(f, sc)
        assert hasattr(result, "default_probability")
        assert hasattr(result, "predicted_label")
        assert hasattr(result, "agrees_with_scorecard")
        assert hasattr(result, "confidence")
        assert hasattr(result, "model_used")
        assert hasattr(result, "divergence_flag")
        assert hasattr(result, "divergence_note")
        assert hasattr(result, "feature_importances")

    def test_default_probability_in_range(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert 0.0 <= result.default_probability <= 1.0

    def test_confidence_in_range(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert 0.0 <= result.confidence <= 1.0

    def test_predicted_label_valid(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert result.predicted_label in ("low_risk", "medium_risk", "high_risk")

    def test_model_used_field_is_informative(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert result.model_used in ("sklearn_hgb", "rule_fallback")

    def test_feature_importances_is_dict(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert isinstance(result.feature_importances, dict)

    def test_to_dict_has_all_keys(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        d = ml_result_to_dict(result)
        expected_keys = {
            "default_probability", "predicted_label", "agrees_with_scorecard",
            "confidence", "model_used", "divergence_flag",
            "divergence_note", "feature_importances",
        }
        assert expected_keys.issubset(set(d.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# Risk label logic
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskLabels:

    def test_excellent_borrower_is_low_risk(self):
        f = make_features(dscr=2.5, de_ratio=0.8, litigation_risk=0.95,
                          security_cover=2.5, gst_compliance=0.95)
        result = validate_with_ml(f, make_scorecard(f))
        assert result.predicted_label == "low_risk"
        assert result.default_probability < 0.25

    def test_distressed_borrower_is_high_risk(self):
        f = make_features(dscr=0.7, de_ratio=5.5, litigation_risk=0.1,
                          gst_compliance=0.3, security_cover=0.6,
                          promoter_track_record=0.2)
        result = validate_with_ml(f, make_scorecard(f))
        assert result.predicted_label == "high_risk"
        assert result.default_probability > 0.55

    def test_borderline_borrower_is_medium_risk(self):
        f = make_features(dscr=1.2, de_ratio=2.8, litigation_risk=0.5,
                          security_cover=1.1)
        result = validate_with_ml(f, make_scorecard(f))
        assert result.predicted_label in ("medium_risk", "high_risk")

    def test_low_prob_maps_to_low_risk(self):
        """default_probability < 0.25 must always give low_risk label."""
        # Force rule fallback for deterministic test
        f = make_features(dscr=3.0, de_ratio=0.5, litigation_risk=1.0,
                          security_cover=2.5, gst_compliance=1.0,
                          promoter_track_record=1.0)
        result = _run_rule_fallback(f, make_scorecard(f))
        if result.default_probability < 0.25:
            assert result.predicted_label == "low_risk"

    def test_high_prob_maps_to_high_risk(self):
        f = make_features(dscr=0.5, de_ratio=7.0, litigation_risk=0.05)
        result = _run_rule_fallback(f, make_scorecard(f))
        if result.default_probability >= 0.55:
            assert result.predicted_label == "high_risk"


# ─────────────────────────────────────────────────────────────────────────────
# Agreement with scorecard
# ─────────────────────────────────────────────────────────────────────────────

class TestScorecardAgreement:

    def test_strong_approve_agrees(self):
        """Very healthy borrower: both scorecard and ML should approve."""
        f = make_features(dscr=2.2, de_ratio=0.8, litigation_risk=0.95)
        sc = make_scorecard(f)
        result = validate_with_ml(f, sc)
        if sc.decision == "APPROVE":
            assert result.agrees_with_scorecard is True

    def test_agreement_is_boolean(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert isinstance(result.agrees_with_scorecard, bool)


# ─────────────────────────────────────────────────────────────────────────────
# Divergence detection
# ─────────────────────────────────────────────────────────────────────────────

class TestDivergenceDetection:

    def test_divergence_flag_is_boolean(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert isinstance(result.divergence_flag, bool)

    def test_divergence_note_string(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert isinstance(result.divergence_note, str)

    def test_divergence_note_populated_when_flagged(self):
        """If divergence_flag is True, note must explain why."""
        f = make_features()
        result = _run_rule_fallback(f, make_scorecard(f))
        if result.divergence_flag:
            assert len(result.divergence_note) > 20

    def test_no_divergence_for_clear_approve(self):
        """Clean borrower: scorecard APPROVE + ML low_risk → no divergence."""
        f = make_features(dscr=2.5, de_ratio=0.8, litigation_risk=0.95,
                          gst_compliance=0.95, security_cover=2.5,
                          promoter_track_record=0.90)
        sc = make_scorecard(f)
        result = _run_rule_fallback(f, sc)
        assert result.divergence_flag is False


# ─────────────────────────────────────────────────────────────────────────────
# Rule fallback determinism and monotonicity
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleFallback:

    def test_deterministic(self):
        """Same inputs always produce the same probability."""
        f = make_features()
        sc = make_scorecard(f)
        r1 = _run_rule_fallback(f, sc)
        r2 = _run_rule_fallback(f, sc)
        assert r1.default_probability == r2.default_probability

    def test_higher_dscr_lowers_default_prob(self):
        sc = make_scorecard(make_features(dscr=1.5))
        r_low  = _run_rule_fallback(make_features(dscr=1.0),  sc)
        r_high = _run_rule_fallback(make_features(dscr=2.5),  sc)
        assert r_low.default_probability > r_high.default_probability

    def test_higher_de_ratio_raises_default_prob(self):
        sc = make_scorecard(make_features())
        r_low  = _run_rule_fallback(make_features(de_ratio=1.0), sc)
        r_high = _run_rule_fallback(make_features(de_ratio=5.0), sc)
        assert r_high.default_probability > r_low.default_probability

    def test_probability_clamped_0_to_1(self):
        """Extreme inputs should still stay in [0,1]."""
        extreme_good = make_features(dscr=4.0, de_ratio=0.1, litigation_risk=1.0,
                                     security_cover=3.5, gst_compliance=1.0)
        extreme_bad  = make_features(dscr=0.3, de_ratio=9.0, litigation_risk=0.0,
                                     gst_compliance=0.0, security_cover=0.5)
        sc_g = make_scorecard(extreme_good)
        sc_b = make_scorecard(extreme_bad)
        r_g = _run_rule_fallback(extreme_good, sc_g)
        r_b = _run_rule_fallback(extreme_bad,  sc_b)
        assert 0.0 <= r_g.default_probability <= 1.0
        assert 0.0 <= r_b.default_probability <= 1.0

    def test_model_used_is_rule_fallback(self):
        f = make_features()
        result = _run_rule_fallback(f, make_scorecard(f))
        assert result.model_used == "rule_fallback"


# ─────────────────────────────────────────────────────────────────────────────
# Feature vector
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureVector:

    def test_length_matches_feature_names(self):
        f = make_features()
        fvec = _build_feature_vector(f)
        assert len(fvec) == len(FEATURE_NAMES)

    def test_promoter_equity_is_normalised(self):
        """promoter_equity_pct is stored as 0–100 but model needs 0–1."""
        f = make_features(promoter_equity_pct=60.0)
        fvec = _build_feature_vector(f)
        idx = FEATURE_NAMES.index("promoter_equity_pct_norm")
        assert abs(fvec[idx] - 0.60) < 1e-6

    def test_all_values_finite(self):
        import math
        f = make_features()
        fvec = _build_feature_vector(f)
        assert all(math.isfinite(v) for v in fvec)

    def test_feature_names_count_is_16(self):
        assert len(FEATURE_NAMES) == 16


# ─────────────────────────────────────────────────────────────────────────────
# Trained model tests (skipped if model file not present)
# ─────────────────────────────────────────────────────────────────────────────

MODEL_PRESENT = MODEL_PATH.exists()

@pytest.mark.skipif(not MODEL_PRESENT, reason="Model file not found — run ml/train_model.py")
class TestTrainedModel:

    def test_model_loads_without_error(self):
        import joblib
        model = joblib.load(MODEL_PATH)
        assert model is not None

    def test_model_predicts_probability(self):
        import joblib, numpy as np
        model = joblib.load(MODEL_PATH)
        f = make_features()
        fvec = np.array([_build_feature_vector(f)])
        prob = model.predict_proba(fvec)[0, 1]
        assert 0.0 <= prob <= 1.0

    def test_model_used_is_sklearn_hgb(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert result.model_used == "sklearn_hgb"

    def test_clean_borrower_low_probability(self):
        f = make_features(dscr=2.5, de_ratio=0.8, litigation_risk=0.95,
                          gst_compliance=0.95, security_cover=2.5)
        result = validate_with_ml(f, make_scorecard(f))
        assert result.default_probability < 0.40

    def test_distressed_borrower_high_probability(self):
        f = make_features(dscr=0.7, de_ratio=6.0, litigation_risk=0.05,
                          gst_compliance=0.2, security_cover=0.5)
        result = validate_with_ml(f, make_scorecard(f))
        assert result.default_probability > 0.55

    def test_feature_importances_non_empty(self):
        f = make_features()
        result = validate_with_ml(f, make_scorecard(f))
        assert len(result.feature_importances) > 0

    def test_never_raises_on_any_valid_input(self):
        """Model should never crash regardless of feature values."""
        import numpy as np
        rng = np.random.default_rng(123)
        for _ in range(20):
            f = make_features(
                dscr=float(rng.uniform(0.3, 4.0)),
                de_ratio=float(rng.uniform(0.1, 8.0)),
                litigation_risk=float(rng.uniform(0, 1)),
                security_cover=float(rng.uniform(0.5, 3.5)),
            )
            result = validate_with_ml(f, make_scorecard(f))
            assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# Training report sanity checks
# ─────────────────────────────────────────────────────────────────────────────

REPORT_PATH = MODEL_PATH.parent / "training_report.json"

@pytest.mark.skipif(not REPORT_PATH.exists(), reason="Training report not found")
class TestTrainingReport:

    @pytest.fixture
    def report(self):
        with open(REPORT_PATH) as f:
            return json.load(f)

    def test_roc_auc_above_0_85(self, report):
        auc = report["holdout_metrics"]["roc_auc"]
        assert auc >= 0.85, f"ROC-AUC too low: {auc}"

    def test_brier_score_below_0_10(self, report):
        brier = report["holdout_metrics"]["brier_score"]
        assert brier <= 0.10, f"Brier score too high: {brier}"

    def test_average_precision_above_0_70(self, report):
        ap = report["holdout_metrics"]["average_precision"]
        assert ap >= 0.70, f"Average Precision too low: {ap}"

    def test_16_features_in_report(self, report):
        assert len(report["feature_names"]) == 16

    def test_feature_names_match_validator(self, report):
        assert set(report["feature_names"]) == set(FEATURE_NAMES)

    def test_decision_threshold_documented(self, report):
        assert "decision_threshold" in report
        assert report["decision_threshold"] == 0.45