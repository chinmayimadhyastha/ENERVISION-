import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  AlertTriangle,
  Award,
  BrainCircuit,
  Cpu,
  Database,
  FlaskConical,
  Gauge,
  Layers,
  Ruler,
  Target,
} from 'lucide-react'

import { getFeatureImportance, getModelPerformance } from '../services/api.js'
import useAsync from '../hooks/useAsync.js'
import { formatNumber, formatPercent } from '../utils/format.js'
import { AXIS_PROPS, GRID_PROPS, PALETTE } from '../utils/constants.js'

import PageHeader from '../components/ui/PageHeader.jsx'
import SectionTitle from '../components/ui/SectionTitle.jsx'
import Card from '../components/ui/Card.jsx'
import ChartCard from '../components/ui/ChartCard.jsx'
import StatCard from '../components/ui/StatCard.jsx'
import Badge from '../components/ui/Badge.jsx'
import Select from '../components/ui/Select.jsx'
import SegmentedControl from '../components/ui/SegmentedControl.jsx'
import DemoNotice, { RESEARCH_DEMO_LABEL } from '../components/ui/DemoNotice.jsx'
import LoadingState from '../components/ui/LoadingState.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import DataTable from '../components/ui/DataTable.jsx'
import { ChartTooltip, ChartLegend } from '../components/charts/index.js'

const FEATURE_METHOD_LABEL = 'Random Forest impurity'

const MODEL_ACCENTS = {
  random_forest: 'brand',
  solar_lstm: 'solar',
  wind_lstm: 'wind',
}

/** Committed model metrics from /api/model-performance and Random Forest
 *  impurity importance from /api/feature-importance. Only values the API
 *  publishes are rendered; unavailable metrics are shown as “not published”. */
