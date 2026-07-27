import { api } from '@/lib/api'

export type FundEvidence = {
  history_years: number | null
  evidence_strength: number
  windows: Record<string, Window>
  direct_ter: number | null
  regular_ter: number | null
}

export type FundDetail = {
  scheme_code: string
  scheme_name: string
  fund_house: string
  category: string
  is_direct_growth: boolean
  latest_nav: number
  latest_nav_date: string
  metrics: FundMetrics
  evidence: FundEvidence | null
  nav_series: { date: string; nav: number }[]
}

export type StockFundamentals = {
  ticker: string
  name: string
  price: number
  previous_close: number | null
  currency: string
  day_change_pct: number | null
  sector: string | null
  industry: string | null
  market_cap: number | null
  pe_ratio: number | null
  eps: number | null
  book_value: number | null
  dividend_yield_pct: number | null
  week52_high: number | null
  week52_low: number | null
}


export async function fetchFund(schemeCode: string): Promise<FundDetail> {
  return (await api.get(`/api/v1/research/funds/${schemeCode}`)).data
}

export async function fetchStock(ticker: string): Promise<StockFundamentals> {
  return (await api.get(`/api/v1/research/stocks/${ticker}`)).data
}

export type UniverseStock = {
  ticker: string
  symbol: string
  name: string
  industry: string | null
  indices: string[]
}

export type StockUniverse = {
  stocks: UniverseStock[]
  total: number
  available_indices: string[]
  available_industries: string[]
}

export async function fetchStockUniverse(params: {
  index?: string
  industry?: string
  q?: string
  limit?: number
}): Promise<StockUniverse> {
  return (await api.get('/api/v1/research/stocks', { params })).data
}

export async function fetchFundCategories(): Promise<string[]> {
  return (await api.get('/api/v1/research/fund-categories')).data
}


/** Still returned by the fund-detail endpoint; the panel uses volatility and
 * the worst fall from it. The ranking itself no longer reads any of it. */
export type FundMetrics = {
  cagr_1y: number | null
  cagr_3y: number | null
  cagr_5y: number | null
  volatility: number | null
  sortino: number | null
  max_drawdown: number | null
  alpha: number | null
  downside_capture: number | null
  consistency: number | null
}

export type Window = {
  mean: number
  worst: number
  share_positive: number
  count: number
}

export type Verdict = {
  headline: string
  points: string[]
  caveat: string | null
}

export type RankedFundV2 = {
  rank: number
  scheme_code: string
  scheme_name: string
  category: string
  score: number
  breakdown: Record<string, number>
  evidence_strength: number
  history_years: number | null
  windows: Record<string, Window>
  volatility: number | null
  max_drawdown: number | null
  direct_ter: number | null
  regular_ter: number | null
  verdict: Verdict
}

export type CategoryRankingV2 = {
  category: string
  ranked: RankedFundV2[]
  unscorable: { scheme_code: string; scheme_name: string; reason: string }[]
  priced: number
}

export async function fetchCategoryRankingV2(
  category: string,
  params: { monthly_sip?: number; years?: number } = {},
): Promise<CategoryRankingV2> {
  return (
    await api.get(`/api/v1/research/fund-rankings/${encodeURIComponent(category)}`, {
      params,
    })
  ).data
}

export type StockScore = {
  ticker: string
  name: string
  sector: string | null
  benchmark_used: string
  base_total: number
  adjustment_total: number
  total: number
  factors: Record<string, { score: number; detail: string }>
  adjustments: { name: string; points: number; detail: string }[]
  range_position: number | null
  verdict: Verdict
}

export async function fetchStockScore(ticker: string): Promise<StockScore> {
  return (await api.get(`/api/v1/research/stocks/${ticker}/score`)).data
}
