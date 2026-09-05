import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Hospital, Pencil, Phone, Plus, Trash2, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, ConfirmButton, EmptyState, Field, Modal, PageHeader, TableSkeleton } from '../components/ui'

export default function VetCenters() {
  const { isDistrictPlus } = useAuth()
  const { t } = useI18n()
  const toast = useToast()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['vet-centers'], queryFn: () => api('/api/v1/vet-centers') })
  const [edit, setEdit] = useState(null)
  const del = useMutation({ mutationFn: (id) => api(`/api/v1/vet-centers/${id}`, { method: 'DELETE' }), onMutate: async (id) => { const prev = qc.getQueryData(['vet-centers']); qc.setQueryData(['vet-centers'], (d) => d && { items: d.items.filter((x) => x.id !== id) }); return { prev } }, onError: (e, _, ctx) => { qc.setQueryData(['vet-centers'], ctx.prev); toast.error(e.message) }, onSuccess: () => toast.success('Centre removed'), onSettled: () => qc.invalidateQueries({ queryKey: ['vet-centers'] }) })
  const items = q.data?.items || []
  const groups = items.reduce((m, x) => ((m[x.district] ||= []).push(x), m), {})
  return (
    <div className="space-y-4">
      <PageHeader title={t('Vet centres')} subtitle="Veterinary polyclinics, hospitals, dispensaries and aid centres — feeds nearest-clinic discovery" actions={isDistrictPlus && <button onClick={() => setEdit({})} className="btn-primary"><Plus className="h-4 w-4" />Add centre</button>} />
      {q.isLoading ? <Card padded={false}><TableSkeleton /></Card> : !items.length ? <Card><EmptyState icon={Hospital} title="No centres" /></Card> : Object.entries(groups).map(([d, list]) => (
        <Card key={d} title={`${d} district`} subtitle={`${list.length} centre${list.length > 1 ? 's' : ''}`} padded={false}>
          <table className="table"><thead><tr><th>Name</th><th>Type</th><th>Taluka</th><th>Officer</th><th>Coordinates</th>{isDistrictPlus && <th />}</tr></thead>
            <tbody>{list.map((x) => <tr key={x.id}><td className="font-medium">{x.name}</td><td><span className="badge bg-slate-100 capitalize">{x.type.replace('_', ' ')}</span></td><td>{x.taluka}</td><td>{x.officer_name}<div><a href={`tel:${x.officer_phone}`} className="flex items-center gap-1 text-xs text-forest-700"><Phone className="h-3 w-3" />{x.officer_phone}</a></div></td><td className="font-mono text-xs text-slate-500">{x.lat}, {x.lng}</td>{isDistrictPlus && <td className="whitespace-nowrap text-right"><button onClick={() => setEdit(x)} className="btn-ghost !p-1.5"><Pencil className="h-4 w-4" /></button><ConfirmButton className="btn-ghost !p-1.5 !text-red-600" confirmLabel="Remove this centre?" onConfirm={() => del.mutate(x.id)}><Trash2 className="h-4 w-4" /></ConfirmButton></td>}</tr>)}</tbody></table>
        </Card>
      ))}
      {edit && <CenterModal c={edit} onClose={() => setEdit(null)} />}
    </div>
  )
}

function CenterModal({ c, onClose }) {
  const qc = useQueryClient(); const toast = useToast()
  const gaz = useQuery({ queryKey: ['gazetteer'], queryFn: () => api('/api/v1/geo/gazetteer'), staleTime: Infinity })
  const [f, setF] = useState({ name: c.name || '', type: c.type || 'dispensary', district_code: c.district_code || '', taluka_code: c.taluka_code || '', lat: c.lat ?? '', lng: c.lng ?? '', officer_name: c.officer_name || '', officer_phone: c.officer_phone || '' })
  const m = useMutation({ mutationFn: () => api(c.id ? `/api/v1/vet-centers/${c.id}` : '/api/v1/vet-centers', { method: c.id ? 'PATCH' : 'POST', body: { ...f, lat: +f.lat, lng: +f.lng } }), onSuccess: () => { qc.invalidateQueries({ queryKey: ['vet-centers'] }); toast.success(c.id ? 'Centre updated' : 'Centre added'); onClose() }, onError: (e) => toast.error(e.message) })
  return (
    <Modal open onClose={onClose} title={c.id ? 'Edit centre' : 'Add veterinary centre'} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!f.name || f.lat === '' || m.isPending} onClick={() => m.mutate()}>{m.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Save</button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><Field label="Name" required><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field></div>
        <Field label="Type"><select className="input" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{['polyclinic', 'hospital', 'dispensary', 'aid_centre', 'mobile_unit'].map((x) => <option key={x} value={x}>{x.replace('_', ' ')}</option>)}</select></Field>
        <Field label="District"><select className="input" value={f.district_code} onChange={(e) => setF({ ...f, district_code: e.target.value, taluka_code: '' })}><option value="">—</option>{gaz.data?.districts.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}</select></Field>
        <Field label="Taluka"><select className="input" value={f.taluka_code} onChange={(e) => { const t = gaz.data?.talukas.find((x) => x.code === e.target.value); setF({ ...f, taluka_code: e.target.value, lat: f.lat || t?.lat || '', lng: f.lng || t?.lng || '' }) }}><option value="">—</option>{gaz.data?.talukas.filter((t) => t.district_code === f.district_code).map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}</select></Field>
        <div className="grid grid-cols-2 gap-2"><Field label="Lat" required><input type="number" step="0.0001" className="input" value={f.lat} onChange={(e) => setF({ ...f, lat: e.target.value })} /></Field><Field label="Lng" required><input type="number" step="0.0001" className="input" value={f.lng} onChange={(e) => setF({ ...f, lng: e.target.value })} /></Field></div>
        <Field label="Officer in charge"><input className="input" value={f.officer_name} onChange={(e) => setF({ ...f, officer_name: e.target.value })} /></Field>
        <Field label="Phone"><input className="input" value={f.officer_phone} onChange={(e) => setF({ ...f, officer_phone: e.target.value })} /></Field>
      </div>
    </Modal>
  )
}
