# Bachatt sip-optimizer: what it does, and where NexTrade stands against it

Read 2026-07-27 from `~/bachattdev/sip-optimizer` (read-only; nothing there was
modified). This is a teardown of the *logic*, not the code — we take no APIs and
copy no implementation. Where their method is better than ours, the gap is
named. Where it is worse, that is named too, because "10x better" means beating
the good parts and not inheriting the bad ones.

---

## 1. How their system is shaped

**Everything is precomputed nightly.** `scripts/fill_metrics.py` runs as a cron
over ~3,000 funds and writes metric columns onto the `funds` table. Every API
endpoint then reads a column. Nothing is computed inside a request.

The order matters and is enforced: metrics → `bachatt_fund_score` → grades →
risk score. Grades derive from score percentiles, and the risk score consumes
columns the same run just populated.

Their storage is Postgres with a 22M-row `nav_history` keyed `(fund_id,
nav_date)`. Their own `CLAUDE.md` records that the join key is `fund_id`, not
`scheme_code` — joining on the AMFI text code returns empty. Ours is a JSON
disk cache, which is the right call at our scale but is the reason a cold
category ever took 38 seconds.

---

## 2. The fund score, in full

### Quality — three pillars

```
consistency = 0.50·roll_1y + 0.25·roll_6m + 0.15·roll_3m + 0.10·roll_1m
performance = 0.55·ret_3y  + 0.30·ret_1y  + 0.15·ret_3m
risk        = 1 − volatility
quality     = 0.45·consistency + 0.40·performance + 0.15·risk
```

The distinction that matters: **`roll_*` are rolling returns — the mean of every
overlapping window of that length across the fund's whole history. `ret_*` are
point-to-point trailing returns.** Consistency, the largest pillar, is built
entirely from rolling windows, so a fund that happened to end its 3-year window
on a good day cannot buy its way to the top.

### Final score

```
final = 0.73·quality + 0.15·momentum + 0.12·(1 − drawdown)
```

### Hybrid normalisation — the part worth stealing

Every metric goes through `hyb(series, w_rank, w_mag)`:

```
w_rank · percentile_rank(series)  +  w_mag · minmax(series, capped at 0.95)
```

Percentile rank alone is stable but throws away magnitude: the #1 fund gets 1.0
whether it beat #2 by 0.1pp or 8pp. Min-max alone is magnitude-faithful but one
outlier squashes everyone else. They blend, and — this is the subtle bit —
**the weights shift by horizon**:

| metric | w_rank | w_mag |
|---|---|---|
| roll_1y | 0.70 | 0.30 |
| roll_6m | 0.75 | 0.25 |
| roll_3m | 0.80 | 0.20 |
| roll_1m | 0.90 | 0.10 |
| ret_3y | 0.70 | 0.30 |
| ret_3m | 0.85 | 0.15 |

Longer horizon → trust the magnitude more. Shorter horizon → magnitude is noise,
so lean almost entirely on rank. That is a genuinely well-reasoned choice and
our pure-percentile scorer has no equivalent.

### Out-of-sample scoring

Funds outside the eligible universe still get a comparable score, computed
against the eligible distribution **without entering it** (`_make_oos_hybrid`).
So displaying a score for a fund a user holds cannot shift the peer percentiles
of the funds being recommended. Clean separation of "scored for display" from
"scored for ranking".

### Grading by value cutoff, not rank position

```
Very Good ≥ p90    Good ≥ p65    Avg ≥ p30    Bad below
```

Graded by `score >= cutoff`, never by position, so funds with identical scores
always land in the same grade. Peer group is `category`, except Debt and
Commodity which grade within `(category, sub_category)`.

---

## 3. The risk score — a separate model, and the reason for it

`scripts/fill_risk_scores.py` opens with the argument, and it is correct:

> SEBI's riskometer classifies 100% of `Equity Scheme` (177 funds) and
> `Equity Index Fund` (154 funds) as "Very High" — zero differentiation between
> a Large Cap fund (~12.6 volatility) and a Small Cap fund (~15.9).

So they built their own, in the same six-tier vocabulary so nobody has to learn
a new one:

