import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Login } from '@/pages/Login'
import { AuthCallback } from '@/pages/AuthCallback'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ThemeToggle } from '@/components/ThemeToggle'
import { clearToken, isAuthenticated } from '@/lib/auth'
import { cn } from '@/lib/utils'

// Split per route. The charting library alone is most of the bundle and it is
// only ever drawn on three of these pages, but every user was downloading it
// before the first paint — including somebody on a phone who has not added a
// holding yet and will see no chart at all. Login stays eager: it is the first
// thing an unauthenticated visitor needs and there is nothing to defer.
const Portfolio = lazy(() => import('@/pages/Portfolio').then((m) => ({ default: m.Portfolio })))
const Research = lazy(() => import('@/pages/Research').then((m) => ({ default: m.Research })))
const Goals = lazy(() => import('@/pages/Goals').then((m) => ({ default: m.Goals })))
const GoalNew = lazy(() => import('@/pages/GoalNew').then((m) => ({ default: m.GoalNew })))
const GoalDetail = lazy(() => import('@/pages/GoalDetail').then((m) => ({ default: m.GoalDetail })))
const Profile = lazy(() => import('@/pages/Profile').then((m) => ({ default: m.Profile })))

const queryClient = new QueryClient()

/** Shaped like the page headers behind it, so the swap is not a jolt. */
function RouteFallback() {
  return (
    <div className="flex flex-col gap-8">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-56 w-full" />
    </div>
  )
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

const NAV = [
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/research', label: 'Research' },
  { to: '/goals', label: 'Goals' },
  { to: '/profile', label: 'You' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const signedIn = isAuthenticated()

  return (
    <div className="min-h-svh bg-background text-foreground">
      {/* Two rows on a phone, one on a laptop. Everything used to sit on a
          single row, which pushed 555px of header through a 390px screen and
          made every page in the app scroll sideways. */}
      <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex max-w-6xl flex-col px-4 sm:h-14 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6">
          <div className="flex h-14 items-center justify-between gap-4 sm:h-auto sm:justify-start sm:gap-8">
            <NavLink
              to={signedIn ? '/portfolio' : '/login'}
              className="py-2 text-sm font-semibold tracking-tight"
            >
              NexTrade
            </NavLink>
            <div className="flex items-center gap-1">
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
          {signedIn && (
            // Scrolls rather than wraps: a nav that reflows to two lines moves
            // the page content down by a row on exactly the screens with the
            // least of it.
            <nav className="-mx-4 flex items-center gap-1 overflow-x-auto px-4 pb-2 sm:mx-0 sm:overflow-visible sm:px-0 sm:pb-0">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'shrink-0 rounded-md px-2.5 py-2 text-sm transition-colors',
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
          <Suspense fallback={<RouteFallback />}>
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
              path="/goals"
              element={
                <RequireAuth>
                  <Goals />
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
          </Suspense>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
