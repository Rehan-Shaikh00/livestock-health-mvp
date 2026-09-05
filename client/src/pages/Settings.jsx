import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save, Database, Cpu, Globe2, ShieldCheck } from 'lucide-react'
import { api, offline } from '../lib/api'
import { useAuth, ROLE_LABEL, TIER } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, Field, PageHeader } from '../components/ui'

export default function SettingsPage() {
  const { user, setUser, isDistrictPlus } = useAuth()
  const { t, setLang } = useI18n()
  const toast = useToast(); const qc = useQueryClient()
  const health = useQuery({ queryKey: ['health'], queryFn: () => api('/api/v1/health') })
  const audit = useQuery({ queryKey: ['audit'], queryFn: () => api('/api/v1/audit'), enabled: isDistrictPlus })
  const [f, setF] = useState({ full_name: user.full_name, phone: user.phone || '', language: user.language, password: '' })
  const m = useMutation({ mutationFn: () => api('/api/v1/auth/me', { method: 'PATCH', body: { ...f, password: f.password || undefined } }), onSuccess: (d) => { setUser(d.user); setLang(d.user.language); qc.invalidateQueries(); toast.success('Profile saved') }, onError: (e) => toast.error(e.message) })
  return (
    <div className="space-y-4">
      <PageHeader title={t('Settings')} subtitle="Profile, language preference and system status" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Profile">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Full name"><input className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
            <Field label="Phone" hint="Used to match IVR / WhatsApp reports to you"><input className="input" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
            <Field label="Preferred language" hint="Applies to advisories, SMS/IVR and the UI"><select className="input" value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}><option value="en">English</option><option value="mr">मराठी</option><option value="hi">हिंदी</option></select></Field>
            <Field label="New password"><input type="password" className="input" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} placeholder="••••" /></Field>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-slate-50 p-3 text-xs"><dt className="text-slate-500">Role</dt><dd>{ROLE_LABEL[user.role]} (tier {TIER[user.role]})</dd><dt className="text-slate-500">Scope</dt><dd className="font-mono">{[user.district_code && `D:${user.district_code}`, user.taluka_code && `T:${user.taluka_code}`, user.village_code && `V:${user.village_code}`].filter(Boolean).join(' ') || 'statewide'}</dd></dl>
          <button onClick={() => m.mutate()} className="btn-primary mt-4" disabled={m.isPending}>{m.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t('Save')}</button>
        </Card>
        <Card title="System status">
          <ul className="space-y-2 text-sm">
            <li className="flex items-center gap-2"><Database className="h-4 w-4 text-slate-400" />Persistence: SQLite (WAL) · <span className="text-slate-500">schema.sql = PostgreSQL + PostGIS production target</span></li>
            <li className="flex items-center gap-2"><Globe2 className="h-4 w-4 text-slate-400" />Spatial engine: <span className="font-mono text-xs">{health.data?.spatial_backend}</span></li>
            <li className="flex items-center gap-2"><Cpu className="h-4 w-4 text-slate-400" />ML model loaded: {health.data?.model ? 'yes (RandomForestRegressor)' : 'no'}</li>
            <li className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-slate-400" />Auth: PBKDF2 passwords · HS256 JWT · hierarchical scoping</li>
            <li className="text-xs text-slate-500">Server time {health.data?.time} · {health.data?.cases} cases total · offline queue {offline.read().length}</li>
          </ul>
        </Card>
      </div>
      {isDistrictPlus && <Card title="Audit log" subtitle="Last 100 mutating actions" padded={false}>
        <div className="max-h-96 overflow-y-auto"><table className="table"><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Entity</th><th>Detail</th></tr></thead><tbody>{(audit.data?.items || []).map((a) => <tr key={a.id}><td className="text-xs whitespace-nowrap text-slate-500">{a.created_at.replace('T', ' ').slice(0, 19)}</td><td className="text-xs">{a.actor_name}</td><td><span className="badge bg-slate-100">{a.action}</span></td><td className="text-xs">{a.entity} <span className="font-mono text-slate-400">{a.entity_id}</span></td><td className="font-mono text-[10px] text-slate-500">{a.detail}</td></tr>)}</tbody></table></div>
      </Card>}
    </div>
  )
}
