/**
 * The same allocation as `SortedStackedBar`, drawn as rings instead of a bar.
 *
 * §13.6 says never a pie — a donut asks the eye to compare angles, which it
 * is measurably bad at. This app has exactly one user, and he asked for the
 * donut anyway ("humare rules hai, no worries"), so it exists as a second
 * VIEW of the same numbers rather than a replacement: `AllocationChart`
 * toggles between this and the bar, and both read the same `Segment[]`, so
 * they can never disagree with each other.
 *
 * The numbers live in the legend, not painted on the ring — same reason as
 * the bar: a segment's own colour cannot promise 4.5:1 text contrast against
 * itself, and the legend can.
 */
import { ChartFrame, chartState } from './ChartFrame'
import { PALETTE, PALETTE_TEXT, type Segment } from './SortedStackedBar'

const SIZE = 160
const STROKE = 22
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function AllocationDonut({
  segments,
  loading = false,
  label,
  format = (pct: number) => `${pct.toFixed(0)}%`,
}: {
  segments: Segment[]
  loading?: boolean
  label: string
  format?: (pct: number) => string
}) {
  const total = segments.reduce((sum, s) => sum + Math.max(0, s.value), 0)
  const state = chartState(loading, total > 0 ? segments.length : 0)
  const sorted = [...segments].filter((s) => s.value > 0).sort((a, b) => b.value - a.value)

  // Each ring segment's arc, walking around the circle from the top (-90deg).
  let offset = 0
  const arcs = sorted.map((s, i) => {
    const frac = s.value / total
    const dash = frac * CIRCUMFERENCE
    const arc = { s, i, dash, gapBefore: offset }
    offset += dash
    return arc
  })

  return (
    <ChartFrame state={state} height={SIZE} label={label} emptyNote="Nothing allocated yet">
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="img"
          aria-label={label}
          className="shrink-0 -rotate-90"
        >
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            className="stroke-muted"
            strokeWidth={STROKE}
          />
          {arcs.map(({ s, i, dash, gapBefore }) => (
            <circle
              key={s.label}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              className={s.strokeClassName ?? PALETTE_TEXT[i % PALETTE_TEXT.length]}
              stroke="currentColor"
              strokeWidth={STROKE}
              strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
              strokeDashoffset={-gapBefore}
              strokeLinecap="butt"
            />
          ))}
        </svg>
        <ul className="flex flex-1 flex-col gap-1.5">
          {sorted.map((s, i) => (
            <li key={s.label} className="flex items-center gap-1.5 text-sm text-foreground">
              <span
                className={`size-2.5 shrink-0 rounded-sm ${s.className ?? PALETTE[i % PALETTE.length]}`}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate">{s.label}</span>
              <span className="num shrink-0 font-medium">{format((s.value / total) * 100)}</span>
            </li>
          ))}
        </ul>
      </div>
    </ChartFrame>
  )
}
