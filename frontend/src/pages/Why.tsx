/**
 * Where every number on the front page comes from, and what it is worth.
 *
 * The content already existed and was scattered across three pages: the track
 * record renders inside `Decide`, the factor evidence inside `Research`, the
 * coverage figures inside `Screener`. Scattered, none of it answers the question
 * somebody actually has, which is *"why should I believe the number I am looking
 * at"* — and that question is asked about the front page, not about whichever
 * page happens to hold the evidence.
 *
 * §14's coverage rule applied to the app's own front page: **every figure on
 * `Today` appears here with its source named.** A source is a file, an endpoint
 * or a named study — never "our model".
 *
 * The uncomfortable half is first. This page opens with what the app CANNOT do,
 * because a scoreboard that leads with its wins is marketing.
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchLevers } from '@/lib/portfolio-api'
import { Notice } from '@/components/ui/notice'
import { Panel } from '@/components/ui/panel'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * Every figure the front page can show, and where it is computed.
 *
 * Kept as data rather than prose so it can be checked against the app. A
 * paragraph claiming "everything is sourced" is not a coverage rule; a list
 * with a row per figure is.
 */
export const SOURCES: {
  figure: string
  source: string
  worth: string
}[] = [
  {
    figure: 'What your portfolio is worth',
    source: 'Your own transactions, priced at AMFI’s published NAV for each scheme code.',
    worth: 'Exact, up to the age of the NAV — which the page states when it is stale.',
  },
  {
    figure: 'Returns and XIRR',
    source: 'Your transaction dates and amounts, against the same NAV series.',
    worth:
      'Arithmetic on your own money. A holding whose price could not be fetched is excluded by name, never counted at zero.',
  },
  {
    figure: 'Expense ratio, and the direct-plan saving',
    source:
      'AMFI’s monthly TER filing, cross-checked against Groww’s published figure. Both are shown when they disagree by more than 0.10pp.',
    worth:
      'A measured fee difference, not an estimate. This is the one signal this app has tested and found to work.',
  },
  {
    figure: 'The fund score and its rank',
    source: 'NAV history for the fund and its category peers, scored in the open.',
    worth:
      'It is right about 64% of the time on the sample it was tested against, and its own cost ingredient beats the composite. That is stated on the page.',
  },
  {
    figure: 'Base rates — “what this category has done to people before”',
    source: 'Rolling windows across the whole category’s NAV history.',
    worth:
      'A count, not a forecast. The denominator is always shown, because 43 of 52 and 43 of 44 are different claims.',
  },
  {
    figure: 'Tax figures',
    source:
      'The Income Tax Act’s current rates and thresholds, including the s.112A exemption and s.113 marginal relief.',
    worth: 'Arithmetic on a published rule. Not advice, and not a filing.',
  },
  {
    figure: 'What you own through your funds',
    source: 'The AMCs’ own monthly portfolio disclosures, which SEBI requires.',
    worth:
      'Seven AMCs have a source we have verified, so this covers part of a portfolio and says which part. It never reports what it could not read as zero.',
  },
  {
    figure: 'Factor evidence',
    source:
      'The IIM Ahmedabad Indian Fama-French-Momentum library, survivorship-bias adjusted, monthly from October 1993. Built by academics with no stake in this app.',
    worth:
      'Thirty-two years of published returns. Each factor ships with its bad periods attached.',
  },
]

export function Why() {
  const { data, isPending } = useQuery({
    // The scoreboard, not the levers. Nothing on this page depends on the
    // horizon or the assumed return, so none is sent — and `monthly_sip` is
    // deliberately absent for the same reason as on `Decide`: the server
    // derives it, and passing 0 is not the same as not passing it.
    queryKey: ['levers', 'why'],
    queryFn: () => fetchLevers({ years_remaining: 15 }),
    retry: false,
  })
  const record = data?.track_record ?? null

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="font-heading text-3xl font-semibold leading-[1.1] tracking-[-0.02em] sm:text-4xl">
          Why you should believe any of this
        </h1>
        <p className="max-w-3xl text-[15px] leading-relaxed text-muted-foreground">
          Every number on your dashboard comes from somewhere. This page names
          where, and says what each one is actually worth — including the ones
          that are worth less than they look.
        </p>
      </header>

      {/* First, deliberately. A scoreboard that leads with its wins is
          marketing, and this app's central finding is a negative one. */}
      <Panel title="What this app cannot do">
        <div className="flex flex-col gap-3 text-[15px] leading-relaxed">
          <p>
            It cannot tell you which fund will do best. We tested that directly:
            ranking funds by their past three-year return put the{' '}
            <strong>worse</strong> quartile on top by 0.9 percentage points, and
            won 19 of 44 windows — worse than a coin.
          </p>
          <p>
            It will not tell you to sell an underperformer, set a stop-loss, or
            act on a manager change, and it never places an order. Each of those
            has a reason rather than a policy, and{' '}
            <Link to="/decide" className="underline underline-offset-2">
              the levers page
            </Link>{' '}
            shows what is left once they are gone.
          </p>
          <p className="text-muted-foreground">
            What it can do is cost. That is a smaller claim than most apps make,
            and it is the one that survived being tested.
          </p>
        </div>
      </Panel>

      <Panel title="How often we have actually been right">
        {isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : record ? (
          <div className="flex flex-col gap-3">
            <p className="max-w-3xl text-[15px] leading-relaxed">{record.plain}</p>
            <p className="num text-sm text-muted-foreground">
              {record.wins} of {record.windows} windows
              {record.beats_chance ? '' : ' — no better than a coin on this sample'}
            </p>
            {data?.better_signal && <Notice>{data.better_signal}</Notice>}
            <p className="max-w-3xl text-xs text-muted-foreground">
              Measured on {record.measured_on} by re-running the tests against
              real NAV history, not by copying an old result.
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Add a holding and this will show the score’s record against the
            category your money is actually in.
          </p>
        )}
      </Panel>

      <Panel title="Where each number comes from">
        <div className="-mx-4 overflow-x-auto sm:mx-0">
          <table className="w-full min-w-[40rem] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="py-2 pr-4 font-normal">The figure</th>
                <th className="py-2 pr-4 font-normal">Where it comes from</th>
                <th className="py-2 font-normal">What it is worth</th>
              </tr>
            </thead>
            <tbody>
              {SOURCES.map((row) => (
                <tr key={row.figure} className="border-b align-top last:border-0">
                  <th className="py-2.5 pr-4 text-left font-medium">{row.figure}</th>
                  <td className="py-2.5 pr-4 text-muted-foreground">{row.source}</td>
                  <td className="py-2.5 text-muted-foreground">{row.worth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="When a number is missing">
        <div className="flex flex-col gap-3 text-[15px] leading-relaxed">
          <p>
            You will see <span className="num">n/a</span> more often here than in
            other apps. That is deliberate. A zero where we could not measure
            something reads as good news — 0% overlap looks like perfect
            diversification, a missing expense ratio sorts as the cheapest fund —
            and both readings flatter the thing we failed to check.
          </p>
          <p className="text-muted-foreground">
            So a figure we could not compute says so, and says why.
          </p>
        </div>
      </Panel>
    </div>
  )
}
