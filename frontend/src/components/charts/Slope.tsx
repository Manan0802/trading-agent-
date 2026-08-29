/**
 * Two points and the line between them: what changed, for several things at once.
 *
 * For "your allocation now vs your target", or "this fund's rank last year vs
 * this year". A grouped bar chart answers "how big" and buries "which way";
 * a slope chart answers "which way" first, which is the question.
 *
 * Labels sit on both ends. A slope chart with a legend is a line chart.
 */
import { ChartFrame, chartState } from './ChartFrame'

export type SlopeRow = { label: string; from: number; to: number }

export function Slope({
  rows,
  loading = false,
  height = 160,
  fromLabel,
  toLabel,
  format = (v: number) => `${v.toFixed(0)}%`,
  label = 'Change between two points',
}: {
  rows: SlopeRow[]
  loading?: boolean
  height?: number
  fromLabel: string
  toLabel: string
  format?: (v: number) => string
  label?: string
}) {
  const state = chartState(loading, rows.length)
  const values = rows.flatMap((r) => [r.from, r.to])
  const low = state === 'ready' ? Math.min(...values) : 0
  const high = state === 'ready' ? Math.max(...values) : 1
  const span = high - low || 1
  const top = 16
  const plot = height - top - 18
  const y = (v: number) => top + plot - ((v - low) / span) * plot

  return (
    <ChartFrame state={state} height={height} label={label} emptyNote="Nothing to compare yet">
      <svg width="100%" height={height} role="img" aria-label={label}>
        <title>{label}</title>
        {rows.map((r) => {
          const rising = r.to >= r.from
          return (
            <g key={r.label}>
              <line
                x1="28%"
                y1={y(r.from)}
                x2="72%"
                y2={y(r.to)}
                strokeWidth={1.75}
                className={rising ? 'stroke-emerald-500' : 'stroke-rose-500'}
              />
              <circle cx="28%" cy={y(r.from)} r={3} className="fill-muted-foreground" />
              <circle
                cx="72%"
                cy={y(r.to)}
                r={3.5}
                className={rising ? 'fill-emerald-500' : 'fill-rose-500'}
              />
              <text
                x="26%"
                y={y(r.from) + 3}
                textAnchor="end"
                className="fill-muted-foreground text-[10px]"
              >
                {r.label} {format(r.from)}
              </text>
              <text x="74%" y={y(r.to) + 3} className="fill-foreground text-[10px]">
                {format(r.to)}
              </text>
            </g>
          )
        })}
        <text x="28%" y={height - 4} textAnchor="middle" className="fill-muted-foreground text-[10px]">
          {fromLabel}
        </text>
        <text x="72%" y={height - 4} textAnchor="middle" className="fill-muted-foreground text-[10px]">
          {toLabel}
        </text>
      </svg>
    </ChartFrame>
  )
}
