import { Notice } from '@/components/ui/notice'
import { Panel } from '@/components/ui/panel'
import { count } from '@/lib/format'
import type { BaseRate } from '@/lib/screener-api'
import { cn } from '@/lib/utils'

/**
 * What this kind of fund has done to people before.
 *
 * ## Where this sits, and why it is not negotiable
 *
 * **Before** the fund's own record, never beside it. Kahneman & Lovallo (1993)
 * found a base rate shown alongside a vivid individual case gets ignored in
 * favour of the case; Flyvbjerg's reference-class forecasting, which the UK
 * Treasury mandates for infrastructure costing, puts the class first and
 * adjusts afterwards. Sequence, not just presence.
 *
 * ## Why rupees
 *
 * Fifteen Indian investing apps were surveyed while designing this and **not
 * one turns volatility into a loss a reader can picture.** The closest anyone
 * gets is "34.67% fall from 52-week high". "Standard deviation 14.2" and even
 * "−57% worst fall" are not answers to "what could happen to my money".
 * ₹4,59,280 of your ₹8,00,000 is.
 */
export function BaseRatePanel({
  rate,
  amount,
  className,
}: {
  rate: BaseRate | null
  /** The reader's own money in this, so the fall can be shown in rupees. */
  amount?: number | null
  className?: string
}) {
  if (!rate) {
    return (
      <Panel title="What this kind of fund has done before" className={className}>
        <Notice>
          This category has fewer than eight funds with enough history, so there
          is no honest base rate for it. We will not quote you a broader
          category's number instead — &ldquo;equity funds&rdquo; and this
          category are different claims.
        </Notice>
      </Panel>
    )
  }

  const shown = rate.horizons.filter((h) => ['1y', '3y', '5y', '10y'].includes(h.key))
  const atRisk = rate.rupees_at_risk

  return (
    <Panel
      title="What this kind of fund has done before"
      aside={`${count(rate.funds)} funds · since 2006`}
      className={className}
    >
      <div className="flex flex-col gap-5">
        {rate.plain.base_rate && (
          <p className="max-w-3xl text-[15px] leading-relaxed">{rate.plain.base_rate}</p>
        )}

        {/* How often money went backwards, by how long it was left alone. This
            is the finding: the loss rate collapses with holding period, and it
            barely moves with which fund was picked. */}
        <div>
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md bg-border sm:grid-cols-4">
            {shown.map((h) => (
              <div key={h.key} className="flex flex-col gap-0.5 bg-card p-3">
                <dt className="text-xs text-muted-foreground">Held {h.words}</dt>
                <dd
                  className={cn(
                    'num-display text-xl',
                    h.loss_share <= 0.02 && 'text-[color:var(--gain)]',
                  )}
                >
                  {outOfHundred(h.loss_share)}
                </dd>
                <dd className="text-xs text-muted-foreground">
                  of every 100 stretches lost money
                </dd>
              </div>
            ))}
          </dl>
          <p className="pt-2 text-xs text-muted-foreground">
            Each column counts every month someone could have started, from{' '}
            <span className="tnum">{count(shown[0]?.windows ?? 0)}</span> such
            stretches at the shortest horizon. They overlap, so they are not
            independent — that is what a base rate is.
          </p>
        </div>

        {rate.plain.worst_fall && (
          <div className="flex flex-col gap-1.5">
            <p className="max-w-3xl text-sm">{rate.plain.worst_fall}</p>
            {atRisk !== null && amount ? (
              <p className="text-sm text-muted-foreground">
                That is the worst it has been, not a forecast, and not a floor —
                a bigger fall is possible and simply has not happened yet.
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                Tell us what you hold and we will show that as a rupee figure
                rather than a percentage.
              </p>
            )}
          </div>
        )}

        <p className="max-w-3xl text-xs text-muted-foreground">
          {rate.plain.coverage} Measured to {rate.as_of}.
        </p>
      </div>
    </Panel>
  )
}

/**
 * A loss rate as a count, without rounding a real risk down to "never".
 *
 * 0.4% rounds to 0, and "0" reads as *it cannot happen* — but 0.4% is about one
 * stretch in 250, and somebody is in it. Mirrors `plain_words._out_of_hundred`
 * on the server, which produces the sentence above these tiles; if the two ever
 * disagree the panel contradicts its own headline.
 */
function outOfHundred(share: number): string {
  if (share <= 0) return 'None'
  const n = Math.round(share * 100)
  return n === 0 ? '<1' : String(n)
}
