import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Pencil, Pill, Syringe, Trash2, ClipboardList, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, ConfirmButton, ErrorState, Field, Modal, PageHeader, RiskBadge, StatusBadge, fmtDate } from '../components/ui'
import { RegisterModal } from './Animals'

const VACC = { cattle: ['FMD (Raksha Ovac)|Foot and Mouth Disease|180', 'HS (Raksha HS)|Haemorrhagic Septicaemia|365', 'BQ|Black Quarter|365', 'Brucella S19|Brucellosis|0', 'LSD (Goat pox vaccine)|Lumpy Skin Disease|365', 'Anthrax spore vaccine|Anthrax|365'], buffalo: ['FMD (Raksha Ovac)|Foot and Mouth Disease|180', 'HS (Raksha HS)|Haemorrhagic Septicaemia|365', 'BQ|Black Quarter|365', 'Anthrax spore vaccine|Anthrax|365'], goat: ['PPR (Sungri/96)|Peste des petits ruminants|1095', 'ET|Enterotoxaemia|365', 'Goat pox|Goat pox|365'], sheep: ['PPR (Sungri/96)|Peste des petits ruminants|1095', 'ET|Enterotoxaemia|365', 'Sheep pox|Sheep pox|365'], poultry: ['Ranikhet (Lasota)|Newcastle disease|180', 'IBD|Gumboro|365'], pig: ['CSF|Classical Swine Fever|365'] }

