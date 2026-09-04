"""Explainable deterministic triage with a replaceable statistical interface."""
def _normalise(values): return {str(v).strip().lower() for v in values or []}
def historical_classifier_stub(report):
    """Future local model contract; returns a 0..30 historical-risk contribution."""
    return min(30, int(report.get("local_incidence_score", 0) or 0))
def assess_triage(report):
    symptoms = _normalise(report.get("symptoms")); anomalies = _normalise(report.get("physical_anomalies"))
    temp = float(report.get("temperature_f", 0) or 0); deaths = int(report.get("mortality_count", 0) or 0)
    score, signals = historical_classifier_stub(report), []
    if temp > 104 and ({"skin nodules", "nodules", "skin_nodules"} & (symptoms | anomalies)):
        score += 65; signals.append("Lumpy Skin Disease rule: fever above 104°F with skin nodules")
    if {"sudden death", "bloody discharge", "blood discharge"} & symptoms:
        score += 55; signals.append("Anthrax-compatible symptom pattern")
    if deaths >= 3: score += 35; signals.append(f"Elevated mortality: {deaths}")
    elif deaths: score += 15; signals.append(f"Mortality reported: {deaths}")
    score = min(score, 100); level = "HIGH" if score >= 60 else "MEDIUM" if score >= 30 else "LOW"
    return {"score": score, "level": level, "signals": signals, "engine": "rules-v1+statistical-stub"}
