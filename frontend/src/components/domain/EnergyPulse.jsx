import { Activity, CalendarDays, Sun, Wind, Zap } from 'lucide-react'
import { cx } from '../../utils/format.js'
import { formatDate, formatMU, formatNumber, formatPercent } from '../../utils/format.js'
import { PALETTE } from '../../utils/constants.js'
import { useCountUp } from '../../hooks/useCountUp.js'
import MiniSparkline from '../charts/MiniSparkline.jsx'

/**
 * Latest observed daily-generation strip: fleet MU/day, solar/wind split,
 * reporting coverage and a trailing daily generation trace. Daily only — the
 * API does not publish instantaneous MW.
 */
export default function EnergyPulse({
  totalMU = 0,
  solarMU = 0,
  windMU = 0,
  plantCount = 0,
  reportingPlants = 0,
  date,
  spark = [],
  className = '',
}) {
  const total = useCountUp(totalMU, { duration: 1200, decimals: 2 })
  const solar = useCountUp(solarMU, { duration: 1200, decimals: 2 })
  const wind = useCountUp(windMU, { duration: 1200, decimals: 2 })
  const denom = (solarMU || 0) + (windMU || 0) || 1
  const solarShare = ((solarMU || 0) / denom) * 100
  const coverage = plantCount ? Math.min(100, ((reportingPlants || 0) / plantCount) * 100) : null

  return (
    <div className={cx('panel relative overflow-hidden p-4 sm:p-5', className)}>
      <div className="pointer-events-none absolute inset-0 ev-grid-sm opacity-40" aria-hidden />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-400/60 to-transparent"
        aria-hidden
      />

      <div className="relative flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-1.5 eyebrow">
            <Activity className="h-3 w-3 text-brand-300" /> Karnataka daily generation pulse
          </p>
          <div className="mt-1 flex flex-wrap items-end gap-2">
            <span className="metric-value text-3xl leading-none text-white">{formatMU(total, 2)}</span>
            <span className="pb-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-graphite-400">
              latest observed day
            </span>
          </div>
          <p className="mt-1 flex items-center gap-1.5 font-mono text-[10px] text-graphite-400">
            <CalendarDays className="h-3 w-3" />
            {date ? formatDate(date) : 'Date unavailable'}
            {coverage !== null ? ` · ${reportingPlants}/${plantCount} plants reporting (${formatPercent(coverage, 0)})` : ''}
          </p>
        </div>

        <div className="flex w-full max-w-[240px] flex-col gap-2 sm:w-auto">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-solar-400/20 bg-solar-400/[0.06] px-2.5 py-1.5">
              <p className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wide text-solar-300">
                <Sun className="h-3 w-3" /> Solar
              </p>
              <p className="mt-0.5 font-mono text-[11px] font-bold tabular-nums text-graphite-100">
                {formatMU(solar, 2)}
              </p>
            </div>
            <div className="rounded-lg border border-wind-400/20 bg-wind-400/[0.06] px-2.5 py-1.5">
              <p className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wide text-wind-300">
                <Wind className="h-3 w-3" /> Wind
              </p>
              <p className="mt-0.5 font-mono text-[11px] font-bold tabular-nums text-graphite-100">
                {formatMU(wind, 2)}
              </p>
            </div>
          </div>
          <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-white/5">
            <span style={{ width: `${solarShare}%`, background: PALETTE.solar }} />
            <span style={{ width: `${100 - solarShare}%`, background: PALETTE.wind }} />
          </div>
          <div className="flex items-center justify-between font-mono text-[9px] text-graphite-500">
            <span>Solar {formatPercent(solarShare, 0)}</span>
            <span>Wind {formatPercent(100 - solarShare, 0)}</span>
          </div>
        </div>
      </div>

      <div className="relative mt-3 flex items-end gap-3">
        <div className="min-w-0 flex-1">
          {spark.length ? (
            <MiniSparkline data={spark} dataKey="total" color={PALETTE.brand} height={34} />
          ) : (
            <p className="font-mono text-[10px] text-graphite-500">No trailing daily series available.</p>
          )}
        </div>
        <span className="flex items-center gap-1 pb-1 font-mono text-[9px] font-semibold uppercase tracking-wide text-graphite-500">
          <Zap className="h-3 w-3 text-brand-300" /> trailing 30 days
        </span>
      </div>
    </div>
  )
}