export default function AnimalDetail() {
  const { key } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const { user, isClinical, is } = useAuth()
  const { t, term, statusLabel } = useI18n()
  const q = useQuery({ queryKey: ['animals', key], queryFn: () => api(`/api/v1/animals/${key}`) })
  const [modal, setModal] = useState(null)
  const inv = () => { qc.invalidateQueries({ queryKey: ['animals'] }); qc.invalidateQueries({ queryKey: ['coverage'] }) }
  const del = useMutation({ mutationFn: () => api(`/api/v1/animals/${q.data.animal.id}`, { method: 'DELETE' }), onSuccess: () => { toast.success('Animal removed from ledger'); inv(); nav('/animals') }, onError: (e) => toast.error(e.message) })
  const delVac = useMutation({ mutationFn: (id) => api(`/api/v1/vaccinations/${id}`, { method: 'DELETE' }), onSuccess: () => { toast.success('Vaccination removed'); inv() } })

  if (q.isLoading) return <div className="space-y-4"><div className="skeleton h-8 w-72" /><div className="skeleton h-64" /></div>
  if (q.isError) return <ErrorState error={q.error} retry={q.refetch} />
  const a = q.data.animal
  const canVacc = isClinical || is('pashu_sakhi')
  return (
    <div className="space-y-5">
      <Link to="/animals" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800"><ArrowLeft className="h-3.5 w-3.5" />{t('Animals')}</Link>
      <PageHeader title={<span className="font-mono">{a.ear_tag}</span>} subtitle={`${a.breed} ${a.species} · ${a.sex} · born ${a.birth_year} · ${a.color || ''} · ${a.village}, ${a.taluka}, ${a.district}`}
        actions={<>
          {canVacc && <button onClick={() => setModal('vacc')} className="btn-primary"><Syringe className="h-4 w-4" />{t('Add vaccination')}</button>}
          {canVacc && <button onClick={() => setModal('treat')} className="btn-secondary"><Pill className="h-4 w-4" />{t('Add treatment')}</button>}
          <button onClick={() => setModal('edit')} className="btn-secondary"><Pencil className="h-4 w-4" />{t('Edit')}</button>
          {(isClinical || a.owner_id === user.id) && <ConfirmButton className="btn-ghost !text-red-600" confirmLabel="Remove this animal from the ledger?" onConfirm={() => del.mutate()} busy={del.isPending}><Trash2 className="h-4 w-4" /></ConfirmButton>}
        </>} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card title="Vaccination record" padded={false}>
            {!a.vaccinations.length ? <div className="p-6 text-center text-sm text-slate-400">No vaccinations recorded</div> : (
              <table className="table"><thead><tr><th>Vaccine</th><th>Protects against</th><th>Given</th><th>Next due</th><th>Batch</th><th>By</th><th /></tr></thead>
                <tbody>{a.vaccinations.map((v) => { const due = v.next_due_on && new Date(v.next_due_on); const overdue = due && due < new Date(); const soon = due && !overdue && due < new Date(Date.now() + 30 * 864e5); return (
                  <tr key={v.id}><td className="font-medium">{v.vaccine}</td><td>{term(v.disease)}</td><td className="text-xs">{fmtDate(v.administered_on)}</td><td className="text-xs">{due ? <span className={clsx('badge', overdue ? 'bg-red-100 text-red-700' : soon ? 'bg-amber-100 text-amber-800' : 'bg-slate-100')}>{fmtDate(v.next_due_on)}{overdue ? ' · overdue' : soon ? ' · due soon' : ''}</span> : '—'}</td><td className="font-mono text-xs">{v.batch_no}</td><td className="text-xs">{v.administered_by}</td><td>{canVacc && <button onClick={() => delVac.mutate(v.id)} className="text-slate-300 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>}</td></tr>) })}</tbody></table>
            )}
          </Card>
          <Card title={t('Treatments')} padded={false}>
            {!a.treatments.length ? <div className="p-6 text-center text-sm text-slate-400">No treatments recorded</div> : (
              <table className="table"><thead><tr><th>Date</th><th>Diagnosis</th><th>Treatment</th><th>Drug / dose</th><th>Outcome</th><th>Clinician</th></tr></thead>
                <tbody>{a.treatments.map((x) => <tr key={x.id}><td className="text-xs whitespace-nowrap">{fmtDate(x.treated_on)}</td><td className="font-medium">{term(x.diagnosis)}{x.case_id && <Link to={`/cases/${x.case_id}`} className="ml-1 font-mono text-[10px] text-forest-700 hover:underline">{x.case_id}</Link>}</td><td className="text-xs">{x.treatment}</td><td className="text-xs">{x.drug} {x.dosage}</td><td><span className={clsx('badge', x.outcome === 'recovered' ? 'bg-forest-100 text-forest-800' : x.outcome === 'died' ? 'bg-red-100 text-red-700' : 'bg-slate-100')}>{x.outcome || '—'}</span></td><td className="text-xs">{x.clinician_name}</td></tr>)}</tbody></table>
            )}
          </Card>
          <Card title="Linked disease reports" padded={false}>
            {!a.cases.length ? <div className="p-6 text-center text-sm text-slate-400"><ClipboardList className="mx-auto mb-1 h-4 w-4" />No reports reference this ear tag</div> : (
              <ul className="divide-y divide-slate-100">{a.cases.map((c) => <li key={c.id}><Link to={`/cases/${c.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50"><RiskBadge level={c.risk_level} /><span className="flex-1 text-sm"><span className="font-mono text-xs">{c.id}</span> · {term(c.suspected_disease)}</span><StatusBadge status={c.status} label={statusLabel(c.status)} /><span className="text-xs text-slate-400">{fmtDate(c.created_at)}</span></Link></li>)}</ul>
            )}
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="Owner">
            <div className="text-sm font-semibold">{a.owner_name || '—'}</div><div className="text-xs text-slate-500">{a.owner_phone}</div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs"><dt className="text-slate-500">LGD village</dt><dd className="font-mono">{a.village_code}</dd><dt className="text-slate-500">Status</dt><dd className="capitalize">{a.status}</dd><dt className="text-slate-500">Registered</dt><dd>{fmtDate(a.created_at)}</dd></dl>
            {a.notes && <div className="mt-3 rounded-xl bg-slate-50 p-2 text-xs">{a.notes}</div>}
          </Card>
          <Card title={t('Timeline')} padded={false}>
            <ol className="relative ml-4 space-y-3 border-l border-slate-200 py-4 pr-4">{a.timeline.map((e, i) => (
              <li key={i} className="ml-4"><span className={clsx('absolute -left-1.5 mt-1 h-3 w-3 rounded-full ring-4 ring-white', e.kind === 'vaccination' ? 'bg-forest-600' : e.kind === 'treatment' ? 'bg-sky-500' : 'bg-red-500')} />
                <div className="text-xs font-semibold text-slate-800">{e.kind === 'case' ? term(e.title) : e.title}</div><div className="text-xs text-slate-500">{e.kind === 'case' ? term(e.detail) : e.detail}{e.outcome ? ` · ${e.outcome}` : ''}</div><div className="text-[11px] text-slate-400">{fmtDate(e.at)}{e.by ? ` · ${e.by}` : ''}</div></li>
            ))}</ol>
          </Card>
        </div>
      </div>
      <VaccModal open={modal === 'vacc'} onClose={() => setModal(null)} animal={a} onDone={() => { inv(); q.refetch() }} />
      <TreatModal open={modal === 'treat'} onClose={() => setModal(null)} animal={a} onDone={() => { inv(); q.refetch() }} />
      {modal === 'edit' && <RegisterModal open onClose={() => setModal(null)} user={user} initial={{ id: a.id, ear_tag: a.ear_tag, species: a.species, breed: a.breed, sex: a.sex, birth_year: a.birth_year, color: a.color || '', owner_name: a.owner_name || '', owner_phone: a.owner_phone || '', village_code: a.village_code, notes: a.notes || '', status: a.status }} onSaved={(an) => { if (an.ear_tag !== key) nav(`/animals/${an.ear_tag}`, { replace: true }); q.refetch() }} />}
    </div>
  )
}

function VaccModal({ open, onClose, animal, onDone }) {
  const toast = useToast()
  const opts = VACC[animal.species] || []
  const [sel, setSel] = useState(opts[0] || '')
  const [f, setF] = useState({ administered_on: new Date().toISOString().slice(0, 10), batch_no: '', administered_by: '' })
  const [vaccine, disease, interval] = sel.split('|')
  const nextDue = interval && +interval ? new Date(new Date(f.administered_on).getTime() + +interval * 864e5).toISOString().slice(0, 10) : null
  const m = useMutation({ mutationFn: () => api(`/api/v1/animals/${animal.id}/vaccinations`, { method: 'POST', body: { vaccine, disease, next_due_on: nextDue, ...f, administered_by: f.administered_by || undefined } }), onSuccess: () => { toast.success('Vaccination recorded', nextDue ? `Next due ${nextDue}` : ''); onDone(); onClose() }, onError: (e) => toast.error(e.message) })
  return (
    <Modal open={open} onClose={onClose} title="Record vaccination" footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={m.isPending} onClick={() => m.mutate()}>{m.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Save</button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Vaccine" required><select className="input" value={sel} onChange={(e) => setSel(e.target.value)}>{opts.map((o) => <option key={o} value={o}>{o.split('|')[0]} — {o.split('|')[1]}</option>)}</select></Field>
        <Field label="Date administered" required><input type="date" className="input" value={f.administered_on} onChange={(e) => setF({ ...f, administered_on: e.target.value })} /></Field>
        <Field label="Batch no."><input className="input" value={f.batch_no} onChange={(e) => setF({ ...f, batch_no: e.target.value })} /></Field>
        <Field label="Administered by" hint="Defaults to you"><input className="input" value={f.administered_by} onChange={(e) => setF({ ...f, administered_by: e.target.value })} /></Field>
      </div>
      <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs text-slate-600">Next due: <b>{nextDue || 'one-time vaccine'}</b> (interval {interval || 0} days)</div>
    </Modal>
  )
}

function TreatModal({ open, onClose, animal, onDone }) {
  const toast = useToast()
  const [f, setF] = useState({ diagnosis: '', treatment: '', drug: '', dosage: '', treated_on: new Date().toISOString().slice(0, 10), outcome: 'under observation' })
  const m = useMutation({ mutationFn: () => api(`/api/v1/animals/${animal.id}/treatments`, { method: 'POST', body: f }), onSuccess: () => { toast.success('Treatment recorded'); onDone(); onClose() }, onError: (e) => toast.error(e.message) })
  return (
    <Modal open={open} onClose={onClose} title="Record treatment" footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={m.isPending || !f.treatment} onClick={() => m.mutate()}>Save</button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Diagnosis"><input className="input" value={f.diagnosis} onChange={(e) => setF({ ...f, diagnosis: e.target.value })} placeholder="Mastitis, tick infestation…" /></Field>
        <Field label="Treatment" required><input className="input" value={f.treatment} onChange={(e) => setF({ ...f, treatment: e.target.value })} /></Field>
        <Field label="Drug"><input className="input" value={f.drug} onChange={(e) => setF({ ...f, drug: e.target.value })} /></Field>
        <Field label="Dosage"><input className="input" value={f.dosage} onChange={(e) => setF({ ...f, dosage: e.target.value })} /></Field>
        <Field label="Date"><input type="date" className="input" value={f.treated_on} onChange={(e) => setF({ ...f, treated_on: e.target.value })} /></Field>
        <Field label="Outcome"><select className="input" value={f.outcome} onChange={(e) => setF({ ...f, outcome: e.target.value })}>{['under observation', 'improving', 'recovered', 'died'].map((o) => <option key={o}>{o}</option>)}</select></Field>
      </div>
    </Modal>
  )
}
