/**
 * One value against its peer group, on the group's own scale.
 *
 * Replaces the gauge and the star rating. A fund's 0.62% TER means nothing
 * alone; against a category running 0.31% to 2.11% with a median of 0.94% it
 * means "cheaper than most", and the reader can see how much of the range they
 * are looking at rather than being told a grade.
 *
 * `lowerIsBetter` exists because this device is used for cost as often as for
 * return, and colouring 'high' as good on an expense ratio is the kind of
 * mistake that survives review.
 */
import { ChartFrame, chartState } from './ChartFrame'

export function Bullet({
  value,
  median,
  low,
  high,
  loading = false,
  label,
  lowerIsBetter = false,
  format = (v: number) => v.toFixed(2),
}: {
  value: number | null
  median: number | null
  low: number | null
  high: number | null
  loading?: boolean
  label: string
  lowerIsBetter?: boolean
  format?: (v: number) => string
}) {
  const measurable =
    value !== null && low !== null && high !== null && high > low ? 1 : 0
  const state = chartState(loading, measurable)

  let pct = 0
  let medianPct: number | null = null
  let good = false
  if (state === 'ready') {
    pct = ((value! - low!) / (high! - low!)) * 100
    medianPct = median === null ? null : ((median - low!) / (high! - low!)) * 100
    good = lowerIsBetter ? value! <= (median ?? value!) : value! >= (median ?? value!)
  }

  return (
    <ChartFrame
      state={state}
      height={34}
      label={label}
      // Never "0" — an unmeasured peer group is not a fund at the bottom of it.
      emptyNote="Its peer group is too small to place this against"
    >
      <div role="img" aria-label={`${label}: ${value === null ? 'n/a' : format(value)}`}>
        <div className="relative h-2 w-full rounded-full bg-muted">
          {medianPct !== null && (
            <span
              className="absolute top-[-3px] h-[14px] w-px bg-muted-foreground/70"
              style={{ left: `${medianPct}%` }}
              title="category median"
            />
          )}
          <span
            className={`absolute top-[-2px] size-3 -translate-x-1/2 rounded-full ${
              good ? 'bg-emerald-500' : 'bg-amber-500'
            }`}
            style={{ left: `${Math.min(100, Math.max(0, pct))}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
          <span className="num">{low === null ? 'n/a' : format(low)}</span>
          <span className="num font-medium text-foreground">
            {value === null ? 'n/a' : format(value)}
          </span>
          <span className="num">{high === null ? 'n/a' : format(high)}</span>
        </div>
      </div>
    </ChartFrame>
  )
}
