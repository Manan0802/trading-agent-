/**
 * Where you are, and every hop you took to get here — each one clickable.
 *
 * The case this exists for: a company reached THROUGH a fund. You open Screener,
 * pick HDFC Flexi Cap, see HDFC Bank inside it, and click through. Without a
 * trail the only route back to the fund is the browser's back button, and the
 * page gives no sign that the fund is where you came from — so the two hops are
 * invisible and the app feels like a set of dead ends.
 *
 * The middle hop cannot be derived from the URL. `/screener/stock/HDFCBANK` says
 * nothing about which fund you were looking at, and guessing from history is
 * wrong the moment somebody opens the link directly. So it travels in the
 * router's location state, and when it is absent the trail is simply shorter —
 * which is correct: a deep link genuinely has no middle hop.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

export type Hop = { label: string; to: string }

/** What a page passes when it sends you somewhere it wants to stay behind you. */
export type TrailVia = { label: string; to: string }

const ROOTS: { prefix: string; label: string; to: string }[] = [
  { prefix: '/screener', label: 'Screener', to: '/screener' },
  { prefix: '/portfolio', label: 'Portfolio', to: '/portfolio' },
  { prefix: '/research', label: 'Research', to: '/research' },
  { prefix: '/decide', label: 'Decide', to: '/decide' },
  { prefix: '/goals', label: 'Goals', to: '/goals' },
  { prefix: '/profile', label: 'You', to: '/profile' },
]

export function trailFor(
  pathname: string,
  params: Record<string, string | undefined>,
  via?: TrailVia | null,
  leaf?: string,
): Hop[] {
  const root = ROOTS.find((r) => pathname.startsWith(r.prefix))
  if (!root) return []
  // The root alone is not a trail. One item tells you nothing you did not
  // already know from the nav, and renders as a stray word above the heading.
  if (pathname === root.to) return []

  const hops: Hop[] = [{ label: root.label, to: root.to }]
  if (via && via.to !== pathname) hops.push({ label: via.label, to: via.to })
  hops.push({
    label: leaf ?? params.schemeCode ?? params.ticker ?? params.id ?? 'Details',
    to: pathname,
  })
  return hops
}

/**
 * The last crumb's real name, set by the page that knows it.
 *
 * The trail lives in the layout so every page gets one for free, but only the
 * detail page knows that `122639` is "Parag Parikh Flexi Cap Fund". Without
 * this the last crumb is a scheme code, which is the identifier the app uses
 * internally and not a thing a person recognises.
 */
const LeafContext = createContext<{
  leaf: string | null
  setLeaf: (name: string | null) => void
}>({ leaf: null, setLeaf: () => {} })

export function TrailProvider({ children }: { children: ReactNode }) {
  const [leaf, setLeaf] = useState<string | null>(null)
  const value = useMemo(() => ({ leaf, setLeaf }), [leaf])
  return <LeafContext.Provider value={value}>{children}</LeafContext.Provider>
}

/** Call from a detail page with the name it is showing. Cleared on unmount, so
 *  navigating away cannot leave the previous fund's name in the trail. */
export function useTrailLeaf(name: string | null | undefined) {
  const { setLeaf } = useContext(LeafContext)
  useEffect(() => {
    setLeaf(name ?? null)
    return () => setLeaf(null)
  }, [name, setLeaf])
}

export function Trail({ leaf }: { leaf?: string }) {
  const location = useLocation()
  const params = useParams()
  const fromPage = useContext(LeafContext).leaf
  const via = (location.state as { via?: TrailVia } | null)?.via ?? null
  const hops = trailFor(location.pathname, params, via, leaf ?? fromPage ?? undefined)
  if (hops.length === 0) return null

  return (
    <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
      <ol className="flex flex-wrap items-center gap-1.5">
        {hops.map((hop, i) => {
          const last = i === hops.length - 1
          return (
            <li key={`${hop.to}-${i}`} className="flex items-center gap-1.5">
              {last ? (
                <span aria-current="page" className="font-medium text-foreground">
                  {hop.label}
                </span>
              ) : (
                <>
                  <Link
                    to={hop.to}
                    // A breadcrumb is small by design and a tap target is not.
                    // The phone harness measured this at 31x16 against a 44x44
                    // minimum — a word like "Goals" is 31px wide, so BOTH axes
                    // needed work. The vertical padding is cancelled by a
                    // negative margin so the row keeps its height; the
                    // horizontal minimum is not, because a couple of pixels of
                    // slack around a crumb costs nothing and clipping the first
                    // one against the page edge would.
                    className="-my-3 inline-flex min-h-11 min-w-11 items-center justify-center rounded-sm px-1 py-3 underline-offset-2 hover:text-foreground hover:underline"
                  >
                    {hop.label}
                  </Link>
                  <span aria-hidden className="text-muted-foreground/50">
                    /
                  </span>
                </>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
