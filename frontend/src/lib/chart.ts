/**
 * Chart plumbing shared by the fund page and the stock page.
 *
 * Every function here was written for `FundAnalysis.tsx` against a real chart
 * that was drawing something wrong; the comments record which. They live here
 * rather than in either page because a second page drawing a rebased line
 * against a peer median needs the same answers, and two copies of a tick
 * algorithm is how two charts start disagreeing about what a year looks like.
 */

/**
 * Dates arrive as bare `YYYY-MM-DD` with no timezone. `new Date('2026-03-01')`
 * parses that as UTC midnight and then prints it in the reader's zone, which
 * moves it to 28 February for anybody west of Greenwich. Parsed and formatted
 * in UTC end to end, a published date is the day it was published, everywhere.
 */
export function utc(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Date.UTC(y, m - 1, d)
}

const FULL_DATE = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})

const TICK_DAY = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
})

const TICK_MONTH = new Intl.DateTimeFormat('en-IN', {
  month: 'short',
  year: '2-digit',
  timeZone: 'UTC',
})

export function longDate(iso: string | null | undefined): string {
  return iso ? FULL_DATE.format(utc(iso)) : '—'
}

export function daysBetween(from: string, to: string): number {
  return Math.round((utc(to) - utc(from)) / 86_400_000)
}

export const RANGES = [
  { key: '1m', label: '1M', words: 'one month' },
  { key: '6m', label: '6M', words: 'six months' },
  { key: '1y', label: '1Y', words: 'one year' },
  { key: '3y', label: '3Y', words: 'three years' },
  { key: '5y', label: '5Y', words: 'five years' },
  { key: 'max', label: 'Max', words: 'its whole record' },
] as const

export type RangeKey = (typeof RANGES)[number]['key']

export function rangeWords(key: string): string {
  return RANGES.find((r) => r.key === key)?.words ?? key
}

export function axisTick(range: string): (iso: string) => string {
  if (range === '1m' || range === '6m') return (iso) => TICK_DAY.format(utc(iso))
  if (range === '1y' || range === '3y') return (iso) => TICK_MONTH.format(utc(iso))
  return (iso) => iso.slice(0, 4)
}

/**
 * Explicit tick positions, one per distinct label.
 *
 * Left to `minTickGap` Recharts picks ticks by pixel spacing, which over a year
 * printed "Nov 25" twice and "Mar 26" twice — two ticks landing in the same
 * month is far enough apart in pixels and identical once formatted. Choosing
 * the first row of each label and thinning that keeps every label unique and
 * the spacing even.
 */
export function axisTicks(
  rows: { date: string }[],
  format: (iso: string) => string,
  most = 8,
): string[] {
  if (rows.length <= most) return rows.map((r) => r.date)
  const stride = (rows.length - 1) / (most - 1)
  const out: string[] = []
  let previous = ''
  for (let i = 0; i < most; i++) {
    const { date } = rows[Math.round(i * stride)]
    const label = format(date)
    // Evenly spaced first, unique second: a repeated label is dropped rather
    // than nudged, so the ticks that remain still sit where they belong.
    if (label === previous) continue
    previous = label
    out.push(date)
  }
  return out
}

/**
 * The plotted range, padded a little.
 *
 * Recharts' `auto` rounds outwards to whole ticks, which over one year turned
 * a series living between 93 and 106 into an axis from 85 to 105 and left the
 * bottom third of the chart empty.
 */
export function paddedDomain(values: number[]): [number, number] {
  const low = Math.min(...values)
  const high = Math.max(...values)
  const pad = Math.max((high - low) * 0.06, 0.5)
  return [low - pad, high + pad]
}

/**
 * Y ticks on round numbers.
 *
 * Given an explicit domain Recharts splits it into equal parts, which over the
 * full record produced an axis reading 45, 295, 545, 795, 999. A gridline is
 * only worth its ink if the number beside it is one a person can hold.
 */
export function niceTicks(low: number, high: number, want = 5): number[] {
  const rough = (high - low) / Math.max(1, want - 1)
  if (!(rough > 0)) return []
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? rough
  const ticks: number[] = []
  for (let v = Math.ceil(low / step) * step; v <= high + step / 1e6; v += step) {
    ticks.push(Number(v.toFixed(6)))
  }
  return ticks
}

/** Enough decimals to tell two ticks apart, and no more. */
export function axisNumber(value: number): string {
  return String(Number(value.toFixed(2)))
}

export type ChartRow = { date: string; own: number | null; peer: number | null }

/**
 * One row per date, from the two series that do not share their dates.
 *
 * Both are thinned to 240 points, but each is thinned from its own set of days
 * — over three years a fund and its category share 142 of 240, and over the
 * full record 18 of 240. Plotting them as parallel arrays would pair the
 * fund's 2013 point with the peers' 2021 one and draw a chart that is simply
 * wrong.
 *
 * So: the union of dates, and each series carried forward across the other's
 * days. Carrying forward, rather than leaving a gap, is what lets the tooltip
 * always answer with both numbers; the gap it fills is one sample wide, which
 * at 240 points across a chart is under three pixels.
 */
export function mergeSeries(
  own: { date: string; value: number }[],
  peer: { date: string; value: number }[],
): ChartRow[] {
  const byDate = new Map<string, ChartRow>()
  for (const p of own) byDate.set(p.date, { date: p.date, own: p.value, peer: null })
  for (const p of peer) {
    const row = byDate.get(p.date)
    if (row) row.peer = p.value
    else byDate.set(p.date, { date: p.date, own: null, peer: p.value })
  }
  const rows = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
  let lastOwn: number | null = null
  let lastPeer: number | null = null
  for (const row of rows) {
    if (row.own === null) row.own = lastOwn
    else lastOwn = row.own
    if (row.peer === null) row.peer = lastPeer
    else lastPeer = row.peer
  }
  return rows
}

export const TOOLTIP_STYLE = {
  background: 'var(--popover)',
  color: 'var(--popover-foreground)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  fontSize: 12,
} as const
