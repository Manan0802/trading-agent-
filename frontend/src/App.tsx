import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Login } from '@/pages/Login'
import { AuthCallback } from '@/pages/AuthCallback'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { CommandPalette } from '@/components/CommandPalette'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Trail, TrailProvider } from '@/components/Trail'
import { WakingNotice } from '@/components/WakingNotice'
import { clearToken, isAuthenticated } from '@/lib/auth'
import { cn } from '@/lib/utils'

// Split per route. The charting library alone is most of the bundle and it is
// only ever drawn on three of these pages, but every user was downloading it
// before the first paint — including somebody on a phone who has not added a
// holding yet and will see no chart at all. Login stays eager: it is the first
// thing an unauthenticated visitor needs and there is nothing to defer.
const Portfolio = lazy(() => import('@/pages/Portfolio').then((m) => ({ default: m.Portfolio })))
const Holdings = lazy(() => import('@/pages/Holdings').then((m) => ({ default: m.Holdings })))
const Research = lazy(() => import('@/pages/Research').then((m) => ({ default: m.Research })))
const Why = lazy(() => import('@/pages/Why').then((m) => ({ default: m.Why })))
const Screener = lazy(() => import('@/pages/Screener').then((m) => ({ default: m.Screener })))
const Decide = lazy(() => import('@/pages/Decide').then((m) => ({ default: m.Decide })))
const FundAnalysis = lazy(() =>
  import('@/pages/FundAnalysis').then((m) => ({ default: m.FundAnalysis })),
)
const StockAnalysis = lazy(() =>
  import('@/pages/StockAnalysis').then((m) => ({ default: m.StockAnalysis })),
)
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

// The six real destinations. One list, so the top nav and ⌘K cannot drift
// apart -- a palette that reaches five of six is worse than none, because the
// missing one is the one somebody will hunt for.
const NAV = [
  { to: '/portfolio', label: 'Portfolio', hint: 'how you are doing' },
  { to: '/portfolio/holdings', label: 'Holdings', hint: 'every position, with cost and XIRR' },
  { to: '/research', label: 'Research', hint: 'what has been shown to work' },
  { to: '/why', label: 'Why', hint: 'where every number comes from' },
  { to: '/decide', label: 'Decide', hint: 'the levers worth pulling' },
  { to: '/screener', label: 'Screener', hint: 'find a fund' },
  { to: '/goals', label: 'Goals', hint: 'what you are saving for' },
  { to: '/profile', label: 'You', hint: 'tax regime, settings' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const signedIn = isAuthenticated()

  return (
    <TrailProvider>
    <div className="min-h-svh bg-background text-foreground">
      {/* Two rows on a phone, one on a laptop. Everything used to sit on a
          single row, which pushed 555px of header through a 390px screen and
          made every page in the app scroll sideways. */}
      <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex max-w-[100rem] flex-col px-4 sm:h-14 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6">
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
                      // min-h-11 is 44px, the smallest target a thumb hits
                      // reliably. Without it the links measured 16px tall on a
                      // phone once the nav gained a seventh item and started
                      // scrolling — a link you cannot tap is not navigation.
                      'flex shrink-0 items-center rounded-md px-2.5 py-2 text-sm',
                      'min-h-11 transition-colors',
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
      {/* Wider than a reading column: a dashboard's job is to put several
          answers in one glance, and 6xl forced the panels into a single stack
          on every screen size anyone actually uses. */}
      <main className="mx-auto flex max-w-[100rem] flex-col gap-4 px-4 py-8 sm:px-6 sm:py-10">
        {/* Above the page, not inside it: the server is waking for every
            request on the page, not for one panel. */}
        <WakingNotice />
        {/* Renders nothing on a top-level page: one crumb is not a trail, and a
            stray word above the heading reads as a mistake. */}
        {signedIn && <Trail />}
        {children}
      </main>
      {signedIn && <CommandPalette destinations={NAV} />}
    </div>
    </TrailProvider>
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
            {/* One level down, deliberately. `/` redirects to `/portfolio`, so
                that route is the app's front door and answers "how am I doing";
                the list is where you go to add a purchase or correct a unit
                count, which is a task rather than a glance. */}
            <Route
              path="/portfolio/holdings"
              element={
                <RequireAuth>
                  <Holdings />
                </RequireAuth>
              }
            />
            <Route
              path="/why"
              element={
                <RequireAuth>
                  <Why />
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
              path="/decide"
              element={
                <RequireAuth>
                  <Decide />
                </RequireAuth>
              }
            />
            <Route
              path="/screener"
              element={
                <RequireAuth>
                  <Screener />
                </RequireAuth>
              }
            />
            <Route
              path="/screener/fund/:schemeCode"
              element={
                <RequireAuth>
                  <FundAnalysis />
                </RequireAuth>
              }
            />
            <Route
              path="/screener/stock/:ticker"
              element={
                <RequireAuth>
                  <StockAnalysis />
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
