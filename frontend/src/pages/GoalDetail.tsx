import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { AllocationPie } from '@/components/AllocationPie'
import { GoalFundPlan } from '@/components/GoalFundPlan'
import { Levers } from '@/components/Levers'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr, plainProse } from '@/lib/format'

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

function LoadingState() {
  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-12 w-56" />
        <Skeleton className="h-4 w-80" />
      </div>
      <Skeleton className="h-44 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  )
}

export function GoalDetail() {
  const { id } = useParams()
  const { data, isLoading, isError } = useQuery<Goal>({
    queryKey: ['goal', id],
    queryFn: async () => (await api.get(`/api/v1/goals/${id}`)).data,
  })

  if (isLoading) return <LoadingState />

  if (isError || !data) {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-lg font-medium">Couldn't load this goal</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Either the goal no longer exists or the server did not respond. Refresh the
          page, and if it keeps failing check that the API is running.
        </p>
      </div>
    )
  }

  const sip = data.required_monthly_sip

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-semibold tracking-tight">{data.goal_name}</h1>
          <Badge variant={data.status === 'active' ? 'default' : 'secondary'}>
            {data.status}
          </Badge>
        </div>

        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Monthly SIP
          </p>
          <p className="num num-display text-4xl font-semibold leading-none sm:text-5xl">
            {formatInr(sip)}
          </p>
          <p className="tnum max-w-2xl text-sm text-muted-foreground">
            {sip != null
              ? `Invested every month, this is what reaches ${formatInr(
                  data.target_amount,
                )} in ${data.years} years at the returns we assume. It is a projection, not a promise.`
              : `We have not worked out a monthly amount for this goal yet. The target is ${formatInr(
                  data.target_amount,
                )} in ${data.years} years.`}
          </p>
        </div>
      </header>

      <section className="flex flex-col gap-4">
        <h2 className="text-sm font-medium">Where the money goes</h2>
        <AllocationPie
          equity={data.equity_allocation ?? 0}
          debt={data.debt_allocation ?? 0}
          gold={data.gold_allocation ?? 0}
        />
      </section>

      {data.llm_explanation && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-medium">What this means</h2>
          <p className="max-w-3xl text-sm leading-relaxed">
            {plainProse(data.llm_explanation)}
          </p>
          <p className="max-w-3xl text-xs text-muted-foreground">
            Every figure on this page is a projected estimate, not a guaranteed
            return.
          </p>
        </section>
      )}

      {id && <GoalFundPlan goalId={id} />}

      {/* Placed after the picks, not before them. The list prices fund
          selection at zero, and that lands as a useful caveat on a plan the
          reader has already seen rather than as a reason to skip reading it.
          A goal is also the one place the horizon and the SIP are both known,
          so every lever here is priced against this goal's own numbers. */}
      <Levers yearsRemaining={data.years} monthlySip={sip ?? undefined} />
    </div>
  )
}
