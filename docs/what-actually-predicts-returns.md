# What actually predicts returns

Written 2026-07-30, answering a direct objection:

> "Cost ka kya hai, humein toh returns matter karte hain. Ek fund ₹10 ka hai 6%
> de raha hai, ek ₹1000 ka hai 20% de raha hai. Mere paas fixed amount hai, toh
> mera paisa accordingly grow karega na?"

Two separate claims are folded together here. One is correct and this document
confirms it with a measurement. The other is the exact question the product was
built to answer, and it is settled — not by argument, but by the same harness
that has already failed our own scoring engine once.

---

## Part 1 — NAV per unit is irrelevant. Confirmed.

Correct, and it is worth stating plainly because it is the most common
misconception in Indian retail investing. ₹1,000 into a ₹10 NAV fund buys 100
units; into a ₹1,000 NAV fund it buys 1 unit. Same ₹1,000 deployed. If both grow
15%, both are worth ₹1,150. The unit price is an accounting artefact of when the
scheme launched, nothing more.

We did not take that on faith. It was ranked as a signal alongside the others:

```
signal        top quartile   bottom q   spread   top>bottom   rank IC
nav_level          19.3%       19.0%     +0.3%     20/44        +0.020
```

Rank IC **+0.020** across 44 category-windows. That is zero. A fund's NAV level
carries no information about its next three years.

This also kills the NFO pitch. A new scheme at ₹10 is not cheap; it is a fund
with no record, sold on the one number that does not matter.

---

## Part 2 — Returns are the goal. Cost is how you predict them.

The objection treats cost and return as alternatives. They are not. Two facts
collapse the choice:

**1. The return we measure is already net of cost.** Under SEBI regulation, TER
is deducted from the scheme's assets daily, and the published NAV is after
expenses. So cost is not a separate charge on top of the return — it is already
inside every return number in this app.

**2. Then the only question left is which visible signal predicts the return we
are about to receive.** That is measurable, and we measured it.

`backend/scripts/why_not_returns.py` — 44 category-windows across Indian equity
categories, decision dates 2018-06 to 2023-06, three-year hold. On each decision
date, funds are ranked using **only** what was visible that day, then scored on
the forward three years.

```
signal        top quartile   bottom q   spread   top>bottom   rank IC
past_3y            18.6%       19.5%     -1.0%     20/44        -0.033
cost               19.6%       17.7%     +1.9%     34/44        +0.184
nav_level          19.3%       19.0%     +0.3%     20/44        +0.020
blend              18.9%       18.2%     +0.7%     28/44        +0.091
```

Read it in three lines:

- **Past return is worse than a coin.** 20 of 44, IC −0.033. The funds with the
  best three-year record went on to return *less* than the ones with the worst.
- **Cost predicts.** 34 of 44 (77%), IC +0.184, +1.9%/year.
- **Blending them halves the signal.** `blend` is a 50/50 mix of the past-return
  rank and the cost rank. IC drops from +0.184 to +0.091.

That third line is the answer to the objection, and it is the strongest result
here. Adding "but returns matter" to the ranking does not merely fail to help —
**it destroys half of the only signal that works.** Past return is not neutral
information being ignored. It is noise, and mixing noise into a signal degrades
it. This is the quantitative justification for `past_return` carrying weight
**0%** rather than a small positive weight.

### The ₹10-at-6% vs ₹1000-at-20% scenario

If we could know in advance which fund would deliver 20%, we would obviously
take it — cost would be irrelevant, and so would everything else. The entire
problem is that we cannot. The table above *is* the attempt: rank by the best
available evidence of who will return 20%, and check. Ranking by who *did*
return 20% loses.

---

## Part 3 — What the world's evidence says

Everything below was checked against primary sources where reachable.

### Fees predict returns (replicated, strong)

Morningstar, *Predictive Power of Fees* (Russel Kinnel, May 2016), primary
document read. Method: funds grouped into expense quintiles within peer group,
then scored forward. **Dead funds included** — critical, because expensive funds
are the ones that get merged away, and excluding them flatters high cost.

