import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Coins,
  Layers2,
  Receipt,
  ScanSearch,
  ShieldQuestion,
  Sparkles,
} from 'lucide-react'
import { buttonVariants } from '@/components/ui/button'
import { InView } from '@/components/ui/in-view'
import { cn } from '@/lib/utils'

/**
 * The page somebody who has never heard of this sees first.
 *
 * There was no such page. `/` redirected straight to `/portfolio`, which
 * bounced a signed-out visitor to a login form, and signing in dropped them
 * into `/goals/new` — a form, before anything had explained what the thing is
 * or why its answers are worth trusting.
 *
 * The copy leads with what the app CANNOT do, because that is its actual
 * differentiator and it is measured rather than claimed: ranking funds by past
 * return put the worse quartile on top by 0.9pp and won 19 of 44 windows. Every
 * figure on this page is one the product already proves on `/why`, with the
 * same numbers. A landing page that promises more than the product's own
 * evidence page is a landing page that has to be walked back at the first
 * screen.
 *
 * Motion: entrance and scroll-reveal only, and every section is legible with
 * the animation removed. Nothing loops except one 7s float behind the hero.
 */

/** The three claims, in the order they are worth hearing. */
const PROOF = [
  {
    figure: '0.64pp',
    label: 'a year',
    body: 'What a regular plan quietly takes for a portfolio identical to the direct one. Measured against the funds you actually hold.',
  },
  {
    figure: '19 of 44',
    label: 'windows',
    body: 'How often ranking funds by past return beat its category. Worse than a coin — so this app does not do it.',
  },
  {
    figure: 'Every',
    label: 'figure',
    body: 'Names its source on one page. AMFI, SEBI, the Income Tax Act — never “our model”.',
  },
]

/** Companies really returned by `/look-through`, at their real weights. */
const OWNED = [
  { name: 'HDFC Bank', industry: 'Banks', pct: 2.2, width: 100, via: 2 },
  { name: 'Power Grid', industry: 'Power', pct: 1.8, width: 82 },
  { name: 'ITC', industry: 'Diversified FMCG', pct: 1.7, width: 77 },
  { name: 'ICICI Bank', industry: 'Banks', pct: 1.6, width: 73 },
]

const LookThroughVisual = (
  <div className="flex flex-col gap-3 rounded-xl border bg-card p-4">
    <div className="flex items-baseline gap-2">
      <span className="num text-2xl font-semibold text-v-indigo">50</span>
      <span className="text-xs text-muted-foreground">companies, behind 3 funds</span>
    </div>
    <p className="flex items-center gap-2 rounded-lg border border-v-violet/25 bg-v-violet-soft/60 px-2.5 py-1.5 text-xs">
      <Layers2 className="size-3.5 shrink-0 text-v-violet" aria-hidden />
      1 company reaches you through more than one fund
    </p>
    <ul className="flex flex-col gap-2">
      {OWNED.map((c) => (
        <li key={c.name} className="flex flex-col gap-1">
          <span className="flex items-baseline justify-between gap-2 text-xs">
            <span className="truncate">
              <span className="font-medium">{c.name}</span>
              <span className="text-muted-foreground"> &middot; {c.industry}</span>
              {c.via && (
                <span className="font-medium text-v-violet-ink"> &middot; via {c.via} funds</span>
              )}
            </span>
            <span className="num shrink-0 font-semibold">{c.pct}%</span>
          </span>
          <span className="h-1.5 overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-v-indigo"
              style={{ width: `${c.width}%` }}
            />
          </span>
        </li>
      ))}
    </ul>
  </div>
)

