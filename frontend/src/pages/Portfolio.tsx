import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Layers,
  Target,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { AddHoldingDialog } from '@/components/AddHoldingDialog'
import { Announcements } from '@/components/Announcements'
import { CostReview } from '@/components/CostReview'
import { FundOverlap } from '@/components/FundOverlap'
import { Levers } from '@/components/Levers'
import { PortfolioChart } from '@/components/PortfolioChart'
import { StartHere } from '@/components/StartHere'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import { Sparkline } from '@/components/charts'
import { Stat } from '@/components/ui/stat'
import { useCountUp } from '@/lib/count-up'
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
  const Arrow = ahead ? ArrowUpRight : ArrowDownRight

  return (
    <div
      className={`lift flex h-full flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border p-4 sm:px-5 ${
        ahead ? 'border-gain/25 bg-gain/[0.06]' : 'border-loss/25 bg-loss/[0.06]'
      }`}
    >
      <span
        className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${
          ahead ? 'bg-gain/15 text-gain' : 'bg-loss/15 text-loss'
        }`}
      >
        <Arrow className="size-5" aria-hidden />
      </span>
      <p className="flex-1 text-[15px]">
        <span className={`num text-lg font-semibold ${gainClass(gap)}`}>
          {Math.abs(gap * 100).toFixed(1)}pp
        </span>{' '}
        {ahead ? 'ahead of' : 'behind'} the Nifty 50, on the same money and the same
        dates.
      </p>
      <p className="tnum text-xs text-muted-foreground">
        {formatInr(data.portfolio_value)} vs {formatInr(data.benchmark_value)} &middot;
        XIRR {formatPercent(data.portfolio_xirr)} vs {formatPercent(data.benchmark_xirr)}
      </p>
    </div>
  )
}

function LoadingState() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-28 w-full rounded-2xl" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-56 w-full rounded-2xl" />
      <Skeleton className="h-72 w-full rounded-2xl" />
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

  const up = (data.total_unrealised_gain ?? 0) >= 0

  return (
    <div className="flex flex-col gap-6">
      {/* THE HERO. One number, at a size nothing else on the page competes
          with, on a tinted slab so it reads as the page's subject rather than
          the first row of a list. */}
      <header className="rise relative overflow-hidden rounded-2xl border bg-card p-6 sm:p-8">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.10]"
          style={{
            background:
              'radial-gradient(120% 140% at 0% 0%, var(--v-indigo) 0%, transparent 55%), radial-gradient(100% 120% at 100% 0%, var(--v-cyan) 0%, transparent 50%)',
          }}
          aria-hidden
        />
        <div className="relative flex flex-wrap items-start justify-between gap-6">
          <div className="flex flex-col gap-2">
            {/* An h1, not a styled <p>. The page had no first-level heading at
                all after the redesign, so a screen reader opened on an h2 and
                the accessibility walk said so — the label looks like a caption
                and is the page's title. */}
            <h1 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Portfolio value
            </h1>
            <HeroValue amount={data.total_current_value} />
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-sm font-medium ${
                  up ? 'bg-gain/12 text-gain' : 'bg-loss/12 text-loss'
                }`}
              >
                {up ? (
                  <ArrowUpRight className="size-3.5" aria-hidden />
                ) : (
                  <ArrowDownRight className="size-3.5" aria-hidden />
                )}
                <span className="num">{formatInrSigned(data.total_unrealised_gain)}</span>
                <span className="num opacity-75">
                  ({formatPercent(data.absolute_return)})
                </span>
              </span>
              <span className="text-sm text-muted-foreground">unrealised</span>
            </div>
          </div>

          {/* The shape of the number beside it, given the width it needs to
              read as a shape. At 180px in the top-right corner it was a
              squiggle in the margin, and the middle of a 1600px hero was
              empty — so the line now spans the gap and says what it spans. */}
          {history && history.points.length > 1 && (
            <div className="hidden flex-1 flex-col items-center gap-1 self-center px-6 lg:flex">
              <Sparkline
                values={history.points.map((h) => h.portfolio_value)}
                width={420}
                height={64}
                label="How your portfolio value has moved"
              />
              <p className="tnum text-xs text-muted-foreground">
                {monthOf(history.points[0].date)} &rarr;{' '}
                {monthOf(history.points[history.points.length - 1].date)}
              </p>
            </div>
          )}

          <div className="flex flex-col items-end gap-4">
            <AddHoldingDialog />
            {/* Below the laptop breakpoint the middle disappears, so the line
                comes back here at its old size rather than vanishing. */}
            {history && history.points.length > 1 && (
              <div className="lg:hidden">
                <Sparkline
                  values={history.points.map((h) => h.portfolio_value)}
                  width={180}
                  height={44}
                  label="How your portfolio value has moved"
                />
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Four cards, four colours. The row of hairline-separated figures this
          replaces was correct and unreadable: same size, same weight, same
          colour, so the eye had nowhere to land and read all four or none. */}
      <div className="rise rise-1 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Invested"
          tone="indigo"
          icon={<Wallet className="size-4" aria-hidden />}
          value={formatInr(data.total_invested)}
        />
        <Stat
          label="XIRR"
          tone="violet"
          icon={<TrendingUp className="size-4" aria-hidden />}
          value={formatPercent(data.xirr)}
          valueClassName={gainClass(data.xirr)}
          hint="Money-weighted, so when you invested counts."
        />
        <Stat
          label="Realised gain"
          tone="amber"
          icon={<Target className="size-4" aria-hidden />}
          value={formatInrSigned(data.total_realised_gain)}
          valueClassName={gainClass(data.total_realised_gain)}
          hint="Already booked by selling."
        />
        {/* The one card that goes somewhere. "How many" is the only figure up
            here that provokes "which ones?", and the answer is a whole page —
            so the card is the way through, instead of the bordered box further
            down that existed only to hold one link the nav already has. */}
        <Link
          to="/portfolio/holdings"
          className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <Stat
            label="Holdings"
            tone="cyan"
            icon={<Layers className="size-4" aria-hidden />}
            value={String(data.holdings.length)}
            hint="See every position &rarr;"
          />
        </Link>
      </div>

      {/* Actions before history. The chart says how it went; this says what to
          do, and a page that opens on a chart invites reading rather than
          acting. */}
      <div className="rise rise-2">
        <Levers />
      </div>

      {/* Two verdicts, side by side. They answer the same kind of question —
          "is anything wrong?" — in one line each, and both were previously
          stranded: the benchmark alone on a full-width row, the cost panel next
          to a much taller neighbour with a column of empty page under it. */}
      <div className="rise rise-3 grid gap-4 lg:grid-cols-2">
        <BenchmarkVerdict />
        <CostReview />
      </div>

      {history && (
        <div className="rise rise-4">
          {/* No Panel title: PortfolioChart prints its own heading, and two
              "Value over time" lines stacked reads as a rendering fault. */}
          <Panel>
            <PortfolioChart
              points={history.points}
              excluded={history.excluded}
              excludedValue={history.excluded_value}
            />
          </Panel>
        </div>
      )}

      {data.has_pricing_errors && (
        <p className="flex items-start gap-2 rounded-xl border border-v-amber/30 bg-v-amber-soft/60 p-4 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-v-amber" aria-hidden />
          <span>
            <span className="tnum font-medium">{formatInr(data.unpriced_invested)}</span>{' '}
            could not be priced right now and is left out of the totals above, so the
            return figures stay honest rather than inventing a paper loss.
          </span>
        </p>
      )}

      {/* No "go to Holdings" panel here. It was a bordered box containing one
          link to a destination already in the nav — a whole surface spent
          saying what the nav says for free. */}
      <div className="rise rise-5">
        <FundOverlap />
      </div>

      <Announcements />
    </div>
  )
}

/**
 * The portfolio value, counted up once on arrival.
 *
 * Its own component because a hook cannot sit behind the early returns above —
 * and it earns the ceremony: it is the first thing anybody looks at, and a
 * figure that lands reads as stored while one that counts reads as just worked
 * out, which is what it is.
 */
function HeroValue({ amount }: { amount: number | null | undefined }) {
  const shown = useCountUp(amount)
  return (
    <p className="num num-display text-[2.75rem] font-semibold leading-none sm:text-6xl">
      {formatInr(Math.round(shown))}
    </p>
  )
}

/** "Apr 24" from "2024-04-30" — the sparkline's span, not a full date. */
function monthOf(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
}
