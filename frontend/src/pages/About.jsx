import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Clock,
  Cloud,
  Database,
  Factory,
  Filter,
  GitCompare,
  Globe2,
  Layers,
  LayoutDashboard,
  LineChart,
  MapPinned,
  Satellite,
  Server,
  ShieldCheck,
  Sparkles,
  Target,
  Wrench,
  Zap,
} from 'lucide-react'

import { API_MODE, getPlants, referenceData } from '../services/api.js'
import useAsync from '../hooks/useAsync.js'
import { FEATURE_LABELS, PALETTE } from '../utils/constants.js'
import { cx, formatNumber } from '../utils/format.js'

import PageHeader from '../components/ui/PageHeader.jsx'
import SectionTitle from '../components/ui/SectionTitle.jsx'
import Card from '../components/ui/Card.jsx'
import Badge from '../components/ui/Badge.jsx'
import Button from '../components/ui/Button.jsx'
import StatCard from '../components/ui/StatCard.jsx'
import Icon from '../components/ui/Icon.jsx'
import DemoNotice, { RESEARCH_DEMO_LABEL } from '../components/ui/DemoNotice.jsx'
import RadialGauge from '../components/domain/RadialGauge.jsx'

/* -------------------------------------------------------------------------- */
/*  Static descriptive content                                                */
/* -------------------------------------------------------------------------- */

const MODEL_SUMMARY = [
  {
    name: 'Random Forest',
    family: 'Daily production candidate',
    short: 'RF',
    tone: 'brand',
    note: 'Current leakage-free 24-feature daily model. MAE, RMSE and R² are published by the API.',
  },
  {
    name: 'Solar LSTM',
    family: 'Type-specific sequence model',
    short: 'S-LSTM',
    tone: 'solar',
    note: 'Committed solar daily artifact. Only the committed MAE is published — no other metric is inferred.',
  },
  {
    name: 'Wind LSTM',
    family: 'Type-specific sequence model',
    short: 'W-LSTM',
    tone: 'wind',
    note: 'Committed wind daily artifact. Only the committed MAE is published — no other metric is inferred.',
  },
]

const FEATURE_GROUPS = [
  {
    title: 'Weather features',
    tone: 'solar',
    icon: <Cloud className="h-3.5 w-3.5" />,
    items: [
      FEATURE_LABELS.ghi,
      FEATURE_LABELS.temperature,
      FEATURE_LABELS.humidity,
      FEATURE_LABELS.windSpeed,
      FEATURE_LABELS.pressure,
    ],
  },
  {
    title: 'Generation lag features',
    tone: 'brand',
    icon: <Zap className="h-3.5 w-3.5" />,
    items: [FEATURE_LABELS.prevGeneration, FEATURE_LABELS.rollingGeneration],
  },
  {
    title: 'Calendar features',
    tone: 'violet',
    icon: <Layers className="h-3.5 w-3.5" />,
    items: [FEATURE_LABELS.dayOfYear, FEATURE_LABELS.month, FEATURE_LABELS.season],
  },
]

const DATA_FLOW = [
  { icon: Database, label: 'CEA generation data', sub: 'Daily target · MU/day' },
  { icon: Satellite, label: 'NASA POWER weather', sub: 'Observed daily features' },
  { icon: Factory, label: 'Plant master data', sub: 'Capacity · coordinates' },
  { icon: Filter, label: 'Preprocess & join', sub: 'Clean · align · QC' },
  { icon: Wrench, label: 'Feature engineering', sub: 'Weather · lags · calendar' },
  { icon: BrainCircuit, label: 'Daily forecasting', sub: 'RF · solar/wind LSTM' },
  { icon: ShieldCheck, label: 'Explainability', sub: 'Impurity importance (not SHAP)' },
  { icon: LayoutDashboard, label: 'Decision support', sub: 'This dashboard' },
]

