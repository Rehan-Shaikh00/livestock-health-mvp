import { useEffect } from 'react'
import { X, Inbox, ChevronLeft, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import { formatDistanceToNowStrict, parseISO, format } from 'date-fns'

export const RISK_STYLE = {
  HIGH: 'bg-red-100 text-red-700 ring-1 ring-red-200', MEDIUM: 'bg-amber-100 text-amber-800 ring-1 ring-amber-200', LOW: 'bg-forest-100 text-forest-800 ring-1 ring-forest-200',
}
export const RISK_COLOR = { HIGH: '#dc2626', MEDIUM: '#d97706', LOW: '#2b6b32' }
export const STATUS_STYLE = {
  REPORTED: 'bg-slate-100 text-slate-700', FIELD_INSPECTED_BY_LDO: 'bg-sky-100 text-sky-800', SAMPLE_COLLECTED: 'bg-violet-100 text-violet-800',
  LAB_TRANSIT: 'bg-indigo-100 text-indigo-800', LAB_RECEIVED: 'bg-fuchsia-100 text-fuchsia-800', PATHOGEN_CONFIRMED: 'bg-red-100 text-red-800',
  PATHOGEN_REJECTED: 'bg-slate-200 text-slate-700', CASE_RESOLVED: 'bg-forest-100 text-forest-800',
  COLLECTED: 'bg-violet-100 text-violet-800', IN_TRANSIT: 'bg-indigo-100 text-indigo-800', RECEIVED: 'bg-fuchsia-100 text-fuchsia-800', RESULTED: 'bg-forest-100 text-forest-800',
  SUSPECTED: 'bg-amber-100 text-amber-800', CONFIRMED: 'bg-red-100 text-red-800', CONTAINED: 'bg-forest-100 text-forest-800', DISMISSED: 'bg-slate-100 text-slate-600',
}
export const CHANNEL_ICON = { web: '🖥', mobile: '📱', whatsapp: '💬', ivr: '☎️' }

export function RiskBadge({ level, children }) {
  return <span className={clsx('badge', RISK_STYLE[level] || 'bg-slate-100 text-slate-700')}>{children || level}</span>
}
export function StatusBadge({ status, label }) {
  return <span className={clsx('badge whitespace-nowrap', STATUS_STYLE[status] || 'bg-slate-100 text-slate-700')}>{label || status?.replace(/_/g, ' ')}</span>
}

export function timeAgo(iso) {
  if (!iso) return '—'
  try { return formatDistanceToNowStrict(parseISO(iso), { addSuffix: true }) } catch { return iso }
}
export function fmtDate(iso, f = 'd MMM yyyy') {
  if (!iso) return '—'
  try { return format(parseISO(iso), f) } catch { return iso }
}
export function fmtDateTime(iso) { return fmtDate(iso, 'd MMM yyyy, HH:mm') }

export function PageHeader({ title, subtitle, actions, children }) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
        {children}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Card({ className, title, subtitle, actions, children, padded = true }) {
  return (
    <section className={clsx('card', className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <div>
            {title && <h2 className="text-sm font-semibold text-slate-800">{title}</h2>}
            {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={padded ? 'p-5' : ''}>{children}</div>
    </section>
  )
}

export function Stat({ label, value, hint, icon: Icon, tone = 'default', loading }) {
  const tones = { default: 'bg-slate-100 text-slate-700', danger: 'bg-red-50 text-red-600', warn: 'bg-amber-50 text-amber-600', good: 'bg-forest-50 text-forest-700', info: 'bg-sky-50 text-sky-700' }
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <div className="text-xs font-medium text-slate-500">{label}</div>
          {loading ? <div className="skeleton mt-2 h-7 w-20" /> : <div className="mt-1 text-2xl font-bold tracking-tight text-slate-900">{value ?? '—'}</div>}
          {hint && !loading && <div className="mt-0.5 text-[11px] text-slate-500 truncate">{hint}</div>}
        </div>
        {Icon && <div className={clsx('rounded-xl p-2', tones[tone])}><Icon className="h-4 w-4" /></div>}
      </div>
    </div>
  )
}

export function EmptyState({ icon: Icon = Inbox, title = 'Nothing here yet', detail, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 rounded-2xl bg-slate-100 p-3 text-slate-400"><Icon className="h-6 w-6" /></div>
      <div className="text-sm font-semibold text-slate-700">{title}</div>
      {detail && <div className="mt-1 max-w-sm text-xs text-slate-500">{detail}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, retry }) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">
      <div className="font-semibold">Something went wrong</div>
      <div className="mt-1 text-xs">{error?.message || String(error)}</div>
      {retry && <button onClick={retry} className="btn-secondary mt-3">Retry</button>}
    </div>
  )
}

export function TableSkeleton({ rows = 6, cols = 5 }) {
  return (
    <div className="p-4 space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-3">
          {Array.from({ length: cols }).map((_, j) => <div key={j} className="skeleton h-5" style={{ width: `${[26, 14, 18, 12, 20, 10][j % 6]}%` }} />)}
        </div>
      ))}
    </div>
  )
}

export function Modal({ open, onClose, title, children, wide, footer }) {
  useEffect(() => {
    if (!open) return
    const k = (e) => e.key === 'Escape' && onClose?.()
    window.addEventListener('keydown', k)
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', k); document.body.style.overflow = '' }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[900] flex items-end justify-center bg-slate-900/40 p-0 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={clsx('toast-in flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl', wide ? 'sm:max-w-3xl' : 'sm:max-w-lg')}>
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="h-5 w-5" /></button>
        </div>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function Field({ label, children, hint, error, required }) {
  return (
    <label className="block">
      <span className="label">{label}{required && <span className="text-red-500"> *</span>}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-[11px] text-slate-500">{hint}</span>}
      {error && <span className="mt-1 block text-[11px] text-red-600">{error}</span>}
    </label>
  )
}

export function Pagination({ page, pages, total, onPage }) {
  if (!pages || pages <= 1) return total ? <div className="px-4 py-2.5 text-xs text-slate-500">{total} result{total === 1 ? '' : 's'}</div> : null
  return (
    <div className="flex items-center justify-between px-4 py-2.5 text-xs text-slate-500">
      <span>Page {page} of {pages} · {total} results</span>
      <div className="flex gap-1">
        <button className="btn-ghost !p-1.5" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft className="h-4 w-4" /></button>
        <button className="btn-ghost !p-1.5" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight className="h-4 w-4" /></button>
      </div>
    </div>
  )
}

export function Spinner({ className }) {
  return <span className={clsx('inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-forest-700', className)} />
}

export function Segmented({ value, onChange, options }) {
  return (
    <div className="inline-flex rounded-xl bg-slate-100 p-0.5">
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)} className={clsx('rounded-lg px-3 py-1.5 text-xs font-medium transition', value === o.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800')}>{o.label}</button>
      ))}
    </div>
  )
}

export function ConfirmButton({ onConfirm, children, className = 'btn-danger', confirmLabel = 'Confirm', busy }) {
  return (
    <button className={className} disabled={busy} onClick={() => { if (window.confirm(typeof confirmLabel === 'string' ? confirmLabel : 'Are you sure?')) onConfirm() }}>{busy ? <Spinner /> : children}</button>
  )
}
