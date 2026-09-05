import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Trash2 } from 'lucide-react'
import { AddHoldingDialog } from '@/components/AddHoldingDialog'
import { AddTransactionDialog } from '@/components/AddTransactionDialog'
import { StartHere } from '@/components/StartHere'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow } from '@/components/ui/table'
import {
  formatInr,
  formatInrSigned,
  formatPercent,
  formatUnits,
  gainClass } from '@/lib/format'
import {
  PORTFOLIO_QUERY_KEYS,
  deleteHolding,
  fetchPortfolio,
  type HoldingSummary,
} from '@/lib/portfolio-api'


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
    } })

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
      {/* The live NAV or share price. It was fetched, used for every figure on
          the row, and never shown -- so there was no way to see today's number
          or tell how old it was. */}
      <TableCell className="num text-right">
        <span className="block">{formatInr(holding.current_price)}</span>
        {holding.price_as_of && (
          <span className="tnum block text-xs text-muted-foreground">
            {holding.price_as_of}
          </span>
        )}
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

/**
 * Every position, with units, cost and XIRR — the page you open to DO something.
 *
 * Split out of the single page that rendered the summary, the levers, the
 * chart, the cost review, the overlap AND this table on one screen. They answer
 * different questions at different moments: "how am I doing" is a glance, and
 * "what exactly do I hold" is a task — you are here to add a purchase, correct
 * a unit count, or check one fund's cost basis.
 *
 * `/portfolio` keeps the summary because `/` redirects there, so it is the app's
 * front door, and a front door should answer how things are going rather than
 * open onto a table. This lives one level down, which is where a deliberate
 * destination belongs.
 */
export function Holdings() {
  // The same key and the same fetch as Portfolio, so the two pages share one cached
  // response and moving between them costs no request.
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
  })

  if (isLoading) return <LoadingState />
  if (isError || !data) {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-lg font-medium">Couldn&rsquo;t load your holdings</h1>
        <p className="text-sm text-muted-foreground">
          The server did not respond. Refresh the page, and if it keeps failing
          check that the API is running.
        </p>
      </div>
    )
  }
  if (data.holdings.length === 0) return <EmptyState />

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="font-heading text-3xl font-semibold leading-[1.1] tracking-[-0.02em] sm:text-4xl">
            Holdings
          </h1>
          <p className="text-sm text-muted-foreground">
            {data.holdings.length}{' '}
            {data.holdings.length === 1 ? 'position' : 'positions'}, worth{' '}
            {formatInr(data.total_current_value)}
          </p>
        </div>
        <AddHoldingDialog />
      </header>

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
                <TableHead className="text-right">Price</TableHead>
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
    </div>
  )
}
