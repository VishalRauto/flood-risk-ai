'use client'

/**
 * LanguageSwitcher.tsx
 * Dropdown to switch between all 9 supported Indian languages.
 * Works standalone — can be dropped into any page.
 */

import { useState, useRef, useEffect } from 'react'
import { useTranslation, SUPPORTED_LANGUAGES } from '@/hooks/useTranslation'
import { Globe } from 'lucide-react'

interface Props {
  className?: string
  compact?: boolean   // show only globe icon on small screens
}

export default function LanguageSwitcher({ className = '', compact = false }: Props) {
  const { lang, setLang } = useTranslation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const current = SUPPORTED_LANGUAGES.find(l => l.code === lang) || SUPPORTED_LANGUAGES[0]

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg
                   bg-gray-800/60 hover:bg-gray-700/80 border border-gray-600/50
                   text-gray-200 text-sm transition-colors"
        title="Change language"
      >
        <Globe className="h-4 w-4 text-blue-400 flex-shrink-0" />
        {!compact && (
          <span className="max-w-[80px] truncate hidden sm:inline">
            {current.native}
          </span>
        )}
        <svg className="h-3 w-3 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-48 rounded-xl shadow-2xl
                        bg-gray-900 border border-gray-700/50 z-50 overflow-hidden">
          <div className="p-1">
            {SUPPORTED_LANGUAGES.map(l => (
              <button
                key={l.code}
                onClick={() => { setLang(l.code); setOpen(false) }}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg
                           text-sm transition-colors
                           ${lang === l.code
                             ? 'bg-blue-600/20 text-blue-300'
                             : 'text-gray-300 hover:bg-gray-800 hover:text-white'}`}
              >
                <span>{l.native}</span>
                <span className="text-xs text-gray-500">{l.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
