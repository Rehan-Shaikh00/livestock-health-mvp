"""Pashu Arogya — animal-health surveillance & decision-support API.

Run:  python -m server.app   (or: flask --app server.app run)
Serves the REST/SSE API under /api/v1 and, when client/dist exists, the built
React SPA for every other path.
"""
from __future__ import annotations

import json
import os
import queue
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, Response, g, jsonify, request, send_from_directory

from . import barcode, i18n
from .auth import (CLINICAL_ROLES, DISTRICT_PLUS, ROLES, STATE_ROLES, can_access_row, hash_password, issue_token,
                   public_user, require_auth, scope, scope_clause, verify_password)
from .db import db, init_schema, one, rows
from .gazetteer import DISTRICTS, DISTRICT_BY_CODE, TALUKAS, TALUKA_BY_CODE, VILLAGES, resolve_village
from .services import (STATE_TRANSITIONS, TRANSITION_ROLES, add_case_event, audit, bus, create_alert, detect_outbreaks,
                       event_visible, haversine_km, hydrate_case, model_status, new_id, now_ms, predict_deaths, run_triage, utcnow)
from .spatial import nearest_clinics as spatial_nearest
from .seed import seed_if_empty

BASE_DIR = Path(__file__).resolve().parent.parent
DIST = BASE_DIR / "client" / "dist"
EAR_TAG_RE = re.compile(r"^\d{12}$")

app = Flask(__name__, static_folder=None)
app.config["JSON_SORT_KEYS"] = False


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def body() -> dict:
    return request.get_json(silent=True) or {}


def err(msg, code=400, **extra):
    return jsonify(error=msg, **extra), code


def lang():
    q = request.args.get("lang") or request.headers.get("X-Lang")
    if q:
        return i18n.normalise(q)
    u = getattr(g, "user", None)
    return i18n.normalise(u["language"] if u else "en")


def enrich_geo(p: dict, user: dict | None = None):
    """Fill taluka/district from the LGD village code (or the user's profile)."""
    geo = resolve_village(p.get("village_code"))
    if geo:
        p.setdefault("taluka_code", geo["taluka_code"]); p.setdefault("district_code", geo["district_code"])
        p["taluka_code"] = p["taluka_code"] or geo["taluka_code"]; p["district_code"] = p["district_code"] or geo["district_code"]
    elif user:
        p["village_code"] = p.get("village_code") or user.get("village_code")
        p["taluka_code"] = p.get("taluka_code") or user.get("taluka_code")
        p["district_code"] = p.get("district_code") or user.get("district_code")
        geo = resolve_village(p.get("village_code"))
        if geo:
            p["taluka_code"] = p["taluka_code"] or geo["taluka_code"]; p["district_code"] = p["district_code"] or geo["district_code"]
    return p


def paginate(sql, params, c, page_size_default=25):
    page = max(1, int(request.args.get("page", 1) or 1))
    size = min(200, max(1, int(request.args.get("page_size", page_size_default) or page_size_default)))
    total = one(c.execute(f"SELECT COUNT(*) AS n FROM ({sql})", params))["n"]
    items = rows(c.execute(sql + " LIMIT ? OFFSET ?", (*params, size, (page - 1) * size)))
    return items, {"page": page, "page_size": size, "total": total, "pages": (total + size - 1) // size}


# ----------------------------------------------------------------------------
# health / meta
# ----------------------------------------------------------------------------
@app.get("/api/v1/health")
def health():
    with db() as c:
        n = one(c.execute("SELECT COUNT(*) n FROM cases"))["n"]
    return jsonify(status="ok", time=utcnow(), cases=n, model=model_status()["loaded"], spatial_backend="postgis" if os.getenv("DATABASE_URL") else "sqlite+haversine")


@app.get("/api/v1/meta")
def meta():
    return jsonify(
        roles=ROLES, languages=i18n.LANGUAGES,
        symptoms=sorted({"high fever", "fever", "skin nodules", "foot lesions", "frothy salivation", "salivation", "lameness", "sudden death",
                         "bloody discharge", "respiratory distress", "swelling of throat", "nasal discharge", "coughing", "diarrhea",
                         "loss of appetite", "weakness", "reduced milk yield", "abortion", "bloat", "difficulty breathing"}),
        species=["cattle", "buffalo", "goat", "sheep", "poultry", "pig"],
        statuses=list(STATE_TRANSITIONS.keys()), transitions={k: sorted(v) for k, v in STATE_TRANSITIONS.items()},
        channels=["web", "mobile", "whatsapp", "ivr"],
        ui=i18n.TRANSLATIONS, states=i18n.STATES, diseases=i18n.DISEASES, advisory=i18n.ADVISORY, symptom_terms=i18n.SYMPTOMS,
    )


@app.get("/api/v1/geo/gazetteer")
def gazetteer():
    return jsonify(
        districts=[{"code": d[0], "name": d[1], "name_mr": d[2], "name_hi": d[3], "lat": d[4], "lng": d[5], "region": d[6]} for d in DISTRICTS],
        talukas=[{"code": t[0], "district_code": t[1], "name": t[2], "lat": t[3], "lng": t[4]} for t in TALUKAS],
        villages=[{"code": v[0], "taluka_code": v[1], "district_code": TALUKA_BY_CODE[v[1]][1], "name": v[2], "lat": v[3], "lng": v[4], "livestock_population": v[5]} for v in VILLAGES],
    )


# ----------------------------------------------------------------------------
# auth
# ----------------------------------------------------------------------------
@app.post("/api/v1/auth/login")
def login():
    b = body()
    with db() as c:
        u = one(c.execute("SELECT * FROM users WHERE username=? AND active=1", ((b.get("username") or "").strip().lower(),)))
    if not u or not verify_password(b.get("password") or "", u["password_hash"]):
        return err("invalid username or password", 401)
    return jsonify(token=issue_token(u), user=public_user(u))


@app.get("/api/v1/auth/me")
@require_auth()
def me():
    return jsonify(user=public_user(g.user))


@app.patch("/api/v1/auth/me")
@require_auth()
def update_me():
    b = body()
    fields = {k: b[k] for k in ("language", "full_name", "phone") if k in b}
    if "language" in fields:
        fields["language"] = i18n.normalise(fields["language"])
    if b.get("password"):
        fields["password_hash"] = hash_password(b["password"])
    if not fields:
        return err("nothing to update")
    with db() as c:
        c.execute(f"UPDATE users SET {', '.join(f'{k}=?' for k in fields)}, updated_at=? WHERE id=?", (*fields.values(), utcnow(), g.user["id"]))
        u = one(c.execute("SELECT * FROM users WHERE id=?", (g.user["id"],)))
    return jsonify(user=public_user(u))


@app.get("/api/v1/auth/demo-accounts")
def demo_accounts():
    return jsonify(accounts=[
        {"username": "farmer1", "role": "farmer", "label": "Ramesh Patil · Farmer, Wagholi"},
        {"username": "sakhi1", "role": "pashu_sakhi", "label": "Sunita Jadhav · Pashu Sakhi, Wagholi"},
        {"username": "paravet1", "role": "paravet", "label": "Sachin More · Paravet, Haveli"},
        {"username": "ldo1", "role": "ldo", "label": "Dr. Anjali Deshmukh · LDO, Haveli"},
        {"username": "acah1", "role": "acah", "label": "Dr. Prakash Shinde · ACAH, Pune"},
        {"username": "dcah1", "role": "dcah", "label": "Dr. Meera Kulkarni · DCAH, Pune"},
        {"username": "state1", "role": "state", "label": "Commissioner AH · Pune HQ"},
        {"username": "lab1", "role": "lab", "label": "Dr. Nilesh Kale · DIS Pune"},
        {"username": "admin", "role": "admin", "label": "System Administrator"},
    ], password="1234")


# ----------------------------------------------------------------------------
# users (admin / district management)
# ----------------------------------------------------------------------------
@app.get("/api/v1/users")
@require_auth(*DISTRICT_PLUS, "ldo")
def list_users():
    clause, params = scope_clause(g.user, reporter_col=None)
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM users WHERE 1=1" + clause
    if q:
        sql += " AND (full_name LIKE ? OR username LIKE ? OR phone LIKE ?)"; params = (*params, f"%{q}%", f"%{q}%", f"%{q}%")
    if request.args.get("role"):
        sql += " AND role=?"; params = (*params, request.args["role"])
    sql += " ORDER BY created_at DESC"
    with db() as c:
        items, page = paginate(sql, params, c, 50)
    return jsonify(items=[public_user(u) for u in items], **page)


@app.post("/api/v1/users")
@require_auth(*DISTRICT_PLUS)
def create_user():
    b = body()
    for f in ("username", "password", "full_name", "role"):
        if not b.get(f):
            return err(f"{f} is required")
    if b["role"] not in ROLES:
        return err("unknown role")
    if scope(g.user["role"]) == "district":
        if b["role"] in STATE_ROLES:
            return err("district officers cannot create state-level accounts", 403)
        b["district_code"] = g.user["district_code"]
    enrich_geo(b)
    uid = new_id("U")
    with db() as c:
        if one(c.execute("SELECT 1 FROM users WHERE username=?", (b["username"].lower(),))):
            return err("username already exists", 409)
        c.execute("INSERT INTO users(id,username,password_hash,full_name,role,phone,language,district_code,taluka_code,village_code,lab_id,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                  (uid, b["username"].lower(), hash_password(b["password"]), b["full_name"], b["role"], b.get("phone"), i18n.normalise(b.get("language", "en")),
                   b.get("district_code"), b.get("taluka_code"), b.get("village_code"), b.get("lab_id"), utcnow(), utcnow()))
        audit(c, g.user, "create", "user", uid, {"role": b["role"]})
        u = one(c.execute("SELECT * FROM users WHERE id=?", (uid,)))
    return jsonify(user=public_user(u)), 201


