/**
 * One fund's shape, small enough to sit in a table row.
 *
 * §3.2 puts one of these in every `Find` row, which is the constraint that
 * shaped it: 1,689 rows means this renders up to a hundred times per page, so
 * it is a single <path> in plain SVG rather than a recharts container. A
 * ResponsiveContainer per row is a ResizeObserver per row.
 *
 * No axes, no ticks, no tooltip. A sparkline that needs a label is a chart.
 */
import { ChartFrame, chartState } from './ChartFrame'

export function Sparkline({
  values,
  loading = false,
  width = 88,
  height = 24,
  label,
}: {
  values: number[]
  loading?: boolean
  width?: number
  height?: number
  label: string
}) {
  const state = chartState(loading, values.length >= 2 ? values.length : 0)

  let path = ''
  let up = true
  if (state === 'ready') {
    const low = Math.min(...values)
    const high = Math.max(...values)
    // A flat series has zero range; dividing by it puts every point at NaN and
    // the row renders an empty box that looks like missing data.
    const span = high - low || 1
    const step = width / (values.length - 1)
    path = values
      .map((v, i) => {
        const x = i * step
        const y = height - ((v - low) / span) * height
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
    up = values[values.length - 1] >= values[0]
  }

  return (
    <ChartFrame state={state} height={height} label={label} emptyNote="No history">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img">
        <title>{label}</title>
        <path
          d={path}
          fill="none"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          className={up ? 'stroke-emerald-500' : 'stroke-rose-500'}
        />
      </svg>
    </ChartFrame>
  )
}
