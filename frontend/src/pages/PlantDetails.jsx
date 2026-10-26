import { useMemo } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Activity,
  ArrowLeft,
  Calendar,
  CloudSun,
  Compass,
  Factory,
  Gauge,
  Layers,
  LineChart as LineChartIcon,
  MapPin,
  MapPinned,
  RefreshCw,
  Sun,
  Target,
  Thermometer,
  Wind,
  Wrench,
  Zap,
} from 'lucide-react'

import { API_MODE, getForecast, getPlantById, getWeather, referenceData } from '../services/api.js'
import useAsync from '../hooks/useAsync.js'
import { cx, formatCoord, formatDate, formatDateShort, formatMU, formatNumber } from '../utils/format.js'
import { AXIS_PROPS, CHART_MARGIN, GRID_PROPS, PALETTE } from '../utils/constants.js'

import PageHeader from '../components/ui/PageHeader.jsx'
import Card from '../components/ui/Card.jsx'
import Button from '../components/ui/Button.jsx'
import Badge from '../components/ui/Badge.jsx'
import StatCard from '../components/ui/StatCard.jsx'
import ChartCard from '../components/ui/ChartCard.jsx'
import MetricCard from '../components/ui/MetricCard.jsx'
import DataTable from '../components/ui/DataTable.jsx'
import SectionTitle from '../components/ui/SectionTitle.jsx'
import LoadingState from '../components/ui/LoadingState.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import DemoNotice, { ASSET_DEMO_LABEL } from '../components/ui/DemoNotice.jsx'
import { ChartTooltip, ChartLegend } from '../components/charts/index.js'
import KarnatakaMap from '../components/domain/KarnatakaMap.jsx'
import WeatherCard from '../components/domain/WeatherCard.jsx'
import WeatherEnergyLink from '../components/domain/WeatherEnergyLink.jsx'
import ForecastCard from '../components/domain/ForecastCard.jsx'
import { PlantTypeBadge } from '../components/domain/PlantStatus.jsx'

