"""LGD-aware Maharashtra gazetteer used for seeding and coordinate resolution.

Codes follow the Local Government Directory convention: state 27 (Maharashtra),
3-digit LGD district codes, 4-digit sub-district (taluka) codes and 6-digit
village codes. Coordinates are real WGS84 centroids (EPSG:4326).
"""

STATE_CODE = "27"
STATE_NAME = "Maharashtra"

# code, name, name_mr, name_hi, lat, lng, region (revenue division)
DISTRICTS = [
    ("521", "Pune", "पुणे", "पुणे", 18.5204, 73.8567, "Pune"),
    ("516", "Nashik", "नाशिक", "नासिक", 19.9975, 73.7898, "Nashik"),
    ("505", "Nagpur", "नागपूर", "नागपुर", 21.1458, 79.0882, "Nagpur"),
    ("524", "Beed", "बीड", "बीड", 18.9891, 75.7601, "Aurangabad"),
    ("517", "Jalna", "जालना", "जालना", 19.8410, 75.8864, "Aurangabad"),
    ("530", "Kolhapur", "कोल्हापूर", "कोल्हापुर", 16.7050, 74.2433, "Pune"),
    ("523", "Solapur", "सोलापूर", "सोलापुर", 17.6599, 75.9064, "Pune"),
    ("522", "Ahilyanagar", "अहिल्यानगर", "अहिल्यानगर", 19.0948, 74.7480, "Nashik"),
    ("503", "Amravati", "अमरावती", "अमरावती", 20.9374, 77.7796, "Amravati"),
    ("526", "Latur", "लातूर", "लातूर", 18.4088, 76.5604, "Aurangabad"),
    ("532", "Satara", "सातारा", "सातारा", 17.6805, 74.0183, "Pune"),
    ("510", "Yavatmal", "यवतमाळ", "यवतमाल", 20.3897, 78.1204, "Amravati"),
]

# code, district_code, name, lat, lng
TALUKAS = [
    ("4189", "521", "Haveli", 18.4636, 73.8683),
    ("4190", "521", "Mulshi", 18.5100, 73.5100),
    ("4191", "521", "Baramati", 18.1514, 74.5772),
    ("4192", "521", "Junnar", 19.2083, 73.8753),
    ("4193", "521", "Shirur", 18.8276, 74.3758),
    ("4150", "516", "Nashik", 19.9975, 73.7898),
    ("4151", "516", "Sinnar", 19.8452, 73.9950),
    ("4152", "516", "Malegaon", 20.5537, 74.5288),
    ("4060", "505", "Nagpur Rural", 21.0900, 79.0300),
    ("4061", "505", "Katol", 21.2725, 78.5858),
    ("4062", "505", "Ramtek", 21.3968, 79.3277),
    ("4210", "524", "Beed", 18.9891, 75.7601),
    ("4211", "524", "Ambajogai", 18.7333, 76.3833),
    ("4212", "524", "Georai", 19.2620, 75.7520),
    ("4170", "517", "Jalna", 19.8410, 75.8864),
    ("4171", "517", "Ambad", 19.6117, 75.7926),
    ("4230", "530", "Karvir", 16.7050, 74.2433),
    ("4231", "530", "Shirol", 16.7333, 74.6000),
    ("4200", "523", "Pandharpur", 17.6792, 75.3319),
    ("4201", "523", "Barshi", 18.2333, 75.6833),
    ("4180", "522", "Sangamner", 19.5771, 74.2080),
    ("4181", "522", "Rahuri", 19.3900, 74.6500),
    ("4040", "503", "Achalpur", 21.2572, 77.5086),
    ("4041", "503", "Chandur Railway", 20.8236, 77.9800),
    ("4220", "526", "Latur", 18.4088, 76.5604),
    ("4221", "526", "Udgir", 18.3943, 77.1152),
    ("4240", "532", "Satara", 17.6805, 74.0183),
    ("4241", "532", "Karad", 17.2850, 74.1810),
    ("4080", "510", "Pusad", 19.9130, 77.5790),
    ("4081", "510", "Wani", 20.0550, 78.9530),
]

