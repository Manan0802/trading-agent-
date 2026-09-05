import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * Reveals its children once, when they scroll into view.
 *
 * An IntersectionObserver rather than a scroll handler. A `scroll` listener
 * runs on every frame the page moves and cannot be batched; driving a reveal
 * from `window.scrollY` in React state re-renders the tree at 60fps and falls
 * over on a phone. The observer fires once per element and then disconnects.
 *
 * `once` is not an option. A section that fades out when you scroll back up is
 * a section you cannot re-read, and re-reading is the only reason anybody
 * scrolls up.
 */
export function InView({
  children,
  className,
  delay = 0,
  as: Tag = 'div',
}: {
  children: ReactNode
  className?: string
  /** Seconds. Stagger siblings rather than firing a whole section at once. */
  delay?: number
  as?: 'div' | 'section' | 'li'
}) {
  const ref = useRef<HTMLElement | null>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const el = ref.current
    // No element, or a browser without the observer: the CSS leaves `.reveal`
    // hidden, so show it rather than leaving a blank band on the page.
    if (!el || typeof IntersectionObserver === 'undefined') {
      setShown(true)
      return
    }
    // Already on screen at mount — the hero, and anything above the fold on a
    // tall monitor. Waiting for a scroll that never comes is a blank first
    // impression.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShown(true)
            observer.disconnect()
          }
        }
      },
      // Fires slightly before the element's top edge arrives, so the movement
      // has finished by the time it is properly in the reading area.
      { rootMargin: '0px 0px -12% 0px', threshold: 0.01 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <Tag
      ref={ref as never}
      className={cn('reveal', shown && 'in-view', className)}
      style={delay ? { transitionDelay: `${delay}s` } : undefined}
    >
      {children}
    </Tag>
  )
}
