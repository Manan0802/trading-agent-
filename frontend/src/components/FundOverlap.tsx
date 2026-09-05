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
 * What a correlation is, in words, plus the bar colour that goes with it.
 *
 * Every bar used to be violet unless it crossed 0.90, which meant 0.77 and 0.17
 * were drawn identically -- on a panel whose entire argument is comparative.
 * The band is a MAGNITUDE, not a verdict: two equity funds at 0.85 is what
 * equity does, so the words say "move together" rather than "too similar", and
 * no band is red until a pair is genuinely one position bought twice.
 */
function band(correlation: number): { label: string; bar: string; ink: string } {
  if (correlation >= DUPLICATE_ABOVE)
    return { label: 'the same position twice', bar: 'bg-v-rose', ink: 'text-v-rose' }
  if (correlation >= 0.7)
    return { label: 'move closely together', bar: 'bg-v-amber', ink: 'text-v-amber-ink' }
  if (correlation >= 0.4)
    return { label: 'partly related', bar: 'bg-v-violet', ink: 'text-v-violet-ink' }
  return { label: 'doing separate work', bar: 'bg-v-cyan', ink: 'text-v-cyan-ink' }
}

/**
 * "SBI Small Cap" out of "SBI Small Cap Fund - Regular Plan - Growth".
 *
 * A pair row prints two of these side by side. At full length they wrapped to
 * three lines and the number they belong to ended up on a different line from
 * the names, which is the one thing a comparison row cannot afford.
 */
function shortFund(name: string): string {
  return name
    .split(/ - |\s+Fund\b/)[0]
    .replace(/\s+(Direct|Regular)\s+Plan.*$/i, '')
    .trim()
}

/** "154mo" is a unit nobody speaks. */
function historySpan(months: number): string {
  if (months < 24) return `${months} months of history`
  return `${Math.floor(months / 12)} years of history`
}

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

  // The server returns pairs heaviest-correlation first, but reading the
  // maximum is one line and does not depend on that staying true.
  const closest = data?.pairs.reduce<(typeof data.pairs)[number] | null>(
    (best, p) => (best === null || p.correlation > best.correlation ? p : best),
    null,
  )

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
            <span className="num text-foreground">{data.counted}</span>{' '}
            {data.counted === 1 ? 'fund' : 'funds'}
          </span>
        </div>
      )}

      {/* The closest pair, named, with the same words its bar uses.
          This used to print the server's first sentence, which is written
          against the 0.90 duplicate threshold -- so a portfolio whose tightest
          pair sat at 0.77 read "Nothing here is a duplicate of anything else"
          directly above a bar labelled "move closely together". Both were
          correct and together they were nonsense. The full summary is still one
          line down, where a sentence about a threshold belongs. */}
      {closest ? (
        <p className="text-sm leading-relaxed">
          Closest pair: <span className="font-medium">{shortFund(closest.a_name)}</span>{' '}
          and <span className="font-medium">{shortFund(closest.b_name)}</span> &mdash;
          they {band(closest.correlation).label}.
        </p>
      ) : (
        <p className="text-sm leading-relaxed">{firstLine(data.summary)}</p>
      )}

      {data.pairs.length > 0 && (
        <ul className="flex flex-col gap-3">
          {data.pairs.map((p) => {
            const b = band(p.correlation)
            return (
              <li key={`${p.a}-${p.b}`} className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-sm font-medium">
                    {shortFund(p.a_name)}{' '}
                    <span className="font-normal text-muted-foreground">and</span>{' '}
                    {shortFund(p.b_name)}
                  </span>
                  <span className="flex shrink-0 items-baseline gap-2">
                    <span className={cn('text-xs', b.ink)}>{b.label}</span>
                    <span className={cn('num text-sm font-semibold', b.ink)}>
                      {p.correlation.toFixed(2)}
                    </span>
                  </span>
                </div>
                {/* The bar is the number's shape. A column of "0.93 / 0.84 /
                    0.80" makes a reader do the comparing; a row of bars has
                    already done it. */}
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn('h-full rounded-full transition-[width] duration-700', b.bar)}
                    style={{ width: `${Math.max(0, Math.min(1, p.correlation)) * 100}%` }}
                  />
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {/* Unmeasured says so in words. A dash rendered as 0% would
                      claim these funds share nothing, which we do not know. */}
                  {p.common_weight === null ? (
                    <span>same shares not published</span>
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
                  <span>{historySpan(p.months)}</span>
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
          holding the same shares twice. <em>Same shares not published</em> means that
          AMC publishes no file we can read: unknown, not zero.
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
