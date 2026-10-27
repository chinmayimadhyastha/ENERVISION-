import { useMemo, useState } from 'react'
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
  BarChart3,
  BatteryCharging,
  CalendarDays,
  Gauge,
  Layers,
  RefreshCw,
  Sun,
  Target,
  TrendingUp,
  Wind,
  Zap,
} from 'lucide-react'

import { getAnalytics } from '../services/api.js'
import useAsync from '../hooks/useAsync.js'
import { formatDate, formatDateShort, formatMU, formatNumber, formatPercent, formatPower } from '../utils/format.js'
import { ANALYTICS_PERIODS, AXIS_PROPS, CHART_MARGIN, GRID_PROPS, PALETTE } from '../utils/constants.js'

import PageHeader from '../components/ui/PageHeader.jsx'
import Card from '../components/ui/Card.jsx'
import Button from '../components/ui/Button.jsx'
import Badge from '../components/ui/Badge.jsx'
import StatCard from '../components/ui/StatCard.jsx'
import ChartCard from '../components/ui/ChartCard.jsx'
import SectionTitle from '../components/ui/SectionTitle.jsx'
import SegmentedControl from '../components/ui/SegmentedControl.jsx'
import LoadingState from '../components/ui/LoadingState.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import DemoNotice, { RESEARCH_DEMO_LABEL } from '../components/ui/DemoNotice.jsx'
import DataTable from '../components/ui/DataTable.jsx'
import { ChartTooltip, ChartLegend } from '../components/charts/index.js'
import { PlantTypeBadge } from '../components/domain/PlantStatus.jsx'

const TYPE_COLORS = { solar: PALETTE.solar, wind: PALETTE.wind }

/** Descriptive daily analytics from /api/analytics — no hourly data or derived
 *  capacity-factor claims. The backend ratio generation_per_mw_per_day is
 *  presented only as the descriptive ratio the API defines. */
