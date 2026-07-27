import { useEffect, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Metric, MetricRow } from '@/components/ui/metric'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  NO_VALUE,
  formatInr,
  formatInrCompact,
  formatPercent,
  formatRatio,
  gainClass,
  plainProse,
} from '@/lib/format'
import {
  fetchFund,
  fetchCategoryRankingV2,
  fetchFundCategories,
  fetchStock,
  fetchStockUniverse,
  fetchStockScore,
  type RankedFundV2,
} from '@/lib/research-api'

/**
 * Caveats and failures both sit at the same weight: a quiet line with a mark
 * beside it. Amber would be a second accent, and none of these are emergencies.
 */
function Notice({ children }: { children: ReactNode }) {
  return (
    <p className="flex max-w-3xl items-start gap-2 text-sm text-muted-foreground">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  )
}

/**
 * The one place a card earns its elevation on this page: it is a detail view
 * opened on top of the list, and the border is what says so.
 */
function FundDetailPanel({
  schemeCode,
  onClose,
}: {
  schemeCode: string
  onClose: () => void
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['fund', schemeCode],
    queryFn: () => fetchFund(schemeCode),
  })

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex flex-col gap-6">
          <Skeleton className="h-10 w-80" />
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (isError || !data) {
    return (
      <Card>
        <CardContent className="flex flex-col gap-3">
          <Notice>
            We could not load this fund's NAV history. Close this panel and open it
            again, and if it keeps failing the AMFI feed is probably down.
          </Notice>
          <div>
            <Button variant="outline" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  const m = data.metrics
  const ev = data.evidence
  const w3 = ev?.windows['3y']

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="flex flex-col gap-1.5">
            <h3 className="text-lg font-medium leading-tight">{data.scheme_name}</h3>
            <p className="text-sm text-muted-foreground">
              {data.fund_house} &middot; {data.category}
            </p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-1">
              <Badge variant={data.is_direct_growth ? 'secondary' : 'destructive'}>
                {data.is_direct_growth ? 'Direct Growth' : 'Regular plan'}
              </Badge>
              <span className="text-sm">
                NAV <span className="tnum font-medium">{formatInr(data.latest_nav)}</span>{' '}
                <span className="tnum text-xs text-muted-foreground">
                  on {data.latest_nav_date}
                </span>
              </span>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-8">
        <section className="flex flex-col gap-3">
          <h4 className="text-sm font-medium">NAV over time</h4>
          <div className="h-56 w-full sm:h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.nav_series}
                margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
              >
                <CartesianGrid
                  vertical={false}
                  stroke="var(--border)"
                  strokeDasharray="2 4"
                />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  minTickGap={48}
                  tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  tickFormatter={(d: string) => d.slice(0, 4)}
                />
                <YAxis
                  width={56}
                  tickLine={false}
                  axisLine={false}
                  domain={['auto', 'auto']}
                  tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  tickFormatter={(v: number) => formatInrCompact(v)}
                />
                <Tooltip
                  cursor={{ stroke: 'var(--muted-foreground)', strokeWidth: 1 }}
                  contentStyle={{
                    background: 'var(--popover)',
                    color: 'var(--popover-foreground)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 12,
                  }}
                  formatter={(v) => [formatInr(Number(v)), 'NAV'] as [string, string]}
                />
                <Line
                  type="monotone"
                  dataKey="nav"
                  stroke="var(--primary)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* The same evidence the ranking is built from. Sortino, alpha and
            downside capture used to sit here, which meant this panel and the
            list beside it judged the same fund on two different models. */}
        <MetricRow className="sm:grid-cols-3 lg:grid-cols-3 sm:[&>*:nth-child(3n+1)]:pl-0 sm:[&>*:nth-child(3n)]:border-r-0">
          <Metric
            label="Worst 3 years"
            value={w3 ? formatPercent(w3.worst) : NO_VALUE}
            valueClassName={w3 ? gainClass(w3.worst) : undefined}
            hint="The least it ever returned over a full three years, across every possible start date."
            size="sm"
          />
          <Metric
            label="Windows won"
            value={w3 ? formatPercent(w3.share_positive, { signed: false }) : NO_VALUE}
            hint={
              w3
                ? `How many of its ${w3.count.toLocaleString('en-IN')} three-year windows made money.`
                : undefined
            }
            size="sm"
          />
          <Metric
            label="3-year average"
            value={w3 ? formatPercent(w3.mean, { signed: false }) : NO_VALUE}
            hint="Averaged across every window, not measured between two chosen dates."
            size="sm"
          />
          <Metric
            label="Volatility"
            value={formatPercent(m.volatility, { signed: false })}
            hint="How much the NAV swings in a year. Higher means a bumpier ride."
            size="sm"
          />
          <Metric
            label="Worst fall"
            value={formatPercent(m.max_drawdown, { signed: false })}
            hint="The deepest peak-to-trough drop in the history we have."
            size="sm"
          />
          <Metric
            label="Record length"
            value={ev?.history_years ? `${ev.history_years}y` : NO_VALUE}
            hint={
              ev && ev.evidence_strength < 0.5
                ? 'Short enough that its windows nearly all describe one market, so its consistency counts for less.'
                : 'Long enough to have been through more than one market.'
            }
            size="sm"
          />
          <Metric
            label="Cost, direct"
            value={ev?.direct_ter != null ? formatPercent(ev.direct_ter, { signed: false }) : NO_VALUE}
            hint="The direct plan's expense ratio, charged every year."
            size="sm"
          />
          <Metric
            label="Cost, regular"
            value={ev?.regular_ter != null ? formatPercent(ev.regular_ter, { signed: false }) : NO_VALUE}
            hint="What the same fund costs bought through a distributor."
            size="sm"
          />
          <Metric
            label="Commission"
            value={
              ev?.direct_ter != null && ev?.regular_ter != null
                ? formatPercent(ev.regular_ter - ev.direct_ter)
                : NO_VALUE
            }
            valueClassName={
              ev?.direct_ter != null && ev?.regular_ter != null ? 'text-loss' : undefined
            }
            hint="What the regular plan takes out of your return every year, for the identical portfolio."
            size="sm"
          />
        </MetricRow>
      </CardContent>
    </Card>
  )
}

