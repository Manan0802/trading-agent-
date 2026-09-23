import { Fragment, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronsUpDown,
  Trash2,
} from 'lucide-react'
import { AddHoldingDialog } from '@/components/AddHoldingDialog'
import { AddTransactionDialog } from '@/components/AddTransactionDialog'
import { AllocationBreakdown } from '@/components/AllocationBreakdown'
import { StartHere } from '@/components/StartHere'
import { useTrailLeaf } from '@/components/Trail'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow } from '@/components/ui/table'
import {
  formatInr,
  formatInrSigned,
  formatNav,
  formatPercent,
  formatUnits,
  gainClass } from '@/lib/format'
import {
  PORTFOLIO_QUERY_KEYS,
  deleteHolding,
  fetchHolding,
  fetchPortfolio,
  type HoldingSummary,
} from '@/lib/portfolio-api'
import { cn } from '@/lib/utils'

type SortKey = 'name' | 'invested' | 'value' | 'gain' | 'xirr'
type Sort = { key: SortKey; dir: 'asc' | 'desc' }
type Kind = 'all' | 'MF' | 'STOCK'

/** Columns in the table, so the footer and the detail row span the same width. */
const COLUMNS = 6

/** Transactions shown before "show all". A SIP is a row a month. */
const RECENT_TXNS = 6

/**
 * Holdings shown before "show all". Sorted by value, the first five are
 * usually most of the money. Everything is still one click away, and the
 * totals row always covers every holding, shown or not.
 */
const FIRST_ROWS = 5

/**
 * "Parag Parikh Flexi Cap Fund" out of "Parag Parikh Flexi Cap Fund - Direct
 * Plan - Growth". Every row repeated its plan and option in full, which is the
 * part of the name that is the same on nine rows out of eleven.
 */
function shortName(name: string): string {
  return name.split(' - ')[0].trim()
}

/**
 * Only Regular is worth a label. It is the exception, and it is the one that
 * costs money: part of every year's return goes to a distributor. Labelling
 * Direct as well would put the same word on most rows and hide the one that
 * matters among them.
 */
function isRegular(h: HoldingSummary): boolean {
  return h.asset_type === 'MF' && /\bregular\b/i.test(h.name)
}

/** "18 Sep" — a price date, not a timestamp. */
function shortDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: undefined })
}

function longDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

/**
 * The date most holdings of one kind are priced at. Said once above the table
 * instead of under every price: fourteen identical dates in a column read as
 * fourteen things to check, and the one that differs gets lost among them.
 */
function commonDate(holdings: HoldingSummary[], kind: 'MF' | 'STOCK'): string | null {
  const counts = new Map<string, number>()
  for (const h of holdings) {
    if (h.asset_type === kind && h.price_as_of) {
      counts.set(h.price_as_of, (counts.get(h.price_as_of) ?? 0) + 1)
    }
  }
  let best: string | null = null
  let most = 0
  for (const [date, n] of counts) {
    if (n > most) {
      best = date
      most = n
    }
  }
  return best
}

function sortValue(h: HoldingSummary, key: SortKey): number | string | null {
  switch (key) {
    case 'name':
      return shortName(h.name).toLowerCase()
    case 'invested':
      return h.invested
    case 'value':
      return h.current_value
    case 'gain':
      return h.unrealised_gain
    case 'xirr':
      return h.xirr
  }
}

function sorted(holdings: HoldingSummary[], sort: Sort): HoldingSummary[] {
  const sign = sort.dir === 'asc' ? 1 : -1
  return [...holdings].sort((a, b) => {
    const x = sortValue(a, sort.key)
    const y = sortValue(b, sort.key)
    // Unpriced holdings sort last in either direction. At the top of a
    // descending sort, a dash would claim to be the largest thing you own.
    if (x === null) return y === null ? 0 : 1
    if (y === null) return -1
    return x < y ? -sign : x > y ? sign : 0
  })
}

/* ------------------------------------------------------------------ header */

function SortHead({
  label,
  k,
  sort,
  onSort,
  align = 'right',
}: {
  label: string
  k: SortKey
  sort: Sort
  onSort: (k: SortKey) => void
  align?: 'left' | 'right'
}) {
  const active = sort.key === k
  const Icon = !active ? ChevronsUpDown : sort.dir === 'asc' ? ArrowUp : ArrowDown
  return (
    <TableHead
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={align === 'right' ? 'text-right' : undefined}
    >
      <button
        type="button"
        onClick={() => onSort(k)}
        className={cn(
          'inline-flex min-h-9 items-center gap-1 rounded-md px-1 -mx-1 transition-colors hover:text-foreground',
          active ? 'text-foreground' : 'text-muted-foreground',
        )}
      >
        {label}
        <Icon className={cn('size-3.5', !active && 'opacity-50')} aria-hidden />
      </button>
    </TableHead>
  )
}

