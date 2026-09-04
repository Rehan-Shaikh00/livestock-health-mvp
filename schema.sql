-- ============================================================================
-- SIH SH26128 — Scalable Animal-Health Surveillance & Decision-Support
-- Production-target schema (PostgreSQL + PostGIS).
-- NOTE: The MVP application runs on SQLite (see app.py init_db()); this DDL is
-- the production reference for horizontal scale + geospatial querying.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- Local Government Directory (LGD) resolved administrative hierarchy ----------
CREATE TABLE IF NOT EXISTS lgd_locations (
    village_census_code TEXT PRIMARY KEY,
    village_name        TEXT NOT NULL,
    block_name          TEXT,
    district_code       TEXT NOT NULL,
    district_name       TEXT NOT NULL,
    state_code          TEXT NOT NULL,
    state_name          TEXT NOT NULL,
    centroid            geometry(Point, 4326)
);

-- Actors: farmers, Pashu Sakhis, LDOs, ACAH/DCAH, vets, admins ---------------
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL,
    phone         TEXT,
    village_code  TEXT REFERENCES lgd_locations(village_census_code),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Animal / herd master ledger ------------------------------------------------
CREATE TABLE IF NOT EXISTS livestock_records (
    id            BIGSERIAL PRIMARY KEY,
    ear_tag       TEXT UNIQUE NOT NULL,
    species       TEXT NOT NULL,
    breed         TEXT,
    sex           TEXT,
    date_of_birth DATE,
    owner_id      BIGINT REFERENCES users(id),
    village_code  TEXT REFERENCES lgd_locations(village_census_code),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vaccination history --------------------------------------------------------
CREATE TABLE IF NOT EXISTS vaccination_history (
    id            BIGSERIAL PRIMARY KEY,
    animal_id     BIGINT NOT NULL REFERENCES livestock_records(id) ON DELETE CASCADE,
    vaccine       TEXT NOT NULL,
    dose          TEXT,
    administered_on DATE NOT NULL,
    next_due_on   DATE,
    administered_by BIGINT REFERENCES users(id)
);

-- Clinical treatments --------------------------------------------------------
CREATE TABLE IF NOT EXISTS clinical_treatments (
    id            BIGSERIAL PRIMARY KEY,
    animal_id     BIGINT NOT NULL REFERENCES livestock_records(id) ON DELETE CASCADE,
    diagnosis     TEXT,
    medication    TEXT,
    dosage        TEXT,
    treated_on    DATE NOT NULL,
    treated_by    BIGINT REFERENCES users(id),
    notes         TEXT
);

-- Physiological metrics (temperature, weight, milk yield, etc.) --------------
CREATE TABLE IF NOT EXISTS physiological_metrics (
    id            BIGSERIAL PRIMARY KEY,
    animal_id     BIGINT NOT NULL REFERENCES livestock_records(id) ON DELETE CASCADE,
    metric        TEXT NOT NULL,
    value_numeric NUMERIC,
    unit          TEXT,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Field symptom / mortality reports (multi-channel intake) -------------------
CREATE TABLE IF NOT EXISTS symptom_reports (
    id              BIGSERIAL PRIMARY KEY,
    case_id         TEXT UNIQUE NOT NULL,
    animal_id       BIGINT REFERENCES livestock_records(id),
    village_code    TEXT REFERENCES lgd_locations(village_census_code),
    reporter_id     BIGINT REFERENCES users(id),
    channel         TEXT NOT NULL DEFAULT 'web',
    symptoms        JSONB,
    physical_anomalies JSONB,
    temperature_f   NUMERIC,
    mortality_count INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'REPORTED',
    reported_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    location        geometry(Point, 4326)
);

-- Explainable triage decision log --------------------------------------------
CREATE TABLE IF NOT EXISTS triage_logs (
    id          BIGSERIAL PRIMARY KEY,
    case_id     TEXT NOT NULL REFERENCES symptom_reports(case_id) ON DELETE CASCADE,
    score       INTEGER NOT NULL,
    level       TEXT NOT NULL,
    signals     JSONB,
    engine      TEXT,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sample collection -> lab referral escalation -------------------------------
CREATE TABLE IF NOT EXISTS lab_referrals (
    id            BIGSERIAL PRIMARY KEY,
    referral_id   TEXT UNIQUE NOT NULL,
    case_id       TEXT NOT NULL REFERENCES symptom_reports(case_id) ON DELETE CASCADE,
    lab_name      TEXT,
    sample_type   TEXT,
    status        TEXT NOT NULL DEFAULT 'LAB_TRANSIT',
    result        TEXT,
    pathogen      TEXT,
    referred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    resulted_at   TIMESTAMPTZ
);

-- Environmental telemetry (MAHAVEDH weather ETL) -----------------------------
CREATE TABLE IF NOT EXISTS weather_telemetry (
    id                   BIGSERIAL PRIMARY KEY,
    village_code         TEXT REFERENCES lgd_locations(village_census_code),
    humidity             NUMERIC,
    temperature_anomaly  NUMERIC,
    precipitation_mm     NUMERIC,
    observed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Containment / surveillance zones (outbreak radius geometry) ----------------
CREATE TABLE IF NOT EXISTS containment_zones (
    id           BIGSERIAL PRIMARY KEY,
    case_id      TEXT REFERENCES symptom_reports(case_id),
    zone_type    TEXT NOT NULL,
    radius_km    NUMERIC NOT NULL,
    declared_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    area         geometry(Polygon, 4326)
);

-- Indexes --------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_symptom_reports_village ON symptom_reports(village_code);
CREATE INDEX IF NOT EXISTS idx_symptom_reports_status  ON symptom_reports(status);
CREATE INDEX IF NOT EXISTS idx_symptom_reports_geom    ON symptom_reports USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_triage_logs_case        ON triage_logs(case_id);
CREATE INDEX IF NOT EXISTS idx_lab_referrals_case      ON lab_referrals(case_id);
CREATE INDEX IF NOT EXISTS idx_weather_village         ON weather_telemetry(village_code);
CREATE INDEX IF NOT EXISTS idx_containment_geom        ON containment_zones USING GIST(area);
CREATE INDEX IF NOT EXISTS idx_lgd_centroid            ON lgd_locations USING GIST(centroid);