"Success ratio" = share of funds that **both survived and beat their category**.

Subsequent total-return success ratio, cheapest → priciest quintile:

| Asset class | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| U.S. Equity | **62** | 48 | 39 | 30 | **20** |
| Sector Equity | **65** | 50 | 45 | 34 | **19** |
| International Equity | **51** | 50 | 39 | 31 | **21** |
| Balanced | **54** | 50 | 45 | 31 | **24** |
| Taxable Bond | **59** | 54 | 44 | 29 | **17** |
| Municipal Bond | **56** | 52 | 32 | 28 | **16** |

Monotonic in every single asset class. Cheapest quintile ~3x as likely to
succeed as priciest.

The detail that matters most is in Appendix 1. U.S. equity, 5-year annualised
total return by quintile: **10.91 / 10.34 / 9.93 / 9.53 / 8.88**. Average expense
ratio: 0.65% vs 2.20%. So the fee gap was 1.55pp but the **return gap was
2.03pp** — expensive funds lost more than their fee. Fees are not just a
subtraction; they proxy for the behaviours that come with them (turnover,
asset-gathering, closet indexing).

Investor-return gap was wider still: **9.78% vs 7.16%**.

Fees were a *weak* predictor of standard deviation — so cost buys you return
prediction, not risk prediction. That is consistent with keeping risk as its own
pillar in our score.

Bogle's framing is the reason this is not a coincidence — the **Cost Matters
Hypothesis**: gross market return minus intermediation cost equals what
investors receive, in aggregate, whether or not markets are efficient. It is
arithmetic, not a theory that can fail.

### Past performance does not persist (replicated, strong)

Carhart (1997), *On Persistence in Mutual Fund Performance* — after controlling
for market, size, value and momentum, persistence essentially vanishes beyond one
year, except at the bottom (bad funds keep being bad, largely because they are
expensive). The apparent skill of winners is mostly momentum exposure.

Our own 60-window test (`docs/does-the-score-work.md`) reproduced this on Indian
funds independently: 50% hit rate, bottom quartile +19.4% vs top +17.2%.

### India specifically

SPIVA India Mid-Year 2025: Indian **large-cap** active funds underperforming
their benchmark — **75.0%** over 1 year, **74.2%** over 3, **84.4%** over 5,
**76.3%** over 10. Mid/small-cap active had an unusually good 2025 (best relative
year since 2014) — a reminder that any one window can flatter a category, which
is exactly the trap our stock-score backtest fell into.

An Indian academic study (JETIR, 2024, large-cap funds 2019–2023) reports the
same inverse expense-ratio/performance relationship. Weaker evidence than
Morningstar's — smaller sample, ARIMA methodology — logged as supporting, not
load-bearing.

### What drives the outcome more than fund choice

Brinson, Hood & Beebower (1986) and the 1991 update: **investment policy —
the asset allocation — explained ~93–95% of the variance** in total plan return
across 82 large pension plans. Security selection and market timing contributed
little on average.

This is the honest reframe of "returns matter": your returns come overwhelmingly
from **how much of your money is in equity**, not from which flexi-cap you
picked. NexTrade's asset allocator is therefore doing more for the outcome than
the fund ranking ever will.

### Behaviour

Morningstar *Mind the Gap* 2025: investors earned **7.0%** against their own
funds' **8.2%** over 2015–2024 — a **1.2%/year** gap from the timing of their own
cash flows, ~15% of the funds' gains.

Logged with its rebuttal: Fulkerson, Jordan, Riley & Yan (*Financial Analysts
Journal*, 2026) re-examined the same sample and attribute only **0.10%/year** to
bad timing specifically, the rest to arithmetic artefacts of dollar-weighting. So
the direction is real, the magnitude is disputed. Do not quote 1.2% as settled.

