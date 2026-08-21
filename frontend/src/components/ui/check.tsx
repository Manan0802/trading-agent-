import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * A named check: what it is, whether it is settled, and one line of why.
 *
 * ## Why this shape and not a score
 *
 * Three sources arrived at it independently. Simply Wall St's Snowflake is five
 * axes of six named pass/fail checks, and the decomposition — not the composite
 * — is the interface. Ghostfolio's X-ray is a set of independently named rules
 * that each fire or don't and say why in a sentence. And Kahneman's Mediating
 * Assessments Protocol prescribes exactly this: score the parts separately
 * before forming an overall impression, so one early read cannot contaminate
 * the rest.
 *
 * A single blended number does the opposite. It hides which part is driving it,
 * it cannot be argued with, and when it turns out to be wrong once, people
 * abandon the whole tool — Dietvorst's algorithm-aversion result. A reader who
 * can see the six parts can disagree with one of them and keep the other five.
 *
 * ## The tone rule
 *
 * `state` is deliberately not "good/bad". Most of what this app reports is
 * neither: a base rate is a fact, a cost is a fact, and a fund's past record is
 * a fact that does not predict. Only `done` and `todo` make a claim about the
 * reader, and they are reserved for things that genuinely are settled or not.
 */
export type CheckState = 'done' | 'todo' | 'fact' | 'unknown'

const DOT: Record<CheckState, string> = {
  // Deliberately reusing the gain/loss tokens rather than minting new colour.
  // Six new hues would be six new contrast risks across two themes, and the
  // word beside the dot already carries the meaning — the dot is redundant
  // encoding, which is the only reason it is allowed to be colour at all.
  done: 'bg-[color:var(--gain)]',
  // The accent, not the loss token. A thing worth doing is an opportunity, and
  // red read as "something is broken" next to "Use the ₹1.25 lakh tax-free
  // gain" — which is not a problem, it is money on the table.
  todo: 'bg-[color:var(--primary)]',
  fact: 'bg-muted-foreground',
  unknown: 'bg-muted-foreground/50',
}

const LABEL: Record<CheckState, string> = {
  done: 'Already done',
  todo: 'Worth doing',
  fact: 'For information',
  unknown: 'Not known',
}

export function Check({
  title,
  state = 'fact',
  value,
  detail,
  children,
  className,
}: {
  title: string
  state?: CheckState
  /** The headline figure, already formatted. Rupees wherever we can. */
  value?: ReactNode
  /** One line. If it needs two sentences it is two checks. */
  detail?: ReactNode
  /** Evidence, action, what would change it — anything that reads underneath. */
  children?: ReactNode
  className?: string
}) {
  return (
    <li className={cn('flex gap-3 py-3', className)}>
      {/* aria-hidden and paired with a visually-hidden word, so the state is
          never carried by colour alone — a reader who cannot distinguish the
          two tokens still gets "Already done" from the accessibility tree. */}
      <span
        aria-hidden
        className={cn('mt-[0.45rem] size-2 shrink-0 rounded-full', DOT[state])}
      />
      <span className="sr-only">{LABEL[state]}:</span>
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <span className="text-sm font-medium leading-snug">{title}</span>
          {value !== undefined && value !== null && (
            <span className="num text-sm leading-snug">{value}</span>
          )}
        </div>
        {detail && (
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
            {detail}
          </p>
        )}
        {children}
      </div>
    </li>
  )
}

export function CheckList({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <ul className={cn('flex flex-col divide-y', className)}>{children}</ul>
}

/**
 * A small caps label above a section.
 *
 * Cheap wayfinding, and the one piece of Univest's page furniture worth taking
 * outright: it tells a reader what kind of thing the next block is before they
 * read any of it. Rendered as a plain span, never a heading — the heading order
 * is load-bearing for the accessibility gate and an eyebrow is not a level.
 */
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="text-xs font-semibold uppercase tracking-[0.08em] text-[color:var(--primary)]">
      {children}
    </span>
  )
}
