import { useState } from 'react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function Login() {
  const [isRedirecting, setIsRedirecting] = useState(false)

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
          <CardDescription>Sign in to see your goals and plans.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            className="w-full"
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
