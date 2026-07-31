import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Trash2 } from 'lucide-react'
import { AddHoldingDialog } from '@/components/AddHoldingDialog'
import { AddTransactionDialog } from '@/components/AddTransactionDialog'
import { Announcements } from '@/components/Announcements'
import { CostReview } from '@/components/CostReview'
import { FundOverlap } from '@/components/FundOverlap'
import { Levers } from '@/components/Levers'
import { PortfolioChart } from '@/components/PortfolioChart'
import { StartHere } from '@/components/StartHere'
import { Button } from '@/components/ui/button'
import { Metric, MetricRow } from '@/components/ui/metric'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  formatInr,
  formatInrSigned,
  formatPercent,
  formatUnits,
  gainClass,
} from '@/lib/format'
import {
  PORTFOLIO_QUERY_KEYS,
  deleteHolding,
  fetchBenchmark,
  fetchHistory,
  fetchPortfolio,
  type HoldingSummary,
} from '@/lib/portfolio-api'

function BenchmarkVerdict() {
  const { data, isLoading } = useQuery({
    queryKey: ['benchmark'],
    queryFn: fetchBenchmark,
  })

  if (isLoading) return <Skeleton className="h-14 w-full" />
  if (!data) return null

  if (!data.comparable) {
    return (
      <p className="border-l-2 py-1 pl-3 text-sm text-muted-foreground">
        {data.reason ?? 'Not enough history to compare against the index yet.'}
      </p>
    )
  }

  const gap = data.outperformance ?? 0
  const ahead = gap >= 0

  return (
    <div className="flex flex-col gap-1 border-l-2 border-primary py-1 pl-3">
      <p className="text-sm">
        Your funds are{' '}
        <span className={`tnum font-medium ${gainClass(gap)}`}>
          {Math.abs(gap * 100).toFixed(1)}pp {ahead ? 'ahead of' : 'behind'}
        </span>{' '}
        the Nifty 50 on the same money and the same dates.
      </p>
      <p className="tnum text-xs text-muted-foreground">
        {formatInr(data.portfolio_value)} against {formatInr(data.benchmark_value)} in
        the index &middot; XIRR {formatPercent(data.portfolio_xirr)} against{' '}
        {formatPercent(data.benchmark_xirr)}
      </p>
    </div>
  )
}

