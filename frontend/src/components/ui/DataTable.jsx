import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react'
import { cx } from '../../utils/format.js'
import EmptyState from './EmptyState.jsx'

/**
 * Responsive data table.
 *
 * columns: [{ key, header, align, className, sortable, render(row, index) }]
 * Sticky header, horizontal scroll on small screens, optional row click.
 */
export default function DataTable({
  columns = [],
  rows = [],
  keyField = 'id',
  onRowClick,
  emptyTitle = 'No records found',
  emptyDescription = 'Try adjusting the filters above.',
  className = '',
  maxHeight,
  sort,
  onSortChange,
  dense = false,
}) {
  const cellPad = dense ? 'px-3 py-2' : 'px-4 py-2.5'

  const handleSort = (col) => {
    if (!col.sortable || !onSortChange) return
    const dir = sort?.key === col.key && sort.dir === 'asc' ? 'desc' : 'asc'
    onSortChange({ key: col.key, dir })
  }

  if (!rows.length) {
    return (
      <div className={cx('rounded-lg border border-dashed border-graphite-650 bg-graphite-900/40', className)}>
        <EmptyState title={emptyTitle} description={emptyDescription} />
      </div>
    )
  }

  return (
    <div className={cx('relative overflow-hidden rounded-lg border border-graphite-700/80', className)}>
      <div className="ev-scroll overflow-x-auto" style={maxHeight ? { maxHeight } : undefined}>
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="sticky top-0 z-10 bg-graphite-900/95 backdrop-blur">
              {columns.map((col) => {
                const align = col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                const isSorted = sort?.key === col.key
                return (
                  <th
                    key={col.key}
                    scope="col"
                    onClick={() => handleSort(col)}
                    className={cx(
                      'border-b border-graphite-700 bg-graphite-900/95 px-4 py-2.5',
                      'text-[10px] font-bold uppercase tracking-[0.12em] text-graphite-400',
                      align,
                      col.sortable && 'cursor-pointer select-none hover:text-graphite-100',
                      col.className,
                    )}
                  >
                    <span className={cx('inline-flex items-center gap-1', col.align === 'right' && 'flex-row-reverse')}>
                      {col.header}
                      {col.sortable ? (
                        isSorted ? (
                          sort.dir === 'asc' ? (
                            <ArrowUp className="h-3 w-3 text-brand-300" />
                          ) : (
                            <ArrowDown className="h-3 w-3 text-brand-300" />
                          )
                        ) : (
                          <ChevronsUpDown className="h-3 w-3 text-graphite-500" />
                        )
                      ) : null}
                    </span>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={row[keyField] ?? i}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cx(
                  'group border-b border-graphite-800/80 transition-colors last:border-0',
                  onRowClick && 'cursor-pointer hover:bg-white/[0.035]',
                  !onRowClick && 'hover:bg-white/[0.02]',
                )}
              >
                {columns.map((col) => {
                  const align =
                    col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
                  return (
                    <td key={col.key} className={cx(cellPad, 'align-middle text-graphite-200', align, col.className)}>
                      {col.render ? col.render(row, i) : row[col.key]}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
