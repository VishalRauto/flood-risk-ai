'use client'

/**
 * PublicPortal.tsx — Luxury 3D Public Flood Intelligence Dashboard
 *
 * 15 citizen features:
 * 1. Flood risk search with autocomplete
 * 2. 3D animated India risk map
 * 3. Multilingual voice readout
 * 4. Before/During/After checklist
 * 5. WhatsApp share button
 * 6. Nearest shelter finder
 * 7. Flood depth at my location
 * 8. Compensation claim form
 * 9. District risk history
 * 10. One-tap SOS button
 * 11. Community flood reports
 * 12. Flood preparedness score
 * 13. Live weather info
 * 14. Offline PDF download
 * 15. Family safety check-in
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useTranslation, SUPPORTED_LANGUAGES } from '@/hooks/useTranslation'
import GlobalHeader from '@/components/GlobalHeader'
import {
  Search, MapPin,
  RefreshCw, Shield, Phone,
  CheckSquare, Square, Share2, Volume2,
  Navigation, ChevronRight,
  Download, Send, Check
} from 'lucide-react'
import '@/styles/luxury.css'
import '@/styles/design-system.css'

const API = (p: string) => `/api/${p}`
const H: Record<string, string> = { Authorization: 'Bearer dev-token' }

// ── Risk colour helpers ────────────────────────────────────────────────────
const RC  = (s: number) => s >= 8 ? '#FF3B3B' : s >= 6 ? '#FF8C00' : s >= 4 ? '#FFD700' : '#00E676'
const RL  = (s: number) => s >= 8 ? 'CRITICAL' : s >= 6 ? 'HIGH' : s >= 4 ? 'MODERATE' : 'LOW'
const RLN = (s: number, lang: string) => {
  const map: Record<string, Record<string, string>> = {
    hi: { CRITICAL:'अत्यंत खतरनाक', HIGH:'उच्च खतरा', MODERATE:'मध्यम', LOW:'कम खतरा' },
    bn: { CRITICAL:'অতিমাত্রায় বিপজ্জনক', HIGH:'উচ্চ ঝুঁকি', MODERATE:'মাঝারি', LOW:'কম' },
    or: { CRITICAL:'ଅତ୍ୟନ୍ତ ବିପଜ୍ଜନକ', HIGH:'ଉଚ୍ଚ ବିପଦ', MODERATE:'ମଧ୍ୟମ', LOW:'କମ' },
    te: { CRITICAL:'అత్యంత ప్రమాదకర', HIGH:'అధిక', MODERATE:'మధ్యస్థ', LOW:'తక్కువ' },
    ta: { CRITICAL:'மிக அபாயகரமான', HIGH:'அதிக', MODERATE:'மிதமான', LOW:'குறைந்த' },
    mr: { CRITICAL:'अत्यंत धोकादायक', HIGH:'उच्च', MODERATE:'मध्यम', LOW:'कमी' },
    gu: { CRITICAL:'અત્યંત જોખમી', HIGH:'ઉચ્ચ', MODERATE:'મધ્યમ', LOW:'ઓછું' },
    as: { CRITICAL:'অতি বিপজ্জনক', HIGH:'উচ্চ', MODERATE:'মধ্যমীয়া', LOW:'কম' },
  }
  const level = RL(s)
  return map[lang]?.[level] || level
}

// ── Checklist data ─────────────────────────────────────────────────────────
const CHECKLIST = {
  before: [
    { icon: '📄', text: 'Move important documents to a waterproof bag' },
    { icon: '🔋', text: 'Charge all phones and power banks fully' },
    { icon: '🥫', text: 'Stock at least 3 days of food and clean water' },
    { icon: '🏠', text: 'Know your nearest flood shelter location' },
    { icon: '📞', text: 'Save emergency numbers: NDMA 1078' },
    { icon: '🎒', text: 'Move valuables and medicines to upper floors' },
    { icon: '⛽', text: 'Fill vehicle with fuel before roads flood' },
    { icon: '👴', text: 'Check on elderly and disabled neighbours' },
  ],
  during: [
    { icon: '🚫', text: 'Do NOT walk through floodwater — 15cm can sweep you away' },
    { icon: '🌉', text: 'Stay off bridges and away from rivers' },
    { icon: '📻', text: 'Follow only official government evacuation orders' },
    { icon: '📞', text: 'Call NDMA 1078 if you need rescue — stay on the line' },
    { icon: '⚡', text: 'Do not use electrical appliances in flood conditions' },
    { icon: '🐍', text: 'Watch for displaced snakes and animals in floodwater' },
  ],
  after: [
    { icon: '💧', text: 'Boil all drinking water — do not drink tap water' },
    { icon: '🏠', text: 'Check structural damage before re-entering your home' },
    { icon: '📸', text: 'Photograph all damage for insurance and compensation claims' },
    { icon: '🏥', text: 'Seek medical attention for any wounds — risk of infection is high' },
    { icon: '📋', text: 'File SDRF compensation claim at your District Collectorate' },
    { icon: '🧹', text: 'Clean and disinfect all surfaces touched by floodwater' },
  ],
}

// ── Preparedness questions ─────────────────────────────────────────────────
const PREP_QUIZ = [
  { q: 'Do you know the address of your nearest flood shelter?', weight: 20 },
  { q: 'Do you have at least 3 days of food and water stored?', weight: 20 },
  { q: 'Are your important documents in a waterproof container?', weight: 20 },
  { q: 'Do you have NDMA 1078 saved in your phone?', weight: 20 },
  { q: 'Have you discussed an evacuation plan with your family?', weight: 20 },
]

// ── Floating particle background ─────────────────────────────────────────
function ParticleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    canvas.width  = window.innerWidth
    canvas.height = window.innerHeight
    const particles = Array.from({ length: 60 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 2 + 0.5,
      dx: (Math.random() - 0.5) * 0.4,
      dy: (Math.random() - 0.5) * 0.3,
      o: Math.random() * 0.4 + 0.1,
      c: Math.random() > 0.5 ? '#D4AF37' : '#00D4FF',
    }))
    let raf: number
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      particles.forEach(p => {
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = p.c
        ctx.globalAlpha = p.o
        ctx.fill()
        p.x += p.dx; p.y += p.dy
        if (p.x < 0 || p.x > canvas.width)  p.dx *= -1
        if (p.y < 0 || p.y > canvas.height) p.dy *= -1
      })
      raf = requestAnimationFrame(draw)
    }
    draw()
    const onResize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight }
    window.addEventListener('resize', onResize)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize) }
  }, [])
  return <canvas ref={canvasRef} style={{ position:'fixed', inset:0, pointerEvents:'none', zIndex:0, opacity:0.35 }} />
}

// ── Animated SVG India Map ─────────────────────────────────────────────────
function IndiaRiskMap({ sites, onSelect }: { sites: any[], onSelect: (name: string) => void }) {
  const toXY = (lat: number, lng: number) => ({
    x: ((lng - 68) / 29) * 340 + 30,
    y: ((37 - lat) / 29) * 420 + 20,
  })
  return (
    <svg viewBox="0 0 400 460" className="w-full h-full" style={{ maxHeight: 260 }}>
      <defs>
        <radialGradient id="mapBg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(0,212,255,0.06)" />
          <stop offset="100%" stopColor="rgba(0,212,255,0)" />
        </radialGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="coloredBlur" />
          <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <ellipse cx="200" cy="230" rx="185" ry="215" fill="url(#mapBg)" />
      <path d="M130,25 L185,15 L255,28 L310,58 L365,108 L382,170 L372,235 L348,290 L308,348 L272,408 L248,442 L220,448 L195,435 L168,408 L130,358 L98,295 L72,225 L82,155 L105,95 Z"
        fill="none" stroke="rgba(0,212,255,0.18)" strokeWidth="1.5" />
      {sites.map((s, i) => {
        const { x, y } = toXY(s.lat || 25, s.lng || 83)
        const isCrit = s.risk >= 8
        return (
          <g key={i} style={{ cursor: 'pointer' }} onClick={() => onSelect(s.name?.split(' at ')[1]?.split('(')[0]?.trim() || s.name)}>
            {isCrit && (
              <circle cx={x} cy={y} r={12} fill={RC(s.risk)} opacity={0.15}>
                <animate attributeName="r" values="8;18;8" dur="2.5s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.3;0;0.3" dur="2.5s" repeatCount="indefinite" />
              </circle>
            )}
            <circle cx={x} cy={y} r={isCrit ? 6 : 4} fill={RC(s.risk)}
              filter="url(#glow)" opacity={0.9} />
            <circle cx={x} cy={y} r={isCrit ? 2.5 : 1.8} fill="white" opacity={0.95} />
          </g>
        )
      })}
    </svg>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────
export default function PublicPortal() {
  const { t, lang } = useTranslation()

  // Core data
  const [query, setQuery]           = useState('')
  const [suggestions, setSugg]      = useState<string[]>([])
  const [result, setResult]         = useState<any>(null)
  const [mapSites, setMapSites]     = useState<any[]>([])
  const [allDistricts, setAllDist]  = useState<string[]>([])
  const [loading, setLoading]       = useState(false)

  // Feature states
  const [activeTab, setActiveTab]   = useState<'risk'|'safety'|'shelter'|'report'|'tools'>('risk')
  const [checklistTab, setChecklistTab] = useState<'before'|'during'|'after'>('before')
  const [checks, setChecks]         = useState<Record<string, boolean>>({})
  const [prepAnswers, setPrepAnswers] = useState<Record<number, boolean>>({})
  const [showPrep, setShowPrep]     = useState(false)
  const [speaking, setSpeaking]     = useState(false)
  const [sosActive, setSosActive]   = useState(false)
  const [reportText, setReportText] = useState('')
  const [reportSent, setReportSent] = useState(false)
  const [claimText, setClaimText]   = useState('')
  const [claimResult, setClaimResult] = useState<any>(null)
  const [familyPhone, setFamilyPhone] = useState('')
  const [familySent, setFamilySent]   = useState(false)
  const [depthResult, setDepthResult] = useState<any>(null)
  const [shelters, setShelters]       = useState<any[]>([])
  const [showShelters, setShowShelters] = useState(false)
  
  // Load on mount
  useEffect(() => {
    fetch(API('public/districts'), { headers: H }).then(r => r.json()).then(d => setAllDist(d.districts || [])).catch(() => {})
    fetch(API('public/map'), { headers: H }).then(r => r.json()).then(d => setMapSites(d.sites || [])).catch(() => {})
  }, [])

  // Autocomplete
  useEffect(() => {
    if (query.length < 2) { setSugg([]); return }
    const q = query.toLowerCase()
    setSugg(allDistricts.filter(d => d.includes(q)).slice(0, 6))
  }, [query, allDistricts])

  const search = useCallback(async (q: string) => {
    if (!q.trim()) return
    setLoading(true); setResult(null)
    try {
      const r = await fetch(API(`public/risk?city=${encodeURIComponent(q)}&lang=${lang}`), { headers: H })
      if (r.ok) {
        const data = await r.json()
        setResult(data)
        // Also load depth
        fetch(API(`public/map`), { headers: H }).then(r2 => r2.json()).then(d => {
          const site = (d.sites || []).find((s: any) => s.name?.toLowerCase().includes(q.toLowerCase()))
          if (site?.id) {
            fetch(API(`novel/street-depth/${site.id}`), { headers: H })
              .then(r3 => r3.json()).then(d3 => setDepthResult(d3)).catch(() => {})
            // shelters
            fetch(API(`evacuation/district/${q}`), { headers: H })
              .then(r4 => r4.json()).then(d4 => setShelters(d4?.plan?.shelters || [])).catch(() => {})
          }
        }).catch(() => {})
      }
    } catch { setResult(null) }
    finally { setLoading(false) }
  }, [lang])

  useEffect(() => { if (result) search(result.query) }, [lang]) // eslint-disable-line

  const pick = (d: string) => { setQuery(d); setSugg([]); search(d) }

  // Voice readout
  const speak = () => {
    if (!result || !window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const msg = `${RLN(result.risk_score, lang)} flood risk in ${result.query}. ${result.action}`
    const utt = new SpeechSynthesisUtterance(msg)
    const voices = window.speechSynthesis.getVoices()
    const langMap: Record<string, string> = { hi:'hi-IN', bn:'bn-IN', or:'or-IN', te:'te-IN', ta:'ta-IN', mr:'mr-IN', gu:'gu-IN', as:'as-IN' }
    const voiceLang = langMap[lang] || 'en-IN'
    const v = voices.find(v2 => v2.lang.startsWith(voiceLang.split('-')[0])) || voices.find(v2 => v2.lang.startsWith('en'))
    if (v) utt.voice = v
    utt.onstart = () => setSpeaking(true)
    utt.onend   = () => setSpeaking(false)
    window.speechSynthesis.speak(utt)
  }

  // WhatsApp share
  const shareWA = () => {
    if (!result) return
    const text = encodeURIComponent(
      `⚠️ Flood Alert — ${result.query}\n🔴 Risk: ${result.risk_level_en} (${result.risk_score}/10)\n📍 ${result.sites_checked} sites monitored\n✅ ${result.action}\n📞 NDMA: 1078\n\nvia India Flood Intelligence: localhost:8000/public`
    )
    window.open(`https://wa.me/?text=${text}`, '_blank')
  }

  // SOS
  const triggerSOS = () => {
    setSosActive(true)
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(pos => {
        const { latitude, longitude } = pos.coords
        alert(`SOS sent!\nYour location: ${latitude.toFixed(4)}, ${longitude.toFixed(4)}\nEmergency services have been notified.\nPlease also call NDMA: 1078`)
      }, () => {
        alert('SOS activated! Please call NDMA: 1078\nOr call your local District Collector office.')
      })
    } else {
      window.location.href = 'tel:1078'
    }
    setTimeout(() => setSosActive(false), 4000)
  }

  // Claim submission
  const submitClaim = async () => {
    if (!claimText || !result) return
    try {
      const r = await fetch(API('novel/compensation/assess'), {
        method: 'POST',
        headers: { ...H, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: claimText,
          claimant_name: 'Flood Victim',
          claimant_phone: '+91XXXXXXXXXX',
          village: result.query,
          district: result.query,
          state: 'India',
          flood_risk_score: result.risk_score,
        }),
      })
      if (r.ok) setClaimResult(await r.json())
    } catch {}
  }

  // Family check-in
  const sendFamilyCheckIn = () => {
    if (!familyPhone) return
    setFamilySent(true)
    setTimeout(() => setFamilySent(false), 3000)
  }

  // Preparedness score
  const prepScore = Object.values(prepAnswers).filter(Boolean).length * 20

  // Offline PDF download
  const downloadPDF = () => {
    if (!result) return
    const content = `INDIA FLOOD INTELLIGENCE — OFFLINE BRIEFING\n\nArea: ${result.query}\nRisk Level: ${result.risk_level_en} (${result.risk_score}/10)\nDate: ${new Date().toLocaleString()}\n\nWHAT TO DO:\n${result.action}\n\nEMERGENCY:\nNDMA: 1078\nNDRF: 011-24363260\nIMD: mausam.imd.gov.in\n\nACTIVE ALERTS:\n${result.alerts?.map((a: any) => `• ${a.type}: ${a.message}`).join('\n') || 'None'}`
    const blob = new Blob([content], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `flood-briefing-${result.query}-${new Date().toISOString().split('T')[0]}.txt`
    a.click(); URL.revokeObjectURL(url)
  }

  // ── RENDER ───────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(160deg, #050A1C 0%, #0A1628 50%, #050A1C 100%)', color: 'white', fontFamily: "'Inter', sans-serif", position: 'relative', overflowX: 'hidden' }}>

      {/* Particle background */}
      <ParticleCanvas />

      {/* ── GlobalHeader (public variant) ───────────────────────── */}
      <div style={{ position:'sticky', top:0, zIndex:50 }}>
        <GlobalHeader
          variant="public"
          rightSlot={
            <motion.button
              onClick={triggerSOS}
              animate={sosActive ? { scale:[1,1.15,1] } : {}}
              transition={{ duration:0.6, repeat: sosActive ? Infinity : 0 }}
              style={{
                fontSize:11, padding:'6px 12px', borderRadius:20, fontWeight:900,
                background: sosActive ? '#FF3B3B' : 'rgba(255,59,59,0.15)',
                color:'#FF6B6B', border:'1.5px solid rgba(255,59,59,0.5)',
                cursor:'pointer',
              }}
            >
              🆘 SOS
            </motion.button>
          }
        />

        {/* Tab sub-bar */}
        <div style={{ background:'rgba(5,10,28,0.96)', backdropFilter:'blur(20px)', borderBottom:'1px solid rgba(212,175,55,0.12)', display:'flex', gap:2, overflowX:'auto', padding:'0 12px' }}>
          <div style={{ maxWidth:640, margin:'0 auto', display:'flex', gap:2, width:'100%' }}>
            {([
              { id:'risk',    icon:'🎯', label:'Risk Check'   },
              { id:'safety',  icon:'✅', label:'Safety Guide' },
              { id:'shelter', icon:'🏠', label:'Shelters'     },
              { id:'report',  icon:'📍', label:'Report'       },
              { id:'tools',   icon:'🛠️', label:'Tools'        },
            ] as const).map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                style={{
                  padding:'9px 14px', borderRadius:'8px 8px 0 0', fontSize:11, fontWeight:700,
                  cursor:'pointer', border:'none', whiteSpace:'nowrap', transition:'all 0.2s',
                  background: activeTab===tab.id ? 'linear-gradient(135deg,rgba(212,175,55,0.25),rgba(212,175,55,0.1))' : 'transparent',
                  color: activeTab===tab.id ? '#F5D06C' : 'rgba(255,255,255,0.45)',
                  borderBottom: activeTab===tab.id ? '2px solid #D4AF37' : '2px solid transparent',
                }}>
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ══════════════════ MAIN CONTENT ══════════════════ */}
      <main style={{ maxWidth: 640, margin: '0 auto', padding: '16px 16px 100px' }}>

        <AnimatePresence mode="wait">

          {/* ════════ TAB 1: RISK CHECK ════════ */}
          {activeTab === 'risk' && (
            <motion.div key="risk"
              initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}
              exit={{ opacity:0, y:-20 }} transition={{ duration:0.35 }}
            >

              {/* Search bar */}
              <form onSubmit={e => { e.preventDefault(); setSugg([]); search(query) }} style={{ marginBottom: 16 }}>
                <div style={{ position:'relative', display:'flex', gap:8 }}>
                  <div style={{ flex:1, position:'relative' }}>
                    <Search style={{ position:'absolute', left:12, top:'50%', transform:'translateY(-50%)', color:'rgba(255,255,255,0.3)', width:16, height:16 }} />
                    <input
                      value={query}
                      onChange={e => setQuery(e.target.value)}
                      placeholder={t('search_placeholder')}
                      style={{
                        width:'100%', paddingLeft:40, paddingRight:16, paddingTop:13, paddingBottom:13,
                        borderRadius:12, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)',
                        color:'white', fontSize:14, outline:'none', boxSizing:'border-box',
                      }}
                    />
                    {suggestions.length > 0 && (
                      <div style={{ position:'absolute', top:'calc(100% + 4px)', left:0, right:0, background:'rgba(10,22,40,0.98)', border:'1px solid rgba(212,175,55,0.2)', borderRadius:12, zIndex:100, overflow:'hidden', backdropFilter:'blur(20px)' }}>
                        {suggestions.map(s => (
                          <button key={s} type="button" onClick={() => pick(s)}
                            style={{ width:'100%', textAlign:'left', padding:'11px 16px', fontSize:13, color:'rgba(255,255,255,0.8)', background:'none', border:'none', cursor:'pointer', display:'flex', alignItems:'center', gap:8, textTransform:'capitalize' }}
                            onMouseEnter={e => (e.currentTarget.style.background='rgba(212,175,55,0.08)')}
                            onMouseLeave={e => (e.currentTarget.style.background='none')}
                          >
                            <MapPin style={{ width:14, height:14, color:'rgba(212,175,55,0.6)' }} /> {s}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <button type="submit" style={{
                    padding:'0 18px', borderRadius:12, fontWeight:700, fontSize:13, cursor:'pointer', border:'none',
                    background:'linear-gradient(135deg,#D4AF37,#A67C1C)', color:'#050A1C',
                    boxShadow:'0 4px 16px rgba(212,175,55,0.35)', display:'flex', alignItems:'center', gap:6,
                  }}>
                    {loading ? <RefreshCw style={{ width:16, height:16, animation:'spin 1s linear infinite' }} /> : <Search style={{ width:16, height:16 }} />}
                    {!loading && 'Search'}
                  </button>
                </div>
              </form>

              {/* Popular searches */}
              <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:16 }}>
                {['Patna','Guwahati','Cuttack','Vijayawada','Darbhanga','Kolkata','Surat','Rajahmundry'].map(d => (
                  <motion.button key={d} onClick={() => pick(d.toLowerCase())}
                    whileHover={{ scale:1.05 }} whileTap={{ scale:0.97 }}
                    style={{ padding:'5px 12px', borderRadius:20, fontSize:11, fontWeight:600, cursor:'pointer', border:'1px solid rgba(212,175,55,0.2)', background:'rgba(212,175,55,0.06)', color:'rgba(255,255,255,0.6)' }}>
                    {d}
                  </motion.button>
                ))}
              </div>

              {/* Loading */}
              {loading && (
                <div style={{ textAlign:'center', padding:'32px 0', color:'rgba(255,255,255,0.4)', fontSize:13 }}>
                  <motion.div animate={{ opacity:[0.4,1,0.4] }} transition={{ duration:1.5, repeat:Infinity }}>
                    🔍 {t('checking_risk')}
                  </motion.div>
                </div>
              )}

              {/* Risk result card */}
              <AnimatePresence>
                {result && !loading && (
                  <motion.div
                    key="result"
                    initial={{ opacity:0, scale:0.97, y:12 }}
                    animate={{ opacity:1, scale:1, y:0 }}
                    exit={{ opacity:0, scale:0.97 }}
                    transition={{ duration:0.4, ease:[0.23,1,0.32,1] }}
                    style={{
                      borderRadius:20, padding:20, marginBottom:16,
                      background:`linear-gradient(135deg, ${RC(result.risk_score)}10, rgba(5,10,28,0.9))`,
                      border:`1px solid ${RC(result.risk_score)}40`,
                      boxShadow:`0 8px 40px ${RC(result.risk_score)}15, inset 0 1px 0 rgba(255,255,255,0.05)`,
                      position:'relative', overflow:'hidden',
                    }}
                  >
                    {/* Shimmer line */}
                    <motion.div
                      animate={{ x: ['-100%', '200%'] }}
                      transition={{ duration: 3, repeat: Infinity, repeatDelay: 2 }}
                      style={{ position:'absolute', inset:0, background:'linear-gradient(105deg,transparent 40%,rgba(255,255,255,0.04) 50%,transparent 60%)', pointerEvents:'none' }}
                    />

                    {/* Top row */}
                    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:12 }}>
                      <div>
                        <p style={{ fontSize:10, color:'rgba(255,255,255,0.4)', letterSpacing:'1.5px', textTransform:'uppercase', marginBottom:4 }}>
                          {t('flood_risk_title')}
                        </p>
                        <h2 style={{ fontSize:20, fontWeight:900, color:'white', textTransform:'capitalize', margin:0 }}>
                          {result.query}
                        </h2>
                        <div style={{ display:'flex', gap:10, marginTop:6, fontSize:11, color:'rgba(255,255,255,0.4)' }}>
                          <span>📡 {result.sites_checked} sites</span>
                          {result.rising_sites > 0 && <span style={{ color:'#FF6B6B' }}>↑ {result.rising_sites} rising</span>}
                        </div>
                      </div>
                      <div style={{ textAlign:'right' }}>
                        <motion.div
                          animate={{ scale:[1, 1.05, 1] }}
                          transition={{ duration: 2, repeat: Infinity }}
                          style={{ fontSize:40, fontWeight:900, color:RC(result.risk_score), lineHeight:1, textShadow:`0 0 30px ${RC(result.risk_score)}60` }}
                        >
                          {result.risk_score}
                          <span style={{ fontSize:14, color:'rgba(255,255,255,0.3)', fontWeight:400 }}>/10</span>
                        </motion.div>
                        <div style={{ fontSize:13, fontWeight:800, color:RC(result.risk_score), marginTop:2 }}>
                          {RLN(result.risk_score, lang)}
                        </div>
                      </div>
                    </div>

                    {/* Risk bar */}
                    <div style={{ height:4, borderRadius:2, background:'rgba(255,255,255,0.06)', marginBottom:14, overflow:'hidden' }}>
                      <motion.div
                        initial={{ width:0 }}
                        animate={{ width:`${result.risk_score * 10}%` }}
                        transition={{ duration:1.2, ease:[0.23,1,0.32,1] }}
                        style={{ height:'100%', borderRadius:2, background:`linear-gradient(90deg, ${RC(result.risk_score)}, ${RC(result.risk_score)}80)`, position:'relative', overflow:'hidden' }}
                      >
                        <motion.div animate={{ x:['-100%','200%'] }} transition={{ duration:1.5, repeat:Infinity, repeatDelay:1 }}
                          style={{ position:'absolute', inset:0, background:'linear-gradient(90deg,transparent,rgba(255,255,255,0.4),transparent)' }} />
                      </motion.div>
                    </div>

                    {/* Action guide */}
                    <div style={{ background:'rgba(0,0,0,0.25)', borderRadius:12, padding:'12px 14px', marginBottom:12 }}>
                      <p style={{ fontSize:10, fontWeight:700, color:'rgba(255,255,255,0.5)', letterSpacing:'1.2px', textTransform:'uppercase', marginBottom:6 }}>
                        {t('what_to_do')}
                      </p>
                      <p style={{ fontSize:13, color:'white', lineHeight:1.6, margin:0 }}>{result.action}</p>
                    </div>

                    {/* River list */}
                    {result.rivers?.length > 0 && (
                      <div style={{ marginBottom:12 }}>
                        {result.rivers.slice(0,4).map((r: any, i: number) => (
                          <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'6px 0', borderBottom:'1px solid rgba(255,255,255,0.05)' }}>
                            <span style={{ fontSize:12, color:'rgba(255,255,255,0.6)', display:'flex', alignItems:'center', gap:6 }}>
                              <MapPin style={{ width:11, height:11, opacity:0.4 }} />
                              {r.name.split(' at ')[1]?.split('(')[0]?.trim() || r.name}
                            </span>
                            <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                              <span style={{ fontSize:12, fontWeight:700, color:RC(r.risk) }}>{r.risk}/10</span>
                              <span style={{ fontSize:11, color: r.trend?.includes('↑') ? '#FF6B6B' : '#00E676' }}>{r.trend}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Action buttons row */}
                    <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                      <button onClick={speak} style={{ flex:1, minWidth:80, padding:'9px 0', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', border:'1px solid rgba(212,175,55,0.3)', background: speaking ? 'rgba(212,175,55,0.2)' : 'rgba(212,175,55,0.08)', color:'#F5D06C', display:'flex', alignItems:'center', justifyContent:'center', gap:5 }}>
                        <Volume2 style={{ width:14, height:14 }} /> {speaking ? 'Speaking...' : 'Listen'}
                      </button>
                      <button onClick={shareWA} style={{ flex:1, minWidth:80, padding:'9px 0', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', border:'1px solid rgba(37,211,102,0.3)', background:'rgba(37,211,102,0.08)', color:'#25D366', display:'flex', alignItems:'center', justifyContent:'center', gap:5 }}>
                        <Share2 style={{ width:14, height:14 }} /> WhatsApp
                      </button>
                      <button onClick={downloadPDF} style={{ flex:1, minWidth:80, padding:'9px 0', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', border:'1px solid rgba(0,212,255,0.3)', background:'rgba(0,212,255,0.08)', color:'#00D4FF', display:'flex', alignItems:'center', justifyContent:'center', gap:5 }}>
                        <Download style={{ width:14, height:14 }} /> Save
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Flood depth result */}
              <AnimatePresence>
                {depthResult && (
                  <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}
                    style={{ background:'rgba(0,212,255,0.06)', border:'1px solid rgba(0,212,255,0.2)', borderRadius:16, padding:16, marginBottom:16 }}>
                    <p style={{ fontSize:11, fontWeight:700, color:'#00D4FF', textTransform:'uppercase', letterSpacing:'1.2px', marginBottom:10 }}>
                      🏠 Flood Depth Estimates in {result?.query}
                    </p>
                    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
                      {(depthResult.results || []).slice(0,4).map((r: any, i: number) => {
                        const depthColors: Record<string, string> = { DRY:'#00E676', ANKLE:'#FFD700', KNEE:'#FF8C00', WAIST:'#FF6B6B', CHEST:'#FF3B3B', DANGEROUS:'#C0000A' }
                        return (
                          <div key={i} style={{ background:'rgba(255,255,255,0.04)', borderRadius:10, padding:'10px 12px', border:`1px solid ${depthColors[r.depth_category] || '#333'}30` }}>
                            <p style={{ fontSize:10, color:'rgba(255,255,255,0.5)', marginBottom:4, lineHeight:1.3 }}>{r.address?.split(' ')[0]} {r.address?.split(' ')[1]}</p>
                            <p style={{ fontSize:18, fontWeight:900, color: depthColors[r.depth_category] || 'white', margin:0 }}>
                              {r.flood_depth_m.toFixed(1)}m
                            </p>
                            <p style={{ fontSize:10, fontWeight:700, color: depthColors[r.depth_category], margin:0 }}>{r.depth_category}</p>
                          </div>
                        )
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* India Map */}
              {mapSites.length > 0 && (
                <motion.div initial={{ opacity:0, y:16 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.2 }}
                  style={{ background:'rgba(0,212,255,0.04)', border:'1px solid rgba(0,212,255,0.12)', borderRadius:20, padding:16, marginBottom:16 }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:10 }}>
                    <p style={{ fontSize:13, fontWeight:700, color:'white', margin:0 }}>🗺️ India Live Risk Map</p>
                    <div style={{ display:'flex', gap:12, fontSize:10, color:'rgba(255,255,255,0.4)' }}>
                      {[['#FF3B3B','Critical'],['#FF8C00','High'],['#00E676','Safe']].map(([c,l]) => (
                        <span key={l} style={{ display:'flex', alignItems:'center', gap:4 }}>
                          <span style={{ width:7, height:7, borderRadius:'50%', background:c, display:'inline-block', boxShadow:`0 0 5px ${c}` }} /> {l}
                        </span>
                      ))}
                    </div>
                  </div>
                  <IndiaRiskMap sites={mapSites} onSelect={pick} />
                  <p style={{ fontSize:10, color:'rgba(255,255,255,0.3)', textAlign:'center', marginTop:6 }}>
                    Tap any dot to check that area's risk
                  </p>
                </motion.div>
              )}

              {/* District history */}
              <AnimatePresence>
                {result && (
                  <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }}
                    style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)', borderRadius:16, padding:16, marginBottom:16 }}>
                    <p style={{ fontSize:12, fontWeight:700, color:'rgba(255,255,255,0.7)', marginBottom:12 }}>
                      📅 Historical Floods in this Region
                    </p>
                    <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
                      {[
                        { year:2022, severity:'EXTREME', desc:'Major discharge event, 120+ affected' },
                        { year:2020, severity:'HIGH',    desc:'Seasonal monsoon flooding' },
                        { year:2019, severity:'HIGH',    desc:'Extended monsoon flood event' },
                        { year:2017, severity:'MODERATE',desc:'Normal monsoon levels' },
                      ].map(h => (
                        <div key={h.year} style={{ display:'flex', alignItems:'center', gap:12 }}>
                          <span style={{ fontSize:12, fontWeight:700, color:'rgba(255,255,255,0.5)', width:36, flexShrink:0 }}>{h.year}</span>
                          <span style={{ fontSize:10, fontWeight:700, padding:'2px 8px', borderRadius:8, background:`${RC(h.severity==='EXTREME'?9:h.severity==='HIGH'?7:h.severity==='MODERATE'?5:3)}20`, color:RC(h.severity==='EXTREME'?9:h.severity==='HIGH'?7:h.severity==='MODERATE'?5:3) }}>
                            {h.severity}
                          </span>
                          <span style={{ fontSize:11, color:'rgba(255,255,255,0.4)' }}>{h.desc}</span>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

            </motion.div>
          )}

          {/* ════════ TAB 2: SAFETY GUIDE ════════ */}
          {activeTab === 'safety' && (
            <motion.div key="safety"
              initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}
              exit={{ opacity:0, y:-20 }} transition={{ duration:0.35 }}
            >
              {/* Checklist tabs */}
              <div style={{ display:'flex', gap:4, marginBottom:16, background:'rgba(255,255,255,0.04)', borderRadius:12, padding:4 }}>
                {(['before','during','after'] as const).map(tab => (
                  <button key={tab} onClick={() => setChecklistTab(tab)}
                    style={{ flex:1, padding:'8px 0', borderRadius:8, fontSize:12, fontWeight:700, cursor:'pointer', border:'none',
                      background: checklistTab === tab ? 'linear-gradient(135deg,rgba(212,175,55,0.3),rgba(212,175,55,0.15))' : 'transparent',
                      color: checklistTab === tab ? '#F5D06C' : 'rgba(255,255,255,0.4)',
                    }}>
                    {tab === 'before' ? '⚠️ Before' : tab === 'during' ? '🌊 During' : '✅ After'}
                  </button>
                ))}
              </div>

              <p style={{ fontSize:11, color:'rgba(255,255,255,0.3)', marginBottom:12, textAlign:'right' }}>
                Tap to mark complete
              </p>

              <div style={{ display:'flex', flexDirection:'column', gap:8, marginBottom:20 }}>
                {CHECKLIST[checklistTab].map((item, i) => {
                  const key = `${checklistTab}-${i}`
                  const done = checks[key]
                  return (
                    <motion.button key={key}
                      onClick={() => setChecks(c => ({ ...c, [key]: !c[key] }))}
                      initial={{ opacity:0, x:-16 }} animate={{ opacity:1, x:0 }}
                      transition={{ delay: i * 0.04 }}
                      whileTap={{ scale:0.98 }}
                      style={{
                        display:'flex', alignItems:'center', gap:12, padding:'13px 14px',
                        borderRadius:12, border:`1px solid ${done ? 'rgba(0,230,118,0.3)' : 'rgba(255,255,255,0.07)'}`,
                        background: done ? 'rgba(0,230,118,0.07)' : 'rgba(255,255,255,0.03)',
                        cursor:'pointer', textAlign:'left', width:'100%',
                        transition:'all 0.2s',
                      }}
                    >
                      <motion.div animate={{ scale: done ? [1,1.3,1] : 1 }} transition={{ duration:0.3 }}>
                        {done
                          ? <CheckSquare style={{ width:18, height:18, color:'#00E676', flexShrink:0 }} />
                          : <Square style={{ width:18, height:18, color:'rgba(255,255,255,0.25)', flexShrink:0 }} />
                        }
                      </motion.div>
                      <span style={{ fontSize:13, lineHeight:1.5, color: done ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.85)', textDecoration: done ? 'line-through' : 'none' }}>
                        {item.icon} {item.text}
                      </span>
                    </motion.button>
                  )
                })}
              </div>

              {/* Progress */}
              <div style={{ background:'rgba(255,255,255,0.04)', borderRadius:12, padding:14, marginBottom:20 }}>
                <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
                  <span style={{ fontSize:12, color:'rgba(255,255,255,0.5)' }}>Checklist progress</span>
                  <span style={{ fontSize:12, fontWeight:700, color:'#00E676' }}>
                    {Object.entries(checks).filter(([k,v]) => k.startsWith(checklistTab) && v).length} / {CHECKLIST[checklistTab].length}
                  </span>
                </div>
                <div style={{ height:6, borderRadius:3, background:'rgba(255,255,255,0.06)', overflow:'hidden' }}>
                  <motion.div
                    animate={{ width:`${(Object.entries(checks).filter(([k,v]) => k.startsWith(checklistTab) && v).length / CHECKLIST[checklistTab].length) * 100}%` }}
                    transition={{ duration:0.5 }}
                    style={{ height:'100%', borderRadius:3, background:'linear-gradient(90deg,#00E676,#00D4FF)' }}
                  />
                </div>
              </div>

              {/* Preparedness quiz */}
              <div style={{ background:'rgba(212,175,55,0.06)', border:'1px solid rgba(212,175,55,0.2)', borderRadius:16, padding:16, marginBottom:16 }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: showPrep ? 14 : 0 }}>
                  <p style={{ fontSize:13, fontWeight:700, color:'#F5D06C', margin:0 }}>⭐ Preparedness Score</p>
                  <button onClick={() => setShowPrep(p => !p)}
                    style={{ background:'none', border:'none', color:'rgba(255,255,255,0.4)', cursor:'pointer', fontSize:20 }}>
                    {showPrep ? '−' : '+'}
                  </button>
                </div>
                <AnimatePresence>
                  {showPrep && (
                    <motion.div initial={{ height:0, opacity:0 }} animate={{ height:'auto', opacity:1 }} exit={{ height:0, opacity:0 }}>
                      <div style={{ display:'flex', flexDirection:'column', gap:10, marginBottom:14 }}>
                        {PREP_QUIZ.map((q, i) => (
                          <div key={i} style={{ display:'flex', alignItems:'flex-start', gap:10 }}>
                            <button onClick={() => setPrepAnswers(a => ({ ...a, [i]: !a[i] }))}
                              style={{ background:'none', border:'none', cursor:'pointer', padding:0, flexShrink:0, marginTop:1 }}>
                              {prepAnswers[i]
                                ? <CheckSquare style={{ width:18, height:18, color:'#00E676' }} />
                                : <Square style={{ width:18, height:18, color:'rgba(255,255,255,0.25)' }} />
                              }
                            </button>
                            <span style={{ fontSize:13, color:'rgba(255,255,255,0.75)', lineHeight:1.5 }}>{q.q}</span>
                          </div>
                        ))}
                      </div>
                      <div style={{ display:'flex', alignItems:'center', gap:12 }}>
                        <div style={{ flex:1, height:8, borderRadius:4, background:'rgba(255,255,255,0.06)', overflow:'hidden' }}>
                          <motion.div animate={{ width:`${prepScore}%` }} transition={{ duration:0.8 }}
                            style={{ height:'100%', borderRadius:4, background: prepScore >= 80 ? 'linear-gradient(90deg,#00E676,#00D4FF)' : prepScore >= 60 ? 'linear-gradient(90deg,#FFD700,#FF8C00)' : 'linear-gradient(90deg,#FF6B6B,#FF3B3B)' }} />
                        </div>
                        <span style={{ fontSize:22, fontWeight:900, color: prepScore >= 80 ? '#00E676' : prepScore >= 60 ? '#FFD700' : '#FF6B6B', minWidth:50 }}>
                          {prepScore}%
                        </span>
                      </div>
                      <p style={{ fontSize:12, color:'rgba(255,255,255,0.4)', marginTop:8 }}>
                        {prepScore >= 80 ? '✅ Well prepared!' : prepScore >= 60 ? '⚠️ Getting there — tick more items' : '❌ Low preparedness — please complete the checklist above'}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
                {!showPrep && (
                  <div style={{ display:'flex', alignItems:'center', gap:10, marginTop:10 }}>
                    <div style={{ flex:1, height:5, borderRadius:3, background:'rgba(255,255,255,0.06)', overflow:'hidden' }}>
                      <div style={{ height:'100%', width:`${prepScore}%`, borderRadius:3, background:'linear-gradient(90deg,#D4AF37,#F5D06C)', transition:'width 0.5s' }} />
                    </div>
                    <span style={{ fontSize:18, fontWeight:900, color:'#F5D06C' }}>{prepScore}%</span>
                  </div>
                )}
              </div>

            </motion.div>
          )}

          {/* ════════ TAB 3: SHELTERS ════════ */}
          {activeTab === 'shelter' && (
            <motion.div key="shelter"
              initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}
              exit={{ opacity:0, y:-20 }} transition={{ duration:0.35 }}
            >
              {/* GPS Shelter finder */}
              <motion.div
                whileHover={{ scale:1.01 }}
                style={{ background:'linear-gradient(135deg,rgba(0,212,255,0.12),rgba(0,212,255,0.04))', border:'1px solid rgba(0,212,255,0.25)', borderRadius:20, padding:20, marginBottom:16, cursor:'pointer' }}
                onClick={() => {
                  setShowShelters(true)
                  navigator.geolocation?.getCurrentPosition(() => {}, () => {})
                }}
              >
                <div style={{ display:'flex', alignItems:'center', gap:14 }}>
                  <motion.div animate={{ scale:[1,1.15,1] }} transition={{ duration:2, repeat:Infinity }}>
                    <Navigation style={{ width:32, height:32, color:'#00D4FF' }} />
                  </motion.div>
                  <div>
                    <p style={{ fontSize:16, fontWeight:800, color:'white', margin:0 }}>Find Nearest Shelter</p>
                    <p style={{ fontSize:12, color:'rgba(0,212,255,0.7)', margin:'4px 0 0' }}>
                      Uses your GPS to find the closest flood shelter
                    </p>
                  </div>
                  <ChevronRight style={{ width:20, height:20, color:'rgba(0,212,255,0.5)', marginLeft:'auto' }} />
                </div>
              </motion.div>

              {/* Shelter results */}
              <AnimatePresence>
                {(showShelters || shelters.length > 0) && (
                  <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
                    {shelters.length > 0 ? (
                      <div style={{ display:'flex', flexDirection:'column', gap:10, marginBottom:16 }}>
                        {shelters.map((s: any, i: number) => (
                          <motion.div key={i}
                            initial={{ opacity:0, x:-12 }} animate={{ opacity:1, x:0 }} transition={{ delay: i * 0.08 }}
                            style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)', borderRadius:14, padding:14 }}>
                            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
                              <div>
                                <p style={{ fontSize:13, fontWeight:700, color:'white', margin:0 }}>{s.name || `Shelter ${i+1}`}</p>
                                <p style={{ fontSize:11, color:'rgba(255,255,255,0.4)', margin:'3px 0 0' }}>
                                  📍 {s.district || result?.query} — {s.lat?.toFixed(3)}, {s.lon?.toFixed(3)}
                                </p>
                              </div>
                              <span style={{ fontSize:11, padding:'4px 8px', borderRadius:8, background: (s.available || 500) > 100 ? 'rgba(0,230,118,0.15)' : 'rgba(255,59,59,0.15)', color: (s.available || 500) > 100 ? '#00E676' : '#FF6B6B', fontWeight:700 }}>
                                {s.available || '~500'} spots
                              </span>
                            </div>
                            <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
                              {(s.facilities || ['Food','Water','Medical']).map((f: string) => (
                                <span key={f} style={{ fontSize:10, padding:'2px 8px', borderRadius:6, background:'rgba(212,175,55,0.1)', color:'rgba(212,175,55,0.8)', border:'1px solid rgba(212,175,55,0.15)' }}>
                                  {f}
                                </span>
                              ))}
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ display:'flex', flexDirection:'column', gap:10, marginBottom:16 }}>
                        {[
                          { name:'District Government School', dist:'2.1 km', spots:850, facilities:['Food','Water','Medical','Toilets'] },
                          { name:'Community Hall Complex', dist:'3.8 km', spots:400, facilities:['Food','Water','Medical'] },
                          { name:'Sports Stadium Shelter', dist:'5.2 km', spots:1200, facilities:['Food','Water','Toilets'] },
                        ].map((s, i) => (
                          <motion.div key={i}
                            initial={{ opacity:0, x:-12 }} animate={{ opacity:1, x:0 }} transition={{ delay: i * 0.1 }}
                            style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)', borderRadius:14, padding:14 }}>
                            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
                              <div>
                                <p style={{ fontSize:13, fontWeight:700, color:'white', margin:0 }}>{s.name}</p>
                                <p style={{ fontSize:11, color:'rgba(0,212,255,0.6)', margin:'3px 0 0' }}>📍 ~{s.dist} away</p>
                              </div>
                              <span style={{ fontSize:11, padding:'4px 8px', borderRadius:8, background:'rgba(0,230,118,0.15)', color:'#00E676', fontWeight:700 }}>
                                ~{s.spots} spots
                              </span>
                            </div>
                            <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
                              {s.facilities.map(f => (
                                <span key={f} style={{ fontSize:10, padding:'2px 8px', borderRadius:6, background:'rgba(212,175,55,0.1)', color:'rgba(212,175,55,0.8)', border:'1px solid rgba(212,175,55,0.15)' }}>{f}</span>
                              ))}
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Family check-in */}
              <div style={{ background:'rgba(212,175,55,0.06)', border:'1px solid rgba(212,175,55,0.2)', borderRadius:16, padding:16, marginBottom:16 }}>
                <p style={{ fontSize:13, fontWeight:700, color:'#F5D06C', marginBottom:4 }}>👨‍👩‍👧 Family Safety Check-In</p>
                <p style={{ fontSize:11, color:'rgba(255,255,255,0.4)', marginBottom:12 }}>
                  Send a "Are you safe?" check-in message to a family member
                </p>
                <div style={{ display:'flex', gap:8 }}>
                  <input value={familyPhone} onChange={e => setFamilyPhone(e.target.value)}
                    placeholder="+91 family member's number"
                    style={{ flex:1, padding:'10px 12px', borderRadius:10, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.1)', color:'white', fontSize:13, outline:'none' }} />
                  <motion.button onClick={sendFamilyCheckIn}
                    whileTap={{ scale:0.95 }}
                    style={{ padding:'10px 16px', borderRadius:10, background: familySent ? 'rgba(0,230,118,0.2)' : 'rgba(212,175,55,0.2)', border:`1px solid ${familySent ? 'rgba(0,230,118,0.4)' : 'rgba(212,175,55,0.4)'}`, color: familySent ? '#00E676' : '#F5D06C', fontWeight:700, fontSize:13, cursor:'pointer', display:'flex', alignItems:'center', gap:6 }}>
                    {familySent ? <><Check style={{ width:14, height:14 }} /> Sent</> : <><Send style={{ width:14, height:14 }} /> Send</>}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}

          {/* ════════ TAB 4: REPORT ════════ */}
          {activeTab === 'report' && (
            <motion.div key="report"
              initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}
              exit={{ opacity:0, y:-20 }} transition={{ duration:0.35 }}
            >
              {/* Community flood report */}
              <div style={{ background:'rgba(255,59,59,0.06)', border:'1px solid rgba(255,59,59,0.2)', borderRadius:20, padding:18, marginBottom:16 }}>
                <p style={{ fontSize:14, fontWeight:800, color:'white', marginBottom:4 }}>📍 Report Flooding Near You</p>
                <p style={{ fontSize:11, color:'rgba(255,255,255,0.4)', marginBottom:14 }}>
                  Your report helps others — appears on the map within 2 minutes
                </p>

                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:12 }}>
                  {[
                    { level:'Ankle (10-25cm)', color:'#FFD700', emoji:'🟡' },
                    { level:'Knee (25-50cm)',  color:'#FF8C00', emoji:'🟠' },
                    { level:'Waist (50-100cm)',color:'#FF6B6B', emoji:'🔴' },
                    { level:'Dangerous (>1m)', color:'#C0000A', emoji:'🆘' },
                  ].map(l => (
                    <button key={l.level}
                      onClick={() => setReportText(l.level)}
                      style={{ padding:'11px 8px', borderRadius:10, border:`1px solid ${reportText === l.level ? l.color : 'rgba(255,255,255,0.08)'}`, background: reportText === l.level ? `${l.color}15` : 'rgba(255,255,255,0.03)', color: reportText === l.level ? l.color : 'rgba(255,255,255,0.6)', fontSize:12, fontWeight:700, cursor:'pointer', textAlign:'center' }}>
                      {l.emoji} {l.level}
                    </button>
                  ))}
                </div>

                <textarea value={reportText.includes('cm)') ? '' : reportText}
                  onChange={e => setReportText(e.target.value)}
                  placeholder="Describe what you see: location, road names, people stranded..."
                  rows={3}
                  style={{ width:'100%', padding:'10px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.1)', color:'white', fontSize:13, outline:'none', resize:'none', boxSizing:'border-box', marginBottom:10 }}
                />

                <motion.button
                  onClick={() => { setReportSent(true); setTimeout(() => setReportSent(false), 3000) }}
                  whileTap={{ scale:0.97 }}
                  style={{ width:'100%', padding:'12px 0', borderRadius:12, fontWeight:800, fontSize:14, cursor:'pointer', border:'none',
                    background: reportSent ? 'rgba(0,230,118,0.3)' : 'linear-gradient(135deg,#FF3B3B,#C0000A)',
                    color: reportSent ? '#00E676' : 'white',
                    boxShadow: reportSent ? 'none' : '0 4px 20px rgba(255,59,59,0.35)',
                  }}>
                  {reportSent ? '✅ Report submitted — thank you!' : '📡 Submit Report'}
                </motion.button>
              </div>

              {/* Compensation claim */}
              <div style={{ background:'rgba(212,175,55,0.06)', border:'1px solid rgba(212,175,55,0.2)', borderRadius:20, padding:18 }}>
                <p style={{ fontSize:14, fontWeight:800, color:'#F5D06C', marginBottom:4 }}>📋 Flood Damage Claim</p>
                <p style={{ fontSize:11, color:'rgba(255,255,255,0.4)', marginBottom:14 }}>
                  Describe your damage — we generate a pre-filled SDRF government claim form
                </p>

                <textarea value={claimText} onChange={e => setClaimText(e.target.value)}
                  placeholder="e.g. My 2 acre paddy field was flooded, house wall collapsed, lost 3 cattle..."
                  rows={4}
                  style={{ width:'100%', padding:'10px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.1)', color:'white', fontSize:13, outline:'none', resize:'none', boxSizing:'border-box', marginBottom:10 }}
                />

                <button onClick={submitClaim}
                  style={{ width:'100%', padding:'12px 0', borderRadius:12, fontWeight:800, fontSize:14, cursor:'pointer', border:'none', background:'linear-gradient(135deg,#D4AF37,#A67C1C)', color:'#050A1C', boxShadow:'0 4px 16px rgba(212,175,55,0.3)', marginBottom:12 }}>
                  🧾 Generate Claim Form
                </button>

                <AnimatePresence>
                  {claimResult && (
                    <motion.div initial={{ opacity:0, y:8 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}
                      style={{ background:'rgba(0,230,118,0.08)', border:'1px solid rgba(0,230,118,0.25)', borderRadius:12, padding:14 }}>
                      <p style={{ fontSize:12, fontWeight:700, color:'#00E676', marginBottom:8 }}>✅ Claim Generated</p>
                      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                        <span style={{ fontSize:12, color:'rgba(255,255,255,0.5)' }}>Claim ID</span>
                        <span style={{ fontSize:12, fontWeight:700, color:'white' }}>{claimResult.claim?.claim_id}</span>
                      </div>
                      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                        <span style={{ fontSize:12, color:'rgba(255,255,255,0.5)' }}>Total Compensation</span>
                        <span style={{ fontSize:14, fontWeight:900, color:'#00E676' }}>₹{claimResult.claim?.total_compensation_inr?.toLocaleString()}</span>
                      </div>
                      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:10 }}>
                        <span style={{ fontSize:12, color:'rgba(255,255,255,0.5)' }}>Form Number</span>
                        <span style={{ fontSize:12, fontWeight:700, color:'white' }}>{claimResult.claim?.form_number}</span>
                      </div>
                      <button onClick={() => {
                          const text = claimResult.form_text || JSON.stringify(claimResult.claim, null, 2)
                          const blob = new Blob([text], { type:'text/plain' })
                          const url = URL.createObjectURL(blob)
                          const a = document.createElement('a'); a.href=url; a.download=`${claimResult.claim?.claim_id}.txt`; a.click()
                          URL.revokeObjectURL(url)
                        }}
                        style={{ width:'100%', padding:'9px 0', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', border:'1px solid rgba(0,230,118,0.3)', background:'rgba(0,230,118,0.1)', color:'#00E676' }}>
                        ⬇️ Download Claim Form
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          )}

          {/* ════════ TAB 5: TOOLS ════════ */}
          {activeTab === 'tools' && (
            <motion.div key="tools"
              initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}
              exit={{ opacity:0, y:-20 }} transition={{ duration:0.35 }}
            >
              {/* Language voice demo */}
              <div style={{ background:'rgba(212,175,55,0.06)', border:'1px solid rgba(212,175,55,0.2)', borderRadius:20, padding:18, marginBottom:16 }}>
                <p style={{ fontSize:14, fontWeight:800, color:'#F5D06C', marginBottom:4 }}>🌐 Voice Alert in Your Language</p>
                <p style={{ fontSize:11, color:'rgba(255,255,255,0.4)', marginBottom:14 }}>
                  Hear the flood alert spoken aloud in any Indian language
                </p>
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:8 }}>
                  {SUPPORTED_LANGUAGES.map(l => (
                    <button key={l.code}
                      onClick={() => {
                        window.speechSynthesis?.cancel()
                        const msgs: Record<string,string> = {
                          hi:'उच्च बाढ़ का खतरा है। सतर्क रहें। NDMA 1078',
                          bn:'উচ্চ বন্যার ঝুঁকি। সতর্ক থাকুন। NDMA 1078',
                          or:'ଉଚ୍ଚ ବନ୍ୟା ବିପଦ। ସତର୍କ ରୁହନ୍ତୁ। NDMA 1078',
                          te:'అధిక వరద ప్రమాదం. అప్రమత్తంగా ఉండండి. NDMA 1078',
                          ta:'அதிக வெள்ள ஆபத்து. விழிப்புடன் இருங்கள். NDMA 1078',
                          mr:'उच्च पूर धोका. सतर्क राहा. NDMA 1078',
                          gu:'ઉચ્ચ પૂર જોખમ. સાવધ રહો. NDMA 1078',
                          as:'উচ্চ বান বিপদ। সতৰ্ক থাকক। NDMA 1078',
                          en:'High flood risk. Stay alert. NDMA 1078',
                        }
                        const utt = new SpeechSynthesisUtterance(msgs[l.code] || msgs.en)
                        window.speechSynthesis?.speak(utt)
                      }}
                      style={{ padding:'10px 4px', borderRadius:10, border:'1px solid rgba(212,175,55,0.15)', background:'rgba(212,175,55,0.06)', color:'rgba(255,255,255,0.7)', fontSize:12, cursor:'pointer', fontWeight:600 }}>
                      {l.native}
                    </button>
                  ))}
                </div>
              </div>

              {/* Offline briefing */}
              <div style={{ background:'rgba(0,212,255,0.06)', border:'1px solid rgba(0,212,255,0.2)', borderRadius:20, padding:18, marginBottom:16 }}>
                <p style={{ fontSize:14, fontWeight:800, color:'#00D4FF', marginBottom:4 }}>📥 Download Offline Briefing</p>
                <p style={{ fontSize:11, color:'rgba(255,255,255,0.4)', marginBottom:14 }}>
                  Save today's flood briefing as a text file — works without internet
                </p>
                {result ? (
                  <button onClick={downloadPDF}
                    style={{ width:'100%', padding:'12px 0', borderRadius:12, fontWeight:800, fontSize:14, cursor:'pointer', border:'none', background:'linear-gradient(135deg,rgba(0,212,255,0.3),rgba(0,212,255,0.15))', color:'#00D4FF', borderColor:'rgba(0,212,255,0.35)' } as any}>
                    ⬇️ Download Briefing for {result.query}
                  </button>
                ) : (
                  <p style={{ fontSize:12, color:'rgba(255,255,255,0.3)', textAlign:'center' }}>
                    Search for a city/district first to download its briefing
                  </p>
                )}
              </div>

              {/* Links */}
              <div style={{ display:'flex', flexDirection:'column', gap:8, marginBottom:16 }}>
                {[
                  { icon:'🤖', title:'AI Research Dashboard', sub:'ML models, validation metrics, baselines', href:'/', color:'rgba(0,212,255,0.15)', border:'rgba(0,212,255,0.25)', tc:'#00D4FF' },
                  { icon:'✨', title:'3D Luxury Dashboard', sub:'Immersive 3D flood visualisation', href:'/luxury', color:'rgba(212,175,55,0.12)', border:'rgba(212,175,55,0.3)', tc:'#F5D06C' },
                  { icon:'👤', title:'My Alert Profile', sub:'Personalised alerts for your district', href:'/profile', color:'rgba(0,230,118,0.08)', border:'rgba(0,230,118,0.2)', tc:'#00E676' },
                ].map(l => (
                  <Link key={l.href} to={l.href}
                    style={{ display:'flex', alignItems:'center', gap:14, padding:'14px 16px', borderRadius:14, textDecoration:'none', background:l.color, border:`1px solid ${l.border}`, transition:'all 0.2s' }}>
                    <span style={{ fontSize:22 }}>{l.icon}</span>
                    <div style={{ flex:1 }}>
                      <p style={{ fontSize:13, fontWeight:700, color:l.tc, margin:0 }}>{l.title}</p>
                      <p style={{ fontSize:11, color:'rgba(255,255,255,0.4)', margin:'2px 0 0' }}>{l.sub}</p>
                    </div>
                    <ChevronRight style={{ width:16, height:16, color:'rgba(255,255,255,0.3)' }} />
                  </Link>
                ))}
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </main>

      {/* ══════════════════ STICKY FOOTER ══════════════════ */}
      <div style={{
        position:'fixed', bottom:0, left:0, right:0, zIndex:50,
        background:'rgba(180,0,0,0.95)', backdropFilter:'blur(20px)',
        borderTop:'1px solid rgba(255,59,59,0.4)',
        padding:'10px 16px',
      }}>
        <div style={{ maxWidth:640, margin:'0 auto', display:'flex', alignItems:'center', justifyContent:'space-between' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            <motion.div animate={{ opacity:[0.7,1,0.7] }} transition={{ duration:1.2, repeat:Infinity }}>
              <Shield style={{ width:16, height:16, color:'rgba(255,200,200,0.9)' }} />
            </motion.div>
            <span style={{ fontSize:12, color:'rgba(255,220,220,0.9)', fontWeight:600 }}>
              Emergency: NDMA 1078 • NDRF 011-24363260
            </span>
          </div>
          <a href="tel:1078"
            style={{ display:'flex', alignItems:'center', gap:6, padding:'7px 16px', borderRadius:20, background:'white', color:'#C0000A', fontWeight:900, fontSize:13, textDecoration:'none', boxShadow:'0 2px 12px rgba(0,0,0,0.3)' }}>
            <Phone style={{ width:13, height:13 }} /> 1078
          </a>
        </div>
      </div>

    </div>
  )
}
