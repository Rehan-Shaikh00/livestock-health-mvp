"""Realistic demo seed: geography, users for every persona, 300+ animals with
vaccination/treatment ledgers, ~140 cases over 60 days across channels, lab
referrals with signed barcodes, MAHAVEDH weather, alerts and outbreak signals."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from . import barcode
from .auth import hash_password
from .db import db, one, rows
from .gazetteer import DISTRICTS, LABS, TALUKAS, VET_CENTERS, VILLAGES, DISTRICT_BY_CODE, TALUKA_BY_CODE, resolve_village
from .services import add_case_event, create_alert, detect_outbreaks, new_id, run_triage, utcnow

R = random.Random(26128)

FIRST = ["Ramesh", "Sunita", "Vitthal", "Mangal", "Sachin", "Kavita", "Dnyaneshwar", "Archana", "Bhausaheb", "Shobha", "Tukaram",
         "Vaishali", "Ganesh", "Rekha", "Balasaheb", "Lata", "Nitin", "Savita", "Popat", "Alka", "Somnath", "Jyoti", "Dattatray", "Meena"]
LAST = ["Patil", "Jadhav", "Shinde", "More", "Pawar", "Kale", "Gaikwad", "Deshmukh", "Bhosale", "Chavan", "Kadam", "Sawant", "Thorat", "Mane"]
SPECIES = [("cattle", 0.45), ("buffalo", 0.30), ("goat", 0.17), ("sheep", 0.05), ("poultry", 0.03)]
BREEDS = {"cattle": ["Gir", "Khillar", "Deoni", "Holstein-Friesian cross", "Jersey cross", "Dangi"],
          "buffalo": ["Murrah", "Pandharpuri", "Nagpuri", "Mehsana"],
          "goat": ["Osmanabadi", "Sangamneri", "Berari", "Konkan Kanyal"],
          "sheep": ["Deccani", "Madgyal"], "poultry": ["Giriraja", "Vanaraja", "Kadaknath"]}
VACCINES = {"cattle": [("FMD (Raksha Ovac)", "Foot and Mouth Disease", 180), ("HS (Raksha HS)", "Haemorrhagic Septicaemia", 365),
                       ("BQ", "Black Quarter", 365), ("Brucella S19", "Brucellosis", 0), ("LSD (Goat pox vaccine)", "Lumpy Skin Disease", 365)],
            "buffalo": [("FMD (Raksha Ovac)", "Foot and Mouth Disease", 180), ("HS (Raksha HS)", "Haemorrhagic Septicaemia", 365), ("BQ", "Black Quarter", 365)],
            "goat": [("PPR (Sungri/96)", "Peste des petits ruminants", 1095), ("ET", "Enterotoxaemia", 365), ("Goat pox", "Goat pox", 365)],
            "sheep": [("PPR (Sungri/96)", "Peste des petits ruminants", 1095), ("ET", "Enterotoxaemia", 365), ("Sheep pox", "Sheep pox", 365)],
            "poultry": [("Ranikhet (Lasota)", "Newcastle disease", 180), ("IBD", "Gumboro", 365)]}
TREATMENTS = [("Mastitis", "Intramammary antibiotic + NSAID", "Ceftriaxone", "3 g IM x 3 days"),
              ("Tympany/Bloat", "Antifoaming agent, trocarisation if needed", "Simethicone", "100 ml PO"),
              ("Tick infestation", "Acaricide spray + Ivermectin", "Ivermectin", "1 ml/50 kg SC"),
              ("Wound", "Debridement, topical antiseptic", "Povidone iodine", "topical BID"),
              ("Retained placenta", "Manual removal + uterine bolus", "Oxytetracycline bolus", "2 boli intrauterine"),
              ("Anorexia/indigestion", "Rumenotoric powder", "Rumentas", "100 g PO x 3 days"),
              ("Diarrhoea", "Fluids + antibiotics", "Enrofloxacin", "5 mg/kg IM x 3 days"),
              ("Foot rot", "Foot bath + antibiotics", "Penicillin-Streptomycin", "2.5 g IM x 5 days")]

# disease signatures matching triage_engine + weight of occurrence
SIGNATURES = [
    ("Lumpy Skin Disease", ["high fever", "skin nodules", "loss of appetite", "nasal discharge"], 0.15),
    ("Foot and Mouth Disease", ["high fever", "foot lesions", "frothy salivation", "lameness"], 0.12),
    ("Haemorrhagic Septicaemia", ["high fever", "respiratory distress", "swelling of throat", "weakness"], 0.10),
    ("Anthrax", ["sudden death", "bloody discharge", "high fever"], 0.03),
    ("Non-specific", ["fever", "loss of appetite", "diarrhea", "weakness"], 0.25),
    ("Non-specific", ["coughing", "nasal discharge"], 0.15),
    ("Non-specific", ["lameness", "reduced milk yield"], 0.12),
    ("Non-specific", ["skin nodules", "loss of appetite"], 0.08),
]
CHANNELS = [("web", 0.30), ("mobile", 0.38), ("whatsapp", 0.14), ("ivr", 0.18)]
STATUS_FLOW = ["REPORTED", "FIELD_INSPECTED_BY_LDO", "SAMPLE_COLLECTED", "LAB_TRANSIT", "LAB_RECEIVED", "PATHOGEN_CONFIRMED", "CASE_RESOLVED"]


def weighted(choices):
    r = R.random(); acc = 0
    for v, w in choices:
        acc += w
        if r <= acc:
            return v
    return choices[-1][0]


def name(): return f"{R.choice(FIRST)} {R.choice(LAST)}"
def phone(): return f"+91-{R.choice(['98', '97', '94', '90', '80'])}{R.randint(100, 999)}-{R.randint(10000, 99999)}"


def iso(dt: datetime): return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def ear_tag(i): return f"2700{i:08d}"


def seed_if_empty():
    with db() as c:
        if one(c.execute("SELECT 1 FROM users LIMIT 1")):
            return False
    seed()
    return True


def seed():
    now = datetime.now(timezone.utc)
    with db() as c:
        # ---------------- geography ----------------
        c.executemany("INSERT OR IGNORE INTO districts VALUES(?,?,?,?,?,?,?)", DISTRICTS)
        c.executemany("INSERT OR IGNORE INTO talukas VALUES(?,?,?,?,?)", TALUKAS)
        c.executemany("INSERT OR IGNORE INTO villages VALUES(?,?,?,?,?,?,?)",
                      [(v[0], v[1], TALUKA_BY_CODE[v[1]][1], v[2], v[3], v[4], v[5]) for v in VILLAGES])
        for vc in VET_CENTERS:
            c.execute("INSERT INTO vet_centers(id,name,type,district_code,taluka_code,lat,lng,officer_name,officer_phone,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (new_id("VC"), *vc, utcnow(), utcnow()))
        lab_ids = {}
        for code, nm, tier, dc, lat, lng, ph, caps in LABS:
            lid = new_id("LAB"); lab_ids[code] = lid
            c.execute("INSERT INTO labs VALUES(?,?,?,?,?,?,?,?,?)", (lid, code, nm, tier, dc, lat, lng, ph, caps))

        # ---------------- users ----------------
        pw = hash_password("1234")
        ts = utcnow()

        def add_user(uid, username, full_name, role, lang="en", district=None, taluka=None, village=None, lab=None):
            c.execute("INSERT INTO users(id,username,password_hash,full_name,role,phone,language,district_code,taluka_code,village_code,lab_id,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
                      (uid, username, pw, full_name, role, phone(), lang, district, taluka, village, lab, ts, ts))
            return uid

        demo = {
            "farmer1": add_user("U-FARMER1", "farmer1", "Ramesh Patil", "farmer", "mr", "521", "4189", "556325"),
            "sakhi1": add_user("U-SAKHI1", "sakhi1", "Sunita Jadhav", "pashu_sakhi", "mr", "521", "4189", "556325"),
            "paravet1": add_user("U-PARAVET1", "paravet1", "Sachin More", "paravet", "en", "521", "4189", "556326"),
            "ldo1": add_user("U-LDO1", "ldo1", "Dr. Anjali Deshmukh", "ldo", "en", "521", "4189", None),
            "acah1": add_user("U-ACAH1", "acah1", "Dr. Prakash Shinde", "acah", "en", "521", None, None),
            "dcah1": add_user("U-DCAH1", "dcah1", "Dr. Meera Kulkarni", "dcah", "en", "521", None, None),
            "state1": add_user("U-STATE1", "state1", "Dr. Vijay Bhosale (Commissioner AH)", "state", "en"),
            "lab1": add_user("U-LAB1", "lab1", "Dr. Nilesh Kale (DIS Pune)", "lab", "en", "521", None, None, lab_ids["DIS-PUNE"]),
            "admin": add_user("U-ADMIN", "admin", "System Administrator", "admin", "en"),
        }
        # additional per-district officers + village reporters
        reporters_by_village: dict[str, list[str]] = {}
        officers_by_taluka: dict[str, list[str]] = {}
        i = 0
        for d in DISTRICTS:
            if d[0] != "521":
                add_user(f"U-ACAH-{d[0]}", f"acah_{d[1].lower()}", f"Dr. {name()}", "acah", "en", d[0])
        for t in TALUKAS:
            i += 1
            uid = add_user(f"U-LDO-{t[0]}", f"ldo_{t[2].lower().replace(' ', '')}", f"Dr. {name()}", "ldo", "en", t[1], t[0])
            officers_by_taluka.setdefault(t[0], []).append(uid)
            if t[0] == "4189":
                officers_by_taluka[t[0]].append("U-LDO1")
        for v in VILLAGES:
            tal = TALUKA_BY_CODE[v[1]]
            lst = reporters_by_village.setdefault(v[0], [])
            for k in range(2):
                i += 1
                lst.append(add_user(f"U-F{i:04d}", f"farmer_{v[2].lower().replace(' ', '')}_{k+1}", name(), "farmer", "mr", tal[1], v[1], v[0]))
            i += 1
            lst.append(add_user(f"U-S{i:04d}", f"sakhi_{v[2].lower().replace(' ', '')}", name(), "pashu_sakhi", "mr", tal[1], v[1], v[0]))
        reporters_by_village["556325"] = ["U-FARMER1", "U-SAKHI1"] + reporters_by_village["556325"]
        users = {r["id"]: r for r in rows(c.execute("SELECT * FROM users"))}

        # ---------------- animals ----------------
        animals = []
        n = 0
        for v in VILLAGES:
            tal = TALUKA_BY_CODE[v[1]]
            count = 12 if v[0] == "556325" else R.randint(5, 9)
            for _ in range(count):
                n += 1
                sp = weighted(SPECIES)
                owner_id = R.choice(reporters_by_village[v[0]][:2]) if v[0] != "556325" else R.choice(["U-FARMER1", "U-FARMER1", reporters_by_village[v[0]][2]])
                owner = users[owner_id]
                aid = new_id("AN")
                created = now - timedelta(days=R.randint(30, 700))
                c.execute("INSERT INTO animals(id,ear_tag,species,breed,sex,birth_year,color,owner_id,owner_name,owner_phone,village_code,taluka_code,district_code,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (aid, ear_tag(n), sp, R.choice(BREEDS[sp]), R.choice(["female", "female", "female", "male"]), now.year - R.randint(1, 9),
                           R.choice(["brown", "black", "white", "grey", "brown-white", "black-white"]), owner_id, owner["full_name"], owner["phone"],
                           v[0], v[1], tal[1], "active", None, iso(created), iso(created)))
                animals.append({"id": aid, "ear_tag": ear_tag(n), "species": sp, "village_code": v[0], "taluka_code": v[1], "district_code": tal[1], "owner_id": owner_id})
                # vaccinations
                for vac, dis, interval in VACCINES[sp]:
                    if R.random() < 0.72:
                        given = now - timedelta(days=R.randint(10, 400))
                        due = given + timedelta(days=interval) if interval else None
                        c.execute("INSERT INTO vaccinations VALUES(?,?,?,?,?,?,?,?,?)",
                                  (new_id("VX"), aid, vac, dis, given.date().isoformat(), due.date().isoformat() if due else None,
                                   f"B{R.randint(1000, 9999)}/{given.year % 100}", users[R.choice(officers_by_taluka[v[1]])]["full_name"], iso(given)))
                # treatments
                for _ in range(R.choice([0, 0, 0, 1, 1, 2])):
                    dx, tx, drug, dose = R.choice(TREATMENTS)
                    on = now - timedelta(days=R.randint(3, 300))
                    clin = users[R.choice(officers_by_taluka[v[1]])]
                    c.execute("INSERT INTO treatments VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                              (new_id("TX"), aid, None, dx, tx, drug, dose, on.date().isoformat(), clin["id"], clin["full_name"],
                               R.choice(["recovered", "recovered", "improving", "under observation"]), iso(on)))

        # ---------------- MAHAVEDH weather (last 10 days per taluka, 2/day) ----------------
        for t in TALUKAS:
            base_h = R.uniform(58, 86); base_t = R.uniform(24, 33)
            for day in range(10, -1, -1):
                for hr in (6, 15):
                    obs = now - timedelta(days=day, hours=(now.hour - hr) % 24)
                    hum = max(30, min(98, base_h + R.uniform(-8, 8) + (6 if hr == 6 else -6)))
                    tmp = max(18, min(41, base_t + R.uniform(-2, 2) + (-3 if hr == 6 else 3)))
                    c.execute("INSERT INTO weather VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (new_id("WX"), t[1], t[0], None, round(hum, 1), round(tmp, 1), round(max(0, R.gauss(4, 9)), 1), round(R.uniform(3, 22), 1), iso(obs), "MAHAVEDH"))

        # ---------------- cases ----------------
        hot_talukas = {"4189": 3.2, "4190": 1.4, "4210": 2.4, "4150": 1.6, "4060": 1.5, "4230": 1.2}
        case_rows = []
        village_list = list(VILLAGES)
        for _ in range(150):
            # bias toward hot talukas
            weights = [hot_talukas.get(v[1], 0.6) for v in village_list]
            v = R.choices(village_list, weights=weights)[0]
            tal = TALUKA_BY_CODE[v[1]]
            # temporal profile: more recent cases in hot talukas (active clusters)
            if v[1] in ("4189", "4210") and R.random() < 0.55:
                age_days = R.uniform(0, 6)
            else:
                age_days = R.uniform(0, 60) ** 1.0
            created = now - timedelta(days=age_days, minutes=R.randint(0, 1400))
            dis, sym, _ = R.choices(SIGNATURES, weights=[s[2] for s in SIGNATURES])[0]
            if v[1] == "4189" and age_days < 7 and R.random() < 0.5:
                dis, sym = "Lumpy Skin Disease", ["high fever", "skin nodules", "loss of appetite"]
            if v[1] == "4210" and age_days < 7 and R.random() < 0.5:
                dis, sym = "Foot and Mouth Disease", ["high fever", "foot lesions", "frothy salivation"]
            sym = list(sym)
            if R.random() < 0.35 and len(sym) > 1:
                sym.pop(R.randrange(len(sym)))
            sp = "goat" if dis == "Non-specific" and R.random() < 0.3 else weighted([("cattle", 0.55), ("buffalo", 0.35), ("goat", 0.10)])
            herd = R.randint(4, 60)
            affected = max(1, min(herd, int(R.gauss(4, 3))))
            mort = 0 if R.random() < 0.55 else max(0, min(affected, int(R.gauss(1.5, 1.5))))
            if dis == "Anthrax":
                mort = max(1, mort)
            channel = weighted(CHANNELS)
            reporter = users[R.choice(reporters_by_village[v[0]])]
            village_animals = [a for a in animals if a["village_code"] == v[0] and a["species"] == sp]
            tags = [a["ear_tag"] for a in R.sample(village_animals, min(len(village_animals), R.randint(0, 2)))]
            payload = {"species": sp, "symptoms": sym, "herd_size": herd, "affected_count": affected, "mortality_count": mort,
                       "village_code": v[0], "taluka_code": v[1], "district_code": tal[1]}
            triage = run_triage(c, payload)
            # progress through workflow depending on age & risk
            max_step = 0
            if age_days > 1: max_step = 1
            if age_days > 3 and triage["level"] in ("HIGH", "MEDIUM"): max_step = R.choice([1, 2, 3])
            if age_days > 8 and triage["level"] == "HIGH": max_step = R.choice([3, 4, 5, 6])
            if age_days > 15: max_step = R.choice([1, 6, 6, 5, 4]) if triage["level"] != "LOW" else R.choice([0, 1, 6, 6])
            if age_days > 30: max_step = 6 if R.random() < 0.85 else max_step
            status = STATUS_FLOW[max_step]
            if status == "PATHOGEN_CONFIRMED" and R.random() < 0.25:
                status = "PATHOGEN_REJECTED"
            cid = new_id("MH")
            gps = R.random() < 0.7
            lat = round(v[3] + R.uniform(-0.02, 0.02), 6) if gps else None
            lng = round(v[4] + R.uniform(-0.02, 0.02), 6) if gps else None
            assigned = R.choice(officers_by_taluka[v[1]]) if max_step >= 1 else None
            c.execute("INSERT INTO cases(id,reporter_id,reporter_name,channel,species,herd_size,affected_count,mortality_count,symptoms,onset_date,duration_days,notes,ear_tags,village_code,taluka_code,district_code,lat,lng,status,triage,suspected_disease,risk_level,risk_score,predicted_deaths,assigned_to,device_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (cid, reporter["id"], reporter["full_name"], channel, sp, herd, affected, mort, json.dumps(sym),
                       (created - timedelta(days=R.randint(0, 4))).date().isoformat(), R.randint(1, 6),
                       R.choice([None, None, "Animals grazing near common water source.", "Neighbouring farm reported similar signs.", "Purchased animal from weekly market 10 days ago.", "Heavy rain in the area last week."]),
                       json.dumps(tags), v[0], v[1], tal[1], lat, lng, status, json.dumps(triage), triage["suspected_disease"], triage["level"], triage["score"],
                       triage.get("predicted_deaths"), assigned, f"DEV-{R.randint(1000, 9999)}" if channel == "mobile" else None,
                       iso(created), int(created.timestamp() * 1000)))
            add_case_event(c, cid, reporter, "created", None, "REPORTED", f"Reported via {channel}")
            t_cursor = created
            for step in range(1, max_step + 1):
                t_cursor += timedelta(hours=R.randint(4, 40))
                actor = users[assigned] if step <= 3 else users["U-LAB1"]
                to = STATUS_FLOW[step] if not (step == 5 and status == "PATHOGEN_REJECTED") else "PATHOGEN_REJECTED"
                if step == 6:
                    actor = users[assigned]
                add_case_event(c, cid, actor, "transition", STATUS_FLOW[step - 1], to, None)
                c.execute("UPDATE case_events SET created_at=? WHERE case_id=? AND to_status=?", (iso(t_cursor), cid, to))
            case_rows.append({"id": cid, "status": status, "max_step": max_step, "district_code": tal[1], "taluka_code": v[1], "village_code": v[0],
                              "disease": triage["suspected_disease"], "level": triage["level"], "created": created, "assigned": assigned, "sp": sp, "tags": tags})
            # treatments linked to case
            if max_step >= 1 and tags and R.random() < 0.6:
                a = next(a for a in animals if a["ear_tag"] == tags[0])
                clin = users[assigned]
                c.execute("INSERT INTO treatments VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                          (new_id("TX"), a["id"], cid, triage["suspected_disease"], "Symptomatic & supportive therapy, isolation",
                           R.choice(["Meloxicam", "Oxytetracycline LA", "Enrofloxacin", "Multivitamin + fluids"]), "as per body weight",
                           (created + timedelta(days=1)).date().isoformat(), clin["id"], clin["full_name"],
                           R.choice(["improving", "under observation", "recovered", "died"]) if mort else R.choice(["improving", "recovered"]), iso(created + timedelta(days=1))))

        # ---------------- lab referrals ----------------
        lab_for_district = {"521": "DIS-PUNE", "516": "DDL-NASHIK", "505": "DDL-NAGPUR", "524": "DDL-AURANGABAD", "517": "DDL-AURANGABAD",
                            "530": "DDL-KOLHAPUR", "523": "DIS-PUNE", "522": "DDL-NASHIK", "503": "DDL-AKOLA", "526": "DDL-AURANGABAD", "532": "DDL-KOLHAPUR", "510": "DDL-AKOLA"}
        ref_status_by_step = {2: "COLLECTED", 3: "IN_TRANSIT", 4: "RECEIVED", 5: "RESULTED", 6: "RESULTED"}
        sample_types = {"Lumpy Skin Disease": ("Skin biopsy / scab", "Viral transport medium", "PCR (Capripox)"),
                        "Foot and Mouth Disease": ("Vesicular epithelium", "Glycerol-phosphate buffer", "ELISA + RT-PCR"),
                        "Haemorrhagic Septicaemia": ("Heart blood swab", "Amies transport medium", "Bacterial culture"),
                        "Anthrax": ("Ear-vein blood smear", "Dry slide (sealed)", "Polychrome methylene blue smear"),
                        "No specific pathogen signature": ("Whole blood (EDTA)", "Ice pack (4°C)", "Haematology + serology")}
        for cr in case_rows:
            if cr["max_step"] < 2 or (cr["max_step"] == 6 and cr["level"] == "LOW"):
                continue
            code, sig = barcode.generate(cr["district_code"])
            st, media, test = sample_types.get(cr["disease"], sample_types["No specific pathogen signature"])
            collector = users[cr["assigned"]]
            collected = cr["created"] + timedelta(hours=R.randint(20, 60))
            step = cr["max_step"]
            rstatus = ref_status_by_step[step]
            chain = [{"at": iso(collected), "by": collector["full_name"], "event": "Sample collected & barcode issued", "location": "field"}]
            if step >= 3:
                chain.append({"at": iso(collected + timedelta(hours=3)), "by": collector["full_name"], "event": "Handed to cold-chain courier", "location": "taluka dispensary"})
            if step >= 4:
                chain.append({"at": iso(collected + timedelta(hours=R.randint(12, 30))), "by": "Dr. Nilesh Kale (DIS Pune)", "event": "Received at laboratory, barcode signature verified", "location": lab_for_district[cr["district_code"]]})
            result = pathogen = result_at = None
            if step >= 5:
                positive = cr["status"] in ("PATHOGEN_CONFIRMED", "CASE_RESOLVED") and R.random() < 0.8
                result = "POSITIVE" if positive else "NEGATIVE"
                pathogen = cr["disease"] if positive else None
                result_at = iso(collected + timedelta(hours=R.randint(36, 96)))
                chain.append({"at": result_at, "by": "Dr. Nilesh Kale (DIS Pune)", "event": f"Result released: {result}", "location": lab_for_district[cr["district_code"]]})
            c.execute("INSERT INTO lab_referrals(id,case_id,barcode,signature,sample_type,transport_media,cold_chain_ok,lab_id,collected_by,collected_by_name,collected_at,priority,status,test_requested,result,pathogen,result_notes,result_at,result_by,chain,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (new_id("LR"), cr["id"], code, sig, st, media, 1 if R.random() < 0.92 else 0, lab_ids[lab_for_district[cr["district_code"]]],
                       collector["id"], collector["full_name"], iso(collected), "urgent" if cr["level"] == "HIGH" else "routine", rstatus, test,
                       result, pathogen, ("Confirmed by " + test) if result == "POSITIVE" else ("No pathogen detected" if result else None),
                       result_at, "U-LAB1" if result else None, json.dumps(chain), iso(collected), iso(collected)))

        # ---------------- alerts + outbreak detection ----------------
        signals = detect_outbreaks(c, None)
        for s in signals[:1]:
            c.execute("UPDATE outbreak_signals SET status='CONFIRMED', confirmed_by=?, confirmed_at=?, notes=? WHERE id=?",
                      ("U-DCAH1", utcnow(), "Confirmed after DIS Pune PCR positives; ring vaccination ordered within 5 km.", s["id"]))
            create_alert(c, users["U-DCAH1"], "outbreak_confirmed", "critical", f"Confirmed {s['disease']} outbreak — {TALUKA_BY_CODE[s['taluka_code']][2]}",
                         message_key="alert_outbreak_confirmed", fmt={"disease": s["disease"], "radius": 5}, district_code=s["district_code"],
                         taluka_code=s["taluka_code"], disease=s["disease"], radius_km=5)
        create_alert(c, users["U-STATE1"], "weather_advisory", "warning", "MAHAVEDH vector-activity advisory — Pune district",
                     message_key="alert_weather", fmt={"humidity": 84, "temp": 29, "district": "Pune"}, district_code="521")
        create_alert(c, users["U-LDO1"], "vaccination_due", "info", "FMD booster round due — Wagholi",
                     message_key="alert_vaccination_due", fmt={"count": 9, "village": "Wagholi", "vaccine": "FMD"}, district_code="521", taluka_code="4189", village_code="556325")
        # back-date alerts a little so the feed looks lived-in
        for k, r in enumerate(rows(c.execute("SELECT id FROM alerts ORDER BY created_at DESC"))):
            c.execute("UPDATE alerts SET created_at=? WHERE id=?", (iso(now - timedelta(hours=3 + k * 9)), r["id"]))

        # ---------------- channel log ----------------
        for cr in case_rows[:40]:
            ch = one(c.execute("SELECT channel, reporter_name FROM cases WHERE id=?", (cr["id"],)))
            if ch["channel"] in ("whatsapp", "ivr"):
                body = ("DTMF: 1 (cattle) → 2 (fever) → 3 animals → 1 death" if ch["channel"] == "ivr"
                        else f"REPORT {cr['sp'].upper()} {cr['village_code']} " + " ".join(s.replace(' ', '_') for s in R.choice(SIGNATURES)[1][:2]))
                c.execute("INSERT INTO channel_log VALUES(?,?,?,?,?,?,?,?,?)",
                          (new_id("CH"), ch["channel"], "inbound", phone(), body, cr["id"], None, json.dumps({"lang": "mr"}), iso(cr["created"])))
        # sync log
        for k in range(6):
            rec = R.randint(3, 14); stale = R.randint(0, 2)
            c.execute("INSERT INTO sync_log VALUES(?,?,?,?,?,?,?,?)",
                      (new_id("SY"), f"DEV-{R.randint(1000, 9999)}", "U-PARAVET1", rec, rec - stale, stale, 0, iso(now - timedelta(days=k * 2, hours=R.randint(1, 9)))))
    return True


if __name__ == "__main__":
    from .db import init_schema
    init_schema()
    print("seeded" if seed_if_empty() else "already seeded")
