import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr, formatPercent } from '@/lib/format'
import { fetchCostReview } from '@/lib/portfolio-api'

/**
 * What the regular-plan funds in this portfolio cost against their direct
 * equivalents. Both plans own the identical portfolio; the difference is a
 * distributor commission taken out of the regular plan's NAV every day, and
 * AMFI publishes both figures, so this is a measured fee rather than an
 * estimate.
 */
export function CostReview({ yearsRemaining = 15 }: { yearsRemaining?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['cost-review', yearsRemaining],
    queryFn: () => fetchCostReview(yearsRemaining),
  })

  if (isLoading) return <Skeleton className="h-20 w-full" />
  if (!data) return null

  const clean = data.flagged.length === 0 && data.unpriced.length === 0

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium">What your funds cost</h2>

      <p
        className={
          clean
            ? 'max-w-3xl border-l-2 py-1 pl-3 text-sm text-muted-foreground'
            : 'max-w-3xl border-l-2 border-loss py-1 pl-3 text-sm'
        }
      >
        {data.summary}
      </p>

      {data.flagged.length > 0 && (
        <ul className="flex flex-col divide-y border-y">
          {data.flagged.map((f) => (
            <li key={f.name} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-2.5">
              <div className="flex max-w-2xl flex-col gap-0.5">
                <span className="text-sm leading-tight">{f.name}</span>
                <span className="tnum text-xs text-muted-foreground">
                  {formatInr(f.value)} held &middot;{' '}
                  {formatPercent(f.ter_gap, { signed: false })} a year more than the
                  direct plan
                </span>
                {/* The scheme to actually buy. Without this the advice stops at
                    "switch to the direct plan" and the reader is left guessing
                    in a broker's search box, which is where a plan like this
                    dies. */}
                {f.direct_name && (
                  <span className="text-xs leading-snug text-muted-foreground">
                    Buy instead:{' '}
                    <span className="text-foreground">{f.direct_name}</span>
                    {f.direct_code && (
                      <>
                        {' '}
                        <span className="tnum">(AMFI {f.direct_code})</span>
                      </>
                    )}
                  </span>
                )}
              </div>
              <span className="num text-sm text-loss">
                {formatInr(f.annual_cost)}/yr
              </span>
            </li>
          ))}
        </ul>
      )}

      {data.unpriced.length > 0 && (
        <p className="flex max-w-3xl items-start gap-2 text-sm text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {/* Named rather than averaged: assigning a typical gap would invent
                the very number this is here to measure. */}
            AMFI publishes no direct-plan expense ratio for {data.unpriced.join(', ')},
            so its cost is left unmeasured rather than estimated.
          </span>
        </p>
      )}
    </section>
  )
}
