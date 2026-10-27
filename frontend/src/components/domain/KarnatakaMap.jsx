import { useMemo, useState } from 'react'
import { cx } from '../../utils/format.js'
import { KARNATAKA_DISTRICTS, KARNATAKA_BBOX } from '../../data/karnatakaOutline.js'
import { canonicalDistrict, PALETTE } from '../../utils/constants.js'
import { formatDate, formatMU, formatNumber } from '../../utils/format.js'
import { PlantTypeBadge } from './PlantStatus.jsx'

/* Geographic projection ---------------------------------------------------- */
const VW = 800
const VH = 1270
// Pad the bounding box so edge nodes are never clipped.
const PAD = 0.04
const LON_MIN = KARNATAKA_BBOX.minLon
const LON_SPAN = KARNATAKA_BBOX.maxLon - KARNATAKA_BBOX.minLon
const LAT_MIN = KARNATAKA_BBOX.minLat
const LAT_SPAN = KARNATAKA_BBOX.maxLat - KARNATAKA_BBOX.minLat

function project(lng, lat) {
  const x = ((lng - LON_MIN) / LON_SPAN) * VW * (1 - PAD * 2) + VW * PAD
  const y = ((LAT_MIN + LAT_SPAN - lat) / LAT_SPAN) * VH * (1 - PAD * 2) + VH * PAD
  return [x, y]
}

