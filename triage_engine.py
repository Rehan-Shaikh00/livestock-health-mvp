"""Dual-layer, explainable triage engine.

Layer A — deterministic pathogen signatures: fixed symptom combinations map to
a suspected disease with a seed outbreak probability (0..1).
Layer B — environmental amplification: if recent local weather is favourable to
vectors (humidity > 80% and 25-35 C within 72h), vector-borne diseases (LSD,
Haemorrhagic Septicaemia) get a +15% risk coefficient.

The compiled probability is mapped back onto the legacy 0..100 `score` /
`level` contract so existing callers (save_case, dashboards) are unaffected.
Escalation (SSE priority alert on P>=0.75) is performed by the caller
(save_case in app.py), which holds the case + assigned officer context; this
module stays a pure function.
"""

VECTOR_BORNE = {"Lumpy Skin Disease", "Haemorrhagic Septicaemia"}
WEATHER_COEFFICIENT = 1.15  # +15% amplification for vector-borne under favourable weather
HIGH_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.40


def _normalise(values):
    return {str(v).strip().lower().replace("_", " ") for v in values or []}


def historical_classifier_stub(report):
    """Future local model contract; returns a 0..30 historical-risk contribution."""
    return min(30, int(report.get("local_incidence_score", 0) or 0))


def _pathogen_signatures(symptoms):
    """Layer A. Return (suspected_disease, probability, signals[]) for the
    strongest matching deterministic signature, else a low-probability default."""
    has = lambda *needed: all(any(n in s for s in symptoms) for n in needed)
    # Ordered most-specific / highest-probability first.
    if has("high fever", "foot lesion") and (has("frothy salivation") or has("salivation")):
        return "Foot and Mouth Disease", 0.95, ["fmd_signature"]
    if has("high fever") and has("skin nodule"):
        return "Lumpy Skin Disease", 0.90, ["lsd_signature"]
    if has("sudden death") and (has("bloody discharge") or has("blood discharge")):
        return "Anthrax", 0.85, ["anthrax_signature"]
    if has("high fever") and has("respiratory distress"):
        return "Haemorrhagic Septicaemia", 0.70, ["hs_signature"]
    return "No specific pathogen signature", 0.20, []


def _weather_favourable(weather):
    """Layer B gate: humidity > 80% and 25 <= temp <= 35 (within the caller's
    72h window). `weather` is a dict with humidity_percent / temperature_c, or
    None when no recent telemetry exists."""
    if not weather:
        return False
    try:
        humidity = float(weather.get("humidity_percent", weather.get("humidity", 0)) or 0)
        temp = float(weather.get("temperature_c", weather.get("temperature", 0)) or 0)
    except (TypeError, ValueError):
        return False
    return humidity > 80 and 25 <= temp <= 35


def assess_triage(report, weather=None):
    """Compile a triage assessment.

    report: the case payload (symptoms[], physical_anomalies[], mortality_count,
            temperature_f, ...).
    weather: optional latest local weather dict for the report's zone; when
             provided and favourable it amplifies vector-borne probability.

    Returns the legacy contract (score 0..100, level, signals, engine) plus the
    new fields (probability, suspected_disease, weather_amplified, coefficient).
    """
    symptoms = _normalise(report.get("symptoms")) | _normalise(report.get("physical_anomalies"))
    deaths = int(report.get("mortality_count", 0) or 0)

    disease, probability, signals = _pathogen_signatures(symptoms)

    # Layer B: environmental amplification for vector-borne diseases.
    amplified = False
    coefficient = 1.0
    if disease in VECTOR_BORNE and _weather_favourable(weather):
        probability = min(0.99, round(probability * WEATHER_COEFFICIENT, 4))
        amplified = True
        coefficient = WEATHER_COEFFICIENT
        signals.append("weather_amplified_vector_risk")

    # Mortality is an independent escalator: many dead animals raise probability
    # even without a clean signature match.
    if deaths >= 3:
        probability = min(0.99, probability + 0.15); signals.append("high_mortality")
    elif deaths:
        probability = min(0.99, probability + 0.05); signals.append("mortality_reported")

    # Blend a small historical-incidence contribution (0..30 -> 0..0.15).
    probability = min(0.99, probability + historical_classifier_stub(report) / 200.0)

    level = "HIGH" if probability >= HIGH_THRESHOLD else "MEDIUM" if probability >= MEDIUM_THRESHOLD else "LOW"
    score = round(probability * 100)

    return {
        "score": score,
        "level": level,
        "probability": round(probability, 4),
        "suspected_disease": disease,
        "signals": signals,
        "weather_amplified": amplified,
        "weather_coefficient": coefficient,
        "engine": "rules-v2+weather-correlated",
    }
