'use client'

/**
 * GlobalHeader.tsx — Shared header for all 4 websites
 *
 * Used by: MainDashboard, LuxuryDashboard, PublicPortal, Auth pages
 * Provides: consistent branding, cross-site navigation, auth state, language
 *
 * Props:
 *   variant: 'main' | 'luxury' | 'public' | 'auth'
 *   title?: override page title
 *   rightSlot?: extra content in right section
 */

import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@/pages/UserAuth'
import { useTranslation, SUPPORTED_LANGUAGES } from '@/hooks/useTranslation'
import {
  Menu, X, Bell, User, LogOut, Globe, ChevronDown,
  LayoutDashboard, Sparkles, Shield, UserCircle,
  LogIn, UserPlus, Phone
} from 'lucide-react'
import '@/styles/design-system.css'

interface GlobalHeaderProps {
  variant?: 'main' | 'luxury' | 'public' | 'auth'
  title?: string
  rightSlot?: React.ReactNode
  onMenuToggle?: () => void
}

// ── Nav items per variant ─────────────────────────────────────────────
const NAV_ITEMS = {
  main: [
    { label: '3D Experience', href: '/luxury',  icon: Sparkles,         highlight: 'gold'  },
    { label: 'Public Portal', href: '/public',  icon: Shield,           highlight: 'cyan'  },
  ],
  luxury: [
    { label: 'Full Dashboard',href: '/',        icon: LayoutDashboard,  highlight: 'cyan'  },
    { label: 'Public Portal', href: '/public',  icon: Shield,           highlight: 'cyan'  },
    { label: 'Research',      href: '/#research',icon: null,            highlight: null    },
  ],
  public: [
    { label: 'Full Dashboard',href: '/',        icon: LayoutDashboard,  highlight: 'cyan'  },
    { label: '3D Experience', href: '/luxury',  icon: Sparkles,         highlight: 'gold'  },
  ],
  auth: [
    { label: 'Dashboard',     href: '/',        icon: LayoutDashboard,  highlight: 'cyan'  },
    { label: 'Public Portal', href: '/public',  icon: Shield,           highlight: 'cyan'  },
  ],
}

