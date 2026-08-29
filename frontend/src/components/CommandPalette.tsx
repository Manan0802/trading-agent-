/**
 * ⌘K — every destination in the app, from anywhere, without reaching for the nav.
 *
 * The nav scrolls sideways on a phone and a destination five items along is a
 * swipe away. This is the keyboard route to all of them, and it is the only
 * navigation in the app that does not depend on being able to see where you are.
 *
 * Deliberately just the destinations. A palette that also searches 1,689 funds
 * has to decide what a fund result means when you are mid-typing, and gets slow
 * exactly when someone is typing fast. Search lives on `Find`, which is one of
 * the destinations below.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export type Destination = { to: string; label: string; hint?: string }

export function matchDestinations(
  destinations: Destination[],
  query: string,
): Destination[] {
  const q = query.trim().toLowerCase()
  if (!q) return destinations
  // Substring, not fuzzy. Fuzzy matching on six items produces surprising
  // ordering for no benefit — every label is one word and already on screen.
  return destinations.filter(
    (d) => d.label.toLowerCase().includes(q) || d.hint?.toLowerCase().includes(q),
  )
}

export function CommandPalette({ destinations }: { destinations: Destination[] }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const results = useMemo(
    () => matchDestinations(destinations, query),
    [destinations, query],
  )

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((was) => !was)
        setQuery('')
        setCursor(0)
      }
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  if (!open) return null

  function go(to: string) {
    setOpen(false)
    navigate(to)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[12vh]"
      onClick={() => setOpen(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Go to"
        className="w-[min(32rem,92vw)] overflow-hidden rounded-lg border bg-popover shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setCursor(0)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setCursor((c) => Math.min(c + 1, results.length - 1))
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault()
              setCursor((c) => Math.max(c - 1, 0))
            }
            if (e.key === 'Enter' && results[cursor]) go(results[cursor].to)
          }}
          placeholder="Go to…"
          aria-label="Go to"
          className="w-full border-b bg-transparent px-4 py-3 text-sm outline-none"
        />
        <ul role="listbox" className="max-h-72 overflow-y-auto py-1">
          {results.length === 0 && (
            <li className="px-4 py-3 text-sm text-muted-foreground">
              Nothing here by that name.
            </li>
          )}
          {results.map((d, i) => (
            <li key={d.to}>
              <button
                type="button"
                role="option"
                aria-selected={i === cursor}
                onMouseEnter={() => setCursor(i)}
                onClick={() => go(d.to)}
                className={`flex w-full items-baseline gap-2 px-4 py-2 text-left text-sm ${
                  i === cursor ? 'bg-secondary' : ''
                }`}
              >
                <span className="font-medium">{d.label}</span>
                {d.hint && <span className="text-xs text-muted-foreground">{d.hint}</span>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
