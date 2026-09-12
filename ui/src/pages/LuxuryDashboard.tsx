'use client'

/**
 * LuxuryDashboard.tsx — Ultra Luxury 3D Flood Intelligence Dashboard
 *
 * Features:
 * - Three.js animated 3D background (particles + wave geometry)
 * - Glassmorphism panels with animated borders
 * - 3D flip metric cards
 * - Animated India risk map
 * - All 12 novel features with premium UI
 * - Real-time data from backend APIs
 * - Framer Motion animations throughout
 * - Gold/Cyan luxury color palette
 */

import { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'
import LuxuryMetricCard from '@/components/LuxuryMetricCard'
import '@/styles/luxury.css'

// Lazy load heavy 3D background
const LuxuryBackground = lazy(() => import('@/components/LuxuryBackground'))

// ── API helpers ───────────────────────────────────────────────────
const API = (p: string) => `/api/${p}`
const H = { Authorization: 'Bearer dev-token' }

const safe = async (url: string) => {
  try {
    const r = await fetch(url, { headers: H })
    if (!r.ok) return null
    return r.json()
  } catch { return null }
}

// ── Risk color helpers ────────────────────────────────────────────
const riskColor = (score: number) => {
  if (score >= 8) return '#FF3B3B'
  if (score >= 6) return '#FF8C00'
  if (score >= 4) return '#FFD700'
  return '#00E676'
}

const riskLabel = (score: number) => {
  if (score >= 8) return 'CRITICAL'
  if (score >= 6) return 'HIGH'
  if (score >= 4) return 'MODERATE'
  return 'LOW'
}

// ── Novel features config ─────────────────────────────────────────
const NOVEL_FEATURES = [
  { id: 1,  icon: '🧠', title: 'AI Flood Memory',         sub: 'Auto self-retraining',        color: '#D4AF37', endpoint: 'novel/memory/status' },
  { id: 2,  icon: '🌊', title: 'Cascade Predictor',       sub: 'Bridge · Disease · Power',    color: '#00D4FF', endpoint: 'novel/cascade/5'     },
  { id: 3,  icon: '🏠', title: 'Street-Level Depth',      sub: 'Per-address flood depth',     color: '#00FFD1', endpoint: 'novel/street-depth/5' },
  { id: 4,  icon: '🆘', title: 'Vulnerability Profile',   sub: 'NDRF rescue priority',        color: '#FF6B6B', endpoint: 'novel/vulnerability/5'},
  { id: 5,  icon: '📞', title: 'Voice IVR Alert',         sub: '8 Indian languages',          color: '#D4AF37', endpoint: 'novel/ivr/script?risk_level=HIGH&lang=hi' },
  { id: 6,  icon: '🏗️', title: 'Dam Negotiation',         sub: 'Staggered release schedule',  color: '#00D4FF', endpoint: 'novel/dam-negotiation/mundali' },
  { id: 7,  icon: '📋', title: 'AI Compensation',         sub: 'SDRF auto claim generation',  color: '#FFD700', endpoint: 'novel/compensation/rates' },
  { id: 8,  icon: '🔮', title: 'Digital Twin',            sub: 'What-if basin simulation',    color: '#00FFD1', endpoint: 'novel/digital-twin/all-scenarios/5' },
  { id: 9,  icon: '🔒', title: 'Federated Learning',      sub: 'Privacy-preserving 9 states', color: '#D4AF37', endpoint: 'novel/federated/status'  },
  { id: 10, icon: '💰', title: 'Economic Impact',         sub: 'Pre-event ₹ forecast',        color: '#00D4FF', endpoint: 'novel/economic-impact/5' },
  { id: 11, icon: '🌿', title: 'Carbon Credits',          sub: 'Wetland VCU certificates',    color: '#00E676', endpoint: 'novel/carbon/5'          },
  { id: 12, icon: '🧬', title: 'Flood Genome',            sub: 'Hydrological fingerprint',    color: '#FF8C00', endpoint: 'novel/genome/5'           },
]

// ── Main dashboard ────────────────────────────────────────────────
export default function LuxuryDashboard() {
  const [summary, setSummary]         = useState<any>(null)
  const [watersheds, setWatersheds]   = useState<any[]>([])
  const [alerts, setAlerts]           = useState<any[]>([])
  const [novelStatus, setNovelStatus] = useState<any>(null)
  const [activeFeature, setActiveFeature] = useState<number | null>(null)
  const [featureData, setFeatureData] = useState<Record<number, any>>({})
  const [activeTab, setActiveTab]     = useState<'map' | 'features' | 'alerts' | 'twin'>('map')
  const [twinResult, setTwinResult]   = useState<any>(null)

  // Load core data
  const load = useCallback(async () => {
    const [sum, ws, al, nov] = await Promise.all([
      safe(API('dashboard/summary')),
      safe(API('watersheds')),
      safe(API('alerts')),
      safe(API('novel/summary')),
    ])
    if (sum) setSummary(sum)
    if (ws)  setWatersheds((ws as any).watersheds || ws)
    if (al)  setAlerts((al as any).alerts || al)
    if (nov) setNovelStatus(nov)
  }, [])

  useEffect(() => { load() }, [load])

  // Load feature detail on click
  const loadFeature = async (f: typeof NOVEL_FEATURES[0]) => {
    setActiveFeature(f.id)
    if (featureData[f.id]) return
    const data = await safe(API(f.endpoint))
    if (data) setFeatureData(prev => ({ ...prev, [f.id]: data }))
  }

  // Run digital twin
  const runTwin = async () => {
    const r = await fetch(API('novel/digital-twin/simulate'), {
      method: 'POST',
      headers: { ...H, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        watershed_id: 5,
        scenario_type: 'EXTRA_RAINFALL',
        extra_rainfall_mm: 150,
        rainfall_duration_h: 6,
        horizon_hours: 48,
      }),
    })
    if (r.ok) setTwinResult(await r.json())
  }

  const highRisk   = watersheds.filter(w => (w.risk_score || 0) >= 6)
  const maxRisk    = watersheds.reduce((mx, w) => Math.max(mx, w.risk_score || 0), 0)

  return (
    <div className="luxury-root" style={{ minHeight: '100vh', position: 'relative' }}>

      {/* 3D Background */}
      <Suspense fallback={null}>
        <LuxuryBackground />
      </Suspense>

      {/* ── Header ──────────────────────────────────────────────── */}
      <motion.header
        initial={{ y: -60, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.8, ease: [0.23, 1, 0.32, 1] }}
        className="relative z-50 flex items-center justify-between px-6 py-3"
        style={{
          background: 'rgba(5,10,28,0.85)',
          backdropFilter: 'blur(30px)',
          borderBottom: '1px solid rgba(212,175,55,0.15)',
          boxShadow: '0 4px 40px rgba(0,0,0,0.5)',
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <motion.div
            animate={{ rotate: [0, 5, -5, 0] }}
            transition={{ duration: 4, repeat: Infinity }}
            className="text-3xl"
          >
            🌊
          </motion.div>
          <div>
            <h1 className="font-black text-lg leading-none" style={{
              background: 'linear-gradient(135deg, #F5D06C, #D4AF37, #A67C1C)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
            }}>
              FLOOD INTELLIGENCE
            </h1>
            <p className="text-xs" style={{ color: 'rgba(0,212,255,0.7)', letterSpacing: '2px' }}>
              INDIA · AI-POWERED · REAL-TIME
            </p>
          </div>
        </div>

        {/* Nav tabs */}
        <div className="flex items-center gap-1 p-1 rounded-xl"
             style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
          {([
            { id: 'map',      label: '🗺️ Live Map',   },
            { id: 'features', label: '✨ 12 Features', },
            { id: 'alerts',   label: '⚠️ Alerts',     },
            { id: 'twin',     label: '🔮 Digital Twin'},
          ] as const).map(tab => (
            <motion.button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="px-4 py-2 rounded-lg text-xs font-semibold transition-all relative"
              style={{
                color: activeTab === tab.id ? '#050A1C' : 'rgba(255,255,255,0.5)',
                background: activeTab === tab.id
                  ? 'linear-gradient(135deg, #F5D06C, #D4AF37)'
                  : 'transparent',
              }}
            >
              {tab.label}
              {activeTab === tab.id && (
                <motion.div
                  layoutId="tabIndicator"
                  className="absolute inset-0 rounded-lg"
                  style={{ background: 'linear-gradient(135deg, #F5D06C, #D4AF37)', zIndex: -1 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                />
              )}
            </motion.button>
          ))}
        </div>

        {/* Status + links */}
        <div className="flex items-center gap-3">
          {summary && (
            <motion.div
              animate={{ opacity: [0.7, 1, 0.7] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full"
              style={{ background: 'rgba(0,230,118,0.1)', border: '1px solid rgba(0,230,118,0.25)' }}
            >
              <div className="w-2 h-2 rounded-full bg-green-400" />
              <span className="text-xs font-semibold text-green-400">
                {summary.total_watersheds} Sites Active
              </span>
            </motion.div>
          )}
          <Link to="/" className="btn-ghost text-xs px-3 py-1.5">
            Full Dashboard
          </Link>
          <Link to="/public" className="btn-luxury text-xs px-3 py-1.5">
            Public Portal
          </Link>
        </div>
      </motion.header>

      {/* ── Main Content ─────────────────────────────────────────── */}
      <div className="relative z-10 p-4 luxury-scroll" style={{ maxHeight: 'calc(100vh - 60px)', overflowY: 'auto' }}>

        {/* ── Top Metrics Row ─────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3 mb-4"
        >
          <LuxuryMetricCard
            title="Overall Risk" icon="🎯" color="red" delay={0.1}
            value={maxRisk.toFixed(1)}
            subtitle={`${highRisk.length} sites above 6/10`}
            trend={highRisk.length > 3 ? 'up' : 'stable'}
            trendValue={`${highRisk.length} HIGH`}
            backContent={
              <div className="space-y-2">
                {highRisk.slice(0, 3).map(w => (
                  <div key={w.id} className="flex justify-between text-xs">
                    <span style={{ color: 'rgba(255,255,255,0.6)' }}>{w.name?.split(' at ')[1]?.split('(')[0]?.trim() || w.name}</span>
                    <span style={{ color: riskColor(w.risk_score) }}>{w.risk_score?.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            }
          />
          <LuxuryMetricCard
            title="Active Alerts" icon="🚨" color="orange" delay={0.15}
            value={summary?.active_alerts ?? alerts.length}
            subtitle="Across 8 India basins"
            trend={alerts.length > 5 ? 'up' : 'stable'}
            trendValue={alerts.length > 5 ? 'Escalating' : 'Stable'}
          />
          <LuxuryMetricCard
            title="Sites Monitored" icon="📡" color="cyan" delay={0.2}
            value={summary?.total_watersheds ?? watersheds.length}
            subtitle="GloFAS + CWC real-time"
            trend="stable" trendValue="Live"
          />
          <LuxuryMetricCard
            title="Rising Trend" icon="📈" color="red" delay={0.25}
            value={watersheds.filter(w => w.trend === 'rising').length}
            subtitle="Rivers with rising discharge"
            trend={watersheds.filter(w => w.trend === 'rising').length > 5 ? 'up' : 'stable'}
          />
          <LuxuryMetricCard
            title="Novel Features" icon="✨" color="gold" delay={0.3}
            value={novelStatus?.active ?? 12}
            subtitle="World-first capabilities"
            trend="stable" trendValue="All Active"
          />
          <LuxuryMetricCard
            title="AI Agents" icon="🤖" color="cyan" delay={0.35}
            value={4}
            subtitle="LSTM · GRU · Transformer · RF"
            trend="stable" trendValue="Trained"
          />
        </motion.div>

        {/* ── Tab Content ─────────────────────────────────────── */}
        <AnimatePresence mode="wait">

          {/* ── MAP TAB ──────────────────────────────────────── */}
          {activeTab === 'map' && (
            <motion.div key="map"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}
              className="grid grid-cols-3 gap-4"
            >
              {/* Risk map panel */}
              <div className="col-span-2 glass-cyan rounded-2xl overflow-hidden"
                   style={{ minHeight: 420 }}>
                <div className="p-4 flex items-center justify-between"
                     style={{ borderBottom: '1px solid rgba(0,212,255,0.12)' }}>
                  <div>
                    <h2 className="font-bold text-white">India Flood Risk Map</h2>
                    <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
                      45+ CWC/GloFAS monitoring sites • Updated hourly
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    {[['#FF3B3B','Critical'],['#FF8C00','High'],['#FFD700','Moderate'],['#00E676','Low']].map(([c, l]) => (
                      <div key={l} className="flex items-center gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: c, boxShadow: `0 0 6px ${c}` }} />
                        <span style={{ color: 'rgba(255,255,255,0.5)' }}>{l}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* SVG India Risk Map */}
                <div className="relative p-4" style={{ height: 360 }}>
                  <svg viewBox="0 0 500 580" className="w-full h-full" style={{ opacity: 0.9 }}>
                    {/* India outline */}
                    <defs>
                      <radialGradient id="mapGlow" cx="50%" cy="50%" r="50%">
                        <stop offset="0%" stopColor="rgba(0,212,255,0.1)" />
                        <stop offset="100%" stopColor="rgba(0,212,255,0)" />
                      </radialGradient>
                    </defs>
                    <ellipse cx="250" cy="290" rx="200" ry="270" fill="url(#mapGlow)" />
                    <path
                      d="M 150 80 L 200 60 L 300 70 L 380 100 L 430 160 L 440 230 L 420 310 L 390 380 L 350 440 L 310 500 L 270 540 L 240 520 L 200 480 L 150 420 L 110 350 L 80 270 L 90 190 Z"
                      fill="none" stroke="rgba(0,212,255,0.15)" strokeWidth="1.5"
                    />

                    {/* River site dots */}
                    {watersheds.slice(0, 20).map((w, i) => {
                      const lat = w.location_lat || 25
                      const lng = w.location_lng || 83
                      // Map lat/lng to SVG coords
                      const x = ((lng - 68) / (97 - 68)) * 380 + 60
                      const y = ((37 - lat) / (37 - 8)) * 460 + 60
                      const rc = riskColor(w.risk_score || 0)
                      const isCritical = (w.risk_score || 0) >= 8

                      return (
                        <g key={w.id || i}>
                          {isCritical && (
                            <motion.circle
                              cx={x} cy={y}
                              animate={{ r: [8, 18, 8], opacity: [0.6, 0, 0.6] }}
                              transition={{ duration: 2, repeat: Infinity, delay: i * 0.15 }}
                              fill={rc} opacity={0.3}
                            />
                          )}
                          <motion.circle
                            cx={x} cy={y} r={isCritical ? 7 : 5}
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ delay: i * 0.05 }}
                            fill={rc}
                            style={{ filter: `drop-shadow(0 0 4px ${rc})` }}
                          />
                          <circle cx={x} cy={y} r={isCritical ? 3 : 2} fill="white" opacity={0.9} />
                        </g>
                      )
                    })}
                  </svg>

                  {/* Overlay: top risk sites */}
                  <div className="absolute bottom-4 left-4 space-y-1.5">
                    {highRisk.slice(0, 3).map(w => (
                      <motion.div
                        key={w.id}
                        initial={{ x: -20, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-full"
                        style={{
                          background: 'rgba(5,10,28,0.85)',
                          border: `1px solid ${riskColor(w.risk_score)}40`,
                          backdropFilter: 'blur(10px)',
                        }}
                      >
                        <div className="w-2 h-2 rounded-full"
                             style={{ background: riskColor(w.risk_score), boxShadow: `0 0 6px ${riskColor(w.risk_score)}` }} />
                        <span className="text-xs text-white font-medium">
                          {w.name?.split(' at ')[1]?.split('(')[0]?.trim() || w.name}
                        </span>
                        <span className="text-xs font-bold"
                              style={{ color: riskColor(w.risk_score) }}>
                          {w.risk_score?.toFixed(1)}
                        </span>
                        <span className="text-xs" style={{ color: w.trend === 'rising' ? '#FF6B6B' : '#00E676' }}>
                          {w.trend === 'rising' ? '↑' : w.trend === 'falling' ? '↓' : '→'}
                        </span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right panel — Risk breakdown */}
              <div className="space-y-3">
                {/* Basin risk cards */}
                <div className="glass rounded-2xl p-4" style={{ border: '1px solid rgba(212,175,55,0.15)' }}>
                  <h3 className="text-xs font-semibold uppercase tracking-widest mb-3"
                      style={{ color: '#D4AF37', letterSpacing: '2px' }}>
                    Basin Risk Scores
                  </h3>
                  <div className="space-y-2.5">
                    {[
                      ['Brahmaputra', 'IN-BRAHMAPUTRA'],
                      ['Ganga',       'IN-GANGA'],
                      ['Mahanadi',    'IN-MAHANADI'],
                      ['Godavari',    'IN-GODAVARI'],
                      ['Krishna',     'IN-KRISHNA'],
                      ['Narmada',     'IN-NARMADA'],
                      ['Kaveri',      'IN-KAVERI'],
                      ['Indus',       'IN-INDUS'],
                    ].map(([name, code]) => {
                      const sites = watersheds.filter(w => w.region_code === code)
                      const maxS  = sites.reduce((m, w) => Math.max(m, w.risk_score || 0), 0)
                      const pct   = maxS * 10
                      return (
                        <div key={code}>
                          <div className="flex justify-between text-xs mb-1">
                            <span style={{ color: 'rgba(255,255,255,0.6)' }}>{name}</span>
                            <span style={{ color: riskColor(maxS), fontWeight: 700 }}>
                              {maxS.toFixed(1)}/10
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${pct}%` }}
                              transition={{ duration: 1, delay: 0.3, ease: [0.23, 1, 0.32, 1] }}
                              className="h-full rounded-full"
                              style={{
                                background: `linear-gradient(90deg, ${riskColor(maxS)}, ${riskColor(maxS)}80)`,
                                boxShadow: `0 0 8px ${riskColor(maxS)}50`,
                              }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Live alerts */}
                <div className="glass rounded-2xl p-4" style={{ border: '1px solid rgba(255,59,59,0.15)', flex: 1 }}>
                  <h3 className="text-xs font-semibold uppercase tracking-widest mb-3"
                      style={{ color: '#FF6B6B', letterSpacing: '2px' }}>
                    Active Alerts
                  </h3>
                  <div className="space-y-2 max-h-48 overflow-y-auto luxury-scroll">
                    {alerts.slice(0, 6).map((a, i) => (
                      <motion.div key={i}
                        initial={{ x: 20, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        transition={{ delay: i * 0.08 }}
                        className="flex items-start gap-2 p-2 rounded-lg"
                        style={{ background: 'rgba(255,59,59,0.06)', border: '1px solid rgba(255,59,59,0.12)' }}
                      >
                        <span className="text-xs">⚠️</span>
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-white truncate">{a.alert_type || 'Alert'}</p>
                          <p className="text-xs truncate" style={{ color: 'rgba(255,255,255,0.4)' }}>
                            {a.watershed || 'Multiple sites'}
                          </p>
                        </div>
                        <span className="text-xs flex-shrink-0 font-bold"
                              style={{ color: a.severity === 'High' ? '#FF6B6B' : '#FFD700' }}>
                          {a.severity}
                        </span>
                      </motion.div>
                    ))}
                    {alerts.length === 0 && (
                      <p className="text-xs text-center py-4" style={{ color: 'rgba(255,255,255,0.3)' }}>
                        No active alerts
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* ── NOVEL FEATURES TAB ───────────────────────────── */}
          {activeTab === 'features' && (
            <motion.div key="features"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}
            >
              <div className="mb-4">
                <h2 className="text-xl font-black text-gold">12 World-First Novel Features</h2>
                <p className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>
                  Click any feature to see live data from the AI engine
                </p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3 mb-4">
                {NOVEL_FEATURES.map((f, i) => (
                  <motion.div
                    key={f.id}
                    initial={{ opacity: 0, scale: 0.9, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ delay: i * 0.05, duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
                    onClick={() => loadFeature(f)}
                    className="animated-border cursor-pointer group"
                    style={{
                      background: activeFeature === f.id
                        ? `linear-gradient(135deg, ${f.color}15, rgba(5,10,28,0.9))`
                        : 'rgba(5,10,28,0.7)',
                      borderRadius: 16,
                      padding: 16,
                      backdropFilter: 'blur(20px)',
                      transition: 'all 0.3s ease',
                    }}
                    whileHover={{ scale: 1.02, y: -4 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <motion.div
                      className="text-3xl mb-2"
                      animate={activeFeature === f.id ? { rotate: [0, 10, -10, 0] } : {}}
                      transition={{ duration: 0.5 }}
                    >
                      {f.icon}
                    </motion.div>
                    <div className="flex items-start justify-between mb-1">
                      <p className="text-sm font-bold text-white leading-tight">{f.title}</p>
                      <span className="text-xs font-bold rounded-full px-2 py-0.5"
                            style={{ background: `${f.color}20`, color: f.color, border: `1px solid ${f.color}40` }}>
                        #{f.id}
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>{f.sub}</p>

                    {/* Status indicator */}
                    <div className="flex items-center gap-1.5 mt-3">
                      <motion.div
                        animate={{ opacity: [0.5, 1, 0.5] }}
                        transition={{ duration: 1.5, repeat: Infinity }}
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: novelStatus?.features?.[Object.keys(novelStatus?.features || {})[f.id - 1]] === 'active' ? '#00E676' : f.color }}
                      />
                      <span className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>
                        {novelStatus?.active === 12 ? 'Active' : 'Loading...'}
                      </span>
                    </div>

                    {/* Expanded data */}
                    <AnimatePresence>
                      {activeFeature === f.id && featureData[f.id] && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.4 }}
                          className="mt-3 pt-3 overflow-hidden"
                          style={{ borderTop: `1px solid ${f.color}25` }}
                          onClick={e => e.stopPropagation()}
                        >
                          <pre className="text-xs overflow-x-auto luxury-scroll"
                               style={{ color: `${f.color}CC`, maxHeight: 120, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                            {JSON.stringify(featureData[f.id], null, 2).slice(0, 400)}
                            {JSON.stringify(featureData[f.id]).length > 400 ? '\n...' : ''}
                          </pre>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {/* ── ALERTS TAB ───────────────────────────────────── */}
          {activeTab === 'alerts' && (
            <motion.div key="alerts"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Active alerts list */}
                <div className="glass rounded-2xl p-5" style={{ border: '1px solid rgba(255,59,59,0.2)' }}>
                  <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                    <span>🚨</span>
                    <span>Active Flood Alerts</span>
                    <span className="text-xs px-2 py-0.5 rounded-full"
                          style={{ background: 'rgba(255,59,59,0.15)', color: '#FF6B6B' }}>
                      {alerts.length}
                    </span>
                  </h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto luxury-scroll">
                    {alerts.map((a, i) => (
                      <motion.div key={i}
                        initial={{ x: -20, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        transition={{ delay: i * 0.06 }}
                        className="p-4 rounded-xl"
                        style={{
                          background: a.severity === 'High'
                            ? 'rgba(255,59,59,0.08)' : 'rgba(255,140,0,0.07)',
                          border: `1px solid ${a.severity === 'High' ? 'rgba(255,59,59,0.25)' : 'rgba(255,140,0,0.2)'}`,
                        }}
                      >
                        <div className="flex items-start justify-between mb-1">
                          <p className="text-sm font-semibold text-white">{a.alert_type}</p>
                          <span className="text-xs font-bold"
                                style={{ color: a.severity === 'High' ? '#FF6B6B' : '#FF8C00' }}>
                            {a.severity?.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-xs mb-1" style={{ color: 'rgba(255,255,255,0.5)' }}>
                          📍 {a.watershed || 'Multiple sites'}
                        </p>
                        <p className="text-xs leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
                          {a.message?.slice(0, 100)}{(a.message?.length || 0) > 100 ? '...' : ''}
                        </p>
                      </motion.div>
                    ))}
                    {alerts.length === 0 && (
                      <div className="text-center py-12">
                        <div className="text-4xl mb-3">✅</div>
                        <p className="text-white font-semibold">No Active Alerts</p>
                        <p className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>
                          All river sites within safe parameters
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* High-risk watersheds */}
                <div className="glass rounded-2xl p-5" style={{ border: '1px solid rgba(212,175,55,0.2)' }}>
                  <h3 className="font-bold mb-4 flex items-center gap-2">
                    <span>⚡</span>
                    <span style={{ color: '#D4AF37' }}>High Risk Watersheds</span>
                  </h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto luxury-scroll">
                    {watersheds
                      .filter(w => (w.risk_score || 0) >= 5)
                      .sort((a, b) => b.risk_score - a.risk_score)
                      .map((w, i) => (
                        <motion.div key={w.id}
                          initial={{ x: 20, opacity: 0 }}
                          animate={{ x: 0, opacity: 1 }}
                          transition={{ delay: i * 0.07 }}
                          className="flex items-center gap-3 p-3 rounded-xl"
                          style={{
                            background: `${riskColor(w.risk_score)}08`,
                            border: `1px solid ${riskColor(w.risk_score)}20`,
                          }}
                        >
                          <div className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center font-black text-sm"
                               style={{
                                 background: `${riskColor(w.risk_score)}20`,
                                 color: riskColor(w.risk_score),
                                 border: `2px solid ${riskColor(w.risk_score)}40`,
                               }}>
                            {w.risk_score?.toFixed(1)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-white truncate">{w.name}</p>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
                                {(w.current_streamflow_cfs || 0).toLocaleString()} CFS
                              </span>
                              <span className="text-xs" style={{ color: w.trend === 'rising' ? '#FF6B6B' : '#00E676' }}>
                                {w.trend === 'rising' ? '↑ Rising' : w.trend === 'falling' ? '↓ Falling' : '→ Stable'}
                              </span>
                            </div>
                          </div>
                          <div className="text-xs font-bold px-2 py-1 rounded-full flex-shrink-0"
                               style={{ background: `${riskColor(w.risk_score)}20`, color: riskColor(w.risk_score) }}>
                            {riskLabel(w.risk_score)}
                          </div>
                        </motion.div>
                      ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* ── DIGITAL TWIN TAB ─────────────────────────────── */}
          {activeTab === 'twin' && (
            <motion.div key="twin"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}
            >
              <div className="grid grid-cols-3 gap-4">
                {/* Control panel */}
                <div className="glass-gold rounded-2xl p-5 float-3d">
                  <h3 className="font-bold text-gold mb-1">🔮 Flood Digital Twin</h3>
                  <p className="text-xs mb-4" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    World-first what-if simulation engine
                  </p>

                  <div className="space-y-4">
                    <div>
                      <label className="text-xs font-semibold uppercase tracking-widest mb-2 block"
                             style={{ color: 'rgba(212,175,55,0.7)' }}>
                        Scenario
                      </label>
                      <div className="space-y-2">
                        {[
                          { label: '🌧️ +150mm Rainfall / 6h', type: 'EXTRA_RAINFALL' },
                          { label: '🌊 Extreme Rain + Saturated Soil', type: 'COMBINED' },
                          { label: '🏗️ Dam Emergency Release', type: 'DAM_RELEASE' },
                          { label: '💧 Fully Saturated Soil', type: 'SOIL_SATURATED' },
                        ].map(s => (
                          <button key={s.type}
                            className="w-full text-left p-2.5 rounded-lg text-xs transition-all"
                            style={{
                              background: 'rgba(212,175,55,0.08)',
                              border: '1px solid rgba(212,175,55,0.2)',
                              color: 'rgba(255,255,255,0.7)',
                            }}
                            onClick={runTwin}
                          >
                            {s.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <button onClick={runTwin} className="btn-luxury w-full text-center">
                      ▶ Run Simulation
                    </button>
                  </div>
                </div>

                {/* Results */}
                <div className="col-span-2 glass-cyan rounded-2xl p-5">
                  <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                    <span>📊</span> Simulation Results
                    {twinResult && (
                      <span className="text-xs px-2 py-0.5 rounded-full ml-2"
                            style={{ background: 'rgba(0,212,255,0.15)', color: '#00D4FF' }}>
                        {twinResult.scenario?.scenario_type}
                      </span>
                    )}
                  </h3>

                  {twinResult ? (
                    <div className="space-y-4">
                      {/* Key metrics */}
                      <div className="grid grid-cols-3 gap-3">
                        {[
                          { label: 'Base Peak', value: `${twinResult.base_peak_cfs?.toLocaleString()} CFS`, color: '#00E676' },
                          { label: 'Scenario Peak', value: `${twinResult.scenario_peak_cfs?.toLocaleString()} CFS`, color: '#FF6B6B' },
                          { label: 'Increase', value: `+${twinResult.peak_increase_pct?.toFixed(1)}%`, color: '#FFD700' },
                        ].map(m => (
                          <div key={m.label} className="rounded-xl p-3 text-center"
                               style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                            <p className="text-xs mb-1" style={{ color: 'rgba(255,255,255,0.4)' }}>{m.label}</p>
                            <p className="font-bold text-lg" style={{ color: m.color }}>{m.value}</p>
                          </div>
                        ))}
                      </div>

                      {/* Recommendation */}
                      <div className="p-4 rounded-xl"
                           style={{ background: 'rgba(255,59,59,0.08)', border: '1px solid rgba(255,59,59,0.2)' }}>
                        <p className="text-xs font-semibold mb-1" style={{ color: '#FF6B6B' }}>
                          ⚠️ AI Recommendation
                        </p>
                        <p className="text-xs text-white leading-relaxed">
                          {twinResult.recommendation}
                        </p>
                      </div>

                      {/* Time series chart */}
                      {twinResult.time_series && (
                        <div>
                          <p className="text-xs font-semibold mb-2" style={{ color: 'rgba(255,255,255,0.5)' }}>
                            48-Hour Discharge Forecast
                          </p>
                          <div className="relative h-32">
                            <svg viewBox="0 0 400 100" className="w-full h-full" preserveAspectRatio="none">
                              {/* Base line */}
                              <polyline
                                points={twinResult.time_series.slice(0, 48).map((t: any, i: number) => {
                                  const x = (i / 47) * 400
                                  const maxVal = Math.max(...twinResult.time_series.map((t: any) => t.scenario_discharge_cfs))
                                  const y = 90 - (t.discharge_cfs / maxVal) * 80
                                  return `${x},${y}`
                                }).join(' ')}
                                fill="none" stroke="#00E676" strokeWidth="1.5" opacity="0.7"
                              />
                              {/* Scenario line */}
                              <polyline
                                points={twinResult.time_series.slice(0, 48).map((t: any, i: number) => {
                                  const x = (i / 47) * 400
                                  const maxVal = Math.max(...twinResult.time_series.map((t: any) => t.scenario_discharge_cfs))
                                  const y = 90 - (t.scenario_discharge_cfs / maxVal) * 80
                                  return `${x},${y}`
                                }).join(' ')}
                                fill="none" stroke="#FF6B6B" strokeWidth="2" opacity="0.9"
                              />
                              {/* Flood stage line */}
                              <line x1="0" y1="25" x2="400" y2="25"
                                stroke="#FFD700" strokeWidth="1" strokeDasharray="4 4" opacity="0.5" />
                            </svg>
                            <div className="absolute top-2 right-0 flex items-center gap-3 text-xs"
                                 style={{ color: 'rgba(255,255,255,0.5)' }}>
                              <span className="flex items-center gap-1"><span style={{ color: '#00E676' }}>━</span> Base</span>
                              <span className="flex items-center gap-1"><span style={{ color: '#FF6B6B' }}>━</span> Scenario</span>
                              <span className="flex items-center gap-1"><span style={{ color: '#FFD700' }}>┄</span> Flood Stage</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-64 text-center">
                      <motion.div
                        animate={{ rotate: [0, 10, -10, 0], scale: [1, 1.1, 1] }}
                        transition={{ duration: 3, repeat: Infinity }}
                        className="text-6xl mb-4"
                      >
                        🔮
                      </motion.div>
                      <p className="text-white font-semibold mb-2">Select a Scenario</p>
                      <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
                        Choose a what-if scenario and click Run Simulation to see<br />
                        hour-by-hour downstream impact predictions
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

        </AnimatePresence>

        {/* ── Bottom: Emergency contacts ──────────────────────── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="mt-4 flex items-center justify-between px-4 py-3 rounded-xl"
          style={{
            background: 'linear-gradient(135deg, rgba(255,59,59,0.08), rgba(255,140,0,0.05))',
            border: '1px solid rgba(255,59,59,0.15)',
          }}
        >
          <div className="flex items-center gap-2">
            <motion.span animate={{ opacity: [0.7, 1, 0.7] }} transition={{ duration: 1.5, repeat: Infinity }}>
              🛡️
            </motion.span>
            <span className="text-xs font-semibold text-white">Emergency Response</span>
          </div>
          <div className="flex items-center gap-6 text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>
            <span>NDMA: <strong className="text-red-400">1078</strong></span>
            <span>NDRF: <strong className="text-red-400">011-24363260</strong></span>
            <span>IMD: <a href="https://mausam.imd.gov.in" className="text-cyan-400">mausam.imd.gov.in</a></span>
            <span>CWC: <a href="https://cwc.gov.in" className="text-cyan-400">cwc.gov.in</a></span>
          </div>
        </motion.div>

      </div>
    </div>
  )
}
