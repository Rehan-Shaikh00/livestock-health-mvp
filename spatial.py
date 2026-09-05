"""Spatial engine for nearest-clinic discovery — dual backend.

Default (demo / offline): SQLite store + great-circle (haversine) distance
computed in Python. Real kilometres on real WGS84 (EPSG:4326) coordinates.

Production: when DATABASE_URL is set (PostgreSQL + PostGIS), the same contract
is served by a native spatial query using ST_SetSRID / ST_MakePoint /
ST_Distance / ST_DWithin against the veterinary_centers.geom column. The literal
query is defined here (POSTGIS_NEAREST_SQL) so it ships and is reviewable
regardless of whether Postgres is present at runtime.
"""
import math
import os

EARTH_RADIUS_KM = 6371.0088
DEFAULT_RADIUS_KM = 50.0  # ST_DWithin guard / bounding-box prefilter radius


def _valid_latlng(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if -90 <= lat <= 90 and -180 <= lng <= 180 and not (lat == 0 and lng == 0):
        return (lat, lng)
    return None


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in kilometres between two WGS84 points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return EARTH_RADIUS_KM * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


# --- Production PostGIS query (executed when DATABASE_URL is configured) ------
# Parameters are bound (%(lat)s / %(lng)s / %(radius)s / %(k)s) — never string
# interpolated — to prevent SQL injection. geom is geometry(Point,4326); the
# ::geography cast makes ST_Distance / ST_DWithin return real metres.
POSTGIS_NEAREST_SQL = """
SELECT
    name,
    officer_phone,
    ST_Y(geom)                                   AS lat,
    ST_X(geom)                                   AS lng,
    ST_Distance(
        geom::geography,
        ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography
    ) / 1000.0                                   AS distance_km
FROM veterinary_centers
WHERE ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography,
    %(radius_m)s
)
ORDER BY geom::geography <-> ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326)::geography
LIMIT %(k)s;
"""


def _shape(name, phone, lat, lng, distance_km):
    return {
        "name": name,
        "distance_km": round(float(distance_km), 2),
        "coordinates": {"lat": round(float(lat), 6), "lng": round(float(lng), 6)},
        "officer_phone": phone,
    }


def _nearest_sqlite(conn, lat, lng, k, radius_km):
    """SQLite backend: bounding-box prefilter, then exact haversine + top-k."""
    # ~111 km per degree lat; scale lng by cos(lat) so the box stays square-ish.
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    rows = conn.execute(
        "SELECT name, officer_phone, lat, lng FROM veterinary_centers "
        "WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?",
        (lat - dlat, lat + dlat, lng - dlng, lng + dlng),
    ).fetchall()
    if not rows:  # fall back to a full scan if the box caught nothing
        rows = conn.execute("SELECT name, officer_phone, lat, lng FROM veterinary_centers").fetchall()
    scored = []
    for r in rows:
        d = haversine_km(lat, lng, r["lat"], r["lng"])
        if d <= radius_km:
            scored.append(_shape(r["name"], r["officer_phone"], r["lat"], r["lng"], d))
    scored.sort(key=lambda x: x["distance_km"])
    return scored[:k]


def _nearest_postgis(lat, lng, k, radius_km):
    """PostGIS backend: native ST_Distance/ST_DWithin. Requires psycopg2 + a
    reachable DATABASE_URL. Raises on connection error so the caller can fall
    back to SQLite."""
    import psycopg2, psycopg2.extras  # imported lazily; optional dependency
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(POSTGIS_NEAREST_SQL, {"lat": lat, "lng": lng, "radius_m": radius_km * 1000.0, "k": k})
            return [_shape(r["name"], r["officer_phone"], r["lat"], r["lng"], r["distance_km"]) for r in cur.fetchall()]
    finally:
        conn.close()


def nearest_clinics(conn, lat, lng, k=3, radius_km=DEFAULT_RADIUS_KM):
    """Return up to `k` nearest veterinary clinics, nearest first.

    conn: an open SQLite connection (used for the default backend).
    Returns [] for invalid coordinates. Uses PostGIS when DATABASE_URL is set,
    otherwise the SQLite + haversine backend; on any PostGIS error it degrades
    gracefully to SQLite so the demo never hard-fails.
    """
    point = _valid_latlng(lat, lng)
    if not point:
        return None  # signals a 400 to the caller
    lat, lng = point
    if os.environ.get("DATABASE_URL"):
        try:
            return _nearest_postgis(lat, lng, k, radius_km)
        except Exception:
            pass  # fall through to the always-available SQLite backend
    return _nearest_sqlite(conn, lat, lng, k, radius_km)