const CostVisual = (
  <div className="flex flex-col gap-3 rounded-xl border bg-card p-4">
    <p className="flex flex-wrap items-baseline gap-x-3">
      <span className="num text-3xl font-semibold leading-none text-loss">
        &#8377;163<span className="text-sm font-normal text-muted-foreground">/yr</span>
      </span>
      <span className="text-xs text-muted-foreground">
        going to a distributor for a portfolio you could hold for less
      </span>
    </p>
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-xs font-medium">
          SBI Small Cap Fund &ndash; Regular Plan
        </span>
        <span className="num shrink-0 text-xs font-semibold text-loss">&#8377;163/yr</span>
      </div>
      <p className="tnum mt-0.5 text-[11px] text-muted-foreground">
        &#8377;19,697 held &middot; 0.8% a year more than direct
      </p>
      <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-snug">
        <ArrowRight className="mt-0.5 size-3 shrink-0 text-gain" aria-hidden />
        <span>
          <span className="text-muted-foreground">Buy instead: </span>
          <span className="font-medium">SBI Small Cap Fund &ndash; Direct Plan</span>
        </span>
      </p>
    </div>
  </div>
)

const HonestyVisual = (
  <div className="flex flex-col gap-3 rounded-xl border bg-card p-4">
    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      What this app cannot do
    </p>
    <p className="text-sm leading-relaxed">
      It cannot tell you which fund will do best. Ranking funds by past
      three-year return put the <strong>worse</strong> quartile on top by{' '}
      <span className="num">0.9</span> percentage points.
    </p>
    <div className="flex flex-wrap gap-2">
      {['AMFI', 'SEBI', 'Income Tax Act', 'IIM Ahmedabad'].map((src) => (
        <span
          key={src}
          className="rounded-md border bg-muted/40 px-2 py-1 text-[11px] text-muted-foreground"
        >
          {src}
        </span>
      ))}
    </div>
  </div>
)

const SECTIONS = [
  {
    icon: ScanSearch,
    eyebrow: 'Look through',
    title: 'Three funds are not three things',
    visual: LookThroughVisual,
    body: 'They are a few hundred companies, and some of them arrive through more than one fund at once. That is one bet, not two — and it is invisible everywhere else.',
    tone: 'text-v-indigo',
    tint: 'from-v-indigo/12',
  },
  {
    icon: Receipt,
    eyebrow: 'Cost',
    title: 'The one fund decision that measured out as real',
    visual: CostVisual,
    body: 'Not which fund. Which plan. We price the gap against the funds in your account, name the direct scheme to buy instead, and show the tax the switch would trigger before you make it.',
    tone: 'text-v-emerald',
    tint: 'from-v-emerald/12',
  },
  {
    icon: ShieldQuestion,
    eyebrow: 'Honesty',
    title: 'A page for everything we get wrong',
    visual: HonestyVisual,
    body: 'Where each number came from, how often the score has actually been right, and when it is no better than a coin. It leads with the losses, because a scoreboard that leads with its wins is marketing.',
    tone: 'text-v-amber',
    tint: 'from-v-amber/12',
  },
]

