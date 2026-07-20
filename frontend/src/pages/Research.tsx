import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
import { formatInr, formatPercent, gainClass } from '@/lib/format'
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

function MetricCell({ value, kind }: { value: number | null; kind: 'pct' | 'ratio' }) {
  if (value === null) return <span className="text-muted-foreground">—</span>
  if (kind === 'ratio') return <span className="tabular-nums">{value.toFixed(2)}</span>
  return <span className="tabular-nums">{formatPercent(value, { signed: false })}</span>
}

function FundRow({ fund, rank, onOpen }: { fund: RankedFund; rank: number; onOpen: () => void }) {
  const m = fund.metrics
  return (
    <TableRow>
      <TableCell className="text-muted-foreground tabular-nums">{rank}</TableCell>
      <TableCell>
        <button className="text-left hover:underline" onClick={onOpen}>
          <span className="font-medium">{fund.scheme_name}</span>
        </button>
      </TableCell>
      <TableCell className="text-right">
        <Badge variant={fund.score >= 70 ? 'default' : 'secondary'}>
          {fund.score.toFixed(0)}
        </Badge>
      </TableCell>
      <TableCell className="text-right"><MetricCell value={m.cagr_3y} kind="pct" /></TableCell>
      <TableCell className="text-right"><MetricCell value={m.sortino} kind="ratio" /></TableCell>
      <TableCell className="text-right"><MetricCell value={m.consistency} kind="pct" /></TableCell>
      <TableCell className="text-right">
        <MetricCell value={m.downside_capture} kind="ratio" />
      </TableCell>
      <TableCell className={`text-right ${gainClass(m.alpha)}`}>
        <MetricCell value={m.alpha} kind="pct" />
      </TableCell>
    </TableRow>
  )
}

