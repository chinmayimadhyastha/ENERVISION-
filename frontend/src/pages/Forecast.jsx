import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { AlertTriangle, CalendarDays, CloudSun, Gauge, LineChart, Target, TrendingUp, Zap } from 'lucide-react'

import { getForecast, getGenerationHistory, getPlants, getWeather } from '../services/api.js'
import useAsync from '../hooks/useAsync.js'
import { formatDate, formatDateShort, formatMU, formatNumber } from '../utils/format.js'
import {
  AXIS_PROPS,
  FORECAST_HORIZONS,
  FORECAST_MODELS,
  GRID_PROPS,
  PALETTE,
  RENEWABLE_TYPES,
} from '../utils/constants.js'

import PageHeader from '../components/ui/PageHeader.jsx'
import Card from '../components/ui/Card.jsx'
import ChartCard from '../components/ui/ChartCard.jsx'
import StatCard from '../components/ui/StatCard.jsx'
import Badge from '../components/ui/Badge.jsx'
import Select from '../components/ui/Select.jsx'
import DemoNotice, { RESEARCH_DEMO_LABEL } from '../components/ui/DemoNotice.jsx'
import LoadingState from '../components/ui/LoadingState.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import DataTable from '../components/ui/DataTable.jsx'
import { ChartTooltip, ChartLegend } from '../components/charts/index.js'

import ForecastTimeline from '../components/domain/ForecastTimeline.jsx'
import WeatherEnergyLink from '../components/domain/WeatherEnergyLink.jsx'
import WeatherCard from '../components/domain/WeatherCard.jsx'
import { PlantTypeBadge } from '../components/domain/PlantStatus.jsx'
import ForecastExplainability from '../components/domain/ForecastExplainability.jsx'

const DEFAULT_HORIZON = 3

const STATUS_COPY = {
  weather_required: {
    title: 'Forecast unavailable — future weather required',
    body: 'Every forecast day needs weather inputs, and no future-weather provider is configured. The API returned an honest unavailable state; no prediction, zero value, or historical weather has been substituted.',
  },
  insufficient_history: {
    title: 'Forecast unavailable — insufficient history',
    body: 'This plant does not have enough preceding daily observations for the selected model. No values have been interpolated or synthesised.',
  },
}

