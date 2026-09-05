"""Domain services: triage, ML risk, outbreak detection, alerts/SSE bus, audit."""
from __future__ import annotations

import json
import math
import queue
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import db, one, rows
from .gazetteer import DISTRICT_BY_CODE, resolve_village
from .triage_engine import assess_triage
from . import i18n

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml" / "livestock_risk_model.pkl"

_model = None
_model_err = None
try:  # optional — the app degrades gracefully without scikit-learn
    import joblib
    import pandas as pd
    _model = joblib.load(MODEL_PATH)
except Exception as e:  # pragma: no cover
    _model_err = str(e)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


# ----------------------------------------------------------------------------
# Server-Sent Events bus (fan-out to every connected dashboard)
# ----------------------------------------------------------------------------
class EventBus:
    def __init__(self):
        self._subs: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self.recent: list[dict] = []

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=200)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            self._subs.discard(q)

    def publish(self, event: str, data: dict):
        payload = {"event": event, "data": data, "ts": utcnow()}
        with self._lock:
            self.recent = ([payload] + self.recent)[:50]
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass


bus = EventBus()


def event_visible(user: dict, data: dict) -> bool:
    from .auth import scope
    s = scope(user["role"])
    if s in ("state", "lab"):
        return True
    if s == "district":
        return data.get("district_code") in (None, user.get("district_code"))
    if s == "taluka":
        return data.get("taluka_code") in (None, user.get("taluka_code")) or data.get("district_code") == user.get("district_code") and data.get("kind") == "advisory"
    return data.get("village_code") in (None, user.get("village_code")) or data.get("reporter_id") == user["id"]


# ----------------------------------------------------------------------------
# Audit
# ----------------------------------------------------------------------------
def audit(c, actor: dict | None, action: str, entity: str, entity_id: str | None, detail: dict | None = None):
    c.execute("INSERT INTO audit_log VALUES(?,?,?,?,?,?,?,?)",
              (new_id("AUD"), actor["id"] if actor else None, actor["full_name"] if actor else "system",
               action, entity, entity_id, json.dumps(detail or {}), utcnow()))


# ----------------------------------------------------------------------------
# ML: RandomForest mortality regression
# ----------------------------------------------------------------------------
def predict_deaths(outbreaks: int, susceptible: int, attacks: int, year: int | None = None) -> float | None:
    if _model is None:
        return None
    try:
        frame = pd.DataFrame([[year or datetime.now().year, outbreaks, susceptible, attacks]],
                             columns=["Year", "Outbreaks", "Susceptible", "Attacks"])
        return round(max(0.0, float(_model.predict(frame)[0])), 2)
    except Exception:
        return None


def model_status() -> dict:
    info = {"loaded": _model is not None, "path": str(MODEL_PATH.relative_to(BASE_DIR)), "error": _model_err}
    if _model is not None:
        info.update(algorithm=type(_model).__name__, n_estimators=getattr(_model, "n_estimators", None),
                    features=["Year", "Outbreaks", "Susceptible", "Attacks"], target="Deaths",
                    feature_importances=dict(zip(["Year", "Outbreaks", "Susceptible", "Attacks"],
                                                 [round(float(x), 4) for x in getattr(_model, "feature_importances_", [])])))
    return info


# ----------------------------------------------------------------------------
# Triage orchestration (rules + weather + ML + local history)
# ----------------------------------------------------------------------------
def latest_weather(c, village_code=None, taluka_code=None, district_code=None, hours=72):
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    for col, val in (("village_code", village_code), ("taluka_code", taluka_code), ("district_code", district_code)):
        if not val:
            continue
        w = one(c.execute(f"SELECT * FROM weather WHERE {col}=? AND observed_at>=? ORDER BY observed_at DESC LIMIT 1", (val, since)))
        if w:
            return w
    return None


def recent_local_activity(c, taluka_code, days=14, exclude_id=None):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    r = one(c.execute("SELECT COUNT(*) AS n, COALESCE(SUM(mortality_count),0) AS deaths, COALESCE(SUM(affected_count),0) AS attacks "
                      "FROM cases WHERE taluka_code=? AND created_at>=? AND deleted_at IS NULL AND id IS NOT ?",
                      (taluka_code, since, exclude_id)))
    return r or {"n": 0, "deaths": 0, "attacks": 0}