/* --------------------------------------------------------------------- row */

function HoldingRow({
  holding,
  weight,
  bar,
  open,
  onToggle,
}: {
  holding: HoldingSummary
  weight: number | null
  /** Share of the largest holding, 0-1, for the bar. */
  bar: number
  open: boolean
  onToggle: () => void
}) {
  const detailId = `holding-${holding.holding_id}`
  return (
    <TableRow className={cn('group', open && 'bg-muted/40 hover:bg-muted/40')}>
      <TableCell className="max-w-[26rem] py-2.5">
        {/* The whole name is the control. A row you click to expand is a
            <tr> with a handler, which a keyboard cannot reach; a button
            inside the first cell can. */}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls={detailId}
          className="flex min-h-11 w-full items-start gap-2 rounded-md text-left"
        >
          <ChevronDown
            className={cn(
              'mt-1 size-4 shrink-0 text-muted-foreground transition-transform duration-200',
              open && 'rotate-180 text-foreground',
            )}
            aria-hidden
          />
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className="truncate font-medium leading-tight" title={holding.name}>
                {shortName(holding.name)}
              </span>
              {isRegular(holding) && (
                <span className="rounded-full border border-v-amber/40 bg-v-amber-soft px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-v-amber-ink">
                  Regular
                </span>
              )}
            </span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              {holding.asset_type === 'MF' ? 'Fund' : 'Stock'}
              {holding.asset_type === 'MF'
                ? holding.category
                  ? ` · ${holding.category}`
                  : ''
                : ` · ${holding.identifier}`}
            </span>
          </span>
        </button>

        {/* The three honesty states stay on the row, not in the detail. Each
            one means every figure on this line is wrong or out of date, and a
            warning you have to expand a row to find is one nobody reads. */}
        {holding.misnamed_as && (
          <p className="mt-1 ml-6 flex items-start gap-1 text-xs font-medium">
            <AlertTriangle className="mt-0.5 size-3 shrink-0 text-v-amber" aria-hidden />
            <span>
              Code <span className="tnum">{holding.identifier}</span> is{' '}
              <strong>{holding.misnamed_as}</strong>. Every figure here is for that
              fund, not the name above &mdash; fix the name or the code.
            </span>
          </p>
        )}
        {holding.stale_days !== null && (
          <p className="mt-1 ml-6 flex items-start gap-1 text-xs font-medium">
            <AlertTriangle className="mt-0.5 size-3 shrink-0 text-v-amber" aria-hidden />
            <span>
              Priced from{' '}
              <span className="tnum">{holding.price_as_of}</span>,{' '}
              <span className="tnum">{holding.stale_days}</span> days behind your other{' '}
              {holding.asset_type === 'MF' ? 'funds' : 'stocks'}. This value is not current.
            </span>
          </p>
        )}
        {holding.price_error && (
          <p className="mt-1 ml-6 flex items-center gap-1 text-xs text-muted-foreground">
            <AlertTriangle className="size-3 shrink-0" aria-hidden />
            Live price unavailable, so this is left out of the returns
          </p>
        )}
      </TableCell>

      {/* Weight: what share of your money this is. The column a holdings page
          most needs and did not have — the only way to see it was to divide
          one column by a total printed somewhere else. */}
      <TableCell className="w-36 text-right">
        <span className="num block text-sm">
          {weight === null ? '—' : `${(weight * 100).toFixed(1)}%`}
        </span>
        <span className="mt-1 ml-auto block h-1 w-20 overflow-hidden rounded-full bg-muted">
          <span
            className="block h-full rounded-full bg-v-cyan"
            style={{ width: `${Math.round(Math.max(0, Math.min(1, bar)) * 100)}%` }}
          />
        </span>
      </TableCell>
      <TableCell className="num text-right text-muted-foreground">
        {formatInr(holding.invested)}
      </TableCell>
      <TableCell className="num text-right font-medium">
        {formatInr(holding.current_value)}
      </TableCell>
      <TableCell className={cn('num text-right', gainClass(holding.unrealised_gain))}>
        <span className="block">{formatInrSigned(holding.unrealised_gain)}</span>
        <span className="block text-xs opacity-80">{formatPercent(holding.absolute_return)}</span>
      </TableCell>
      <TableCell className={cn('num text-right font-medium', gainClass(holding.xirr))}>
        {formatPercent(holding.xirr)}
      </TableCell>
    </TableRow>
  )
}

