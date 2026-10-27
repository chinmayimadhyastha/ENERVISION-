/**
 * ============================================================================
 *  ENERVISION - API layer
 * ============================================================================
 *
 *  Single facade used by every page/component. Pages never import demo data
 *  directly and never call fetch() themselves.
 *
 *  Two strictly separated modes:
 *
 *   1. DEMO MODE (default)
 *      VITE_API_BASE_URL is empty -> responses are derived from ./mockData.js,
 *      wrapped in Promises with a small simulated latency. Every demo payload is
 *      labelled with `isDemo: true` so the UI can show a demo notice.
 *
 *   2. LIVE MODE
 *      VITE_API_BASE_URL points at the ENERVISION Flask API -> the same
 *      functions issue HTTP requests. There is NO demo fallback: failures are
 *      propagated as ApiError so pages render an honest error/empty state.
 *
 *  The Flask API is a DAILY forecasting API:
 *    target: DailyGeneration_MU   unit: MU/day
 *    horizon: 1-7 future days (default 3)
 *
 *  Endpoints (live):
 *    GET /api/health
 *    GET /api/plants
 *    GET /api/plants/<plant_id>
 *    GET /api/generation-history
 *    GET /api/weather
 *    GET /api/forecast
 *    GET /api/model-performance
 *    GET /api/feature-importance
 *    GET /api/dashboard
 *    GET /api/analytics
 *
 *  Responses are normalised into a single UI-facing shape so pages never have
 *  to know about snake_case backend fields. Missing backend fields are kept as
 *  null/'N/A' - they are never synthesised in live mode.
 * ============================================================================
 */

import { ENV, isLiveBackend } from '../utils/env.js'
import { dayOffsetLabel } from '../utils/format.js'
import * as mock from './mockData.js'

const JSON_HEADERS = { Accept: 'application/json' }
const DAY_MS = 86400000
const HORIZON_MAX_DAYS = 7

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function log(...args) {
  if (ENV.debug) console.info('[ENERVISION/api]', ...args)
}

function num(value) {
  // Treat missing/blank values as unknown rather than inventing a zero.
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function round(value, digits = 2) {
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  const f = 10 ** digits
  return Math.round(n * f) / f
}

function typeKey(value) {
  const v = String(value || '').toLowerCase()
  return v === 'solar' || v === 'wind' ? v : v || null
}

function isoDate(date) {
  const d = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(d.getTime())) return null
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function addDaysISO(iso, days) {
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return null
  d.setDate(d.getDate() + days)
  return isoDate(d)
}

function daysBetween(startISO, endISO) {
  const a = new Date(`${startISO}T00:00:00`).getTime()
  const b = new Date(`${endISO}T00:00:00`).getTime()
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null
  return Math.round((b - a) / DAY_MS)
}

/** Human label for a forecast date relative to the model base date. */
export { dayOffsetLabel }

/** Prettify backend feature keys, e.g. Generation_lag_1 -> Generation lag 1. */
export function prettifyFeatureName(key) {
  return String(key || '')
    .replace(/_/g, ' ')
    .replace(/\bMU\b/g, 'MU')
    .trim()
}

/* -------------------------------------------------------------------------- */
/*  Errors                                                                     */
/* -------------------------------------------------------------------------- */

const STATUS_FALLBACK = {
  400: 'The request was rejected by the ENERVISION API.',
  404: 'The requested resource was not found.',
  405: 'That request method is not allowed.',
  422: 'The requested data is not available.',
  500: 'The ENERVISION API encountered an internal error.',
  503: 'The ENERVISION model/report service is currently unavailable.',
}

/** Error raised by the live API layer. Never swallowed or replaced by demo data. */
export class ApiError extends Error {
  constructor(message, { endpoint, status, code, details, cause } = {}) {
    super(message)
    this.name = 'ApiError'
    this.endpoint = endpoint
    this.status = status
    this.code = code || null
    this.details = details || null
    if (cause !== undefined) this.cause = cause
  }

  /** Short, user-safe message for empty/error states. */
  get userMessage() {
    if (this.code === 'PLANT_NOT_FOUND') return 'Plant not found.'
    if (this.code === 'FUTURE_WEATHER_UNAVAILABLE') {
      return 'Future weather data is unavailable. Only observed historical weather can be served.'
    }
    if (this.code === 'WEATHER_PROVIDER_ERROR' || this.code === 'WEATHER_PROVIDER_INVALID') {
      return 'The future-weather provider failed. No forecast weather was generated.'
    }
    if (this.code === 'MODEL_SERVICE_UNAVAILABLE' || this.code === 'MODEL_INFERENCE_FAILED') {
      return 'The forecasting model is currently unavailable.'
    }
    if (this.code === 'REPORT_UNAVAILABLE' || this.code === 'REPORT_INVALID') {
      return 'The requested model report is unavailable.'
    }
    return this.message
  }
}

function apiPath(path) {
  const base = ENV.apiBaseUrl.replace(/\/+$/, '')
  const clean = path.startsWith('/') ? path : `/${path}`
  const withApi = clean.startsWith('/api/') || clean === '/api' ? clean : `/api${clean}`
  if (base.endsWith('/api')) return `${base}${withApi.slice(4)}`
  return `${base}${withApi}`
}

async function request(path, params = {}) {
  const url = new URL(apiPath(path))
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
  })

  let res
  try {
    res = await fetch(url.toString(), { headers: JSON_HEADERS })
  } catch (cause) {
    throw new ApiError(
      `Cannot reach the ENERVISION API at ${url.origin}. Check that the backend is running and CORS is configured.`,
      { endpoint: path, cause },
    )
  }

  if (!res.ok) {
    let code = null
    let message = null
    let details = null
    try {
      const body = await res.json()
      code = body?.error?.code ?? null
      message = body?.error?.message ?? null
      details = body?.error?.details ?? null
    } catch {
      // Non-JSON error body; fall back to a status-based message.
    }
    throw new ApiError(message || STATUS_FALLBACK[res.status] || `ENERVISION API request failed (${res.status}).`, {
      endpoint: path,
      status: res.status,
      code,
      details,
    })
  }

  try {
    return await res.json()
  } catch (cause) {
    throw new ApiError(`ENERVISION API returned an invalid JSON response for ${path}.`, {
      endpoint: path,
      cause,
    })
  }
}

/** Wrap a demo response so it behaves like a network call. */
async function demo(payload, label) {
  log('demo ->', label)
  if (ENV.demoLatency > 0) await delay(ENV.demoLatency)
  return payload
}

async function resolve(liveFn, demoFn, label) {
  if (isLiveBackend()) {
    log('live ->', label)
    return liveFn()
  }
  return demo(await demoFn(), label)
}

