"""
ml/train_model.py
──────────────────────────────────────────────────────────────────────────────
Training Script — Intelli-Credit ML Validator Model.

Model: sklearn HistGradientBoostingClassifier
  - Histogram-based gradient boosting (equivalent to XGBoost/LightGBM)
  - Handles missing values natively
  - Fast training, low memory footprint
  - Calibrated with Platt scaling for reliable probability estimates

Pipeline:
  1. Load synthetic training data (generate_data.py must run first)
  2. Hyperparameter search with 5-fold CV (RandomizedSearchCV)
  3. Train final model on full training set
  4. Calibrate with CalibratedClassifierCV (Platt/sigmoid)
  5. Evaluate on holdout set
  6. Save model + metadata to ml/models/

Output files:
  ml/models/credit_validator.joblib     ← loaded by ml_validator.py
  ml/models/feature_importances.json    ← permutation importances
  ml/models/training_report.json        ← metrics, thresholds, metadata

Usage:
  cd intelli-credit
  python ml/generate_data.py     # generates training/holdout CSVs
  python ml/train_model.py       # trains and saves the model
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
import joblib

warnings.filterwarnings("ignore", category=UserWarning)

# ── Paths ─────────────────────────────────────────────────────────────────────
ML_DIR      = Path(__file__).parent
DATA_DIR    = ML_DIR / "data"
MODELS_DIR  = ML_DIR / "models"

FEATURE_COLS = [
    "litigation_risk",
    "promoter_track_record",
    "gst_compliance",
    "management_quality",
    "dscr",
    "ebitda_margin_trend",
    "revenue_cagr_vs_sector",
    "plant_utilization",
    "de_ratio",
    "net_worth_trend",
    "promoter_equity_pct_norm",
    "security_cover",
    "collateral_encumbrance",
    "sector_outlook",
    "customer_concentration",
    "regulatory_environment",
]
TARGET_COL = "default"


# ── 1. Load Data ──────────────────────────────────────────────────────────────

def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    train_path   = DATA_DIR / "training_data.csv"
    holdout_path = DATA_DIR / "holdout_data.csv"

    if not train_path.exists():
        raise FileNotFoundError(
            f"Training data not found at {train_path}. "
            "Run `python ml/generate_data.py` first."
        )

    train_df   = pd.read_csv(train_path)
    holdout_df = pd.read_csv(holdout_path)

    print(f"Loaded training set:  {len(train_df):,} rows")
    print(f"Loaded holdout set:   {len(holdout_df):,} rows")
    print(f"Training default rate: {train_df[TARGET_COL].mean():.1%}")
    print(f"Holdout default rate:  {holdout_df[TARGET_COL].mean():.1%}")

    return train_df, holdout_df


# ── 2. Hyperparameter Search ──────────────────────────────────────────────────

def tune_hyperparameters(X_train: np.ndarray, y_train: np.ndarray) -> dict:
    print("\n── Hyperparameter search (5-fold CV, 20 iterations) ──")

    param_dist = {
        "max_iter":           [200, 300, 500],
        "max_depth":          [3, 4, 5, 6],
        "learning_rate":      [0.05, 0.08, 0.10, 0.15],
        "min_samples_leaf":   [10, 20, 30, 50],
        "l2_regularization":  [0.0, 0.1, 0.5, 1.0],
        "max_leaf_nodes":     [15, 31, 63],
        "class_weight":       ["balanced", None],
    }

    base_model = HistGradientBoostingClassifier(random_state=42, early_stopping=True)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    search = RandomizedSearchCV(
        base_model,
        param_distributions=param_dist,
        n_iter=20,
        cv=cv,
        scoring="roc_auc",
        n_jobs=-1,
        random_state=42,
        verbose=1,
    )

    t0 = time.time()
    search.fit(X_train, y_train)
    elapsed = time.time() - t0

    print(f"Best CV AUC: {search.best_score_:.4f} (found in {elapsed:.1f}s)")
    print(f"Best params: {search.best_params_}")

    return search.best_params_


# ── 3. Train Final Model ──────────────────────────────────────────────────────

def train_final_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    best_params: dict,
) -> CalibratedClassifierCV:
    print("\n── Training final model with best params ──")

    final_model = HistGradientBoostingClassifier(
        random_state=42,
        early_stopping=False,   # Use full iterations for final model
        **best_params,
    )

    # Calibrate with Platt scaling (sigmoid) for reliable probabilities
    calibrated = CalibratedClassifierCV(
        estimator=final_model,
        method="sigmoid",
        cv=5,
    )
    calibrated.fit(X_train, y_train)

    print("✅ Model trained and calibrated")
    return calibrated


# ── 4. Evaluate on Holdout ────────────────────────────────────────────────────

def evaluate_model(
    model: CalibratedClassifierCV,
    X_holdout: np.ndarray,
    y_holdout: np.ndarray,
    feature_names: list[str],
) -> dict:
    print("\n── Holdout evaluation ──")

    probs  = model.predict_proba(X_holdout)[:, 1]
    preds  = (probs >= 0.45).astype(int)

    auc    = roc_auc_score(y_holdout, probs)
    ap     = average_precision_score(y_holdout, probs)
    brier  = brier_score_loss(y_holdout, probs)
    f1     = f1_score(y_holdout, preds)
    cm     = confusion_matrix(y_holdout, preds)

    print(f"  ROC-AUC:                {auc:.4f}")
    print(f"  Average Precision (AP): {ap:.4f}")
    print(f"  Brier Score:            {brier:.4f}  (lower = better; 0.25 = random)")
    print(f"  F1 @ threshold 0.45:    {f1:.4f}")
    print(f"  Confusion matrix:\n{cm}")
    print(f"\n{classification_report(y_holdout, preds, target_names=['Performing','Default'])}")

    # Optimal threshold by F1
    precisions, recalls, thresholds = precision_recall_curve(y_holdout, probs)
    f1_scores  = 2 * precisions * recalls / (precisions + recalls + 1e-9)
    best_idx   = np.argmax(f1_scores)
    best_thr   = float(thresholds[best_idx]) if best_idx < len(thresholds) else 0.45
    best_f1    = float(f1_scores[best_idx])
    print(f"  Optimal threshold (F1): {best_thr:.3f}  →  F1 = {best_f1:.4f}")

    # Calibration check
    fraction_pos, mean_pred = calibration_curve(y_holdout, probs, n_bins=10)
    calibration_gap = float(np.mean(np.abs(fraction_pos - mean_pred)))
    print(f"  Calibration gap (ECE):  {calibration_gap:.4f}  (lower = better)")

    # Permutation importances on holdout
    print("\n── Computing permutation feature importances ──")
    perm = permutation_importance(
        model, X_holdout, y_holdout,
        n_repeats=10, random_state=42, scoring="roc_auc", n_jobs=-1
    )
    importance_dict = {
        name: round(float(mean), 5)
        for name, mean in zip(feature_names, perm.importances_mean)
    }
    sorted_importances = dict(
        sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
    )
    print("  Top 8 features by permutation importance:")
    for feat, imp in list(sorted_importances.items())[:8]:
        bar = "█" * int(imp * 500)
        print(f"    {feat:<30} {imp:+.5f}  {bar}")

    return {
        "roc_auc":            round(auc, 4),
        "average_precision":  round(ap, 4),
        "brier_score":        round(brier, 4),
        "f1_at_0_45":        round(f1, 4),
        "optimal_threshold":  round(best_thr, 3),
        "optimal_f1":        round(best_f1, 4),
        "calibration_ece":   round(calibration_gap, 4),
        "confusion_matrix":  cm.tolist(),
        "feature_importances": sorted_importances,
        "n_holdout":          int(len(y_holdout)),
        "default_rate_holdout": round(float(y_holdout.mean()), 4),
    }


# ── 5. Save Artefacts ─────────────────────────────────────────────────────────

def save_artefacts(
    model:        CalibratedClassifierCV,
    best_params:  dict,
    metrics:      dict,
    feature_names: list[str],
) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Model
    model_path = MODELS_DIR / "credit_validator.joblib"
    joblib.dump(model, model_path)
    print(f"\n✅ Model saved → {model_path}")

    # Feature importances
    fi_path = MODELS_DIR / "feature_importances.json"
    with open(fi_path, "w") as f:
        json.dump(metrics["feature_importances"], f, indent=2)
    print(f"✅ Feature importances → {fi_path}")

    # Full training report
    report = {
        "model_class":        "sklearn.ensemble.HistGradientBoostingClassifier",
        "calibration_method": "Platt sigmoid (CalibratedClassifierCV, cv=5)",
        "feature_names":      feature_names,
        "n_features":         len(feature_names),
        "best_hyperparams":   best_params,
        "holdout_metrics":    {k: v for k, v in metrics.items()
                               if k != "feature_importances"},
        "decision_threshold": 0.45,
        "note": (
            "HistGradientBoostingClassifier is sklearn's histogram-based "
            "gradient boosting — equivalent in architecture to XGBoost. "
            "Calibrated probabilities can be used directly as default_probability."
        ),
    }
    report_path = MODELS_DIR / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"✅ Training report  → {report_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Intelli-Credit ML Model Training")
    print("=" * 60)

    # Load
    train_df, holdout_df = load_data()
    X_train   = train_df[FEATURE_COLS].values
    y_train   = train_df[TARGET_COL].values
    X_holdout = holdout_df[FEATURE_COLS].values
    y_holdout = holdout_df[TARGET_COL].values

    # Tune
    best_params = tune_hyperparameters(X_train, y_train)

    # Train
    model = train_final_model(X_train, y_train, best_params)

    # Evaluate
    metrics = evaluate_model(model, X_holdout, y_holdout, FEATURE_COLS)

    # Save
    save_artefacts(model, best_params, metrics, FEATURE_COLS)

    print("\n" + "=" * 60)
    print(f"  Training complete.")
    print(f"  ROC-AUC: {metrics['roc_auc']:.4f}  |  "
          f"Brier: {metrics['brier_score']:.4f}  |  "
          f"AP: {metrics['average_precision']:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()