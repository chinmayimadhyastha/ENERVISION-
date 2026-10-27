import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts'
import { CalendarDays } from 'lucide-react'
import { cx } from '../../utils/format.js'
import { formatDate, formatMU, formatNumber } from '../../utils/format.js'
import { PALETTE } from '../../utils/constants.js'

/**
 * Daily forecast horizon: base date plus one stop per forecast day. Shows
 * predicted DailyGeneration_MU (MU/day) only — the API publishes no confidence
 * or prediction interval, so none is rendered.
 */
export default function ForecastTimeline({ forecast, activeDate, onSelect, className = '' }) {
  const points = forecast?.points ?? []
  if (!points.length) return null

  const chartData = points.map((p) => ({ label: p.label, prediction: p.prediction }))
  const columns = points.length + 1

  return (
    <div className={cx('panel relative overflow-hidden p-5', className)}>
      <div className="pointer-events-none absolute inset-0 ev-grid-sm opacity-40" aria-hidden />
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-400/50 to-transparent"
        aria-hidden
      />

      <div className="relative flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-brand-400/25 bg-brand-400/10 text-brand-300">
            <CalendarDays className="h-4 w-4" />
          </span>
          <div>
            <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Daily Forecast Horizon</h3>
            <p className="eyebrow">
              {forecast.plant?.name ? `${forecast.plant.name} · ` : ''}
              base date {forecast.baseDate ? formatDate(forecast.baseDate) : '—'} · MU/day
            </p>
          </div>
        </div>
        <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-graphite-400">
          {points.length} forecast {points.length === 1 ? 'day' : 'days'}
        </span>
      </div>

      <div className="relative mt-4 h-[110px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
            <defs>
              <linearGradient id="tl-daily" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={PALETTE.brand} stopOpacity={0.3} />
                <stop offset="100%" stopColor={PALETTE.brand} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <YAxis hide domain={[0, 'dataMax']} />
            <Area
              type="monotone"
              dataKey="prediction"
              stroke={PALETTE.brand}
              strokeWidth={2.2}
              fill="url(#tl-daily)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="relative mt-5">
        <div
          className="absolute left-0 right-0 top-[9px] h-px bg-gradient-to-r from-brand-400/60 via-graphite-600 to-graphite-700"
          aria-hidden
        />
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
          <div className="flex flex-col items-center text-center">
            <span className="relative z-10 flex h-[18px] w-[18px] items-center justify-center rounded-full border-2 border-graphite-600 bg-graphite-900">
              <span className="h-1.5 w-1.5 rounded-full bg-graphite-500" />
            </span>
            <span className="mt-2 font-mono text-[10px] font-bold uppercase tracking-wide text-graphite-400">BASE</span>
            <span className="mt-0.5 font-mono text-[10px] text-graphite-500">
              {forecast.baseDate ? formatDate(forecast.baseDate, { year: undefined }) : '—'}
            </span>
            <span className="mt-1.5 text-[10px] font-semibold text-graphite-500">observed</span>
          </div>

          {points.map((p) => {
            const active = activeDate ? p.date === activeDate : false
            return (
              <button
                key={p.date}
                type="button"
                onClick={() => onSelect?.(p.date)}
                className={cx(
                  'group flex flex-col items-center text-center transition-all duration-200',
                  onSelect ? 'cursor-pointer' : 'cursor-default',
                )}
              >
                <span
                  className={cx(
                    'relative z-10 flex h-[18px] w-[18px] items-center justify-center rounded-full border-2 transition-all',
                    active ? 'scale-110 border-brand-300 bg-graphite-950' : 'border-graphite-600 bg-graphite-900',
                  )}
                >
                  <span className={cx('h-1.5 w-1.5 rounded-full', active ? 'bg-brand-400' : 'bg-graphite-500')} />
                </span>

                <span
                  className={cx(
                    'mt-2 font-mono text-[10px] font-bold uppercase tracking-wide',
                    active ? 'text-brand-200' : 'text-graphite-400',
                  )}
                >
                  {p.label}
                </span>
                <span className="mt-0.5 font-mono text-[10px] text-graphite-500">
                  {formatDate(p.date, { year: undefined })}
                </span>

                <span
                  className={cx(
                    'mt-1.5 font-display text-sm font-bold tabular-nums',
                    active ? 'text-white' : 'text-graphite-100',
                  )}
                >
                  {formatNumber(p.prediction, 2)}
                  <span className="ml-0.5 text-[9px] font-semibold text-graphite-500">MU/day</span>
                </span>
                {p.clampApplied ? (
                  <span className="mt-1 text-[9px] font-semibold uppercase tracking-wide text-solar-400">
                    clamped
                  </span>
                ) : null}
              </button>
            )
          })}
        </div>
      </div>

      {forecast.summary?.totalMU !== null && forecast.summary?.totalMU !== undefined ? (
        <p className="relative mt-4 border-t border-graphite-700/60 pt-3 font-mono text-[10px] text-graphite-400">
          Horizon total {formatMU(forecast.summary.totalMU)} · mean {formatMU(forecast.summary.meanMU)} · peak{' '}
          {formatMU(forecast.summary.peakMU)}
          {forecast.summary.peakDate ? ` on ${formatDate(forecast.summary.peakDate)}` : ''}
        </p>
      ) : null}
    </div>
  )
}
