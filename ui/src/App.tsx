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

// Global style imports
import '@/styles/luxury.css'
import '@/styles/design-system.css'

function AppContent() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── Main Research Dashboard ────────────────────── */}
        <Route path="/"          element={<UnifiedDashboard />} />
        <Route path="/dashboard" element={<UnifiedDashboard />} />

        {/* ── Luxury 3D Dashboard ────────────────────────── */}
        <Route path="/luxury"    element={<LuxuryDashboard />} />

        {/* ── Public Citizen Portal ──────────────────────── */}
        <Route path="/public"    element={<PublicPortal />} />

        {/* ── Authentication & Profile ────────────────────── */}
        <Route path="/register"  element={<RegisterPage />} />
        <Route path="/login"     element={<LoginPage />} />
        <Route path="/profile"   element={<ProfilePage />} />
        <Route path="/alerts"    element={<AlertHistoryPage />} />

        {/* ── Fallback ────────────────────────────────────── */}
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
          {/* AuthProvider wraps everything — useAuth() works in all pages */}
          <AuthProvider>
            <AppContent />
          </AuthProvider>
        </ThemeProvider>
      </LoggingProvider>
    </ConfigProvider>
  )
}

export default App
