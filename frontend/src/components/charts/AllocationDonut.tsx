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

const SIZE = 168
const STROKE = 24
const RADIUS = (SIZE - STROKE) / 2
/** Gap between segments, in `pathLength` units (percent of the ring). */
const GAP = 0.8

export function AllocationDonut({
  segments,
  loading = false,
  label,
  format = (pct: number) => `${pct.toFixed(0)}%`,
  formatValue,
  order = 'value',
  center,
}: {
  segments: Segment[]
  loading?: boolean
  label: string
  format?: (pct: number) => string
  formatValue?: (value: number) => string
  order?: 'value' | 'given'
  /** A figure in the hole, e.g. the total the ring divides up. */
  center?: { value: string; caption: string }
}) {
  const total = segments.reduce((sum, s) => sum + Math.max(0, s.value), 0)
  const state = chartState(loading, total > 0 ? segments.length : 0)
  const shown = segments.filter((s) => s.value > 0)
  const sorted = order === 'value' ? [...shown].sort((a, b) => b.value - a.value) : shown
  const gap = sorted.length > 1 ? GAP : 0

  // Measured in `pathLength` units (the ring is 100 long), not pixels. A
  // dasharray computed from 2*pi*r does not match the length the browser
  // actually draws -- it approximates a circle's path -- so the first
  // segment's pattern repeated a sliver past the end of the ring: a notch of
  // equity blue sitting inside the last segment at twelve o'clock.
  let start = 0
  const arcs = sorted.map((s, i) => {
    const pct = (s.value / total) * 100
    const arc = { s, i, dash: Math.max(0, pct - gap), start }
    start += pct
    return arc
  })

  // The frame wraps the RING only. It used to wrap the legend too, at the
  // ring's fixed height, so an eleven-row legend ran out of its panel and
  // over the filters beneath it.
  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
      <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
        <ChartFrame state={state} height={SIZE} label={label} emptyNote="Nothing allocated yet">
          <svg
            width={SIZE}
            height={SIZE}
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            role="img"
            aria-label={label}
            className="-rotate-90"
          >
            {arcs.map(({ s, i, dash, start: at }) => (
              <circle
                key={s.label}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                fill="none"
                pathLength={100}
                className={s.strokeClassName ?? PALETTE_TEXT[i % PALETTE_TEXT.length]}
                stroke="currentColor"
                strokeWidth={STROKE}
                strokeDasharray={`${dash} ${100 - dash}`}
                strokeDashoffset={-at}
              />
            ))}
          </svg>
        </ChartFrame>
        {state === 'ready' && center && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="num text-lg font-semibold leading-none">{center.value}</span>
            <span className="mt-1 text-[11px] text-muted-foreground">{center.caption}</span>
          </div>
        )}
      </div>
      {state === 'ready' && (
        // Capped width, so a figure sits beside its label instead of at the
        // far edge of a half-page column.
        <ul className="flex w-full max-w-xs flex-col gap-1.5">
          {sorted.map((s, i) => (
            <li key={s.label} className="flex items-center gap-2 text-sm text-foreground">
              <span
                className={`size-2.5 shrink-0 rounded-sm ${s.className ?? PALETTE[i % PALETTE.length]}`}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate">{s.label}</span>
              {formatValue && (
                <span className="num shrink-0 text-xs text-muted-foreground">
                  {formatValue(s.value)}
                </span>
              )}
              <span className="num w-10 shrink-0 text-right font-medium">
                {format((s.value / total) * 100)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
