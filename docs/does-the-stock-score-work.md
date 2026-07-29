# Does the stock score work?

**Not established. The direction is encouraging and the sample is too small to
claim anything.** The Research page keeps saying the score has not been shown to
predict, because that is still true.

This is the same question asked of the fund score in `does-the-score-work.md`,
which was answered — it did not predict, and the product was rebuilt on cost.
The stock score has now been tested the same way for the first time.

Run it yourself: `python scripts/validate_stock_score.py --index "NIFTY 500"
--limit 500 --lag-months 6`

## Method

Every input is reconstructed as it stood on a past fiscal year end: EPS and net
income from that year's income statement, book value from that year's balance
sheet, the share price on that date. Sector medians are computed from the same
cross-section rather than from today's committed table — scoring 2023 against
2026's medians would be marking the exam with the answer sheet.

Each year's cross-section is ranked by the live `score_stock` function, split
into quartiles, and the top and bottom quartiles' forward one-year returns are
compared. Same bar the fund score failed.

## What came back

NIFTY 500, scored on the fiscal year end itself:

| year | n | top quartile | bottom quartile | spread |
|---|---:|---:|---:|---:|
| 2023-03-31 | 218 | 130.7% | 98.3% | +32.4% |
| 2024-03-31 | 294 | 18.5% | 13.8% | +4.6% |
| 2025-03-31 | 308 | 11.8% | 3.5% | +8.3% |

Three of three, +15.1% a year. Which is far too good, and a suspiciously good
result is a thing to attack rather than publish.

## The first attack: those numbers had not been filed yet

Indian companies file annual results months after the year end. Scoring on
31 March uses figures nobody had until August, and starts the forward return
before the market could have reacted to them. In a year the market ran, that is
worth a great deal.

Re-run with a six-month lag, so only figures that had actually been published
are used:

| year | n | top quartile | bottom quartile | spread |
|---|---:|---:|---:|---:|
| 2023-09-30 | 100 | 68.0% | 50.9% | +17.2% |
| 2024-09-30 | 125 | −2.8% | −6.9% | +4.1% |

The lookahead was worth about 4.5 percentage points a year. The spread survives
at +10.6% — but the lag costs a year of sample, leaving two.

## Why this is not a finding

**Two annual observations.** A score with no skill at all lands both the same
way 25% of the time. The fund score was judged on sixty overlapping three-year
windows; this is two. The script now refuses to print a conclusion below five
years, because an earlier version of it declared success on those two — the
exact self-flattery this app exists to avoid, written by the app.

**The universe is today's index.** `stock_universe.json` holds the current
NIFTY 500. Companies that collapsed and were dropped are absent, so every
observation here is drawn from survivors. That likely flatters the *bottom*
quartile most, since the worst outcomes are the ones missing — which would if
anything understate the spread — but the whole exercise is still run on a
sample of winners and cannot be read as what a real screen would have returned.

**Overlapping and few.** Three fiscal year ends across one unusually strong
stretch of Indian equities. 2023-24 was a historic year for mid and small caps;
a cross-section skewed that way returning 100%+ says more about the period than
the model.

## What the app says as a result

Unchanged. The Research page still reads:

> Unlike the fund score, this one has not been backtested: point-in-time
> fundamentals for past years are not something we can get, so we cannot say
> whether a high score has predicted anything.

The first clause of that is now out of date — the test exists and is in this
repo. The claim it protects is not: the score still has not been *shown* to
predict, and two years cannot show it. The wording will change when the sample
reaches five years, in whichever direction the evidence goes.

## Re-run it

The data deepens by one fiscal year annually. Yahoo rate-limits after roughly a
thousand companies, so a 500-name run twice in an hour will be blocked; the
script now says so explicitly rather than reporting an empty result as though
the market had nothing to show.