export default function PlantDetails() {
  const { plantId } = useParams()
  const navigate = useNavigate()
  const { data, loading, error, refetch } = useAsync(() => getPlantById(plantId), [plantId])

  const forecastAsync = useAsync(
    () => (data?.id ? getForecast({ plantId: data.id, model: 'auto', horizon: 1 }) : Promise.resolve(null)),
    [data?.id],
  )
  const weatherAsync = useAsync(
    () => (data?.id ? getWeather({ plantId: data.id }) : Promise.resolve(null)),
    [data?.id],
  )

  const accent = data?.type === 'wind' ? 'wind' : 'solar'
  const accentColor = data?.type === 'wind' ? PALETTE.wind : PALETTE.solar

  const historyPoints = useMemo(() => {
    const points = data?.recentGeneration?.points ?? []
    return points.slice(-30)
  }, [data])

  const weatherPoints = useMemo(() => {
    const rows = weatherAsync.data?.data ?? []
    return rows.slice(-30)
  }, [weatherAsync.data])

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingState label="Loading plant…" />
        <LoadingState variant="cards" />
        <LoadingState variant="chart" />
        <LoadingState variant="table" />
      </div>
    )
  }

  if (error) {
    const notFound = error.status === 404
    return (
      <div className="mx-auto max-w-3xl space-y-5 py-4">
        <ErrorState
          title={notFound ? 'Plant not found' : 'Plant could not be loaded'}
          message={error.userMessage || error.message}
          onRetry={refetch}
        />
        <div className="flex justify-center">
          <Button as={Link} to="/plants" variant="secondary" size="md">
            <ArrowLeft className="h-4 w-4" /> Back to Plant Explorer
          </Button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-3xl space-y-5 py-4">
        <ErrorState
          title="Plant not found"
          message={`No plant with ID “${plantId}” exists in the ENERVISION registry.`}
        />
        <div className="flex justify-center">
          <Button as={Link} to="/plants" variant="primary" size="md">
            <ArrowLeft className="h-4 w-4" /> Back to Plant Explorer
          </Button>
        </div>
      </div>
    )
  }

  const capability = data.forecastCapability
  const futureWeather = capability?.future_weather
  const weatherCurrent = data.weatherContext
    ? {
        ...data.weatherContext,
        plantName: data.name,
        district: data.district,
        ghiUnit: 'kWh/m²/day',
      }
    : null
  const weatherCoverage = weatherAsync.data?.coverage
  const recentRows = [...(data.recentGeneration?.points ?? [])].reverse()

  const typeLabel = data.type === 'solar' ? 'Solar photovoltaic' : 'Wind'
  const description = `${typeLabel} asset in ${data.district || 'Karnataka'}${
    data.owner ? `, operated by ${data.owner}` : ''
  }. Installed capacity ${formatNumber(data.capacityMW, 0)} MW. Daily generation target DailyGeneration_MU (MU/day).`

  const infoRows = [
    { label: 'Plant ID', value: data.id, mono: true },
    { label: 'Renewable type', value: data.type === 'solar' ? 'Solar PV' : 'Wind' },
    { label: 'District', value: data.district || '—' },
    { label: 'State', value: data.state || 'Karnataka' },
    { label: 'Owner / operator', value: data.owner || '—' },
    { label: 'Installed capacity', value: data.capacityMW === null ? '—' : `${formatNumber(data.capacityMW, 0)} MW`, mono: true },
    { label: 'Commission date', value: data.commissionDate || '—', mono: true },
    { label: 'First observed', value: data.firstObserved ? formatDate(data.firstObserved) : '—', mono: true },
    { label: 'Last observed', value: data.lastObserved ? formatDate(data.lastObserved) : '—', mono: true },
    { label: 'Observed rows', value: formatNumber(data.observations, 0), mono: true },
    { label: 'Latitude', value: formatCoord(data.lat, 'lat'), mono: true },
    { label: 'Longitude', value: formatCoord(data.lng, 'lng'), mono: true },
  ]

  const recentColumns = [
    {
      key: 'date',
      header: 'Date',
      render: (r) => <span className="font-mono text-xs text-graphite-300">{formatDate(r.date)}</span>,
    },
    {
      key: 'generationMU',
      header: 'Daily generation',
      align: 'right',
      render: (r) => (
        <span className="font-mono text-xs font-semibold text-white">
          {formatNumber(r.generationMU, 2)} <span className="text-graphite-500">MU/day</span>
        </span>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Asset Detail"
        breadcrumb={[{ label: 'Plants', to: '/plants' }, { label: data.name }]}
        title={data.name}
        description={description}
        icon={<Factory className="h-5 w-5" />}
        badge={
          <div className="flex flex-wrap items-center gap-2">
            <PlantTypeBadge type={data.type} size="sm" />
            <Badge tone="neutral" size="sm" mono icon={<MapPin className="h-3 w-3" />}>
              {data.id}
            </Badge>
          </div>
        }
        meta={[
          { label: 'District', value: data.district || '—' },
          { label: 'Capacity', value: data.capacityMW === null ? '—' : `${formatNumber(data.capacityMW, 0)} MW` },
          { label: 'Last observed', value: data.lastObserved ? formatDate(data.lastObserved) : '—' },
          { label: 'Unit', value: 'MU/day' },
        ]}
        actions={
          <>
            <Button variant="secondary" size="md" onClick={() => navigate('/plants')}>
              <ArrowLeft className="h-4 w-4" /> All plants
            </Button>
            <Button variant="secondary" size="md" onClick={refetch}>
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            <Button variant="primary" size="md" onClick={() => navigate(`/forecast?plant=${data.id}`)}>
              <LineChartIcon className="h-4 w-4" /> Forecast this plant
            </Button>
          </>
        }
      />

      <DemoNotice label={ASSET_DEMO_LABEL}>
        In demo mode this asset is an illustrative record. With a live API, all registry fields, coordinates, daily
        generation and observed weather on this page come from the backend. No technical specifications are invented.
      </DemoNotice>

      {/* ------------------------------------------- Location + snapshot --- */}
      <section className="space-y-4 animate-fade-up">
        <SectionTitle
          eyebrow="Asset Overview"
          title="Observed Snapshot"
          description="Where the asset sits in the Karnataka network, alongside its latest observed daily generation."
          tone={accent}
        />

        <div className="grid gap-5 xl:grid-cols-3">
          <Card padded={false} className="overflow-hidden xl:col-span-1">
            <PanelHeader
              tone={accent}
              icon={<MapPinned className="h-4 w-4" />}
              title="Asset Location"
              subtitle="node size ∝ capacity"
              actions={<Badge tone={accent} size="sm">{data.hasCoordinates ? 'Mapped' : 'No coordinates'}</Badge>}
            />
            <div className="relative h-[340px] sm:h-[400px]">
              {data.hasCoordinates ? (
                <KarnatakaMap plants={[data]} selectedId={data.id} showLabels showNetwork={false} showLegend={false} />
              ) : (
                <div className="flex h-full items-center justify-center p-6 text-center">
                  <div>
                    <MapPin className="mx-auto h-6 w-6 text-graphite-500" />
                    <p className="mt-2 text-xs font-semibold text-graphite-300">Coordinates not available</p>
                    <p className="mt-1 text-[11px] text-graphite-500">
                      The backend does not publish coordinates for this plant.
                    </p>
                  </div>
                </div>
              )}
            </div>
            <div className="grid grid-cols-2 divide-x divide-graphite-700/70 border-t border-graphite-700/70">
              <div className="px-4 py-3">
                <p className="eyebrow">Latitude</p>
                <p className="mt-1 font-mono text-xs font-bold tabular-nums text-graphite-100">
                  {formatCoord(data.lat, 'lat')}
                </p>
              </div>
              <div className="px-4 py-3">
                <p className="eyebrow">Longitude</p>
                <p className="mt-1 font-mono text-xs font-bold tabular-nums text-graphite-100">
                  {formatCoord(data.lng, 'lng')}
                </p>
              </div>
            </div>
          </Card>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:col-span-2">
            <StatCard
              label="Installed capacity"
              value={data.capacityMW ?? null}
              unit="MW"
              icon={<Gauge className="h-4 w-4" />}
              tone="brand"
              hint={data.commissionDate ? `commissioned ${data.commissionDate}` : 'commission date unavailable'}
            />
            <StatCard
              label="Latest daily generation"
              value={data.latestGenerationMU ?? null}
              decimals={2}
              unit="MU/day"
              icon={<Zap className="h-4 w-4" />}
              tone={accent}
              hint={data.latestGenerationDate ? formatDate(data.latestGenerationDate) : 'no observed date'}
            />
            <StatCard
              label="Observed rows"
              value={data.observations ?? null}
              icon={<Activity className="h-4 w-4" />}
              tone="violet"
              hint={`${data.firstObserved ? formatDate(data.firstObserved) : '—'} → ${
                data.lastObserved ? formatDate(data.lastObserved) : '—'
              }`}
            />
            <StatCard
              label="1-day LSTM capability"
              value={capability?.lstm?.one_day_horizon_available ? 'Available' : 'Unavailable'}
              tone={capability?.lstm?.one_day_horizon_available ? 'emerald' : 'neutral'}
              icon={<Target className="h-4 w-4" />}
              hint={futureWeather?.future_weather_available ? 'future weather configured' : 'future weather unavailable'}
            />
          </div>
        </div>
      </section>

      {/* ------------------------------------------------- Plant profile --- */}
      <section className="space-y-4 animate-fade-up">
        <SectionTitle
          eyebrow="Asset Profile"
          title="Registry & Forecast Capability"
          description="Backend registry attributes and the honest daily forecast capability for this plant."
          tone="brand"
        />

        <div className="grid gap-5 xl:grid-cols-3">
          <Card padded className="animate-fade-up">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-400/10 text-brand-300 ring-1 ring-inset ring-brand-400/20">
                <Factory className="h-4 w-4" />
              </span>
              <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Plant Information</h3>
            </div>
            <div className="mt-3">
              {infoRows.map((row) => (
                <InfoRow key={row.label} label={row.label} value={row.value} mono={row.mono} />
              ))}
            </div>
          </Card>

          <Card padded className="animate-fade-up">
            <div className="flex items-center gap-2.5">
              <span
                className={cx(
                  'flex h-9 w-9 items-center justify-center rounded-lg ring-1 ring-inset',
                  accent === 'wind'
                    ? 'bg-wind-400/10 text-wind-300 ring-wind-400/20'
                    : 'bg-solar-400/10 text-solar-300 ring-solar-400/20',
                )}
              >
                {data.type === 'wind' ? <Wind className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
              </span>
              <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Forecast Capability</h3>
            </div>
            <div className="mt-3.5 grid gap-3 sm:grid-cols-2">
              <MetricCard
                label="Frequency"
                value={capability?.frequency || 'daily'}
                icon={<Calendar className="h-4 w-4" />}
                tone="brand"
              />
              <MetricCard
                label="Unit"
                value={capability?.unit || 'MU/day'}
                icon={<Gauge className="h-4 w-4" />}
                tone="violet"
              />
              <MetricCard
                label="Default horizon"
                value={`${capability?.horizon_default_days ?? 3} days`}
                icon={<Target className="h-4 w-4" />}
                tone="solar"
              />
              <MetricCard
                label="Max horizon"
                value={`${capability?.horizon_max_days ?? 7} days`}
                icon={<Calendar className="h-4 w-4" />}
                tone="wind"
              />
            </div>

            <div className="mt-4 space-y-2">
              <CapabilityRow
                label="Random Forest"
                available={capability?.random_forest?.available}
                reason={capability?.random_forest?.reason}
              />
              <CapabilityRow
                label="1-day LSTM"
                available={capability?.lstm?.one_day_horizon_available}
                reason={capability?.lstm?.reason}
              />
              <CapabilityRow
                label="Multi-day LSTM"
                available={capability?.lstm?.multi_day_horizon_available}
                reason={capability?.lstm?.multi_day_horizon_available ? null : 'Requires future weather inputs.'}
              />
            </div>

            <div className="mt-4 rounded-lg border border-graphite-700/70 bg-graphite-850/50 px-3 py-2.5">
              <p className="eyebrow">Future weather</p>
              <p className="mt-1 text-[11px] leading-relaxed text-graphite-300">
                {futureWeather?.future_weather_available
                  ? 'A future-weather provider is configured.'
                  : 'Not provided. Historical weather is never reused or truncated as a forecast.'}
              </p>
              <p className="mt-1 font-mono text-[10px] text-graphite-500">
                provider: {futureWeather?.provider || 'unavailable'}
              </p>
            </div>
          </Card>

          <Card padded className="animate-fade-up">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-400/10 text-violet-300 ring-1 ring-inset ring-violet-400/20">
                <Layers className="h-4 w-4" />
              </span>
              <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Data Coverage</h3>
            </div>
            <div className="mt-4 space-y-3">
              <StatRow label="Generation rows" value={formatNumber(data.observations, 0)} />
              <StatRow
                label="Generation range"
                value={`${data.firstObserved ? formatDate(data.firstObserved) : '—'} → ${
                  data.lastObserved ? formatDate(data.lastObserved) : '—'
                }`}
              />
              <StatRow label="Recent history rows" value={formatNumber(data.recentGeneration?.count, 0)} />
              <StatRow
                label="Observed weather rows"
                value={
                  weatherAsync.loading
                    ? 'Loading…'
                    : weatherAsync.error
                      ? 'Unavailable'
                      : formatNumber(weatherAsync.data?.count, 0)
                }
              />
              <StatRow
                label="Weather range"
                value={
                  weatherAsync.data?.availableRange
                    ? `${formatDate(weatherAsync.data.availableRange.start)} → ${formatDate(
                        weatherAsync.data.availableRange.end,
                      )}`
                    : '—'
                }
              />
              {weatherCoverage ? (
                <StatRow
                  label="Weather coverage"
                  value={`${weatherCoverage.returned_observations ?? '—'} / ${
                    weatherCoverage.requested_calendar_days ?? '—'
                  } days`}
                />
              ) : null}
            </div>
            <div className="mt-4 rounded-lg border border-graphite-700/70 bg-graphite-850/50 px-3 py-2.5">
              <p className="eyebrow">Latest observed weather context</p>
              <p className="mt-1 font-mono text-[11px] text-graphite-200">
                {weatherCurrent ? formatDate(weatherCurrent.date) : '—'}
              </p>
              <p className="mt-1 text-[10px] text-graphite-500">
                {weatherCurrent ? 'Observed historical weather on the last reporting date.' : 'Not available.'}
              </p>
            </div>
          </Card>
        </div>
      </section>

      {/* ------------------------------------------- Generation history --- */}
      <section className="space-y-4 animate-fade-up">
        <SectionTitle
          eyebrow="Observed Data"
          title="Daily Generation History"
          description="Observed daily generation in MU/day. No hourly values or interpolation are applied."
          tone={accent}
          badge="MU/day"
        />

        <div className="grid gap-5 xl:grid-cols-3">
          <ChartCard
            className="xl:col-span-2"
            title="Daily Generation"
            subtitle={`Observed daily generation (MU/day) · ${historyPoints.length} most recent rows`}
            icon={<Zap className="h-4 w-4" />}
            tone={accent}
            accent={accent}
            height={300}
            footer={<ChartLegend items={[{ key: 'generationMU', label: 'Observed (MU/day)', color: accentColor }]} />}
          >
            {historyPoints.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={historyPoints} margin={CHART_MARGIN}>
                  <defs>
                    <linearGradient id="plantDaily" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={accentColor} stopOpacity={0.34} />
                      <stop offset="100%" stopColor={accentColor} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis dataKey="date" tickFormatter={formatDateShort} minTickGap={26} {...AXIS_PROPS} />
                  <YAxis
                    width={52}
                    {...AXIS_PROPS}
                    label={{ value: 'MU/day', angle: -90, position: 'insideLeft', fill: PALETTE.tick, fontSize: 10 }}
                  />
                  <Tooltip
                    content={
                      <ChartTooltip
                        units={{ generationMU: ' MU/day' }}
                        digits={2}
                        labelFormatter={(value) => formatDate(value)}
                      />
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="generationMU"
                    name="Observed"
                    stroke={accentColor}
                    strokeWidth={2}
                    fill="url(#plantDaily)"
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-graphite-400">
                No recent daily generation rows were returned for this plant.
              </div>
            )}
          </ChartCard>

          <ChartCard
            title="Observed Weather"
            subtitle="Historical GHI, temperature and wind speed"
            icon={<Sun className="h-4 w-4" />}
            tone="solar"
            accent="solar"
            height={300}
            footer={
              <ChartLegend
                items={[
                  { key: 'ghi', label: 'GHI (kWh/m²/day)', color: PALETTE.solar },
                  { key: 'temperature', label: 'Temperature (°C)', color: PALETTE.danger },
                  { key: 'windSpeed', label: 'Wind (m/s)', color: PALETTE.wind },
                ]}
              />
            }
          >
            {weatherAsync.loading ? (
              <LoadingState variant="chart" className="border-0 bg-transparent" />
            ) : weatherAsync.error ? (
              <div className="flex h-full items-center justify-center p-4 text-center text-[11px] text-graphite-400">
                {weatherAsync.error.userMessage || weatherAsync.error.message}
              </div>
            ) : weatherPoints.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={weatherPoints} margin={CHART_MARGIN}>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis dataKey="date" tickFormatter={formatDateShort} minTickGap={24} {...AXIS_PROPS} />
                  <YAxis yAxisId="left" width={40} {...AXIS_PROPS} />
                  <YAxis yAxisId="right" orientation="right" width={36} {...AXIS_PROPS} />
                  <Tooltip
                    content={
                      <ChartTooltip
                        units={{ ghi: ' kWh/m²/day', temperature: ' °C', windSpeed: ' m/s' }}
                        digits={2}
                        labelFormatter={(value) => formatDate(value)}
                      />
                    }
                  />
                  <Area
                    yAxisId="left"
                    type="monotone"
                    dataKey="ghi"
                    name="GHI"
                    stroke={PALETTE.solar}
                    strokeWidth={1.8}
                    fill={PALETTE.solar}
                    fillOpacity={0.12}
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="temperature"
                    name="Temperature"
                    stroke={PALETTE.danger}
                    strokeWidth={1.6}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="windSpeed"
                    name="Wind speed"
                    stroke={PALETTE.wind}
                    strokeWidth={1.6}
                    dot={false}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-graphite-400">
                No observed weather rows were returned for this plant.
              </div>
            )}
          </ChartCard>
        </div>
      </section>

      {/* --------------------------------------------- Daily forecast --- */}
      <section className="space-y-4 animate-fade-up">
        <SectionTitle
          eyebrow="Daily Forecasting"
          title="Forecast Capability & Output"
          description={
            API_MODE === 'live'
              ? 'A one-day type-specific LSTM forecast. Longer horizons require future weather and will report an honest unavailable state.'
              : 'An illustrative one-day demo forecast. In live mode this card shows a type-specific LSTM forecast; longer horizons require future weather.'
          }
          tone="violet"
          badge="1 day"
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate(`/forecast?plant=${data.id}`)}>
              Open full forecast
              <LineChartIcon className="h-3.5 w-3.5" />
            </Button>
          }
        />

        <div className="grid gap-5 xl:grid-cols-3">
          <div className="xl:col-span-2">
            {forecastAsync.loading ? (
              <LoadingState variant="chart" />
            ) : forecastAsync.error ? (
              <ErrorState
                compact
                title="Forecast request failed"
                message={forecastAsync.error.userMessage || forecastAsync.error.message}
                onRetry={forecastAsync.refetch}
              />
            ) : (
              <ForecastCard
                forecast={forecastAsync.data}
                title={API_MODE === 'live' ? 'One-day LSTM forecast' : 'One-day demo forecast'}
                showPlant={false}
              />
            )}
          </div>

          <Card padded className="animate-fade-up">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-400/10 text-violet-300 ring-1 ring-inset ring-violet-400/20">
                <Target className="h-4 w-4" />
              </span>
              <div>
                <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Interpretation</h3>
                <p className="eyebrow">daily contract</p>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              <StatRow label="Target" value="DailyGeneration_MU" />
              <StatRow label="Unit" value="MU/day" />
              <StatRow label="Default horizon" value={`${capability?.horizon_default_days ?? 3} days`} />
              <StatRow label="Max horizon" value={`${capability?.horizon_max_days ?? 7} days`} />
              <StatRow label="Confidence" value="Not calibrated" />
            </div>
            <p className="mt-3 text-[10px] leading-relaxed text-graphite-500">
              The API returns confidence as null and provides a confidence note. No percentage, interval, hourly step or
              synthetic value is displayed here.
            </p>
          </Card>
        </div>
      </section>

      {/* --------------------------------------- Weather + signal chain --- */}
      <section className="space-y-4 animate-fade-up">
        <SectionTitle
          eyebrow="Weather Intelligence"
          title="Observed Weather & Model Inputs"
          description="Historical weather measured for this plant. Future weather is not available and is never simulated."
          tone="wind"
        />

        <div className="grid gap-5 xl:grid-cols-3">
          <div className="min-w-0 space-y-5">
            {weatherCurrent ? (
              <WeatherCard weather={weatherCurrent} variant="full" showOutlook />
            ) : (
              <Card padded>
                <p className="eyebrow">Observed weather</p>
                <p className="mt-2 text-xs text-graphite-400">No observed weather context was returned for this plant.</p>
              </Card>
            )}
            {weatherCurrent ? (
              <div className="grid grid-cols-2 gap-3">
                <MetricCard
                  label="GHI"
                  value={formatNumber(weatherCurrent.ghi, 2)}
                  unit="kWh/m²/day"
                  icon={<Sun className="h-4 w-4" />}
                  tone="solar"
                />
                <MetricCard
                  label="Temperature"
                  value={formatNumber(weatherCurrent.temperature, 1)}
                  unit="°C"
                  icon={<Thermometer className="h-4 w-4" />}
                  tone="rose"
                />
                <MetricCard
                  label="Humidity"
                  value={formatNumber(weatherCurrent.humidity, 0)}
                  unit="%"
                  icon={<Activity className="h-4 w-4" />}
                  tone="wind"
                />
                <MetricCard
                  label="Wind speed"
                  value={formatNumber(weatherCurrent.windSpeed, 1)}
                  unit="m/s"
                  icon={<Wind className="h-4 w-4" />}
                  tone="wind"
                />
              </div>
            ) : null}
          </div>

          <div className="min-w-0 space-y-5 xl:col-span-2">
            {weatherCurrent ? <WeatherEnergyLink weather={weatherCurrent} /> : null}
            <Card padded accent="solar">
              <p className="flex items-center gap-1.5 eyebrow">
                <CloudSun className="h-3 w-3 text-solar-300" /> Future weather availability
              </p>
              <p className="mt-2 text-[11px] leading-relaxed text-graphite-300">
                {futureWeather?.future_weather_available
                  ? 'A future-weather provider is configured for this deployment, so multi-day requests may be possible.'
                  : 'No future-weather provider is configured. Weather shown above is observed history, never a future forecast; multi-day forecasts therefore remain unavailable.'}
              </p>
              <p className="mt-2 font-mono text-[10px] text-graphite-500">
                provider: {futureWeather?.provider || 'unavailable'} · historical only
              </p>
            </Card>
          </div>
        </div>
      </section>

      {/* --------------------------------------------- Recent observations --- */}
      <section className="space-y-4 animate-fade-up">
        <SectionTitle
          eyebrow="Observed Data"
          title="Recent Daily Observations"
          description="Latest observed plant-day generation values in MU/day."
          tone="brand"
          badge={`${recentRows.length} rows`}
        />
        <Card padded={false} className="overflow-hidden">
          <PanelHeader
            tone="brand"
            icon={<Activity className="h-4 w-4" />}
            title="Observation Log"
            subtitle="date · daily generation"
            actions={<Badge tone="neutral" size="sm">{recentRows.length} rows</Badge>}
          />
          <div className="p-3">
            <DataTable
              columns={recentColumns}
              rows={recentRows}
              keyField="date"
              dense
              emptyTitle="No observations available"
              emptyDescription="The API returned no recent daily readings for this plant."
            />
          </div>
        </Card>
      </section>

      {/* ------------------------------------------------- Data provenance --- */}
      <Card padded className="animate-fade-up">
        <div className="flex flex-wrap items-center gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/5 text-graphite-300 ring-1 ring-inset ring-white/10">
            <Layers className="h-4 w-4" />
          </span>
          <div className="min-w-[220px] flex-1">
            <h3 className="font-display text-sm font-bold text-white">Data provenance</h3>
            <p className="mt-0.5 text-xs leading-relaxed text-graphite-400">
              Daily generation and plant registry values are served by the ENERVISION API. Observed weather is historical
              data for the plant coordinates ({formatCoord(data.lat, 'lat')}, {formatCoord(data.lng, 'lng')}); it is not a
              future forecast.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {referenceData.dataSources.map((s) => (
              <Badge key={s.id} tone="neutral" size="sm" icon={<Calendar className="h-3 w-3" />}>
                {s.name}
              </Badge>
            ))}
            <Badge tone="brand" size="sm" icon={<Wrench className="h-3 w-3" />}>
              Daily contract · MU/day
            </Badge>
          </div>
        </div>
      </Card>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Small presentational helpers                                              */
/* -------------------------------------------------------------------------- */

function InfoRow({ label, value, mono = false }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-graphite-800/80 py-2.5 last:border-0">
      <span className="eyebrow">{label}</span>
      <span className={cx('text-right text-[13px] font-semibold text-graphite-100', mono && 'font-mono tabular-nums')}>
        {value}
      </span>
    </div>
  )
}

