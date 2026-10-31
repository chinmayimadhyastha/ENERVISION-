import { useNavigate } from 'react-router-dom'
import { ArrowRight, BarChart2, Cpu, Factory, LineChart, ShieldCheck, Sun, Wind } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext.jsx'

export default function PortalHero() {
  const navigate = useNavigate()
  const { t } = useLanguage()

  return (
    <div className="portal-hero relative overflow-hidden rounded-2xl border border-emerald-200/80 bg-gradient-to-br from-emerald-900 via-teal-900 to-slate-900 p-6 sm:p-8 md:p-10 text-white shadow-md">
      {/* Subtle Karnataka red & yellow accent hairline on top edge */}
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-red-600 via-amber-400 to-emerald-500" />

      {/* Background ambient lighting */}
      <div className="pointer-events-none absolute -right-16 -top-16 h-80 w-80 rounded-full bg-emerald-500/20 blur-3xl" />
      <div className="pointer-events-none absolute right-1/3 -bottom-20 h-64 w-64 rounded-full bg-amber-500/15 blur-3xl" />

      <div className="relative z-10 max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-950/60 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-emerald-300 backdrop-blur-sm">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
          <span>{t('heroTag')}</span>
        </div>

        <h2 className="mt-4 font-display text-2xl sm:text-3xl md:text-4xl font-bold tracking-tight text-white leading-tight">
          {t('heroTitle')}
        </h2>

        <p className="mt-3 text-sm sm:text-base leading-relaxed text-slate-200 max-w-2xl font-normal">
          {t('heroSubtitle')}
        </p>

        {/* Feature badges */}
        <div className="mt-6 flex flex-wrap items-center gap-3 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/10 px-2.5 py-1 text-slate-200">
            <Sun className="h-3.5 w-3.5 text-amber-400" />
            30 Solar Plants (incl. Pavagada)
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/10 px-2.5 py-1 text-slate-200">
            <Wind className="h-3.5 w-3.5 text-sky-400" />
            7 Wind Complexes (Gadag, Koppal)
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/10 px-2.5 py-1 text-slate-200">
            <Cpu className="h-3.5 w-3.5 text-emerald-400" />
            LSTM & Random Forest ML
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/10 px-2.5 py-1 text-slate-200">
            <BarChart2 className="h-3.5 w-3.5 text-purple-400" />
            Target: MU/day
          </span>
        </div>

        {/* Action Buttons */}
        <div className="mt-7 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/forecast')}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-950 shadow-sm transition hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            <LineChart className="h-4 w-4" />
            {t('exploreForecastsBtn')}
            <ArrowRight className="h-3.5 w-3.5" />
          </button>

          <button
            type="button"
            onClick={() => navigate('/plants')}
            className="inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-4 py-2.5 text-xs sm:text-sm font-semibold text-white backdrop-blur-sm transition hover:bg-white/20 focus:outline-none"
          >
            <Factory className="h-4 w-4" />
            Karnataka Plant Explorer
          </button>
        </div>
      </div>
    </div>
  )
}
