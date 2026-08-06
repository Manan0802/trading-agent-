import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { Panel } from '@/components/ui/panel'
import { Plain } from '@/components/ui/plain'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchMomentum } from '@/lib/portfolio-api'

/**
 * Stocks ranked by the one signal in this app measured to predict.
 *
 * Everything else the app is good at is arithmetic — what a fund costs, what a
 * tax regime costs. This is the only forecast that survived testing, and it
 * survived on two independent datasets: our own universe at t = +2.99 over 60
 * non-overlapping windows, and IIMA's 32-year survivorship-adjusted series at
 * t = +3.11.
 *
 * The risk travels with the rank rather than sitting in a footnote. Momentum
 * holds up while the market falls and then loses violently when it turns —
 * −53.5% through the 2009 rebound. A list of green percentages with that fact
 * on another page is a list that will be misread, so it is stated above the
 * table and again at the bottom.
 *
 * And the language is deliberately about the *group*, not the stock. A rank IC
 * of 0.07 separates quartiles over many names and many years; it says nothing
 * about whether any single company here goes up.
 */

const SHOWN = 20

export function MomentumScreen() {
  const { data, isLoading } = useQuery({
    queryKey: ['momentum'],
    queryFn: () => fetchMomentum(),
  })

  if (isLoading) return <Skeleton className="h-72 w-full" />
  if (!data || data.ranked.length === 0) return null

  const top = data.ranked.slice(0, SHOWN)

  return (
    <Panel
      title="Which stocks have been going up"
      aside={`${data.measured_from} to ${data.measured_to}`}
    >
      <p className="max-w-4xl text-sm">
        This is the one thing in this app that has actually been shown to
        predict anything about a share&rsquo;s next year: shares that have been
        rising tend to keep rising, a little, on average.{' '}
        <span className="font-medium">
          It is not a prediction about any one company here.
        </span>{' '}
        It says the top group has historically done better than the bottom
        group, over many names and many years.
      </p>

      {/* Above the table, not below it. A list of green percentages with this
          fact on another page is a list that will be misread. */}
      <p className="flex max-w-4xl items-start gap-2 rounded-md bg-muted/40 px-3 py-2 text-sm">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>
          <span className="font-medium">The catch, and it is a big one.</span>{' '}
          This works while markets fall and then loses badly when they turn. In
          the 2009 recovery it dropped{' '}
          <span className="num font-medium text-loss">
            {Math.abs(data.rebound_loss).toFixed(0)}%
          </span>{' '}
          in a year while the market gained 92%. Do not put money here that you
          would need back in a hurry.
        </span>
      </p>

      <div className="-mx-4 overflow-x-auto sm:mx-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground">
              <th className="w-10 py-2 text-left font-normal">#</th>
              <th className="py-2 text-left font-normal">Company</th>
              <th className="py-2 text-left font-normal">Industry</th>
              <th className="py-2 text-right font-normal">Past year</th>
            </tr>
          </thead>
          <tbody>
            {top.map((row) => (
              <tr key={row.symbol} className="border-b last:border-0">
                <td className="num py-2 text-muted-foreground">{row.rank}</td>
                <td className="py-2">
                  <span className="font-medium">{row.name}</span>{' '}
                  <span className="tnum text-xs text-muted-foreground">
                    {row.symbol}
                  </span>
                </td>
                <td className="py-2 text-xs text-muted-foreground">
                  {row.industry ?? '—'}
                </td>
                <td
                  className={`num py-2 text-right ${
                    row.momentum >= 0 ? 'text-gain' : 'text-loss'
                  }`}
                >
                  {row.momentum >= 0 ? '+' : '−'}
                  {Math.abs(row.momentum * 100).toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Plain
        label="how this is worked out"
        detail={
          <div className="flex flex-col gap-1.5 py-1">
            <p>
              Each share&rsquo;s return over the twelve months ending a month
              ago. The last month is skipped on purpose: very recent moves tend
              to reverse, which pulls the opposite way and weakens the signal.
            </p>
            <p>
              Tested two ways. On this universe: 60 separate quarterly windows
              over 15 years, t = +2.99, after charging trading costs. Against
              IIMA&rsquo;s 32-year Indian factor series, which counts companies
              that went bust: t = +3.11.
            </p>
            <p>
              Showing the top <span className="tnum">{SHOWN}</span> of{' '}
              <span className="tnum">{data.ranked.length}</span> ranked, out of{' '}
              <span className="tnum">{data.considered}</span> considered.
              {data.unranked.length > 0 && (
                <>
                  {' '}
                  <span className="tnum">{data.unranked.length}</span> could not
                  be ranked for want of a full year of prices:{' '}
                  {data.unranked.slice(0, 8).join(', ')}
                  {data.unranked.length > 8 && ' and others'}.
                </>
              )}
            </p>
          </div>
        }
      >
        Ranked on the past year&rsquo;s return, skipping the most recent month,
        and tested on 32 years of Indian data before being shown here.
      </Plain>
    </Panel>
  )
}
