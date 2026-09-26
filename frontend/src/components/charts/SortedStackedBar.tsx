/**
 * A whole broken into parts, in order, with the parts labelled in place.
 *
 * §13.6 says never a pie, and this is what replaces it. A donut makes people
 * compare angles, which they are measurably bad at, and it needs a legend —
 * so reading it is a lookup. One sorted bar puts the largest slice first, the
 * labels on the segments, and the comparison on one axis.
 *
 * A small segment is drawn and named in the legend rather than merged into
 * "Other". Merging hides a name the reader may be looking for.
 *
 * **The numbers live in the legend, not inside the bar.** White text on an
 * arbitrary palette colour cannot be guaranteed readable — the accessibility
 * walk measured a 10% gold segment at **1.47:1 against the 4.5:1 minimum**, and
 * there is no build-time fix because the colours are CSS variables the viewer's
 * theme can change. So the bar carries proportion, which is what a bar is for,
 * and the legend beneath carries every label and figure at full contrast.
 */
import { ChartFrame, chartState } from './ChartFrame'

export type Segment = {
  label: string
  value: number
  /** For a filled swatch: the bar segment, the legend dot. */
  className?: string
  /** For a stroke or glyph: `AllocationDonut`'s ring. Tailwind's `bg-*` and
      `text-*` utilities are different class names, so a swatch colour cannot
      be reused for a stroke -- an SVG `stroke="currentColor"` reads `color`,
      not `background-color`. Falls back to PALETTE_TEXT by index. */
  strokeClassName?: string
}

// Written out longhand, in both forms, rather than derived from one another
// at runtime (e.g. `className.replace('bg-', 'text-')`): Tailwind scans
// SOURCE TEXT for class names, so a computed string compiles to nothing and
// the donut it feeds would render as a single dark ring with no colour --
// which is exactly the bug this pair of arrays replaced.
export const PALETTE = [
  'bg-sky-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-violet-500',
  'bg-rose-500',
  'bg-teal-500',
  'bg-orange-500',
]

export const PALETTE_TEXT = [
  'text-sky-500',
  'text-emerald-500',
  'text-amber-500',
  'text-violet-500',
  'text-rose-500',
  'text-teal-500',
  'text-orange-500',
]

export function SortedStackedBar({
  segments,
  loading = false,
  label,
  format = (pct: number) => `${pct.toFixed(0)}%`,
  formatValue,
  order = 'value',
}: {
  segments: Segment[]
  loading?: boolean
  label: string
  format?: (pct: number) => string
  /** Optional amount beside each legend entry, e.g. "₹27L". */
  formatValue?: (value: number) => string
  /** `given` keeps the caller's order -- for a fixed set such as asset
      classes, where the same class sitting in the same place every visit
      matters more than largest-first. */
  order?: 'value' | 'given'
}) {
  const total = segments.reduce((sum, s) => sum + Math.max(0, s.value), 0)
  const state = chartState(loading, total > 0 ? segments.length : 0)
  const shown = segments.filter((s) => s.value > 0)
  const sorted = order === 'value' ? [...shown].sort((a, b) => b.value - a.value) : shown

  // The frame wraps the BAR only. It used to wrap the legend too, inside a
  // fixed 64px box, so a legend that wrapped to a third line -- eleven
  // categories do -- spilled out of its panel and over whatever came next.
  return (
    <div className="flex flex-col gap-2">
      <ChartFrame state={state} height={24} label={label} emptyNote="Nothing allocated yet">
        {/* Segments grow in proportion to value from a zero basis, so the
            2px gaps between them come out of the whole rather than pushing
            the last segment past the end of the bar. */}
        <div className="flex h-6 w-full gap-0.5 overflow-hidden rounded-md" role="img" aria-label={label}>
          {sorted.map((s, i) => (
            <div
              key={s.label}
              className={s.className ?? PALETTE[i % PALETTE.length]}
              style={{ flex: `${s.value} 1 0` }}
              title={`${s.label} ${format((s.value / total) * 100)}`}
              aria-hidden
            />
          ))}
        </div>
      </ChartFrame>
      {state === 'ready' && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1">
          {sorted.map((s, i) => (
            <li key={s.label} className="flex items-center gap-1.5 text-xs text-foreground">
              <span
                className={`size-2 rounded-sm ${s.className ?? PALETTE[i % PALETTE.length]}`}
                aria-hidden
              />
              {s.label}
              {formatValue && (
                <span className="num text-muted-foreground">{formatValue(s.value)}</span>
              )}
              <span className="num font-medium">{format((s.value / total) * 100)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