export default function GlobalHeader({ variant = 'main', rightSlot }: GlobalHeaderProps) {
  const { user, logout } = useAuth()
  const { lang, setLang } = useTranslation()
  const navigate  = useNavigate()

  const [mobileOpen,  setMobileOpen]  = useState(false)
  const [langOpen,    setLangOpen]    = useState(false)
  const [userOpen,    setUserOpen]    = useState(false)
  const [scrolled,    setScrolled]    = useState(false)
  const langRef = useRef<HTMLDivElement>(null)
  const userRef = useRef<HTMLDivElement>(null)

  // Scroll detection for header shadow
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(e.target as Node)) setLangOpen(false)
      if (userRef.current && !userRef.current.contains(e.target as Node)) setUserOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/public')
    setUserOpen(false)
  }

  const navItems = NAV_ITEMS[variant] || NAV_ITEMS.main
  const isLuxury = variant === 'luxury'

  return (
    <>
      {/* ── Main Header ──────────────────────────────────────── */}
      <motion.header
        initial={{ y: -60, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.55, ease: [0.23, 1, 0.32, 1] }}
        style={{
          position: 'sticky', top: 0, zIndex: 400,
          background: scrolled
            ? 'rgba(5,10,28,0.96)'
            : isLuxury ? 'rgba(2,8,20,0.92)' : 'rgba(5,10,28,0.92)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          borderBottom: `1px solid ${isLuxury ? 'rgba(212,175,55,0.18)' : 'rgba(0,212,255,0.12)'}`,
          boxShadow: scrolled ? '0 4px 40px rgba(0,0,0,0.6)' : 'none',
          transition: 'all 0.3s ease',
        }}
      >
        <div style={{
          maxWidth: 1440, margin: '0 auto',
          padding: '0 20px',
          display: 'flex', alignItems: 'center',
          height: 60, gap: 16,
        }}>

          {/* ── Logo ─────────────────────────────────────────── */}
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none', flexShrink: 0 }}>
            <motion.div
              animate={{ rotate: [0, 5, -5, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
              style={{ fontSize: 26, lineHeight: 1 }}
            >
              🌊
            </motion.div>
            <div style={{ lineHeight: 1 }}>
              <div style={{
                fontSize: 15, fontWeight: 900, letterSpacing: '-0.3px',
                background: isLuxury
                  ? 'linear-gradient(135deg, #F5D06C, #D4AF37, #A67C1C)'
                  : 'linear-gradient(135deg, #ffffff, #00D4FF)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              }}>
                Flood Intelligence
              </div>
              <div style={{ fontSize: 9, color: 'rgba(0,212,255,0.65)', letterSpacing: '1.8px', textTransform: 'uppercase', marginTop: 1 }}>
                India · AI-Powered · Real-Time
              </div>
            </div>
          </Link>

          {/* ── Desktop nav links ─────────────────────────────── */}
          <nav className="ifi-hide-mobile" style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
            {navItems.map(item => (
              <Link key={item.href} to={item.href}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '6px 12px', borderRadius: 8,
                  fontSize: 13, fontWeight: 500, textDecoration: 'none',
                  color: item.highlight === 'gold' ? '#F5D06C'
                       : item.highlight === 'cyan' ? '#00D4FF'
                       : 'rgba(255,255,255,0.6)',
                  background: item.highlight === 'gold' ? 'rgba(212,175,55,0.08)'
                            : item.highlight === 'cyan' ? 'rgba(0,212,255,0.07)'
                            : 'transparent',
                  border: item.highlight === 'gold' ? '1px solid rgba(212,175,55,0.25)'
                        : item.highlight === 'cyan' ? '1px solid rgba(0,212,255,0.2)'
                        : 'none',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
              >
                {item.icon && <item.icon style={{ width: 13, height: 13 }} />}
                {item.label}
              </Link>
            ))}
          </nav>

          {/* ── Spacer ─────────────────────────────────────────── */}
          <div style={{ flex: 1 }} />

          {/* ── Right controls ───────────────────────────────── */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>

            {/* Right slot (optional) */}
            {rightSlot}

            {/* Language picker */}
            <div ref={langRef} style={{ position: 'relative' }}>
              <button
                onClick={() => setLangOpen(o => !o)}
                className="ifi-hide-mobile"
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '6px 10px', borderRadius: 8, cursor: 'pointer',
                  background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                  color: 'rgba(255,255,255,0.65)', fontSize: 12, fontWeight: 500,
                  transition: 'all 0.2s',
                }}
              >
                <Globe style={{ width: 13, height: 13 }} />
                {SUPPORTED_LANGUAGES.find(l => l.code === lang)?.native || 'EN'}
                <ChevronDown style={{ width: 11, height: 11, opacity: 0.6 }} />
              </button>
              <AnimatePresence>
                {langOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 6, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 4, scale: 0.97 }}
                    transition={{ duration: 0.18 }}
                    style={{
                      position: 'absolute', right: 0, top: 'calc(100% + 6px)',
                      background: 'rgba(10,22,40,0.98)', border: '1px solid rgba(0,212,255,0.18)',
                      borderRadius: 12, overflow: 'hidden', minWidth: 170, zIndex: 500,
                      boxShadow: '0 12px 40px rgba(0,0,0,0.5)', backdropFilter: 'blur(20px)',
                    }}
                  >
                    {SUPPORTED_LANGUAGES.map(l => (
                      <button key={l.code}
                        onClick={() => { setLang(l.code); setLangOpen(false) }}
                        style={{
                          width: '100%', display: 'flex', justifyContent: 'space-between',
                          alignItems: 'center', padding: '9px 14px', fontSize: 12,
                          fontWeight: 500, background: lang === l.code ? 'rgba(0,212,255,0.1)' : 'none',
                          color: lang === l.code ? '#00D4FF' : 'rgba(255,255,255,0.75)',
                          border: 'none', cursor: 'pointer', transition: 'all 0.15s',
                        }}
                        onMouseEnter={e => { if (lang !== l.code) e.currentTarget.style.background = 'rgba(255,255,255,0.05)' }}
                        onMouseLeave={e => { if (lang !== l.code) e.currentTarget.style.background = 'none' }}
                      >
                        <span>{l.native}</span>
                        <span style={{ fontSize: 10, opacity: 0.5 }}>{l.name}</span>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Auth controls */}
            {user ? (
              <div ref={userRef} style={{ position: 'relative' }}>
                <button
                  onClick={() => setUserOpen(o => !o)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 7,
                    padding: '6px 12px', borderRadius: 20, cursor: 'pointer',
                    background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.25)',
                    color: '#00D4FF', fontSize: 12, fontWeight: 600, transition: 'all 0.2s',
                  }}
                >
                  <UserCircle style={{ width: 14, height: 14 }} />
                  <span className="ifi-hide-mobile">{user.name?.split(' ')[0]}</span>
                  {(user.unread_alerts || 0) > 0 && (
                    <span style={{
                      width: 16, height: 16, borderRadius: '50%', background: 'var(--risk-critical)',
                      color: 'white', fontSize: 9, fontWeight: 900,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {user.unread_alerts}
                    </span>
                  )}
                </button>
                <AnimatePresence>
                  {userOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 6, scale: 0.97 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 4 }}
                      transition={{ duration: 0.18 }}
                      style={{
                        position: 'absolute', right: 0, top: 'calc(100% + 6px)',
                        background: 'rgba(10,22,40,0.98)', border: '1px solid rgba(0,212,255,0.18)',
                        borderRadius: 12, overflow: 'hidden', minWidth: 200, zIndex: 500,
                        boxShadow: '0 12px 40px rgba(0,0,0,0.5)', backdropFilter: 'blur(20px)',
                      }}
                    >
                      {/* User info */}
                      <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                        <p style={{ fontSize: 13, fontWeight: 700, color: 'white', margin: 0 }}>{user.name}</p>
                        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', margin: '2px 0 0' }}>
                          {user.email || user.phone}
                        </p>
                      </div>
                      {/* Menu items */}
                      {[
                        { icon: User,          label: 'My Profile',    href: '/profile'  },
                        { icon: Bell,          label: `Alerts ${(user.unread_alerts || 0) > 0 ? `(${user.unread_alerts} new)` : ''}`, href: '/alerts' },
                        { icon: Shield,        label: 'Public Portal', href: '/public'   },
                      ].map(item => (
                        <Link key={item.href} to={item.href}
                          onClick={() => setUserOpen(false)}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 9,
                            padding: '10px 14px', fontSize: 13, color: 'rgba(255,255,255,0.75)',
                            textDecoration: 'none', transition: 'all 0.15s',
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                          onMouseLeave={e => e.currentTarget.style.background = 'none'}
                        >
                          <item.icon style={{ width: 14, height: 14, opacity: 0.6 }} />
                          {item.label}
                        </Link>
                      ))}
                      <div style={{ borderTop: '1px solid rgba(255,255,255,0.07)', marginTop: 4 }}>
                        <button onClick={handleLogout}
                          style={{
                            width: '100%', display: 'flex', alignItems: 'center', gap: 9,
                            padding: '10px 14px', fontSize: 13, color: '#FF6B6B',
                            background: 'none', border: 'none', cursor: 'pointer', transition: 'all 0.15s',
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,59,59,0.07)'}
                          onMouseLeave={e => e.currentTarget.style.background = 'none'}
                        >
                          <LogOut style={{ width: 14, height: 14 }} /> Sign Out
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 6 }}>
                <Link to="/login" style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '6px 12px', borderRadius: 8,
                  fontSize: 12, fontWeight: 600, textDecoration: 'none',
                  color: 'rgba(255,255,255,0.65)', border: '1px solid rgba(255,255,255,0.12)',
                  transition: 'all 0.2s',
                }}>
                  <LogIn style={{ width: 13, height: 13 }} />
                  <span className="ifi-hide-mobile">Login</span>
                </Link>
                <Link to="/register" style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '6px 12px', borderRadius: 8,
                  fontSize: 12, fontWeight: 600, textDecoration: 'none',
                  background: 'linear-gradient(135deg, #D4AF37, #A67C1C)',
                  color: '#050A1C',
                  boxShadow: '0 2px 10px rgba(212,175,55,0.25)',
                  transition: 'all 0.2s',
                }}>
                  <UserPlus style={{ width: 13, height: 13 }} />
                  <span className="ifi-hide-mobile">Register</span>
                </Link>
              </div>
            )}

            {/* Mobile hamburger */}
            <button
              className="ifi-show-mobile-only"
              onClick={() => setMobileOpen(o => !o)}
              style={{
                padding: 8, borderRadius: 8, background: 'rgba(255,255,255,0.07)',
                border: '1px solid rgba(255,255,255,0.1)', color: 'white',
                cursor: 'pointer', display: 'flex', alignItems: 'center',
              }}
            >
              {mobileOpen ? <X style={{ width: 18, height: 18 }} /> : <Menu style={{ width: 18, height: 18 }} />}
            </button>
          </div>
        </div>

        {/* ── Mobile menu ─────────────────────────────────────── */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              style={{
                overflow: 'hidden', borderTop: '1px solid rgba(255,255,255,0.07)',
                background: 'rgba(5,10,28,0.98)',
              }}
            >
              <div style={{ padding: '12px 20px 16px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {/* Nav links */}
                {navItems.map(item => (
                  <Link key={item.href} to={item.href}
                    onClick={() => setMobileOpen(false)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10, padding: '11px 12px',
                      borderRadius: 10, fontSize: 14, fontWeight: 500, textDecoration: 'none',
                      color: item.highlight === 'gold' ? '#F5D06C'
                           : item.highlight === 'cyan' ? '#00D4FF' : 'rgba(255,255,255,0.8)',
                    }}
                  >
                    {item.icon && <item.icon style={{ width: 16, height: 16 }} />}
                    {item.label}
                  </Link>
                ))}
                {/* Divider */}
                <div style={{ height: 1, background: 'rgba(255,255,255,0.07)', margin: '6px 0' }} />
                {/* Auth links */}
                {user ? (
                  <>
                    <Link to="/profile" onClick={() => setMobileOpen(false)}
                      style={{ display:'flex',alignItems:'center',gap:10,padding:'11px 12px',borderRadius:10,fontSize:14,fontWeight:500,textDecoration:'none',color:'rgba(255,255,255,0.8)' }}>
                      <User style={{ width: 16, height: 16 }} /> My Profile
                    </Link>
                    <Link to="/alerts" onClick={() => setMobileOpen(false)}
                      style={{ display:'flex',alignItems:'center',gap:10,padding:'11px 12px',borderRadius:10,fontSize:14,fontWeight:500,textDecoration:'none',color:'rgba(255,255,255,0.8)' }}>
                      <Bell style={{ width: 16, height: 16 }} /> My Alerts
                    </Link>
                    <button onClick={() => { handleLogout(); setMobileOpen(false) }}
                      style={{ display:'flex',alignItems:'center',gap:10,padding:'11px 12px',borderRadius:10,fontSize:14,fontWeight:500,background:'none',border:'none',cursor:'pointer',color:'#FF6B6B',textAlign:'left' }}>
                      <LogOut style={{ width: 16, height: 16 }} /> Sign Out
                    </button>
                  </>
                ) : (
                  <>
                    <Link to="/login" onClick={() => setMobileOpen(false)}
                      style={{ display:'flex',alignItems:'center',gap:10,padding:'11px 12px',borderRadius:10,fontSize:14,fontWeight:500,textDecoration:'none',color:'#00D4FF' }}>
                      <LogIn style={{ width: 16, height: 16 }} /> Login
                    </Link>
                    <Link to="/register" onClick={() => setMobileOpen(false)}
                      style={{ display:'flex',alignItems:'center',gap:10,padding:'11px 12px',borderRadius:10,fontSize:14,fontWeight:700,textDecoration:'none',color:'#F5D06C' }}>
                      <UserPlus style={{ width: 16, height: 16 }} /> Register for Alerts
                    </Link>
                  </>
                )}
                {/* Language */}
                <div style={{ height: 1, background: 'rgba(255,255,255,0.07)', margin: '6px 0' }} />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '4px 4px' }}>
                  {SUPPORTED_LANGUAGES.map(l => (
                    <button key={l.code} onClick={() => { setLang(l.code); setMobileOpen(false) }}
                      style={{
                        padding: '5px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600,
                        cursor: 'pointer', transition: 'all 0.15s',
                        background: lang === l.code ? 'rgba(0,212,255,0.15)' : 'rgba(255,255,255,0.05)',
                        border: `1px solid ${lang === l.code ? 'rgba(0,212,255,0.3)' : 'rgba(255,255,255,0.1)'}`,
                        color: lang === l.code ? '#00D4FF' : 'rgba(255,255,255,0.6)',
                      }}
                    >
                      {l.native}
                    </button>
                  ))}
                </div>
                {/* Emergency */}
                <a href="tel:1078" style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px',
                  borderRadius: 10, background: 'rgba(255,45,45,0.1)', border: '1px solid rgba(255,45,45,0.25)',
                  color: '#FF6B6B', fontSize: 13, fontWeight: 700, textDecoration: 'none', marginTop: 4,
                }}>
                  <Phone style={{ width: 15, height: 15 }} /> Emergency: NDMA 1078
                </a>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.header>
    </>
  )
}
