import axios from 'axios'
import { clearToken, getToken } from '@/lib/auth'

// The free host sleeps after fifteen minutes idle and takes about a minute to
// wake. For an app opened a few times a week that makes the cold start the
// MODAL experience, not an edge case -- and this client had no timeout at all,
// so a waking container looked exactly like a hung one. Ninety seconds is the
// wake plus headroom; past that something is actually wrong.
const WAKE_TIMEOUT_MS = 90_000

// A request slower than this is almost certainly waiting on a sleeping
// container rather than on work. Subscribers use it to show the waking state
// instead of a skeleton, because §13.5's "skeletons, no spinner" rule is the
// worst available presentation of a sixty-second wait: a skeleton promises
// data is arriving now.
const WAKING_AFTER_MS = 2_000

type WakingListener = (waking: boolean) => void
const wakingListeners = new Set<WakingListener>()
let inFlight = 0
let wakingTimer: ReturnType<typeof setTimeout> | null = null

/** Called when the app is probably waiting on a cold container, and when it stops. */
export function onWaking(listener: WakingListener): () => void {
  wakingListeners.add(listener)
  return () => wakingListeners.delete(listener)
}

function announce(waking: boolean) {
  for (const listener of wakingListeners) listener(waking)
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
  withCredentials: true,
  timeout: WAKE_TIMEOUT_MS,
  timeoutErrorMessage:
    'The server did not answer within 90 seconds. It may still be waking.',
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (inFlight === 0 && wakingTimer === null) {
    wakingTimer = setTimeout(() => announce(true), WAKING_AFTER_MS)
  }
  inFlight += 1
  return config
})

function settled() {
  inFlight = Math.max(0, inFlight - 1)
  if (inFlight === 0) {
    if (wakingTimer !== null) {
      clearTimeout(wakingTimer)
      wakingTimer = null
    }
    announce(false)
  }
}

api.interceptors.response.use(
  (response) => {
    settled()
    return response
  },
  (error) => {
    settled()
    if (error.response?.status === 401) {
      clearToken()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export type TaxComparison = {
  recommended: 'new' | 'old'
  new_regime_tax: number
  old_regime_tax: number
  saving: number
  breakeven_deductions: number | null
  rationale: string
}

export type Profile = {
  annual_income: number | null
  basic_salary: number | null
  monthly_expenses: number | null
  is_salaried: boolean
  existing_80c: number
  existing_80d: number
  other_deductions: number
  current_tax_regime: 'new' | 'old'
  years_to_goal: number | null
  tax: TaxComparison | null
}

export async function fetchProfile(): Promise<Profile> {
  return (await api.get('/api/v1/profile')).data
}

export async function saveProfile(patch: Partial<Profile>): Promise<Profile> {
  return (await api.patch('/api/v1/profile', patch)).data
}
