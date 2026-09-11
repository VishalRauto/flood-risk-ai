'use client'

/**
 * UserAuth.tsx — Register / Login / Profile / Alert History
 *
 * Four views in one file, controlled by `mode` prop:
 *   'register'   — new user signup
 *   'login'      — email/phone + password
 *   'profile'    — preferences (district, language, threshold, channels)
 *   'alerts'     — personal alert history with acknowledge
 */

import { useState, useEffect, useCallback, createContext, useContext } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from '@/hooks/useTranslation'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import {
  Bell, User, LogOut, ChevronLeft, Check, AlertTriangle,
  Phone, Mail, MapPin, Eye, EyeOff, Settings,
  RefreshCw, CheckCircle, Clock
} from 'lucide-react'

const API = (p: string) => `/api/${p}`

// ── Auth context (app-wide) ───────────────────────────────────────────────────
interface AuthUser {
  id: number; name: string; email?: string; phone?: string
  home_district?: string; home_state?: string; language: string
  alert_threshold: string; alert_sms: number; alert_email: number
  alert_whatsapp: number; unread_alerts?: number
}

interface AuthCtx {
  user: AuthUser | null
  token: string | null
  login: (user: AuthUser, token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthCtx>({
  user: null, token: null,
  login: () => {}, logout: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser]   = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)

  // Restore from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('flood_auth')
    if (saved) {
      try {
        const { user: u, token: t } = JSON.parse(saved)
        setUser(u); setToken(t)
      } catch {}
    }
  }, [])

  const login = useCallback((u: AuthUser, t: string) => {
    setUser(u); setToken(t)
    localStorage.setItem('flood_auth', JSON.stringify({ user: u, token: t }))
  }, [])

  const logout = useCallback(() => {
    if (token) {
      fetch(API('user/logout'), {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      }).catch(() => {})
    }
    setUser(null); setToken(null)
    localStorage.removeItem('flood_auth')
  }, [token])

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)

// ── Shared layout ─────────────────────────────────────────────────────────────
function PageShell({ title, back, children }: {
  title: string; back?: string; children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="sticky top-0 z-40 bg-gray-900/95 backdrop-blur border-b border-gray-800">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {back && (
              <Link to={back} className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-400">
                <ChevronLeft className="h-5 w-5" />
              </Link>
            )}
            <span className="font-semibold text-white text-sm">{title}</span>
          </div>
          <LanguageSwitcher compact />
        </div>
      </header>
      <main className="max-w-lg mx-auto px-4 py-6">{children}</main>
    </div>
  )
}

