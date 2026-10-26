import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, CircleDot, Menu, Search, Settings } from 'lucide-react'
import { cx } from '../../utils/format.js'
import { API_MODE } from '../../services/api.js'
import Badge from '../ui/Badge.jsx'
import Logo from './Logo.jsx'

function useClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30000)
    return () => clearInterval(id)
  }, [])
  return now
}

export default function Header({ onOpenSidebar }) {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  const now = useClock()

  const submit = (e) => {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/plants?q=${encodeURIComponent(q)}` : '/plants')
  }

  const time = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })

  return (
    <header className="sticky top-0 z-30 border-b border-graphite-800 bg-graphite-950/85 backdrop-blur-xl">
      <div className="flex h-14 items-center gap-3 px-3 sm:px-5">
        <button
          type="button"
          onClick={onOpenSidebar}
          className="rounded-lg p-2 text-graphite-300 transition-colors hover:bg-white/5 hover:text-white lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="lg:hidden">
          <Logo compact />
        </div>

        <div className="hidden items-center gap-2.5 lg:flex">
          <span className="relative flex h-2 w-2 items-center justify-center">
            <span className="absolute h-2 w-2 rounded-full bg-brand-400/60" />
            <span className="absolute h-2 w-2 animate-ping-ring rounded-full bg-brand-400/70" />
            <CircleDot className="h-2.5 w-2.5 text-brand-300" />
          </span>
          <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-graphite-400">
            Karnataka Energy Mission Control
          </span>
        </div>

        <form onSubmit={submit} className="relative ml-auto hidden w-full max-w-xs md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-graphite-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search plants, districts…"
            className="ev-input h-9 py-0 pl-9 pr-3 text-[13px]"
          />
        </form>

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <div className="hidden items-center gap-2 rounded-lg border border-graphite-800 bg-graphite-900/60 px-3 py-1.5 sm:flex">
            <span className="eyebrow">IST</span>
            <span className="font-mono text-xs font-semibold tabular-nums text-graphite-100">{time}</span>
          </div>

          <Badge tone={API_MODE === 'live' ? 'success' : 'brand'} size="sm" dot pulse className="hidden sm:inline-flex">
            {API_MODE === 'live' ? 'Live feed' : 'Demo data'}
          </Badge>

          <button
            type="button"
            className="relative rounded-lg p-2 text-graphite-300 transition-colors hover:bg-white/5 hover:text-white"
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" />
            <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-solar-400" />
          </button>
          <button
            type="button"
            className="rounded-lg p-2 text-graphite-300 transition-colors hover:bg-white/5 hover:text-white"
            aria-label="Settings"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  )
}