@app.route("/api/v1/users/<uid>", methods=["PATCH", "DELETE"])
@require_auth(*DISTRICT_PLUS)
def modify_user(uid):
    with db() as c:
        u = one(c.execute("SELECT * FROM users WHERE id=?", (uid,)))
        if not u:
            return err("not found", 404)
        if scope(g.user["role"]) == "district" and u["district_code"] != g.user["district_code"]:
            return err("outside your jurisdiction", 403)
        if request.method == "DELETE":
            if uid == g.user["id"]:
                return err("cannot deactivate yourself")
            c.execute("UPDATE users SET active=0, updated_at=? WHERE id=?", (utcnow(), uid))
            audit(c, g.user, "deactivate", "user", uid)
            return jsonify(ok=True)
        b = body(); fields = {}
        for k in ("full_name", "phone", "language", "role", "district_code", "taluka_code", "village_code", "active", "lab_id"):
            if k in b:
                fields[k] = b[k]
        if b.get("password"):
            fields["password_hash"] = hash_password(b["password"])
        if not fields:
            return err("nothing to update")
        c.execute(f"UPDATE users SET {', '.join(f'{k}=?' for k in fields)}, updated_at=? WHERE id=?", (*fields.values(), utcnow(), uid))
        audit(c, g.user, "update", "user", uid, {"fields": list(fields)})
        u = one(c.execute("SELECT * FROM users WHERE id=?", (uid,)))
    return jsonify(user=public_user(u))


# ----------------------------------------------------------------------------
# cases (multi-channel capture + CRUD + workflow)
# ----------------------------------------------------------------------------
def save_case(c, p: dict, channel: str, actor: dict, case_id: str | None = None):
    """Create or update (LWW) a case, run triage, emit events. Returns (case, error)."""
    enrich_geo(p, actor)
    if not p.get("species"):
        return None, "species is required"
    symptoms = p.get("symptoms") or []
    if isinstance(symptoms, str):
        symptoms = [s.strip() for s in re.split(r"[,;|]", symptoms) if s.strip()]
    if not symptoms and not int(p.get("mortality_count") or 0):
        return None, "at least one symptom or a mortality count is required"
    tags = p.get("ear_tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,\s]+", tags) if t.strip()]
    for t in tags:
        if not EAR_TAG_RE.fullmatch(str(t)):
            return None, f"ear tag '{t}' must be exactly 12 digits (Bharat Pashudhan format)"
    if not p.get("village_code"):
        return None, "village_code (LGD) is required"
    cid = case_id or p.get("id") or new_id("MH")
    client_ts = int(p.get("updated_at") or 0)
    old = one(c.execute("SELECT * FROM cases WHERE id=?", (cid,)))
    if old and client_ts and client_ts <= old["updated_at"]:
        return hydrate_case(old) | {"conflict": "stale_write_ignored"}, None
    triage_in = {"species": p["species"], "symptoms": symptoms, "herd_size": p.get("herd_size"), "affected_count": p.get("affected_count"),
                 "mortality_count": p.get("mortality_count"), "village_code": p["village_code"], "taluka_code": p.get("taluka_code"), "district_code": p.get("district_code")}
    triage = run_triage(c, triage_in, exclude_id=cid)
    ts = utcnow()
    vals = dict(reporter_id=old["reporter_id"] if old else actor["id"], reporter_name=old["reporter_name"] if old else actor["full_name"],
                channel=channel if not old else old["channel"], species=p["species"], herd_size=int(p.get("herd_size") or 0),
                affected_count=int(p.get("affected_count") or 0), mortality_count=int(p.get("mortality_count") or 0), symptoms=json.dumps(symptoms),
                onset_date=p.get("onset_date"), duration_days=p.get("duration_days"), notes=p.get("notes"), ear_tags=json.dumps(tags),
                village_code=p["village_code"], taluka_code=p.get("taluka_code"), district_code=p.get("district_code"),
                lat=float(p["lat"]) if p.get("lat") not in (None, "") else None, lng=float(p["lng"]) if p.get("lng") not in (None, "") else None,
                status=old["status"] if old else "REPORTED", triage=json.dumps(triage), suspected_disease=triage["suspected_disease"],
                risk_level=triage["level"], risk_score=triage["score"], predicted_deaths=triage.get("predicted_deaths"),
                assigned_to=p.get("assigned_to", old["assigned_to"] if old else None), device_id=p.get("device_id"),
                created_at=old["created_at"] if old else ts, updated_at=max(client_ts, now_ms()))
    if old:
        c.execute(f"UPDATE cases SET {', '.join(f'{k}=?' for k in vals)} WHERE id=?", (*vals.values(), cid))
        add_case_event(c, cid, actor, "updated", note="Report details updated; triage re-run")
    else:
        c.execute(f"INSERT INTO cases(id,{','.join(vals)}) VALUES(?,{','.join('?' * len(vals))})", (cid, *vals.values()))
        add_case_event(c, cid, actor, "created", None, "REPORTED", f"Reported via {channel}")
    case = hydrate_case(one(c.execute("SELECT * FROM cases WHERE id=?", (cid,))))
    bus.publish("case_created" if not old else "case_updated", {k: case.get(k) for k in ("id", "risk_level", "suspected_disease", "village", "village_code", "taluka_code", "district_code", "reporter_id", "channel", "mortality_count")})
    if triage["level"] == "HIGH" and not old:
        create_alert(c, None, "high_triage", "critical", f"High-risk {triage['suspected_disease']} report — {case['village']}",
                     message_key="alert_high_triage", fmt={"disease": triage["suspected_disease"], "village": case["village"]},
                     district_code=case["district_code"], taluka_code=case["taluka_code"], village_code=case["village_code"], case_id=cid, disease=triage["suspected_disease"])
        bus.publish("priority_alert", {"case_id": cid, "risk_level": "HIGH", "suspected_disease": triage["suspected_disease"], "village": case["village"],
                                       "district_code": case["district_code"], "taluka_code": case["taluka_code"], "village_code": case["village_code"], "reporter_id": case["reporter_id"]})
    for s in detect_outbreaks(c, actor):
        bus.publish("outbreak_suspected", s)
    return case, None


@app.get("/api/v1/cases")
@require_auth()
def list_cases():
    clause, params = scope_clause(g.user)
    if g.user["role"] == "lab":
        clause, params = " AND id IN (SELECT case_id FROM lab_referrals WHERE lab_id=?)", (g.user["lab_id"],)
    sql = "SELECT * FROM cases WHERE deleted_at IS NULL" + clause
    a = request.args
    for col in ("status", "risk_level", "species", "channel", "district_code", "taluka_code", "village_code", "suspected_disease", "assigned_to"):
        if a.get(col):
            sql += f" AND {col}=?"; params = (*params, a[col])
    if a.get("open") == "1":
        sql += " AND status NOT IN ('CASE_RESOLVED','PATHOGEN_REJECTED')"
    if a.get("since"):
        sql += " AND created_at>=?"; params = (*params, a["since"])
    if a.get("q"):
        sql += " AND (id LIKE ? OR reporter_name LIKE ? OR suspected_disease LIKE ? OR village_code LIKE ?)"; params = (*params, *([f"%{a['q']}%"] * 4))
    sql += " ORDER BY created_at DESC"
    with db() as c:
        items, page = paginate(sql, params, c)
    return jsonify(items=[hydrate_case(r) for r in items], **page)


@app.post("/api/v1/cases")
@app.post("/api/v1/reports/web")
@require_auth()
def create_case():
    with db() as c:
        case, e = save_case(c, body(), body().get("channel", "web"), g.user)
        if e:
            return err(e)
        audit(c, g.user, "create", "case", case["id"], {"channel": case["channel"], "risk": case["risk_level"]})
    return jsonify(case=case, advisory=i18n.engine.advisory_for(case["risk_level"], lang())), 201


@app.post("/api/v1/triage/preview")
@require_auth()
def triage_preview():
    p = enrich_geo(body(), g.user)
    with db() as c:
        t = run_triage(c, p)
    return jsonify(triage=t, advisory=i18n.engine.advisory_for(t["level"], lang()))


@app.get("/api/v1/cases/<cid>")
@require_auth()
def get_case(cid):
    with db() as c:
        r = one(c.execute("SELECT * FROM cases WHERE id=? AND deleted_at IS NULL", (cid,)))
        if not r:
            return err("not found", 404)
        if g.user["role"] == "lab":
            ok = one(c.execute("SELECT 1 FROM lab_referrals WHERE case_id=? AND lab_id=?", (cid, g.user["lab_id"])))
        else:
            ok = can_access_row(g.user, r)
        if not ok:
            return err("forbidden: outside your jurisdiction", 403)
        case = hydrate_case(r)
        case["events"] = rows(c.execute("SELECT * FROM case_events WHERE case_id=? ORDER BY created_at", (cid,)))
        case["referrals"] = [dict(x, chain=json.loads(x["chain"] or "[]")) for x in rows(c.execute("SELECT r.*, l.name AS lab_name, l.code AS lab_code FROM lab_referrals r LEFT JOIN labs l ON l.id=r.lab_id WHERE case_id=? ORDER BY created_at", (cid,)))]
        case["treatments"] = rows(c.execute("SELECT t.*, a.ear_tag FROM treatments t JOIN animals a ON a.id=t.animal_id WHERE t.case_id=? ORDER BY treated_on DESC", (cid,)))
        if case.get("ear_tags"):
            case["animals"] = rows(c.execute(f"SELECT id, ear_tag, species, breed, owner_name, status FROM animals WHERE ear_tag IN ({','.join('?' * len(case['ear_tags']))})", tuple(case["ear_tags"])))
        if case.get("assigned_to"):
            a = one(c.execute("SELECT full_name, phone, role FROM users WHERE id=?", (case["assigned_to"],)))
            case["assignee"] = a
        nearby = rows(c.execute("SELECT id, suspected_disease, risk_level, status, created_at, village_code, mortality_count FROM cases WHERE taluka_code=? AND id!=? AND deleted_at IS NULL AND created_at>=? ORDER BY created_at DESC LIMIT 8",
                                (r["taluka_code"], cid, (datetime.now(timezone.utc) - timedelta(days=14)).isoformat())))
        case["nearby_cases"] = [hydrate_case(x) for x in nearby]
        case["allowed_transitions"] = sorted(t for t in STATE_TRANSITIONS.get(case["status"], set()) if g.user["role"] in TRANSITION_ROLES.get(t, ()))
    case["advisory"] = i18n.engine.advisory_for(case["risk_level"], lang())
    return jsonify(case=case)


