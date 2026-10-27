import { Cloud, CloudRain, Factory, Sun, Wind } from 'lucide-react'
import { cx } from '../../utils/format.js'
import Badge from '../ui/Badge.jsx'
import { PLANT_STATUS, RENEWABLE_TYPES } from '../../utils/constants.js'

export function PlantTypeBadge({ type, size = 'md', withIcon = true, className = '' }) {
  const meta = RENEWABLE_TYPES[type] || RENEWABLE_TYPES.solar
  return (
    <Badge
      tone={type === 'wind' ? 'wind' : 'solar'}
      size={size}
      className={className}
      icon={withIcon ? (type === 'wind' ? <Wind className="h-3 w-3" /> : <Sun className="h-3 w-3" />) : undefined}
    >
      {meta.label}
    </Badge>
  )
}

export function PlantStatusBadge({ status, size = 'md', className = '' }) {
  const meta = PLANT_STATUS[status] || PLANT_STATUS.operational
  return (
    <Badge tone={meta.tone} size={size} dot pulse={meta.tone === 'success'} className={className}>
      {meta.label}
    </Badge>
  )
}

export function TypeIcon({ type, className = 'h-4 w-4' }) {
  return type === 'wind' ? <Wind className={className} /> : <Sun className={className} />
}

export function WeatherConditionIcon({ condition, className = 'h-4 w-4' }) {
  const key = String(condition || '').toLowerCase()
  if (key.includes('rain')) return <CloudRain className={className} />
  if (key.includes('cloud') || key.includes('overcast')) return <Cloud className={className} />
  return <Sun className={className} />
}

/** Small factory/plant glyph chip used in tables and list rows. */
export function PlantGlyph({ type, className = '' }) {
  const isWind = type === 'wind'
  return (
    <span
      className={cx(
        'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset',
        isWind ? 'bg-wind-400/10 text-wind-300 ring-wind-400/20' : 'bg-solar-400/10 text-solar-300 ring-solar-400/20',
        className,
      )}
    >
      {isWind ? <Wind className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </span>
  )
}

export { Factory }

/** Backwards-compatible alias (older pages import PlantAvatar). */
export const PlantAvatar = PlantGlyph

/** Maps a utilisation percentage (0–100) to a semantic tone. */
export function utilTone(utilization) {
  const u = Number(utilization) || 0
  if (u >= 75) return 'emerald'
  if (u >= 55) return 'brand'
  if (u >= 35) return 'solar'
  return 'danger'
}
