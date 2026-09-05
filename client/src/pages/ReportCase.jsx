import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Crosshair, Loader2, MapPin, Save, WifiOff, Sparkles, Phone, CheckCircle2, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import { api, offline } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, Field, PageHeader, RiskBadge, timeAgo } from '../components/ui'

const SPECIES_ICON = { cattle: '🐄', buffalo: '🐃', goat: '🐐', sheep: '🐑', poultry: '🐔', pig: '🐖' }

export default function ReportCase() {
  const { user } = useAuth()
  const { t, term, meta } = useI18n()
  const toast = useToast()
  const nav = useNavigate()
  const qc = useQueryClient()
  const gaz = useQuery({ queryKey: ['gazetteer'], queryFn: () => api('/api/v1/geo/gazetteer'), staleTime: Infinity })
  const [form, setForm] = useState({ species: 'cattle', symptoms: [], herd_size: '', affected_count: 1, mortality_count: 0, onset_date: '', notes: '', ear_tags: '', village_code: user.village_code || '', lat: '', lng: '' })
  const [gps, setGps] = useState(null)
  const [preview, setPreview] = useState(null)
  const [queue, setQueue] = useState(offline.read())
  const [clinics, setClinics] = useState(null)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  useEffect(() => { const h = () => setQueue(offline.read()); window.addEventListener('pa:queue', h); return () => window.removeEventListener('pa:queue', h) }, [])

  const villages = gaz.data?.villages || []
  const village = villages.find((v) => v.code === form.village_code)
  const districtOf = (v) => gaz.data?.districts.find((d) => d.code === v?.district_code)?.name
  const talukaOf = (v) => gaz.data?.talukas.find((tt) => tt.code === v?.taluka_code)?.name

  // debounced live triage preview
  useEffect(() => {
    if (!navigator.onLine || (!form.symptoms.length && !form.mortality_count)) { setPreview(null); return }
    const id = setTimeout(() => {
      api('/api/v1/triage/preview', { method: 'POST', body: { ...form, ear_tags: undefined } }).then(setPreview).catch(() => setPreview(null))
    }, 350)
    return () => clearTimeout(id)
  }, [form.symptoms, form.mortality_count, form.affected_count, form.herd_size, form.species, form.village_code]) // eslint-disable-line

  const locate = () => {
    if (!navigator.geolocation) return toast.warning('Geolocation unavailable')
    setGps('loading')
    navigator.geolocation.getCurrentPosition((p) => { set('lat', p.coords.latitude.toFixed(6)); set('lng', p.coords.longitude.toFixed(6)); setGps({ acc: Math.round(p.coords.accuracy) }) },
      () => { setGps(null); toast.warning('Could not get GPS fix', 'Village centroid will be used') }, { enableHighAccuracy: true, timeout: 8000 })
  }
  useEffect(() => { if (form.lat && form.lng) api(`/api/v1/geo/nearest-clinic?lat=${form.lat}&lng=${form.lng}`).then(setClinics).catch(() => {}) }, [form.lat, form.lng])

  const payload = () => ({ ...form, herd_size: Number(form.herd_size) || 0, affected_count: Number(form.affected_count) || 0, mortality_count: Number(form.mortality_count) || 0, ear_tags: form.ear_tags.split(/[,\s]+/).filter(Boolean), lat: form.lat || null, lng: form.lng || null, channel: 'web' })

  const submit = useMutation({
    mutationFn: () => api('/api/v1/cases', { method: 'POST', body: payload() }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['cases'] }); qc.invalidateQueries({ queryKey: ['summary'] })
      toast[d.case.risk_level === 'HIGH' ? 'error' : d.case.risk_level === 'MEDIUM' ? 'warning' : 'success'](`${term(d.case.risk_level)} · ${term(d.case.suspected_disease)}`, d.advisory)
      nav(`/cases/${d.case.id}`)
    },
    onError: (e) => {
      if (e.status && e.status < 500) return toast.error('Could not submit', e.message)
      offline.enqueue(payload()); toast.warning('Saved offline', 'Will sync automatically when connectivity returns')
    },
  })
  const saveOffline = () => { offline.enqueue(payload()); toast.info('Queued for sync', `${offline.read().length} report(s) waiting`); setForm((f) => ({ ...f, symptoms: [], notes: '', ear_tags: '', affected_count: 1, mortality_count: 0 })) }

  const errors = useMemo(() => ({
    symptoms: !form.symptoms.length && !Number(form.mortality_count) ? 'Select at least one symptom or record deaths' : null,
    village: !form.village_code ? 'Village required' : null,
    tags: form.ear_tags.split(/[,\s]+/).filter(Boolean).some((x) => !/^\d{12}$/.test(x)) ? 'Each ear tag must be 12 digits' : null,
  }), [form])
  const valid = !errors.symptoms && !errors.village && !errors.tags
  const symptomList = meta?.symptoms || []

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
      <div className="space-y-5">
        <PageHeader title={t('Report a case')} subtitle="Symptom & mortality report · triaged instantly by the dual-matrix engine" />
        <Card title="1 · Animals">
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {(meta?.species || ['cattle', 'buffalo', 'goat', 'sheep', 'poultry', 'pig']).map((s) => (
              <button key={s} type="button" onClick={() => set('species', s)} className={clsx('flex flex-col items-center gap-1 rounded-xl border p-3 text-xs font-medium capitalize transition', form.species === s ? 'border-forest-600 bg-forest-50 text-forest-900 ring-2 ring-forest-500/20' : 'border-slate-200 hover:border-slate-300')}>
                <span className="text-2xl">{SPECIES_ICON[s]}</span>{s}
              </button>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <Field label={t('Herd size')}><input type="number" min="0" className="input" value={form.herd_size} onChange={(e) => set('herd_size', e.target.value)} placeholder="e.g. 12" /></Field>
            <Field label={t('Affected')} required><input type="number" min="0" className="input" value={form.affected_count} onChange={(e) => set('affected_count', e.target.value)} /></Field>
            <Field label={t('Dead')}><input type="number" min="0" className={clsx('input', Number(form.mortality_count) > 0 && '!border-red-300 !bg-red-50')} value={form.mortality_count} onChange={(e) => set('mortality_count', e.target.value)} /></Field>
          </div>
          <div className="mt-3"><Field label={`${t('Ear tag')}s (Bharat Pashudhan, 12 digits)`} error={errors.tags} hint="Comma or space separated. Links this report to the animal's EHR."><input className="input font-mono" value={form.ear_tags} onChange={(e) => set('ear_tags', e.target.value)} placeholder="270000000001, 270000000002" /></Field></div>
        </Card>

        <Card title="2 · Symptoms" subtitle="Tap all that apply — combinations drive pathogen signatures">
          <div className="flex flex-wrap gap-2">
            {symptomList.map((s) => {
              const on = form.symptoms.includes(s)
              return <button key={s} type="button" onClick={() => set('symptoms', on ? form.symptoms.filter((x) => x !== s) : [...form.symptoms, s])} className={clsx('rounded-full border px-3 py-1.5 text-sm transition', on ? 'border-forest-700 bg-forest-800 text-white' : 'border-slate-200 bg-white text-slate-700 hover:border-forest-400')}>{term(s)}</button>
            })}
          </div>
          {errors.symptoms && <div className="mt-2 text-xs text-red-600">{errors.symptoms}</div>}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Field label="Onset date"><input type="date" className="input" value={form.onset_date} onChange={(e) => set('onset_date', e.target.value)} max={new Date().toISOString().slice(0, 10)} /></Field>
            <Field label={t('Notes')}><input className="input" value={form.notes} onChange={(e) => set('notes', e.target.value)} placeholder="Grazing near common water, new animal purchased…" /></Field>
          </div>
        </Card>

        <Card title="3 · Location" subtitle="LGD village code + optional GPS fix">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <Field label={t('Village')} required error={errors.village}>
              <select className="input" value={form.village_code} onChange={(e) => set('village_code', e.target.value)}>
                <option value="">Select village…</option>
                {villages.map((v) => <option key={v.code} value={v.code}>{v.name} — {talukaOf(v)}, {districtOf(v)} (LGD {v.code})</option>)}
              </select>
              {village && user.taluka_code && village.taluka_code !== user.taluka_code && !['acah','dcah','state','admin'].includes(user.role) && (
                <p className="mt-1 text-[11px] text-amber-700">Outside your assigned taluka — the case will be routed to that taluka's LDO; you'll keep read access as reporter.</p>
              )}
            </Field>
            <div className="flex items-end"><button type="button" onClick={locate} className="btn-secondary w-full">{gps === 'loading' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Crosshair className="h-4 w-4" />}Use GPS</button></div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-600">
            {village && <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{village.name} · {talukaOf(village)} taluka · {districtOf(village)} district · centroid {village.lat}, {village.lng}</span>}
            {form.lat && <span className="badge bg-sky-50 text-sky-700">GPS {form.lat}, {form.lng}{gps?.acc ? ` (±${gps.acc} m)` : ''}</span>}
          </div>
          {clinics?.clinics?.length > 0 && (
            <div className="mt-4 rounded-xl bg-slate-50 p-3">
              <div className="mb-2 text-xs font-semibold text-slate-600">{t('Nearest clinic')} · {clinics.backend}</div>
              <ul className="space-y-1.5 text-sm">{clinics.clinics.map((c) => <li key={c.name} className="flex items-center justify-between gap-2"><span className="truncate">{c.name}</span><span className="flex shrink-0 items-center gap-2 text-xs text-slate-500">{c.distance_km} km <a href={`tel:${c.officer_phone}`} className="btn-ghost !p-1"><Phone className="h-3.5 w-3.5" /></a></span></li>)}</ul>
            </div>
          )}
        </Card>

        <div className="flex flex-wrap items-center justify-end gap-2">
          <button type="button" onClick={saveOffline} disabled={!valid} className="btn-secondary"><WifiOff className="h-4 w-4" />Save offline</button>
          <button type="button" onClick={() => submit.mutate()} disabled={!valid || submit.isPending} className="btn-primary !px-6">{submit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t('Submit report')}</button>
        </div>
      </div>

      <div className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        <Card title="Live triage preview" subtitle="Dual-matrix: rules + MAHAVEDH + RandomForest" actions={<Sparkles className="h-4 w-4 text-saffron-500" />}>
          {!preview ? <div className="py-6 text-center text-xs text-slate-400">{navigator.onLine ? 'Select symptoms to see the assessment' : 'Offline — triage runs on sync'}</div> : (
            <div className="space-y-3">
              <div className="flex items-center justify-between"><RiskBadge level={preview.triage.level}>{term(preview.triage.level)}</RiskBadge><span className="text-2xl font-bold">{preview.triage.score}<span className="text-sm font-normal text-slate-400">/100</span></span></div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className={clsx('h-full transition-all', preview.triage.level === 'HIGH' ? 'bg-red-500' : preview.triage.level === 'MEDIUM' ? 'bg-amber-500' : 'bg-forest-500')} style={{ width: `${preview.triage.score}%` }} /></div>
              <div><div className="text-xs text-slate-500">{t('Suspected disease')}</div><div className="font-semibold">{term(preview.triage.suspected_disease)}</div></div>
              <ul className="space-y-1.5 text-xs text-slate-600">{preview.triage.explanation.map((x, i) => <li key={i} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-forest-600" />{x}</li>)}</ul>
              {preview.triage.predicted_deaths != null && <div className="rounded-xl bg-slate-50 p-2.5 text-xs"><span className="text-slate-500">RF projected mortality:</span> <span className="font-semibold">{preview.triage.predicted_deaths}</span> <span className="text-slate-400">({preview.triage.ml_band})</span></div>}
              <div className="rounded-xl border border-forest-200 bg-forest-50 p-3 text-xs text-forest-900"><div className="mb-0.5 font-semibold">{t('Advisory')}</div>{preview.advisory}</div>
            </div>
          )}
        </Card>
        <Card title={t('Offline queue')} subtitle={`${queue.length} pending · last-write-wins on sync`} padded={false}>
          {queue.length === 0 ? <div className="px-5 py-5 text-center text-xs text-slate-400">Queue is empty</div> : (
            <ul className="divide-y divide-slate-100">{queue.map((r) => <li key={r.local_id} className="flex items-center gap-2 px-4 py-2 text-xs"><span>{SPECIES_ICON[r.species]}</span><span className="flex-1 truncate">{r.symptoms?.map(term).join(', ') || `${r.mortality_count} deaths`} · {timeAgo(r.queued_at)}</span><button onClick={() => offline.remove(r.local_id)} className="text-slate-400 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button></li>)}</ul>
          )}
        </Card>
      </div>
    </div>
  )
}
