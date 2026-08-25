import type { BaseRate } from '@/lib/screener-api'
import { api } from '@/lib/api'

export type AssetType = 'MF' | 'STOCK'

/**
 * Every query whose answer depends on which holdings exist.
 *
 * Listed in one place because it was previously spelled out at each call site
 * and the lists drifted: adding a holding refreshed three of them, deleting one
 * refreshed a different three, and nothing anywhere refreshed the filings. The
 * cost review, the levers and the overlap all kept quoting a fund that had just
 * been deleted until the page was reloaded.
 */
export const PORTFOLIO_QUERY_KEYS = [
  'portfolio',
  'benchmark',
  'history',
  'cost-review',
  'levers',
  'overlap',
  'announcements',
] as const

export type HoldingSummary = {
  holding_id: string
  name: string
  asset_type: AssetType
  identifier: string
  category: string | null
  units_held: number
  invested: number
  current_price: number | null
  current_value: number | null
  /**
   * AMFI's name for this scheme code, set ONLY when it is a different fund
   * from `name`. Non-null means every figure on this row is correct — and
   * correct about something else.
   */
  misnamed_as: string | null
  /** The date this price is actually from. */
  price_as_of: string | null
  /**
   * Days behind the rest of the portfolio. Set only when far enough behind to
   * mean the feed stopped rather than the market being shut for a holiday.
   */
  stale_days: number | null
  unrealised_gain: number | null
  realised_gain: number
  absolute_return: number | null
  xirr: number | null
  price_error: string | null
}

export type PortfolioSummary = {
  holdings: HoldingSummary[]
  total_invested: number
  total_current_value: number
  total_unrealised_gain: number
  total_realised_gain: number
  absolute_return: number
  xirr: number | null
  unpriced_invested: number
  has_pricing_errors: boolean
}

export type BenchmarkComparison = {
  comparable: boolean
  portfolio_value: number
  benchmark_value: number | null
  portfolio_xirr: number | null
  benchmark_xirr: number | null
  outperformance: number | null
  reason: string | null
}

export type NewHolding = {
  name: string
  asset_type: AssetType
  identifier: string
  category?: string | null
}

export type NewTransaction = {
  txn_date: string
  txn_type: 'BUY' | 'SELL'
  units: number
  price: number
}

export async function fetchPortfolio(): Promise<PortfolioSummary> {
  return (await api.get('/api/v1/portfolio')).data
}

export async function fetchBenchmark(): Promise<BenchmarkComparison> {
  return (await api.get('/api/v1/portfolio/benchmark')).data
}

export async function createHolding(body: NewHolding) {
  return (await api.post('/api/v1/portfolio/holdings', body)).data
}

export async function addTransaction(holdingId: string, body: NewTransaction) {
  return (await api.post(`/api/v1/portfolio/holdings/${holdingId}/transactions`, body)).data
}

export async function deleteHolding(holdingId: string) {
  await api.delete(`/api/v1/portfolio/holdings/${holdingId}`)
}

export type HistoryPoint = {
  date: string
  invested: number
  portfolio_value: number
  benchmark_value: number | null
}

export type PortfolioHistory = {
  points: HistoryPoint[]
  /** Holding name -> why it is not in the line. Never silent. */
  excluded: Record<string, string>
  /** What those holdings are worth today, so the gap to the headline is stated. */
  excluded_value: number
}

export async function fetchHistory(): Promise<PortfolioHistory> {
  return (await api.get('/api/v1/portfolio/history')).data
}

export type CostReview = {
  annual_cost: number
  lifetime_cost: number
  flagged: {
    name: string
    value: number
    ter_gap: number
    annual_cost: number
    // The scheme to buy instead, when it can be named with confidence.
    direct_code: string | null
    direct_name: string | null
  }[]
  unpriced: string[]
  summary: string
}

export async function fetchCostReview(yearsRemaining = 15): Promise<CostReview> {
  return (
    await api.get('/api/v1/portfolio/cost-review', {
      params: { years_remaining: yearsRemaining },
    })
  ).data
}

export type Lever = {
  key: string
  title: string
  /** Rupees. Not a fraction, so never formatPercent. */
  annual_value: number
  lifetime_value: number
  detail: string
  action: string
  /**
   * What kind of claim this is. They must not be rendered as one list.
   *
   *   certain   — arithmetic. A fee difference, a slab calculation, an
   *               exemption. The number is the number.
   *   behaviour — sound arithmetic, worth this much only if the person does it.
   *   trade     — buys return by taking risk. Never sorted among the levers.
   *   gate      — earns nothing; prevents a forced sale.
   */
  kind: 'certain' | 'behaviour' | 'trade' | 'gate'
  /**
   * Bottom and top, in rupees, where the value turns on an assumption we cannot
   * pin. `save_more` has a band because it scales WITH the assumed return
   * (₹14.6L at 6%, ₹30.6L at 14%); a cost gap does not, so its band is null.
   */
  low: number | null
  high: number | null
  /** How we know, and how well. */
  evidence: string
  /** What would change this answer. */
  revisit: string
}

