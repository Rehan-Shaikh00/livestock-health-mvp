import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Biohazard, Loader2, RefreshCw, ShieldAlert } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, EmptyState, ErrorState, Field, Modal, PageHeader, StatusBadge, fmtDateTime } from '../components/ui'

export default function Outbreaks() {
  const { isDistrictPlus, isClinical } = useAuth()
  const { t, term } = useI18n()
  const toast = useToast()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['outbreaks'], queryFn: () => api('/api/v1/outbreaks') })
  const [act, setAct] = useState(null)
  const inv = () => { qc.invalidateQueries({ queryKey: ['outbreaks'] }); qc.invalidateQueries({ queryKey: ['alerts'] }); qc.invalidateQueries({ queryKey: ['summary'] }); qc.invalidateQueries({ queryKey: ['risk-map'] }) }
  const detect = useMutation({ mutationFn: () => api('/api/v1/outbreaks/detect', { method: 'POST', body: {} }), onSuccess: (d) => { toast.info(`Detection run · ${d.created} new signal(s)`); inv() }, onError: (e) => toast.error(e.message) })
  const status = useMutation({ mutationFn: ({ id, ...b }) => api(`/api/v1/outbreaks/${id}/status`, { method: 'POST', body: b }), onSuccess: (d) => { toast.success(`Outbreak ${d.outbreak.status}`, d.outbreak.status === 'CONFIRMED' ? 'Multilingual advisories queued to SMS/WhatsApp/IVR' : ''); setAct(null); inv() }, onError: (e) => toast.error(e.message) })
  if (q.isError) return <ErrorState error={q.error} retry={q.refetch} />
  const items = q.data?.items || []
  return (
    <div className="space-y-4">
      <PageHeader title={t('Outbreaks')} subtitle="Spatio-temporal clusters: ≥3 same-disease reports in one taluka within 7 days (or ≥2 with a HIGH triage)"
        actions={isClinical && <button onClick={() => detect.mutate()} className="btn-secondary" disabled={detect.isPending}><RefreshCw className={clsx('h-4 w-4', detect.isPending && 'animate-spin')} />Run detection</button>} />
      {q.isLoading ? <div className="grid gap-3 md:grid-cols-2">{[...Array(4)].map((_, i) => <div key={i} className="skeleton h-40" />)}</div> : !items.length ? <Card><EmptyState icon={Biohazard} title="No outbreak signals" detail="The detector runs after every report, lab result and resolution." /></Card> : (
        <div className="grid gap-3 md:grid-cols-2">{items.map((o) => (
          <Card key={o.id} className={clsx(o.status === 'CONFIRMED' && 'border-red-300 ring-1 ring-red-200', o.status === 'SUSPECTED' && 'border-amber-300')}>
            <div className="flex items-start justify-between gap-3">
              <div><div className="flex items-center gap-2"><ShieldAlert className={clsx('h-5 w-5', o.status === 'CONFIRMED' ? 'text-red-600' : o.status === 'SUSPECTED' ? 'text-amber-600' : 'text-slate-400')} /><h3 className="text-base font-bold">{term(o.disease)}</h3><StatusBadge status={o.status} /></div>
                <div className="mt-1 text-sm text-slate-600">{o.taluka} taluka, {o.district} district · <span className="font-mono text-xs">LGD {o.taluka_code}</span></div></div>
              <div className="text-right"><div className="text-2xl font-bold">{o.case_count}</div><div className="text-[11px] text-slate-500">cases · {o.mortality} deaths</div></div>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600"><div>First reported<br /><b>{fmtDateTime(o.first_reported)}</b></div><div>Detected<br /><b>{fmtDateTime(o.detected_at)}</b></div>{o.confirmed_at && <div className="col-span-2">{o.status} by {o.confirmed_by_name} · {fmtDateTime(o.confirmed_at)}</div>}</div>
            {o.notes && <div className="mt-2 rounded-xl bg-slate-50 p-2 text-xs">{o.notes}</div>}
            <div className="mt-3 flex flex-wrap gap-1">{o.case_ids.slice(0, 8).map((id) => <Link key={id} to={`/cases/${id}`} className="rounded-lg bg-slate-100 px-2 py-0.5 font-mono text-[10px] hover:bg-forest-100">{id}</Link>)}{o.case_ids.length > 8 && <span className="text-[10px] text-slate-400">+{o.case_ids.length - 8}</span>}</div>
            {isDistrictPlus && ['SUSPECTED', 'CONFIRMED'].includes(o.status) && (
              <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                {o.status === 'SUSPECTED' && <button onClick={() => setAct({ o, status: 'CONFIRMED', radius_km: 5, notes: '' })} className="btn-danger !py-1.5 text-xs">Confirm & alert</button>}
                {o.status === 'SUSPECTED' && <button onClick={() => status.mutate({ id: o.id, status: 'DISMISSED', notes: 'Reviewed — not an outbreak' })} className="btn-secondary !py-1.5 text-xs">Dismiss</button>}
                {o.status === 'CONFIRMED' && <button onClick={() => status.mutate({ id: o.id, status: 'CONTAINED', notes: 'Containment measures complete' })} className="btn-primary !py-1.5 text-xs">Mark contained</button>}
              </div>
            )}
          </Card>
        ))}</div>
      )}
      <Modal open={!!act} onClose={() => setAct(null)} title={`Confirm ${term(act?.o?.disease)} outbreak`} footer={<><button className="btn-secondary" onClick={() => setAct(null)}>Cancel</button><button className="btn-danger" disabled={status.isPending} onClick={() => status.mutate({ id: act.o.id, status: 'CONFIRMED', radius_km: act.radius_km, notes: act.notes })}>{status.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Confirm & dispatch advisories</button></>}>
        {act && <div className="space-y-3">
          <Field label="Alert radius (km)"><input type="number" className="input" value={act.radius_km} onChange={(e) => setAct({ ...act, radius_km: +e.target.value })} /></Field>
          <Field label="Containment notes"><textarea className="input" rows={3} value={act.notes} onChange={(e) => setAct({ ...act, notes: e.target.value })} placeholder="Ring vaccination ordered, movement restrictions, market closure…" /></Field>
          <p className="text-xs text-slate-500">A critical advisory is generated in English, Marathi and Hindi and queued to app, SMS, WhatsApp and IVR for the affected taluka.</p>
        </div>}
      </Modal>
    </div>
  )
}
