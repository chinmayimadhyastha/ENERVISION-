import { useId } from 'react'
import { cx } from '../../utils/format.js'

/**
 * ENERVISION identity mark — clean modern energy hexagonal cell
 * with emerald & teal gradients.
 */
export default function Logo({ compact = false, className = '' }) {
  const id = useId().replace(/:/g, '')
  const grad = `evlogo-${id}`

  return (
    <div className={cx('flex items-center gap-2.5', className)}>
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center">
        <svg viewBox="0 0 32 32" className="h-9 w-9" role="img" aria-label="ENERVISION">
          <defs>
            <linearGradient id={grad} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#047857" />
              <stop offset="60%" stopColor="#0f766e" />
              <stop offset="100%" stopColor="#0284c7" />
            </linearGradient>
          </defs>
          <path
            d="M16 2.4 27.4 9v14L16 29.6 4.6 23V9Z"
            fill="#ecfdf5"
            stroke={`url(#${grad})`}
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
          <path
            d="M17.9 8.2 11 17.4h4.4l-1.6 6.4 7.2-9.8h-4.4Z"
            fill={`url(#${grad})`}
          />
        </svg>
      </span>
      {!compact ? (
        <span className="min-w-0 leading-none">
          <span className="block font-display text-[15px] font-bold tracking-tight text-slate-900">
            ENER<span className="text-emerald-700">VISION</span>
          </span>
          <span className="mt-1 block font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Karnataka Clean Energy
          </span>
        </span>
      ) : null}
    </div>
  )
}
