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
import { Skeleton } from '@/components/ui/skeleton'
import { fetchFactorEvidence } from '@/lib/portfolio-api'

/**
 * What has actually been shown to work on Indian equities, and what has not.
 *
 * This is the strongest measurement in the app and it lived in a document
 * nobody opens. It is thirty-two years of published factor returns,
 * survivorship-bias adjusted, built by academics with no stake in this being
 * right — which is exactly why it is worth showing rather than our own
 * fifteen-year run on today's index members.
 *
 * The crash rows lead. An average across thirty-two years hides that momentum
 * paid nothing through 2008 and nothing through COVID, and that is the number
 * that should decide how much of it anyone holds. A reader who takes the
 * +13.4% and skips the −0.4% has been misled by a true number.
 */

/** Below this, a result is consistent with luck. Stated, not left implied. */
const SIGNIFICANT_T = 2

function Episode({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`num text-sm ${value >= 0 ? 'text-gain' : 'text-loss'}`}>
        {value >= 0 ? '+' : '−'}
        {Math.abs(value).toFixed(1)}%
      </span>
    </div>
  )
}

function Stat({ factor }: { factor: Factor }) {
  /*
   * Crash and rebound are shown side by side because for momentum they point
   * opposite ways, and either one alone is misleading. It holds up while the
   * market falls and then loses violently when it turns, since the losers it
   * has stepped away from bounce hardest. A reader shown only the crash column
   * would size the position as though it were a hedge.
   */
  const shown = factor.episodes.filter((e) => e.label !== 'Last 8 years')

  return (
    <div className="flex flex-col gap-2 border-t py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <div className="min-w-0">
          <p className="font-medium">{factor.name}</p>
          <p className="text-xs text-muted-foreground">{factor.plain}</p>
        </div>
        <div className="flex items-baseline gap-5">
          <span className="flex flex-col items-end">
            <span className="text-xs text-muted-foreground">per year</span>
            <span
              className={`num text-lg leading-none ${
                factor.annual_return >= 0 ? 'text-gain' : 'text-loss'
              }`}
            >
              {factor.annual_return >= 0 ? '+' : '−'}
              {Math.abs(factor.annual_return).toFixed(1)}%
            </span>
          </span>
          <span className="flex flex-col items-end">
            <span className="text-xs text-muted-foreground">t</span>
            <span className="num text-lg leading-none">
              {factor.t_stat >= 0 ? '+' : '−'}
              {Math.abs(factor.t_stat).toFixed(2)}
            </span>
          </span>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        {factor.significant ? (
          <>
            Above <span className="tnum">{SIGNIFICANT_T}</span> on{' '}
            <span className="tnum">{factor.months}</span> months, so this is not
            luck.
          </>
        ) : (
          <>
            Below <span className="tnum">{SIGNIFICANT_T}</span> on{' '}
            <span className="tnum">{factor.months}</span> months &mdash; this is
            consistent with luck, whatever the average says.
          </>
        )}
      </p>

      {shown.length > 0 && (
        <div className="flex flex-wrap gap-x-8 gap-y-2 rounded-md bg-muted/40 px-3 py-2">
          {shown.map((e) => (
            <Episode key={e.label} label={e.label} value={e.annual_return} />
          ))}
        </div>
      )}
    </div>
  )
}

type Factor = {
  code: string
  name: string
  plain: string
  annual_return: number
  t_stat: number
  months: number
  significant: boolean
  episodes: { label: string; annual_return: number; t_stat: number }[]
}

export function FactorEvidence() {
  const { data, isLoading } = useQuery({
    queryKey: ['factor-evidence'],
    queryFn: fetchFactorEvidence,
  })

  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (!data) return null

  return (
    <Panel
      title="What has actually been shown to work"
      aside={`${data.period.from} to ${data.period.to} · ${data.period.months} months`}
    >
      <p className="max-w-4xl text-sm">
        Not our numbers. This is India&rsquo;s published factor record &mdash;{' '}
        <span className="font-medium">survivorship-bias adjusted</span>, so the
        companies that failed are still counted, and built by academics with no
        stake in this app being right.
      </p>

      <div className="grid items-start gap-x-10 gap-y-0 xl:grid-cols-2">
        <div className="flex flex-col">
          {data.factors.map((f) => (
            <Stat key={f.code} factor={f} />
          ))}
        </div>

        <div className="flex flex-col gap-2 pt-4 xl:pt-0">
          <p className="text-sm font-medium">
            A rupee in momentum, since 1993
          </p>
          {/* One series, so no legend — the title names it. The shape is the
              argument: it climbs, then goes flat for years at a time, and no
              table conveys that as directly. */}
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
                  tickFormatter={(v: number) => `${v.toFixed(0)}x`}
                  tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                  tickLine={false}
                  axisLine={false}
                  width={38}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--card)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(v) => [`${Number(v).toFixed(1)}x`, 'Growth']}
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
            Long winners, short losers, rebalanced monthly and before costs. A
            long-only investor reaches roughly half of it. The flat stretches
            are the point, and the numbers on the left say where they come
            from: momentum holds up while the market falls and loses violently
            when it turns, because the losers it has stepped away from bounce
            hardest.
          </p>
        </div>
      </div>

      <p className="max-w-4xl text-xs text-muted-foreground">
        {/* Sourced and dated, so it can be checked and so a stale file cannot
            pass for a fresh one. */}
        Source: {data.source.name}, built {data.built_on}. {data.source.note}{' '}
        <span className="tnum">t</span> is the mean over its own standard error
        on non-overlapping monthly observations.
      </p>
    </Panel>
  )
}
