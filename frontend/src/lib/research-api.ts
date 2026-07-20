import { api } from '@/lib/api'

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

export type FundDetail = {
  scheme_code: string
  scheme_name: string
  fund_house: string
  category: string
  is_direct_growth: boolean
  latest_nav: number
  latest_nav_date: string
  metrics: FundMetrics
  nav_series: { date: string; nav: number }[]
}

export type RankedFund = {
  scheme_code: string
  scheme_name: string
  category: string
  score: number
  breakdown: Record<string, number>
  metrics: FundMetrics
}

export type CategoryRanking = {
  asset_class: string
  benchmarked: boolean
  ranked: RankedFund[]
  unscorable: { scheme_code: string; scheme_name: string; reason: string }[]
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

export async function fetchCategoryRanking(assetClass: string): Promise<CategoryRanking> {
  return (await api.get(`/api/v1/research/categories/${assetClass}`)).data
}

export async function fetchFund(schemeCode: string): Promise<FundDetail> {
  return (await api.get(`/api/v1/research/funds/${schemeCode}`)).data
}

export async function fetchStock(ticker: string): Promise<StockFundamentals> {
  return (await api.get(`/api/v1/research/stocks/${ticker}`)).data
}
