import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import {
  LayoutDashboard, ClipboardList, PlusCircle, PawPrint, Syringe, FlaskConical, Map, BellRing, Biohazard, CloudSun,
  Radio, Hospital, Users, Settings, LogOut, Menu, X, Wifi, WifiOff, Languages, UploadCloud, Activity, Sparkles,
} from 'lucide-react'
import { useAuth, ROLE_LABEL } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { useEvents } from '../hooks/useEvents'
import { offline } from '../lib/api'
import { useToast } from '../lib/toast'
import { useQueryClient } from '@tanstack/react-query'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/report', label: 'Report a case', icon: PlusCircle, roles: ['farmer', 'pashu_sakhi', 'paravet', 'ldo', 'admin'] },
  { to: '/cases', label: 'Cases', icon: ClipboardList },
  { to: '/animals', label: 'Animals', icon: PawPrint },
  { to: '/vaccination', label: 'Vaccination', icon: Syringe },
  { to: '/lab', label: 'Laboratory', icon: FlaskConical },
  { to: '/map', label: 'Risk map', icon: Map },
  { to: '/outbreaks', label: 'Outbreaks', icon: Biohazard, roles: ['paravet', 'ldo', 'acah', 'dcah', 'state', 'admin', 'lab'] },
  { to: '/alerts', label: 'Alerts', icon: BellRing },
  { to: '/weather', label: 'Weather', icon: CloudSun, roles: ['paravet', 'ldo', 'acah', 'dcah', 'state', 'admin'] },
  { to: '/analytics', label: 'Analytics & ML', icon: Sparkles, roles: ['ldo', 'acah', 'dcah', 'state', 'admin'] },
  { to: '/channels', label: 'Channels', icon: Radio, roles: ['paravet', 'ldo', 'acah', 'dcah', 'state', 'admin'] },
  { to: '/vet-centers', label: 'Vet centres', icon: Hospital },
  { to: '/users', label: 'Users', icon: Users, roles: ['ldo', 'acah', 'dcah', 'state', 'admin'] },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Layout() {
  const { user, logout, role } = useAuth()
  const { t, lang, setLang, languages } = useI18n()
  const { connected } = useEvents()
  const toast = useToast()
  const qc = useQueryClient()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  const [queued, setQueued] = useState(offline.read().length)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => { setOpen(false) }, [loc.pathname])
  useEffect(() => {
    const on = () => setOnline(true), off = () => setOnline(false), q = () => setQueued(offline.read().length)
    window.addEventListener('online', on); window.addEventListener('offline', off); window.addEventListener('pa:queue', q)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); window.removeEventListener('pa:queue', q) }
  }, [])

  const doSync = async () => {
    setSyncing(true)
    try {
      const r = await offline.sync()
      toast.success(`Synced ${r.applied} report${r.applied === 1 ? '' : 's'}`, r.stale ? `${r.stale} stale (server newer) · ${r.rejected} rejected` : r.rejected ? `${r.rejected} rejected` : 'Last-write-wins applied')
      qc.invalidateQueries()
    } catch (e) { toast.error('Sync failed', e.message) } finally { setSyncing(false) }
  }
  useEffect(() => { if (online && queued > 0) doSync() }, [online]) // eslint-disable-line

  const items = NAV.filter((n) => !n.roles || n.roles.includes(role))

  const Sidebar = (
    <aside className="flex h-full w-64 flex-col bg-forest-950 text-forest-100">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-forest-800 ring-1 ring-forest-700"><Activity className="h-5 w-5 text-saffron-400" /></div>
        <div>
          <div className="text-[15px] font-bold leading-tight text-white">Pashu Arogya</div>
          <div className="text-[10px] uppercase tracking-wider text-forest-300">AH Dept · Maharashtra</div>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-3">
        {items.map(({ to, label, icon: I, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => clsx('flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition', isActive ? 'bg-forest-800 text-white shadow-inner' : 'text-forest-200/90 hover:bg-forest-900 hover:text-white')}>
            <I className="h-4 w-4 shrink-0" />{t(label)}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-forest-900 p-3">
        <div className="flex items-center gap-3 rounded-xl bg-forest-900/70 p-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-saffron-500 text-sm font-bold text-forest-950">{user.full_name?.replace(/^Dr\.\s*/, '')[0]}</div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-white">{user.full_name}</div>
            <div className="truncate text-[11px] text-forest-300">{ROLE_LABEL[role]}{user.district_code ? ` · ${user.district_code}` : ''}</div>
          </div>
          <button onClick={() => { logout(); nav('/login') }} title={t('Sign out')} className="rounded-lg p-1.5 text-forest-300 hover:bg-forest-800 hover:text-white"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </aside>
  )

  return (
    <div className="flex h-full">
      <div className="hidden lg:block">{Sidebar}</div>
      {open && (
        <div className="fixed inset-0 z-[800] lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 shadow-2xl">{Sidebar}</div>
          <button onClick={() => setOpen(false)} className="absolute left-[17rem] top-4 rounded-lg bg-white p-1.5 shadow"><X className="h-5 w-5" /></button>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-[700] flex h-14 items-center gap-3 border-b border-slate-200 bg-white/85 px-4 backdrop-blur sm:px-6">
          <button onClick={() => setOpen(true)} className="btn-ghost !p-2 lg:hidden"><Menu className="h-5 w-5" /></button>
          <div className="hidden text-sm text-slate-500 sm:block">Maharashtra Animal Health Surveillance &amp; Decision Support</div>
          <div className="ml-auto flex items-center gap-2">
            {queued > 0 && (
              <button onClick={doSync} disabled={!online || syncing} className="btn-secondary !py-1.5 text-xs !border-amber-300 !bg-amber-50 !text-amber-800">
                <UploadCloud className={clsx('h-4 w-4', syncing && 'animate-bounce')} />{queued} {t('Offline queue').toLowerCase()} · {t('Sync now')}
              </button>
            )}
            <span className={clsx('badge', online ? 'bg-forest-50 text-forest-700' : 'bg-red-50 text-red-700')} title={online ? 'Online' : 'Offline — reports will queue'}>
              {online ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}<span className="hidden sm:inline">{online ? 'Online' : 'Offline'}</span>
            </span>
            <span className={clsx('badge', connected ? 'bg-sky-50 text-sky-700' : 'bg-slate-100 text-slate-500')} title="Server-Sent Events stream">
              <span className={clsx('h-1.5 w-1.5 rounded-full', connected ? 'bg-sky-500 pulse-dot' : 'bg-slate-400')} />{t('Live')}
            </span>
            <div className="relative">
              <Languages className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
              <select value={lang} onChange={(e) => { setLang(e.target.value); qc.invalidateQueries() }} className="input !w-auto !py-1.5 !pl-7 !pr-7 text-xs">
                {Object.entries(languages).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-4 py-5 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl"><Outlet /></div>
        </main>
      </div>
    </div>
  )
}