# code, taluka_code, name, lat, lng, livestock_population
VILLAGES = [
    ("556325", "4189", "Wagholi", 18.5800, 73.9800, 4200),
    ("556326", "4189", "Loni Kalbhor", 18.4790, 73.9860, 3100),
    ("556327", "4189", "Khed Shivapur", 18.3660, 73.8340, 2600),
    ("556340", "4190", "Paud", 18.5250, 73.6100, 1900),
    ("556341", "4190", "Pirangut", 18.5060, 73.6820, 1500),
    ("556360", "4191", "Malegaon Bk", 18.1740, 74.5320, 5200),
    ("556361", "4191", "Supe", 18.3040, 74.3540, 3800),
    ("556380", "4192", "Otur", 19.2760, 73.9750, 2900),
    ("556381", "4192", "Narayangaon", 19.1070, 73.9750, 4600),
    ("556400", "4193", "Shikrapur", 18.6910, 74.1380, 3300),
    ("556401", "4193", "Talegaon Dhamdhere", 18.6690, 74.1550, 2400),
    ("553120", "4150", "Pimpalgaon Baswant", 20.1660, 73.9920, 3500),
    ("553121", "4150", "Ozar", 20.0940, 73.9260, 2800),
    ("553140", "4151", "Wavi", 19.9510, 74.1230, 2100),
    ("553141", "4151", "Dodi Bk", 19.7620, 74.1040, 1700),
    ("553160", "4152", "Dabhadi", 20.4760, 74.5880, 2600),
    ("531200", "4060", "Kamptee Rural", 21.2160, 79.1950, 2200),
    ("531201", "4060", "Hingna", 21.0760, 78.9800, 3000),
    ("531220", "4061", "Kondhali", 21.1700, 78.4000, 1900),
    ("531240", "4062", "Mansar", 21.3990, 79.2600, 1600),
    ("558010", "4210", "Pali", 18.9200, 75.6500, 3900),
    ("558011", "4210", "Neknoor", 18.8600, 75.8100, 3400),
    ("558030", "4211", "Bardapur", 18.6800, 76.4300, 2700),
    ("558050", "4212", "Talwada", 19.3500, 75.7000, 2300),
    ("554510", "4170", "Badnapur", 19.8700, 75.7300, 3100),
    ("554530", "4171", "Wadigodri", 19.5500, 75.8300, 2500),
    ("560210", "4230", "Ispurli", 16.6500, 74.2200, 2800),
    ("560230", "4231", "Kurundwad", 16.6850, 74.5900, 4100),
    ("557120", "4200", "Karkamb", 17.8600, 75.3000, 4700),
    ("557140", "4201", "Pangri", 18.3400, 75.7300, 2200),
    ("555710", "4180", "Ashvi Bk", 19.5900, 74.4200, 3600),
    ("555730", "4181", "Taharabad", 19.3300, 74.6100, 2900),
    ("529010", "4040", "Paratwada", 21.2600, 77.5100, 2400),
    ("529030", "4041", "Talegaon Dashasar", 20.8700, 77.9400, 1800),
    ("559010", "4220", "Murud", 18.3200, 76.4800, 3200),
    ("559030", "4221", "Wadhona", 18.3600, 77.0600, 2000),
    ("561010", "4240", "Limb", 17.6400, 74.0300, 2600),
    ("561030", "4241", "Umbraj", 17.4500, 74.1100, 3000),
    ("532010", "4080", "Shembalpimpri", 19.8800, 77.6200, 2100),
    ("532030", "4081", "Shindola", 20.1000, 78.8700, 1700),
]

