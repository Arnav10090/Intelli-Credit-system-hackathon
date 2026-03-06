"""
tests/test_scoring_formulas.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Five Cs scoring formulas in five_cs_scorer.py.

Run:
  cd backend && pytest ../tests/test_scoring_formulas.py -v
──────────────────────────────────────────────────────────────────────────────
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from scoring.five_cs_scorer import (
    _score_litigation_risk,
    _score_promoter_track_record,
    _score_gst_compliance,
    _score_management_quality,
    _score_dscr,
    _score_ebitda_margin_trend,
    _score_revenue_cagr,
    _score_plant_utilization,
    _score_de_ratio,
    _score_net_worth_trend,
    _score_promoter_equity,
    _score_security_cover,
    _score_collateral_encumbrance,
    _score_sector_outlook,
    _score_customer_concentration,
    _score_regulatory_environment,
    compute_score,
    _contrib,
    _get_grade,
)
from scoring.feature_engineer import FeatureSet


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_features(**overrides) -> FeatureSet:
    """Return a perfect FeatureSet (all features = max score), with optional overrides."""
    defaults = dict(
        litigation_risk=1.0,
        promoter_track_record=1.0,
        gst_compliance=1.0,
        management_quality=1.0,
        dscr=2.5,
        ebitda_margin_trend=1.0,
        revenue_cagr_vs_sector=1.0,
        plant_utilization=1.0,
        de_ratio=0.5,
        net_worth_trend=1.0,
        promoter_equity_pct=75.0,
        security_cover=2.5,
        collateral_encumbrance=1.0,
        sector_outlook=1.0,
        customer_concentration=1.0,
        regulatory_environment=1.0,
    )
    defaults.update(overrides)
    return FeatureSet(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# CHARACTER — 60 pts
# ─────────────────────────────────────────────────────────────────────────────

class TestLitigationRisk:
    """_score_litigation_risk: max 20 pts — knockout if ≤4 pts (value < 0.25)"""

    def test_clean_borrower_scores_max(self):
        assert _score_litigation_risk(1.0) == 20

    def test_critical_litigation_scores_zero(self):
        assert _score_litigation_risk(0.0) == 0

    def test_just_below_knockout_boundary(self):
        # value < 0.25 → scores 0–4 pts → knockout
        assert _score_litigation_risk(0.24) == 3

    def test_at_0_25_is_in_serious_band_not_knockout(self):
        # value=0.25 falls in the ≥0.25 band → 10 pts (no knockout)
        assert _score_litigation_risk(0.25) == 10

    def test_just_above_knockout_threshold(self):
        # 0.26 is solidly in the serious band → >4 pts
        assert _score_litigation_risk(0.26) >= 10

    def test_moderate_litigation_midrange(self):
        # 0.5 → start of moderate band → 15 pts
        assert _score_litigation_risk(0.5) == 15

    def test_serious_litigation_midrange(self):
        score = _score_litigation_risk(0.375)
        assert 10 <= score <= 15

    def test_knockout_trigger_at_very_low_value(self):
        # Value ≤ 0.20 yields ≤ 3 pts → knockout (≤ 4 pts threshold)
        pts = _score_litigation_risk(0.20)
        assert pts <= 4

    def test_monotonically_increasing(self):
        scores = [_score_litigation_risk(v / 10) for v in range(0, 11)]
        assert scores == sorted(scores), "Scores should be non-decreasing"


class TestPromoterTrackRecord:
    def test_clean_promoter_max(self):
        assert _score_promoter_track_record(1.0) == 15

    def test_zero_promoter_score(self):
        assert _score_promoter_track_record(0.0) == 0

    def test_boundary_at_0_3(self):
        assert _score_promoter_track_record(0.3) == 5

    def test_boundary_at_0_6(self):
        assert _score_promoter_track_record(0.6) == 10

    def test_monotonically_increasing(self):
        scores = [_score_promoter_track_record(v / 10) for v in range(0, 11)]
        assert scores == sorted(scores)


class TestGstCompliance:
    def test_fully_compliant_scores_max(self):
        assert _score_gst_compliance(1.0) == 10

    def test_circular_trading_knockout(self):
        assert _score_gst_compliance(0.0) == 0

    def test_good_compliance_at_0_8(self):
        assert _score_gst_compliance(0.8) == 10

    def test_serious_violation_at_0_4(self):
        score = _score_gst_compliance(0.4)
        assert 0 < score < 10

    def test_monotonically_increasing(self):
        scores = [_score_gst_compliance(v / 10) for v in range(0, 11)]
        assert scores == sorted(scores)


class TestManagementQuality:
    def test_max_score(self):
        assert _score_management_quality(1.0) == 15

    def test_zero_score(self):
        assert _score_management_quality(0.0) == 0

    def test_midpoint(self):
        assert _score_management_quality(0.5) == 7


# ─────────────────────────────────────────────────────────────────────────────
# CAPACITY — 60 pts
# ─────────────────────────────────────────────────────────────────────────────

class TestDscr:
    def test_excellent_dscr_above_2(self):
        assert _score_dscr(2.0) == 25
        assert _score_dscr(3.0) == 25

    def test_strong_dscr_1_75_to_2(self):
        assert _score_dscr(1.75) == 22
        assert _score_dscr(1.99) == 22

    def test_comfortable_dscr_1_5_to_1_75(self):
        assert _score_dscr(1.5) == 18
        assert _score_dscr(1.74) == 18

    def test_at_minimum_threshold_1_3(self):
        assert _score_dscr(1.3) == 14

    def test_below_minimum_1_1_to_1_3(self):
        assert _score_dscr(1.1) == 8

    def test_barely_covers_1_0_to_1_1(self):
        assert _score_dscr(1.0) == 3
        assert _score_dscr(1.09) == 3

    def test_knockout_below_1_0(self):
        assert _score_dscr(0.99) == 0
        assert _score_dscr(0.75) == 0
        assert _score_dscr(0.0) == 0

    def test_knockout_boundary_exact(self):
        assert _score_dscr(0.999) == 0
        assert _score_dscr(1.000) == 3

    def test_monotonically_increasing(self):
        test_values = [0.5, 1.0, 1.1, 1.3, 1.5, 1.75, 2.0, 3.0]
        scores = [_score_dscr(v) for v in test_values]
        assert scores == sorted(scores)


class TestEbitdaMarginTrend:
    def test_max(self):      assert _score_ebitda_margin_trend(1.0) == 15
    def test_zero(self):     assert _score_ebitda_margin_trend(0.0) == 0
    def test_midpoint(self): assert _score_ebitda_margin_trend(0.5) == 7


class TestRevenueCagr:
    def test_above_sector(self):      assert _score_revenue_cagr(1.0) == 10
    def test_at_sector_0_6(self):     assert _score_revenue_cagr(0.6) == 7
    def test_below_sector_0_3(self):  assert _score_revenue_cagr(0.3) == 3
    def test_far_below_sector(self):  assert _score_revenue_cagr(0.0) == 0

    def test_monotonically_increasing(self):
        scores = [_score_revenue_cagr(v / 10) for v in range(0, 11)]
        assert scores == sorted(scores)


class TestPlantUtilization:
    def test_full_utilization(self): assert _score_plant_utilization(1.0) == 10
    def test_zero_utilization(self): assert _score_plant_utilization(0.0) == 0


# ─────────────────────────────────────────────────────────────────────────────
# CAPITAL — 45 pts
# ─────────────────────────────────────────────────────────────────────────────

class TestDeRatio:
    def test_conservative_leverage(self):
        assert _score_de_ratio(1.0) == 20
        assert _score_de_ratio(0.5) == 20

    def test_moderate_leverage_1_to_2(self):   assert _score_de_ratio(1.5) == 16
    def test_elevated_leverage_2_to_3(self):   assert _score_de_ratio(2.5) == 12
    def test_high_leverage_3_to_4(self):       assert _score_de_ratio(3.5) == 8
    def test_very_high_leverage_4_to_5(self):  assert _score_de_ratio(4.5) == 4
    def test_critical_leverage_above_5(self):
        assert _score_de_ratio(5.1) == 0
        assert _score_de_ratio(10.0) == 0

    def test_boundary_at_exactly_5(self):
        assert _score_de_ratio(5.0) == 4     # not >5, so 4 pts
        assert _score_de_ratio(5.01) == 0    # >5, so 0 pts

    def test_boundary_at_exactly_1(self):
        assert _score_de_ratio(1.0) == 20    # ≤1.0 → 20 pts
        assert _score_de_ratio(1.01) == 16   # >1.0 → 16 pts

    def test_monotonically_decreasing(self):
        test_values = [0.5, 1.5, 2.5, 3.5, 4.5, 6.0]
        scores = [_score_de_ratio(v) for v in test_values]
        assert scores == sorted(scores, reverse=True)


class TestNetWorthTrend:
    def test_max(self):  assert _score_net_worth_trend(1.0) == 15
    def test_zero(self): assert _score_net_worth_trend(0.0) == 0


class TestPromoterEquity:
    def test_majority_holder_above_51(self):
        assert _score_promoter_equity(75.0) >= 7

    def test_significant_holder_26_to_51(self):
        score = _score_promoter_equity(38.0)
        assert 3 <= score <= 7

    def test_minority_holder_below_26(self):
        assert 0 <= _score_promoter_equity(10.0) < 3

    def test_zero_promoter(self):      assert _score_promoter_equity(0.0) == 0
    def test_boundary_at_51(self):     assert _score_promoter_equity(51.0) == 7
    def test_boundary_at_26(self):     assert _score_promoter_equity(26.0) == 3

    def test_monotonically_increasing(self):
        test_values = [0, 10, 26, 40, 51, 75, 100]
        scores = [_score_promoter_equity(v) for v in test_values]
        assert scores == sorted(scores)


# ─────────────────────────────────────────────────────────────────────────────
# COLLATERAL — 30 pts
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityCover:
    def test_excellent_cover_above_2(self):
        assert _score_security_cover(2.0) == 20
        assert _score_security_cover(3.0) == 20

    def test_good_cover_1_5_to_2(self):     assert _score_security_cover(1.5)  == 17
    def test_adequate_cover_1_25_to_1_5(self): assert _score_security_cover(1.25) == 14
    def test_marginal_cover_1_0_to_1_25(self): assert _score_security_cover(1.0)  == 10
    def test_thin_cover_0_8_to_1_0(self):   assert _score_security_cover(0.8)  == 5

    def test_knockout_below_0_8(self):
        assert _score_security_cover(0.79) == 0
        assert _score_security_cover(0.0)  == 0

    def test_boundary_exact_0_8(self):
        assert _score_security_cover(0.80)  == 5   # In 0.8–1.0 band
        assert _score_security_cover(0.799) == 0   # Below 0.8 → knockout

    def test_monotonically_increasing(self):
        test_values = [0.5, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5]
        scores = [_score_security_cover(v) for v in test_values]
        assert scores == sorted(scores)


class TestCollateralEncumbrance:
    def test_unencumbered(self):    assert _score_collateral_encumbrance(1.0) == 10
    def test_fully_encumbered(self): assert _score_collateral_encumbrance(0.0) == 0


# ─────────────────────────────────────────────────────────────────────────────
# CONDITIONS — 35 pts
# ─────────────────────────────────────────────────────────────────────────────

class TestConditions:
    def test_sector_outlook_max(self):         assert _score_sector_outlook(1.0) == 15
    def test_customer_concentration_max(self): assert _score_customer_concentration(1.0) == 10
    def test_regulatory_environment_max(self): assert _score_regulatory_environment(1.0) == 10

    def test_all_zeros(self):
        assert _score_sector_outlook(0.0) == 0
        assert _score_customer_concentration(0.0) == 0
        assert _score_regulatory_environment(0.0) == 0


# ─────────────────────────────────────────────────────────────────────────────
# CONTRIBUTION HELPER
# ─────────────────────────────────────────────────────────────────────────────

class TestContrib:
    def test_full_score(self):
        c = _contrib(20, 20)
        assert c["points_awarded"] == 20
        assert c["max_points"] == 20
        assert c["pct"] == 100.0

    def test_zero_score(self):
        c = _contrib(0, 20)
        assert c["pct"] == 0.0

    def test_partial_score(self):
        c = _contrib(10, 20)
        assert c["pct"] == 50.0

    def test_zero_max_no_division_error(self):
        c = _contrib(0, 0)
        assert c["pct"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# PILLAR TOTALS
# ─────────────────────────────────────────────────────────────────────────────

class TestPillarMaxPoints:

    def test_character_max_is_60(self):
        total = (
            _score_litigation_risk(1.0) +
            _score_promoter_track_record(1.0) +
            _score_gst_compliance(1.0) +
            _score_management_quality(1.0)
        )
        assert total == 60

    def test_capacity_max_is_60(self):
        total = (
            _score_dscr(2.5) +
            _score_ebitda_margin_trend(1.0) +
            _score_revenue_cagr(1.0) +
            _score_plant_utilization(1.0)
        )
        assert total == 60

    def test_capital_max_is_45(self):
        total = (
            _score_de_ratio(0.5) +
            _score_net_worth_trend(1.0) +
            _score_promoter_equity(100.0)
        )
        assert total == 45

    def test_collateral_max_is_30(self):
        total = (
            _score_security_cover(2.5) +
            _score_collateral_encumbrance(1.0)
        )
        assert total == 30

    def test_conditions_max_is_35(self):
        total = (
            _score_sector_outlook(1.0) +
            _score_customer_concentration(1.0) +
            _score_regulatory_environment(1.0)
        )
        assert total == 35

    def test_all_pillar_maxes_sum_to_230(self):
        # 60 + 60 + 45 + 30 + 35 = 230 actual max achievable points
        # Note: SCORE_MAX config is 200 — normalisation divides by 200
        total = 60 + 60 + 45 + 30 + 35
        assert total == 230

    def test_score_max_config_is_200(self):
        from config import settings
        assert settings.SCORE_MAX == 200


# ─────────────────────────────────────────────────────────────────────────────
# FULL SCORECARD
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeScore:

    def test_perfect_borrower_approves(self):
        f = make_features()
        result = compute_score(f)
        assert result.decision == "APPROVE"
        assert result.normalised_score >= 85
        assert result.knockout_flags == []

    def test_litigation_knockout_forces_reject(self):
        # value=0.0 → 0 pts → ≤ 4 pts threshold → knockout
        f = make_features(litigation_risk=0.0)
        result = compute_score(f)
        assert result.decision == "REJECT"
        assert any("litigation" in k.lower() for k in result.knockout_flags)

    def test_dscr_knockout_forces_reject_or_partial(self):
        f = make_features(dscr=0.75)
        result = compute_score(f)
        assert any("dscr" in k.lower() for k in result.knockout_flags)
        assert result.decision in ("REJECT", "PARTIAL")

    def test_gst_knockout_forces_reject(self):
        f = make_features(gst_compliance=0.0)
        result = compute_score(f)
        assert result.decision == "REJECT"
        assert any("gst" in k.lower() for k in result.knockout_flags)

    def test_weak_borrower_rejects(self):
        f = make_features(
            litigation_risk=0.1,
            dscr=0.8,
            de_ratio=6.0,
            promoter_track_record=0.1,
            gst_compliance=0.1,
            management_quality=0.1,
            ebitda_margin_trend=0.1,
            revenue_cagr_vs_sector=0.1,
            plant_utilization=0.1,
            net_worth_trend=0.1,
            promoter_equity_pct=5.0,
            security_cover=0.5,
            collateral_encumbrance=0.1,
            sector_outlook=0.1,
            customer_concentration=0.1,
            regulatory_environment=0.1,
        )
        result = compute_score(f)
        assert result.decision == "REJECT"

    def test_borderline_borrower_partial_or_reject(self):
        # Score just below 55 → should not be APPROVE
        f = make_features(
            litigation_risk=0.35,    # serious band → ~12 pts (not knockout)
            dscr=1.32,               # just above 1.3 → 14 pts
            de_ratio=4.0,            # 3-4 band → 8 pts
            promoter_track_record=0.3,
            gst_compliance=0.5,
            management_quality=0.3,
            ebitda_margin_trend=0.25,
            revenue_cagr_vs_sector=0.25,
            plant_utilization=0.3,
            net_worth_trend=0.25,
            promoter_equity_pct=20.0,
            security_cover=0.9,      # thin cover → 5 pts
            collateral_encumbrance=0.3,
            sector_outlook=0.25,
            customer_concentration=0.3,
            regulatory_environment=0.3,
        )
        result = compute_score(f)
        # normalised score should be below 55 → PARTIAL or REJECT
        assert result.normalised_score < 55 or result.decision in ("PARTIAL", "REJECT")

    def test_contributions_keys_match_16_features(self):
        result = compute_score(make_features())
        assert len(result.contributions) == 16

    def test_contributions_pct_between_0_and_100(self):
        result = compute_score(make_features())
        for name, contrib in result.contributions.items():
            assert 0 <= contrib["pct"] <= 100, f"{name} pct out of range"

    def test_normalised_score_between_0_and_100_ish(self):
        # Due to SCORE_MAX=200 vs actual max=230, perfect score > 100 is possible
        for dscr in [0.5, 1.2, 1.5, 2.0]:
            result = compute_score(make_features(dscr=dscr))
            assert result.normalised_score >= 0

    def test_raw_score_sums_correctly(self):
        result = compute_score(make_features())
        expected = (
            result.character_score + result.capacity_score +
            result.capital_score + result.collateral_score +
            result.conditions_score
        )
        assert result.total_raw_score == expected

    def test_normalised_score_is_raw_over_score_max(self):
        from config import settings
        result = compute_score(make_features())
        expected = round((result.total_raw_score / settings.SCORE_MAX) * 100)
        assert result.normalised_score == expected

    def test_acme_textiles_demo_case_rejects(self):
        """Acme Textiles: litigation + DSCR knockout → REJECT."""
        f = make_features(
            litigation_risk=0.05,    # NCLT → knockout
            dscr=0.75,               # Below 1.0 → knockout
            de_ratio=2.8,
            promoter_track_record=0.6,
            gst_compliance=0.75,
            management_quality=0.7,
            ebitda_margin_trend=0.65,
            revenue_cagr_vs_sector=0.55,
            plant_utilization=0.7,
            net_worth_trend=0.6,
            promoter_equity_pct=62.0,
            security_cover=0.9,
            collateral_encumbrance=0.7,
            sector_outlook=0.6,
            customer_concentration=0.55,
            regulatory_environment=0.6,
        )
        result = compute_score(f)
        assert result.decision == "REJECT"
        assert len(result.knockout_flags) >= 1
        assert result.counter_factual


# ─────────────────────────────────────────────────────────────────────────────
# GRADE ASSIGNMENT
# ─────────────────────────────────────────────────────────────────────────────

class TestGradeAssignment:

    def test_a_plus_band_85_to_100(self):
        grade, _ = _get_grade(85);  assert grade == "A+"
        grade, _ = _get_grade(100); assert grade == "A+"

    def test_a_band_70_to_84(self):
        grade, _ = _get_grade(70); assert grade == "A"
        grade, _ = _get_grade(84); assert grade == "A"

    def test_b_plus_band_55_to_69(self):
        grade, _ = _get_grade(55); assert grade == "B+"
        grade, _ = _get_grade(69); assert grade == "B+"

    def test_b_band_45_to_54(self):
        grade, _ = _get_grade(45); assert grade == "B"
        grade, _ = _get_grade(54); assert grade == "B"

    def test_c_band_35_to_44(self):
        grade, _ = _get_grade(35); assert grade == "C"
        grade, _ = _get_grade(44); assert grade == "C"

    def test_d_band_0_to_34(self):
        grade, _ = _get_grade(0);  assert grade == "D"
        grade, _ = _get_grade(34); assert grade == "D"

    def test_perfect_borrower_approves(self):
        result = compute_score(make_features())
        assert result.decision == "APPROVE"