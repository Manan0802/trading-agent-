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

/* --------------------------------------------------------------- stocks */

/**
 * The stock screener: a different model on a different scale.
 *
 * UNITS, and they are NOT the fund units above. `total`, `fundamental`,
 * `technical`, and a factor's `max` and `score` are all POINTS OUT OF 100 —
 * 55.92 means 55.92 points, not 5,592%. None of them may go near
 * formatPercent. `pct` is already 0 to 100. `price` is rupees. There is no
 * fraction anywhere on a stock row.
 */
export type StockFactor = {
  key: string
  label: string
  category: 'fundamental' | 'technical'
  /** This factor's weight, in points out of the 100. */
  max: number
  /** What it scored, out of `max`. */
  score: number
  /** score/max, already expressed 0 to 100. */
  pct: number
  /** A pre-written sentence, "PE 28.1 vs sector median 42". Render it as-is. */
  detail: string
  /**
   * What the factor measures, in words. `detail` is compared character for
   * character against the source method by the backend's parity tests and so
   * cannot be reworded — "Death Cross" is theirs. This explains the term
   * rather than the number, which is why it is the same for every company.
   */
  plain: string | null
}

export type StockAdjustment = {
  key: string
  label: string
  /** Can be 0: several of these are informational rows, not scoring events. */
  points: number
  detail: string
  type: string
}

export type ScoredStock = {
  ticker: string
  symbol: string
  name: string
  sector: string | null
  industry: string | null
  /** Points out of 100. */
  total: number
  bucket: string
  /** The two halves of the total, each out of the 50 points its factors carry. */
  fundamental: number
  technical: number
  /** Rupees. */
  price: number | null
  factors: StockFactor[]
  adjustments: StockAdjustment[]
  /** No 200-day average, so its trend factor is measured against a shorter one. */
  thin_history: boolean
  /** Which peer group the valuation factors compared against — not always `sector`. */
  benchmark_sector: string
  benchmark_constituents: number
}

export type StockCoverage = {
  index: string
  /** Companies in the index. */
  matched: number
  /** Companies actually shown, after the limit and the bucket filter. */
  scored: number
  unscorable: { ticker: string; symbol: string; name: string; reason: string }[]
  thin_history: number
  benchmark_stocks: number
  /** Factors every stock scores identically on, so they separate nobody. */
  neutral_factors: string[]
  /** How much of the 100 points is momentum, which our own scorer excludes. */
  method_note: string
}

export type StockScreen = {
  stocks: ScoredStock[]
  buckets: string[]
  industries: string[]
  indices: string[]
  coverage: StockCoverage
}

export type StockFilters = {
  index?: string
  industry?: string
  bucket?: string
  limit?: number
}

/** Same 404-on-blank rule as the funds endpoints, so the same `live` applies. */
export async function fetchScreenedStocks(filters: StockFilters): Promise<StockScreen> {
  return (await api.get('/api/v1/screener/stocks', { params: live(filters) })).data
}

/* -------------------------------------------------------------- baskets */

/**
 * The two model baskets: a fixed set of sleeves, each filled by the best-scoring
 * fund that fits it, then weighted by an optimiser ported from the reference
 * implementation.
 *
 * UNITS, and they are the FUND units, not the stock ones above. `weight`,
 * `weight_within_bounds`, `cap_asked` and `cap_applied` are all FRACTIONS —
 * 0.405 means 40.5% — so they go to formatPercent, which multiplies by 100
 * itself. `score` is the same 0-to-1 fund score the funds tab shows, so it goes
 * through Screener's `score100`. `pool_size` is a count of funds.
 */
