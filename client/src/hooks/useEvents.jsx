import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getToken } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useToast } from '../lib/toast'

const Ctx = createContext({ connected: false, events: [] })

/** Single SSE connection per session; invalidates queries and raises toasts. */
export function EventsProvider({ children }) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState([])
  const esRef = useRef(null)

  useEffect(() => {
    if (!user) return
    let es
    let closed = false
    const open = () => {
      es = new EventSource(`/api/v1/events?token=${encodeURIComponent(getToken())}`)
      esRef.current = es
      es.addEventListener('ready', () => setConnected(true))
      es.onerror = () => { setConnected(false) }
      const handle = (name) => (e) => {
        let payload
        try { payload = JSON.parse(e.data) } catch { return }
        setEvents((x) => [{ ...payload, name }, ...x].slice(0, 30))
        const d = payload.data || {}
        if (name === 'priority_alert') toast.error(`⚠ High-risk: ${d.suspected_disease || 'case'}`, `${d.village || ''} · ${d.case_id || ''}`)
        else if (name === 'outbreak_suspected') toast.warning(`Suspected ${d.disease} cluster detected`, `${d.case_count} cases in taluka ${d.taluka_code}`)
        else if (name === 'outbreak_confirmed') toast.error(`Outbreak confirmed: ${d.disease}`, 'Advisories dispatched to affected area')
        else if (name === 'alert' && d.kind !== 'high_triage') toast.info(d.title, d.message_en)
        else if (name === 'case_created') toast.info(`New ${d.risk_level} report via ${d.channel}`, `${d.suspected_disease} · ${d.village || ''}`)
        qc.invalidateQueries({ queryKey: ['summary'] })
        qc.invalidateQueries({ queryKey: ['cases'] })
        qc.invalidateQueries({ queryKey: ['alerts'] })
        qc.invalidateQueries({ queryKey: ['outbreaks'] })
        qc.invalidateQueries({ queryKey: ['risk-map'] })
        qc.invalidateQueries({ queryKey: ['referrals'] })
      }
      for (const n of ['priority_alert', 'outbreak_suspected', 'outbreak_confirmed', 'alert', 'case_created', 'case_updated', 'sample_collected']) es.addEventListener(n, handle(n))
    }
    open()
    return () => { closed = true; es?.close(); setConnected(false) }
  }, [user?.id]) // eslint-disable-line

  return <Ctx.Provider value={{ connected, events }}>{children}</Ctx.Provider>
}
export const useEvents = () => useContext(Ctx)
