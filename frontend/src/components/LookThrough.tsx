import { useQuery } from '@tanstack/react-query'
import { Layers2 } from 'lucide-react'
import { Panel } from '@/components/ui/panel'
import { Reveal } from '@/components/ui/reveal'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr } from '@/lib/format'
import { fetchLookThrough } from '@/lib/portfolio-api'

/**
 * The companies behind the funds — what this portfolio actually owns.
 *
 * Three equity funds are not three things. They are a few hundred companies,
 * and several of those are held through more than one fund at once: HDFC Bank
 * at 7% of one, 9% of another and 6% of a third is ONE bet, and it is invisible
 * on every other screen in this app. The `/look-through` endpoint has computed
 * this since it was written and nothing rendered it.
 *
 * Coverage leads the caveat, not the panel. Holdings come from each AMC's
 * monthly disclosure and only some AMCs publish a file we can read, so a real
 * portfolio routinely contains funds this cannot open. Reporting only the
 * readable part produces a number that looks exactly like a complete answer —
 * so the share is stated on the face of the panel, and which funds are missing
 * is one line away.
 *
 * No advice here. Concentration is a fact about a portfolio, not a fault: an
 * index fund is concentrated in exactly the way the index is. The panel shows
 * the shape and leaves the judgement.
 */

/** Enough of the portfolio in one company to be worth seeing as one line. */
const TOP_N = 6

export function LookThrough() {
  const { data, isLoading } = useQuery({
    queryKey: ['look-through'],
    queryFn: fetchLookThrough,
  })

  if (isLoading) return <Skeleton className="h-40 w-full rounded-xl" />
  if (!data || data.companies.length === 0) return null

  const top = data.companies.slice(0, TOP_N)
  // The widest bar sets the scale. Against 100% every bar is a sliver, because
  // no single company is ever a large share of a diversified portfolio — and a
  // row of slivers says nothing about which is bigger.
  const widest = top[0]?.share_pct || 1
  // The reason this panel exists: one company reached through several funds.
  const doubled = data.companies.filter((c) => c.via.length > 1)

  return (
    <Panel
      title="What you actually own"
      aside={
        <span className="tnum">
          read from {data.covered_share.toFixed(0)}% of your money
        </span>
      }
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="num text-3xl font-semibold text-v-indigo">
          {data.companies.length}
        </span>
        <span className="text-sm text-muted-foreground">
          companies, behind the funds you hold
        </span>
      </div>

      {/* The finding, when there is one. Two funds holding the same company is
          the single thing on this panel somebody could not have guessed. */}
      {doubled.length > 0 && (
        <p className="flex items-start gap-2 rounded-lg border border-v-violet/25 bg-v-violet-soft/60 p-3 text-sm">
          <Layers2 className="mt-0.5 size-4 shrink-0 text-v-violet" aria-hidden />
          <span>
            <span className="num font-semibold">{doubled.length}</span>{' '}
            {doubled.length === 1 ? 'company reaches you' : 'companies reach you'}{' '}
            through more than one fund &mdash; one bet each, not two.
          </span>
        </p>
      )}

      <ul className="flex flex-col gap-2.5">
        {top.map((c) => (
          <li key={c.isin} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between gap-3">
              {/* Industry sits next to the name it describes. Right-aligned
                  under the bar it read as a stray word with no owner. */}
              <span className="min-w-0 truncate text-sm">
                <span className="font-medium">{c.name}</span>
                {c.industry && (
                  <span className="text-muted-foreground"> &middot; {c.industry}</span>
                )}
                {c.via.length > 1 && (
                  <span className="font-medium text-v-violet-ink">
                    {' '}
                    &middot; via {c.via.length} funds
                  </span>
                )}
              </span>
              <span className="num shrink-0 text-sm font-semibold tabular-nums">
                {c.share_pct.toFixed(1)}%
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-v-indigo transition-[width] duration-700"
                style={{ width: `${Math.min(100, (c.share_pct / widest) * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>

      <Reveal
        label={
          data.unopened.length > 0
            ? `${data.unopened.length} ${data.unopened.length === 1 ? 'fund is' : 'funds are'} not in this picture, worth ${formatInr(data.unopened_value)}`
            : 'Where this comes from'
        }
      >
        <p>{data.summary}</p>
        {data.unopened.length > 0 && (
          <div>
            <p className="mb-1 font-medium text-foreground">Could not be opened</p>
            <ul className="flex flex-col gap-1">
              {data.unopened.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          </div>
        )}
        <p>
          Every share is against your <em>whole</em> portfolio, including the funds
          above &mdash; not against the part that could be read. The other
          denominator would make each company look bigger than it is, which is the
          one direction a concentration figure must never be wrong in.
        </p>
      </Reveal>
    </Panel>
  )
}