/* -------------------------------------------------------------------------- */
/*  Normalisation - plants                                                     */
/* -------------------------------------------------------------------------- */

function normalisePlant(raw) {
  if (!raw) return null
  const latestMU = num(raw.latest_generation_mu ?? raw.latestGenerationMU)
  return {
    id: raw.plant_id ?? raw.id,
    name: raw.plant_name ?? raw.name,
    type: typeKey(raw.type),
    district: raw.district ?? null,
    state: raw.state ?? 'Karnataka',
    owner: raw.owner ?? raw.operator ?? null,
    capacityMW: num(raw.capacity_mw ?? raw.capacityMW),
    lat: num(raw.latitude ?? raw.lat),
    lng: num(raw.longitude ?? raw.lng),
    hasCoordinates: Boolean(raw.has_coordinates ?? (num(raw.latitude ?? raw.lat) !== null && num(raw.longitude ?? raw.lng) !== null)),
    commissionDate: raw.commission_date ?? raw.commissioned ?? null,
    firstObserved: raw.first_observed_date ?? null,
    lastObserved: raw.last_observed_date ?? null,
    observations: num(raw.observations),
    latestGenerationMU: latestMU,
    latestGenerationDate: raw.latest_generation_date ?? null,
    isDemo: Boolean(raw.isDemo),
  }
}

function demoPlant(raw) {
  if (!raw) return null
  const capacity = num(raw.capacityMW) ?? 0
  const ccf = num(raw.ccf) ?? (raw.type === 'wind' ? 0.3 : 0.2)
  return {
    id: raw.id,
    name: raw.name,
    type: raw.type,
    district: raw.district,
    state: raw.state || 'Karnataka',
    owner: raw.operator || null,
    capacityMW: capacity,
    lat: num(raw.lat),
    lng: num(raw.lng),
    hasCoordinates: num(raw.lat) !== null && num(raw.lng) !== null,
    commissionDate: raw.commissioned ?? null,
    firstObserved: null,
    lastObserved: isoDate(mock.NOW),
    observations: null,
    latestGenerationMU: round((capacity * ccf * 24) / 1000, 2),
    latestGenerationDate: isoDate(mock.NOW),
    isDemo: true,
    // Demo-only metadata kept for the design showcase.
    taluk: raw.taluk ?? null,
    status: raw.status ?? null,
    ccf,
    panel: raw.panel ?? null,
    modules: raw.modules ?? null,
    turbine: raw.turbine ?? null,
    turbines: raw.turbines ?? null,
    hubHeight: raw.hubHeight ?? null,
    gridZone: raw.gridZone ?? null,
  }
}

/* -------------------------------------------------------------------------- */
/*  Normalisation - weather                                                    */
/* -------------------------------------------------------------------------- */

function normaliseWeatherPoint(row) {
  return {
    date: row.date,
    temperature: num(row.temperature),
    humidity: num(row.humidity),
    windSpeed: num(row.wind_speed ?? row.windSpeed),
    ghi: num(row.ghi),
    pressure: num(row.pressure),
    imputed: Boolean(row.weather_imputed ?? row.imputed),
    sentinelCount: num(row.source_sentinel_count ?? row.sentinelCount),
  }
}

function normaliseWeather(raw) {
  if (!raw) return null
  const data = Array.isArray(raw.data) ? raw.data.map(normaliseWeatherPoint) : []
  return {
    plantId: raw.plant_id ?? raw.plantId ?? null,
    plantName: raw.plant_name ?? raw.plantName ?? null,
    type: typeKey(raw.type),
    weatherType: raw.weather_type ?? raw.weatherType ?? 'historical',
    isForecast: Boolean(raw.is_forecast ?? raw.isForecast),
    source: raw.source ?? null,
    units: raw.units ?? { temperature: 'degC', humidity: '%', wind_speed: 'm/s', ghi: 'kWh/m2/day', pressure: 'kPa' },
    availableRange: raw.available_range ?? raw.availableRange ?? null,
    requestedRange: raw.requested_range ?? raw.requestedRange ?? null,
    effectiveRange: raw.effective_range ?? raw.effectiveRange ?? null,
    coverage: raw.coverage ?? null,
    futureWeather: raw.future_weather ?? raw.futureWeather ?? null,
    data,
    count: data.length,
    isDemo: Boolean(raw.isDemo ?? raw.is_demo),
  }
}

function weatherFromContext(ctx, plant) {
  if (!ctx) return null
  return {
    date: ctx.date,
    district: plant?.district || 'Karnataka',
    plantName: plant?.name || null,
    weatherType: ctx.weather_type || 'historical',
    isForecast: Boolean(ctx.is_forecast),
    temperature: num(ctx.temperature),
    humidity: num(ctx.humidity),
    windSpeed: num(ctx.wind_speed),
    ghi: num(ctx.ghi),
    pressure: num(ctx.pressure),
    ghiUnit: 'kWh/m²/day',
    source: ctx.source ?? null,
    isDemo: false,
  }
}

/* -------------------------------------------------------------------------- */
/*  Normalisation - history                                                    */
/* -------------------------------------------------------------------------- */

function normaliseHistory(raw) {
  if (!raw) return null
  const isPlant = raw.scope === 'plant'
  const rows = Array.isArray(raw.data) ? raw.data : Array.isArray(raw.points) ? raw.points : []
  const points = rows.map((row) => ({
    date: row.date,
    generationMU: num(
      isPlant
        ? (row.generation_mu ?? row.generationMU)
        : (row.total_generation_mu ?? row.generationMU),
    ),
    solarMU: num(row.solar_generation_mu ?? row.solarMU),
    windMU: num(row.wind_generation_mu ?? row.windMU),
    reportingPlants: num(row.reporting_plants ?? row.reportingPlants),
  }))
  const availableRange =
    raw.available_range ??
    raw.availableRange ??
    (points.length ? { start: points[0].date, end: points[points.length - 1].date } : null)
  return {
    scope: raw.scope ?? null,
    plantId: raw.plant_id ?? raw.plantId ?? null,
    plantName: raw.plant_name ?? raw.plantName ?? null,
    type: typeKey(raw.type),
    frequency: raw.frequency ?? 'daily',
    unit: raw.unit ?? 'MU/day',
    target: raw.target ?? 'DailyGeneration_MU',
    aggregation: raw.aggregation ?? null,
    requestedRange: raw.requested_range ?? raw.requestedRange ?? null,
    availableRange,
    coverage: raw.coverage ?? null,
    summary: raw.summary ?? null,
    points,
    count: points.length,
    notes: raw.notes ?? [],
    isDemo: Boolean(raw.isDemo ?? raw.is_demo),
  }
}

/* -------------------------------------------------------------------------- */
/*  Normalisation - forecast                                                   */
/* -------------------------------------------------------------------------- */

