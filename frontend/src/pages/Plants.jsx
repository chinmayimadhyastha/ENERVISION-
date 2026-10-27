import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  BatteryCharging,
  CalendarDays,
  Factory,
  LayoutGrid,
  MapPinned,
  Rows3,
  Search,
  Sun,
  Wind,
  X,
  Zap,
} from 'lucide-react'

import { getPlants, referenceData } from '../services/api.js'
import useAsync from '../hooks/useAsync.js'
import { formatDate, formatMU, formatNumber, formatPower } from '../utils/format.js'
import { RENEWABLE_TYPES } from '../utils/constants.js'

import PageHeader from '../components/ui/PageHeader.jsx'
import SectionTitle from '../components/ui/SectionTitle.jsx'
import Card from '../components/ui/Card.jsx'
import Badge from '../components/ui/Badge.jsx'
import Select from '../components/ui/Select.jsx'
import SegmentedControl from '../components/ui/SegmentedControl.jsx'
import StatCard from '../components/ui/StatCard.jsx'
import DataTable from '../components/ui/DataTable.jsx'
import LoadingState from '../components/ui/LoadingState.jsx'
import ErrorState from '../components/ui/ErrorState.jsx'
import EmptyState from '../components/ui/EmptyState.jsx'
import DemoNotice, { ASSET_DEMO_LABEL } from '../components/ui/DemoNotice.jsx'
import KarnatakaMap from '../components/domain/KarnatakaMap.jsx'
import { PlantGlyph, PlantTypeBadge } from '../components/domain/PlantStatus.jsx'

const DEFAULT_FILTERS = { type: 'all', district: 'all', sort: 'capacity-desc' }

const SORTERS = {
  'capacity-desc': (a, b) => (b.capacityMW || 0) - (a.capacityMW || 0),
  'capacity-asc': (a, b) => (a.capacityMW || 0) - (b.capacityMW || 0),
  'generation-desc': (a, b) => (b.latestGenerationMU || 0) - (a.latestGenerationMU || 0),
  'name-asc': (a, b) => String(a.name || '').localeCompare(String(b.name || '')),
  'name-desc': (a, b) => String(b.name || '').localeCompare(String(a.name || '')),
}

