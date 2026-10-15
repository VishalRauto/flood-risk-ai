'use client'

/**
 * UserAuth.tsx — Premium Authentication & Profile System
 *
 * Inspired by reference image 4: split layout with 3D visual right panel
 * Dark midnight-navy background, cyan accent, clean forms
 *
 * Exports:
 *   AuthProvider  — context provider (wrap app root)
 *   useAuth       — hook to access auth state
 *   RegisterPage  — /register
 *   LoginPage     — /login
 *   ProfilePage   — /profile
 *   AlertHistoryPage — /alerts
 */

import { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Eye, EyeOff, RefreshCw, Check,
  Bell, User, LogOut, Settings, Clock, MapPin, Phone, Mail,
  Shield, LogIn,
  LayoutDashboard, Sparkles
} from 'lucide-react'
import '@/styles/design-system.css'

const API = (p: string) => `/api/${p}`
const H   = { 'Content-Type': 'application/json' }

// ── Auth context ──────────────────────────────────────────────────────────────
interface AuthUser {
  id: number; name: string; email?: string; phone?: string
  home_district?: string; home_state?: string; language: string
  alert_threshold: string; alert_sms: number; alert_email: number
  alert_whatsapp: number; unread_alerts?: number
}
interface AuthCtx {
  user: AuthUser | null; token: string | null
  login: (u: AuthUser, t: string) => void; logout: () => void
}
const AuthContext = createContext<AuthCtx>({ user: null, token: null, login: () => {}, logout: () => {} })

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user,  setUser]  = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    try {
      const saved = localStorage.getItem('flood_auth')
      if (saved) { const { user: u, token: t } = JSON.parse(saved); setUser(u); setToken(t) }
    } catch {}
  }, [])

  const login = useCallback((u: AuthUser, t: string) => {
    setUser(u); setToken(t)
    localStorage.setItem('flood_auth', JSON.stringify({ user: u, token: t }))
  }, [])

  const logout = useCallback(() => {
    if (token) fetch(API('user/logout'), { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(() => {})
    setUser(null); setToken(null); localStorage.removeItem('flood_auth')
  }, [token])

  return <AuthContext.Provider value={{ user, token, login, logout }}>{children}</AuthContext.Provider>
}
export const useAuth = () => useContext(AuthContext)

// ── 3D animated visual for right panel ───────────────────────────────────────
function AuthVisual() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return
    const ctx = canvas.getContext('2d')!
    let W = canvas.offsetWidth, H2 = canvas.offsetHeight
    canvas.width = W; canvas.height = H2
    const particles = Array.from({ length: 80 }, () => ({
      x: Math.random() * W, y: Math.random() * H2,
      r: Math.random() * 2.5 + 0.5,
      dx: (Math.random() - 0.5) * 0.5, dy: (Math.random() - 0.5) * 0.4,
      o: Math.random() * 0.5 + 0.1,
      c: Math.random() > 0.6 ? '#00D4FF' : Math.random() > 0.5 ? '#D4AF37' : '#00FFD1',
    }))
    let raf: number
    const draw = () => {
      ctx.clearRect(0, 0, W, H2)
      particles.forEach(p => {
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = p.c; ctx.globalAlpha = p.o; ctx.fill()
        p.x += p.dx; p.y += p.dy
        if (p.x < 0 || p.x > W) p.dx *= -1
        if (p.y < 0 || p.y > H2) p.dy *= -1
      })
      raf = requestAnimationFrame(draw)
    }
    draw()
    const onResize = () => { W = canvas.offsetWidth; H2 = canvas.offsetHeight; canvas.width = W; canvas.height = H2 }
    window.addEventListener('resize', onResize)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize) }
  }, [])

  return (
    <div style={{
      position: 'relative', overflow: 'hidden', height: '100%',
      background: 'linear-gradient(160deg, #020814 0%, #050A1C 40%, #0A1628 100%)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: 48,
    }}>
      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.6 }} />

      {/* Central 3D orb inspired by reference image */}
      <div style={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
          style={{
            width: 200, height: 200, borderRadius: '50%', margin: '0 auto 32px',
            background: 'conic-gradient(from 0deg, #00D4FF, #D4AF37, #00FFD1, #FF3B3B, #00D4FF)',
            padding: 4,
          }}
        >
          <motion.div
            animate={{ rotate: -360 }}
            transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
            style={{
              width: '100%', height: '100%', borderRadius: '50%',
              background: 'radial-gradient(circle at 35% 35%, rgba(0,212,255,0.4), rgba(5,10,28,0.95))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 64,
            }}
          >
            🌊
          </motion.div>
        </motion.div>

        <h2 style={{
          fontSize: 26, fontWeight: 900, marginBottom: 12,
          background: 'linear-gradient(135deg, #ffffff, #00D4FF)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          India Flood Intelligence
        </h2>
        <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.5)', lineHeight: 1.7, maxWidth: 280, margin: '0 auto 32px' }}>
          Real-time flood monitoring powered by AI across 45+ river sites and 8 major India basins
        </p>

        {/* Feature highlights */}
        {[
          { icon: '🎯', text: 'ML ensemble predictions (LSTM · GRU · Transformer)' },
          { icon: '📡', text: 'Live GloFAS + CWC + IMD data streams' },
          { icon: '🆘', text: 'Personalized district alerts + NDMA integration' },
          { icon: '🌐', text: '8 Indian languages · 15 citizen safety features' },
        ].map((f, i) => (
          <motion.div key={i}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 + i * 0.1 }}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10,
              padding: '8px 14px', borderRadius: 10,
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
              textAlign: 'left',
            }}
          >
            <span style={{ fontSize: 18 }}>{f.icon}</span>
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)' }}>{f.text}</span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

