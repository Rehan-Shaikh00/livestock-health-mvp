import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { AlertTriangle, Biohazard, ClipboardList, Clock, FlaskConical, PlusCircle, Skull, Syringe, TrendingDown, TrendingUp, Activity, PawPrint, BellRing, ArrowRight } from 'lucide-react'
import { api, qs } from '../lib/api'
import { useAuth, ROLE_LABEL } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { Card, EmptyState, ErrorState, PageHeader, RiskBadge, Stat, StatusBadge, timeAgo, CHANNEL_ICON, RISK_COLOR } from '../components/ui'
import { useEvents } from '../hooks/useEvents'

const CH_COLOR = { web: '#2b6b32', mobile: '#0ea5e9', whatsapp: '#22c55e', ivr: '#f59e0b' }

export default function Dashboard() {
  const { user, role, canReport, isClinical } = useAuth()
  const { t, term, statusLabel } = useI18n()
  const { events } = useEvents()
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api('/api/v1/analytics/summary') })
  const recent = useQuery({ queryKey: ['cases', 'recent'], queryFn: () => api(`/api/v1/cases${qs({ page_size: 8, open: 1 })}`) })
  const alerts = useQuery({ queryKey: ['alerts', 'dash'], queryFn: () => api(`/api/v1/alerts${qs({ page_size: 5 })}`) })

  if (summary.isError) return <ErrorState error={summary.error} retry={summary.refetch} />
  const k = summary.data?.kpis || {}
  const L = summary.isLoading
  const hour = new Date().getHours()
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const scopeLabel = { state: 'Statewide', district: `District ${user.district_code}`, taluka: `Taluka ${user.taluka_code}`, village: `Village ${user.village_code}`, lab: 'Your laboratory' }[summary.data?.scope] || ''

  const trend = (summary.data?.trend || []).map((d) => ({ ...d, day: d.day.slice(5) }))
  const levelData = ['HIGH', 'MEDIUM', 'LOW'].map((l) => ({ name: l, value: summary.data?.by_level?.[l] || 0 }))
  const channelData = Object.entries(summary.data?.by_channel || {}).map(([name, value]) => ({ name, value }))

  return (
    <div className="space-y-5">
      <PageHeader title={`${greet}, ${user.full_name.replace(/\s*\(.*\)$/, '')}`} subtitle={`${ROLE_LABEL[role]} · ${scopeLabel} · ${new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}`}
        actions={<>
          {canReport && <Link to="/report" className="btn-primary"><PlusCircle className="h-4 w-4" />{t('Report a case')}</Link>}
          {isClinical && <Link to="/map" className="btn-secondary">{t('Risk map')}</Link>}
        </>} />

      {(summary.data?.outbreaks?.length > 0) && (
        <div className="flex flex-col gap-2 rounded-2xl border border-red-200 bg-red-50 p-4 sm:flex-row sm:items-center">
          <Biohazard className="h-5 w-5 shrink-0 text-red-600" />
          <div className="flex-1 text-sm text-red-900">
            <span className="font-semibold">{summary.data.outbreaks.length} active outbreak signal{summary.data.outbreaks.length > 1 ? 's' : ''}:</span>{' '}
            {summary.data.outbreaks.slice(0, 3).map((o) => `${term(o.disease)} — ${o.taluka || o.taluka_code} (${o.case_count} cases, ${o.status})`).join(' · ')}
          </div>
          {isClinical && <Link to="/outbreaks" className="btn-danger !py-1.5 text-xs">Review <ArrowRight className="h-3.5 w-3.5" /></Link>}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat loading={L} label={t('Open cases')} value={k.open_cases} hint={k.delta7_pct != null ? `${k.delta7_pct > 0 ? '▲' : '▼'} ${Math.abs(k.delta7_pct)}% vs prev 7d` : `${k.last7 ?? 0} in last 7d`} icon={ClipboardList} tone="info" />
        <Stat loading={L} label={t('High risk')} value={k.high_open} hint={`${k.awaiting_inspection ?? 0} awaiting inspection`} icon={AlertTriangle} tone="danger" />
        <Stat loading={L} label={t('Deaths (30d)')} value={k.deaths30} hint={`${k.affected30 ?? 0} animals affected`} icon={Skull} tone="warn" />
        <Stat loading={L} label={t('Vaccination coverage')} value={k.coverage_pct != null ? `${k.coverage_pct}%` : '—'} hint={`${k.due_30d ?? 0} due in 30d · ${k.animals ?? 0} animals`} icon={Syringe} tone="good" />
        <Stat loading={L} label={t('Avg response')} value={k.avg_response_hours != null ? `${k.avg_response_hours}h` : '—'} hint={k.lab_tat_hours ? `Lab TAT ${k.lab_tat_hours}h` : 'report → inspection'} icon={Clock} />
        <Stat loading={L} label="Samples" value={(k.samples_in_transit ?? 0) + (k.samples_at_lab ?? 0)} hint={`${k.samples_at_lab ?? 0} at lab · ${k.lab_positives ?? 0} positives`} icon={FlaskConical} tone="info" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Case intake — last 30 days" subtitle="Reports per day with HIGH-triage share and mortality">
          {L ? <div className="skeleton h-56" /> : trend.length === 0 ? <EmptyState title="No reports in the last 30 days" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={trend} margin={{ left: -20, right: 6, top: 6 }}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2b6b32" stopOpacity={0.35} /><stop offset="100%" stopColor="#2b6b32" stopOpacity={0} /></linearGradient>
                  <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#dc2626" stopOpacity={0.35} /><stop offset="100%" stopColor="#dc2626" stopOpacity={0} /></linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="day" tick={{ fontSize: 11 }} interval="preserveStartEnd" /><YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                <Area type="monotone" dataKey="cases" name="Cases" stroke="#2b6b32" fill="url(#g1)" strokeWidth={2} />
                <Area type="monotone" dataKey="high" name="High risk" stroke="#dc2626" fill="url(#g2)" strokeWidth={2} />
                <Area type="monotone" dataKey="deaths" name="Deaths" stroke="#f59e0b" fill="none" strokeWidth={2} strokeDasharray="4 3" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Triage mix (30d)" subtitle="Dual-matrix engine output">
          {L ? <div className="skeleton h-56" /> : levelData.every((d) => !d.value) ? <EmptyState title="No triaged cases" /> : (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="55%" height={190}>
                <PieChart><Pie data={levelData} dataKey="value" innerRadius={48} outerRadius={78} paddingAngle={3} stroke="none">{levelData.map((d) => <Cell key={d.name} fill={RISK_COLOR[d.name]} />)}</Pie><Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} /></PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {levelData.map((d) => (
                  <div key={d.name} className="flex items-center justify-between text-sm"><span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: RISK_COLOR[d.name] }} />{term(d.name)}</span><span className="font-semibold">{d.value}</span></div>
                ))}
                <div className="pt-2 text-[11px] text-slate-500">Rules + MAHAVEDH + RF regression</div>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Recent open cases" subtitle="Live — updates as reports arrive" padded={false} actions={<Link to="/cases" className="text-xs font-medium text-forest-700 hover:underline">View all</Link>}>
          {recent.isLoading ? <div className="p-4 space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="skeleton h-10" />)}</div> : !recent.data?.items?.length ? (
            <EmptyState icon={ClipboardList} title="No open cases in your area" detail={canReport ? 'Submit the first report to see it triaged here in real time.' : 'New reports will appear here as they arrive.'} action={canReport && <Link to="/report" className="btn-primary">{t('Report a case')}</Link>} />
          ) : (
            <ul className="divide-y divide-slate-100">
              {recent.data.items.map((c) => (
                <li key={c.id}><Link to={`/cases/${c.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-forest-50/40">
                  <span className="text-lg" title={c.channel}>{CHANNEL_ICON[c.channel]}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2"><span className="truncate text-sm font-semibold text-slate-800">{term(c.suspected_disease)}</span><RiskBadge level={c.risk_level}>{term(c.risk_level)}</RiskBadge></div>
                    <div className="truncate text-xs text-slate-500">{c.village} · {c.species} · {c.affected_count} affected{c.mortality_count ? ` · ${c.mortality_count} dead` : ''} · {timeAgo(c.created_at)}</div>
                  </div>
                  <StatusBadge status={c.status} label={statusLabel(c.status)} />
                </Link></li>
              ))}
            </ul>
          )}
        </Card>
        <div className="space-y-4">
          <Card title={t('Alerts')} subtitle="Advisories for your area" padded={false} actions={<Link to="/alerts" className="text-xs font-medium text-forest-700 hover:underline">All</Link>}>
            {alerts.isLoading ? <div className="p-4 space-y-3">{[...Array(3)].map((_, i) => <div key={i} className="skeleton h-12" />)}</div> : !alerts.data?.items?.length ? <EmptyState icon={BellRing} title="No alerts" /> : (
              <ul className="divide-y divide-slate-100">
                {alerts.data.items.map((a) => (
                  <li key={a.id} className="px-5 py-3">
                    <div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${a.severity === 'critical' ? 'bg-red-500' : a.severity === 'warning' ? 'bg-amber-500' : 'bg-sky-500'}`} /><span className="truncate text-sm font-medium text-slate-800">{a.title}</span></div>
                    <div className="mt-0.5 line-clamp-2 text-xs text-slate-500">{a.message}</div>
                    <div className="mt-1 text-[11px] text-slate-400">{a.area} · {timeAgo(a.created_at)}</div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Live event stream" subtitle="Server-Sent Events" padded={false}>
            {events.length === 0 ? <div className="px-5 py-6 text-center text-xs text-slate-400"><Activity className="mx-auto mb-1 h-4 w-4" />Listening for events…</div> : (
              <ul className="max-h-48 divide-y divide-slate-100 overflow-y-auto">
                {events.slice(0, 8).map((e, i) => (
                  <li key={i} className="px-5 py-2 text-xs"><span className="font-mono text-[10px] text-slate-400">{e.ts?.slice(11, 19)}</span> <span className="font-semibold text-slate-700">{e.name}</span> <span className="text-slate-500">{e.data?.suspected_disease || e.data?.disease || e.data?.title || e.data?.status || ''}</span></li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="By channel (30d)" subtitle="Multi-channel data capture">
          {L ? <div className="skeleton h-40" /> : !channelData.length ? <EmptyState title="No data" /> : (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={channelData} layout="vertical" margin={{ left: 0, right: 16 }}>
                <XAxis type="number" hide /><YAxis type="category" dataKey="name" width={70} tick={{ fontSize: 12 }} />
                <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                <Bar dataKey="value" name="Reports" radius={[0, 8, 8, 0]}>{channelData.map((d) => <Cell key={d.name} fill={CH_COLOR[d.name] || '#64748b'} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Suspected diseases (30d)" padded={false}>
          {L ? <div className="p-4 skeleton h-40" /> : !summary.data?.by_disease?.length ? <EmptyState title="No data" /> : (
            <table className="table"><thead><tr><th>Disease</th><th className="text-right">Cases</th><th className="text-right">High</th><th className="text-right">Deaths</th></tr></thead>
              <tbody>{summary.data.by_disease.slice(0, 6).map((d) => <tr key={d.disease}><td className="font-medium">{term(d.disease)}</td><td className="text-right">{d.n}</td><td className="text-right text-red-700">{d.high}</td><td className="text-right">{d.deaths}</td></tr>)}</tbody></table>
          )}
        </Card>
        <Card title={`Hotspots by ${summary.data?.top_areas_level || 'area'} (30d)`} padded={false}>
          {L ? <div className="p-4 skeleton h-40" /> : !summary.data?.top_areas?.length ? <EmptyState title="No data" /> : (
            <table className="table"><thead><tr><th>Area</th><th className="text-right">Cases</th><th className="text-right">High</th><th className="text-right">Deaths</th></tr></thead>
              <tbody>{summary.data.top_areas.slice(0, 6).map((d) => <tr key={d.code}><td><div className="font-medium">{d.name}</div><div className="font-mono text-[10px] text-slate-400">LGD {d.code}</div></td><td className="text-right">{d.cases}</td><td className="text-right text-red-700">{d.high}</td><td className="text-right">{d.deaths}</td></tr>)}</tbody></table>
          )}
        </Card>
      </div>
    </div>
  )
}
