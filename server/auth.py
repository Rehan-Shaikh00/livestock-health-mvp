"""Authentication (PBKDF2 password hashing + HS256 JWT) and RBAC scoping."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from functools import wraps

from flask import g, jsonify, request

SECRET = os.getenv("SECRET_KEY", "dev-secret-rotate-me-" + "x" * 16)
TOKEN_TTL = int(os.getenv("TOKEN_TTL", 12 * 3600))

# Role catalogue --------------------------------------------------------------
# tier 1: field reporters, tier 2: clinical/field officers, tier 3: district,
# tier 4: state directorate, lab: laboratory personnel (scoped by lab)
ROLES = {
    "farmer":      {"label": "Individual Farmer", "tier": 1, "scope": "village"},
    "pashu_sakhi": {"label": "Pashu Sakhi (Community Livestock Supervisor)", "tier": 1, "scope": "village"},
    "paravet":     {"label": "Paravet (Auxiliary Veterinary Staff)", "tier": 2, "scope": "taluka"},
    "ldo":         {"label": "Livestock Development Officer (Vet)", "tier": 2, "scope": "taluka"},
    "acah":        {"label": "Assistant Commissioner of Animal Husbandry", "tier": 3, "scope": "district"},
    "dcah":        {"label": "Deputy Commissioner of Animal Husbandry", "tier": 3, "scope": "district"},
    "state":       {"label": "State Directorate / Commissioner (Pune HQ)", "tier": 4, "scope": "state"},
    "lab":         {"label": "Diagnostic Laboratory Personnel", "tier": 2, "scope": "lab"},
    "admin":       {"label": "System Administrator", "tier": 4, "scope": "state"},
}
FIELD_ROLES = ("farmer", "pashu_sakhi", "paravet", "ldo")
OFFICER_ROLES = ("paravet", "ldo", "acah", "dcah", "state", "admin")
CLINICAL_ROLES = ("ldo", "paravet", "acah", "dcah", "state", "admin")
DISTRICT_PLUS = ("acah", "dcah", "state", "admin")
STATE_ROLES = ("state", "admin")


def tier(role): return ROLES.get(role, {}).get("tier", 0)
def scope(role): return ROLES.get(role, {}).get("scope", "village")


# Password hashing ------------------------------------------------------------
def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120_000)
    return f"pbkdf2$120000${salt}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, iters, salt, hexd = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), hexd)
    except Exception:
        return False


# JWT -------------------------------------------------------------------------
def _b64(b: bytes) -> bytes: return base64.urlsafe_b64encode(b).rstrip(b"=")
def _unb64(s: bytes) -> bytes: return base64.urlsafe_b64decode(s + b"=" * (-len(s) % 4))


def issue_token(user: dict) -> str:
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    claims = {"sub": user["id"], "role": user["role"], "iat": int(time.time()), "exp": int(time.time()) + TOKEN_TTL}
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    sig = _b64(hmac.new(SECRET.encode(), header + b"." + payload, hashlib.sha256).digest())
    return (header + b"." + payload + b"." + sig).decode()


def decode_token(token: str) -> dict | None:
    try:
        h, p, s = token.encode().split(b".")
        expected = _b64(hmac.new(SECRET.encode(), h + b"." + p, hashlib.sha256).digest())
        if not hmac.compare_digest(s, expected):
            return None
        body = json.loads(_unb64(p))
        return body if body.get("exp", 0) >= time.time() else None
    except Exception:
        return None


def bearer_claims() -> dict | None:
    value = request.headers.get("Authorization", "")
    if value.startswith("Bearer "):
        return decode_token(value[7:].strip())
    alt = request.headers.get("X-Auth-Token")  # some reverse proxies strip Authorization
    if alt:
        return decode_token(alt.strip())
    tok = request.args.get("token")  # SSE (EventSource cannot set headers)
    return decode_token(tok) if tok else None


def public_user(u: dict) -> dict:
    return {k: v for k, v in u.items() if k != "password_hash"}


def require_auth(*roles):
    """Decorator: loads g.user from the JWT and optionally enforces roles."""
    def deco(fn):
        @wraps(fn)
        def wrapped(*a, **kw):
            from .db import db, one
            claims = bearer_claims()
            if not claims:
                return jsonify(error="authentication required"), 401
            with db() as c:
                u = one(c.execute("SELECT * FROM users WHERE id=? AND active=1", (claims["sub"],)))
            if not u:
                return jsonify(error="account not found or disabled"), 401
            if roles and u["role"] not in roles:
                return jsonify(error="forbidden", required_roles=sorted(roles), your_role=u["role"]), 403
            g.user = u
            return fn(*a, **kw)
        return wrapped
    return deco


# Hierarchical data isolation -------------------------------------------------
def scope_clause(user: dict, alias: str = "", reporter_col: str | None = "reporter_id"):
    """SQL fragment restricting rows to the caller's jurisdiction.

    state/admin -> everything; district roles -> own district; taluka roles ->
    own taluka; village roles -> own village OR rows they created.
    Returns (sql, params) with sql beginning with ' AND ...' or ''."""
    p = f"{alias}." if alias else ""
    s = scope(user["role"])
    if s == "state":
        return "", ()
    if s == "district" and user.get("district_code"):
        if reporter_col:
            return f" AND ({p}district_code=? OR {p}{reporter_col}=?)", (user["district_code"], user["id"])
        return f" AND {p}district_code=?", (user["district_code"],)
    if s == "taluka" and user.get("taluka_code"):
        if reporter_col:
            return f" AND ({p}taluka_code=? OR {p}{reporter_col}=?)", (user["taluka_code"], user["id"])
        return f" AND {p}taluka_code=?", (user["taluka_code"],)
    if s == "lab":
        return "", ()  # lab visibility is applied per-query on lab_id
    parts, params = [], []
    if user.get("village_code"):
        parts.append(f"{p}village_code=?"); params.append(user["village_code"])
    if reporter_col:
        parts.append(f"{p}{reporter_col}=?"); params.append(user["id"])
    if not parts:
        return " AND 0", ()
    return " AND (" + " OR ".join(parts) + ")", tuple(params)


def can_access_row(user: dict, row: dict, owner_cols=("reporter_id", "owner_id", "collected_by")) -> bool:
    s = scope(user["role"])
    if s == "state":
        return True
    if any(row.get(c) == user["id"] for c in owner_cols):
        return True  # you can always see what you created / own
    if s == "district":
        return row.get("district_code") == user.get("district_code")
    if s == "taluka":
        return row.get("taluka_code") == user.get("taluka_code")
    if s == "lab":
        return True
    if row.get("village_code") and row.get("village_code") == user.get("village_code"):
        return True
    return any(row.get(c) == user["id"] for c in owner_cols)
