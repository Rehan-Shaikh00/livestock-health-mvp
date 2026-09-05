import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ClipboardList, Filter, PlusCircle, Search, X } from 'lucide-react'
import { api, qs } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { Card, EmptyState, ErrorState, PageHeader, Pagination, RiskBadge, StatusBadge, TableSkeleton, timeAgo, CHANNEL_ICON, Segmented } from '../components/ui'

export default function Cases() {
  const { canReport } = useAuth()
  const { t, term, statusLabel, meta } = useI18n()
  const [sp, setSp] = useSearchParams()
  const f = Object.fromEntries(sp.entries())
  const setF = (k, v) => { const n = new URLSearchParams(sp); if (v) n.set(k, v); else n.delete(k); if (k !== 'page') n.delete('page'); setSp(n, { replace: true }) }
  const [q, setQ] = useState(f.q || '')
  const query = useQuery({ queryKey: ['cases', f], queryFn: () => api(`/api/v1/cases${qs({ ...f, page_size: 20 })}`), placeholderData: (p) => p })
  const active = Object.keys(f).filter((k) => !['page', 'open'].includes(k)).length

  return (
    <div className="space-y-4">
      <PageHeader title={t('Cases')} subtitle="All symptom & mortality reports visible in your jurisdiction" actions={canReport && <Link to="/report" className="btn-primary"><PlusCircle className="h-4 w-4" />{t('Report a case')}</Link>} />
      <Card padded={false}>
        <div className="flex flex-col gap-3 border-b border-slate-100 p-3 sm:flex-row sm:items-center">
          <form onSubmit={(e) => { e.preventDefault(); setF('q', q) }} className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input className="input !pl-9" placeholder={`${t('Search')} case id, reporter, disease, village code…`} value={q} onChange={(e) => setQ(e.target.value)} />
          </form>
          <Segmented value={f.open || ''} onChange={(v) => setF('open', v)} options={[{ value: '', label: t('All') }, { value: '1', label: 'Open' }]} />
          <select className="input !w-auto" value={f.risk_level || ''} onChange={(e) => setF('risk_level', e.target.value)}><option value="">{t('Risk')}: {t('All')}</option>{['HIGH', 'MEDIUM', 'LOW'].map((l) => <option key={l} value={l}>{term(l)}</option>)}</select>
          <select className="input !w-auto" value={f.status || ''} onChange={(e) => setF('status', e.target.value)}><option value="">{t('Status')}: {t('All')}</option>{(meta?.statuses || []).map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}</select>
          <select className="input !w-auto" value={f.channel || ''} onChange={(e) => setF('channel', e.target.value)}><option value="">{t('Channel')}: {t('All')}</option>{(meta?.channels || []).map((s) => <option key={s} value={s}>{s}</option>)}</select>
          <select className="input !w-auto" value={f.species || ''} onChange={(e) => setF('species', e.target.value)}><option value="">{t('Species')}: {t('All')}</option>{(meta?.species || []).map((s) => <option key={s} value={s}>{s}</option>)}</select>
          {active > 0 && <button onClick={() => { setQ(''); setSp({}, { replace: true }) }} className="btn-ghost text-xs"><X className="h-3.5 w-3.5" />Clear</button>}
        </div>
        {query.isLoading ? <TableSkeleton rows={8} cols={7} /> : query.isError ? <div className="p-4"><ErrorState error={query.error} retry={query.refetch} /></div> : !query.data.items.length ? (
          <EmptyState icon={active ? Filter : ClipboardList} title={active ? 'No cases match these filters' : 'No cases yet'} detail={active ? 'Try widening the filters.' : 'Reports from web, mobile sync, IVR and WhatsApp will appear here.'} action={active ? <button onClick={() => setSp({}, { replace: true })} className="btn-secondary">Clear filters</button> : canReport && <Link to="/report" className="btn-primary">{t('Report a case')}</Link>} />
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead><tr><th>Case</th><th>{t('Suspected disease')}</th><th>{t('Risk')}</th><th>{t('Species')}</th><th className="text-right">{t('Affected')}/{t('Dead')}</th><th>{t('Village')}</th><th>{t('Status')}</th><th>{t('Reported')}</th></tr></thead>
              <tbody className={query.isFetching ? 'opacity-60' : ''}>
                {query.data.items.map((c) => (
                  <tr key={c.id}>
                    <td><Link to={`/cases/${c.id}`} className="font-mono text-xs font-semibold text-forest-800 hover:underline">{c.id}</Link><div className="text-[11px] text-slate-400">{CHANNEL_ICON[c.channel]} {c.channel} · {c.reporter_name}</div></td>
                    <td className="font-medium">{term(c.suspected_disease)}<div className="max-w-[220px] truncate text-[11px] text-slate-400">{(c.symptoms || []).map(term).join(', ')}</div></td>
                    <td><RiskBadge level={c.risk_level}>{term(c.risk_level)} {c.risk_score}</RiskBadge></td>
                    <td className="capitalize">{c.species}</td>
                    <td className="text-right tabular-nums">{c.affected_count} / <span className={c.mortality_count ? 'font-semibold text-red-700' : ''}>{c.mortality_count}</span></td>
                    <td>{c.village}<div className="text-[11px] text-slate-400">{c.taluka}, {c.district}</div></td>
                    <td><StatusBadge status={c.status} label={statusLabel(c.status)} /></td>
                    <td className="whitespace-nowrap text-xs text-slate-500">{timeAgo(c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {query.data && <Pagination page={query.data.page} pages={query.data.pages} total={query.data.total} onPage={(p) => setF('page', String(p))} />}
      </Card>
    </div>
  )
}
