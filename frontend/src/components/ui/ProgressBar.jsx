import { cx } from '../../utils/format.js'

const BAR_TONES = {
  brand: 'from-brand-400 to-brand-500',
  solar: 'from-solar-400 to-solar-500',
  wind: 'from-wind-400 to-wind-500',
  danger: 'from-rose-400 to-rose-500',
  warning: 'from-solar-400 to-solar-600',
  violet: 'from-violet-400 to-violet-500',
  emerald: 'from-emerald-400 to-emerald-500',
}

export default function ProgressBar({
  value = 0,
  max = 100,
  tone = 'brand',
  size = 'md',
  showLabel = false,
  label,
  className = '',
}) {
  const pct = Math.max(0, Math.min(100, (Number(value) / (max || 100)) * 100))
  const heights = { sm: 'h-1', md: 'h-1.5', lg: 'h-2' }
  return (
    <div className={className}>
      {showLabel || label ? (
        <div className="mb-1 flex items-center justify-between text-[11px] font-medium text-graphite-400">
          <span>{label}</span>
          {showLabel ? <span className="font-mono tabular-nums">{pct.toFixed(1)}%</span> : null}
        </div>
      ) : null}
      <div className={cx('w-full overflow-hidden rounded-full bg-white/5', heights[size] || heights.md)}>
        <div
          className={cx('h-full rounded-full bg-gradient-to-r transition-[width] duration-700 ease-smooth', BAR_TONES[tone] || BAR_TONES.brand)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
