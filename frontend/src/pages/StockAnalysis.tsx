import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChartLegend } from '@/components/ChartLegend'
import { StockScoreBreakdown } from '@/components/StockScoreBreakdown'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Metric, MetricRow } from '@/components/ui/metric'
import { Notice } from '@/components/ui/notice'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  NO_VALUE,
  count,
  formatInr,
  formatRatio,
  gainClass,
} from '@/lib/format'
import {
  RANGES,
  type RangeKey,
  TOOLTIP_STYLE,
  axisNumber,
  axisTick,
  axisTicks,
  longDate,
  mergeSeries,
  niceTicks,
  paddedDomain,
  rangeWords,
} from '@/lib/chart'
import {
  fetchStockAnalysis,
  type RatioVsSector,
  type StockAnalysisData,
} from '@/lib/screener-api'
import { cn } from '@/lib/utils'

/* ----------------------------------------------------------------- numbers */

/** Already a percent on the wire, so formatPercent would multiply it again. */
function pct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return NO_VALUE
  return `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(digits)}%`
}

/** A bare percent, for a figure that is a level rather than a change. */
function level(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return NO_VALUE
  return `${value.toFixed(digits)}%`
}

const IN_NUMBER = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

/**
 * Rupees in crores, the unit every Indian reader holds market cap in.
 *
 * `formatInrCompact` speaks in K/M/B, which is the wrong ladder here: a reader
 * comparing two Indian companies wants ₹11,26,467 Cr against ₹1,04,133 Cr, not
 * ₹11.3T against ₹104B.
 */
function crores(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  return `₹${IN_NUMBER.format(value / 1e7)} Cr`
}

/**
 * A count of shares, on the lakh/crore ladder rather than the rupee one.
 *
 * Not `formatInrCompact`: that returns "₹19.1M", and a volume is neither
 * rupees nor a figure an Indian reader groups in millions.
 */
function shares(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  if (value >= 1e7) return `${(value / 1e7).toFixed(2)} Cr`
  if (value >= 1e5) return `${(value / 1e5).toFixed(2)} L`
  return IN_NUMBER.format(value)
}

/** How the ratio units differ, in one place rather than at four call sites. */
function ratioValue(r: RatioVsSector, which: 'value' | 'sector_median'): string {
  const v = r[which]
  if (v === null) return NO_VALUE
  return r.key === 'roe' || r.key === 'div_yield' ? level(v) : formatRatio(v)
}

/* ------------------------------------------------------------------ panels */