@app.route("/api/v1/cases/<cid>", methods=["PUT", "PATCH"])
@require_auth()
def update_case(cid):
    with db() as c:
        r = one(c.execute("SELECT * FROM cases WHERE id=? AND deleted_at IS NULL", (cid,)))
        if not r:
            return err("not found", 404)
        if not can_access_row(g.user, r):
            return err("forbidden", 403)
        if r["status"] != "REPORTED" and g.user["role"] in ("farmer", "pashu_sakhi"):
            return err("report can no longer be edited once inspected", 409)
        merged = dict(r); merged["symptoms"] = json.loads(r["symptoms"] or "[]"); merged["ear_tags"] = json.loads(r["ear_tags"] or "[]")
        merged.update(body()); merged.pop("triage", None); merged.pop("updated_at", None)
        case, e = save_case(c, merged, r["channel"], g.user, case_id=cid)
        if e:
            return err(e)
        audit(c, g.user, "update", "case", cid)
    return jsonify(case=case)


@app.delete("/api/v1/cases/<cid>")
@require_auth()
def delete_case(cid):
    with db() as c:
        r = one(c.execute("SELECT * FROM cases WHERE id=? AND deleted_at IS NULL", (cid,)))
        if not r:
            return err("not found", 404)
        if not (g.user["role"] in DISTRICT_PLUS or (r["reporter_id"] == g.user["id"] and r["status"] == "REPORTED")):
            return err("forbidden", 403)
        c.execute("UPDATE cases SET deleted_at=? WHERE id=?", (utcnow(), cid))
        audit(c, g.user, "delete", "case", cid)
    return jsonify(ok=True)


@app.post("/api/v1/cases/<cid>/transition")
@require_auth()
def transition(cid):
    b = body(); to = b.get("to")
    with db() as c:
        r = one(c.execute("SELECT * FROM cases WHERE id=? AND deleted_at IS NULL", (cid,)))
        if not r:
            return err("not found", 404)
        if not can_access_row(g.user, r) and g.user["role"] != "lab":
            return err("forbidden", 403)
        if to not in STATE_TRANSITIONS.get(r["status"], set()):
            return err(f"invalid transition {r['status']} → {to}", 409, allowed=sorted(STATE_TRANSITIONS.get(r["status"], set())))
        if g.user["role"] not in TRANSITION_ROLES.get(to, ()):
            return err(f"role {g.user['role']} may not perform {to}", 403)
        assigned = r["assigned_to"] or (g.user["id"] if g.user["role"] in ("ldo", "paravet") else None)
        c.execute("UPDATE cases SET status=?, assigned_to=?, updated_at=? WHERE id=?", (to, assigned, now_ms(), cid))
        add_case_event(c, cid, g.user, "transition", r["status"], to, b.get("note"))
        audit(c, g.user, "transition", "case", cid, {"from": r["status"], "to": to})
        case = hydrate_case(one(c.execute("SELECT * FROM cases WHERE id=?", (cid,))))
        bus.publish("case_updated", {k: case.get(k) for k in ("id", "status", "risk_level", "village", "district_code", "taluka_code", "village_code", "reporter_id")})
        if to == "CASE_RESOLVED":
            detect_outbreaks(c, g.user)
    return jsonify(case=case)


@app.post("/api/v1/cases/<cid>/assign")
@require_auth(*CLINICAL_ROLES)
def assign_case(cid):
    uid = body().get("user_id") or g.user["id"]
    with db() as c:
        r = one(c.execute("SELECT * FROM cases WHERE id=? AND deleted_at IS NULL", (cid,)))
        if not r or not can_access_row(g.user, r):
            return err("not found", 404)
        u = one(c.execute("SELECT full_name FROM users WHERE id=?", (uid,)))
        c.execute("UPDATE cases SET assigned_to=?, updated_at=? WHERE id=?", (uid, now_ms(), cid))
        add_case_event(c, cid, g.user, "assigned", note=f"Assigned to {u['full_name'] if u else uid}")
        case = hydrate_case(one(c.execute("SELECT * FROM cases WHERE id=?", (cid,))))
    return jsonify(case=case)


# ---- offline batch sync (LWW) ----------------------------------------------
@app.post("/api/v1/reports/mobile/sync")
@require_auth()
def mobile_sync():
    b = body(); reports = b.get("reports") or b.get("records") or []
    device = b.get("device_id") or request.headers.get("X-Device-Id")
    results, applied, stale, rejected = [], 0, 0, 0
    with db() as c:
        for rep in reports:
            rep = dict(rep); rep.setdefault("device_id", device)
            local_id = rep.pop("local_id", None)
            case, e = save_case(c, rep, "mobile", g.user)
            if e:
                rejected += 1; results.append({"local_id": local_id, "status": "rejected", "error": e})
            elif case.get("conflict"):
                stale += 1; results.append({"local_id": local_id, "id": case["id"], "status": "stale_ignored", "server_updated_at": case["updated_at"]})
            else:
                applied += 1; results.append({"local_id": local_id, "id": case["id"], "status": "applied", "risk_level": case["risk_level"], "suspected_disease": case["suspected_disease"]})
        c.execute("INSERT INTO sync_log VALUES(?,?,?,?,?,?,?,?)", (new_id("SY"), device, g.user["id"], len(reports), applied, stale, rejected, utcnow()))
    return jsonify(received=len(reports), applied=applied, stale=stale, rejected=rejected, results=results, conflict_policy="last-write-wins(updated_at)")


@app.get("/api/v1/sync/log")
@require_auth(*CLINICAL_ROLES)
def sync_log():
    with db() as c:
        return jsonify(items=rows(c.execute("SELECT s.*, u.full_name FROM sync_log s LEFT JOIN users u ON u.id=s.user_id ORDER BY created_at DESC LIMIT 50")))


# ---- IVR / WhatsApp webhooks -----------------------------------------------
IVR_SPECIES = {"1": "cattle", "2": "buffalo", "3": "goat", "4": "sheep", "5": "poultry"}
IVR_SYMPTOMS = {"1": "high fever", "2": "skin nodules", "3": "foot lesions", "4": "respiratory distress", "5": "diarrhea", "6": "sudden death", "7": "loss of appetite"}


def _phone_user(c, phone):
    digits = re.sub(r"\D", "", phone or "")[-10:]
    if not digits:
        return None
    return one(c.execute("SELECT * FROM users WHERE REPLACE(REPLACE(phone,'-',''),'+','') LIKE ? AND active=1", (f"%{digits}",)))


@app.post("/webhooks/ivr")
def ivr_webhook():
    """Telephony provider posts DTMF digits: species, symptoms (multi-digit), affected, deaths."""
    b = body()
    with db() as c:
        u = _phone_user(c, b.get("caller")) or one(c.execute("SELECT * FROM users WHERE username='sakhi1'"))
        digits = str(b.get("digits") or "")
        species = IVR_SPECIES.get(b.get("species") or digits[:1], "cattle")
        symptoms = [IVR_SYMPTOMS[d] for d in str(b.get("symptoms") or digits[1:3]) if d in IVR_SYMPTOMS]
        p = {"species": species, "symptoms": symptoms, "affected_count": int(b.get("affected") or 1), "mortality_count": int(b.get("deaths") or 0),
             "village_code": b.get("village_code") or u["village_code"], "notes": f"IVR call from {b.get('caller', 'unknown')}"}
        case, e = save_case(c, p, "ivr", u)
        c.execute("INSERT INTO channel_log VALUES(?,?,?,?,?,?,?,?,?)", (new_id("CH"), "ivr", "inbound", b.get("caller"), json.dumps(b), case["id"] if case else None, u["id"], json.dumps({"lang": u["language"]}), utcnow()))
        if e:
            return err(e)
    l = u["language"]
    return jsonify(case_id=case["id"], risk_level=case["risk_level"], tts=i18n.engine.advisory_for(case["risk_level"], l), language=l, say_case_id=" ".join(case["id"][-6:]))


WA_RE = re.compile(r"^(?:report|अहवाल|रिपोर्ट)\s+(\w+)\s+(\d{6})\s+(.+)$", re.I)


@app.post("/webhooks/whatsapp")
def whatsapp_webhook():
    """Free-text: `REPORT <species> <village_code> <symptom, symptom> [deaths=N] [affected=N]`."""
    b = body(); text = (b.get("text") or b.get("Body") or "").strip(); sender = b.get("from") or b.get("From")
    with db() as c:
        u = _phone_user(c, sender) or one(c.execute("SELECT * FROM users WHERE username='sakhi1'"))
        m = WA_RE.match(text)
        if not m:
            reply = ("Format: REPORT <species> <village LGD code> <symptoms separated by comma> deaths=N affected=N\n"
                     "e.g. REPORT cattle 556325 high fever, skin nodules deaths=1 affected=3")
            c.execute("INSERT INTO channel_log VALUES(?,?,?,?,?,?,?,?,?)", (new_id("CH"), "whatsapp", "inbound", sender, text, None, u["id"], json.dumps({"parsed": False}), utcnow()))
            return jsonify(reply=reply, parsed=False)
        species, village, rest = m.group(1).lower(), m.group(2), m.group(3)
        kv = dict(re.findall(r"(deaths|affected|herd)\s*=\s*(\d+)", rest, re.I))
        sym_text = re.sub(r"(deaths|affected|herd)\s*=\s*\d+", "", rest, flags=re.I)
        symptoms = [s.strip().replace("_", " ") for s in re.split(r"[,;]", sym_text) if s.strip()]
        p = {"species": species, "symptoms": symptoms, "village_code": village, "mortality_count": int(kv.get("deaths", 0)),
             "affected_count": int(kv.get("affected", 1)), "herd_size": int(kv.get("herd", 0)), "notes": f"WhatsApp from {sender}"}
        case, e = save_case(c, p, "whatsapp", u)
        c.execute("INSERT INTO channel_log VALUES(?,?,?,?,?,?,?,?,?)", (new_id("CH"), "whatsapp", "inbound", sender, text, case["id"] if case else None, u["id"], json.dumps({"parsed": True, "error": e}), utcnow()))
        if e:
            return jsonify(reply=f"Could not file report: {e}", parsed=True, error=e), 400
    l = u["language"]
    reply = f"✅ {case['id']}\n{i18n.engine.term(case['risk_level'], l)} · {i18n.engine.term(case['suspected_disease'], l)}\n{i18n.engine.advisory_for(case['risk_level'], l)}"
    return jsonify(reply=reply, parsed=True, case_id=case["id"], risk_level=case["risk_level"])


@app.get("/api/v1/channels/log")
@require_auth(*CLINICAL_ROLES)
def channel_log():
    clause, params = scope_clause(g.user, alias="c")
    where = f" AND (c.id IS NULL OR ({clause[5:]}))" if clause else ""
    with db() as c:
        return jsonify(items=rows(c.execute("SELECT l.*, c.risk_level, c.suspected_disease, c.village_code FROM channel_log l LEFT JOIN cases c ON c.id=l.case_id WHERE 1=1" + where + " ORDER BY l.created_at DESC LIMIT 100", params)))


