import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'

const Ctx = createContext(null)
const ICON = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info }
const STYLE = {
  success: 'border-forest-200 bg-white text-forest-900', error: 'border-red-200 bg-white text-red-800',
  warning: 'border-amber-200 bg-white text-amber-900', info: 'border-slate-200 bg-white text-slate-800',
}
const ICON_STYLE = { success: 'text-forest-600', error: 'text-red-600', warning: 'text-amber-600', info: 'text-sky-600' }

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const dismiss = useCallback((id) => setItems((x) => x.filter((t) => t.id !== id)), [])
  const push = useCallback((type, title, detail, ttl = 4500) => {
    const id = Math.random().toString(36).slice(2)
    setItems((x) => [...x, { id, type, title, detail }].slice(-5))
    if (ttl) setTimeout(() => dismiss(id), ttl)
    return id
  }, [dismiss])
  const value = useMemo(() => ({
    push, dismiss,
    success: (t, d) => push('success', t, d), error: (t, d) => push('error', t, d, 7000),
    warning: (t, d) => push('warning', t, d, 6000), info: (t, d) => push('info', t, d),
  }), [push, dismiss])
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-[1000] flex flex-col gap-2 w-[min(92vw,380px)]">
        {items.map((t) => {
          const I = ICON[t.type] || Info
          return (
            <div key={t.id} className={`toast-in flex items-start gap-3 rounded-2xl border p-3.5 shadow-lg ${STYLE[t.type]}`}>
              <I className={`h-5 w-5 shrink-0 mt-0.5 ${ICON_STYLE[t.type]}`} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold leading-tight">{t.title}</div>
                {t.detail && <div className="mt-0.5 text-xs text-slate-600 break-words">{t.detail}</div>}
              </div>
              <button onClick={() => dismiss(t.id)} className="text-slate-400 hover:text-slate-700"><X className="h-4 w-4" /></button>
            </div>
          )
        })}
      </div>
    </Ctx.Provider>
  )
}
export const useToast = () => useContext(Ctx)
