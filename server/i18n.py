"""Lightweight i18n layer for the surveillance UI (Phase C stub).

Provides English / Hindi / Marathi strings for key UI labels and a translate()
helper with graceful fallback (requested lang -> English -> raw key). The Flask
app exposes translate() to templates as `t(...)` and stores the active language
in the session (and on the user's profile when logged in).

Production path: swap this dict for Flask-Babel + .po/.mo catalogs; the template
contract ({{ t('key') }}) stays identical.
"""

DEFAULT_LANG = "en"

# code -> native label (used to render the language toggle)
LANGUAGES = {"en": "English", "hi": "हिंदी", "mr": "मराठी"}

TRANSLATIONS = {
    "en": {
        "app_title": "Animal Health Surveillance",
        "app_subtitle": "Maharashtra State Veterinary Surveillance & Decision Support System",
        "dept_badge": "Department of Animal Husbandry · Maharashtra",
        "language": "Language",
        "username": "Username",
        "password": "Password",
        "username_ph": "Enter username",
        "password_ph": "Enter password",
        "sign_in": "Sign In",
        "demo_access": "DEMO ACCESS",
        "footer": "Prototype · Maharashtra Animal Health Surveillance & Decision Support System",
        "dashboard": "Dashboard",
        "logout": "Logout",
        "open_cases": "Open Cases",
        "high_risk": "High Risk",
        "submit_report": "Submit Report",
    },
    "hi": {
        "app_title": "पशु स्वास्थ्य निगरानी",
        "app_subtitle": "महाराष्ट्र राज्य पशु चिकित्सा निगरानी एवं निर्णय समर्थन प्रणाली",
        "dept_badge": "पशुपालन विभाग · महाराष्ट्र",
        "language": "भाषा",
        "username": "उपयोगकर्ता नाम",
        "password": "पासवर्ड",
        "username_ph": "उपयोगकर्ता नाम दर्ज करें",
        "password_ph": "पासवर्ड दर्ज करें",
        "sign_in": "साइन इन करें",
        "demo_access": "डेमो एक्सेस",
        "footer": "प्रोटोटाइप · महाराष्ट्र पशु स्वास्थ्य निगरानी एवं निर्णय समर्थन प्रणाली",
        "dashboard": "डैशबोर्ड",
        "logout": "लॉग आउट",
        "open_cases": "लंबित मामले",
        "high_risk": "उच्च जोखिम",
        "submit_report": "रिपोर्ट भेजें",
    },
    "mr": {
        "app_title": "पशु आरोग्य सर्वेक्षण",
        "app_subtitle": "महाराष्ट्र राज्य पशुवैद्यकीय सर्वेक्षण व निर्णय समर्थन प्रणाली",
        "dept_badge": "पशुसंवर्धन विभाग · महाराष्ट्र",
        "language": "भाषा",
        "username": "वापरकर्तानाव",
        "password": "पासवर्ड",
        "username_ph": "वापरकर्तानाव प्रविष्ट करा",
        "password_ph": "पासवर्ड प्रविष्ट करा",
        "sign_in": "साइन इन करा",
        "demo_access": "डेमो प्रवेश",
        "footer": "प्रोटोटाइप · महाराष्ट्र पशु आरोग्य सर्वेक्षण व निर्णय समर्थन प्रणाली",
        "dashboard": "डॅशबोर्ड",
        "logout": "लॉग आउट",
        "open_cases": "प्रलंबित प्रकरणे",
        "high_risk": "उच्च धोका",
        "submit_report": "अहवाल पाठवा",
    },
}


def normalise(lang):
    """Coerce an arbitrary value to a supported language code."""
    return lang if lang in TRANSLATIONS else DEFAULT_LANG


def translate(key, lang=DEFAULT_LANG):
    """Look up key in lang, falling back to English then the raw key."""
    lang = normalise(lang)
    return TRANSLATIONS[lang].get(key) or TRANSLATIONS[DEFAULT_LANG].get(key) or key


