import type { ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

/**
 * Caveats and failures both sit at the same weight: a quiet line with a mark
 * beside it. Amber would be a second accent, and none of these are emergencies.
 *
 * Lifted out of Research when the screener needed the same thing. Two copies of
 * a caveat component is how two screens start caveating differently.
 */
export function Notice({ children }: { children: ReactNode }) {
  return (
    <p className="flex max-w-3xl items-start gap-2 text-sm text-muted-foreground">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  )
}
