const TOKEN_KEY = 'pa.token'
const LANG_KEY = 'pa.lang'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))
export const getLang = () => localStorage.getItem(LANG_KEY) || 'en'
export const setLang = (l) => localStorage.setItem(LANG_KEY, l)

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.error || `Request failed (${status})`)
    this.status = status
    this.body = body
  }
}

export async function api(path, { method = 'GET', body, headers = {}, raw = false } = {}) {
  const h = { Accept: 'application/json', 'X-Lang': getLang(), ...headers }
  const tok = getToken()
  if (tok) h.Authorization = `Bearer ${tok}`
  if (body !== undefined) h['Content-Type'] = 'application/json'
  const res = await fetch(path, { method, headers: h, body: body !== undefined ? JSON.stringify(body) : undefined })
  if (raw) return res
  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = { error: text } }
  if (!res.ok) {
    if (res.status === 401 && tok) {
      setToken(null)
      window.dispatchEvent(new Event('pa:logout'))
    }
    throw new ApiError(res.status, data)
  }
  return data
}

export const qs = (obj) => {
  const p = new URLSearchParams()
  Object.entries(obj || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, v) })
  const s = p.toString()
  return s ? `?${s}` : ''
}

// ---- offline queue (localStorage) ------------------------------------------
const QUEUE_KEY = 'pa.offline.queue'
export const offline = {
  read() { try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]') } catch { return [] } },
  write(q) { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); window.dispatchEvent(new Event('pa:queue')) },
  enqueue(report) {
    const q = offline.read()
    q.push({ ...report, local_id: `L-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`, updated_at: Date.now(), queued_at: new Date().toISOString() })
    offline.write(q)
    return q.length
  },
  remove(localId) { offline.write(offline.read().filter((r) => r.local_id !== localId)) },
  async sync() {
    const q = offline.read()
    if (!q.length) return { received: 0, applied: 0, stale: 0, rejected: 0, results: [] }
    const device = localStorage.getItem('pa.device') || (() => { const d = `DEV-${Math.floor(1000 + Math.random() * 9000)}`; localStorage.setItem('pa.device', d); return d })()
    const res = await api('/api/v1/reports/mobile/sync', { method: 'POST', body: { device_id: device, reports: q.map(({ queued_at, ...r }) => r) } })
    const failed = new Set(res.results.filter((r) => r.status === 'rejected').map((r) => r.local_id))
    offline.write(q.filter((r) => failed.has(r.local_id)))
    return res
  },
}