# ============================================================================
# I18nEngine — end-to-end translation for API payloads, triage output, alerts.
#
# Beyond the login-screen UI labels above, downstream features carry dynamic
# strings: case lifecycle states, medical symptom names, triage assessment
# lines and public advisories. The engine hardcodes full en/mr/hi maps for
# these domains and can walk an arbitrary API response, translating only the
# values under known translatable keys (leaving ids/numbers/coordinates alone).
# ============================================================================

# Canonical case lifecycle states (see app.py STATE_TRANSITIONS). The spec's
# shorthand (FIELD_INSPECTED, LAB_TRANSIT, PATHOGEN_CONFIRMED, RESOLVED) maps
# onto these canonical codes.
STATES = {
    "en": {
        "REPORTED": "Reported",
        "FIELD_INSPECTED_BY_LDO": "Field Inspected",
        "SAMPLE_COLLECTED": "Sample Collected",
        "LAB_TRANSIT": "In Lab Transit",
        "LAB_RECEIVED": "Received at Lab",
        "PATHOGEN_CONFIRMED": "Pathogen Confirmed",
        "PATHOGEN_REJECTED": "Pathogen Rejected",
        "CASE_RESOLVED": "Resolved",
    },
    "mr": {
        "REPORTED": "नोंदवले",
        "FIELD_INSPECTED_BY_LDO": "क्षेत्र तपासणी झाली",
        "SAMPLE_COLLECTED": "नमुना गोळा केला",
        "LAB_TRANSIT": "प्रयोगशाळेकडे पाठवले",
        "LAB_RECEIVED": "प्रयोगशाळेत प्राप्त",
        "PATHOGEN_CONFIRMED": "रोगजंतू निश्चित",
        "PATHOGEN_REJECTED": "रोगजंतू नाकारले",
        "CASE_RESOLVED": "निराकरण झाले",
    },
    "hi": {
        "REPORTED": "दर्ज किया गया",
        "FIELD_INSPECTED_BY_LDO": "क्षेत्र निरीक्षण हुआ",
        "SAMPLE_COLLECTED": "नमूना एकत्र किया",
        "LAB_TRANSIT": "प्रयोगशाला भेजा गया",
        "LAB_RECEIVED": "प्रयोगशाला में प्राप्त",
        "PATHOGEN_CONFIRMED": "रोगाणु की पुष्टि",
        "PATHOGEN_REJECTED": "रोगाणु अस्वीकृत",
        "CASE_RESOLVED": "हल किया गया",
    },
}

# Medical symptom names. Keys are normalised (lower, spaces or underscores) so
# both "High Fever" and "high_fever" resolve.
SYMPTOMS = {
    "en": {
        "high fever": "High Fever",
        "skin nodules": "Skin Nodules",
        "salivation": "Salivation",
        "frothy salivation": "Frothy Salivation",
        "lameness": "Lameness",
        "foot lesions": "Foot Lesions",
        "respiratory distress": "Respiratory Distress",
        "sudden death": "Sudden Death",
        "bloody discharge": "Bloody Discharge",
        "nasal discharge": "Nasal Discharge",
        "fever": "Fever",
        "coughing": "Coughing",
        "diarrhea": "Diarrhea",
        "loss of appetite": "Loss of Appetite",
        "weakness": "Weakness",
        "difficulty breathing": "Difficulty Breathing",
    },
    "mr": {
        "high fever": "तीव्र ताप",
        "skin nodules": "त्वचेवरील गाठी",
        "salivation": "लाळ गळणे",
        "frothy salivation": "फेसाळ लाळ",
        "lameness": "लंगडेपणा",
        "foot lesions": "पायावरील जखमा",
        "respiratory distress": "श्वसनाचा त्रास",
        "sudden death": "अचानक मृत्यू",
        "bloody discharge": "रक्तस्राव",
        "nasal discharge": "नाकातून स्राव",
        "fever": "ताप",
        "coughing": "खोकला",
        "diarrhea": "अतिसार",
        "loss of appetite": "भूक मंदावणे",
        "weakness": "अशक्तपणा",
        "difficulty breathing": "श्वास घेण्यास त्रास",
    },
    "hi": {
        "high fever": "तेज बुखार",
        "skin nodules": "त्वचा की गांठें",
        "salivation": "लार आना",
        "frothy salivation": "झागदार लार",
        "lameness": "लंगड़ापन",
        "foot lesions": "पैर के घाव",
        "respiratory distress": "श्वसन कष्ट",
        "sudden death": "अचानक मृत्यु",
        "bloody discharge": "रक्तस्राव",
        "nasal discharge": "नाक से स्राव",
        "fever": "बुखार",
        "coughing": "खांसी",
        "diarrhea": "दस्त",
        "loss of appetite": "भूख न लगना",
        "weakness": "कमजोरी",
        "difficulty breathing": "सांस लेने में कठिनाई",
    },
}