export type UnpricedLever = {
  key: string
  title: string
  why: string
  what_we_need: string
}

/**
 * How often a claim of this kind has actually been right.
 *
 * `wins` out of `windows` is the denominator, and it is required rather than
 * optional. Univest prints "Price moved −196.70 (21.23%) since then" under its
 * verdict — one call marked to market, and you cannot tell from it whether that
 * call was typical or their worst. A hit rate without its sample is the same
 * trick with a percentage sign.
 */
export type TrackRecord = {
  key: string
  title: string
  wins: number
  windows: number
  /** 0 to 1, not a percentage. */
  hit_rate: number
  /** Percentage points of forward return a year, top quartile minus bottom. */
  spread_pp: number
  /** False when it is no better than a coin over this sample. */
  beats_chance: boolean
  plain: string
  measured_on: string
}

export type Levers = {
  /** Do these first. They earn nothing and stop a forced sale. */
  gates: Lever[]
  /** Then these, biggest first. */
  levers: Lever[]
  /** Bought with risk. Rendered apart from the levers, always. */
  trades: Lever[]
  /** What we know matters and could not value, with what we would need. */
  unpriced: UnpricedLever[]
  /**
   * What the category holding most of this person's money has done before.
   * Null when nothing could be classified, or the category is too thin for an
   * honest base rate — never a broader category's number in its place.
   */
  base_rate: BaseRate | null
  /** How often the score this app ranks funds on has actually been right. */
  track_record: TrackRecord | null
  /**
   * Said out loud when one of the score's own ingredients beats the score.
   * It currently does: cost alone works 83 times in 100, the composite 61.
   */
  better_signal: string | null
  years_remaining: number
  /** What the figures were built on, echoed back — it may have been clamped. */
  assumed_return: number
  /** What the reader may move it to. Bounded on purpose. */
  return_bounds: number[]
  portfolio_value: number
}

export type Announcements = {
  announcements: {
    symbol: string
    company: string
    category: string
    summary: string
    published: string
    attachment: string | null
  }[]
  // Material filings held back only by the display cap.
  withheld: number
  // Routine filings dropped as noise.
  filtered_out: number
  not_covered: Record<string, string>
}

export async function fetchAnnouncements(): Promise<Announcements> {
  return (await api.get('/api/v1/portfolio/announcements')).data
}

export type Overlap = {
  pairs: {
    a: string
    b: string
    a_name: string
    b_name: string
    correlation: number
    months: number
    /**
     * Share of net assets the two funds hold in the same securities.
     * `null` means unmeasured — one of the AMCs does not publish a portfolio
     * we can read — which is not the same as zero and must not render as 0%.
     */
    common_weight: number | null
    shared_securities: number | null
    /**
     * Which month's disclosure this was read from. AMCs file up to ten days
     * after month end, so in the first week of a month this is the month
     * before last — and the number changes when the new file lands.
     */
    holdings_as_of: string | null
  }[]
  effective_positions: number | null
  counted: number
  excluded: Record<string, string>
  summary: string
}

export async function fetchOverlap(): Promise<Overlap> {
  return (await api.get('/api/v1/portfolio/overlap')).data
}

/**
 * Omitted params are genuinely omitted, not sent as zero: the server falls back
 * to the horizon stored on the profile, and a default sent from here would
 * silently overwrite it.
 */
export async function fetchLevers(params: {
  assumed_return?: number
  liquid_savings?: number
  high_interest_debt?: number
  years_remaining?: number
  monthly_sip?: number
}): Promise<Levers> {
  return (await api.get('/api/v1/portfolio/levers', { params })).data
}

export type FactorEvidence = {
  built_on: string
  source: { name: string; url: string; note: string }
  period: { from: string; to: string; months: number }
  factors: {
    code: string
    name: string
    plain: string
    annual_return: number
    t_stat: number
    months: number
    significant: boolean
    episodes: { label: string; annual_return: number; t_stat: number }[]
  }[]
  momentum_curve: { date: string; value: number }[]
}

export async function fetchFactorEvidence(): Promise<FactorEvidence> {
  return (await api.get('/api/v1/research/evidence')).data
}

export type MomentumRanking = {
  index: string
  measured_from: string
  measured_to: string
  ranked: {
    rank: number
    symbol: string
    name: string
    industry: string | null
    momentum: number
    band: string
  }[]
  considered: number
  /** Named, not just counted, so a symbol you hold is findable here. */
  unranked: string[]
  /** What the same measurement lost through the 2009 rebound. */
  rebound_loss: number
}

export async function fetchMomentum(limit = 60): Promise<MomentumRanking> {
  return (await api.get('/api/v1/research/momentum', { params: { limit } })).data
}
