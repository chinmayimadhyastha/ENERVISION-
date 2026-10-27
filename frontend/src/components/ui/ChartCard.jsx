import { cx } from '../../utils/format.js'
import { CardHeader } from './Card.jsx'

/**
 * Card wrapper purpose-built for charts: fixed-height chart area, header with
 * optional actions, optional footer legend/summary and an optional accent
 * hairline. Optional `grid` lays a faint technical grid behind the plot.
 */
export default function ChartCard({
  title,
  subtitle,
  icon,
  tone = 'brand',
  accent = 'none',
  actions,
  footer,
  height = 300,
  className = '',
  bodyClassName = '',
  padded = true,
  grid = false,
  children,
}) {
  return (
    <div
      className={cx(
        'panel flex h-full flex-col overflow-hidden',
        accent !== 'none' &&
          cx(
            'before:absolute before:inset-x-0 before:top-0 before:h-px before:content-[""]',
            accent === 'solar' && 'before:bg-solar-400',
            accent === 'wind' && 'before:bg-wind-400',
            accent === 'violet' && 'before:bg-violet-400',
            accent === 'brand' && 'before:bg-brand-400',
          ),
        padded && 'p-4 sm:p-5',
        className,
      )}
    >
      {title ? <CardHeader title={title} subtitle={subtitle} icon={icon} tone={tone} actions={actions} /> : null}

      <div className={cx('relative w-full min-w-0 shrink-0', title && 'mt-4', bodyClassName)} style={{ height }}>
        {grid ? (
          <div className="pointer-events-none absolute inset-0 ev-grid-sm opacity-60" aria-hidden />
        ) : null}
        {children}
      </div>

      {footer ? (
        <div className="mt-3 border-t border-graphite-700/70 pt-3">{footer}</div>
      ) : null}
    </div>
  )
}