export default function ModelPerformance() {
  const perf = useAsync(() => getModelPerformance(), [])
  const fi = useAsync(() => getFeatureImportance(), [])

  const [selectedId, setSelectedId] = useState('random_forest')
  const [fiView, setFiView] = useState('current')

  const models = perf.data?.models ?? []
  const selected = models.find((m) => m.id === selectedId) ?? models[0] ?? null

  const maeRows = useMemo(
    () =>
      models
        .filter((m) => m.metrics?.mae !== null && m.metrics?.mae !== undefined)
        .map((m) => ({
          id: m.id,
          name: m.name,
          shortName: m.shortName,
          mae: m.metrics.mae,
          color: MODEL_ACCENTS[m.id] === 'solar' ? PALETTE.solar : MODEL_ACCENTS[m.id] === 'wind' ? PALETTE.wind : PALETTE.brand,
        }))
        .sort((a, b) => a.mae - b.mae),
    [models],
  )

  const rf = models.find((m) => m.id === 'random_forest') ?? null
  const solar = models.find((m) => m.id === 'solar_lstm') ?? null
  const wind = models.find((m) => m.id === 'wind_lstm') ?? null

  const modelColumns = useMemo(
    () => [
      {
        key: 'name',
        header: 'Model',
        render: (r) => (
          <div className="min-w-0">
            <p className="truncate text-[12px] font-semibold text-graphite-100">{r.name}</p>
            <p className="truncate font-mono text-[10px] text-graphite-500">{r.modelId}</p>
          </div>
        ),
      },
      {
        key: 'family',
        header: 'Family',
        render: (r) => <span className="text-[11px] text-graphite-300">{r.family}</span>,
      },
      {
        key: 'featureCount',
        header: 'Inputs',
        align: 'right',
        render: (r) => (
          <span className="font-mono text-[11px] text-graphite-300">
            {r.featureCount === null || r.featureCount === undefined ? '—' : formatNumber(r.featureCount, 0)}
            {r.sequenceLength ? <span className="text-graphite-500"> · seq {r.sequenceLength}</span> : null}
          </span>
        ),
      },
      {
        key: 'mae',
        header: 'MAE',
        align: 'right',
        render: (r) => <MetricValue value={r.metrics?.mae} digits={3} unit="MU/day" />,
      },
      {
        key: 'rmse',
        header: 'RMSE',
        align: 'right',
        render: (r) => <MetricValue value={r.metrics?.rmse} digits={3} unit="MU/day" />,
      },
      {
        key: 'r2',
        header: 'R²',
        align: 'right',
        render: (r) => <MetricValue value={r.metrics?.r2} digits={3} />,
      },
      {
        key: 'status',
        header: 'Status',
        align: 'right',
        render: (r) => (
          <Badge tone={r.status === 'production_candidate' ? 'success' : 'neutral'} size="sm">
            {r.status === 'production_candidate'
              ? 'production candidate'
              : r.status === 'demo_only'
                ? 'demo only'
                : 'committed artifact'}
          </Badge>
        ),
      },
    ],
    [],
  )

  const featureColumns = useMemo(
    () => [
      {
        key: 'rank',
        header: '#',
        render: (r) => <span className="font-mono text-[11px] text-graphite-500">{r.rank}</span>,
      },
      {
        key: 'label',
        header: 'Feature',
        render: (r) => <span className="text-[12px] font-semibold text-graphite-100">{r.label}</span>,
      },
      {
        key: 'key',
        header: 'API key',
        render: (r) => <span className="font-mono text-[10px] text-graphite-500">{r.key}</span>,
      },
      {
        key: 'importance',
        header: 'Importance',
        align: 'right',
        render: (r) => (
          <div className="flex items-center justify-end gap-2">
            <span className="hidden h-1.5 w-24 overflow-hidden rounded-full bg-white/5 sm:block">
              <span
                className="block h-full rounded-full"
                style={{
                  width: `${Math.max(1, Math.min(100, (r.importance || 0) * 100))}%`,
                  background: PALETTE.brand,
                }}
              />
            </span>
            <span className="font-mono text-[11px] font-bold text-white">{formatPercent((r.importance || 0) * 100, 2)}</span>
          </div>
        ),
      },
    ],
    [],
  )

  if (perf.loading) {
    return (
      <div className="space-y-6">
        <LoadingState variant="cards" />
        <LoadingState variant="chart" />
      </div>
    )
  }

  if (perf.error || !perf.data) {
    return (
      <ErrorState
        title="Model metrics unavailable"
        message={perf.error?.userMessage || perf.error?.message}
        onRetry={perf.refetch}
      />
    )
  }

  const currentFeatures = fi.data?.features ?? []
  const historical = fi.data?.historical ?? null
  const chartFeatures = [...currentFeatures].slice(0, 14)

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Forecasting Laboratory"
        title="Model Performance"
        description={
          perf.data.isDemo
            ? 'Illustrative daily models for interface review. In live mode, committed artifacts and published metrics are read from the ENERVISION API. Target DailyGeneration_MU, unit MU/day.'
            : 'Committed daily forecasting artifacts published by the ENERVISION API. Target DailyGeneration_MU, unit MU/day. Only metrics actually exported by the backend are shown.'
        }
        icon={<FlaskConical className="h-5 w-5" />}
        badge={
          <Badge tone="solar" size="sm">
            {models.length} daily models
          </Badge>
        }
        meta={[
          { label: 'Frequency', value: perf.data.frequency || 'daily' },
          { label: 'Target', value: perf.data.target || 'DailyGeneration_MU' },
          { label: 'Unit', value: perf.data.unit || 'MU/day' },
          { label: 'Importance', value: FEATURE_METHOD_LABEL },
        ]}
      />

      <DemoNotice label={RESEARCH_DEMO_LABEL} tone="sky">
        In demo mode these values are illustrative. With a live API, metrics and feature importance are read directly
        from <code className="font-mono">/api/model-performance</code> and{' '}
        <code className="font-mono">/api/feature-importance</code>. Nothing is synthesised, and SHAP is not used.
      </DemoNotice>

      {/* ----------------------------------------------------------- KPIs --- */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5">
        <StatCard
          label="Random Forest MAE"
          value={rf?.metrics?.mae ?? null}
          decimals={3}
          unit="MU/day"
          tone="brand"
          icon={<Cpu className="h-4 w-4" />}
          hint={rf?.featureCount ? `${rf.featureCount} leakage-free features` : 'current 24-feature model'}
        />
        <StatCard
          label="Random Forest R²"
          value={rf?.metrics?.r2 ?? null}
          decimals={3}
          tone="emerald"
          icon={<Target className="h-4 w-4" />}
          hint="chronological test split"
        />
        <StatCard
          label="Solar LSTM MAE"
          value={solar?.metrics?.mae ?? null}
          decimals={3}
          unit="MU/day"
          tone="solar"
          icon={<Ruler className="h-4 w-4" />}
          hint={perf.data.isDemo ? 'demo artifact · only MAE shown' : 'committed artifact · only MAE published'}
        />
        <StatCard
          label="Wind LSTM MAE"
          value={wind?.metrics?.mae ?? null}
          decimals={3}
          unit="MU/day"
          tone="wind"
          icon={<Ruler className="h-4 w-4" />}
          hint={perf.data.isDemo ? 'demo artifact · only MAE shown' : 'committed artifact · only MAE published'}
        />
        <StatCard
          label="Model inputs"
          value={rf?.metrics?.features ?? rf?.featureCount ?? null}
          tone="violet"
          icon={<Layers className="h-4 w-4" />}
          hint="Random Forest feature count"
        />
      </div>

      {/* --------------------------------------------- MAE + model table --- */}
      <section className="grid gap-5 xl:grid-cols-3">
        <ChartCard
          className="xl:col-span-2"
          title="Published MAE by Model"
          subtitle="Mean absolute error in MU/day · lower is better"
          icon={<BrainCircuit className="h-4 w-4" />}
          accent="brand"
          height={300}
          footer={
            <div className="flex flex-wrap items-center justify-between gap-2">
              <ChartLegend items={[{ key: 'mae', label: 'MAE (MU/day)', color: PALETTE.brand }]} />
              <span className="font-mono text-[10px] text-graphite-500">
                MAE is published for all three artifacts. RMSE and R² are published only for the Random Forest — no
                cross-model rank is claimed.
              </span>
            </div>
          }
        >
          {maeRows.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={maeRows} margin={{ top: 10, right: 16, bottom: 0, left: -12 }}>
                <CartesianGrid {...GRID_PROPS} />
                <XAxis dataKey="name" {...AXIS_PROPS} />
                <YAxis width={52} {...AXIS_PROPS} tickFormatter={(v) => formatNumber(v, 2)} />
                <Tooltip
                  cursor={{ fill: 'rgba(148,163,184,0.06)' }}
                  content={
                    <ChartTooltip
                      units={{ mae: ' MU/day' }}
                      digits={4}
                      valueFormatter={(v) => formatNumber(v, 4)}
                    />
                  }
                />
                <Bar dataKey="mae" name="MAE" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {maeRows.map((row) => (
                    <Cell key={row.id} fill={row.color} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-graphite-400">
              No published metric values returned.
            </div>
          )}
        </ChartCard>

        <Card padded accent="solar" className="flex flex-col justify-between gap-4">
          <div>
            <p className="flex items-center gap-1.5 eyebrow">
              <Award className="h-3 w-3 text-solar-300" /> Metric definitions
            </p>
            <div className="mt-3 space-y-2">
              {Object.entries(perf.data.metricDefinitions || {}).map(([key, value]) => (
                <div key={key} className="rounded-lg border border-graphite-700/70 bg-graphite-850/50 px-3 py-2">
                  <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-graphite-300">{key}</p>
                  <p className="mt-0.5 text-[10px] leading-relaxed text-graphite-500">{value}</p>
                </div>
              ))}
              {!perf.data.metricDefinitions ? (
                <p className="text-xs leading-relaxed text-graphite-400">
                  The API did not return metric definitions for this deployment.
                </p>
              ) : null}
            </div>
          </div>
          {perf.data.comparisonPolicy ? (
            <div className="rounded-lg border border-solar-400/25 bg-solar-400/[0.06] px-3 py-2.5">
              <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-solar-200">
                <AlertTriangle className="h-3 w-3" /> Comparability policy
              </p>
              <p className="mt-1 text-[10px] leading-relaxed text-graphite-300">{perf.data.comparisonPolicy.reason}</p>
              <p className="mt-1 font-mono text-[10px] text-graphite-500">
                current features: {perf.data.comparisonPolicy.current_random_forest_features ?? '—'} · historical:{' '}
                {perf.data.comparisonPolicy.historical_random_forest_features ?? '—'}
              </p>
            </div>
          ) : null}
        </Card>
      </section>

      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-graphite-700/70 px-4 py-3.5">
          <div>
            <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">
              {perf.data.isDemo ? 'Demo Artifacts' : 'Committed Artifacts'}
            </h3>
            <p className="eyebrow">metrics exactly as published · no imputation</p>
          </div>
          <span className="font-mono text-[11px] text-graphite-400">{models.length} models</span>
        </div>
        <div className="p-3">
          <DataTable columns={modelColumns} rows={models} keyField="id" maxHeight={360} />
        </div>
      </Card>

      {/* ------------------------------------------------- Model inspector --- */}
      <section className="space-y-4">
        <SectionTitle
          eyebrow="Model Inspector"
          title="Model Card"
          description={
            perf.data.isDemo
              ? 'Illustrative provenance for one demo artifact. Unavailable metrics are never inferred.'
              : 'Provenance and published metrics for one committed artifact. Unavailable metrics are never inferred.'
          }
          badge="daily"
          actions={
            <Select
              aria-label="Model"
              value={selected?.id ?? ''}
              onChange={(e) => setSelectedId(e.target.value)}
              options={models.map((m) => ({ value: m.id, label: `${m.name} · ${m.modelId}` }))}
              className="w-full sm:w-80"
              selectClassName="py-1.5 text-xs"
            />
          }
        />

        {selected ? (
          <div className="grid gap-5 xl:grid-cols-3">
            <Card padded accent={MODEL_ACCENTS[selected.id] || 'brand'} className="xl:col-span-2">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-brand-400/25 bg-brand-400/10 text-brand-300">
                    <Cpu className="h-5 w-5" />
                  </span>
                  <div>
                    <h3 className="font-display text-base font-bold text-white">{selected.name}</h3>
                    <p className="eyebrow">{selected.modelId}</p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="neutral" size="sm">
                    {selected.family}
                  </Badge>
                  {selected.status ? (
                    <Badge tone="success" size="sm">
                      {selected.status.replace(/_/g, ' ')}
                    </Badge>
                  ) : (
                    <Badge tone="neutral" size="sm">
                      {perf.data.isDemo ? 'demo only' : 'committed artifact'}
                    </Badge>
                  )}
                </div>
              </div>

              <p className="mt-4 text-xs leading-relaxed text-graphite-300">{selected.description}</p>

              <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <MetricBit label="MAE" value={metricText(selected.metrics?.mae, 4, 'MU/day')} />
                <MetricBit label="RMSE" value={metricText(selected.metrics?.rmse, 4, 'MU/day')} />
                <MetricBit label="R²" value={metricText(selected.metrics?.r2, 4)} />
                <MetricBit
                  label="Input features"
                  value={
                    selected.featureCount === null || selected.featureCount === undefined
                      ? 'Not published'
                      : `${formatNumber(selected.featureCount, 0)}${selected.sequenceLength ? ` · seq ${selected.sequenceLength}` : ''}`
                  }
                />
                <MetricBit
                  label="Train rows"
                  value={selected.metrics?.trainRows === null || selected.metrics?.trainRows === undefined ? 'Not published' : formatNumber(selected.metrics.trainRows, 0)}
                />
                <MetricBit
                  label="Test rows"
                  value={selected.metrics?.testRows === null || selected.metrics?.testRows === undefined ? 'Not published' : formatNumber(selected.metrics.testRows, 0)}
                />
                <MetricBit
                  label="Plants"
                  value={selected.metrics?.plants === null || selected.metrics?.plants === undefined ? 'Not published' : formatNumber(selected.metrics.plants, 0)}
                />
                <MetricBit
                  label="Sequence length"
                  value={selected.sequenceLength === null || selected.sequenceLength === undefined ? 'Not applicable' : `${selected.sequenceLength} days`}
                />
              </div>

              <p className="mt-4 border-t border-graphite-700/60 pt-3 text-[10px] leading-relaxed text-graphite-500">
                Values are copied from the API payload without transformation. A dash or “Not published” means the
                backend does not export that metric for this artifact.
              </p>
            </Card>

            <Card padded accent="violet">
              <p className="eyebrow">Artifact provenance</p>
              <div className="mt-3 space-y-2">
                <ProvenanceRow label="Model ID" value={selected.modelId} mono />
                <ProvenanceRow label="Status" value={selected.status || (perf.data.isDemo ? 'demo only' : 'committed artifact')} />
                <ProvenanceRow label="Target" value={perf.data.target || 'DailyGeneration_MU'} mono />
                <ProvenanceRow label="Unit" value={perf.data.unit || 'MU/day'} mono />
                <ProvenanceRow label="Frequency" value={perf.data.frequency || 'daily'} mono />
              </div>

              {rf?.historical ? (
                <div className="mt-4 rounded-lg border border-solar-400/25 bg-solar-400/[0.06] px-3 py-2.5">
                  <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-solar-200">
                    <AlertTriangle className="h-3 w-3" /> Historical 25-feature reference
                  </p>
                  <p className="mt-1 text-[10px] leading-relaxed text-graphite-300">
                    Leakage-affected ({String(rf.historical.leakage_affected)}) and not comparable to the current
                    24-feature model. Provenance only — never current production performance.
                  </p>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="font-mono text-[10px] text-graphite-500">historical MAE</span>
                    <span className="font-mono text-[11px] font-semibold text-solar-200">
                      {metricText(rf.historical.MAE, 4, 'MU/day')}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between">
                    <span className="font-mono text-[10px] text-graphite-500">comparable</span>
                    <span className="font-mono text-[11px] font-semibold text-solar-200">
                      {String(rf.historical.comparable_to_current_24_feature_model)}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between">
                    <span className="font-mono text-[10px] text-graphite-500">usage</span>
                    <span className="font-mono text-[11px] font-semibold text-solar-200">{rf.historical.usage || 'provenance only'}</span>
                  </div>
                </div>
              ) : null}

              {selected.id !== 'random_forest' ? (
                <p className="mt-4 text-[10px] leading-relaxed text-graphite-500">
                  Only the committed MAE is published for this LSTM artifact. RMSE, R² and split sizes are not inferred
                  or imported from a separate regenerated pipeline.
                </p>
              ) : null}
            </Card>
          </div>
        ) : null}
      </section>

      {/* --------------------------------------------- Feature importance --- */}
      <section className="space-y-4">
        <SectionTitle
          eyebrow="Explainability"
          title="Random Forest Feature Importance"
          description="Mean decrease in impurity (Gini importance) from the fitted production-candidate Random Forest. This is not SHAP and not permutation importance."
          badge="shap_used: false"
          actions={
            <SegmentedControl
              ariaLabel="Feature importance view"
              value={fiView}
              onChange={setFiView}
              options={[
                { value: 'current', label: 'Current 24-feature' },
                { value: 'historical', label: 'Historical reference' },
              ]}
            />
          }
        />

        {fi.loading ? (
          <LoadingState variant="chart" />
        ) : fi.error ? (
          <ErrorState
            compact
            title="Feature importance unavailable"
            message={fi.error.userMessage || fi.error.message}
            onRetry={fi.refetch}
          />
        ) : !fi.data ? (
          <Card padded>
            <p className="text-xs text-graphite-400">The API returned no feature-importance payload.</p>
          </Card>
        ) : fiView === 'current' ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Importance method" value={FEATURE_METHOD_LABEL} tone="solar" icon={<Award className="h-4 w-4" />} hint="not SHAP" />
              <StatCard label="Features" value={fi.data.featureCount ?? currentFeatures.length} tone="brand" icon={<Database className="h-4 w-4" />} hint={fi.data.modelId || 'random_forest_daily'} />
              <StatCard label="Importance sum" value={fi.data.importanceSum} decimals={4} tone="violet" icon={<Gauge className="h-4 w-4" />} hint="normalised impurity importance" />
              <StatCard label="SHAP used" value="No" tone="neutral" icon={<AlertTriangle className="h-4 w-4" />} hint="shap_used: false" />
            </div>

            <div className="grid gap-5 xl:grid-cols-3">
              <ChartCard
                className="xl:col-span-2"
                title="Top Feature Importance"
                subtitle={`Top ${chartFeatures.length} of ${currentFeatures.length} inputs · mean decrease in impurity`}
                icon={<BrainCircuit className="h-4 w-4" />}
                accent="solar"
                height={380}
                footer={
                  <span className="font-mono text-[10px] leading-relaxed text-graphite-500">
                    {fi.data.methodDescription || 'Random Forest impurity importance. Not SHAP.'}
                  </span>
                }
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartFeatures} layout="vertical" margin={{ top: 4, right: 26, bottom: 0, left: 40 }}>
                    <CartesianGrid {...GRID_PROPS} vertical horizontal={false} />
                    <XAxis type="number" {...AXIS_PROPS} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                    <YAxis type="category" dataKey="label" width={160} {...AXIS_PROPS} />
                    <Tooltip
                      cursor={{ fill: 'rgba(148,163,184,0.06)' }}
                      content={<ChartTooltip valueFormatter={(v) => formatPercent(v * 100, 2)} />}
                    />
                    <Bar dataKey="importance" name="Importance" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                      {chartFeatures.map((f, i) => (
                        <Cell key={f.key} fill={i < 3 ? PALETTE.solar : PALETTE.brand} fillOpacity={0.85} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>

              <Card padded accent="brand">
                <p className="eyebrow">Method disclosure</p>
                <p className="mt-2 text-[11px] leading-relaxed text-graphite-300">
                  The API publishes <code className="font-mono text-brand-200">method: random_forest_impurity</code> and{' '}
                  <code className="font-mono text-brand-200">shap_used: false</code>. The UI labels this as Random Forest
                  impurity importance and never as SHAP.
                </p>
                {fi.data.notes?.length ? (
                  <ul className="mt-3 space-y-1.5">
                    {fi.data.notes.map((note) => (
                      <li key={note} className="text-[10px] leading-relaxed text-graphite-500">
                        {note}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <p className="mt-3 border-t border-graphite-700/60 pt-2 font-mono text-[10px] text-graphite-500">
                  target: {fi.data.target || 'DailyGeneration_MU'} · frequency: {fi.data.frequency || 'daily'}
                </p>
              </Card>
            </div>

            <Card padded={false}>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-graphite-700/70 px-4 py-3.5">
                <div>
                  <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Feature Register</h3>
                  <p className="eyebrow">current leakage-free inputs · importance share</p>
                </div>
                <Badge tone="brand" size="sm">
                  {currentFeatures.length} features
                </Badge>
              </div>
              <div className="p-3">
                <DataTable columns={featureColumns} rows={currentFeatures} keyField="key" dense maxHeight={440} />
              </div>
            </Card>
          </>
        ) : (
          <HistoricalImportance historical={historical} columns={featureColumns} />
        )}
      </section>

      {perf.data.notes?.length ? (
        <Card padded accent="neutral">
          <p className="eyebrow">API notes</p>
          <ul className="mt-2 space-y-1">
            {perf.data.notes.map((note) => (
              <li key={note} className="text-[10px] leading-relaxed text-graphite-400">
                {note}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Local helper components                                                   */
/* -------------------------------------------------------------------------- */

function MetricValue({ value, digits, unit }) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return <span className="font-mono text-[10px] text-graphite-500">not published</span>
  }
  return (
    <span className="font-mono text-[11px] font-semibold text-graphite-100">
      {formatNumber(value, digits)}
      {unit ? <span className="ml-0.5 text-graphite-500">{unit}</span> : null}
    </span>
  )
}

function metricText(value, digits, unit) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Not published'
  return `${formatNumber(value, digits)}${unit ? ` ${unit}` : ''}`
}

function MetricBit({ label, value }) {
  return (
    <div className="rounded-lg border border-graphite-700/60 bg-graphite-850/50 px-3 py-2">
      <p className="text-[9px] font-semibold uppercase tracking-wide text-graphite-500">{label}</p>
      <p className="mt-0.5 truncate font-mono text-[11px] font-bold tabular-nums text-graphite-100">{value}</p>
    </div>
  )
}

function ProvenanceRow({ label, value, mono }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-graphite-800/80 py-2 last:border-0">
      <span className="eyebrow">{label}</span>
      <span className={`text-right text-[11px] font-semibold text-graphite-100 ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  )
}

function HistoricalImportance({ historical, columns }) {
  if (!historical) {
    return (
      <Card padded>
        <p className="text-xs text-graphite-400">The API did not return a historical 25-feature reference block.</p>
      </Card>
    )
  }

  return (
    <>
      <Card padded accent="solar" className="border-solar-400/25 bg-solar-400/[0.04]">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-solar-400/25 bg-solar-400/10 text-solar-300">
            <AlertTriangle className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="font-display text-sm font-bold text-solar-100">Historical 25-feature reference — not comparable</p>
            <p className="mt-1 text-[11px] leading-relaxed text-graphite-300">
              {historical.note ||
                'Historical importances from the removed 25-feature model. They include the leaked Generation_per_MW feature and are not comparable to the current 24-feature model.'}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone="warning" size="sm" mono>
                leakage_affected: {String(historical.leakageAffected)}
              </Badge>
              <Badge tone="neutral" size="sm" mono>
                comparable_to_current: {String(historical.comparableToCurrent)}
              </Badge>
              <Badge tone="neutral" size="sm" mono>
                method: {historical.method || 'random_forest_impurity'}
              </Badge>
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-graphite-500">
              Provenance only. These values must never be presented as current production feature importance.
            </p>
          </div>
        </div>
      </Card>

      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-graphite-700/70 px-4 py-3.5">
          <div>
            <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Historical Feature Register</h3>
            <p className="eyebrow">25-feature model · includes leaked Generation_per_MW</p>
          </div>
          <Badge tone="warning" size="sm">
            {historical.features?.length ?? 0} features
          </Badge>
        </div>
        <div className="p-3">
          <DataTable
            columns={columns}
            rows={historical.features ?? []}
            keyField="key"
            dense
            emptyTitle="No historical importance rows"
            emptyDescription="The API returned no historical reference features."
            maxHeight={440}
          />
        </div>
      </Card>
    </>
  )
}
