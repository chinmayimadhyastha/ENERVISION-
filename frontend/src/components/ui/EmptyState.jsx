import { cx } from '../../utils/format.js'
import { Icon } from './Icon.jsx'

export default function EmptyState({
  icon = 'Search',
  title = 'Nothing to show',
  description,
  action,
  className = '',
}) {
  return (
    <div className={cx('flex flex-col items-center justify-center px-6 py-12 text-center', className)}>
      <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-graphite-700 bg-graphite-900/70 text-graphite-400">
        {typeof icon === 'string' ? <Icon name={icon} className="h-5 w-5" /> : icon}
      </span>
      <h3 className="mt-3 font-display text-sm font-bold text-graphite-100">{title}</h3>
      {description ? <p className="mt-1 max-w-sm text-xs leading-relaxed text-graphite-400">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
