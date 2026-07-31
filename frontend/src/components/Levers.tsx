import { useQuery } from '@tanstack/react-query'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr } from '@/lib/format'
import { fetchLevers } from '@/lib/portfolio-api'

/**
 * The decisions that are actually worth money, in rupees, biggest first.
 *
 * Fund selection sits on this list at zero rather than being left off it. We
 * measured it over sixty three-year windows and it does not work, and the zero
 * is the most useful thing on the page: it is where nearly everyone spends
 * their attention.
 */
export function Levers({
  yearsRemaining,
  monthlySip,
}: {
  /** Left undefined outside a goal, so the server uses the stored profile
   *  horizon rather than a number this component invented. */
  yearsRemaining?: number
  monthlySip?: number
} = {}) {
  const { data, isLoading } = useQuery({
    queryKey: ['levers', yearsRemaining, monthlySip],
    queryFn: () =>
      fetchLevers({ years_remaining: yearsRemaining, monthly_sip: monthlySip }),
  })

  if (isLoading) return <Skeleton className="h-40 w-full" />
  if (!data || data.levers.length === 0) return null

  return (
    <Panel className="xl:col-span-1">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="text-sm font-medium">What actually moves your money</h2>
        <p className="text-xs text-muted-foreground">
          Over the next <span className="tnum">{data.years_remaining}</span> years
        </p>
      </div>

      <ul className="flex flex-col divide-y border-y">
        {data.levers.map((lever) => {
          const worthless = lever.lifetime_value === 0
          return (
            <li key={lever.key} className="flex flex-col gap-1.5 py-4">
              <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                <span className={worthless ? 'text-muted-foreground' : 'font-medium'}>
                  {lever.title}
                </span>
                <span className="flex items-baseline gap-3">
                  <span
                    className={`num text-lg ${
                      worthless ? 'text-muted-foreground' : 'font-medium text-gain'
                    }`}
                  >
                    {formatInr(lever.lifetime_value)}
                  </span>
                  {lever.annual_value > 0 && (
                    <span className="num text-xs text-muted-foreground">
                      {formatInr(lever.annual_value)}/yr
                    </span>
                  )}
                </span>
              </div>
              <p className="max-w-3xl text-sm text-muted-foreground">{lever.detail}</p>
              <p className="max-w-3xl text-sm">{lever.action}</p>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