export default function Plants() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState(params.get('q') || '')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [view, setView] = useState('map')
  const [sort, setSort] = useState({ key: 'capacityMW', dir: 'desc' })

  const { data, loading, error, refetch } = useAsync(() => getPlants({}), [])

  useEffect(() => {
    const q = params.get('q')
    if (q !== null) setSearch(q)
  }, [params])

  const rows = data || []

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    let out = rows
    if (q) {
      out = out.filter((p) =>
        [p.name, p.district, p.id, p.owner, p.state]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(q)),
      )
    }
    if (filters.type !== 'all') out = out.filter((p) => p.type === filters.type)
    if (filters.district !== 'all') out = out.filter((p) => p.district === filters.district)
    return [...out].sort(SORTERS[filters.sort] || SORTERS['capacity-desc'])
  }, [rows, search, filters])

  const sorted = useMemo(() => {
    const dir = sort.dir === 'asc' ? 1 : -1
    const key = sort.key
    return [...filtered].sort((a, b) => {
      const va = a[key]
      const vb = b[key]
      if (typeof va === 'string' || typeof vb === 'string') {
        return String(va ?? '').localeCompare(String(vb ?? '')) * dir
      }
      return ((va ?? 0) - (vb ?? 0)) * dir
    })
  }, [filtered, sort])

  const totals = useMemo(() => {
    const cap = filtered.reduce((s, p) => s + (p.capacityMW || 0), 0)
    const gen = filtered.reduce((s, p) => s + (p.latestGenerationMU || 0), 0)
    const solar = filtered.filter((p) => p.type === 'solar')
    const wind = filtered.filter((p) => p.type === 'wind')
    return {
      count: filtered.length,
      cap,
      gen,
      mapped: filtered.filter((p) => p.hasCoordinates).length,
      solarCap: solar.reduce((s, p) => s + (p.capacityMW || 0), 0),
      windCap: wind.reduce((s, p) => s + (p.capacityMW || 0), 0),
      solarCount: solar.length,
      windCount: wind.length,
    }
  }, [filtered])

  const districtOptions = useMemo(() => {
    const names = [...new Set(rows.map((p) => p.district).filter(Boolean))].sort((a, b) => a.localeCompare(b))
    return [{ value: 'all', label: 'All Districts' }, ...names.map((name) => ({ value: name, label: name }))]
  }, [rows])

  const columns = [
    {
      key: 'name',
      header: 'Plant',
      sortable: true,
      render: (r) => (
        <div className="flex items-center gap-3">
          <PlantGlyph type={r.type} />
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold text-graphite-100">{r.name}</p>
            <p className="truncate font-mono text-[10px] text-graphite-500">
              {r.id}
              {r.owner ? ` · ${r.owner}` : ''}
            </p>
          </div>
        </div>
      ),
    },
    { key: 'type', header: 'Type', render: (r) => <PlantTypeBadge type={r.type} size="sm" /> },
    {
      key: 'district',
      header: 'District',
      sortable: true,
      render: (r) => <span className="text-[12px] text-graphite-200">{r.district || '—'}</span>,
    },
    {
      key: 'capacityMW',
      header: 'Capacity',
      align: 'right',
      sortable: true,
      render: (r) => <span className="font-mono text-xs font-bold text-white">{formatPower(r.capacityMW, 0)}</span>,
    },
    {
      key: 'latestGenerationMU',
      header: 'Latest day',
      align: 'right',
      sortable: true,
      render: (r) => <span className="font-mono text-xs text-graphite-100">{formatMU(r.latestGenerationMU, 2)}</span>,
    },
    {
      key: 'latestGenerationDate',
      header: 'Observed',
      align: 'right',
      sortable: true,
      render: (r) => (
        <span className="font-mono text-[11px] text-graphite-400">
          {r.latestGenerationDate ? formatDate(r.latestGenerationDate) : '—'}
        </span>
      ),
    },
    {
      key: 'observations',
      header: 'Rows',
      align: 'right',
      sortable: true,
      render: (r) => <span className="font-mono text-[11px] text-graphite-400">{formatNumber(r.observations, 0)}</span>,
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Asset Intelligence"
        title="Plant Explorer"
        description="Explore Karnataka's monitored renewable fleet geographically, then drill into any asset. Daily generation is reported in MU/day from the live plant registry."
        icon={<Factory className="h-5 w-5" />}
        badge={
          <Badge tone="neutral" size="sm">
            {totalOrDash(loading, rows.length)} assets
          </Badge>
        }
        actions={
          <SegmentedControl
            ariaLabel="View mode"
            value={view}
            onChange={setView}
            options={[
              { value: 'map', label: 'Map', icon: <MapPinned className="h-3.5 w-3.5" /> },
              { value: 'table', label: 'Table', icon: <Rows3 className="h-3.5 w-3.5" /> },
            ]}
          />
        }
      />

      <DemoNotice tone="amber" label={ASSET_DEMO_LABEL}>
        In demo mode these assets are illustrative records. With a live API, names, IDs, capacities, coordinates and daily
        generation come directly from the backend registry; coordinates are shown only where the backend provides them.
      </DemoNotice>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Assets in view"
          value={totals.count}
          tone="brand"
          icon={<Factory className="h-4 w-4" />}
          hint={`${totals.solarCount} solar · ${totals.windCount} wind`}
        />
        <StatCard
          label="Capacity in view"
          value={totals.cap ? totals.cap / 1000 : null}
          decimals={2}
          unit="GW"
          tone="solar"
          icon={<BatteryCharging className="h-4 w-4" />}
          hint={`${formatPower(totals.solarCap, 0)} solar · ${formatPower(totals.windCap, 0)} wind`}
        />
        <StatCard
          label="Latest daily generation"
          value={totals.gen || null}
          decimals={2}
          unit="MU/day"
          tone="wind"
          icon={<Zap className="h-4 w-4" />}
          hint="sum of latest observed plant days"
        />
        <StatCard
          label="Mapped coordinates"
          value={totals.mapped}
          tone="emerald"
          icon={<MapPinned className="h-4 w-4" />}
          hint={`${totals.count - totals.mapped} without coordinates`}
        />
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))]">
          <label className="block">
            <span className="eyebrow mb-1.5 block">Search</span>
            <span className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-graphite-500" />
              <input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })
                }}
                placeholder="Plant, district, owner…"
                className="ev-input py-2 pl-9"
              />
              {search ? (
                <button
                  type="button"
                  onClick={() => {
                    setSearch('')
                    setParams({}, { replace: true })
                  }}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-graphite-500 hover:text-white"
                  aria-label="Clear search"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              ) : null}
            </span>
          </label>
          <Select
            label="Source"
            value={filters.type}
            onChange={(e) => setFilters((f) => ({ ...f, type: e.target.value }))}
            options={referenceData.types}
          />
          <Select
            label="District"
            value={filters.district}
            onChange={(e) => setFilters((f) => ({ ...f, district: e.target.value }))}
            options={districtOptions}
          />
          <Select
            label="Sort"
            value={filters.sort}
            onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value }))}
            options={referenceData.sorts}
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setFilters(DEFAULT_FILTERS)
                setSearch('')
                setParams({}, { replace: true })
              }}
              className="text-[11px] font-semibold text-graphite-400 underline-offset-2 hover:text-white hover:underline"
            >
              Reset filters
            </button>
          </div>
          <p className="font-mono text-[11px] text-graphite-400">
            {totals.count} / {rows.length} assets matched
          </p>
        </div>
      </Card>

      {loading ? (
        <LoadingState variant="chart" />
      ) : error ? (
        <ErrorState onRetry={refetch} message={error.userMessage || error.message} />
      ) : !rows.length ? (
        <EmptyState icon="Factory" title="No plants available" description="The plant registry returned no assets." />
      ) : view === 'map' ? (
        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card padded={false} className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-graphite-700/70 px-4 py-3.5">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-brand-400/25 bg-brand-400/10 text-brand-300">
                  <MapPinned className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">
                    Geographic Explorer
                  </h3>
                  <p className="eyebrow">highlighted districts contain matching nodes</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="solar" size="sm" dot>
                  {totals.solarCount}
                </Badge>
                <Badge tone="wind" size="sm" dot>
                  {totals.windCount}
                </Badge>
              </div>
            </div>
            <div className="h-[520px] sm:h-[600px] xl:h-[680px]">
              {filtered.length ? (
                <KarnatakaMap plants={filtered} onSelect={(p) => navigate(`/plants/${p.id}`)} />
              ) : (
                <EmptyState
                  icon="MapPin"
                  title="No matches on the map"
                  description="Adjust the filters to highlight plants."
                />
              )}
            </div>
          </Card>

          <Card padded={false} className="flex max-h-[680px] flex-col overflow-hidden">
            <div className="flex items-center justify-between border-b border-graphite-700/70 px-4 py-3.5">
              <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Matched Assets</h3>
              <span className="font-mono text-[11px] text-graphite-400">{filtered.length}</span>
            </div>
            <div className="ev-scroll flex-1 divide-y divide-graphite-800/80 overflow-y-auto">
              {filtered.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => navigate(`/plants/${p.id}`)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.03]"
                >
                  <PlantGlyph type={p.type} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-graphite-100">{p.name}</p>
                    <p className="truncate text-[11px] text-graphite-500">
                      {p.district || 'Karnataka'} · {formatPower(p.capacityMW, 0)}
                    </p>
                    <p className="mt-1 flex items-center gap-1 font-mono text-[10px] text-graphite-500">
                      <CalendarDays className="h-2.5 w-2.5" />
                      {p.latestGenerationDate ? formatDate(p.latestGenerationDate) : 'No observed date'}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-xs font-bold text-white">{formatNumber(p.latestGenerationMU, 2)}</p>
                    <p className="font-mono text-[10px] text-graphite-500">MU/day</p>
                  </div>
                </button>
              ))}
            </div>
          </Card>
        </section>
      ) : (
        <Card padded={false}>
          <div className="flex items-center justify-between border-b border-graphite-700/70 px-4 py-3.5">
            <h3 className="font-display text-[15px] font-semibold tracking-tight text-white">Asset Registry</h3>
            <span className="font-mono text-[11px] text-graphite-400">{sorted.length} rows</span>
          </div>
          <div className="p-3">
            <DataTable
              columns={columns}
              rows={sorted}
              keyField="id"
              onRowClick={(r) => navigate(`/plants/${r.id}`)}
              sort={sort}
              onSortChange={setSort}
              maxHeight={620}
            />
          </div>
        </Card>
      )}

      <SectionTitle
        eyebrow="Reference"
        title="Source mix"
        description="Solar and wind plants share the daily forecasting contract: target DailyGeneration_MU, unit MU/day. No hourly telemetry or synthetic operating statuses are shown."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(RENEWABLE_TYPES).map(([key, meta]) => (
          <Card key={key} className="flex items-center gap-3 p-4">
            <span
              className="flex h-10 w-10 items-center justify-center rounded-lg ring-1 ring-inset"
              style={{ background: `${meta.color}14`, color: meta.color }}
            >
              {key === 'wind' ? <Wind className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
            </span>
            <div>
              <p className="font-display text-sm font-bold text-white">{meta.label} portfolio</p>
              <p className="text-[11px] text-graphite-400">
                {key === 'solar'
                  ? `${totals.solarCount} plants · ${formatPower(totals.solarCap, 0)} installed`
                  : `${totals.windCount} plants · ${formatPower(totals.windCap, 0)} installed`}
              </p>
            </div>
            <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
              <Badge tone={key === 'wind' ? 'wind' : 'solar'} size="sm" mono>
                {key === 'wind' ? 'wind_lstm_daily' : 'solar_lstm_daily'}
              </Badge>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

function totalOrDash(loading, n) {
  return loading ? '—' : n
}
