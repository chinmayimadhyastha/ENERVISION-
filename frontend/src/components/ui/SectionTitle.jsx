import { cx } from '../../utils/format.js'
import Badge from './Badge.jsx'

/** Section heading used inside pages to group cards. */
export default function SectionTitle({
  title,
  description,
  eyebrow,
  badge,
  tone = 'brand',
  actions,
  className = '',
}) {
  const bar =
    tone === 'solar' ? 'bg-solar-400' : tone === 'wind' ? 'bg-wind-400' : tone === 'violet' ? 'bg-violet-400' : 'bg-brand-400'
  return (
    <div className={cx('flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between', className)}>
      <div>
        {eyebrow ? <p className="eyebrow mb-1">{eyebrow}</p> : null}
        <div className="flex items-center gap-2">
          <span className={cx('h-4 w-1 rounded-full', bar)} />
          <h2 className="font-display text-lg font-bold tracking-tight text-white">{title}</h2>
          {badge ? (
            <Badge tone="neutral" size="sm">
              {badge}
            </Badge>
          ) : null}
        </div>
        {description ? (
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-graphite-400">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  )
}
