import { useId } from 'react'
import { Area, AreaChart, ResponsiveContainer } from 'recharts'

/**
 * Tiny inline sparkline for stat tiles. Deterministic — receives its own data.
 */
export default function MiniSparkline({ data = [], color = '#2dd4bf', dataKey = 'value', height = 32 }) {
  const id = useId().replace(/:/g, '')
  if (!data.length) return null
  const gradId = `spark-${id}`
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={1.8}
            fill={`url(#${gradId})`}
            isAnimationActive
            animationDuration={700}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