function normaliseForecast(raw) {
  if (!raw) return null
  const baseDate = raw.base_date ?? raw.baseDate ?? null
  // LIVE payloads expose `forecasts`; the demo adapter exposes the same shape as `points`.
  const forecasts = Array.isArray(raw.forecasts)
    ? raw.forecasts
    : Array.isArray(raw.points)
      ? raw.points
      : []
  const points = forecasts.map((f) => ({
    date: f.date,
    horizonDay:
      f.horizon_day ?? f.horizonDay ?? (baseDate ? daysBetween(baseDate, f.date) : null),
    label: dayOffsetLabel(baseDate, f.date),
    prediction: num(f.prediction),
    rawPrediction: num(f.raw_prediction ?? f.rawPrediction),
    clampApplied: Boolean(f.clamp_applied ?? f.clampApplied),
    confidence: null,
    unit: f.unit ?? 'MU/day',
  }))

  const values = points.map((p) => p.prediction).filter((v) => v !== null)
  const total = values.reduce((s, v) => s + v, 0)
  const peak = points.reduce((best, p) => (p.prediction !== null && (!best || p.prediction > best.prediction) ? p : best), null)
  const trough = points.reduce((best, p) => (p.prediction !== null && (!best || p.prediction < best.prediction) ? p : best), null)

  return {
    status: raw.status ?? 'ok',
    frequency: raw.frequency ?? 'daily',
    target: raw.target ?? 'DailyGeneration_MU',
    unit: raw.unit ?? 'MU/day',
    horizonDays: raw.horizon_days ?? points.length,
    modelRequested: raw.model_requested ?? raw.modelRequested ?? null,
    model: raw.model ?? null,
    modelFamily: raw.model_family ?? raw.modelFamily ?? null,
    plant: normalisePlant(raw.plant),
    baseDate,
    forecastDates: raw.forecast_dates ?? raw.forecastDates ?? points.map((p) => p.date),
    confidence: raw.confidence ?? null,
    confidenceNote: raw.confidence_note ?? raw.confidenceNote ?? null,
    inputContract: raw.input_contract ?? null,
    futureWeather: raw.future_weather ?? raw.futureWeather ?? null,
    postProcessing: raw.post_processing ?? null,
    historyContext: raw.history_context ?? null,
    requiredWeather: raw.required_weather ?? null,
    missingWeather: raw.required_weather?.missing ?? raw.missing_weather ?? [],
    missingWeatherSummary: raw.missing_weather_summary ?? raw.required_weather?.missing_weather_summary ?? null,
    insufficientHistory: raw.insufficient_history ?? null,
    reason: raw.reason ?? null,
    points,
    summary: {
      count: points.length,
      totalMU: values.length ? round(total, 3) : null,
      meanMU: values.length ? round(total / values.length, 3) : null,
      peakMU: peak?.prediction ?? null,
      peakDate: peak?.date ?? null,
      minMU: trough?.prediction ?? null,
      minDate: trough?.date ?? null,
      horizonDays: raw.horizon_days ?? raw.horizonDays ?? points.length,
      avgConfidence: null,
      uncertaintyMU: null,
    },
    notes: raw.notes ?? [],
    isDemo: Boolean(raw.isDemo ?? raw.is_demo),
  }
}

/* -------------------------------------------------------------------------- */
/*  Normalisation - analytics / dashboard / models                             */
/* -------------------------------------------------------------------------- */

function normaliseAnalytics(raw, { plants = [], dashboard = null } = {}) {
  if (!raw) return null
  const rows = Array.isArray(raw.generation_by_date) ? raw.generation_by_date : []
  const daily = rows.map((r) => ({
    date: r.date,
    solar: num(r.solar_generation_mu),
    wind: num(r.wind_generation_mu),
    total: num(r.total_generation_mu),
    reportingPlants: num(r.reporting_plants),
  }))

  const summary = raw.summary ?? {}
  const totalGenerationMU = num(summary.total_generation_mu)
  const solarGenerationMU = daily.reduce((s, r) => s + (r.solar || 0), 0)
  const windGenerationMU = daily.reduce((s, r) => s + (r.wind || 0), 0)

  const plantRows = (raw.generation_by_plant || []).map((p) => ({
    id: p.plant_id,
    name: p.plant_name,
    type: typeKey(p.type),
    capacityMW: num(p.capacity_mw),
    totalGenerationMU: num(p.total_generation_mu),
    meanDailyMU: num(p.mean_daily_generation_mu),
    perMWPerDay: num(p.generation_per_mw_per_day),
    observations: num(p.observations),
    firstObserved: p.first_observed_date ?? null,
    lastObserved: p.last_observed_date ?? null,
    district: plants.find((x) => x.id === p.plant_id)?.district ?? null,
  }))

  const capByType = dashboard?.capacity_by_type_mw ?? {}
  const totalCapacity = num(dashboard?.total_installed_capacity_mw)
  const solarCapacity = num(capByType.Solar)
  const windCapacity = num(capByType.Wind)

  return {
    scope: raw.scope ?? 'fleet',
    frequency: raw.frequency ?? 'daily',
    unit: raw.unit ?? 'MU/day',
    target: raw.target ?? 'DailyGeneration_MU',
    requestedRange: raw.requested_range ?? null,
    coverage: raw.coverage ?? null,
    summary: {
      totalGenerationMU,
      meanDailyMU: num(summary.mean_daily_generation_mu),
      minDailyMU: num(summary.min_daily_generation_mu),
      maxDailyMU: num(summary.max_daily_generation_mu),
      days: num(summary.days),
      plantDayObservations: num(summary.plant_day_observations),
      plants: num(summary.plants),
      capacityMW: num(summary.capacity_mw),
      solarGenerationMU: round(solarGenerationMU, 3),
      windGenerationMU: round(windGenerationMU, 3),
      solarSharePct: totalGenerationMU ? round((solarGenerationMU / totalGenerationMU) * 100, 1) : null,
      windSharePct: totalGenerationMU ? round((windGenerationMU / totalGenerationMU) * 100, 1) : null,
    },
    daily,
    byType: raw.generation_by_type ?? [],
    plants: plantRows,
    mix: [
      { name: 'Solar', value: solarCapacity, color: '#fbbf24' },
      { name: 'Wind', value: windCapacity, color: '#38bdf8' },
    ].filter((m) => m.value !== null),
    totalCapacityMW: totalCapacity,
    derivedMetrics: raw.derived_metrics ?? null,
    notes: raw.notes ?? [],
    isDemo: false,
  }
}

