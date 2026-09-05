import { useQuery } from '@tanstack/react-query'
import { Panel } from '@/components/ui/panel'
import { Reveal } from '@/components/ui/reveal'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchOverlap } from '@/lib/portfolio-api'
import { cn } from '@/lib/utils'

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
 *
 * The four paragraphs that used to define both numbers are now behind one
 * toggle. They were correct and nobody read them: on a three-fund portfolio the
 * definitions ran four times longer than the figures they defined, and the panel
 * read as an essay with a table stuck in the middle. Each pair now draws its
 * correlation as a bar, which is the shape of the number, and the prose is
 * there for whoever wants to argue with it.
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

  // The oldest month across the pairs: the set is only as current as its
  // stalest side.
  const asOf =
    data?.pairs
      .map((p) => p.holdings_as_of)
      .filter((d): d is string => d !== null)
      .sort()[0] ?? null

  if (isLoading) return <Skeleton className="h-32 w-full rounded-xl" />
  if (!data || (data.pairs.length === 0 && Object.keys(data.excluded).length === 0)) {
    return null
  }

  return (
    <Panel title="Are these funds actually different?">
      {data.effective_positions !== null && (
        <div className="flex items-baseline gap-2">
          <span className="num text-3xl font-semibold text-v-violet">
            {data.effective_positions.toFixed(1)}
          </span>
          <span className="text-sm text-muted-foreground">
            separate bets across{' '}
            <span className="num text-foreground">{data.counted}</span> funds
          </span>
        </div>
      )}

      {/* The verdict, not the working. The server's summary names both funds
          in the closest pair and repeats the effective-bets figure printed
          directly above it — three lines to say what the number already said. */}
      <p className="text-sm leading-relaxed">{firstLine(data.summary)}</p>

      {data.pairs.length > 0 && (
        <ul className="flex flex-col gap-3">
          {data.pairs.map((p) => {
            const duplicate = p.correlation >= DUPLICATE_ABOVE
            return (
              <li key={`${p.a}-${p.b}`} className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-sm text-muted-foreground">
                    {p.a_name} <span className="opacity-60">and</span> {p.b_name}
                  </span>
                  <span
                    className={cn(
                      'num shrink-0 text-sm font-semibold',
                      duplicate ? 'text-v-rose' : 'text-v-violet',
                    )}
                  >
                    {p.correlation.toFixed(2)}
                  </span>
                </div>
                {/* The bar is the number's shape. A column of "0.93 / 0.84 /
                    0.80" makes a reader do the comparing; a row of bars has
                    already done it. */}
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      'h-full rounded-full transition-[width] duration-700',
                      duplicate ? 'bg-v-rose' : 'bg-v-violet',
                    )}
                    style={{ width: `${Math.max(0, Math.min(1, p.correlation)) * 100}%` }}
                  />
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {/* Unmeasured says so in words. A dash rendered as 0% would
                      claim these funds share nothing, which we do not know. */}
                  {p.common_weight === null ? (
                    <span>holdings n/a</span>
                  ) : (
                    <span
                      className={cn(
                        'num',
                        p.common_weight >= SAME_STOCKS_ABOVE && 'font-semibold text-v-rose',
                      )}
                      title={`${p.shared_securities} securities in common`}
                    >
                      {p.common_weight.toFixed(0)}% same shares
                    </span>
                  )}
                  <span className="num">{p.months}mo of history</span>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {Object.entries(data.excluded).length > 0 && (
        <p className="text-xs text-muted-foreground">
          Left out:{' '}
          {Object.entries(data.excluded)
            .map(([name, reason]) => `${name} — ${reason}`)
            .join('; ')}
          .
        </p>
      )}

      <Reveal label="What these two numbers mean">
        <p>{data.summary}</p>
        <p>
          The first figure is how closely two funds&rsquo; monthly returns moved
          together over the months they both cover.{' '}
          <span className="tnum">1.00</span> means the same position twice;{' '}
          <span className="tnum">0.00</span> means unrelated. Two equity funds near{' '}
          <span className="tnum">0.85</span> is normal, not a fault &mdash; the useful
          comparison is against whatever else you hold.
        </p>
        <p>
          The second is the share of assets both funds hold in the <em>same</em>{' '}
          securities, read from each AMC&rsquo;s monthly disclosure and matched on
          ISIN. Sharing <span className="tnum">15&ndash;30%</span> is ordinary &mdash;
          both own the index leaders. Above <span className="tnum">40%</span> you are
          holding the same shares twice. <em>holdings n/a</em> means that AMC
          publishes no file we can read: unknown, not zero.
        </p>
        {/* AMCs file within ten days of month end, so in the first week of a
            month this reads the month before last. Without the date the number
            simply changes and nothing explains why. */}
        {asOf && (
          <p className="text-xs">
            Holdings are from each AMC&rsquo;s <span className="tnum">{asOf}</span>{' '}
            disclosure, the latest published. They file within ten days of month end,
            so this moves when the next one lands.
          </p>
        )}
      </Reveal>
    </Panel>
  )
}

/** The first sentence. The rest restates the figure printed above it. */
function firstLine(text: string): string {
  const match = text.match(/^.*?[.!?](?=\s|$)/)
  return match ? match[0] : text
}
