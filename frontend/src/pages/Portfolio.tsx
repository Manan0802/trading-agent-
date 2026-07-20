import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AddHoldingDialog } from '@/components/AddHoldingDialog'
import { AddTransactionDialog } from '@/components/AddTransactionDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  fetchPortfolio,
  type HoldingSummary,
} from '@/lib/portfolio-api'

function Stat({
  label,
  value,
  hint,
  className,
}: {
  label: string
  value: string
  hint?: string
  className?: string
}) {
  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-0.5">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={`text-xl font-semibold tabular-nums ${className ?? ''}`}>
          {value}
        </span>
        {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
      </CardContent>
    </Card>
  )
}

function BenchmarkCard() {
  const { data, isLoading } = useQuery({
    queryKey: ['benchmark'],
    queryFn: fetchBenchmark,
  })

  if (isLoading) return <Skeleton className="h-24 w-full rounded-xl" />
  if (!data) return null

  if (!data.comparable) {
    return (
      <Card size="sm">
        <CardContent className="text-sm text-muted-foreground">
          {data.reason ?? 'Not enough history to compare against the index yet.'}
        </CardContent>
      </Card>
    )
  }

  const ahead = (data.outperformance ?? 0) >= 0

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-sm text-muted-foreground">
          If you had bought the Nifty 50 instead
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex gap-8">
          <div className="flex flex-col">
            <span className="text-xs text-muted-foreground">Your portfolio</span>
            <span className="text-lg font-semibold tabular-nums">
              {formatInr(data.portfolio_value)}
            </span>
            <span className="text-xs text-muted-foreground tabular-nums">
              XIRR {formatPercent(data.portfolio_xirr)}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs text-muted-foreground">Same money in the index</span>
            <span className="text-lg font-semibold tabular-nums text-muted-foreground">
              {formatInr(data.benchmark_value)}
            </span>
            <span className="text-xs text-muted-foreground tabular-nums">
              XIRR {formatPercent(data.benchmark_xirr)}
            </span>
          </div>
        </div>
        <Badge variant={ahead ? 'default' : 'destructive'}>
          {Math.abs((data.outperformance ?? 0) * 100).toFixed(1)}pp{' '}
          {ahead ? 'ahead' : 'behind'}
        </Badge>
      </CardContent>
    </Card>
  )
}

function HoldingRow({ holding }: { holding: HoldingSummary }) {
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: () => deleteHolding(holding.holding_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
      queryClient.invalidateQueries({ queryKey: ['benchmark'] })
    },
  })

  return (
    <TableRow>
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium">{holding.name}</span>
          <span className="text-xs text-muted-foreground">
            {holding.asset_type === 'MF' ? 'Fund' : 'Stock'} · {holding.identifier}
            {holding.category ? ` · ${holding.category}` : ''}
          </span>
          {holding.price_error && (
            <span className="text-xs text-amber-600 dark:text-amber-400">
              Live price unavailable — excluded from returns
            </span>
          )}
        </div>
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatUnits(holding.units_held)}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatInr(holding.invested)}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatInr(holding.current_value)}
      </TableCell>
      <TableCell className={`text-right tabular-nums ${gainClass(holding.unrealised_gain)}`}>
        <div className="flex flex-col items-end">
          <span>{formatInrSigned(holding.unrealised_gain)}</span>
          <span className="text-xs">{formatPercent(holding.absolute_return)}</span>
        </div>
      </TableCell>
      <TableCell className={`text-right tabular-nums ${gainClass(holding.xirr)}`}>
        {formatPercent(holding.xirr)}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end gap-1">
          <AddTransactionDialog holding={holding} />
          <Button
            variant="ghost"
            size="xs"
            disabled={remove.isPending}
            onClick={() => remove.mutate()}
          >
            Remove
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

export function Portfolio() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
  })

  if (isLoading) {
    return (
      <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-10">
        <Skeleton className="h-16 w-64" />
        <div className="grid gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <p className="text-destructive">Couldn't load your portfolio. Please refresh.</p>
      </div>
    )
  }

  const empty = data.holdings.length === 0

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">Portfolio value</span>
          <span className="text-4xl font-semibold tabular-nums">
            {formatInr(data.total_current_value)}
          </span>
          {!empty && (
            <span className={`text-sm tabular-nums ${gainClass(data.total_unrealised_gain)}`}>
              {formatInrSigned(data.total_unrealised_gain)} (
              {formatPercent(data.absolute_return)}) unrealised
            </span>
          )}
        </div>
        <AddHoldingDialog />
      </div>

      {empty ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
            <p className="font-medium">Nothing tracked yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Add a fund or stock you already own, then record the purchases. We'll
              fetch live prices and work out what it's actually earned you.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Invested" value={formatInr(data.total_invested)} />
            <Stat label="Current value" value={formatInr(data.total_current_value)} />
            <Stat
              label="Unrealised gain"
              value={formatInrSigned(data.total_unrealised_gain)}
              className={gainClass(data.total_unrealised_gain)}
              hint={
                data.total_realised_gain
                  ? `${formatInrSigned(data.total_realised_gain)} already booked`
                  : undefined
              }
            />
            <Stat
              label="XIRR"
              value={formatPercent(data.xirr)}
              className={gainClass(data.xirr)}
              hint="annualised, money-weighted"
            />
          </div>

          <BenchmarkCard />

          {data.has_pricing_errors && (
            <p className="text-sm text-amber-600 dark:text-amber-400">
              {formatInr(data.unpriced_invested)} could not be priced right now and is
              left out of the totals above, so the return figures stay honest.
            </p>
          )}

          <Card className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Holding</TableHead>
                  <TableHead className="text-right">Units</TableHead>
                  <TableHead className="text-right">Invested</TableHead>
                  <TableHead className="text-right">Value</TableHead>
                  <TableHead className="text-right">Gain</TableHead>
                  <TableHead className="text-right">XIRR</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.holdings.map((h) => (
                  <HoldingRow key={h.holding_id} holding={h} />
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}
    </div>
  )
}
