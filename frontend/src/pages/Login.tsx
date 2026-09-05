import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { setToken } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'

export function Login() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRedirecting, setIsRedirecting] = useState(false)

  async function loginWithPassword(loginEmail: string, loginPassword: string) {
    const body = new URLSearchParams()
    body.set('username', loginEmail)
    body.set('password', loginPassword)
    const { data } = await api.post('/api/v1/auth/jwt/login', body)
    setToken(data.access_token)
    // The dashboard, not a form. Signing in used to land on `/goals/new`,
    // which asks a brand-new user to name a target amount and a date before
    // anything has shown them what the product does. An empty `/portfolio`
    // already renders `StartHere` -- the same onboarding, in the order the
    // steps are actually worth money, with setting a goal as one of them.
    navigate('/portfolio', { replace: true })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      if (mode === 'register') {
        await api.post('/api/v1/auth/register', { email, password, name })
      }
      await loginWithPassword(email, password)
    } catch (err: any) {
      setError(err.response?.data?.detail ?? 'Something went wrong. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function signInWithGoogle() {
    setIsRedirecting(true)
    try {
      const { data } = await api.get('/api/v1/auth/google/authorize')
      window.location.href = data.authorization_url
    } catch {
      setIsRedirecting(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col items-center justify-center px-4 py-20">
      <Card className="w-full">
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Welcome to NexTrade</CardTitle>
          <CardDescription>
            {mode === 'login' ? 'Sign in to see your goals and plans.' : 'Create your account.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
            {mode === 'register' && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" size="lg" disabled={isSubmitting}>
              {isSubmitting
                ? 'Please wait…'
                : mode === 'login'
                  ? 'Log in'
                  : 'Create account'}
            </Button>
          </form>

          <button
            type="button"
            className="-my-2 py-2 text-sm text-muted-foreground underline-offset-4 hover:underline"
            onClick={() => {
              setError(null)
              setMode(mode === 'login' ? 'register' : 'login')
            }}
          >
            {mode === 'login' ? "Don't have an account? Create one" : 'Already have an account? Log in'}
          </button>

          <Separator />

          <Button
            className="w-full"
            variant="outline"
            size="lg"
            onClick={signInWithGoogle}
            disabled={isRedirecting}
          >
            {isRedirecting ? 'Redirecting to Google…' : 'Sign in with Google'}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
