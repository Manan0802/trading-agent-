import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BaseRatePanel } from '@/components/BaseRatePanel'
import { Check, CheckList, Eyebrow } from '@/components/ui/check'
import { Label } from '@/components/ui/label'
import { Notice } from '@/components/ui/notice'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'
import { formatInr } from '@/lib/format'
import { fetchLevers, type Lever, type Levers } from '@/lib/portfolio-api'

/**
 * What to actually do, ranked by what it is worth.
 *
 * ## Why this page exists
 *
 * Our own harnesses have tested "which fund will do better" three times and it
 * failed three times — 50% by three-year record, 38% by lifetime return, and
 * 68% by the industry-standard score but at or below chance in three of its
 * seven years. Meanwhile cost predicts at 87% and the tax regime is a slab
 * calculation.
 *
 * Priced for a real user, picking the best fund is worth ₹0 and eight other
 * decisions are worth ₹6L to ₹50L each. This app had four screens for the ₹0
 * one and none for the rest. So does every other Indian investing app.
 *
 * ## Why four lists and not one ranking
 *
 * Because they are different kinds of claim. A guaranteed fee saving, a bet on
 * holding through a 40% fall, and a credit card at 42% are not comparable, and
 * one sorted list would present them as though they were. The separation is
 * structural — the API returns four arrays, so a trade cannot be sorted in
 * among the levers by accident.
 */

const RUPEES_HINT =
  'Everything here is in rupees over your own horizon, not in percentages.'

function value(lever: Lever): string | undefined {
  // Undefined, not a dash. A gate earns nothing by design and a lever measured
  // at zero is a finding; an em dash in the figure slot reads as a number we
  // tried to compute and failed to.
  if (lever.lifetime_value <= 0) return undefined
  return formatInr(lever.lifetime_value)
}

/**
 * The figure at the reader's own setting, and the band across every setting.
 *
 * Both, not one. Showing only the band made the slider look broken — every
 * growth lever has a band, so nothing on screen moved when the assumption did.
 * Showing only the point would hide that the number is an estimate at all.
 */
function band(lever: Lever): string | null {
  if (lever.low === null || lever.high === null) return null
  return `${formatInr(lever.lifetime_value)}`
}

function spread(lever: Lever): string | null {
  if (lever.low === null || lever.high === null) return null
  return `${formatInr(lever.low)} to ${formatInr(lever.high)} across every setting from 4% to 16%`
}

function LeverRow({ lever }: { lever: Lever }) {
  const [open, setOpen] = useState(false)
  const worthless = lever.lifetime_value <= 0
  return (
    <Check
      title={lever.title}
      state={worthless ? 'fact' : 'todo'}
      value={band(lever) ?? value(lever)}
      detail={lever.detail}
    >
      {spread(lever) && (
        <p className="text-xs text-muted-foreground">{spread(lever)}</p>
      )}
      <div className="flex flex-col gap-2 pt-1">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          // A 12px line is a 16px target. The negative margin hands the extra
          // height back to the row so the list does not grow by 20px a line.
          className="-my-2 flex min-h-8 w-fit items-center text-left text-xs font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          {open ? 'Hide the reasoning' : 'How we know, and what to do'}
        </button>
        {open && (
          <dl className="flex max-w-3xl flex-col gap-2 text-sm">
            <div>
              <dt className="text-xs font-medium text-muted-foreground">What to do</dt>
              <dd>{lever.action}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground">How we know</dt>
              <dd className="text-muted-foreground">{lever.evidence}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground">
                When to look at this again
              </dt>
              <dd className="text-muted-foreground">{lever.revisit}</dd>
            </div>
          </dl>
        )}
      </div>
    </Check>
  )
}

function Gates({ data }: { data: Levers }) {
  if (data.gates.length === 0) return null
  return (
    <Panel title="Do these before anything else">
      <div className="flex flex-col gap-3">
        <p className="max-w-3xl text-sm text-muted-foreground">
          Neither of these earns a return. They exist so that a bad month does
          not force you to sell at the bottom, which is the most expensive thing
          an investor can do.
        </p>
        <CheckList>
          {data.gates.map((gate) => (
            <LeverRow key={gate.key} lever={gate} />
          ))}
        </CheckList>
      </div>
    </Panel>
  )
}

function Trades({ data }: { data: Levers }) {
  if (data.trades.length === 0) return null
  return (
    <Panel title="This one is a trade, not a free lever">
      <div className="flex flex-col gap-3">
        <Notice>
          The figure below is arithmetically true and it is not free money. It
          is the payment for sitting through a fall, and you only collect it if
          you actually sit through one. That is why it is not in the list above.
        </Notice>
        <CheckList>
          {data.trades.map((trade) => (
            <LeverRow key={trade.key} lever={trade} />
          ))}
        </CheckList>
      </div>
    </Panel>
  )
}

