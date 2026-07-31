import { useQuery } from '@tanstack/react-query'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchOverlap } from '@/lib/portfolio-api'

/**
 * Whether the funds someone holds are actually different from each other.
 *
 * Two numbers per pair, and they answer different questions. Correlation says
 * whether two funds are one position — NAV history says that directly, for every
 * fund. Shared holdings say why: a correlated pair sharing 3% of its assets is
 * the same market bought two ways, while one sharing 45% is the same shares
 * twice. Only the second is worth acting on beyond consolidating paperwork.
 *
 * Holdings coverage is partial, because it comes from parsing each AMC's own
 * monthly disclosure. A pair with no figure is shown as unmeasured, never as
 * zero — zero would read as "perfectly diversified", the opposite of unknown.
 *
 * The framing matters. Two equity funds correlating 0.95 is not a fault, it is
 * what equity does — so nothing here is coloured as a warning. The useful
 * reading is comparative, and the action is to hold fewer funds rather than
 * different ones.
 */

/** Below this a pair is doing genuinely separate work. */
const DUPLICATE_ABOVE = 0.9

/**
 * Share of assets in the same securities that makes a pair the same shares
 * rather than merely the same exposure. Two diversified Indian equity funds
 * routinely share 15–30% just by both owning the index leaders.
 */
const SAME_STOCKS_ABOVE = 40

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
    <Panel>
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
                {p.a_name} <span className="text-muted-foreground">and</span>{' '}
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
                {/* Unmeasured says so in words. Rendering a dash as 0% would
                    claim these funds share nothing, which we do not know. */}
                {p.common_weight === null ? (
                  <span className="text-xs text-muted-foreground">
                    holdings n/a
                  </span>
                ) : (
                  <span
                    className={`num text-xs ${
                      p.common_weight >= SAME_STOCKS_ABOVE
                        ? 'font-medium'
                        : 'text-muted-foreground'
                    }`}
                    title={`${p.shared_securities} securities in common`}
                  >
                    {p.common_weight.toFixed(0)}% same
                  </span>
                )}
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
        The second figure is the share of assets both funds hold in the{' '}
        <em>same</em> securities, read from each AMC&rsquo;s own monthly
        portfolio disclosure and matched on ISIN. Two diversified equity funds
        sharing <span className="tnum">15&ndash;30%</span> is ordinary; both own
        the index leaders. Above <span className="tnum">40%</span> you are
        holding the same shares twice. Where it says{' '}
        <em>holdings n/a</em>, that AMC does not publish a file we can read yet
        &mdash; unknown, not zero.
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
    </Panel>
  )
}
