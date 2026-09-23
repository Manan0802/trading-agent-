import { useState } from 'react'
import { LayoutGrid, PieChart } from 'lucide-react'
import { AllocationDonut, SortedStackedBar, type Segment } from '@/components/charts'
import { Panel } from '@/components/ui/panel'
import { formatInr } from '@/lib/format'
import type { HoldingSummary } from '@/lib/portfolio-api'
import { cn } from '@/lib/utils'

const CLASS_LABEL: Record<string, string> = {
  equity: 'Equity',
  international: 'International',
  debt: 'Debt',
  gold: 'Gold',
  hybrid: 'Hybrid',
  other: 'Unclassified',
}

/**
 * Fixed order, not sorted by size: the same class is always the same colour
 * from one look to the next, which sorting by value would break.
 *
 * Both the fill (`bg-*`, for the bar segment and the legend dot) and the
 * stroke (`text-*`, for the donut ring) are written out as literal strings.
 * Deriving one from the other at runtime (`.replace('bg-', 'text-')`) is the
 * bug this shape replaced: Tailwind scans SOURCE TEXT for class names, so a
 * computed string compiles to nothing and the donut painted every segment
 * the same default ink colour.
 */
const CLASS_TONE: Record<string, { bg: string; text: string }> = {
  equity: { bg: 'bg-v-indigo', text: 'text-v-indigo' },
  international: { bg: 'bg-v-rose', text: 'text-v-rose' },
  gold: { bg: 'bg-v-amber', text: 'text-v-amber' },
  debt: { bg: 'bg-v-violet', text: 'text-v-violet' },
  hybrid: { bg: 'bg-v-cyan', text: 'text-v-cyan' },
  other: { bg: 'bg-muted-foreground/50', text: 'text-muted-foreground' },
}

function toSegments(
  holdings: HoldingSummary[],
  key: (h: HoldingSummary) => string,
  label: (key: string) => string,
  tone?: (key: string) => { bg: string; text: string } | undefined,
): Segment[] {
  const by = new Map<string, number>()
  for (const h of holdings) {
    const value = h.current_value
    if (value === null || value <= 0) continue
    const k = key(h) || 'other'
    by.set(k, (by.get(k) ?? 0) + value)
  }
  return [...by.entries()].map(([k, value]) => {
    const t = tone?.(k)
    return { label: label(k), value, className: t?.bg, strokeClassName: t?.text }
  })
}

/**
 * Where the money actually sits, in two cuts: broad asset class, then category
 * within it. §13.6 says never a pie; this app has one user and he asked for a
 * donut anyway, so both views exist and a toggle switches between them --
 * reading the same `Segment[]`, so they can never show different numbers.
 */
export function AllocationBreakdown({ holdings }: { holdings: HoldingSummary[] }) {
  const [view, setView] = useState<'bar' | 'donut'>('bar')

  const byClass = toSegments(
    holdings,
    (h) => h.asset_class ?? 'other',
    (k) => CLASS_LABEL[k] ?? k,
    (k) => CLASS_TONE[k],
  )
  // "Category" has no fixed palette -- it is whichever sub-categories this
  // portfolio actually holds -- so it falls through to PALETTE/PALETTE_TEXT
  // by index, the same pairing the bar and the donut already agree on.
  const byCategory = toSegments(
    holdings,
    (h) => h.sub_category ?? 'Unclassified',
    (k) => k,
  )

  const unclassifiedValue = holdings
    .filter((h) => (h.asset_class ?? 'other') === 'other')
    .reduce((sum, h) => sum + (h.current_value ?? 0), 0)

  if (byClass.length === 0) return null

  const Chart = view === 'bar' ? SortedStackedBar : AllocationDonut

  return (
    <Panel
      title="Where your money is"
      aside={
        <div className="flex items-center gap-1" role="group" aria-label="Chart style">
          {(
            [
              ['bar', 'Bar', LayoutGrid],
              ['donut', 'Donut', PieChart],
            ] as const
          ).map(([value, label, Icon]) => (
            <button
              key={value}
              type="button"
              aria-pressed={view === value}
              onClick={() => setView(value)}
              className={cn(
                'inline-flex min-h-8 items-center gap-1 rounded-md px-2 text-xs transition-colors',
                view === value
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Icon className="size-3.5" aria-hidden />
              {label}
            </button>
          ))}
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Asset class
          </p>
          <Chart segments={byClass} label="Portfolio value by asset class" />
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Category
          </p>
          <Chart segments={byCategory} label="Portfolio value by category" />
        </div>
      </div>

      {unclassifiedValue > 0 && (
        <p className="text-xs text-muted-foreground">
          <span className="num">{formatInr(unclassifiedValue)}</span> could not be placed in a
          class -- its category is not in the AMFI catalogue this reads from. Shown as
          Unclassified rather than guessed.
        </p>
      )}
    </Panel>
  )
}