/**
 * How often the thing we rank on has actually been right.
 *
 * No Indian investing app publishes this about its own engine — ARQ Prime, Mojo
 * Score, Tickertape's Entry Point, ET Money Genius all make forward-looking
 * calls and none says how often they landed. Univest gets closest with "Price
 * moved −196.70 (21.23%) since then" under its verdict: one call marked to
 * market, no denominator, so you cannot tell whether it was typical or their
 * worst one.
 *
 * The denominator is the feature. `wins of windows` is rendered, always.
 */
function OurRecord({ data }: { data: Levers }) {
  const record = data.track_record
  if (!record) return null
  return (
    <Panel title="How often we have actually been right">
      <div className="flex flex-col gap-3">
        <p className="max-w-3xl text-[15px] leading-relaxed">{record.plain}</p>
        {data.better_signal && (
          <Notice>{data.better_signal}</Notice>
        )}
        <p className="max-w-3xl text-xs text-muted-foreground">
          Measured on {record.measured_on} by re-running the tests against real
          NAV history, not by copying an old result. Every other app on this
          market shows you its picks; none of them shows you its scoreboard.
        </p>
      </div>
    </Panel>
  )
}

function Unpriced({ data }: { data: Levers }) {
  if (data.unpriced.length === 0) return null
  return (
    <Panel title="What we could not work out for you">
      <div className="flex flex-col gap-3">
        <p className="max-w-3xl text-sm text-muted-foreground">
          These are named rather than left off. A list containing only what we
          happened to be able to compute would read as a complete list of what
          matters.
        </p>
        <CheckList>
          {data.unpriced.map((gap) => (
            <Check
              key={gap.key}
              title={gap.title}
              state="unknown"
              detail={gap.why}
            >
              <p className="text-sm">
                <span className="text-muted-foreground">We would need: </span>
                {gap.what_we_need}
              </p>
            </Check>
          ))}
        </CheckList>
        {/* Its own control rather than a link inside a sentence: an inline
            link in 14px prose is an 18px-tall target, and the phone gate wants
            32. `min-h-9` with a negative margin gives it the height without
            opening up the paragraph above it. */}
        <Link
          to="/profile"
          className="-my-1 flex min-h-9 w-fit items-center text-sm underline underline-offset-4"
        >
          Fill some of it in on your situation
        </Link>
      </div>
    </Panel>
  )
}

