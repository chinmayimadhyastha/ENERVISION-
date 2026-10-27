import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Activity,
  ArrowUpRight,
  BatteryCharging,
  CalendarDays,
  CloudSun,
  Gauge,
  Leaf,
  MapPinned,
  Radar,
  Target,
  Zap,
} from 'lucide-react'

import { getDashboardData, getForecast } from '../services/api.js'
import useAsync from '../hooks/useAsync.js'
import { formatDate, formatDateShort, formatMU, formatNumber, formatPercent, formatPower } from '../utils/format.js'
import { AXIS_PROPS, GRID_PROPS, PALETTE } from '../utils/constants.js'

import PageHeader from '../components/ui/PageHeader.jsx'
import SectionTitle from '../components/ui/SectionTitle.jsx'
import Card from '../components/ui/Card.jsx'
import ChartCard from '../components/ui/ChartCard.jsx'
import StatCard from '../components/ui/StatCard.jsx'
import Badge from '../components/ui/Badge.jsx'
import Button from '../components/ui/Button.jsx'
import DemoNotice, { RESEARCH_DEMO_LABEL } from '../components/ui/DemoNotice.jsx'
import LoadingState from '../components/ui/LoadingState.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import { ChartTooltip, ChartLegend } from '../components/charts/index.js'

import KarnatakaMap from '../components/domain/KarnatakaMap.jsx'
import EnergyPulse from '../components/domain/EnergyPulse.jsx'
import ForecastTimeline from '../components/domain/ForecastTimeline.jsx'
import ForecastCard from '../components/domain/ForecastCard.jsx'
import InsightPanel from '../components/domain/InsightPanel.jsx'
import WeatherEnergyLink from '../components/domain/WeatherEnergyLink.jsx'
import WeatherCard from '../components/domain/WeatherCard.jsx'
import { PlantGlyph, PlantTypeBadge } from '../components/domain/PlantStatus.jsx'

const MIX_COLORS = { Solar: PALETTE.solar, Wind: PALETTE.wind }