```
volatility 55%  (rank 0.60 / mag 0.40)   ↑ risk
drawdown   25%  (rank 0.70 / mag 0.30)   ↑ risk
sortino    15%  (rank 1.00 / mag 0.00)   ↓ risk, rank-only
momentum    5%  (rank 0.70 / mag 0.30)
```

Sortino is rank-only on purpose: raw values reach ~208 for near-zero-volatility
overnight funds, and a magnitude blend would be destroyed by that. Tiers are
global (one peer group = the whole universe), because cross-category
comparability is the entire point.

**We have nothing here.** We surface no risk classification at all.

---

## 4. Momentum and drawdown (14 days)

Linear recency weights `[1..14]` over log returns, so the most recent day counts
14× the oldest.

- **Adaptive trigger**: `1.5 × rolling_7d_mean`, floored at 0. A fund is only
  "moving" relative to its own recent pace, not an absolute bar.
- **Magnitude-weighted, not binary**: contribution is `clip(actual/trigger, 1.0,
  2.5)` rather than 1-or-0. How far above the trigger matters.
- **Drawdown threshold** `log(1 − 0.01)`, contribution `clip(1 + depth/|thr|,
  1.0, 3.0)`.
- Before any of it, `_cap_log_returns_for_metrics` **neutralises days with
  |simple return| > 25%** as splits/restatements/bad NAV.

That last line is a real data-hygiene lesson. We drop zero-NAV rows; we do not
catch a 40% one-day artefact.

---

## 5. The optimizer

`services/optimizer.py`, SLSQP mean-variance, three objectives:

- `sharpe`, `sortino` — the textbook ones.
- `bachatt` — maximise `portfolio_score − 0.05 × annual_volatility`.

The comment explains the choice and it is a good one: a ratio objective
(`score / vol`) blows up when a near-zero-variance fund (arbitrage) collapses
the denominator. A linear combination cannot. It also means the "return" signal
is the *score*, not the historical mean return — dodging the classic
mean-variance failure of extrapolating past means.

**Constraint as soft penalty with a smooth min.** The constraint is
`rolling_30d_min_return ≥ max_loss_threshold`. Rather than a hard `np.min()` —
which gives SLSQP a discontinuous gradient every time the binding window
changes — they use a softmin:

```
−log(Σ exp(−α·x)) / α        with α = 50
```

Regime scales the threshold: bullish ×1.5, bearish ×0.5. Penalty weight is 1.0
for the bachatt objective (the score already encodes risk) and 1000 otherwise.

**Failure handling is serious**: three deterministic starting points (regime
init, seeded perturbation around bounds midpoint, reversed priority), then
`trust-constr`, then equal weights. Bounds are checked for feasibility first
(`Σlower ≤ 1 ≤ Σupper`) because commodity caps summing under 1.0 made every
attempt fail with "inequality constraints incompatible".

**Tactical post-adjustment**: after optimisation, each fund's weight is
multiplied by a bucket factor keyed on `current_weight / suggested_weight`, with
separate bucket tables for momentum funds, drawdown funds, and neutral. Drawdown
funds get scaled *down* hard (0.1× at ratio > 3). This is a buy-the-dip /
ride-the-trend overlay bolted onto a mean-variance result.

---

## 6. Repair — the layer that makes it a product

This is the part we most conspicuously lack. `portfolio_schedule_v2.py`:

The optimizer returns weights. Weights × amount gives rupees. **Funds have
minimum investment amounts, per frequency, set by the AMC** — synced from their
own API into `fund_min_investment` (`min_lumpsum`, `min_sip_daily`,
`min_sip_weekly`, `min_sip_monthly`).

If a fund's allocation falls below its minimum:

1. Look for a swap in the same slot whose minimum the amount *does* clear.
2. If none, drop the fund, add its rupees to a carry pool, redistribute with a
   per-fund cap, and emit a user-facing warning.
3. Every action is appended to an `events` list — `{stage, action, from, to,
   slot_key, amount}` — so the final allocation can explain itself.

`distribute_lumpsum` is stricter still: a constraint-satisfaction pass that
takes from lower-priority funds first, then from higher-priority *surplus*, with
a full rollback if the deficit still cannot be met. Then
`_round_to_10_preserving_total` rounds to ₹10 while keeping the sum exact.

