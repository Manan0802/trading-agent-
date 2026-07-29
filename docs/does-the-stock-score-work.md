# Does the stock score work?

**No signal shown.** The Research page keeps saying the score has not been shown
to predict, because after three attacks on the first flattering result, that is
still the honest answer.

This is the question `does-the-score-work.md` asked of the fund score — which
did not predict, and the product was rebuilt on cost. The stock score has now
been put through the same test.

Run it: `python scripts/validate_stock_score.py`. The defaults are the honest
invocation. The ledger at `app/data/stock_score_ledger.csv` keeps every run.

## Method

Every input is reconstructed as it stood on a past fiscal year end: EPS and net
income from that year's income statement, book value from that year's balance
sheet, the share price on that date. Sector medians come from the same
cross-section, not from today's committed table — scoring 2023 against 2026's
medians would be marking the exam with the answer sheet.

Each year's cross-section is ranked by the live `score_stock` function. Two
readings: the spread between top and bottom quartile forward returns, and the
Spearman rank correlation between score and forward return across every company
in that year — the information coefficient.

## The result, and three attacks on it

**First run: NIFTY 500, scored on the fiscal year end. +15.1% a year, three of
three.** Far too good. A suspiciously good number is a thing to attack.

**Attack one: those figures had not been filed yet.** Indian companies publish
annual results months after the year end, so scoring on 31 March uses numbers
nobody had until August and starts the forward return before the market could
react to them. Re-run six months lagged: the spread falls to **+10.6%**. The
lookahead was worth about 4.5 percentage points a year.

**Attack two: two observations is not a sample.** The lag costs a year, leaving
two. A score with no skill lands two the same way a quarter of the time. The
script now refuses to print a conclusion below five years — because the version
of it written an hour earlier declared success on those two, which is the exact
self-flattery this app exists to prevent, produced by the app.

**Attack three, and the one that settles it: change the universe and the answer
inverts.** The same test, same lag, on the NIFTY 50:

| universe | years | spread | mean IC |
|---|---:|---:|---:|
| NIFTY 500 | 2 | **+10.6%** | not yet measured |
| NIFTY 50 | 2 | **−5.0%** | **−0.084** |

On the large caps the top quartile *lost* to the bottom in both years, and the
rank correlation is slightly negative — the score orders them faintly backwards.
The NIFTY 50 cut is noisy (45 companies, so quartiles of eleven), but a result
that reverses sign when you change the index is not a signal. The likeliest
reading of the NIFTY 500 number is a size effect: that index carries mid and
small caps, and 2023-24 was a historic run for them. Any score that leans toward
smaller or cheaper companies looked brilliant in that window without knowing
anything.

## What the test does not cover

Two of the score's five weighted inputs are never exercised. `dividend_yield` is
passed as `None` and `promoter_history` as empty for every observation, so the
dividend factor returns its neutral constant throughout and the promoter-stake
adjustment — which the model's own docstring calls the cheapest read on India's
dominant equity risk — has never been tested at all. Whatever this concludes is
a claim about 87 of the score's 100 points.

**Survivorship, direction unknown.** `stock_universe.json` holds today's
constituents, so every observation is drawn from survivors. An earlier version
of this document claimed that flatters the bottom quartile and therefore
understates the spread. That is only one channel. India's characteristic
blow-ups — Yes Bank, DHFL, IL&FS, Reliance Capital — read as respectable on
P/E, ROE and earnings growth until the governance or leverage failure that a
score with no debt or auditor signal cannot see. Every such name scored well and
then collapsed, and every one is now missing from the top quartile's average.
The net direction is genuinely unsigned, and the earlier claim was too
confident.

Nearly every remaining defect biases *toward* finding a spread. A score that
still cannot clear its own bar with several thumbs on the scale in its favour is
a conservative negative.

## Why waiting will not fix it by itself

yfinance serves a *rolling* five fiscal years. As a new year becomes usable the
oldest ages out at about the same rate, so re-running this in two years would
still show two or three usable years and the sample would never reach five —
which puts quiet pressure on lowering the bar rather than meeting it. Every run
now appends to `app/data/stock_score_ledger.csv`, keyed by universe, lag and
year, so the count grows monotonically instead of depending on Yahoo's retention
window. Universe and lag are part of the key because a NIFTY 50 run and a NIFTY
500 run are different experiments, and pooling them under a bare year would
blend two answers into one that is neither.

## One claim that was checked and did not hold

A methodology audit flagged, as its highest-severity finding, that `history(...)`
returns split-adjusted prices while `income_stmt` EPS is as-filed — which would
make any company that later split look artificially cheap, concentrated in
exactly the companies whose price had run. It could not run yfinance to confirm
it and supplied a verification recipe instead.

The recipe was run. It does not reproduce: yfinance split-adjusts the statement
line items too. Nestlé India's P/E computed this way reads 66.7, 76.1 and 85.3
across its 2025 split; Bajaj Finance reads 26.1, 32.9 and 30.2 across its own.
Both are continuous and both sit where the market actually valued them. Recorded
here so nobody re-litigates it.

## What the app says

Unchanged in substance: the score has not been shown to predict. The Research
page now says what was measured, that the answer inverts between indices, and
what would change the wording.
