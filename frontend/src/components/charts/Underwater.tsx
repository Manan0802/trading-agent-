/**
 * How far below its own peak this has been, for every day it existed.
 *
 * The risk device. "Volatility 18%" is a number people nod at; "you were 42%
 * down for fourteen months" is a fact about a year of somebody's life, and it
 * is the one that predicts whether they will still be holding at the bottom.
 *
 * Always drawn from 0 down. Auto-scaling the axis to the worst drawdown makes
 * a fund that fell 8% look exactly like one that fell 60%.
 */
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TOOLTIP_STYLE, axisTick } from '@/lib/chart'
import { ChartFrame, chartState } from './ChartFrame'

export function Underwater({
  points,
  loading = false,
  height = 140,
  range = '3y',
  label = 'Drawdown from the previous peak',
}: {
  points: { date: string; drawdown: number }[]
  loading?: boolean
  height?: number
  range?: string
  label?: string
}) {
  const state = chartState(loading, points.length)
  const worst = state === 'ready' ? Math.min(...points.map((p) => p.drawdown)) : 0

  return (
    <ChartFrame
      state={state}
      height={height}
      label={label}
      emptyNote="No NAV history to measure a fall from"
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: -8 }}>
          <XAxis
            dataKey="date"
            tickFormatter={axisTick(range)}
            tick={{ fontSize: 10 }}
            minTickGap={28}
          />
          <YAxis
            // Fixed at the top, so 0 is always the surface. A relative axis
            // makes an 8% fall and a 60% fall the same picture.
            domain={[Math.min(-5, Math.floor(worst / 5) * 5), 0]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fontSize: 10 }}
            width={38}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(v) => [`${Number(v).toFixed(1)}%`, 'below peak']}
          />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="var(--destructive)"
            fill="var(--destructive)"
            fillOpacity={0.14}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
