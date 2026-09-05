"""SIH26128 animal-health surveillance API. SQLite is the local offline MVP store."""
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
import base64, hashlib, hmac, json, os, re, sqlite3, uuid
import joblib
import pandas as pd
from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from geo_engine import vector_risk, weather_etl_stub, resolve_coordinates, cases_to_geojson, case_to_feature
from notification_service import notifications, publish_priority_alert, queue_outbreak_notifications
from triage_engine import assess_triage
from spatial import nearest_clinics
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "server")); import access_control as ac
from i18n import translate, LANGUAGES, DEFAULT_LANG, normalise, engine as i18n_engine

BASE_DIR = Path(__file__).resolve().parent; DB_PATH = BASE_DIR / "data" / "surveillance.db"; EAR_TAG_RE = re.compile(r"^\d{12}$")
DISEASE_DATA_PATH = BASE_DIR / "ml" / "data" / "livestock_disease_risk.csv"
ANTHRAX_DATA_PATH = BASE_DIR / "ml" / "data" / "anthrax_2020_2023.csv"
MODEL_PATH = BASE_DIR / "ml" / "livestock_risk_model.pkl"
STATE_TRANSITIONS = {"REPORTED":{"FIELD_INSPECTED_BY_LDO"},"FIELD_INSPECTED_BY_LDO":{"SAMPLE_COLLECTED","CASE_RESOLVED"},"SAMPLE_COLLECTED":{"LAB_TRANSIT"},"LAB_TRANSIT":{"LAB_RECEIVED"},"LAB_RECEIVED":{"PATHOGEN_CONFIRMED","PATHOGEN_REJECTED"},"PATHOGEN_CONFIRMED":{"CASE_RESOLVED"},"PATHOGEN_REJECTED":{"CASE_RESOLVED"},"CASE_RESOLVED":set()}
# The role dashboards write human-readable labels into the same `status` column as
# the canonical state machine.  Canonicalising on read keeps /transition reachable
# for a case that a dashboard has already touched.
LEGACY_TO_CANONICAL = {"Pending Review":"REPORTED","Inspected":"FIELD_INSPECTED_BY_LDO","Escalated":"FIELD_INSPECTED_BY_LDO","Under Veterinary Review":"FIELD_INSPECTED_BY_LDO","Sample Collection Pending":"SAMPLE_COLLECTED","District Escalated":"LAB_TRANSIT","State Escalated":"LAB_RECEIVED","Monitoring":"LAB_RECEIVED","Containment Active":"PATHOGEN_CONFIRMED","Resolved":"CASE_RESOLVED"}
def canonical_status(status): return LEGACY_TO_CANONICAL.get(status,status)
ROLE_TIERS = {"farmer":1,"pashu_sakhi":1,"ldo":2,"acah":3,"dcah":4,"admin":4,"paravet":2,"vet":2,"district":3,"state":4}
app = Flask(__name__); app.config.update(SECRET_KEY=os.getenv("SECRET_KEY", "replace-this-development-secret"), JSON_SORT_KEYS=False)
try:
    disease_df = pd.read_csv(DISEASE_DATA_PATH, sep="\t"); disease_df.columns = disease_df.columns.str.strip()
except Exception: disease_df = pd.DataFrame()
try:
    anthrax_df = pd.read_csv(ANTHRAX_DATA_PATH); anthrax_df.columns = anthrax_df.columns.str.strip()
