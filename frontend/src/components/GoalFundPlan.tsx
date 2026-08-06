import { useQuery } from '@tanstack/react-query'
import { Panel } from '@/components/ui/panel'
import { useState } from 'react'
import { AlertTriangle, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr, formatPercent, plainProse } from '@/lib/format'

type Verdict = {
  headline: string
  points: string[]
  caveat: string | null
}

type FundRecommendation = {
  asset_class: string
  rank: number
  scheme_code: string
  scheme_name: string
  category: string
  monthly_amount: number
  score: number
  direct_ter: number | null
  regular_ter: number | null
  verdict: Verdict
}

type Reallocation = {
  asset_class: string
  amount: number
  moved_to: Record<string, number>
  note: string
}

type GoalRecommendations = {
  goal_id: string
  monthly_sip: number
  allocation: Record<string, number>
  recommendations: FundRecommendation[]
  skipped: { asset_class: string; reason: string }[]
  annual_commission_avoided: number | null
  // Where the plan left the target mix to stay buyable, and what is actually
  // being bought. The two differ whenever a sleeve was too small to place.
  reallocations: Reallocation[]
  actual_mix: Record<string, number>
}

const ASSET_LABEL: Record<string, string> = {
  equity: 'Equity',
  debt: 'Debt',
  gold: 'Gold',
}

function SectionHeading({ children }: { children?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h2 className="text-sm font-medium">What to actually buy</h2>
      {children}
    </div>
  )
}

function FundEntry({ fund }: { fund: FundRecommendation }) {
  const [open, setOpen] = useState(false)

  return (
    <li className="py-3">
      {/* Collapsed by default. Six funds each carrying the same four sentences
          made a 6,000-pixel page where the numbers you came for -- what to buy
          and how much -- were buried in prose that repeated verbatim. The
          reasoning is still one click away, per fund, for anyone who wants it. */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-start gap-4 text-left"
      >
        <ChevronRight
          aria-hidden
          className={`mt-1 size-4 shrink-0 text-muted-foreground transition-transform ${
            open ? 'rotate-90' : ''
          }`}
        />
        <div className="grid min-w-0 flex-1 gap-x-6 gap-y-1 sm:grid-cols-[minmax(0,1fr)_auto_auto_auto]">
          <div className="min-w-0">
            <p className="truncate font-medium leading-tight">{fund.scheme_name}</p>
            <p className="text-xs text-muted-foreground">
              Ranked <span className="tnum">{fund.rank}</span> in{' '}
              {fund.category.split(' - ').slice(1).join(' - ') || fund.category}
            </p>
          </div>
          <Stat label="Score" value={fund.score.toFixed(0)} />
          {/* Cost, not past return: it is the one input measured to predict,
              and it is why this fund is on the list at all. */}
          {/* formatPercent, not toFixed: every TER crossing this API is a
              fraction (0.0067), and that helper exists precisely to do the
              x100. Writing the conversion by hand printed 0.01% for a fund
              that costs 0.67% -- the same percent-against-fraction mistake
              this codebase has made twice before. */}
          <Stat
            label="Cost / yr"
            value={
              fund.direct_ter != null
                ? formatPercent(fund.direct_ter, { signed: false })
                : '—'
            }
          />
          <div className="flex flex-col items-start sm:items-end">
            <span className="num text-lg font-medium leading-none">
              {formatInr(fund.monthly_amount)}
            </span>
            <span className="mt-1 text-xs text-muted-foreground">per month</span>
          </div>
        </div>
      </button>

      {open && (
        <div className="mt-3 ml-8 flex flex-col gap-2">
          <p className="max-w-4xl text-sm leading-relaxed">
            {plainProse(fund.verdict.headline)}
          </p>
          <ul className="grid gap-x-10 gap-y-2 xl:grid-cols-2">
            {fund.verdict.points.map((point) => (
              <li key={point} className="flex gap-2 text-sm text-muted-foreground">
                <span aria-hidden className="text-muted-foreground/50">
                  &middot;
                </span>
                <span>{plainProse(point)}</span>
              </li>
            ))}
          </ul>
          {fund.verdict.caveat && (
            <p className="flex max-w-4xl items-start gap-2 text-sm text-muted-foreground">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>{plainProse(fund.verdict.caveat)}</span>
            </p>
          )}
        </div>
      )}
    </li>
  )
}

function Stat({
  label,
  value,
  className = '',
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className="flex flex-col sm:items-end">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`num text-sm ${className}`}>{value}</span>
    </div>
  )
}

