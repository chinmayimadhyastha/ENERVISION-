/**
 * Cross-cutting constants: chart palette, navigation model, status/type
 * metadata and geographic aliases. Single source of truth for the UI.
 *
 * Palette is tuned for the dark graphite "mission control" surface.
 */

export const PALETTE = {
  brand: '#0f766e',
  brandDeep: '#047857',
  solar: '#d97706',
  solarSoft: '#f59e0b',
  wind: '#0284c7',
  windSoft: '#38bdf8',
  actual: '#0f766e',
  forecast: '#7c3aed',
  forecastSoft: '#a78bfa',
  violet: '#7c3aed',
  grid: 'rgba(148, 163, 184, 0.22)',
  axis: '#64748b',
  tick: '#475569',
  danger: '#e11d48',
  warning: '#d97706',
  success: '#059669',
  ink: '#0f172a',
}

export const CHART_MARGIN = { top: 8, right: 12, bottom: 0, left: -10 }

/** Shared Recharts axis/grid styling for the dark theme. */
export const AXIS_PROPS = {
  stroke: PALETTE.axis,
  tick: { fill: PALETTE.tick, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: PALETTE.grid },
}

export const GRID_PROPS = {
  stroke: PALETTE.grid,
  strokeDasharray: '3 5',
  vertical: false,
}

export const RENEWABLE_TYPES = {
  solar: {
    label: 'Solar',
    short: 'Solar',
    color: PALETTE.solar,
    soft: PALETTE.solarSoft,
    icon: 'sun',
    accent: 'solar',
    ring: 'ring-solar-400/30',
  },
  wind: {
    label: 'Wind',
    short: 'Wind',
    color: PALETTE.wind,
    soft: PALETTE.windSoft,
    icon: 'wind',
    accent: 'wind',
    ring: 'ring-wind-400/30',
  },
}

export const PLANT_STATUS = {
  operational: { label: 'Operational', tone: 'success' },
  'partial-outage': { label: 'Partial Outage', tone: 'warning' },
  maintenance: { label: 'Maintenance', tone: 'info' },
  offline: { label: 'Offline', tone: 'danger' },
}

/**
 * Canonicalises a district name so mock-data districts and the simplified
 * boundary dataset (older spellings) resolve to the same key.
 */
const DISTRICT_ALIASES = {
  bagalkote: 'bagalkot',
  belagavi: 'belgaum',
  ballari: 'bellary',
  vijayapura: 'bijapur',
  kalaburagi: 'gulbarga',
  shivamogga: 'shimoga',
  mysuru: 'mysore',
  tumakuru: 'tumkur',
  chikkamagaluru: 'chikmagalur',
  chikkaballapura: 'kolar',
  'bengaluru rural': 'bangalore rural',
  'bengaluru urban': 'bangalore urban',
  'dakshina kannada': 'dakshin kannad',
  'uttara kannada': 'uttar kannand',
}

export function canonicalDistrict(name) {
  if (!name) return ''
  const key = String(name).trim().toLowerCase()
  return DISTRICT_ALIASES[key] || key
}

export const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: 'LayoutDashboard', end: true },
  { to: '/plants', label: 'Plants', icon: 'Factory' },
  { to: '/forecast', label: 'Forecast', icon: 'LineChart' },
  { to: '/analytics', label: 'Analytics', icon: 'BarChart3' },
  { to: '/model-performance', label: 'Model Performance', icon: 'BrainCircuit' },
  { to: '/about', label: 'About ENERVISION', icon: 'Info' },
]

export const FORECAST_HORIZONS = [
  { value: 1, label: '1 day' },
  { value: 2, label: '2 days' },
  { value: 3, label: '3 days' },
  { value: 4, label: '4 days' },
  { value: 5, label: '5 days' },
  { value: 6, label: '6 days' },
  { value: 7, label: '7 days' },
]

export const FORECAST_MODELS = [
  { value: 'auto', label: 'Auto (LSTM by plant type)' },
  { value: 'rf', label: 'Random Forest' },
  { value: 'lstm', label: 'LSTM (type-specific)' },
]

export const ANALYTICS_PERIODS = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
  { value: '365d', label: '365 days' },
]

/**
 * Narrative labels for the daily model inputs described on the About page.
 * Live feature importance always uses the API-provided feature names.
 */
export const FEATURE_LABELS = {
  ghi: 'GHI (daily irradiance)',
  temperature: 'Temperature',
  humidity: 'Humidity',
  windSpeed: 'Wind Speed',
  rainfall: 'Rainfall',
  pressure: 'Pressure',
  prevGeneration: 'Previous-day Generation',
  rollingGeneration: 'Rolling Generation (daily mean)',
  dayOfYear: 'Day of Year',
  month: 'Month',
  season: 'Season',
}
