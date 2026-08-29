import { useState } from 'react'
import { AlreadyOwn } from '@/components/AlreadyOwn'
import { useTrailLeaf } from '@/components/Trail'
import { Link, useParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { BaseRatePanel } from '@/components/BaseRatePanel'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Metric, MetricRow } from '@/components/ui/metric'
import { Notice } from '@/components/ui/notice'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import { ChartLegend } from '@/components/ChartLegend'
import {
  RANGES,
  TOOLTIP_STYLE,
  axisNumber,
  axisTick,
  axisTicks,
  daysBetween,
  longDate,
  mergeSeries,
  niceTicks,
  paddedDomain,
  rangeWords,
  type RangeKey,
} from '@/lib/chart'
import {
  NO_VALUE,
  count,
  formatNav,
  formatPercent,
  formatRatio,
  gainClass,
  score100,
} from '@/lib/format'
import { fetchFundAnalysis, type FundAnalysisData } from '@/lib/screener-api'
import { cn } from '@/lib/utils'

/** "18 days", "11 months", "2.3 years" — the unit a person would have used. */
function spanWords(from: string, to: string): string {
  const days = Math.abs(daysBetween(from, to))
  if (days < 45) return `${days} day${days === 1 ? '' : 's'}`
  const months = Math.round(days / 30.44)
  if (months < 24) return `${months} months`
  return `${(days / 365.25).toFixed(1)} years`
}

/* ------------------------------------------------------------------ panels */

