import { cx } from '../../utils/format.js'
import { useCountUp } from '../../hooks/useCountUp.js'

/**
 * Animated radial gauge (0–100). Used for confidence, R² and coverage visuals.
 */
export default function RadialGauge({
  value = 0,
  size = 96,
  thickness = 8,
  label,
  sublabel,
  color = '#2dd4bf',
  trackColor = 'rgba(148,163,184,0.14)',
  valueText,
  className = '',
}) {
  const v = useCountUp(value, { duration: 1100, decimals: 1 })
  const clamped = Math.max(0, Math.min(100, v))
  const r = (size - thickness) / 2
  const circ = 2 * Math.PI * r
  const dash = (clamped / 100) * circ
  const center = size / 2

  return (
    <div className={cx('flex flex-col items-center', className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={center} cy={center} r={r} fill="none" stroke={trackColor} strokeWidth={thickness} />
          <circle
            cx={center}
            cy={center}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={thickness}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
            style={{ filter: `drop-shadow(0 0 6px ${color}88)`, transition: 'stroke-dasharray 120ms linear' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-lg font-bold tabular-nums text-white">
            {valueText ?? `${Math.round(clamped)}`}
          </span>
          {sublabel ? <span className="font-mono text-[9px] uppercase tracking-wide text-graphite-500">{sublabel}</span> : null}
        </div>
      </div>
      {label ? <span className="eyebrow mt-2 text-center">{label}</span> : null}
    </div>
  )
}
