import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PawPrint, Plus, Search, Loader2, X } from 'lucide-react'
import { api, qs } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, EmptyState, ErrorState, Field, Modal, PageHeader, Pagination, TableSkeleton, fmtDate } from '../components/ui'

const SPECIES_ICON = { cattle: '🐄', buffalo: '🐃', goat: '🐐', sheep: '🐑', poultry: '🐔', pig: '🐖' }
const BREEDS = { cattle: ['Gir', 'Khillar', 'Deoni', 'Dangi', 'Holstein-Friesian cross', 'Jersey cross', 'Red Kandhari', 'Non-descript'], buffalo: ['Murrah', 'Pandharpuri', 'Nagpuri', 'Mehsana', 'Non-descript'], goat: ['Osmanabadi', 'Sangamneri', 'Berari', 'Konkan Kanyal', 'Non-descript'], sheep: ['Deccani', 'Madgyal', 'Non-descript'], poultry: ['Giriraja', 'Vanaraja', 'Kadaknath', 'Broiler'], pig: ['Large White Yorkshire', 'Desi'] }

export default function Animals() {
  const { t, meta } = useI18n()
  const { user } = useAuth()
  const [sp, setSp] = useSearchParams()
  const f = Object.fromEntries(sp.entries())
  const setF = (k, v) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== 'page') n.delete('page'); setSp(n, { replace: true }) }
  const [q, setQ] = useState(f.q || '')
  const [open, setOpen] = useState(false)
  const query = useQuery({ queryKey: ['animals', f], queryFn: () => api(`/api/v1/animals${qs({ ...f, page_size: 20 })}`), placeholderData: (p) => p })

  return (
    <div className="space-y-4">
      <PageHeader title={t('Animals')} subtitle="Bharat Pashudhan EHR ledger · 12-digit ear-tag identity, vaccination & treatment history" actions={<button onClick={() => setOpen(true)} className="btn-primary"><Plus className="h-4 w-4" />{t('Register animal')}</button>} />
      <Card padded={false}>
        <div className="flex flex-col gap-3 border-b border-slate-100 p-3 sm:flex-row sm:items-center">
          <form onSubmit={(e) => { e.preventDefault(); setF('q', q) }} className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input className="input !pl-9" placeholder="Ear tag, owner, breed…" value={q} onChange={(e) => setQ(e.target.value)} /></form>
          <select className="input !w-auto" value={f.species || ''} onChange={(e) => setF('species', e.target.value)}><option value="">{t('Species')}: {t('All')}</option>{(meta?.species || []).map((s) => <option key={s} value={s}>{s}</option>)}</select>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-forest-700" checked={f.due === '1'} onChange={(e) => setF('due', e.target.checked ? '1' : '')} />Vaccination due ≤30d</label>
          {(f.q || f.species || f.due) && <button onClick={() => { setQ(''); setSp({}, { replace: true }) }} className="btn-ghost text-xs"><X className="h-3.5 w-3.5" />Clear</button>}
        </div>
        {query.isLoading ? <TableSkeleton rows={8} cols={6} /> : query.isError ? <div className="p-4"><ErrorState error={query.error} retry={query.refetch} /></div> : !query.data.items.length ? (
          <EmptyState icon={PawPrint} title="No animals registered" detail="Register an animal with its 12-digit Bharat Pashudhan ear tag to start its health record." action={<button onClick={() => setOpen(true)} className="btn-primary">{t('Register animal')}</button>} />
        ) : (
          <div className="overflow-x-auto"><table className="table">
            <thead><tr><th>{t('Ear tag')}</th><th>{t('Species')} / {t('Breed')}</th><th>{t('Owner')}</th><th>{t('Village')}</th><th>Last vaccinated</th><th>Next due</th><th className="text-right">{t('Treatments')}</th></tr></thead>
            <tbody className={query.isFetching ? 'opacity-60' : ''}>{query.data.items.map((a) => (
              <tr key={a.id}>
                <td><Link to={`/animals/${a.ear_tag}`} className="font-mono text-sm font-semibold text-forest-800 hover:underline">{a.ear_tag}</Link>{a.status !== 'active' && <span className="ml-2 badge bg-slate-200 text-slate-600">{a.status}</span>}</td>
                <td><span className="mr-1">{SPECIES_ICON[a.species]}</span><span className="capitalize">{a.species}</span><div className="text-xs text-slate-500">{a.breed} · {a.sex} · b.{a.birth_year}</div></td>
                <td>{a.owner_name}<div className="text-xs text-slate-400">{a.owner_phone}</div></td>
                <td>{a.village}<div className="font-mono text-[10px] text-slate-400">{a.village_code}</div></td>
                <td className="text-xs">{fmtDate(a.last_vaccinated)}</td>
                <td className="text-xs">{a.next_due ? <span className={new Date(a.next_due) < new Date(Date.now() + 30 * 864e5) ? 'font-semibold text-amber-700' : ''}>{fmtDate(a.next_due)}</span> : '—'}</td>
                <td className="text-right">{a.treatment_count}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        {query.data && <Pagination page={query.data.page} pages={query.data.pages} total={query.data.total} onPage={(p) => setF('page', String(p))} />}
      </Card>
      <RegisterModal open={open} onClose={() => setOpen(false)} user={user} />
    </div>
  )
}

export function RegisterModal({ open, onClose, user, initial, onSaved }) {
  const qc = useQueryClient()
  const toast = useToast()
  const { meta } = useI18n()
  const gaz = useQuery({ queryKey: ['gazetteer'], queryFn: () => api('/api/v1/geo/gazetteer'), staleTime: Infinity })
  const [f, setF] = useState(initial || { ear_tag: '', species: 'cattle', breed: 'Gir', sex: 'female', birth_year: new Date().getFullYear() - 3, color: '', owner_name: user?.role === 'farmer' ? user.full_name : '', owner_phone: user?.role === 'farmer' ? user.phone || '' : '', village_code: user?.village_code || '', notes: '' })
  const edit = !!initial?.id
  const m = useMutation({
    mutationFn: () => api(edit ? `/api/v1/animals/${initial.id}` : '/api/v1/animals', { method: edit ? 'PATCH' : 'POST', body: f }),
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ['animals'] }); toast.success(edit ? 'Animal updated' : 'Animal registered', d.animal.ear_tag); onSaved?.(d.animal); onClose() },
    onError: (e) => toast.error('Could not save', e.message),
  })
  const tagOk = /^\d{12}$/.test(f.ear_tag)
  return (
    <Modal open={open} onClose={onClose} title={edit ? 'Edit animal' : 'Register animal (Bharat Pashudhan)'} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!tagOk || m.isPending} onClick={() => m.mutate()}>{m.isPending && <Loader2 className="h-4 w-4 animate-spin" />}{edit ? 'Save' : 'Register'}</button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Ear tag (12 digits)" required error={f.ear_tag && !tagOk ? 'Must be exactly 12 numeric digits' : null} hint="INAPH / Bharat Pashudhan ear-tag number"><input className="input font-mono tracking-wider" maxLength={12} value={f.ear_tag} onChange={(e) => setF({ ...f, ear_tag: e.target.value.replace(/\D/g, '') })} placeholder="270000000123" /></Field>
        <Field label="Species" required><select className="input" value={f.species} onChange={(e) => setF({ ...f, species: e.target.value, breed: BREEDS[e.target.value]?.[0] || '' })}>{(meta?.species || Object.keys(BREEDS)).map((s) => <option key={s} value={s}>{s}</option>)}</select></Field>
        <Field label="Breed"><select className="input" value={f.breed} onChange={(e) => setF({ ...f, breed: e.target.value })}>{(BREEDS[f.species] || []).map((b) => <option key={b}>{b}</option>)}</select></Field>
        <Field label="Sex"><select className="input" value={f.sex} onChange={(e) => setF({ ...f, sex: e.target.value })}><option value="female">Female</option><option value="male">Male</option></select></Field>
        <Field label="Birth year"><input type="number" className="input" value={f.birth_year} onChange={(e) => setF({ ...f, birth_year: +e.target.value })} /></Field>
        <Field label="Colour / markings"><input className="input" value={f.color} onChange={(e) => setF({ ...f, color: e.target.value })} /></Field>
        <Field label="Owner name"><input className="input" value={f.owner_name} onChange={(e) => setF({ ...f, owner_name: e.target.value })} /></Field>
        <Field label="Owner phone"><input className="input" value={f.owner_phone} onChange={(e) => setF({ ...f, owner_phone: e.target.value })} /></Field>
        <Field label="Village (LGD)" required><select className="input" value={f.village_code} onChange={(e) => setF({ ...f, village_code: e.target.value })}><option value="">Select…</option>{gaz.data?.villages.map((v) => <option key={v.code} value={v.code}>{v.name} ({v.code})</option>)}</select></Field>
        {edit && <Field label="Status"><select className="input" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>{['active', 'sold', 'died', 'culled'].map((s) => <option key={s}>{s}</option>)}</select></Field>}
      </div>
      <div className="mt-3"><Field label="Notes"><input className="input" value={f.notes || ''} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field></div>
    </Modal>
  )
}
