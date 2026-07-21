import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { api } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr, plainProse } from '@/lib/format'

type FundRecommendation = {
  asset_class: string
  scheme_code: string
  scheme_name: string
  category: string
  monthly_amount: number
  score: number
  rationale: string
}

type GoalRecommendations = {
  goal_id: string
  monthly_sip: number
  allocation: Record<string, number>
  recommendations: FundRecommendation[]
  skipped: { asset_class: string; reason: string }[]
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
  return (
    <li className="flex flex-col gap-1.5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-1">
        <div className="flex flex-col gap-0.5">
          <p className="font-medium leading-tight">{fund.scheme_name}</p>
          <p className="text-xs text-muted-foreground">
            {fund.category} &middot; scheme{' '}
            <span className="tnum">{fund.scheme_code}</span> &middot; score{' '}
            <span className="tnum">{fund.score.toFixed(0)}</span> of 100
          </p>
        </div>
        <div className="flex flex-col items-end">
          <span className="num text-lg font-medium leading-none">
            {formatInr(fund.monthly_amount)}
          </span>
          <span className="mt-1 text-xs text-muted-foreground">per month</span>
        </div>
      </div>
      <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
        {plainProse(fund.rationale)}
      </p>
    </li>
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
    <section className="flex flex-col gap-6">
      <SectionHeading>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Direct Growth plans only. A regular plan of the same fund carries a
          distributor commission inside the NAV, so you end up with less for an
          otherwise identical portfolio. Buy these yourself on your broker.
        </p>
      </SectionHeading>

      {Object.entries(byClass).map(([assetClass, funds]) => (
        <div key={assetClass} className="flex flex-col">
          <div className="flex items-baseline justify-between gap-4 border-b pb-2">
            <h3 className="text-sm font-medium">
              {ASSET_LABEL[assetClass] ?? assetClass}
            </h3>
            <span className="num text-xs text-muted-foreground">
              {data.allocation[assetClass]}% &middot;{' '}
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
        {data.skipped.map((s) => (
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
    </section>
  )
}
