import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip as LTooltip } from 'react-leaflet'
import { Layers, Crosshair, Phone, Hospital } from 'lucide-react'
import clsx from 'clsx'
import { api, qs } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { Card, ErrorState, PageHeader, RiskBadge, Segmented, RISK_COLOR, timeAgo } from '../components/ui'

const BAND = { HIGH: '#dc2626', MEDIUM: '#f59e0b', LOW: '#2b6b32' }

export default function RiskMap() {
  const { user } = useAuth()
  const { t, term } = useI18n()
  const [days, setDays] = useState(14)
  const [layers, setLayers] = useState({ talukas: true, cases: true, centers: false, weather: true })
  const [nearest, setNearest] = useState(null)
  const q = useQuery({ queryKey: ['risk-map', days], queryFn: () => api(`/api/v1/geo/risk-map${qs({ days })}`) })
  const centers = useQuery({ queryKey: ['vet-centers'], queryFn: () => api('/api/v1/vet-centers'), enabled: layers.centers || !!nearest })
  const center = useMemo(() => {
    const tk = q.data?.talukas || []
    if (user.district_code && tk.length) { const own = tk.filter((x) => x.district_code === user.district_code); if (own.length) return [own.reduce((s, x) => s + x.lat, 0) / own.length, own.reduce((s, x) => s + x.lng, 0) / own.length] }
    return [19.3, 75.7]
  }, [q.data, user.district_code])
  const zoom = user.district_code ? 8 : 7

  const locate = () => navigator.geolocation?.getCurrentPosition(async (p) => {
    const r = await api(`/api/v1/geo/nearest-clinic?lat=${p.coords.latitude}&lng=${p.coords.longitude}&k=5`)
    setNearest({ ...r, me: [p.coords.latitude, p.coords.longitude] })
  }, () => setNearest({ error: 'GPS unavailable' }))

  if (q.isError) return <ErrorState error={q.error} retry={q.refetch} />
  const tk = q.data?.talukas || []
  const hot = [...tk].sort((a, b) => b.risk_score - a.risk_score).slice(0, 8)

  return (
    <div className="space-y-4">
      <PageHeader title={t('Risk map')} subtitle="Composite taluka risk = recent cases + mortality + HIGH triage + MAHAVEDH vector conditions + active outbreak signals"
        actions={<><Segmented value={days} onChange={setDays} options={[{ value: 7, label: '7d' }, { value: 14, label: '14d' }, { value: 30, label: '30d' }, { value: 60, label: '60d' }]} /><button onClick={locate} className="btn-secondary"><Crosshair className="h-4 w-4" />{t('Nearest clinic')}</button></>} />
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card padded={false} className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-3 py-2 text-xs">
            <Layers className="h-4 w-4 text-slate-400" />
            {[['talukas', 'Taluka risk'], ['cases', 'Case points'], ['weather', 'Vector-favourable'], ['centers', 'Vet centres']].map(([k, l]) => <label key={k} className="flex items-center gap-1.5"><input type="checkbox" className="accent-forest-700" checked={layers[k]} onChange={(e) => setLayers({ ...layers, [k]: e.target.checked })} />{l}</label>)}
            <span className="ml-auto flex items-center gap-3">{Object.entries(BAND).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{term(k)}</span>)}</span>
          </div>
          <div className="relative">
            {q.isLoading && <div className="absolute inset-0 z-[500] grid place-items-center bg-white/60 text-sm text-slate-500">Loading layers…</div>}
            <MapContainer center={center} zoom={zoom} style={{ height: 560 }} className="!rounded-none">
              <TileLayer attribution="&copy; OpenStreetMap contributors &copy; CARTO" url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" />
              {layers.talukas && tk.map((x) => (
                <CircleMarker key={x.taluka_code} center={[x.lat, x.lng]} radius={8 + Math.sqrt(x.risk_score) * 3} pathOptions={{ color: BAND[x.risk_band], fillColor: BAND[x.risk_band], fillOpacity: 0.28, weight: x.outbreak ? 3 : 1.5, dashArray: x.outbreak ? '4 3' : null }}>
                  <LTooltip direction="top" opacity={0.95}><b>{x.taluka}</b> · {x.district}<br />Risk {x.risk_score} · {x.cases} cases · {x.deaths} deaths</LTooltip>
                  <Popup><div className="text-xs"><div className="font-semibold">{x.taluka}, {x.district} <span className="font-mono text-slate-400">LGD {x.taluka_code}</span></div><div className="mt-1">Risk score <b>{x.risk_score}</b> ({x.risk_band})</div><div>{x.cases} cases · {x.high} high · {x.deaths} deaths · {x.affected} affected</div>{x.diseases.length > 0 && <div>Diseases: {x.diseases.map(term).join(', ')}</div>}{x.weather && <div>MAHAVEDH: {x.weather.humidity}% RH, {x.weather.temperature_c}°C {x.vector_favourable && '· ⚠ vector-favourable'}</div>}{x.outbreak && <div className="mt-1 font-semibold text-red-700">Outbreak {x.outbreak.status}: {term(x.outbreak.disease)}</div>}</div></Popup>
                </CircleMarker>
              ))}
              {layers.weather && tk.filter((x) => x.vector_favourable).map((x) => <CircleMarker key={'w' + x.taluka_code} center={[x.lat, x.lng]} radius={22} pathOptions={{ color: '#0ea5e9', fillOpacity: 0.06, weight: 1, dashArray: '2 4' }} />)}
              {layers.cases && (q.data?.cases || []).filter((c) => c.lat != null).map((c) => (
                <CircleMarker key={c.id} center={[c.lat, c.lng]} radius={c.risk_level === 'HIGH' ? 6 : 4} pathOptions={{ color: '#fff', weight: 1, fillColor: RISK_COLOR[c.risk_level], fillOpacity: 0.9 }}>
                  <Popup><div className="text-xs"><Link to={`/cases/${c.id}`} className="font-mono font-semibold text-forest-800 underline">{c.id}</Link><div>{term(c.suspected_disease)} · <RiskBadge level={c.risk_level} /></div><div>{c.village} · {c.species} · {c.affected_count} affected · {c.mortality_count} dead</div><div className="text-slate-500">{c.status} · {timeAgo(c.created_at)} · {c.precision}</div></div></Popup>
                </CircleMarker>
              ))}
              {layers.centers && (centers.data?.items || []).map((v) => <CircleMarker key={v.id} center={[v.lat, v.lng]} radius={5} pathOptions={{ color: '#1d4ed8', fillColor: '#3b82f6', fillOpacity: 1 }}><Popup><div className="text-xs"><b>{v.name}</b><div>{v.type} · {v.officer_name}</div><a href={`tel:${v.officer_phone}`}>{v.officer_phone}</a></div></Popup></CircleMarker>)}
              {nearest?.me && <CircleMarker center={nearest.me} radius={8} pathOptions={{ color: '#7c3aed', fillColor: '#a78bfa', fillOpacity: 0.9 }}><Popup>You are here</Popup></CircleMarker>}
              {nearest?.clinics?.map((c) => <CircleMarker key={c.name} center={[c.coordinates.lat, c.coordinates.lng]} radius={6} pathOptions={{ color: '#1d4ed8', fillColor: '#60a5fa', fillOpacity: 1 }}><Popup><b>{c.name}</b><br />{c.distance_km} km · {c.officer_phone}</Popup></CircleMarker>)}
            </MapContainer>
          </div>
        </Card>
        <div className="space-y-4">
          {nearest && (
            <Card title={t('Nearest clinic')} subtitle={nearest.backend ? `Engine: ${nearest.backend}` : ''} padded={false}>
              {nearest.error ? <div className="p-4 text-xs text-red-600">{nearest.error}</div> : <ul className="divide-y divide-slate-100">{nearest.clinics.map((c) => <li key={c.name} className="flex items-center gap-2 px-4 py-2.5 text-sm"><Hospital className="h-4 w-4 shrink-0 text-sky-600" /><div className="min-w-0 flex-1"><div className="truncate font-medium">{c.name}</div><div className="text-xs text-slate-500">{c.distance_km} km · {c.officer_name}</div></div><a href={`tel:${c.officer_phone}`} className="btn-ghost !p-1.5"><Phone className="h-4 w-4" /></a></li>)}</ul>}
            </Card>
          )}
          <Card title="Hotspot ranking" subtitle={`Last ${days} days`} padded={false}>
            {q.isLoading ? <div className="p-4 space-y-2">{[...Array(6)].map((_, i) => <div key={i} className="skeleton h-9" />)}</div> : (
              <ul className="divide-y divide-slate-100">{hot.map((x, i) => (
                <li key={x.taluka_code} className="flex items-center gap-3 px-4 py-2.5">
                  <span className="w-5 text-right text-xs font-bold text-slate-400">{i + 1}</span>
                  <div className="min-w-0 flex-1"><div className="flex items-center gap-2 text-sm font-medium">{x.taluka}<span className="text-xs font-normal text-slate-400">{x.district}</span>{x.outbreak && <span className="badge bg-red-100 text-red-700">outbreak</span>}</div><div className="text-xs text-slate-500">{x.cases} cases · {x.deaths} deaths · {x.high} high{x.vector_favourable ? ' · 🦟 vector' : ''}</div></div>
                  <div className="text-right"><div className="text-lg font-bold" style={{ color: BAND[x.risk_band] }}>{x.risk_score}</div></div>
                </li>
              ))}</ul>
            )}
          </Card>
          <Card title="How risk is scored">
            <ul className="space-y-1 text-xs text-slate-600"><li>• 6 pts per case, 8 per death, 10 per HIGH triage</li><li>• +12 when MAHAVEDH shows &gt;80% RH and 25–35 °C (vector window)</li><li>• +25 when an outbreak signal is open in the taluka</li><li>• Points: GPS fix when captured, else LGD village centroid</li><li>• Production: PostGIS <span className="font-mono">ST_DWithin</span> on village polygons; here SQLite + Haversine</li></ul>
          </Card>
        </div>
      </div>
    </div>
  )
}
