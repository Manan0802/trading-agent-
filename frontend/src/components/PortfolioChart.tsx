import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatInr, formatInrCompact } from '@/lib/format'
import type { HistoryPoint } from '@/lib/portfolio-api'

const SERIES = [
  { key: 'portfolio_value', label: 'Your portfolio' },
  { key: 'benchmark_value', label: 'Same money in the index' },
  { key: 'invested', label: 'Invested' },
] as const

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: { dataKey: string; value: number }[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  const by = new Map(payload.map((p) => [p.dataKey, p.value]))

  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-sm">
      <p className="mb-1.5 font-medium text-popover-foreground">
        {new Date(label!).toLocaleDateString('en-IN', {
          month: 'short',
          year: 'numeric',
        })}
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        {SERIES.map(({ key, label: name }) =>
          by.get(key) === undefined || by.get(key) === null ? null : (
            <div key={key} className="contents">
              <dt className="text-muted-foreground">{name}</dt>
              <dd className="num text-right text-popover-foreground">
                {formatInr(by.get(key))}
              </dd>
            </div>
          ),
        )}
      </dl>
    </div>
  )
}

export function PortfolioChart({
  points,
  excluded = {},
  excludedValue = 0,
}: {
  points: HistoryPoint[]
  /** Holdings this line does not cover, with the reason. */
  excluded?: Record<string, string>
  /** What they are worth today. */
  excludedValue?: number
}) {
  // Two points draw a straight line that implies a trend from nothing.
  if (points.length < 3) return null

  const left = Object.entries(excluded)

  const hasBenchmark = points.some((p) => p.benchmark_value !== null)

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="text-sm font-medium">Value over time</h2>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full bg-primary" aria-hidden />
            Your portfolio
          </span>
          {hasBenchmark && (
            <span className="flex items-center gap-1.5">
              <span
                className="h-0.5 w-4 rounded-full border-t-2 border-dashed border-muted-foreground"
                aria-hidden
              />
              Same money in the index
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full bg-border" aria-hidden />
            Invested
          </span>
        </div>
      </div>

      <div className="h-64 w-full sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={points}
            margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              vertical={false}
              stroke="var(--border)"
              strokeDasharray="2 4"
            />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              minTickGap={48}
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              tickFormatter={(d: string) =>
                new Date(d).toLocaleDateString('en-IN', {
                  month: 'short',
                  year: '2-digit',
                })
              }
            />
            <YAxis
              width={56}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              tickFormatter={(v: number) => formatInrCompact(v)}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: 'var(--muted-foreground)', strokeWidth: 1 }}
            />
            {/* Invested sits underneath as a filled floor, so the gap between
                it and the value line is the gain, read directly off the chart. */}
            <Area
              dataKey="invested"
              stroke="var(--border)"
              strokeWidth={1}
              fill="var(--muted)"
              fillOpacity={0.55}
              isAnimationActive={false}
            />
            {hasBenchmark && (
              <Line
                dataKey="benchmark_value"
                stroke="var(--muted-foreground)"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            )}
            <Line
              dataKey="portfolio_value"
              stroke="var(--primary)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Without this the chart sat 29% below the total printed above it, with
          nothing to explain the gap. Two plausible numbers disagreeing is worse
          than one visible error, because neither looks wrong. */}
      {left.length > 0 && (
        <p className="max-w-3xl text-xs text-muted-foreground">
          This line covers your funds only.{' '}
          {left.map(([name]) => name).join(', ')}
          {excludedValue > 0 && (
            <>
              {' '}&mdash; worth{' '}
              <span className="tnum">{formatInr(excludedValue)}</span> today
            </>
          )}
          {' '}
          {left.length === 1 ? 'is' : 'are'} not in it, so it reads below the
          total above. {left[0][1]}.
        </p>
      )}
    </section>
  )
}
