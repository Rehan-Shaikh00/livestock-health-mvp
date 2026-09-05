import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getLang, setLang as persistLang } from './api'

// UI strings: English is the source; Marathi / Hindi override. Dynamic domain
// terms (states, diseases, symptoms, advisories) come from the server /meta
// catalogue so the same dictionaries drive SMS/IVR/WhatsApp renderings.
const UI = {
  en: {},
  mr: {
    'Dashboard': 'डॅशबोर्ड', 'Cases': 'प्रकरणे', 'Report a case': 'प्रकरण नोंदवा', 'Animals': 'जनावरे', 'Vaccination': 'लसीकरण',
    'Laboratory': 'प्रयोगशाळा', 'Risk map': 'धोका नकाशा', 'Alerts': 'सूचना', 'Outbreaks': 'उद्रेक', 'Weather': 'हवामान',
    'Channels': 'चॅनेल', 'Vet centres': 'पशुवैद्यकीय केंद्रे', 'Users': 'वापरकर्ते', 'Settings': 'सेटिंग्ज', 'Sign out': 'बाहेर पडा',
    'Sign in': 'साइन इन', 'Username': 'वापरकर्तानाव', 'Password': 'पासवर्ड', 'Search': 'शोधा', 'Open cases': 'खुली प्रकरणे',
    'High risk': 'उच्च धोका', 'Deaths (30d)': 'मृत्यू (३० दिवस)', 'Vaccination coverage': 'लसीकरण व्याप्ती', 'Active outbreaks': 'सक्रिय उद्रेक',
    'Avg response': 'सरासरी प्रतिसाद', 'Save': 'जतन करा', 'Cancel': 'रद्द करा', 'Delete': 'हटवा', 'Edit': 'संपादित करा', 'New': 'नवीन',
    'Species': 'प्रजाती', 'Symptoms': 'लक्षणे', 'Affected': 'बाधित', 'Dead': 'मृत', 'Herd size': 'कळपाचा आकार', 'Village': 'गाव',
    'Status': 'स्थिती', 'Risk': 'धोका', 'Reported': 'नोंदवले', 'Submit report': 'अहवाल पाठवा', 'Offline queue': 'ऑफलाइन रांग',
    'Sync now': 'आता सिंक करा', 'Nearest clinic': 'जवळचे दवाखाने', 'Language': 'भाषा', 'All': 'सर्व', 'Loading…': 'लोड होत आहे…',
    'No results': 'निकाल नाहीत', 'Ear tag': 'कानातील टॅग', 'Owner': 'मालक', 'Breed': 'जात', 'Timeline': 'कालरेषा', 'Treatments': 'उपचार',
    'Add vaccination': 'लसीकरण जोडा', 'Add treatment': 'उपचार जोडा', 'Register animal': 'जनावर नोंदवा', 'Advisory': 'सल्ला',
    'Suspected disease': 'संशयित रोग', 'Channel': 'चॅनेल', 'Assigned to': 'नियुक्त', 'Notes': 'टिपा', 'Live': 'थेट',
  },
  hi: {
    'Dashboard': 'डैशबोर्ड', 'Cases': 'मामले', 'Report a case': 'मामला दर्ज करें', 'Animals': 'पशु', 'Vaccination': 'टीकाकरण',
    'Laboratory': 'प्रयोगशाला', 'Risk map': 'जोखिम मानचित्र', 'Alerts': 'अलर्ट', 'Outbreaks': 'प्रकोप', 'Weather': 'मौसम',
    'Channels': 'चैनल', 'Vet centres': 'पशु चिकित्सा केंद्र', 'Users': 'उपयोगकर्ता', 'Settings': 'सेटिंग्स', 'Sign out': 'साइन आउट',
    'Sign in': 'साइन इन', 'Username': 'उपयोगकर्ता नाम', 'Password': 'पासवर्ड', 'Search': 'खोजें', 'Open cases': 'खुले मामले',
    'High risk': 'उच्च जोखिम', 'Deaths (30d)': 'मौतें (30 दिन)', 'Vaccination coverage': 'टीकाकरण कवरेज', 'Active outbreaks': 'सक्रिय प्रकोप',
    'Avg response': 'औसत प्रतिक्रिया', 'Save': 'सहेजें', 'Cancel': 'रद्द करें', 'Delete': 'हटाएं', 'Edit': 'संपादित करें', 'New': 'नया',
    'Species': 'प्रजाति', 'Symptoms': 'लक्षण', 'Affected': 'प्रभावित', 'Dead': 'मृत', 'Herd size': 'झुंड का आकार', 'Village': 'गांव',
    'Status': 'स्थिति', 'Risk': 'जोखिम', 'Reported': 'रिपोर्ट किया', 'Submit report': 'रिपोर्ट भेजें', 'Offline queue': 'ऑफ़लाइन कतार',
    'Sync now': 'अभी सिंक करें', 'Nearest clinic': 'निकटतम क्लिनिक', 'Language': 'भाषा', 'All': 'सभी', 'Loading…': 'लोड हो रहा है…',
    'No results': 'कोई परिणाम नहीं', 'Ear tag': 'कान का टैग', 'Owner': 'मालिक', 'Breed': 'नस्ल', 'Timeline': 'समयरेखा', 'Treatments': 'उपचार',
    'Add vaccination': 'टीकाकरण जोड़ें', 'Add treatment': 'उपचार जोड़ें', 'Register animal': 'पशु पंजीकृत करें', 'Advisory': 'परामर्श',
    'Suspected disease': 'संदिग्ध रोग', 'Channel': 'चैनल', 'Assigned to': 'नियुक्त', 'Notes': 'नोट्स', 'Live': 'लाइव',
  },
}

const Ctx = createContext(null)

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(getLang())
  const [meta, setMeta] = useState(null)
  useEffect(() => { api('/api/v1/meta').then(setMeta).catch(() => {}) }, [])
  const setLang = useCallback((l) => { persistLang(l); setLangState(l) }, [])

  const value = useMemo(() => {
    const t = (s) => UI[lang]?.[s] || s
    const norm = (v) => String(v || '').trim().toLowerCase().replace(/_/g, ' ')
    const term = (v) => {
      if (!v || !meta) return v
      const L = lang
      if (meta.states?.[L]?.[v] || meta.states?.en?.[v]) return meta.states[L]?.[v] || meta.states.en[v]
      if (meta.advisory?.en?.[v]) return meta.advisory[L]?.[v] || meta.advisory.en[v]
      const n = norm(v)
      for (const tbl of [meta.diseases, meta.symptom_terms]) {
        if (tbl?.[L]?.[n]) return tbl[L][n]
        if (tbl?.en?.[n]) return tbl[L]?.[n] || tbl.en[n]
      }
      return v
    }
    const statusLabel = (s) => meta?.states?.[lang]?.[s] || meta?.states?.en?.[s] || s
    return { lang, setLang, t, term, statusLabel, meta, languages: meta?.languages || { en: 'English', mr: 'मराठी', hi: 'हिंदी' } }
  }, [lang, meta, setLang])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useI18n = () => useContext(Ctx)