export default function Analytics() {
  const [period, setPeriod] = useState('30d')
  const [activeKeys, setActiveKeys] = useState(['solar', 'wind'])

  const { data, loading, error, refetch } = useAsync(() => getAnalytics({ period }), [period])

  const daily = useMemo(() => data?.daily ?? [], [data])
  const plants = useMemo(
    () => [...(data?.plants ?? [])].sort((a, b) => (b.meanDailyMU || 0) - (a.meanDailyMU || 0)),
    [data],
  )
  const byType = data?.byType ?? []
  const summary = data?.summary ?? null
  const coverage = data?.coverage ?? null
  const requestedRange = data?.requestedRange ?? null

  const peakDay = useMemo(
    () => daily.reduce((best, row) => ((row.total || 0) > (best?.total ?? -Infinity) ? row : best), null),
    [daily],
  )
  const troughDay = useMemo(
    () => daily.reduce((worst, row) => ((row.total || 0) < (worst?.total ?? Infinity) ? row : worst), null),
    [daily],
  )

  const topPlants = useMemo(() => plants.slice(0, 14), [plants])

  const typeRows = useMemo(
    () =>
      byType.map((t) => {
        const key = String(t.type || '').toLowerCase()
        return {
          key,
          label: t.type || '—',
          color: TYPE_COLORS[key] || PALETTE.brand,
          totalGenerationMU: t.total_generation_mu ?? null,
          meanDailyMU: t.mean_daily_generation_mu ?? null,
          observations: t.observations ?? null,
          days: t.days ?? null,
          plantCount: t.plant_count ?? null,
          capacityMW: t.capacity_mw ?? null,
        }
      }),
    [byType],
  )

  const toggleKey = (key) => {
    setActiveKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  const plantColumns = useMemo(
    () => [
      {
        key: 'name',
        header: 'Plant',
        render: (r) => (
          <div className="min-w-0">
            <p className="truncate text-[12px] font-semibold text-graphite-100">{r.name}</p>
            <p className="truncate font-mono text-[10px] text-graphite-500">{r.id}</p>
          </div>
        ),
      },
      { key: 'type', header: 'Type', render: (r) => <PlantTypeBadge type={r.type} size="sm" /> },
      {
        key: 'district',
        header: 'District',
        render: (r) => <span className="text-[11px] text-graphite-300">{r.district || '—'}</span>,
      },
      {
        key: 'capacityMW',
        header: 'Capacity',
        align: 'right',
        render: (r) => (
          <span className="font-mono text-[11px] text-graphite-200">
            {r.capacityMW === null || r.capacityMW === undefined ? '—' : formatPower(r.capacityMW, 0)}
          </span>
        ),
      },
      {
        key: 'meanDailyMU',
        header: 'Mean / day',
        align: 'right',
        render: (r) => <span className="font-mono text-[11px] font-semibold text-graphite-100">{formatMU(r.meanDailyMU, 2)}</span>,
      },
      {
        key: 'totalGenerationMU',
        header: 'Period total',
        align: 'right',
        render: (r) => (
          <span className="font-mono text-[11px] text-graphite-300">
            {r.totalGenerationMU === null || r.totalGenerationMU === undefined
              ? '—'
              : `${formatNumber(r.totalGenerationMU, 2)} MU`}
          </span>
        ),
      },
      {
        key: 'observations',
        header: 'Rows',
        align: 'right',
        render: (r) => <span className="font-mono text-[11px] text-graphite-400">{formatNumber(r.observations, 0)}</span>,
      },
      {
        key: 'lastObserved',
        header: 'Last observed',
        align: 'right',
        render: (r) => (
          <span className="font-mono text-[11px] text-graphite-400">
            {r.lastObserved ? formatDate(r.lastObserved) : '—'}
          </span>
        ),
      },
    ],
    [],
  )

  const headerMeta = data
    ? [
        {
          label: 'Range',
          value: requestedRange?.start
            ? `${formatDate(requestedRange.start)} → ${formatDate(requestedRange.end)}`
            : '—',
        },
        { label: 'Unit', value: data.unit || 'MU/day' },
        { label: 'Observed days', value: formatNumber(summary?.days, 0) },
        { label: 'Plants', value: formatNumber(summary?.plants, 0) },
      ]
    : undefined

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Analytics Lab"
        title="Generation Analytics"
        description="Descriptive daily analytics for the monitored Karnataka renewable fleet — observed generation by date, source and plant, with explicit data coverage. DailyGeneration_MU, MU/day."
        badge={
          <Badge tone="brand" size="sm" dot>
            {period}
          </Badge>
        }
        icon={<BarChart3 className="h-5 w-5" />}
        meta={headerMeta}
        actions={
          <>
            <SegmentedControl
              ariaLabel="Analysis period"
              value={period}
              onChange={setPeriod}
              options={ANALYTICS_PERIODS.map((p) => ({ value: p.value, label: p.label }))}
            />
            <Button variant="secondary" size="md" onClick={refetch}>
              <RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
              Refresh
            </Button>
          </>
        }
      />

      <DemoNotice label={RESEARCH_DEMO_LABEL} tone="sky">
        In demo mode these daily aggregates are illustrative. With <code className="font-mono">VITE_API_BASE_URL</code>{' '}
        configured, every figure comes from <code className="font-mono">/api/analytics</code> for the selected date range;
        empty periods return zeros rather than invented values.
      </DemoNotice>

      {loading ? (
        <div className="space-y-6">
          <LoadingState variant="cards" />
          <LoadingState variant="chart" />
          <LoadingState variant="chart" />
        </div>
      ) : error ? (
        <ErrorState
          title="Analytics unavailable"
          message={error.userMessage || error.message}
          onRetry={refetch}
        />
      ) : !data ? (
        <ErrorState title="No analytics returned" message="The API returned no analytics payload for this range." />
      ) : (
        <>
          {/* ------------------------------------------------------- KPIs --- */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
            <StatCard
              label="Period generation"
              value={summary?.totalGenerationMU ?? null}
              decimals={2}
              unit="MU"
              icon={<Zap className="h-4 w-4" />}
              tone="brand"
              hint={`${formatNumber(summary?.days, 0)} observed days`}
            />
            <StatCard
              label="Mean daily generation"
              value={summary?.meanDailyMU ?? null}
              decimals={2}
              unit="MU/day"
              icon={<Activity className="h-4 w-4" />}
              tone="solar"
              spark={daily.map((d) => ({ value: d.total }))}
            />
            <StatCard
              label="Peak day"
              value={summary?.maxDailyMU ?? null}
              decimals={2}
              unit="MU/day"
              icon={<TrendingUp className="h-4 w-4" />}
              tone="violet"
              hint={peakDay ? formatDate(peakDay.date) : '—'}
            />
            <StatCard
              label="Lowest day"
              value={summary?.minDailyMU ?? null}
              decimals={2}
              unit="MU/day"
              icon={<Target className="h-4 w-4" />}
              tone="wind"
              hint={troughDay ? formatDate(troughDay.date) : '—'}
            />
            <StatCard
              label="Installed capacity"
              value={data.totalCapacityMW ? data.totalCapacityMW / 1000 : null}
              decimals={2}
              unit="GW"
              icon={<BatteryCharging className="h-4 w-4" />}
              tone="neutral"
              hint={`${formatNumber(summary?.plants, 0)} plants`}
            />
            <StatCard
              label="Date coverage"
              value={
                coverage?.calendar_days
                  ? (Number(coverage.dates_observed) / Number(coverage.calendar_days)) * 100
                  : null
              }
              decimals={0}
              unit="%"
              icon={<CalendarDays className="h-4 w-4" />}
              tone="emerald"
              progress={
                coverage?.calendar_days
                  ? (Number(coverage.dates_observed) / Number(coverage.calendar_days)) * 100
                  : 0
              }
              hint={
                coverage
                  ? `${coverage.dates_observed ?? '—'}/${coverage.calendar_days ?? '—'} days observed`
                  : 'coverage unavailable'
              }
            />
          </div>

          {!daily.length ? (
            <Card padded>
              <p className="flex items-center gap-1.5 eyebrow">
                <CalendarDays className="h-3 w-3 text-solar-300" /> No observations in this range
              </p>
              <p className="mt-2 text-xs leading-relaxed text-graphite-400">
                The API returned an empty daily series for {period}. Nothing has been generated or interpolated to fill
                the gap.
              </p>
            </Card>
          ) : (
            <>
              {/* ------------------------------------------------ Trends --- */}
              <SectionTitle
                eyebrow="Temporal"
                title="Daily Generation Trend"
                description={`Fleet generation by source across ${daily.length} observed days. All values are MU/day.`}
                badge={period}
                actions={
                  <ChartLegend
                    items={[
                      { key: 'solar', label: 'Solar', color: PALETTE.solar },
                      { key: 'wind', label: 'Wind', color: PALETTE.wind },
                    ]}
                    activeKeys={activeKeys}
                    onClick={toggleKey}
                  />
                }
              />

              <div className="grid gap-5 xl:grid-cols-3">
                <ChartCard
                  className="xl:col-span-2"
                  title="Fleet Daily Generation"
                  subtitle="Stacked solar and wind generation with the fleet total"
                  icon={<TrendingUp className="h-4 w-4" />}
                  accent="brand"
                  height={330}
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
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={daily} margin={CHART_MARGIN}>
                      <defs>
                        <linearGradient id="anSolar" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={PALETTE.solar} stopOpacity={0.45} />
                          <stop offset="100%" stopColor={PALETTE.solar} stopOpacity={0.06} />
                        </linearGradient>
                        <linearGradient id="anWind" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={PALETTE.wind} stopOpacity={0.45} />
                          <stop offset="100%" stopColor={PALETTE.wind} stopOpacity={0.06} />
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
                            units={{ solar: ' MU/day', wind: ' MU/day', total: ' MU/day' }}
                            digits={2}
                            labelFormatter={(value) => formatDate(value)}
                          />
                        }
                      />
                      {activeKeys.includes('solar') ? (
                        <Area
                          type="monotone"
                          dataKey="solar"
                          name="Solar"
                          stackId="gen"
                          stroke={PALETTE.solar}
                          strokeWidth={1.6}
                          fill="url(#anSolar)"
                          isAnimationActive={false}
                        />
                      ) : null}
                      {activeKeys.includes('wind') ? (
                        <Area
                          type="monotone"
                          dataKey="wind"
                          name="Wind"
                          stackId="gen"
                          stroke={PALETTE.wind}
                          strokeWidth={1.6}
                          fill="url(#anWind)"
                          isAnimationActive={false}
                        />
                      ) : null}
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
                </ChartCard>

                <ChartCard
                  title="Source Contribution"
                  subtitle="Observed generation share for the selected range (MU)"
                  icon={<Sun className="h-4 w-4" />}
                  accent="solar"
                  height={330}
                  footer={
                    <div className="space-y-1.5">
                      <LegendRow
                        label="Solar"
                        value={`${formatNumber(summary?.solarGenerationMU, 2)} MU`}
                        percent={summary?.solarSharePct}
                        color={PALETTE.solar}
                      />
                      <LegendRow
                        label="Wind"
                        value={`${formatNumber(summary?.windGenerationMU, 2)} MU`}
                        percent={summary?.windSharePct}
                        color={PALETTE.wind}
                      />
                      <p className="pt-1 font-mono text-[10px] text-graphite-500">
                        Shares of observed daily generation, not installed capacity.
                      </p>
                    </div>
                  }
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { name: 'Solar', value: summary?.solarGenerationMU || 0, color: PALETTE.solar },
                          { name: 'Wind', value: summary?.windGenerationMU || 0, color: PALETTE.wind },
                        ]}
                        dataKey="value"
                        nameKey="name"
                        innerRadius="56%"
                        outerRadius="88%"
                        paddingAngle={3}
                        strokeWidth={0}
                      >
                        <Cell fill={PALETTE.solar} />
                        <Cell fill={PALETTE.wind} />
                      </Pie>
                      <Tooltip
                        content={
                          <ChartTooltip
                            units={{ value: ' MU' }}
                            digits={2}
                            valueFormatter={(v) => formatNumber(v, 2)}
                          />
                        }
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </ChartCard>
              </div>

              {/* ------------------------------------------ Coverage + types --- */}
              <div className="grid gap-5 xl:grid-cols-3">
                <ChartCard
                  className="xl:col-span-1"
                  title="Reporting Plants per Day"
                  subtitle="Plants with an observed record on each date"
                  icon={<Gauge className="h-4 w-4" />}
                  accent="violet"
                  height={280}
                  footer={<ChartLegend items={[{ key: 'reportingPlants', label: 'Reporting plants', color: PALETTE.forecast }]} />}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={daily} margin={CHART_MARGIN}>
                      <CartesianGrid {...GRID_PROPS} />
                      <XAxis dataKey="date" tickFormatter={formatDateShort} minTickGap={22} {...AXIS_PROPS} />
                      <YAxis width={38} allowDecimals={false} {...AXIS_PROPS} />
                      <Tooltip
                        cursor={{ fill: 'rgba(148,163,184,0.06)' }}
                        content={
                          <ChartTooltip
                            units={{ reportingPlants: ' plants' }}
                            digits={0}
                            labelFormatter={(value) => formatDate(value)}
                          />
                        }
                      />
                      <Bar dataKey="reportingPlants" name="Reporting plants" fill={PALETTE.forecast} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>

                <Card padded className="xl:col-span-2">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-400/10 text-brand-300 ring-1 ring-inset ring-brand-400/20">
                      <Layers className="h-4 w-4" />
                    </span>
                    <div>
                      <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Source Summary</h3>
                      <p className="eyebrow">by renewable type · MU/day means</p>
                    </div>
                  </div>

                  {typeRows.length ? (
                    <div className="mt-4 space-y-2.5">
                      {typeRows.map((t) => (
                        <div
                          key={t.key}
                          className="grid grid-cols-[minmax(0,1.1fr)_repeat(3,minmax(0,1fr))] items-center gap-3 rounded-lg border border-graphite-700/70 bg-graphite-850/50 px-3 py-2.5"
                        >
                          <span className="flex items-center gap-2">
                            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: t.color }} />
                            <span className="text-[12px] font-semibold text-graphite-100">{t.label}</span>
                          </span>
                          <TypeStat label="Mean / day" value={formatMU(t.meanDailyMU, 2)} />
                          <TypeStat label="Period total" value={`${formatNumber(t.totalGenerationMU, 2)} MU`} />
                          <TypeStat
                            label="Plants · capacity"
                            value={`${formatNumber(t.plantCount, 0)} · ${formatPower(t.capacityMW, 0)}`}
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-xs text-graphite-400">
                      No per-type breakdown is available for this scope.
                    </p>
                  )}

                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    <CoverageBit label="Requested range" value={requestedRange ? `${formatDate(requestedRange.start)} → ${formatDate(requestedRange.end)}` : '—'} />
                    <CoverageBit
                      label="Observed dates"
                      value={coverage ? `${coverage.dates_observed ?? '—'} / ${coverage.calendar_days ?? '—'} days` : '—'}
                    />
                    <CoverageBit
                      label="Plant-day rows"
                      value={formatNumber(coverage?.plant_day_observations, 0)}
                    />
                  </div>
                  {coverage?.missing_calendar_days ? (
                    <p className="mt-2 font-mono text-[10px] text-solar-300">
                      {coverage.missing_calendar_days} calendar day(s) without observations — shown as gaps, never
                      interpolated.
                    </p>
                  ) : null}
                </Card>
              </div>

              {/* ------------------------------------------ Plant comparison --- */}
              <SectionTitle
                eyebrow="Assets"
                title="Plant Comparison"
                description="Observed daily generation by plant for the selected range. Capacity is installed MW; it is not a generation metric."
                badge={`${plants.length} plants`}
              />

              <ChartCard
                title="Mean Daily Generation by Plant"
                subtitle="Top plants by mean observed MU/day, coloured by renewable type"
                icon={<BarChart3 className="h-4 w-4" />}
                accent="wind"
                height={360}
                footer={
                  <ChartLegend
                    items={[
                      { key: 'solar', label: 'Solar', color: PALETTE.solar },
                      { key: 'wind', label: 'Wind', color: PALETTE.wind },
                    ]}
                  />
                }
              >
                {topPlants.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={topPlants} layout="vertical" margin={{ top: 4, right: 22, bottom: 0, left: 30 }}>
                      <CartesianGrid {...GRID_PROPS} horizontal={false} />
                      <XAxis type="number" {...AXIS_PROPS} tickFormatter={(v) => formatNumber(v, 1)} />
                      <YAxis type="category" dataKey="name" width={170} {...AXIS_PROPS} />
                      <Tooltip
                        cursor={{ fill: 'rgba(148,163,184,0.06)' }}
                        content={
                          <ChartTooltip
                            units={{ meanDailyMU: ' MU/day', totalGenerationMU: ' MU' }}
                            digits={2}
                          />
                        }
                      />
                      <Bar dataKey="meanDailyMU" name="Mean / day" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                        {topPlants.map((p) => (
                          <Cell key={p.id} fill={TYPE_COLORS[p.type] || PALETTE.brand} fillOpacity={0.85} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-graphite-400">
                    No plant-level generation rows returned for this range.
                  </div>
                )}
              </ChartCard>

              <Card padded={false}>
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-graphite-700/70 px-4 py-3.5">
                  <div>
                    <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Plant Daily Register</h3>
                    <p className="eyebrow">descriptive aggregates · MU/day</p>
                  </div>
                  <span className="font-mono text-[11px] text-graphite-400">{plants.length} plants</span>
                </div>
                <div className="p-3">
                  <DataTable
                    columns={plantColumns}
                    rows={plants}
                    keyField="id"
                    emptyTitle="No plants in this range"
                    emptyDescription="The API returned no plant-level observations for the selected dates."
                    maxHeight={520}
                  />
                </div>
              </Card>

              {/* ------------------------------------------------- Notes --- */}
              <Card padded accent="neutral">
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-graphite-700 bg-graphite-850 text-graphite-300">
                    <Layers className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <h3 className="font-display text-sm font-bold text-white">Method notes</h3>
                    <p className="mt-1 text-[11px] leading-relaxed text-graphite-400">
                      {data.derivedMetrics?.generation_per_mw_per_day ||
                        'Values are observed daily aggregates. No hourly interpolation, capacity-factor calculation or weather correlation is published by this endpoint.'}
                    </p>
                    {data.notes?.length ? (
                      <ul className="mt-2 space-y-1">
                        {data.notes.map((note) => (
                          <li key={note} className="text-[10px] leading-relaxed text-graphite-500">
                            {note}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </div>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Local helper components                                                   */
/* -------------------------------------------------------------------------- */

function LegendRow({ label, value, percent, color }) {
  return (
    <div className="flex items-center justify-between text-[11px]">
      <span className="flex items-center gap-2 text-graphite-300">
        <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
        {label}
      </span>
      <span className="font-mono text-graphite-100">
        {value}
        {percent !== null && percent !== undefined ? ` · ${formatPercent(percent, 1)}` : ''}
      </span>
    </div>
  )
}

function TypeStat({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-[9px] uppercase tracking-wide text-graphite-500">{label}</p>
      <p className="truncate font-mono text-[11px] font-semibold tabular-nums text-graphite-100">{value}</p>
    </div>
  )
}

function CoverageBit({ label, value }) {
  return (
    <div className="rounded-lg border border-graphite-700/60 bg-graphite-900/40 px-3 py-2">
      <p className="eyebrow">{label}</p>
      <p className="mt-0.5 truncate font-mono text-[11px] font-semibold text-graphite-100">{value}</p>
    </div>
  )
}
