import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { Sparkles, Loader2, BrainCircuit } from 'lucide-react'
import clsx from 'clsx'
import { api, qs } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { Card, EmptyState, Field, PageHeader } from '../components/ui'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const RISK_W = { 'Very High Risk': 3, 'High Risk': 2, 'Medium Risk': 1 }

export default function Analytics() {
  const { user } = useAuth()
  const { term } = useI18n()
  const gaz = useQuery({ queryKey: ['gazetteer'], queryFn: () => api('/api/v1/geo/gazetteer'), staleTime: Infinity })
  const [district, setDistrict] = useState(gaz.data?.districts.find((d) => d.code === user.district_code)?.name || 'Pune')
  const hist = useQuery({ queryKey: ['history', district], queryFn: () => api(`/api/v1/analytics/history${qs({ district })}`) })
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api('/api/v1/analytics/summary') })
  const [inp, setInp] = useState({ outbreaks: 2, susceptible: 400, attacks: 30 })
  const pred = useMutation({ mutationFn: () => api('/api/v1/ml/predict', { method: 'POST', body: inp }) })
  const model = summary.data?.model || pred.data?.model
  const seasonal = hist.data?.seasonal_risk || []
  const byMonth = MONTHS.map((m) => ({ month: m.slice(0, 3), ...Object.fromEntries(seasonal.filter((s) => s.month === m).map((s) => [s.disease, RISK_W[s.predicted] || 0])) }))
  const diseases = [...new Set(seasonal.map((s) => s.disease))].slice(0, 6)
  const anthrax = hist.data?.anthrax_history || []
  const COLORS = ['#dc2626', '#f59e0b', '#2b6b32', '#0ea5e9', '#7c3aed', '#64748b']
  return (
    <div className="space-y-4">
      <PageHeader title="Analytics & ML" subtitle="Historical disease trends, seasonal risk calendar and the RandomForest mortality regressor" actions={<select className="input !w-auto" value={district} onChange={(e) => setDistrict(e.target.value)}>{(gaz.data?.districts || []).map((d) => <option key={d.code} value={d.name}>{d.name}</option>)}{['Amravati', 'Akola', 'Latur', 'Nagpur'].filter((x) => !gaz.data?.districts.some((d) => d.name === x)).map((x) => <option key={x}>{x}</option>)}</select>} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title={`Seasonal disease risk calendar — ${district}`} subtitle="NADRES-style monthly forecast (3 = very high, 2 = high, 1 = medium)">
          {hist.isLoading ? <div className="skeleton h-64" /> : !seasonal.length ? <EmptyState title="No seasonal data for this district" /> : (
            <ResponsiveContainer width="100%" height={260}><BarChart data={byMonth} margin={{ left: -20 }}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="month" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} allowDecimals={false} /><Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} /><Legend wrapperStyle={{ fontSize: 11 }} />{diseases.map((d, i) => <Bar key={d} dataKey={d} stackId="a" fill={COLORS[i]} radius={i === diseases.length - 1 ? [4, 4, 0, 0] : 0} />)}</BarChart></ResponsiveContainer>
          )}
        </Card>
        <Card title="RandomForest mortality regressor" subtitle="ml/livestock_risk_model.pkl" actions={<BrainCircuit className="h-4 w-4 text-saffron-500" />}>
          {model && <div className="mb-3 space-y-1 text-xs text-slate-600"><div><b>{model.algorithm}</b> · {model.n_estimators} trees</div><div>Features → {model.target}: {model.features?.join(', ')}</div><div className="mt-2 space-y-1">{Object.entries(model.feature_importances || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => <div key={k} className="flex items-center gap-2"><span className="w-20">{k}</span><div className="h-1.5 flex-1 rounded-full bg-slate-100"><div className="h-full rounded-full bg-forest-600" style={{ width: `${v * 100}%` }} /></div><span className="w-10 text-right tabular-nums">{(v * 100).toFixed(0)}%</span></div>)}</div></div>}
          <div className="grid grid-cols-3 gap-2">
            <Field label="Outbreaks"><input type="number" className="input" value={inp.outbreaks} onChange={(e) => setInp({ ...inp, outbreaks: +e.target.value })} /></Field>
            <Field label="Susceptible"><input type="number" className="input" value={inp.susceptible} onChange={(e) => setInp({ ...inp, susceptible: +e.target.value })} /></Field>
            <Field label="Attacks"><input type="number" className="input" value={inp.attacks} onChange={(e) => setInp({ ...inp, attacks: +e.target.value })} /></Field>
          </div>
          <button onClick={() => pred.mutate()} className="btn-primary mt-3 w-full" disabled={pred.isPending}>{pred.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}Predict</button>
          {pred.data && <div className={clsx('mt-3 rounded-xl p-3 text-center', pred.data.band === 'HIGH' ? 'bg-red-50 text-red-800' : pred.data.band === 'MEDIUM' ? 'bg-amber-50 text-amber-800' : 'bg-forest-50 text-forest-800')}><div className="text-3xl font-bold">{pred.data.predicted_deaths}</div><div className="text-xs">projected deaths · band {pred.data.band}</div></div>}
        </Card>
      </div>
      <Card title={`Anthrax outbreak history — ${district} (2020–2023)`} subtitle="Training data for the regressor" padded={false}>
        {!anthrax.length ? <EmptyState title="No historical records for this district" /> : <table className="table"><thead><tr><th>Year</th><th className="text-right">Outbreaks</th><th className="text-right">Susceptible</th><th className="text-right">Attacks</th><th className="text-right">Deaths</th><th className="text-right">CFR</th></tr></thead><tbody>{anthrax.map((r, i) => <tr key={i}><td>{r.Year}</td><td className="text-right">{r.Outbreaks}</td><td className="text-right">{r.Susceptible}</td><td className="text-right">{r.Attacks}</td><td className="text-right font-semibold text-red-700">{r.Deaths}</td><td className="text-right">{r.Attacks ? `${(100 * r.Deaths / r.Attacks).toFixed(0)}%` : '—'}</td></tr>)}</tbody></table>}
      </Card>
      {summary.data?.by_species?.length > 0 && <Card title="Species burden (30d, your scope)"><ResponsiveContainer width="100%" height={180}><BarChart data={summary.data.by_species} margin={{ left: -20 }}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="species" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} /><Legend wrapperStyle={{ fontSize: 11 }} /><Bar dataKey="n" name="Cases" fill="#2b6b32" radius={[4, 4, 0, 0]} /><Bar dataKey="deaths" name="Deaths" fill="#dc2626" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></Card>}
    </div>
  )
}