function buildInsight({ overview, daily, isDemo = false }) {
  if (!overview) return null
  const last = daily?.[daily.length - 1]
  const dominant = (overview.solarGenerationMU || 0) >= (overview.windGenerationMU || 0) ? 'Solar' : 'Wind'
  const dominantMU = Math.max(overview.solarGenerationMU || 0, overview.windGenerationMU || 0)
  const share = overview.totalGenerationMU ? round((dominantMU / overview.totalGenerationMU) * 100, 1) : null
  const coverage = overview.plantCount ? round((overview.reportingPlants / overview.plantCount) * 100, 0) : null
  return {
    headline: last
      ? `Daily fleet generation on ${last.date} was ${round(last.total, 2)} MU/day across ${overview.reportingPlants} reporting plants.`
      : null,
    dominantSource: dominant,
    dominantShare: share,
    bullets: [
      `${dominant} contributed ${share ?? 'N/A'}% of the latest observed daily generation.`,
      `Installed capacity is ${round(overview.totalCapacityMW, 0)} MW (${overview.solarPlantCount} solar, ${overview.windPlantCount} wind plants).`,
      `${overview.reportingPlants} of ${overview.plantCount} plants reported on ${overview.latestDate} (${coverage ?? 'N/A'}% coverage).`,
      isDemo
        ? 'Demo forecasts are illustrative and are not driven by a future-weather provider.'
        : 'Daily forecasts beyond one day require future weather inputs, which are not currently provided.',
    ],
    disclaimer: isDemo
      ? 'Illustrative demo values. In live mode these statistics are computed directly from the ENERVISION daily dataset.'
      : 'Descriptive statistics computed directly from the ENERVISION daily dataset. No values are interpolated or fabricated.',
  }
}

function normaliseModelPerformance(raw) {
  if (!raw) return null
  const rf = raw.models?.random_forest
  const solar = raw.models?.solar_lstm
  const wind = raw.models?.wind_lstm
  const rfCurrent = rf?.metrics?.current_leakage_free_24_feature ?? {}
  const models = [
    {
      id: 'random_forest',
      modelId: rf?.model_id ?? 'random_forest_daily',
      name: 'Random Forest',
      shortName: 'RF',
      family: 'Random Forest (production candidate)',
      status: rf?.status ?? null,
      featureCount: num(rf?.feature_count),
      sequenceLength: null,
      metrics: {
        mae: num(rfCurrent.MAE),
        rmse: num(rfCurrent.RMSE),
        r2: num(rfCurrent.R2),
        trainRows: num(rfCurrent.train_rows),
        testRows: num(rfCurrent.test_rows),
        plants: num(rfCurrent.plants),
        features: num(rfCurrent.features),
      },
      historical: rf?.metrics?.historical_25_feature_reference ?? null,
      description:
        'Chronological leakage-free daily Random Forest. The leaked Generation_per_MW feature and the prediction-day target are excluded from the 24 current inputs.',
      isDemo: false,
    },
    {
      id: 'solar_lstm',
      modelId: solar?.model_id ?? 'solar_lstm_daily',
      name: 'Solar LSTM',
      shortName: 'S-LSTM',
      family: 'Sequence model (solar)',
      status: solar?.status ?? null,
      featureCount: num(solar?.feature_count),
      sequenceLength: num(solar?.sequence_length),
      metrics: {
        mae: num(solar?.metrics?.committed_actual?.MAE),
        rmse: null,
        r2: null,
        trainRows: null,
        testRows: null,
        plants: null,
        features: num(solar?.feature_count),
      },
      historical: null,
      description: 'Committed solar LSTM artifact. Only MAE is published for this model; no other metrics are inferred.',
      isDemo: false,
    },
    {
      id: 'wind_lstm',
      modelId: wind?.model_id ?? 'wind_lstm_daily',
      name: 'Wind LSTM',
      shortName: 'W-LSTM',
      family: 'Sequence model (wind)',
      status: wind?.status ?? null,
      featureCount: num(wind?.feature_count),
      sequenceLength: num(wind?.sequence_length),
      metrics: {
        mae: num(wind?.metrics?.committed_actual?.MAE),
        rmse: null,
        r2: null,
        trainRows: null,
        testRows: null,
        plants: null,
        features: num(wind?.feature_count),
      },
      historical: null,
      description: 'Committed wind LSTM artifact. Only MAE is published for this model; no other metrics are inferred.',
      isDemo: false,
    },
  ]

  return {
    frequency: raw.frequency ?? 'daily',
    target: raw.target ?? 'DailyGeneration_MU',
    unit: raw.unit ?? 'MU/day',
    metricDefinitions: raw.metric_definitions ?? null,
    comparisonPolicy: raw.comparison_policy ?? null,
    models,
    ranking: [...models].sort((a, b) => {
      const av = a.metrics.mae
      const bv = b.metrics.mae
      if (av === null) return 1
      if (bv === null) return -1
      return av - bv
    }),
    notes: raw.notes ?? [],
    isDemo: Boolean(raw.is_demo),
  }
}

function normaliseFeatureImportance(raw) {
  if (!raw) return null
  const features = (raw.features || []).map((f, i) => ({
    rank: f.rank ?? i + 1,
    key: f.feature ?? f.key,
    label: f.label ?? prettifyFeatureName(f.feature ?? f.key),
    importance: num(f.importance),
  }))
  const hist = raw.historical_25_feature_reference
  return {
    modelId: raw.model_id ?? null,
    frequency: raw.frequency ?? 'daily',
    target: raw.target ?? 'DailyGeneration_MU',
    method: raw.method ?? 'random_forest_impurity',
    methodDescription: raw.method_description ?? null,
    shapUsed: Boolean(raw.shap_used),
    featureCount: num(raw.feature_count) ?? features.length,
    importanceSum: num(raw.importance_sum),
    features,
    historical: hist
      ? {
          method: hist.method ?? null,
          leakageAffected: Boolean(hist.leakage_affected),
          comparableToCurrent: Boolean(hist.comparable_to_current),
          note: hist.note ?? null,
          features: (hist.features || []).map((f, i) => ({
            rank: f.rank ?? i + 1,
            key: f.feature ?? f.key,
            label: f.label ?? prettifyFeatureName(f.feature ?? f.key),
            importance: num(f.importance),
          })),
        }
      : null,
    notes: raw.notes ?? [],
    isDemo: Boolean(raw.is_demo),
  }
}

/* -------------------------------------------------------------------------- */
/*  Demo generators (DEMO MODE ONLY)                                           */
/* -------------------------------------------------------------------------- */