Our splitter is `[60%, 40%]` with a flat ₹500 floor.

---

## 7. Market regime

`market_regime_nifty.py`. Nifty 50 vs 50/200 DMA, trailing P/E vs its own 5-year
average, and India VIX.

The good judgement is in the **depth requirement**: a death cross alone is not
bearish. It needs Nifty > 8% below the 200 DMA *and* the 50 DMA > 5% below it.
A shallow death cross is classified neutral — "transitional correction". That
single rule kills most whipsaw.

VIX overrides on top: > 25 forces bearish, > 20 downgrades bullish to neutral,
< 20 upgrades bearish to neutral.

When VIX is elevated, a three-phase crash-recovery ladder runs, and Phase 3 —
recovery confirmed — triggers on `15DMA > 50DMA`, checked *first*, because
short-term trend recovery outranks the other signals.

---

## 8. Stock scorer

10 weighted factors summing to 100:

```
pe 15 · eps_growth 12 · rsi 12 · macd 12 · roe 10 · ema_trend 10
pb 8 · delivery 9 · support 7 · div_yield 5
```

Three ideas worth taking:

- **Sector-relative, not absolute.** P/E is scored against the *sector* median
  (Energy 8.9, Consumer Defensive 53.4). An absolute P/E screen in India ranks
  every FMCG stock as expensive and every PSU bank as cheap, which is a sector
  bet dressed as a valuation signal.
- **Missing data scores `weight × 0.5`, never 0.** A fund or stock is not
  punished for a gap in the feed.
- **A bonus/penalty layer on top of the base score**, each surfaced as a named
  event: dual revenue+profit growth +3/+5/+7, promoter buying +3, promoter
  selling −3, two consecutive quarters of profit decline −4, price-down +
  delivery-up (accumulation) +3, price-up + delivery-down (distribution) −2.

**Delivery %** — the share of traded volume actually delivered rather than
squared off intraday — is an India-specific conviction signal we do not use at
all. Promoter stake change is the governance signal our own research flagged as
India's dominant risk.

RSI is scored as a Gaussian centred on 50, so both oversold and overbought
score low. That is a defensible choice for a buy-and-hold screen, though it
means a genuinely oversold quality name scores like an overbought one.

---

## 9. How they justify a recommendation

`top_funds_week.py` is disciplined about this in a way we are not.

A claim is only printed when the fund is **in the top 15% of its peer group AND
ranked #5 or better** on that metric. The peer group is its own `sub_category`,
falling back to `category` only when the sub-category has fewer than 5 funds —
and if even the category is too thin, no claim is made at all.

The rank number itself is deliberately *not* shown; only the value and period
("+6.2% (1M)"). Curated per-sector bullets can replace generic ones. A Gemini
pass can rewrite the bullets, with a rule-based fallback on any error.

We print every metric we have, unconditionally, for every fund.

---

## 10. Point-in-time scoring, and the basket NAV

`bachatt_score_as_of.py` recomputes the entire three-pillar score from NAV as of
a past date, so a backtest picks funds using only what was knowable then.

`maxx_weekly_index_nav.py` publishes their basket as its own NAV series
(base ₹100) and benchmarks it against **the same weekly cashflow into an index
fund** — the docstring calls this out explicitly: "apples-to-apples, not a
buy-and-hold price rebase". That is the same discipline our benchmark
comparison already uses, and it is the correct one.

---

# Where NexTrade actually stands

## Behind — and it is not close

