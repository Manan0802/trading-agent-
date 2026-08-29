/**
 * A whole broken into parts, in order, with the parts labelled in place.
 *
 * §13.6 says never a pie, and this is what replaces it. A donut makes people
 * compare angles, which they are measurably bad at, and it needs a legend —
 * so reading it is a lookup. One sorted bar puts the largest slice first, the
 * labels on the segments, and the comparison on one axis.
 *
 * Segments below `minLabelPct` are drawn and not labelled, rather than merged
 * into "Other". Merging hides a name the reader may be looking for.
 */
import { ChartFrame, chartState } from './ChartFrame'

export type Segment = { label: string; value: number; className?: string }

const PALETTE = [
  'bg-sky-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-violet-500',
  'bg-rose-500',
  'bg-teal-500',
  'bg-orange-500',
]

export function SortedStackedBar({
  segments,
  loading = false,
  label,
  minLabelPct = 8,
  format = (pct: number) => `${pct.toFixed(0)}%`,
}: {
  segments: Segment[]
  loading?: boolean
  label: string
  minLabelPct?: number
  format?: (pct: number) => string
}) {
  const total = segments.reduce((sum, s) => sum + Math.max(0, s.value), 0)
  const state = chartState(loading, total > 0 ? segments.length : 0)
  const sorted = [...segments].filter((s) => s.value > 0).sort((a, b) => b.value - a.value)

  return (
    <ChartFrame state={state} height={64} label={label} emptyNote="Nothing allocated yet">
      <div role="img" aria-label={label}>
        <div className="flex h-6 w-full overflow-hidden rounded-md">
          {sorted.map((s, i) => {
            const pct = (s.value / total) * 100
            return (
              <div
                key={s.label}
                className={`${s.className ?? PALETTE[i % PALETTE.length]} flex items-center justify-center`}
                style={{ width: `${pct}%` }}
                title={`${s.label} ${format(pct)}`}
              >
                {pct >= minLabelPct && (
                  <span className="truncate px-1 text-[10px] font-medium text-white">
                    {format(pct)}
                  </span>
                )}
              </div>
            )
          })}
        </div>
        <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5">
          {sorted.map((s, i) => (
            <li key={s.label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <span className={`size-2 rounded-sm ${s.className ?? PALETTE[i % PALETTE.length]}`} />
              {s.label} <span className="num">{format((s.value / total) * 100)}</span>
            </li>
          ))}
        </ul>
      </div>
    </ChartFrame>
  )
}