India's own behaviour signal is blunter: the AMFI **SIP stoppage ratio** hit
109% in January 2025 (61 lakh SIPs stopped against 56 lakh started) and exceeded
100% again in March–April 2026. Investors quit during drawdowns. Note the
measurement caveat — AMFI's figure lumps matured SIPs in with discontinued ones,
so >100% is not pure distress.

### Is anything else predictive? Yes, with conditions

**Factors.** Momentum has the strongest long-run Indian record, but a 19-year NSE
backtest decomposes it uncomfortably: low-turnover momentum returned **19.43%
CAGR** while high-turnover momentum returned **8.51%** — below Nifty 50's
10.41%. The premium is largely an **illiquidity premium**, not a free behavioural
edge. Quality and low-volatility show better risk-adjusted returns and smaller
drawdowns, and low-vol reliably underperforms in bull markets (2007, 2017, 2021).

Implication for us: factor tilts are real but they are *risk you are being paid
to take*, not skill. Charging them into a score as "quality" would be dishonest
unless the score also says what the investor is exposed to.

**Valuation, at long horizons.** Shiller CAPE explains a meaningful share of
10-year forward returns — but the R² is wildly period-dependent (0.43 for
1926–2011, ~0.9 in some post-1975 windows). Anything that unstable is a
conversation, not a screen.

**Volatility, at short horizons.** This is the one genuinely reliable forecast in
finance: volatility clusters and is predictable (the entire ARCH/GARCH
literature), while returns are not. Forecasts mean-revert toward the long-run
level, so the horizon is short.

That asymmetry — **risk is predictable, return is not** — is the cleanest
justification for the shape of this product. We should predict risk, cost and
tax, and refuse to predict return.

### The practitioners

Howard Marks, *You Can't Predict. You Can Prepare.* (Oaktree, Nov 2001): build a
portfolio that survives several futures rather than one that maximises for the
future you forecast. Marks is blunt that he does not believe in forecasts.

There is a counter-current worth logging honestly: recent work
(*Journal of Financial Economics*, 2023) claims machine learning on fund
characteristics can select positive-alpha funds. Could not read the paper —
ScienceDirect returns 403 to both WebFetch and Firecrawl. **Unverified. Do not
cite as support for anything until read.**

---

## What this changes in NexTrade

Nothing about the weights — the evidence points where the score already points.
It changes what we can *claim*, and adds one thing.

1. **`past_return` weight stays 0%, and now has a positive reason.** Previously
   the justification was "it failed its test." Now it is stronger: blending it in
   measurably halves the working signal.

2. **Say NAV level does not matter, on screen.** It is the most common Indian
   retail error, we have measured it (IC +0.020), and the fund picker is the
   right place to say so.

3. **Cost 55% stays. Do not raise it to 70%.** The evidence supports cost, but
   fees predict *return*, not *risk* (Morningstar found them a weak predictor of
   standard deviation). Risk needs its own pillar or the score becomes a sorted
   fee list wearing a ranking's clothes.

4. **The allocator deserves more prominence than the fund ranking.** Brinson's
   ~93% dwarfs cost's +1.9%. Right now Research is a fund list and allocation is
   buried inside Goals. That ordering is backwards relative to the evidence.

5. **Real holdings are obtainable, and this was already known.** The line "no
   holdings feed exists" that appears in several of our notes is wrong, and was
   already known to be wrong — earlier research had a working parser and real
   overlap numbers. Correct about APIs, wrong about documents. Re-verified today
   by downloading and parsing PPFAS's February 2026 disclosure: 580KB `.xls`, 7
   scheme sheets, 427 rows, columns exactly as SEBI prescribes — instrument,
   **ISIN**, industry/rating, quantity, market value. ISIN solves cross-AMC name
   matching. So correlation-based overlap is a *choice*, not a constraint, and
   the notes should stop claiming otherwise.

   Known traps from the earlier work, still applicable: Nippon's `.xls` is
   actually xlsx; `% to NAV` scale differs by AMC (fractions vs percent — 100x
   errors if not normalised); header row position varies, so find it by locating
   the ISIN cell; HDFC's WAF blocks non-browser clients. Legacy `.xls` needs
   `xlrd>=2.0.1`, which is not yet in `requirements.txt` because nothing in the
   app imports it yet. AMFI's own `/online-center/portfolio-disclosure` page is
   JS-rendered and yields nothing to a plain scrape.

