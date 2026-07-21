import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

type AllocationPieProps = {
  equity: number
  debt: number
  gold: number
}

/* Spaced across the sequential ramp rather than adjacent to it, so three
   slices of one whole stay distinguishable without a second accent colour. */
const SLICES = [
  {
    key: 'equity',
    name: 'Equity',
    color: 'var(--chart-1)',
    note: 'Stocks and equity funds. Grows the most over a long horizon, and falls the hardest in a bad year.',
  },
  {
    key: 'debt',
    name: 'Debt',
    color: 'var(--chart-3)',
    note: 'Bonds and debt funds. Steadier, and what the plan leans on when equity is down.',
  },
  {
    key: 'gold',
    name: 'Gold',
    color: 'var(--chart-5)',
    note: 'A hedge. It tends not to move with Indian equity, so it cushions the worst years.',
  },
] as const

export function AllocationPie({ equity, debt, gold }: AllocationPieProps) {
  const values: Record<string, number> = { equity, debt, gold }
  const slices = SLICES.filter((s) => values[s.key] > 0).map((s) => ({
    ...s,
    value: values[s.key],
  }))

  if (slices.length === 0) {
    return (
      <p className="max-w-2xl text-sm text-muted-foreground">
        No split has been worked out for this goal yet. Create the goal again to get
        an equity, debt and gold allocation.
      </p>
    )
  }

  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:gap-10">
      <div className="h-44 w-44 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              innerRadius={52}
              outerRadius={76}
              paddingAngle={2}
              stroke="var(--background)"
              isAnimationActive={false}
            >
              {slices.map((s) => (
                <Cell key={s.key} fill={s.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value) => [`${value}%`, 'Allocation'] as [string, string]}
              contentStyle={{
                background: 'var(--popover)',
                color: 'var(--popover-foreground)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                fontSize: 12,
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* The exact figures live here rather than as labels on the arcs: labels
          around a donut collide as soon as two slices are thin. */}
      <dl className="w-full divide-y border-y">
        {slices.map((s) => (
          <div key={s.key} className="flex items-start gap-3 py-3">
            <span
              className="mt-1.5 size-2 shrink-0 rounded-full"
              style={{ background: s.color }}
              aria-hidden
            />
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <div className="flex items-baseline justify-between gap-4">
                <dt className="text-sm font-medium">{s.name}</dt>
                <dd className="num text-sm font-medium">{s.value}%</dd>
              </div>
              <p className="text-xs leading-snug text-muted-foreground">{s.note}</p>
            </div>
          </div>
        ))}
      </dl>
    </div>
  )
}