# Suspected-disease names emitted by the triage engine.
DISEASES = {
    "en": {
        "lumpy skin disease": "Lumpy Skin Disease",
        "foot and mouth disease": "Foot and Mouth Disease",
        "haemorrhagic septicaemia": "Haemorrhagic Septicaemia",
        "anthrax": "Anthrax",
        "no specific pathogen signature": "No specific pathogen signature",
    },
    "mr": {
        "lumpy skin disease": "लम्पी त्वचा रोग",
        "foot and mouth disease": "लाळ्या खुरकूत रोग",
        "haemorrhagic septicaemia": "घटसर्प",
        "anthrax": "फाशी रोग",
        "no specific pathogen signature": "विशिष्ट रोगजंतू आढळला नाही",
    },
    "hi": {
        "lumpy skin disease": "लम्पी त्वचा रोग",
        "foot and mouth disease": "खुरपका-मुंहपका रोग",
        "haemorrhagic septicaemia": "गलघोंटू",
        "anthrax": "एंथ्रेक्स",
        "no specific pathogen signature": "कोई विशिष्ट रोगाणु संकेत नहीं",
    },
}

# Triage risk levels + short advisory templates.
ADVISORY = {
    "en": {
        "HIGH": "High Risk",
        "MEDIUM": "Medium Risk",
        "LOW": "Low Risk",
        "advisory_high": "High-risk animal-health alert. Isolate affected animals and contact your Veterinary Officer immediately.",
        "advisory_medium": "Monitor affected animals closely and report any worsening to your local para-vet.",
        "advisory_low": "No immediate risk detected. Continue routine care and observation.",
    },
    "mr": {
        "HIGH": "उच्च धोका",
        "MEDIUM": "मध्यम धोका",
        "LOW": "कमी धोका",
        "advisory_high": "उच्च-धोका पशु आरोग्य सूचना. बाधित जनावरे वेगळी करा आणि तात्काळ पशुवैद्यकीय अधिकाऱ्यांशी संपर्क साधा.",
        "advisory_medium": "बाधित जनावरांवर बारकाईने लक्ष ठेवा आणि त्रास वाढल्यास स्थानिक पॅरा-व्हेटला कळवा.",
        "advisory_low": "तात्काळ धोका आढळला नाही. नियमित काळजी व निरीक्षण सुरू ठेवा.",
    },
    "hi": {
        "HIGH": "उच्च जोखिम",
        "MEDIUM": "मध्यम जोखिम",
        "LOW": "कम जोखिम",
        "advisory_high": "उच्च-जोखिम पशु स्वास्थ्य चेतावनी. प्रभावित पशुओं को अलग करें और तुरंत पशु चिकित्सा अधिकारी से संपर्क करें.",
        "advisory_medium": "प्रभावित पशुओं पर बारीकी से नजर रखें और स्थिति बिगड़ने पर स्थानीय पैरा-वेट को सूचित करें.",
        "advisory_low": "कोई तत्काल जोखिम नहीं मिला. नियमित देखभाल और निगरानी जारी रखें.",
    },
}


def _norm_term(text):
    return str(text or "").strip().lower().replace("_", " ")


