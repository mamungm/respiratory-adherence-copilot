"""
Synthetic training cohort generator for the adherence risk classifier.

The live demo dataset (data-generator/generate_data.py) only has 12 patients
-- realistic for a small pilot dashboard, but far too few to train a
classifier on. This script generates a much larger population (default
3,000) directly at the *feature* level (adherence_rate,
missed_dose_max_streak, dose_interval_variance, technique_error_rate) --
the same four features etl/etl.py computes from raw dose events -- plus a
simulated binary outcome label standing in for a real clinical event (e.g.
an exacerbation or unplanned care visit) that isn't available to this
project.

The label is generated from a logistic function of the features plus
independent noise, so it is learnable but not perfectly separable --
similar to what a real adherence -> outcome relationship looks like.
This is explicitly a stand-in: swap in real labeled outcomes data once
available and train_classifier.py does not need to change.

Usage:
    python ml/train/simulate_training_cohort.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(7)
N_PATIENTS = 3000

OUT_PATH = Path(__file__).resolve().parent / "training_data.csv"


def simulate_features(n: int) -> pd.DataFrame:
    adherence_rate = np.clip(RNG.beta(5, 2, n), 0, 1)  # skewed toward adherent
    missed_dose_max_streak = np.clip(
        RNG.gamma(shape=1.5, scale=4, size=n) * (1.2 - adherence_rate), 0, 60
    ).round().astype(int)
    dose_interval_variance = np.clip(RNG.gamma(shape=2.0, scale=800, size=n), 0, 8000)
    technique_error_rate = np.clip(
        RNG.beta(1.5, 6, n) + (1 - adherence_rate) * 0.15, 0, 1
    )

    return pd.DataFrame(
        {
            "adherence_rate": adherence_rate.round(4),
            "missed_dose_max_streak": missed_dose_max_streak,
            "dose_interval_variance": dose_interval_variance.round(2),
            "technique_error_rate": technique_error_rate.round(4),
        }
    )


def simulate_labels(features: pd.DataFrame) -> np.ndarray:
    logit = (
        -3.2
        + 4.5 * (1 - features["adherence_rate"])
        + 0.10 * features["missed_dose_max_streak"]
        + 2.0 * features["technique_error_rate"]
        + 0.0003 * features["dose_interval_variance"]
        + RNG.normal(0, 0.6, len(features))  # unobserved factors / noise
    )
    prob = 1 / (1 + np.exp(-logit))
    return (RNG.random(len(features)) < prob).astype(int)


def main():
    features = simulate_features(N_PATIENTS)
    features["adverse_event"] = simulate_labels(features)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(OUT_PATH, index=False)

    rate = features["adverse_event"].mean()
    print(f"Wrote {len(features)} simulated patients to {OUT_PATH}")
    print(f"Positive class (adverse_event) rate: {rate:.1%}")


if __name__ == "__main__":
    main()