// ── Shared form input ─────────────────────────────────────────────────────────
function FormInput({
  label, type = 'text', value, onChange, placeholder, error, required, icon: Icon, hint
}: {
  label: string; type?: string; value: string; onChange: (v: string) => void
  placeholder?: string; error?: string; required?: boolean; icon?: any; hint?: string
}) {
  const [show, setShow] = useState(false)
  const inputType = type === 'password' ? (show ? 'text' : 'password') : type

  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'rgba(255,255,255,0.5)', marginBottom: 6 }}>
        {label}{required && <span style={{ color: '#FF6B6B', marginLeft: 3 }}>*</span>}
      </label>
      <div style={{ position: 'relative' }}>
        {Icon && <Icon style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', width: 15, height: 15, color: 'rgba(255,255,255,0.3)' }} />}
        <input
          type={inputType} value={value} onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          style={{
            width: '100%', padding: `11px ${type === 'password' ? '40px' : '14px'} 11px ${Icon ? '38px' : '14px'}`,
            borderRadius: 10, fontSize: 13, fontFamily: 'Inter, sans-serif',
            background: 'rgba(255,255,255,0.05)',
            border: `1px solid ${error ? 'rgba(255,59,59,0.5)' : 'rgba(255,255,255,0.1)'}`,
            color: 'white', outline: 'none', transition: 'all 0.2s', boxSizing: 'border-box',
          }}
          onFocus={e => { e.target.style.borderColor = error ? 'rgba(255,59,59,0.6)' : 'rgba(0,212,255,0.45)'; e.target.style.boxShadow = `0 0 0 3px ${error ? 'rgba(255,59,59,0.08)' : 'rgba(0,212,255,0.08)'}` }}
          onBlur={e => { e.target.style.borderColor = error ? 'rgba(255,59,59,0.5)' : 'rgba(255,255,255,0.1)'; e.target.style.boxShadow = 'none' }}
        />
        {type === 'password' && (
          <button type="button" onClick={() => setShow(s => !s)} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', padding: 0 }}>
            {show ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
          </button>
        )}
      </div>
      {error && <p style={{ fontSize: 11, color: '#FF6B6B', marginTop: 5 }}>⚠ {error}</p>}
      {hint && !error && <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginTop: 5 }}>{hint}</p>}
    </div>
  )
}

// ── Auth layout wrapper ───────────────────────────────────────────────────────
function AuthLayout({ children, showVisual = true }: { children: React.ReactNode; showVisual?: boolean }) {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      background: 'linear-gradient(135deg, #020814 0%, #050A1C 100%)',
      fontFamily: 'Inter, -apple-system, sans-serif',
    }}>
      {/* Left: Form */}
      <div style={{
        flex: showVisual ? '0 0 480px' : '1',
        maxWidth: showVisual ? 480 : '100%',
        display: 'flex', flexDirection: 'column',
        borderRight: showVisual ? '1px solid rgba(255,255,255,0.07)' : 'none',
      }}>
        {/* Mini header */}
        <div style={{ padding: '20px 32px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
            <span style={{ fontSize: 20 }}>🌊</span>
            <span style={{ fontSize: 14, fontWeight: 800, color: '#00D4FF' }}>Flood Intelligence</span>
          </Link>
          <div style={{ display: 'flex', gap: 6 }}>
            <Link to="/"        style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', textDecoration: 'none', padding: '5px 10px', borderRadius: 6, transition: 'all 0.15s' }}>Dashboard</Link>
            <Link to="/public"  style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', textDecoration: 'none', padding: '5px 10px', borderRadius: 6, transition: 'all 0.15s' }}>Public Portal</Link>
          </div>
        </div>
        {/* Form content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '32px 40px', overflowY: 'auto' }}>
          {children}
        </div>
      </div>

      {/* Right: Visual */}
      {showVisual && (
        <div style={{ flex: 1, display: 'none' }} className="auth-visual-panel">
          <AuthVisual />
        </div>
      )}

      <style>{`
        @media (min-width: 900px) {
          .auth-visual-panel { display: block !important; }
        }
        input:-webkit-autofill { -webkit-text-fill-color: white !important; caret-color: white; }
        input:-webkit-autofill, input:-webkit-autofill:hover, input:-webkit-autofill:focus {
          -webkit-box-shadow: 0 0 0 1000px rgba(10,22,40,0.9) inset !important;
          border-color: rgba(0,212,255,0.3) !important;
        }
      `}</style>
    </div>
  )
}

