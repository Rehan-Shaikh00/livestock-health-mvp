"""Administrative role-based data segregation for analytics/reporting.

The Directorate mandates strict visibility boundaries. This module builds the
parameterized SQL for each administrative tier so the enforcement lives in one
auditable place. All user-derived values are passed as bound parameters (never
string-interpolated) to prevent SQL injection.

Tiers:
  STATE  — aggregate to DISTRICT level only; raw village/farm rows are BLOCKED.
  DISTRICT — locked to their own district_code; aggregate to taluka + village
             *within that district*; cross-district lookups are unauthorized.
  LDO/VET — granular: individual farm records, 12-digit ear tags, and
            village-by-village chronological symptom timelines within their
            taluka / clinic cluster.
"""

# Map application roles onto the three administrative access tiers.
STATE_ROLES = {"state", "admin", "dcah"}
DISTRICT_ROLES = {"district", "acah"}
LDO_ROLES = {"ldo", "vet", "paravet"}


def tier_for(role):
    if role in STATE_ROLES:
        return "state"
    if role in DISTRICT_ROLES:
        return "district"
    if role in LDO_ROLES:
        return "ldo"
    return "field"  # farmer / pashu_sakhi — own reports only


# --- STATE: district-level aggregates only -----------------------------------
def state_aggregate_sql():
    """District-wise metrics. Returns (sql, params). No raw rows are exposed."""
    sql = (
        "SELECT district_code, "
        "COUNT(*) AS total_cases, "
        "SUM(CASE WHEN json_extract(triage,'$.level')='HIGH' THEN 1 ELSE 0 END) AS high_risk, "
        "SUM(CASE WHEN status='PATHOGEN_CONFIRMED' THEN 1 ELSE 0 END) AS confirmed_outbreaks "
        "FROM cases GROUP BY district_code ORDER BY total_cases DESC"
    )
    return sql, ()


# --- DISTRICT: taluka/village aggregates within one district -----------------
def district_aggregate_sql(district_code):
    """Aggregate to taluka + village *within the caller's own district only*."""
    sql = (
        "SELECT taluka_code, village_code, "
        "COUNT(*) AS total_cases, "
        "SUM(CASE WHEN json_extract(triage,'$.level')='HIGH' THEN 1 ELSE 0 END) AS high_risk "
        "FROM cases WHERE district_code=? "
        "GROUP BY taluka_code, village_code ORDER BY total_cases DESC"
    )
    return sql, (district_code,)


# --- LDO/VET: granular rows within taluka / clinic cluster -------------------
def ldo_rows_sql(taluka_code, village_code, district_code):
    """Individual case rows for site-visit planning. Scoped to the officer's
    taluka when known, else their village, else their district (never wider)."""
    if taluka_code:
        return ("SELECT * FROM cases WHERE taluka_code=? ORDER BY created_at DESC", (taluka_code,))
    if village_code:
        return ("SELECT * FROM cases WHERE village_code=? ORDER BY created_at DESC", (village_code,))
    return ("SELECT * FROM cases WHERE district_code=? ORDER BY created_at DESC", (district_code,))


def ldo_ear_tags_sql(village_code):
    """12-digit Bharat Pashudhan ear tags for livestock in the officer's village."""
    return (
        "SELECT ear_tag, species, breed, village_code, updated_at "
        "FROM livestock_records WHERE village_code=? ORDER BY updated_at DESC",
        (village_code,),
    )
