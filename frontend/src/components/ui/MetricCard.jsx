import { cx } from '../../utils/format.js'
import { useCountUp } from '../../hooks/useCountUp.js'

const TONES = {
  brand: 'bg-brand-400/10 text-brand-300',
  solar: 'bg-solar-400/10 text-solar-300',
  wind: 'bg-wind-400/10 text-wind-300',
  violet: 'bg-violet-400/10 text-violet-300',
  rose: 'bg-rose-400/10 text-rose-300',
  emerald: 'bg-emerald-400/10 text-emerald-300',
  slate: 'bg-white/5 text-graphite-300',
  neutral: 'bg-white/5 text-graphite-300',
}

/** Labelled metric row, used inside detail panels and cards. */
export default function MetricCard({ label, value, unit, icon, tone = 'slate', hint, decimals = 0, className = '' }) {
  const numeric = typeof value === 'number' && Number.isFinite(value)
  const animated = useCountUp(numeric ? value : 0, { decimals })
  const shown = numeric
    ? Number(animated).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
    : value

  return (
    <div
      className={cx(
        'flex items-center gap-3 rounded-lg border border-graphite-700/70 bg-graphite-850/60 px-3.5 py-3',
        className,
      )}
    >
      {icon ? (
        <span className={cx('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', TONES[tone] || TONES.slate)}>
          {icon}
        </span>
      ) : null}
      <div className="min-w-0">
        <p className="eyebrow">{label}</p>
        <p className="mt-0.5 truncate font-display text-[15px] font-bold tabular-nums text-white">
          {shown}
          {unit ? <span className="ml-1 text-xs font-semibold text-graphite-400">{unit}</span> : null}
        </p>
        {hint ? <p className="text-[11px] text-graphite-400">{hint}</p> : null}
      </div>
    </div>
  )
}
