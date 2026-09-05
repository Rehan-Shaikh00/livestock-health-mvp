import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './lib/auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Cases from './pages/Cases'
import CaseDetail from './pages/CaseDetail'
import ReportCase from './pages/ReportCase'
import Animals from './pages/Animals'
import AnimalDetail from './pages/AnimalDetail'
import Vaccination from './pages/Vaccination'
import Lab from './pages/Lab'
import RiskMap from './pages/RiskMap'
import Outbreaks from './pages/Outbreaks'
import Alerts from './pages/Alerts'
import Weather from './pages/Weather'
import Analytics from './pages/Analytics'
import Channels from './pages/Channels'
import VetCenters from './pages/VetCenters'
import UsersPage from './pages/Users'
import SettingsPage from './pages/Settings'
import { Spinner } from './components/ui'

function Guard({ children }) {
  const { user, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return <div className="grid h-full place-items-center"><Spinner className="h-8 w-8" /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return children
}

export default function App() {
  const { user, ready } = useAuth()
  return (
    <Routes>
      <Route path="/login" element={ready && user ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route index element={<Dashboard />} />
        <Route path="report" element={<ReportCase />} />
        <Route path="cases" element={<Cases />} />
        <Route path="cases/:id" element={<CaseDetail />} />
        <Route path="animals" element={<Animals />} />
        <Route path="animals/:key" element={<AnimalDetail />} />
        <Route path="vaccination" element={<Vaccination />} />
        <Route path="lab" element={<Lab />} />
        <Route path="map" element={<RiskMap />} />
        <Route path="outbreaks" element={<Outbreaks />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="weather" element={<Weather />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="channels" element={<Channels />} />
        <Route path="vet-centers" element={<VetCenters />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
