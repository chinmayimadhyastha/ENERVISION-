/**
 * ============================================================================
 *  ENERVISION — Centralised demo / placeholder data layer
 * ============================================================================
 *
 *  IMPORTANT (project rule)
 *  ---------------------------------------------------------------------------
 *  The ENERVISION research results are NOT final yet. Every number produced
 *  here is *DEMO / PLACEHOLDER* data, generated deterministically so the UI is
 *  stable and reproducible. Nothing in this file should be quoted as an actual
 *  research finding.
 *
 *  All values are derived from a deterministic seeded PRNG — NOT Math.random()
 *  inside components — so charts, tables and KPIs always agree with each other.
 *
 *  When the real backend is available set VITE_API_BASE_URL and the API layer
 *  (src/services/api.js) will serve live data instead of this file, with no
 *  component changes.
 *
 *  Physical model used for the demo signal (documented, so it can be replaced):
 *    Solar  : clear-sky bell curve (06:15–18:25) × seasonal factor × cloud
 *             attenuation × smooth noise.
 *    Wind   : base capacity factor × diurnal cycle × monsoon seasonal factor ×
 *             smooth noise.
 *  Model "skill" is emulated by shrinking the noise and persistence error of
 *  the forecast relative to the actual series.
 * ============================================================================
 */

/* -------------------------------------------------------------------------- */
/*  Deterministic PRNG helpers                                                 */
/* -------------------------------------------------------------------------- */