export function GoalFundPlan({ goalId }: { goalId: string }) {
  const { data, isLoading, isError, error } = useQuery<GoalRecommendations>({
    queryKey: ['goal-recommendations', goalId],
    queryFn: async () =>
      (await api.get(`/api/v1/goals/${goalId}/recommendations`)).data,
    retry: false,
  })

  if (isLoading) {
    return (
      <section className="flex flex-col gap-4">
        <SectionHeading>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Pulling NAV history for the whole shortlist. This takes a moment the first
            time.
          </p>
        </SectionHeading>
        <div className="flex flex-col gap-4 border-y py-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      </section>
    )
  }

  if (isError) {
    const detail = (error as any)?.response?.data?.detail
    return (
      <section className="flex flex-col gap-4">
        <SectionHeading />
        <p className="flex max-w-3xl items-start gap-2 text-sm text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {plainProse(
              detail ??
                'Fund data is not available right now, so we cannot name specific schemes. Refresh the page to try again; the allocation above still stands.',
            )}
          </span>
        </p>
      </section>
    )
  }

  if (!data || data.recommendations.length === 0) {
    return (
      <section className="flex flex-col gap-4">
        <SectionHeading />
        <p className="max-w-3xl text-sm text-muted-foreground">
          No fund passed our screen for this allocation yet. The split above is still
          what to aim for, so any low-cost Direct Growth fund in each asset class will
          do the job until we can name one.
        </p>
      </section>
    )
  }

  const byClass = data.recommendations.reduce<Record<string, FundRecommendation[]>>(
    (acc, fund) => {
      ;(acc[fund.asset_class] ??= []).push(fund)
      return acc
    },
    {},
  )

  return (
    <Panel>
      <SectionHeading>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Direct Growth plans only. A regular plan of the same fund carries a
          distributor commission inside the NAV, so you end up with less for an
          otherwise identical portfolio. Buy these yourself on your broker.
          {data.annual_commission_avoided !== null && (
            <>
              {' '}
              On this plan that is worth{' '}
              <span className="tnum font-medium text-foreground">
                {formatInr(data.annual_commission_avoided)}
              </span>{' '}
              a year at today&rsquo;s balance, and more as it grows.
            </>
          )}
        </p>
      </SectionHeading>

      {Object.entries(byClass).map(([assetClass, funds]) => (
        <div key={assetClass} className="flex flex-col">
          <div className="flex items-baseline justify-between gap-4 border-b pb-2">
            <h3 className="text-sm font-medium">
              {ASSET_LABEL[assetClass] ?? assetClass}
            </h3>
            {/* The share actually being bought, not the target. Showing the
                target beside the real rupee figure made the two contradict
                each other whenever a sleeve had to be dropped: "65% ·
                ₹4,333/mo" out of a ₹6,000 SIP is not 65% of anything. */}
            <span className="num text-xs text-muted-foreground">
              {(data.actual_mix[assetClass] ?? data.allocation[assetClass]).toFixed(0)}%
              {data.actual_mix[assetClass] !== undefined &&
                Math.abs(data.actual_mix[assetClass] - data.allocation[assetClass]) >=
                  1 && (
                  <span className="text-muted-foreground/70">
                    {' '}
                    (target {data.allocation[assetClass]}%)
                  </span>
                )}{' '}
              &middot;{' '}
              {formatInr(funds.reduce((sum, f) => sum + f.monthly_amount, 0))}/mo
            </span>
          </div>
          <ul className="divide-y">
            {funds.map((fund) => (
              <FundEntry key={fund.scheme_code} fund={fund} />
            ))}
          </ul>
        </div>
      ))}

      <div className="flex flex-col gap-2 border-t pt-4">
        {/* Money that could not be placed where the allocation wanted it is
            named, along with where it went. Silently dropping it would leave
            the user investing less than their own SIP. */}
        {data.reallocations.map((r) => (
          <p key={r.asset_class} className="max-w-3xl text-sm text-muted-foreground">
            <span className="font-medium">
              {ASSET_LABEL[r.asset_class] ?? r.asset_class}
            </span>{' '}
            is not bought:{' '}
            <span className="tnum">{formatInr(r.amount)}</span> a month is under
            what a fund will accept, so it goes to{' '}
            {Object.entries(r.moved_to)
              .map(
                ([to, amount]) =>
                  `${ASSET_LABEL[to] ?? to} (${formatInr(amount)})`,
              )
              .join(' and ')}{' '}
            instead. Every rupee of your SIP is still invested, but the mix above
            is not the one the goal asked for.
          </p>
        ))}
        {data.skipped
          .filter((s) => !data.reallocations.some((r) => r.asset_class === s.asset_class))
          .map((s) => (
            <p key={s.asset_class} className="max-w-3xl text-sm text-muted-foreground">
              <span className="font-medium">
                {ASSET_LABEL[s.asset_class] ?? s.asset_class}
              </span>{' '}
              has no fund named here: {plainProse(s.reason)}
            </p>
          ))}
        <p className="max-w-3xl text-xs text-muted-foreground">
          Scores are our own, worked out from public NAV history, not a licensed
          rating. Past performance is not a promise of future returns.
        </p>
      </div>
    </Panel>
  )
}