function HoldingRow({ holding }: { holding: HoldingSummary }) {
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: () => deleteHolding(holding.holding_id),
    onSuccess: () => {
      // Every view that reads the holdings list, not the three somebody
      // remembered at the time. The cost review, the levers, the overlap and
      // the filings all kept describing a fund that had just been deleted.
      for (const key of PORTFOLIO_QUERY_KEYS) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
  })

  return (
    <TableRow className="group">
      <TableCell className="max-w-[22rem] py-3">
        <p className="truncate font-medium leading-tight">{holding.name}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {holding.asset_type === 'MF' ? 'Fund' : 'Stock'} &middot;{' '}
          <span className="tnum">{holding.identifier}</span>
          {holding.category ? ` · ${holding.category}` : ''}
        </p>
        {/* The scheme code drives every number here; the name is only a label.
            When they disagree, nothing errors — the figures are simply about a
            different fund. That is worth interrupting for. */}
        {holding.misnamed_as && (
          <p className="mt-1 flex items-start gap-1 text-xs font-medium">
            <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
            <span>
              Code <span className="tnum">{holding.identifier}</span> is{' '}
              <strong>{holding.misnamed_as}</strong>. Every figure below is for
              that fund, not the name above &mdash; fix the name or the code.
            </span>
          </p>
        )}
        {/* A NAV keeps being returned after a scheme stops publishing, so a
            frozen price otherwise reads as today's value. */}
        {holding.stale_days !== null && (
          <p className="mt-1 flex items-start gap-1 text-xs font-medium">
            <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
            <span>
              Priced from a NAV of{' '}
              <span className="tnum">{holding.price_as_of}</span>, which is{' '}
              <span className="tnum">{holding.stale_days}</span> days behind
              your other funds. This value is not current.
            </span>
          </p>
        )}
        {holding.price_error && (
          <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
            <AlertTriangle className="size-3 shrink-0" aria-hidden />
            Live price unavailable, so this is left out of the returns
          </p>
        )}
      </TableCell>
      <TableCell className="num text-right text-muted-foreground">
        {formatUnits(holding.units_held)}
      </TableCell>
      <TableCell className="num text-right">{formatInr(holding.invested)}</TableCell>
      <TableCell className="num text-right font-medium">
        {formatInr(holding.current_value)}
      </TableCell>
      <TableCell className={`num text-right ${gainClass(holding.unrealised_gain)}`}>
        <span className="block">{formatInrSigned(holding.unrealised_gain)}</span>
        <span className="block text-xs opacity-80">
          {formatPercent(holding.absolute_return)}
        </span>
      </TableCell>
      <TableCell className={`num text-right ${gainClass(holding.xirr)}`}>
        {formatPercent(holding.xirr)}
      </TableCell>
      <TableCell className="text-right">
        {/* Held at low emphasis until the row is hovered: these are per-row
            controls, not the page's primary action. */}
        <div className="flex justify-end gap-1 opacity-60 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <AddTransactionDialog holding={holding} />
          <Button
            variant="ghost"
            size="xs"
            aria-label={`Remove ${holding.name}`}
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
          >
            <Trash2 className="size-3.5" aria-hidden />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

function LoadingState() {
  return (
    <div className="flex flex-col gap-8">
      <Skeleton className="h-20 w-72" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-72 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}

/**
 * Nothing owned yet. The page used to open with "add a fund", which is the most
 * work for the least money — see StartHere for the order that is actually worth
 * something.
 */
function EmptyState() {
  return (
    <div className="flex flex-col gap-10">
      <StartHere />
      <p className="max-w-2xl text-sm text-muted-foreground">
        Once something is in here, this page works out your real return — the
        money-weighted XIRR that a simple percentage hides — against what the same
        money would have done in the index, and what your regular plans are costing
        you.
      </p>
    </div>
  )
}

export function Portfolio() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
  })
  const { data: history } = useQuery({
    queryKey: ['history'],
    queryFn: fetchHistory,
    enabled: !!data && data.holdings.length > 0,
  })

  if (isLoading) return <LoadingState />

  if (isError || !data) {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-lg font-medium">Couldn't load your portfolio</h1>
        <p className="text-sm text-muted-foreground">
          The server did not respond. Refresh the page, and if it keeps failing check
          that the API is running.
        </p>
      </div>
    )
  }

  if (data.holdings.length === 0) {
    return (
      <div className="flex flex-col gap-8">
        <h1 className="text-2xl font-semibold tracking-tight">Portfolio</h1>
        <EmptyState />
      </div>
    )
  }

  return (
    /*
     * Dashboard order is by how often it is read, not by how the app is built.
     * What you own and how it is doing come first; the analyses that change
     * slowly sit below. The chart and the holdings share a row on wide screens
     * because they answer the same question — how is this going — and reading
     * one usually means glancing at the other.
     */
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Portfolio value
          </h1>
          <p className="num num-display text-4xl font-semibold leading-none sm:text-5xl">
            {formatInr(data.total_current_value)}
          </p>
          <p className={`tnum text-sm ${gainClass(data.total_unrealised_gain)}`}>
            {formatInrSigned(data.total_unrealised_gain)} (
            {formatPercent(data.absolute_return)}) unrealised
          </p>
        </div>
        <AddHoldingDialog />
      </header>

      <Panel>
        <MetricRow>
          <Metric label="Invested" value={formatInr(data.total_invested)} size="sm" />
          <Metric
            label="XIRR"
            value={formatPercent(data.xirr)}
            valueClassName={gainClass(data.xirr)}
            hint="Annualised and money-weighted, so it accounts for when you invested."
            size="sm"
          />
          <Metric
            label="Realised gain"
            value={formatInrSigned(data.total_realised_gain)}
            valueClassName={gainClass(data.total_realised_gain)}
            hint="Already booked by selling."
            size="sm"
          />
          <Metric label="Holdings" value={String(data.holdings.length)} size="sm" />
        </MetricRow>
      </Panel>

      <BenchmarkVerdict />

      {/* Two thirds to the chart: a trend needs horizontal room to be a trend,
          while the levers are a short ranked list that reads fine narrow. */}
      <div className="grid gap-6 xl:grid-cols-3">
        {history && (
          <Panel className="xl:col-span-2">
            <PortfolioChart
              points={history.points}
              excluded={history.excluded}
              excludedValue={history.excluded_value}
            />
          </Panel>
        )}
        <Levers />
      </div>

      {data.has_pricing_errors && (
        <p className="flex items-start gap-2 text-sm text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            <span className="tnum">{formatInr(data.unpriced_invested)}</span> could not
            be priced right now and is left out of the totals above, so the return
            figures stay honest rather than inventing a paper loss.
          </span>
        </p>
      )}

      <Panel
        title="Holdings"
        aside={`${data.holdings.length} ${data.holdings.length === 1 ? 'position' : 'positions'}`}
      >
        <div className="-mx-4 overflow-x-auto sm:mx-0">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Holding</TableHead>
                <TableHead className="text-right">Units</TableHead>
                <TableHead className="text-right">Invested</TableHead>
                <TableHead className="text-right">Value</TableHead>
                <TableHead className="text-right">Gain</TableHead>
                <TableHead className="text-right">XIRR</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.holdings.map((h) => (
                <HoldingRow key={h.holding_id} holding={h} />
              ))}
            </TableBody>
          </Table>
        </div>
      </Panel>

      {/* Below the fold on purpose: these change monthly at most, and putting
          them above the holdings pushed the table people actually read off the
          first screen. */}
      {/* Each of these renders nothing when it has nothing to say, and each
          owns its own surface — wrapping them here left empty bordered boxes on
          a portfolio with one holding, which reads as "something failed". */}
      <div className="grid items-start gap-6 xl:grid-cols-2">
        <CostReview />
        <FundOverlap />
      </div>

      <Announcements />
    </div>
  )
}
