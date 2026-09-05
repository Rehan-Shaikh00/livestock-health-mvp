import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Loader2, ShieldCheck, Smartphone, Radio, Globe2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth, ROLE_LABEL } from '../lib/auth'
import { useI18n } from '../lib/i18n'

export default function Login() {
  const { login } = useAuth()
  const { t, lang, setLang, languages } = useI18n()
  const nav = useNavigate()
  const [username, setU] = useState('ldo1')
  const [password, setP] = useState('1234')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [accounts, setAccounts] = useState([])

  useEffect(() => { api('/api/v1/auth/demo-accounts').then((d) => setAccounts(d.accounts)).catch(() => {}) }, [])

  const submit = async (e, u = username, p = password) => {
    e?.preventDefault(); setBusy(true); setError(null)
    try { await login(u, p); nav('/') } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden bg-forest-950 p-12 text-forest-100 lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-forest-800/50 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-saffron-500/10 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-forest-800 ring-1 ring-forest-700"><Activity className="h-6 w-6 text-saffron-400" /></div>
          <div>
            <div className="text-lg font-bold text-white">Pashu Arogya</div>
            <div className="text-[11px] uppercase tracking-widest text-forest-300">Department of Animal Husbandry · Government of Maharashtra</div>
          </div>
        </div>
        <div className="relative max-w-lg">
          <h1 className="text-4xl font-bold leading-tight text-white">Animal-health surveillance &amp; decision support for every level of the field hierarchy.</h1>
          <p className="mt-4 text-forest-200">Farmers and Pashu Sakhis report in seconds; dual-matrix triage flags suspected outbreaks; LDOs, labs and district officers coordinate sampling, containment and vaccination — in English, मराठी and हिंदी.</p>
          <div className="mt-8 grid grid-cols-2 gap-3 text-sm">
            {[[Smartphone, 'Offline-first mobile capture with LWW sync'], [Radio, 'IVR & WhatsApp intake for low-connectivity villages'], [ShieldCheck, 'Signed Code-128 sample custody barcodes'], [Globe2, 'LGD-coded geography · PostGIS / Haversine']].map(([I, s]) => (
              <div key={s} className="flex items-start gap-2 rounded-xl bg-forest-900/60 p-3 ring-1 ring-forest-800"><I className="mt-0.5 h-4 w-4 shrink-0 text-saffron-400" /><span className="text-forest-100">{s}</span></div>
            ))}
          </div>
        </div>
        <div className="relative text-xs text-forest-400">SIH 26128 · Prototype · Pune Headquarters</div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-2 lg:hidden"><Activity className="h-6 w-6 text-forest-800" /><span className="font-bold">Pashu Arogya</span></div>
            <select value={lang} onChange={(e) => setLang(e.target.value)} className="input ml-auto !w-auto text-xs">
              {Object.entries(languages).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <h2 className="text-2xl font-bold text-slate-900">{t('Sign in')}</h2>
          <p className="mt-1 text-sm text-slate-500">Use your departmental credentials or pick a demo persona below.</p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div><label className="label">{t('Username')}</label><input className="input" value={username} onChange={(e) => setU(e.target.value)} autoComplete="username" /></div>
            <div><label className="label">{t('Password')}</label><input className="input" type="password" value={password} onChange={(e) => setP(e.target.value)} autoComplete="current-password" /></div>
            {error && <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <button className="btn-primary w-full !py-2.5" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />}{t('Sign in')}</button>
          </form>
          <div className="mt-8">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Demo personas · password <span className="kbd">1234</span></div>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {accounts.map((a) => (
                <button key={a.username} type="button" disabled={busy} onClick={(e) => { setU(a.username); setP('1234'); submit(e, a.username, '1234') }} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-xs hover:border-forest-400 hover:bg-forest-50">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-forest-100 text-[11px] font-bold text-forest-800">{ROLE_LABEL[a.role]?.slice(0, 2).toUpperCase()}</span>
                  <span className="min-w-0"><span className="block truncate font-semibold text-slate-800">{a.label.split(' · ')[0]}</span><span className="block truncate text-slate-500">{a.label.split(' · ')[1] || ROLE_LABEL[a.role]}</span></span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
