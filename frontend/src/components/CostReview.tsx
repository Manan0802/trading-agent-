import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, CheckCircle2 } from 'lucide-react'
import { Panel } from '@/components/ui/panel'
import { Reveal } from '@/components/ui/reveal'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr, formatPercent } from '@/lib/format'
import { fetchCostReview } from '@/lib/portfolio-api'

/**
 * What the regular-plan funds in this portfolio cost against their direct
 * equivalents. Both plans own the identical portfolio; the difference is a
 * distributor commission taken out of the regular plan's NAV every day, and
 * AMFI publishes both figures, so this is a measured fee rather than an
 * estimate.
 *
 * The answer is a rupee figure per year, and it now leads. The four-sentence
 * paragraph that used to open this panel said the same thing plus the caveat
 * about capital gains — correct, and read by nobody, because it arrived before
 * the number it was qualifying.
 */
export function CostReview({ yearsRemaining = 15 }: { yearsRemaining?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['cost-review', yearsRemaining],
    queryFn: () => fetchCostReview(yearsRemaining),
  })

  if (isLoading) return <Skeleton className="h-32 w-full rounded-xl" />
  if (!data) return null

  const clean = data.flagged.length === 0 && data.unpriced.length === 0
  const annual = data.flagged.reduce((sum, f) => sum + f.annual_cost, 0)

  return (
    <Panel title="What your funds cost" className="h-full">
      {clean ? (
        <div className="flex items-center gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-gain/12 text-gain">
            <CheckCircle2 className="size-5" aria-hidden />
          </span>
          <p className="text-[15px]">
            <span className="font-semibold text-gain">Nothing to fix.</span> Every
            fund here is a direct plan, so none of your return goes to a
            distributor.
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap items-end gap-x-4 gap-y-1">
          <p className="num text-3xl font-semibold leading-none text-loss">
            {formatInr(annual)}
            <span className="text-base font-normal text-muted-foreground">/yr</span>
          </p>
          <p className="text-sm text-muted-foreground">
            going to a distributor for a portfolio you could hold for less
          </p>
        </div>
      )}

      {data.flagged.length > 0 && (
        <ul className="flex flex-col gap-2">
          {data.flagged.map((f) => (
            <li key={f.name} className="rounded-lg border bg-muted/30 p-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-medium leading-snug">{f.name}</span>
                <span className="num shrink-0 text-sm font-semibold text-loss">
                  {formatInr(f.annual_cost)}/yr
                </span>
              </div>
              <p className="tnum mt-0.5 text-xs text-muted-foreground">
                {formatInr(f.value)} held &middot;{' '}
                {formatPercent(f.ter_gap, { signed: false })} a year more than direct
              </p>
              {/* The scheme to actually buy. Without it the advice stops at
                  "switch to the direct plan" and the reader is left guessing in
                  a broker's search box, which is where a plan like this dies. */}
              {f.direct_name && (
                <p className="mt-2 flex items-start gap-1.5 text-xs leading-snug">
                  <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-gain" aria-hidden />
                  <span>
                    <span className="text-muted-foreground">Buy instead: </span>
                    <span className="font-medium">{f.direct_name}</span>
                    {f.direct_code && (
                      <span className="tnum text-muted-foreground"> (AMFI {f.direct_code})</span>
                    )}
                  </span>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {data.unpriced.length > 0 && (
        <p className="flex items-start gap-2 text-xs text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-v-amber" aria-hidden />
          {/* Named rather than averaged: assigning a typical gap would invent
              the very number this panel exists to measure. */}
          <span>
            No direct-plan expense ratio published for {data.unpriced.join(', ')} —
            left unmeasured rather than estimated.
          </span>
        </p>
      )}

      {!clean && (
        <Reveal label="Before you switch">
          <p>{data.summary}</p>
        </Reveal>
      )}
    </Panel>
  )
}
