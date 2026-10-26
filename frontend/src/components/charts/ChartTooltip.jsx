import { formatNumber } from '../../utils/format.js'

/**
 * Shared Recharts tooltip. Consumes the payload Recharts provides and renders a
 * compact dark control-room panel. `units` maps a series dataKey → unit suffix.
 */
export default function ChartTooltip({
  active,
  payload,
  label,
  units = {},
  digits = 1,
  labelFormatter,
  hideZero = false,
  valueFormatter,
}) {
  if (!active || !payload || !payload.length) return null
  const rows = payload.filter((p) => {
    if (p.value === null || p.value === undefined) return false
    if (hideZero && Number(p.value) === 0) return false
    return true
  })
  if (!rows.length) return null

  return (
    <div className="pointer-events-none min-w-[150px] rounded-lg border border-graphite-650 bg-graphite-900/95 px-3 py-2 shadow-panel-lg backdrop-blur">
      <p className="mb-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-graphite-400">
        {labelFormatter ? labelFormatter(label) : label}
      </p>
      <div className="space-y-1">
        {rows.map((p) => (
          <div key={p.dataKey} className="flex items-center justify-between gap-4 text-[11px]">
            <span className="flex items-center gap-1.5 text-graphite-400">
              <span className="h-2 w-2 rounded-sm" style={{ background: p.color || p.stroke || p.fill }} />
              {p.name}
            </span>
            <span className="font-mono font-semibold tabular-nums text-white">
              {valueFormatter
                ? valueFormatter(p.value, p)
                : formatNumber(p.value, digits)}
              {units[p.dataKey] ? <span className="ml-0.5 text-graphite-400">{units[p.dataKey]}</span> : null}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
