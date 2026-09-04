"""Geospatial core: LGD-compatible coordinate resolution + GeoJSON for the live map.

The MVP has no per-village geometry source, so we ship an authoritative WGS84
gazetteer of Maharashtra district centroids (real coordinates) plus the seeded
demo village. resolve_coordinates() prefers a real device GPS fix, then the
village centroid, then the district centroid with a deterministic in-district
offset so distinct villages don't stack on one pixel. Every point is tagged with
its precision so the UI never passes an approximate point off as exact.

Production path: replace GAZETTEER lookups with the LGD directory + Bhuvan/Survey
of India village boundaries (serve real Polygon geometry instead of jittered
points); the cases_to_geojson() contract stays identical.
"""
from datetime import datetime, timezone
import hashlib

# --- Real WGS84 district centroids (lat, lng) for Maharashtra --------------------
DISTRICT_NAME_CENTROIDS = {
    "pune": (18.5204, 73.8567), "mumbai": (19.0760, 72.8777),
    "mumbai city": (18.9388, 72.8354), "mumbai suburban": (19.1136, 72.8697),
    "thane": (19.2183, 72.9781), "nashik": (19.9975, 73.7898),
    "nagpur": (21.1458, 79.0882), "latur": (18.4088, 76.5604),
    "kolhapur": (16.7050, 74.2433), "solapur": (17.6599, 75.9064),
    "aurangabad": (19.8762, 75.3433), "chhatrapati sambhajinagar": (19.8762, 75.3433),
    "amravati": (20.9374, 77.7796), "nanded": (19.1383, 77.3210),
    "satara": (17.6805, 74.0183), "sangli": (16.8524, 74.5815),
    "ahmednagar": (19.0948, 74.7480), "ahilyanagar": (19.0948, 74.7480),
    "jalgaon": (21.0077, 75.5626), "ratnagiri": (16.9902, 73.3120),
    "sindhudurg": (16.1300, 73.6800), "raigad": (18.5158, 73.1822),
    "beed": (18.9891, 75.7601), "osmanabad": (18.1860, 76.0419),
    "dharashiv": (18.1860, 76.0419), "buldhana": (20.5292, 76.1842),
    "akola": (20.7002, 77.0082), "yavatmal": (20.3897, 78.1204),
    "wardha": (20.7453, 78.6022), "chandrapur": (19.9615, 79.2961),
    "gadchiroli": (20.1809, 80.0037), "gondia": (21.4602, 80.1920),
    "bhandara": (21.1667, 79.6500), "washim": (20.1113, 77.1330),
    "hingoli": (19.7173, 77.1490), "parbhani": (19.2704, 76.7708),
    "jalna": (19.8410, 75.8864), "nandurbar": (21.3667, 74.2400),
    "dhule": (20.9042, 74.7749), "palghar": (19.6967, 72.7699),
}
# District codes actually used by the app (users/cases carry MH-XXX codes).
DISTRICT_CODE_CENTROIDS = {"MH-PUNE": DISTRICT_NAME_CENTROIDS["pune"]}

# Seeded demo village (LGD census code) -> a real rural point in Pune district.
VILLAGE_CENTROIDS = {
    "271000100001": {"lat": 18.4636, "lng": 73.8683, "name": "Haveli (demo village)", "district_code": "MH-PUNE"},
}

STATE_CENTROID = (19.7515, 75.7139)  # Maharashtra, fallback of last resort
_MAX_JITTER_DEG = 0.06               # ~6.5 km spread inside a district


def _valid_latlng(lat, lng):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if -90 <= lat <= 90 and -180 <= lng <= 180 and not (lat == 0 and lng == 0):
        return (lat, lng)
    return None


def _norm(text):
    return str(text or "").strip().lower()


def _deterministic_jitter(seed):
    """Stable ±_MAX_JITTER_DEG offset derived from a seed (e.g. village code)."""
    h = hashlib.md5(_norm(seed).encode("utf-8")).hexdigest()
    dlat = (int(h[0:8], 16) / 0xFFFFFFFF - 0.5) * 2 * _MAX_JITTER_DEG
    dlng = (int(h[8:16], 16) / 0xFFFFFFFF - 0.5) * 2 * _MAX_JITTER_DEG
    return dlat, dlng


def resolve_coordinates(village_code=None, district_code=None, district_name=None, lat=None, lng=None):
    """Resolve the best-available real-world point for a case.

    Precedence: live GPS fix -> village centroid -> district centroid (+stable
    in-district offset) -> state centroid. Returns a dict with lat/lng and a
    `precision` of gps | village | district | state so callers can be honest
    about accuracy.
    """
    gps = _valid_latlng(lat, lng)
    if gps:
        return {"lat": gps[0], "lng": gps[1], "precision": "gps"}

    v = VILLAGE_CENTROIDS.get(str(village_code or "").strip())
    if v:
        return {"lat": v["lat"], "lng": v["lng"], "precision": "village"}

    base = DISTRICT_CODE_CENTROIDS.get(district_code) or DISTRICT_NAME_CENTROIDS.get(_norm(district_name))
    if not base and district_code and district_code.startswith("MH-"):
        base = DISTRICT_NAME_CENTROIDS.get(_norm(district_code[3:]))
    if base:
        dlat, dlng = _deterministic_jitter(village_code or district_code or district_name)
        return {"lat": round(base[0] + dlat, 6), "lng": round(base[1] + dlng, 6), "precision": "district"}

    dlat, dlng = _deterministic_jitter(village_code or "unknown")
    return {"lat": round(STATE_CENTROID[0] + dlat, 6), "lng": round(STATE_CENTROID[1] + dlng, 6), "precision": "state"}


_LEVEL_COLORS = {"HIGH": "#c0392b", "MEDIUM": "#e0a800", "LOW": "#176b45"}


def case_to_feature(case_view_dict, coords):
    """Build one GeoJSON Point Feature (GeoJSON order is [lng, lat])."""
    level = str(case_view_dict.get("risk_level", "LOW")).upper()
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [coords["lng"], coords["lat"]]},
        "properties": {
            "case_id": case_view_dict.get("case_id") or case_view_dict.get("id"),
            "village": case_view_dict.get("village"),
            "district": case_view_dict.get("district"),
            "risk_level": level,
            "risk_score": case_view_dict.get("risk_score", 0),
            "status": case_view_dict.get("status"),
            "animal_type": case_view_dict.get("animal_type"),
            "affected": case_view_dict.get("affected", 0),
            "disease_name": case_view_dict.get("disease_name", ""),
            "created_at": case_view_dict.get("created_at"),
            "precision": coords.get("precision"),
            "color": _LEVEL_COLORS.get(level, _LEVEL_COLORS["LOW"]),
        },
    }


def cases_to_geojson(features):
    """Wrap a list of Features in a FeatureCollection with a real CRS (WGS84)."""
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def weather_etl_stub(payload):
    return {"accepted": True, "source": "MAHAVEDH", "records_received": len(payload.get("observations", [])), "processed_at": datetime.now(timezone.utc).isoformat()}


def vector_risk(village_code):
    coords = resolve_coordinates(village_code=village_code)
    return {
        "village_census_code": village_code,
        "vector_risk": "UNKNOWN",
        "centroid": {"lat": coords["lat"], "lng": coords["lng"], "precision": coords["precision"]},
        "layers": ["humidity", "temperature_anomaly", "precipitation", "ticks", "culicoides"],
        "map_provider": "Leaflet + OpenStreetMap (WGS84 / EPSG:4326)",
    }
