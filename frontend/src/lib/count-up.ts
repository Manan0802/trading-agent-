import { useEffect, useRef, useState } from 'react'

/**
 * Counts a figure up on first paint, then never again.
 *
 * Not decoration. A portfolio value that lands instantly reads as a stored
 * label; one that counts reads as just worked out, which is what it is — XIRR
 * over your own transactions, computed on request.
 *
 * It animates ONCE per value. Re-running on every refetch would make the page
 * twitch every thirty seconds, and a number that keeps moving is one nobody
 * trusts.
 *
 * ⚠️ The "once" bookkeeping is the whole difficulty, and a first version got it
 * wrong in a way that only broke in development. It marked the target as done
 * BEFORE animating; React StrictMode double-invokes effects, so the second run
 * saw its own mark, returned early, and the number sat at ₹0 forever — while
 * production, which does not double-invoke, was fine. So the mark is written
 * when the animation COMPLETES, and cleanup that interrupts it leaves the mark
 * unset so the next run can start over.
 */
export function useCountUp(target: number | null | undefined, ms = 750): number {
  const [value, setValue] = useState(0)
  const settled = useRef<number | null>(null)

  useEffect(() => {
    if (target === null || target === undefined || !Number.isFinite(target)) return
    if (settled.current === target) return

    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced || ms <= 0) {
      settled.current = target
      setValue(target)
      return
    }

    let frame = 0
    let finished = false
    const started = performance.now()
    const step = (now: number) => {
      const t = Math.min(1, (now - started) / ms)
      // Ease out: quick off the mark, settling at the end. A linear count reads
      // like a slot machine.
      setValue(target * (1 - (1 - t) ** 3))
      if (t < 1) {
        frame = requestAnimationFrame(step)
      } else {
        finished = true
        settled.current = target
      }
    }
    frame = requestAnimationFrame(step)
    return () => {
      cancelAnimationFrame(frame)
      // Interrupted, so it was never shown in full. Leaving the mark set here
      // is exactly the StrictMode bug above.
      if (!finished) settled.current = null
    }
  }, [target, ms])

  return value
}
