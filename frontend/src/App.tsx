import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GoalNew } from '@/pages/GoalNew'
import { GoalDetail } from '@/pages/GoalDetail'
import { Login } from '@/pages/Login'
import { AuthCallback } from '@/pages/AuthCallback'
import { Portfolio } from '@/pages/Portfolio'
import { Profile } from '@/pages/Profile'
import { Research } from '@/pages/Research'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
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
  { to: '/research', label: 'Research' },
  { to: '/goals/new', label: 'New goal' },
  { to: '/profile', label: 'You' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const signedIn = isAuthenticated()

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-8">
            <NavLink
              to={signedIn ? '/portfolio' : '/login'}
              className="text-sm font-semibold tracking-tight"
            >
              NexTrade
            </NavLink>
            {signedIn && (
              <nav className="flex items-center gap-1">
                {NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        'rounded-md px-2.5 py-1.5 text-sm transition-colors',
                        isActive
                          ? 'bg-secondary font-medium text-foreground'
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
          <div className="flex items-center gap-2">
            <ThemeToggle />
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
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
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
              path="/research"
              element={
                <RequireAuth>
                  <Research />
                </RequireAuth>
              }
            />
            <Route
              path="/profile"
              element={
                <RequireAuth>
                  <Profile />
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
