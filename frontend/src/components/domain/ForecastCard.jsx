import { AlertTriangle, CalendarDays, Gauge, TrendingUp, Zap } from 'lucide-react'
import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts'
import { cx } from '../../utils/format.js'
import { formatDate, formatMU } from '../../utils/format.js'
import { PALETTE } from '../../utils/constants.js'
import { useCountUp } from '../../hooks/useCountUp.js'
import { PlantTypeBadge } from './PlantStatus.jsx'

export const FORECAST_STATUS_COPY = {
  weather_required: {
    title: 'Forecast unavailable — future weather required',
    body: 'The model needs future weather inputs that are not currently available. No prediction has been generated or substituted.',
  },
  insufficient_history: {
    title: 'Forecast unavailable — insufficient history',
    body: 'This plant does not have enough preceding daily observations for the selected model. Nothing has been interpolated.',
  },
}

/**
 * Daily forecast card for one plant: predicted DailyGeneration_MU (MU/day),
 * horizon summary and the API's calibration status. Confidence is never invented
 * — the backend publishes `confidence: null` and a `confidence_note`.
 */
export default function ForecastCard({ forecast, title = 'Daily Forecast', showPlant = true, className = '' }) {
  if (!forecast) return null
  const { plant, summary, points = [], status } = forecast
  const next = points[0] ?? null
  const nextMU = useCountUp(next?.prediction ?? 0, { duration: 900, decimals: 2 })
  const chartData = points.map((p) => ({ label: p.label, prediction: p.prediction }))

  const header = (
    <div className="relative flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="eyebrow">{title}</p>
        <div className="mt-1 flex items-center gap-2">
          <h3 className="truncate font-display text-base font-bold text-white">
            {showPlant ? plant?.name : 'Selected plant'}
          </h3>
          {plant?.type ? <PlantTypeBadge type={plant.type} size="sm" withIcon={false} /> : null}
        </div>
      </div>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-graphite-700 bg-graphite-900/70 text-brand-300">
        <Zap className="h-4 w-4" />
      </span>
    </div>
  )

  if (status !== 'ok' || !points.length) {
    const copy = FORECAST_STATUS_COPY[status] || {
      title: 'Forecast unavailable',
      body: 'The API did not return a prediction for this plant and horizon.',
    }
    return (
      <div className={cx('panel relative overflow-hidden p-5', className)}>
        {header}
        <div className="relative mt-4 rounded-lg border border-solar-400/25 bg-solar-400/[0.06] p-4">
          <p className="flex items-center gap-1.5 font-display text-sm font-semibold text-solar-200">
            <AlertTriangle className="h-4 w-4" />
            {copy.title}
          </p>
          <p className="mt-1.5 text-[11px] leading-relaxed text-graphite-300">{copy.body}</p>
          {forecast.missingWeather?.length ? (
            <div className="mt-2 space-y-1 font-mono text-[10px] text-graphite-400">
              <p>Missing dates: {forecast.missingWeather.map((m) => (typeof m === 'string' ? m : m.date)).join(', ')}</p>
              {forecast.requiredWeather?.inputs?.length ? (
                <p>Required inputs: {forecast.requiredWeather.inputs.join(', ')}</p>
              ) : null}
            </div>
          ) : null}
          {forecast.insufficientHistory ? (
            <p className="mt-2 font-mono text-[10px] text-graphite-400">
              Available rows: {forecast.insufficientHistory.available ?? '—'} · required:{' '}
              {forecast.insufficientHistory.required ?? '—'}
            </p>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className={cx('panel relative overflow-hidden p-5', className)}>
      <div
        className="pointer-events-none absolute -right-10 -top-14 h-36 w-36 rounded-full bg-brand-400/10 blur-3xl"
        aria-hidden
      />
      {header}

      <div className="relative mt-3 flex items-end gap-2">
        <span className="metric-value text-3xl leading-none">{nextMU}</span>
        <span className="pb-1 text-xs font-semibold text-graphite-400">MU/day · {next?.label || 'next day'}</span>
        <span className="ml-auto pb-1 font-mono text-[11px] text-graphite-400">
          {next?.date ? formatDate(next.date) : '—'}
        </span>
      </div>

      <div className="relative mt-3 h-[110px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 4, right: 2, bottom: 0, left: 2 }}>
            <defs>
              <linearGradient id="fcg-daily" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={PALETTE.brand} stopOpacity={0.28} />
                <stop offset="100%" stopColor={PALETTE.brand} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <YAxis hide domain={[0, 'dataMax']} />
            <Area
              type="monotone"
              dataKey="prediction"
              stroke={PALETTE.brand}
              strokeWidth={2.2}
              fill="url(#fcg-daily)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="relative mt-3 grid grid-cols-3 gap-2">
        <MiniStat
          icon={<TrendingUp className="h-3.5 w-3.5" />}
          label="Peak day"
          value={formatMU(summary?.peakMU)}
          tone="text-brand-300"
        />
        <MiniStat
          icon={<CalendarDays className="h-3.5 w-3.5" />}
          label="Horizon total"
          value={formatMU(summary?.totalMU)}
          tone="text-solar-300"
        />
        <MiniStat
          icon={<Gauge className="h-3.5 w-3.5" />}
          label="Mean / day"
          value={formatMU(summary?.meanMU)}
          tone="text-graphite-300"
        />
      </div>

      <div className="relative mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-graphite-700/60 bg-graphite-850/40 px-3 py-2">
        <span className="eyebrow">Model confidence</span>
        <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-graphite-400">
          Not calibrated
        </span>
        <p className="w-full text-[10px] leading-relaxed text-graphite-500">
          {forecast.confidenceNote || 'No calibrated probabilistic confidence is published for this forecast.'}
        </p>
      </div>
    </div>
  )
}

function MiniStat({ icon, label, value, tone = 'text-graphite-300' }) {
  return (
    <div className="rounded-lg border border-graphite-700/60 bg-graphite-850/50 px-2.5 py-2">
      <p className="flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wide text-graphite-500">
        <span className={tone}>{icon}</span>
        {label}
      </p>
      <p className="mt-0.5 truncate font-mono text-[11px] font-bold tabular-nums text-graphite-100">{value}</p>
    </div>
  )
}
