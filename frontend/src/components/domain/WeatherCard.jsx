import { Droplets, Gauge, Sun, Thermometer, Wind } from 'lucide-react'
import { cx } from '../../utils/format.js'
import { formatDate, formatNumber } from '../../utils/format.js'
import { useCountUp } from '../../hooks/useCountUp.js'
import { WeatherConditionIcon } from './PlantStatus.jsx'

/**
 * Observed-weather summary card. Accepts either a single normalised weather
 * point or a full /api/weather response (latest point is used). Historic and
 * forecast weather are labelled distinctly; missing fields render as N/A.
 */
export default function WeatherCard({ weather, variant = 'compact', className = '', showOutlook = false }) {
  if (!weather) return null
  const point = weather.current ?? (Array.isArray(weather.data) ? weather.data[weather.data.length - 1] : weather)
  if (!point) return null

  const { temperature, humidity, ghi, windSpeed, pressure, condition, cloudCover, rainfall, date } = point
  const temperatureValue = useCountUp(temperature, { decimals: 1 })
  const isFull = variant === 'full'

  const ghiUnit =
    point.ghiUnit || (String(weather?.units?.ghi || '').includes('kWh') ? 'kWh/m²/day' : 'W/m²')

  const title = point.plantName || point.district || weather.plantName || 'Karnataka'
  const isForecast = Boolean(point.isForecast ?? weather.isForecast)
  const weatherType = point.weatherType || weather.weatherType || 'historical'
  const periodLabel = isForecast || weatherType === 'forecast' ? 'Forecast weather' : 'Observed weather'

  const metrics = [
    {
      key: 'hum',
      label: 'Humidity',
      value: valueOrNa(humidity, 0, '%'),
      icon: Droplets,
      cls: 'text-wind-300',
    },
    {
      key: 'ghi',
      label: 'GHI',
      value: valueOrNa(ghi, ghiUnit.includes('kWh') ? 2 : 0),
      unit: ghi === null || ghi === undefined ? '' : ghiUnit,
      icon: Sun,
      cls: 'text-solar-300',
    },
    {
      key: 'wind',
      label: 'Wind',
      value: valueOrNa(windSpeed, 1),
      unit: windSpeed === null || windSpeed === undefined ? '' : 'm/s',
      icon: Wind,
      cls: 'text-brand-300',
    },
    {
      key: 'pressure',
      label: 'Pressure',
      value: valueOrNa(pressure, 2),
      unit: pressure === null || pressure === undefined ? '' : 'kPa',
      icon: Gauge,
      cls: 'text-graphite-300',
    },
  ]

  if (showOutlook && rainfall !== null && rainfall !== undefined) {
    metrics.push({
      key: 'rain',
      label: 'Rainfall',
      value: formatNumber(rainfall, 1),
      unit: 'mm',
      icon: Droplets,
      cls: 'text-sky-300',
    })
  }

  return (
    <div className={cx('panel relative overflow-hidden', isFull ? 'p-5' : 'p-4', className)}>
      <div
        className="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full bg-wind-400/10 blur-3xl"
        aria-hidden
      />

      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow">{periodLabel}</p>
          <p className="mt-1 truncate font-display text-sm font-bold text-white">{title}</p>
          <p className="text-[11px] text-graphite-400">
            {date ? formatDate(date) : 'Date unavailable'}
            {condition ? ` · ${condition}` : ''}
          </p>
        </div>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-graphite-700 bg-graphite-900/70 text-solar-300">
          <WeatherConditionIcon condition={condition} className="h-5 w-5" />
        </span>
      </div>

      <div className="relative mt-3 flex items-end gap-1.5">
        <span className="metric-value text-3xl leading-none">
          {temperature === null || temperature === undefined ? '—' : formatNumber(temperatureValue, 1)}
        </span>
        <span className="pb-1 text-sm font-semibold text-graphite-400">°C</span>
        {showOutlook && cloudCover !== null && cloudCover !== undefined ? (
          <span className="ml-auto pb-1 font-mono text-[11px] text-graphite-400">
            Cloud {formatNumber(cloudCover, 0)}%
          </span>
        ) : null}
      </div>

      <div className={cx('relative mt-4 grid gap-2', isFull ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-2')}>
        {metrics.map((m) => (
          <div
            key={m.key}
            className="flex items-center gap-2 rounded-lg border border-graphite-700/60 bg-graphite-850/50 px-2.5 py-2"
          >
            <m.icon className={cx('h-3.5 w-3.5 shrink-0', m.cls)} />
            <div className="min-w-0">
              <p className="text-[9px] font-semibold uppercase tracking-wide text-graphite-500">{m.label}</p>
              <p className="truncate font-mono text-[11px] font-semibold tabular-nums text-graphite-100">
                {m.value}
                {m.unit ? <span className="ml-0.5 text-graphite-500">{m.unit}</span> : null}
              </p>
            </div>
          </div>
        ))}
      </div>

      <p className="relative mt-3 border-t border-graphite-700/60 pt-2 text-[10px] leading-relaxed text-graphite-500">
        {isForecast || weatherType === 'forecast'
          ? 'Forecast weather supplied by the configured provider.'
          : 'Observed historical weather on the stated date — not a future forecast.'}
        {point.source || weather.source ? ` Source: ${point.source || weather.source}.` : ''}
      </p>
    </div>
  )
}

function valueOrNa(value, digits, suffix = '') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return `${formatNumber(value, digits)}${suffix}`
}