const OBJECTIVE_META = [
  { icon: Database, tone: 'wind' },
  { icon: GitCompare, tone: 'brand' },
  { icon: BrainCircuit, tone: 'violet' },
  { icon: Target, tone: 'solar' },
  { icon: ShieldCheck, tone: 'brand' },
  { icon: LayoutDashboard, tone: 'wind' },
]

const ARCH_TONES = ['wind', 'brand', 'solar', 'violet', 'wind', 'brand']

const SOURCE_ICONS = { cea: Database, 'nasa-power': Satellite, plant: Factory }
const SOURCE_TONE = { brand: 'brand', sky: 'wind', amber: 'solar' }

const TECH_ICONS = { Frontend: Globe2, 'Data & API': Server, 'ML / Modelling (research)': BrainCircuit, Explainability: ShieldCheck }
const TECH_TONE = { Frontend: 'brand', 'Data & API': 'wind', 'ML / Modelling (research)': 'violet', Explainability: 'solar' }

const ICON_TONES = {
  brand: 'border-brand-400/25 bg-brand-400/10 text-brand-300',
  solar: 'border-solar-400/25 bg-solar-400/10 text-solar-300',
  wind: 'border-wind-400/25 bg-wind-400/10 text-wind-300',
  violet: 'border-violet-400/25 bg-violet-400/10 text-violet-300',
}

/* -------------------------------------------------------------------------- */
/*  Small local primitives                                                    */
/* -------------------------------------------------------------------------- */

function IconTile({ icon, tone = 'brand', className = '' }) {
  return (
    <span className={cx('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border', ICON_TONES[tone] || ICON_TONES.brand, className)}>
      {icon}
    </span>
  )
}

