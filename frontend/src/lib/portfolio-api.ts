import { api } from '@/lib/api'

export type AssetType = 'MF' | 'STOCK'

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

export async function fetchHistory(): Promise<HistoryPoint[]> {
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
  annual_value: number
  lifetime_value: number
  detail: string
  action: string
}

export type Levers = {
  levers: Lever[]
  years_remaining: number
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
  years_remaining?: number
  monthly_sip?: number
}): Promise<Levers> {
  return (await api.get('/api/v1/portfolio/levers', { params })).data
}