export type BasketSlot = {
  /** The sleeve's key, e.g. "Commodity::Gold". Quoted verbatim by `notes`. */
  slot_key: string
  /** The sleeve in plain words. `slot_key` carries the reference's own
   *  punctuation (`Flexi / Multi::Flexi Cap Fund`); the optimiser's notes quote
   *  this label too, so the table and its notes name the same thing. */
  label: string
  /** Null when nothing eligible could fill the sleeve; `reason` says why. */
  scheme_code: string | null
  name: string | null
  category: string | null
  score: number | null
  /**
   * What the basket actually holds, AFTER a momentum overlay that renormalises
   * without re-checking the caps. So this one CAN sit above `cap_applied`.
   */
  weight: number | null
  /** What the optimiser itself agreed to, before that overlay. Never above the cap. */
  weight_within_bounds: number | null
  /** What the sleeve asked for, and what the optimiser could actually enforce. */
  cap_asked: number
  cap_applied: number
  /** How many funds competed for this sleeve. "Best of 2" is not "best of 90". */
  pool_size: number
  /** A pre-written sentence. Render it as-is. */
  caveat: string | null
  /** A pre-written sentence, present when the sleeve holds nothing. */
  reason: string | null
}

export type Basket = {
  basket_id: string
  name: string
  strategy: string
  regime: string
  slots: BasketSlot[]
  /** How many of `slots` found a fund. */
  /** Sleeves that found a fund. */
  filled: number
  /** Sleeves that actually got money. Lower than `filled` when the optimiser
   *  picks a fund and then allocates it 0% — which MAXX's gold sleeve does. */
  allocated: number
  success: boolean
  as_of: string | null
  /** Per-run findings, already written as sentences. Render as-is. */
  notes: string[]
  /** The standing disclosures, the same three on every response. Render as-is. */
  method_notes: string[]
}

export type BasketFilters = {
  strategy?: string
  regime?: string
}

/** Same 404-on-blank rule as every other screener endpoint, so the same `live`. */
export async function fetchBaskets(filters: BasketFilters): Promise<{ baskets: Basket[] }> {
  return (await api.get('/api/v1/screener/baskets', { params: live(filters) })).data
}

/* --------------------------------------------------- one fund's own page */

/**
 * Everything the fund page draws, in one request.
 *
 * UNITS, and this one response mixes three of them, which is the whole reason
 * this comment exists:
 *
 *   `nav` and `peer_median` are INDEX POINTS, rebased to 100 at the window's
 *   start. 183.2 means ₹100 became ₹183.20. They are not fractions and not
 *   percentages, so formatPercent would render "+18320%".
 *
 *   `drawdown` is ALREADY PERCENT. -24.3 means 24.3% below the running peak.
 *   Also not a fraction, so also never formatPercent.
 *
 *   `total_return`, `peer_total_return`, every field on `rolling_1y`, and
 *   every `returns_*` / `rolling_*` / `volatility` / `max_drawdown` on `fund`
 *   ARE fractions, and those are the ones formatPercent is for.
 *
 * The path sits under `/api/v1/screener/funds`, which is on the rate limiter's
 * HEAVY tier at 20 requests a minute per user. Six range buttons is six
 * requests, so nothing here may prefetch or poll.
 */
export type ChartPoint = {
  date: string
  value: number
}

export type RollingReturns = {
  /** How many entry dates were available. 0 for a fund younger than the window. */
  windows: number
  window_days: number
  best: number | null
  worst: number | null
  median: number | null
  positive_share: number | null
}

export type FundAnalysisData = {
  scheme_code: string
  name: string
  category: string
  sub_category: string | null
  range: string
  ranges: string[]
  /** The first and last day actually plotted, not the window that was asked for. */
  start: string | null
  end: string | null

  nav: ChartPoint[]
  /** The fund's own category median. Empty when the category is too thin to have one. */
  peer_median: ChartPoint[]
  drawdown: ChartPoint[]

  total_return: number | null
  peer_total_return: number | null
  peers_compared: number
  /**
   * True when the fund's first NAV in the window is later than the window's
   * start. That includes the harmless case where the window began on a Sunday,
   * so the page checks `first_nav_date` before it says anything alarming.
   */
  clipped_to_fund_history: boolean

  /** The fund's first published NAV ever, not the first one in this window. */
  first_nav_date: string | null
  latest_nav: number | null
  latest_nav_date: string | null
  nav_points_available: number

  rolling_1y: RollingReturns
  /** The whole ranked row, so the page needs no second request. */
  fund: ScreenedFund
}

