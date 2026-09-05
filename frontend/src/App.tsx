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
        {/* Three zones, not two. The old header put the brand and the controls
            hard left and every destination hard right, so eight tabs crowded
            into the last third of a 1440px screen while half the bar sat empty.
            The nav now takes the middle and spreads across it; the controls sit
            where a product's controls sit, which is the far right. */}
        <div className="mx-auto flex max-w-[100rem] flex-col gap-1 px-4 py-2 sm:h-16 sm:flex-row sm:items-center sm:gap-6 sm:py-0 sm:px-6">
          <div className="flex h-11 shrink-0 items-center justify-between gap-4 sm:h-auto">
            <NavLink
              to={signedIn ? '/portfolio' : '/login'}
              // 44px of height even though the word is 23px tall. It is a link
              // home, and the phone harness measures the anchor's own box —
              // rewriting this header dropped the padding it used to have and
              // every page went red on the same target.
              className="flex min-h-11 items-center text-[15px] font-semibold tracking-tight"
            >
              NexTrade
            </NavLink>
            {/* Only on a phone, where the right-hand zone has nowhere to go. */}
            <div className="flex items-center gap-1 sm:hidden">
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
            // Scrolls rather than wraps: a nav that reflows to two lines pushes
            // the page down by a row on exactly the screens with the least of
            // it.
            <nav className="-mx-4 min-w-0 flex-1 overflow-x-auto px-4 pb-1 sm:mx-0 sm:overflow-visible sm:px-0 sm:pb-0">
              <div className="flex items-center gap-1 sm:justify-center lg:gap-2">
                {NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/portfolio'}
                    className={({ isActive }) =>
                      cn(
                        // min-h-11 is 44px, the smallest target a thumb hits
                        // reliably. Without it the links measured 16px tall on
                        // a phone once the nav gained an item and began to
                        // scroll — a link you cannot tap is not navigation.
                        'relative flex min-h-11 shrink-0 items-center rounded-lg px-3 text-sm lg:px-4',
                        'transition-colors duration-200',
                        isActive
                          ? 'font-semibold text-foreground'
                          : 'text-muted-foreground hover:text-foreground',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {item.label}
                        {/* An underline rather than a filled pill. Eight pills
                            in a row is eight boxes; one rule under the live tab
                            says the same thing and leaves the words as words. */}
                        <span
                          aria-hidden
                          className={cn(
                            'absolute inset-x-2.5 -bottom-px h-0.5 rounded-full transition-opacity lg:inset-x-3.5',
                            isActive ? 'bg-primary opacity-100' : 'opacity-0',
                          )}
                        />
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </nav>
          )}

          <div className="hidden shrink-0 items-center gap-1 sm:flex">
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
