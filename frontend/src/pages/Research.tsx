import { useState, type ReactNode } from 'react'
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
  fetchCategoryRanking,
  fetchFund,
  fetchStock,
  type RankedFund,
} from '@/lib/research-api'

const ASSET_CLASSES = [
  { value: 'equity', label: 'Equity (Flexi Cap)' },
  { value: 'debt', label: 'Debt (Corporate Bond)' },
  { value: 'gold', label: 'Gold' },
]

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

function FundRow({
  fund,
  rank,
  isOpen,
  onOpen,
}: {
  fund: RankedFund
  rank: number
  isOpen: boolean
  onOpen: () => void
}) {
  const m = fund.metrics

  return (
    <TableRow>
      <TableCell className="num text-muted-foreground">{rank}</TableCell>
      <TableCell className="max-w-[24rem] py-3 whitespace-normal">
        <button
          className="text-left font-medium leading-tight underline-offset-4 hover:underline"
          aria-expanded={isOpen}
          onClick={onOpen}
        >
          {fund.scheme_name}
        </button>
        <p className="mt-0.5 text-xs text-muted-foreground">{fund.category}</p>
      </TableCell>
      <TableCell className="text-right">
        <Badge variant={fund.score >= 70 ? 'default' : 'secondary'} className="num">
          {fund.score.toFixed(0)}
        </Badge>
      </TableCell>
      <TableCell className="num text-right">
        {formatPercent(m.cagr_3y, { signed: false })}
      </TableCell>
      <TableCell className="num text-right text-muted-foreground">
        {formatRatio(m.sortino)}
      </TableCell>
      <TableCell className="num text-right text-muted-foreground">
        {formatPercent(m.consistency, { signed: false })}
      </TableCell>
      <TableCell className="num text-right text-muted-foreground">
        {formatRatio(m.downside_capture)}
      </TableCell>
      <TableCell className={`num text-right ${gainClass(m.alpha)}`}>
        {formatPercent(m.alpha)}
      </TableCell>
    </TableRow>
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

        <MetricRow className="sm:grid-cols-3 lg:grid-cols-3 sm:[&>*:nth-child(3n+1)]:pl-0 sm:[&>*:nth-child(3n)]:border-r-0">
          <Metric
            label="1-year return"
            value={formatPercent(m.cagr_1y, { signed: false })}
            size="sm"
          />
          <Metric
            label="3-year return"
            value={formatPercent(m.cagr_3y, { signed: false })}
            hint="Annualised, so it is comparable with the 1 and 5-year figures."
            size="sm"
          />
          <Metric
            label="5-year return"
            value={formatPercent(m.cagr_5y, { signed: false })}
            size="sm"
          />
          <Metric
            label="Volatility"
            value={formatPercent(m.volatility, { signed: false })}
            hint="How much the NAV swings in a year. Higher means a bumpier ride."
            size="sm"
          />
          <Metric
            label="Sortino"
            value={formatRatio(m.sortino)}
            hint="Return per unit of downside risk. Higher is better."
            size="sm"
          />
          <Metric
            label="Worst fall"
            value={formatPercent(m.max_drawdown, { signed: false })}
            hint="The deepest peak-to-trough drop in the history we have."
            size="sm"
          />
          <Metric
            label="Alpha vs Nifty"
            value={formatPercent(m.alpha)}
            valueClassName={gainClass(m.alpha)}
            hint="Return above what the index gave over the same period."
            size="sm"
          />
          <Metric
            label="Downside capture"
            value={formatRatio(m.downside_capture)}
            hint="Below 1.00 means the fund fell less than the market did."
            size="sm"
          />
          <Metric
            label="Beat the index"
            value={formatPercent(m.consistency, { signed: false })}
            hint="Share of rolling periods it finished ahead of the benchmark."
            size="sm"
          />
        </MetricRow>
      </CardContent>
    </Card>
  )
}

function FundsLoading() {
  return (
    <div className="flex flex-col gap-3">
      <Skeleton className="h-5 w-40" />
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  )
}

function FundsTab() {
  const [assetClass, setAssetClass] = useState('equity')
  const [openFund, setOpenFund] = useState<string | null>(null)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['category', assetClass],
    queryFn: () => fetchCategoryRanking(assetClass),
    retry: false,
  })

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap gap-2">
        {ASSET_CLASSES.map((c) => (
          <Button
            key={c.value}
            size="sm"
            variant={assetClass === c.value ? 'default' : 'outline'}
            onClick={() => {
              setAssetClass(c.value)
              setOpenFund(null)
            }}
          >
            {c.label}
          </Button>
        ))}
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
              <h2 className="text-sm font-medium">Ranked by our score, best first</h2>
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
                    <TableHead className="text-right">Score</TableHead>
                    <TableHead className="text-right">3y return</TableHead>
                    <TableHead className="text-right">Sortino</TableHead>
                    <TableHead className="text-right">Beat index</TableHead>
                    <TableHead className="text-right">Down capture</TableHead>
                    <TableHead className="text-right">Alpha</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.ranked.map((f, i) => (
                    <FundRow
                      key={f.scheme_code}
                      fund={f}
                      rank={i + 1}
                      isOpen={openFund === f.scheme_code}
                      onOpen={() =>
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
              {data.benchmarked
                ? `Scored against the ${data.benchmark_name}. A higher score is better, and a downside capture below 1.00 means the fund fell less than the market did.`
                : 'Not benchmarked against equities. A debt or gold fund is not trying to track the Nifty, so it is ranked on its own risk-adjusted record.'}
            </p>

            {data.benchmark_caveat && (
              <Notice>{plainProse(data.benchmark_caveat)}</Notice>
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

function StocksTab() {
  const [input, setInput] = useState('')
  const [ticker, setTicker] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['stock', ticker],
    queryFn: () => fetchStock(ticker as string),
    enabled: !!ticker,
    retry: false,
  })

  return (
    <div className="flex flex-col gap-8">
      <form
        className="flex max-w-sm items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          const t = input.trim().toUpperCase()
          if (!t) return
          setTicker(t.includes('.') ? t : `${t}.NS`)
        }}
      >
        <div className="flex flex-1 flex-col gap-1.5">
          <Label htmlFor="ticker">NSE ticker</Label>
          <Input
            id="ticker"
            placeholder="RELIANCE"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
        </div>
        <Button type="submit">Look up</Button>
      </form>

      {!ticker && (
        <p className="max-w-2xl text-sm text-muted-foreground">
          Type an NSE ticker to see the live price and the basic fundamentals. Plain
          names work, so RELIANCE and TCS are enough; we add the .NS suffix for you.
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