export async function fetchFundAnalysis(
  schemeCode: string,
  range: string,
): Promise<FundAnalysisData> {
  return (
    await api.get(
      `/api/v1/screener/funds/${encodeURIComponent(schemeCode)}/analysis`,
      { params: { range } },
    )
  ).data
}

/* -------------------------------------------------- one company's own page */

/**
 * Everything the stock page draws, in one request.
 *
 * UNITS, which differ from the fund page's:
 *
 *   `price_series` and `sector_series` are INDEX POINTS rebased to 100 at the
 *   window's start, same as the fund page's `nav`. Never formatPercent.
 *
 *   Every `ratios[].value` and `ratios[].sector_median` is in the unit the
 *   ratio is normally quoted in — P/E and P/B are multiples, ROE and dividend
 *   yield are ALREADY PERCENT (14.4 means 14.4%). None of them is a fraction.
 *
 *   `position_in_52w` IS a fraction, 0 at the year's low and 1 at its high.
 *
 *   `day_change_pct` is already percent. `market_cap` is rupees.
 *
 * The path sits under `/api/v1/screener/stocks`, so it shares the fund page's
 * heavy-tier budget of 20 requests a minute. Six range buttons is six
 * requests: nothing here may prefetch or poll.
 */
export type RatioVsSector = {
  /** One of `pe`, `pb`, `roe`, `div_yield`. */
  key: string
  label: string
  value: number | null
  /** The true median across this sector in traa's own universe, not an index. */
  sector_median: number | null
  /** Reads naturally after the company's name: "cheaper than its sector". */
  verdict: string | null
  /**
   * Whether the comparison favours this company. Direction is per-ratio: a low
   * P/E is good news and a low ROE is not, so this cannot be derived from the
   * two numbers alone.
   */
  better: boolean | null
}

export type SimilarStock = {
  ticker: string
  symbol: string
  name: string
  price: number | null
  pe: number | null
  market_cap: number | null
}

export type StockAnalysisData = {
  ticker: string
  symbol: string
  name: string
  sector: string | null
  industry: string | null

  price: number | null
  previous_close: number | null
  day_change_pct: number | null
  day_low: number | null
  day_high: number | null
  week52_low: number | null
  week52_high: number | null
  /** 0 at the year's low, 1 at its high. Null when the year has no range. */
  position_in_52w: number | null
  volume: number | null
  market_cap: number | null

  range: string
  ranges: string[]
  price_series: ChartPoint[]
  /** The sector's median company. Empty when too few peers priced to take one. */
  sector_series: ChartPoint[]
  peers_compared: number

  ratios: RatioVsSector[]
  similar: SimilarStock[]
  /**
   * The group `similar` was drawn from. Not `industry`: that comes from the
   * fundamentals feed and is granular ("Banks - Regional"), while the peer
   * list is built from the universe's broader grouping ("Financial
   * Services"). Labelling the list with the wrong one claims six regional
   * banks when two of them are insurers.
   */
  similar_group: string | null
  benchmark_sector: string
  benchmark_constituents: number

  /** Null when the company is too new to score. */
  score: ScoredStock | null
  /** Keyed sentences: position, valuation, quality, dividend, size, score. */
  plain: Record<string, string>
}

export async function fetchStockAnalysis(
  ticker: string,
  range: string,
): Promise<StockAnalysisData> {
  return (
    await api.get(
      `/api/v1/screener/stocks/${encodeURIComponent(ticker)}/analysis`,
      { params: { range } },
    )
  ).data
}
