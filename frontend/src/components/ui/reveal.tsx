import { useState } from 'react'
import type { ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * The paragraph, folded.
 *
 * Every panel on this dashboard had the same shape: a figure worth two seconds,
 * followed by three hundred words explaining how it was arrived at. The words
 * are not padding — they are what lets somebody argue with the number, and the
 * app's whole claim is that its figures can be argued with. They were simply in
 * front of the answer instead of behind it.
 *
 * So: the answer stays visible, the reasoning gets a row you can open. One
 * component rather than six copies, because six copies drift.
 */
export function Reveal({
  label = 'How this is worked out',
  children,
  className,
}: {
  label?: string
  children: ReactNode
  className?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className={cn('border-t', className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex min-h-11 w-full items-center gap-2 text-left text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <span className="flex-1">{label}</span>
        <ChevronDown
          aria-hidden
          className={cn('size-4 shrink-0 transition-transform duration-200', open && 'rotate-180')}
        />
      </button>
      {open && (
        <div className="flex flex-col gap-3 pb-3 text-sm leading-relaxed text-muted-foreground">
          {children}
        </div>
      )}
    </div>
  )
}
