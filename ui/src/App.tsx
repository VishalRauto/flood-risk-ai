import { ConfigProvider } from '@/contexts/ConfigContext'
import { ThemeProvider }  from '@/contexts/ThemeContext'
import { LoggingProvider } from '@/contexts/LoggingContext'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import UnifiedDashboard from '@/components/UnifiedDashboard'
import PublicPortal from '@/pages/PublicPortal'
import LuxuryDashboard from '@/pages/LuxuryDashboard'
import {
  AuthProvider,
  RegisterPage,
  LoginPage,
  ProfilePage,
  AlertHistoryPage,
} from '@/pages/UserAuth'
import '@/styles/luxury.css'

function AppContent() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── Main research dashboard ───────────────────────── */}
        <Route path="/"          element={<UnifiedDashboard />} />
        <Route path="/dashboard" element={<UnifiedDashboard />} />

        {/* ── Luxury 3D Dashboard ───────────────────────────── */}
        <Route path="/luxury"    element={<LuxuryDashboard />} />

        {/* ── Public citizen portal ─────────────────────────── */}
        <Route path="/public"    element={<PublicPortal />} />

        {/* ── User auth + profile ───────────────────────────── */}
        <Route path="/register"  element={<RegisterPage />} />
        <Route path="/login"     element={<LoginPage />} />
        <Route path="/profile"   element={<ProfilePage />} />
        <Route path="/alerts"    element={<AlertHistoryPage />} />

        {/* ── Fallback ──────────────────────────────────────── */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

function App() {
  return (
    <ConfigProvider>
      <LoggingProvider>
        <ThemeProvider>
          {/* AuthProvider wraps everything so any page can call useAuth() */}
          <AuthProvider>
            <AppContent />
          </AuthProvider>
        </ThemeProvider>
      </LoggingProvider>
    </ConfigProvider>
  )
}

export default App