# ----------------------------------------------------------------------------
# lab referrals / sample chain of custody
# ----------------------------------------------------------------------------
@app.get("/api/v1/labs")
@require_auth()
def labs():
    with db() as c:
        return jsonify(items=rows(c.execute("SELECT l.*, (SELECT COUNT(*) FROM lab_referrals r WHERE r.lab_id=l.id AND r.status IN ('IN_TRANSIT','RECEIVED')) AS pending FROM labs l ORDER BY tier, name")))


@app.get("/api/v1/lab-referrals")
@require_auth()
def list_referrals():
    a = request.args
    if g.user["role"] == "lab":
        clause, params = " AND r.lab_id=?", (g.user["lab_id"],)
    else:
        clause, params = scope_clause(g.user, alias="c", reporter_col="reporter_id")
    sql = ("SELECT r.*, l.name AS lab_name, l.code AS lab_code, c.suspected_disease, c.risk_level, c.species, c.village_code, c.district_code, c.taluka_code, c.status AS case_status "
           "FROM lab_referrals r JOIN cases c ON c.id=r.case_id LEFT JOIN labs l ON l.id=r.lab_id WHERE c.deleted_at IS NULL" + clause)
    for col in ("status", "priority", "result"):
        if a.get(col):
            sql += f" AND r.{col}=?"; params = (*params, a[col])
    if a.get("q"):
        sql += " AND (r.barcode LIKE ? OR r.case_id LIKE ?)"; params = (*params, f"%{a['q']}%", f"%{a['q']}%")
    sql += " ORDER BY CASE r.priority WHEN 'urgent' THEN 0 ELSE 1 END, r.created_at DESC"
    with db() as c:
        items, page = paginate(sql, params, c)
    for it in items:
        it["chain"] = json.loads(it["chain"] or "[]"); geo = resolve_village(it["village_code"]); it["village"] = geo["village"] if geo else it["village_code"]
    return jsonify(items=items, **page)


@app.post("/api/v1/cases/<cid>/lab-referrals")
@require_auth(*CLINICAL_ROLES)
def create_referral(cid):
    b = body()
    with db() as c:
        r = one(c.execute("SELECT * FROM cases WHERE id=? AND deleted_at IS NULL", (cid,)))
        if not r or not can_access_row(g.user, r):
            return err("case not found", 404)
        if not b.get("sample_type"):
            return err("sample_type is required")
        lab_id = b.get("lab_id")
        if not lab_id:  # nearest lab by district, else state referral lab
            lab = one(c.execute("SELECT id FROM labs WHERE district_code=? LIMIT 1", (r["district_code"],))) or one(c.execute("SELECT id FROM labs WHERE tier='state'"))
            lab_id = lab["id"]
        code, sig = barcode.generate(r["district_code"])
        rid = new_id("LR"); ts = utcnow()
        chain = [{"at": ts, "by": g.user["full_name"], "event": "Sample collected & barcode issued", "location": "field"}]
        c.execute("INSERT INTO lab_referrals(id,case_id,barcode,signature,sample_type,transport_media,cold_chain_ok,lab_id,collected_by,collected_by_name,collected_at,priority,status,test_requested,chain,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (rid, cid, code, sig, b["sample_type"], b.get("transport_media"), 1 if b.get("cold_chain_ok", True) else 0, lab_id, g.user["id"], g.user["full_name"], ts,
                   b.get("priority", "urgent" if r["risk_level"] == "HIGH" else "routine"), "COLLECTED", b.get("test_requested"), json.dumps(chain), ts, ts))
        if r["status"] in ("REPORTED", "FIELD_INSPECTED_BY_LDO"):
            if r["status"] == "REPORTED":
                add_case_event(c, cid, g.user, "transition", "REPORTED", "FIELD_INSPECTED_BY_LDO", "Auto: inspected during sample collection")
            c.execute("UPDATE cases SET status='SAMPLE_COLLECTED', assigned_to=COALESCE(assigned_to,?), updated_at=? WHERE id=?", (g.user["id"], now_ms(), cid))
            add_case_event(c, cid, g.user, "transition", r["status"] if r["status"] != "REPORTED" else "FIELD_INSPECTED_BY_LDO", "SAMPLE_COLLECTED", f"Sample {code}")
        add_case_event(c, cid, g.user, "sample", note=f"Sample {code} ({b['sample_type']}) referred")
        audit(c, g.user, "create", "lab_referral", rid, {"case": cid, "barcode": code})
        ref = one(c.execute("SELECT r.*, l.name AS lab_name, l.code AS lab_code FROM lab_referrals r LEFT JOIN labs l ON l.id=r.lab_id WHERE r.id=?", (rid,)))
    ref["chain"] = json.loads(ref["chain"])
    bus.publish("sample_collected", {"referral_id": rid, "case_id": cid, "barcode": code, "district_code": r["district_code"], "taluka_code": r["taluka_code"], "village_code": r["village_code"]})
    return jsonify(referral=ref), 201


@app.get("/api/v1/lab-referrals/<rid>/barcode.svg")
def referral_barcode(rid):
    with db() as c:
        ref = one(c.execute("SELECT barcode, signature FROM lab_referrals WHERE id=?", (rid,)))
    if not ref:
        return err("not found", 404)
    return Response(barcode.code128_svg(f"{ref['barcode']}-{ref['signature']}", label=f"{ref['barcode']} ✓{ref['signature']}"), mimetype="image/svg+xml")


@app.post("/api/v1/lab-referrals/verify")
@require_auth()
def verify_barcode():
    b = body(); raw = (b.get("scan") or "").strip().upper()
    code, _, sig = raw.rpartition("-") if raw.count("-") >= 4 else (b.get("barcode", "").upper(), "", b.get("signature", "").upper())
    valid = barcode.verify(code, sig)
    with db() as c:
        ref = one(c.execute("SELECT r.*, c.suspected_disease, c.village_code FROM lab_referrals r JOIN cases c ON c.id=r.case_id WHERE r.barcode=?", (code,)))
    return jsonify(valid=valid and ref is not None and ref["signature"] == sig, signature_ok=valid, known=ref is not None, referral=(dict(ref, chain=json.loads(ref["chain"])) if ref else None))


REF_FLOW = {"COLLECTED": "IN_TRANSIT", "IN_TRANSIT": "RECEIVED", "RECEIVED": "RESULTED"}
REF_TO_CASE = {"IN_TRANSIT": "LAB_TRANSIT", "RECEIVED": "LAB_RECEIVED"}


@app.post("/api/v1/lab-referrals/<rid>/advance")
@require_auth()
def advance_referral(rid):
    b = body()
    with db() as c:
        ref = one(c.execute("SELECT * FROM lab_referrals WHERE id=?", (rid,)))
        if not ref:
            return err("not found", 404)
        nxt = REF_FLOW.get(ref["status"])
        if not nxt or nxt == "RESULTED":
            return err("use /result to close a referral" if nxt == "RESULTED" else "referral already closed", 409)
        if nxt == "RECEIVED" and g.user["role"] not in ("lab", "state", "admin"):
            return err("only laboratory staff can receive samples", 403)
        chain = json.loads(ref["chain"] or "[]")
        chain.append({"at": utcnow(), "by": g.user["full_name"], "event": {"IN_TRANSIT": "Dispatched to laboratory (cold chain)", "RECEIVED": "Received at laboratory, barcode signature verified"}[nxt], "location": b.get("location") or ("lab" if nxt == "RECEIVED" else "field"), "note": b.get("note")})
        c.execute("UPDATE lab_referrals SET status=?, chain=?, updated_at=? WHERE id=?", (nxt, json.dumps(chain), utcnow(), rid))
        case = one(c.execute("SELECT * FROM cases WHERE id=?", (ref["case_id"],)))
        to = REF_TO_CASE[nxt]
        if to in STATE_TRANSITIONS.get(case["status"], set()):
            c.execute("UPDATE cases SET status=?, updated_at=? WHERE id=?", (to, now_ms(), case["id"]))
            add_case_event(c, case["id"], g.user, "transition", case["status"], to, f"Sample {ref['barcode']}")
        ref = one(c.execute("SELECT * FROM lab_referrals WHERE id=?", (rid,)))
    ref["chain"] = json.loads(ref["chain"])
    return jsonify(referral=ref)


@app.post("/api/v1/lab-referrals/<rid>/result")
@require_auth("lab", "state", "admin")
def referral_result(rid):
    b = body(); result = (b.get("result") or "").upper()
    if result not in ("POSITIVE", "NEGATIVE", "INCONCLUSIVE"):
        return err("result must be POSITIVE, NEGATIVE or INCONCLUSIVE")
    with db() as c:
        ref = one(c.execute("SELECT * FROM lab_referrals WHERE id=?", (rid,)))
        if not ref:
            return err("not found", 404)
        if g.user["role"] == "lab" and ref["lab_id"] != g.user["lab_id"]:
            return err("sample belongs to another laboratory", 403)
        case = one(c.execute("SELECT * FROM cases WHERE id=?", (ref["case_id"],)))
        pathogen = b.get("pathogen") or (case["suspected_disease"] if result == "POSITIVE" else None)
        chain = json.loads(ref["chain"] or "[]"); ts = utcnow()
        chain.append({"at": ts, "by": g.user["full_name"], "event": f"Result released: {result}" + (f" ({pathogen})" if pathogen else ""), "location": "lab"})
        c.execute("UPDATE lab_referrals SET status='RESULTED', result=?, pathogen=?, result_notes=?, result_at=?, result_by=?, chain=?, updated_at=? WHERE id=?",
                  (result, pathogen, b.get("notes"), ts, g.user["id"], json.dumps(chain), ts, rid))
        # advance the case
        cur = case["status"]
        if cur in ("SAMPLE_COLLECTED", "LAB_TRANSIT"):
            add_case_event(c, case["id"], g.user, "transition", cur, "LAB_RECEIVED", "Auto: result recorded"); cur = "LAB_RECEIVED"
        to = "PATHOGEN_CONFIRMED" if result == "POSITIVE" else "PATHOGEN_REJECTED" if result == "NEGATIVE" else None
        if to and cur == "LAB_RECEIVED":
            c.execute("UPDATE cases SET status=?, suspected_disease=COALESCE(?, suspected_disease), updated_at=? WHERE id=?", (to, pathogen, now_ms(), case["id"]))
            add_case_event(c, case["id"], g.user, "transition", cur, to, f"{result}: {pathogen or 'no pathogen'}")
        if result == "POSITIVE":
            geo = resolve_village(case["village_code"])
            create_alert(c, g.user, "lab_confirmed", "critical", f"Lab confirmed {pathogen} — {geo['village'] if geo else case['village_code']}",
                         message_key="alert_lab_confirmed", fmt={"disease": pathogen, "barcode": ref["barcode"]}, district_code=case["district_code"],
                         taluka_code=case["taluka_code"], village_code=case["village_code"], case_id=case["id"], disease=pathogen)
            bus.publish("priority_alert", {"case_id": case["id"], "risk_level": "HIGH", "suspected_disease": pathogen, "village": geo["village"] if geo else None, "district_code": case["district_code"], "taluka_code": case["taluka_code"], "village_code": case["village_code"], "kind": "lab_confirmed"})
        detect_outbreaks(c, g.user)
        audit(c, g.user, "result", "lab_referral", rid, {"result": result})
        ref = one(c.execute("SELECT * FROM lab_referrals WHERE id=?", (rid,)))
    ref["chain"] = json.loads(ref["chain"])
    return jsonify(referral=ref)