function FundDetailPanel({ schemeCode, onClose }: { schemeCode: string; onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['fund', schemeCode],
    queryFn: () => fetchFund(schemeCode),
  })

  if (isLoading) return <Skeleton className="h-80 w-full rounded-xl" />
  if (isError || !data) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-destructive">
          Couldn't load this fund.
        </CardContent>
      </Card>
    )
  }

  const m = data.metrics
  const chart = data.nav_series.map((p) => ({ date: p.date, nav: p.nav }))

  const rows: [string, string][] = [
    ['1-year return', formatPercent(m.cagr_1y, { signed: false })],
    ['3-year return', formatPercent(m.cagr_3y, { signed: false })],
    ['5-year return', formatPercent(m.cagr_5y, { signed: false })],
    ['Volatility', formatPercent(m.volatility, { signed: false })],
    ['Sortino', m.sortino?.toFixed(2) ?? '—'],
    ['Worst fall', formatPercent(m.max_drawdown, { signed: false })],
    ['Alpha vs Nifty', m.alpha === null ? '—' : formatPercent(m.alpha)],
    ['Downside capture', m.downside_capture?.toFixed(2) ?? '—'],
    ['Beat benchmark', formatPercent(m.consistency, { signed: false })],
  ]

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <CardTitle>{data.scheme_name}</CardTitle>
            <CardDescription>
              {data.fund_house} · {data.category}
            </CardDescription>
            <div className="flex items-center gap-2 pt-1">
              {data.is_direct_growth ? (
                <Badge variant="secondary">Direct Growth</Badge>
              ) : (
                <Badge variant="destructive">Regular plan</Badge>
              )}
              <span className="text-sm tabular-nums">
                NAV {formatInr(data.latest_nav)}{' '}
                <span className="text-xs text-muted-foreground">
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
      <CardContent className="flex flex-col gap-6">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chart} margin={{ left: 4, right: 4, top: 4, bottom: 4 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              tickFormatter={(d: string) => d.slice(0, 4)}
              minTickGap={40}
              stroke="var(--border)"
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              width={48}
              stroke="var(--border)"
              domain={['auto', 'auto']}
            />
            <Tooltip
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
              stroke="var(--chart-1)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>

        <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
          {rows.map(([label, value]) => (
            <div key={label} className="flex justify-between border-b py-1 text-sm">
              <span className="text-muted-foreground">{label}</span>
              <span className="tabular-nums">{value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
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
    <div className="flex flex-col gap-4">
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

      {isLoading && <Skeleton className="h-64 w-full rounded-xl" />}

      {isError && (
        <Card>
          <CardContent className="py-6 text-sm text-amber-600 dark:text-amber-400">
            {(error as any)?.response?.data?.detail ??
              'Fund data is temporarily unavailable. Please refresh to retry.'}
          </CardContent>
        </Card>
      )}

      {data && (
        <>
          <Card className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">#</TableHead>
                  <TableHead>Fund</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead className="text-right">3y</TableHead>
                  <TableHead className="text-right">Sortino</TableHead>
                  <TableHead className="text-right">Beat bmk</TableHead>
                  <TableHead className="text-right">Down cap</TableHead>
                  <TableHead className="text-right">Alpha</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.ranked.map((f, i) => (
                  <FundRow
                    key={f.scheme_code}
                    fund={f}
                    rank={i + 1}
                    onOpen={() => setOpenFund(f.scheme_code)}
                  />
                ))}
              </TableBody>
            </Table>
          </Card>

          <p className="text-xs text-muted-foreground">
            {data.benchmarked
              ? 'Scored against the Nifty 50. Higher score is better; downside capture below 1.00 means the fund fell less than the market.'
              : 'Not benchmarked against equities — a debt or gold fund is not trying to track the Nifty, so it is ranked on its own risk-adjusted record.'}
          </p>

          {data.unscorable.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Left out: {data.unscorable.map((u) => u.scheme_name).join(', ')} —{' '}
              {data.unscorable[0].reason.toLowerCase()}.
            </p>
          )}
        </>
      )}
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

  const rows: [string, string][] = data
    ? [
        ['Sector', data.sector ?? '—'],
        ['Industry', data.industry ?? '—'],
        ['P/E ratio', data.pe_ratio?.toFixed(1) ?? '—'],
        ['EPS', data.eps ? formatInr(data.eps) : '—'],
        ['Book value', data.book_value ? formatInr(data.book_value) : '—'],
        [
          'Market cap',
          data.market_cap ? `${formatInr(data.market_cap / 1e7)} cr` : '—',
        ],
        [
          'Dividend yield',
          data.dividend_yield_pct !== null ? `${data.dividend_yield_pct}%` : '—',
        ],
        [
          '52-week range',
          data.week52_low && data.week52_high
            ? `${formatInr(data.week52_low)} – ${formatInr(data.week52_high)}`
            : '—',
        ],
      ]
    : []

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          const t = input.trim().toUpperCase()
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

      {isLoading && <Skeleton className="h-48 w-full rounded-xl" />}

      {isError && (
        <Card>
          <CardContent className="py-6 text-sm text-amber-600 dark:text-amber-400">
            No data for that ticker. NSE tickers look like RELIANCE.NS or TCS.NS.
          </CardContent>
        </Card>
      )}

      {data && (
        <Card>
          <CardHeader>
            <CardTitle>{data.name}</CardTitle>
            <CardDescription>{data.ticker}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-semibold tabular-nums">
                {formatInr(data.price)}
              </span>
              <span className={`text-sm tabular-nums ${gainClass(data.day_change_pct)}`}>
                {data.day_change_pct === null
                  ? '—'
                  : `${data.day_change_pct >= 0 ? '+' : '−'}${Math.abs(data.day_change_pct).toFixed(2)}% today`}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
              {rows.map(([label, value]) => (
                <div key={label} className="flex justify-between border-b py-1 text-sm">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="tabular-nums">{value}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export function Research() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Research</h1>
        <p className="text-sm text-muted-foreground">
          Fund scores are computed here from public NAV history — they are not a
          licensed rating.
        </p>
      </div>

      <Tabs defaultValue="funds">
        <TabsList>
          <TabsTrigger value="funds">Mutual funds</TabsTrigger>
          <TabsTrigger value="stocks">Stocks</TabsTrigger>
        </TabsList>
        <TabsContent value="funds" className="pt-4">
          <FundsTab />
        </TabsContent>
        <TabsContent value="stocks" className="pt-4">
          <StocksTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