class I18nEngine:
    """End-to-end translator for dynamic API payloads across en / mr / hi.

    Resolves the caller's language from the request, translates individual
    domain terms (states, symptoms, diseases, risk levels, advisories, UI
    labels), and can recursively transform a whole response payload — touching
    only values under known translatable keys, never ids/numbers/coordinates.
    """

    SUPPORTED = tuple(TRANSLATIONS.keys())

    # Response keys whose *string value* should be translated in-place.
    _SCALAR_KEYS = {"status", "risk_level", "level", "suspected_disease", "disease_name", "message", "advisory"}
    # Response keys whose value is a *list of terms* to translate element-wise.
    _LIST_KEYS = {"symptoms", "signals"}

    def resolve_lang(self, req):
        """Header-first language resolution: Accept-Language, then ?lang=, then default."""
        header = ""
        try:
            header = req.headers.get("Accept-Language", "") or ""
        except Exception:
            header = ""
        # Take the first tag's primary subtag, e.g. "mr-IN,mr;q=0.9" -> "mr".
        primary = header.split(",")[0].split("-")[0].strip().lower() if header else ""
        if primary in self.SUPPORTED:
            return primary
        try:
            q = (req.args.get("lang") or req.values.get("lang") or "").strip().lower()
        except Exception:
            q = ""
        return normalise(q)

    def t(self, key, lang=DEFAULT_LANG):
        """Layered lookup: UI labels -> states -> diseases -> advisory/levels -> English -> raw key."""
        lang = normalise(lang)
        for table in (TRANSLATIONS, STATES, DISEASES, ADVISORY):
            hit = table.get(lang, {}).get(key)
            if hit:
                return hit
        for table in (TRANSLATIONS, STATES, DISEASES, ADVISORY):
            hit = table.get(DEFAULT_LANG, {}).get(key)
            if hit:
                return hit
        return key

    def term(self, value, lang=DEFAULT_LANG):
        """Translate a single free-text domain term (symptom/disease/state/level)."""
        lang = normalise(lang)
        if not isinstance(value, str) or not value.strip():
            return value
        # States are upper-case codes; levels are HIGH/MEDIUM/LOW.
        if value in STATES.get(lang, {}) or value in STATES.get(DEFAULT_LANG, {}):
            return STATES[lang].get(value) or STATES[DEFAULT_LANG].get(value) or value
        if value in ADVISORY.get(DEFAULT_LANG, {}):
            return ADVISORY[lang].get(value) or ADVISORY[DEFAULT_LANG].get(value) or value
        norm = _norm_term(value)
        for table in (SYMPTOMS, DISEASES):
            if norm in table.get(lang, {}) or norm in table.get(DEFAULT_LANG, {}):
                return table[lang].get(norm) or table[DEFAULT_LANG].get(norm) or value
        return value

    def advisory_for(self, level, lang=DEFAULT_LANG):
        """Public automated advisory text for a triage risk level."""
        return self.t({"HIGH": "advisory_high", "MEDIUM": "advisory_medium"}.get(str(level).upper(), "advisory_low"), lang)

    def translate_payload(self, obj, lang=DEFAULT_LANG):
        """Recursively translate values under known translatable keys.

        Leaves ids, numbers, coordinates and unknown keys untouched. Returns a
        new structure (does not mutate the input)."""
        lang = normalise(lang)
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if k in self._SCALAR_KEYS and isinstance(v, str):
                    out[k] = self.term(v, lang)
                elif k in self._LIST_KEYS and isinstance(v, list):
                    out[k] = [self.term(x, lang) if isinstance(x, str) else self.translate_payload(x, lang) for x in v]
                else:
                    out[k] = self.translate_payload(v, lang)
            return out
        if isinstance(obj, list):
            return [self.translate_payload(x, lang) for x in obj]
        return obj


engine = I18nEngine()


