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
