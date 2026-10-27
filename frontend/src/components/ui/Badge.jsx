import { cx } from '../../utils/format.js'

const TONES = {
  success: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/25',
  warning: 'bg-solar-400/10 text-solar-300 ring-solar-400/25',
  danger: 'bg-rose-400/10 text-rose-300 ring-rose-400/25',
  info: 'bg-sky-400/10 text-sky-300 ring-sky-400/25',
  brand: 'bg-brand-400/12 text-brand-300 ring-brand-400/30',
  neutral: 'bg-graphite-700/60 text-graphite-200 ring-white/10',
  solar: 'bg-solar-400/12 text-solar-300 ring-solar-400/30',
  wind: 'bg-wind-400/12 text-wind-300 ring-wind-400/30',
  violet: 'bg-violet-400/12 text-violet-300 ring-violet-400/30',
  dark: 'bg-graphite-950 text-graphite-100 ring-white/10',
}

const DOTS = {
  success: 'bg-emerald-400',
  warning: 'bg-solar-400',
  danger: 'bg-rose-400',
  info: 'bg-sky-400',
  brand: 'bg-brand-400',
  neutral: 'bg-graphite-300',
  solar: 'bg-solar-400',
  wind: 'bg-wind-400',
  violet: 'bg-violet-400',
  dark: 'bg-graphite-200',
}

const SIZES = {
  sm: 'px-2 py-0.5 text-[10px] gap-1',
  md: 'px-2.5 py-1 text-[11px] gap-1.5',
}

export default function Badge({
  tone = 'neutral',
  size = 'md',
  dot = false,
  pulse = false,
  icon,
  mono = false,
  className = '',
  children,
}) {
  const dotColor = DOTS[tone] || DOTS.neutral
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full font-semibold uppercase tracking-wide ring-1 ring-inset whitespace-nowrap',
        TONES[tone] || TONES.neutral,
        SIZES[size],
        mono && 'font-mono tracking-normal',
        className,
      )}
    >
      {dot ? (
        <span className={cx('relative flex h-1.5 w-1.5 shrink-0', pulse && 'animate-pulse-soft')}>
          <span className={cx('h-1.5 w-1.5 rounded-full', dotColor)} />
        </span>
      ) : null}
      {icon ? <span className="shrink-0">{icon}</span> : null}
      {children}
    </span>
  )
}