function MiniTile({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-graphite-700/60 bg-graphite-850/50 px-3 py-2.5">
      <p className="eyebrow">{label}</p>
      <p className="mt-0.5 font-display text-sm font-bold text-white">{value}</p>
      {sub ? <p className="text-[10px] leading-snug text-graphite-500">{sub}</p> : null}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Page                                                                      */
/* -------------------------------------------------------------------------- */

export default function About() {
  const { dataSources, techStack, architecture, objectives, problemStatement, futureScope } = referenceData
  const plantsAsync = useAsync(() => getPlants(), [])
  const plants = useMemo(() => plantsAsync.data ?? [], [plantsAsync.data])

  const districts = useMemo(
    () => [...new Set(plants.map((p) => p.district).filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [plants],
  )
  const solarCount = plants.filter((p) => p.type === 'solar').length
  const windCount = plants.filter((p) => p.type === 'wind').length
  const total = plants.length || 1
  const solarPct = (solarCount / total) * 100
  const windPct = (windCount / total) * 100
  const totalCapacity = plants.reduce((sum, p) => sum + (p.capacityMW || 0), 0)

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------- Page header --- */}
      <PageHeader
        eyebrow="About"
        title="About ENERVISION"
        icon={<Sparkles className="h-5 w-5" />}
        badge={<Badge tone="solar" size="sm">Final-year project</Badge>}
        description="ENERVISION is an AI-powered renewable energy forecasting and decision-support platform for Karnataka. It combines authoritative daily generation and weather data with committed machine-learning models to deliver plant-wise daily forecasts and descriptive analytics."
        meta={[
          { label: 'Scope', value: 'Karnataka' },
          { label: 'Targets', value: 'Solar + Wind' },
          { label: 'Pipeline', value: `${architecture.length} stages` },
          { label: 'Contract', value: 'Daily · MU/day' },
        ]}
        actions={
          <>
            <Button as={Link} to="/model-performance" variant="secondary" size="md">
              <BrainCircuit className="h-4 w-4" />
              Model performance
            </Button>
            <Button as={Link} to="/" variant="primary" size="md">
              <LayoutDashboard className="h-4 w-4" />
              Open dashboard
            </Button>
          </>
        }
      />

      {/* ------------------------------------------------------------- Hero --- */}
      <Card accent="brand" className="relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute inset-0 ev-grid opacity-[0.35]" aria-hidden />
        <div className="pointer-events-none absolute inset-0 ev-contour ev-fade-mask opacity-70" aria-hidden />
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-brand-500/15 blur-3xl" aria-hidden />

        <div className="relative grid grid-cols-1 gap-8 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Badge tone="brand" size="sm" dot pulse>
              AI-powered renewable energy intelligence
            </Badge>
            <h2 className="mt-4 font-display text-2xl font-bold leading-tight tracking-tight text-white sm:text-3xl">
              Forecasting Karnataka&rsquo;s daily solar and wind generation, plant by plant.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-graphite-300">
              ENERVISION brings together CEA daily generation records and NASA POWER observed weather, engineers the
              physical drivers of renewable output, serves committed Random Forest and type-specific LSTM artifacts, and
              surfaces the results through an honest decision-support dashboard. The target is{' '}
              <span className="font-mono text-brand-200">DailyGeneration_MU</span> in{' '}
              <span className="font-mono text-brand-200">MU/day</span>.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {['Plant-wise daily forecasting', 'Three committed models', 'Impurity importance (not SHAP)', 'Descriptive daily analytics'].map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-white/5 px-2.5 py-1.5 text-[11px] font-semibold text-graphite-200 ring-1 ring-inset ring-white/10"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 text-brand-300" />
                  {t}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-graphite-700/70 bg-graphite-950/50 p-4">
            <div className="flex items-center justify-between">
              <p className="eyebrow">Fleet composition</p>
              <Badge tone="neutral" size="sm" mono>
                {plantsAsync.loading ? '—' : `${formatNumber(total)} plants`}
              </Badge>
            </div>
            <div className="mt-3 flex items-center justify-around gap-2">
              <RadialGauge value={solarPct} valueText={String(solarCount)} label="Solar" sublabel="plants" color={PALETTE.solar} />
              <RadialGauge value={windPct} valueText={String(windCount)} label="Wind" sublabel="plants" color={PALETTE.wind} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-graphite-700/60 pt-3">
              <div>
                <p className="eyebrow">Installed</p>
                <p className="font-display text-sm font-bold text-white tabular">
                  {plantsAsync.loading ? '—' : `${formatNumber(totalCapacity)} MW`}
                </p>
              </div>
              <div>
                <p className="eyebrow">Districts</p>
                <p className="font-display text-sm font-bold text-white tabular">
                  {plantsAsync.loading ? '—' : formatNumber(districts.length)}
                </p>
              </div>
            </div>
            {plantsAsync.error ? (
              <p className="mt-3 text-[10px] leading-relaxed text-solar-300">
                Plant registry unavailable: {plantsAsync.error.userMessage || plantsAsync.error.message}
              </p>
            ) : null}
          </div>
        </div>
      </Card>

      {/* -------------------------------------------------------- KPI strip --- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Districts covered"
          value={plantsAsync.loading ? null : districts.length}
          tone="wind"
          icon={<MapPinned className="h-4 w-4" />}
          hint="districts present in the plant registry"
        />
        <StatCard
          label="Monitored plants"
          value={plantsAsync.loading ? null : plants.length}
          tone="brand"
          icon={<Factory className="h-4 w-4" />}
          hint={
            API_MODE === 'live'
              ? 'solar + wind assets from the backend registry'
              : 'illustrative solar + wind assets'
          }
        />
        <StatCard
          label={API_MODE === 'live' ? 'Committed models' : 'Models'}
          value={MODEL_SUMMARY.length}
          tone="violet"
          icon={<BrainCircuit className="h-4 w-4" />}
          hint="Random Forest · solar/wind LSTM"
        />
        <StatCard
          label="Forecast horizon"
          value={7}
          unit="days"
          tone="solar"
          icon={<Clock className="h-4 w-4" />}
          hint="1–7 daily steps · default 3"
        />
      </div>

      <DemoNotice tone="sky" label={RESEARCH_DEMO_LABEL}>
        In demo mode the daily values shown across this frontend are illustrative. With{' '}
        <code className="font-mono">VITE_API_BASE_URL</code> configured, registry data, generation, forecasts, metrics and
        feature importance are read from the ENERVISION API; failures are surfaced rather than replaced by demo data.
      </DemoNotice>

      {/* -------------------------------------------- Problem statement --- */}
      <section className="space-y-4">
        <SectionTitle eyebrow="The problem" title={problemStatement.heading} tone="solar" badge="Context" />
        <Card className="border-rose-500/25 bg-rose-500/[0.04] p-5 sm:p-6">
          <div className="flex items-start gap-3.5">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-rose-500/25 bg-rose-500/10 text-rose-300">
              <Target className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <p className="text-sm leading-relaxed text-graphite-200">{problemStatement.body}</p>
              <ul className="mt-4 grid gap-2.5 sm:grid-cols-2">
                {problemStatement.points.map((p) => (
                  <li key={p} className="flex gap-2.5 text-xs leading-relaxed text-graphite-300">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      </section>

      {/* ----------------------------------------------------- Objectives --- */}
      <section className="space-y-4">
        <SectionTitle eyebrow="Mission" title="Objectives" tone="brand" badge={`${objectives.length} goals`} description="What the project sets out to deliver, end to end." />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {objectives.map((o, i) => {
            const meta = OBJECTIVE_META[i] || OBJECTIVE_META[OBJECTIVE_META.length - 1]
            const Ico = meta.icon
            return (
              <Card key={o} hover accent={meta.tone} className="flex h-full flex-col p-5">
                <div className="flex items-center justify-between">
                  <IconTile icon={<Ico className="h-4 w-4" />} tone={meta.tone} />
                  <span className="font-display text-2xl font-extrabold text-graphite-700 tabular">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                </div>
                <p className="mt-4 text-xs leading-relaxed text-graphite-300">{o}</p>
              </Card>
            )
          })}
        </div>
      </section>

      {/* ------------------------------------------------- Architecture --- */}
      <section className="space-y-4">
        <SectionTitle
          eyebrow="Pipeline"
          title="System Architecture & Workflow"
          tone="wind"
          badge={`${architecture.length} stages`}
          description="The end-to-end pipeline: from raw generation and weather data through plant-wise modelling to the decision-support dashboard."
        />

        <Card padded={false} className="p-5 sm:p-6">
          {/* Horizontal pipeline (lg+) */}
          <div className="relative hidden lg:block">
            <svg className="pointer-events-none absolute inset-x-0 top-[21px] h-[2px] w-full" aria-hidden>
              <line
                x1="3%"
                y1="50%"
                x2="97%"
                y2="50%"
                stroke="rgba(45,212,191,0.4)"
                strokeWidth="2"
                strokeDasharray="7 7"
                strokeLinecap="round"
                className="animate-dash-flow"
              />
            </svg>
            <ol className="relative grid grid-cols-6 gap-4">
              {architecture.map((a, i) => {
                const tone = ARCH_TONES[i % ARCH_TONES.length]
                return (
                  <li key={a.step} className="flex flex-col items-center text-center">
                    <span className={cx('relative z-10 flex h-11 w-11 items-center justify-center rounded-xl border bg-graphite-900', ICON_TONES[tone])}>
                      <Icon name={a.icon} className="h-5 w-5" />
                    </span>
                    <Card accent={tone} hover className="mt-5 w-full p-4 text-left">
                      <div className="flex items-center justify-between">
                        <span className="eyebrow">Stage {a.step}</span>
                        <span className="font-display text-lg font-extrabold text-graphite-700 tabular">{a.step}</span>
                      </div>
                      <h3 className="mt-1.5 font-display text-sm font-bold text-white">{a.title}</h3>
                      <p className="mt-1.5 text-[11px] leading-relaxed text-graphite-400">{a.body}</p>
                    </Card>
                  </li>
                )
              })}
            </ol>
          </div>

          {/* Vertical timeline (below lg) */}
          <ol className="relative space-y-3 lg:hidden">
            <span className="absolute bottom-4 left-[21px] top-4 w-px bg-graphite-700/70" aria-hidden />
            {architecture.map((a, i) => {
              const tone = ARCH_TONES[i % ARCH_TONES.length]
              return (
                <li key={a.step} className="relative flex gap-3">
                  <span className={cx('relative z-10 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border bg-graphite-900', ICON_TONES[tone])}>
                    <Icon name={a.icon} className="h-5 w-5" />
                  </span>
                  <Card accent={tone} className="flex-1 p-4">
                    <div className="flex items-center justify-between">
                      <span className="eyebrow">Stage {a.step}</span>
                      <span className="font-display text-lg font-extrabold text-graphite-700 tabular">{a.step}</span>
                    </div>
                    <h3 className="mt-1 font-display text-sm font-bold text-white">{a.title}</h3>
                    <p className="mt-1.5 text-[11px] leading-relaxed text-graphite-400">{a.body}</p>
                  </Card>
                </li>
              )
            })}
          </ol>
        </Card>

        {/* Data flow ribbon */}
        <Card className="p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <IconTile icon={<GitCompare className="h-4 w-4" />} tone="brand" />
            <div>
              <h3 className="font-display text-sm font-bold text-white">Data Flow</h3>
              <p className="text-[11px] text-graphite-400">How a single forecast request moves through the platform.</p>
            </div>
          </div>
          <div className="ev-scroll mt-5 overflow-x-auto pb-1">
            <div className="flex min-w-[860px] items-stretch gap-3">
              {DATA_FLOW.map((s, i, arr) => {
                const Ico = s.icon
                return (
                  <div key={s.label} className="flex items-center gap-3">
                    <div className="flex h-full min-w-[152px] flex-col rounded-xl border border-graphite-700/60 bg-graphite-850/50 p-3.5">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-graphite-700/70 bg-graphite-900/80 text-brand-300">
                        <Ico className="h-4 w-4" />
                      </span>
                      <p className="mt-2.5 text-xs font-bold text-graphite-100">{s.label}</p>
                      <p className="mt-0.5 text-[10px] text-graphite-500">{s.sub}</p>
                    </div>
                    {i < arr.length - 1 ? <ArrowRight className="h-4 w-4 shrink-0 text-graphite-600" /> : null}
                  </div>
                )
              })}
            </div>
          </div>
        </Card>
      </section>

      {/* -------------------------------------------------- Data sources --- */}
      <section className="space-y-4">
        <SectionTitle
          eyebrow="Provenance"
          title="Data Sources"
          tone="solar"
          badge={`${dataSources.length} sources`}
          description="ENERVISION is built on two authoritative public datasets plus the plant registry that ties them together."
        />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {dataSources.map((s) => {
            const Ico = SOURCE_ICONS[s.id] || Database
            const tone = SOURCE_TONE[s.color] || 'brand'
            return (
              <Card key={s.id} accent={tone} hover className="flex h-full flex-col p-5 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <span className={cx('flex h-11 w-11 items-center justify-center rounded-xl border', ICON_TONES[tone])}>
                    <Ico className="h-5 w-5" />
                  </span>
                  <Badge tone={tone} size="sm">
                    {s.cadence}
                  </Badge>
                </div>
                <h3 className="mt-4 font-display text-base font-bold text-white">{s.name}</h3>
                <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide text-graphite-400">{s.role}</p>
                <p className="mt-3 text-xs leading-relaxed text-graphite-400">{s.description}</p>
                <p className="mt-auto pt-4 font-mono text-[11px] text-graphite-500">{s.full}</p>
              </Card>
            )
          })}
        </div>
      </section>

      {/* ------------------------------------------- Plant-wise + Features --- */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <div className="flex items-center gap-2.5">
            <IconTile icon={<Factory className="h-4 w-4" />} tone="wind" />
            <h2 className="font-display text-lg font-bold text-white">Plant-wise Forecasting</h2>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-graphite-300">
            Rather than producing a single state-level number, ENERVISION preserves plant identity and renewable type.
            The Random Forest is trained on fleet-wide daily rows, while dedicated solar and wind LSTM artifacts model
            each technology. Inputs are daily observed records; no hourly resolution is claimed.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <MiniTile label="Target" value="DailyGeneration_MU" sub="Observed daily generation" />
            <MiniTile label="Unit" value="MU/day" sub="One value per plant-day" />
            <MiniTile label="Models" value="RF + LSTM" sub="Type-specific sequence models" />
            <MiniTile label="Evaluation" value="Chronological split" sub="Leakage-free current RF" />
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center gap-2.5">
            <IconTile icon={<Wrench className="h-4 w-4" />} tone="solar" />
            <h2 className="font-display text-lg font-bold text-white">Feature Engineering</h2>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-graphite-300">
            Daily weather and generation records are transformed into the physical drivers of renewable output. The
            current Random Forest uses 24 leakage-free inputs; the leaked{' '}
            <span className="font-mono text-graphite-200">Generation_per_MW</span> feature is excluded.
          </p>
          <div className="mt-4 space-y-3">
            {FEATURE_GROUPS.map((g) => (
              <div key={g.title} className="rounded-xl border border-graphite-700/60 bg-graphite-850/50 p-3.5">
                <Badge tone={g.tone} size="sm" icon={g.icon}>
                  {g.title}
                </Badge>
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {g.items.map((it) => (
                    <span
                      key={it}
                      className="rounded-md border border-graphite-700/70 bg-graphite-900/70 px-2 py-1 font-mono text-[10px] font-semibold text-graphite-300"
                    >
                      {it}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* -------------------------------------------------- ML models --- */}
      <section className="space-y-4">
        <SectionTitle
          eyebrow="Modelling"
          title="Daily Forecasting Models"
          tone="violet"
          badge={`${MODEL_SUMMARY.length} committed artifacts`}
          description="Random Forest and type-specific LSTMs are the committed daily models. Metrics come from the API; only MAE is published for the LSTMs."
          actions={
            <Button as={Link} to="/model-performance" variant="ghost" size="sm">
              Open model performance <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          }
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {MODEL_SUMMARY.map((m) => (
            <Card key={m.name} accent={m.tone} hover className="flex h-full gap-3 p-4">
              <span
                className={cx(
                  'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border font-mono text-[11px] font-bold',
                  ICON_TONES[m.tone] || ICON_TONES.brand,
                )}
              >
                {m.short}
              </span>
              <div className="min-w-0">
                <p className="font-display text-sm font-bold text-white">{m.name}</p>
                <p className="text-[11px] font-semibold text-graphite-400">{m.family}</p>
                <p className="mt-1.5 text-xs leading-relaxed text-graphite-400">{m.note}</p>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------ Explainability --- */}
      <Card className="p-5 sm:p-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <div className="flex items-center gap-2.5">
              <IconTile icon={<ShieldCheck className="h-4 w-4" />} tone="violet" />
              <h2 className="font-display text-lg font-bold text-white">Explainability</h2>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-graphite-300">
              ENERVISION publishes the Random Forest&rsquo;s mean decrease in impurity (Gini importance) so the drivers
              behind the model are visible. This is not SHAP and not permutation importance; no local attribution or
              per-prediction contribution is published.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:col-span-2">
            {[
              { icon: Layers, label: 'Impurity importance', body: 'Mean decrease in impurity across the current 24 leakage-free features.', tone: 'brand' },
              { icon: LineChart, label: 'Provenance separation', body: 'Historical 25-feature values are labelled leakage-affected and non-comparable.', tone: 'wind' },
              { icon: Target, label: 'Honest limits', body: 'SHAP, permutation importance and per-prediction attribution are not claimed.', tone: 'solar' },
            ].map((e) => {
              const Ico = e.icon
              return (
                <div key={e.label} className="rounded-xl border border-graphite-700/60 bg-graphite-850/50 p-4">
                  <IconTile icon={<Ico className="h-4 w-4" />} tone={e.tone} />
                  <p className="mt-2.5 text-xs font-bold text-graphite-100">{e.label}</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-graphite-400">{e.body}</p>
                </div>
              )
            })}
          </div>
        </div>
      </Card>

      {/* -------------------------------------------------- Tech stack --- */}
      <section className="space-y-4">
        <SectionTitle
          eyebrow="Stack"
          title="Technology Stack"
          tone="brand"
          description="The frontend, data layer and research tooling used by the project."
        />
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {techStack.map((g) => {
            const Ico = TECH_ICONS[g.group] || BrainCircuit
            const tone = TECH_TONE[g.group] || 'brand'
            return (
              <Card key={g.group} accent={tone} hover className="flex h-full flex-col p-5">
                <div className="flex items-center gap-2.5">
                  <IconTile icon={<Ico className="h-4 w-4" />} tone={tone} />
                  <h3 className="font-display text-sm font-bold text-white">{g.group}</h3>
                </div>
                <ul className="mt-3 flex flex-wrap gap-1.5">
                  {g.items.map((it) => (
                    <li
                      key={it}
                      className="rounded-md border border-graphite-700/70 bg-graphite-900/70 px-2 py-1 text-[11px] font-semibold text-graphite-300"
                    >
                      {it}
                    </li>
                  ))}
                </ul>
              </Card>
            )
          })}
        </div>
      </section>

      {/* -------------------------------------------------- Future scope --- */}
      <section className="space-y-4">
        <SectionTitle eyebrow="Roadmap" title="Future Scope" tone="wind" badge={`${futureScope.length} directions`} />
        <Card className="p-5 sm:p-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {futureScope.map((f, i) => (
              <div key={f} className="flex gap-3 rounded-xl border border-graphite-700/60 bg-graphite-850/50 p-3.5">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-emerald-400/25 bg-emerald-400/10 text-emerald-300">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                </span>
                <div className="min-w-0">
                  <span className="font-mono text-[10px] font-bold uppercase tracking-wide text-graphite-500">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <p className="text-xs leading-relaxed text-graphite-300">{f}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>

      {/* -------------------------------------------------- Statement --- */}
      <div className="space-y-4">
        <Card className="border-2 border-dashed border-graphite-700 bg-graphite-900/40 p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-graphite-700/70 bg-graphite-900/80 text-graphite-400">
              <Target className="h-4 w-4" />
            </span>
            <div>
              <h3 className="font-display text-sm font-bold text-white">Statement on results</h3>
              <p className="mt-1 max-w-4xl text-xs leading-relaxed text-graphite-400">
                In demo mode (the default), every value presented in this interface is clearly labelled{' '}
                <strong>DEMO / ILLUSTRATIVE DATA — NOT FINAL RESEARCH RESULTS</strong> so that no unverified claim is
                presented as a research outcome. In live mode the interface instead shows committed backend metrics and
                daily forecasts — or an explicit error/unavailable state if the API or future weather is missing. It never
                falls back to demo values, never invents confidence intervals, and never presents the leakage-affected
                25-feature reference as current production performance.
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Badge tone="brand" size="sm">
                  API-ready
                </Badge>
                <span className="font-mono text-[11px] text-graphite-500">set VITE_API_BASE_URL to switch to live data</span>
              </div>
            </div>
          </div>
        </Card>

        <DemoNotice tone="amber" label="RESULTS PENDING">
          ENERVISION currently ships demonstration data. Point the frontend at the research backend by setting{' '}
          <span className="font-mono">VITE_API_BASE_URL</span> — no component changes are required when the final results land.
        </DemoNotice>
      </div>
    </div>
  )
}
