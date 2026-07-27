import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Trash2 } from 'lucide-react'
import { AddHoldingDialog } from '@/components/AddHoldingDialog'
import { AddTransactionDialog } from '@/components/AddTransactionDialog'
import { CostReview } from '@/components/CostReview'
import { Levers } from '@/components/Levers'
import { PortfolioChart } from '@/components/PortfolioChart'
import { Button } from '@/components/ui/button'
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
import {
  formatInr,
  formatInrSigned,
  formatPercent,
  formatUnits,
  gainClass,
} from '@/lib/format'
import {
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
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
      queryClient.invalidateQueries({ queryKey: ['benchmark'] })
      queryClient.invalidateQueries({ queryKey: ['history'] })
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

function EmptyState() {
  return (
    <div className="flex flex-col items-start gap-3 border-t pt-10">
      <h2 className="text-lg font-medium">Nothing tracked yet</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        Add a fund or stock you already own, then record what you actually paid and
        when. NexTrade fetches live prices and works out your real return, including
        the money-weighted XIRR that a simple percentage hides.
      </p>
      <div className="pt-1">
        <AddHoldingDialog />
      </div>
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
    <div className="flex flex-col gap-10">
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

      <BenchmarkVerdict />

      <Levers />

      <CostReview />

      {history && <PortfolioChart points={history} />}

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

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium">Holdings</h2>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
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
      </section>
    </div>
  )
}
