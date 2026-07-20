import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr } from '@/lib/format'

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

function FundCard({ fund }: { fund: FundRecommendation }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col">
          <span className="font-medium leading-snug">{fund.scheme_name}</span>
          <span className="text-xs text-muted-foreground">
            {ASSET_LABEL[fund.asset_class] ?? fund.asset_class} · scheme {fund.scheme_code}
          </span>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-lg font-semibold tabular-nums">
            {formatInr(fund.monthly_amount)}
          </span>
          <span className="text-xs text-muted-foreground">per month</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Badge variant="secondary">Score {fund.score.toFixed(0)}/100</Badge>
      </div>

      <p className="text-sm leading-relaxed text-muted-foreground">{fund.rationale}</p>
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
      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">
            Working out which funds to buy…
          </CardTitle>
          <CardDescription>
            Pulling NAV history for the whole shortlist. This takes a moment the first time.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Skeleton className="h-24 w-full rounded-lg" />
          <Skeleton className="h-24 w-full rounded-lg" />
        </CardContent>
      </Card>
    )
  }

  if (isError) {
    const detail = (error as any)?.response?.data?.detail
    return (
      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">Fund plan</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-amber-600 dark:text-amber-400">
            {detail ?? 'Fund data is temporarily unavailable. Please refresh to retry.'}
          </p>
        </CardContent>
      </Card>
    )
  }

  if (!data || data.recommendations.length === 0) return null

  const byClass = data.recommendations.reduce<Record<string, FundRecommendation[]>>(
    (acc, fund) => {
      ;(acc[fund.asset_class] ??= []).push(fund)
      return acc
    },
    {},
  )

  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle>What to actually buy</CardTitle>
        <CardDescription>
          Direct-Growth plans only — regular plans carry a distributor commission inside
          the NAV for an otherwise identical portfolio. Buy these yourself on your broker.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {Object.entries(byClass).map(([assetClass, funds]) => (
          <div key={assetClass} className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between">
              <h3 className="text-sm font-medium">
                {ASSET_LABEL[assetClass] ?? assetClass}
              </h3>
              <span className="text-xs text-muted-foreground tabular-nums">
                {data.allocation[assetClass]}% ·{' '}
                {formatInr(funds.reduce((sum, f) => sum + f.monthly_amount, 0))}/mo
              </span>
            </div>
            {funds.map((fund) => (
              <FundCard key={fund.scheme_code} fund={fund} />
            ))}
          </div>
        ))}

        {data.skipped.length > 0 && (
          <div className="flex flex-col gap-1 border-t pt-3">
            {data.skipped.map((s) => (
              <p key={s.asset_class} className="text-xs text-muted-foreground">
                <span className="font-medium">{ASSET_LABEL[s.asset_class] ?? s.asset_class}</span>{' '}
                left out — {s.reason}
              </p>
            ))}
          </div>
        )}

        <p className="border-t pt-3 text-xs text-muted-foreground">
          Scores are our own, computed from public NAV history — not a licensed rating.
          Past performance is not a promise of future returns.
        </p>
      </CardContent>
    </Card>
  )
}