# ============================================================================
# Advisory / alert message templates (en / mr / hi) used by the alert service.
# ============================================================================
MESSAGES = {
    "alert_cluster": {
        "en": "Suspected {disease} cluster: {n} reports and {deaths} deaths in this taluka within 7 days. Isolate sick animals, stop animal movement and await LDO inspection.",
        "mr": "संशयित {disease} समूह: या तालुक्यात ७ दिवसांत {n} अहवाल व {deaths} मृत्यू. आजारी जनावरे वेगळी करा, जनावरांची ने-आण थांबवा आणि पशुधन विकास अधिकाऱ्यांच्या तपासणीची वाट पहा.",
        "hi": "संदिग्ध {disease} समूह: इस तालुका में 7 दिनों में {n} रिपोर्ट और {deaths} मौतें. बीमार पशुओं को अलग करें, पशुओं की आवाजाही रोकें और एलडीओ निरीक्षण की प्रतीक्षा करें.",
    },
    "alert_high_triage": {
        "en": "High-risk report ({disease}) in {village}. Isolate affected animals and contact your Veterinary Officer immediately.",
        "mr": "{village} येथे उच्च-धोका अहवाल ({disease}). बाधित जनावरे वेगळी करा आणि तात्काळ पशुवैद्यकीय अधिकाऱ्यांशी संपर्क साधा.",
        "hi": "{village} में उच्च-जोखिम रिपोर्ट ({disease}). प्रभावित पशुओं को अलग करें और तुरंत पशु चिकित्सा अधिकारी से संपर्क करें.",
    },
    "alert_outbreak_confirmed": {
        "en": "Confirmed {disease} outbreak within {radius} km. Ring vaccination and movement restrictions are in force. Follow LDO guidance.",
        "mr": "{radius} किमी परिसरात {disease} उद्रेकाची पुष्टी. रिंग लसीकरण व जनावरांच्या ने-आणीवर निर्बंध लागू. पशुधन विकास अधिकाऱ्यांच्या सूचनांचे पालन करा.",
        "hi": "{radius} किमी के भीतर {disease} प्रकोप की पुष्टि. रिंग टीकाकरण और आवाजाही प्रतिबंध लागू. एलडीओ के निर्देशों का पालन करें.",
    },
    "alert_lab_confirmed": {
        "en": "Laboratory confirmed {disease} for sample {barcode}. Case escalated for containment.",
        "mr": "नमुना {barcode} साठी प्रयोगशाळेने {disease} निश्चित केले. प्रतिबंधासाठी प्रकरण वरिष्ठ स्तरावर पाठवले.",
        "hi": "नमूना {barcode} के लिए प्रयोगशाला ने {disease} की पुष्टि की. नियंत्रण हेतु मामला आगे बढ़ाया गया.",
    },
    "alert_vaccination_due": {
        "en": "{count} animals in {village} are due for {vaccine} vaccination this week. Contact your Pashu Sakhi to schedule.",
        "mr": "{village} येथील {count} जनावरांचे {vaccine} लसीकरण या आठवड्यात देय आहे. वेळ ठरवण्यासाठी पशु सखीशी संपर्क साधा.",
        "hi": "{village} में {count} पशुओं का {vaccine} टीकाकरण इस सप्ताह देय है. समय तय करने हेतु पशु सखी से संपर्क करें.",
    },
    "alert_weather": {
        "en": "MAHAVEDH advisory: humidity {humidity}% and {temp}°C expected in {district}. Elevated vector activity — check animals for skin nodules and fever daily.",
        "mr": "महावेध सूचना: {district} मध्ये आर्द्रता {humidity}% व {temp}°C अपेक्षित. कीटकवाहक क्रियाशीलता वाढली — जनावरांना त्वचेवर गाठी व ताप आहे का ते रोज तपासा.",
        "hi": "महावेध परामर्श: {district} में आर्द्रता {humidity}% और {temp}°C अपेक्षित. वाहक गतिविधि बढ़ी — पशुओं में त्वचा की गांठें और बुखार रोज़ जांचें.",
    },
}


def render(key, lang="en", **fmt):
    lang = normalise(lang)
    tpl = MESSAGES.get(key, {})
    text = tpl.get(lang) or tpl.get("en") or key
    # translate disease names inside the template
    if "disease" in fmt and isinstance(fmt["disease"], str):
        fmt = dict(fmt); fmt["disease"] = engine.term(fmt["disease"], lang)
    try:
        return text.format(**fmt)
    except (KeyError, IndexError):
        return text