except Exception: anthrax_df = pd.DataFrame()
try: model = joblib.load(MODEL_PATH)
except Exception: model = None
def utcnow(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
def _hours_ago_iso(hours): return (datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat(timespec="milliseconds")
def issue_token(u):
    """HS256 JWT for mobile/API clients; production should delegate to Gov OAuth2 IdP."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=')
    keys=u.keys() if hasattr(u,"keys") else ()
    claims={"sub":u["id"],"role":u["role"],"district_code":u["district_code"] if "district_code" in keys else None,"village_code":u["village_code"] if "village_code" in keys else None,"taluka_code":u["taluka_code"] if "taluka_code" in keys else None,"exp":int(datetime.now().timestamp())+3600}
    payload = base64.urlsafe_b64encode(json.dumps(claims,separators=(',',':')).encode()).rstrip(b'=')
    signature = base64.urlsafe_b64encode(hmac.new(app.config["SECRET_KEY"].encode(),header+b'.'+payload,hashlib.sha256).digest()).rstrip(b'=')
    return (header+b'.'+payload+b'.'+signature).decode()
def token_subject():
    value=request.headers.get("Authorization","")
    if not value.startswith("Bearer "): return None
    try:
        h,p,s=value[7:].encode().split(b'.'); expected=base64.urlsafe_b64encode(hmac.new(app.config["SECRET_KEY"].encode(),h+b'.'+p,hashlib.sha256).digest()).rstrip(b'=')
        if not hmac.compare_digest(s,expected): return None
        body=json.loads(base64.urlsafe_b64decode(p+b'='*(-len(p)%4)))
        return body["sub"] if body["exp"]>=int(datetime.now().timestamp()) else None
    except (ValueError, KeyError, json.JSONDecodeError): return None
def db():
    DB_PATH.parent.mkdir(exist_ok=True); c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c
def init_db():
    with db() as c:
        c.executescript("""PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,village_code TEXT,district_code TEXT,language TEXT DEFAULT 'en');
        CREATE TABLE IF NOT EXISTS livestock_records(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL REFERENCES users(id),ear_tag TEXT NOT NULL UNIQUE CHECK(length(ear_tag)=12),species TEXT NOT NULL,breed TEXT,village_code TEXT NOT NULL,updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,reporter_id TEXT NOT NULL REFERENCES users(id),village_code TEXT NOT NULL,district_code TEXT,channel TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,triage TEXT NOT NULL,updated_at INTEGER NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lab_referrals(id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES cases(id),barcode_uid TEXT UNIQUE NOT NULL,sample_type TEXT NOT NULL,transport_media TEXT,cold_chain_ok INTEGER NOT NULL,lab_result TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS weather_telemetry(id TEXT PRIMARY KEY,village_code TEXT NOT NULL,humidity REAL,temperature_anomaly REAL,precipitation_mm REAL,observed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vaccinations(id TEXT PRIMARY KEY,livestock_id TEXT NOT NULL REFERENCES livestock_records(id),vaccine_name TEXT NOT NULL,administered_on TEXT NOT NULL,next_due_on TEXT,administered_by TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS treatments(id TEXT PRIMARY KEY,livestock_id TEXT NOT NULL REFERENCES livestock_records(id),diagnosis TEXT,treatment TEXT NOT NULL,treated_at TEXT NOT NULL,clinician_id TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS veterinary_centers(id TEXT PRIMARY KEY,name TEXT NOT NULL,district_code TEXT,taluka_code TEXT,lat REAL NOT NULL,lng REAL NOT NULL,officer_phone TEXT);""")
        # Lightweight forward-migration: add taluka_code to older DBs that predate it.
        for table in ("users","cases"):
            cols={r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            if "taluka_code" not in cols: c.execute(f"ALTER TABLE {table} ADD COLUMN taluka_code TEXT")
        # Seed real Maharashtra veterinary centers (EPSG:4326) with officer contacts.
        vet_centers=[
            ("vc-pune","Pune District Veterinary Polyclinic","MH-PUNE","TAL-HAVELI",18.5204,73.8567,"+91-20-2612-3456"),
            ("vc-haveli","Haveli Taluka Veterinary Dispensary","MH-PUNE","TAL-HAVELI",18.4636,73.8683,"+91-20-2695-1122"),
            ("vc-mulshi","Mulshi Veterinary Clinic","MH-PUNE","TAL-MULSHI",18.5100,73.5100,"+91-20-2522-3344"),
            ("vc-baramati","Baramati Veterinary Hospital","MH-PUNE","TAL-BARAMATI",18.1514,74.5772,"+91-2112-22-5566"),
            ("vc-nagpur","Nagpur Regional Veterinary Hospital","MH-NAGPUR","TAL-NAGPUR",21.1458,79.0882,"+91-712-256-7788"),
            ("vc-beed","Beed District Veterinary Center","MH-BEED","TAL-BEED",18.9891,75.7601,"+91-2442-22-3399"),
            ("vc-jalna","Jalna Taluka Veterinary Dispensary","MH-JALNA","TAL-JALNA",19.8410,75.8864,"+91-2482-23-4455"),
            ("vc-nashik","Nashik Veterinary Polyclinic","MH-NASHIK","TAL-NASHIK",19.9975,73.7898,"+91-253-257-9900"),
        ]
        c.executemany("INSERT OR IGNORE INTO veterinary_centers VALUES(?,?,?,?,?,?,?)",vet_centers)
        rows=[("u-farmer","farmer1","1234","farmer","271000100001","MH-PUNE","mr"),("u-sakhi","sakhi1","1234","pashu_sakhi","271000100001","MH-PUNE","mr"),("u-ldo","ldo1","1234","ldo","271000100001","MH-PUNE","en"),("u-acah","acah1","1234","acah",None,"MH-PUNE","en"),("u-admin","admin","1234","admin",None,None,"mr"),("u-paravet","paravet1","1234","paravet","271000100001","MH-PUNE","en"),("u-vet","vet1","1234","vet","271000100001","MH-PUNE","en"),("u-district","district1","1234","district",None,"MH-PUNE","en")]
        c.executemany("INSERT OR IGNORE INTO users(id,username,password,role,village_code,district_code,language) VALUES (?,?,?,?,?,?,?)",rows)
        # Assign taluka jurisdiction to the demo field/authority users (LGD taluka codes).
        c.executemany("UPDATE users SET taluka_code=? WHERE id=?",[("TAL-HAVELI","u-farmer"),("TAL-HAVELI","u-sakhi"),("TAL-HAVELI","u-ldo"),("TAL-HAVELI","u-paravet"),("TAL-HAVELI","u-vet")])
def user():
    subject=session.get("user_id") or token_subject()
    if not subject: return None
    with db() as c: return c.execute("SELECT * FROM users WHERE id=?",(subject,)).fetchone()
def wants_json(): return request.path.startswith(("/api/","/webhooks/")) or request.accept_mimetypes.best=="application/json"
def current_language():
    # API/mobile/IVR callers signal language per-request (Accept-Language or
    # ?lang=); browser sessions carry it in the cookie / user profile.
    if request.path.startswith(("/api/","/webhooks/")):
        header=request.headers.get("Accept-Language",""); q=request.args.get("lang") or request.values.get("lang")
        if header or q: return i18n_engine.resolve_lang(request)
    lang=session.get("lang")
    if not lang:
        u=user(); lang=(u["language"] if u and "language" in u.keys() else None) or DEFAULT_LANG
    return normalise(lang)
@app.after_request
def i18n_transform(response):
    # Translate dynamic string values in JSON API/webhook payloads to the
    # caller's language before they reach web/mobile/IVR/WhatsApp clients.
    try:
        if response.is_json and request.path.startswith(("/api/","/webhooks/")):
            lang=current_language()
            if lang!=DEFAULT_LANG:
                data=response.get_json(silent=True)
                if data is not None:
                    response.set_data(json.dumps(i18n_engine.translate_payload(data,lang)))
    except Exception:
        pass  # never let translation break a response
    return response
@app.context_processor
def inject_i18n():
    lang=current_language(); return {"t":lambda key:translate(key,lang),"current_lang":lang,"languages":LANGUAGES}
def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapped(*a,**kw):
            u=user()
            if not u: return (jsonify(error="authentication required"),401) if wants_json() else redirect(url_for("login"))
            if u["role"] not in roles:
                if wants_json(): return jsonify(error="forbidden",required_roles=sorted(roles),your_role=u["role"]),403
                return render_template("403.html",user=u,required_roles=sorted(roles)),403
            return fn(*a,**kw)
        return wrapped
    return deco
def allowed(case,u): return ROLE_TIERS[u["role"]]>=4 or (ROLE_TIERS[u["role"]]==3 and case["district_code"]==u["district_code"]) or case["village_code"]==u["village_code"] or case["reporter_id"]==u["id"]
def validate(p):
    miss=[x for x in ("village_code","species") if not p.get(x)]
    if miss:return "Missing required fields: "+", ".join(miss)
    if p.get("ear_tag") and not EAR_TAG_RE.fullmatch(str(p["ear_tag"])):return "ear_tag must contain exactly 12 numeric digits"
def norm(value): return str(value or "").strip().casefold()
def districts_for_state(state):
    if disease_df.empty or not {"State Name","District Name"}.issubset(disease_df.columns): return []
    values=disease_df.loc[disease_df["State Name"].map(norm)==norm(state),"District Name"].dropna().astype(str).str.strip().unique().tolist()
    return sorted(value for value in values if value and norm(value)!="nan")
def surveillance_signals(district):
    if disease_df.empty:return 0,[]
    rows=disease_df[(disease_df["State Name"].map(norm)=="maharashtra") & (disease_df["District Name"].map(norm)==norm(district))]
    alerts=[]
    for _,row in rows.iterrows():
        level=str(row.get("Predicted","Low Risk")); score=3 if "very high" in norm(level) else 2 if "high" in norm(level) else 1 if "medium" in norm(level) else 0
        alerts.append({"disease":str(row.get("Disease Name","Unknown")),"month":str(row.get("Month","")),"risk_level":level,"score":score})
    alerts.sort(key=lambda item:item["score"],reverse=True)
    return (alerts[0]["score"] if alerts else 0),alerts
def anthrax_history(district):
    if anthrax_df.empty or not {"State","District"}.issubset(anthrax_df.columns):return (0,0,0)
    rows=anthrax_df[(anthrax_df["State"].map(norm)=="maharashtra") & (anthrax_df["District"].map(norm)==norm(district))]
    def total(column): return int(pd.to_numeric(rows.get(column,pd.Series(dtype=float)),errors="coerce").fillna(0).sum())
    return total("Outbreaks"),total("Attacks"),total("Deaths")
def save_case(p,channel,actor):
    error=validate(p)
    if error:return None,error
    cid=p.get("id") or "MH-"+uuid.uuid4().hex[:12].upper(); client=int(p.get("updated_at",0) or 0); now=int(datetime.now().timestamp()*1000)
    with db() as c:
        old=c.execute("SELECT * FROM cases WHERE id=?",(cid,)).fetchone()
        if old and client<=old["updated_at"]:
            # Last-write-wins: a stale offline replay loses. Decode triage so every
            # caller receives the same dict shape as the insert path below.
            stale=dict(old); stale["triage"]=json.loads(stale["triage"]); return stale,None
        # Layer B input: most recent local weather within 72h for this village.
        wx=c.execute("SELECT humidity AS humidity_percent,temperature_anomaly AS temperature_c,observed_at FROM weather_telemetry WHERE village_code=? AND observed_at>=? ORDER BY observed_at DESC LIMIT 1",(p["village_code"],_hours_ago_iso(72))).fetchone()
        triage=assess_triage(p,weather=dict(wx) if wx else None)
        actor_keys=actor.keys() if hasattr(actor,"keys") else ()
        taluka=p.get("taluka_code") or (actor["taluka_code"] if "taluka_code" in actor_keys else None)
        values=(cid,actor["id"],p["village_code"],p.get("district_code",actor["district_code"]),channel,old["status"] if old else "REPORTED",json.dumps(p),json.dumps(triage),max(client,now),utcnow(),taluka)
        c.execute("INSERT INTO cases(id,reporter_id,village_code,district_code,channel,status,payload,triage,updated_at,created_at,taluka_code) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,triage=excluded.triage,updated_at=excluded.updated_at",values); case=dict(c.execute("SELECT * FROM cases WHERE id=?",(cid,)).fetchone())
    case["triage"]=triage
    # Escalation: a HIGH / >=0.75 probability outbreak pushes an immediate SSE
    # priority alert to the assigned local Veterinary Officer's clinic dashboard.
    if triage["level"]=="HIGH":
        publish_priority_alert(case)
        notifications.publish({"type":"PRIORITY_ALERT","case_id":case["id"],"district_code":case["district_code"],"village_code":case["village_code"],"suspected_disease":triage.get("suspected_disease"),"probability":triage.get("probability"),"risk_level":triage["level"],"priority":"immediate","issued_at":utcnow()})
    return case,None
def case_view(row):
    """Compatibility adapter for the existing Paravet/Vet/District dashboard JavaScript."""
    payload=json.loads(row["payload"]); triage=json.loads(row["triage"])
    dashboard_status={"REPORTED":"Pending Review","FIELD_INSPECTED_BY_LDO":"Inspected"}.get(row["status"],row["status"])
    return {"case_id":row["id"],"id":row["id"],"status":dashboard_status,"state":"Maharashtra","district":row["district_code"],"village":payload.get("village",payload.get("village_code")),"animal_type":payload.get("species","cattle"),"affected":payload.get("mortality_count",payload.get("affected",0)),"symptoms":payload.get("symptoms",[]),"age":payload.get("age",""),"duration":payload.get("duration",""),"risk_score":triage.get("score",0),"risk_level":triage.get("level","LOW"),"disease_name":", ".join(triage.get("signals",[])),"created_at":row["created_at"],"sample_status":payload.get("sample_status","Pending Collection")}
def visible_rows(u):
    with db() as c: rows=[dict(r) for r in c.execute("SELECT * FROM cases ORDER BY created_at DESC")]
    return [r for r in rows if allowed(r,u)]
def legacy_status(case_id, status):
    # Legacy dashboard labels map back to the production workflow states.
    status={"Pending Review":"REPORTED","Inspected":"FIELD_INSPECTED_BY_LDO"}.get(status,status)
    with db() as c:
        row=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
        if not row:return None
        c.execute("UPDATE cases SET status=?,updated_at=? WHERE id=?",(status,int(datetime.now().timestamp()*1000),case_id))
        return dict(c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone())

@app.route("/")
def home():return redirect(url_for("dashboard") if user() else url_for("login"))
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        with db() as c:u=c.execute("SELECT * FROM users WHERE username=? AND password=?",(request.form.get("username",""),request.form.get("password",""))).fetchone()
        if u:session.clear();session.update(user_id=u["id"],user=u["username"],role=u["role"],lang=normalise(u["language"] if "language" in u.keys() else DEFAULT_LANG));return redirect(url_for("dashboard"))
        return render_template("login.html",error="Invalid username or password.")
    return render_template("login.html")
@app.post("/api/v1/auth/token")
def token():
    """OAuth2 password-grant-compatible development endpoint (replace with IdP in production)."""
    values=request.get_json(silent=True) or request.form
    with db() as c:u=c.execute("SELECT * FROM users WHERE username=? AND password=?",(values.get("username",""),values.get("password",""))).fetchone()
    if not u:return jsonify(error="invalid credentials"),401
    return jsonify(access_token=issue_token(u),token_type="Bearer",expires_in=3600,role=u["role"])
@app.route("/logout")
def logout():session.clear();return redirect(url_for("login"))
@app.get("/set-language/<lang>")
def set_language(lang):
    session["lang"]=normalise(lang); u=user()
    if u:
        with db() as c:c.execute("UPDATE users SET language=? WHERE id=?",(session["lang"],u["id"]))
    return redirect(request.referrer or url_for("login"))
@app.route("/dashboard")
def dashboard():
    u=user()
    if not u:return redirect(url_for("login"))
    routes={"farmer":"farmer_dashboard","pashu_sakhi":"farmer_dashboard","paravet":"paravet_dashboard","vet":"vet_dashboard","district":"district_dashboard","state":"state_dashboard","admin":"state_dashboard","dcah":"state_dashboard","ldo":"vet_dashboard","acah":"district_dashboard"}
    return redirect(url_for(routes[u["role"]])) if u["role"] in routes else render_template("dashboard.html",user=u)
@app.route("/farmer")
@role_required("farmer","pashu_sakhi")
def farmer_dashboard():return render_template("dashboards/farmer.html")
@app.route("/paravet")
@role_required("paravet")
def paravet_dashboard():return render_template("dashboards/paravet.html")
@app.route("/vet")
@role_required("vet","ldo")
def vet_dashboard():return render_template("dashboards/vet.html")
@app.route("/district")
@role_required("district","acah")
def district_dashboard():return render_template("dashboards/district.html")
@app.route("/state")
@role_required("state","admin","dcah")
def state_dashboard():return render_template("dashboards/state.html")
@app.get("/districts/<state>")
@role_required("farmer","pashu_sakhi","paravet")
def districts(state):
    return jsonify(districts=districts_for_state(state))

@app.post("/api/v1/reports/mobile/sync")
@role_required("farmer","pashu_sakhi","ldo")
def mobile_sync():
    reports=(request.get_json(silent=True) or {}).get("reports",[])
    if not isinstance(reports,list):return jsonify(error="reports must be an array"),400
    result=[]
    for p in reports:
        case,error=save_case(p,"mobile",user());result.append({"id":p.get("id"),"case":case,"error":error})
    return jsonify(results=result,sync_at=utcnow())
@app.post("/api/v1/reports/web")
@role_required("farmer","pashu_sakhi","ldo")
def web_report():
    case,error=save_case(request.get_json(silent=True) or request.form.to_dict(flat=True),"web",user());return (jsonify(case=case),201) if not error else (jsonify(error=error),400)
@app.post("/webhooks/ivr")
def ivr():
    d=request.values.get("Digits","");p={"village_code":request.values.get("village_code",""),"species":request.values.get("species","cattle"),"mortality_count":{"1":0,"2":1,"3":3}.get(d,0),"symptoms":["ivr_report"],"updated_at":int(datetime.now().timestamp()*1000)}; _,e=save_case(p,"ivr",{"id":"u-sakhi","district_code":"MH-PUNE"});return Response("<Response><Say>Report recorded.</Say></Response>" if not e else "<Response><Say>Invalid report.</Say></Response>",mimetype="text/xml")
@app.post("/webhooks/whatsapp")
def whatsapp():
    b=request.get_json(silent=True) or request.form.to_dict();p={"village_code":b.get("village_code",""),"species":b.get("species","cattle"),"symptoms":[x.strip() for x in b.get("Body",b.get("text","")).split(",") if x.strip()],"mortality_count":int(b.get("mortality_count",0)),"updated_at":int(datetime.now().timestamp()*1000)};case,e=save_case(p,"whatsapp",{"id":"u-sakhi","district_code":"MH-PUNE"});return jsonify(status="accepted" if not e else "rejected",case_id=case["id"] if case else None,error=e)
@app.get("/api/v1/cases")
def cases():
    u=user()
    if not u:return jsonify(error="authentication required"),401
    with db() as c:rows=[dict(r) for r in c.execute("SELECT * FROM cases ORDER BY created_at DESC")]
    return jsonify([r for r in rows if allowed(r,u)])

# Compatibility endpoints used by the existing dashboard templates.  New clients
# should use /api/v1/cases and the documented state-machine endpoints instead.
@app.get("/api/paravet/cases")
@role_required("paravet")
def paravet_cases():return jsonify([case_view(r) for r in visible_rows(user())])
@app.get("/case/<case_id>")
@role_required("paravet")
def paravet_case_details(case_id):
    with db() as c: row=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
    return jsonify(case_view(row)) if row and allowed(row,user()) else (jsonify(error="Case not found."),404)
@app.post("/api/paravet/cases/<case_id>/status")
@role_required("paravet")
def paravet_status(case_id):
    status=(request.get_json(silent=True) or {}).get("status")
    if status not in {"Pending Review","Inspected","Escalated"}:return jsonify(error="Invalid status."),400
    row=legacy_status(case_id,status)
    return jsonify(success=True,case=case_view(row)) if row else (jsonify(error="Case not found."),404)
@app.get("/api/vet/cases")
@role_required("vet","ldo")
def vet_cases():return jsonify([case_view(r) for r in visible_rows(user()) if r["status"] in {"Escalated","Under Veterinary Review","Sample Collection Pending","District Escalated"}])
@app.get("/vet/case/<case_id>")
@app.get("/api/vet/cases/<case_id>")  # canonical URL used by dashboards/vet.html
@role_required("vet","ldo")
def vet_case_details(case_id):
    with db() as c: row=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
    return jsonify(case_view(row)) if row and allowed(row,user()) else (jsonify(error="Case not found."),404)
@app.post("/api/vet/cases/<case_id>/status")
@role_required("vet","ldo")
def vet_status(case_id):
    status=(request.get_json(silent=True) or {}).get("status")
    if status not in {"Under Veterinary Review","Sample Collection Pending","District Escalated"}:return jsonify(error="Invalid veterinary status."),400
    row=legacy_status(case_id,status);return jsonify(success=True,case=case_view(row)) if row else (jsonify(error="Case not found."),404)
@app.post("/api/vet/cases/<case_id>/sample")
@role_required("vet","ldo")
def vet_sample(case_id):
    status=(request.get_json(silent=True) or {}).get("sample_status")
    if status not in {"Pending Collection","Collected","Sent to Lab"}:return jsonify(error="Invalid sample status."),400
    with db() as c:
        row=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
        if not row:return jsonify(error="Case not found."),404
        payload=json.loads(row["payload"]);payload["sample_status"]=status;c.execute("UPDATE cases SET payload=?,status=? WHERE id=?",(json.dumps(payload),"District Escalated" if status=="Sent to Lab" else "Sample Collection Pending",case_id));row=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
    return jsonify(success=True,case=case_view(row))
@app.get("/api/district/cases")
@role_required("district","acah")
def district_cases():
    """District surveillance queue: retain all cases in the officer's district,
    including those already forwarded to the State Directorate."""
    return jsonify([case_view(r) for r in visible_rows(user())])
@app.get("/district/case/<case_id>")
@app.get("/api/district/cases/<case_id>")
@role_required("district","acah")
def district_case_details(case_id):
    with db() as c: row=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
    return jsonify(case_view(row)) if row and allowed(row,user()) else (jsonify(error="Case not found."),404)
@app.post("/api/district/cases/<case_id>/status")
@role_required("district","acah")
def district_status(case_id):
    status=(request.get_json(silent=True) or {}).get("status")
    if status not in {"Monitoring","Resolved","State Escalated"}:return jsonify(error="Invalid district status."),400
    row=legacy_status(case_id,status);return jsonify(success=True,case=case_view(row)) if row else (jsonify(error="Case not found."),404)
@app.get("/api/state/cases")
@role_required("state","admin","dcah")
def state_cases():return jsonify([case_view(r) for r in visible_rows(user()) if r["status"]=="State Escalated"])
@app.get("/state/case/<case_id>")
@role_required("state","admin","dcah")
def state_case_details(case_id):
    with db() as c: row=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
    return jsonify(case_view(row)) if row else (jsonify(error="Case not found."),404)
@app.post("/api/state/cases/<case_id>/status")
@role_required("state","admin","dcah")
def state_status(case_id):
    status=(request.get_json(silent=True) or {}).get("status")
    if status not in {"Containment Active","Monitoring","Resolved"}:return jsonify(error="Invalid state status."),400
    row=legacy_status(case_id,status);return jsonify(success=True,case=case_view(row)) if row else (jsonify(error="Case not found."),404)
@app.post("/api/v1/cases/<case_id>/transition")
@role_required("ldo","acah","dcah","admin","vet","district")
def transition(case_id):
    wanted=(request.get_json(silent=True) or {}).get("status")
    with db() as c:
        case=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
        if not case:return jsonify(error="case not found"),404
        if not allowed(case,user()):return jsonify(error="forbidden"),403
        current=canonical_status(case["status"]); permitted=STATE_TRANSITIONS.get(current,set())
        if wanted not in permitted:return jsonify(error="invalid state transition",current_status=current,allowed=sorted(permitted)),400
        c.execute("UPDATE cases SET status=?,updated_at=? WHERE id=?",(wanted,int(datetime.now().timestamp()*1000),case_id))
    return jsonify(success=True,status=wanted)
@app.post("/api/v1/cases/<case_id>/lab-referrals")
@role_required("ldo","vet")
def referral(case_id):
    x=request.get_json(silent=True) or {};stype=x.get("sample_type")
    if stype not in {"Serum","Swab","Blood","Scab"}:return jsonify(error="invalid sample_type"),400
    barcode="MH"+uuid.uuid4().hex.upper()[:22];row=(str(uuid.uuid4()),case_id,barcode,stype,x.get("transport_media",""),int(bool(x.get("cold_chain_ok",False))),None,"SCHEDULED",utcnow())
    with db() as c:c.execute("INSERT INTO lab_referrals VALUES(?,?,?,?,?,?,?,?,?)",row)
    return jsonify(referral_id=row[0],barcode_uid=barcode),201
@app.get("/api/v1/cases/<case_id>/lab-referrals")
def list_referrals(case_id):
    u=user()
    if not u:return jsonify(error="authentication required"),401
    with db() as c:
        case=c.execute("SELECT * FROM cases WHERE id=?",(case_id,)).fetchone()
        if not case:return jsonify(error="case not found"),404
        if not allowed(case,u):return jsonify(error="forbidden"),403
        rows=[dict(r) for r in c.execute("SELECT * FROM lab_referrals WHERE case_id=? ORDER BY created_at DESC",(case_id,))]
    return jsonify(rows)
@app.post("/api/v1/lab-referrals/<referral_id>/result")
@role_required("ldo","vet","acah","dcah","admin")
def referral_result(referral_id):
    x=request.get_json(silent=True) or {};result=x.get("lab_result")
    if not result:return jsonify(error="lab_result is required"),400
    with db() as c:
        row=c.execute("SELECT * FROM lab_referrals WHERE id=?",(referral_id,)).fetchone()
        if not row:return jsonify(error="referral not found"),404
        c.execute("UPDATE lab_referrals SET lab_result=?,status=? WHERE id=?",(result,x.get("status","RESULT_READY"),referral_id))
    return jsonify(success=True,referral_id=referral_id,lab_result=result)

# ---- Animal-level / herd-level Health Records Ledger ---------------------
@app.post("/api/v1/livestock")
@role_required("farmer","pashu_sakhi","ldo","vet","paravet")
def create_livestock():
    x=request.get_json(silent=True) or request.form.to_dict(flat=True);u=user()
    tag=str(x.get("ear_tag","")).strip()
    if not EAR_TAG_RE.fullmatch(tag):return jsonify(error="ear_tag must contain exactly 12 numeric digits"),400
    if not x.get("species"):return jsonify(error="species is required"),400
    row=(str(uuid.uuid4()),u["id"],tag,x["species"],x.get("breed"),x.get("village_code") or u["village_code"] or "271000100001",int(datetime.now().timestamp()*1000))
    try:
        with db() as c:c.execute("INSERT INTO livestock_records VALUES(?,?,?,?,?,?,?)",row)
    except sqlite3.IntegrityError:return jsonify(error="ear_tag already registered"),409
    return jsonify(id=row[0],ear_tag=tag,species=x["species"]),201
@app.get("/api/v1/livestock")
def list_livestock():
    u=user()
    if not u:return jsonify(error="authentication required"),401
    with db() as c:
        if ROLE_TIERS[u["role"]]>=3:rows=c.execute("SELECT * FROM livestock_records ORDER BY updated_at DESC").fetchall()
        else:rows=c.execute("SELECT * FROM livestock_records WHERE owner_id=? OR village_code=? ORDER BY updated_at DESC",(u["id"],u["village_code"])).fetchall()
    return jsonify([dict(r) for r in rows])
@app.get("/api/v1/livestock/<livestock_id>")
def livestock_ledger(livestock_id):
    u=user()
    if not u:return jsonify(error="authentication required"),401
    with db() as c:
        animal=c.execute("SELECT * FROM livestock_records WHERE id=? OR ear_tag=?",(livestock_id,livestock_id)).fetchone()
        if not animal:return jsonify(error="animal not found"),404
        lid=animal["id"]
        vac=[dict(r) for r in c.execute("SELECT * FROM vaccinations WHERE livestock_id=? ORDER BY administered_on DESC",(lid,))]
        tre=[dict(r) for r in c.execute("SELECT * FROM treatments WHERE livestock_id=? ORDER BY treated_at DESC",(lid,))]
    return jsonify(animal=dict(animal),vaccinations=vac,treatments=tre)
@app.post("/api/v1/livestock/<livestock_id>/vaccinations")
@role_required("vet","ldo","paravet","pashu_sakhi")
def add_vaccination(livestock_id):
    x=request.get_json(silent=True) or request.form.to_dict(flat=True);u=user()
    if not x.get("vaccine_name"):return jsonify(error="vaccine_name is required"),400
    with db() as c:
        if not c.execute("SELECT 1 FROM livestock_records WHERE id=?",(livestock_id,)).fetchone():return jsonify(error="animal not found"),404
        row=(str(uuid.uuid4()),livestock_id,x["vaccine_name"],x.get("administered_on",utcnow()[:10]),x.get("next_due_on"),u["id"],utcnow())
        c.execute("INSERT INTO vaccinations VALUES(?,?,?,?,?,?,?)",row)
    return jsonify(id=row[0],vaccine_name=x["vaccine_name"]),201
@app.post("/api/v1/livestock/<livestock_id>/treatments")
@role_required("vet","ldo","paravet")
def add_treatment(livestock_id):
    x=request.get_json(silent=True) or request.form.to_dict(flat=True);u=user()
    if not x.get("treatment"):return jsonify(error="treatment is required"),400
    with db() as c:
        if not c.execute("SELECT 1 FROM livestock_records WHERE id=?",(livestock_id,)).fetchone():return jsonify(error="animal not found"),404
        row=(str(uuid.uuid4()),livestock_id,x.get("diagnosis"),x["treatment"],x.get("treated_at",utcnow()),u["id"],utcnow())
        c.execute("INSERT INTO treatments VALUES(?,?,?,?,?,?,?)",row)
    return jsonify(id=row[0],treatment=x["treatment"]),201

@app.post("/api/v1/weather/etl")
@role_required("admin","dcah")
def etl():
    payload=request.get_json(silent=True) or {}; accepted=0
    with db() as c:
        for obs in payload.get("observations",[]):
            if not obs.get("village_code"):continue
            c.execute("INSERT INTO weather_telemetry(id,village_code,humidity,temperature_anomaly,precipitation_mm,observed_at) VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),obs["village_code"],obs.get("humidity_percent"),obs.get("temperature_anomaly_c"),obs.get("precipitation_mm"),obs.get("observed_at",utcnow())));accepted+=1
    result=weather_etl_stub(payload);result["records_saved"]=accepted
    return jsonify(result),202
@app.get("/api/v1/risk-map/<village_code>")
def risk_map(village_code):
    with db() as c:weather=c.execute("SELECT * FROM weather_telemetry WHERE village_code=? ORDER BY observed_at DESC LIMIT 1",(village_code,)).fetchone()
    projection=vector_risk(village_code); projection["latest_weather"]=dict(weather) if weather else None
    if weather and (weather["humidity"] or 0)>=70 and (weather["precipitation_mm"] or 0)>=10:projection["vector_risk"]="ELEVATED"
    return jsonify(projection)
@app.get("/api/v1/geo/cases.geojson")
def cases_geojson():
    """Live, role-scoped GeoJSON FeatureCollection for the Leaflet surveillance map.
    Points bind to real WGS84 coordinates (device GPS when present, else the
    village/district gazetteer centroid); each feature carries its precision."""
    u=user()
    if not u:return jsonify(error="authentication required"),401
    features=[]
    for row in visible_rows(u):
        payload=json.loads(row["payload"]); cv=case_view(row)
        coords=resolve_coordinates(village_code=row["village_code"],district_code=row["district_code"],district_name=cv.get("district"),lat=payload.get("lat",payload.get("latitude")),lng=payload.get("lng",payload.get("longitude")))
        features.append(case_to_feature(cv,coords))
    return jsonify(cases_to_geojson(features))
@app.route("/api/v1/geo/nearest-clinic",methods=["GET","POST"])
def nearest_clinic():
    """Farmer-facing clinic locator. Accepts decimal latitude/longitude (query
    params or JSON body) and returns the 3 nearest veterinary centers, nearest
    first, each with real distance (km), coordinates and the officer's phone."""
    body=request.get_json(silent=True) or {}
    lat=body.get("latitude",body.get("lat",request.values.get("latitude",request.values.get("lat"))))
    lng=body.get("longitude",body.get("lng",request.values.get("longitude",request.values.get("lng"))))
    with db() as c:
        results=nearest_clinics(c,lat,lng,k=3)
    if results is None:
        return jsonify(error="valid decimal latitude and longitude are required"),400
    return jsonify(query={"lat":float(lat),"lng":float(lng)},count=len(results),clinics=results)
@app.get("/api/v1/analytics/summary")
def analytics_summary():
    """Role-segregated analytics feed enforcing the Directorate's access tiers.

    STATE   -> district-level aggregates ONLY (raw village/farm rows blocked).
    DISTRICT-> taluka + village aggregates WITHIN their own district only.
    LDO/VET -> granular chart feed for their taluka/village (the original
               dashboard contract: village counts, triage mix, channel, trend).
    """
    u=user()
    if not u:return jsonify(error="authentication required"),401
    tier=ac.tier_for(u["role"])

    # STATE: strictly district-aggregated. Any attempt to request a raw row
    # (?scope=raw / ?village=... / ?case_id=...) is explicitly unauthorized.
    if tier=="state":
        if any(k in request.args for k in ("village","village_code","case_id")) or request.args.get("scope")=="raw":
            return jsonify(error="forbidden: state directorate is limited to district-level aggregates",tier="state"),403
        with db() as c:
            sql,params=ac.state_aggregate_sql(); agg=[dict(r) for r in c.execute(sql,params)]
        # Chart-compat fields, aggregated to DISTRICT granularity (never village).
        by_level={"HIGH":sum(r["high_risk"] for r in agg),"MEDIUM":0,"LOW":0}
        top=[{"village":r["district_code"],"cases":r["total_cases"]} for r in agg[:8]]
        return jsonify(tier="state",aggregation="district",districts=agg,total_cases=sum(r["total_cases"] for r in agg),by_level=by_level,top_villages=top,by_channel={},trend=[])

    # DISTRICT: locked to own district_code, aggregated to taluka/village.
    if tier=="district":
        if not u["district_code"]:
            return jsonify(error="district authority has no assigned district_code",tier="district"),403
        # A cross-district lookup is explicitly unauthorized.
        req_district=request.args.get("district_code")
        if req_district and req_district!=u["district_code"]:
            return jsonify(error="forbidden: cross-district access is not authorized",tier="district",your_district=u["district_code"]),403
        with db() as c:
            sql,params=ac.district_aggregate_sql(u["district_code"]); agg=[dict(r) for r in c.execute(sql,params)]
        # Chart-compat fields, aggregated to village granularity WITHIN this district.
        by_level={"HIGH":sum(r["high_risk"] for r in agg),"MEDIUM":0,"LOW":0}
        top=[{"village":(r["village_code"] or "Unknown"),"cases":r["total_cases"]} for r in agg[:8]]
        return jsonify(tier="district",district_code=u["district_code"],aggregation="taluka+village",areas=agg,total_cases=sum(r["total_cases"] for r in agg),by_level=by_level,top_villages=top,by_channel={},trend=[])

    # LDO/VET/field: granular chart feed (unchanged dashboard contract).
    rows=visible_rows(u)
    by_village,by_level,by_channel,by_day={}, {"HIGH":0,"MEDIUM":0,"LOW":0}, {}, {}
    for r in rows:
        triage=json.loads(r["triage"]); payload=json.loads(r["payload"])
        v=payload.get("village",payload.get("village_code","Unknown")); by_village[v]=by_village.get(v,0)+1
        lvl=triage.get("level","LOW"); by_level[lvl]=by_level.get(lvl,0)+1
        by_channel[r["channel"]]=by_channel.get(r["channel"],0)+1
        day=(r["created_at"] or "")[:10]; by_day[day]=by_day.get(day,0)+1
    top=sorted(by_village.items(),key=lambda kv:kv[1],reverse=True)[:8]
    trend=sorted(by_day.items())[-14:]
    return jsonify(tier="ldo",total_cases=len(rows),by_level=by_level,by_channel=by_channel,top_villages=[{"village":k,"cases":v} for k,v in top],trend=[{"date":k,"cases":v} for k,v in trend])
@app.get("/api/v1/ldo/ear-tags")
@role_required("ldo","vet","paravet")
def ldo_ear_tags():
    """Granular Bharat Pashudhan 12-digit ear-tag registry for the officer's
    village — used for daily site-visit planning."""
    u=user()
    with db() as c:
        sql,params=ac.ldo_ear_tags_sql(u["village_code"]); tags=[dict(r) for r in c.execute(sql,params)]
    return jsonify(village_code=u["village_code"],count=len(tags),animals=tags)
@app.post("/api/v1/outbreaks/<case_id>/confirm")
@role_required("dcah","admin")
def confirm(case_id):
    x=request.get_json(silent=True) or {};return jsonify(queue_outbreak_notifications(case_id,x.get("radius_km",5),x.get("language","mr")))
@app.get("/api/v1/events")
def events():
    def stream():
        yield "event: ready\ndata: {\"status\":\"connected\"}\n\n"
        for e in notifications.drain():yield f"event: priority_alert\ndata: {json.dumps(e)}\n\n"
    return Response(stream(),mimetype="text/event-stream")

# Existing browser forms still work; API routes above are the production interface.
@app.route("/report",methods=["GET","POST"])
@role_required("farmer","pashu_sakhi","paravet")
def report():
    if request.method=="POST":session["report"]=request.form.to_dict(flat=False);session.pop("report_case_id",None);return redirect(url_for("location"))
    return render_template("report.html")
@app.route("/location",methods=["GET","POST"])
@role_required("farmer","pashu_sakhi","paravet")
def location():
    if request.method=="POST":session.update(state=request.form.get("state","Maharashtra"),district=request.form.get("district","Pune"),village=request.form.get("village", ""),lat=(request.form.get("lat") or "").strip(),lng=(request.form.get("lng") or "").strip());return redirect(url_for("analysis"))
    return render_template("location.html",village=session.get("village",""),lat=session.get("lat",""),lng=session.get("lng",""),selected_state=session.get("state","Maharashtra"))
@app.route("/analysis")
@role_required("farmer","pashu_sakhi","paravet")
def analysis():
    raw=session.get("report",{})
    def first(name,default=""):
        value=raw.get(name,default); return value[0] if isinstance(value,list) and value else value
    try: affected=max(0,int(first("affected",0) or 0))
    except (TypeError,ValueError): affected=0
    symptoms=raw.get("symptoms",[]); symptoms=symptoms if isinstance(symptoms,list) else [symptoms]
    report_data={"animal_type":first("animal_type","cattle"),"age":first("age"),"affected":affected,"symptoms":symptoms,"duration":first("duration")}
    district=session.get("district","Pune")
    payload={"village_code":"271000100001","village":session.get("village", ""),"district_code":"MH-"+district.upper().replace(" ","-"),"species":report_data["animal_type"],"symptoms":symptoms,"mortality_count":affected,"duration":report_data["duration"],"age":report_data["age"],"updated_at":int(datetime.now().timestamp()*1000)}
    if session.get("lat") and session.get("lng"): payload["lat"],payload["lng"]=session["lat"],session["lng"]  # real device GPS fix -> resolves to precision "gps" on the live map
    # Reuse the case id created by the first render so refreshing /analysis updates
    # the existing case instead of inserting a duplicate on every page load.
    if session.get("report_case_id"): payload["id"]=session["report_case_id"]
    case,error=save_case(payload,"web",user())
    if error:return jsonify(error=error),400
    session["report_case_id"]=case["id"]
    t=case["triage"]; disease_score,alerts=surveillance_signals(district); outbreaks,attacks,deaths=anthrax_history(district)
    symptom_risk=min(6,len(symptoms)+2*sum(norm(x) in {"difficulty breathing","weakness","loss of appetite"} for x in symptoms)); affected_risk=3 if affected>=10 else 2 if affected>=5 else 1 if affected>=2 else 0
    historical_risk=(3 if deaths>=10 else 2 if deaths else 0)+(1 if attacks else 0)+(1 if outbreaks else 0)
    predicted=0.0
    if model is not None:
        try: predicted=round(max(0,float(model.predict(pd.DataFrame([[2023,1,affected,affected]],columns=["Year","Outbreaks","Susceptible","Attacks"]))[0])),2)
        except Exception: predicted=0.0
    ml_risk=5 if predicted>=10 else 4 if predicted>=5 else 3 if predicted>=2 else 2 if predicted>0 else 0
    score=t["score"]+disease_score+historical_risk+ml_risk+symptom_risk+affected_risk; level="HIGH" if score>=60 or t["level"]=="HIGH" else "MEDIUM" if score>=25 else "LOW"
    return render_template("analysis.html",report=report_data,location={"state":session.get("state"),"district":district,"village":session.get("village")},risk_score=score,risk_level=level,ml_risk=ml_risk,predicted_deaths=predicted,historical_risk=historical_risk,historical_outbreaks=outbreaks,historical_attacks=attacks,historical_deaths=deaths,symptom_risk=symptom_risk,affected_risk=affected_risk,disease_risk_score=disease_score,disease_alerts=alerts,current_case_id=case["id"])
@app.get("/service-worker.js")
def service_worker():
    # Served from root so the SW controls the whole origin, not just /static/.
    resp = send_from_directory(app.static_folder, "service-worker.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp
init_db()
if __name__=="__main__":app.run(debug=True)