export function Decide() {
  // Not in the profile yet, and both change the answer materially. Asked for
  // here rather than assumed away: a credit card at 42% outranks every lever on
  // the page, and assuming there isn't one is the expensive assumption.
  // Dietvorst, Simmons & Massey (Management Science 2018): people who can
  // adjust an algorithm's output — even slightly, even within a restricted
  // range — rely on it more and end up better off. His 2015 paper is the other
  // half: an unalterable verdict gets abandoned the first time it errs. So this
  // is adjustable, and bounded, and both halves matter.
  const [rate, setRate] = useState(0.12)
  const [debt, setDebt] = useState('')
  const [savings, setSavings] = useState('')

  const parsed = (raw: string): number | undefined => {
    const n = Number(raw.replace(/[^0-9.]/g, ''))
    return raw.trim() === '' || Number.isNaN(n) ? undefined : n
  }

  const { data, isPending, isError } = useQuery({
    queryKey: ['levers', 15, rate, parsed(debt), parsed(savings)],
    queryFn: () =>
      // `monthly_sip` is deliberately NOT sent. The server derives it from this
      // person's own buys over the last twelve months. Passing 0 — which this
      // page did, and which is not the same as "unsupplied" — silently removed
      // the largest lever on the page, the one worth ₹25 lakh.
      fetchLevers({
        years_remaining: 15,
        assumed_return: rate,
        high_interest_debt: parsed(debt),
        liquid_savings: parsed(savings),
      }),
    retry: false,
  })

  const worthSomething = data?.levers.filter((l) => l.lifetime_value > 0) ?? []
  const worthNothing = data?.levers.filter((l) => l.lifetime_value <= 0) ?? []

  // The server sends the range it will actually honour, because it clamps what
  // it is given -- `assumed_return` comes back echoed for exactly that reason.
  // This slider used to hardcode 4 and 16. They matched, and nothing kept them
  // matching: move RETURN_BOUNDS and the slider would go on offering the old
  // range while the backend quietly used a different number, which is the one
  // failure `return_bounds` exists to prevent.
  const [lo, hi] = data?.return_bounds ?? [0.04, 0.16]

  return (
    <div className="flex flex-col gap-6">
      {/* Outside every loading and error branch: Panel emits an h2, so a page
          whose h1 waits for data starts at h2 while fetching and the heading
          check fails on the state nobody screenshots. */}
      <header className="flex flex-col gap-2">
        <Eyebrow>Your money</Eyebrow>
        <h1 className="font-heading text-3xl font-semibold leading-[1.1] tracking-[-0.02em] sm:text-4xl">
          What to do next
        </h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Every decision we can price for you, biggest first. {RUPEES_HINT}
        </p>
      </header>

      <Panel title="What we are assuming">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <Label htmlFor="decide-rate" className="shrink-0">
              If markets return
            </Label>
            <input
              id="decide-rate"
              type="range"
              min={Math.round(lo * 100)}
              max={Math.round(hi * 100)}
              step={1}
              value={Math.round(rate * 100)}
              onChange={(e) => setRate(Number(e.target.value) / 100)}
              className="h-9 w-full max-w-xs"
            />
            <span className="num-display text-xl">{Math.round(rate * 100)}% a year</span>
          </div>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Disagree with us and move it — the figures below rebuild. It stops at
            4% and 16% because outside that the arithmetic stops describing any
            decision a person could be making. Two things do not move at all:
            picking the best fund stays at zero at every setting, and the tax
            regime is a slab calculation rather than a forecast.
          </p>
        </div>
      </Panel>

      <Panel title="Two things we do not know about you">
        <div className="flex flex-col gap-4">
          <p className="max-w-3xl text-sm text-muted-foreground">
            Both change the answer more than any fund choice. Leave them blank
            and we will say so rather than assume.
          </p>
          <div className="flex flex-wrap gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="decide-debt">Owed on cards or personal loans</Label>
              <input
                id="decide-debt"
                inputMode="numeric"
                value={debt}
                onChange={(e) => setDebt(e.target.value)}
                placeholder="e.g. 100000"
                className="h-9 w-full max-w-full rounded-md border bg-transparent px-2 text-sm sm:w-56"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="decide-savings">Cash you could reach this week</Label>
              <input
                id="decide-savings"
                inputMode="numeric"
                value={savings}
                onChange={(e) => setSavings(e.target.value)}
                placeholder="e.g. 150000"
                className="h-9 w-full max-w-full rounded-md border bg-transparent px-2 text-sm sm:w-56"
              />
            </div>
          </div>
        </div>
      </Panel>

      {isError ? (
        <Panel title="Nothing to show">
          <Notice>
            We could not work out your decisions. If this keeps happening, the
            price feed behind your holdings is probably down.
          </Notice>
        </Panel>
      ) : isPending || !data ? (
        <Panel title="Working out what is worth what">
          <Skeleton className="h-40 w-full" />
        </Panel>
      ) : (
        <>
          {/* Before the levers, not after. The reference class is the outside
              view and it has to land before any specific recommendation —
              Kahneman & Lovallo, and the sequence the UK Treasury mandates for
              infrastructure costing. */}
          <BaseRatePanel rate={data.base_rate} amount={data.portfolio_value} />
          <Gates data={data} />

          <Panel
            title="Worth doing, biggest first"
            aside={`over ${Math.round(data.years_remaining)} years`}
          >
            {worthSomething.length === 0 ? (
              <Notice>
                Nothing here is worth money to you right now — which is a good
                position to be in, not an error.
              </Notice>
            ) : (
              <CheckList>
                {worthSomething.map((lever) => (
                  <LeverRow key={lever.key} lever={lever} />
                ))}
              </CheckList>
            )}
          </Panel>

          <Trades data={data} />

          {worthNothing.length > 0 && (
            <Panel title="Already done, or worth nothing">
              <div className="flex flex-col gap-3">
                <p className="max-w-3xl text-sm text-muted-foreground">
                  Shown rather than hidden. A decision already made correctly is
                  worth knowing about, and one measured at zero is a finding —
                  leaving it off would read as though we never checked.
                </p>
                <CheckList>
                  {worthNothing.map((lever) => (
                    <LeverRow key={lever.key} lever={lever} />
                  ))}
                </CheckList>
              </div>
            </Panel>
          )}

          <Unpriced data={data} />

          <OurRecord data={data} />

          <Panel title="How this page is worked out">
            <div className="flex max-w-3xl flex-col gap-3 text-sm text-muted-foreground">
              <p>
                Every figure is what the decision is worth to you over{' '}
                {Math.round(data.years_remaining)} years, on the{' '}
                {formatInr(data.portfolio_value)} we can see. Cost and tax
                figures are arithmetic. Anything that depends on what markets do
                is shown as a range, not a number.
              </p>
              <p>
                Picking the best-performing fund sits at zero because we tested
                it on our own NAV history three times and it failed three times.
                That zero is the reason this page exists.
              </p>
              <p>
                The screener still ranks funds, because you have to hold
                something. It is just not where the money is.
              </p>
              <Link
                to="/screener"
                className="-my-1 flex min-h-9 w-fit items-center text-sm underline underline-offset-4"
              >
                Go to the screener
              </Link>
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}