# ----------------------------------------------------------------------------
# animals — Bharat Pashudhan EHR ledger
# ----------------------------------------------------------------------------
def animal_scope(alias=""):
    p = f"{alias}." if alias else ""
    if g.user["role"] in ("farmer",):
        return f" AND {p}owner_id=?", (g.user["id"],)
    return scope_clause(g.user, alias=alias, reporter_col="owner_id")


@app.get("/api/v1/animals")
@require_auth()
def list_animals():
    clause, params = animal_scope()
    a = request.args
    sql = "SELECT a.*, (SELECT MAX(administered_on) FROM vaccinations v WHERE v.animal_id=a.id) AS last_vaccinated, (SELECT MIN(next_due_on) FROM vaccinations v WHERE v.animal_id=a.id AND next_due_on>=date('now')) AS next_due, (SELECT COUNT(*) FROM treatments t WHERE t.animal_id=a.id) AS treatment_count FROM animals a WHERE deleted_at IS NULL" + clause
    for col in ("species", "village_code", "taluka_code", "district_code", "status", "owner_id"):
        if a.get(col):
            sql += f" AND a.{col}=?"; params = (*params, a[col])
    if a.get("q"):
        sql += " AND (ear_tag LIKE ? OR owner_name LIKE ? OR breed LIKE ?)"; params = (*params, *([f"%{a['q']}%"] * 3))
    if a.get("due") == "1":
        sql += " AND EXISTS (SELECT 1 FROM vaccinations v WHERE v.animal_id=a.id AND v.next_due_on BETWEEN date('now') AND date('now','+30 days'))"
    sql += " ORDER BY a.updated_at DESC"
    with db() as c:
        items, page = paginate(sql, params, c)
    for it in items:
        geo = resolve_village(it["village_code"]); it["village"] = geo["village"] if geo else it["village_code"]
    return jsonify(items=items, **page)


@app.post("/api/v1/animals")
@require_auth()
def create_animal():
    b = body()
    tag = str(b.get("ear_tag") or "").strip()
    if not EAR_TAG_RE.fullmatch(tag):
        return err("ear_tag must be exactly 12 numeric digits (Bharat Pashudhan INAPH format)")
    if not b.get("species"):
        return err("species is required")
    enrich_geo(b, g.user)
    owner_id = b.get("owner_id") or (g.user["id"] if g.user["role"] == "farmer" else None)
    aid = new_id("AN"); ts = utcnow()
    with db() as c:
        if one(c.execute("SELECT 1 FROM animals WHERE ear_tag=?", (tag,))):
            return err("an animal with this ear tag already exists", 409)
        owner = one(c.execute("SELECT full_name, phone FROM users WHERE id=?", (owner_id,))) if owner_id else None
        c.execute("INSERT INTO animals(id,ear_tag,species,breed,sex,birth_year,color,owner_id,owner_name,owner_phone,village_code,taluka_code,district_code,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (aid, tag, b["species"], b.get("breed"), b.get("sex"), b.get("birth_year"), b.get("color"), owner_id, b.get("owner_name") or (owner["full_name"] if owner else None),
                   b.get("owner_phone") or (owner["phone"] if owner else None), b.get("village_code"), b.get("taluka_code"), b.get("district_code"), b.get("status", "active"), b.get("notes"), ts, ts))
        audit(c, g.user, "create", "animal", aid, {"ear_tag": tag})
        an = one(c.execute("SELECT * FROM animals WHERE id=?", (aid,)))
    return jsonify(animal=an), 201


def _find_animal(c, key):
    return one(c.execute("SELECT * FROM animals WHERE (id=? OR ear_tag=?) AND deleted_at IS NULL", (key, key)))


@app.get("/api/v1/animals/<key>")
@require_auth()
def get_animal(key):
    with db() as c:
        an = _find_animal(c, key)
        if not an:
            return err("not found", 404)
        if not can_access_row(g.user, an):
            return err("forbidden", 403)
        an["vaccinations"] = rows(c.execute("SELECT * FROM vaccinations WHERE animal_id=? ORDER BY administered_on DESC", (an["id"],)))
        an["treatments"] = rows(c.execute("SELECT * FROM treatments WHERE animal_id=? ORDER BY treated_on DESC", (an["id"],)))
        an["cases"] = [hydrate_case(r) for r in rows(c.execute("SELECT * FROM cases WHERE ear_tags LIKE ? AND deleted_at IS NULL ORDER BY created_at DESC", (f'%"{an["ear_tag"]}"%',)))]
        geo = resolve_village(an["village_code"]); an["village"] = geo["village"] if geo else an["village_code"]; an["taluka"] = geo["taluka"] if geo else None; an["district"] = geo["district"] if geo else None
        # timeline merge
        tl = [{"at": v["administered_on"], "kind": "vaccination", "title": v["vaccine"], "detail": v["disease"], "by": v["administered_by"]} for v in an["vaccinations"]]
        tl += [{"at": t["treated_on"], "kind": "treatment", "title": t["diagnosis"] or t["treatment"], "detail": f"{t['drug'] or ''} {t['dosage'] or ''}".strip(), "by": t["clinician_name"], "outcome": t["outcome"]} for t in an["treatments"]]
        tl += [{"at": cs["created_at"][:10], "kind": "case", "title": cs["suspected_disease"], "detail": cs["risk_level"], "id": cs["id"]} for cs in an["cases"]]
        an["timeline"] = sorted(tl, key=lambda x: x["at"] or "", reverse=True)
    return jsonify(animal=an)


@app.route("/api/v1/animals/<key>", methods=["PUT", "PATCH", "DELETE"])
@require_auth()
def modify_animal(key):
    with db() as c:
        an = _find_animal(c, key)
        if not an:
            return err("not found", 404)
        if not can_access_row(g.user, an):
            return err("forbidden", 403)
        if request.method == "DELETE":
            c.execute("UPDATE animals SET deleted_at=?, updated_at=? WHERE id=?", (utcnow(), utcnow(), an["id"]))
            audit(c, g.user, "delete", "animal", an["id"])
            return jsonify(ok=True)
        b = body(); fields = {}
        for k in ("species", "breed", "sex", "birth_year", "color", "owner_name", "owner_phone", "village_code", "status", "notes", "owner_id"):
            if k in b:
                fields[k] = b[k]
        if "ear_tag" in b and b["ear_tag"] != an["ear_tag"]:
            if not EAR_TAG_RE.fullmatch(str(b["ear_tag"])):
                return err("ear_tag must be exactly 12 digits")
            if one(c.execute("SELECT 1 FROM animals WHERE ear_tag=?", (b["ear_tag"],))):
                return err("ear tag already registered", 409)
            fields["ear_tag"] = b["ear_tag"]
        if "village_code" in fields:
            geo = resolve_village(fields["village_code"])
            if geo:
                fields["taluka_code"], fields["district_code"] = geo["taluka_code"], geo["district_code"]
        if not fields:
            return err("nothing to update")
        c.execute(f"UPDATE animals SET {', '.join(f'{k}=?' for k in fields)}, updated_at=? WHERE id=?", (*fields.values(), utcnow(), an["id"]))
        audit(c, g.user, "update", "animal", an["id"], {"fields": list(fields)})
        an = one(c.execute("SELECT * FROM animals WHERE id=?", (an["id"],)))
    return jsonify(animal=an)


@app.post("/api/v1/animals/<key>/vaccinations")
@require_auth()
def add_vaccination(key):
    b = body()
    if not b.get("vaccine") or not b.get("administered_on"):
        return err("vaccine and administered_on are required")
    with db() as c:
        an = _find_animal(c, key)
        if not an or not can_access_row(g.user, an):
            return err("not found", 404)
        vid = new_id("VX")
        c.execute("INSERT INTO vaccinations VALUES(?,?,?,?,?,?,?,?,?)", (vid, an["id"], b["vaccine"], b.get("disease"), b["administered_on"], b.get("next_due_on"), b.get("batch_no"), b.get("administered_by") or g.user["full_name"], utcnow()))
        c.execute("UPDATE animals SET updated_at=? WHERE id=?", (utcnow(), an["id"]))
        v = one(c.execute("SELECT * FROM vaccinations WHERE id=?", (vid,)))
    return jsonify(vaccination=v), 201


@app.delete("/api/v1/vaccinations/<vid>")
@require_auth(*CLINICAL_ROLES, "pashu_sakhi")
def delete_vaccination(vid):
    with db() as c:
        c.execute("DELETE FROM vaccinations WHERE id=?", (vid,))
    return jsonify(ok=True)


