import { useEffect, useRef } from 'react'

/**
 * Tilts an element toward the pointer.
 *
 * The angles are written to CSS custom properties on the node, never to React
 * state. A pointer that moves 400 times a second through `useState` re-renders
 * the whole tree 400 times; through `style.setProperty` it touches one element
 * and stays on the compositor. The rAF here batches to one write per frame and
 * never reads React.
 *
 * Three things switch it off entirely, and in each case the CSS defaults are
 * the resting pose, so the element is still correctly tilted:
 *   - `prefers-reduced-motion`, because this is decoration
 *   - a coarse pointer, because a finger has no hover and the first tap would
 *     freeze the card at wherever it landed
 *   - no element, i.e. the breakpoint that hides the stack entirely
 */
export function useTilt<T extends HTMLElement>(maxDeg = 7) {
  const ref = useRef<T | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    if (!window.matchMedia?.('(pointer: fine)').matches) return

    let frame = 0
    const move = (event: PointerEvent) => {
      const box = el.getBoundingClientRect()
      const x = (event.clientX - box.left) / box.width - 0.5
      const y = (event.clientY - box.top) / box.height - 0.5
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        // Around the resting angles in the stylesheet, not from zero — the
        // stack should lean toward the cursor, not snap flat under it.
        el.style.setProperty('--ry', `${-16 + x * maxDeg * 2}deg`)
        el.style.setProperty('--rx', `${8 - y * maxDeg * 2}deg`)
      })
    }
    const enter = () => el.setAttribute('data-tracking', '1')
    const leave = () => {
      cancelAnimationFrame(frame)
      el.removeAttribute('data-tracking')
      el.style.removeProperty('--ry')
      el.style.removeProperty('--rx')
    }

    el.addEventListener('pointerenter', enter)
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerleave', leave)
    return () => {
      cancelAnimationFrame(frame)
      el.removeEventListener('pointerenter', enter)
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerleave', leave)
    }
  }, [maxDeg])

  return ref
}