---

## Sources

- Morningstar, *Predictive Power of Fees*, Kinnel, May 2016 — [PDF](https://assets.contentstack.io/v3/assets/blt4eb669caa7dc65b2/blt70866588660aea5a/60416664f9638443346d4e9b/predictive-power-of-fees.pdf) · [commentary](https://www.morningstar.com/funds/fund-fees-predict-future-success-or-failure)
- Carhart, *On Persistence in Mutual Fund Performance*, J. Finance 1997 — [Wiley](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1997.tb03808.x)
- Bogle, *The Relentless Rules of Humble Arithmetic*, FAJ 2005 — [FAJ](https://www.tandfonline.com/doi/abs/10.2469/faj.v61.n6.2769) · [Cost Matters Hypothesis](https://www.bogleheads.org/wiki/Cost_matters_hypothesis)
- SPIVA India Mid-Year 2025 — [S&P](https://www.spglobal.com/spdji/en/spiva/article/spiva-india) (PDF blocked to automated fetch; figures via search index)
- Brinson, Hood & Beebower, *Determinants of Portfolio Performance*, FAJ 1986 — [FAJ](https://www.tandfonline.com/doi/abs/10.2469/faj.v42.n4.39) · [1991 update](https://indexacapital.com/bundles/unaiadvisor/docs/papers/1991-Brinson%20-Determinants-of-Portfolio-Performance-II.pdf)
- Morningstar, *Mind the Gap* 2025 — [Morningstar](https://www.morningstar.com/business/insights/research/mind-the-gap) · rebuttal: [CFA Institute / FAJ 2026](https://rpc.cfainstitute.org/research/financial-analysts-journal/2026/bad-timing-does-not-cost-investors-funds-returns)
- Momentum in India, 19-year NSE backtest — [backtestindia](https://backtestindia.com/blog/momentum-factor-india-liquidity-premium-scaled-turnover)
- Nifty factor indices — [NSE low-vol factsheet](https://www.niftyindices.com/Factsheet/Nifty100_LowVolatility30.pdf) · [Capitalmind factor comparison](https://www.capitalmind.in/blog/nse-strategy-indices-factor-investing-basics)
- Shiller CAPE predictive power — [Advisor Perspectives](https://www.advisorperspectives.com/articles/2020/07/20/the-remarkable-accuracy-of-cape-as-a-predictor-of-returns-1) · [Evidence Investor caveats](https://www.evidenceinvestor.com/post/the-shiller-cape-10-how-to-use-it-not-abuse-it)
- Marks, *You Can't Predict. You Can Prepare.*, Oaktree 2001 — [memo PDF](https://www.oaktreecapital.com/docs/default-source/memos/2001-11-20-you-cant-predict-you-can-prepare.pdf)
- AMFI on TER and NAV — [AMFI expense ratio](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=expenseRatio) · [TER of MF schemes](https://www.amfiindia.com/ter-of-mf-schemes)
- India expense-ratio study (weak evidence) — [JETIR 2024](https://www.jetir.org/papers/JETIR2409216.pdf)
- AMFI SIP stoppage data — [Feb 2026](https://www.bonvista.in/blog/amfi-data-february-2026-sip-stoppage-ratio-rises) · [Jan 2025](https://www.indiainfoline.com/blog/sip-flows-above-26000-crore-in-dec-24-but-sip-stoppage-spikes-again)
- ML fund selection — **unread, 403** — [JFE 2023](https://www.sciencedirect.com/science/article/pii/S0304405X23001770)