/* ------------------------------------------------------------------ detail */

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="num text-sm">{children}</span>
    </div>
  )
}

/**
 * Everything about one holding: the per-unit facts, what you actually did,
 * and the two things you can do about it.
 *
 * The transaction history existed in the API from the start —
 * `GET /holdings/{id}` returns it — and no screen showed it. You could add a
 * purchase to a holding and never see the fifty-six already on it.
 */
function HoldingDetail({ holding }: { holding: HoldingSummary }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['holding', holding.holding_id],
    queryFn: () => fetchHolding(holding.holding_id),
  })
  const [all, setAll] = useState(false)

  const txns = useMemo(
    () => [...(data?.transactions ?? [])].sort((a, b) => b.txn_date.localeCompare(a.txn_date)),
    [data],
  )
  const shown = all ? txns : txns.slice(0, RECENT_TXNS)
  const first = txns.length > 0 ? txns[txns.length - 1].txn_date : null
  const avgCost = holding.units_held > 0 ? holding.invested / holding.units_held : null

  return (
    <div className="flex flex-col gap-5 px-2 py-4 sm:px-6">
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
        <Fact label="Units held">{formatUnits(holding.units_held)}</Fact>
        <Fact label={holding.asset_type === 'MF' ? 'NAV' : 'Price'}>
          {formatNav(holding.current_price)}
          {holding.price_as_of && (
            <span className="ml-1 text-xs text-muted-foreground">{shortDate(holding.price_as_of)}</span>
          )}
        </Fact>
        <Fact label="Avg cost">{formatNav(avgCost)}</Fact>
        <Fact label="Realised">
          <span className={gainClass(holding.realised_gain)}>
            {formatInrSigned(holding.realised_gain)}
          </span>
        </Fact>
        <Fact label="First bought">{first ? longDate(first) : '—'}</Fact>
        <Fact label={holding.asset_type === 'MF' ? 'Scheme code' : 'Ticker'}>
          {holding.identifier}
        </Fact>
      </div>

      {/* The two notes this row can need, and only when it needs them. */}
      {(holding.realised_gain !== 0 || isRegular(holding)) && (
        <div className="flex flex-col gap-1.5 text-sm text-muted-foreground">
          {holding.realised_gain !== 0 && (
            <p>
              XIRR counts the <span className="num text-foreground">{formatInr(holding.realised_gain)}</span>{' '}
              already booked by selling. Unrealised covers only the units you still
              hold &mdash; which is why the two can point in different directions.
            </p>
          )}
          {isRegular(holding) && (
            <p>
              A <span className="font-medium text-v-amber-ink">regular plan</span>: part of
              every year&rsquo;s return goes to a distributor. The Portfolio page
              prices it and names the direct plan to buy instead.
            </p>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Transactions{txns.length > 0 && <span className="num ml-1">({txns.length})</span>}
        </p>
        {isLoading && <Skeleton className="h-24 w-full" />}
        {isError && (
          <p className="text-sm text-muted-foreground">
            Could not load the transactions for this holding.
          </p>
        )}
        {data && txns.length === 0 && (
          <p className="text-sm text-muted-foreground">No transactions recorded yet.</p>
        )}
        {txns.length > 0 && (
          <div className="overflow-x-auto rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-xs text-muted-foreground">
                  <th className="px-3 py-2 text-left font-medium">Date</th>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-right font-medium">Units</th>
                  <th className="px-3 py-2 text-right font-medium">Price</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((t) => (
                  <tr key={t.id} className="border-b last:border-0">
                    <td className="tnum px-3 py-1.5">{longDate(t.txn_date)}</td>
                    <td className="px-3 py-1.5">
                      <span
                        className={cn(
                          'rounded px-1.5 py-px text-[11px] font-semibold',
                          t.txn_type === 'BUY'
                            ? 'bg-v-cyan-soft text-v-cyan-ink'
                            : 'bg-v-amber-soft text-v-amber-ink',
                        )}
                      >
                        {t.txn_type === 'BUY' ? 'Buy' : 'Sell'}
                      </span>
                    </td>
                    <td className="num px-3 py-1.5 text-right">{formatUnits(t.units)}</td>
                    <td className="num px-3 py-1.5 text-right">{formatNav(t.price)}</td>
                    <td className="num px-3 py-1.5 text-right">{formatInr(t.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {txns.length > RECENT_TXNS && (
          <Button variant="ghost" size="sm" className="w-fit" onClick={() => setAll((v) => !v)}>
            {all ? 'Show recent only' : `Show all ${txns.length}`}
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t pt-4">
        <AddTransactionDialog holding={holding} />
        <RemoveHolding holding={holding} count={data ? txns.length : null} />
      </div>
    </div>
  )
}

/**
 * Delete, in two steps.
 *
 * It used to be one click on a bin icon sitting beside "Add txn", which
 * permanently removed the holding and every transaction on it with nothing
 * asked. The second step names what goes, how many transactions go with it,
 * and that there is no undo — and defaults focus to keeping it.
 */
function RemoveHolding({ holding, count }: { holding: HoldingSummary; count: number | null }) {
  const [confirming, setConfirming] = useState(false)
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

  if (!confirming) {
    return (
      <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
        <Trash2 aria-hidden />
        Remove holding
      </Button>
    )
  }

  return (
    <div
      role="group"
      aria-label="Confirm removal"
      className="flex flex-wrap items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm"
    >
      <span>
        Remove <strong>{shortName(holding.name)}</strong>
        {count !== null && (
          <>
            {' '}and its <span className="num">{count}</span>{' '}
            {count === 1 ? 'transaction' : 'transactions'}
          </>
        )}
        ? This cannot be undone.
      </span>
      <Button variant="outline" size="sm" autoFocus onClick={() => setConfirming(false)}>
        Keep it
      </Button>
      <Button
        variant="destructive"
        size="sm"
        disabled={remove.isPending}
        onClick={() => remove.mutate()}
      >
        {remove.isPending ? 'Removing…' : 'Remove'}
      </Button>
    </div>
  )
}

/* -------------------------------------------------------------------- page */

function LoadingState() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-16 w-72" />
      <Skeleton className="h-10 w-80" />
      <Skeleton className="h-96 w-full" />
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
 *
 * The table is sortable and each row opens onto its own transactions. Per-row
 * actions moved into that detail: a bin icon on every row, one click from
 * deleting a holding, was the most dangerous control in the app and sat next
 * to the most common one.
 */
export function Holdings() {
  // The same key and the same fetch as Portfolio, so the two pages share one cached
  // response and moving between them costs no request.
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
  })
  useTrailLeaf('Holdings')

  const [sort, setSort] = useState<Sort>({ key: 'value', dir: 'desc' })
  const [kind, setKind] = useState<Kind>('all')
  const [open, setOpen] = useState<string | null>(null)
  const [everything, setEverything] = useState(false)

  const onSort = (key: SortKey) =>
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
        : // Names read A to Z; every figure reads largest first.
          { key, dir: key === 'name' ? 'asc' : 'desc' },
    )

  const holdings = useMemo(() => data?.holdings ?? [], [data])
  const rows = useMemo(
    () => sorted(kind === 'all' ? holdings : holdings.filter((h) => h.asset_type === kind), sort),
    [holdings, kind, sort],
  )

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

  const total = data.total_current_value
  const weightOf = (h: HoldingSummary) =>
    h.current_value !== null && total > 0 ? h.current_value / total : null
  // Bars are scaled to the largest holding, not to 100%. No single position is
  // a large share of a spread portfolio, so against 100% every bar is a sliver
  // and a column of slivers cannot be compared by eye. The percentage beside
  // each bar is the real share.
  const largest = Math.max(0, ...holdings.map((h) => weightOf(h) ?? 0)) || 1

  const funds = holdings.filter((h) => h.asset_type === 'MF').length
  const stocks = holdings.length - funds
  const fundDate = commonDate(holdings, 'MF')
  const stockDate = commonDate(holdings, 'STOCK')

  const sum = (pick: (h: HoldingSummary) => number | null) =>
    rows.reduce((acc, h) => acc + (pick(h) ?? 0), 0)
  const shownWeight = sum(weightOf)

  return (
    <div className="flex flex-col gap-6">
      <header className="rise flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <h1 className="font-heading text-3xl font-semibold leading-[1.1] tracking-[-0.02em] sm:text-4xl">
            Holdings
          </h1>
          <p className="text-sm text-muted-foreground">
            <span className="num">{data.holdings.length}</span>{' '}
            {data.holdings.length === 1 ? 'position' : 'positions'}, worth{' '}
            <span className="num font-medium text-foreground">
              {formatInr(data.total_current_value)}
            </span>
            <span className={cn('num ml-2', gainClass(data.total_unrealised_gain))}>
              {formatInrSigned(data.total_unrealised_gain)}
            </span>{' '}
            unrealised
          </p>
          {(fundDate || stockDate) && (
            <p className="text-xs text-muted-foreground">
              {fundDate && <>Fund NAVs as of {shortDate(fundDate)}</>}
              {fundDate && stockDate && ' · '}
              {stockDate && <>stock prices as of {shortDate(stockDate)}</>}
            </p>
          )}
        </div>
        <AddHoldingDialog />
      </header>

      <div className="rise rise-1">
        <AllocationBreakdown holdings={holdings} />
      </div>

      {/* Filters only when there is something to filter between. */}
      {funds > 0 && stocks > 0 && (
        <div className="rise rise-2 flex flex-wrap gap-2" role="group" aria-label="Show">
          {(
            [
              ['all', 'All', holdings.length],
              ['MF', 'Funds', funds],
              ['STOCK', 'Stocks', stocks],
            ] as const
          ).map(([value, label, n]) => (
            <button
              key={value}
              type="button"
              aria-pressed={kind === value}
              onClick={() => setKind(value)}
              className={cn(
                'inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3.5 text-sm transition-colors',
                kind === value
                  ? 'border-foreground/20 bg-foreground text-background'
                  : 'bg-card text-muted-foreground hover:text-foreground',
              )}
            >
              {label}
              <span className="num text-xs opacity-70">{n}</span>
            </button>
          ))}
        </div>
      )}

      <div className="rise rise-3">
        {/* No Panel title. The page heading is two lines up and says the same
            word; so did "14 positions", printed twice. */}
        <Panel>
          <div className="-mx-4 overflow-x-auto sm:mx-0">
            <Table className="min-w-[46rem]">
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <SortHead label="Holding" k="name" sort={sort} onSort={onSort} align="left" />
                  <TableHead className="text-right">Weight</TableHead>
                  <SortHead label="Invested" k="invested" sort={sort} onSort={onSort} />
                  <SortHead label="Value" k="value" sort={sort} onSort={onSort} />
                  <SortHead label="Unrealised" k="gain" sort={sort} onSort={onSort} />
                  <SortHead label="XIRR" k="xirr" sort={sort} onSort={onSort} />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(everything ? rows : rows.slice(0, FIRST_ROWS)).map((h) => {
                  const w = weightOf(h)
                  const isOpen = open === h.holding_id
                  return (
                    <Fragment key={h.holding_id}>
                      <HoldingRow
                        holding={h}
                        weight={w}
                        bar={w === null ? 0 : w / largest}
                        open={isOpen}
                        onToggle={() => setOpen(isOpen ? null : h.holding_id)}
                      />
                      {isOpen && (
                        <TableRow
                          id={`holding-${h.holding_id}`}
                          className="bg-muted/40 hover:bg-muted/40"
                        >
                          <TableCell colSpan={COLUMNS} className="p-0 whitespace-normal">
                            <HoldingDetail holding={h} />
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  )
                })}
              </TableBody>
              <TableFooter>
                <TableRow className="hover:bg-transparent">
                  <TableCell className="font-medium">
                    {kind === 'all' ? 'Total' : kind === 'MF' ? 'All funds' : 'All stocks'}
                    <span className="num ml-2 text-xs font-normal text-muted-foreground">
                      {rows.length}
                    </span>
                  </TableCell>
                  <TableCell className="num text-right">
                    {(shownWeight * 100).toFixed(1)}%
                  </TableCell>
                  <TableCell className="num text-right text-muted-foreground">
                    {formatInr(sum((h) => h.invested))}
                  </TableCell>
                  <TableCell className="num text-right font-semibold">
                    {formatInr(sum((h) => h.current_value))}
                  </TableCell>
                  <TableCell className={cn('num text-right', gainClass(sum((h) => h.unrealised_gain)))}>
                    {formatInrSigned(sum((h) => h.unrealised_gain))}
                  </TableCell>
                  {/* XIRR is money-weighted over dated cash flows, so it cannot
                      be summed or averaged from the rows above. The portfolio's
                      own figure is exact; a subset's would be invented. */}
                  <TableCell className={cn('num text-right font-semibold', gainClass(data.xirr))}>
                    {kind === 'all' ? formatPercent(data.xirr) : ''}
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </div>
          {rows.length > FIRST_ROWS && (
            <Button
              variant="outline"
              className="w-full sm:w-fit sm:self-center"
              aria-expanded={everything}
              onClick={() => setEverything((v) => !v)}
            >
              <ChevronDown
                className={cn('transition-transform duration-200', everything && 'rotate-180')}
                aria-hidden
              />
              {everything
                ? `Show top ${FIRST_ROWS} only`
                : `Show all ${rows.length} holdings`}
            </Button>
          )}
        </Panel>
      </div>
    </div>
  )
}
