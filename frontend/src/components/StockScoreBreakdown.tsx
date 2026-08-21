import { count } from '@/lib/format'
import type { ScoredStock } from '@/lib/screener-api'

const FACTOR_GROUPS = [
  { category: 'fundamental' as const, title: 'The business' },
  { category: 'technical' as const, title: 'Momentum and technicals' },
]

/**
 * How much of a score came from the business and how much from momentum.
 *
 * aria-hidden, and both numbers are written out in the sentence above it: the
 * bar is the thing you notice, the sentence is the thing you can read.
 */
function SplitBar({
  fundamental,
  technical,
  total,
}: {
  fundamental: number
  technical: number
  total: number
}) {
  return (
    <div
      aria-hidden
      className="flex h-1.5 w-full max-w-md overflow-hidden rounded-full bg-secondary"
    >
      <div className="h-full bg-primary" style={{ width: `${(fundamental / total) * 100}%` }} />
      <div
        className="h-full bg-muted-foreground"
        style={{ width: `${(technical / total) * 100}%` }}
      />
    </div>
  )
}

/**
 * All ten factors, split by half, plus who the peers actually were.
 *
 * Shared by the expanded row on the stocks table and the company's own page.
 * Two copies would be two chances for the screens to explain the same score
 * differently — which is the failure `scripts/consistency.py` exists to catch.
 */
export function StockScoreBreakdown({ stock }: { stock: ScoredStock }) {
  const groups = FACTOR_GROUPS.map((g) => {
    const factors = stock.factors.filter((f) => f.category === g.category)
    return {
      ...g,
      factors,
      // Summed rather than hardcoded at 50: the weights are the API's to
      // change, and a hardcoded denominator would go quietly wrong.
      max: factors.reduce((n, f) => n + f.max, 0),
      scored: g.category === 'fundamental' ? stock.fundamental : stock.technical,
    }
  })
  const outOf = groups.reduce((n, g) => n + g.max, 0)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <p className="max-w-3xl text-sm">
          <span className="tnum">{stock.total.toFixed(0)}</span> points out of{' '}
          <span className="tnum">{outOf}</span>:{' '}
          <span className="tnum">{stock.fundamental.toFixed(1)}</span> from the business and{' '}
          <span className="tnum">{stock.technical.toFixed(1)}</span> from momentum and
          technicals.
        </p>
        <SplitBar fundamental={stock.fundamental} technical={stock.technical} total={outOf} />
      </div>

      {groups.map((group) => (
        <div key={group.category} className="flex flex-col gap-2">
          <p className="text-sm font-medium">
            {group.title} — <span className="tnum">{group.scored.toFixed(1)}</span> of{' '}
            <span className="tnum">{group.max}</span> points
          </p>
          <ul className="grid gap-x-10 gap-y-2 xl:grid-cols-2">
            {group.factors.map((factor) => (
              <li key={factor.key} className="flex flex-col text-sm">
                <span>
                  {factor.label} — <span className="tnum">{factor.score.toFixed(1)}</span> of{' '}
                  <span className="tnum">{factor.max}</span>
                </span>
                {/* Written upstream, sentence and all. Rebuilding it here from
                    the numbers is how two screens start disagreeing. */}
                <span className="text-xs text-muted-foreground">{factor.detail}</span>
                {/* And what those initials mean. The line above cannot be
                    reworded — it is held character for character against the
                    source method — so the explanation goes beside it. */}
                {factor.plain && (
                  <span className="text-xs text-muted-foreground italic">{factor.plain}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}

      {stock.adjustments.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">On top of the ten factors</p>
          <ul className="flex flex-col gap-2">
            {stock.adjustments.map((adjustment) => (
              <li key={adjustment.key} className="flex flex-col text-sm">
                <span>
                  {adjustment.label}
                  {/* Zero is not a scoring event. Several of these rows exist
                      only to say something, and "+0.0" reads as one. */}
                  {adjustment.points !== 0 && (
                    <>
                      {' — '}
                      <span className="tnum">
                        {adjustment.points > 0 ? '+' : '−'}
                        {Math.abs(adjustment.points).toFixed(1)}
                      </span>{' '}
                      points
                    </>
                  )}
                </span>
                <span className="text-xs text-muted-foreground">{adjustment.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="max-w-3xl text-sm text-muted-foreground">
        Cheap or expensive is measured against{' '}
        <span className="tnum">{count(stock.benchmark_constituents)}</span> companies in{' '}
        {stock.benchmark_sector}
        {stock.sector && stock.sector !== stock.benchmark_sector
          ? `, which is not its own sector of ${stock.sector} — nothing here has a peer set for that one.`
          : '.'}
        {stock.thin_history
          ? ' It has under 200 days of price history, so its trend factor is measured against a shorter average than everything else here.'
          : ''}
      </p>
    </div>
  )
}