function PanelHeader({ icon, title, subtitle, tone = 'brand', actions }) {
  const chip = {
    brand: 'border-brand-400/25 bg-brand-400/10 text-brand-300',
    solar: 'border-solar-400/25 bg-solar-400/10 text-solar-300',
    wind: 'border-wind-400/25 bg-wind-400/10 text-wind-300',
    violet: 'border-violet-400/25 bg-violet-400/10 text-violet-300',
  }[tone]
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-graphite-700/70 px-4 py-3.5">
      <div className="flex items-center gap-2.5">
        <span className={cx('flex h-8 w-8 items-center justify-center rounded-lg border', chip)}>{icon}</span>
        <div>
          <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">{title}</h3>
          {subtitle ? <p className="eyebrow">{subtitle}</p> : null}
        </div>
      </div>
      {actions}
    </div>
  )
}

function StatRow({ label, value, tone = 'text-graphite-100' }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-graphite-700/70 bg-graphite-850/50 px-3 py-2.5">
      <span className="eyebrow">{label}</span>
      <span className={cx('truncate text-right font-mono text-[13px] font-bold tabular-nums', tone)}>{value}</span>
    </div>
  )
}

function CapabilityRow({ label, available, reason }) {
  return (
    <div className="rounded-lg border border-graphite-700/70 bg-graphite-850/50 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold text-graphite-200">{label}</span>
        <Badge tone={available ? 'success' : 'neutral'} size="sm">
          {available ? 'available' : 'unavailable'}
        </Badge>
      </div>
      {reason ? <p className="mt-1 text-[10px] leading-relaxed text-graphite-500">{reason}</p> : null}
    </div>
  )
}