function mulberry32(a) {
  return function next() {
    let t = (a += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function demoLatestDate() {
  return isoDate(mock.NOW)
}

function demoDailyGeneration(plant, days = 30) {
  const end = demoLatestDate()
  const baseCF = num(plant.ccf) ?? (plant.type === 'wind' ? 0.3 : 0.2)
  const seed = mock.hashSeed(`daily:${plant.id}`)
  const rnd = mulberry32(seed)
  const out = []
  for (let i = days - 1; i >= 0; i -= 1) {
    const date = addDaysISO(end, -i)
    const d = new Date(`${date}T12:00:00`)
    const season = mock.seasonalFactor(plant.type, d)
    const variation = 0.88 + rnd() * 0.24
    const mu = Math.max(0, ((plant.capacityMW || 0) * baseCF * season * variation * 24) / 1000)
    out.push({ date, generationMU: round(mu, 3) })
  }
  return out
}

function demoHistory(plant, days = 90, scope = 'plant') {
  if (scope === 'fleet' || scope === 'type') {
    const d = mock.getAnalytics({ period: 'daily' })
    const points = (d.series.all || []).map((b) => ({
      date: isoDate(b.t),
      generationMU: round(((b.total || 0) * 24) / 1000, 3),
      solarMU: round(((b.solar || 0) * 24) / 1000, 3),
      windMU: round(((b.wind || 0) * 24) / 1000, 3),
      reportingPlants: null,
    }))
    return {
      scope,
      plantId: null,
      plantName: null,
      type: scope === 'type' ? typeKey(plant?.type) : null,
      frequency: 'daily',
      unit: 'MU/day',
      target: 'DailyGeneration_MU',
      points,
      count: points.length,
      notes: ['Demo data.'],
      isDemo: true,
    }
  }
  const points = demoDailyGeneration(plant, days)
  return {
    scope: 'plant',
    plantId: plant.id,
    plantName: plant.name,
    type: plant.type,
    frequency: 'daily',
    unit: 'MU/day',
    target: 'DailyGeneration_MU',
    points,
    count: points.length,
    notes: ['Demo data.'],
    isDemo: true,
  }
}

function demoForecast(plant, horizon = 3) {
  const days = Math.max(1, Math.min(HORIZON_MAX_DAYS, Number(horizon) || 3))
  const baseDate = demoLatestDate()
  const baseCF = num(plant.ccf) ?? (plant.type === 'wind' ? 0.3 : 0.2)
  const seed = mock.hashSeed(`forecast:${plant.id}`)
  const rnd = mulberry32(seed)
  const points = []
  for (let h = 1; h <= days; h += 1) {
    const date = addDaysISO(baseDate, h)
    const d = new Date(`${date}T12:00:00`)
    const season = mock.seasonalFactor(plant.type, d)
    const variation = 0.9 + rnd() * 0.2
    const value = Math.max(0, ((plant.capacityMW || 0) * baseCF * season * variation * 24) / 1000)
    points.push({
      date,
      horizonDay: h,
      label: dayOffsetLabel(baseDate, date),
      prediction: round(value, 3),
      rawPrediction: round(value, 3),
      clampApplied: false,
      confidence: null,
      unit: 'MU/day',
    })
  }
  const values = points.map((p) => p.prediction)
  return {
    status: 'ok',
    frequency: 'daily',
    target: 'DailyGeneration_MU',
    unit: 'MU/day',
    horizonDays: days,
    modelRequested: 'demo',
    model: 'demo_daily',
    modelFamily: 'demo',
    plant: demoPlant(plant),
    baseDate,
    forecastDates: points.map((p) => p.date),
    confidence: null,
    confidenceNote: 'Demo mode. No calibrated probabilistic confidence is available.',
    futureWeather: { provider: 'demo', provider_available: false, is_forecast: false, required_for_this_request: false },
    points,
    summary: {
      count: points.length,
      totalMU: round(values.reduce((s, v) => s + v, 0), 3),
      meanMU: round(values.reduce((s, v) => s + v, 0) / values.length, 3),
      peakMU: Math.max(...values),
      peakDate: points[values.indexOf(Math.max(...values))]?.date ?? null,
      minMU: Math.min(...values),
      minDate: points[values.indexOf(Math.min(...values))]?.date ?? null,
      horizonDays: days,
      avgConfidence: null,
      uncertaintyMU: null,
    },
    notes: ['Demo forecast generated for interface demonstration only.'],
    isDemo: true,
  }
}

function demoWeather(plant, days = 30) {
  const end = demoLatestDate()
  const data = []
  for (let i = days - 1; i >= 0; i -= 1) {
    const date = addDaysISO(end, -i)
    const at = new Date(`${date}T12:00:00`)
    const w = mock.getWeatherForDistrict(plant.district || mock.DISTRICTS[0].name, at)
    data.push({
      date,
      // Daily means rather than the instantaneous noon sample: the backend
      // weather contract is a daily series, not hourly telemetry.
      temperature: round(w.temperature - 3, 1),
      humidity: round(Math.min(96, w.humidity + 10), 0),
      windSpeed: w.windSpeed,
      // `w.ghi` is modelled peak irradiance in W/m². Daily insolation
      // (kWh/m²/day) is numerically ~peak kW/m² for a Karnataka day.
      ghi: round(w.ghi / 1000, 2),
      pressure: round(w.pressure / 10, 1),
      imputed: false,
      sentinelCount: null,
    })
  }
  return {
    plantId: plant.id,
    plantName: plant.name,
    type: plant.type,
    weatherType: 'historical',
    isForecast: false,
    source: 'Demo weather generator (illustrative)',
    units: { temperature: 'degC', humidity: '%', wind_speed: 'm/s', ghi: 'kWh/m2/day', pressure: 'kPa' },
    availableRange: { start: data[0]?.date ?? null, end: data[data.length - 1]?.date ?? null },
    requestedRange: null,
    coverage: { requested_calendar_days: data.length, returned_observations: data.length, missing_calendar_days: 0 },
    futureWeather: {
      available: false,
      is_forecast: false,
      provider: 'demo',
      message: 'Demo mode has no future weather provider.',
    },
    data,
    count: data.length,
    isDemo: true,
  }
}

function demoPlants() {
  return mock.getPlantSummaries().map(demoPlant)
}

function demoDashboard() {
  const raw = mock.getDashboardData()
  const plants = demoPlants()
  const analytics = demoAnalytics({ days: 30 })
  const overviewRaw = raw.overview
  const latest = analytics.daily[analytics.daily.length - 1]
  const solarMU = round(((overviewRaw.solarGenerationMW || 0) * 24) / 1000, 2)
  const windMU = round(((overviewRaw.windGenerationMW || 0) * 24) / 1000, 2)
  const totalMU = round(solarMU + windMU, 2)
  const topDistricts = raw.topDistricts.map((d) => ({
    district: d.district,
    capacity: d.capacity,
    generationMU: round(((d.generation || 0) * 24) / 1000, 3),
    plants: d.plants,
  }))
  const overview = {
    plantCount: overviewRaw.plantCount,
    solarPlantCount: overviewRaw.solarPlantCount,
    windPlantCount: overviewRaw.windPlantCount,
    totalCapacityMW: overviewRaw.totalCapacityMW,
    solarCapacityMW: overviewRaw.solarCapacityMW,
    windCapacityMW: overviewRaw.windCapacityMW,
    latestDate: latest?.date ?? demoLatestDate(),
    totalGenerationMU: totalMU,
    solarGenerationMU: solarMU,
    windGenerationMU: windMU,
    reportingPlants: overviewRaw.plantCount,
    coveragePct: 100,
  }
  return {
    meta: { generatedAt: raw.meta.generatedAt, asOfDate: overview.latestDate, frequency: 'daily', target: 'DailyGeneration_MU', unit: 'MU/day', isLive: false },
    overview,
    mix: raw.mix.map((m) => ({ name: m.name, value: m.value, color: m.color })),
    plants,
    daily: analytics.daily,
    topDistricts,
    latestWeather: {
      date: overview.latestDate,
      district: 'Karnataka (fleet mean)',
      temperature: 26.4,
      humidity: 62,
      windSpeed: 5.2,
      ghi: 5.4,
      pressure: 100.4,
      ghiUnit: 'kWh/m²/day',
      weatherType: 'historical',
      isForecast: false,
      isDemo: true,
    },
    forecastStatus: {
      futureWeather: { future_weather_available: false, provider: 'unavailable' },
      randomForestForecastAvailable: false,
      oneDayLstmForecastAvailable: true,
      multiDayLstmForecastAvailable: false,
      defaultHorizonDays: 3,
      maxHorizonDays: 7,
    },
    dataCoverage: null,
    insight: buildInsight({
      overview,
      daily: analytics.daily,
      isDemo: true,
    }),
    notes: ['Demo mode: illustrative data only.'],
    isDemo: true,
  }
}

function demoAnalytics({ days = 30 } = {}) {
  const raw = mock.getAnalytics({ period: 'daily', buckets: days })
  const daily = (raw.series.all || []).map((b) => ({
    date: isoDate(b.t),
    solar: round(((b.solar || 0) * 24) / 1000, 3),
    wind: round(((b.wind || 0) * 24) / 1000, 3),
    total: round(((b.total || 0) * 24) / 1000, 3),
    reportingPlants: raw.kpis.plantCount ?? null,
  }))
  const solarTotal = daily.reduce((s, r) => s + (r.solar || 0), 0)
  const windTotal = daily.reduce((s, r) => s + (r.wind || 0), 0)
  const total = solarTotal + windTotal
  const totals = daily.map((r) => r.total).filter((v) => v !== null)
  const plantRows = (raw.plantComparison || []).map((p) => ({
    id: p.id,
    name: p.name,
    type: p.type,
    capacityMW: p.capacityMW,
    totalGenerationMU: round(((p.currentGenerationMW || 0) * 24) / 1000, 3),
    meanDailyMU: round(((p.currentGenerationMW || 0) * 24) / 1000, 3),
    perMWPerDay: p.capacityMW ? round((p.currentGenerationMW || 0) / p.capacityMW, 5) : null,
    observations: daily.length,
    firstObserved: daily[0]?.date ?? null,
    lastObserved: daily[daily.length - 1]?.date ?? null,
    district: p.district,
  }))
  return {
    scope: 'fleet',
    frequency: 'daily',
    unit: 'MU/day',
    target: 'DailyGeneration_MU',
    requestedRange:
      daily.length > 0
        ? { start: daily[0].date, end: daily[daily.length - 1].date }
        : null,
    coverage:
      daily.length > 0
        ? {
            calendar_days: daily.length,
            dates_observed: daily.length,
            missing_calendar_days: 0,
            plant_day_observations: daily.length * (raw.kpis.plantCount || 0),
          }
        : null,
    summary: {
      totalGenerationMU: round(total, 3),
      meanDailyMU: daily.length ? round(total / daily.length, 3) : null,
      minDailyMU: totals.length ? Math.min(...totals) : null,
      maxDailyMU: totals.length ? Math.max(...totals) : null,
      days: daily.length,
      plantDayObservations: daily.length * (raw.kpis.plantCount || 0),
      plants: raw.kpis.plantCount,
      capacityMW: raw.kpis.totalCapacityMW,
      solarGenerationMU: round(solarTotal, 3),
      windGenerationMU: round(windTotal, 3),
      solarSharePct: total ? round((solarTotal / total) * 100, 1) : null,
      windSharePct: total ? round((windTotal / total) * 100, 1) : null,
    },
    daily,
    byType: [],
    plants: plantRows,
    mix: raw.mix,
    totalCapacityMW: raw.kpis.totalCapacityMW,
    derivedMetrics: null,
    notes: ['Demo data.'],
    isDemo: true,
  }
}

function demoModelPerformance() {
  return {
    is_demo: true,
    frequency: 'daily',
    target: 'DailyGeneration_MU',
    unit: 'MU/day',
    metric_definitions: {
      MAE: 'Illustrative mean absolute error in MU/day (demo data).',
      RMSE: 'Illustrative root mean squared error in MU/day (demo data).',
      R2: 'Illustrative coefficient of determination (demo data).',
    },
    comparison_policy: {
      historical_25_feature_metrics_comparable_to_current: false,
      reason:
        'Demo mode. The historical 25-feature reference included the leaked Generation_per_MW feature and is not comparable to the current 24-feature model.',
      current_random_forest_features: 24,
      historical_random_forest_features: 25,
    },
    models: {
      random_forest: {
        model_id: 'demo_random_forest_daily',
        status: 'demo_only',
        feature_count: 24,
        metrics: {
          current_leakage_free_24_feature: {
            MAE: 1.62,
            RMSE: 2.71,
            R2: 0.91,
            train_rows: null,
            test_rows: null,
            plants: null,
            features: 24,
          },
          historical_25_feature_reference: {
            MAE: 1.38,
            leakage_affected: true,
            comparable_to_current_24_feature_model: false,
            usage: 'provenance only',
          },
        },
      },
      solar_lstm: {
        model_id: 'demo_solar_lstm_daily',
        status: 'demo_only',
        feature_count: null,
        sequence_length: 30,
        metrics: { committed_actual: { MAE: 1.74 } },
      },
      wind_lstm: {
        model_id: 'demo_wind_lstm_daily',
        status: 'demo_only',
        feature_count: null,
        sequence_length: 30,
        metrics: { committed_actual: { MAE: 2.13 } },
      },
    },
    notes: ['Demo mode: illustrative metrics for interface review only. Not final research results.'],
  }
}

function demoFeatureImportance() {
  const raw = mock.getFeatureImportance({ modelId: 'demo_random_forest_daily', type: 'solar' })
  return {
    is_demo: true,
    model_id: 'demo_random_forest_daily',
    frequency: 'daily',
    target: 'DailyGeneration_MU',
    method: 'random_forest_impurity',
    method_description: 'Demo importance values. The live API reports mean decrease in impurity; SHAP is not used.',
    shap_used: false,
    feature_count: raw.features.length,
    importance_sum: null,
    features: raw.features.map((f) => ({ feature: f.key, label: f.label, importance: f.importance })),
    notes: ['Demo mode: illustrative feature importance. Not final research results.'],
  }
}

/* -------------------------------------------------------------------------- */
/*  Public API                                                                 */
/* -------------------------------------------------------------------------- */

export function getHealth() {
  return resolve(
    () => request('/health'),
    () => ({
      status: 'demo',
      service: 'ENERVISION frontend demo mode',
      loaded: true,
      forecasting_contract: {
        frequency: 'daily',
        target: 'DailyGeneration_MU',
        unit: 'MU/day',
        default_horizon_days: 3,
        max_horizon_days: 7,
        hourly_forecasting: false,
      },
      future_weather: { future_weather_available: false, provider: 'unavailable' },
      isDemo: true,
    }),
    'getHealth',
  )
}

export function getDashboardData() {
  return resolve(
    async () => {
      // One dashboard read anchors every derived date range; plants and the
      // trailing 30-day analytics window are then fetched concurrently.
      const dash = await request('/dashboard')
      const [plantsRaw, analyticsRaw] = await Promise.all([
        request('/plants'),
        request('/analytics', {
          start_date: addDaysISO(dash.as_of_date, -29),
          end_date: dash.as_of_date,
        }),
      ])
      const plants = (plantsRaw.plants || []).map(normalisePlant)
      const analytics = normaliseAnalytics(analyticsRaw, { plants, dashboard: dash })
      const latest = dash.latest_generation || {}
      const capacityByType = dash.capacity_by_type_mw || {}
      const overview = {
        plantCount: num(dash.total_plants),
        solarPlantCount: num(dash.solar_plant_count),
        windPlantCount: num(dash.wind_plant_count),
        totalCapacityMW: num(dash.total_installed_capacity_mw),
        solarCapacityMW: num(capacityByType.Solar),
        windCapacityMW: num(capacityByType.Wind),
        latestDate: latest.date ?? dash.as_of_date ?? null,
        totalGenerationMU: num(latest.total_generation_mu),
        solarGenerationMU: num(latest.solar_generation_mu),
        windGenerationMU: num(latest.wind_generation_mu),
        reportingPlants: num(latest.reporting_plants),
        coveragePct:
          num(dash.total_plants) && num(latest.reporting_plants)
            ? round((num(latest.reporting_plants) / num(dash.total_plants)) * 100, 0)
            : null,
      }
      const topDistricts = Object.values(
        plants.reduce((acc, p) => {
          if (!p.district) return acc
          acc[p.district] = acc[p.district] || { district: p.district, capacity: 0, generationMU: 0, plants: 0 }
          acc[p.district].capacity += p.capacityMW || 0
          acc[p.district].generationMU += p.latestGenerationMU || 0
          acc[p.district].plants += 1
          return acc
        }, {}),
      )
        .map((d) => ({
          ...d,
          capacity: round(d.capacity, 1),
          generationMU: round(d.generationMU, 3),
        }))
        .sort((a, b) => b.capacity - a.capacity)

      const context = dash.latest_weather_context
      const latestWeather = context
        ? {
            date: context.date,
            district: 'Karnataka (fleet mean)',
            temperature: num(context.temperature),
            humidity: num(context.humidity),
            windSpeed: num(context.wind_speed),
            ghi: num(context.ghi),
            pressure: num(context.pressure),
            ghiUnit: 'kWh/m²/day',
            weatherType: context.weather_type || 'historical',
            isForecast: Boolean(context.is_forecast),
            reportingPlants: num(context.reporting_plants),
            source: 'Observed fleet-mean weather on the latest reporting date',
            isDemo: false,
          }
        : null

      const forecastStatus = {
        futureWeather: dash.forecast_status?.future_weather ?? null,
        randomForestForecastAvailable: Boolean(dash.forecast_status?.random_forest_forecast_available),
        oneDayLstmForecastAvailable: Boolean(dash.forecast_status?.one_day_lstm_forecast_available),
        multiDayLstmForecastAvailable: Boolean(dash.forecast_status?.multi_day_lstm_forecast_available),
        defaultHorizonDays: num(dash.forecast_status?.default_horizon_days),
        maxHorizonDays: num(dash.forecast_status?.max_horizon_days),
      }

      return {
        meta: {
          generatedAt: dash.as_of_date,
          asOfDate: dash.as_of_date,
          frequency: 'daily',
          target: 'DailyGeneration_MU',
          unit: 'MU/day',
          isLive: true,
        },
        overview,
        mix: [
          { name: 'Solar', value: overview.solarCapacityMW, color: '#fbbf24' },
          { name: 'Wind', value: overview.windCapacityMW, color: '#38bdf8' },
        ].filter((m) => m.value !== null),
        plants,
        daily: analytics.daily,
        topDistricts,
        latestWeather,
        forecastStatus,
        dataCoverage: dash.data_coverage ?? null,
        insight: buildInsight({ overview, daily: analytics.daily }),
        notes: dash.notes ?? [],
        isDemo: false,
      }
    },
    demoDashboard,
    'getDashboardData',
  )
}

export function getPlants(filters = {}) {
  return resolve(
    async () => {
      const raw = await request('/plants', { type: filters.type, district: filters.district })
      return (raw.plants || []).map(normalisePlant)
    },
    () => demoPlants(),
    'getPlants',
  )
}

export function getPlantById(id) {
  return resolve(
    async () => {
      const raw = await request(`/plants/${encodeURIComponent(id)}`)
      const plant = normalisePlant(raw.plant)
      const recent = raw.recent_generation?.data || []
      const latest = raw.latest_generation
      return {
        ...plant,
        latestGenerationMU: num(latest?.generation_mu) ?? plant?.latestGenerationMU ?? null,
        latestGenerationDate: latest?.date ?? plant?.latestGenerationDate ?? null,
        unit: latest?.unit ?? 'MU/day',
        recentGeneration: {
          count: recent.length,
          points: recent.map((r) => ({ date: r.date, generationMU: num(r.generation_mu) })),
        },
        weatherContext: raw.weather_context
          ? {
              date: raw.weather_context.date,
              weatherType: raw.weather_context.weather_type,
              isForecast: Boolean(raw.weather_context.is_forecast),
              temperature: num(raw.weather_context.temperature),
              humidity: num(raw.weather_context.humidity),
              windSpeed: num(raw.weather_context.wind_speed),
              ghi: num(raw.weather_context.ghi),
              pressure: num(raw.weather_context.pressure),
              source: raw.weather_context.source ?? null,
            }
          : null,
        forecastCapability: raw.forecast_capability ?? null,
        isDemo: false,
      }
    },
    () => {
      const raw = mock.getPlantDetail(id)
      if (!raw) return null
      const plant = demoPlant(raw)
      const history = demoHistory(raw, 30)
      return {
        ...plant,
        unit: 'MU/day',
        observations: history.points.length,
        firstObserved: history.points[0]?.date ?? null,
        lastObserved: history.points[history.points.length - 1]?.date ?? null,
        latestGenerationMU: history.points[history.points.length - 1]?.generationMU ?? null,
        latestGenerationDate: history.points[history.points.length - 1]?.date ?? null,
        recentGeneration: { count: history.points.length, points: history.points.slice(-8) },
        weatherContext: (() => {
          // Use a fixed local-noon sample on the latest demo day so the demo
          // weather card does not drift with the viewer's clock time.
          const date = demoLatestDate()
          const w = mock.getWeatherForDistrict(raw.district, new Date(`${date}T12:00:00`))
          return {
            date,
            weatherType: 'historical',
            isForecast: false,
            temperature: round(w.temperature - 3, 1),
            humidity: round(Math.min(96, w.humidity + 10), 0),
            windSpeed: w.windSpeed,
            ghi: round(w.ghi / 1000, 2),
            pressure: round(w.pressure / 10, 1),
            source: 'Demo weather generator',
          }
        })(),
        forecastCapability: {
          frequency: 'daily',
          unit: 'MU/day',
          horizon_default_days: 3,
          horizon_max_days: 7,
          demo_forecast_available: true,
          future_weather: { future_weather_available: false, provider: 'unavailable' },
          random_forest: {
            available: false,
            reason: 'Demo mode shows an illustrative forecast rather than the committed Random Forest artifact.',
          },
          lstm: {
            one_day_horizon_available: false,
            multi_day_horizon_available: false,
            reason: 'Demo mode does not execute the committed LSTM artifacts.',
          },
        },
        isDemo: true,
      }
    },
    `getPlantById(${id})`,
  )
}

export function getForecast(params = {}) {
  const plantId = params.plantId ?? params.plant_id
  const horizon = Math.max(1, Math.min(HORIZON_MAX_DAYS, Math.trunc(Number(params.horizon) || 3)))
  const model = params.model || 'auto'
  const baseDate = params.baseDate ?? params.base_date

  return resolve(
    () => request('/forecast', { plant_id: plantId, model, horizon, base_date: baseDate }),
    () => {
      const plant = mock.findPlant(plantId) || mock.PLANTS[0]
      return demoForecast(plant, horizon)
    },
    `getForecast(${plantId}, ${model}, ${horizon}d)`,
  ).then(normaliseForecast)
}

export function getGenerationHistory(params = {}) {
  const plantId = params.plantId ?? params.plant_id
  const type = params.type
  const startDate = params.startDate ?? params.start_date
  const endDate = params.endDate ?? params.end_date

  return resolve(
    () => request('/generation-history', { plant_id: plantId, type, start_date: startDate, end_date: endDate }),
    () => {
      const plant = plantId ? mock.findPlant(plantId) : null
      return demoHistory(plant, params.days ?? 90, plantId ? 'plant' : type ? 'type' : 'fleet')
    },
    `getGenerationHistory(${plantId || type || 'fleet'})`,
  ).then(normaliseHistory)
}

export function getWeather(params = {}) {
  const plantId = params.plantId ?? params.plant_id
  const startDate = params.startDate ?? params.start_date
  const endDate = params.endDate ?? params.end_date

  return resolve(
    () => request('/weather', { plant_id: plantId, start_date: startDate, end_date: endDate }),
    () => {
      const plant = mock.findPlant(plantId) || mock.PLANTS[0]
      return demoWeather(plant, params.days ?? 30)
    },
    `getWeather(${plantId})`,
  ).then(normaliseWeather)
}

export function getAnalytics(params = {}) {
  const period = params.period || '90d'
  const days = period === '7d' ? 7 : period === '30d' ? 30 : period === '365d' ? 365 : 90
  const plantId = params.plantId ?? params.plant_id
  const type = params.type

  return resolve(
    async () => {
      const [dash, plantsRaw] = await Promise.all([request('/dashboard'), request('/plants')])
      const endDate = dash.as_of_date
      const startDate = addDaysISO(endDate, -(days - 1))
      const raw = await request('/analytics', {
        plant_id: plantId,
        type,
        start_date: startDate,
        end_date: endDate,
      })
      const plants = (plantsRaw.plants || []).map(normalisePlant)
      return normaliseAnalytics(raw, { plants, dashboard: dash })
    },
    () => demoAnalytics({ days }),
    `getAnalytics(${period})`,
  )
}

export function getModelPerformance() {
  return resolve(
    () => request('/model-performance'),
    demoModelPerformance,
    'getModelPerformance',
  ).then(normaliseModelPerformance)
}

export function getFeatureImportance(params = {}) {
  return resolve(
    () => request('/feature-importance'),
    demoFeatureImportance,
    'getFeatureImportance',
  ).then(normaliseFeatureImportance)
}

/* -------------------------------------------------------------------------- */
/*  Synchronous reference data (presentation metadata, never plant data)       */
/* -------------------------------------------------------------------------- */

export const referenceData = {
  districts: mock.DISTRICTS,
  types: [
    { value: 'all', label: 'All Types' },
    { value: 'solar', label: 'Solar' },
    { value: 'wind', label: 'Wind' },
  ],
  sorts: [
    { value: 'capacity-desc', label: 'Capacity (High -> Low)' },
    { value: 'capacity-asc', label: 'Capacity (Low -> High)' },
    { value: 'generation-desc', label: 'Latest daily generation (High -> Low)' },
    { value: 'name-asc', label: 'Name (A -> Z)' },
    { value: 'name-desc', label: 'Name (Z -> A)' },
  ],
  dataSources: mock.DATA_SOURCES,
  techStack: mock.TECH_STACK,
  architecture: mock.ARCHITECTURE_STEPS,
  objectives: mock.OBJECTIVES,
  problemStatement: mock.PROBLEM_STATEMENT,
  futureScope: mock.FUTURE_SCOPE,
}

export { isLiveBackend }
export const API_MODE = isLiveBackend() ? 'live' : 'demo'
export const API_BASE_URL = ENV.apiBaseUrl
