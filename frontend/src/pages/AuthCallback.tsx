import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { setToken } from '@/lib/auth'

export function AuthCallback() {
  const [params] = useSearchParams()
  const navigate = useNavigate()

  useEffect(() => {
    const token = params.get('token')
    if (token) {
      setToken(token)
      navigate('/goals/new', { replace: true })
    } else {
      navigate('/login', { replace: true })
    }
  }, [params, navigate])

  return <div className="px-4 py-20 text-center text-muted-foreground">Signing you in…</div>
}
