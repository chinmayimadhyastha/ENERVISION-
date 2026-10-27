import { cx } from '../../utils/format.js'
import { Icon as IconCmp } from './Icon.jsx'
import { useCountUp } from '../../hooks/useCountUp.js'
import MiniSparkline from '../charts/MiniSparkline.jsx'
import { PALETTE } from '../../utils/constants.js'

const TONES = {
  brand: { icon: 'bg-brand-400/10 text-brand-300 ring-brand-400/20', line: 'from-brand-400 to-brand-500/0', glow: 'bg-brand-400/10' },
  solar: { icon: 'bg-solar-400/10 text-solar-300 ring-solar-400/20', line: 'from-solar-400 to-solar-500/0', glow: 'bg-solar-400/10' },
  wind: { icon: 'bg-wind-400/10 text-wind-300 ring-wind-400/20', line: 'from-wind-400 to-wind-500/0', glow: 'bg-wind-400/10' },
  violet: { icon: 'bg-violet-400/10 text-violet-300 ring-violet-400/20', line: 'from-violet-400 to-violet-500/0', glow: 'bg-violet-400/10' },
  emerald: { icon: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/20', line: 'from-emerald-400 to-emerald-500/0', glow: 'bg-emerald-400/10' },
  rose: { icon: 'bg-rose-400/10 text-rose-300 ring-rose-400/20', line: 'from-rose-400 to-rose-500/0', glow: 'bg-rose-400/10' },
  neutral: { icon: 'bg-white/5 text-graphite-300 ring-white/10', line: 'from-graphite-400 to-graphite-600/0', glow: 'bg-white/5' },
}

const SPARK_COLORS = {
  brand: PALETTE.brand,
  solar: PALETTE.solar,
  wind: PALETTE.wind,
  violet: PALETTE.violet,
  emerald: PALETTE.success,
  rose: PALETTE.danger,
  neutral: PALETTE.tick,
}

/** Compact KPI tile with optional count-up, sparkline, delta and progress. */
export default function StatCard({
  label,
  value,
  unit,
  icon,
  tone = 'brand',
  delta,
  deltaLabel = 'vs forecast',
  deltaSuffix = '%',
  hint,
  progress,
  progressTone,
  spark,
  decimals = 0,
  animate = true,
  badge,
  className = '',
  children,
}) {
  const t = TONES[tone] || TONES.brand
  const numeric = typeof value === 'number' && Number.isFinite(value)
  const animated = useCountUp(numeric ? value : 0, { decimals, enabled: animate && numeric })
  const shown = numeric ? (animate ? animated : value) : value

  const pct = typeof progress === 'number' ? Math.max(0, Math.min(100, progress)) : null
  const dNum = typeof delta === 'number' ? delta : null
  const dTone = dNum == null ? 'neutral' : dNum > 0 ? 'positive' : dNum < 0 ? 'negative' : 'neutral'

  return (
    <div className={cx('panel relative overflow-hidden p-4', className)}>
      <div className={cx('pointer-events-none absolute -right-10 -top-12 h-32 w-32 rounded-full blur-3xl', t.glow)} aria-hidden />

      <div className="relative flex items-start justify-between gap-3">
        <p className="eyebrow">{label}</p>
        <div className="flex items-center gap-2">
          {badge}
          {icon ? (
            <span className={cx('flex h-8 w-8 items-center justify-center rounded-lg ring-1 ring-inset', t.icon)}>
              {icon}
            </span>
          ) : null}
        </div>
      </div>

      <div className="relative mt-3 flex items-end gap-1.5">
        <span className="metric-value text-[26px] leading-none">
          {typeof shown === 'number'
            ? shown.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
            : shown}
        </span>
        {unit ? <span className="pb-0.5 text-xs font-semibold text-graphite-400">{unit}</span> : null}
      </div>

      {spark && spark.length ? (
        <div className="relative mt-3">
          <MiniSparkline
            data={spark.map((v) => ({ value: typeof v === 'number' ? v : v.value }))}
            color={SPARK_COLORS[tone] || PALETTE.brand}
            height={30}
          />
        </div>
      ) : null}

      {pct != null ? (
        <div className="relative mt-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
            <div
              className={cx(
                'h-full rounded-full bg-gradient-to-r transition-[width] duration-700 ease-smooth',
                progressTone
                  ? progressTone
                  : tone === 'solar'
                    ? 'from-solar-400 to-solar-500'
                    : tone === 'wind'
                      ? 'from-wind-400 to-wind-500'
                      : 'from-brand-400 to-brand-500',
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      ) : null}

      {(delta != null || hint) ? (
        <div className="relative mt-3 flex items-center justify-between gap-2 text-[11px]">
          {delta != null ? (
            <span
              className={cx(
                'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono font-semibold',
                dTone === 'positive' && 'bg-emerald-400/10 text-emerald-300',
                dTone === 'negative' && 'bg-rose-400/10 text-rose-300',
                dTone === 'neutral' && 'bg-white/5 text-graphite-300',
              )}
            >
              {dNum != null ? `${dNum > 0 ? '▲' : dNum < 0 ? '▼' : '■'} ${Math.abs(dNum)}${deltaSuffix}` : delta}
              <span className="font-sans font-medium text-graphite-400">{deltaLabel}</span>
            </span>
          ) : null}
          {hint ? <span className="truncate text-graphite-400">{hint}</span> : null}
        </div>
      ) : null}

      {children}
    </div>
  )
}
