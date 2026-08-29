/**
 * Two series on the same starting line, so their shapes can be compared.
 *
 * A fund at ₹94 NAV and its benchmark at 26,400 cannot share an axis: the fund
 * is a flat line along the bottom and the chart says nothing. Both are rebased
 * to 100 at the first date they SHARE — rebasing each to its own first point
 * silently compares different periods when one starts earlier, and the result
 * looks entirely normal.
 */
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TOOLTIP_STYLE, axisTick, paddedDomain, rebase } from '@/lib/chart'
import type { ChartRow } from '@/lib/chart'
import { ChartFrame, chartState } from './ChartFrame'

export function RebasedLine({
  rows,
  ownLabel,
  peerLabel,
  loading = false,
  height = 220,
  range = '3y',
  label = 'Growth of the same money',
}: {
  rows: ChartRow[]
  ownLabel: string
  peerLabel: string
  loading?: boolean
  height?: number
  range?: string
  label?: string
}) {
  const state = chartState(loading, rows.length)
  const data = state === 'ready' ? rebase(rows) : []
  const values = data.flatMap((r) => [r.own, r.peer]).filter((v): v is number => v !== null)

  return (
    <ChartFrame
      state={state}
      height={height}
      label={label}
      emptyNote="No overlapping history between these two"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
          <XAxis dataKey="date" tickFormatter={axisTick(range)} tick={{ fontSize: 10 }} minTickGap={28} />
          <YAxis
            domain={values.length ? paddedDomain(values) : [90, 110]}
            tick={{ fontSize: 10 }}
            width={40}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v, key) => [
              `₹${Number(v).toFixed(1)} per ₹100`,
              key === 'own' ? ownLabel : peerLabel,
            ]}
          />
          <Line dataKey="own" stroke="var(--primary)" strokeWidth={1.75} dot={false} isAnimationActive={false} />
          <Line
            dataKey="peer"
            stroke="var(--muted-foreground)"
            strokeWidth={1.25}
            strokeDasharray="4 3"
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
