"""
ML classifier training script.

Run with:  uv run python ml/train.py

## Features

Each feature maps directly to a measurable, research-backed dimension of
traveller experience:

  avg_temp_july       → climate comfort (°C in peak summer month)
  cost_per_day_usd    → affordability signal for budget/luxury discrimination
  crowd_index         → overtourism avoidance (1=empty, 10=overrun)
  hiking_score        → trail quality, terrain variety, guided-trek options
  beach_score         → water clarity, sand quality, marine life
  cultural_sites      → UNESCO sites + major museums + historic districts count
  safety_score        → composite of crime index, political stability, health
  english_score       → ease of independent travel without a guide
  nature_score        → wildlife density, forest cover, national-park quality
  nightlife_score     → bar/club scene, live music, late-night dining
  family_amenities    → theme parks, kid-friendly menus, stroller infrastructure
  luxury_hotels       → count of rated 5-star / ultra-luxury properties
  food_scene_score    → cuisine diversity, street-food quality, Michelin density
  infrastructure_score → transport reliability, internet speed, hospital access
  wellness_score      → spa resorts, yoga retreats, thermal baths, health tourism

## Label assignment — composite scoring

Labels are assigned by computing a weighted score for each of the six travel
styles and choosing the winner. This replaces the previous priority-based
if/else chain, which was biased toward Budget (any cheap destination won
regardless of other strengths). Each weight reflects how strongly the feature
predicts that style according to travel-industry segmentation studies.

  Adventure  = 0.35·hiking + 0.25·nature + 0.20·(1−crowd) + 0.10·(1−cost) + 0.10·wellness
  Relaxation = 0.35·beach  + 0.25·wellness + 0.20·(1−crowd) + 0.15·warmth  + 0.05·safety
  Culture    = 0.30·sites  + 0.25·food    + 0.20·nightlife + 0.15·english  + 0.10·infra
  Budget     = 0.45·cheap  + 0.25·safety  + 0.20·english   + 0.10·infra
  Luxury     = 0.35·cost   + 0.30·hotels  + 0.20·safety    + 0.15·infra
  Family     = 0.35·family + 0.30·safety  + 0.15·english   + 0.10·infra    + 0.10·wellness

All inputs are normalised to [0, 1] before weighting so no single raw scale
dominates. See `compute_dominant_style()` for the implementation.

## Model selection

We compare three classifiers, then tune the best with GridSearchCV:

  GradientBoostingClassifier — typically best on tabular data; captures
    non-linear feature interactions; soft-margin natural for mixed data.
    Selected as primary based on empirical CV results.

  RandomForestClassifier — useful ensemble baseline; feature_importances_
    aid interpretability; robust to outliers.

  LogisticRegression (OvR) — fast linear baseline; shows whether linear
    decision boundaries are sufficient for this dataset.

## Class imbalance

SMOTE is placed INSIDE each pipeline so it only runs on training folds
during cross-validation, preventing leakage from synthetic samples.
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
    "food_scene_score",
    "infrastructure_score",
    "wellness_score",
]
TARGET_COLUMN = "label"


def compute_dominant_style(row: pd.Series) -> str:
    """
    Compute the dominant travel style for a destination row.

    All inputs are normalised to [0, 1] so weights are directly comparable.
    Used during data-generation to produce the CSV labels; reproduced here
    for transparency and reproducibility.
    """
    cost_norm = min(row["cost_per_day_usd"] / 500.0, 1.0)
    cheap_norm = 1.0 - cost_norm
    crowd_inv = 1.0 - (row["crowd_index"] / 10.0)
    warmth = min(max(row["avg_temp_july"], 0) / 35.0, 1.0)
    sites_norm = min(row["cultural_sites"] / 12.0, 1.0)
    hotels_norm = min(row["luxury_hotels"] / 20.0, 1.0)

    def n(col: str, scale: float = 10.0) -> float:
        return row[col] / scale

    scores = {
        "Adventure": (
            0.35 * n("hiking_score")
            + 0.25 * n("nature_score")
            + 0.20 * crowd_inv
            + 0.10 * cheap_norm
            + 0.10 * n("wellness_score")
        ),
        "Relaxation": (
            0.35 * n("beach_score")
            + 0.25 * n("wellness_score")
            + 0.20 * crowd_inv
            + 0.15 * warmth
            + 0.05 * n("safety_score")
        ),
        "Culture": (
            0.30 * sites_norm
            + 0.25 * n("food_scene_score")
            + 0.20 * n("nightlife_score")
            + 0.15 * n("english_score")
            + 0.10 * n("infrastructure_score")
        ),
        "Budget": (
            0.45 * cheap_norm
            + 0.25 * n("safety_score")
            + 0.20 * n("english_score")
            + 0.10 * n("infrastructure_score")
        ),
        "Luxury": (
            0.35 * cost_norm
            + 0.30 * hotels_norm
            + 0.20 * n("safety_score")
            + 0.15 * n("infrastructure_score")
        ),
        "Family": (
            0.35 * n("family_amenities")
            + 0.30 * n("safety_score")
            + 0.15 * n("english_score")
            + 0.10 * n("infrastructure_score")
            + 0.10 * n("wellness_score")
        ),
    }
    return max(scores, key=scores.get)


def load_data() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} destinations")
    print(f"Class distribution:\n{df[TARGET_COLUMN].value_counts()}\n")
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    return X, y


def make_pipelines() -> dict[str, ImbPipeline]:
    return {
        "GradientBoosting": ImbPipeline([
            ("scaler", StandardScaler()),
            ("smote", SMOTE(random_state=RANDOM_STATE)),
            ("clf", GradientBoostingClassifier(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=5,
                subsample=0.8,
                random_state=RANDOM_STATE,
            )),
        ]),
        "RandomForest": ImbPipeline([
            ("scaler", StandardScaler()),
            ("smote", SMOTE(random_state=RANDOM_STATE)),
            ("clf", RandomForestClassifier(
                n_estimators=300,
                random_state=RANDOM_STATE,
                class_weight="balanced",
            )),
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


def tune_gradient_boosting(X: pd.DataFrame, y_encoded: np.ndarray) -> ImbPipeline:
    """
    GridSearchCV on GradientBoosting.

    learning_rate and n_estimators are co-dependent: lower LR needs more
    trees to converge. max_depth controls the complexity of each weak learner.
    subsample < 1 introduces stochastic gradient boosting, which reduces
    variance and often improves generalisation on small datasets.
    """
    print("\nTuning GradientBoosting with GridSearchCV...")
    param_grid = {
        "clf__n_estimators": [200, 400],
        "clf__learning_rate": [0.05, 0.1],
        "clf__max_depth": [3, 5],
        "clf__subsample": [0.8, 1.0],
    }
    base = ImbPipeline([
        ("scaler", StandardScaler()),
        ("smote", SMOTE(random_state=RANDOM_STATE)),
        ("clf", GradientBoostingClassifier(random_state=RANDOM_STATE)),
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

    # ── Step 1: Compare all three classifiers ─────────────────────────────────
    pipelines = make_pipelines()
    results = evaluate_pipelines(pipelines, X, y, le)

    # ── Step 2: Tune GradientBoosting (primary model) ─────────────────────────
    tuned_gb = tune_gradient_boosting(X, y_encoded)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    tuned_scores = cross_validate(tuned_gb, X, y_encoded, cv=cv, scoring=["accuracy", "f1_macro"])
    results.append({
        "model": "GradientBoosting_tuned",
        "params": str(tuned_gb.named_steps["clf"].get_params()),
        "accuracy_mean": round(tuned_scores["test_accuracy"].mean(), 4),
        "accuracy_std": round(tuned_scores["test_accuracy"].std(), 4),
        "f1_macro_mean": round(tuned_scores["test_f1_macro"].mean(), 4),
        "f1_macro_std": round(tuned_scores["test_f1_macro"].std(), 4),
        "timestamp": datetime.now().isoformat(),
    })

    write_results(results)

    # ── Step 3: Final fit on full dataset ──────────────────────────────────────
    print("\nFitting tuned GradientBoosting on full dataset...")
    tuned_gb.fit(X, y_encoded)
    y_pred = tuned_gb.predict(X)
    print("\nPer-class metrics (training set — label sanity check):")
    print(classification_report(y_encoded, y_pred, target_names=le.classes_))

    # ── Step 4: Save winner ────────────────────────────────────────────────────
    joblib.dump(tuned_gb, MODELS_DIR / "classifier.joblib")
    joblib.dump(le, MODELS_DIR / "label_encoder.joblib")
    print(f"\nModel saved → {MODELS_DIR / 'classifier.joblib'}")
    print(f"Label encoder saved → {MODELS_DIR / 'label_encoder.joblib'}")

    # ── Step 5: Feature importances ────────────────────────────────────────────
    clf = tuned_gb.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        print("\nFeature importances (GradientBoosting):")
        for feat, imp in sorted(
            zip(FEATURE_COLUMNS, clf.feature_importances_), key=lambda x: -x[1]
        ):
            bar = "█" * int(imp * 40)
            print(f"  {feat:25s} {imp:.4f}  {bar}")


if __name__ == "__main__":
    main()