function ringToPath(ring) {
  let d = ''
  for (let i = 0; i < ring.length; i += 1) {
    const [x, y] = project(ring[i][0], ring[i][1])
    d += `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
  }
  return `${d}Z`
}

/** Bengaluru hub used as the visual anchor for the transmission overlay. */
const HUB = project(77.5946, 12.9716)

function nodeRadius(capacityMW) {
  const cap = Math.max(50, Number(capacityMW) || 50)
  return 3.6 + Math.sqrt(cap / 2050) * 7.4
}

/**
 * Interactive Karnataka plant map. District boundaries form the base layer;
 * solar/wind plants render as pulsing nodes scaled by capacity. Hovering reveals
 * a data card, clicking selects the plant.
 */
export default function KarnatakaMap({
  plants = [],
  onSelect,
  selectedId,
  showNetwork = true,
  showLabels = false,
  showLegend = true,
  className = '',
}) {
  const [hovered, setHovered] = useState(null)

  const districtPaths = useMemo(
    () => KARNATAKA_DISTRICTS.map((d) => ({ name: d.name, d: d.rings.map(ringToPath).join(' ') })),
    [],
  )

  const activeDistricts = useMemo(() => {
    const set = new Set()
    plants.forEach((p) => set.add(canonicalDistrict(p.district)))
    return set
  }, [plants])

  const nodes = useMemo(
    () =>
      plants
        .filter((p) => p.hasCoordinates !== false && Number.isFinite(Number(p.lng)) && Number.isFinite(Number(p.lat)))
        .map((p) => {
          const [x, y] = project(Number(p.lng), Number(p.lat))
          return { plant: p, x, y, r: nodeRadius(p.capacityMW), isWind: p.type === 'wind' }
        }),
    [plants],
  )

  const active = hovered ? nodes.find((n) => n.plant.id === hovered) : null

  return (
    <div className={cx('relative h-full w-full overflow-hidden', className)}>
      {/* Ambience: grid, contour rings, radar sweep */}
      <div className="pointer-events-none absolute inset-0 ev-grid opacity-50" aria-hidden />
      <div className="pointer-events-none absolute inset-0 ev-contour ev-fade-mask opacity-70" aria-hidden />
      <div className="pointer-events-none absolute left-1/2 top-[44%] h-[70%] w-[70%] -translate-x-1/2 -translate-y-1/2 ev-fade-mask" aria-hidden>
        <div
          className="h-full w-full animate-sweep rounded-full"
          style={{
            background:
              'conic-gradient(from 0deg, rgba(45,212,191,0.22) 0deg, rgba(45,212,191,0.0) 60deg, rgba(45,212,191,0) 360deg)',
            animationDuration: '12s',
          }}
        />
      </div>

      <svg viewBox={`0 0 ${VW} ${VH}`} className="relative h-full w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id="km-node-solar" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fde68a" />
            <stop offset="100%" stopColor={PALETTE.solar} />
          </radialGradient>
          <radialGradient id="km-node-wind" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#a5f3fc" />
            <stop offset="100%" stopColor={PALETTE.wind} />
          </radialGradient>
          <filter id="km-glow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="6" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* District fills */}
        <g>
          {districtPaths.map((d) => {
            const hot = activeDistricts.has(canonicalDistrict(d.name))
            return (
              <path
                key={d.name}
                d={d.d}
                fill={hot ? 'rgba(45,212,191,0.09)' : 'rgba(148,163,184,0.035)'}
                stroke={hot ? 'rgba(45,212,191,0.35)' : 'rgba(148,163,184,0.16)'}
                strokeWidth={hot ? 1.1 : 0.8}
                vectorEffect="non-scaling-stroke"
              />
            )
          })}
        </g>

        {/* Transmission overlay */}
        {showNetwork ? (
          <g>
            {nodes.map((n) => (
              <line
                key={`ln-${n.plant.id}`}
                x1={HUB[0]}
                y1={HUB[1]}
                x2={n.x}
                y2={n.y}
                stroke={n.isWind ? PALETTE.wind : PALETTE.solar}
                strokeOpacity={0.14}
                strokeWidth={0.8}
                strokeDasharray="2 7"
                className="animate-dash-flow"
                vectorEffect="non-scaling-stroke"
              />
            ))}
            <circle cx={HUB[0]} cy={HUB[1]} r={2.4} fill={PALETTE.brand} />
          </g>
        ) : null}

        {/* Plant nodes */}
        <g>
          {nodes.map((n, i) => {
            const color = n.isWind ? PALETTE.wind : PALETTE.solar
            const grad = n.isWind ? 'url(#km-node-wind)' : 'url(#km-node-solar)'
            const selected = selectedId === n.plant.id
            const dim = hovered && hovered !== n.plant.id
            return (
              <g
                key={n.plant.id}
                transform={`translate(${n.x} ${n.y})`}
                className="cursor-pointer transition-opacity duration-200"
                style={{ opacity: dim ? 0.35 : 1 }}
                onMouseEnter={() => setHovered(n.plant.id)}
                onMouseLeave={() => setHovered((h) => (h === n.plant.id ? null : h))}
                onClick={() => onSelect?.(n.plant)}
              >
                {/* ping ring */}
                <circle
                  r={n.r}
                  fill="none"
                  stroke={color}
                  strokeWidth={1}
                  className="animate-ping-ring"
                  style={{ animationDelay: `${(i % 6) * 0.4}s`, transformOrigin: 'center', transformBox: 'fill-box' }}
                />
                {/* halo */}
                <circle r={n.r + 4} fill={color} opacity={selected ? 0.22 : 0.1} />
                {/* core */}
                <circle
                  r={n.r}
                  fill={grad}
                  stroke="rgba(255,255,255,0.55)"
                  strokeWidth={selected ? 1.4 : 0.7}
                  filter={selected || hovered === n.plant.id ? 'url(#km-glow)' : undefined}
                  className="animate-node-breathe"
                  style={{ animationDelay: `${(i % 5) * 0.5}s`, transformOrigin: 'center', transformBox: 'fill-box' }}
                />
                {selected ? <circle r={n.r + 6.5} fill="none" stroke={color} strokeWidth={1.2} strokeDasharray="2 3" /> : null}

                {showLabels ? (
                  <text
                    x={n.r + 5}
                    y={0}
                    dy="0.32em"
                    fill="rgba(219,226,233,0.72)"
                    fontSize={13}
                    fontFamily="'JetBrains Mono', monospace"
                  >
                    {n.plant.id}
                  </text>
                ) : null}
              </g>
            )
          })}
        </g>
      </svg>

      {/* Hover data card */}
      {active ? (
        <div
          className="pointer-events-none absolute z-20 w-56 -translate-x-1/2 -translate-y-[calc(100%+14px)] animate-fade-in"
          style={{ left: `${(active.x / VW) * 100}%`, top: `${(active.y / VH) * 100}%` }}
        >
          <div className="panel overflow-hidden p-3 shadow-panel-lg">
            <p className="font-display text-[13px] font-bold leading-snug text-white">{active.plant.name}</p>
            <p className="mt-0.5 text-[11px] text-graphite-400">
              {active.plant.district || 'Karnataka'}
              {active.plant.owner ? ` · ${active.plant.owner}` : ''}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <PlantTypeBadge type={active.plant.type} size="sm" />
            </div>
            <div className="mt-2 grid grid-cols-3 gap-2">
              <div>
                <p className="text-[9px] uppercase tracking-wide text-graphite-500">Capacity</p>
                <p className="font-mono text-[11px] font-bold text-white">
                  {active.plant.capacityMW === null || active.plant.capacityMW === undefined
                    ? '—'
                    : `${formatNumber(active.plant.capacityMW, 0)} MW`}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-wide text-graphite-500">Latest day</p>
                <p className="font-mono text-[11px] font-bold text-white">
                  {formatMU(active.plant.latestGenerationMU, 2)}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-wide text-graphite-500">Observed</p>
                <p className="font-mono text-[11px] font-bold text-white">
                  {active.plant.latestGenerationDate ? formatDate(active.plant.latestGenerationDate) : '—'}
                </p>
              </div>
            </div>
          </div>
          <div className="mx-auto h-2 w-px bg-white/20" />
        </div>
      ) : null}

      {/* Legend */}
      {showLegend ? (
        <div className="pointer-events-none absolute bottom-3 left-3 flex flex-col gap-1.5 rounded-lg border border-graphite-700/70 bg-graphite-950/70 px-3 py-2 backdrop-blur">
          <p className="eyebrow">Nodes</p>
          <span className="flex items-center gap-2 text-[10px] text-graphite-300">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: PALETTE.solar, boxShadow: `0 0 10px ${PALETTE.solar}` }} />
            Solar
          </span>
          <span className="flex items-center gap-2 text-[10px] text-graphite-300">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: PALETTE.wind, boxShadow: `0 0 10px ${PALETTE.wind}` }} />
            Wind
          </span>
          <span className="mt-0.5 text-[9px] text-graphite-500">size ∝ capacity</span>
          <span className="text-[9px] text-graphite-500">
            {nodes.length} of {plants.length} plants mapped · coordinates where available
          </span>
        </div>
      ) : null}

      <p className="pointer-events-none absolute bottom-3 right-3 font-mono text-[9px] uppercase tracking-wide text-graphite-600">
        Schematic projection · observed sites
      </p>
    </div>
  )
}
