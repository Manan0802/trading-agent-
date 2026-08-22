const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

/**
 * What we print where a figure genuinely is not available. One glyph for the
 * whole app, so a missing number never reads as a zero.
 */
export const NO_VALUE = '—'

export function formatInr(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  return inr.format(value)
}

/**
 * A NAV, which needs its paise.
 *
 * `formatInr` rounds to whole rupees, which is right for a portfolio value and
 * wrong for a unit price: a NAV of ₹90.4028 rendered as "₹90" loses the four
 * digits people use to check a statement against, and two funds a paisa apart
 * print identically. AMFI publishes four decimals; two is what a reader can
 * hold and enough to tell any two funds apart.
 */
export function formatNav(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  return `₹${value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** Signed rupees, for gains and losses. */
export function formatInrSigned(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  return `${value >= 0 ? '+' : '−'}${inr.format(Math.abs(value))}`
}

/** Takes a fraction (0.182), renders a percentage (+18.2%). */
export function formatPercent(
  value: number | null | undefined,
  { signed = true }: { signed?: boolean } = {},
): string {
  if (value === null || value === undefined) return NO_VALUE
  const pct = (value * 100).toFixed(1)
  if (!signed) return `${pct}%`
  return `${value >= 0 ? '+' : '−'}${Math.abs(Number(pct)).toFixed(1)}%`
}

/** Unitless ratios: Sortino, downside capture, P/E. */
export function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  return value.toFixed(2)
}

export function formatUnits(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  return value.toLocaleString('en-IN', { maximumFractionDigits: 3 })
}

/**
 * Prose that arrives from the API or from the model sometimes carries em and en
 * dashes. The interface punctuates with commas, so incoming copy is normalised
 * on the way in rather than reading as if it came from somewhere else.
 * Only ever apply this to sentences, never to a formatted figure.
 */
export function plainProse(text: string): string {
  return text.replace(/\s*[—–]\s*/g, ', ')
}

/** Tailwind classes for a number whose sign carries meaning. */
export function gainClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'text-muted-foreground'
  if (value > 0) return 'text-gain'
  if (value < 0) return 'text-loss'
  return 'text-muted-foreground'
}

/**
 * Compact rupees for axis ticks and dense cells, in the Indian scale the user
 * actually reads in: 1.2Cr and 45L, never 12M.
 */
export function formatInrCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  const abs = Math.abs(value)
  const sign = value < 0 ? '−' : ''
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(abs >= 1e8 ? 0 : 2)}Cr`
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(abs >= 1e6 ? 0 : 1)}L`
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(0)}k`
  return `${sign}₹${abs.toFixed(0)}`
}

/** "Equity Scheme - Small Cap Fund" is how SEBI writes it, not how anyone says it. */
export function shortCategory(category: string): string {
  return category.split(' - ').slice(1).join(' - ') || category
}

/** "Equity Scheme" -> "Equity", so a select can group ninety categories into five. */
export function categoryGroup(category: string): string {
  return category.split(' Scheme')[0]
}

/**
 * fund_score, peer_median and the two signals all arrive between 0 and 1. This
 * is the only place in the app that multiplies one by a hundred, so there is
 * exactly one thing to correct if the API ever changes its mind. It lives here
 * rather than in Screener because the fund page shows the same figures, and a
 * second copy is how two screens start scoring the same fund differently.
 */
export function score100(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  return (value * 100).toFixed(0)
}

/** A plain count, grouped the way an Indian reader expects: 1,20,455. */
export function count(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_VALUE
  return value.toLocaleString('en-IN')
}