@app.post("/api/v1/animals/<key>/treatments")
@require_auth(*CLINICAL_ROLES, "pashu_sakhi")
def add_treatment(key):
    b = body()
    if not b.get("treatment") or not b.get("treated_on"):
        return err("treatment and treated_on are required")
    with db() as c:
        an = _find_animal(c, key)
        if not an or not can_access_row(g.user, an):
            return err("not found", 404)
        tid = new_id("TX")
        c.execute("INSERT INTO treatments VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (tid, an["id"], b.get("case_id"), b.get("diagnosis"), b["treatment"], b.get("drug"), b.get("dosage"), b["treated_on"], g.user["id"], g.user["full_name"], b.get("outcome"), utcnow()))
        c.execute("UPDATE animals SET updated_at=? WHERE id=?", (utcnow(), an["id"]))
        if b.get("case_id"):
            add_case_event(c, b["case_id"], g.user, "treatment", note=f"{an['ear_tag']}: {b['treatment']}")
        t = one(c.execute("SELECT * FROM treatments WHERE id=?", (tid,)))
    return jsonify(treatment=t), 201


@app.patch("/api/v1/treatments/<tid>")
@require_auth(*CLINICAL_ROLES)
def update_treatment(tid):
    b = body(); fields = {k: b[k] for k in ("outcome", "diagnosis", "treatment", "drug", "dosage") if k in b}
    if not fields:
        return err("nothing to update")
    with db() as c:
        c.execute(f"UPDATE treatments SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?", (*fields.values(), tid))
        t = one(c.execute("SELECT * FROM treatments WHERE id=?", (tid,)))
    return jsonify(treatment=t)


@app.get("/api/v1/vaccinations/coverage")
@require_auth()
def vaccination_coverage():
    clause, params = animal_scope()
    a_clause, _ = animal_scope(alias="a")
    with db() as c:
        total = one(c.execute("SELECT COUNT(*) n FROM animals WHERE deleted_at IS NULL" + clause, params))["n"]
        by = rows(c.execute("SELECT v.disease, COUNT(DISTINCT v.animal_id) covered, SUM(CASE WHEN v.next_due_on < date('now') THEN 1 ELSE 0 END) overdue, SUM(CASE WHEN v.next_due_on BETWEEN date('now') AND date('now','+30 days') THEN 1 ELSE 0 END) due_soon "
                            "FROM vaccinations v JOIN animals a ON a.id=v.animal_id WHERE a.deleted_at IS NULL" + a_clause + " GROUP BY v.disease ORDER BY covered DESC", params))
        due = rows(c.execute("SELECT a.id, a.ear_tag, a.species, a.owner_name, a.village_code, v.vaccine, v.next_due_on FROM vaccinations v JOIN animals a ON a.id=v.animal_id WHERE a.deleted_at IS NULL AND v.next_due_on BETWEEN date('now','-30 days') AND date('now','+30 days')" + a_clause + " ORDER BY v.next_due_on LIMIT 60", params))
        species = rows(c.execute("SELECT species, COUNT(*) n FROM animals WHERE deleted_at IS NULL" + clause + " GROUP BY species ORDER BY n DESC", params))
    for d in due:
        geo = resolve_village(d["village_code"]); d["village"] = geo["village"] if geo else d["village_code"]
    return jsonify(total_animals=total, by_disease=[dict(b, coverage_pct=round(100 * b["covered"] / total, 1) if total else 0) for b in by], due=due, species=species)


# ----------------------------------------------------------------------------
# vet centres (CRUD) + nearest clinic
# ----------------------------------------------------------------------------
@app.get("/api/v1/vet-centers")
@require_auth()
def list_centers():
    with db() as c:
        items = rows(c.execute("SELECT * FROM vet_centers WHERE deleted_at IS NULL ORDER BY district_code, name"))
    for it in items:
        d = DISTRICT_BY_CODE.get(it["district_code"]); t = TALUKA_BY_CODE.get(it["taluka_code"])
        it["district"] = d[1] if d else it["district_code"]; it["taluka"] = t[2] if t else it["taluka_code"]
    return jsonify(items=items)


@app.post("/api/v1/vet-centers")
@require_auth(*DISTRICT_PLUS)
def create_center():
    b = body()
    for f in ("name", "lat", "lng"):
        if b.get(f) in (None, ""):
            return err(f"{f} is required")
    vid = new_id("VC"); ts = utcnow()
    with db() as c:
        c.execute("INSERT INTO vet_centers(id,name,type,district_code,taluka_code,lat,lng,officer_name,officer_phone,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                  (vid, b["name"], b.get("type", "dispensary"), b.get("district_code") or g.user.get("district_code"), b.get("taluka_code"), float(b["lat"]), float(b["lng"]), b.get("officer_name"), b.get("officer_phone"), ts, ts))
        audit(c, g.user, "create", "vet_center", vid)
        it = one(c.execute("SELECT * FROM vet_centers WHERE id=?", (vid,)))
    return jsonify(center=it), 201


@app.route("/api/v1/vet-centers/<vid>", methods=["PATCH", "DELETE"])
@require_auth(*DISTRICT_PLUS)
def modify_center(vid):
    with db() as c:
        it = one(c.execute("SELECT * FROM vet_centers WHERE id=? AND deleted_at IS NULL", (vid,)))
        if not it:
            return err("not found", 404)
        if request.method == "DELETE":
            c.execute("UPDATE vet_centers SET deleted_at=? WHERE id=?", (utcnow(), vid)); audit(c, g.user, "delete", "vet_center", vid)
            return jsonify(ok=True)
        b = body(); fields = {k: b[k] for k in ("name", "type", "district_code", "taluka_code", "lat", "lng", "officer_name", "officer_phone") if k in b}
        if not fields:
            return err("nothing to update")
        c.execute(f"UPDATE vet_centers SET {', '.join(f'{k}=?' for k in fields)}, updated_at=? WHERE id=?", (*fields.values(), utcnow(), vid))
        it = one(c.execute("SELECT * FROM vet_centers WHERE id=?", (vid,)))
    return jsonify(center=it)


@app.route("/api/v1/geo/nearest-clinic", methods=["GET", "POST"])
def nearest_clinic():
    b = body(); lat = b.get("lat", request.args.get("lat")); lng = b.get("lng", request.args.get("lng")); k = int(b.get("k", request.args.get("k", 3)))
    with db() as c:
        # spatial.py expects table veterinary_centers; provide a compatible view
        c.execute("CREATE TEMP VIEW IF NOT EXISTS veterinary_centers AS SELECT id, name, district_code, taluka_code, lat, lng, officer_phone FROM vet_centers WHERE deleted_at IS NULL")
        res = spatial_nearest(c, lat, lng, k=k, radius_km=float(b.get("radius_km", request.args.get("radius_km", 150))))
        if res is None:
            return err("valid decimal lat/lng required")
        centers = rows(c.execute("SELECT * FROM vet_centers WHERE deleted_at IS NULL"))
    by_name = {x["name"]: x for x in centers}
    for r in res:
        src = by_name.get(r["name"], {}); r.update(id=src.get("id"), type=src.get("type"), officer_name=src.get("officer_name"))
    return jsonify(query={"lat": float(lat), "lng": float(lng)}, backend="postgis" if os.getenv("DATABASE_URL") else "sqlite+haversine", clinics=res)


# ----------------------------------------------------------------------------
# weather (MAHAVEDH ETL) + risk map
# ----------------------------------------------------------------------------
@app.post("/api/v1/weather/etl")
@require_auth(*DISTRICT_PLUS, "ldo")
def weather_etl():
    obs = body().get("observations") or []
    n = 0
    with db() as c:
        for o in obs:
            geo = resolve_village(o.get("village_code"))
            c.execute("INSERT INTO weather VALUES(?,?,?,?,?,?,?,?,?,?)", (new_id("WX"), o.get("district_code") or (geo["district_code"] if geo else None), o.get("taluka_code") or (geo["taluka_code"] if geo else None),
                                                                       o.get("village_code"), o.get("humidity"), o.get("temperature_c"), o.get("rainfall_mm"), o.get("wind_kmh"), o.get("observed_at") or utcnow(), o.get("source", "MAHAVEDH")))
            n += 1
    return jsonify(accepted=n, source="MAHAVEDH")


@app.get("/api/v1/weather/latest")
@require_auth()
def weather_latest():
    with db() as c:
        items = rows(c.execute("SELECT w.* FROM weather w JOIN (SELECT taluka_code, MAX(observed_at) m FROM weather GROUP BY taluka_code) x ON x.taluka_code=w.taluka_code AND x.m=w.observed_at ORDER BY w.district_code"))
        series = rows(c.execute("SELECT substr(observed_at,1,10) day, ROUND(AVG(humidity),1) humidity, ROUND(AVG(temperature_c),1) temperature_c, ROUND(SUM(rainfall_mm)/COUNT(DISTINCT taluka_code),1) rainfall_mm FROM weather WHERE observed_at>=? GROUP BY day ORDER BY day", ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),)))
    for it in items:
        t = TALUKA_BY_CODE.get(it["taluka_code"]); d = DISTRICT_BY_CODE.get(it["district_code"])
        it["taluka"] = t[2] if t else None; it["district"] = d[1] if d else None
        it["vector_favourable"] = bool(it["humidity"] and it["humidity"] > 80 and 25 <= (it["temperature_c"] or 0) <= 35)
    return jsonify(items=items, series=series)


@app.get("/api/v1/geo/risk-map")
@require_auth()
def risk_map():
    """Per-taluka composite risk: recent cases, mortality, HIGH triage, vector-favourable weather."""
    since = (datetime.now(timezone.utc) - timedelta(days=int(request.args.get("days", 14)))).isoformat()
    clause, params = scope_clause(g.user, reporter_col=None) if scope(g.user["role"]) in ("district", "state") else ("", ())
    with db() as c:
        agg = {r["taluka_code"]: r for r in rows(c.execute("SELECT taluka_code, COUNT(*) n, SUM(mortality_count) deaths, SUM(affected_count) affected, SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) high, "
                                                             "GROUP_CONCAT(DISTINCT suspected_disease) diseases FROM cases WHERE created_at>=? AND deleted_at IS NULL" + clause + " GROUP BY taluka_code", (since, *params)))}
        wx = {r["taluka_code"]: r for r in rows(c.execute("SELECT w.* FROM weather w JOIN (SELECT taluka_code, MAX(observed_at) m FROM weather GROUP BY taluka_code) x ON x.taluka_code=w.taluka_code AND x.m=w.observed_at"))}
        signals = rows(c.execute("SELECT * FROM outbreak_signals WHERE status IN ('SUSPECTED','CONFIRMED')"))
        cases = rows(c.execute("SELECT id, lat, lng, village_code, taluka_code, district_code, risk_level, suspected_disease, status, mortality_count, affected_count, species, created_at FROM cases WHERE created_at>=? AND deleted_at IS NULL" + clause, (since, *params)))
    feats = []
    for t in TALUKAS:
        if scope(g.user["role"]) == "district" and t[1] != g.user.get("district_code"):
            continue
        a = agg.get(t[0], {}); w = wx.get(t[0])
        n = a.get("n", 0) or 0; deaths = a.get("deaths", 0) or 0; high = a.get("high", 0) or 0
        vec = bool(w and w["humidity"] > 80 and 25 <= w["temperature_c"] <= 35)
        score = min(100, n * 6 + deaths * 8 + high * 10 + (12 if vec else 0) + (25 if any(s["taluka_code"] == t[0] for s in signals) else 0))
        feats.append({"taluka_code": t[0], "taluka": t[2], "district_code": t[1], "district": DISTRICT_BY_CODE[t[1]][1], "lat": t[3], "lng": t[4],
                      "cases": n, "deaths": deaths, "high": high, "affected": a.get("affected", 0) or 0, "diseases": (a.get("diseases") or "").split(",") if a.get("diseases") else [],
                      "vector_favourable": vec, "weather": {"humidity": w["humidity"], "temperature_c": w["temperature_c"]} if w else None,
                      "risk_score": score, "risk_band": "HIGH" if score >= 50 else "MEDIUM" if score >= 20 else "LOW",
                      "outbreak": next((s for s in signals if s["taluka_code"] == t[0]), None)})
    pts = [dict(hydrate_case(x), ) for x in cases]
    return jsonify(talukas=feats, cases=[{k: p.get(k) for k in ("id", "lat", "lng", "village", "risk_level", "suspected_disease", "status", "mortality_count", "affected_count", "species", "created_at", "precision")} for p in pts], generated_at=utcnow())