def run_triage(c, payload: dict, exclude_id=None) -> dict:
    """Dual-matrix triage: deterministic rules + MAHAVEDH climate + RF regression."""
    wx = latest_weather(c, payload.get("village_code"), payload.get("taluka_code"), payload.get("district_code"))
    local = recent_local_activity(c, payload.get("taluka_code"), exclude_id=exclude_id)
    report = dict(payload)
    # local incidence 0..30 feeds the rule engine's historical term
    report["local_incidence_score"] = min(30, local["n"] * 4 + local["deaths"])
    t = assess_triage(report, weather={"humidity_percent": wx["humidity"], "temperature_c": wx["temperature_c"]} if wx else None)

    herd = int(payload.get("herd_size") or 0) or max(int(payload.get("affected_count") or 0), 1) * 4
    predicted = predict_deaths(outbreaks=1 + local["n"], susceptible=herd, attacks=int(payload.get("affected_count") or 0) + local["attacks"])
    ml_band = "NONE"
    if predicted is not None:
        ml_band = "HIGH" if predicted >= 10 else "MEDIUM" if predicted >= 5 else "LOW" if predicted > 0 else "NONE"
        if ml_band == "HIGH" and t["level"] != "HIGH":
            t["probability"] = min(0.99, t["probability"] + 0.15)
            t["signals"].append("ml_high_mortality_projection")
        elif ml_band == "MEDIUM" and t["level"] == "LOW":
            t["probability"] = min(0.99, t["probability"] + 0.08)
            t["signals"].append("ml_elevated_mortality_projection")
        t["level"] = "HIGH" if t["probability"] >= 0.75 else "MEDIUM" if t["probability"] >= 0.40 else "LOW"
        t["score"] = round(t["probability"] * 100)
    t.update({
        "predicted_deaths": predicted, "ml_band": ml_band,
        "weather": {"humidity": wx["humidity"], "temperature_c": wx["temperature_c"], "rainfall_mm": wx["rainfall_mm"], "observed_at": wx["observed_at"]} if wx else None,
        "local_activity_14d": local, "engine": "dual-matrix v3 (rules + MAHAVEDH + RandomForest)",
        "explanation": explain(t, wx, local, predicted),
    })
    return t


def explain(t, wx, local, predicted) -> list[str]:
    out = [f"Symptom signature → {t['suspected_disease']} (base probability {round(t['probability'] * 100)}%)."]
    if t.get("weather_amplified"):
        out.append(f"MAHAVEDH: humidity {wx['humidity']}% and {wx['temperature_c']}°C favour vectors — +15% amplification applied.")
    elif wx:
        out.append(f"MAHAVEDH: humidity {wx['humidity']}%, {wx['temperature_c']}°C — no vector amplification.")
    else:
        out.append("No recent MAHAVEDH telemetry for this zone (climate layer skipped).")
    if local["n"]:
        out.append(f"{local['n']} other case(s) with {local['deaths']} deaths in this taluka over 14 days raise local incidence.")
    if predicted is not None:
        out.append(f"RandomForest projects ≈{predicted} deaths for this exposure profile.")
    return out


# ----------------------------------------------------------------------------
# Outbreak detection (spatio-temporal clustering)
# ----------------------------------------------------------------------------
CLUSTER_MIN_CASES = 3
CLUSTER_WINDOW_DAYS = 7