/** The company against its sector's median company, both rebased to 100. */
function PricePanel({
  data,
  range,
  onRange,
  busy,
}: {
  data: StockAnalysisData
  range: RangeKey
  onRange: (next: RangeKey) => void
  busy: boolean
}) {
  const own = data.price_series
  const peer = data.sector_series

  /**
   * The sector line is only drawn when it starts where the company's does.
   *
   * The median is taken across peers each rebased to its own first day inside
   * the window. If the two lines begin on different days, or the median begins
   * anywhere but 100, the chart shows a gap that is an artefact of when the
   * peers listed rather than of how either performed.
   */
  const showPeer =
    peer.length >= 2 &&
    own.length >= 2 &&
    Math.abs(peer[0].value - 100) <= 0.5 &&
    peer[0].date === own[0].date

  const rows = mergeSeries(own, showPeer ? peer : [])
  const tick = axisTick(data.range)
  const plotted = rows.flatMap((r) => [r.own, r.peer]).filter((v): v is number => v !== null)
  const domain: [number, number] = plotted.length ? paddedDomain(plotted) : [0, 100]

  // Both series are index points from 100, so the return over the window is
  // the last point minus 100 — no second request, and no chance of the
  // headline figure disagreeing with the line drawn beside it.
  const ownReturn = own.length ? own[own.length - 1].value - 100 : null
  const peerReturn = showPeer ? peer[peer.length - 1].value - 100 : null
  const gap = ownReturn !== null && peerReturn !== null ? ownReturn - peerReturn : null

  return (
    <Panel
      title="How the price has moved"
      aside={
        own.length ? (
          <span className="tnum">
            {longDate(own[0].date)} — {longDate(own[own.length - 1].date)}
          </span>
        ) : undefined
      }
     
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          {RANGES.map((r) => (
            <Button
              key={r.key}
              size="lg"
              variant={r.key === range ? 'default' : 'outline'}
              aria-pressed={r.key === range}
              onClick={() => onRange(r.key)}
            >
              {r.label}
            </Button>
          ))}
        </div>

        <MetricRow>
          <Metric
            label={`Over ${rangeWords(data.range)}`}
            value={pct(ownReturn, 1)}
            valueClassName={gainClass(ownReturn)}
            size="lg"
          />
          {showPeer && (
            <Metric
              label="The median company in its sector"
              value={pct(peerReturn, 1)}
              valueClassName={gainClass(peerReturn)}
              size="lg"
            />
          )}
          {gap !== null && (
            <Metric
              label="Difference"
              value={pct(gap, 1)}
              valueClassName={gainClass(gap)}
              size="lg"
              hint={`Against ${count(data.peers_compared)} priced peers`}
            />
          )}
        </MetricRow>

        <ChartLegend
          series={[
            { label: data.name, color: 'var(--chart-1)' },
            ...(showPeer
              ? [
                  {
                    label: `Median company in ${data.sector ?? 'its sector'}`,
                    color: 'var(--muted-foreground)',
                    dashed: true,
                  },
                ]
              : []),
          ]}
        />

        {/* min-w-0 and w-full together: a ResponsiveContainer inside a flex or
            grid parent measures its parent's content width, and without these
            the chart sets the page's width instead of reading it. That is a
            phone scrolling sideways. */}
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
                formatter={(v, name) => [Number(v).toFixed(1), String(name)] as [string, string]}
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
                  name="Sector median"
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

        <p className="max-w-3xl text-sm text-muted-foreground">
          Both lines start at 100 on the same day, so what you are comparing is
          the shape, not the price. {data.name} at{' '}
          <span className="tnum">{own.length ? own[own.length - 1].value.toFixed(1) : NO_VALUE}</span>{' '}
          means ₹100 put in on the first day would be worth that today.
        </p>

        {!showPeer && (
          <Notice>
            {peer.length < 2
              ? `Too few companies in ${data.sector ?? 'this sector'} could be priced over ${rangeWords(data.range)} to take a median, so there is no sector line to compare against.`
              : `The sector line is left off this range: it does not start on the same day this company's does, so the two shapes are not comparable and drawing them together would invent a gap.`}
          </Notice>
        )}
      </div>
    </Panel>
  )
}

