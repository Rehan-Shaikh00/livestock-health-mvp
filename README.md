# Livestock Health MVP — Scalable Animal-Health Surveillance & Decision-Support

**Smart India Hackathon · Problem Statement SH26128**

A prototype platform for rapid field reporting of livestock symptoms and mortality,
AI-assisted outbreak triage, geospatial + environmental risk integration, a health-records
ledger, multi-lingual alerting with sample-collection → lab-referral escalation, an
offline/low-connectivity capture mode, and role-based dashboards for government and
veterinary officials.

---

## Quick start

```bash
# 1. Create and populate a virtual environment
python -m venv .venv
.venv/Scripts/pip.exe install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux

# 2. (Optional) retrain the ML model — a pre-trained model ships in ml/
.venv/Scripts/python.exe ml/train_model.py

# 3. Run the app (creates data/surveillance.db and seeds demo users on first run)
.venv/Scripts/python.exe app.py
```

Then open <http://127.0.0.1:5000>.

### Demo credentials (password `1234` for all)

| Username    | Role         | Tier | Lands on dashboard |
|-------------|--------------|------|--------------------|
| `farmer1`   | farmer       | 1    | Farmer / reporting |
| `sakhi1`    | pashu_sakhi  | 1    | Farmer / reporting |
| `paravet1`  | paravet      | 2    | Paravet            |
| `vet1`      | vet          | 2    | Vet                |
| `ldo1`      | ldo          | 2    | Vet                |
| `district1` | district     | 3    | District           |
| `acah1`     | acah         | 3    | District           |
| `admin`     | admin        | 4    | State / admin      |

---

## Architecture

Single-file Flask backend (`app.py`) + Jinja2/Bootstrap templates, backed by SQLite for the
MVP. `schema.sql` is the production-target PostgreSQL + PostGIS reference schema for
horizontal scale and geospatial querying.

| Capability | Where |
|---|---|
| **Data capture** (multi-channel: web, mobile batch sync, IVR, WhatsApp) | `app.py` intake routes, `/api/v1/reports/*`, `/webhooks/*` |
| **AI triage / rule engine** (explainable Low/Medium/High) | `triage_engine.py` |
| **ML mortality-risk prediction** (RandomForest) | `ml/train_model.py`, `ml/predict.py`, `ml/livestock_risk_model.pkl` |
| **Geospatial & environmental** (weather ETL, vector risk) | `geo_engine.py`, `/api/v1/weather/etl`, `/api/v1/risk-map/<village_code>` |
| **Health-records ledger** (animals, vaccinations, treatments) | `/api/v1/livestock*` |
| **Alerts & escalation** (multi-lingual, sample → lab referral) | `notification_service.py`, `/api/v1/cases/<id>/lab-referrals`, SSE `/api/v1/events` |
| **Offline / low-connectivity** | `static/service-worker.js`, `static/js/offline-sync.js`, `static/manifest.webmanifest` |
| **Admin dashboards** (village-level analytics) | `templates/dashboards/*`, `/api/v1/analytics/summary` |

### Case lifecycle (canonical state machine)

```
REPORTED → FIELD_INSPECTED_BY_LDO → SAMPLE_COLLECTED → LAB_TRANSIT
        → LAB_RECEIVED → PATHOGEN_CONFIRMED | PATHOGEN_REJECTED → CASE_RESOLVED
```

Legacy dashboard status labels are mapped onto this machine via `LEGACY_TO_CANONICAL`
in `app.py` so older UI actions still advance the workflow.

---

## Key API endpoints

| Method & path | Purpose |
|---|---|
| `POST /api/v1/auth/token` | Issue an HS256 JWT |
| `POST /api/v1/reports/web` | Web symptom/mortality report |
| `POST /api/v1/reports/mobile/sync` | Offline batch sync from field devices |
| `POST /webhooks/ivr`, `POST /webhooks/whatsapp` | Low-connectivity intake channels |
| `POST /api/v1/cases/<id>/transition` | Advance a case through the state machine |
| `POST /api/v1/cases/<id>/lab-referrals` · `GET …` | Create / list lab referrals |
| `POST /api/v1/lab-referrals/<id>/result` | Record a lab result |
| `POST/GET /api/v1/livestock` · `GET /api/v1/livestock/<id>` | Health-records ledger (id or ear-tag) |
| `POST /api/v1/livestock/<id>/vaccinations` · `…/treatments` | Append to an animal's history |
| `POST /api/v1/weather/etl` | MAHAVEDH-style weather telemetry ingestion |
| `GET /api/v1/risk-map/<village_code>` | Vector-risk layers for a village |
| `GET /api/v1/analytics/summary` | Dashboard aggregates (levels, channels, top villages, trend) |
| `GET /api/v1/events` | Server-Sent Events priority-alert stream |

---

## Machine-learning model

Trained on `ml/data/anthrax_2020_2023.csv` (district-year outbreak records).

- **Features:** `Year`, `Outbreaks`, `Susceptible`, `Attacks`
- **Target:** `Deaths`
- **Model:** `RandomForestRegressor` (scikit-learn), persisted to `ml/livestock_risk_model.pkl`

```bash
# Score a single observation
.venv/Scripts/python.exe ml/predict.py --year 2023 --outbreaks 2 --susceptible 400 --attacks 30
```

---

## Project structure

```
livestock-health-mvp/
├── app.py                     # Flask backend (routes, auth, SQLite, triage/ML wiring)
├── triage_engine.py           # Explainable rule-based triage
├── geo_engine.py              # Weather ETL + vector-risk boundary
├── notification_service.py    # Multi-lingual alert queue (en / mr)
├── schema.sql                 # Production-target PostgreSQL + PostGIS DDL
├── requirements.txt
├── ml/
│   ├── train_model.py         # Trains + saves the RandomForest model
│   ├── predict.py             # Inference helper + CLI
│   ├── livestock_risk_model.pkl
│   └── data/                  # Training CSVs (tracked)
├── templates/
│   ├── login.html, report.html, location.html, analysis.html, 403.html
│   └── dashboards/            # farmer / paravet / vet / district / state
├── static/
│   ├── style.css
│   ├── js/offline-sync.js
│   ├── service-worker.js
│   └── manifest.webmanifest
└── data/                      # Runtime SQLite DB (git-ignored)
```

---

## Tech stack

Python · Flask 3.1 · SQLite (dev) / PostgreSQL + PostGIS (prod target) · scikit-learn ·
pandas · joblib · Jinja2 · Bootstrap 5 · Server-Sent Events · Service Workers.

## Security note (prototype)

Demo users store **plaintext passwords** and JWTs use a static dev secret. These are
acceptable only for the hackathon prototype and **must** be replaced with hashed
credentials (e.g. `werkzeug.security` / Argon2) and a rotated secret before any real
deployment.
