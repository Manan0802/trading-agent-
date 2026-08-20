import { api } from '@/lib/api'

/**
 * The fund screener: the whole scored universe, ranked on its record.
 *
 * UNITS, because getting this wrong is silent. Every `returns_*`, `rolling_*`,
 * plus `volatility`, `max_drawdown` and `worst_30d` is a FRACTION — 0.126 means
 * 12.6% — so they go straight to formatPercent, which multiplies by 100 itself.
 * `sortino` is a bare ratio. `fund_score`, `peer_median`, `momentum_signal`,
 * `drawdown_signal` and `risk_score` all run 0 to 1 and are turned into a score
 * out of 100 in exactly one place (Screener's `score100`).
 */

export type ScreenerReason = {
  kind: string
  label: string
  value: number
  unit: string
  peer_group: string | null
  /** A pre-written sentence. Render it as-is. */
  text: string
}

export type ScreenedFund = {
  scheme_code: string
  name: string
  fund_house: string
  category: string
  sub_category: string
  asset_class: string
  /** Rank across the whole scored universe. 0 for a fund too new to rank. */
  rank: number
  category_rank: number
  fund_score: number
  grade: string | null
  peer_median: number | null
  peer_size: number | null
  returns_1m: number | null
  returns_3m: number | null
  returns_6m: number | null
  returns_1y: number | null
  returns_3y: number | null
  rolling_1m: number | null
  rolling_3m: number | null
  rolling_6m: number | null
  rolling_1y: number | null
  rolling_3y: number | null
  sortino: number | null
  volatility: number | null
  max_drawdown: number | null
  worst_30d: number | null
  momentum_signal: number | null
  drawdown_signal: number | null
  risk_score: number | null
  risk_tier: string | null
  history_years: number | null
  nav_rows: number
  is_new: boolean
  reasons: ScreenerReason[]
}

export type ScreenerCoverage = {
  universe: number
  scored: number
  shown: number
  new_funds: number
  categories_total: number
  categories_ranked: number
  thin_categories: { category: string; sub_category: string; peer_size: number }[]
  unscorable: { scheme_code: string; reason: string }[]
  missing_columns: string[]
  as_of: string
  stale_days: number
}

export type ScreenerCategory = {
  category: string
  sub_category: string
  asset_class: string
  peer_size: number
  rankable: boolean
  caveat: string | null
}

export type ScreenerCategories = {
  categories: ScreenerCategory[]
  asset_classes: string[]
  grades: string[]
  risk_tiers: string[]
  coverage: ScreenerCoverage
}

export type ScreenerGroup = {
  category: string
  sub_category: string
  asset_class: string
  peer_size: number
  caveat: string | null
  funds: ScreenedFund[]
}

/** How much of the top of the leaderboard one kind of fund has taken. */
export type ScreenerDominance = {
  asset_class: string
  sub_category: string
  count: number
  of: number
  share: number
  lift: number
}

export type ScreenerTopFunds = {
  groups: ScreenerGroup[]
  new_funds: ScreenedFund[]
  dominance: ScreenerDominance[]
  coverage: ScreenerCoverage
}

export type ScreenerAllFunds = {
  funds: ScreenedFund[]
  new_funds: ScreenedFund[]
  coverage: ScreenerCoverage
}

export type ScreenerFilters = {
  category?: string
  asset_class?: string
  grade?: string
  risk_tier?: string
}

/**
 * An empty string is not "no filter" to this API — `?category=` is a 404, which
 * the browser sweep counts as a failure. Blank values are dropped here rather
 * than at every call site.
 */
function live(params: Record<string, string | number | boolean | undefined>) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== ''),
  )
}

export async function fetchScreenerCategories(): Promise<ScreenerCategories> {
  return (await api.get('/api/v1/screener/categories')).data
}

export async function fetchTopFunds(
  filters: ScreenerFilters & { per_category?: number },
): Promise<ScreenerTopFunds> {
  return (await api.get('/api/v1/screener/top-funds', { params: live(filters) })).data
}

export async function fetchAllFunds(
  filters: ScreenerFilters & { include_new?: boolean },
): Promise<ScreenerAllFunds> {
  return (await api.get('/api/v1/screener/funds', { params: live(filters) })).data
}