# name, type, district, taluka, lat, lng, officer, phone
VET_CENTERS = [
    ("Pune District Veterinary Polyclinic", "polyclinic", "521", "4189", 18.5204, 73.8567, "Dr. S. R. Kulkarni", "+91-20-2612-3456"),
    ("Haveli Taluka Veterinary Dispensary", "dispensary", "521", "4189", 18.4636, 73.8683, "Dr. A. V. Jadhav", "+91-20-2695-1122"),
    ("Wagholi Primary Veterinary Aid Centre", "aid_centre", "521", "4189", 18.5790, 73.9810, "Dr. P. M. Shinde", "+91-98220-11223"),
    ("Mulshi Veterinary Clinic", "dispensary", "521", "4190", 18.5100, 73.5100, "Dr. R. D. Patil", "+91-20-2522-3344"),
    ("Baramati Veterinary Hospital", "hospital", "521", "4191", 18.1514, 74.5772, "Dr. N. S. Deshmukh", "+91-2112-22-5566"),
    ("Junnar Taluka Veterinary Dispensary", "dispensary", "521", "4192", 19.2083, 73.8753, "Dr. M. K. Gaikwad", "+91-2132-22-1100"),
    ("Shirur Veterinary Dispensary", "dispensary", "521", "4193", 18.8276, 74.3758, "Dr. V. B. Pawar", "+91-2138-22-4411"),
    ("Nashik Veterinary Polyclinic", "polyclinic", "516", "4150", 19.9975, 73.7898, "Dr. H. P. Sonawane", "+91-253-257-9900"),
    ("Sinnar Veterinary Dispensary", "dispensary", "516", "4151", 19.8452, 73.9950, "Dr. K. L. More", "+91-2551-22-3300"),
    ("Malegaon Veterinary Hospital", "hospital", "516", "4152", 20.5537, 74.5288, "Dr. F. A. Shaikh", "+91-2554-25-6677"),
    ("Nagpur Regional Veterinary Hospital", "hospital", "505", "4060", 21.1458, 79.0882, "Dr. U. R. Wankhede", "+91-712-256-7788"),
    ("Katol Veterinary Dispensary", "dispensary", "505", "4061", 21.2725, 78.5858, "Dr. S. G. Meshram", "+91-7112-22-3355"),
    ("Beed District Veterinary Centre", "polyclinic", "524", "4210", 18.9891, 75.7601, "Dr. B. T. Munde", "+91-2442-22-3399"),
    ("Ambajogai Veterinary Hospital", "hospital", "524", "4211", 18.7333, 76.3833, "Dr. R. S. Kale", "+91-2446-24-7788"),
    ("Jalna Taluka Veterinary Dispensary", "dispensary", "517", "4170", 19.8410, 75.8864, "Dr. D. N. Rathod", "+91-2482-23-4455"),
    ("Kolhapur Veterinary Polyclinic", "polyclinic", "530", "4230", 16.7050, 74.2433, "Dr. A. A. Ghatge", "+91-231-265-4433"),
    ("Pandharpur Veterinary Hospital", "hospital", "523", "4200", 17.6792, 75.3319, "Dr. S. V. Bhosale", "+91-2186-22-5511"),
    ("Sangamner Veterinary Dispensary", "dispensary", "522", "4180", 19.5771, 74.2080, "Dr. P. R. Thorat", "+91-2425-22-6600"),
    ("Achalpur Veterinary Dispensary", "dispensary", "503", "4040", 21.2572, 77.5086, "Dr. G. M. Ingle", "+91-7223-22-1177"),
    ("Latur District Veterinary Polyclinic", "polyclinic", "526", "4220", 18.4088, 76.5604, "Dr. V. D. Swami", "+91-2382-24-3300"),
    ("Karad Veterinary Hospital", "hospital", "532", "4241", 17.2850, 74.1810, "Dr. J. S. Yadav", "+91-2164-22-2288"),
    ("Pusad Veterinary Dispensary", "dispensary", "510", "4080", 19.9130, 77.5790, "Dr. N. P. Rathod", "+91-7233-24-5566"),
]

# code, name, tier, district, lat, lng, phone, capabilities
LABS = [
    ("DIS-PUNE", "Disease Investigation Section, Pune (State Referral Lab)", "state", "521", 18.5310, 73.8450, "+91-20-2553-7100",
     "PCR,ELISA,Bacteriology,Histopathology,Virology,Serology"),
    ("DDL-NASHIK", "Regional Disease Diagnostic Laboratory, Nashik", "regional", "516", 20.0050, 73.7800, "+91-253-259-0011",
     "PCR,ELISA,Bacteriology,Parasitology"),
    ("DDL-NAGPUR", "Regional Disease Diagnostic Laboratory, Nagpur", "regional", "505", 21.1400, 79.0950, "+91-712-255-2200",
     "PCR,ELISA,Bacteriology,Parasitology,Serology"),
    ("DDL-AURANGABAD", "Regional Disease Diagnostic Laboratory, Chh. Sambhajinagar", "regional", "517", 19.8762, 75.3433, "+91-240-233-1144",
     "ELISA,Bacteriology,Parasitology"),
    ("DDL-KOLHAPUR", "Regional Disease Diagnostic Laboratory, Kolhapur", "regional", "530", 16.7100, 74.2300, "+91-231-269-8800",
     "ELISA,Bacteriology,Parasitology"),
    ("DDL-AKOLA", "Regional Disease Diagnostic Laboratory, Akola", "regional", "503", 20.7002, 77.0082, "+91-724-245-8899",
     "ELISA,Bacteriology"),
]

DISTRICT_BY_CODE = {d[0]: d for d in DISTRICTS}
TALUKA_BY_CODE = {t[0]: t for t in TALUKAS}
VILLAGE_BY_CODE = {v[0]: v for v in VILLAGES}


def district_of_taluka(taluka_code):
    t = TALUKA_BY_CODE.get(taluka_code)
    return t[1] if t else None


def resolve_village(village_code):
    v = VILLAGE_BY_CODE.get(str(village_code or ""))
    if not v:
        return None
    t = TALUKA_BY_CODE[v[1]]
    d = DISTRICT_BY_CODE[t[1]]
    return {
        "village_code": v[0], "village": v[2], "taluka_code": t[0], "taluka": t[2],
        "district_code": d[0], "district": d[1], "lat": v[3], "lng": v[4],
    }
