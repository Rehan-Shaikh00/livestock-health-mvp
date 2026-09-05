import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Syringe, CalendarClock, AlertCircle, PawPrint } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Card, EmptyState, ErrorState, PageHeader, Stat, fmtDate } from '../components/ui'

export default function Vaccination() {
  const { t, term } = useI18n()
  const q = useQuery({ queryKey: ['coverage'], queryFn: () => api('/api/v1/vaccinations/coverage') })
  if (q.isError) return <ErrorState error={q.error} retry={q.refetch} />
  const d = q.data
  const L = q.isLoading
  const overdue = d?.due?.filter((x) => new Date(x.next_due_on) < new Date()) || []
  const soon = d?.due?.filter((x) => new Date(x.next_due_on) >= new Date()) || []
  const chart = (d?.by_disease || []).map((x) => ({ ...x, name: term(x.disease) }))
  return (
    <div className="space-y-5">
      <PageHeader title={t('Vaccination')} subtitle="Coverage by disease within your jurisdiction · due & overdue schedule for micro-planning" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat loading={L} label="Animals in ledger" value={d?.total_animals} icon={PawPrint} tone="info" hint={d?.species?.map((s) => `${s.n} ${s.species}`).join(' · ')} />
        <Stat loading={L} label="Best coverage" value={d?.by_disease?.[0] ? `${d.by_disease[0].coverage_pct}%` : '—'} hint={d?.by_disease?.[0] ? term(d.by_disease[0].disease) : ''} icon={Syringe} tone="good" />
        <Stat loading={L} label="Due in 30 days" value={soon.length} icon={CalendarClock} tone="warn" />
        <Stat loading={L} label="Overdue" value={overdue.length} icon={AlertCircle} tone="danger" />
      </div>
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3" title="Coverage by disease" subtitle="% of ledger animals with at least one recorded dose">
          {L ? <div className="skeleton h-64" /> : !chart.length ? <EmptyState title="No vaccination records" /> : (
            <ResponsiveContainer width="100%" height={Math.max(220, chart.length * 38)}>
              <BarChart data={chart} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#eef2f7" />
                <XAxis type="number" domain={[0, 100] } tick={{ fontSize: 11 }} unit="%" /><YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} formatter={(v, n, p) => [`${v}% (${p.payload.covered} animals, ${p.payload.overdue} overdue)`, 'Coverage']} />
                <Bar dataKey="coverage_pct" radius={[0, 8, 8, 0]} label={{ position: 'right', fontSize: 11, formatter: (v) => `${v}%` }}>{chart.map((x) => <Cell key={x.disease} fill={x.coverage_pct >= 70 ? '#2b6b32' : x.coverage_pct >= 40 ? '#f59e0b' : '#dc2626'} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card className="lg:col-span-2" title="Due & overdue schedule" subtitle="±30 days · plan Pashu Sakhi visits" padded={false}>
          {L ? <div className="p-4 space-y-2">{[...Array(6)].map((_, i) => <div key={i} className="skeleton h-9" />)}</div> : !d.due.length ? <EmptyState icon={CalendarClock} title="Nothing due" detail="No boosters fall within the next 30 days." /> : (
            <ul className="max-h-[480px] divide-y divide-slate-100 overflow-y-auto">{d.due.map((x, i) => { const od = new Date(x.next_due_on) < new Date(); return (
              <li key={i}><Link to={`/animals/${x.ear_tag}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50">
                <span className={clsx('h-2 w-2 shrink-0 rounded-full', od ? 'bg-red-500' : 'bg-amber-400')} />
                <div className="min-w-0 flex-1"><div className="truncate text-sm"><span className="font-mono font-semibold">{x.ear_tag}</span> <span className="text-slate-500">· {x.species} · {x.owner_name}</span></div><div className="truncate text-xs text-slate-500">{x.vaccine} · {x.village}</div></div>
                <span className={clsx('text-xs whitespace-nowrap', od ? 'font-semibold text-red-700' : 'text-slate-600')}>{fmtDate(x.next_due_on)}</span>
              </Link></li>) })}</ul>
          )}
        </Card>
      </div>
    </div>
  )
}