// ── Register Page ─────────────────────────────────────────────────────────────
export function RegisterPage() {
  const navigate   = useNavigate()

  const [step,    setStep]    = useState<1 | 2>(1)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [errors,  setErrors]  = useState<Record<string, string>>({})

  // Step 1 fields
  const [name,      setName]      = useState('')
  const [email,     setEmail]     = useState('')
  const [phone,     setPhone]     = useState('')
  const [password,  setPassword]  = useState('')
  const [confirm,   setConfirm]   = useState('')
  const [consent,   setConsent]   = useState(false)
  // Step 2 fields
  const [district,  setDistrict]  = useState('')
  const [state,     setState_]    = useState('')
  const [lang,      setLang_]     = useState('en')
  const [threshold, setThreshold] = useState('HIGH')

  const INDIA_STATES = ['Assam','Bihar','West Bengal','Odisha','Andhra Pradesh','Telangana','Maharashtra','Gujarat','Tamil Nadu','Karnataka','Kerala','Madhya Pradesh','Uttar Pradesh','Rajasthan','Punjab','Haryana','Jharkhand','Chhattisgarh','Uttarakhand','Himachal Pradesh','Jammu & Kashmir','Manipur','Meghalaya','Nagaland','Mizoram','Tripura','Sikkim','Arunachal Pradesh','Goa']

  // Password strength
  const pwStrength = password.length === 0 ? 0 : password.length < 6 ? 1 : password.length < 10 ? 2 : /[A-Z]/.test(password) && /[0-9]/.test(password) ? 4 : 3
  const pwColors   = ['','#FF3B3B','#FF8C00','#FFD600','#00E676']
  const pwLabels   = ['','Weak','Fair','Good','Strong']

  const validateStep1 = () => {
    const e: Record<string, string> = {}
    if (!name.trim())              e.name     = 'Full name is required'
    if (!email && !phone)          e.email    = 'Email or phone number is required'
    if (email && !/\S+@\S+\.\S+/.test(email)) e.email = 'Enter a valid email address'
    if (password.length < 6)       e.password = 'Password must be at least 6 characters'
    if (password !== confirm)      e.confirm  = 'Passwords do not match'
    if (!consent)                  e.consent  = 'You must agree to the privacy notice'
    setErrors(e); return Object.keys(e).length === 0
  }

  const validateStep2 = () => {
    const e: Record<string, string> = {}
    if (!state)    e.state    = 'Please select your state'
    if (!district) e.district = 'Please enter your district'
    setErrors(e); return Object.keys(e).length === 0
  }

  const handleStep1 = (ev: React.FormEvent) => {
    ev.preventDefault()
    if (validateStep1()) setStep(2)
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!validateStep2()) return
    setLoading(true)
    try {
      const r = await fetch(API('user/register'), {
        method: 'POST', headers: H,
        body: JSON.stringify({
          name, email: email || undefined, phone: phone || undefined,
          password, home_district: district, home_state: state,
          language: lang, alert_threshold: threshold,
        }),
      })
      const d = await r.json()
      if (!r.ok) { setErrors({ form: d.detail || 'Registration failed. Please try again.' }); return }
      setSuccess(true)
      setTimeout(() => navigate('/login'), 2200)
    } catch {
      setErrors({ form: 'Network error. Please check your connection.' })
    } finally { setLoading(false) }
  }

  return (
    <AuthLayout>
      {success ? (
        <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} style={{ textAlign: 'center', padding: '40px 0' }}>
          <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ duration: 0.5 }} style={{ fontSize: 72, marginBottom: 20 }}>✅</motion.div>
          <h2 style={{ fontSize: 24, fontWeight: 900, color: '#00E676', marginBottom: 8 }}>Account Created!</h2>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14 }}>Redirecting to login...</p>
        </motion.div>
      ) : (
        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.25 }}>
            {/* Step indicator */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 28 }}>
              {[1, 2].map(s => (
                <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 700,
                    background: step >= s ? 'linear-gradient(135deg, #00D4FF, #0099BB)' : 'rgba(255,255,255,0.08)',
                    color: step >= s ? '#050A1C' : 'rgba(255,255,255,0.35)',
                    border: `2px solid ${step >= s ? '#00D4FF' : 'rgba(255,255,255,0.12)'}`,
                  }}>
                    {step > s ? <Check style={{ width: 12, height: 12 }} /> : s}
                  </div>
                  <span style={{ fontSize: 11, color: step >= s ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.3)' }}>
                    {s === 1 ? 'Account' : 'Preferences'}
                  </span>
                  {s < 2 && <div style={{ width: 40, height: 1, background: step > s ? '#00D4FF' : 'rgba(255,255,255,0.12)', marginLeft: 4 }} />}
                </div>
              ))}
            </div>

            <h1 style={{ fontSize: 26, fontWeight: 900, color: 'white', marginBottom: 6 }}>
              {step === 1 ? 'Create your account' : 'Set your preferences'}
            </h1>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', marginBottom: 28 }}>
              {step === 1 ? 'Get personalized flood alerts for your district' : 'Customize alerts for your location and language'}
            </p>

            {errors.form && (
              <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
                style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(255,59,59,0.1)', border: '1px solid rgba(255,59,59,0.3)', color: '#FF6B6B', fontSize: 13, marginBottom: 16 }}>
                ⚠ {errors.form}
              </motion.div>
            )}

            {step === 1 ? (
              <form onSubmit={handleStep1}>
                <FormInput label="Full Name" value={name} onChange={setName} placeholder="Your full name" icon={User} required error={errors.name} />
                <FormInput label="Email Address" type="email" value={email} onChange={setEmail} placeholder="your@email.com" icon={Mail} error={errors.email} hint="Or use a phone number below" />
                <FormInput label="Phone Number (optional)" type="tel" value={phone} onChange={setPhone} placeholder="+91 98765 43210" icon={Phone} />
                <FormInput label="Password" type="password" value={password} onChange={setPassword} placeholder="Create a strong password" required error={errors.password} />

                {/* Password strength */}
                {password.length > 0 && (
                  <div style={{ marginTop: -10, marginBottom: 16 }}>
                    <div style={{ display: 'flex', gap: 3, marginBottom: 4 }}>
                      {[1,2,3,4].map(i => (
                        <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: pwStrength >= i ? pwColors[pwStrength] : 'rgba(255,255,255,0.1)', transition: 'background 0.3s' }} />
                      ))}
                    </div>
                    <span style={{ fontSize: 10, color: pwColors[pwStrength] }}>{pwLabels[pwStrength]} password</span>
                  </div>
                )}

                <FormInput label="Confirm Password" type="password" value={confirm} onChange={setConfirm} placeholder="Repeat your password" required error={errors.confirm} />

                {/* Consent */}
                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer', marginBottom: 24 }}>
                  <div onClick={() => setConsent(!consent)} style={{
                    width: 18, height: 18, borderRadius: 5, flexShrink: 0, marginTop: 1,
                    background: consent ? '#00D4FF' : 'rgba(255,255,255,0.08)',
                    border: `2px solid ${consent ? '#00D4FF' : errors.consent ? 'rgba(255,59,59,0.5)' : 'rgba(255,255,255,0.2)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', transition: 'all 0.2s',
                  }}>
                    {consent && <Check style={{ width: 11, height: 11, color: '#050A1C' }} />}
                  </div>
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', lineHeight: 1.5 }}>
                    I agree to the <a href="#" style={{ color: '#00D4FF' }}>Privacy Notice</a>. My location and contact data will only be used for flood alert delivery.
                    {errors.consent && <span style={{ display: 'block', color: '#FF6B6B', marginTop: 3 }}>⚠ {errors.consent}</span>}
                  </span>
                </label>

                <button type="submit" style={{
                  width: '100%', padding: '13px 0', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  cursor: 'pointer', border: 'none', transition: 'all 0.2s',
                  background: 'linear-gradient(135deg, #00D4FF, #0099BB)',
                  color: '#050A1C', boxShadow: '0 4px 20px rgba(0,212,255,0.3)',
                }}>
                  Continue →
                </button>

                <p style={{ textAlign: 'center', fontSize: 13, color: 'rgba(255,255,255,0.4)', marginTop: 20 }}>
                  Already have an account?{' '}
                  <Link to="/login" style={{ color: '#00D4FF', fontWeight: 600, textDecoration: 'none' }}>Log in</Link>
                </p>
              </form>
            ) : (
              <form onSubmit={handleSubmit}>
                {/* State selector */}
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'rgba(255,255,255,0.5)', marginBottom: 6 }}>
                    Home State <span style={{ color: '#FF6B6B' }}>*</span>
                  </label>
                  <select value={state} onChange={e => setState_(e.target.value)} style={{
                    width: '100%', padding: '11px 14px', borderRadius: 10, fontSize: 13,
                    background: 'rgba(255,255,255,0.05)', border: `1px solid ${errors.state ? 'rgba(255,59,59,0.5)' : 'rgba(255,255,255,0.1)'}`,
                    color: state ? 'white' : 'rgba(255,255,255,0.35)', outline: 'none', boxSizing: 'border-box',
                    fontFamily: 'Inter, sans-serif',
                  }}>
                    <option value="" style={{ background: '#0A1628' }}>Select your state</option>
                    {INDIA_STATES.map(s => <option key={s} value={s} style={{ background: '#0A1628' }}>{s}</option>)}
                  </select>
                  {errors.state && <p style={{ fontSize: 11, color: '#FF6B6B', marginTop: 5 }}>⚠ {errors.state}</p>}
                </div>

                <FormInput label="Home District" value={district} onChange={setDistrict} placeholder="e.g. Patna, Guwahati, Cuttack" icon={MapPin} required error={errors.district} />

                {/* Language */}
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>
                    Preferred Language
                  </label>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
                    {[
                      { code:'en',label:'English'  }, { code:'hi',label:'हिन्दी'   }, { code:'bn',label:'বাংলা'   },
                      { code:'or',label:'ଓଡ଼ିଆ'      }, { code:'as',label:'অসমীয়া'  }, { code:'te',label:'తెలుగు'  },
                      { code:'ta',label:'தமிழ்'      }, { code:'mr',label:'मराठी'    }, { code:'gu',label:'ગુજরાતી' },
                    ].map(l => (
                      <button key={l.code} type="button" onClick={() => setLang_(l.code)}
                        style={{
                          padding: '8px 6px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                          border: `1px solid ${lang === l.code ? 'rgba(0,212,255,0.4)' : 'rgba(255,255,255,0.1)'}`,
                          background: lang === l.code ? 'rgba(0,212,255,0.12)' : 'rgba(255,255,255,0.04)',
                          color: lang === l.code ? '#00D4FF' : 'rgba(255,255,255,0.6)',
                          transition: 'all 0.15s',
                        }}>
                        {l.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Alert threshold */}
                <div style={{ marginBottom: 24 }}>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>
                    Alert Sensitivity — notify me when risk is
                  </label>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
                    {[
                      { value: 'MODERATE', label: 'Moderate+', color: '#FFD600' },
                      { value: 'HIGH',     label: 'High+',     color: '#FF8C00' },
                      { value: 'CRITICAL', label: 'Critical',  color: '#FF3B3B' },
                    ].map(t => (
                      <button key={t.value} type="button" onClick={() => setThreshold(t.value)}
                        style={{
                          padding: '10px 8px', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                          border: `1px solid ${threshold === t.value ? t.color + '60' : 'rgba(255,255,255,0.1)'}`,
                          background: threshold === t.value ? t.color + '18' : 'rgba(255,255,255,0.04)',
                          color: threshold === t.value ? t.color : 'rgba(255,255,255,0.5)',
                          transition: 'all 0.15s',
                        }}>
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button type="button" onClick={() => setStep(1)} style={{
                    flex: '0 0 44px', height: 46, borderRadius: 12, cursor: 'pointer', border: '1px solid rgba(255,255,255,0.15)',
                    background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    ←
                  </button>
                  <button type="submit" disabled={loading} style={{
                    flex: 1, padding: '13px 0', borderRadius: 12, fontSize: 14, fontWeight: 700,
                    cursor: loading ? 'not-allowed' : 'pointer', border: 'none', transition: 'all 0.2s',
                    background: 'linear-gradient(135deg, #D4AF37, #A67C1C)', color: '#050A1C',
                    boxShadow: '0 4px 20px rgba(212,175,55,0.3)', opacity: loading ? 0.7 : 1,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  }}>
                    {loading ? <><RefreshCw style={{ width: 15, height: 15, animation: 'spin 1s linear infinite' }} /> Creating account...</> : '🎉 Create Account'}
                  </button>
                </div>
              </form>
            )}
          </motion.div>
        </AnimatePresence>
      )}
    </AuthLayout>
  )
}

// ── Login Page ────────────────────────────────────────────────────────────────
export function LoginPage() {
  const { login } = useAuth()
  const navigate   = useNavigate()

  const [identifier, setIdentifier] = useState('')
  const [password,   setPassword]   = useState('')
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState('')

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!identifier || !password) { setError('Please fill in all fields'); return }
    setLoading(true); setError('')
    try {
      const r = await fetch(API('user/login'), {
        method: 'POST', headers: H,
        body: JSON.stringify({ identifier, password }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || 'Invalid credentials. Please try again.'); return }
      login(d.user, d.token)
      navigate('/profile')
    } catch { setError('Network error. Please check your connection.') }
    finally { setLoading(false) }
  }

  return (
    <AuthLayout>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 900, color: 'white', marginBottom: 8 }}>Welcome back</h1>
        <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.45)' }}>
          Sign in to manage your flood alerts and preferences
        </p>
      </div>

      {error && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
          style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(255,59,59,0.1)', border: '1px solid rgba(255,59,59,0.3)', color: '#FF6B6B', fontSize: 13, marginBottom: 16 }}>
          ⚠ {error}
        </motion.div>
      )}

      <form onSubmit={handleSubmit}>
        <FormInput label="Email or Phone Number" value={identifier} onChange={setIdentifier}
          placeholder="your@email.com or +91..." icon={Mail} required />
        <FormInput label="Password" type="password" value={password} onChange={setPassword}
          placeholder="Your password" required />

        <button type="submit" disabled={loading} style={{
          width: '100%', padding: '13px 0', borderRadius: 12, fontSize: 14, fontWeight: 700, marginTop: 8,
          cursor: loading ? 'not-allowed' : 'pointer', border: 'none', transition: 'all 0.2s',
          background: 'linear-gradient(135deg, #00D4FF, #0099BB)', color: '#050A1C',
          boxShadow: '0 4px 20px rgba(0,212,255,0.3)', opacity: loading ? 0.7 : 1,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          {loading ? <><RefreshCw style={{ width: 15, height: 15, animation: 'spin 1s linear infinite' }} /> Signing in...</> : <><LogIn style={{ width: 15, height: 15 }} /> Sign In</>}
        </button>
      </form>

      {/* Divider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '24px 0' }}>
        <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.08)' }} />
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)' }}>or</span>
        <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.08)' }} />
      </div>

      {/* Quick access without account */}
      <Link to="/public" style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        padding: '12px 0', borderRadius: 12, fontSize: 13, fontWeight: 600,
        textDecoration: 'none', color: 'rgba(255,255,255,0.65)',
        border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)',
        transition: 'all 0.2s',
      }}>
        <Shield style={{ width: 15, height: 15 }} />
        Check flood risk without an account
      </Link>

      <p style={{ textAlign: 'center', fontSize: 13, color: 'rgba(255,255,255,0.4)', marginTop: 24 }}>
        Don't have an account?{' '}
        <Link to="/register" style={{ color: '#D4AF37', fontWeight: 600, textDecoration: 'none' }}>
          Create one free
        </Link>
      </p>

      {/* Navigation links */}
      <div style={{ marginTop: 32, paddingTop: 24, borderTop: '1px solid rgba(255,255,255,0.07)', display: 'flex', justifyContent: 'center', gap: 20 }}>
        {[
          { icon: LayoutDashboard, label: 'Dashboard',   href: '/' },
          { icon: Sparkles,        label: '3D View',      href: '/luxury' },
          { icon: Shield,          label: 'Public Portal',href: '/public' },
        ].map(l => (
          <Link key={l.href} to={l.href} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, textDecoration: 'none', color: 'rgba(255,255,255,0.35)', fontSize: 10, fontWeight: 600, transition: 'all 0.15s' }}>
            <l.icon style={{ width: 16, height: 16 }} />
            {l.label}
          </Link>
        ))}
      </div>
    </AuthLayout>
  )
}

// ── Profile Page ──────────────────────────────────────────────────────────────
export function ProfilePage() {
  const { user, token, logout } = useAuth()
  const navigate = useNavigate()

  const [district,  setDistrict]  = useState('')
  const [state_,    setState_]    = useState('')
  const [lang_,     setLang_]     = useState('en')
  const [threshold, setThreshold] = useState('HIGH')
  const [sms,       setSms]       = useState(true)
  const [email_,    setEmail_]    = useState(true)
  const [wa,        setWa]        = useState(false)
  const [saving,    setSaving]    = useState(false)
  const [saved,     setSaved]     = useState(false)

  useEffect(() => {
    if (!user) { navigate('/login'); return }
    setDistrict(user.home_district || '')
    setState_(user.home_state || '')
    setLang_(user.language || 'en')
    setThreshold(user.alert_threshold || 'HIGH')
    setSms(!!user.alert_sms); setEmail_(!!user.alert_email); setWa(!!user.alert_whatsapp)
  }, [user, navigate])

  if (!user) return null

  const savePrefs = async () => {
    if (!token) return
    setSaving(true)
    try {
      await fetch(API('user/preferences'), {
        method: 'PUT',
        headers: { ...H, Authorization: `Bearer ${token}` },
        body: JSON.stringify({ home_district: district, home_state: state_, language: lang_, alert_threshold: threshold, alert_sms: sms, alert_email: email_, alert_whatsapp: wa }),
      })
      setSaved(true); setTimeout(() => setSaved(false), 2500)
    } catch {} finally { setSaving(false) }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #020814 0%, #050A1C 100%)', fontFamily: 'Inter, sans-serif', color: 'white' }}>
      {/* Header */}
      <div style={{ padding: '16px 24px', borderBottom: '1px solid rgba(255,255,255,0.07)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
          <span style={{ fontSize: 20 }}>🌊</span>
          <span style={{ fontSize: 14, fontWeight: 800, color: '#00D4FF' }}>Flood Intelligence</span>
        </Link>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/"       style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', textDecoration: 'none', padding: '5px 10px', borderRadius: 6 }}>Dashboard</Link>
          <Link to="/public" style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', textDecoration: 'none', padding: '5px 10px', borderRadius: 6 }}>Public Portal</Link>
          <Link to="/alerts" style={{ fontSize: 11, color: '#00D4FF', textDecoration: 'none', padding: '5px 10px', borderRadius: 6 }}>My Alerts {(user.unread_alerts || 0) > 0 && `(${user.unread_alerts})`}</Link>
        </div>
      </div>

      <div style={{ maxWidth: 680, margin: '0 auto', padding: '32px 24px' }}>
        {/* User card */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          style={{ background: 'rgba(0,212,255,0.06)', border: '1px solid rgba(0,212,255,0.2)', borderRadius: 20, padding: 24, marginBottom: 24, display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{
            width: 64, height: 64, borderRadius: '50%',
            background: 'linear-gradient(135deg, #00D4FF, #0099BB)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 28, fontWeight: 900, color: '#050A1C', flexShrink: 0,
          }}>
            {user.name?.[0]?.toUpperCase() || '?'}
          </div>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: 20, fontWeight: 900, color: 'white', margin: 0 }}>{user.name}</h2>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', margin: '4px 0 0' }}>{user.email || user.phone}</p>
            {user.home_district && <p style={{ fontSize: 12, color: '#00D4FF', margin: '2px 0 0' }}>📍 {user.home_district}{user.home_state ? `, ${user.home_state}` : ''}</p>}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Link to="/alerts" style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10,
              background: (user.unread_alerts || 0) > 0 ? 'rgba(255,59,59,0.15)' : 'rgba(255,255,255,0.06)',
              border: `1px solid ${(user.unread_alerts || 0) > 0 ? 'rgba(255,59,59,0.3)' : 'rgba(255,255,255,0.1)'}`,
              color: (user.unread_alerts || 0) > 0 ? '#FF6B6B' : 'rgba(255,255,255,0.6)',
              textDecoration: 'none', fontSize: 12, fontWeight: 600,
            }}>
              <Bell style={{ width: 13, height: 13 }} />
              {(user.unread_alerts || 0) > 0 ? `${user.unread_alerts} new` : 'Alerts'}
            </Link>
          </div>
        </motion.div>

        {/* Preferences */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, padding: 24, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.6)', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: 20 }}>
            ⚙️ Alert Preferences
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <FormInput label="Home District" value={district} onChange={setDistrict} placeholder="Patna, Guwahati..." icon={MapPin} />
            <div>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'rgba(255,255,255,0.5)', marginBottom: 6 }}>State</label>
              <input value={state_} onChange={e => setState_(e.target.value)} placeholder="Your state" style={{
                width: '100%', padding: '11px 14px', borderRadius: 10, fontSize: 13,
                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                color: 'white', outline: 'none', boxSizing: 'border-box', fontFamily: 'Inter, sans-serif',
              }} />
            </div>
          </div>

          {/* Alert threshold */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>
              Alert Sensitivity
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              {[{ v:'MODERATE',l:'Moderate+',c:'#FFD600'},{v:'HIGH',l:'High+',c:'#FF8C00'},{v:'CRITICAL',l:'Critical only',c:'#FF3B3B'}].map(t => (
                <button key={t.v} type="button" onClick={() => setThreshold(t.v)} style={{
                  flex: 1, padding: '9px 0', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  border: `1px solid ${threshold === t.v ? t.c + '50' : 'rgba(255,255,255,0.1)'}`,
                  background: threshold === t.v ? t.c + '14' : 'rgba(255,255,255,0.04)',
                  color: threshold === t.v ? t.c : 'rgba(255,255,255,0.45)', transition: 'all 0.15s',
                }}>{t.l}</button>
              ))}
            </div>
          </div>

          {/* Notification channels */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>
              Notification Channels
            </label>
            {[
              { label: 'SMS Alerts',      value: sms,    set: setSms    },
              { label: 'Email Alerts',    value: email_,  set: setEmail_ },
              { label: 'WhatsApp Alerts', value: wa,     set: setWa     },
            ].map(ch => (
              <div key={ch.label} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 14px', borderRadius: 10, marginBottom: 6,
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
              }}>
                <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.75)' }}>{ch.label}</span>
                <button type="button" onClick={() => ch.set(!ch.value)} style={{
                  width: 42, height: 24, borderRadius: 12, cursor: 'pointer', border: 'none',
                  background: ch.value ? '#00D4FF' : 'rgba(255,255,255,0.15)', position: 'relative', transition: 'background 0.3s',
                }}>
                  <span style={{
                    position: 'absolute', top: 3, width: 18, height: 18, borderRadius: '50%',
                    background: 'white', transition: 'left 0.25s cubic-bezier(0.34,1.56,0.64,1)',
                    left: ch.value ? 21 : 3,
                  }} />
                </button>
              </div>
            ))}
          </div>

          <button onClick={savePrefs} disabled={saving} style={{
            width: '100%', padding: '12px 0', borderRadius: 12, fontSize: 14, fontWeight: 700,
            cursor: saving ? 'not-allowed' : 'pointer', border: 'none', transition: 'all 0.2s',
            background: saved ? 'linear-gradient(135deg,#00E676,#00B05A)' : 'linear-gradient(135deg,#D4AF37,#A67C1C)',
            color: '#050A1C', boxShadow: `0 4px 20px ${saved ? 'rgba(0,230,118,0.3)' : 'rgba(212,175,55,0.3)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
            {saving ? <><RefreshCw style={{ width: 15, height: 15, animation: 'spin 1s linear infinite' }} /> Saving...</>
              : saved ? <><Check style={{ width: 15, height: 15 }} /> Saved!</>
              : <><Settings style={{ width: 15, height: 15 }} /> Save Preferences</>}
          </button>
        </motion.div>

        {/* Sign out */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <button onClick={() => { logout(); navigate('/public') }} style={{
            width: '100%', padding: '12px 0', borderRadius: 12, fontSize: 13, fontWeight: 600,
            cursor: 'pointer', border: '1px solid rgba(255,59,59,0.25)',
            background: 'rgba(255,59,59,0.07)', color: '#FF6B6B',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'all 0.2s',
          }}>
            <LogOut style={{ width: 15, height: 15 }} /> Sign Out
          </button>
        </motion.div>
      </div>
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}

// ── Alert History Page ────────────────────────────────────────────────────────
export function AlertHistoryPage() {
  const { user, token } = useAuth()
  const navigate = useNavigate()

  const [alerts,  setAlerts]  = useState<any[]>([])
  const [unread,  setUnread]  = useState(0)
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState<'all' | 'unread'>('all')

  useEffect(() => {
    if (!user || !token) { navigate('/login'); return }
    fetch(API('user/alerts'), { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(d => { setAlerts(d.alerts || []); setUnread(d.unread || 0) })
      .catch(() => {}).finally(() => setLoading(false))
  }, [user, token, navigate])

  const ack = async (id: number) => {
    if (!token) return
    await fetch(API(`user/alerts/${id}/acknowledge`), { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, is_read: 1 } : a))
    setUnread(u => Math.max(0, u - 1))
  }

  const sevColor = (s: string) => s === 'CRITICAL' ? '#FF3B3B' : s === 'HIGH' ? '#FF8C00' : s === 'MODERATE' ? '#FFD600' : '#00E676'
  const filtered = filter === 'unread' ? alerts.filter(a => !a.is_read) : alerts

  if (!user) return null

  return (
    <div style={{ minHeight: '100vh', background: '#020814', fontFamily: 'Inter, sans-serif', color: 'white' }}>
      {/* Header */}
      <div style={{ padding: '16px 24px', borderBottom: '1px solid rgba(255,255,255,0.07)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'sticky', top: 0, background: 'rgba(2,8,20,0.95)', backdropFilter: 'blur(20px)', zIndex: 50 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Link to="/profile" style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'rgba(255,255,255,0.5)', textDecoration: 'none', fontSize: 13 }}>
            ← Profile
          </Link>
          <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.1)' }} />
          <h1 style={{ fontSize: 16, fontWeight: 800, color: 'white', margin: 0 }}>
            My Alerts {unread > 0 && <span style={{ fontSize: 12, padding: '2px 8px', borderRadius: 10, background: 'rgba(255,59,59,0.2)', color: '#FF6B6B', marginLeft: 6 }}>{unread} new</span>}
          </h1>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['all', 'unread'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{
              padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600,
              cursor: 'pointer', border: `1px solid ${filter === f ? 'rgba(0,212,255,0.35)' : 'rgba(255,255,255,0.1)'}`,
              background: filter === f ? 'rgba(0,212,255,0.12)' : 'rgba(255,255,255,0.04)',
              color: filter === f ? '#00D4FF' : 'rgba(255,255,255,0.5)', transition: 'all 0.15s',
            }}>
              {f === 'all' ? 'All' : `Unread (${unread})`}
            </button>
          ))}
        </div>
      </div>

      <div style={{ maxWidth: 680, margin: '0 auto', padding: '24px 20px' }}>
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1,2,3].map(i => <div key={i} style={{ height: 80, borderRadius: 14, background: 'rgba(255,255,255,0.04)', animation: 'shimmer 1.8s infinite' }} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <div style={{ fontSize: 56, marginBottom: 16 }}>🔔</div>
            <p style={{ fontSize: 16, fontWeight: 700, color: 'rgba(255,255,255,0.6)' }}>
              {filter === 'unread' ? 'All caught up!' : 'No alerts yet'}
            </p>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.35)', marginTop: 6 }}>
              {filter === 'unread' ? 'You have no unread alerts.' : 'Flood alerts for your district will appear here.'}
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {filtered.map((a, i) => (
              <motion.div key={a.id}
                initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
                style={{
                  padding: 16, borderRadius: 14,
                  background: a.is_read ? 'rgba(255,255,255,0.03)' : `${sevColor(a.severity)}0C`,
                  border: `1px solid ${a.is_read ? 'rgba(255,255,255,0.07)' : sevColor(a.severity) + '35'}`,
                  opacity: a.is_read ? 0.65 : 1, transition: 'all 0.3s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {!a.is_read && <div style={{ width: 7, height: 7, borderRadius: '50%', background: sevColor(a.severity), flexShrink: 0, boxShadow: `0 0 6px ${sevColor(a.severity)}` }} />}
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'white' }}>{a.alert_type || 'Flood Alert'}</span>
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 6, background: sevColor(a.severity) + '20', color: sevColor(a.severity) }}>
                    {a.severity}
                  </span>
                </div>
                <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', lineHeight: 1.5, marginBottom: 8 }}>{a.message?.slice(0, 120)}{(a.message?.length || 0) > 120 ? '...' : ''}</p>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: 10, fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>
                    {a.district && <span>📍 {a.district}</span>}
                    <span><Clock style={{ width: 10, height: 10, display: 'inline' }} /> {new Date(a.sent_at).toLocaleDateString()}</span>
                  </div>
                  {!a.is_read && (
                    <button onClick={() => ack(a.id)} style={{
                      fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 6,
                      background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)',
                      color: 'rgba(255,255,255,0.55)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
                    }}>
                      <Check style={{ width: 10, height: 10 }} /> Mark read
                    </button>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
      <style>{`@keyframes shimmer{0%{opacity:0.4}50%{opacity:0.8}100%{opacity:0.4}}`}</style>
    </div>
  )
}
