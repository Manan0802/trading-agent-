import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { AddHoldingDialog } from '@/components/AddHoldingDialog'
import { Announcements } from '@/components/Announcements'
import { CostReview } from '@/components/CostReview'
import { FundOverlap } from '@/components/FundOverlap'
import { Levers } from '@/components/Levers'
import { PortfolioChart } from '@/components/PortfolioChart'
import { StartHere } from '@/components/StartHere'
import { Metric, MetricRow } from '@/components/ui/metric'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import {
  formatInr,
  formatInrSigned,
  formatPercent,
  gainClass } from '@/lib/format'
import {
  fetchBenchmark,
  fetchHistory,
  fetchPortfolio,
} from '@/lib/portfolio-api'

function BenchmarkVerdict() {
  const { data, isLoading } = useQuery({
    queryKey: ['benchmark'],
    queryFn: fetchBenchmark })

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

export function Today() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio })
  const { data: history } = useQuery({
    queryKey: ['history'],
    queryFn: fetchHistory,
    enabled: !!data && data.holdings.length > 0 })

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
        <h1 className="font-heading text-3xl font-semibold leading-[1.1] tracking-[-0.02em] sm:text-4xl">Portfolio</h1>
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

      {/* Actions first. The chart says how it has gone; this says what to do,
          and a page that opens with a chart invites reading rather than acting. */}
      <Levers />

      <BenchmarkVerdict />

      {history && (
        <Panel>
          <PortfolioChart
            points={history.points}
            excluded={history.excluded}
            excludedValue={history.excluded_value}
          />
        </Panel>
      )}

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

      {/* The list lives on its own page now. Today answers "how am I doing";
          the table answers "what exactly do I hold", and they are different
          questions asked at different moments. The link is here rather than
          only in the nav because this is where somebody wonders. */}
      <Panel
        title="Holdings"
        aside={`${data.holdings.length} ${data.holdings.length === 1 ? 'position' : 'positions'}`}
      >
        <Link
          to="/portfolio/holdings"
          className="inline-flex min-h-11 items-center text-sm underline underline-offset-4"
        >
          See every holding, with units, cost and XIRR
        </Link>
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
