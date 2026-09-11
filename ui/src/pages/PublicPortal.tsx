'use client'

/**
 * PublicPortal.tsx  — /public route
 *
 * Simplified public-facing flood risk portal for citizens.
 * Designed for:
 *  - Mobile-first (3G networks, small screens)
 *  - No login required
 *  - Plain language — no technical jargon
 *  - 8 Indian languages via useTranslation hook
 *  - City/district search with instant results
 *  - Color-coded risk card with action guide
 *  - Live risk map of India (SVG dot map)
 *  - Emergency contacts always visible
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from '@/hooks/useTranslation'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import {
  Search, AlertTriangle, Phone, MapPin, TrendingUp,
  TrendingDown, Minus, RefreshCw, ChevronRight, Shield,
  Bell
} from 'lucide-react'

const API = (path: string) => `/api/${path}`

interface RiskResult {
  query: string
  region_code: string
  risk_score: number
  risk_level: string
  risk_level_en: string
  color: string
  action: string
  emergency: string
  rising_sites: number
  sites_checked: number
  alerts: Array<{ type: string; message: string; severity: string }>
  rivers: Array<{ name: string; risk: number; trend: string; level_en: string }>
  last_updated: string | null
  lang: string
}

interface MapSite {
  id: number; name: string; lat: number; lng: number
  risk: number; level: string; color: string; region: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const RISK_BG: Record<string, string> = {
  CRITICAL: 'bg-red-500/20 border-red-500/60',
  HIGH:     'bg-orange-500/20 border-orange-500/60',
  MODERATE: 'bg-yellow-500/20 border-yellow-500/50',
  LOW:      'bg-green-500/20 border-green-500/50',
}

const RISK_TEXT: Record<string, string> = {
  CRITICAL: 'text-red-400', HIGH: 'text-orange-400',
  MODERATE: 'text-yellow-400', LOW: 'text-green-400',
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend.includes('↑') || trend.toLowerCase().includes('ris'))
    return <TrendingUp className="h-3.5 w-3.5 text-red-400 inline" />
  if (trend.includes('↓') || trend.toLowerCase().includes('fall'))
    return <TrendingDown className="h-3.5 w-3.5 text-green-400 inline" />
  return <Minus className="h-3.5 w-3.5 text-gray-400 inline" />
}

// Simple SVG India dot-map (approximate lat/lng → SVG coords)
function IndiaMap({ sites }: { sites: MapSite[] }) {
  // Map India bounds: lat 8–37, lng 68–97 → SVG 400×460
  const toSVG = (lat: number, lng: number) => ({
    x: ((lng - 68) / (97 - 68)) * 380 + 10,
    y: ((37 - lat) / (37 - 8)) * 440 + 10,
  })

  return (
    <svg viewBox="0 0 400 460" className="w-full h-auto max-h-64"
         style={{ background: 'transparent' }}>
      {/* Faint India outline (simplified polygon) */}
      <path
        d="M120,30 L180,20 L250,30 L300,60 L360,100 L380,160
           L370,220 L350,270 L310,320 L280,380 L250,420 L220,440
           L190,420 L160,380 L120,320 L90,260 L70,200 L80,130
           L100,80 Z"
        fill="none" stroke="#374151" strokeWidth="1" opacity="0.4"
      />
      {/* Site dots */}
      {sites.map(site => {
        const { x, y } = toSVG(site.lat, site.lng)
        return (
          <g key={site.id}>
            <circle cx={x} cy={y} r={site.risk >= 6 ? 7 : 5}
                    fill={site.color} opacity={0.85} />
            {site.risk >= 6 && (
              <circle cx={x} cy={y} r={10}
                      fill="none" stroke={site.color}
                      strokeWidth="1.5" opacity="0.4">
                <animate attributeName="r" values="6;14;6" dur="2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.5;0;0.5" dur="2s" repeatCount="indefinite" />
              </circle>
            )}
          </g>
        )
      })}
    </svg>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function PublicPortal() {
  const { t, lang } = useTranslation()

  const [query, setQuery]         = useState('')
  const [suggestions, setSugg]    = useState<string[]>([])
  const [result, setResult]       = useState<RiskResult | null>(null)
  const [mapData, setMapData]     = useState<MapSite[]>([])
  const [loading, setLoading]     = useState(false)
  const [allDistricts, setAllDist]= useState<string[]>([])
  const [mapLoaded, setMapLoaded] = useState(false)

  // Load district list + map on mount
  useEffect(() => {
    fetch(API('public/districts'))
      .then(r => r.json())
      .then(d => setAllDist(d.districts || []))
      .catch(() => {})

    fetch(API('public/map'))
      .then(r => r.json())
      .then(d => { setMapData(d.sites || []); setMapLoaded(true) })
      .catch(() => {})
  }, [])

  // Autocomplete
  useEffect(() => {
    if (query.length < 2) { setSugg([]); return }
    const q = query.toLowerCase()
    setSugg(allDistricts.filter(d => d.includes(q)).slice(0, 6))
  }, [query, allDistricts])

  const search = useCallback(async (q: string) => {
    if (!q.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const r = await fetch(API(`public/risk?city=${encodeURIComponent(q)}&lang=${lang}`))
      if (!r.ok) throw new Error('not found')
      setResult(await r.json())
    } catch {
      setResult(null)
    } finally {
      setLoading(false)
    }
  }, [lang])

  // Re-fetch when language changes
  useEffect(() => {
    if (result) search(result.query)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSugg([])
    search(query)
  }

  const pick = (d: string) => {
    setQuery(d)
    setSugg([])
    search(d)
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* ── Top bar ──────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-gray-900/95 backdrop-blur border-b border-gray-800">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🌊</span>
            <div>
              <p className="text-sm font-bold text-white leading-none">Flood Alert India</p>
              <p className="text-xs text-gray-400">NDMA · IMD · CWC</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSwitcher compact />
            <Link to="/login"
              className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors">
              {t('login')}
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-5">

        {/* ── Search ───────────────────────────────────────────────── */}
        <form onSubmit={handleSubmit} className="relative">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder={t('search_placeholder')}
                className="w-full pl-9 pr-4 py-3 rounded-xl bg-gray-800 border border-gray-600
                           text-white placeholder-gray-400 text-sm focus:outline-none
                           focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50"
              />
              {/* Autocomplete dropdown */}
              {suggestions.length > 0 && (
                <div className="absolute top-full mt-1 w-full rounded-xl bg-gray-800
                                border border-gray-700 shadow-xl z-50 overflow-hidden">
                  {suggestions.map(s => (
                    <button key={s} type="button" onClick={() => pick(s)}
                            className="w-full text-left px-4 py-2.5 text-sm capitalize
                                       hover:bg-gray-700 text-gray-200 flex items-center gap-2">
                      <MapPin className="h-3.5 w-3.5 text-gray-500" />
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button type="submit"
                    className="px-4 py-3 rounded-xl bg-blue-600 hover:bg-blue-700
                               text-white font-medium text-sm transition-colors flex items-center gap-1.5">
              {loading
                ? <RefreshCw className="h-4 w-4 animate-spin" />
                : <Search className="h-4 w-4" />}
            </button>
          </div>
        </form>

        {/* ── Loading ───────────────────────────────────────────────── */}
        {loading && (
          <div className="text-center py-8 text-gray-400 text-sm animate-pulse">
            {t('checking_risk')}
          </div>
        )}

        {/* ── Result card ───────────────────────────────────────────── */}
        {result && !loading && (
          <div className={`rounded-2xl border p-5 space-y-4 ${RISK_BG[result.risk_level_en] || 'bg-gray-800/50 border-gray-700'}`}>

            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                  {t('flood_risk_title')}
                </p>
                <h2 className="text-xl font-bold text-white capitalize">{result.query}</h2>
              </div>
              <div className="text-right">
                <div className={`text-3xl font-black ${RISK_TEXT[result.risk_level_en] || 'text-white'}`}>
                  {result.risk_score}
                  <span className="text-sm font-normal text-gray-400">/10</span>
                </div>
                <div className={`text-sm font-bold ${RISK_TEXT[result.risk_level_en] || 'text-white'}`}>
                  {result.risk_level}
                </div>
              </div>
            </div>

            {/* Stats row */}
            <div className="flex gap-3 text-xs text-gray-400">
              <span>{result.sites_checked} {t('sites_checked')}</span>
              {result.rising_sites > 0 && (
                <span className="text-red-400 flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" />
                  {result.rising_sites} {t('rising_sites')}
                </span>
              )}
            </div>

            {/* Action guide */}
            <div className="rounded-xl bg-black/30 p-4">
              <p className="text-xs font-semibold text-gray-300 uppercase tracking-wide mb-1.5">
                {t('what_to_do')}
              </p>
              <p className="text-sm text-white leading-relaxed">{result.action}</p>
            </div>

            {/* Active alerts */}
            {result.alerts.length > 0 && (
              <div className="space-y-2">
                {result.alerts.map((a, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <AlertTriangle className="h-4 w-4 text-orange-400 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-300 text-xs leading-relaxed">{a.message}</span>
                  </div>
                ))}
              </div>
            )}

            {/* River list */}
            {result.rivers.length > 0 && (
              <div className="space-y-1.5">
                {result.rivers.map((r, i) => (
                  <div key={i}
                       className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0">
                    <div className="flex items-center gap-2 text-sm">
                      <MapPin className="h-3.5 w-3.5 text-gray-500" />
                      <span className="text-gray-200 truncate max-w-[180px]">{r.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-mono ${RISK_TEXT[r.level_en] || 'text-gray-300'}`}>
                        {r.risk}/10
                      </span>
                      <span className="text-xs text-gray-400 flex items-center gap-0.5">
                        <TrendIcon trend={r.trend} /> {r.trend}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Last updated */}
            {result.last_updated && (
              <p className="text-xs text-gray-500">
                {t('last_updated')}: {new Date(result.last_updated).toLocaleString()}
              </p>
            )}
          </div>
        )}

        {/* ── India risk map ─────────────────────────────────────────── */}
        {mapLoaded && mapData.length > 0 && (
          <div className="rounded-2xl bg-gray-900/60 border border-gray-700/50 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-200">India Flood Risk Map</h3>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> Critical</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500 inline-block" /> High</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500 inline-block" /> Low</span>
              </div>
            </div>
            <IndiaMap sites={mapData} />
          </div>
        )}

        {/* ── Quick district buttons ────────────────────────────────── */}
        <div>
          <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Popular searches</p>
          <div className="flex flex-wrap gap-2">
            {['Patna', 'Guwahati', 'Cuttack', 'Vijayawada', 'Surat', 'Kolkata', 'Darbhanga', 'Rajahmundry'].map(d => (
              <button key={d} onClick={() => pick(d.toLowerCase())}
                      className="px-3 py-1.5 rounded-full text-xs bg-gray-800 hover:bg-gray-700
                                 text-gray-300 border border-gray-700 transition-colors capitalize">
                {d}
              </button>
            ))}
          </div>
        </div>

        {/* ── Link to full dashboard ────────────────────────────────── */}
        <Link to="/"
              className="flex items-center justify-between w-full px-4 py-3 rounded-xl
                         bg-blue-600/10 border border-blue-500/30 hover:bg-blue-600/20 transition-colors">
          <span className="text-sm text-blue-300 font-medium">{t('view_dashboard')}</span>
          <ChevronRight className="h-4 w-4 text-blue-400" />
        </Link>

        {/* ── Register CTA ──────────────────────────────────────────── */}
        <div className="rounded-2xl bg-gradient-to-r from-blue-900/40 to-purple-900/40
                        border border-blue-500/20 p-5 flex items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Bell className="h-4 w-4 text-blue-400" />
              <span className="text-sm font-semibold text-white">{t('register')}</span>
            </div>
            <p className="text-xs text-gray-400">Get SMS/WhatsApp alerts for your district</p>
          </div>
          <Link to="/register"
                className="flex-shrink-0 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700
                           text-white text-sm font-medium transition-colors">
            {t('register')}
          </Link>
        </div>

      </main>

      {/* ── Sticky emergency footer ─────────────────────────────────── */}
      <div className="fixed bottom-0 left-0 right-0 z-50
                      bg-red-900/95 backdrop-blur border-t border-red-700/50 py-2 px-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-red-400 flex-shrink-0" />
            <span className="text-xs text-red-200 font-medium">{t('emergency_contact')}</span>
          </div>
          <a href="tel:1078"
             className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                        bg-red-600 hover:bg-red-700 text-white text-sm font-bold transition-colors">
            <Phone className="h-3.5 w-3.5" />
            1078
          </a>
        </div>
      </div>

      {/* Bottom padding for sticky footer */}
      <div className="h-14" />
    </div>
  )
}
