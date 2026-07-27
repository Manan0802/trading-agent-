import { useQuery } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchOverlap } from '@/lib/portfolio-api'

/**
 * Whether the funds someone holds are actually different from each other.
 *
 * Not a holdings-overlap calculator, because no holdings feed exists for Indian
 * funds. This measures the thing holdings overlap is a proxy for: two funds are
 * one position when they move together, and NAV history says so directly.
 *
 * The framing matters. Two equity funds correlating 0.95 is not a fault, it is
 * what equity does — so nothing here is coloured as a warning. The useful
 * reading is comparative, and the action is to hold fewer funds rather than
 * different ones.
 */

/** Below this a pair is doing genuinely separate work. */
const DUPLICATE_ABOVE = 0.9

export function FundOverlap() {
  const { data, isLoading } = useQuery({
    queryKey: ['overlap'],
    queryFn: fetchOverlap,
  })

  if (isLoading) return <Skeleton className="h-32 w-full" />
  if (!data || (data.pairs.length === 0 && Object.keys(data.excluded).length === 0)) {
    return null
  }

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="text-sm font-medium">Are these funds actually different?</h2>
        {data.effective_positions !== null && (
          <p className="text-xs text-muted-foreground">
            About <span className="tnum">{data.effective_positions.toFixed(1)}</span>{' '}
            separate bets across <span className="tnum">{data.counted}</span> funds
          </p>
        )}
      </div>

      <p className="max-w-3xl text-sm">{data.summary}</p>

      {data.pairs.length > 0 && (
        <ul className="flex flex-col divide-y border-y">
          {data.pairs.map((p) => (
            <li
              key={`${p.a}-${p.b}`}
              className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-2.5"
            >
              <span className="text-sm text-muted-foreground">
                {p.a_name} <span className="text-muted-foreground/50">and</span>{' '}
                {p.b_name}
              </span>
              <span className="flex items-baseline gap-3">
                <span
                  className={`num text-sm ${
                    p.correlation >= DUPLICATE_ABOVE ? 'font-medium' : ''
                  }`}
                >
                  {p.correlation.toFixed(2)}
                </span>
                <span className="num text-xs text-muted-foreground">
                  {p.months}mo
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}

      <p className="max-w-3xl text-sm text-muted-foreground">
        {/* Says what the number is, so it can be argued with. */}
        Each figure is how closely two funds&rsquo; monthly returns moved together
        over the months they both cover. <span className="tnum">1.00</span> means
        the same position twice; <span className="tnum">0.00</span> means they are
        unrelated. Two equity funds sitting near{' '}
        <span className="tnum">0.85</span> is normal and not a fault — the useful
        comparison is against whatever else you hold.
      </p>
      <p className="max-w-3xl text-sm text-muted-foreground">
        There is no holdings feed for Indian mutual funds, so this is not a
        share-of-portfolio overlap. It measures what that number is a proxy for,
        and does it better: two funds can hold different companies and still be
        one bet.
      </p>

      {Object.entries(data.excluded).length > 0 && (
        <p className="max-w-3xl text-sm text-muted-foreground">
          Left out:{' '}
          {Object.entries(data.excluded)
            .map(([name, reason]) => `${name} — ${reason}`)
            .join('; ')}
          .
        </p>
      )}
    </section>
  )
}
