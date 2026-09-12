'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

interface MetricCardProps {
  title:       string
  value:       string | number
  subtitle?:   string
  trend?:      'up' | 'down' | 'stable'
  trendValue?: string
  icon?:       string
  color?:      'gold' | 'cyan' | 'red' | 'green' | 'orange'
  backContent?: React.ReactNode
  delay?:      number
  size?:       'sm' | 'md' | 'lg'
  animate?:    boolean
}

const COLOR_MAP = {
  gold:   { border: 'rgba(212,175,55,0.35)',  glow: 'rgba(212,175,55,0.15)',  text: '#F5D06C', bg: 'rgba(212,175,55,0.06)' },
  cyan:   { border: 'rgba(0,212,255,0.30)',   glow: 'rgba(0,212,255,0.12)',   text: '#00D4FF', bg: 'rgba(0,212,255,0.05)'  },
  red:    { border: 'rgba(255,59,59,0.35)',   glow: 'rgba(255,59,59,0.15)',   text: '#FF6B6B', bg: 'rgba(255,59,59,0.06)'  },
  green:  { border: 'rgba(0,230,118,0.30)',   glow: 'rgba(0,230,118,0.12)',   text: '#00E676', bg: 'rgba(0,230,118,0.05)'  },
  orange: { border: 'rgba(255,140,0,0.30)',   glow: 'rgba(255,140,0,0.12)',   text: '#FF8C00', bg: 'rgba(255,140,0,0.05)'  },
}

// Animated number counter
function AnimatedNumber({ target }: { target: number }) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    let start = 0
    const duration = 1200
    const step = target / (duration / 16)
    const timer = setInterval(() => {
      start += step
      if (start >= target) { setDisplay(target); clearInterval(timer) }
      else setDisplay(Math.floor(start))
    }, 16)
    return () => clearInterval(timer)
  }, [target])
  return <>{display.toLocaleString()}</>
}

export default function LuxuryMetricCard({
  title, value, subtitle, trend, trendValue,
  icon = '🌊', color = 'cyan', backContent,
  delay = 0, size = 'md', animate = true,
}: MetricCardProps) {
  const [flipped, setFlipped] = useState(false)
  const [hovered, setHovered] = useState(false)
  const c = COLOR_MAP[color]
  const isNum = typeof value === 'number'

  const sizeClass = { sm: 'h-32', md: 'h-40', lg: 'h-52' }[size]

  return (
    <motion.div
      initial={animate ? { opacity: 0, y: 30, scale: 0.95 } : {}}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.6, delay, ease: [0.23, 1, 0.32, 1] }}
      className={`relative ${sizeClass} cursor-pointer`}
      style={{ perspective: '1000px' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => backContent && setFlipped(f => !f)}
    >
      {/* Animated glow ring */}
      <motion.div
        animate={{ opacity: hovered ? 1 : 0 }}
        transition={{ duration: 0.3 }}
        className="absolute inset-0 rounded-2xl pointer-events-none"
        style={{
          boxShadow: `0 0 40px ${c.glow}, 0 0 80px ${c.glow}`,
          borderRadius: 16,
        }}
      />

      {/* Card flip container */}
      <motion.div
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={{ duration: 0.7, ease: [0.23, 1, 0.32, 1] }}
        style={{ transformStyle: 'preserve-3d', width: '100%', height: '100%', position: 'relative' }}
      >
        {/* Front face */}
        <div
          className="absolute inset-0 rounded-2xl p-4 flex flex-col justify-between overflow-hidden"
          style={{
            backfaceVisibility: 'hidden',
            background: `linear-gradient(135deg, ${c.bg}, rgba(5,10,28,0.8))`,
            border: `1px solid ${c.border}`,
            boxShadow: `0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)`,
          }}
        >
          {/* Shimmer overlay on hover */}
          <motion.div
            animate={{ x: hovered ? '200%' : '-100%' }}
            transition={{ duration: 0.8 }}
            className="absolute inset-0 pointer-events-none"
            style={{
              background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.06) 50%, transparent 60%)',
            }}
          />

          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest"
                 style={{ color: 'rgba(255,255,255,0.4)', letterSpacing: '1.5px' }}>
                {title}
              </p>
            </div>
            <motion.div
              animate={{ rotate: hovered ? 10 : 0, scale: hovered ? 1.15 : 1 }}
              transition={{ duration: 0.3 }}
              className="text-2xl"
            >
              {icon}
            </motion.div>
          </div>

          {/* Value */}
          <div>
            <motion.div
              animate={{ scale: hovered ? 1.03 : 1 }}
              className="font-black tracking-tight leading-none"
              style={{
                fontSize: size === 'lg' ? '3rem' : size === 'md' ? '2.2rem' : '1.6rem',
                color: c.text,
                textShadow: `0 0 30px ${c.glow}`,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {isNum ? <AnimatedNumber target={value as number} /> : value}
            </motion.div>

            {/* Trend indicator */}
            {trend && (
              <div className="flex items-center gap-2 mt-2">
                <motion.span
                  animate={{ y: trend === 'up' ? [-1, 1] : trend === 'down' ? [1, -1] : [0] }}
                  transition={{ duration: 1.5, repeat: Infinity, repeatType: 'reverse' }}
                  style={{
                    color: trend === 'up' ? '#FF6B6B' : trend === 'down' ? '#00E676' : '#94a3b8',
                    fontSize: 13,
                    fontWeight: 700,
                  }}
                >
                  {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
                  {' '}{trendValue}
                </motion.span>
              </div>
            )}

            {subtitle && (
              <p className="text-xs mt-1.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
                {subtitle}
              </p>
            )}
          </div>

          {/* Bottom accent line */}
          <motion.div
            animate={{ scaleX: hovered ? 1 : 0.3, opacity: hovered ? 1 : 0.3 }}
            transition={{ duration: 0.4 }}
            className="h-0.5 rounded-full origin-left"
            style={{ background: `linear-gradient(90deg, ${c.text}, transparent)` }}
          />

          {/* Flip hint */}
          {backContent && (
            <div className="absolute top-3 right-3 opacity-30 text-xs" style={{ color: c.text }}>
              ⟳
            </div>
          )}
        </div>

        {/* Back face */}
        {backContent && (
          <div
            className="absolute inset-0 rounded-2xl p-4 overflow-hidden"
            style={{
              backfaceVisibility: 'hidden',
              transform: 'rotateY(180deg)',
              background: `linear-gradient(135deg, rgba(5,10,28,0.95), ${c.bg})`,
              border: `1px solid ${c.border}`,
            }}
          >
            <p className="text-xs font-semibold uppercase tracking-widest mb-3"
               style={{ color: c.text, letterSpacing: '1.5px' }}>
              {title} — Details
            </p>
            {backContent}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
