import { Window } from 'happy-dom'
const win = new Window({ url: 'http://localhost:5173/', width: 1400, height: 900 })
const doc = win.document
for (const k of Object.getOwnPropertyNames(win)) { if (!(k in globalThis)) { try { globalThis[k] = win[k] } catch {} } }
globalThis.window = win; globalThis.document = doc; Object.defineProperty(globalThis, 'navigator', { value: win.navigator, configurable: true })
globalThis.localStorage = win.localStorage
globalThis.ResizeObserver = class { observe(){} unobserve(){} disconnect(){} }
globalThis.EventSource = class { addEventListener(){} close(){} }
win.HTMLCanvasElement && (win.HTMLCanvasElement.prototype.getContext = () => null)
Object.defineProperty(win.HTMLElement.prototype, 'clientWidth', { get(){ return 800 } })
Object.defineProperty(win.HTMLElement.prototype, 'clientHeight', { get(){ return 400 } })
Object.defineProperty(win.HTMLElement.prototype, 'offsetWidth', { get(){ return 800 } })
Object.defineProperty(win.HTMLElement.prototype, 'offsetHeight', { get(){ return 400 } })
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const nodeFetch = globalThis.fetch
globalThis.fetch = (u, o) => nodeFetch(typeof u === 'string' && u.startsWith('/') ? 'http://localhost:5000' + u : u, o)
globalThis.confirm = () => true
const React = (await import('react')).default
const { createRoot } = await import('react-dom/client')
const { MemoryRouter } = await import('react-router-dom')
const { QueryClient, QueryClientProvider } = await import('@tanstack/react-query')
const M = await import('./dist-smoke/smoke-entry.js')
const errors = []
process.on('unhandledRejection', (e) => errors.push('unhandled: ' + (e?.message || e)))
const origErr = console.error; console.error = (...a) => { const s = a.map(String).join(' '); if (!/act\(|Warning:|Not implemented|Each child/.test(s)) errors.push(s.slice(0, 300)) }
const user = process.argv[2] || 'ldo1'
const r = await fetch('http://localhost:5000/api/v1/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ username: user, password: '1234' }) }).then(r => r.json())
const caseId = (await fetch('http://localhost:5000/api/v1/cases?page_size=1', { headers: { Authorization: 'Bearer ' + r.token } }).then(r => r.json())).items[0]?.id
const tag = (await fetch('http://localhost:5000/api/v1/animals?page_size=1', { headers: { Authorization: 'Bearer ' + r.token } }).then(r => r.json())).items[0]?.ear_tag
const routes = ['/', '/cases', `/cases/${caseId}`, '/animals', `/animals/${tag}`, '/vaccination', '/lab', '/map', '/outbreaks', '/alerts', '/weather', '/analytics', '/channels', '/vet-centers', '/users', '/settings', '/report']
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
for (const route of routes) {
  M.setToken(r.token)
  const el = doc.createElement('div'); doc.body.appendChild(el)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: 0 } } })
  const root = createRoot(el)
  const before = errors.length
  try {
    root.render(React.createElement(QueryClientProvider, { client: qc }, React.createElement(MemoryRouter, { initialEntries: [route] }, React.createElement(M.I18nProvider, null, React.createElement(M.ToastProvider, null, React.createElement(M.AuthProvider, null, React.createElement(M.EventsProvider, null, React.createElement(M.App))))))))
    await sleep(2500)
    const text = el.textContent || ''
    const bad = /Something went wrong|Request failed/.test(text)
    console.log((bad || errors.length > before ? '✗' : '✓'), route.padEnd(24), text.length, 'chars', bad ? text.match(/Something went wrong.{0,120}/)?.[0] : '')
  } catch (e) { console.log('✗', route, 'THREW', e.message) }
  root.unmount(); el.remove()
}
console.log('runtime errors:', errors.length); errors.slice(0, 15).forEach(e => console.log('  -', e))
process.exit(0)
