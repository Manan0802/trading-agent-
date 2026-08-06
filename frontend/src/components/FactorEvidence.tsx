import { useQuery } from '@tanstack/react-query'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Panel } from '@/components/ui/panel'
import { Plain } from '@/components/ui/plain'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchFactorEvidence } from '@/lib/portfolio-api'

/**
 * What has actually been shown to work on Indian equities, and what has not.
 *
 * Rewritten after Manan read the first version and said he could not tell what
 * the app was doing. It led with `t = +3.11` and `+13.4%/yr` — both true, both
 * checkable, and both addressed to somebody who already knows what a
 * t-statistic is. The person deciding where to put money needs the sentence,
 * not the statistic.
 *
 * So each factor states its verdict in a line and the arithmetic sits one click
 * behind it. Nothing is removed: an unfalsifiable claim is worse than a
 * hard-to-read one, and the whole argument of this app is that its claims can
 * be checked.
 *
 * The bad episode goes in the sentence rather than the detail, because it is
 * the number that decides how much of this anyone should hold. Momentum holds
 * up while the market falls and then loses violently when it turns — shown only
 * the average, a reader sizes it as though it were safe.
 */

type Episode = { label: string; annual_return: number; t_stat: number }

type Factor = {
  code: string
  name: string
  plain: string
  annual_return: number
  t_stat: number
  months: number
  significant: boolean
  episodes: Episode[]
}

/** Losing this much in a year is worth interrupting a good average for. */
const ALARMING_LOSS = 20

/** The plain-language verdict. One sentence, no jargon, decision-shaped. */
function verdict(factor: Factor): string {
  const years = Math.round(factor.months / 12)
  const worst = factor.episodes
    .filter((e) => e.label !== 'Last 8 years')
    .sort((a, b) => a.annual_return - b.annual_return)[0]

  if (!factor.significant) {
    return factor.annual_return < 0
      ? `Does not work in India — on average it has lost money over ${years} years. Ignore it.`
      : `No real evidence either way. The average looks positive, but it sits inside the range of luck.`
  }

  const caveat =
    worst && worst.annual_return < -ALARMING_LOSS
      ? ` But in the ${worst.label.toLowerCase()} it lost ${Math.abs(
          worst.annual_return,
        ).toFixed(0)}% in a year, so this is not somewhere to put all of your money.`
      : ''

  return `Works, and it is not luck — ${years} years of evidence say so.${caveat}`
}

function FactorRow({ factor }: { factor: Factor }) {
  const episodes = factor.episodes.filter((e) => e.label !== 'Last 8 years')

  return (
    <div className="flex flex-col gap-2 border-t py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <p className="font-medium">{factor.name}</p>
        <span
          className={`text-xs font-medium ${
            factor.significant ? 'text-gain' : 'text-muted-foreground'
          }`}
        >
          {factor.significant ? 'Shown to work' : 'Not shown to work'}
        </span>
      </div>

      <Plain
        detail={
          <div className="flex flex-col gap-1.5 py-1">
            <p>
              <span className="tnum">
                {factor.annual_return >= 0 ? '+' : '−'}
                {Math.abs(factor.annual_return).toFixed(1)}%
              </span>{' '}
              a year on average, measured over{' '}
              <span className="tnum">{factor.months}</span> months.
            </p>
            <p>
              t = <span className="tnum">{factor.t_stat.toFixed(2)}</span>. This
              weighs the average against how much it swings about. Above 2 means
              it is unlikely to be luck; below 2 means it may well be.
            </p>
            {episodes.length > 0 && (
              <div className="flex flex-wrap gap-x-6 gap-y-1 pt-1">
                {episodes.map((e) => (
                  <span key={e.label}>
                    {e.label}{' '}
                    <span
                      className={`tnum ${
                        e.annual_return >= 0 ? 'text-gain' : 'text-loss'
                      }`}
                    >
                      {e.annual_return >= 0 ? '+' : '−'}
                      {Math.abs(e.annual_return).toFixed(1)}%
                    </span>
                  </span>
                ))}
              </div>
            )}
          </div>
        }
      >
        <span className="text-muted-foreground">{factor.plain}</span>{' '}
        {verdict(factor)}
      </Plain>
    </div>
  )
}

export function FactorEvidence() {
  const { data, isLoading } = useQuery({
    queryKey: ['factor-evidence'],
    queryFn: fetchFactorEvidence,
  })

  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (!data) return null

  const works = data.factors.filter((f) => f.significant).map((f) => f.name)

  return (
    <Panel title="What has actually been shown to work">
      <p className="max-w-4xl text-sm">
        Most investing advice is somebody&rsquo;s opinion. This is not.
        {works.length > 0 && (
          <>
            {' '}Of the four things anyone can measure about Indian shares, only{' '}
            <span className="font-medium">{works.join(' and ')}</span>{' '}
            {works.length === 1 ? 'holds' : 'hold'} up over thirty-two years.
          </>
        )}
      </p>

      <div className="grid items-start gap-x-10 gap-y-0 xl:grid-cols-2">
        <div className="flex flex-col">
          {data.factors.map((f) => (
            <FactorRow key={f.code} factor={f} />
          ))}
        </div>

        <div className="flex flex-col gap-2 pt-4 xl:pt-0">
          <p className="text-sm font-medium">
            What &#8377;1 in momentum became, since 1993
          </p>
          {/* One series, so no legend — the title names it. The shape is the
              argument, and the flat stretches are the part that matters. */}
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={data.momentum_curve}
                margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
              >
                <CartesianGrid
                  stroke="var(--border)"
                  strokeDasharray="2 4"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v: string) => v.slice(0, 4)}
                  tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={40}
                />
                <YAxis
                  tickFormatter={(v: number) => `₹${v.toFixed(0)}`}
                  tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  tickLine={false}
                  axisLine={false}
                  width={44}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--card)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(v) => [`₹${Number(v).toFixed(1)}`, 'Worth']}
                />
                <Area
                  dataKey="value"
                  stroke="var(--primary)"
                  strokeWidth={2}
                  fill="var(--primary)"
                  fillOpacity={0.08}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-muted-foreground">
            Notice the flat stretches. That is the catch: this grows well for
            years and then hands a chunk back all at once, usually just as the
            market is recovering from a fall.
          </p>
        </div>
      </div>

      <Plain
        label="where this comes from"
        detail={
          <p className="py-1">
            {data.source.name}, built {data.built_on}. {data.source.note} Covers{' '}
            {data.period.from} to {data.period.to},{' '}
            <span className="tnum">{data.period.months}</span> months.{' '}
            <a
              href={data.source.url}
              className="underline"
              target="_blank"
              rel="noreferrer"
            >
              The raw data
            </a>
            .
          </p>
        }
      >
        These are not our numbers. They are published by academics, cover
        thirty-two years, and count the companies that went bust &mdash; which
        most published returns quietly leave out.
      </Plain>
    </Panel>
  )
}
