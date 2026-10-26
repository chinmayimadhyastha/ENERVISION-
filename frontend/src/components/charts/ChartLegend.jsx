import { cx } from '../../utils/format.js'

/** Ordered swatch legend used beneath charts. */
export default function ChartLegend({ items = [], className = '', onClick, activeKeys }) {
  return (
    <div className={cx('flex flex-wrap items-center gap-x-4 gap-y-2', className)}>
      {items.map((it) => {
        const dimmed = activeKeys && activeKeys.length > 0 && !activeKeys.includes(it.key)
        return (
          <button
            key={it.key}
            type="button"
            onClick={onClick ? () => onClick(it.key) : undefined}
            className={cx(
              'inline-flex items-center gap-1.5 text-[11px] font-semibold text-graphite-300 transition-opacity',
              onClick && 'hover:text-white',
              dimmed && 'opacity-40',
            )}
          >
            <span
              className="h-2.5 w-2.5 rounded-sm"
              style={{
                background: it.dashed ? 'transparent' : it.color,
                border: it.dashed ? `2px dashed ${it.color}` : undefined,
                boxShadow: it.glow ? `0 0 8px -1px ${it.color}` : undefined,
              }}
            />
            {it.label}
          </button>
        )
      })}
    </div>
  )
}
