import { useId } from 'react'
import { cx } from '../../utils/format.js'

/**
 * ENERVISION identity mark — a hexagonal energy cell with a lightning glyph and
 * a live pulse. Rendered inline so it scales cleanly everywhere.
 */
export default function Logo({ compact = false, light = true, className = '' }) {
  const id = useId().replace(/:/g, '')
  const grad = `evlogo-${id}`
  const glow = `evglow-${id}`

  return (
    <div className={cx('flex items-center gap-2.5', className)}>
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center">
        <span className="absolute inset-0 rounded-[11px] bg-gradient-to-br from-brand-400/30 to-wind-500/20 blur-[2px]" aria-hidden />
        <svg viewBox="0 0 32 32" className="relative h-9 w-9" role="img" aria-label="ENERVISION">
          <defs>
            <linearGradient id={grad} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#2dd4bf" />
              <stop offset="55%" stopColor="#14b8a6" />
              <stop offset="100%" stopColor="#0891b2" />
            </linearGradient>
            <radialGradient id={glow} cx="50%" cy="35%" r="70%">
              <stop offset="0%" stopColor="#5eead4" stopOpacity="0.55" />
              <stop offset="100%" stopColor="#5eead4" stopOpacity="0" />
            </radialGradient>
          </defs>
          <path d="M16 2.4 27.4 9v14L16 29.6 4.6 23V9Z" fill={`url(#${glow})`} />
          <path
            d="M16 2.4 27.4 9v14L16 29.6 4.6 23V9Z"
            fill="none"
            stroke={`url(#${grad})`}
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
          <path d="M17.9 8.2 11 17.4h4.4l-1.6 6.4 7.2-9.8h-4.4Z" fill={`url(#${grad})`} />
        </svg>
        <span className="absolute right-0 top-0 h-1.5 w-1.5 rounded-full bg-brand-300">
          <span className="absolute inset-0 animate-ping-ring rounded-full bg-brand-300/70" />
        </span>
      </span>
      {!compact ? (
        <span className="min-w-0 leading-none">
          <span
            className={cx(
              'block font-display text-[15px] font-bold tracking-tight',
              light ? 'text-white' : 'text-graphite-900',
            )}
          >
            ENER<span className="text-brand-300">VISION</span>
          </span>
          <span
            className={cx(
              'mt-1 block font-mono text-[8.5px] font-semibold uppercase tracking-[0.18em]',
              light ? 'text-graphite-400' : 'text-graphite-500',
            )}
          >
            Renewable Intelligence
          </span>
        </span>
      ) : null}
    </div>
  )
}