export function hashSeed(str) {
  let h = 2166136261
  for (let i = 0; i < String(str).length; i += 1) {
    h ^= String(str).charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function mulberry32(seed) {
  let a = seed >>> 0
  return function next() {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Smooth, continuous pseudo-noise (in [-1, 1]) so series don't look ragged. */
function smoothNoise(seed, t) {
  const r = mulberry32(seed)
  const p1 = r() * Math.PI * 2
  const p2 = r() * Math.PI * 2
  const f1 = 0.25 + r() * 0.35
  const f2 = 0.9 + r() * 1.1
  return 0.68 * Math.sin(t * f1 + p1) + 0.32 * Math.sin(t * f2 + p2)
}

function round(value, digits = 1) {
  const f = 10 ** digits
  return Math.round(value * f) / f
}

/* -------------------------------------------------------------------------- */
/*  Reference clock                                                            */
/* -------------------------------------------------------------------------- */

export const NOW = (() => {
  const d = new Date()
  d.setMinutes(0, 0, 0)
  return d
})()

/* -------------------------------------------------------------------------- */
/*  Karnataka districts — climate reference (indicative)                       */
/* -------------------------------------------------------------------------- */

export const DISTRICTS = [
  { name: 'Tumakuru', lat: 13.3392, lng: 77.114, tempBase: 27.5, humidityBase: 58, ghiBase: 5.85, windBase: 3.4, zone: 'South Interior' },
  { name: 'Bengaluru Rural', lat: 13.2845, lng: 77.6278, tempBase: 25.2, humidityBase: 64, ghiBase: 5.55, windBase: 3.6, zone: 'South Interior' },
  { name: 'Belagavi', lat: 15.8497, lng: 74.4977, tempBase: 25.8, humidityBase: 68, ghiBase: 5.45, windBase: 5.1, zone: 'North Interior' },
  { name: 'Kalaburagi', lat: 17.3297, lng: 76.8343, tempBase: 29.4, humidityBase: 48, ghiBase: 5.95, windBase: 4.6, zone: 'North Interior' },
  { name: 'Raichur', lat: 16.2076, lng: 77.3463, tempBase: 30.1, humidityBase: 46, ghiBase: 6.05, windBase: 4.2, zone: 'North Interior' },
  { name: 'Vijayapura', lat: 16.8302, lng: 75.71, tempBase: 29.8, humidityBase: 45, ghiBase: 6.0, windBase: 4.4, zone: 'North Interior' },
  { name: 'Hassan', lat: 13.0072, lng: 76.0962, tempBase: 23.9, humidityBase: 72, ghiBase: 5.25, windBase: 4.0, zone: 'Malnad / Southern' },
  { name: 'Mysuru', lat: 12.2958, lng: 76.6394, tempBase: 24.6, humidityBase: 70, ghiBase: 5.4, windBase: 3.2, zone: 'South Interior' },
  { name: 'Bidar', lat: 17.9104, lng: 77.5199, tempBase: 28.6, humidityBase: 50, ghiBase: 5.9, windBase: 4.3, zone: 'North Interior' },
  { name: 'Chitradurga', lat: 14.2251, lng: 76.398, tempBase: 27.1, humidityBase: 55, ghiBase: 5.75, windBase: 6.9, zone: 'Central Plateau' },
  { name: 'Gadag', lat: 15.4166, lng: 75.6167, tempBase: 27.8, humidityBase: 52, ghiBase: 5.8, windBase: 7.1, zone: 'North Interior' },
  { name: 'Ballari', lat: 15.1394, lng: 76.9214, tempBase: 28.9, humidityBase: 49, ghiBase: 5.9, windBase: 6.4, zone: 'East Plateau' },
  { name: 'Koppal', lat: 15.35, lng: 76.15, tempBase: 28.5, humidityBase: 50, ghiBase: 5.85, windBase: 6.2, zone: 'East Plateau' },
  { name: 'Davanagere', lat: 14.4644, lng: 75.9218, tempBase: 27.3, humidityBase: 57, ghiBase: 5.7, windBase: 6.6, zone: 'Central Plateau' },
  { name: 'Uttara Kannada', lat: 14.7936, lng: 74.6865, tempBase: 26.4, humidityBase: 78, ghiBase: 5.15, windBase: 6.0, zone: 'Coastal / Malnad' },
]

export function getDistrictMeta(name) {
  return DISTRICTS.find((d) => d.name === name) || DISTRICTS[0]
}

/* -------------------------------------------------------------------------- */
/*  Plant fleet — DEMO/PLACEHOLDER reference data                              */
/* -------------------------------------------------------------------------- */

/**
 * DEMO FLEET — 25 placeholder plant records.
 *
 * Names reflect well-known Karnataka renewable locations so the demo feels
 * realistic, and the record count mirrors the planned 25-asset research
 * registry so the interface stays consistent with the study scope. Capacities,
 * operators, coordinates, commissioning years and telemetry are PLACEHOLDER
 * values for UI development only — these are NOT the final research-dataset
 * records, and the map nodes are illustrative demo assets.
 */
const RAW_PLANTS = [
  // ---------------------------------------------------------------- SOLAR --
  { id: 'PVG-01', name: 'Pavagada Solar Park (Shakti Sthala)', type: 'solar', district: 'Tumakuru', taluk: 'Pavagada', lat: 14.1009, lng: 77.2801, capacityMW: 2050, commissioned: 2019, operator: 'KSPDCL', status: 'operational', ccf: 0.82, panel: 'Monocrystalline PERC, single-axis tracker', modules: 6100000 },
  { id: 'BLG-02', name: 'Belagavi Solar PV Park', type: 'solar', district: 'Belagavi', taluk: 'Belagavi', lat: 15.8497, lng: 74.4977, capacityMW: 480, commissioned: 2020, operator: 'KPCL', status: 'operational', ccf: 0.79, panel: 'Polycrystalline, fixed-tilt', modules: 1180000 },
  { id: 'KLB-03', name: 'Kalaburagi Solar Park', type: 'solar', district: 'Kalaburagi', taluk: 'Kalaburagi', lat: 17.3297, lng: 76.8343, capacityMW: 610, commissioned: 2021, operator: 'KREDL', status: 'operational', ccf: 0.84, panel: 'Bifacial, single-axis tracker', modules: 1320000 },
  { id: 'RCH-04', name: 'Raichur Solar PV Farm', type: 'solar', district: 'Raichur', taluk: 'Raichur', lat: 16.2076, lng: 77.3463, capacityMW: 385, commissioned: 2020, operator: 'KPCL', status: 'operational', ccf: 0.85, panel: 'Monocrystalline, single-axis tracker', modules: 880000 },
  { id: 'VJP-05', name: 'Vijayapura Solar Park', type: 'solar', district: 'Vijayapura', taluk: 'Vijayapura', lat: 16.8302, lng: 75.71, capacityMW: 540, commissioned: 2022, operator: 'KREDL', status: 'operational', ccf: 0.83, panel: 'Bifacial, single-axis tracker', modules: 1150000 },
  { id: 'HSN-06', name: 'Hassan Solar Photovoltaic Plant', type: 'solar', district: 'Hassan', taluk: 'Hassan', lat: 13.0072, lng: 76.0962, capacityMW: 300, commissioned: 2019, operator: 'KREDL', status: 'operational', ccf: 0.76, panel: 'Polycrystalline, fixed-tilt', modules: 700000 },
  { id: 'MYS-07', name: 'Mysuru Distributed Solar Cluster', type: 'solar', district: 'Mysuru', taluk: 'Mysuru', lat: 12.2958, lng: 76.6394, capacityMW: 210, commissioned: 2021, operator: 'CESC', status: 'operational', ccf: 0.74, panel: 'Rooftop + ground-mount hybrid', modules: 520000 },
  { id: 'BDR-08', name: 'Bidar Solar Park', type: 'solar', district: 'Bidar', taluk: 'Bidar', lat: 17.9104, lng: 77.5199, capacityMW: 260, commissioned: 2023, operator: 'KREDL', status: 'partial-outage', ccf: 0.82, panel: 'Monocrystalline, single-axis tracker', modules: 590000 },
  { id: 'YNK-09', name: 'Yelahanka Solar Photovoltaic Plant', type: 'solar', district: 'Bengaluru Rural', taluk: 'Devanahalli', lat: 13.2845, lng: 77.6278, capacityMW: 320, commissioned: 2018, operator: 'BESCOM', status: 'operational', ccf: 0.78, panel: 'Monocrystalline, fixed-tilt', modules: 760000 },
  { id: 'TMR-17', name: 'Sira Solar Farm', type: 'solar', district: 'Tumakuru', taluk: 'Sira', lat: 13.7419, lng: 76.904, capacityMW: 180, commissioned: 2022, operator: 'KREDL', status: 'operational', ccf: 0.8, panel: 'Monocrystalline, single-axis tracker', modules: 410000 },
  { id: 'KLB-18', name: 'Afzalpur Solar Farm', type: 'solar', district: 'Kalaburagi', taluk: 'Afzalpur', lat: 17.2033, lng: 76.3549, capacityMW: 140, commissioned: 2023, operator: 'KREDL', status: 'operational', ccf: 0.82, panel: 'Bifacial, single-axis tracker', modules: 320000 },
  { id: 'BLL-19', name: 'Siruguppa Solar Farm', type: 'solar', district: 'Ballari', taluk: 'Siruguppa', lat: 15.6311, lng: 76.8948, capacityMW: 165, commissioned: 2022, operator: 'KPCL', status: 'operational', ccf: 0.81, panel: 'Monocrystalline, fixed-tilt', modules: 380000 },
  { id: 'RCH-20', name: 'Sindhanur Solar Farm', type: 'solar', district: 'Raichur', taluk: 'Sindhanur', lat: 15.7779, lng: 76.7568, capacityMW: 150, commissioned: 2021, operator: 'KPCL', status: 'operational', ccf: 0.83, panel: 'Monocrystalline, single-axis tracker', modules: 345000 },
  { id: 'BLG-21', name: 'Gokak Solar Farm', type: 'solar', district: 'Belagavi', taluk: 'Gokak', lat: 16.1669, lng: 74.8239, capacityMW: 130, commissioned: 2022, operator: 'KREDL', status: 'operational', ccf: 0.78, panel: 'Polycrystalline, fixed-tilt', modules: 300000 },

  // ----------------------------------------------------------------- WIND --
  { id: 'CTD-10', name: 'Chitradurga Wind Cluster', type: 'wind', district: 'Chitradurga', taluk: 'Chitradurga', lat: 14.2251, lng: 76.398, capacityMW: 980, commissioned: 2017, operator: 'ReNew Power', status: 'operational', ccf: 0.34, turbine: 'Suzlon S111 · 2.1 MW', turbines: 466, hubHeight: 90 },
  { id: 'GDG-11', name: 'Gadag Wind Cluster (Kappatagudda Belt)', type: 'wind', district: 'Gadag', taluk: 'Gadag', lat: 15.4166, lng: 75.6167, capacityMW: 760, commissioned: 2016, operator: 'Suzlon Energy', status: 'operational', ccf: 0.36, turbine: 'Suzlon S97 · 2.0 MW', turbines: 380, hubHeight: 90 },
  { id: 'BLL-12', name: 'Ballari Wind Farm', type: 'wind', district: 'Ballari', taluk: 'Ballari', lat: 15.1394, lng: 76.9214, capacityMW: 640, commissioned: 2015, operator: 'Mytrah Energy', status: 'operational', ccf: 0.32, turbine: 'Gamesa G114 · 2.0 MW', turbines: 320, hubHeight: 84 },
  { id: 'KPL-13', name: 'Koppal Wind Farm', type: 'wind', district: 'Koppal', taluk: 'Koppal', lat: 15.35, lng: 76.15, capacityMW: 520, commissioned: 2018, operator: 'ReNew Power', status: 'maintenance', ccf: 0.33, turbine: 'Vestas V120 · 2.2 MW', turbines: 236, hubHeight: 92 },
  { id: 'DVG-14', name: 'Davanagere–Jagalur Wind Farm', type: 'wind', district: 'Davanagere', taluk: 'Jagalur', lat: 14.4644, lng: 75.9218, capacityMW: 580, commissioned: 2019, operator: 'Mytrah Energy', status: 'operational', ccf: 0.35, turbine: 'Siemens SWT-2.3 · 2.3 MW', turbines: 252, hubHeight: 95 },
  { id: 'UKN-15', name: 'Haliyal Wind Farm', type: 'wind', district: 'Uttara Kannada', taluk: 'Haliyal', lat: 14.7936, lng: 74.6865, capacityMW: 340, commissioned: 2020, operator: 'KPCL', status: 'operational', ccf: 0.3, turbine: 'Inox WT2000 · 2.0 MW', turbines: 170, hubHeight: 84 },
  { id: 'KLB-16', name: 'Kalaburagi Wind Belt (Sedam)', type: 'wind', district: 'Kalaburagi', taluk: 'Sedam', lat: 17.15, lng: 77.2, capacityMW: 420, commissioned: 2021, operator: 'Siemens Gamesa', status: 'operational', ccf: 0.31, turbine: 'SG 2.6-114 · 2.6 MW', turbines: 161, hubHeight: 92 },
  { id: 'CTD-22', name: 'Hosadurga Wind Farm', type: 'wind', district: 'Chitradurga', taluk: 'Hosadurga', lat: 13.7961, lng: 76.284, capacityMW: 300, commissioned: 2018, operator: 'ReNew Power', status: 'operational', ccf: 0.34, turbine: 'Suzlon S111 · 2.1 MW', turbines: 143, hubHeight: 90 },
  { id: 'GDG-23', name: 'Mundargi Wind Farm', type: 'wind', district: 'Gadag', taluk: 'Mundargi', lat: 15.2073, lng: 75.9026, capacityMW: 260, commissioned: 2017, operator: 'Suzlon Energy', status: 'operational', ccf: 0.35, turbine: 'Suzlon S97 · 2.0 MW', turbines: 130, hubHeight: 90 },
  { id: 'KPL-24', name: 'Kushtagi Wind Farm', type: 'wind', district: 'Koppal', taluk: 'Kushtagi', lat: 15.7561, lng: 76.196, capacityMW: 220, commissioned: 2019, operator: 'Mytrah Energy', status: 'operational', ccf: 0.33, turbine: 'Gamesa G114 · 2.0 MW', turbines: 110, hubHeight: 84 },
  { id: 'DVG-25', name: 'Channagiri Wind Farm', type: 'wind', district: 'Davanagere', taluk: 'Channagiri', lat: 14.0263, lng: 75.924, capacityMW: 240, commissioned: 2020, operator: 'ReNew Power', status: 'operational', ccf: 0.34, turbine: 'Siemens SWT-2.3 · 2.3 MW', turbines: 104, hubHeight: 95 },
]

export const PLANTS = RAW_PLANTS.map((p) => ({
  ...p,
  state: 'Karnataka',
  country: 'India',
  gridZone: getDistrictMeta(p.district).zone,
}))

export function findPlant(id) {
  return PLANTS.find((p) => p.id === id) || null
}

/* -------------------------------------------------------------------------- */
/*  Weather model (demo)                                                       */
/* -------------------------------------------------------------------------- */

export function getWeatherForDistrict(districtName, at = NOW) {
  const meta = getDistrictMeta(districtName)
  const seed = hashSeed(`weather:${districtName}:${at.toISOString().slice(0, 10)}`)
  const r = mulberry32(seed)
  const hour = at.getHours() + at.getMinutes() / 60

  const month = at.getMonth()
  const isMonsoon = month >= 5 && month <= 8
  const diurnal = Math.sin(((hour - 9) / 24) * Math.PI * 2)
  const cloudCover = round(Math.min(98, Math.max(2, (isMonsoon ? 58 : 30) + (r() - 0.5) * 46 + diurnal * 10)), 0)

  const temperature = round(meta.tempBase + diurnal * 4.6 + (r() - 0.5) * 1.8, 1)
  const humidity = round(Math.min(96, Math.max(22, meta.humidityBase + (isMonsoon ? 14 : 0) - diurnal * 12 + (r() - 0.5) * 8)), 0)

  const solarShape = Math.max(0, Math.sin((Math.PI * (hour - 6.2)) / 12.2))
  const cloudAtten = 1 - 0.62 * (cloudCover / 100) ** 1.35
  const ghi = round(Math.max(0, meta.ghiBase * solarShape * cloudAtten * 1000), 0) // W/m²

  const windSpeed = round(
    Math.max(0.4, meta.windBase * (0.86 + 0.2 * Math.cos(((hour - 4) / 24) * Math.PI * 2)) + (isMonsoon ? 1.5 : 0) + (r() - 0.5) * 1.6),
    1,
  )
  const windDirection = Math.round((200 + (r() - 0.5) * 120 + 360) % 360)

  const condition =
    cloudCover < 20
      ? 'Clear'
      : cloudCover < 45
        ? 'Partly Cloudy'
        : cloudCover < 70
          ? 'Cloudy'
          : humidity > 78
            ? 'Overcast'
            : 'Cloudy'

  const rainfall = isMonsoon && cloudCover > 65 ? round(r() * 6.5, 1) : 0
  const pressure = round(1006 + (r() - 0.5) * 10, 1)
  const uvIndex = round(Math.max(0, (ghi / 1000) * 11 * 1.15), 1)

  return {
    district: districtName,
    zone: meta.zone,
    lat: meta.lat,
    lng: meta.lng,
    temperature,
    humidity,
    ghi,
    windSpeed,
    windDirection,
    cloudCover,
    rainfall,
    pressure,
    uvIndex,
    condition,
    isMonsoon,
    updatedAt: at.toISOString(),
  }
}

/* -------------------------------------------------------------------------- */
/*  Generation model (demo)                                                    */
/* -------------------------------------------------------------------------- */

const SOLAR_SEASON = [0.84, 0.92, 1.0, 1.02, 0.97, 0.85, 0.79, 0.8, 0.86, 0.93, 0.9, 0.85]
const WIND_SEASON = [0.94, 1.0, 1.05, 1.02, 0.94, 1.16, 1.26, 1.21, 1.04, 0.95, 0.9, 0.92]

export function seasonalFactor(type, date) {
  const table = type === 'wind' ? WIND_SEASON : SOLAR_SEASON
  return table[date.getMonth()]
}

function solarShape(hourFloat) {
  const sunrise = 6.2
  const sunset = 18.4
  if (hourFloat <= sunrise || hourFloat >= sunset) return 0
  return Math.sin((Math.PI * (hourFloat - sunrise)) / (sunset - sunrise)) ** 1.15
}

function windShape(hourFloat) {
  return 0.84 + 0.16 * Math.cos(((hourFloat - 4) / 24) * Math.PI * 2)
}

/**
 * Instantaneous generation for a plant at a given time.
 * @param {object} plant
 * @param {Date} date
 * @param {object} opts { weather, noiseScale }
 */
export function instantaneousGeneration(plant, date, opts = {}) {
  const weather = opts.weather || getWeatherForDistrict(plant.district, date)
  const noiseScale = opts.noiseScale ?? 1
  const hourFloat = date.getHours() + date.getMinutes() / 60
  const n = smoothNoise(hashSeed(`${plant.id}:gen`), date.getTime() / 3600000)
  const dayN = smoothNoise(hashSeed(`${plant.id}:day`), Math.floor(date.getTime() / 86400000))

  if (plant.type === 'solar') {
    const cloudAtten = 1 - 0.62 * (weather.cloudCover / 100) ** 1.35
    const cf = plant.ccf * solarShape(hourFloat) * seasonalFactor('solar', date) * cloudAtten
    const perturbed = cf * (1 + (n * 0.09 + dayN * 0.05) * noiseScale)
    const mw = Math.max(0, Math.min(plant.capacityMW, plant.capacityMW * perturbed))
    return { mw: round(mw, 2), utilization: round((mw / plant.capacityMW) * 100, 1), weather }
  }

  const cf = plant.ccf * windShape(hourFloat) * seasonalFactor('wind', date) * (1 + (weather.windSpeed - 5) * 0.045)
  const gust = weather.windSpeed > 14 ? 0.94 : 1 // extreme-wind curtailment
  const perturbed = Math.max(0, cf) * (1 + (n * 0.15 + dayN * 0.08) * noiseScale) * gust
  const capped = Math.min(perturbed, 0.98)
  const mw = Math.max(0, plant.capacityMW * capped)
  return { mw: round(mw, 2), utilization: round((mw / plant.capacityMW) * 100, 1), weather }
}

/**
 * Resampled history for analytics: daily / weekly / monthly buckets.
 */
export function buildAggregatedHistory({ type = 'all', period = 'monthly', buckets = 12 } = {}) {
  const out = []
  const now = NOW
  for (let i = buckets - 1; i >= 0; i -= 1) {
    let d = new Date(now)
    let label = ''
    if (period === 'daily') {
      d = new Date(now.getTime() - i * 86400000)
      label = d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
    } else if (period === 'weekly') {
      d = new Date(now.getTime() - i * 7 * 86400000)
      label = `W${buckets - i}`
    } else {
      d = new Date(now.getFullYear(), now.getMonth() - i, 1)
      label = d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
    }

    const dayIdx = Math.floor(d.getTime() / 86400000)
    const seed = hashSeed(`agg:${type}:${period}:${dayIdx}`)
    const r = mulberry32(seed)

    const solarCap = PLANTS.filter((p) => p.type === 'solar').reduce((s, p) => s + p.capacityMW, 0)
    const windCap = PLANTS.filter((p) => p.type === 'wind').reduce((s, p) => s + p.capacityMW, 0)
    const season = seasonalFactor(type === 'wind' ? 'wind' : 'solar', d)

    const solarCF = 0.19 * season * (0.9 + r() * 0.2)
    const windCF = 0.29 * seasonalFactor('wind', d) * (0.86 + r() * 0.3)

    const includeSolar = type === 'all' || type === 'solar'
    const includeWind = type === 'all' || type === 'wind'
    const solar = includeSolar ? round(solarCap * solarCF, 1) : 0
    const wind = includeWind ? round(windCap * windCF, 1) : 0
    const total = round(solar + wind, 1)

    out.push({
      label,
      t: d.toISOString(),
      solar,
      wind,
      total,
      forecast: round(total * (1 + (r() - 0.5) * 0.06), 1),
      utilization: round(type === 'wind' ? windCF * 100 : type === 'solar' ? solarCF * 100 : ((solar + wind) / (solarCap + windCap)) * 100, 1),
      capacityFactor: round((total / (solarCap + windCap)) * 100, 1),
      // Period-average weather drivers (demo).
      ghi: round(5.6 * season * (0.92 + r() * 0.16), 2),
      temperature: round(26 + (r() - 0.4) * 6, 1),
      humidity: round(56 + (r() - 0.4) * 20, 0),
      windSpeed: round(5.4 + (r() - 0.4) * 2.2, 1),
    })
  }
  return out
}

/* -------------------------------------------------------------------------- */
/*  Plant summaries (fleet table / dashboard)                                  */
/* -------------------------------------------------------------------------- */

export function getPlantSummaries() {
  return PLANTS.map((plant) => {
    const live = instantaneousGeneration(plant, NOW)
    return {
      ...plant,
      currentGenerationMW: live.mw,
      utilization: live.utilization,
      capacityFactor: plant.ccf,
      weather: live.weather,
    }
  })
}

export function getPlantDetail(id) {
  const summary = getPlantSummaries().find((p) => p.id === id)
  return summary ? { ...summary } : null
}

/* -------------------------------------------------------------------------- */
/*  Dashboard aggregation                                                      */
/* -------------------------------------------------------------------------- */

export function getDashboardData() {
  const summaries = getPlantSummaries()
  const solar = summaries.filter((p) => p.type === 'solar')
  const wind = summaries.filter((p) => p.type === 'wind')

  const sum = (arr, key) => round(arr.reduce((s, p) => s + (p[key] || 0), 0), 1)

  const totalCapacityMW = sum(summaries, 'capacityMW')
  const solarCapacityMW = sum(solar, 'capacityMW')
  const windCapacityMW = sum(wind, 'capacityMW')
  const currentGenerationMW = sum(summaries, 'currentGenerationMW')
  const solarGenerationMW = sum(solar, 'currentGenerationMW')
  const windGenerationMW = sum(wind, 'currentGenerationMW')

  const trend = buildAggregatedHistory({ type: 'all', period: 'monthly', buckets: 12 })
  const mix = [
    { name: 'Solar', value: solarCapacityMW, generation: solarGenerationMW, color: '#f59e0b' },
    { name: 'Wind', value: windCapacityMW, generation: windGenerationMW, color: '#0ea5e9' },
  ]

  const topDistricts = Object.entries(
    summaries.reduce((acc, p) => {
      acc[p.district] = acc[p.district] || { district: p.district, capacity: 0, generation: 0, plants: 0 }
      acc[p.district].capacity += p.capacityMW
      acc[p.district].generation += p.currentGenerationMW
      acc[p.district].plants += 1
      return acc
    }, {}),
  )
    .map(([, v]) => ({ ...v, capacity: round(v.capacity, 1), generation: round(v.generation, 1) }))
    .sort((a, b) => b.capacity - a.capacity)

  const weatherOverview = topDistricts.slice(0, 6).map((d) => getWeatherForDistrict(d.district))

  const util = round((currentGenerationMW / totalCapacityMW) * 100, 1)

  return {
    meta: {
      generatedAt: NOW.toISOString(),
      dataMode: 'demo',
      label: 'DEMO / PLACEHOLDER DATA',
      note: 'Frontend demonstration dataset. Replace with live ENERVISION API output when available.',
    },
    overview: {
      totalCapacityMW,
      currentGenerationMW,
      solarCapacityMW,
      windCapacityMW,
      solarGenerationMW,
      windGenerationMW,
      plantCount: summaries.length,
      solarPlantCount: solar.length,
      windPlantCount: wind.length,
      fleetUtilization: util,
      dailyEnergyMWh: round(currentGenerationMW * 24 * 0.62, 0),
      co2OffsetTonnes: round(currentGenerationMW * 24 * 0.62 * 0.82, 0),
      gridFrequencyHz: 49.98,
      curtailmentMW: round(summaries.reduce((s, p) => s + (p.status === 'partial-outage' ? p.capacityMW * 0.18 : 0), 0), 1),
    },
    generationTrend: trend,
    mix,
    topDistricts,
    weatherOverview,
    plants: summaries,
  }
}

/* -------------------------------------------------------------------------- */
/*  Analytics aggregation                                                      */
/* -------------------------------------------------------------------------- */

export function getAnalytics({ period = 'monthly', buckets: bucketOverride = null } = {}) {
  const buckets = bucketOverride ?? (period === 'daily' ? 14 : period === 'weekly' ? 12 : 12)
  const all = buildAggregatedHistory({ type: 'all', period, buckets })
  const solar = buildAggregatedHistory({ type: 'solar', period, buckets })
  const wind = buildAggregatedHistory({ type: 'wind', period, buckets })
  const summaries = getPlantSummaries()

  const totalCapacityMW = round(summaries.reduce((s, p) => s + p.capacityMW, 0), 1)
  const totalGenerationMW = round(summaries.reduce((s, p) => s + p.currentGenerationMW, 0), 1)
  const avgCF = round(all.reduce((s, b) => s + b.capacityFactor, 0) / all.length, 1)
  const bestBucket = all.reduce((a, b) => (a && a.total > b.total ? a : b), all[0])
  const avgGhi = round(all.reduce((s, b) => s + b.ghi, 0) / all.length, 2)
  const avgWind = round(all.reduce((s, b) => s + b.windSpeed, 0) / all.length, 1)

  // Weather vs generation scatter (bucketed daily samples).
  const scatter = buildAggregatedHistory({ type: 'all', period: 'daily', buckets: 30 }).map((b) => ({
    ghi: b.ghi,
    windSpeed: b.windSpeed,
    temperature: b.temperature,
    generation: b.total,
    solar: b.solar,
    wind: b.wind,
  }))

  const plantComparison = summaries
    .map((p) => ({
      id: p.id,
      name: p.name.replace(' (Shakti Sthala)', ''),
      short: p.name.split(' ')[0],
      type: p.type,
      district: p.district,
      capacityMW: p.capacityMW,
      utilization: p.utilization,
      currentGenerationMW: p.currentGenerationMW,
      capacityFactor: round(p.ccf * 100, 1),
    }))
    .sort((a, b) => b.capacityMW - a.capacityMW)

  const mix = [
    { name: 'Solar', value: round(summaries.filter((p) => p.type === 'solar').reduce((s, p) => s + p.capacityMW, 0), 1), color: '#f59e0b' },
    { name: 'Wind', value: round(summaries.filter((p) => p.type === 'wind').reduce((s, p) => s + p.capacityMW, 0), 1), color: '#0ea5e9' },
  ]

  // Pearson correlation helpers (demo relationship, computed from the series).
  const correlation = (xKey, yKey, rows = scatter) => {
    const xs = rows.map((r) => r[xKey])
    const ys = rows.map((r) => r[yKey])
    const n = xs.length
    const mx = xs.reduce((a, b) => a + b, 0) / n
    const my = ys.reduce((a, b) => a + b, 0) / n
    const num = xs.reduce((a, x, i) => a + (x - mx) * (ys[i] - my), 0)
    const den = Math.sqrt(xs.reduce((a, x) => a + (x - mx) ** 2, 0) * ys.reduce((a, y) => a + (y - my) ** 2, 0))
    return den === 0 ? 0 : round(num / den, 2)
  }

  return {
    meta: { generatedAt: NOW.toISOString(), period, dataMode: 'demo' },
    kpis: {
      totalCapacityMW,
      totalGenerationMW,
      avgCapacityFactor: avgCF,
      avgGhi,
      avgWindSpeed: avgWind,
      bestBucket: { label: bestBucket.label, total: bestBucket.total },
      plantCount: summaries.length,
      co2OffsetTonnes: round(totalGenerationMW * 24 * 0.82, 0),
    },
    series: { all, solar, wind },
    scatter,
    plantComparison,
    mix,
    correlations: {
      ghiVsSolar: correlation('ghi', 'solar'),
      windSpeedVsWind: correlation('windSpeed', 'wind'),
      temperatureVsSolar: correlation('temperature', 'solar'),
      ghiVsTotal: correlation('ghi', 'generation'),
    },
  }
}


/* -------------------------------------------------------------------------- */
/*  Feature importance — DEMO / PLACEHOLDER                                    */
/* -------------------------------------------------------------------------- */

const FEATURE_BASE = {
  ghi: 0.24,
  temperature: 0.11,
  humidity: 0.07,
  rainfall: 0.05,
  pressure: 0.04,
  windSpeed: 0.13,
  prevGeneration: 0.15,
  rollingGeneration: 0.09,
  dayOfYear: 0.05,
  month: 0.04,
  season: 0.03,
}

const FEATURE_META = {
  ghi: { label: 'GHI (daily irradiance)', unit: 'kWh/m²/day', source: 'NASA POWER', color: '#f59e0b' },
  temperature: { label: 'Temperature', unit: '°C', source: 'NASA POWER', color: '#ef4444' },
  humidity: { label: 'Humidity', unit: '%', source: 'NASA POWER', color: '#0ea5e9' },
  rainfall: { label: 'Rainfall', unit: 'mm/day', source: 'NASA POWER', color: '#38bdf8' },
  pressure: { label: 'Pressure', unit: 'kPa', source: 'NASA POWER', color: '#94a3b8' },
  windSpeed: { label: 'Wind Speed', unit: 'm/s', source: 'NASA POWER', color: '#06b6d4' },
  prevGeneration: { label: 'Previous-day Generation', unit: 'MU/day', source: 'CEA', color: '#178a80' },
  rollingGeneration: { label: 'Rolling Generation (daily mean)', unit: 'MU/day', source: 'Engineered', color: '#14b8a6' },
  dayOfYear: { label: 'Day of Year', unit: '—', source: 'Engineered', color: '#6366f1' },
  month: { label: 'Month', unit: '—', source: 'Engineered', color: '#8b5cf6' },
  season: { label: 'Season', unit: '—', source: 'Engineered', color: '#a78bfa' },
}

export function getFeatureImportance({ modelId = 'random_forest_daily', type = 'solar' } = {}) {
  const seed = hashSeed(`fi:${modelId}:${type}`)
  const r = mulberry32(seed)
  let weightTotal = 0
  const weighted = Object.entries(FEATURE_BASE).map(([key, base]) => {
    let w = base
    if (type === 'wind') {
      if (key === 'windSpeed') w = 0.3
      if (key === 'ghi') w = 0.12
      if (key === 'temperature') w = 0.07
    }
    const jittered = Math.max(0.01, w * (1 + (r() - 0.5) * 0.24))
    weightTotal += jittered
    return [key, jittered]
  })

  const features = weighted
    .map(([key, w]) => ({
      key,
      ...FEATURE_META[key],
      importance: round(w / weightTotal, 4),
    }))
    .sort((a, b) => b.importance - a.importance)

  return {
    meta: {
      generatedAt: NOW.toISOString(),
      dataMode: 'demo',
      modelId,
      type,
      label: 'DEMO / ILLUSTRATIVE FEATURE IMPORTANCE',
      note: 'Illustrative impurity-importance values. The live API publishes random_forest_impurity importance; SHAP is not used.',
    },
    features,
  }
}

/* -------------------------------------------------------------------------- */
/*  Static descriptive content (About / model docs)                           */
/* -------------------------------------------------------------------------- */

export const DATA_SOURCES = [
  {
    id: 'cea',
    name: 'CEA Generation Data',
    full: 'Central Electricity Authority (CEA) — daily generation reports',
    description:
      'Historical plant-wise and state-wise daily generation records used to build the supervised learning target DailyGeneration_MU. The API serves observed daily values in MU/day.',
    role: 'Target variable · daily generation',
    cadence: 'Daily',
    color: 'brand',
  },
  {
    id: 'nasa-power',
    name: 'NASA POWER Weather Data',
    full: 'NASA POWER — Prediction Of Worldwide Energy Resources',
    description:
      'Daily meteorological and solar-resource variables (GHI, temperature, humidity, wind speed, pressure) for the coordinates of each Karnataka plant. Supplies the exogenous model inputs.',
    role: 'Feature variables · observed weather',
    cadence: 'Daily',
    color: 'sky',
  },
  {
    id: 'plant',
    name: 'Plant Master Data',
    full: 'Plant registry — capacity, technology, coordinates, commissioning',
    description:
      'Registry attributes for every monitored plant: stable plant ID, installed capacity, renewable type, district, latitude/longitude and observed date range. Used for plant identity, mapping and per-plant daily series.',
    role: 'Metadata · plant registry',
    cadence: 'Static',
    color: 'amber',
  },
]

export const TECH_STACK = [
  { group: 'Frontend', items: ['React 18', 'Vite', 'JavaScript (ES2022)', 'Tailwind CSS', 'React Router', 'Recharts', 'Lucide React'] },
  { group: 'Data & API', items: ['Flask REST API', 'Daily JSON contract', 'Centralised service layer', 'Environment-driven demo/live switch', 'No silent mock fallback'] },
  { group: 'ML / Modelling (research)', items: ['Random Forest (24 features)', 'Solar LSTM', 'Wind LSTM', 'Chronological split', 'Committed artifacts'] },
  { group: 'Explainability', items: ['Random Forest impurity importance', 'Provenance separation', 'No SHAP', 'No prediction intervals'] },
]

export const ARCHITECTURE_STEPS = [
  {
    step: '01',
    title: 'Data Acquisition',
    body: 'Plant master data is joined with CEA daily generation records and NASA POWER daily weather series on plant ID and date.',
    icon: 'Database',
  },
  {
    step: '02',
    title: 'Preprocessing & Cleaning',
    body: 'Daily records are aligned, missing calendar days are retained as gaps, and observed values are screened without inventing hourly or synthetic rows.',
    icon: 'Filter',
  },
  {
    step: '03',
    title: 'Feature Engineering',
    body: 'Daily weather features, calendar features (day of year, month, season), generation lags and rolling-window statistics are constructed per plant.',
    icon: 'Wrench',
  },
  {
    step: '04',
    title: 'Daily Modelling',
    body: 'A current leakage-free 24-feature Random Forest and type-specific solar/wind LSTM artifacts are loaded from committed model files.',
    icon: 'BrainCircuit',
  },
  {
    step: '05',
    title: 'Evaluation & Explainability',
    body: 'MAE is published for all committed models, with RMSE and R² for the current Random Forest. Feature importance is Random Forest mean decrease in impurity — not SHAP.',
    icon: 'Activity',
  },
  {
    step: '06',
    title: 'Decision Support',
    body: 'Daily forecasts (1–7 days, MU/day) are served through the API to this dashboard, including honest unavailable states when future weather is missing.',
    icon: 'LayoutDashboard',
  },
]

export const OBJECTIVES = [
  'Assemble a plant-wise daily renewable generation dataset for Karnataka by combining CEA generation records with NASA POWER observed weather series.',
  'Engineer daily weather, calendar, lag and rolling-window features that capture the physical drivers of solar and wind output.',
  'Train and evaluate the committed daily models: a leakage-free Random Forest and type-specific solar and wind LSTMs.',
  'Report only metrics published by the API — MAE for all committed models, plus RMSE and R² for the current Random Forest — under a chronological split.',
  'Provide honest explainability through Random Forest impurity importance and clearly separated provenance, never claiming SHAP.',
  'Deliver the result through a decision-support dashboard that presents observed daily generation, daily forecasts and descriptive analytics for Karnataka plants.',
]

export const PROBLEM_STATEMENT = {
  heading: 'Why ENERVISION exists',
  body: 'Renewable generation is variable, weather-driven and difficult to schedule. Karnataka operates a large and growing portfolio of solar and wind assets, yet plant-level daily generation forecasts are frequently coarse or unavailable to operators. Without reliable daily forecasts, grid scheduling becomes conservative, curtailment increases and maintenance is planned reactively. ENERVISION addresses this by combining authoritative daily generation and weather data with committed machine-learning models to produce plant-wise daily forecasts and the descriptive analytics needed to act on them.',
  points: [
    'Solar and wind output varies with irradiance, temperature, humidity and wind speed — not with demand.',
    'Aggregate state-level forecasts hide plant-level variability that operators actually dispatch against.',
    'Forecasts are difficult to trust without disclosed model provenance and feature importance.',
    'Historical generation and weather data exist but are fragmented across sources and formats.',
  ],
}

export const FUTURE_SCOPE = [
  'Integrate a future-weather provider so Random Forest and multi-day LSTM horizons can return predictions instead of an honest unavailable state.',
  'Expand coverage from the monitored fleet to the full Karnataka plant registry as new observed data arrives.',
  'Add probabilistic / quantile forecasts and formal prediction intervals calibrated on held-out data.',
  'Extend the daily horizon to week-ahead scheduling with uncertainty-aware dispatch recommendations.',
  'Introduce automated retraining and drift monitoring as new CEA and NASA POWER data arrives.',
  'Add anomaly detection for underperformance and predictive maintenance signals per asset.',
  'Provide authenticated multi-user access with role-based views for operators, analysts and planners.',
]
