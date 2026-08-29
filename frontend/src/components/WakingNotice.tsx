import { useEffect, useState } from 'react'
import { onWaking } from '@/lib/api'

/**
 * The eleventh state, and the most frequent one.
 *
 * §13.5 tabled ten UI states and called itself "the half that was entirely
 * missing". It was still missing this one: the free host sleeps after fifteen
 * minutes idle and takes about a minute to wake, so for an app opened a few
 * times a week nearly every session starts cold. The rule §13.5 does give for
 * loading -- "skeletons, no spinner" -- is the worst available presentation of
 * a sixty-second wait, because a skeleton promises data is arriving now.
 *
 * So this says the true thing instead: the server was asleep, this is the
 * first visit, it is coming. Nothing here is a spinner and nothing pretends to
 * measure progress it cannot see.
 */
export function WakingNotice() {
  const [waking, setWaking] = useState(false)
  const [seconds, setSeconds] = useState(0)

  useEffect(() => onWaking(setWaking), [])

  useEffect(() => {
    if (!waking) {
      setSeconds(0)
      return
    }
    const tick = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(tick)
  }, [waking])

  if (!waking) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-start gap-2 rounded-md border border-border bg-[var(--surface-2)] px-3 py-2 text-sm"
    >
      <span aria-hidden className="mt-0.5">
        &#9679;
      </span>
      <span>
        <strong className="font-medium">Waking the server.</strong> It sleeps
        when nobody has used it for a while, and takes about a minute to come
        back. Nothing is wrong and nothing is lost.
        {seconds >= 5 && (
          <span className="tnum text-muted-foreground"> {seconds}s</span>
        )}
      </span>
    </div>
  )
}