| # | Gap | Them | Us |
|---|---|---|---|
| 1 | **Rolling returns** | Consistency (45% of quality) is built from means of *all* overlapping windows | Point-to-point CAGR only. One lucky endpoint moves our rank |
| 2 | **Normalisation** | Hybrid rank+magnitude, weights shifting by horizon | Pure percentile rank. #1 by 0.1pp scores the same as #1 by 8pp |
| 3 | **Return windows** | 8 (1m/3m/6m/1y trailing + rolling, 3y) | 2 (cagr_3y, consistency) |
| 4 | **Risk classification** | Own 6-tier cross-category score, built because SEBI's is flat | None |
| 5 | **Minimum investment** | Per fund, per frequency, from the AMC, with a swap/drop/redistribute repair loop and user-facing events | Flat ₹500 constant |
| 6 | **Expense ratio** | Synced per fund | Not integrated (already our own P0) |
| 7 | **AUM / fund size** | Synced per fund | Nothing |
| 8 | **Market regime** | Nifty DMA + P/E + VIX, with a depth requirement and crash phases | Nothing |
| 9 | **Stock scoring** | 10 sector-relative factors + bonus/penalty layer | Raw fundamentals printed |
| 10 | **Claim discipline** | Top-15% *and* rank ≤5, else silence | Every metric printed always |
| 11 | **Outlier hygiene** | Neutralise \|daily move\| > 25% | Only zero-NAV rows dropped |
| 12 | **Point-in-time** | Full as-of rescoring | No backtest exists |
| 13 | **Precompute** | Nightly cron, endpoints read columns | Per-request compute behind a cache |
| 14 | **Diversification rules** | Max 2 per sub-category, dominance detection, AMC spread | None |

## Ahead — and worth protecting

1. **Tax.** They have no tax logic at all. We compute both regimes with the
   breakeven deduction. For an Indian investor this is worth more than a 14-day
   momentum term.
2. **Goals.** No goal planner exists there. We have goal-specific inflation
   (education 10%, healthcare 13%).
3. **Whole balance sheet.** EPF/PPF/FD/ESOP classification and allocating new
   money against everything owned. They allocate only the money passing through
   their platform.
4. **Real XIRR on real transactions.** Theirs simulates a ₹1 SIP on fund NAV.
   Ours is the user's actual money with FIFO lot accounting. Different question;
   ours is the personal one.
5. **Honest benchmark caveats.** We refuse to benchmark sectoral and index funds
   at all, and vary the caveat by category. They compare everything to one Nifty
   50 index fund with no caveat.
6. **Free data.** No RDS, no SSM tunnel, no internal API.

## What we should deliberately NOT copy

1. **27% of the final score is a 14-day signal.** `0.15·momentum + 0.12·(1−drawdown)`
   is a two-week window driving more than a quarter of a score used to pick funds
   for multi-year SIPs. Our own research found short-horizon momentum does not
   survive Indian transaction costs and has no published Indian test for fund
   selection. This is their single biggest methodological weakness.
2. **Expense ratio is synced but not scored.** TER is the most replicated
   predictor of future fund returns that exists. They have the column and do not
   use it. We should.
3. **`PREFERRED_AMCS` with a 0.03 score delta.** A distribution-economics rule
   sitting inside what presents as a quality ranking. We are not a distributor
   and must never do this.
4. **Survivorship bias in the backtest universe.** `fetch_universe_fund_ids`
   filters on `bachatt_fund_score IS NOT NULL` — a *live* column. A fund wound up
   in 2023 is invisible to a 2022 backtest, so the backtest is optimistic by
   construction.
5. **Mean-variance for a retail SIP.** Even with the score-based objective, this
   is a lot of machinery whose output is dominated by a covariance matrix
   estimated from overlapping history. Their own `portfolio_suggestion.py`
   docstring says it best: the optimizer endpoint is "a numeric black box" and
   explainable rule-based reasoning was built separately for anything
   user-facing.
6. **LLM-written reasons over numbers.** They fall back to rules on error, which
   is right, but the hallucination surface is real and unnecessary.

---

# The plan to actually beat it

Ordered by evidence strength per unit of work, not by how impressive it sounds.

### Tier 1 — the score (this is the product)

1. **Rolling returns as the consistency backbone.** Compute rolling 1m/3m/6m/1y/3y
   means over all overlapping windows. Beat them by also carrying the *dispersion*
   of those windows (std, min, worst) — they compute it in
   `calculate_fund_trailing_returns` and throw it away in the score. "Beat its
   benchmark in 93% of 3-year windows *and its worst 3-year window was +4%*" is a
   materially stronger claim than a mean.
2. **Hybrid rank+magnitude normalisation**, with their horizon-shifting weights.
   Direct adoption; the reasoning is sound.
