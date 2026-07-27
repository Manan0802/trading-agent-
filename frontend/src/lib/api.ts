import axios from 'axios'
import { clearToken, getToken } from '@/lib/auth'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
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
  years_to_goal: number | null
  tax: TaxComparison | null
}

export async function fetchProfile(): Promise<Profile> {
  return (await api.get('/api/v1/profile')).data
}

export async function saveProfile(patch: Partial<Profile>): Promise<Profile> {
  return (await api.patch('/api/v1/profile', patch)).data
}