# ----------------------------------------------------------------------------
# outbreaks
# ----------------------------------------------------------------------------
@app.get("/api/v1/outbreaks")
@require_auth()
def list_outbreaks():
    clause, params = scope_clause(g.user, reporter_col=None) if scope(g.user["role"]) != "village" else ("", ())
    with db() as c:
        items = rows(c.execute("SELECT o.*, u.full_name confirmed_by_name FROM outbreak_signals o LEFT JOIN users u ON u.id=o.confirmed_by WHERE 1=1" + clause.replace("district_code", "o.district_code").replace("taluka_code", "o.taluka_code") + " ORDER BY CASE o.status WHEN 'CONFIRMED' THEN 0 WHEN 'SUSPECTED' THEN 1 ELSE 2 END, detected_at DESC", params))
    for it in items:
        it["case_ids"] = json.loads(it["case_ids"]); t = TALUKA_BY_CODE.get(it["taluka_code"]); d = DISTRICT_BY_CODE.get(it["district_code"])
        it["taluka"] = t[2] if t else None; it["district"] = d[1] if d else None; it["lat"] = t[3] if t else None; it["lng"] = t[4] if t else None
    return jsonify(items=items)


@app.post("/api/v1/outbreaks/<oid>/status")
@require_auth(*DISTRICT_PLUS)
def outbreak_status(oid):
    b = body(); st = b.get("status")
    if st not in ("CONFIRMED", "DISMISSED", "CONTAINED"):
        return err("status must be CONFIRMED, DISMISSED or CONTAINED")
    with db() as c:
        o = one(c.execute("SELECT * FROM outbreak_signals WHERE id=?", (oid,)))
        if not o:
            return err("not found", 404)
        c.execute("UPDATE outbreak_signals SET status=?, confirmed_by=?, confirmed_at=?, notes=? WHERE id=?", (st, g.user["id"], utcnow(), b.get("notes"), oid))
        if st == "CONFIRMED":
            radius = float(b.get("radius_km", 5))
            create_alert(c, g.user, "outbreak_confirmed", "critical", f"Confirmed {o['disease']} outbreak — {TALUKA_BY_CODE[o['taluka_code']][2]}",
                         message_key="alert_outbreak_confirmed", fmt={"disease": o["disease"], "radius": radius}, district_code=o["district_code"], taluka_code=o["taluka_code"], disease=o["disease"], radius_km=radius,
                         channels=b.get("channels") or ["app", "sms", "whatsapp", "ivr"])
            bus.publish("outbreak_confirmed", {"id": oid, "disease": o["disease"], "district_code": o["district_code"], "taluka_code": o["taluka_code"], "kind": "advisory"})
        audit(c, g.user, st.lower(), "outbreak", oid)
        o = one(c.execute("SELECT * FROM outbreak_signals WHERE id=?", (oid,)))
    o["case_ids"] = json.loads(o["case_ids"])
    return jsonify(outbreak=o)


@app.post("/api/v1/outbreaks/detect")
@require_auth(*CLINICAL_ROLES)
def run_detection():
    with db() as c:
        created = detect_outbreaks(c, g.user)
    return jsonify(created=len(created), signals=created)


# ----------------------------------------------------------------------------
# alerts & advisories
# ----------------------------------------------------------------------------
@app.get("/api/v1/alerts")
@require_auth()
def list_alerts():
    s = scope(g.user["role"]); u = g.user
    sql = "SELECT a.*, (SELECT COUNT(*) FROM alert_acks k WHERE k.alert_id=a.id) acks, EXISTS(SELECT 1 FROM alert_acks k WHERE k.alert_id=a.id AND k.user_id=?) acked FROM alerts a WHERE deleted_at IS NULL"
    params: tuple = (u["id"],)
    if s == "district":
        sql += " AND (district_code=? OR district_code IS NULL)"; params += (u["district_code"],)
    elif s == "taluka":
        sql += " AND ((district_code=? AND taluka_code IS NULL) OR taluka_code=? OR district_code IS NULL)"; params += (u["district_code"], u["taluka_code"])
    elif s == "village":
        sql += " AND ((district_code=? AND taluka_code IS NULL AND village_code IS NULL) OR (taluka_code=? AND village_code IS NULL) OR village_code=? OR district_code IS NULL)"; params += (u["district_code"], u["taluka_code"], u["village_code"])
    if request.args.get("severity"):
        sql += " AND severity=?"; params += (request.args["severity"],)
    sql += " ORDER BY created_at DESC"
    with db() as c:
        items, page = paginate(sql, params, c, 30)
    l = lang()
    for it in items:
        it["message"] = it.get(f"message_{l}") or it["message_en"]; it["channels"] = json.loads(it["channels"] or "[]")
        d = DISTRICT_BY_CODE.get(it["district_code"] or ""); t = TALUKA_BY_CODE.get(it["taluka_code"] or ""); v = resolve_village(it["village_code"])
        it["area"] = v["village"] if v else t[2] if t else d[1] if d else "Statewide"
    return jsonify(items=items, **page)


@app.post("/api/v1/alerts")
@require_auth(*CLINICAL_ROLES)
def create_advisory():
    b = body()
    if not b.get("title") or not b.get("message_en"):
        return err("title and message_en are required")
    if scope(g.user["role"]) == "district":
        b["district_code"] = g.user["district_code"]
    if scope(g.user["role"]) == "taluka":
        b["district_code"], b["taluka_code"] = g.user["district_code"], g.user["taluka_code"]
    with db() as c:
        a = create_alert(c, g.user, b.get("kind", "advisory"), b.get("severity", "info"), b["title"],
                         messages={"en": b["message_en"], "mr": b.get("message_mr") or b["message_en"], "hi": b.get("message_hi") or b["message_en"]},
                         district_code=b.get("district_code"), taluka_code=b.get("taluka_code"), village_code=b.get("village_code"), disease=b.get("disease"),
                         radius_km=b.get("radius_km"), channels=b.get("channels"), expires_days=int(b.get("expires_days", 7)))
        audit(c, g.user, "create", "alert", a["id"])
    return jsonify(alert=a), 201


@app.route("/api/v1/alerts/<aid>", methods=["PATCH", "DELETE"])
@require_auth(*CLINICAL_ROLES)
def modify_alert(aid):
    with db() as c:
        a = one(c.execute("SELECT * FROM alerts WHERE id=? AND deleted_at IS NULL", (aid,)))
        if not a:
            return err("not found", 404)
        if request.method == "DELETE":
            c.execute("UPDATE alerts SET deleted_at=? WHERE id=?", (utcnow(), aid)); audit(c, g.user, "delete", "alert", aid)
            return jsonify(ok=True)
        b = body(); fields = {k: b[k] for k in ("title", "message_en", "message_mr", "message_hi", "severity", "expires_at") if k in b}
        if not fields:
            return err("nothing to update")
        c.execute(f"UPDATE alerts SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?", (*fields.values(), aid))
        a = one(c.execute("SELECT * FROM alerts WHERE id=?", (aid,)))
    return jsonify(alert=a)


@app.post("/api/v1/alerts/<aid>/ack")
@require_auth()
def ack_alert(aid):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO alert_acks VALUES(?,?,?)", (aid, g.user["id"], utcnow()))
    return jsonify(ok=True)


@app.get("/api/v1/alerts/<aid>/preview")
@require_auth()
def alert_preview(aid):
    """Channel renderings (SMS 160-char, IVR script, WhatsApp) in all languages."""
    with db() as c:
        a = one(c.execute("SELECT * FROM alerts WHERE id=?", (aid,)))
    if not a:
        return err("not found", 404)
    out = {}
    for l in ("en", "mr", "hi"):
        msg = a.get(f"message_{l}") or a["message_en"]
        out[l] = {"sms": (msg[:157] + "…") if len(msg) > 160 else msg, "whatsapp": f"*{a['title']}*\n{msg}", "ivr_script": msg}
    return jsonify(preview=out)