3. **Expense ratio as a first-class term.** AMFI's TER API is already verified
   working in our own notes. This is where we beat them outright, because it is
   the one input with replicated predictive power and they leave it on the floor.
4. **Rebalance the score toward the horizon the user actually has.** Their 27%
   two-week term becomes, for us, either zero or a clearly-labelled separate
   "recent momentum" display field that never enters the score used for a
   15-year goal.
5. **Outlier neutralisation** at |daily move| > 25% before any metric.

### Tier 2 — the things we simply do not have

6. **Own risk tier**, cross-category, six tiers, for the same reason theirs
   exists. Beat them by fitting it to the *goal horizon*, not just the fund:
   a small-cap fund is not "Very High" risk for a 20-year goal and "Very High"
   for a 2-year one — the same fund carries different risk per horizon.
7. **Minimum investment awareness.** No internal AMC API for us, but minimums
   are published per scheme and the *structure* — swap, drop, redistribute, emit
   an event — is the part that matters and is ours to build.
8. **Market regime**, with their depth requirement (it is the good part) — but
   used only to *narrate*, never to time. Howard Marks' framing from our own
   research: calibrate against where we are, never call tops.
9. **Stock scoring**, sector-relative, with the missing-data-is-neutral rule and
   a named bonus/penalty layer. Our 751-name universe is already built.

### Tier 3 — the credibility layer

10. **Point-in-time backtest — done honestly.** Recompute scores as-of, and fix
    their survivorship hole by snapshotting the universe as it was, not as it is.
    A backtest that admits dead funds is worth more than one that does not.
11. **Claim discipline.** Print a reason only when the fund genuinely leads its
    peer group. Silence is a feature.
12. **Precompute + nightly refresh.** Our disk cache is the right shape already;
    it needs a scheduled warm rather than a cold first visitor.

### Where we win on ground they never contested

Tax, goals, EPF/PPF, and real-money XIRR are ours already. Their app allocates
the money flowing through their platform; ours is supposed to advise on a whole
financial life. That is the actual moat — not out-optimising their optimiser.

---

# Part 2 — The data layer, traced end to end

Every external source they touch, what it feeds, and whether it is available to
us. All endpoint results below were probed live on 2026-07-27, not assumed.

## 2.1 Their sources

| Source | Endpoint | Feeds | Live for us? |
|---|---|---|---|
| AMFI daily NAV | `portal.amfiindia.com/spages/NAVOpen.txt` | `nav_history` (22M rows) | **Yes** — 200, 12,756 lines. Open-ended only, so smaller than NAVAll |
| AMFI AAUM | `amfiindia.com/api/average-aum-schemewise` | `fund_aum_history` per quarter | Partly — needs `strType=Typewise\|Categorywise`; current quarter returns empty |
| Bachatt internal | `investment.bachatt.app/fund-schemes/v2/internal/get-funds` | `bachatt_active`, **min investment per frequency**, `fund_size_cr`, **`expense_ratio`**, `investment_mode` | **No** — their own platform API |
| yfinance | `^NSEI`, `^INDIAVIX`, `GOLDBEES.NS`, `SILVERBEES.NS`, `*.NS` | regime, gold/silver signal, all stock fundamentals | **Yes** — already ours |
| NSE allIndices | `nseindia.com/api/allIndices` | Nifty trailing P/E, sector dividend yield | Cookie-gated |
| NSE quote-equity | `nseindia.com/api/quote-equity?...&section=trade_info` | **delivery %** | **No — 403 Access Denied.** Their own code silently degrades to `weight × 0.5` here |
| Screener.in | scraped `screener.in/company/{SYM}/` | **promoter holding, last 4 quarters** | **Yes** — 200, parsed Reliance promoters `[50.01, 50.0, 50.0, 50.48]` |
| niftyindices.com | yearly chunks from 1995 | index TRI history | Untested |
| Yahoo + Google News RSS | per-symbol / per-sector | `market_news` → Gemini summaries | Yes, with the licensing caveat they themselves flag |
| AMFI PDFs | per-SSD factsheet | `pdf_ingestion.py` | Yes |