export function Landing() {
  return (
    <div className="flex flex-col gap-20 pb-24 sm:gap-28">
      {/* ---------------------------------------------------------- hero
          Split, not centred. A centred headline over a dark mesh is the
          default every generated landing page reaches for; this one has an
          actual product surface to show, so the surface takes half the room. */}
      <section className="relative -mt-4 grid items-center gap-12 pt-6 lg:min-h-[64dvh] lg:grid-cols-[1.05fr_1fr] lg:gap-8 lg:pt-10">
        {/* Fixed and pointer-events-none: it never repaints while scrolling. */}
        <div
          className="field pointer-events-none absolute inset-x-0 -top-24 bottom-0 -z-10 text-foreground opacity-70"
          aria-hidden
        />
        <div
          // Sized in vw first, capped in rem. At a fixed 64rem this was 1024px
          // of decoration on a 390px screen and pushed every page on the phone
          // sideways by 317px -- a background wash that made the content scroll.
          className="pointer-events-none absolute -top-32 left-1/2 -z-10 h-[34rem] w-[92vw] max-w-[64rem] -translate-x-1/2 opacity-[0.16] blur-3xl"
          style={{
            background:
              'radial-gradient(45% 55% at 30% 40%, var(--v-cyan) 0%, transparent 70%), radial-gradient(45% 55% at 70% 30%, var(--v-indigo) 0%, transparent 70%)',
          }}
          aria-hidden
        />

        <div className="flex flex-col items-start gap-6">
          <span className="rise inline-flex items-center gap-2 rounded-full border border-v-cyan/30 bg-v-cyan-soft/70 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-v-cyan-ink">
            <Sparkles className="size-3.5" aria-hidden />
            Built on what is measurable
          </span>

          {/* 3-5 words would earn text-7xl. This is nine, so it starts lower
              and the line count stays at three. */}
          <h1 className="rise rise-1 font-heading text-4xl font-semibold leading-[1.05] tracking-[-0.03em] sm:text-5xl lg:text-6xl">
            Most investing apps
            <br />
            guess. This one
            <br />
            {/* Solid, with the gradient moved to a bar underneath it.
                `bg-clip-text` + `text-transparent` measured 1.00:1 against the
                page -- the accessibility walk was right to fail it, because a
                gradient clipped to glyphs has no contrast to check and
                disappears completely wherever the clip is unsupported. The
                colour pop is still there; it is just not load-bearing. */}
            <span className="relative inline-block text-v-cyan-ink">
              shows its working.
              <span
                aria-hidden
                className="absolute inset-x-0 -bottom-1 h-1.5 rounded-full bg-gradient-to-r from-v-cyan via-v-indigo to-v-violet opacity-80"
              />
            </span>
          </h1>

          <p className="rise rise-2 max-w-xl text-lg leading-relaxed text-muted-foreground">
            NexTrade reads the funds and stocks you already own, prices what they
            cost you every year, and names the source of every number it prints.
          </p>

          <div className="rise rise-3 flex flex-wrap items-center gap-3">
            <Link to="/login" className={cn(buttonVariants({ size: 'lg' }), 'group gap-2')}>
              See your portfolio
              <ArrowRight
                className="size-4 transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </Link>
            <Link
              to="/why"
              className={buttonVariants({ variant: 'outline', size: 'lg' })}
            >
              Where the numbers come from
            </Link>
          </div>

          <p className="rise rise-4 text-sm text-muted-foreground">
            No brokerage account needed. It never places an order.
          </p>
        </div>

        {/* The product, tilted. Three real surfaces from the dashboard rather
            than a stock screenshot or an invented chart. */}
        <div className="stage-3d rise rise-3 hidden lg:block" aria-hidden>
          <div className="float-slow">
          <div className="tilt-3d relative mx-auto min-h-[23rem] w-full max-w-md">
            <div className="rounded-2xl border bg-card p-6 shadow-2xl shadow-foreground/10">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Portfolio value
              </p>
              <p className="num num-display mt-2 text-5xl font-semibold leading-none">
                &#8377;1,52,311
              </p>
              <span className="mt-3 inline-flex items-center gap-1 rounded-full bg-gain/12 px-2.5 py-1 text-sm font-medium text-gain">
                <span className="num">+&#8377;66,218</span>
                <span className="num opacity-75">(+76.9%)</span>
              </span>
            </div>

            <div
              className="absolute -left-14 top-[9.5rem] w-64 rounded-xl border bg-card p-4 shadow-xl shadow-foreground/10"
              style={{ transform: 'translateZ(60px)' }}
            >
              <div className="flex items-center gap-2">
                <span className="flex size-6 items-center justify-center rounded-md bg-v-emerald/15 text-v-emerald">
                  <Coins className="size-3.5" aria-hidden />
                </span>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-v-emerald-ink">
                  Do this one thing
                </p>
              </div>
              <p className="mt-2 text-sm font-semibold leading-snug">
                Use the &#8377;1.25 lakh tax-free gain every year
              </p>
              <p className="num mt-1 text-xl font-semibold text-gain">
                &#8377;15,625<span className="text-xs font-normal text-muted-foreground">/yr</span>
              </p>
            </div>

            <div
              className="absolute -right-6 top-[12.5rem] w-60 rounded-xl border bg-card p-4 shadow-xl shadow-foreground/10"
              style={{ transform: 'translateZ(110px)' }}
            >
              <div className="flex items-center gap-2">
                <Layers2 className="size-3.5 text-v-violet" aria-hidden />
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  What you actually own
                </p>
              </div>
              <p className="num mt-2 text-2xl font-semibold text-v-indigo">50</p>
              <p className="text-xs text-muted-foreground">
                companies, behind 3 funds
              </p>
              <div className="mt-2 flex flex-col gap-1.5">
                {[100, 78, 62].map((w) => (
                  <div key={w} className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-v-indigo" style={{ width: `${w}%` }} />
                  </div>
                ))}
              </div>
            </div>
          </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------ the proof
          Under the hero, not inside it. Three figures the product can
          defend, each linked to the page that defends it. */}
      <InView as="section" className="grid gap-4 sm:grid-cols-3">
        {PROOF.map((p, i) => (
          <div
            key={p.figure}
            className="lift flex flex-col gap-2 rounded-2xl border bg-card p-6"
            style={{ transitionDelay: `${i * 0.06}s` }}
          >
            <p className="flex items-baseline gap-2">
              <span className="num text-3xl font-semibold text-v-cyan-ink">{p.figure}</span>
              <span className="text-sm text-muted-foreground">{p.label}</span>
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">{p.body}</p>
          </div>
        ))}
      </InView>

      {/* ------------------------------------------------- what it does
          Alternating sides. Three equal cards in a row is the shape every
          generated page uses, and it flattens three unequal ideas. */}
      <div className="flex flex-col gap-16 sm:gap-24">
        {SECTIONS.map((s, i) => {
          const Icon = s.icon
          const flipped = i % 2 === 1
          return (
            <InView
              key={s.title}
              as="section"
              className={cn(
                'grid items-center gap-8 lg:grid-cols-2 lg:gap-16',
                flipped && 'lg:[&>*:first-child]:order-2',
              )}
            >
              <div className="flex flex-col items-start gap-4">
                <span
                  className={cn(
                    'flex size-11 items-center justify-center rounded-xl border bg-card',
                    s.tone,
                  )}
                >
                  <Icon className="size-5" aria-hidden />
                </span>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {s.eyebrow}
                </p>
                <h2 className="font-heading text-2xl font-semibold leading-tight tracking-[-0.02em] sm:text-3xl">
                  {s.title}
                </h2>
                <p className="max-w-lg text-[15px] leading-relaxed text-muted-foreground">
                  {s.body}
                </p>
              </div>
              {/* The actual surface, not a placeholder. This was a 4:3 box
                  with the section's own icon at 25% opacity inside it --
                  a spacer shipped as a design, and the exact thing that makes
                  a landing page read as generated. Every figure below is one
                  the product really prints. */}
              <div
                className={cn(
                  'rounded-2xl border bg-gradient-to-br to-transparent p-5 sm:p-6',
                  s.tint,
                )}
              >
                {s.visual}
              </div>
            </InView>
          )
        })}
      </div>

      {/* --------------------------------------------------------- close */}
      <InView as="section" className="relative overflow-hidden rounded-3xl border bg-card p-10 text-center sm:p-16">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.11]"
          style={{
            background:
              'radial-gradient(70% 120% at 20% 0%, var(--v-cyan) 0%, transparent 60%), radial-gradient(70% 120% at 80% 100%, var(--v-indigo) 0%, transparent 60%)',
          }}
          aria-hidden
        />
        <div className="relative flex flex-col items-center gap-5">
          <h2 className="font-heading text-3xl font-semibold tracking-[-0.02em] sm:text-4xl">
            Add one holding. See what it costs you.
          </h2>
          <p className="max-w-xl text-[15px] leading-relaxed text-muted-foreground">
            The first answer takes two fields and about a minute. Nothing here asks
            for a broker login, and nothing here places an order.
          </p>
          <Link to="/login" className={cn(buttonVariants({ size: 'lg' }), 'group gap-2')}>
            Get started
            <ArrowRight
              className="size-4 transition-transform group-hover:translate-x-0.5"
              aria-hidden
            />
          </Link>
        </div>
      </InView>
    </div>
  )
}