export default function Dashboard() {
  const navigate = useNavigate()
  const dash = useAsync(() => getDashboardData(), [])

  const data = dash.data
  const representative = useMemo(() => {
    const plants = data?.plants ?? []
    return plants.find((p) => p.type === 'solar') ?? plants[0] ?? null
  }, [data])

  const repForecast = useAsync(
    () => (representative?.id ? getForecast({ plantId: representative.id, model: 'lstm', horizon: 1 }) : Promise.resolve(null)),
    [representative?.id],
  )

  if (dash.loading) {
    return (
      <div className="space-y-5">
        <LoadingState variant="cards" />
        <div className="grid gap-5 xl:grid-cols-12">
          <div className="xl:col-span-8">
            <LoadingState variant="chart" />
          </div>
          <div className="space-y-5 xl:col-span-4">
            <LoadingState variant="chart" />
          </div>
        </div>
      </div>
    )
  }

  if (dash.error || !data) {
    return (
      <ErrorState
        title="Dashboard unavailable"
        message={dash.error?.userMessage || dash.error?.message}
        onRetry={dash.refetch}
      />
    )
  }

  const o = data.overview
  const topDistricts = data.topDistricts.slice(0, 8)
  const plantRows = [...data.plants].sort((a, b) => (b.capacityMW || 0) - (a.capacityMW || 0)).slice(0, 6)
  const mixTotal = data.mix.reduce((s, m) => s + (m.value || 0), 0) || 1
  const daily = data.daily ?? []
  const spark = daily.slice(-30).map((d) => ({ total: d.total }))
  const latest = daily[daily.length - 1] ?? null

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Mission Control"
        title="Karnataka Renewable Energy Dashboard"
        description="State-wide view of monitored solar and wind assets, observed daily generation (MU/day), weather drivers and the daily generation forecast."
        badge={
          <Badge tone="brand" size="sm" dot>
            Daily dataset
          </Badge>
        }
        icon={<Radar className="h-5 w-5" />}
        meta={[
          { label: 'Fleet', value: `${o.plantCount ?? '—'} plants` },
          { label: 'Capacity', value: formatPower(o.totalCapacityMW, 0) },
          { label: 'As of', value: data.meta?.asOfDate ? formatDate(data.meta.asOfDate) : '—' },
          {
            label: 'Reporting',
            value: `${o.reportingPlants ?? '—'}/${o.plantCount ?? '—'} plants`,
          },
        ]}
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => navigate('/forecast')}>
              <Zap className="h-3.5 w-3.5" /> Open forecast
            </Button>
            <Button variant="primary" size="sm" onClick={() => navigate('/plants')}>
              <MapPinned className="h-3.5 w-3.5" /> Plant explorer
            </Button>
          </>
        }
      />

      <DemoNotice label={RESEARCH_DEMO_LABEL}>
        Demo mode shows illustrative daily values. With <code className="font-mono">VITE_API_BASE_URL</code> configured,
        every figure below comes from the live backend; failures are shown as errors rather than replaced by demo data.
      </DemoNotice>

      {/* HERO — map + daily pulse/KPIs */}
      <section className="grid gap-5 xl:grid-cols-12">
        <Card padded={false} className="xl:col-span-8">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-graphite-700/70 px-4 py-3.5">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-brand-400/25 bg-brand-400/10 text-brand-300">
                <MapPinned className="h-4 w-4" />
              </span>
              <div>
                <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">
                  Karnataka Plant Network
                </h3>
                <p className="eyebrow">Observed sites · node size ∝ capacity · click a node to open its asset view</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone="solar" size="sm" dot>
                {o.solarPlantCount} solar
              </Badge>
              <Badge tone="wind" size="sm" dot>
                {o.windPlantCount} wind
              </Badge>
            </div>
          </div>

          <div className="relative h-[480px] sm:h-[560px] xl:h-[600px]">
            <KarnatakaMap plants={data.plants} onSelect={(p) => navigate(`/plants/${p.id}`)} />
          </div>

          <div className="grid grid-cols-2 divide-x divide-graphite-700/70 border-t border-graphite-700/70 sm:grid-cols-4">
            <MiniStat label="Solar latest day" value={formatMU(o.solarGenerationMU, 2)} tone="text-solar-300" />
            <MiniStat label="Wind latest day" value={formatMU(o.windGenerationMU, 2)} tone="text-wind-300" />
            <MiniStat label="Fleet latest day" value={formatMU(o.totalGenerationMU, 2)} tone="text-brand-300" />
            <MiniStat
              label="Coverage"
              value={o.coveragePct === null || o.coveragePct === undefined ? '—' : formatPercent(o.coveragePct, 0)}
              tone="text-graphite-100"
            />
          </div>
        </Card>

        <div className="space-y-5 xl:col-span-4">
          <EnergyPulse
            totalMU={o.totalGenerationMU}
            solarMU={o.solarGenerationMU}
            windMU={o.windGenerationMU}
            plantCount={o.plantCount}
            reportingPlants={o.reportingPlants}
            date={o.latestDate}
            spark={spark}
          />

          <div className="grid grid-cols-2 gap-4">
            <StatCard
              label="Installed capacity"
              value={o.totalCapacityMW ? o.totalCapacityMW / 1000 : null}
              decimals={2}
              unit="GW"
              tone="brand"
              icon={<BatteryCharging className="h-4 w-4" />}
              hint={`${o.plantCount ?? '—'} plants`}
            />
            <StatCard
              label="Latest daily generation"
              value={o.totalGenerationMU ?? null}
              decimals={2}
              unit="MU/day"
              tone="violet"
              icon={<Target className="h-4 w-4" />}
              hint={o.latestDate ? formatDate(o.latestDate) : ''}
            />
            <StatCard
              label="Reporting coverage"
              value={o.coveragePct ?? null}
              decimals={0}
              unit="%"
              tone="solar"
              icon={<Gauge className="h-4 w-4" />}
              progress={o.coveragePct ?? 0}
              hint={`${o.reportingPlants ?? '—'} of ${o.plantCount ?? '—'} plants`}
            />
            <StatCard
              label={data.isDemo ? '1-day demo forecast' : '1-day LSTM forecast'}
              value={data.forecastStatus?.oneDayLstmForecastAvailable ? 'Available' : 'Unavailable'}
              tone={data.forecastStatus?.oneDayLstmForecastAvailable ? 'emerald' : 'neutral'}
              icon={<Activity className="h-4 w-4" />}
              hint={
                data.isDemo
                  ? 'illustrative demo forecast'
                  : data.forecastStatus?.futureWeather?.future_weather_available
                    ? 'future weather configured'
                    : 'future weather not provided'
              }
            />
          </div>
        </div>
      </section>

      {/* DAILY FORECAST CENTREPIECE */}
      <section className="space-y-4">
        <SectionTitle
          eyebrow="Daily Forecasting"
          title="Forecast Centrepiece"
          description={
            data.isDemo
              ? 'Representative solar plant with an illustrative one-day demo forecast. Target DailyGeneration_MU, unit MU/day.'
              : 'Representative solar plant with a one-day LSTM forecast. Target DailyGeneration_MU, unit MU/day.'
          }
          badge="MU/DAY"
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate('/forecast')}>
              Full forecast <ArrowUpRight className="h-3.5 w-3.5" />
            </Button>
          }
        />
        <div className="grid gap-5 xl:grid-cols-3">
          <div className="xl:col-span-2">
            {repForecast.loading ? (
              <LoadingState variant="chart" />
            ) : repForecast.error ? (
              <ErrorState
                compact
                onRetry={repForecast.refetch}
                message={repForecast.error.userMessage || repForecast.error.message}
              />
            ) : repForecast.data?.status === 'ok' ? (
              <ForecastTimeline forecast={repForecast.data} />
            ) : (
              <ForecastCard forecast={repForecast.data} title="Representative 1-day forecast" />
            )}
          </div>

          <div className="space-y-5">
            <Card padded accent="brand">
              <div className="flex items-center justify-between">
                <div>
                  <p className="eyebrow">Representative asset</p>
                  <p className="mt-0.5 font-display text-sm font-bold text-white">
                    {repForecast.data?.plant?.name ?? representative?.name ?? 'Loading…'}
                  </p>
                </div>
                {(repForecast.data?.plant?.type ?? representative?.type) ? (
                  <PlantTypeBadge type={repForecast.data?.plant?.type ?? representative?.type} size="sm" />
                ) : null}
              </div>

              {repForecast.data?.status === 'ok' ? (
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <MetricBit
                    icon={<Zap className="h-3.5 w-3.5" />}
                    label="Next day"
                    value={formatMU(repForecast.data.points[0]?.prediction, 2)}
                  />
                  <MetricBit
                    icon={<Target className="h-3.5 w-3.5" />}
                    label="Horizon total"
                    value={formatMU(repForecast.data.summary?.totalMU, 2)}
                  />
                  <MetricBit
                    icon={<CalendarDays className="h-3.5 w-3.5" />}
                    label="Forecast date"
                    value={
                      repForecast.data.points[0]?.date
                        ? formatDate(repForecast.data.points[0].date)
                        : '—'
                    }
                  />
                  <MetricBit
                    icon={<Gauge className="h-3.5 w-3.5" />}
                    label="Confidence"
                    value="Not calibrated"
                  />
                </div>
              ) : (
                <p className="mt-4 rounded-lg border border-solar-400/25 bg-solar-400/[0.06] p-3 text-[11px] leading-relaxed text-graphite-300">
                  {repForecast.data?.status === 'weather_required'
                    ? 'The representative one-day forecast is unavailable because future weather inputs are not provided.'
                    : repForecast.data?.status === 'insufficient_history'
                      ? 'The representative plant does not have enough history for a one-day LSTM forecast.'
                      : 'No representative forecast is available.'}
                </p>
              )}

              <p className="mt-3 text-[10px] leading-relaxed text-graphite-500">
                Daily model output only. The API does not publish hourly values, confidence intervals, or instantaneous
                MW.
              </p>
            </Card>

            <InsightPanel insight={data.insight} />
          </div>
        </div>
      </section>

      {/* FLEET DAILY GENERATION + MIX */}
      <section className="grid gap-5 xl:grid-cols-3">
        <ChartCard
          title="Fleet Daily Generation"
          subtitle={`Observed daily generation by source (MU/day) · trailing ${daily.length} days`}
          icon={<Activity className="h-4 w-4" />}
          accent="brand"
          height={300}
          className="xl:col-span-2"
          actions={
            <div className="flex items-center gap-3">
              <Badge tone="solar" size="sm">
                solar
              </Badge>
              <Badge tone="wind" size="sm">
                wind
              </Badge>
            </div>
          }
          footer={
            <ChartLegend
              items={[
                { key: 'solar', label: 'Solar (MU/day)', color: PALETTE.solar },
                { key: 'wind', label: 'Wind (MU/day)', color: PALETTE.wind },
                { key: 'total', label: 'Fleet total (MU/day)', color: PALETTE.brand },
              ]}
            />
          }
        >
          {daily.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={daily} margin={{ top: 8, right: 10, bottom: 0, left: -12 }}>
                <CartesianGrid {...GRID_PROPS} />
                <XAxis dataKey="date" tickFormatter={formatDateShort} minTickGap={26} {...AXIS_PROPS} />
                <YAxis {...AXIS_PROPS} width={48} />
                <Tooltip
                  content={
                    <ChartTooltip
                      units={{ solar: ' MU/day', wind: ' MU/day', total: ' MU/day' }}
                      digits={2}
                      labelFormatter={(value) => formatDate(value)}
                    />
                  }
                />
                <Area
                  type="monotone"
                  dataKey="solar"
                  name="Solar"
                  stackId="gen"
                  stroke={PALETTE.solar}
                  fill={PALETTE.solar}
                  fillOpacity={0.18}
                  strokeWidth={1.6}
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="wind"
                  name="Wind"
                  stackId="gen"
                  stroke={PALETTE.wind}
                  fill={PALETTE.wind}
                  fillOpacity={0.18}
                  strokeWidth={1.6}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="total"
                  name="Fleet total"
                  stroke={PALETTE.brand}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-graphite-400">
              No daily generation rows returned for the selected window.
            </div>
          )}
        </ChartCard>

        <ChartCard
          title="Renewable Capacity Mix"
          subtitle="Installed capacity by source (MW)"
          icon={<Leaf className="h-4 w-4" />}
          accent="solar"
          height={300}
          footer={
            <div className="space-y-1.5">
              {data.mix.map((m) => (
                <div key={m.name} className="flex items-center justify-between text-[11px]">
                  <span className="flex items-center gap-2 text-graphite-300">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: MIX_COLORS[m.name] }} />
                    {m.name}
                  </span>
                  <span className="font-mono text-graphite-100">
                    {formatPower(m.value, 0)} · {formatNumber((m.value / mixTotal) * 100, 0)}%
                  </span>
                </div>
              ))}
            </div>
          }
        >
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip content={<ChartTooltip units={{ value: ' MW' }} />} />
              <Pie
                data={data.mix}
                dataKey="value"
                nameKey="name"
                innerRadius="58%"
                outerRadius="86%"
                paddingAngle={3}
                stroke="none"
              >
                {data.mix.map((m) => (
                  <Cell key={m.name} fill={MIX_COLORS[m.name]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </section>

      {/* WEATHER → ENERGY */}
      <section className="grid gap-5 xl:grid-cols-3">
        <div className="xl:col-span-2">
          {data.latestWeather ? (
            <WeatherEnergyLink weather={data.latestWeather} />
          ) : (
            <Card padded>
              <p className="flex items-center gap-1.5 eyebrow">
                <CloudSun className="h-3 w-3 text-solar-300" /> Weather → energy model inputs
              </p>
              <p className="mt-2 text-xs leading-relaxed text-graphite-400">
                No observed fleet weather context was returned on the latest reporting date.
              </p>
            </Card>
          )}
        </div>
        <div className="space-y-4">
          {data.latestWeather ? (
            <WeatherCard weather={data.latestWeather} />
          ) : (
            <Card padded>
              <p className="eyebrow">Observed weather</p>
              <p className="mt-2 text-xs text-graphite-400">No fleet weather context available.</p>
            </Card>
          )}
          <Card padded accent="solar">
            <p className="eyebrow">Future weather</p>
            <p className="mt-2 text-[11px] leading-relaxed text-graphite-300">
              {data.forecastStatus?.futureWeather?.future_weather_available
                ? 'A future-weather provider is configured; multi-day forecasts can be requested.'
                : 'Not provided. Multi-day forecasts return an honest unavailable state; historical weather is never reused as a forecast.'}
            </p>
          </Card>
        </div>
      </section>

      {/* DISTRICTS + PLANTS */}
      <section className="grid gap-5 xl:grid-cols-3">
        <ChartCard
          title="District Capacity Leaderboard"
          subtitle="Installed renewable capacity by district (MW)"
          icon={<MapPinned className="h-4 w-4" />}
          accent="wind"
          height={320}
          className="xl:col-span-2"
        >
          {topDistricts.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topDistricts} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 24 }}>
                <CartesianGrid {...GRID_PROPS} horizontal={false} />
                <XAxis type="number" {...AXIS_PROPS} />
                <YAxis type="category" dataKey="district" width={110} {...AXIS_PROPS} />
                <Tooltip
                  cursor={{ fill: 'rgba(148,163,184,0.06)' }}
                  content={<ChartTooltip units={{ capacity: ' MW' }} />}
                />
                <Bar dataKey="capacity" radius={[0, 4, 4, 0]} isAnimationActive>
                  {topDistricts.map((d, i) => (
                    <Cell key={d.district} fill={i % 2 === 0 ? PALETTE.brand : PALETTE.wind} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-graphite-400">
              No district metadata returned by the API.
            </div>
          )}
        </ChartCard>

        <Card padded={false} className="xl:col-span-1">
          <div className="flex items-center justify-between border-b border-graphite-700/70 px-4 py-3.5">
            <div>
              <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Largest Assets</h3>
              <p className="eyebrow">by installed capacity</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => navigate('/plants')}>
              All
            </Button>
          </div>
          <div className="divide-y divide-graphite-800/80">
            {plantRows.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => navigate(`/plants/${p.id}`)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.03]"
              >
                <PlantGlyph type={p.type} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-graphite-100">{p.name}</p>
                  <p className="truncate text-[11px] text-graphite-500">
                    {p.district || 'Karnataka'} · {p.id}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-xs font-bold text-white">{formatPower(p.capacityMW, 0)}</p>
                  <p className="font-mono text-[10px] text-graphite-500">{formatMU(p.latestGenerationMU, 2)}</p>
                </div>
              </button>
            ))}
          </div>
        </Card>
      </section>

      {latest ? (
        <p className="text-center font-mono text-[10px] text-graphite-500">
          Latest observed fleet day {formatDate(latest.date)} · {formatMU(latest.total)} ·{' '}
          {latest.reportingPlants ?? o.reportingPlants ?? '—'} reporting plants.{' '}
          {data.isDemo ? 'Source: demo data — illustrative only.' : 'Source: ENERVISION daily API.'}
        </p>
      ) : null}
    </div>
  )
}

function MiniStat({ label, value, tone = 'text-graphite-100' }) {
  return (
    <div className="px-4 py-3">
      <p className="eyebrow">{label}</p>
      <p className={`mt-1 font-display text-sm font-bold tabular-nums ${tone}`}>{value}</p>
    </div>
  )
}

function MetricBit({ icon, label, value }) {
  return (
    <div className="rounded-lg border border-graphite-700/70 bg-graphite-850/50 px-3 py-2">
      <p className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-wide text-graphite-500">
        <span className="text-brand-300">{icon}</span>
        {label}
      </p>
      <p className="mt-0.5 truncate font-mono text-[11px] font-bold tabular-nums text-graphite-100">{value}</p>
    </div>
  )
}
