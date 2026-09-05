import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, UserX, Pencil, Loader2, Users } from 'lucide-react'
import clsx from 'clsx'
import { api, qs } from '../lib/api'
import { useAuth, ROLE_LABEL, TIER } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, ConfirmButton, EmptyState, Field, Modal, PageHeader, Pagination, TableSkeleton, fmtDate } from '../components/ui'

export default function UsersPage() {
  const { isDistrictPlus, user } = useAuth()
  const { meta } = useI18n()
  const toast = useToast(); const qc = useQueryClient()
  const [f, setF] = useState({ q: '', role: '', page: 1 })
  const [qText, setQ] = useState('')
  const [edit, setEdit] = useState(null)
  const q = useQuery({ queryKey: ['users', f], queryFn: () => api(`/api/v1/users${qs(f)}`), placeholderData: (p) => p })
  const deact = useMutation({ mutationFn: (id) => api(`/api/v1/users/${id}`, { method: 'DELETE' }), onSuccess: () => { toast.success('Account deactivated'); qc.invalidateQueries({ queryKey: ['users'] }) }, onError: (e) => toast.error(e.message) })
  return (
    <div className="space-y-4">
      <PageHeader title="Users & roles" subtitle="Hierarchical role-based access: village → taluka → district → state; lab staff scoped to their laboratory" actions={isDistrictPlus && <button onClick={() => setEdit({})} className="btn-primary"><Plus className="h-4 w-4" />New account</button>} />
      <Card padded={false}>
        <div className="flex flex-col gap-3 border-b border-slate-100 p-3 sm:flex-row">
          <form onSubmit={(e) => { e.preventDefault(); setF({ ...f, q: qText, page: 1 }) }} className="relative flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input className="input !pl-9" placeholder="Name, username, phone…" value={qText} onChange={(e) => setQ(e.target.value)} /></form>
          <select className="input !w-auto" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value, page: 1 })}><option value="">All roles</option>{Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </div>
        {q.isLoading ? <TableSkeleton /> : !q.data?.items?.length ? <EmptyState icon={Users} title="No users" /> : (
          <div className="overflow-x-auto"><table className="table"><thead><tr><th>User</th><th>Role</th><th>Tier</th><th>Jurisdiction (LGD)</th><th>Language</th><th>Created</th>{isDistrictPlus && <th />}</tr></thead>
            <tbody className={q.isFetching ? 'opacity-60' : ''}>{q.data.items.map((u) => <tr key={u.id} className={clsx(!u.active && 'opacity-50')}><td><div className="font-medium">{u.full_name}</div><div className="text-xs text-slate-500">@{u.username} · {u.phone}</div></td><td><span className="badge bg-forest-50 text-forest-800">{ROLE_LABEL[u.role]}</span>{!u.active && <span className="ml-1 badge bg-slate-200">inactive</span>}</td><td>{TIER[u.role]}</td><td className="font-mono text-xs text-slate-600">{[u.district_code && `D:${u.district_code}`, u.taluka_code && `T:${u.taluka_code}`, u.village_code && `V:${u.village_code}`, u.lab_id && 'LAB'].filter(Boolean).join(' · ') || 'Statewide'}</td><td className="uppercase text-xs">{u.language}</td><td className="text-xs text-slate-500">{fmtDate(u.created_at)}</td>{isDistrictPlus && <td className="whitespace-nowrap text-right"><button onClick={() => setEdit(u)} className="btn-ghost !p-1.5"><Pencil className="h-4 w-4" /></button>{u.active && u.id !== user.id && <ConfirmButton className="btn-ghost !p-1.5 !text-red-600" confirmLabel={`Deactivate ${u.full_name}?`} onConfirm={() => deact.mutate(u.id)}><UserX className="h-4 w-4" /></ConfirmButton>}</td>}</tr>)}</tbody></table></div>
        )}
        {q.data && <Pagination page={q.data.page} pages={q.data.pages} total={q.data.total} onPage={(p) => setF({ ...f, page: p })} />}
      </Card>
      {edit && <UserModal u={edit} onClose={() => setEdit(null)} />}
    </div>
  )
}

function UserModal({ u, onClose }) {
  const qc = useQueryClient(); const toast = useToast(); const { user } = useAuth()
  const gaz = useQuery({ queryKey: ['gazetteer'], queryFn: () => api('/api/v1/geo/gazetteer'), staleTime: Infinity })
  const labs = useQuery({ queryKey: ['labs'], queryFn: () => api('/api/v1/labs') })
  const [f, setF] = useState({ username: u.username || '', password: '', full_name: u.full_name || '', role: u.role || 'farmer', phone: u.phone || '', language: u.language || 'mr', district_code: u.district_code || user.district_code || '', taluka_code: u.taluka_code || '', village_code: u.village_code || '', lab_id: u.lab_id || '', active: u.active ?? 1 })
  const m = useMutation({ mutationFn: () => api(u.id ? `/api/v1/users/${u.id}` : '/api/v1/users', { method: u.id ? 'PATCH' : 'POST', body: { ...f, password: f.password || undefined, district_code: f.district_code || null, taluka_code: f.taluka_code || null, village_code: f.village_code || null, lab_id: f.lab_id || null } }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); toast.success(u.id ? 'Account updated' : 'Account created'); onClose() }, onError: (e) => toast.error(e.message) })
  const roles = Object.keys(ROLE_LABEL).filter((r) => user.role === 'state' || user.role === 'admin' || TIER[r] < 4)
  return (
    <Modal open onClose={onClose} title={u.id ? `Edit ${u.full_name}` : 'New account'} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!f.username || !f.full_name || (!u.id && !f.password) || m.isPending} onClick={() => m.mutate()}>{m.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Save</button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Full name" required><input className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Username" required><input className="input" value={f.username} disabled={!!u.id} onChange={(e) => setF({ ...f, username: e.target.value })} /></Field>
        <Field label={u.id ? 'New password (leave blank to keep)' : 'Password'} required={!u.id}><input type="password" className="input" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
        <Field label="Phone"><input className="input" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        <Field label="Role"><select className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{roles.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></Field>
        <Field label="Language"><select className="input" value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}><option value="en">English</option><option value="mr">मराठी</option><option value="hi">हिंदी</option></select></Field>
        <Field label="District"><select className="input" value={f.district_code} disabled={user.role !== 'state' && user.role !== 'admin'} onChange={(e) => setF({ ...f, district_code: e.target.value, taluka_code: '', village_code: '' })}><option value="">—</option>{gaz.data?.districts.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}</select></Field>
        <Field label="Taluka"><select className="input" value={f.taluka_code} onChange={(e) => setF({ ...f, taluka_code: e.target.value, village_code: '' })}><option value="">—</option>{gaz.data?.talukas.filter((t) => t.district_code === f.district_code).map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}</select></Field>
        <Field label="Village"><select className="input" value={f.village_code} onChange={(e) => setF({ ...f, village_code: e.target.value })}><option value="">—</option>{gaz.data?.villages.filter((v) => v.taluka_code === f.taluka_code).map((v) => <option key={v.code} value={v.code}>{v.name}</option>)}</select></Field>
        {f.role === 'lab' && <Field label="Laboratory"><select className="input" value={f.lab_id} onChange={(e) => setF({ ...f, lab_id: e.target.value })}><option value="">—</option>{labs.data?.items.map((l) => <option key={l.id} value={l.id}>{l.code}</option>)}</select></Field>}
        {u.id && <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-forest-700" checked={!!f.active} onChange={(e) => setF({ ...f, active: e.target.checked ? 1 : 0 })} />Active</label>}
      </div>
    </Modal>
  )
}
