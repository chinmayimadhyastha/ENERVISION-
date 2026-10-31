import { NavLink } from 'react-router-dom'
import {
  BarChart3,
  BrainCircuit,
  Factory,
  Info,
  LayoutDashboard,
  LineChart,
  ShieldCheck,
  X,
} from 'lucide-react'
import { cx } from '../../utils/format.js'
import { API_MODE } from '../../services/api.js'
import { useLanguage } from '../../context/LanguageContext.jsx'
import Logo from './Logo.jsx'

export default function Sidebar({ open, onClose }) {
  const { t } = useLanguage()

  const navItems = [
    { to: '/', label: t('navOverview'), icon: LayoutDashboard, end: true },
    { to: '/forecast', label: t('navForecast'), icon: LineChart },
    { to: '/plants', label: t('navPlants'), icon: Factory },
    { to: '/analytics', label: t('navAnalytics'), icon: BarChart3 },
    { to: '/model-performance', label: t('navModels'), icon: BrainCircuit },
    { to: '/about', label: t('navAbout'), icon: Info },
  ]

  return (
    <>
      <div
        onClick={onClose}
        className={cx(
          'fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm transition-opacity duration-300 lg:hidden',
          open ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        aria-hidden
      />

      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-50 flex w-[248px] flex-col border-r border-slate-200 bg-white transition-transform duration-300 ease-in-out lg:translate-x-0 shadow-sm',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="relative flex items-center justify-between border-b border-slate-100 px-4 py-4">
          <Logo />
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 lg:hidden"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Telemetry card */}
        <div className="mx-3 mt-3 rounded-lg border border-emerald-100 bg-emerald-50/60 p-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-900">
              State Grid Status
            </span>
            <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
              {API_MODE === 'live' ? 'Live' : 'Cached'}
            </span>
          </div>
          <p className="mt-1.5 flex items-center gap-1.5 font-mono text-[11px] font-medium text-emerald-800">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
            37 Assets Online
          </p>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-emerald-200/60">
            <div className="h-full w-[88%] rounded-full bg-emerald-600" />
          </div>
        </div>

        {/* Navigation menu */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Decision Support
          </p>
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) =>
                  cx(
                    'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-xs font-semibold transition-all duration-150',
                    isActive
                      ? 'bg-emerald-50 text-emerald-900 shadow-sm border border-emerald-200/60'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cx(
                        'h-4 w-4 shrink-0 transition-colors',
                        isActive ? 'text-emerald-700' : 'text-slate-400 group-hover:text-slate-600',
                      )}
                    />
                    <span className="truncate">{item.label}</span>
                    {isActive ? (
                      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-600" />
                    ) : null}
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* Footer info in sidebar */}
        <div className="border-t border-slate-100 p-3">
          <div className="rounded-lg bg-slate-50 p-2.5 text-[11px] text-slate-500">
            <p className="font-semibold text-slate-700">Department of Energy</p>
            <p className="mt-0.5 text-[10.5px]">Government of Karnataka</p>
            <p className="mt-1 font-mono text-[9.5px] text-slate-400">ENERVISION Platform v2.0</p>
          </div>
        </div>
      </aside>
    </>
  )
}