/** Where today's price sits inside the year, drawn and then said. */
function TodayPanel({ data }: { data: StockAnalysisData }) {
  const at = data.position_in_52w

  return (
    <Panel title="Where the price sits today">
      <div className="flex flex-col gap-5">
        {at !== null && data.week52_low !== null && data.week52_high !== null && (
          <div className="flex flex-col gap-2">
            {/* aria-hidden: the two ends and the position are all written out
                below, so the bar is the thing you notice and the figures are
                the thing you can read. */}
            <div aria-hidden className="flex flex-col gap-1.5">
              <div className="relative h-1.5 w-full rounded-full bg-secondary">
                <div
                  className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card bg-primary"
                  style={{ left: `${Math.min(100, Math.max(0, at * 100))}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span className="tnum">{formatInr(data.week52_low)}</span>
                <span className="tnum">{formatInr(data.week52_high)}</span>
              </div>
            </div>
          </div>
        )}

        {data.plain.position && <p className="max-w-3xl text-sm">{data.plain.position}</p>}

        <MetricRow>
          <Metric
            label="Today"
            value={formatInr(data.price)}
            size="sm"
            hint={
              data.day_low !== null && data.day_high !== null
                ? `Ranged ${formatInr(data.day_low)} to ${formatInr(data.day_high)}`
                : undefined
            }
          />
          <Metric
            label="Change on the day"
            value={pct(data.day_change_pct)}
            valueClassName={gainClass(data.day_change_pct)}
            size="sm"
            hint={`Closed at ${formatInr(data.previous_close)} before`}
          />
          <Metric
            label="Shares traded today"
            value={shares(data.volume)}
            size="sm"
            hint="How much of it changed hands"
          />
          <Metric
            label="What the whole company is worth"
            value={crores(data.market_cap)}
            size="sm"
            hint="Every share at today's price"
          />
        </MetricRow>
      </div>
    </Panel>
  )
}

/**
 * The four ratios, each beside its sector's median.
 *
 * A P/B of 7.6 is expensive for a bank and ordinary for a software company. A
 * bare number cannot say which, which is why no figure on this panel appears
 * without the median it is being judged against.
 */
function RatiosPanel({ data }: { data: StockAnalysisData }) {
  const shown = data.ratios.filter((r) => r.value !== null || r.key === 'div_yield')

  return (
    <Panel
      title="What it costs, against its sector"
      aside={<span className="tnum">{count(data.benchmark_constituents)} companies</span>}
     
    >
      <div className="flex flex-col gap-5">
        <div className="-mx-4 overflow-x-auto sm:mx-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Measure</TableHead>
                <TableHead scope="col" className="text-right">
                  {data.symbol}
                </TableHead>
                <TableHead scope="col" className="text-right">
                  Middle company in {data.benchmark_sector}
                </TableHead>
                <TableHead scope="col">Which way that cuts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((r) => (
                <TableRow key={r.key}>
                  <TableCell>{r.label}</TableCell>
                  <TableCell className="num text-right">{ratioValue(r, 'value')}</TableCell>
                  <TableCell className="num text-right text-muted-foreground">
                    {ratioValue(r, 'sector_median')}
                  </TableCell>
                  <TableCell className="whitespace-normal">
                    {r.verdict ? (
                      <Badge variant="outline">{r.verdict}</Badge>
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        {r.value === null ? 'Not reported' : 'No sector median to compare with'}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <ul className="flex max-w-3xl flex-col gap-2 text-sm">
          {['valuation', 'quality', 'dividend'].map(
            (k) => data.plain[k] && <li key={k}>{data.plain[k]}</li>,
          )}
        </ul>

        <p className="max-w-3xl text-sm text-muted-foreground">
          The middle company is a true median across the{' '}
          <span className="tnum">{count(data.benchmark_constituents)}</span> companies this app
          tracks in {data.benchmark_sector} — not the index figure brokers print, which is
          weighted by size and so mostly describes its two largest members.
        </p>
      </div>
    </Panel>
  )
}

/** Six companies in the same industry, biggest first. */
function SimilarPanel({ data }: { data: StockAnalysisData }) {
  if (data.similar.length === 0) return null

  return (
    <Panel
      title="Companies like this one"
      aside={data.similar_group ?? undefined}
     
    >
      <div className="flex flex-col gap-4">
        <div className="-mx-4 overflow-x-auto sm:mx-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Company</TableHead>
                <TableHead scope="col" className="text-right">
                  Price
                </TableHead>
                <TableHead scope="col" className="text-right">
                  Price to earnings
                </TableHead>
                <TableHead scope="col" className="text-right">
                  Worth
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.similar.map((s) => (
                <TableRow key={s.ticker}>
                  <TableCell className="whitespace-normal">
                    <Link
                      to={`/screener/stock/${encodeURIComponent(s.ticker)}`}
                      className="flex min-h-8 w-fit items-center underline-offset-4 hover:underline"
                    >
                      {s.name}
                    </Link>
                  </TableCell>
                  <TableCell className="num text-right">{formatInr(s.price)}</TableCell>
                  <TableCell className="num text-right">{formatRatio(s.pe)}</TableCell>
                  <TableCell className="num text-right">{crores(s.market_cap)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <p className="max-w-3xl text-sm text-muted-foreground">
          The largest companies in {data.similar_group ?? 'the same group'}, ranked by index
          membership. That grouping is broader than {data.symbol}&rsquo;s own line of business
          {data.industry ? ` (${data.industry})` : ''} — and being alike in business is not being
          alike in prospects. A place to start comparing, not a shortlist.
        </p>
      </div>
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
 * One company, on its own page.
 *
 * Everything comes from a single request. The path is on the rate limiter's
 * heavy tier at 20 a minute, and six range buttons is six requests — so
 * nothing here prefetches, polls, or fetches per row.
 */
export function StockAnalysis() {
  const { ticker = '' } = useParams()
  const [range, setRange] = useState<RangeKey>('1y')

  const { data, isPending, isError, error, isFetching } = useQuery({
    queryKey: ['stock-analysis', ticker, range],
    queryFn: () => fetchStockAnalysis(ticker, range),
    // Without this the page empties and rebuilds — including its h1 — on every
    // range press. The old chart stays and dims instead.
    placeholderData: keepPreviousData,
    retry: false,
  })

  const status = isError ? statusOf(error) : null

  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/screener?tab=stocks"
        className={cn(
          buttonVariants({ variant: 'ghost', size: 'lg' }),
          'w-fit gap-1.5 self-start pl-2 text-muted-foreground hover:text-foreground',
        )}
      >
        <ArrowLeft aria-hidden className="size-4" />
        All stocks
      </Link>

      {/* Outside every loading and error branch on purpose. Panel emits an h2,
          so a page whose h1 waits for data starts at h2 while it is fetching,
          and the heading-order check fails on the state nobody screenshots. */}
      <header className="flex flex-col gap-2">
        <h1 className="font-heading text-3xl font-semibold leading-[1.1] tracking-[-0.02em] sm:text-4xl">
          {data?.name ?? ticker.replace('.NS', '')}
        </h1>
        {data ? (
          <>
            <p className="text-sm text-muted-foreground">
              {data.symbol}
              {data.sector ? ` · ${data.sector}` : ''}
              {data.industry ? ` · ${data.industry}` : ''}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-0.5">
              <span className="num-display text-2xl font-semibold">{formatInr(data.price)}</span>
              <span className={cn('tnum text-sm font-medium', gainClass(data.day_change_pct))}>
                {pct(data.day_change_pct)} today
              </span>
              {data.score && <Badge variant="outline">{data.score.bucket}</Badge>}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            {isError ? 'This company could not be loaded.' : 'Loading this company’s record.'}
          </p>
        )}
      </header>

      {isError && !data ? (
        <Panel title="Nothing to show">
          <Notice>
            {status === 404
              ? `${ticker} is not in the list of companies this app tracks. Either the symbol is wrong, or it is outside the NIFTY 500.`
              : status === 503
                ? (detailOf(error) ??
                  'The price feed did not answer. Nothing is broken; try again in a minute.')
                : 'We could not load this company. If it keeps failing, the price feed is probably down.'}
          </Notice>
        </Panel>
      ) : isPending || !data ? (
        <div className="flex flex-col gap-6">
          <Panel title="How the price has moved">
            <Skeleton className="h-72 w-full sm:h-96" />
          </Panel>
          <Panel title="Where the price sits today">
            <Skeleton className="h-24 w-full" />
          </Panel>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          <PricePanel data={data} range={range} onRange={setRange} busy={isFetching} />
          <TodayPanel data={data} />
          <RatiosPanel data={data} />

          {data.score ? (
            <Panel title="Its score, and what that score is not">
              <div className="flex flex-col gap-5">
                {data.plain.score && <p className="max-w-3xl text-sm">{data.plain.score}</p>}
                <StockScoreBreakdown stock={data.score} />
              </div>
            </Panel>
          ) : (
            <Panel title="Its score">
              <Notice>
                This company has too little price history to score. Under fifteen closing prices
                the momentum half of the method computes nothing at all — and the method it was
                copied from returns 100 out of 100 in that case, which is why nothing is shown
                here instead.
              </Notice>
            </Panel>
          )}

          <SimilarPanel data={data} />
        </div>
      )}
    </div>
  )
}
