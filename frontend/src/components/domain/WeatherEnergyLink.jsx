import { ArrowRight, BrainCircuit, Droplets, Gauge, Sun, Thermometer, Wind, Zap } from 'lucide-react'
import { cx } from '../../utils/format.js'
import { formatNumber } from '../../utils/format.js'
import { PALETTE } from '../../utils/constants.js'

const TARGETS = {
  solar: { label: 'Solar', color: PALETTE.solar, icon: Sun },
  wind: { label: 'Wind', color: PALETTE.wind, icon: Wind },
  fleet: { label: 'Fleet', color: PALETTE.brand, icon: Zap },
}

/**
 * "Weather → Energy" input chain. Lists the observed weather values that the
 * daily models consume. No correlation coefficient is shown because the API
 * does not publish weather-generation correlations.
 */
export default function WeatherEnergyLink({
  weather,
  className = '',
  title = 'Weather → Energy Model Inputs',
}) {
  const rows = [
    { id: 'ghi', driver: 'GHI', icon: Sun, value: weather?.ghi, unit: weather?.ghiUnit || 'kWh/m²/day', target: 'solar' },
    { id: 'temp', driver: 'Temperature', icon: Thermometer, value: weather?.temperature, unit: '°C', target: 'solar' },
    { id: 'hum', driver: 'Humidity', icon: Droplets, value: weather?.humidity, unit: '%', target: 'solar' },
    { id: 'wind', driver: 'Wind Speed', icon: Wind, value: weather?.windSpeed, unit: 'm/s', target: 'wind' },
    { id: 'pressure', driver: 'Pressure', icon: Gauge, value: weather?.pressure, unit: 'kPa', target: 'fleet', subtle: true },
  ]

  return (
    <div className={cx('panel relative overflow-hidden p-5', className)}>
      <div className="pointer-events-none absolute inset-0 ev-grid-sm opacity-40" aria-hidden />

      <div className="relative flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">{title}</h3>
          <p className="mt-0.5 text-xs text-graphite-400">
            Weather variables are the exogenous predictors of the daily generation models.
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-lg border border-brand-400/25 bg-brand-400/10 px-2.5 py-1.5">
          <BrainCircuit className="h-3.5 w-3.5 text-brand-300" />
          <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-brand-200">
            Model input
          </span>
        </span>
      </div>

      <div className="relative mt-4 space-y-2">
        {rows.map((r) => {
          const t = TARGETS[r.target]
          const hasValue = r.value !== null && r.value !== undefined && !Number.isNaN(Number(r.value))
          return (
            <div
              key={r.id}
              className={cx(
                'grid grid-cols-[minmax(0,1.2fr)_minmax(0,1.1fr)_auto] items-center gap-3 rounded-lg border px-3 py-2.5',
                r.subtle
                  ? 'border-graphite-700/50 bg-graphite-900/40 opacity-80'
                  : 'border-graphite-700/70 bg-graphite-850/50',
              )}
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset"
                  style={{ background: `${t.color}14`, color: t.color }}
                >
                  <r.icon className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-graphite-100">{r.driver}</p>
                  <p className="truncate font-mono text-[10px] text-graphite-500">
                    {hasValue ? `${formatNumber(r.value, r.id === 'temp' ? 1 : 2)} ${r.unit}` : 'unavailable'}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-center gap-1.5 text-graphite-500">
                <span className="h-px flex-1 bg-graphite-700" />
                <ArrowRight className="h-3 w-3" />
              </div>

              <span
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: `${t.color}14`, color: t.color }}
              >
                <t.icon className="h-3 w-3" />
                {t.label}
              </span>
            </div>
          )
        })}
      </div>

      <p className="relative mt-3 font-mono text-[10px] leading-relaxed text-graphite-500">
        Live values come from observed historical weather on the selected date. Note: the API does not publish
        weather-generation correlation coefficients, so none are shown.
      </p>
    </div>
  )
}
