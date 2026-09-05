# Pashu Arogya — Animal-Health Surveillance & Decision-Support (Maharashtra)

**Smart India Hackathon · Problem Statement SH26128**

Full-stack platform for the Maharashtra Department of Animal Husbandry: multi-channel
symptom/mortality capture (web, offline mobile sync, IVR, WhatsApp), dual-matrix triage
(deterministic rules × MAHAVEDH climate sync), geospatial risk mapping, herd/animal EHR
with Bharat Pashudhan ear-tag validation, Code-128 sample barcoding → lab referral →
case escalation, real-time SSE outbreak alerts, tri-lingual advisories (English / मराठी /
हिंदी), hierarchical role scoping, and a Random-Forest mortality-risk regressor.

```
┌──────────────┐   /api/v1 (JSON, SSE)   ┌──────────────────────────┐   SQLite (dev)
│ client/      │ ───────────────────────▶ │ server/  Flask 3         │ ─▶ data/surveillance.db
│ React 19 +   │ ◀─────────────────────── │ auth · triage · geo ·    │   PostGIS (prod, opt.)
│ Vite · TW v4 │      Vite dev proxy      │ barcode · i18n · ML      │ ─▶ ml/*.pkl
└──────────────┘                          └──────────────────────────┘
```

---

## Quick start

> Setting up on a fresh PC/laptop (Windows, macOS or Linux)? Follow the step-by-step guide in
> **[SETUP.md](SETUP.md)** — it covers prerequisites, virtual-env activation per OS and troubleshooting.

```bash
# 1. Backend (Python 3.11+)
pip install -r requirements.txt
python3 -m server.app            # → http://localhost:5000  (seeds data/surveillance.db on first run)

# 2. Frontend (Node 20+), in a second terminal
cd client && npm install && npm run dev   # → http://localhost:5173 (proxies /api → :5000)
```

Production-style single process: `cd client && npm run build`, then `python3 -m server.app`
serves the SPA from `client/dist/` on port 5000 (SPA fallback for deep links).

Delete `data/` to reseed. Set `DATABASE_URL=postgres://…` to route nearest-clinic queries
through PostGIS (`server/spatial.py`); otherwise the native Haversine engine is used.

### Demo credentials (password `1234`)

| Username   | Role                      | Tier | Scope                                  |
|------------|---------------------------|------|----------------------------------------|
| `farmer1`  | Farmer (Ramesh Patil)     | 1    | Own reports & animals (Wagholi 556325) |
| `sakhi1`   | Pashu Sakhi               | 1    | Own village                            |
| `paravet1` | Paravet                   | 2    | Assigned taluka                        |
| `ldo1`     | LDO / Vet (Dr. Deshmukh)  | 2    | Assigned taluka                        |
| `acah1`    | ACAH                      | 3    | District                               |
| `dcah1`    | DCAH                      | 3    | District                               |
| `state1`   | State Directorate, Pune   | 4    | All of Maharashtra                     |
| `lab1`     | DIS Pune lab technician   | lab  | Referrals sent to their lab            |
| `admin`    | System admin              | 5    | Everything + user management           |

Every list/KPI query is filtered server-side by `server/access_control.scope_clause()`
(village → taluka → district → state) so the same UI narrows automatically per login.

---

## What's inside

### Case intake channels
| Channel | Entry point | Notes |
|---|---|---|
| Web form | `/report` (UI) → `POST /api/v1/reports/web` | live triage preview as symptoms change |
| Offline mobile | `POST /api/v1/reports/mobile/sync` | queue in `localStorage`, last-write-wins on `updated_at` ms; results `applied / stale_ignored / rejected` |
| IVR | `POST /api/v1/webhooks/ivr` | returns Marathi/Hindi TTS script + spoken case-id |
| WhatsApp | `POST /api/v1/webhooks/whatsapp` | `REPORT <species> <village_lgd> <symptoms,...> deaths=N affected=N` |

### Triage (`server/triage_engine.py`)
Deterministic symptom×species rule matrix produces suspected disease + `LOW/MEDIUM/HIGH`;
`server/services.py` then applies the climate matrix from the latest MAHAVEDH-style
observation for the taluka (humidity/temperature/rainfall → vector-favourable uplift).
Advisories are rendered in `en/mr/hi` by `server/i18n.py`.

### Case lifecycle
`REPORTED → FIELD_INSPECTED_BY_LDO → SAMPLE_COLLECTED → LAB_TRANSIT → LAB_RECEIVED →
PATHOGEN_CONFIRMED | PATHOGEN_REJECTED → CASE_RESOLVED`, enforced per role via
`/cases/<id>/transition`. Sample collection issues a referral with a Code-128 barcode
(`MH-521-YYMMDD-XXXXXX`, HMAC-signed; `GET /lab-referrals/<id>/barcode.svg`, `/verify`).

### Geospatial & environment
`/geo/risk-map` scores talukas from 14-day case load, deaths and climate; `/geo/nearest-clinic`
(Haversine or PostGIS); `/weather/etl` ingests observations; `/analytics/history` exposes
seasonal and historical anthrax series; `/ml/predict` calls the Random-Forest regressor.

### Real-time
`GET /api/v1/events?token=` (SSE) pushes `case.created`, `outbreak.detected`, `alert.created`;
the UI shows toasts and invalidates queries. `/outbreaks/detect` runs the cluster detector.

### Frontend (`client/`)
React 19 · Vite 7 · Tailwind v4 · TanStack Query · React-Leaflet · Recharts · lucide.
Pages: Dashboard, Report, Cases/Detail, Animals/Detail, Vaccination, Lab, Risk Map,
Outbreaks, Alerts, Weather, Analytics, Channels, Vet Centers, Users, Settings.
Sitewide language switch (`pa.lang`) drives both UI strings and API `X-Lang` responses.

---

## Repository layout

```
server/        Flask API (app.py entrypoint) + engines: triage, geo, spatial, barcode,
               access_control, i18n, seed, db
client/        React SPA (src/pages, src/components, src/lib/{api,auth,i18n,toast})
client/scripts/smoke.mjs   mounts every route in happy-dom against the live API (node scripts/smoke.mjs ldo1)
ml/            train_model.py / predict.py, livestock_risk_model.pkl, historical CSVs
legacy/        original Jinja prototype, kept for reference (see legacy/README.md)
schema.sql     reference DDL
```

## Testing

```bash
python3 -m server.app &                    # API on :5000
cd client && node scripts/smoke.mjs farmer1   # renders all 17 routes, reports runtime errors
```
