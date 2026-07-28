import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { AddHoldingDialog } from '@/components/AddHoldingDialog'
import { buttonVariants } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchProfile } from '@/lib/api'
import { formatInr } from '@/lib/format'
import { api } from '@/lib/api'

/**
 * The first three things to do, ordered by what each is actually worth.
 *
 * A new account landed on an empty holdings table and a button saying "add a
 * fund". That is the most work for the least money. Somebody earning ₹24 lakh
 * who has drifted onto the old tax regime is leaving ₹2.45 lakh a year on the
 * table, and answering that takes two fields — but the page led with the task
 * that takes an afternoon.
 *
 * So the order here is the order the levers list uses, and for the same reason.
 * Each step says what it unlocks, and the tax step reprices itself in real
 * rupees the moment there is an income to price it against.
 */

type Step = {
  key: string
  title: string
  /** A rupee figure only once we can stand behind it for this user. */
  worth: string | null
  detail: string
  done: boolean
  action: React.ReactNode
}

export function StartHere() {
  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: fetchProfile,
  })
  const { data: goals, isLoading: goalsLoading } = useQuery<{ id: string }[]>({
    queryKey: ['goals'],
    queryFn: async () => (await api.get('/api/v1/goals')).data,
  })

  if (profileLoading || goalsLoading) return <Skeleton className="h-56 w-full" />

  const hasIncome = !!profile?.annual_income && profile.annual_income > 0
  const hasGoal = (goals?.length ?? 0) > 0
  // Holdings are the reason this component renders at all — the Portfolio page
  // only shows it while the table is empty.
  const steps: Step[] = [
    {
      key: 'profile',
      title: 'Tell us what you earn',
      // No figure until there is an income to price it against. "Up to
      // ₹2,45,700" is true of somebody on ₹24 lakh and meaningless to somebody
      // on ₹8 lakh, and quoting the ceiling to everyone is what a brochure
      // does. The whole app is built on not doing that.
      worth:
        hasIncome && profile?.tax && profile.tax.saving > 0
          ? `${formatInr(profile.tax.saving)} a year`
          : null,
      detail: hasIncome
        ? profile?.tax?.rationale ??
          'Your income is in, so the tax regime answer is on your You page.'
        : 'Two fields. Which tax regime costs you less is a slab calculation rather than a forecast, and for most salaried people it is the largest single thing we can work out. We will not quote you a figure until we can compute yours.',
      done: hasIncome,
      action: (
        <Link to="/profile" className={buttonVariants({ size: 'sm' })}>
          {hasIncome ? 'Review it' : 'Two minutes'}
        </Link>
      ),
    },
    {
      key: 'holdings',
      title: 'Add what you already own',
      worth: null,
      detail:
        'A regular plan of the same fund quietly takes about 0.64 percentage points a year for an identical portfolio. We can only price that against funds you actually hold — and it is the one fund decision that measured out as real.',
      done: false,
      action: <AddHoldingDialog />,
    },
    {
      key: 'goal',
      title: 'Set a goal',
      worth: null,
      detail: hasGoal
        ? 'Done. Your goals page adds them up and says whether they fit together.'
        : 'A name, a rupee target and a date. We work out what it costs a month, which funds to put it in, and whether all your goals together are affordable.',
      done: hasGoal,
      action: (
        <Link to="/goals/new" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
          {hasGoal ? 'Add another' : 'Set one'}
        </Link>
      ),
    },
  ]

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <h2 className="text-lg font-medium">Start here</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          In the order they are worth money, which is not the order that feels
          obvious. The first one takes two fields and is usually the largest.
        </p>
      </div>

      <ol className="flex flex-col divide-y border-y">
        {steps.map((step, i) => (
          <li key={step.key} className="flex flex-col gap-2 py-4">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
              <span className="flex items-baseline gap-2">
                {step.done ? (
                  <Check className="size-4 shrink-0 translate-y-0.5 text-gain" aria-hidden />
                ) : (
                  <span className="num text-sm text-muted-foreground">{i + 1}</span>
                )}
                <span className={step.done ? 'text-muted-foreground' : 'font-medium'}>
                  {step.title}
                </span>
              </span>
              {/* Green and monospaced is this app's treatment for money. Prose
                  wearing it would spend the signal on something that is not a
                  figure, so a step with nothing to quote shows nothing. */}
              {step.worth && (
                <span
                  className={`num text-sm ${step.done ? 'text-muted-foreground' : 'text-gain'}`}
                >
                  {step.worth}
                </span>
              )}
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">{step.detail}</p>
            <div className="pt-1">{step.action}</div>
          </li>
        ))}
      </ol>
    </section>
  )
}
