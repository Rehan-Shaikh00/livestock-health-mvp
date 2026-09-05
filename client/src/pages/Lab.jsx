import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FlaskConical, ScanLine, ShieldCheck, ShieldX, Loader2, Printer, Search, X } from 'lucide-react'
import clsx from 'clsx'
import { api, qs } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, EmptyState, ErrorState, Field, Modal, PageHeader, Pagination, RiskBadge, Segmented, StatusBadge, TableSkeleton, fmtDateTime, timeAgo } from '../components/ui'

export default function Lab() {
  const { is } = useAuth()
  const { t, term } = useI18n()
  const toast = useToast()
  const qc = useQueryClient()
  const [sp, setSp] = useSearchParams()
  const f = Object.fromEntries(sp.entries())
  const setF = (k, v) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== 'page') n.delete('page'); setSp(n, { replace: true }) }
  const [q, setQ] = useState(f.q || '')
  const [scan, setScan] = useState('')
  const [scanRes, setScanRes] = useState(null)
  const [resultFor, setResultFor] = useState(null)
  const list = useQuery({ queryKey: ['referrals', f], queryFn: () => api(`/api/v1/lab-referrals${qs({ ...f, page_size: 20 })}`), placeholderData: (p) => p })
  const labs = useQuery({ queryKey: ['labs'], queryFn: () => api('/api/v1/labs') })
  const inv = () => { qc.invalidateQueries({ queryKey: ['referrals'] }); qc.invalidateQueries({ queryKey: ['cases'] }); qc.invalidateQueries({ queryKey: ['summary'] }); qc.invalidateQueries({ queryKey: ['labs'] }) }
  const verify = useMutation({ mutationFn: () => api('/api/v1/lab-referrals/verify', { method: 'POST', body: { scan } }), onSuccess: setScanRes, onError: (e) => toast.error(e.message) })
  const advance = useMutation({ mutationFn: (id) => api(`/api/v1/lab-referrals/${id}/advance`, { method: 'POST', body: {} }), onSuccess: () => { toast.success('Chain of custody updated'); inv() }, onError: (e) => toast.error(e.message) })
  const isLab = is('lab', 'state', 'admin')

  return (
    <div className="space-y-5">
      <PageHeader title={t('Laboratory')} subtitle="Sample referrals, chain of custody and results · DIS Pune & regional DDLs" />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Verify barcode" subtitle="Scan or paste a Code-128 label — the HMAC suffix proves it was issued by this system">
          <form onSubmit={(e) => { e.preventDefault(); verify.mutate() }} className="flex gap-2">
            <div className="relative flex-1"><ScanLine className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input className="input !pl-9 font-mono" value={scan} onChange={(e) => setScan(e.target.value)} placeholder="MH-521-260905-A3F9C1-7B2E91AC" /></div>
            <button className="btn-primary" disabled={!scan || verify.isPending}>{verify.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Verify'}</button>
          </form>
          {scanRes && (
            <div className={clsx('mt-3 flex items-start gap-3 rounded-xl border p-3 text-sm', scanRes.valid ? 'border-forest-200 bg-forest-50 text-forest-900' : 'border-red-200 bg-red-50 text-red-800')}>
              {scanRes.valid ? <ShieldCheck className="h-5 w-5 shrink-0" /> : <ShieldX className="h-5 w-5 shrink-0" />}
              <div>
                <div className="font-semibold">{scanRes.valid ? 'Authentic sample label' : scanRes.known ? 'Signature mismatch — possible tampering' : scanRes.signature_ok ? 'Signature valid but sample unknown' : 'Invalid barcode'}</div>
                {scanRes.referral && <div className="text-xs">Case <Link className="font-mono underline" to={`/cases/${scanRes.referral.case_id}`}>{scanRes.referral.case_id}</Link> · {scanRes.referral.sample_type} · {term(scanRes.referral.suspected_disease)} · status {scanRes.referral.status}</div>}
              </div>
            </div>
          )}
        </Card>
        <Card title="Laboratories" padded={false}>
          <ul className="divide-y divide-slate-100">{labs.data?.items.map((l) => <li key={l.id} className="flex items-center gap-3 px-4 py-2.5 text-sm"><FlaskConical className={clsx('h-4 w-4', l.tier === 'state' ? 'text-saffron-500' : 'text-slate-400')} /><div className="min-w-0 flex-1"><div className="truncate font-medium">{l.code}</div><div className="truncate text-xs text-slate-500">{l.capabilities}</div></div><span className={clsx('badge', l.pending ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-500')}>{l.pending} pending</span></li>)}</ul>
        </Card>
      </div>

      <Card padded={false}>
        <div className="flex flex-col gap-3 border-b border-slate-100 p-3 sm:flex-row sm:items-center">
          <form onSubmit={(e) => { e.preventDefault(); setF('q', q) }} className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input className="input !pl-9" placeholder="Barcode or case id…" value={q} onChange={(e) => setQ(e.target.value)} /></form>
          <Segmented value={f.status || ''} onChange={(v) => setF('status', v)} options={[{ value: '', label: 'All' }, { value: 'COLLECTED', label: 'Collected' }, { value: 'IN_TRANSIT', label: 'In transit' }, { value: 'RECEIVED', label: 'At lab' }, { value: 'RESULTED', label: 'Resulted' }]} />
          <select className="input !w-auto" value={f.priority || ''} onChange={(e) => setF('priority', e.target.value)}><option value="">Priority: all</option><option value="urgent">Urgent</option><option value="routine">Routine</option></select>
          {(f.q || f.status || f.priority) && <button onClick={() => { setQ(''); setSp({}, { replace: true }) }} className="btn-ghost text-xs"><X className="h-3.5 w-3.5" />Clear</button>}
        </div>
        {list.isLoading ? <TableSkeleton rows={8} cols={7} /> : list.isError ? <div className="p-4"><ErrorState error={list.error} retry={list.refetch} /></div> : !list.data.items.length ? <EmptyState icon={FlaskConical} title="No sample referrals" detail="Samples collected in the field appear here with their custody chain." /> : (
          <div className="overflow-x-auto"><table className="table">
            <thead><tr><th>Barcode</th><th>Case</th><th>Sample</th><th>Lab</th><th>Status</th><th>Result</th><th>Collected</th><th /></tr></thead>
            <tbody className={list.isFetching ? 'opacity-60' : ''}>{list.data.items.map((r) => (
              <tr key={r.id}>
                <td><div className="flex items-center gap-2"><img src={`/api/v1/lab-referrals/${r.id}/barcode.svg`} alt="" className="h-8 rounded border border-slate-200" /><div><div className="font-mono text-xs font-semibold">{r.barcode}</div><div className="text-[10px] text-slate-400">✓ {r.signature}{r.priority === 'urgent' && <span className="ml-1 badge bg-red-100 text-red-700">URGENT</span>}</div></div></div></td>
                <td><Link to={`/cases/${r.case_id}`} className="font-mono text-xs text-forest-800 hover:underline">{r.case_id}</Link><div className="text-xs text-slate-500">{term(r.suspected_disease)} · {r.village}</div></td>
                <td className="text-xs">{r.sample_type}<div className="text-slate-400">{r.test_requested}</div></td>
                <td className="text-xs">{r.lab_code}</td>
                <td><StatusBadge status={r.status} />{!r.cold_chain_ok && <div className="text-[10px] text-red-600">cold-chain break</div>}</td>
                <td>{r.result ? <span className={clsx('badge', r.result === 'POSITIVE' ? 'bg-red-600 text-white' : r.result === 'NEGATIVE' ? 'bg-slate-700 text-white' : 'bg-amber-100 text-amber-800')}>{r.result}{r.pathogen ? ` · ${term(r.pathogen)}` : ''}</span> : <span className="text-xs text-slate-400">pending</span>}</td>
                <td className="text-xs text-slate-500 whitespace-nowrap">{timeAgo(r.collected_at)}<div>{r.collected_by_name}</div></td>
                <td className="whitespace-nowrap">
                  <a href={`/api/v1/lab-referrals/${r.id}/barcode.svg`} target="_blank" rel="noreferrer" className="btn-ghost !p-1.5" title="Print label"><Printer className="h-4 w-4" /></a>
                  {r.status === 'COLLECTED' && !is('lab') && <button onClick={() => advance.mutate(r.id)} className="btn-secondary !py-1 text-xs">Dispatch</button>}
                  {r.status === 'IN_TRANSIT' && isLab && <button onClick={() => advance.mutate(r.id)} className="btn-secondary !py-1 text-xs">Receive</button>}
                  {r.status === 'RECEIVED' && isLab && <button onClick={() => setResultFor(r)} className="btn-primary !py-1 text-xs">Enter result</button>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        {list.data && <Pagination page={list.data.page} pages={list.data.pages} total={list.data.total} onPage={(p) => setF('page', String(p))} />}
      </Card>
      <ResultModal r={resultFor} onClose={() => setResultFor(null)} onDone={inv} />
    </div>
  )
}

function ResultModal({ r, onClose, onDone }) {
  const toast = useToast()
  const { term, meta } = useI18n()
  const [f, setF] = useState({ result: 'POSITIVE', pathogen: '', notes: '' })
  const m = useMutation({ mutationFn: () => api(`/api/v1/lab-referrals/${r.id}/result`, { method: 'POST', body: { ...f, pathogen: f.pathogen || undefined } }), onSuccess: (d) => { toast[d.referral.result === 'POSITIVE' ? 'error' : 'success'](`Result released: ${d.referral.result}`, d.referral.result === 'POSITIVE' ? 'Case escalated · advisories dispatched' : 'Case updated'); onDone(); onClose() }, onError: (e) => toast.error(e.message) })
  if (!r) return null
  const diseases = Object.values(meta?.diseases?.en || {}).filter((x) => !x.startsWith('No specific'))
  return (
    <Modal open onClose={onClose} title={`Record result · ${r.barcode}`} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className={f.result === 'POSITIVE' ? 'btn-danger' : 'btn-primary'} disabled={m.isPending} onClick={() => m.mutate()}>{m.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Release result</button></>}>
      <div className="mb-3 rounded-xl bg-slate-50 p-3 text-xs text-slate-600">Case <span className="font-mono">{r.case_id}</span> · suspected {term(r.suspected_disease)} · {r.sample_type} · {r.test_requested}</div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Result" required><select className="input" value={f.result} onChange={(e) => setF({ ...f, result: e.target.value })}><option>POSITIVE</option><option>NEGATIVE</option><option>INCONCLUSIVE</option></select></Field>
        <Field label="Pathogen confirmed" hint="Defaults to suspected disease when positive"><input list="dz" className="input" value={f.pathogen} onChange={(e) => setF({ ...f, pathogen: e.target.value })} placeholder={r.suspected_disease} /><datalist id="dz">{diseases.map((d) => <option key={d} value={d} />)}</datalist></Field>
      </div>
      <div className="mt-3"><Field label="Notes"><textarea className="input" rows={3} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} placeholder="Ct value, titre, morphology…" /></Field></div>
      {f.result === 'POSITIVE' && <p className="mt-3 text-xs text-red-700">A positive result advances the case to PATHOGEN_CONFIRMED, raises a critical multilingual alert for the village and re-runs cluster detection.</p>}
    </Modal>
  )
}
