import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GoalNew } from '@/pages/GoalNew'
import { GoalDetail } from '@/pages/GoalDetail'
import { Login } from '@/pages/Login'
import { AuthCallback } from '@/pages/AuthCallback'
import { Portfolio } from '@/pages/Portfolio'
import { Button } from '@/components/ui/button'
import { clearToken, isAuthenticated } from '@/lib/auth'
import { cn } from '@/lib/utils'

const queryClient = new QueryClient()

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

const NAV = [
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/goals/new', label: 'New goal' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const signedIn = isAuthenticated()

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <NavLink to={signedIn ? '/portfolio' : '/login'} className="text-base font-semibold">
              NexTrade
            </NavLink>
            {signedIn && (
              <nav className="flex items-center gap-4">
                {NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        'text-sm transition-colors',
                        isActive
                          ? 'font-medium text-foreground'
                          : 'text-muted-foreground hover:text-foreground',
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            )}
          </div>
          {signedIn && (
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
            <Route path="/" element={<Navigate to="/portfolio" replace />} />
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route
              path="/portfolio"
              element={
                <RequireAuth>
                  <Portfolio />
                </RequireAuth>
              }
            />
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
