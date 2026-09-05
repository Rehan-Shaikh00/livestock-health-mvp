import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Radio, Phone, MessageCircle, Smartphone, Loader2, Send } from 'lucide-react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { useToast } from '../lib/toast'
import { Card, EmptyState, Field, PageHeader, RiskBadge, timeAgo, fmtDateTime } from '../components/ui'

export default function Channels() {
  const { term } = useI18n()
  const toast = useToast()
  const qc = useQueryClient()
  const log = useQuery({ queryKey: ['channel-log'], queryFn: () => api('/api/v1/channels/log') })
  const sync = useQuery({ queryKey: ['sync-log'], queryFn: () => api('/api/v1/sync/log') })
  const [wa, setWa] = useState({ from: '+91 98220 11223', text: 'REPORT cattle 556325 high fever, skin nodules deaths=1 affected=3' })
  const [ivr, setIvr] = useState({ caller: '+91 98220 11223', species: '1', symptoms: '14', affected: 3, deaths: 1 })
  const [waRes, setWaRes] = useState(null); const [ivrRes, setIvrRes] = useState(null)
  const inv = () => { qc.invalidateQueries({ queryKey: ['channel-log'] }); qc.invalidateQueries({ queryKey: ['cases'] }); qc.invalidateQueries({ queryKey: ['summary'] }) }
  const sendWa = useMutation({ mutationFn: () => api('/webhooks/whatsapp', { method: 'POST', body: wa }), onSuccess: (d) => { setWaRes(d); inv() }, onError: (e) => { setWaRes(e.body); toast.error(e.message) } })
  const sendIvr = useMutation({ mutationFn: () => api('/webhooks/ivr', { method: 'POST', body: ivr }), onSuccess: (d) => { setIvrRes(d); inv() }, onError: (e) => toast.error(e.message) })
  return (
    <div className="space-y-4">
      <PageHeader title="Multi-channel intake" subtitle="Web · offline mobile batch sync · WhatsApp bot · IVR — every channel lands in the same triage pipeline" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="WhatsApp webhook simulator" subtitle="POST /webhooks/whatsapp" actions={<MessageCircle className="h-4 w-4 text-green-600" />}>
          <div className="space-y-3">
            <Field label="From"><input className="input" value={wa.from} onChange={(e) => setWa({ ...wa, from: e.target.value })} /></Field>
            <Field label="Message" hint="REPORT <species> <LGD village> <symptoms,…> deaths=N affected=N"><textarea className="input font-mono text-xs" rows={2} value={wa.text} onChange={(e) => setWa({ ...wa, text: e.target.value })} /></Field>
            <button onClick={() => sendWa.mutate()} className="btn-primary" disabled={sendWa.isPending}>{sendWa.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}Send</button>
            {waRes && <div className="rounded-2xl rounded-tl-sm bg-green-50 p-3 text-sm whitespace-pre-wrap border border-green-200">{waRes.reply}{waRes.case_id && <div className="mt-2"><Link to={`/cases/${waRes.case_id}`} className="text-xs font-mono text-forest-700 underline">Open {waRes.case_id}</Link></div>}</div>}
          </div>
        </Card>
        <Card title="IVR webhook simulator" subtitle="POST /webhooks/ivr — DTMF tree" actions={<Phone className="h-4 w-4 text-amber-600" />}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Caller"><input className="input" value={ivr.caller} onChange={(e) => setIvr({ ...ivr, caller: e.target.value })} /></Field>
            <Field label="Species key" hint="1 cattle 2 buffalo 3 goat 4 sheep 5 poultry"><input className="input" value={ivr.species} onChange={(e) => setIvr({ ...ivr, species: e.target.value })} /></Field>
            <Field label="Symptom keys" hint="1 fever 2 nodules 3 foot 4 resp 5 diarrhea 6 sudden death 7 anorexia"><input className="input" value={ivr.symptoms} onChange={(e) => setIvr({ ...ivr, symptoms: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-2"><Field label="Affected"><input type="number" className="input" value={ivr.affected} onChange={(e) => setIvr({ ...ivr, affected: +e.target.value })} /></Field><Field label="Deaths"><input type="number" className="input" value={ivr.deaths} onChange={(e) => setIvr({ ...ivr, deaths: +e.target.value })} /></Field></div>
          </div>
          <button onClick={() => sendIvr.mutate()} className="btn-primary mt-3" disabled={sendIvr.isPending}>{sendIvr.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Phone className="h-4 w-4" />}Simulate call</button>
          {ivrRes && <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm"><div className="flex items-center gap-2"><RiskBadge level={ivrRes.risk_level} /><span className="font-mono text-xs">{ivrRes.case_id}</span></div><div className="mt-1 text-xs text-slate-600">🔊 TTS ({ivrRes.language}): {ivrRes.tts}</div><div className="text-xs text-slate-500">Case id read back: "{ivrRes.say_case_id}"</div></div>}
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Inbound message log" padded={false}>
          {log.isLoading ? <div className="p-4 space-y-2">{[...Array(6)].map((_, i) => <div key={i} className="skeleton h-10" />)}</div> : !log.data?.items?.length ? <EmptyState icon={Radio} title="No inbound messages" /> : (
            <ul className="max-h-[440px] divide-y divide-slate-100 overflow-y-auto">{log.data.items.map((m) => <li key={m.id} className="flex gap-3 px-4 py-2.5 text-sm"><span className="text-lg">{m.channel === 'ivr' ? '☎️' : '💬'}</span><div className="min-w-0 flex-1"><div className="flex items-center gap-2 text-xs text-slate-500"><span className="font-medium text-slate-700">{m.sender}</span>· {timeAgo(m.created_at)}{m.case_id && <Link to={`/cases/${m.case_id}`} className="font-mono text-forest-700 hover:underline">{m.case_id}</Link>}{m.risk_level && <RiskBadge level={m.risk_level} />}</div><div className="truncate font-mono text-xs">{m.body}</div></div></li>)}</ul>
          )}
        </Card>
        <Card title="Offline batch sync log" subtitle="Last-write-wins on updated_at" padded={false} actions={<Smartphone className="h-4 w-4 text-sky-600" />}>
          {!sync.data?.items?.length ? <EmptyState title="No syncs yet" /> : <ul className="divide-y divide-slate-100">{sync.data.items.map((s) => <li key={s.id} className="px-4 py-2.5 text-xs"><div className="flex justify-between"><span className="font-mono font-semibold">{s.device_id}</span><span className="text-slate-400">{fmtDateTime(s.created_at)}</span></div><div className="text-slate-600">{s.full_name} · {s.received} received · <span className="text-forest-700">{s.applied} applied</span> · <span className="text-amber-700">{s.stale} stale</span> · <span className="text-red-700">{s.rejected} rejected</span></div></li>)}</ul>}
        </Card>
      </div>
    </div>
  )
}
