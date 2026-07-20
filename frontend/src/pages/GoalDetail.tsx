import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { AllocationPie } from '@/components/AllocationPie'
import { GoalFundPlan } from '@/components/GoalFundPlan'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { formatInr } from '@/lib/format'

type Goal = {
  id: string
  goal_name: string
  target_amount: number
  years: number
  required_monthly_sip: number | null
  equity_allocation: number | null
  debt_allocation: number | null
  gold_allocation: number | null
  llm_explanation: string | null
  status: string
}

export function GoalDetail() {
  const { id } = useParams()
  const { data, isLoading, isError } = useQuery<Goal>({
    queryKey: ['goal', id],
    queryFn: async () => (await api.get(`/api/v1/goals/${id}`)).data,
  })

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl animate-pulse px-4 py-10">
        <div className="mb-4 h-8 w-64 rounded-md bg-muted" />
        <div className="h-40 rounded-xl bg-muted" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-destructive">Couldn't load this goal. Please refresh.</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">{data.goal_name}</h1>
        <Badge variant={data.status === 'active' ? 'default' : 'secondary'}>
          {data.status}
        </Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              Projected monthly SIP
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold tabular-nums">
              {data.required_monthly_sip != null ? formatInr(data.required_monthly_sip) : '—'}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Target {formatInr(data.target_amount)} in {data.years} years
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Asset allocation</CardTitle>
          </CardHeader>
          <CardContent>
            <AllocationPie
              equity={data.equity_allocation ?? 0}
              debt={data.debt_allocation ?? 0}
              gold={data.gold_allocation ?? 0}
            />
          </CardContent>
        </Card>
      </div>

      {data.llm_explanation && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">What this means</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed">{data.llm_explanation}</p>
            <Separator className="my-3" />
            <p className="text-xs text-muted-foreground">
              All figures are projected estimates, not guaranteed returns.
            </p>
          </CardContent>
        </Card>
      )}

      {id && <GoalFundPlan goalId={id} />}
    </div>
  )
}
