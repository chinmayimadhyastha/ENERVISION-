/**
 * Shared formatting helpers used across ENERVISION pages.
 * Keeping them in one place avoids inconsistent units / precision in the UI.
 */

const DAY_MS = 86400000

export function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/**
 * Parse an API daily date (`YYYY-MM-DD`) without timezone drift. Bare dates are
 * anchored at local noon so a locale conversion can never roll over a day.
 */
export function parseDate(value) {
  if (value === null || value === undefined || value === '') return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const text = String(value)
  const d = /^\d{4}-\d{2}-\d{2}$/.test(text) ? new Date(`${text}T12:00:00`) : new Date(text)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Calendar date, e.g. 05 Aug 2026. */
export function formatDate(value, options = {}) {
  const d = parseDate(value)
  if (!d) return '—'
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', ...options })
}

/** Daily energy in MU/day (the only generation unit the API publishes). */
export function formatMU(value, digits = 2) {
  const n = formatNumber(value, digits)
  return n === '—' ? n : `${n} MU/day`
}

/** Daily energy magnitude without the unit suffix (for tables/axis ticks). */
export function formatMUValue(value, digits = 2) {
  return formatNumber(value, digits)
}

/** Human label for a relative day offset: 0 -> TODAY, 1 -> TOMORROW, 2 -> +2 DAYS. */
export function formatDayOffset(offset) {
  if (offset === null || offset === undefined || Number.isNaN(Number(offset))) return '—'
  const n = Math.trunc(Number(offset))
  if (n <= 0) return 'TODAY'
  if (n === 1) return 'TOMORROW'
  return `+${n} DAYS`
}

/** Whole days between two API dates, or null when either is invalid. */
export function daysBetweenDates(start, end) {
  const a = parseDate(start)
  const b = parseDate(end)
  if (!a || !b) return null
  return Math.round((b.getTime() - a.getTime()) / DAY_MS)
}

/** Label a forecast date relative to the model base date. */
export function dayOffsetLabel(baseDate, date) {
  return formatDayOffset(daysBetweenDates(baseDate, date))
}

export function formatPower(mw, digits = 1) {
  if (mw === null || mw === undefined || Number.isNaN(Number(mw))) return '—'
  const value = Number(mw)
  if (Math.abs(value) >= 1000) {
    return `${formatNumber(value / 1000, digits + 1)} GW`
  }
  return `${formatNumber(value, digits)} MW`
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return `${formatNumber(value, digits)}%`
}

export function formatSigned(value, digits = 1, suffix = '%') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const v = Number(value)
  const sign = v > 0 ? '+' : v < 0 ? '−' : ''
  return `${sign}${formatNumber(Math.abs(v), digits)}${suffix}`
}

export function formatCoord(value, axis) {
  if (value === null || value === undefined) return '—'
  const v = Number(value)
  const hemi = axis === 'lat' ? (v >= 0 ? 'N' : 'S') : v >= 0 ? 'E' : 'W'
  return `${Math.abs(v).toFixed(4)}° ${hemi}`
}

export function formatDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

export function formatHourLabel(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', hour12: false }) + ':00'
}

export function formatDateShort(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
}

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

export function cx(...parts) {
  return parts.filter(Boolean).join(' ')
}