**The single biggest structural advantage they have is not a clever algorithm —
it is `investment.bachatt.app`.** Per-fund, per-frequency minimum investment,
expense ratio and fund size arrive as one authenticated call because they are a
distributor. Everything the repair loop does depends on that feed.

## 2.2 The TER finding — where we can beat them outright

They sync `expense_ratio` from their own API into a column, and then **never use
it in the score**. TER is the most replicated predictor of future fund returns
that exists. That is a free win, and AMFI publishes it publicly:

```
GET amfiindia.com/api/populate-te-rdata-revised
    ?MF_ID={amc}&Month=MM-YYYY&strCat=-1&strType=-1&page=1&pageSize=500
→ {"data": [...], "meta": {page, pageSize, total, pageCount}}
```

Verified live: **26 AMCs respond**, each paginated (MF_ID=21 alone reports
`total: 3320` rows). Every row carries both `D_TER` (Direct) and `R_TER`
(Regular), plus the cost breakdown (`*_BER`, brokerage, transaction, statutory
levies) and a `TER_Date`, so the latest value per scheme is a dedup by date.

Real values pulled today:

```
D_TER 0.35%  R_TER 0.72%   HDFC Banking and PSU Debt Fund - Direct
D_TER 0.38%  R_TER 0.63%   HDFC Corporate Bond Fund - Direct
D_TER 0.80%  R_TER 1.71%   Kotak Credit Risk Fund - Direct
D_TER 0.84%  R_TER 1.64%   Aditya Birla Sun Life Credit Risk Fund - Direct
```

**Median Regular-minus-Direct gap: 0.55pp a year, across 257 funds.** That is the
distributor commission, quantified per fund, from a public source. We can show a
user exactly what their regular plan costs them annually — a number neither
Bachatt nor most apps put on screen.

**The join is the work.** TER carries `NSDLSchemeCode`, not an AMFI scheme code,
so it cannot be joined to our catalogue on an identifier. Name matching gets
**75% on a normalised exact match** (strip plan/growth/option suffixes,
punctuation, case). The residue is mostly ETFs and closed-ended schemes that are
not in our universe anyway. Reverse coverage on the three AMCs tested was 24% of
our catalogue rows, which is lower mainly because our catalogue holds many
near-duplicate name variants per real scheme — fuzzy matching within the same
fund house should lift this substantially. This is a solvable one-off mapping
job, cached like the fund catalogue.

## 2.3 Two data-quality lessons worth taking

**Weighted P/E is the wrong number for a peer comparison.** From
`update_sector_benchmarks.py`: NSE's `allIndices` returns *market-cap weighted*
P/E, so Nifty IT reads ~21 because TCS and Infosys dominate the weight. Asking
"is this stock cheap versus its peers" needs the **median across constituents**.
Using the weighted figure makes mid-cap IT at P/E 28-32 look expensive when it is
sitting at the sector median. They compute the median themselves from yfinance
across a balanced large+mid basket, and take dividend yield from NSE separately
because yfinance's is unreliable (returns 13% for banks).

**Outlier days must be neutralised before any metric.**
`_cap_log_returns_for_metrics` zeroes any day with `|simple return| > 25%` as a
split, restatement or bad NAV. We drop zero-NAV rows; we do not catch a 40%
one-day artefact, and a single such day distorts volatility, Sortino, max
drawdown and every rolling window at once.

## 2.4 What we can build that they structurally cannot

Their minimum-investment, expense-ratio and fund-size data comes from being a
distributor. We are not one, so:

- **Minimums**: published per scheme in AMFI factsheets and scheme documents.
  Slower to assemble, but the *structure* — swap, drop, redistribute, emit an
  event — is the valuable part and is ours to build regardless of the source.
- **Expense ratio**: the public AMFI TER API above. Strictly better than their
  position, because we would actually score on it.
- **Fund size**: the AAUM endpoint, once the `strType` and quarter parameters are
  pinned down.
- **Promoter holding**: Screener.in, verified working.
- **Delivery %**: not available — NSE now returns 403. Their scorer allocates 9
  of 100 points to it and silently scores every stock `4.5/9` when the fetch
  fails, which is worth knowing before copying the weight table.