export default function Forecast() {
  const plantsAsync = useAsync(() => getPlants(), [])
  const plants = useMemo(() => plantsAsync.data ?? [], [plantsAsync.data])

  const [searchParams, setSearchParams] = useSearchParams()
  const plantFromQuery = searchParams.get('plant') || ''

  const [plantId, setPlantId] = useState(plantFromQuery)
  const [horizon, setHorizon] = useState(DEFAULT_HORIZON)
  const [model, setModel] = useState('auto')
  const [activeDate, setActiveDate] = useState(null)

  // Keep the selection in sync with deep links such as /forecast?plant=gadag-vena-w
  useEffect(() => {
    setPlantId(plantFromQuery)
  }, [plantFromQuery])

  const requestedPlant = plants.find((p) => p.id === plantId) || null
  const selectedPlantId = requestedPlant?.id || plants.find((p) => p.id === 'kredl')?.id || plants[0]?.id || ''
  const plant = plants.find((p) => p.id === selectedPlantId) || null
  const unknownPlant = Boolean(plantId) && plants.length > 0 && !requestedPlant

  const forecastAsync = useAsync(
    () => (selectedPlantId ? getForecast({ plantId: selectedPlantId, horizon, model }) : Promise.resolve(null)),
    [selectedPlantId, horizon, model],
  )
  const historyAsync = useAsync(
    () => (selectedPlantId ? getGenerationHistory({ plantId: selectedPlantId }) : Promise.resolve(null)),
    [selectedPlantId],
  )
  const weatherAsync = useAsync(
    () => (selectedPlantId ? getWeather({ plantId: selectedPlantId }) : Promise.resolve(null)),
    [selectedPlantId],
  )

  const forecast = forecastAsync.data
  const history = historyAsync.data

  const weatherCurrent = useMemo(() => {
    const w = weatherAsync.data
    if (!w?.data?.length) return null
    const latest = w.data[w.data.length - 1]
    return {
      ...latest,
      plantName: w.plantName,
      district: plant?.district,
      weatherType: w.weatherType,
      isForecast: w.isForecast,
      ghiUnit: 'kWh/m²/day',
      source: w.source,
    }
  }, [weatherAsync.data, plant])

  const chartData = useMemo(() => {
    const observed = (history?.points ?? []).slice(-21).map((p) => ({
      date: p.date,
      observed: p.generationMU,
      forecast: null,
    }))
    const predicted = (forecast?.points ?? []).map((p) => ({
      date: p.date,
      observed: null,
      forecast: p.prediction,
      label: p.label,
    }))
    return [...observed, ...predicted]
  }, [history, forecast])

  const activePoint = useMemo(() => {
    const points = forecast?.points ?? []
    if (!points.length) return null
    return points.find((p) => p.date === activeDate) ?? points[0]
  }, [forecast, activeDate])

  const unavailableCopy = forecast && forecast.status !== 'ok' ? STATUS_COPY[forecast.status] : null
  const missing = forecast?.missingWeather ?? []
  const inputs = forecast?.requiredWeather?.inputs ?? []

  const tableColumns = [
    {
      key: 'label',
      header: 'Day',
      render: (r) => <span className="font-mono text-[11px] font-bold text-graphite-100">{r.label}</span>,
    },
    {
      key: 'date',
      header: 'Date',
      render: (r) => <span className="font-mono text-[11px] text-graphite-300">{formatDate(r.date)}</span>,
    },
    {
      key: 'prediction',
      header: 'Prediction',
      align: 'right',
      render: (r) => (
        <span className="font-mono text-xs font-bold text-white">
          {formatNumber(r.prediction, 2)} <span className="text-graphite-500">MU/day</span>
        </span>
      ),
    },
    {
      key: 'rawPrediction',
      header: 'Raw model output',
      align: 'right',
      render: (r) => (
        <span className="font-mono text-[11px] text-graphite-400">{formatNumber(r.rawPrediction, 3)}</span>
      ),
    },
    {
      key: 'confidenceInterval',
      header: 'P10 – P90 (80% Interval)',
      align: 'right',
      render: (r) => (
        <span className="font-mono text-[11px] text-emerald-800 font-semibold" title={r.p50 != null ? `Median P50: ${formatNumber(r.p50, 2)} MU/day` : ''}>
          {r.lowerBound != null ? `[${formatNumber(r.lowerBound, 2)}, ${formatNumber(r.upperBound, 2)}]` : '—'}
        </span>
      ),
    },
    {
      key: 'clampApplied',
      header: 'Post-processed',
      align: 'right',
      render: (r) => (
        <span className={r.clampApplied ? 'font-mono text-[10px] text-amber-600 font-medium' : 'font-mono text-[10px] text-slate-400'}>
          {r.clampApplied ? 'clamped ≥ 0' : 'nominal'}
        </span>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Daily Forecasting"
        title="Generation Forecast"
        description="Daily plant generation forecast for the next 1–7 days. Target DailyGeneration_MU, unit MU/day. No hourly values are produced by this API."
        icon={<LineChart className="h-5 w-5" />}
        badge={
          <Badge tone="violet" size="sm">
            daily · 1–7 days
          </Badge>
        }
        meta={[
          { label: 'Asset', value: plant?.name ?? '—' },
          { label: 'Source', value: plant ? RENEWABLE_TYPES[plant.type]?.label || plant.type : '—' },
          { label: 'District', value: plant?.district ?? '—' },
          { label: 'Horizon', value: `${horizon} ${horizon === 1 ? 'day' : 'days'}` },
        ]}
        actions={
          <>
            <Select
              aria-label="Plant"
              value={requestedPlant?.id || selectedPlantId}
              onChange={(e) => {
                const value = e.target.value
                setPlantId(value)
                setActiveDate(null)
                setSearchParams(value ? { plant: value } : {}, { replace: true })
              }}
              options={plants.map((p) => ({ value: p.id, label: `${p.name} · ${p.id}` }))}
              className="w-full sm:w-72"
              selectClassName="py-1.5 text-xs"
            />
            <Select
              aria-label="Forecast model"
              value={model}
              onChange={(e) => {
                setModel(e.target.value)
                setActiveDate(null)
              }}
              options={FORECAST_MODELS}
              className="w-full sm:w-56"
              selectClassName="py-1.5 text-xs"
            />
            <Select
              aria-label="Forecast horizon"
              value={horizon}
              onChange={(e) => {
                setHorizon(Number(e.target.value))
                setActiveDate(null)
              }}
              options={FORECAST_HORIZONS}
              className="w-full sm:w-32"
              selectClassName="py-1.5 text-xs"
            />
          </>
        }
      />

      <DemoNotice label={RESEARCH_DEMO_LABEL} tone="sky">
        This screen shows the live daily forecasting contract when <code className="font-mono">VITE_API_BASE_URL</code>{' '}
        is configured. In demo mode the daily values are illustrative and clearly labelled.
      </DemoNotice>

      {unknownPlant ? (
        <Card padded accent="solar" className="border-solar-400/25 bg-solar-400/[0.04]">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-solar-300" />
            <p className="text-[11px] leading-relaxed text-graphite-300">
              The plant id <code className="font-mono text-solar-200">{plantId}</code> is not present in the backend
              plant registry, so no forecast was requested for it. Showing{' '}
              <span className="font-semibold text-graphite-100">{plants[0]?.name}</span> instead — choose a plant from
              the selector to request a real forecast.
            </p>
          </div>
        </Card>
      ) : null}

      {plantsAsync.loading ? (
        <LoadingState variant="cards" />
      ) : plantsAsync.error ? (
        <ErrorState
          onRetry={plantsAsync.refetch}
          message={plantsAsync.error.userMessage || plantsAsync.error.message}
        />
      ) : forecastAsync.loading ? (
        <LoadingState variant="cards" />
      ) : forecastAsync.error ? (
        <ErrorState
          onRetry={forecastAsync.refetch}
          message={forecastAsync.error.userMessage || forecastAsync.error.message}
        />
      ) : !forecast ? (
        <ErrorState title="No forecast returned" message="Select a plant to request a daily forecast." />
      ) : (
        <>
          {unavailableCopy ? (
            <Card padded accent="solar" className="border-solar-400/25 bg-solar-400/[0.04]">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-solar-400/25 bg-solar-400/10 text-solar-300">
                  <AlertTriangle className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <h3 className="font-display text-sm font-bold text-solar-100">{unavailableCopy.title}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-graphite-300">{unavailableCopy.body}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Badge tone="warning" size="sm" mono>
                      status: {forecast.status}
                    </Badge>
                    <Badge tone="neutral" size="sm" mono>
                      model: {forecast.model || forecast.modelRequested || '—'}
                    </Badge>
                    <Badge tone="neutral" size="sm" mono>
                      base date: {forecast.baseDate ? formatDate(forecast.baseDate) : '—'}
                    </Badge>
                  </div>
                  {missing.length ? (
                    <div className="mt-3 rounded-lg border border-graphite-700/70 bg-graphite-900/50 p-3">
                      <p className="eyebrow">Missing future weather</p>
                      <ul className="mt-1.5 space-y-1">
                        {missing.map((m) => (
                          <li key={typeof m === 'string' ? m : m.date} className="font-mono text-[10px] text-graphite-300">
                            {typeof m === 'string' ? m : m.date}
                            {Array.isArray(m.missing_inputs) && m.missing_inputs.length
                              ? ` — ${m.missing_inputs.join(', ')}`
                              : ''}
                          </li>
                        ))}
                      </ul>
                      {inputs.length ? (
                        <p className="mt-2 text-[10px] text-graphite-500">Required inputs: {inputs.join(', ')}</p>
                      ) : null}
                      {forecast.requiredWeather?.note ? (
                        <p className="mt-2 text-[10px] leading-relaxed text-graphite-500">
                          {forecast.requiredWeather.note}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                  {forecast.insufficientHistory ? (
                    <p className="mt-3 font-mono text-[10px] text-graphite-400">
                      Available rows: {forecast.insufficientHistory.available ?? '—'} · required:{' '}
                      {forecast.insufficientHistory.required ?? '—'}
                    </p>
                  ) : null}
                </div>
              </div>
            </Card>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard
                  label={activePoint ? `${activePoint.label} (${formatDate(activePoint.date, { year: undefined })})` : 'Predicted Day'}
                  value={activePoint?.prediction ?? null}
                  decimals={2}
                  unit="MU/day"
                  tone={plant?.type === 'wind' ? 'wind' : 'solar'}
                  icon={<Zap className="h-4 w-4" />}
                  hint={activePoint?.date ? `Raw: ${formatNumber(activePoint.rawPrediction, 3)} MU/day` : ''}
                />
                <StatCard
                  label={activePoint ? `${activePoint.label} P10 – P90 (80%)` : 'P10 – P90 Interval (80%)'}
                  value={
                    activePoint?.lowerBound != null
                      ? `${formatNumber(activePoint.lowerBound, 2)} – ${formatNumber(activePoint.upperBound, 2)}`
                      : '80% Calibrated'
                  }
                  unit="MU/day"
                  tone="emerald"
                  icon={<Gauge className="h-4 w-4" />}
                  hint={activePoint?.p50 != null ? `Median P50: ${formatNumber(activePoint.p50, 2)} MU/day` : (forecast.confidenceNote || 'Calibrated interval')}
                />
                <StatCard
                  label="Horizon total"
                  value={forecast.summary?.totalMU ?? null}
                  decimals={2}
                  unit="MU/day"
                  tone="brand"
                  icon={<Target className="h-4 w-4" />}
                  hint={`${forecast.horizonDays} forecast ${forecast.horizonDays === 1 ? 'day' : 'days'} · MU/day`}
                />
                <StatCard
                  label="Peak day"
                  value={forecast.summary?.peakMU ?? null}
                  decimals={2}
                  unit="MU/day"
                  tone="violet"
                  icon={<TrendingUp className="h-4 w-4" />}
                  hint={forecast.summary?.peakDate ? `${formatDate(forecast.summary.peakDate, { year: undefined })} (highest)` : ''}
                />
              </div>

              <ForecastTimeline forecast={forecast} activeDate={activePoint?.date} onSelect={setActiveDate} />

              <section className="grid gap-5 xl:grid-cols-3">
                <Card padded accent="violet" className="xl:col-span-2">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-violet-400/25 bg-violet-400/10 text-violet-300">
                        <CalendarDays className="h-4 w-4" />
                      </span>
                      <div>
                        <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">
                          Forecast day inspector
                        </h3>
                        <p className="eyebrow">
                          {activePoint ? `${activePoint.label} · ${formatDate(activePoint.date)}` : '—'}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {plant ? <PlantTypeBadge type={plant.type} size="sm" /> : null}
                      <Badge tone="neutral" size="sm" mono>
                        {forecast.model || '—'}
                      </Badge>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 sm:grid-cols-5">
                    <BigStat
                      label="Predicted generation"
                      value={formatMU(activePoint?.prediction, 2)}
                      tone="text-brand-300"
                    />
                    <BigStat label="Forecast day" value={activePoint?.label || '—'} tone="text-violet-300" />
                    <BigStat
                      label="P10 – P90 Interval"
                      value={activePoint?.lowerBound != null ? `${formatNumber(activePoint.lowerBound, 2)} – ${formatNumber(activePoint.upperBound, 2)}` : '—'}
                      unit="MU/day"
                      tone="text-emerald-300"
                    />
                    <BigStat
                      label="Raw model output"
                      value={formatNumber(activePoint?.rawPrediction, 3)}
                      unit="MU/day"
                      tone="text-graphite-200"
                    />
                    <BigStat
                      label="Post-processing"
                      value={activePoint?.clampApplied ? 'Clamped ≥ 0' : 'Unchanged'}
                      tone={activePoint?.clampApplied ? 'text-solar-300' : 'text-emerald-300'}
                    />
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <WeatherPill label="Target" value={forecast.target || 'DailyGeneration_MU'} />
                    <WeatherPill label="Frequency" value={forecast.frequency || 'daily'} />
                    <WeatherPill label="Unit" value={forecast.unit || 'MU/day'} />
                  </div>
                </Card>

                <Card padded accent="brand" className="flex flex-col justify-between gap-4">
                  <div>
                    <p className="eyebrow">Model confidence</p>
                    <p className="mt-2 font-display text-xl font-bold text-white">
                      {forecast.confidence ? 'Calibrated (P10/P50/P90)' : 'Not calibrated'}
                    </p>
                    <p className="mt-2 text-[11px] leading-relaxed text-graphite-400">
                      {forecast.confidenceNote ||
                        'Calibrated 80% coverage interval [P10, P90] generated with pinball loss quantile gradient boosting.'}
                    </p>
                  </div>
                  <div className="rounded-lg border border-graphite-700/60 bg-graphite-850/40 px-3 py-2">
                    <p className="eyebrow">Model requested</p>
                    <p className="mt-0.5 font-mono text-[11px] font-semibold text-graphite-100">
                      {forecast.modelRequested || '—'} → {forecast.model || '—'}
                    </p>
                    <p className="mt-1 text-[10px] text-graphite-500">
                      {forecast.isDemo
                        ? 'Demo mode uses an illustrative daily generator; committed models are used only in live mode.'
                        : model === 'auto'
                          ? 'Auto selects the type-specific LSTM (solar/wind).'
                          : model === 'rf'
                            ? 'Random Forest daily model.'
                            : 'Type-specific LSTM daily model.'}
                    </p>
                  </div>
                </Card>
              </section>

              <ChartCard
                title="Observed & Forecast Daily Generation"
                subtitle={`Observed daily generation followed by the ${forecast.horizonDays}-day forecast · ${plant?.name ?? ''}`}
                icon={<LineChart className="h-4 w-4" />}
                accent="brand"
                height={340}
                actions={
                  <Badge tone="brand" size="sm">
                    {forecast.horizonDays} {forecast.horizonDays === 1 ? 'day' : 'days'} · MU/day
                  </Badge>
                }
                footer={
                  <ChartLegend
                    items={[
                      { key: 'observed', label: 'Observed (MU/day)', color: PALETTE.solar },
                      { key: 'forecast', label: 'Forecast (MU/day)', color: PALETTE.brand, glow: true },
                    ]}
                  />
                }
              >
                {chartData.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 10, right: 12, bottom: 0, left: -10 }}>
                      <defs>
                        <linearGradient id="fcObserved" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={PALETTE.solar} stopOpacity={0.28} />
                          <stop offset="100%" stopColor={PALETTE.solar} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid {...GRID_PROPS} />
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatDateShort}
                        minTickGap={22}
                        {...AXIS_PROPS}
                      />
                      <YAxis
                        {...AXIS_PROPS}
                        width={52}
                        label={{
                          value: 'MU/day',
                          angle: -90,
                          position: 'insideLeft',
                          fill: PALETTE.tick,
                          fontSize: 10,
                        }}
                      />
                      <Tooltip
                        content={
                          <ChartTooltip
                            units={{ observed: ' MU/day', forecast: ' MU/day' }}
                            digits={2}
                            labelFormatter={(value) => formatDate(value)}
                          />
                        }
                      />
                      {forecast.baseDate ? (
                        <ReferenceLine
                          x={forecast.baseDate}
                          stroke={PALETTE.violet}
                          strokeDasharray="4 3"
                          strokeOpacity={0.7}
                          label={{ value: 'BASE', fill: PALETTE.violet, fontSize: 10, position: 'insideTopRight' }}
                        />
                      ) : null}
                      <Area
                        type="monotone"
                        dataKey="observed"
                        name="Observed"
                        stroke={PALETTE.solar}
                        strokeWidth={2}
                        fill="url(#fcObserved)"
                        connectNulls={false}
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="forecast"
                        name="Forecast"
                        stroke={PALETTE.brand}
                        strokeWidth={2.4}
                        dot={{ r: 2.5, fill: PALETTE.brand }}
                        connectNulls={false}
                        isAnimationActive={false}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-graphite-400">
                    No daily series available for this plant.
                  </div>
                )}
              </ChartCard>

              <Card padded={false}>
                <div className="flex items-center justify-between border-b border-graphite-700/70 px-4 py-3.5">
                  <div>
                    <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Daily steps</h3>
                    <p className="eyebrow">one row per forecast day · MU/day</p>
                  </div>
                  <span className="font-mono text-[11px] text-graphite-400">
                    {forecast.points.length} {forecast.points.length === 1 ? 'day' : 'days'}
                  </span>
                </div>
                <div className="p-3">
                  <DataTable columns={tableColumns} rows={forecast.points} keyField="date" dense maxHeight={360} />
                </div>
              </Card>

              <ForecastExplainability
                plantId={selectedPlantId}
                plantName={plant?.name}
                renewableType={plant?.type}
                model={model}
              />
            </>
          )}

          <section className="grid gap-5 xl:grid-cols-2">
            <div className="space-y-4">
              {weatherAsync.loading ? (
                <LoadingState variant="chart" />
              ) : weatherAsync.error ? (
                <ErrorState
                  compact
                  title="Observed weather unavailable"
                  message={weatherAsync.error.userMessage || weatherAsync.error.message}
                  onRetry={weatherAsync.refetch}
                />
              ) : weatherCurrent ? (
                <WeatherCard weather={weatherCurrent} variant="full" showOutlook />
              ) : (
                <Card padded>
                  <p className="eyebrow">Observed weather</p>
                  <p className="mt-2 text-xs text-graphite-400">
                    No observed weather rows were returned for this plant.
                  </p>
                </Card>
              )}
            </div>

            <div className="space-y-4">
              {weatherCurrent ? <WeatherEnergyLink weather={weatherCurrent} /> : null}
              <Card padded accent="solar">
                <p className="flex items-center gap-1.5 eyebrow">
                  <CloudSun className="h-3 w-3 text-solar-300" /> Future weather availability
                </p>
                <p className="mt-2 text-[11px] leading-relaxed text-graphite-300">
                  {forecast?.futureWeather?.future_weather_available
                    ? 'A future-weather provider is configured for this deployment.'
                    : 'No future-weather provider is configured. Historical weather is never reused or truncated as a forecast, so multi-day predictions remain unavailable unless the required future weather is supplied.'}
                </p>
                <p className="mt-2 font-mono text-[10px] text-graphite-500">
                  provider: {forecast?.futureWeather?.provider || forecast?.requiredWeather?.provider || 'unavailable'}
                </p>
              </Card>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function BigStat({ label, value, unit, tone = 'text-white' }) {
  return (
    <div className="rounded-lg border border-graphite-700/70 bg-graphite-850/50 px-3.5 py-3">
      <p className="eyebrow">{label}</p>
      <p className={`mt-1 font-display text-xl font-bold tabular-nums ${tone}`}>
        {value}
        {unit ? <span className="ml-1 text-[11px] font-semibold text-graphite-500">{unit}</span> : null}
      </p>
    </div>
  )
}

function WeatherPill({ label, value }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-graphite-700/60 bg-graphite-900/40 px-3 py-2">
      <span className="eyebrow">{label}</span>
      <span className="truncate font-mono text-[11px] font-semibold text-graphite-200">{value}</span>
    </div>
  )
}
