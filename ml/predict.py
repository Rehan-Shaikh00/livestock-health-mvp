"""Inference helper for the livestock mortality-risk model.

Mirrors the feature contract defined in ml/train_model.py:
    features = ["Year", "Outbreaks", "Susceptible", "Attacks"]  ->  target "Deaths"

The Flask app loads the model directly, but this module gives a clean,
testable boundary (and a CLI) for scoring records outside the request path.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "livestock_risk_model.pkl"
FEATURES = ["Year", "Outbreaks", "Susceptible", "Attacks"]

_model = None


def load_model(path: Path | str = MODEL_PATH):
    """Load and memoise the trained RandomForestRegressor."""
    global _model
    if _model is None:
        _model = joblib.load(path)
    return _model


def predict_deaths(year: int, outbreaks: int, susceptible: int, attacks: int) -> float:
    """Predict expected deaths for a single district-year observation.

    Returns a non-negative float rounded to 2 decimals.
    """
    model = load_model()
    frame = pd.DataFrame([[year, outbreaks, susceptible, attacks]], columns=FEATURES)
    prediction = float(model.predict(frame)[0])
    return round(max(0.0, prediction), 2)


def risk_band(predicted_deaths: float) -> str:
    """Map predicted deaths to a Low / Medium / High band for the UI."""
    if predicted_deaths >= 10:
        return "HIGH"
    if predicted_deaths >= 5:
        return "MEDIUM"
    if predicted_deaths > 0:
        return "LOW"
    return "NONE"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Predict livestock mortality risk.")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--outbreaks", type=int, required=True)
    parser.add_argument("--susceptible", type=int, required=True)
    parser.add_argument("--attacks", type=int, required=True)
    args = parser.parse_args()

    deaths = predict_deaths(args.year, args.outbreaks, args.susceptible, args.attacks)
    print(f"Predicted deaths: {deaths}  ->  risk band: {risk_band(deaths)}")
