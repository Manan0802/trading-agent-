/**
 * A range of outcomes, drawn as a range.
 *
 * The device that exists to stop a projection being read as a promise. A single
 * line to "₹48,20,000 in ten years" is a number people plan around; the same
 * projection drawn as a widening band says the thing the arithmetic actually
 * supports, which is that the spread grows faster than the middle.
 *
 * The median is drawn LAST and thin. Draw it first and thick and the band reads
 * as decoration around the real answer, which is the opposite of the point.
 */
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TOOLTIP_STYLE } from '@/lib/chart'
import { formatInrCompact } from '@/lib/format'
import { ChartFrame, chartState } from './ChartFrame'

export type FanPoint = { year: number; low: number; median: number; high: number }

export function Fan({
  points,
  loading = false,
  height = 200,
  label = 'Range of outcomes',
}: {
  points: FanPoint[]
  loading?: boolean
  height?: number
  label?: string
}) {
  const state = chartState(loading, points.length)
  // Recharts stacks an Area on a base, so the band is drawn as (low, high-low).
  const rows = points.map((p) => ({ ...p, band: p.high - p.low }))

  return (
    <ChartFrame
      state={state}
      height={height}
      label={label}
      emptyNote="Enter an amount and a horizon to see the range"
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 6, right: 6, bottom: 0, left: -4 }}>
          <XAxis
            dataKey="year"
            tick={{ fontSize: 10 }}
            tickFormatter={(y: number) => `${y}y`}
          />
          <YAxis tickFormatter={formatInrCompact} tick={{ fontSize: 10 }} width={52} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v, name) => [
              formatInrCompact(Number(v)),
              name === 'low' ? 'worse case' : name === 'band' ? 'range' : 'middle',
            ]}
          />
          <Area
            dataKey="low"
            stackId="fan"
            stroke="none"
            fill="transparent"
            isAnimationActive={false}
          />
          <Area
            dataKey="band"
            stackId="fan"
            stroke="none"
            fill="var(--primary)"
            fillOpacity={0.16}
            isAnimationActive={false}
          />
          <Line
            dataKey="median"
            stroke="var(--primary)"
            strokeWidth={1.25}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
