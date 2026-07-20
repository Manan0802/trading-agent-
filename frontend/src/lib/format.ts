const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

export function formatInr(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return inr.format(value)
}

/** Signed rupees, for gains and losses. */
export function formatInrSigned(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value >= 0 ? '+' : '−'}${inr.format(Math.abs(value))}`
}

/** Takes a fraction (0.182), renders a percentage (+18.2%). */
export function formatPercent(
  value: number | null | undefined,
  { signed = true }: { signed?: boolean } = {},
): string {
  if (value === null || value === undefined) return '—'
  const pct = (value * 100).toFixed(1)
  if (!signed) return `${pct}%`
  return `${value >= 0 ? '+' : '−'}${Math.abs(Number(pct)).toFixed(1)}%`
}

export function formatUnits(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-IN', { maximumFractionDigits: 3 })
}

/** Tailwind classes for a number whose sign carries meaning. */
export function gainClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'text-muted-foreground'
  if (value > 0) return 'text-emerald-600 dark:text-emerald-400'
  if (value < 0) return 'text-red-600 dark:text-red-400'
  return 'text-muted-foreground'
}
