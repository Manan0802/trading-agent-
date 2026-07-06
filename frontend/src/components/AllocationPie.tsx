import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

type AllocationPieProps = {
  equity: number
  debt: number
  gold: number
}

const SLICES = [
  { key: 'equity', name: 'Equity', color: 'var(--chart-1)' },
  { key: 'debt', name: 'Debt', color: 'var(--chart-2)' },
  { key: 'gold', name: 'Gold', color: 'var(--chart-3)' },
] as const

export function AllocationPie({ equity, debt, gold }: AllocationPieProps) {
  const values: Record<string, number> = { equity, debt, gold }
  const data = SLICES.map((s) => ({ name: s.name, value: values[s.key] })).filter(
    (d) => d.value > 0,
  )

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={2}
          label={({ name, value }) => `${name} ${value}%`}
        >
          {data.map((_, i) => (
            <Cell key={SLICES[i].key} fill={SLICES[i].color} stroke="var(--background)" />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => [`${value}%`, 'Allocation'] as [string, string]}
          contentStyle={{
            background: 'var(--popover)',
            color: 'var(--popover-foreground)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
          }}
        />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  )
}
