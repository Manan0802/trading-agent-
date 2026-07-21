import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * A single figure with its label, and optionally what it should be read
 * against. Metrics sit on hairlines rather than in cards: at this density a
 * card per number turns the page into a wall of boxes, and the elevation is
 * not communicating any real hierarchy.
 */
export function Metric({
  label,
  value,
  hint,
  valueClassName,
  size = 'md',
  className,
}: {
  label: string
  value: ReactNode
  /** What the number means, or what it should be compared against. */
  hint?: ReactNode
  valueClassName?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}) {
  const valueSize = {
    sm: 'text-lg',
    md: 'text-2xl',
    lg: 'text-3xl sm:text-4xl',
  }[size]

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd
        className={cn(
          'num font-medium leading-none tracking-tight',
          valueSize,
          valueClassName,
        )}
      >
        {value}
      </dd>
      {hint ? (
        <p className="text-xs leading-snug text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  )
}

/**
 * A row of metrics separated by hairlines rather than gaps, so the group reads
 * as one instrument cluster instead of several unrelated cards.
 */
export function MetricRow({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <dl
      className={cn(
        'grid grid-cols-2 gap-x-6 gap-y-8 border-y py-6',
        'sm:grid-cols-3 lg:grid-cols-4',
        'sm:divide-x sm:[&>*]:pl-6 sm:[&>*:first-child]:pl-0',
        className,
      )}
    >
      {children}
    </dl>
  )
}
