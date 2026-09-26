import { useState } from 'react'
import { LayoutGrid, PieChart } from 'lucide-react'
import { AllocationDonut, SortedStackedBar, type Segment } from '@/components/charts'
import { Panel } from '@/components/ui/panel'
import { formatInr, formatInrCompact } from '@/lib/format'
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

type Tone = { bg: string; text: string }

/**
 * Asset classes in a FIXED order, each with a fixed colour, so Equity is the
 * same blue in the same place on every visit -- colour follows the class,
 * never its rank this month.
 *
 * Every class is written out longhand, fill and stroke, light and dark:
 * Tailwind builds only the class names it can find in source text, so a
 * name assembled at runtime (`.replace('bg-', 'text-')`) compiles to nothing.
 *
 * The hexes are a checked set, not a pick by eye. Run through a colour-
 * blindness validator in both themes, every neighbour in this order stays
 * distinguishable -- including when a class is missing and its two
 * neighbours meet. The old set failed that: indigo against violet was
 * delta-E 3.8 for a protanope, the same colour to one reader in twelve.
 */
const CLASS_ORDER = ['equity', 'international', 'debt', 'gold', 'hybrid', 'other'] as const

const CLASS_TONE: Record<string, Tone> = {
  equity: { bg: 'bg-[#2a78d6] dark:bg-[#3987e5]', text: 'text-[#2a78d6] dark:text-[#3987e5]' },
  international: { bg: 'bg-[#eb6834] dark:bg-[#d95926]', text: 'text-[#eb6834] dark:text-[#d95926]' },
  debt: { bg: 'bg-[#1baf7a] dark:bg-[#199e70]', text: 'text-[#1baf7a] dark:text-[#199e70]' },
  gold: { bg: 'bg-[#eda100] dark:bg-[#c98500]', text: 'text-[#eda100] dark:text-[#c98500]' },
  hybrid: { bg: 'bg-[#e87ba4] dark:bg-[#d55181]', text: 'text-[#e87ba4] dark:text-[#d55181]' },
  other: { bg: 'bg-muted-foreground/40', text: 'text-muted-foreground/40' },
}

/**
 * Categories are whatever this portfolio holds, so they are coloured by rank,
 * largest first, from the same validated sequence. Six colours and no more:
 * the old version cycled a seven-colour palette over eleven categories, so
 * Flexi Cap and Mid Cap were the same blue and the ring could not be read.
 * Past six, the rest are folded into "Other" -- and named underneath, so no
 * category disappears.
 */
const RANK_TONES: Tone[] = [
  { bg: 'bg-[#2a78d6] dark:bg-[#3987e5]', text: 'text-[#2a78d6] dark:text-[#3987e5]' },
  { bg: 'bg-[#eb6834] dark:bg-[#d95926]', text: 'text-[#eb6834] dark:text-[#d95926]' },
  { bg: 'bg-[#1baf7a] dark:bg-[#199e70]', text: 'text-[#1baf7a] dark:text-[#199e70]' },
  { bg: 'bg-[#eda100] dark:bg-[#c98500]', text: 'text-[#eda100] dark:text-[#c98500]' },
  { bg: 'bg-[#e87ba4] dark:bg-[#d55181]', text: 'text-[#e87ba4] dark:text-[#d55181]' },
  { bg: 'bg-[#008300]', text: 'text-[#008300]' },
]
const MAX_CATEGORIES = RANK_TONES.length

/** Rupees per key, positive holdings only. */
function sumBy(holdings: HoldingSummary[], key: (h: HoldingSummary) => string): Map<string, number> {
  const by = new Map<string, number>()
  for (const h of holdings) {
    const value = h.current_value
    if (value === null || value <= 0) continue
    const k = key(h)
    by.set(k, (by.get(k) ?? 0) + value)
  }
  return by
}

/**
 * Where the money actually sits, in two cuts: broad asset class, then category
 * within it. §13.6 says never a pie; this app has one user and he asked for a
 * donut anyway, so both views exist and a toggle switches between them --
 * reading the same `Segment[]`, so they can never show different numbers.
 */
export function AllocationBreakdown({ holdings }: { holdings: HoldingSummary[] }) {
  const [view, setView] = useState<'bar' | 'donut'>('bar')

  const classTotals = sumBy(holdings, (h) => h.asset_class ?? 'other')
  const byClass: Segment[] = CLASS_ORDER.filter((k) => classTotals.has(k)).map((k) => ({
    label: CLASS_LABEL[k],
    value: classTotals.get(k) ?? 0,
    className: CLASS_TONE[k].bg,
    strokeClassName: CLASS_TONE[k].text,
  }))

  const ranked = [...sumBy(holdings, (h) => h.sub_category ?? 'Unclassified').entries()].sort(
    (a, b) => b[1] - a[1],
  )
  const folded = ranked.length > MAX_CATEGORIES ? ranked.slice(MAX_CATEGORIES) : []
  const kept = folded.length > 0 ? ranked.slice(0, MAX_CATEGORIES) : ranked
  const byCategory: Segment[] = [
    ...kept.map(([label, value], i) => ({
      label,
      value,
      className: RANK_TONES[i].bg,
      strokeClassName: RANK_TONES[i].text,
    })),
    ...(folded.length > 0
      ? [
          {
            label: `Other (${folded.length})`,
            value: folded.reduce((sum, [, v]) => sum + v, 0),
            className: CLASS_TONE.other.bg,
            strokeClassName: CLASS_TONE.other.text,
          },
        ]
      : []),
  ]

  const total = holdings.reduce((sum, h) => sum + Math.max(0, h.current_value ?? 0), 0)
  const center = { value: formatInrCompact(total), caption: 'total' }

  const unclassifiedValue = holdings
    .filter((h) => (h.asset_class ?? 'other') === 'other')
    .reduce((sum, h) => sum + (h.current_value ?? 0), 0)

  if (byClass.length === 0) return null


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
          <AllocationChart
            view={view}
            segments={byClass}
            order="given"
            formatValue={formatInrCompact}
            center={center}
            label="Portfolio value by asset class"
          />
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Category
          </p>
          <AllocationChart
            view={view}
            segments={byCategory}
            order="given"
            formatValue={formatInrCompact}
            center={center}
            label="Portfolio value by category"
          />
          {folded.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Other: {folded.map(([label]) => label).join(', ')}
            </p>
          )}
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

/** One of the two drawings of the same segments. */
function AllocationChart({
  view,
  center,
  ...props
}: {
  view: 'bar' | 'donut'
  segments: Segment[]
  label: string
  order: 'value' | 'given'
  formatValue: (value: number) => string
  center: { value: string; caption: string }
}) {
  return view === 'bar' ? (
    <SortedStackedBar {...props} />
  ) : (
    <AllocationDonut {...props} center={center} />
  )
}
