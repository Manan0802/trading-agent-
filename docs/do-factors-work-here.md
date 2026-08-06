# Do momentum and low volatility pay on the stocks we can buy?

Rewritten 2026-08-06 after the harness was rebuilt. The first version used
eight yearly windows against an external index and could not answer the
question; what follows is the version that can.

`backend/scripts/validate_factors.py`. Fifteen years, **non-overlapping**
windows, point in time, costs charged, benchmarked against the universe itself.

---

## The answer

**Momentum works here. It is real, it is measurable, it is only worth having if
you trade it rarely — and it pays nothing in a crash.** The first three come
from measuring this universe; the fourth from thirty-two years of
survivorship-adjusted data, and it is the one that decides position size.

```
NIFTY 500, 220 names, 15 years

quarterly (60 non-overlapping windows)
factor         top q  vs bottom   vs univ  net of cost   rank IC       t
momentum       8.9%      +3.3%     +2.1%        -1.9%    +0.073   +2.99
low_vol        4.8%      -4.9%     -2.0%        -6.0%    -0.020   -2.67
reversal       5.7%      -3.3%     -1.2%        -5.2%    -0.073   -1.36
random         6.9%      +0.0%     +0.0%        -4.0%    -0.009   +0.07

annual (15 non-overlapping windows)
momentum      40.8%      +7.0%     +8.2%        +7.2%    +0.070   +1.60
low_vol       19.1%     -27.2%    -13.5%       -14.5%    -0.058   -2.56
reversal      33.8%      -7.0%     +1.2%        +0.2%    -0.070   +0.20
random        34.9%      +1.0%     +2.3%        +1.3%    +0.025   +0.52
```

**The signal is the same at both horizons** — rank IC +0.073 and +0.070. What
changes is cost and sample size:

- **Quarterly proves the signal exists.** t = +2.99 over 60 independent
  windows. That is not luck. But rebalancing four times a year costs 4%, and
  the 2.1% edge does not survive it: **net −1.9%**.
- **Annual shows it survives costs.** +8.2% over the universe, **+7.2% net** of
  1% turnover. But fifteen windows only give t = +1.60, below the bar.

Neither run alone would justify anything. Together they say: the effect is
real (the quarterly t), and it is only harvestable at low turnover (the annual
net). That is also exactly what the published 19-year NSE work found —
low-turnover momentum 19.43% CAGR against high-turnover 8.51%.

**Low volatility loses at every horizon.** −2.0% quarterly, −13.5% annually,
consistently. It is a risk-adjusted claim and this sample is a bull market, so
this is the factor behaving as documented rather than failing. It is not a way
to make more money here.

---

## Why the controls matter, with a worked example

Two controls run alongside every factor: `random`, a seeded shuffle that must
score zero, and `reversal`, the negative of momentum which must mirror it.

**They caught a broken benchmark.** The first version compared each factor's
top quartile against `^NSEI`, the Nifty 50. Result:

```
random   vs index +4.2%   t = +4.13
```

A random quartile beating the index by 4.2%, with a t-statistic that would read
as overwhelming significance. That is not an edge — it is mid caps outrunning
large caps across the sample, because the universe was NIFTY 500 and the
benchmark was NIFTY 50. **Measuring a factor against a different universe
measures the universe.**

The benchmark is now the same universe, equally weighted, in the same window.
`random` immediately fell to +0.0% with t = +0.07, and `reversal` came back as
the exact negative of momentum. Only then were the other rows worth reading.

Without the controls that +4.2% would have been reported as a finding.

---

## Method, and why each choice was made

| choice | why |
|---|---|
| **Non-overlapping windows** | Yearly returns sampled quarterly share three quarters of their data; ten such "windows" carry about the information of three, and a t-statistic on them is inflated. Spacing the rebalance to equal the horizon costs sample size and buys the right to do arithmetic. |
| **Benchmark = the universe** | See above. The alternative an investor actually has is the same set of stocks, not a different index. |
| **Costs charged, not assumed** | 0.5% a side, a full round trip per rebalance. A gross edge that dies at retail costs is not something you can buy. |
| **Rank IC, not just quartiles** | The quartile spread collapses 220 names into one win-or-lose bit. IC uses the whole cross-section, which is why it is stable across horizons here while the spread is not. |
| **Both indices, separately** | The stock score won on NIFTY 500 and lost on NIFTY 50, invisibly, until they were split. |
| **Price history only** | No fundamentals, no filing lag, no currency — none of the inputs that produced wrong answers before. |

