/**
 * The frame every device sits in, and the two states they all used to skip.
 *
 * §13.5 lists ten states a surface can be in. Loading and empty were missing
 * from every chart in this app, which in practice means a blank rectangle —
 * and a blank rectangle is indistinguishable from "this fund has no drawdown",
 * "we could not fetch it", and "the component crashed". The person reading it
 * has no way to tell a fact from an outage.
 *
 * So a device never renders nothing. It renders what it knows.
 */
import type { ReactNode } from 'react'

export type ChartState = 'loading' | 'empty' | 'ready'

export function chartState(loading: boolean, count: number): ChartState {
  if (loading) return 'loading'
  return count > 0 ? 'ready' : 'empty'
}

export function ChartFrame({
  state,
  height,
  label,
  emptyNote,
  children,
}: {
  state: ChartState
  height: number
  /** Read by screen readers in place of the drawing. Required, not optional. */
  label: string
  /** Why there is nothing — never just "no data". */
  emptyNote?: string
  children: ReactNode
}) {
  if (state === 'loading') {
    return (
      <div
        className="animate-pulse rounded-md bg-muted/60"
        style={{ height }}
        role="status"
        aria-live="polite"
        aria-label={`Loading ${label}`}
      />
    )
  }
  if (state === 'empty') {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-dashed px-3 text-center text-xs text-muted-foreground"
        style={{ height }}
        role="status"
      >
        {emptyNote ?? 'Not enough history to draw this yet.'}
      </div>
    )
  }
  return (
    <figure className="m-0" style={{ height }} aria-label={label}>
      {children}
    </figure>
  )
}
