"""
tests/test_insights_integration.py
─────────────────────────────────────────────────────────────────────────────
Integration tests for Primary Insight Integration feature.
Tests the complete flow: save insights → score case → verify adjustments applied.
─────────────────────────────────────────────────────────────────────────────
"""

import pytest
from backend.scoring.five_cs_scorer import compute_score
from backend.scoring.feature_engineer import FeatureSet


class TestScoringWithInsights:
    """Test that insights are correctly applied during scoring."""

    def test_scoring_without_insights(self):
        """Test scoring with no insights (base scoring only)."""
        features = FeatureSet(
            dscr=1.5,
            de_ratio=2.0,
            security_cover=1.5,
            litigation_risk=0.8,
            promoter_track_record=0.7,
            gst_compliance=0.9,
            management_quality=0.8,
            ebitda_margin_trend=0.7,
            revenue_cagr_vs_sector=0.6,
            plant_utilization=0.8,
            net_worth_trend=0.7,
            promoter_equity_pct=55.0,
            collateral_encumbrance=0.9,
            sector_outlook=0.8,
            customer_concentration=0.7,
            regulatory_environment=0.8,
        )
        
        result = compute_score(features, insight_adjustments=None)
        
        assert result.total_raw_score > 0
        assert result.normalised_score > 0
        assert result.insight_adjustments_applied == []

    def test_scoring_with_negative_adjustments(self):
        """Test scoring with negative insight adjustments."""
        features = FeatureSet(
            dscr=1.5,
            de_ratio=2.0,
            security_cover=1.5,
            litigation_risk=0.8,
            promoter_track_record=0.7,
            gst_compliance=0.9,
            management_quality=0.8,
            ebitda_margin_trend=0.7,
            revenue_cagr_vs_sector=0.6,
            plant_utilization=0.8,
            net_worth_trend=0.7,
            promoter_equity_pct=55.0,
            collateral_encumbrance=0.9,
            sector_outlook=0.8,
            customer_concentration=0.7,
            regulatory_environment=0.8,
        )
        
        # Get base score
        base_result = compute_score(features, insight_adjustments=None)
        base_score = base_result.total_raw_score
        
        # Apply negative adjustments
        adjustments = [
            {"pillar": "Capacity", "delta": -8, "reason": "Low capacity utilization"},
            {"pillar": "Character", "delta": -10, "reason": "Management evasiveness"},
        ]
        
        adjusted_result = compute_score(features, insight_adjustments=adjustments)
        
        # Score should be lower
        assert adjusted_result.total_raw_score < base_score
        assert adjusted_result.total_raw_score == base_score - 18
        assert len(adjusted_result.insight_adjustments_applied) == 2

    def test_scoring_with_positive_adjustments(self):
        """Test scoring with positive insight adjustments."""
        features = FeatureSet(
            dscr=1.5,
            de_ratio=2.0,
            security_cover=1.5,
            litigation_risk=0.8,
            promoter_track_record=0.7,
            gst_compliance=0.9,
            management_quality=0.8,
            ebitda_margin_trend=0.7,
            revenue_cagr_vs_sector=0.6,
            plant_utilization=0.8,
            net_worth_trend=0.7,
            promoter_equity_pct=55.0,
            collateral_encumbrance=0.9,
            sector_outlook=0.8,
            customer_concentration=0.7,
            regulatory_environment=0.8,
        )
        
        # Get base score
        base_result = compute_score(features, insight_adjustments=None)
        base_score = base_result.total_raw_score
        
        # Apply positive adjustments
        adjustments = [
            {"pillar": "Conditions", "delta": 5, "reason": "New order secured"},
            {"pillar": "Capital", "delta": 6, "reason": "Promoter infusion"},
        ]
        
        adjusted_result = compute_score(features, insight_adjustments=adjustments)
        
        # Score should be higher
        assert adjusted_result.total_raw_score > base_score
        assert adjusted_result.total_raw_score == base_score + 11
        assert len(adjusted_result.insight_adjustments_applied) == 2

    def test_bounds_enforcement_lower(self):
        """Test that adjustments cannot push score below 0."""
        features = FeatureSet(
            dscr=1.5,
            de_ratio=2.0,
            security_cover=1.5,
            litigation_risk=0.8,
            promoter_track_record=0.7,
            gst_compliance=0.9,
            management_quality=0.8,
            ebitda_margin_trend=0.7,
            revenue_cagr_vs_sector=0.6,
            plant_utilization=0.8,
            net_worth_trend=0.7,
            promoter_equity_pct=55.0,
            collateral_encumbrance=0.9,
            sector_outlook=0.8,
            customer_concentration=0.7,
            regulatory_environment=0.8,
        )
        
        # Apply massive negative adjustment
        adjustments = [
            {"pillar": "Character", "delta": -1000, "reason": "Test bounds"},
        ]
        
        result = compute_score(features, insight_adjustments=adjustments)
        
        # Character score should be 0, not negative
        assert result.character_score >= 0

    def test_bounds_enforcement_upper(self):
        """Test that adjustments cannot push score above max."""
        features = FeatureSet(
            dscr=2.5,
            de_ratio=0.5,
            security_cover=2.5,
            litigation_risk=1.0,
            promoter_track_record=1.0,
            gst_compliance=1.0,
            management_quality=1.0,
            ebitda_margin_trend=1.0,
            revenue_cagr_vs_sector=1.0,
            plant_utilization=1.0,
            net_worth_trend=1.0,
            promoter_equity_pct=75.0,
            collateral_encumbrance=1.0,
            sector_outlook=1.0,
            customer_concentration=1.0,
            regulatory_environment=1.0,
        )
        
        # Apply massive positive adjustment
        adjustments = [
            {"pillar": "Character", "delta": 1000, "reason": "Test bounds"},
        ]
        
        result = compute_score(features, insight_adjustments=adjustments)
        
        # Character score should not exceed max (60)
        assert result.character_score <= 60

    def test_adjustments_recorded_in_output(self):
        """Test that applied adjustments are recorded in the result."""
        features = FeatureSet(
            dscr=1.5,
            de_ratio=2.0,
            security_cover=1.5,
            litigation_risk=0.8,
            promoter_track_record=0.7,
            gst_compliance=0.9,
            management_quality=0.8,
            ebitda_margin_trend=0.7,
            revenue_cagr_vs_sector=0.6,
            plant_utilization=0.8,
            net_worth_trend=0.7,
            promoter_equity_pct=55.0,
            collateral_encumbrance=0.9,
            sector_outlook=0.8,
            customer_concentration=0.7,
            regulatory_environment=0.8,
        )
        
        adjustments = [
            {"pillar": "Capacity", "delta": -8, "reason": "Low capacity"},
            {"pillar": "Character", "delta": -10, "reason": "Management issues"},
        ]
        
        result = compute_score(features, insight_adjustments=adjustments)
        
        # Adjustments should be recorded
        assert result.insight_adjustments_applied == adjustments
        assert len(result.insight_adjustments_applied) == 2
        assert result.insight_adjustments_applied[0]["pillar"] == "Capacity"
        assert result.insight_adjustments_applied[0]["delta"] == -8
