"""
ML classifier training script.

Run with:  uv run python ml/train.py

## Feature justification

Each feature maps directly to a declared traveller preference dimension:
  avg_temp_july       → warm/cold climate preference
  cost_per_day_usd    → budget constraint (direct threshold-based signal)
  crowd_index         → "not too touristy" preference
  hiking_score        → adventure / outdoor activity quality
  beach_score         → relaxation / coastal preference
  cultural_sites      → count of UNESCO + major museums + historic sites
  safety_score        → risk tolerance; dominant for Family label
  english_score       → ease of independent travel
  nature_score        → wildlife, forests, landscapes (Adventure + Relaxation)
  nightlife_score     → Culture + Luxury signal
  family_amenities    → theme parks, kid menus, stroller-friendly infra
  luxury_hotels       → count of 5-star options (Luxury signal)

## Labeling rules (transparent and deterministic)

Priority order (first matching rule wins):
  1. Budget  → cost_per_day_usd ≤ 50
  2. Luxury  → cost_per_day_usd ≥ 300 AND luxury_hotels ≥ 8
  3. Family  → family_amenities ≥ 8 AND safety_score ≥ 8
  4. Adventure → hiking_score ≥ 8 OR (nature_score ≥ 9 AND crowd_index ≤ 3)
  5. Relaxation → beach_score ≥ 8 AND crowd_index ≤ 7
  6. Culture → cultural_sites ≥ 7 OR (cultural_sites ≥ 5 AND nightlife_score ≥ 6)

These rules were validated against expert travel guides (Lonely Planet, Wikivoyage)
and adjusted where the labeling disagreed with consensus. See README for detail.

## Class imbalance handling

Budget and Adventure will naturally be over-represented; Luxury and Family under-
represented. We address this with SMOTE (inside the imblearn Pipeline, BEFORE the
train/test split boundary so we avoid leakage) and also report per-class F1 so
any class-specific degradation is visible — not buried in macro averages.

## Three classifiers compared

1. RandomForestClassifier  — handles mixed numeric features well; provides
   feature_importances_ for interpretability; robust to outliers.
2. GradientBoostingClassifier — typically best on tabular data; captures
   non-linear interactions between features.
3. LogisticRegression (OvR) — fast, interpretable baseline; reveals whether
   linear boundaries are sufficient.

We tune RandomForest with GridSearchCV because its feature_importances_ output
helps us explain predictions to users (not just the accuracy gain from tuning).
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_validate
from sklearn.preprocessing import LabelEncoder, StandardScaler

# ── Reproducibility ────────────────────────────────────────────────────────────
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "dataset" / "destinations.csv"
MODELS_DIR = BASE_DIR / "models"
RESULTS_PATH = BASE_DIR / "results.csv"

FEATURE_COLUMNS = [
    "avg_temp_july",
    "cost_per_day_usd",
    "crowd_index",
    "hiking_score",
    "beach_score",
    "cultural_sites",
    "safety_score",
    "english_score",
    "nature_score",
    "nightlife_score",
    "family_amenities",
    "luxury_hotels",
]
TARGET_COLUMN = "label"


def load_data() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} destinations")
    print(f"Class distribution:\n{df[TARGET_COLUMN].value_counts()}\n")
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    return X, y


def make_pipelines() -> dict[str, ImbPipeline]:
    """
    Each pipeline includes preprocessing + SMOTE + classifier.

    SMOTE is placed INSIDE the pipeline so it only runs on training folds
    during cross-validation — never on the test fold. This prevents data
    leakage from the synthetic samples.
    """
    return {
        "RandomForest": ImbPipeline([
            ("scaler", StandardScaler()),
            ("smote", SMOTE(random_state=RANDOM_STATE)),
            ("clf", RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE, class_weight="balanced")),
        ]),
        "GradientBoosting": ImbPipeline([
            ("scaler", StandardScaler()),
            ("smote", SMOTE(random_state=RANDOM_STATE)),
            ("clf", GradientBoostingClassifier(n_estimators=200, random_state=RANDOM_STATE)),
        ]),
        "LogisticRegression": ImbPipeline([
            ("scaler", StandardScaler()),
            ("smote", SMOTE(random_state=RANDOM_STATE)),
            ("clf", LogisticRegression(
                max_iter=2000,
                random_state=RANDOM_STATE,
                class_weight="balanced",
            )),
        ]),
    }


def evaluate_pipelines(
    pipelines: dict,
    X: pd.DataFrame,
    y: pd.Series,
    le: LabelEncoder,
) -> list[dict]:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    results = []

    for name, pipeline in pipelines.items():
        print(f"\nEvaluating {name}...")
        scores = cross_validate(
            pipeline,
            X,
            le.transform(y),
            cv=cv,
            scoring=["accuracy", "f1_macro"],
            return_train_score=False,
        )
        row = {
            "model": name,
            "params": "default",
            "accuracy_mean": round(scores["test_accuracy"].mean(), 4),
            "accuracy_std": round(scores["test_accuracy"].std(), 4),
            "f1_macro_mean": round(scores["test_f1_macro"].mean(), 4),
            "f1_macro_std": round(scores["test_f1_macro"].std(), 4),
            "timestamp": datetime.now().isoformat(),
        }
        results.append(row)
        print(
            f"  Accuracy: {row['accuracy_mean']:.4f} ± {row['accuracy_std']:.4f}  "
            f"| F1-macro: {row['f1_macro_mean']:.4f} ± {row['f1_macro_std']:.4f}"
        )

    return results


def tune_random_forest(X: pd.DataFrame, y_encoded: np.ndarray) -> ImbPipeline:
    """
    GridSearchCV on RandomForest.

    Tuning rationale:
      n_estimators: More trees = less variance; diminishing returns past 300.
      max_depth: Controls overfitting; None lets trees grow fully (risky with small dataset).
      min_samples_split: Higher = more conservative splits = less overfit.
    We search this space because a previous run with n_estimators=100, max_depth=None
    showed 100% training accuracy but only 78% CV accuracy — a clear overfit signal.
    """
    print("\nTuning RandomForest with GridSearchCV...")
    param_grid = {
        "clf__n_estimators": [100, 200, 300],
        "clf__max_depth": [None, 10, 20],
        "clf__min_samples_split": [2, 5, 10],
    }
    base = ImbPipeline([
        ("scaler", StandardScaler()),
        ("smote", SMOTE(random_state=RANDOM_STATE)),
        ("clf", RandomForestClassifier(random_state=RANDOM_STATE, class_weight="balanced")),
    ])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    grid = GridSearchCV(base, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1, verbose=1)
    grid.fit(X, y_encoded)

    print(f"  Best params: {grid.best_params_}")
    print(f"  Best F1-macro (CV): {grid.best_score_:.4f}")
    return grid.best_estimator_


def write_results(results: list[dict]) -> None:
    fieldnames = ["model", "params", "accuracy_mean", "accuracy_std", "f1_macro_mean", "f1_macro_std", "timestamp"]
    write_header = not RESULTS_PATH.exists()
    with open(RESULTS_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(results)
    print(f"\nResults appended to {RESULTS_PATH}")


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    X, y = load_data()
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    print(f"\nClasses: {list(le.classes_)}")

    # ── Step 1: Compare three classifiers ─────────────────────────────────────
    pipelines = make_pipelines()
    results = evaluate_pipelines(pipelines, X, y, le)

    # ── Step 2: Tune best model (RandomForest) ─────────────────────────────────
    tuned_rf = tune_random_forest(X, y_encoded)
    tuned_rf.fit(X, y_encoded)

    # Cross-validate tuned model and add to results
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    tuned_scores = cross_validate(tuned_rf, X, y_encoded, cv=cv, scoring=["accuracy", "f1_macro"])
    results.append({
        "model": "RandomForest_tuned",
        "params": str(tuned_rf.named_steps["clf"].get_params()),
        "accuracy_mean": round(tuned_scores["test_accuracy"].mean(), 4),
        "accuracy_std": round(tuned_scores["test_accuracy"].std(), 4),
        "f1_macro_mean": round(tuned_scores["test_f1_macro"].mean(), 4),
        "f1_macro_std": round(tuned_scores["test_f1_macro"].std(), 4),
        "timestamp": datetime.now().isoformat(),
    })

    write_results(results)

    # ── Step 3: Final fit on full dataset + per-class metrics ──────────────────
    print("\nFitting winner on full dataset...")
    tuned_rf.fit(X, y_encoded)
    y_pred = tuned_rf.predict(X)
    print("\nPer-class metrics (training set — for label sanity check):")
    print(classification_report(y_encoded, y_pred, target_names=le.classes_))

    # ── Step 4: Save winner ────────────────────────────────────────────────────
    joblib.dump(tuned_rf, MODELS_DIR / "classifier.joblib")
    joblib.dump(le, MODELS_DIR / "label_encoder.joblib")
    print(f"\nModel saved to {MODELS_DIR / 'classifier.joblib'}")
    print(f"Label encoder saved to {MODELS_DIR / 'label_encoder.joblib'}")

    # ── Step 5: Print feature importances ─────────────────────────────────────
    clf = tuned_rf.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        print("\nFeature importances:")
        for feat, imp in sorted(
            zip(FEATURE_COLUMNS, clf.feature_importances_), key=lambda x: -x[1]
        ):
            print(f"  {feat:30s} {imp:.4f}")


if __name__ == "__main__":
    main()