/**
 * A category is scored by fetching every constituent fund's NAV history, and
 * the largest holds 364 of them. Cached that is instant, but the first time
 * anyone opens it the wait runs into double-digit seconds. A bare skeleton for
 * that long reads as a broken page, so after a few seconds it says what it is
 * waiting for.
 */
function FundsLoading() {
  const [slow, setSlow] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 2500)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex flex-col gap-3">
      {slow ? (
        <p className="text-sm text-muted-foreground">
          Fetching the NAV history of every fund in this category. The first look
          at a category can take a few seconds; after that it is instant.
        </p>
      ) : (
        <Skeleton className="h-5 w-64" />
      )}
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  )
}

/** "Equity Scheme - Small Cap Fund" is how SEBI writes it, not how anyone says it. */
function shortCategory(category: string): string {
  return category.split(' - ').slice(1).join(' - ') || category
}

function categoryGroup(category: string): string {
  return category.split(' Scheme')[0]
}

const DEFAULT_CATEGORY = 'Equity Scheme - Flexi Cap Fund'


/**
 * A fund's row, and its reasoning underneath when opened. The reasoning is a
 * paragraph rather than a metric grid because a Sortino ratio is an input to a
 * judgement, not the judgement — and it is the judgement a holder can act on.
 */
function RankedRow({
  fund,
  isOpen,
  onToggle,
}: {
  fund: RankedFundV2
  isOpen: boolean
  onToggle: () => void
}) {
  const w3 = fund.windows['3y']
  const thin = fund.evidence_strength < 0.5

  return (
    <>
      <TableRow className="group">
        <TableCell className="num align-top text-muted-foreground">{fund.rank}</TableCell>
        <TableCell className="max-w-[26rem] py-3 align-top whitespace-normal">
          <button
            className="text-left font-medium leading-tight underline-offset-4 hover:underline"
            aria-expanded={isOpen}
            onClick={onToggle}
          >
            {fund.scheme_name}
          </button>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {fund.history_years !== null && (
              <span className="tnum">{fund.history_years}y record</span>
            )}
            {thin && ' · thin record'}
          </p>
        </TableCell>
        <TableCell className="num text-right align-top font-medium">
          {fund.direct_ter !== null
            ? formatPercent(fund.direct_ter, { signed: false })
            : NO_VALUE}
        </TableCell>
        <TableCell className="text-right align-top">
          <Badge variant={fund.score >= 70 ? 'default' : 'secondary'} className="num">
            {fund.score.toFixed(0)}
          </Badge>
        </TableCell>
        <TableCell
          className={`num text-right align-top ${w3 ? gainClass(w3.worst) : ''}`}
        >
          {w3 ? formatPercent(w3.worst) : NO_VALUE}
        </TableCell>
        <TableCell className="num text-right align-top text-muted-foreground">
          {w3 ? formatPercent(w3.share_positive, { signed: false }) : NO_VALUE}
        </TableCell>
        <TableCell className="num text-right align-top text-muted-foreground">
          {w3 ? formatPercent(w3.mean, { signed: false }) : NO_VALUE}
        </TableCell>
      </TableRow>
      {isOpen && (
        <TableRow className="hover:bg-transparent">
          <TableCell />
          <TableCell colSpan={6} className="pb-6 whitespace-normal">
            <p className="max-w-3xl text-sm font-medium">{fund.verdict.headline}</p>
            <ul className="mt-3 flex max-w-3xl flex-col gap-2">
              {fund.verdict.points.map((point) => (
                <li key={point} className="flex gap-2 text-sm text-muted-foreground">
                  <span aria-hidden className="text-muted-foreground/50">&middot;</span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
            {fund.verdict.caveat && (
              <div className="mt-3 max-w-3xl">
                <Notice>{fund.verdict.caveat}</Notice>
              </div>
            )}
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

function FundsTab() {
  const [category, setCategory] = useState(DEFAULT_CATEGORY)
  const [openFund, setOpenFund] = useState<string | null>(null)

  const { data: categories } = useQuery({
    queryKey: ['fund-categories'],
    queryFn: fetchFundCategories,
  })

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['fund-ranking', category],
    // A representative SIP, only so the commission line can be priced in
    // rupees. It does not affect the ranking.
    queryFn: () => fetchCategoryRankingV2(category, { monthly_sip: 15000, years: 15 }),
    retry: false,
  })

  // Grouped by scheme type so the list reads as Equity / Debt / Hybrid rather
  // than ninety alphabetical strings.
  const grouped = (categories ?? []).reduce<Record<string, string[]>>((acc, c) => {
    ;(acc[categoryGroup(c)] ??= []).push(c)
    return acc
  }, {})

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="fund-category">Category</Label>
        <select
          id="fund-category"
          className="h-9 w-full max-w-md rounded-md border bg-transparent px-2 text-sm"
          value={category}
          onChange={(e) => {
            setCategory(e.target.value)
            setOpenFund(null)
          }}
        >
          {Object.entries(grouped).map(([group, items]) => (
            <optgroup key={group} label={group}>
              {items.map((c) => (
                <option key={c} value={c}>
                  {shortCategory(c)}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {openFund && (
        <FundDetailPanel schemeCode={openFund} onClose={() => setOpenFund(null)} />
      )}

      {isLoading && <FundsLoading />}

      {isError && (
        <Notice>
          {plainProse(
            (error as any)?.response?.data?.detail ??
              'Fund data is not available right now. Refresh the page to try again, and if it keeps failing the AMFI feed is down rather than your connection.',
          )}
        </Notice>
      )}

      {data && data.ranked.length === 0 && (
        <Notice>
          Nothing in this category could be scored yet. We need a few years of NAV
          history per fund before a ranking means anything.
        </Notice>
      )}

      {data && data.ranked.length > 0 && (
        <>
          <section className="flex flex-col gap-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
              <h2 className="text-sm font-medium">Ranked cheapest first</h2>
              <p className="text-xs text-muted-foreground">
                Select a fund to see its full record.
              </p>
            </div>
            <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-8">#</TableHead>
                    <TableHead>Fund</TableHead>
                    <TableHead className="text-right">Cost / yr</TableHead>
                    <TableHead className="text-right">Score</TableHead>
                    <TableHead className="text-right">Worst 3y</TableHead>
                    <TableHead className="text-right">Windows won</TableHead>
                    <TableHead className="text-right">3y avg</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.ranked.map((f) => (
                    <RankedRow
                      key={f.scheme_code}
                      fund={f}
                      isOpen={openFund === f.scheme_code}
                      onToggle={() =>
                        setOpenFund(openFund === f.scheme_code ? null : f.scheme_code)
                      }
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          </section>

          <div className="flex flex-col gap-3">
            <p className="max-w-3xl text-sm text-muted-foreground">
              The score is mostly cost, because cost is the only thing here that
              predicts. We tested both: over 52 three-year windows the cheapest
              quarter of funds beat the dearest quarter in 45 of them, while
              ranking by past returns beat its category median in half of sixty
              windows, which is a coin flip.
            </p>
            <p className="max-w-3xl text-sm text-muted-foreground">
              So &ldquo;3y avg&rdquo; is shown because it is true, not because it
              forecasts anything. &ldquo;Worst 3y&rdquo; is the least a fund ever
              returned over a full three years across every possible start date,
              and &ldquo;windows won&rdquo; is how often those three years made
              money. Those two describe what holding it felt like, which is what
              decides whether you stay invested through a bad year.
            </p>
            {data.priced > 0 && (
              <p className="max-w-3xl text-sm text-muted-foreground">
                <span className="tnum">{data.priced}</span> of these funds publish
                both plans, so opening one shows what the regular plan&rsquo;s
                commission costs you a year and over a fifteen-year SIP.
              </p>
            )}

            {data.unscorable.length > 0 && (
              <p className="max-w-3xl text-sm text-muted-foreground">
                Left out of the ranking:{' '}
                {data.unscorable.map((u) => u.scheme_name).join(', ')}.{' '}
                {plainProse(data.unscorable[0].reason)}.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function StockLoading() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-12 w-56" />
      </div>
      <Skeleton className="h-28 w-full" />
    </div>
  )
}

const STOCK_PAGE_SIZE = 60

function StockBrowser({
  selected,
  onSelect,
}: {
  selected: string | null
  onSelect: (ticker: string) => void
}) {
  const [index, setIndex] = useState('NIFTY 50')
  const [industry, setIndustry] = useState<string>('')
  const [query, setQuery] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['stock-universe', index, industry, query],
    queryFn: () =>
      fetchStockUniverse({
        index,
        industry: industry || undefined,
        q: query.trim() || undefined,
        limit: STOCK_PAGE_SIZE,
      }),
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="stock-search">Search</Label>
          <Input
            id="stock-search"
            className="w-56"
            placeholder="Reliance, TCS, Larsen"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="stock-index">Index</Label>
          <select
            id="stock-index"
            className="h-9 rounded-md border bg-transparent px-2 text-sm"
            value={index}
            onChange={(e) => setIndex(e.target.value)}
          >
            {(data?.available_indices ?? ['NIFTY 50']).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="stock-industry">Industry</Label>
          <select
            id="stock-industry"
            className="h-9 rounded-md border bg-transparent px-2 text-sm"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          >
            <option value="">All industries</option>
            {(data?.available_industries ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && <Skeleton className="h-64 w-full" />}

      {data && data.stocks.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Nothing in {index} matches that. Try a wider index, or clear the industry
          filter.
        </p>
      )}

      {data && data.stocks.length > 0 && (
        <>
          <ul className="grid gap-x-6 border-t sm:grid-cols-2 lg:grid-cols-3">
            {data.stocks.map((s) => (
              <li key={s.symbol} className="border-b">
                <button
                  type="button"
                  onClick={() => onSelect(s.ticker)}
                  aria-current={selected === s.ticker}
                  className={`flex w-full flex-col items-start gap-0.5 py-2.5 text-left transition-colors hover:text-primary ${
                    selected === s.ticker ? 'text-primary' : ''
                  }`}
                >
                  <span className="num text-sm font-medium">{s.symbol}</span>
                  <span className="line-clamp-1 text-xs text-muted-foreground">
                    {s.name}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">
            {/* Says what is hidden rather than implying the list is complete. */}
            Showing <span className="tnum">{data.stocks.length}</span> of{' '}
            <span className="tnum">{data.total}</span>. Narrow the search to see the
            rest.
          </p>
        </>
      )}
    </div>
  )
}


/**
 * A company's score and why. The factors are shown as their own sentences
 * rather than a bar chart, because "P/E 16.7 against a sector median of 29.0"
 * is the thing a buyer can argue with; a bar cannot be argued with.
 */
function StockScorePanel({ ticker }: { ticker: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['stock-score', ticker],
    queryFn: () => fetchStockScore(ticker),
    retry: false,
  })

  if (isLoading) return <Skeleton className="h-56 w-full" />
  if (isError || !data) return null

  const known = Object.entries(data.factors).filter(
    ([, f]) => !f.detail.startsWith('Not published'),
  )

  return (
    <section className="flex flex-col gap-4 border-t pt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="text-sm font-medium">How it scores against its peers</h2>
        <span className="num text-2xl font-medium">
          {data.total.toFixed(0)}
          <span className="text-sm text-muted-foreground"> / 100</span>
        </span>
      </div>

      <p className="max-w-3xl text-sm">{data.verdict.headline}</p>

      <ul className="flex flex-col divide-y border-y">
        {known.map(([key, f]) => (
          <li key={key} className="flex flex-wrap items-baseline justify-between gap-x-6 py-2.5">
            <span className="text-sm text-muted-foreground">{f.detail}</span>
            <span className="num text-xs text-muted-foreground">
              {f.score.toFixed(1)}
            </span>
          </li>
        ))}
      </ul>

      {data.adjustments.length > 0 && (
        <ul className="flex flex-col gap-2">
          {data.adjustments.map((a) => (
            <li key={a.name} className="flex gap-2 text-sm">
              <span className={`num shrink-0 ${a.points < 0 ? 'text-loss' : 'text-gain'}`}>
                {a.points > 0 ? '+' : ''}
                {a.points}
              </span>
              <span className="text-muted-foreground">{a.detail}</span>
            </li>
          ))}
        </ul>
      )}

      {data.range_position !== null && (
        <p className="max-w-3xl text-sm text-muted-foreground">
          Trading{' '}
          <span className="tnum">
            {formatPercent(data.range_position, { signed: false })}
          </span>{' '}
          of the way up its 52-week range. That is where the price sits, not a view
          on where it goes next.
        </p>
      )}

      {data.verdict.caveat && <Notice>{data.verdict.caveat}</Notice>}

      {data.benchmark_used === '_ALL' && (
        <Notice>
          Its sector has too few listed peers to take a median from, so it is scored
          against the whole market instead. Read the valuation lines with that in
          mind.
        </Notice>
      )}
    </section>
  )
}

function StocksTab() {
  const [ticker, setTicker] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['stock', ticker],
    queryFn: () => fetchStock(ticker as string),
    enabled: !!ticker,
    retry: false,
  })

  return (
    <div className="flex flex-col gap-8">
      <StockBrowser selected={ticker} onSelect={setTicker} />

      {!ticker && (
        <p className="max-w-2xl border-t pt-6 text-sm text-muted-foreground">
          Pick a company to see its live price and fundamentals. These are raw
          figures from the exchange feed, not a view on whether the stock is worth
          owning.
        </p>
      )}

      {isLoading && <StockLoading />}

      {isError && (
        <Notice>
          We found no data for that ticker. Check the spelling: NSE tickers look like
          RELIANCE.NS or TCS.NS, and BSE-only listings are not covered.
        </Notice>
      )}

      {data && (
        <div className="flex flex-col gap-8">
          <header className="flex flex-col gap-1.5">
            <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {data.name}
            </h2>
            <p className="num num-display text-4xl font-semibold leading-none sm:text-5xl">
              {formatInr(data.price)}
            </p>
            <p className={`tnum text-sm ${gainClass(data.day_change_pct)}`}>
              {data.day_change_pct === null
                ? "Today's change is not available"
                : `${data.day_change_pct >= 0 ? '+' : '−'}${Math.abs(
                    data.day_change_pct,
                  ).toFixed(2)}% today`}
            </p>
            <p className="text-xs text-muted-foreground">
              <span className="tnum">{data.ticker}</span>
              {data.sector ? ` · ${data.sector}` : ''}
              {data.industry ? ` · ${data.industry}` : ''}
            </p>
          </header>

          {ticker && <StockScorePanel ticker={ticker} />}

          <MetricRow className="sm:grid-cols-3 lg:grid-cols-3 sm:[&>*:nth-child(3n+1)]:pl-0 sm:[&>*:nth-child(3n)]:border-r-0">
            <Metric
              label="P/E ratio"
              value={formatRatio(data.pe_ratio)}
              hint="Rupees of price for each rupee of yearly earnings."
              size="sm"
            />
            <Metric
              label="Earnings per share"
              value={formatInr(data.eps)}
              hint="Profit over the last year, per share."
              size="sm"
            />
            <Metric
              label="Book value"
              value={formatInr(data.book_value)}
              hint="Net assets per share, from the balance sheet."
              size="sm"
            />
            <Metric
              label="Market cap"
              value={
                data.market_cap === null
                  ? NO_VALUE
                  : `${formatInr(data.market_cap / 1e7)} cr`
              }
              hint="Price times every share outstanding, in crore rupees."
              size="sm"
            />
            <Metric
              label="Dividend yield"
              value={
                data.dividend_yield_pct === null
                  ? NO_VALUE
                  : `${data.dividend_yield_pct}%`
              }
              hint="Dividend paid over the last year, against today's price."
              size="sm"
            />
            <Metric
              label="52-week range"
              value={
                data.week52_low !== null && data.week52_high !== null
                  ? `${formatInr(data.week52_low)} to ${formatInr(data.week52_high)}`
                  : NO_VALUE
              }
              hint="Where today's price sits against the last year."
              size="sm"
            />
          </MetricRow>
        </div>
      )}
    </div>
  )
}

export function Research() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Research</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Fund scores here are worked out by NexTrade from public NAV history. They
          are not a licensed rating, and nothing on this page is a recommendation to
          buy.
        </p>
      </header>

      <Tabs defaultValue="funds" className="gap-6">
        <TabsList>
          <TabsTrigger value="funds">Mutual funds</TabsTrigger>
          <TabsTrigger value="stocks">Stocks</TabsTrigger>
        </TabsList>
        <TabsContent value="funds">
          <FundsTab />
        </TabsContent>
        <TabsContent value="stocks">
          <StocksTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
