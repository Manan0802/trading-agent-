import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Check, Sparkles } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr } from '@/lib/format'
import { fetchLevers } from '@/lib/portfolio-api'
import { cn } from '@/lib/utils'

/**
 * The one decision worth money, made unmissable — and the three that are worth
 * nothing, kept but folded away.
 *
 * The old version printed all four at the same size with two paragraphs each:
 * roughly 300 words, three of them saying "this is worth ₹0". Every word was
 * true and nobody read any of it, so the one action that IS worth something sat
 * in the middle of a wall of grey text.
 *
 * The zeros are not deleted. Fund selection scoring nothing is the most useful
 * finding this app has — it is where nearly everyone spends their attention —
 * and hiding it would make the app look like every other one. It is collapsed
 * instead: a row you can open, with the number visible while it is shut.
 */
export function Levers({
  className = '',
  yearsRemaining,
  monthlySip,
}: {
  className?: string
  /** Left undefined outside a goal, so the server uses the stored profile
   *  horizon rather than a number this component invented. */
  yearsRemaining?: number
  monthlySip?: number
} = {}) {
  const { data, isLoading } = useQuery({
    queryKey: ['levers', yearsRemaining, monthlySip],
    queryFn: () =>
      fetchLevers({ years_remaining: yearsRemaining, monthly_sip: monthlySip }),
  })
  const [open, setOpen] = useState<string | null>(null)

  if (isLoading) return <Skeleton className={cn('h-56 w-full rounded-xl', className)} />
  if (!data || data.levers.length === 0) return null

  const worth = data.levers.filter((l) => l.lifetime_value > 0)
  const nothing = data.levers.filter((l) => l.lifetime_value === 0)
  const lead = worth[0]

  return (
    <section className={cn('flex flex-col gap-3', className)}>
      {lead && (
        <article className="lift relative overflow-hidden rounded-2xl border border-v-emerald/25 bg-card p-5 sm:p-7">
          {/* The one card on this page allowed a gradient. It is the only thing
              here that is an instruction rather than a reading. */}
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.13]"
            style={{
              background:
                'linear-gradient(115deg, var(--v-emerald) 0%, var(--v-cyan) 55%, var(--v-violet) 100%)',
            }}
            aria-hidden
          />
          <div className="relative flex flex-col gap-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="flex size-7 items-center justify-center rounded-lg bg-v-emerald/15 text-v-emerald">
                  <Sparkles className="size-4" aria-hidden />
                </span>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-v-emerald-ink">
                  Do this one thing
                </p>
              </div>
              <div className="text-right">
                {/* Per YEAR leads. The lifetime figure is ~37x bigger and reads
                    as money you are losing right now, which it is not. */}
                <p className="num text-3xl font-semibold leading-none text-gain sm:text-4xl">
                  {formatInr(lead.annual_value || lead.lifetime_value)}
                  {lead.annual_value > 0 && (
                    <span className="text-base font-normal text-muted-foreground">/yr</span>
                  )}
                </p>
                {lead.annual_value > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    <span className="num">{formatInr(lead.lifetime_value)}</span> over{' '}
                    <span className="num">{data.years_remaining}</span> years
                  </p>
                )}
              </div>
            </div>

            <h2 className="max-w-2xl text-xl font-semibold leading-snug sm:text-2xl">
              {lead.title}
            </h2>
            {/* The instruction only. The reasoning behind it lives on Why. */}
            <p className="max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
              {lead.action}
            </p>
          </div>
        </article>
      )}

      {worth.length > 1 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {worth.slice(1).map((lever) => (
            <article key={lever.key} className="lift rounded-xl border bg-card p-4">
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="text-sm font-medium">{lever.title}</h3>
                <span className="num shrink-0 font-semibold text-gain">
                  {formatInr(lever.annual_value || lever.lifetime_value)}
                  {lever.annual_value > 0 && (
                    <span className="text-xs font-normal text-muted-foreground">/yr</span>
                  )}
                </span>
              </div>
              <p className="mt-1.5 text-sm leading-snug text-muted-foreground">{lever.action}</p>
            </article>
          ))}
        </div>
      )}

      {nothing.length > 0 && (
        <div className="rounded-xl border bg-card/60">
          <p className="border-b px-4 py-2.5 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">
              {nothing.length} things worth nothing
            </span>{' '}
            &mdash; measured, not skipped. Tap to see why.
          </p>
          <ul>
            {nothing.map((lever) => {
              const isOpen = open === lever.key
              return (
                <li key={lever.key} className="border-b last:border-0">
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : lever.key)}
                    aria-expanded={isOpen}
                    className="flex min-h-11 w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-muted/50"
                  >
                    <Check className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="flex-1 text-sm text-muted-foreground">{lever.title}</span>
                    <span className="num text-sm text-muted-foreground">₹0</span>
                    <ChevronDown
                      aria-hidden
                      className={cn(
                        'size-4 shrink-0 text-muted-foreground transition-transform',
                        isOpen && 'rotate-180',
                      )}
                    />
                  </button>
                  {isOpen && (
                    <div className="flex flex-col gap-2 px-4 pb-4 pl-10">
                      <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                        {lever.detail}
                      </p>
                      <p className="max-w-2xl text-sm leading-relaxed">{lever.action}</p>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </section>
  )
}