def detect_outbreaks(c, actor=None) -> list[dict]:
    """Flag a suspected outbreak when >=3 cases of the same suspected disease
    (excluding 'no signature') occur in one taluka within 7 days, or >=2 with
    any HIGH triage. Idempotent — updates an existing open signal."""
    since = (datetime.now(timezone.utc) - timedelta(days=CLUSTER_WINDOW_DAYS)).isoformat()
    groups = rows(c.execute(
        "SELECT taluka_code, district_code, suspected_disease, COUNT(*) n, SUM(mortality_count) deaths, "
        "SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) high, GROUP_CONCAT(id) ids, MIN(created_at) first "
        "FROM cases WHERE created_at>=? AND deleted_at IS NULL AND suspected_disease NOT LIKE 'No specific%' "
        "AND status NOT IN ('CASE_RESOLVED','PATHOGEN_REJECTED') GROUP BY taluka_code, suspected_disease", (since,)))
    created = []
    for g in groups:
        if not (g["n"] >= CLUSTER_MIN_CASES or (g["n"] >= 2 and g["high"] >= 1)):
            continue
        existing = one(c.execute("SELECT * FROM outbreak_signals WHERE taluka_code=? AND disease=? AND status IN ('SUSPECTED','CONFIRMED') ORDER BY detected_at DESC LIMIT 1",
                                 (g["taluka_code"], g["suspected_disease"])))
        ids = sorted(set((g["ids"] or "").split(",")))
        if existing:
            c.execute("UPDATE outbreak_signals SET case_ids=?, case_count=?, mortality=? WHERE id=?",
                      (json.dumps(ids), g["n"], g["deaths"] or 0, existing["id"]))
            continue
        sid = new_id("OB")
        c.execute("INSERT INTO outbreak_signals(id,disease,district_code,taluka_code,case_ids,case_count,mortality,status,first_reported,detected_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (sid, g["suspected_disease"], g["district_code"], g["taluka_code"], json.dumps(ids), g["n"], g["deaths"] or 0, "SUSPECTED", g["first"], utcnow()))
        sig = one(c.execute("SELECT * FROM outbreak_signals WHERE id=?", (sid,)))
        created.append(sig)
        create_alert(c, actor, kind="outbreak_suspected", severity="critical",
                     title=f"Suspected {g['suspected_disease']} cluster",
                     district_code=g["district_code"], taluka_code=g["taluka_code"], disease=g["suspected_disease"],
                     message_key="alert_cluster", fmt={"n": g["n"], "disease": g["suspected_disease"], "deaths": g["deaths"] or 0})
    return created


# ----------------------------------------------------------------------------
# Alerts (multilingual advisories)
# ----------------------------------------------------------------------------
def create_alert(c, actor, kind, severity, title, message_key=None, fmt=None, messages=None, district_code=None,
                 taluka_code=None, village_code=None, case_id=None, disease=None, radius_km=None, channels=None, expires_days=7):
    aid = new_id("AL")
    if messages is None:
        messages = {lang: i18n.render(message_key, lang, **(fmt or {})) for lang in ("en", "mr", "hi")}
    expires = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat(timespec="seconds").replace("+00:00", "Z")
    c.execute("INSERT INTO alerts(id,kind,severity,title,message_en,message_mr,message_hi,district_code,taluka_code,village_code,case_id,disease,radius_km,channels,created_by,created_by_name,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (aid, kind, severity, title, messages.get("en"), messages.get("mr"), messages.get("hi"), district_code, taluka_code,
               village_code, case_id, disease, radius_km, json.dumps(channels or ["app", "sms", "whatsapp", "ivr"]),
               actor["id"] if actor else None, actor["full_name"] if actor else "Triage engine", utcnow(), expires))
    a = one(c.execute("SELECT * FROM alerts WHERE id=?", (aid,)))
    bus.publish("alert", a)
    return a


# ----------------------------------------------------------------------------
# Case helpers
# ----------------------------------------------------------------------------
STATE_TRANSITIONS = {
    "REPORTED": {"FIELD_INSPECTED_BY_LDO", "CASE_RESOLVED"},
    "FIELD_INSPECTED_BY_LDO": {"SAMPLE_COLLECTED", "CASE_RESOLVED"},
    "SAMPLE_COLLECTED": {"LAB_TRANSIT", "CASE_RESOLVED"},
    "LAB_TRANSIT": {"LAB_RECEIVED"},
    "LAB_RECEIVED": {"PATHOGEN_CONFIRMED", "PATHOGEN_REJECTED"},
    "PATHOGEN_CONFIRMED": {"CASE_RESOLVED"},
    "PATHOGEN_REJECTED": {"CASE_RESOLVED"},
    "CASE_RESOLVED": set(),
}
TRANSITION_ROLES = {
    "FIELD_INSPECTED_BY_LDO": ("ldo", "paravet", "acah", "dcah", "state", "admin"),
    "SAMPLE_COLLECTED": ("ldo", "paravet", "acah", "dcah", "state", "admin"),
    "LAB_TRANSIT": ("ldo", "paravet", "acah", "dcah", "state", "admin"),
    "LAB_RECEIVED": ("lab", "state", "admin"),
    "PATHOGEN_CONFIRMED": ("lab", "state", "admin"),
    "PATHOGEN_REJECTED": ("lab", "state", "admin"),
    "CASE_RESOLVED": ("ldo", "acah", "dcah", "state", "admin"),
}


def hydrate_case(r: dict) -> dict:
    out = dict(r)
    for k in ("symptoms", "ear_tags", "triage"):
        if isinstance(out.get(k), str):
            try:
                out[k] = json.loads(out[k])
            except Exception:
                pass
    geo = resolve_village(out.get("village_code"))
    out["village"] = geo["village"] if geo else out.get("village_code")
    out["taluka"] = geo["taluka"] if geo else out.get("taluka_code")
    d = DISTRICT_BY_CODE.get(out.get("district_code") or "")
    out["district"] = d[1] if d else out.get("district_code")
    if out.get("lat") is None and geo:
        out["lat"], out["lng"], out["precision"] = geo["lat"], geo["lng"], "village"
    else:
        out["precision"] = "gps" if out.get("lat") is not None else "unknown"
    return out


def add_case_event(c, case_id, actor, kind, from_status=None, to_status=None, note=None):
    c.execute("INSERT INTO case_events VALUES(?,?,?,?,?,?,?,?,?)",
              (new_id("EV"), case_id, actor["id"] if actor else None, actor["full_name"] if actor else "system",
               kind, from_status, to_status, note, utcnow()))


def haversine_km(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
