import { Link } from 'react-router-dom'
import { Panel } from '@/components/ui/panel'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { buttonVariants } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr } from '@/lib/format'

type Goal = {
  id: string
  goal_type: string
  goal_name: string
  target_amount: number
  current_savings: number
  target_date: string
  years: number
  required_monthly_sip: number | null
  status: string
}

type Commitment = {
  total_monthly: number
  goals: { goal_id: string; goal_name: string; monthly_sip: number; years: number }[]
  affordable_monthly: number | null
  shortfall: number | null
  verdict: string
}

function dueIn(iso: string): string {
  const months = Math.round(
    (new Date(iso).getTime() - Date.now()) / (1000 * 60 * 60 * 24 * 30.4),
  )
  if (months <= 0) return 'due now'
  if (months < 18) return `${months} months away`
  return `${Math.round(months / 12)} years away`
}

function GoalRow({ goal }: { goal: Goal }) {
  // Against today's target, not the inflated one. The inflated figure lives on
  // the goal's own page with the rate that produced it; putting it here without
  // that explanation would look like the target had quietly grown.
  const progress =
    goal.target_amount > 0
      ? Math.min(1, goal.current_savings / goal.target_amount)
      : 0

  return (
    <li className="py-4">
      <Link
        to={`/goals/${goal.id}`}
        className="group flex flex-col gap-2 no-underline"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <span className="font-medium underline-offset-4 group-hover:underline">
            {goal.goal_name}
          </span>
          <span className="flex items-baseline gap-3">
            <span className="num text-lg font-medium">
              {formatInr(goal.required_monthly_sip)}
            </span>
            <span className="text-xs text-muted-foreground">per month</span>
          </span>
        </div>

        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 text-xs text-muted-foreground">
          <span className="tnum">
            {formatInr(goal.target_amount)} &middot; {dueIn(goal.target_date)}
          </span>
          <span className="tnum">
            {formatInr(goal.current_savings)} saved so far
          </span>
        </div>

        <div
          className="h-1 w-full overflow-hidden rounded-full bg-secondary"
          role="progressbar"
          aria-valuenow={Math.round(progress * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${goal.goal_name} progress`}
        >
          <div
            className="h-full rounded-full bg-primary"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </Link>
    </li>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-start gap-3 border-t pt-10">
      <h2 className="text-lg font-medium">No goals yet</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        A goal is what turns a number in an account into a decision you can check
        yourself against. Give one a name, a rupee target and a date, and we work
        out what it costs a month and which funds to put it in.
      </p>
      <Link to="/goals/new" className={buttonVariants({ className: 'mt-1' })}>
        Set a goal
      </Link>
    </div>
  )
}

export function Goals() {
  const { data, isLoading, isError } = useQuery<Goal[]>({
    queryKey: ['goals'],
    queryFn: async () => (await api.get('/api/v1/goals')).data,
  })
  const { data: commitment } = useQuery<Commitment>({
    queryKey: ['goal-commitment'],
    queryFn: async () => (await api.get('/api/v1/goals/commitment')).data,
    enabled: !!data && data.length > 0,
  })

  if (isLoading) {
    return (
      <div className="flex flex-col gap-8">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-lg font-medium">Couldn't load your goals</h1>
        <p className="text-sm text-muted-foreground">
          The server did not respond. Refresh the page, and if it keeps failing
          check that the API is running.
        </p>
      </div>
    )
  }

  const active = data.filter((g) => g.status === 'active')

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div className="flex flex-col gap-1.5">
          {active.length > 0 ? (
            <>
              <h1 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Every goal, every month
              </h1>
              {/* A skeleton, not formatInr(0). The commitment query only starts
                  once the goals resolve, so `?? 0` rendered a confident Rs 0 as
                  the headline for one frame — a real figure, and wrong. */}
              {commitment ? (
                <p className="num num-display text-4xl font-semibold leading-none sm:text-5xl">
                  {formatInr(commitment.total_monthly)}
                </p>
              ) : (
                <Skeleton className="h-10 w-48 sm:h-12" />
              )}
              <p className="tnum text-sm text-muted-foreground">
                Across <span className="tnum">{active.length}</span>{' '}
                {active.length === 1 ? 'goal' : 'goals'}
              </p>
            </>
          ) : (
            <h1 className="text-2xl font-semibold tracking-tight">Goals</h1>
          )}
        </div>
        {active.length > 0 && (
          <Link to="/goals/new" className={buttonVariants({ variant: 'outline' })}>
            New goal
          </Link>
        )}
      </header>

      {active.length === 0 && <EmptyState />}

      {/* The sentence three tidy plans never say. Each goal's own page prices
          that goal; nobody adds them up, and that is how somebody ends up
          committing more than they earn and finding out by missing an
          instalment. */}
      {commitment && active.length > 0 && (
        <p
          className={`max-w-3xl border-l-2 py-1 pl-3 text-sm ${
            commitment.shortfall && commitment.shortfall > 0
              ? 'border-loss'
              : 'border-primary'
          }`}
        >
          {commitment.verdict}
        </p>
      )}

      {active.length > 0 && (
        <Panel
          title="Your goals"
          aside={`${active.length} ${active.length === 1 ? 'goal' : 'goals'}`}
        >
          <ul className="flex flex-col divide-y">
            {active.map((goal) => (
              <GoalRow key={goal.id} goal={goal} />
            ))}
          </ul>
        </Panel>
      )}
    </div>
  )
}
