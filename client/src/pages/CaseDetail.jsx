import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { ArrowLeft, ArrowRight, Barcode, CheckCircle2, ClipboardList, FlaskConical, Loader2, Pencil, Pill, Printer, ShieldCheck, Sparkles, Trash2, UserCheck, Thermometer } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, ConfirmButton, ErrorState, Field, Modal, PageHeader, RiskBadge, StatusBadge, fmtDateTime, timeAgo, CHANNEL_ICON, RISK_COLOR } from '../components/ui'

const FLOW = ['REPORTED', 'FIELD_INSPECTED_BY_LDO', 'SAMPLE_COLLECTED', 'LAB_TRANSIT', 'LAB_RECEIVED', 'PATHOGEN_CONFIRMED', 'CASE_RESOLVED']
const SAMPLE_TYPES = ['Whole blood (EDTA)', 'Serum', 'Skin biopsy / scab', 'Vesicular epithelium', 'Nasal swab', 'Heart blood swab', 'Ear-vein blood smear', 'Faecal sample', 'Milk sample', 'Tissue (post-mortem)']

export default function CaseDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const { user, isClinical, isDistrictPlus, is } = useAuth()
  const { t, term, statusLabel } = useI18n()
  const q = useQuery({ queryKey: ['cases', id], queryFn: () => api(`/api/v1/cases/${id}`) })
  const [modal, setModal] = useState(null)
  const invalidate = () => { qc.invalidateQueries({ queryKey: ['cases'] }); qc.invalidateQueries({ queryKey: ['summary'] }); qc.invalidateQueries({ queryKey: ['referrals'] }) }

  const transition = useMutation({
    mutationFn: ({ to, note }) => api(`/api/v1/cases/${id}/transition`, { method: 'POST', body: { to, note } }),
    onMutate: async ({ to }) => { await qc.cancelQueries({ queryKey: ['cases', id] }); const prev = qc.getQueryData(['cases', id]); qc.setQueryData(['cases', id], (d) => d && { case: { ...d.case, status: to, allowed_transitions: [] } }); return { prev } },
    onError: (e, _v, ctx) => { qc.setQueryData(['cases', id], ctx.prev); toast.error('Transition failed', e.message) },
    onSuccess: (d) => { toast.success(`Status → ${statusLabel(d.case.status)}`); setModal(null) },
    onSettled: invalidate,
  })
  const assign = useMutation({ mutationFn: () => api(`/api/v1/cases/${id}/assign`, { method: 'POST', body: {} }), onSuccess: () => { toast.success('Assigned to you'); invalidate() }, onError: (e) => toast.error(e.message) })
  const del = useMutation({ mutationFn: () => api(`/api/v1/cases/${id}`, { method: 'DELETE' }), onSuccess: () => { toast.success('Case deleted'); invalidate(); nav('/cases') }, onError: (e) => toast.error(e.message) })

  if (q.isLoading) return <div className="space-y-4"><div className="skeleton h-8 w-72" /><div className="grid gap-4 lg:grid-cols-3"><div className="skeleton h-64 lg:col-span-2" /><div className="skeleton h-64" /></div></div>
  if (q.isError) return <ErrorState error={q.error} retry={q.refetch} />
  const c = q.data.case
  const tri = c.triage || {}
  const stepIdx = FLOW.indexOf(c.status === 'PATHOGEN_REJECTED' ? 'PATHOGEN_CONFIRMED' : c.status)
  const canEdit = isClinical || (c.reporter_id === user.id && c.status === 'REPORTED')
  const canDelete = isDistrictPlus || (c.reporter_id === user.id && c.status === 'REPORTED')
  const canSample = isClinical && !is('acah', 'dcah') && ['REPORTED', 'FIELD_INSPECTED_BY_LDO', 'SAMPLE_COLLECTED'].includes(c.status)

  return (
    <div className="space-y-5">
      <Link to="/cases" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800"><ArrowLeft className="h-3.5 w-3.5" />{t('Cases')}</Link>
      <PageHeader title={<span className="flex flex-wrap items-center gap-2"><span className="font-mono">{c.id}</span><RiskBadge level={c.risk_level}>{term(c.risk_level)} · {c.risk_score}</RiskBadge><StatusBadge status={c.status} label={statusLabel(c.status)} /></span>}
        subtitle={`${term(c.suspected_disease)} · ${c.species} · ${c.village}, ${c.taluka}, ${c.district} · ${CHANNEL_ICON[c.channel]} ${c.channel} · ${timeAgo(c.created_at)} by ${c.reporter_name}`}
        actions={<>
          {isClinical && !c.assigned_to && <button onClick={() => assign.mutate()} className="btn-secondary"><UserCheck className="h-4 w-4" />Assign to me</button>}
          {canSample && <button onClick={() => setModal('sample')} className="btn-secondary"><FlaskConical className="h-4 w-4" />Collect sample</button>}
          {isClinical && c.animals?.length > 0 && <button onClick={() => setModal('treat')} className="btn-secondary"><Pill className="h-4 w-4" />{t('Add treatment')}</button>}
          {canEdit && <button onClick={() => setModal('edit')} className="btn-secondary"><Pencil className="h-4 w-4" />{t('Edit')}</button>}
          {canDelete && <ConfirmButton className="btn-ghost !text-red-600" confirmLabel="Delete this case? It will be soft-deleted and hidden from all dashboards." onConfirm={() => del.mutate()} busy={del.isPending}><Trash2 className="h-4 w-4" /></ConfirmButton>}
        </>} />

      {/* workflow stepper */}
      <Card padded={false}>
        <div className="flex items-center gap-0 overflow-x-auto px-4 py-4">
          {FLOW.map((s, i) => {
            const label = s === 'PATHOGEN_CONFIRMED' && c.status === 'PATHOGEN_REJECTED' ? 'PATHOGEN_REJECTED' : s
            const done = i < stepIdx, cur = i === stepIdx
            return (
              <div key={s} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div className={clsx('grid h-7 w-7 place-items-center rounded-full text-[11px] font-bold', done ? 'bg-forest-700 text-white' : cur ? 'bg-saffron-500 text-forest-950 ring-4 ring-saffron-400/30' : 'bg-slate-100 text-slate-400')}>{done ? <CheckCircle2 className="h-4 w-4" /> : i + 1}</div>
                  <div className={clsx('mt-1 w-24 text-center text-[10px] leading-tight', cur ? 'font-semibold text-slate-900' : 'text-slate-500')}>{statusLabel(label)}</div>
                </div>
                {i < FLOW.length - 1 && <div className={clsx('mx-1 mb-5 h-0.5 w-8 sm:w-12', i < stepIdx ? 'bg-forest-600' : 'bg-slate-200')} />}
              </div>
            )
          })}
        </div>
        {c.allowed_transitions?.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50/60 px-4 py-3">
            <span className="text-xs font-medium text-slate-500">Advance:</span>
            {c.allowed_transitions.map((to) => <button key={to} onClick={() => setModal({ transition: to })} className={clsx(to === 'CASE_RESOLVED' ? 'btn-secondary' : 'btn-primary', '!py-1.5 text-xs')} disabled={transition.isPending}>{statusLabel(to)}<ArrowRight className="h-3.5 w-3.5" /></button>)}
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card title="Report details">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
              {[['Species', <span className="capitalize">{c.species}</span>], ['Herd size', c.herd_size || '—'], ['Affected', c.affected_count], ['Dead', <span className={c.mortality_count ? 'font-semibold text-red-700' : ''}>{c.mortality_count}</span>],
                ['Onset', c.onset_date || '—'], ['Reporter', c.reporter_name], ['Assigned to', c.assignee ? `${c.assignee.full_name}` : '—'], ['LGD village', <span className="font-mono">{c.village_code}</span>]].map(([k, v]) => (
                <div key={k}><dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{t(k)}</dt><dd className="mt-0.5 text-slate-800">{v}</dd></div>
              ))}
            </dl>
            <div className="mt-4"><div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{t('Symptoms')}</div><div className="mt-1.5 flex flex-wrap gap-1.5">{(c.symptoms || []).map((s) => <span key={s} className="badge bg-slate-100 text-slate-700">{term(s)}</span>)}</div></div>
            {c.notes && <div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-700">{c.notes}</div>}
            {c.animals?.length > 0 && <div className="mt-4"><div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Linked animals (EHR)</div><div className="mt-1.5 flex flex-wrap gap-2">{c.animals.map((a) => <Link key={a.id} to={`/animals/${a.ear_tag}`} className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs hover:border-forest-400"><span className="font-mono font-semibold">{a.ear_tag}</span> · {a.breed} {a.species} · {a.owner_name}</Link>)}</div></div>}
          </Card>

          <Card title="Triage assessment" subtitle={tri.engine} actions={<Sparkles className="h-4 w-4 text-saffron-500" />}>
            <div className="grid gap-4 sm:grid-cols-[1fr_200px]">
              <div>
                <ul className="space-y-2 text-sm text-slate-700">{(tri.explanation || []).map((x, i) => <li key={i} className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-forest-600" />{x}</li>)}</ul>
                <div className="mt-3 flex flex-wrap gap-1.5">{(tri.signals || []).map((s) => <span key={s} className="badge bg-forest-50 text-forest-800 font-mono">{s}</span>)}</div>
                <div className="mt-4 rounded-xl border border-forest-200 bg-forest-50 p-3 text-sm text-forest-900"><div className="text-[11px] font-semibold uppercase">{t('Advisory')}</div>{c.advisory}</div>
              </div>
              <div className="space-y-2 text-xs">
                <div className="rounded-xl bg-slate-50 p-3"><div className="text-slate-500">Probability</div><div className="text-xl font-bold">{Math.round((tri.probability || 0) * 100)}%</div></div>
                <div className="rounded-xl bg-slate-50 p-3"><div className="text-slate-500">RF mortality projection</div><div className="text-xl font-bold">{tri.predicted_deaths ?? '—'} <span className="text-xs font-normal text-slate-400">{tri.ml_band}</span></div></div>
                <div className="rounded-xl bg-slate-50 p-3"><div className="flex items-center gap-1 text-slate-500"><Thermometer className="h-3 w-3" />MAHAVEDH</div>{tri.weather ? <div>{tri.weather.humidity}% RH · {tri.weather.temperature_c}°C{tri.weather_amplified && <span className="ml-1 badge bg-amber-100 text-amber-800">+15%</span>}</div> : <div className="text-slate-400">no telemetry</div>}</div>
                <div className="rounded-xl bg-slate-50 p-3"><div className="text-slate-500">Taluka 14d</div><div>{tri.local_activity_14d?.n ?? 0} cases · {tri.local_activity_14d?.deaths ?? 0} deaths</div></div>
              </div>
            </div>
          </Card>

          <Card title="Samples & laboratory chain of custody" subtitle="Cryptographically signed Code-128 barcodes" padded={false}>
            {!c.referrals?.length ? <div className="px-5 py-8 text-center text-sm text-slate-400"><Barcode className="mx-auto mb-1 h-5 w-5" />No samples collected{canSample && <div className="mt-2"><button onClick={() => setModal('sample')} className="btn-secondary text-xs">Collect sample</button></div>}</div> : (
              <ul className="divide-y divide-slate-100">{c.referrals.map((r) => <ReferralRow key={r.id} r={r} onChange={invalidate} />)}</ul>
            )}
          </Card>

          {c.treatments?.length > 0 && (
            <Card title={t('Treatments')} padded={false}>
              <table className="table"><thead><tr><th>Animal</th><th>Diagnosis / treatment</th><th>Drug</th><th>Outcome</th><th>By</th></tr></thead>
                <tbody>{c.treatments.map((x) => <tr key={x.id}><td className="font-mono text-xs">{x.ear_tag}</td><td>{x.diagnosis}<div className="text-xs text-slate-500">{x.treatment}</div></td><td className="text-xs">{x.drug} {x.dosage}</td><td><span className="badge bg-slate-100">{x.outcome || '—'}</span></td><td className="text-xs">{x.clinician_name}<div className="text-slate-400">{x.treated_on}</div></td></tr>)}</tbody></table>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card title="Location" subtitle={`Precision: ${c.precision}`} padded={false}>
            {c.lat != null ? (
              <MapContainer center={[c.lat, c.lng]} zoom={c.precision === 'gps' ? 13 : 11} style={{ height: 220 }} scrollWheelZoom={false} className="!rounded-b-2xl !rounded-t-none">
                <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <CircleMarker center={[c.lat, c.lng]} radius={10} pathOptions={{ color: RISK_COLOR[c.risk_level], fillColor: RISK_COLOR[c.risk_level], fillOpacity: 0.7 }}><Popup>{c.village}</Popup></CircleMarker>
                {c.nearby_cases.filter((n) => n.lat != null).map((n) => <CircleMarker key={n.id} center={[n.lat, n.lng]} radius={6} pathOptions={{ color: RISK_COLOR[n.risk_level], fillOpacity: 0.5, weight: 1 }}><Popup><Link to={`/cases/${n.id}`}>{n.id}</Link><br />{term(n.suspected_disease)}</Popup></CircleMarker>)}
              </MapContainer>
            ) : <div className="p-6 text-center text-xs text-slate-400">No coordinates</div>}
            <div className="p-3 text-xs text-slate-500">{c.nearby_cases.length} other case(s) in {c.taluka} taluka in the last 14 days</div>
          </Card>

          <Card title={t('Timeline')} padded={false}>
            <ol className="relative ml-4 space-y-4 border-l border-slate-200 py-4 pr-4">
              {[...c.events].reverse().map((e) => (
                <li key={e.id} className="ml-4">
                  <span className={clsx('absolute -left-1.5 mt-1 h-3 w-3 rounded-full ring-4 ring-white', e.kind === 'transition' ? 'bg-forest-600' : e.kind === 'sample' ? 'bg-violet-500' : e.kind === 'treatment' ? 'bg-sky-500' : 'bg-slate-300')} />
                  <div className="text-xs font-semibold text-slate-800">{e.kind === 'transition' ? <>{statusLabel(e.from_status)} → {statusLabel(e.to_status)}</> : e.kind}</div>
                  {e.note && <div className="text-xs text-slate-600">{e.note}</div>}
                  <div className="text-[11px] text-slate-400">{e.actor_name} · {fmtDateTime(e.created_at)}</div>
                </li>
              ))}
            </ol>
          </Card>

          {c.nearby_cases.length > 0 && (
            <Card title="Nearby cases (14d)" padded={false}>
              <ul className="divide-y divide-slate-100">{c.nearby_cases.map((n) => <li key={n.id}><Link to={`/cases/${n.id}`} className="flex items-center justify-between px-4 py-2 text-xs hover:bg-slate-50"><span><span className="font-mono">{n.id}</span> · {term(n.suspected_disease)}</span><RiskBadge level={n.risk_level} /></Link></li>)}</ul>
            </Card>
          )}
        </div>
      </div>

      {/* modals */}
      <Modal open={!!modal?.transition} onClose={() => setModal(null)} title={`Move to "${statusLabel(modal?.transition)}"`}
        footer={<><button className="btn-secondary" onClick={() => setModal(null)}>{t('Cancel')}</button><button className="btn-primary" disabled={transition.isPending} onClick={() => transition.mutate({ to: modal.transition, note: modal.note })}>{transition.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Confirm</button></>}>
        <Field label="Note (optional)"><textarea className="input" rows={3} value={modal?.note || ''} onChange={(e) => setModal({ ...modal, note: e.target.value })} placeholder="Findings from field visit, containment measures…" /></Field>
      </Modal>
      <SampleModal open={modal === 'sample'} onClose={() => setModal(null)} caseId={id} defaultLab={c.district_code} onDone={invalidate} />
      <TreatModal open={modal === 'treat'} onClose={() => setModal(null)} caseId={id} animals={c.animals || []} disease={c.suspected_disease} onDone={invalidate} />
      <EditModal open={modal === 'edit'} onClose={() => setModal(null)} c={c} onDone={invalidate} />
    </div>
  )
}

function ReferralRow({ r, onChange }) {
  const { is } = useAuth()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const adv = useMutation({ mutationFn: () => api(`/api/v1/lab-referrals/${r.id}/advance`, { method: 'POST', body: {} }), onSuccess: () => { toast.success('Custody updated'); onChange() }, onError: (e) => toast.error(e.message) })
  const nextLabel = { COLLECTED: 'Dispatch to lab', IN_TRANSIT: 'Receive at lab' }[r.status]
  const canAdv = r.status === 'COLLECTED' ? !is('lab', 'farmer', 'pashu_sakhi') : r.status === 'IN_TRANSIT' ? is('lab', 'state', 'admin') : false
  return (
    <li className="px-5 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <img src={`/api/v1/lab-referrals/${r.id}/barcode.svg`} alt={r.barcode} className="h-12 rounded border border-slate-200 bg-white" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-sm font-semibold">{r.barcode}</span><span className="badge bg-forest-50 text-forest-800"><ShieldCheck className="h-3 w-3" />HMAC {r.signature}</span><StatusBadge status={r.status} />{r.priority === 'urgent' && <span className="badge bg-red-100 text-red-700">URGENT</span>}{r.result && <span className={clsx('badge', r.result === 'POSITIVE' ? 'bg-red-600 text-white' : 'bg-slate-700 text-white')}>{r.result}{r.pathogen ? ` · ${r.pathogen}` : ''}</span>}</div>
          <div className="text-xs text-slate-500">{r.sample_type} · {r.transport_media || 'no media specified'} · {r.cold_chain_ok ? '❄ cold chain OK' : '⚠ cold chain break'} · {r.lab_name}</div>
        </div>
        <div className="flex items-center gap-1">
          <a href={`/api/v1/lab-referrals/${r.id}/barcode.svg`} target="_blank" rel="noreferrer" className="btn-ghost !p-1.5" title="Print label"><Printer className="h-4 w-4" /></a>
          {canAdv && nextLabel && <button onClick={() => adv.mutate()} className="btn-secondary !py-1 text-xs" disabled={adv.isPending}>{nextLabel}</button>}
          <button onClick={() => setOpen(!open)} className="btn-ghost !py-1 text-xs">{open ? 'Hide' : 'Custody log'}</button>
        </div>
      </div>
      {open && <ol className="mt-3 space-y-1.5 border-l-2 border-slate-200 pl-3 text-xs">{r.chain.map((x, i) => <li key={i}><span className="font-medium text-slate-800">{x.event}</span> <span className="text-slate-500">· {x.by} · {x.location} · {fmtDateTime(x.at)}</span></li>)}{r.result_notes && <li className="text-slate-600">Result notes: {r.result_notes}</li>}</ol>}
    </li>
  )
}

function SampleModal({ open, onClose, caseId, onDone }) {
  const toast = useToast()
  const labs = useQuery({ queryKey: ['labs'], queryFn: () => api('/api/v1/labs'), enabled: open })
  const [f, setF] = useState({ sample_type: SAMPLE_TYPES[0], transport_media: 'Ice pack (4°C)', cold_chain_ok: true, priority: 'routine', lab_id: '', test_requested: '' })
  const m = useMutation({ mutationFn: () => api(`/api/v1/cases/${caseId}/lab-referrals`, { method: 'POST', body: { ...f, lab_id: f.lab_id || undefined } }), onSuccess: (d) => { toast.success('Sample barcoded', d.referral.barcode); onDone(); onClose() }, onError: (e) => toast.error(e.message) })
  return (
    <Modal open={open} onClose={onClose} title="Collect sample & refer to laboratory" footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={m.isPending} onClick={() => m.mutate()}>{m.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Barcode className="h-4 w-4" />}Issue barcode</button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Sample type" required><select className="input" value={f.sample_type} onChange={(e) => setF({ ...f, sample_type: e.target.value })}>{SAMPLE_TYPES.map((s) => <option key={s}>{s}</option>)}</select></Field>
        <Field label="Transport media"><input className="input" value={f.transport_media} onChange={(e) => setF({ ...f, transport_media: e.target.value })} /></Field>
        <Field label="Laboratory"><select className="input" value={f.lab_id} onChange={(e) => setF({ ...f, lab_id: e.target.value })}><option value="">Auto (nearest by district)</option>{labs.data?.items.map((l) => <option key={l.id} value={l.id}>{l.code} — {l.name} ({l.pending} pending)</option>)}</select></Field>
        <Field label="Priority"><select className="input" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}><option value="routine">Routine</option><option value="urgent">Urgent</option></select></Field>
        <Field label="Test requested"><input className="input" value={f.test_requested} onChange={(e) => setF({ ...f, test_requested: e.target.value })} placeholder="PCR, ELISA, culture…" /></Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={f.cold_chain_ok} onChange={(e) => setF({ ...f, cold_chain_ok: e.target.checked })} className="h-4 w-4 accent-forest-700" />Cold chain maintained</label>
      </div>
      <p className="mt-3 text-xs text-slate-500">A Code-128 label with an HMAC-SHA256 signature suffix is generated. The receiving lab verifies the signature on scan, so a retyped or forged barcode is rejected.</p>
    </Modal>
  )
}

function TreatModal({ open, onClose, caseId, animals, disease, onDone }) {
  const toast = useToast()
  const [f, setF] = useState({ animal: animals[0]?.ear_tag || '', diagnosis: disease, treatment: '', drug: '', dosage: '', treated_on: new Date().toISOString().slice(0, 10), outcome: 'under observation' })
  const m = useMutation({ mutationFn: () => api(`/api/v1/animals/${f.animal}/treatments`, { method: 'POST', body: { ...f, case_id: caseId } }), onSuccess: () => { toast.success('Treatment recorded'); onDone(); onClose() }, onError: (e) => toast.error(e.message) })
  return (
    <Modal open={open} onClose={onClose} title="Record treatment" footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={m.isPending || !f.treatment} onClick={() => m.mutate()}>Save</button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Animal" required><select className="input" value={f.animal} onChange={(e) => setF({ ...f, animal: e.target.value })}>{animals.map((a) => <option key={a.id} value={a.ear_tag}>{a.ear_tag} · {a.breed}</option>)}</select></Field>
        <Field label="Diagnosis"><input className="input" value={f.diagnosis} onChange={(e) => setF({ ...f, diagnosis: e.target.value })} /></Field>
        <Field label="Treatment" required><input className="input" value={f.treatment} onChange={(e) => setF({ ...f, treatment: e.target.value })} placeholder="Supportive therapy, isolation…" /></Field>
        <Field label="Drug"><input className="input" value={f.drug} onChange={(e) => setF({ ...f, drug: e.target.value })} /></Field>
        <Field label="Dosage"><input className="input" value={f.dosage} onChange={(e) => setF({ ...f, dosage: e.target.value })} /></Field>
        <Field label="Date"><input type="date" className="input" value={f.treated_on} onChange={(e) => setF({ ...f, treated_on: e.target.value })} /></Field>
        <Field label="Outcome"><select className="input" value={f.outcome} onChange={(e) => setF({ ...f, outcome: e.target.value })}>{['under observation', 'improving', 'recovered', 'died'].map((o) => <option key={o}>{o}</option>)}</select></Field>
      </div>
    </Modal>
  )
}

function EditModal({ open, onClose, c, onDone }) {
  const toast = useToast()
  const { term, meta } = useI18n()
  const [f, setF] = useState({ herd_size: c.herd_size, affected_count: c.affected_count, mortality_count: c.mortality_count, symptoms: c.symptoms || [], notes: c.notes || '' })
  const m = useMutation({ mutationFn: () => api(`/api/v1/cases/${c.id}`, { method: 'PATCH', body: f }), onSuccess: () => { toast.success('Case updated', 'Triage re-evaluated'); onDone(); onClose() }, onError: (e) => toast.error(e.message) })
  return (
    <Modal open={open} onClose={onClose} title="Edit report" footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={m.isPending} onClick={() => m.mutate()}>Save & re-triage</button></>}>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Herd size"><input type="number" className="input" value={f.herd_size} onChange={(e) => setF({ ...f, herd_size: +e.target.value })} /></Field>
        <Field label="Affected"><input type="number" className="input" value={f.affected_count} onChange={(e) => setF({ ...f, affected_count: +e.target.value })} /></Field>
        <Field label="Dead"><input type="number" className="input" value={f.mortality_count} onChange={(e) => setF({ ...f, mortality_count: +e.target.value })} /></Field>
      </div>
      <div className="mt-3"><span className="label">Symptoms</span><div className="flex flex-wrap gap-1.5">{(meta?.symptoms || []).map((s) => { const on = f.symptoms.includes(s); return <button key={s} type="button" onClick={() => setF({ ...f, symptoms: on ? f.symptoms.filter((x) => x !== s) : [...f.symptoms, s] })} className={clsx('rounded-full border px-2.5 py-1 text-xs', on ? 'border-forest-700 bg-forest-800 text-white' : 'border-slate-200')}>{term(s)}</button> })}</div></div>
      <div className="mt-3"><Field label="Notes"><textarea className="input" rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field></div>
    </Modal>
  )
}