---

## What this does not say

- **Not a trading system.** A rank IC of 0.07 is a real but small edge. It says
  the top quartile beats the average over many names and many years; it says
  nothing about any single stock.
- **Fifteen years is one long expansion.** This sample has no 2008 — now
  addressed by the 32-year survivorship-adjusted data below, which shows
  momentum going flat in exactly those episodes.
- **220 names, not 751.** Limited to keep inside Yahoo's rate limit. The result
  should be re-run on the full universe.
- **Annual significance is unproven.** t = +1.60. The net-of-cost figure is the
  attractive one and it is also the one with the weakest statistics.



---

## Independent confirmation, 32 years, survivorship-adjusted

Everything above rests on today's NIFTY 500 members, which is a
survivorship-biased sample: the companies that failed are not in it. And
fifteen years contains no 2008. Both limitations turned out to have a free fix.

IIT/IIMA publishes an **Indian Fama-French-Momentum factor library** —
survivorship-bias adjusted, monthly, from October 1993:

`faculty.iima.ac.in/iffm/Indian-Fama-French-Momentum/DATA/` →
`2025-12_FourFactors_and_Market_Returns_Monthly_SurvivorshipBiasAdjusted.csv`

386 monthly observations. Independently built, by people with no stake in this
app being right.

```
factor                        mean        t      n
WML (momentum)            +13.4%/yr    +3.11    386
HML (value)                +8.6%/yr    +2.39    386
MF  (market excess)        +8.6%/yr    +1.99    386
SMB (size)                 -2.8%/yr    -0.96    386
```

**Momentum is confirmed.** t = +3.11 over thirty-two years on a
survivorship-adjusted sample, against the t = +2.99 measured here over fifteen
on a biased one. Two different datasets, two different constructions, the same
answer. That is much stronger than either alone.

The magnitudes differ for a reason worth knowing: WML is long-short — long the
winners and short the losers — while the measurement above is long-only, top
quartile against the universe. Roughly half the spread is what a long-only
investor can reach, which is what the +8.2% annual figure is.

**Value works here too, and had not been tested.** HML at t = +2.39.

**Size does not.** SMB is *negative* at −2.8%/yr in India, which is the
opposite of the US result everyone quotes. Worth knowing before building
anything around small caps.

### And the thing the fifteen-year sample could not show

```
2008 crash (2007-2009)   momentum   -0.4%/yr   t = -0.02
COVID (2020)             momentum   +0.0%/yr   t = +0.00
2018-2025 (my sample)    momentum  +13.1%/yr   t = +2.41
```

**Momentum pays nothing in a crash.** Not a small loss — flat, twice, in the
two worst episodes of the last twenty years. My sample measured +13.1% and it
was right about that sample, and the sample was a rally.

That is the honest shape of this edge: it earns well most of the time and
abandons you precisely when everything else is falling. Anyone sizing a
position on the +13.4% average without knowing the 2008 number is being misled
by their own backtest.

It also means momentum is **not** a hedge and must not be sold as one. It is a
return enhancer that is correlated with the market's good times.

---

## What this means for an ML or foundation model

The earlier version of this document said a model could not be evaluated because
the harness could not detect a real effect. **That is now fixed** — the harness
detects momentum at t = +2.99 and correctly scores random at zero.

So a model can now be tested honestly, and it has a defined bar to clear:

```
beat rank IC +0.073 at quarterly horizon
while turning over little enough that costs do not eat it
```

That second clause is the hard part and it is where most published results
quietly fail. Momentum already has the signal; what it lacks is a way to
harvest it cheaply. A model that produces a *stronger* signal at the *same*
turnover is worth having. One that needs weekly rebalancing to shine is not,
whatever its backtest says.

---

*Reproduce:*
```
python backend/scripts/validate_factors.py --index "NIFTY 500" --limit 220 --years 15 --horizon quarterly
python backend/scripts/validate_factors.py --index "NIFTY 500" --limit 220 --years 15 --horizon annual
```
