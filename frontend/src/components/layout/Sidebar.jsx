import { NavLink } from 'react-router-dom'
import { Github, PanelLeftClose, ShieldCheck, X } from 'lucide-react'
import { cx } from '../../utils/format.js'
import { NAV_ITEMS } from '../../utils/constants.js'
import { API_MODE } from '../../services/api.js'
import Icon from '../ui/Icon.jsx'
import Badge from '../ui/Badge.jsx'
import Logo from './Logo.jsx'

function NavItem({ item, onNavigate }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cx(
          'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-semibold transition-all duration-200 ease-smooth',
          isActive
            ? 'bg-brand-400/10 text-white ring-1 ring-inset ring-brand-400/20'
            : 'text-graphite-400 hover:bg-white/[0.04] hover:text-graphite-100',
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={cx(
              'absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-brand-400 transition-all duration-300',
              isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-40',
            )}
          />
          <Icon
            name={item.icon}
            className={cx('h-[17px] w-[17px] shrink-0 transition-colors', isActive ? 'text-brand-300' : 'text-graphite-500 group-hover:text-graphite-200')}
          />
          <span className="truncate">{item.label}</span>
          {isActive ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-300 shadow-glow-brand" /> : null}
        </>
      )}
    </NavLink>
  )
}

export default function Sidebar({ open, onClose }) {
  return (
    <>
      <div
        onClick={onClose}
        className={cx(
          'fixed inset-0 z-40 bg-graphite-950/70 backdrop-blur-sm transition-opacity duration-300 lg:hidden',
          open ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        aria-hidden
      />

      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-50 flex w-[248px] flex-col border-r border-graphite-800 bg-graphite-950/95 backdrop-blur-xl transition-transform duration-300 ease-smooth lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="pointer-events-none absolute inset-0 ev-grid opacity-40" aria-hidden />
        <div className="pointer-events-none absolute -left-16 top-0 h-48 w-48 rounded-full bg-brand-500/10 blur-3xl" aria-hidden />

        <div className="relative flex items-center justify-between px-4 py-4">
          <Logo />
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-graphite-400 transition-colors hover:bg-white/5 hover:text-white lg:hidden"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
          <span className="hidden text-graphite-600 lg:block">
            <PanelLeftClose className="h-4 w-4" />
          </span>
        </div>

        {/* Grid status block */}
        <div className="relative mx-3 mb-3 rounded-lg border border-graphite-800 bg-graphite-900/60 p-3">
          <div className="flex items-center justify-between">
            <span className="eyebrow">Karnataka Grid</span>
            <Badge tone={API_MODE === 'live' ? 'success' : 'brand'} size="sm" dot pulse>
              {API_MODE === 'live' ? 'Live' : 'Demo'}
            </Badge>
          </div>
          <p className="mt-2 flex items-center gap-2 font-mono text-[11px] font-semibold text-graphite-200">
            <ShieldCheck className="h-3.5 w-3.5 text-brand-300" />
            Telemetry nominal
          </p>
          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <div className="h-full w-[78%] rounded-full bg-gradient-to-r from-brand-400 to-wind-400" />
          </div>
        </div>

        <nav className="relative flex-1 overflow-y-auto px-3 pb-4 ev-scroll">
          <p className="eyebrow px-3 pb-2 pt-1">Control</p>
          <div className="space-y-1">
            {NAV_ITEMS.map((item) => (
              <NavItem key={item.to} item={item} onNavigate={onClose} />
            ))}
          </div>
        </nav>

        <div className="relative border-t border-graphite-800 p-3">
          <div className="flex items-center justify-between text-[10px] text-graphite-500">
            <span className="font-mono uppercase tracking-wide">Frontend v2.0</span>
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 transition-colors hover:text-graphite-200"
            >
              <Github className="h-3 w-3" /> repo
            </a>
          </div>
          <p className="mt-1.5 text-[10px] leading-relaxed text-graphite-600">
            AI renewable-energy forecasting & decision support.
          </p>
        </div>
      </aside>
    </>
  )
}
