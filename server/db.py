"""SQLite persistence layer (WAL mode) + schema.

`schema.sql` at the repo root remains the PostgreSQL + PostGIS production
reference; this module is the always-available embedded store used by the MVP
and by field devices running in offline mode.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "surveillance.db"))

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS districts(
  code TEXT PRIMARY KEY, name TEXT NOT NULL, name_mr TEXT, name_hi TEXT,
  lat REAL NOT NULL, lng REAL NOT NULL, region TEXT
);
CREATE TABLE IF NOT EXISTS talukas(
  code TEXT PRIMARY KEY, district_code TEXT NOT NULL REFERENCES districts(code),
  name TEXT NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS villages(
  code TEXT PRIMARY KEY, taluka_code TEXT NOT NULL REFERENCES talukas(code),
  district_code TEXT NOT NULL REFERENCES districts(code),
  name TEXT NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL, livestock_population INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL, role TEXT NOT NULL, phone TEXT, language TEXT DEFAULT 'en',
  district_code TEXT, taluka_code TEXT, village_code TEXT, lab_id TEXT,
  active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS labs(
  id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, tier TEXT NOT NULL,
  district_code TEXT, lat REAL, lng REAL, phone TEXT, capabilities TEXT
);

CREATE TABLE IF NOT EXISTS vet_centers(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'dispensary',
  district_code TEXT, taluka_code TEXT, lat REAL NOT NULL, lng REAL NOT NULL,
  officer_name TEXT, officer_phone TEXT, created_at TEXT, updated_at TEXT, deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS animals(
  id TEXT PRIMARY KEY, ear_tag TEXT UNIQUE NOT NULL CHECK(length(ear_tag)=12),
  species TEXT NOT NULL, breed TEXT, sex TEXT, birth_year INTEGER, color TEXT,
  owner_id TEXT REFERENCES users(id), owner_name TEXT, owner_phone TEXT,
  village_code TEXT, taluka_code TEXT, district_code TEXT,
  status TEXT NOT NULL DEFAULT 'active', notes TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_animals_village ON animals(village_code);

CREATE TABLE IF NOT EXISTS vaccinations(
  id TEXT PRIMARY KEY, animal_id TEXT NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
  vaccine TEXT NOT NULL, disease TEXT, administered_on TEXT NOT NULL, next_due_on TEXT,
  batch_no TEXT, administered_by TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS treatments(
  id TEXT PRIMARY KEY, animal_id TEXT NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
  case_id TEXT, diagnosis TEXT, treatment TEXT NOT NULL, drug TEXT, dosage TEXT,
  treated_on TEXT NOT NULL, clinician_id TEXT, clinician_name TEXT, outcome TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases(
  id TEXT PRIMARY KEY, reporter_id TEXT NOT NULL REFERENCES users(id), reporter_name TEXT,
  channel TEXT NOT NULL, species TEXT NOT NULL, herd_size INTEGER DEFAULT 0,
  affected_count INTEGER DEFAULT 0, mortality_count INTEGER DEFAULT 0,
  symptoms TEXT NOT NULL, onset_date TEXT, duration_days INTEGER, notes TEXT,
  ear_tags TEXT, village_code TEXT, taluka_code TEXT, district_code TEXT, lat REAL, lng REAL,
  status TEXT NOT NULL DEFAULT 'REPORTED', triage TEXT NOT NULL, suspected_disease TEXT,
  risk_level TEXT NOT NULL, risk_score INTEGER NOT NULL, predicted_deaths REAL,
  assigned_to TEXT REFERENCES users(id), device_id TEXT,
  created_at TEXT NOT NULL, updated_at INTEGER NOT NULL, deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_cases_district ON cases(district_code);
CREATE INDEX IF NOT EXISTS idx_cases_taluka ON cases(taluka_code);
CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_at);

CREATE TABLE IF NOT EXISTS case_events(
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  actor_id TEXT, actor_name TEXT, kind TEXT NOT NULL, from_status TEXT, to_status TEXT,
  note TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_referrals(
  id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  barcode TEXT UNIQUE NOT NULL, signature TEXT NOT NULL, sample_type TEXT NOT NULL,
  transport_media TEXT, cold_chain_ok INTEGER NOT NULL DEFAULT 1, lab_id TEXT REFERENCES labs(id),
  collected_by TEXT, collected_by_name TEXT, collected_at TEXT NOT NULL, priority TEXT DEFAULT 'routine',
  status TEXT NOT NULL DEFAULT 'COLLECTED', test_requested TEXT, result TEXT, pathogen TEXT,
  result_notes TEXT, result_at TEXT, result_by TEXT, chain TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weather(
  id TEXT PRIMARY KEY, district_code TEXT, taluka_code TEXT, village_code TEXT,
  humidity REAL, temperature_c REAL, rainfall_mm REAL, wind_kmh REAL,
  observed_at TEXT NOT NULL, source TEXT DEFAULT 'MAHAVEDH'
);
CREATE INDEX IF NOT EXISTS idx_weather_obs ON weather(observed_at);

CREATE TABLE IF NOT EXISTS alerts(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, severity TEXT NOT NULL, title TEXT NOT NULL,
  message_en TEXT NOT NULL, message_mr TEXT, message_hi TEXT,
  district_code TEXT, taluka_code TEXT, village_code TEXT, case_id TEXT, disease TEXT,
  radius_km REAL, channels TEXT, created_by TEXT, created_by_name TEXT,
  created_at TEXT NOT NULL, expires_at TEXT, deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS alert_acks(
  alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL, acked_at TEXT NOT NULL, PRIMARY KEY(alert_id,user_id)
);

CREATE TABLE IF NOT EXISTS outbreak_signals(
  id TEXT PRIMARY KEY, disease TEXT NOT NULL, district_code TEXT, taluka_code TEXT,
  case_ids TEXT NOT NULL, case_count INTEGER NOT NULL, mortality INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'SUSPECTED', first_reported TEXT, detected_at TEXT NOT NULL,
  confirmed_by TEXT, confirmed_at TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS channel_log(
  id TEXT PRIMARY KEY, channel TEXT NOT NULL, direction TEXT NOT NULL, sender TEXT,
  body TEXT, case_id TEXT, user_id TEXT, meta TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_log(
  id TEXT PRIMARY KEY, device_id TEXT, user_id TEXT, received INTEGER NOT NULL,
  applied INTEGER NOT NULL, stale INTEGER NOT NULL, rejected INTEGER NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log(
  id TEXT PRIMARY KEY, actor_id TEXT, actor_name TEXT, action TEXT NOT NULL,
  entity TEXT NOT NULL, entity_id TEXT, detail TEXT, created_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema():
    with db() as c:
        c.executescript(SCHEMA)


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def one(cur) -> dict | None:
    r = cur.fetchone()
    return dict(r) if r else None
