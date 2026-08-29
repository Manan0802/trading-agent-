/**
 * A count you can see, one dot per unit.
 *
 * For "43 of 52 rolling windows were positive". A bar at 83% is a shape; forty
 * three filled dots beside nine empty ones is a number a person can check, and
 * checking is the point — this app's central claim is a base rate, and a base
 * rate shown as a percentage invites belief where a count invites arithmetic.
 *
 * Above `maxDots` it falls back to grouping, because a hundred dots is texture.
 */
import { ChartFrame, chartState } from './ChartFrame'

export function DotGrid({
  filled,
  total,
  loading = false,
  label,
  perRow = 13,
  maxDots = 120,
}: {
  filled: number
  total: number
  loading?: boolean
  label: string
  perRow?: number
  maxDots?: number
}) {
  const state = chartState(loading, total)
  const scale = total > maxDots ? total / maxDots : 1
  const dots = state === 'ready' ? Math.round(total / scale) : 0
  const on = Math.round(filled / scale)
  const rows = Math.ceil(dots / perRow)

  return (
    <ChartFrame
      state={state}
      height={Math.max(20, rows * 12 + 4)}
      label={label}
      emptyNote="No windows measured"
    >
      <div className="flex flex-wrap gap-[3px]" role="img" aria-label={label}>
        {Array.from({ length: dots }, (_, i) => (
          <span
            key={i}
            className={
              i < on
                ? 'size-[7px] rounded-full bg-emerald-500'
                : 'size-[7px] rounded-full border border-muted-foreground/40'
            }
          />
        ))}
        {scale > 1 && (
          <span className="ml-1 self-center text-[10px] text-muted-foreground">
            each dot ≈ {Math.round(scale)}
          </span>
        )}
      </div>
    </ChartFrame>
  )
}