# ----------------------------------------------------------------------------
# analytics dashboards
# ----------------------------------------------------------------------------
@app.get("/api/v1/analytics/summary")
@require_auth()
def analytics_summary():
    u = g.user; s = scope(u["role"])
    clause, params = scope_clause(u)
    if u["role"] == "lab":
        clause, params = " AND id IN (SELECT case_id FROM lab_referrals WHERE lab_id=?)", (u["lab_id"],)
    now = datetime.now(timezone.utc); d7 = (now - timedelta(days=7)).isoformat(); d14 = (now - timedelta(days=14)).isoformat(); d30 = (now - timedelta(days=30)).isoformat()
    with db() as c:
        base = "FROM cases WHERE deleted_at IS NULL" + clause
        k = one(c.execute(f"SELECT COUNT(*) total, SUM(CASE WHEN status NOT IN ('CASE_RESOLVED','PATHOGEN_REJECTED') THEN 1 ELSE 0 END) open_cases, "
                          f"SUM(CASE WHEN risk_level='HIGH' AND status NOT IN ('CASE_RESOLVED','PATHOGEN_REJECTED') THEN 1 ELSE 0 END) high_open, "
                          f"SUM(CASE WHEN created_at>=? THEN 1 ELSE 0 END) last7, SUM(CASE WHEN created_at>=? AND created_at<? THEN 1 ELSE 0 END) prev7, "
                          f"SUM(CASE WHEN created_at>=? THEN mortality_count ELSE 0 END) deaths30, SUM(CASE WHEN created_at>=? THEN affected_count ELSE 0 END) affected30, "
                          f"SUM(CASE WHEN status='REPORTED' THEN 1 ELSE 0 END) awaiting_inspection {base}", (d7, d14, d7, d30, d30, *params)))
        by_level = {r["risk_level"]: r["n"] for r in rows(c.execute(f"SELECT risk_level, COUNT(*) n {base} AND created_at>=? GROUP BY risk_level", (*params, d30)))}
        by_channel = {r["channel"]: r["n"] for r in rows(c.execute(f"SELECT channel, COUNT(*) n {base} AND created_at>=? GROUP BY channel", (*params, d30)))}
        by_status = {r["status"]: r["n"] for r in rows(c.execute(f"SELECT status, COUNT(*) n {base} GROUP BY status", params))}
        by_species = rows(c.execute(f"SELECT species, COUNT(*) n, SUM(mortality_count) deaths {base} AND created_at>=? GROUP BY species ORDER BY n DESC", (*params, d30)))
        by_disease = rows(c.execute(f"SELECT suspected_disease disease, COUNT(*) n, SUM(mortality_count) deaths, SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) high {base} AND created_at>=? GROUP BY suspected_disease ORDER BY n DESC", (*params, d30)))
        trend = rows(c.execute(f"SELECT substr(created_at,1,10) day, COUNT(*) cases, SUM(mortality_count) deaths, SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) high {base} AND created_at>=? GROUP BY day ORDER BY day", (*params, d30)))
        geo_col = "district_code" if s == "state" else "taluka_code" if s == "district" else "village_code"
        top_areas = rows(c.execute(f"SELECT {geo_col} code, COUNT(*) cases, SUM(mortality_count) deaths, SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END) high {base} AND created_at>=? GROUP BY {geo_col} ORDER BY cases DESC LIMIT 10", (*params, d30)))
        # response time: created -> first inspection
        c_clause, c_params = (" AND c.id IN (SELECT case_id FROM lab_referrals WHERE lab_id=?)", (u["lab_id"],)) if u["role"] == "lab" else scope_clause(u, alias="c")
        rt = one(c.execute("SELECT AVG((julianday(e.created_at)-julianday(c.created_at))*24) hrs FROM cases c JOIN case_events e ON e.case_id=c.id AND e.to_status='FIELD_INSPECTED_BY_LDO' WHERE c.deleted_at IS NULL AND c.created_at>=?" + c_clause, (d30, *c_params)))
        lab_tat = one(c.execute("SELECT AVG((julianday(result_at)-julianday(collected_at))*24) hrs FROM lab_referrals WHERE result_at IS NOT NULL"))
        outbreaks = rows(c.execute("SELECT o.* FROM outbreak_signals o WHERE status IN ('SUSPECTED','CONFIRMED')" + (scope_clause(u, reporter_col=None)[0].replace("district_code", "o.district_code").replace("taluka_code", "o.taluka_code") if s in ("district", "taluka") else "") + " ORDER BY detected_at DESC", scope_clause(u, reporter_col=None)[1] if s in ("district", "taluka") else ()))
        ref = one(c.execute("SELECT SUM(CASE WHEN r.status IN ('COLLECTED','IN_TRANSIT') THEN 1 ELSE 0 END) in_transit, SUM(CASE WHEN r.status='RECEIVED' THEN 1 ELSE 0 END) at_lab, SUM(CASE WHEN r.result='POSITIVE' THEN 1 ELSE 0 END) positives FROM lab_referrals r JOIN cases c ON c.id=r.case_id WHERE c.deleted_at IS NULL" + (" AND r.lab_id=?" if u["role"] == "lab" else c_clause), (u["lab_id"],) if u["role"] == "lab" else c_params))
        an_clause, an_params = animal_scope(); an_clause_a, _ = animal_scope(alias="a")
        animals = one(c.execute("SELECT COUNT(*) n FROM animals WHERE deleted_at IS NULL" + an_clause, an_params))["n"]
        vac = one(c.execute("SELECT COUNT(DISTINCT a.id) n FROM animals a JOIN vaccinations v ON v.animal_id=a.id WHERE a.deleted_at IS NULL AND v.administered_on>=date('now','-365 days')" + an_clause_a, an_params))["n"]
        due = one(c.execute("SELECT COUNT(DISTINCT a.id) n FROM animals a JOIN vaccinations v ON v.animal_id=a.id WHERE a.deleted_at IS NULL AND v.next_due_on BETWEEN date('now') AND date('now','+30 days')" + an_clause_a, an_params))["n"]
        alerts_n = one(c.execute("SELECT COUNT(*) n FROM alerts WHERE deleted_at IS NULL AND created_at>=?", (d7,)))["n"]
    for a in top_areas:
        if geo_col == "district_code":
            d = DISTRICT_BY_CODE.get(a["code"]); a["name"] = d[1] if d else a["code"]
        elif geo_col == "taluka_code":
            t = TALUKA_BY_CODE.get(a["code"]); a["name"] = t[2] if t else a["code"]
        else:
            v = resolve_village(a["code"]); a["name"] = v["village"] if v else a["code"]
    for o in outbreaks:
        o["case_ids"] = json.loads(o["case_ids"]); t = TALUKA_BY_CODE.get(o["taluka_code"]); o["taluka"] = t[2] if t else None; d = DISTRICT_BY_CODE.get(o["district_code"]); o["district"] = d[1] if d else None
    prev = k["prev7"] or 0; cur = k["last7"] or 0
    return jsonify(scope=s, kpis=dict(k, delta7_pct=round(100 * (cur - prev) / prev, 1) if prev else None, animals=animals, vaccinated_12m=vac,
                                      coverage_pct=round(100 * vac / animals, 1) if animals else 0, due_30d=due, alerts_7d=alerts_n,
                                      avg_response_hours=round(rt["hrs"], 1) if rt and rt["hrs"] else None, lab_tat_hours=round(lab_tat["hrs"], 1) if lab_tat and lab_tat["hrs"] else None,
                                      samples_in_transit=ref["in_transit"] or 0, samples_at_lab=ref["at_lab"] or 0, lab_positives=ref["positives"] or 0, active_outbreaks=len(outbreaks)),
                   by_level=by_level, by_channel=by_channel, by_status=by_status, by_species=by_species, by_disease=by_disease, trend=trend, top_areas=top_areas,
                   top_areas_level=geo_col.replace("_code", ""), outbreaks=outbreaks, model=model_status())


@app.get("/api/v1/analytics/history")
@require_auth()
def analytics_history():
    """Historical disease trend datasets shipped with the repo (district-level)."""
    import csv
    district = request.args.get("district")
    hist, seasonal = [], []
    try:
        with open(BASE_DIR / "ml" / "data" / "anthrax_2020_2023.csv", newline="") as f:
            for r in csv.DictReader(f):
                if r["State"].strip().upper() == "MAHARASHTRA" and (not district or r["District"].strip().lower() == district.lower()):
                    hist.append({k: (int(v) if v.strip().lstrip("-").isdigit() else v.strip()) for k, v in r.items()})
    except Exception:
        pass
    try:
        with open(BASE_DIR / "ml" / "data" / "livestock_disease_risk.csv", newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                r = {k.strip(): (v or "").strip() for k, v in r.items()}
                if r.get("State Name", "").upper() == "MAHARASHTRA" and (not district or r.get("District Name", "").lower() == district.lower()):
                    seasonal.append({"district": r["District Name"], "disease": r["Disease Name"], "month": r["Month"], "predicted": r["Predicted"]})
    except Exception:
        pass
    return jsonify(anthrax_history=hist, seasonal_risk=seasonal[:400])


@app.post("/api/v1/ml/predict")
@require_auth()
def ml_predict():
    b = body()
    p = predict_deaths(int(b.get("outbreaks", 1)), int(b.get("susceptible", 100)), int(b.get("attacks", 10)), int(b.get("year", datetime.now().year)))
    band = None if p is None else "HIGH" if p >= 10 else "MEDIUM" if p >= 5 else "LOW" if p > 0 else "NONE"
    return jsonify(predicted_deaths=p, band=band, model=model_status())


@app.get("/api/v1/audit")
@require_auth(*DISTRICT_PLUS)
def audit_log():
    with db() as c:
        return jsonify(items=rows(c.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 100")))


# ----------------------------------------------------------------------------
# SSE
# ----------------------------------------------------------------------------
@app.get("/api/v1/events")
@require_auth()
def events():
    user = dict(g.user)
    q = bus.subscribe()

    def stream():
        yield "retry: 3000\nevent: ready\ndata: {\"status\":\"connected\"}\n\n"
        last = time.time()
        try:
            while True:
                try:
                    ev = q.get(timeout=15)
                    if event_visible(user, ev["data"]):
                        yield f"event: {ev['event']}\ndata: {json.dumps(ev)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
                if time.time() - last > 3600:
                    break
        finally:
            bus.unsubscribe(q)
    return Response(stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/v1/events/recent")
@require_auth()
def recent_events():
    return jsonify(items=[e for e in bus.recent if event_visible(g.user, e["data"])][:20])


# ----------------------------------------------------------------------------
# SPA + errors
# ----------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith(("/api/", "/webhooks/")):
        return jsonify(error="not found"), 404
    if DIST.exists():
        return send_from_directory(DIST, "index.html")
    return jsonify(error="client not built — run `npm run build` in client/ or use the Vite dev server"), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify(error="internal server error"), 500


@app.get("/")
def index():
    if DIST.exists():
        return send_from_directory(DIST, "index.html")
    return jsonify(service="Pashu Arogya API", docs="/api/v1/health")


@app.get("/<path:path>")
def spa(path):
    if DIST.exists() and (DIST / path).is_file():
        return send_from_directory(DIST, path)
    if DIST.exists():
        return send_from_directory(DIST, "index.html")
    return jsonify(error="not found"), 404


def bootstrap():
    init_schema()
    if seed_if_empty():
        app.logger.info("database seeded with demo data")


bootstrap()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG") == "1", threaded=True)
