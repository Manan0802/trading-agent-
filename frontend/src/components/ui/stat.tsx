import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export type Tone = 'violet' | 'cyan' | 'amber' | 'emerald' | 'rose' | 'indigo'

/**
 * The tint, the rule and the icon colour for one card, keyed by tone.
 *
 * Written out rather than interpolated (`bg-v-${tone}-soft`) because Tailwind
 * scans source text for class names — a template literal produces a class that
 * exists at runtime and was never compiled, so the card renders untinted and
 * nothing errors.
 */
const TONES: Record<Tone, { tint: string; rule: string; ink: string }> = {
  violet: { tint: 'bg-v-violet-soft', rule: 'bg-v-violet', ink: 'text-v-violet-ink' },
  cyan: { tint: 'bg-v-cyan-soft', rule: 'bg-v-cyan', ink: 'text-v-cyan-ink' },
  amber: { tint: 'bg-v-amber-soft', rule: 'bg-v-amber', ink: 'text-v-amber-ink' },
  emerald: { tint: 'bg-v-emerald-soft', rule: 'bg-v-emerald', ink: 'text-v-emerald-ink' },
  rose: { tint: 'bg-v-rose-soft', rule: 'bg-v-rose', ink: 'text-v-rose-ink' },
  indigo: { tint: 'bg-v-indigo-soft', rule: 'bg-v-indigo', ink: 'text-v-indigo-ink' },
}

/**
 * One figure, on its own card, with a colour that means "this is a different
 * thing from the one beside it".
 *
 * Replaces a row of four numbers separated by hairlines. That row was correct
 * and unreadable: everything the same size, the same weight and the same
 * colour, so the eye had nowhere to land and read all four or none.
 *
 * The colour is NOT a magnitude. Green and red still mean gain and loss, and
 * `valueClassName` is what carries them — the tone is only there so four cards
 * are four things.
 */
export function Stat({
  label,
  value,
  tone,
  icon,
  hint,
  valueClassName,
  className,
}: {
  label: string
  value: ReactNode
  tone: Tone
  icon?: ReactNode
  /** One short line. Anything longer belongs on `Why`. */
  hint?: string
  valueClassName?: string
  className?: string
}) {
  const t = TONES[tone]
  return (
    <div
      className={cn(
        'lift relative flex flex-col gap-1 overflow-hidden rounded-xl border bg-card p-4 sm:p-5',
        className,
      )}
    >
      {/* A wash rather than a fill: at full strength the tint fights the figure
          it is meant to frame. */}
      <div className={cn('pointer-events-none absolute inset-0 opacity-70', t.tint)} aria-hidden />
      <div className={cn('absolute inset-x-0 top-0 h-1', t.rule)} aria-hidden />

      <div className="relative flex items-center gap-2">
        {icon && <span className={cn('shrink-0', t.ink)}>{icon}</span>}
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
      </div>
      <p className={cn('num relative text-2xl font-semibold leading-tight sm:text-[1.75rem]', valueClassName)}>
        {value}
      </p>
      {hint && <p className="relative text-xs leading-snug text-muted-foreground">{hint}</p>}
    </div>
  )
}