function Input({
  label, type = 'text', value, onChange, placeholder, error, icon: Icon, required
}: {
  label: string; type?: string; value: string; onChange: (v: string) => void
  placeholder?: string; error?: string; icon?: any; required?: boolean
}) {
  const [show, setShow] = useState(false)
  const inputType = type === 'password' ? (show ? 'text' : 'password') : type

  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      <div className="relative">
        {Icon && <Icon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />}
        <input
          type={inputType}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className={`w-full ${Icon ? 'pl-9' : 'pl-3'} pr-${type === 'password' ? '10' : '3'}
                     py-2.5 rounded-xl bg-gray-800 border text-white text-sm
                     placeholder-gray-500 focus:outline-none focus:ring-1
                     ${error ? 'border-red-500 focus:ring-red-500/50' : 'border-gray-600 focus:border-blue-500 focus:ring-blue-500/50'}`}
        />
        {type === 'password' && (
          <button type="button" onClick={() => setShow(s => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
            {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}

// ── Register page ─────────────────────────────────────────────────────────────
export function RegisterPage() {
  const { t } = useTranslation()
  const navigate   = useNavigate()

  const [name, setName]       = useState('')
  const [email, setEmail]     = useState('')
  const [phone, setPhone]     = useState('')
  const [password, setPw]     = useState('')
  const [district, setDist]   = useState('')
  const [threshold, setThresh]= useState('HIGH')
  const [loading, setLoading] = useState(false)
  const [errors, setErrors]   = useState<Record<string, string>>({})
  const [success, setSuccess] = useState(false)

  const validate = () => {
    const e: Record<string, string> = {}
    if (!name.trim())              e.name = 'Name is required'
    if (!email && !phone)          e.email = 'Email or phone is required'
    if (password.length < 6)       e.password = 'Password must be at least 6 characters'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      const r = await fetch(API('user/register'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email: email || undefined, phone: phone || undefined,
                               password, home_district: district || undefined,
                               alert_threshold: threshold }),
      })
      const data = await r.json()
      if (!r.ok) { setErrors({ form: data.detail || 'Registration failed' }); return }
      setSuccess(true)
      setTimeout(() => navigate('/login'), 1500)
    } catch {
      setErrors({ form: 'Network error. Please try again.' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageShell title="Register for Flood Alerts" back="/public">
      {success ? (
        <div className="text-center py-16 space-y-3">
          <CheckCircle className="h-16 w-16 text-green-400 mx-auto" />
          <p className="text-lg font-semibold text-white">Registration successful!</p>
          <p className="text-sm text-gray-400">Redirecting to login...</p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {errors.form && (
            <div className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-400">
              {errors.form}
            </div>
          )}

          <Input label="Full Name" value={name} onChange={setName}
                 placeholder="Your name" icon={User} required error={errors.name} />

          <Input label="Email" type="email" value={email} onChange={setEmail}
                 placeholder="your@email.com" icon={Mail} error={errors.email} />

          <div className="text-center text-xs text-gray-500">— or —</div>

          <Input label="Phone Number" type="tel" value={phone} onChange={setPhone}
                 placeholder="+91 98765 43210" icon={Phone} error={errors.phone} />

          <Input label="Password" type="password" value={password} onChange={setPw}
                 placeholder="At least 6 characters" required error={errors.password} />

          <Input label="Home District (optional)" value={district} onChange={setDist}
                 placeholder="e.g. Patna, Guwahati, Cuttack" icon={MapPin} />

          {/* Alert threshold */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">
              Alert Sensitivity
            </label>
            <div className="grid grid-cols-2 gap-2">
              {['MODERATE', 'HIGH', 'CRITICAL'].map(level => (
                <button key={level} type="button" onClick={() => setThresh(level)}
                        className={`py-2.5 rounded-xl text-sm font-medium border transition-colors
                                   ${threshold === level
                                     ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                                     : 'bg-gray-800 border-gray-600 text-gray-400 hover:border-gray-500'}`}>
                  {level}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500">
              Only notify me when risk is {threshold} or above
            </p>
          </div>

          <button type="submit" disabled={loading}
                  className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700
                             disabled:opacity-50 text-white font-semibold text-sm
                             transition-colors flex items-center justify-center gap-2">
            {loading && <RefreshCw className="h-4 w-4 animate-spin" />}
            {loading ? 'Creating account...' : t('register')}
          </button>

          <p className="text-center text-sm text-gray-400">
            Already registered?{' '}
            <Link to="/login" className="text-blue-400 hover:text-blue-300">
              {t('login')}
            </Link>
          </p>
        </form>
      )}
    </PageShell>
  )
}

// ── Login page ────────────────────────────────────────────────────────────────
export function LoginPage() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate   = useNavigate()

  const [identifier, setId] = useState('')
  const [password, setPw]   = useState('')
  const [loading, setLoading]= useState(false)
  const [error, setError]   = useState('')

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!identifier || !password) { setError('Please fill in all fields'); return }
    setLoading(true); setError('')
    try {
      const r = await fetch(API('user/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier, password }),
      })
      const data = await r.json()
      if (!r.ok) { setError(data.detail || 'Invalid credentials'); return }
      login(data.user, data.token)
      navigate('/profile')
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageShell title="Login" back="/public">
      <form onSubmit={submit} className="space-y-4">
        {error && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <Input label="Email or Phone" value={identifier} onChange={setId}
               placeholder="your@email.com or +91..." icon={Mail} required />

        <Input label="Password" type="password" value={password} onChange={setPw}
               placeholder="Your password" required />

        <button type="submit" disabled={loading}
                className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700
                           disabled:opacity-50 text-white font-semibold text-sm
                           transition-colors flex items-center justify-center gap-2">
          {loading && <RefreshCw className="h-4 w-4 animate-spin" />}
          {loading ? 'Logging in...' : t('login')}
        </button>

        <p className="text-center text-sm text-gray-400">
          New user?{' '}
          <Link to="/register" className="text-blue-400 hover:text-blue-300">
            {t('register')}
          </Link>
        </p>
      </form>
    </PageShell>
  )
}

// ── Profile / Preferences page ────────────────────────────────────────────────
export function ProfilePage() {
  const { user, token, logout } = useAuth()
  const { lang, setLang }    = useTranslation()
  const navigate = useNavigate()

  const [district, setDist]   = useState(user?.home_district || '')
  const [threshold, setThresh]= useState(user?.alert_threshold || 'HIGH')
  const [sms, setSms]         = useState(!!user?.alert_sms)
  const [email, setEmail]     = useState(!!user?.alert_email)
  const [wa, setWa]           = useState(!!user?.alert_whatsapp)
  const [saving, setSaving]   = useState(false)
  const [saved, setSaved]     = useState(false)

  useEffect(() => {
    if (!user) navigate('/login')
  }, [user, navigate])

  const save = async () => {
    if (!token) return
    setSaving(true)
    try {
      await fetch(API('user/preferences'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          home_district: district || null,
          language: lang,
          alert_threshold: threshold,
          alert_sms: sms, alert_email: email, alert_whatsapp: wa,
        }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {} finally { setSaving(false) }
  }

  if (!user) return null

  return (
    <PageShell title="My Profile" back="/public">
      <div className="space-y-6">

        {/* User card */}
        <div className="rounded-2xl bg-gray-800/60 border border-gray-700/50 p-4
                        flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-blue-600/20 border border-blue-500/30
                          flex items-center justify-center text-xl font-bold text-blue-400">
            {user.name[0]?.toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-white truncate">{user.name}</p>
            <p className="text-xs text-gray-400 truncate">{user.email || user.phone}</p>
          </div>
          <Link to="/alerts"
                className="relative p-2 rounded-lg hover:bg-gray-700 text-gray-400">
            <Bell className="h-5 w-5" />
            {(user.unread_alerts || 0) > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500
                               text-white text-xs flex items-center justify-center">
                {user.unread_alerts}
              </span>
            )}
          </Link>
        </div>

        {/* Preferences */}
        <div className="space-y-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide flex items-center gap-2">
            <Settings className="h-3.5 w-3.5" /> Preferences
          </h3>

          <Input label="Home District" value={district} onChange={setDist}
                 placeholder="e.g. Patna, Guwahati" icon={MapPin} />

          {/* Language */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">
              Language
            </label>
            <div className="grid grid-cols-3 gap-1.5">
              {[
                { code: 'en', label: 'English' }, { code: 'hi', label: 'हिन्दी' },
                { code: 'bn', label: 'বাংলা' },   { code: 'or', label: 'ଓଡ଼ିଆ' },
                { code: 'as', label: 'অসমীয়া' }, { code: 'te', label: 'తెలుగు' },
                { code: 'ta', label: 'தமிழ்' },   { code: 'mr', label: 'मराठी' },
                { code: 'gu', label: 'ગુજરાતી' },
              ].map(l => (
                <button key={l.code} type="button" onClick={() => setLang(l.code)}
                        className={`py-2 rounded-xl text-xs font-medium border transition-colors
                                   ${lang === l.code
                                     ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                                     : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* Alert threshold */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">
              Alert when risk is
            </label>
            <div className="grid grid-cols-3 gap-2">
              {['MODERATE', 'HIGH', 'CRITICAL'].map(level => (
                <button key={level} type="button" onClick={() => setThresh(level)}
                        className={`py-2.5 rounded-xl text-xs font-medium border transition-colors
                                   ${threshold === level
                                     ? 'bg-orange-600/20 border-orange-500 text-orange-300'
                                     : 'bg-gray-800 border-gray-600 text-gray-400 hover:border-gray-500'}`}>
                  {level}+
                </button>
              ))}
            </div>
          </div>

          {/* Alert channels */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">
              Alert Channels
            </label>
            {[
              { label: 'SMS', value: sms, set: setSms },
              { label: 'Email', value: email, set: setEmail },
              { label: 'WhatsApp', value: wa, set: setWa },
            ].map(({ label, value, set }) => (
              <div key={label}
                   className="flex items-center justify-between py-2.5 px-3
                              rounded-xl bg-gray-800 border border-gray-700">
                <span className="text-sm text-gray-200">{label}</span>
                <button type="button" onClick={() => set(!value)}
                        className={`w-10 h-6 rounded-full transition-colors relative
                                   ${value ? 'bg-blue-600' : 'bg-gray-600'}`}>
                  <span className={`absolute top-1 w-4 h-4 bg-white rounded-full
                                   transition-transform ${value ? 'translate-x-5' : 'translate-x-1'}`} />
                </button>
              </div>
            ))}
          </div>

          {/* Save button */}
          <button onClick={save} disabled={saving}
                  className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700
                             disabled:opacity-50 text-white font-semibold text-sm
                             transition-colors flex items-center justify-center gap-2">
            {saving
              ? <><RefreshCw className="h-4 w-4 animate-spin" /> Saving...</>
              : saved
              ? <><Check className="h-4 w-4" /> Saved!</>
              : 'Save Preferences'}
          </button>
        </div>

        {/* Nav links */}
        <div className="space-y-2">
          <Link to="/alerts"
                className="flex items-center justify-between w-full px-4 py-3 rounded-xl
                           bg-gray-800/60 border border-gray-700/50 hover:bg-gray-700/60 transition-colors">
            <div className="flex items-center gap-2 text-sm text-gray-200">
              <Bell className="h-4 w-4 text-blue-400" />
              My Alert History
            </div>
            {(user.unread_alerts || 0) > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-red-500 text-white text-xs font-bold">
                {user.unread_alerts} new
              </span>
            )}
          </Link>

          <button onClick={() => { logout(); navigate('/public') }}
                  className="flex items-center gap-2 w-full px-4 py-3 rounded-xl
                             bg-gray-800/60 border border-gray-700/50 hover:bg-red-900/30
                             hover:border-red-800 text-sm text-gray-400 hover:text-red-400 transition-colors">
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      </div>
    </PageShell>
  )
}

// ── Alert history page ────────────────────────────────────────────────────────
export function AlertHistoryPage() {
  const { user, token } = useAuth()
  const navigate = useNavigate()

  const [alerts, setAlerts]   = useState<any[]>([])
  const [unread, setUnread]   = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user || !token) { navigate('/login'); return }
    fetch(API('user/alerts'), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(d => { setAlerts(d.alerts || []); setUnread(d.unread || 0) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [user, token, navigate])

  const ack = async (id: number) => {
    if (!token) return
    await fetch(API(`user/alerts/${id}/acknowledge`), {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, is_read: 1 } : a))
    setUnread(u => Math.max(0, u - 1))
  }

  const sevColor: Record<string, string> = {
    CRITICAL: 'text-red-400 border-red-500/30 bg-red-500/10',
    HIGH:     'text-orange-400 border-orange-500/30 bg-orange-500/10',
    MODERATE: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10',
    LOW:      'text-green-400 border-green-500/30 bg-green-500/10',
  }

  return (
    <PageShell title={`My Alerts ${unread > 0 ? `(${unread} new)` : ''}`} back="/profile">
      {loading ? (
        <div className="text-center py-16 text-gray-500 text-sm animate-pulse">
          Loading alerts...
        </div>
      ) : alerts.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <Bell className="h-12 w-12 text-gray-700 mx-auto" />
          <p className="text-gray-500 text-sm">No alerts yet.</p>
          <p className="text-gray-600 text-xs">
            You'll receive alerts here when flood risk exceeds your threshold in your district.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map(a => (
            <div key={a.id}
                 className={`rounded-2xl border p-4 space-y-2 transition-opacity
                            ${a.is_read ? 'opacity-60' : 'opacity-100'}
                            ${sevColor[a.severity] || 'text-gray-300 border-gray-700 bg-gray-800/50'}`}>

              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  <span className="text-sm font-semibold">{a.alert_type}</span>
                </div>
                <span className="text-xs opacity-70 flex-shrink-0">
                  {a.severity}
                </span>
              </div>

              <p className="text-sm text-gray-200 leading-relaxed">{a.message}</p>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs opacity-60">
                  <Clock className="h-3 w-3" />
                  {a.district && <span className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" />{a.district}
                  </span>}
                  <span>{new Date(a.sent_at).toLocaleString()}</span>
                </div>

                {!a.is_read && (
                  <button onClick={() => ack(a.id)}
                          className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg
                                     bg-black/20 hover:bg-black/40 transition-colors">
                    <Check className="h-3 w-3" /> Mark read
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  )
}
