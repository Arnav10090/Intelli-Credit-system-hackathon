"""
ml/generate_data.py
──────────────────────────────────────────────────────────────────────────────
Synthetic Training Data Generator for Intelli-Credit ML Model.

Generates realistic labelled credit cases based on:
  - RBI/CIBIL default rate statistics (~8–12% for MSME lending)
  - Known non-linear relationships from credit literature:
      DSCR < 1.0  → near-certain default
      D/E > 5.0   → high default risk
      Litigation  → significant default predictor
  - Realistic correlations (high D/E tends to accompany low DSCR, etc.)

Output: ml/data/training_data.csv  (5,000 cases)
         ml/data/holdout_data.csv   (1,000 cases)

Label: default = 1 (borrower defaulted within 24 months)
       default = 0 (performing loan)
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

SEED = 42
N_TRAIN = 5_000
N_HOLDOUT = 1_000
DATA_DIR = Path(__file__).parent / "data"


def generate_dataset(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # ── 1. Sample raw feature distributions ──────────────────────────────────

    # litigation_risk: most borrowers are clean, tail of distressed
    litigation_risk = np.clip(
        rng.beta(a=8, b=2, size=n),   # skewed toward 1.0 (clean)
        0.0, 1.0
    )

    # promoter_track_record
    promoter_track_record = np.clip(rng.beta(a=5, b=2, size=n), 0.0, 1.0)

    # gst_compliance: most are ≥0.7, some violators
    gst_compliance = np.clip(rng.beta(a=7, b=2, size=n), 0.0, 1.0)

    # management_quality
    management_quality = np.clip(rng.beta(a=5, b=2, size=n), 0.0, 1.0)

    # dscr: realistic range 0.5–3.5, centred around 1.5
    dscr = np.clip(
        rng.lognormal(mean=0.35, sigma=0.45, size=n),
        0.3, 4.0
    )

    # ebitda_margin_trend
    ebitda_margin_trend = np.clip(rng.beta(a=4, b=3, size=n), 0.0, 1.0)

    # revenue_cagr_vs_sector
    revenue_cagr_vs_sector = np.clip(rng.beta(a=4, b=3, size=n), 0.0, 1.0)

    # plant_utilization
    plant_utilization = np.clip(rng.beta(a=5, b=2, size=n), 0.0, 1.0)

    # de_ratio: lognormal, most in 1–3 range, heavy tail
    de_ratio = np.clip(
        rng.lognormal(mean=0.8, sigma=0.7, size=n),
        0.1, 10.0
    )

    # Introduce realistic correlation: high D/E ↔ low DSCR
    dscr = dscr - np.clip((de_ratio - 2.0) * 0.15, 0, 0.8)
    dscr = np.clip(dscr, 0.3, 4.0)

    # net_worth_trend
    net_worth_trend = np.clip(rng.beta(a=5, b=3, size=n), 0.0, 1.0)

    # promoter_equity_pct: 0–100
    promoter_equity_pct = np.clip(
        rng.normal(loc=55, scale=20, size=n),
        0.0, 100.0
    )
    # Normalise to 0–1 for model (matches ml_validator feature vector)
    promoter_equity_norm = promoter_equity_pct / 100.0

    # security_cover: 0.5–3.0
    security_cover = np.clip(
        rng.lognormal(mean=0.35, sigma=0.45, size=n),
        0.5, 3.5
    )

    # collateral_encumbrance
    collateral_encumbrance = np.clip(rng.beta(a=6, b=2, size=n), 0.0, 1.0)

    # CONDITIONS
    sector_outlook       = np.clip(rng.beta(a=4, b=3, size=n), 0.0, 1.0)
    customer_concentration = np.clip(rng.beta(a=4, b=3, size=n), 0.0, 1.0)
    regulatory_environment = np.clip(rng.beta(a=4, b=3, size=n), 0.0, 1.0)

    # ── 2. Compute default probability (ground truth) ─────────────────────────
    # Logistic model — based on credit literature weights

    log_odds = (
        -2.0                                        # intercept (~12% base rate)
        + (-4.0) * np.clip(dscr - 1.0, -1.5, 1.5)  # DSCR: most important
        + 1.5    * np.clip(de_ratio - 2.0, -2, 5)  # D/E ratio
        + (-2.5) * litigation_risk                  # Litigation (inverse)
        + (-1.5) * promoter_track_record            # Promoter quality (inverse)
        + (-1.0) * gst_compliance                   # GST compliance (inverse)
        + 0.8    * np.clip(de_ratio - 4.0, 0, 4)   # Extra penalty >4x D/E
        + (-0.8) * security_cover                   # Collateral (inverse)
        + (-0.6) * ebitda_margin_trend              # Margin trend (inverse)
        + (-0.5) * net_worth_trend                  # Net worth trend (inverse)
        + (-0.4) * customer_concentration           # Diversification (inverse)
        + rng.normal(0, 0.3, size=n)               # Idiosyncratic noise
    )

    # Hard rules matching scorecard knockouts
    # DSCR < 1.0 → near-certain default
    log_odds[dscr < 1.0] += 3.0
    # Litigation risk < 0.25 → significant risk increase
    log_odds[litigation_risk < 0.25] += 2.0
    # GST compliance = 0 → circular trading risk
    log_odds[gst_compliance < 0.05] += 2.5

    default_prob = 1 / (1 + np.exp(-log_odds))
    default_prob = np.clip(default_prob, 0.01, 0.99)

    # ── 3. Sample binary label with some noise ────────────────────────────────
    default = rng.binomial(n=1, p=default_prob).astype(int)

    # ── 4. Build DataFrame ────────────────────────────────────────────────────
    df = pd.DataFrame({
        "litigation_risk":          np.round(litigation_risk, 4),
        "promoter_track_record":    np.round(promoter_track_record, 4),
        "gst_compliance":           np.round(gst_compliance, 4),
        "management_quality":       np.round(management_quality, 4),
        "dscr":                     np.round(dscr, 4),
        "ebitda_margin_trend":      np.round(ebitda_margin_trend, 4),
        "revenue_cagr_vs_sector":   np.round(revenue_cagr_vs_sector, 4),
        "plant_utilization":        np.round(plant_utilization, 4),
        "de_ratio":                 np.round(de_ratio, 4),
        "net_worth_trend":          np.round(net_worth_trend, 4),
        "promoter_equity_pct_norm": np.round(promoter_equity_norm, 4),
        "security_cover":           np.round(security_cover, 4),
        "collateral_encumbrance":   np.round(collateral_encumbrance, 4),
        "sector_outlook":           np.round(sector_outlook, 4),
        "customer_concentration":   np.round(customer_concentration, 4),
        "regulatory_environment":   np.round(regulatory_environment, 4),
        "default_prob_true":        np.round(default_prob, 4),  # For diagnostics
        "default":                  default,
    })

    return df


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating training data...")
    train_df   = generate_dataset(N_TRAIN,   seed=SEED)
    holdout_df = generate_dataset(N_HOLDOUT, seed=SEED + 1)

    train_df.to_csv(DATA_DIR / "training_data.csv",   index=False)
    holdout_df.to_csv(DATA_DIR / "holdout_data.csv",  index=False)

    default_rate_train   = train_df["default"].mean()
    default_rate_holdout = holdout_df["default"].mean()

    print(f"✅ Training set:  {len(train_df):,} rows | default rate: {default_rate_train:.1%}")
    print(f"✅ Holdout set:   {len(holdout_df):,} rows | default rate: {default_rate_holdout:.1%}")
    print(f"   Saved to: {DATA_DIR}/")


if __name__ == "__main__":
    main()