/** Fund against its category, rebased so the two shapes can share one axis. */
function PerformancePanel({
  data,
  range,
  onRange,
  busy,
}: {
  data: FundAnalysisData
  range: RangeKey
  onRange: (next: RangeKey) => void
  busy: boolean
}) {
  const { nav, peer_median: peer } = data

  /**
   * Whether the category line is comparable at all, which it is not always.
   *
   * The median is taken across peers each rebased to its OWN first day inside
   * the window. When most of a category is younger than this fund, the older
   * peers are already at 336 by the time enough of them exist to take a median
   * of, so the line starts at 336 rather than 100 — and `peer_total_return`,
   * which is computed as `last / 100 - 1`, reports +196% for a stretch over
   * which the median peer actually lost 12%. Drawing it would put the category
   * above the fund from the first pixel and read as underperformance.
   *
   * Two separate things have to hold: the line must start at 100, and it must
   * start on the same day the fund's line does. Either one failing is enough to
   * make the comparison meaningless, so both are checked.
   */
  const peerRebased = peer.length >= 2 && Math.abs(peer[0].value - 100) <= 0.5
  const peerAligned =
    peer.length >= 2 && nav.length >= 2 && Math.abs(daysBetween(nav[0].date, peer[0].date)) <= 7
  const showPeer = peerRebased && peerAligned

  const rows = mergeSeries(nav, showPeer ? peer : [])
  const tick = axisTick(data.range)
  const plotted = rows.flatMap((r) => [r.own, r.peer]).filter((v) => v !== null)
  const domain: [number, number] = plotted.length ? paddedDomain(plotted) : [0, 100]

  const fundReturn = data.total_return
  const peerReturn = showPeer ? data.peer_total_return : null
  const gap = fundReturn !== null && peerReturn !== null ? fundReturn - peerReturn : null

  /**
   * `clipped_to_fund_history` alone is not enough to warn on. It is true
   * whenever the first NAV inside the window lands after the window's first
   * day, which includes a window that opened on a Sunday — it fires for a fund
   * with thirteen years of history asked for five. The fund's own first NAV
   * ever is what says whether the record is genuinely short.
   */
  const trulyClipped =
    data.clipped_to_fund_history &&
    !!data.first_nav_date &&
    !!data.start &&
    data.first_nav_date >= data.start

  return (
    <Panel
      title="How it has done"
      aside={
        data.start && data.end ? (
          <span className="tnum">
            {longDate(data.start)} to {longDate(data.end)}
          </span>
        ) : null
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <dl className="flex flex-wrap items-start gap-x-10 gap-y-4">
          <Metric
            label={`This fund, ${rangeWords(data.range)}`}
            value={formatPercent(fundReturn)}
            valueClassName={cn('num-display', gainClass(fundReturn))}
            size="lg"
          />
          {showPeer && (
            <Metric
              label="Its category, same days"
              value={formatPercent(peerReturn)}
              valueClassName={cn('num-display', gainClass(peerReturn))}
              size="lg"
              // `peers_compared` is capped at the 40 peers the API loads, so this
              // says "of its peers" rather than naming a group size it is not.
              hint={`Median across ${count(data.peers_compared)} of its ${
                data.sub_category ?? data.category
              } peers`}
            />
          )}
        </dl>

        <div
          role="group"
          aria-label="Chart range"
          className="flex flex-wrap items-center gap-1"
        >
          {RANGES.map((r) => (
            <Button
              key={r.key}
              type="button"
              size="lg"
              variant={r.key === range ? 'secondary' : 'ghost'}
              aria-pressed={r.key === range}
              onClick={() => onRange(r.key)}
              // Spelled out rather than left to the size variant: "1M" is 22px
              // of text, and every button on this page has to survive a thumb.
              className="min-h-9 min-w-9 px-3"
            >
              {r.label}
            </Button>
          ))}
        </div>
      </div>

      {gap !== null && (
        <p className="max-w-3xl text-sm">
          Over {rangeWords(data.range)} this fund is{' '}
          <span className={cn('tnum font-medium', gainClass(gap))}>
            {Math.abs(gap * 100).toFixed(1)} points {gap >= 0 ? 'ahead of' : 'behind'}
          </span>{' '}
          the median fund in its own category. Both lines start at 100 on{' '}
          <span className="tnum">{longDate(data.start)}</span>, so a line at 150 means
          ₹100 put in that day was worth ₹150.
        </p>
      )}

      <ChartLegend
        series={[
          { label: data.name, color: 'var(--chart-1)' },
          ...(showPeer
            ? [
                {
                  label: `Median ${data.sub_category ?? data.category}`,
                  color: 'var(--muted-foreground)',
                  dashed: true,
                },
              ]
            : []),
        ]}
      />

      {/* min-w-0 and w-full together: a ResponsiveContainer inside a flex or
          grid parent measures its parent's content width, and without these the
          chart sets the page's width instead of reading it. That is a phone
          scrolling sideways. */}
      <div
        aria-hidden
        className={cn(
          'h-72 w-full min-w-0 transition-opacity duration-200 sm:h-96',
          busy && 'opacity-50',
        )}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 4, right: 24, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="2 4" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              ticks={axisTicks(rows, tick)}
              minTickGap={20}
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              tickFormatter={tick}
            />
            <YAxis
              width={48}
              tickLine={false}
              axisLine={false}
              domain={domain}
              ticks={niceTicks(domain[0], domain[1])}
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              tickFormatter={axisNumber}
            />
            <Tooltip
              cursor={{ stroke: 'var(--muted-foreground)', strokeWidth: 1 }}
              contentStyle={TOOLTIP_STYLE}
              labelFormatter={(d) => longDate(String(d))}
              formatter={(v, name) =>
                [Number(v).toFixed(1), String(name)] as [string, string]
              }
            />
            <Line
              type="monotone"
              dataKey="own"
              name={data.name}
              stroke="var(--chart-1)"
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            {showPeer && (
              <Line
                type="monotone"
                dataKey="peer"
                name="Category median"
                stroke="var(--muted-foreground)"
                strokeWidth={1.5}
                strokeDasharray="5 3"
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {trulyClipped && (
        <Notice>
          This fund's first NAV is {longDate(data.first_nav_date)}, so it has not been
          running for {rangeWords(data.range)}. Both lines cover the{' '}
          {data.start && data.end ? spanWords(data.start, data.end) : 'period'} it has
          actually existed, which is a shorter and weaker record than this button asks
          for.
        </Notice>
      )}

      {peer.length === 0 && (
        <Notice>
          Fewer than eight funds in this category have enough history to build a median
          from, so there is no comparison line. The fund's own return is still its own
          return; there is just nothing here to read it against.
        </Notice>
      )}

      {peer.length >= 2 && !showPeer && (
        <Notice>
          The category median could not be put on the same scale as this fund over{' '}
          {rangeWords(data.range)}
          {peerAligned
            ? ''
            : `, because it only reaches back to ${longDate(peer[0].date)} while the fund reaches back to ${longDate(nav[0]?.date)}`}
          . It is left off rather than drawn on a different base, and the category figure
          is withheld with it. A shorter range will compare the two properly.
        </Notice>
      )}
    </Panel>
  )
}

/** How far below its own peak the fund has been, every day of the window. */
function DrawdownPanel({ data }: { data: FundAnalysisData }) {
  const dd = data.drawdown
  const worst = dd.length ? dd.reduce((a, b) => (b.value < a.value ? b : a)) : null
  const latest = dd.length ? dd[dd.length - 1] : null
  // Zero is the top of this axis by definition — the series is a distance below
  // a running peak, so it can never be positive.
  const floor = worst ? worst.value - Math.max(Math.abs(worst.value) * 0.04, 0.2) : -1
  const ddDomain: [number, number] = [floor, 0]

  /**
   * Half a percent below the old peak counts as back to it. Not pedantry: the
   * series is thinned to 240 points, so the one day a fund printed a new high
   * can fall between two samples, and testing for exactly zero would report a
   * recovered fund as still underwater.
   */
  const RECOVERED = -0.5
  const worstIndex = worst ? dd.indexOf(worst) : -1
  const recovered =
    worstIndex >= 0 ? (dd.slice(worstIndex + 1).find((p) => p.value >= RECOVERED) ?? null) : null

  return (
    <Panel title="Falls from its own peak" className="lg:col-span-3">
      {worst && worst.value < -0.05 ? (
        <p className="max-w-3xl text-sm">
          The deepest fall over {rangeWords(data.range)} was{' '}
          <span className={cn('tnum font-medium', 'text-loss')}>
            −{Math.abs(worst.value).toFixed(1)}%
          </span>{' '}
          below its previous high, on <span className="tnum">{longDate(worst.date)}</span>.{' '}
          {recovered
            ? `It was back at that peak by ${longDate(recovered.date)}, ${spanWords(
                worst.date,
                recovered.date,
              )} later.`
            : 'It has not been back to that peak since.'}{' '}
          {latest && latest.value < -0.05
            ? `Today it is ${Math.abs(latest.value).toFixed(1)}% below its high.`
            : 'Today it is at a new high.'}
        </p>
      ) : (
        <p className="max-w-3xl text-sm text-muted-foreground">
          This fund did not spend a day meaningfully below a previous high over{' '}
          {rangeWords(data.range)}, which is normal for a liquid or overnight fund and
          rare for anything else.
        </p>
      )}

      <ChartLegend
        series={[{ label: 'Percent below its running peak', color: 'var(--loss)' }]}
      />

      <div aria-hidden className="h-56 w-full min-w-0 sm:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={dd} margin={{ top: 4, right: 24, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="nx-drawdown-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--loss)" stopOpacity={0.26} />
                <stop offset="100%" stopColor="var(--loss)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="2 4" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              ticks={axisTicks(dd, axisTick(data.range))}
              minTickGap={20}
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              tickFormatter={axisTick(data.range)}
            />
            <YAxis
              width={48}
              tickLine={false}
              axisLine={false}
              domain={ddDomain}
              ticks={niceTicks(ddDomain[0], ddDomain[1])}
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              // Already a percentage. Multiplying by a hundred here is how a
              // 24% fall becomes a 2,430% one.
              tickFormatter={(v: number) => `${axisNumber(v)}%`}
            />
            <Tooltip
              cursor={{ stroke: 'var(--muted-foreground)', strokeWidth: 1 }}
              contentStyle={TOOLTIP_STYLE}
              labelFormatter={(d) => longDate(String(d))}
              formatter={(v) =>
                [`${Number(v).toFixed(1)}%`, 'Below peak'] as [string, string]
              }
            />
            <Area
              type="monotone"
              dataKey="value"
              baseValue={0}
              stroke="var(--loss)"
              strokeWidth={1.5}
              fill="url(#nx-drawdown-fill)"
              dot={false}
              isAnimationActive={false}
            />
            {worst && (
              <ReferenceDot
                x={worst.date}
                y={worst.value}
                r={4}
                fill="var(--loss)"
                stroke="var(--card)"
                strokeWidth={1.5}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  )
}

/** Every entry date, not the one the calendar happens to hand you. */
function RollingPanel({ data }: { data: FundAnalysisData }) {
  const r = data.rolling_1y

  if (!r.windows || r.best === null || r.worst === null || r.median === null) {
    return (
      <Panel title="Holding it for a year" className="lg:col-span-2">
        <p className="max-w-3xl text-sm text-muted-foreground">
          This fund has not existed for a full year yet, so there is no one-year hold to
          measure. Its first NAV is {longDate(data.first_nav_date)}.
        </p>
      </Panel>
    )
  }

  return (
    <Panel
      title="Holding it for a year"
      aside={<span className="tnum">{count(r.windows)} entry dates</span>}
      className="lg:col-span-2"
    >
      <p className="max-w-3xl text-sm">
        Over {count(r.windows)} possible entry dates, a one-year hold returned between{' '}
        <span className={cn('tnum font-medium', gainClass(r.worst))}>
          {formatPercent(r.worst)}
        </span>{' '}
        and{' '}
        <span className={cn('tnum font-medium', gainClass(r.best))}>
          {formatPercent(r.best)}
        </span>
        , median{' '}
        <span className={cn('tnum font-medium', gainClass(r.median))}>
          {formatPercent(r.median)}
        </span>
        .{' '}
        {r.positive_share !== null && (
          <>
            <span className="tnum font-medium">
              {formatPercent(r.positive_share, { signed: false })}
            </span>{' '}
            of them made money.
          </>
        )}{' '}
        A single &ldquo;1-year return&rdquo; is one of those dates&apos; luck; this is all
        of them.
      </p>

      <MetricRow className="sm:grid-cols-2 lg:grid-cols-2">
        <Metric
          label="Worst year"
          value={formatPercent(r.worst)}
          valueClassName={gainClass(r.worst)}
          size="sm"
          hint="The least anyone holding for a year ever got"
        />
        <Metric
          label="Best year"
          value={formatPercent(r.best)}
          valueClassName={gainClass(r.best)}
          size="sm"
          hint="And the most"
        />
        <Metric
          label="Median year"
          value={formatPercent(r.median)}
          valueClassName={gainClass(r.median)}
          size="sm"
          hint="The middle of every entry date"
        />
        <Metric
          label="Made money"
          value={formatPercent(r.positive_share, { signed: false })}
          size="sm"
          hint={`Of ${count(r.windows)} one-year holds`}
        />
      </MetricRow>
    </Panel>
  )
}

/** The pre-written sentences behind the rank, and the silence when there are none. */
function ReasonsPanel({ data }: { data: FundAnalysisData }) {
  const reasons = data.fund.reasons

  return (
    <Panel title="Why this fund is ranked where it is">
      {reasons.length > 0 ? (
        <ul className="grid gap-x-10 gap-y-2 xl:grid-cols-2">
          {reasons.map((reason) => (
            <li key={reason.kind} className="flex gap-2 text-sm">
              <span aria-hidden className="text-muted-foreground">
                &middot;
              </span>
              <span>{reason.text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="max-w-3xl text-sm text-muted-foreground">
          This fund has nothing that stands out against its category. That silence is the
          honest answer for most funds — a line only appears when a fund is genuinely near
          the top of its own group on something.
        </p>
      )}
    </Panel>
  )
}

/** Everything the score was built from, at one density. */
function FiguresPanel({ data }: { data: FundAnalysisData }) {
  const f = data.fund

  return (
    <Panel
      title="Every figure behind the score"
      aside={
        f.rank > 0 ? (
          <span className="tnum">
            #{count(f.category_rank)} among {f.sub_category || f.category} funds
          </span>
        ) : (
          'Too new to rank'
        )
      }
    >
      <MetricRow>
        <Metric label="Score" value={score100(f.fund_score)} size="sm" hint="Out of 100" />
        <Metric label="Grade" value={f.grade ?? NO_VALUE} size="sm" />
        <Metric
          label="Peer median"
          value={score100(f.peer_median)}
          size="sm"
          hint="The middle score of the group below"
        />
        {/* Deliberately not named as the sub-category. The grade and the peer
            median are computed over `(category, sub_category)` for debt and
            commodity and over `(category,)` for everything else, so an equity
            fund's 509 peers are the whole Equity Scheme, not the 41 flexi caps
            its rank is counted among. Stating a group this page cannot derive
            is how the two numbers get read as one. */}
        <Metric
          label="Graded against"
          value={count(f.peer_size)}
          size="sm"
          hint="Funds its grade and peer median are measured over"
        />

        <Metric label="1 month" value={formatPercent(f.returns_1m)} size="sm" />
        <Metric label="3 months" value={formatPercent(f.returns_3m)} size="sm" />
        <Metric label="6 months" value={formatPercent(f.returns_6m)} size="sm" />
        <Metric label="1 year" value={formatPercent(f.returns_1y)} size="sm" />
        <Metric label="3 years" value={formatPercent(f.returns_3y)} size="sm" />

        <Metric label="Rolling 1 month" value={formatPercent(f.rolling_1m)} size="sm" />
        <Metric label="Rolling 3 months" value={formatPercent(f.rolling_3m)} size="sm" />
        <Metric label="Rolling 6 months" value={formatPercent(f.rolling_6m)} size="sm" />
        <Metric label="Rolling 1 year" value={formatPercent(f.rolling_1y)} size="sm" />
        <Metric label="Rolling 3 years" value={formatPercent(f.rolling_3y)} size="sm" />

        <Metric label="Sortino" value={formatRatio(f.sortino)} size="sm" />
        <Metric
          label="Volatility"
          value={formatPercent(f.volatility, { signed: false })}
          size="sm"
        />
        <Metric label="Worst fall" value={formatPercent(f.max_drawdown)} size="sm" />
        <Metric label="Worst 30 days" value={formatPercent(f.worst_30d)} size="sm" />

        <Metric label="Momentum" value={score100(f.momentum_signal)} size="sm" />
        <Metric label="Fall pressure" value={score100(f.drawdown_signal)} size="sm" />
        <Metric
          label="Record"
          value={f.history_years === null ? NO_VALUE : `${f.history_years.toFixed(1)}y`}
          size="sm"
          hint="What the score is measured over"
        />
        <Metric
          label="Published NAVs"
          value={count(f.nav_rows)}
          size="sm"
          hint="Rows the score is built from"
        />
        <Metric
          label="First NAV"
          value={longDate(data.first_nav_date)}
          size="sm"
          hint="The oldest one on file, which the chart can reach and the score does not"
        />
      </MetricRow>
    </Panel>
  )
}

/* -------------------------------------------------------------------- page */

function statusOf(error: unknown): number | null {
  return (error as { response?: { status?: number } } | null)?.response?.status ?? null
}

function detailOf(error: unknown): string | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } } | null)?.response
    ?.data?.detail
  return typeof detail === 'string' ? detail : null
}

/**
 * One fund, on its own page.
 *
 * Everything on it comes from a single request, which matters because the path
 * is on the rate limiter's heavy tier at 20 a minute — six range buttons is six
 * requests, and nothing here prefetches.
 */

/**
 * What this fund actually owns, and the route from a fund to a company.
 *
 * Two things it must not do. It must not render an empty list as "holds
 * nothing": seven AMCs have a verified monthly disclosure, so for most funds the
 * honest answer is "we could not read it", which is a fact about US. And it must
 * not lose where you came from — each company link carries the fund forward, so
 * the trail on the company page names both hops instead of stranding you one
 * browser-back from a fund you have to remember the name of.
 */
function HoldingsPanel({ data }: { data: FundAnalysisData }) {
  const holdings = data.holdings
  const via = { label: data.name, to: `/screener/fund/${data.scheme_code}` }

  return (
    <Panel title="What it owns">
      {!holdings?.covered ? (
        <p className="text-sm text-muted-foreground">
          This fund&rsquo;s AMC does not publish a monthly portfolio we can read,
          so we cannot show what is inside it. That is a gap on our side, not a
          statement about the fund.
        </p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {holdings.total_positions} positions, as disclosed on{' '}
            {holdings.as_of ?? 'an unstated date'}. The largest are below;
            everything else adds up to {holdings.other_weight.toFixed(1)}%.
          </p>
          <ul className="mt-3 divide-y">
            {holdings.top.map((h) => (
              <li key={`${h.isin ?? h.name}`} className="flex items-baseline justify-between gap-3">
                <Link
                  to={`/screener/stock/${encodeURIComponent(h.name)}`}
                  state={{ via }}
                  // 44px of height, because a row of company names is a list of
                  // links and the phone harness measured these at 20px tall.
                  // The padding lives on the link rather than the <li> so the
                  // whole tappable strip is the thing that navigates.
                  className="flex min-h-11 flex-1 items-center truncate py-2 text-sm underline-offset-2 hover:underline"
                >
                  {h.name}
                </Link>
                <span className="num shrink-0 self-center text-sm text-muted-foreground">
                  {h.weight.toFixed(2)}%
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  )
}

export function FundAnalysis() {
  const { schemeCode = '' } = useParams()
  const [range, setRange] = useState<RangeKey>('1y')

  const { data, isPending, isError, error, isFetching } = useQuery({
    queryKey: ['fund-analysis', schemeCode, range],
    queryFn: () => fetchFundAnalysis(schemeCode, range),
    // The range buttons change the query key, and without this the page would
    // empty out and rebuild — including its h1 — on every press. The old chart
    // stays and dims instead.
    placeholderData: keepPreviousData,
    // This path is on the limiter's heavy tier at 20 a minute, and a rate limit
    // is the one failure here that clears itself. Everything else — a 404, a
    // 503 mid-rebuild — is answered the same way on the second try, so retrying
    // it just delays the explanation.
    retry: (attempt, error) => statusOf(error) === 429 && attempt < 2,
    retryDelay: 4000,
  })

  // The trail lives in the layout, but only this page knows that 122639 is
  // "Parag Parikh Flexi Cap Fund". Without this the last crumb is a scheme
  // code — the identifier the app uses internally, and not a thing a person
  // recognises as the fund they just clicked.
  useTrailLeaf(data?.name)

  const status = isError ? statusOf(error) : null

  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/screener"
        className={cn(
          buttonVariants({ variant: 'ghost', size: 'lg' }),
          'w-fit gap-1.5 self-start pl-2 text-muted-foreground hover:text-foreground',
        )}
      >
        <ArrowLeft aria-hidden className="size-4" />
        All funds
      </Link>

      {/* Outside every loading and error branch on purpose. Panel emits an h2,
          so a page whose h1 waits for data starts at h2 while it is fetching,
          and the heading-order check fails on the state nobody screenshots. */}
      <header className="flex flex-col gap-2">
        <h1 className="font-heading text-3xl font-semibold leading-[1.1] tracking-[-0.02em] sm:text-4xl">
          {data?.name ?? `Scheme ${schemeCode}`}
        </h1>
        {data ? (
          <>
            <p className="text-sm text-muted-foreground">
              {data.category}
              {data.sub_category ? ` · ${data.sub_category}` : ''} · {data.fund.fund_house}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-0.5">
              <Badge variant={data.fund.rank > 0 ? 'default' : 'secondary'} className="num">
                {data.fund.rank > 0 ? `#${count(data.fund.rank)} overall` : 'Too new to rank'}
              </Badge>
              {data.fund.grade && <Badge variant="outline">{data.fund.grade}</Badge>}
              {data.fund.risk_tier && (
                <Badge variant="outline">{data.fund.risk_tier} risk</Badge>
              )}
              <span className="text-sm text-muted-foreground">
                NAV{' '}
                <span className="tnum font-medium text-foreground">
                  {formatNav(data.latest_nav)}
                </span>{' '}
                <span className="tnum text-xs">on {longDate(data.latest_nav_date)}</span>
              </span>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            {isError ? 'This fund could not be loaded.' : 'Loading this fund’s record.'}
          </p>
        )}
      </header>

      {isError && !data ? (
        <Panel title="Nothing to show">
          <Notice>
            {status === 404
              ? `Scheme ${schemeCode} is not in the latest ranking. Either the code is wrong, or the fund was dropped when the nightly run last rebuilt the universe.`
              : status === 429
                ? (detailOf(error) ??
                  'Too many requests. This page is limited to twenty loads a minute; wait a moment and reload.')
                : status === 503
                  ? (detailOf(error) ??
                    'The screener is rebuilding its ranking. Nothing is broken; try again in a few minutes.')
                  : 'We could not load this fund. If it keeps failing, the NAV store is probably still rebuilding.'}
          </Notice>
          <div>
            <Link to="/screener" className={buttonVariants({ variant: 'outline', size: 'lg' })}>
              Back to the screener
            </Link>
          </div>
        </Panel>
      ) : isPending || !data ? (
        <>
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-40 w-full" />
        </>
      ) : (
        <>
          {/* Before this fund's own record, not beside it. A base rate shown
              alongside a vivid individual case gets ignored in favour of the
              case (Kahneman & Lovallo 1993); reference-class forecasting, which
              the UK Treasury mandates for infrastructure costing, puts the
              class first and adjusts afterwards. Sequence, not just presence. */}
          <BaseRatePanel rate={data.base_rate} />
          <PerformancePanel
            data={data}
            range={range}
            onRange={setRange}
            busy={isFetching}
          />
          <div className="grid gap-6 lg:grid-cols-5">
            <DrawdownPanel data={data} />
            <RollingPanel data={data} />
          </div>
          <ReasonsPanel data={data} />
          {/* Before the holdings list, not after: the question "does this add
              anything" comes before "what is in it". */}
          <AlreadyOwn schemeCode={data.scheme_code} />
          <HoldingsPanel data={data} />
          <FiguresPanel data={data} />
        </>
      )}
    </div>
  )
}
