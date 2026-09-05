import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { CloudSun, Droplets, Thermometer, UploadCloud, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, EmptyState, ErrorState, Field, Modal, PageHeader, Stat, timeAgo } from '../components/ui'

export default function Weather() {
  const { t } = useI18n()
  const { isDistrictPlus, is } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['weather'], queryFn: () => api('/api/v1/weather/latest') })
  const gaz = useQuery({ queryKey: ['gazetteer'], queryFn: () => api('/api/v1/geo/gazetteer'), staleTime: Infinity })
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ taluka_code: '', humidity: 86, temperature_c: 29, rainfall_mm: 12, wind_kmh: 8 })
  const etl = useMutation({ mutationFn: () => api('/api/v1/weather/etl', { method: 'POST', body: { observations: [{ ...f, district_code: gaz.data?.talukas.find((x) => x.code === f.taluka_code)?.district_code, source: 'MAHAVEDH-manual' }] } }), onSuccess: () => { toast.success('Telemetry ingested', 'Triage will use it for the next 72 h'); qc.invalidateQueries({ queryKey: ['weather'] }); qc.invalidateQueries({ queryKey: ['risk-map'] }); setOpen(false) }, onError: (e) => toast.error(e.message) })
  if (q.isError) return <ErrorState error={q.error} retry={q.refetch} />
  const items = q.data?.items || []
  const fav = items.filter((x) => x.vector_favourable)
  return (
    <div className="space-y-4">
      <PageHeader title={`MAHAVEDH ${t('Weather')}`} subtitle="Automatic weather station telemetry — Layer B of the triage engine (+15% vector-borne amplification when RH > 80% and 25–35 °C)" actions={(isDistrictPlus || is('ldo')) && <button onClick={() => setOpen(true)} className="btn-secondary"><UploadCloud className="h-4 w-4" />Ingest observation</button>} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat loading={q.isLoading} label="Stations reporting" value={items.length} icon={CloudSun} tone="info" />
        <Stat loading={q.isLoading} label="Vector-favourable talukas" value={fav.length} hint={fav.slice(0, 3).map((x) => x.taluka).join(', ')} icon={Droplets} tone={fav.length ? 'danger' : 'good'} />
        <Stat loading={q.isLoading} label="Mean humidity" value={items.length ? `${(items.reduce((s, x) => s + x.humidity, 0) / items.length).toFixed(0)}%` : '—'} icon={Droplets} />
        <Stat loading={q.isLoading} label="Mean temperature" value={items.length ? `${(items.reduce((s, x) => s + x.temperature_c, 0) / items.length).toFixed(1)}°C` : '—'} icon={Thermometer} tone="warn" />
      </div>
      <Card title="10-day statewide trend" subtitle="Daily mean across stations">
        {q.isLoading ? <div className="skeleton h-56" /> : (
          <ResponsiveContainer width="100%" height={220}><LineChart data={q.data.series.map((d) => ({ ...d, day: d.day.slice(5) }))} margin={{ left: -20, right: 10 }}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="day" tick={{ fontSize: 11 }} /><YAxis yAxisId="l" tick={{ fontSize: 11 }} /><YAxis yAxisId="r" orientation="right" tick={{ fontSize: 11 }} /><Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} /><Legend wrapperStyle={{ fontSize: 12 }} /><Line yAxisId="l" type="monotone" dataKey="humidity" name="Humidity %" stroke="#0ea5e9" strokeWidth={2} dot={false} /><Line yAxisId="r" type="monotone" dataKey="temperature_c" name="Temp °C" stroke="#f59e0b" strokeWidth={2} dot={false} /><Line yAxisId="r" type="monotone" dataKey="rainfall_mm" name="Rain mm" stroke="#2b6b32" strokeWidth={1.5} dot={false} strokeDasharray="4 3" /></LineChart></ResponsiveContainer>
        )}
      </Card>
      <Card title="Latest observation per taluka" padded={false}>
        {q.isLoading ? <div className="p-4 skeleton h-64" /> : !items.length ? <EmptyState title="No telemetry" /> : (
          <div className="overflow-x-auto"><table className="table"><thead><tr><th>Taluka</th><th>District</th><th className="text-right">RH %</th><th className="text-right">°C</th><th className="text-right">Rain mm</th><th className="text-right">Wind</th><th>Vector window</th><th>Observed</th></tr></thead>
            <tbody>{items.map((x) => <tr key={x.id} className={clsx(x.vector_favourable && 'bg-sky-50/40')}><td className="font-medium">{x.taluka}</td><td className="text-slate-500">{x.district}</td><td className="text-right tabular-nums">{x.humidity}</td><td className="text-right tabular-nums">{x.temperature_c}</td><td className="text-right tabular-nums">{x.rainfall_mm}</td><td className="text-right tabular-nums">{x.wind_kmh}</td><td>{x.vector_favourable ? <span className="badge bg-sky-100 text-sky-800">🦟 favourable · +15%</span> : <span className="text-xs text-slate-400">—</span>}</td><td className="text-xs text-slate-500">{timeAgo(x.observed_at)} · {x.source}</td></tr>)}</tbody></table></div>
        )}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Ingest MAHAVEDH observation" footer={<><button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn-primary" disabled={!f.taluka_code || etl.isPending} onClick={() => etl.mutate()}>{etl.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Ingest</button></>}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2"><Field label="Taluka" required><select className="input" value={f.taluka_code} onChange={(e) => setF({ ...f, taluka_code: e.target.value })}><option value="">Select…</option>{gaz.data?.talukas.map((x) => <option key={x.code} value={x.code}>{x.name}</option>)}</select></Field></div>
          <Field label="Humidity %"><input type="number" className="input" value={f.humidity} onChange={(e) => setF({ ...f, humidity: +e.target.value })} /></Field>
          <Field label="Temperature °C"><input type="number" className="input" value={f.temperature_c} onChange={(e) => setF({ ...f, temperature_c: +e.target.value })} /></Field>
          <Field label="Rainfall mm"><input type="number" className="input" value={f.rainfall_mm} onChange={(e) => setF({ ...f, rainfall_mm: +e.target.value })} /></Field>
          <Field label="Wind km/h"><input type="number" className="input" value={f.wind_kmh} onChange={(e) => setF({ ...f, wind_kmh: +e.target.value })} /></Field>
        </div>
        <p className="mt-3 text-xs text-slate-500">Production: scheduled ETL from the MAHAVEDH API posts to <span className="font-mono">/api/v1/weather/etl</span>. This form simulates one payload.</p>
      </Modal>
    </div>
  )
}
