import type { ReactNode } from 'react'

/**
 * A bounded surface for one idea.
 *
 * The dashboard was a single column of sections separated only by whitespace,
 * which reads as one long document rather than a set of answers. On a finance
 * screen the reader scans for the one number they came for, and a bounded
 * surface is what makes that possible — the eye can reject a whole panel at a
 * glance instead of parsing its first line.
 *
 * Deliberately quiet: a hairline border and the card surface, no shadow. Shadow
 * implies elevation and interactivity, and these are readouts, not controls.
 */
export function Panel({
  title,
  aside,
  children,
  className = '',
}: {
  /** Omit for a panel whose content carries its own heading. */
  title?: string
  /** Right-aligned context on the title row — a date range, a count, a total. */
  aside?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`flex min-w-0 flex-col gap-4 rounded-lg border bg-card p-4 sm:p-5 ${className}`}
    >
      {(title || aside) && (
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          {title && (
            <h2 className="font-heading text-base font-semibold tracking-[-0.01em]">{title}</h2>
          )}
          {aside && (
            <div className="text-xs text-muted-foreground">{aside}</div>
          )}
        </div>
      )}
      {children}
    </section>
  )
}
