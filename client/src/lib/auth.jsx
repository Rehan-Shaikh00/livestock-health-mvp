import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getToken, setToken } from './api'

const Ctx = createContext(null)

export const ROLE_LABEL = {
  farmer: 'Farmer', pashu_sakhi: 'Pashu Sakhi', paravet: 'Paravet', ldo: 'LDO / Vet', acah: 'ACAH', dcah: 'DCAH',
  state: 'State Directorate', lab: 'Lab personnel', admin: 'Administrator',
}
export const TIER = { farmer: 1, pashu_sakhi: 1, paravet: 2, ldo: 2, lab: 2, acah: 3, dcah: 3, state: 4, admin: 4 }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const tok = getToken()
    if (!tok) { setReady(true); return }
    api('/api/v1/auth/me').then((d) => setUser(d.user)).catch(() => setToken(null)).finally(() => setReady(true))
    const onLogout = () => setUser(null)
    window.addEventListener('pa:logout', onLogout)
    return () => window.removeEventListener('pa:logout', onLogout)
  }, [])

  const login = useCallback(async (username, password) => {
    const d = await api('/api/v1/auth/login', { method: 'POST', body: { username, password } })
    setToken(d.token); setUser(d.user)
    return d.user
  }, [])
  const logout = useCallback(() => { setToken(null); setUser(null) }, [])
  const refresh = useCallback(async () => { const d = await api('/api/v1/auth/me'); setUser(d.user); return d.user }, [])

  const value = useMemo(() => ({
    user, ready, login, logout, refresh, setUser,
    role: user?.role, tier: TIER[user?.role] || 0,
    is: (...roles) => roles.includes(user?.role),
    canReport: ['farmer', 'pashu_sakhi', 'paravet', 'ldo', 'admin'].includes(user?.role),
    isClinical: ['ldo', 'paravet', 'acah', 'dcah', 'state', 'admin'].includes(user?.role),
    isDistrictPlus: ['acah', 'dcah', 'state', 'admin'].includes(user?.role),
  }), [user, ready, login, logout, refresh])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
