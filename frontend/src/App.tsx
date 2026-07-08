import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GoalNew } from '@/pages/GoalNew'
import { GoalDetail } from '@/pages/GoalDetail'
import { Login } from '@/pages/Login'
import { AuthCallback } from '@/pages/AuthCallback'
import { Button } from '@/components/ui/button'
import { clearToken, isAuthenticated } from '@/lib/auth'

const queryClient = new QueryClient()

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to="/goals/new" className="text-base font-semibold">
            NexTrade
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">Financial Advisor</span>
            {isAuthenticated() && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  clearToken()
                  window.location.href = '/login'
                }}
              >
                Sign out
              </Button>
            )}
          </div>
        </div>
      </header>
      {children}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/goals/new" replace />} />
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route
              path="/goals/new"
              element={
                <RequireAuth>
                  <GoalNew />
                </RequireAuth>
              }
            />
            <Route
              path="/goals/:id"
              element={
                <RequireAuth>
                  <GoalDetail />
                </RequireAuth>
              }
            />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
