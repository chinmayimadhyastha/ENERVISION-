import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CircleDot, Globe2, Menu, Search } from 'lucide-react'
import { API_MODE } from '../../services/api.js'
import { useLanguage } from '../../context/LanguageContext.jsx'
import GovEmblem from './GovEmblem.jsx'
import Logo from './Logo.jsx'

function useClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15000)
    return () => clearInterval(id)
  }, [])
  return now
}

export default function Header({ onOpenSidebar }) {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const now = useClock()
  const { language, setLanguage, t } = useLanguage()

  const submit = (e) => {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/plants?q=${encodeURIComponent(q)}` : '/plants')
  }

  const time = now.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  })

  const dateStr = now.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Kolkata',
  })

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur-md shadow-sm">
      {/* Subtle Karnataka tricolor accent ribbon */}
      <div className="h-[3.5px] w-full bg-gradient-to-r from-red-600 via-amber-500 to-emerald-600" aria-hidden="true" />

      <div className="flex h-16 items-center gap-3 px-3 sm:px-5">
        <button
          type="button"
          onClick={onOpenSidebar}
          className="rounded-lg p-2 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Official Karnataka Government and KREDL identity */}
        <div className="flex items-center gap-3">
          <GovEmblem className="h-10 w-10 shrink-0" />
          <div className="hidden sm:block">
            <h1 className="text-xs font-bold leading-tight text-slate-900 tracking-tight">
              {t('govIdentity')}
            </h1>
            <p className="text-[11px] font-medium leading-tight text-emerald-800">
              {t('govKredl')}
            </p>
          </div>
        </div>

        <div className="hidden h-8 w-px bg-slate-200 mx-1 lg:block" aria-hidden="true" />

        <div className="hidden items-center gap-2 lg:flex">
          <span className="relative flex h-2 w-2 items-center justify-center">
            <span className="absolute h-2 w-2 rounded-full bg-emerald-500/40" />
            <span className="absolute h-2 w-2 animate-ping rounded-full bg-emerald-500/60" />
            <CircleDot className="h-2.5 w-2.5 text-emerald-700" />
          </span>
          <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-600">
            {t('portalTitle')}
          </span>
        </div>

        {/* Global Plant & District Search */}
        <form onSubmit={submit} className="relative ml-auto hidden w-full max-w-xs md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('searchPlaceholder')}
            className="w-full rounded-lg border border-slate-300 bg-slate-50/80 px-3 py-1.5 pl-9 text-xs text-slate-800 placeholder:text-slate-400 focus:border-emerald-600 focus:bg-white focus:outline-none focus:ring-1 focus:ring-emerald-600 transition"
          />
        </form>

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          {/* Bilingual English / Kannada switch */}
          <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setLanguage('en')}
              className={`rounded-md px-2 py-1 font-semibold transition ${
                language === 'en'
                  ? 'bg-white text-emerald-800 shadow-sm border border-slate-200/80'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
              title="Switch to English"
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => setLanguage('kn')}
              className={`rounded-md px-2 py-1 font-semibold transition ${
                language === 'kn'
                  ? 'bg-white text-emerald-800 shadow-sm border border-slate-200/80'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
              title="ಕನ್ನಡಕ್ಕೆ ಬದಲಾಯಿಸಿ"
            >
              ಕನ್ನಡ
            </button>
          </div>

          {/* Real Backend Status Badge */}
          <div className="hidden sm:flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-800">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-600" />
            </span>
            <span>{API_MODE === 'live' ? t('liveFeed') : t('offlineFeed')}</span>
          </div>

          {/* Live IST Clock */}
          <div className="hidden lg:flex flex-col text-right rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1">
            <span className="font-mono text-xs font-semibold tabular-nums text-slate-800">{time} IST</span>
            <span className="text-[10px] text-slate-500 font-medium">{dateStr}</span>
          </div>
        </div>
      </div>
    </header>
  )
}
