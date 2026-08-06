# Do momentum and low volatility pay on the stocks we can buy?

Run 2026-08-06 with `backend/scripts/validate_factors.py`. Eight yearly
rebalances, one-year forward returns, point in time, both indices separately,
costs charged.

The question behind it: the arithmetic this app does well — tax, cost, XIRR —
is knowledge anyone can look up. Is there anything in the *prediction* half
with a real edge on this universe?

---

## Read the controls first

A test that only measures the thing you hope for cannot tell you whether the
harness works. Two controls run alongside every factor:

| control | what it must do | NIFTY 50 | NIFTY 500 |
|---|---|---|---|
| `random` | sit near zero everywhere | +0.1% spread, IC +0.018 | +3.7%, IC +0.027 |
| `reversal` | mirror momentum exactly | −(momentum), IC −(momentum) | mirrored |

Both behaved. `reversal` came back as the exact negative of momentum on both
runs, which says the ranking arithmetic is consistent, and `random` sat near
zero on NIFTY 50. **So the harness can be believed.** Every number below is
about the market, not about the code.

---

## The result

```
NIFTY 50 (8 windows, 50 names)
factor         top q  bottom q   spread  net of cost   top>bot   rank IC
momentum      20.9%    26.7%    -5.8%       19.9%      4/8      -0.056
low_vol       15.4%    32.7%   -17.3%       14.4%      1/8      -0.127
reversal      26.7%    20.9%    +5.8%       25.7%      4/8      +0.056
random        22.9%    22.8%    +0.1%       21.9%      4/8      +0.018

NIFTY 500 (8 windows, 220 names)
momentum      40.2%    39.3%    +0.8%       39.2%      4/8      +0.003
low_vol       20.2%    53.5%   -33.4%       19.2%      1/8      -0.057
reversal      39.3%    40.2%    -0.8%       38.3%      4/8      -0.003
random        38.8%    35.1%    +3.7%       37.8%      5/8      +0.027
```

### Momentum: nothing here

Spread −5.8% on NIFTY 50 and +0.8% on NIFTY 500. **The sign flips with the
index**, which is exactly what killed the stock score, and rank IC is +0.003 on
the wider universe — indistinguishable from nothing.

The line that settles it: on NIFTY 500, **`random` (+3.7%) beat momentum
(+0.8%)**. A seeded coin flip did better.

### Low volatility: lost on both, and that is not a surprise

−17.3% and −33.4%, winning 1 of 8 windows each time. Consistent, so not noise.

But it is a statement about *this period*, not about the factor. The published
low-volatility anomaly is a **risk-adjusted** claim, and low-vol reliably
underperforms in bull markets — 2007, 2017 and 2021 are the standard examples.
India from 2018 to 2025 was largely a rally. A defensive factor losing a bull
run is the factor behaving as documented, not failing.

What it does mean for us: **low-vol is not a way to make more money here.** If
it earns its place it will be for smaller drawdowns, which is a different
claim and needs a different test.

---

## The honest limit of this test

**Eight yearly windows cannot detect a 2-4% annual factor premium.** That is
the size the literature reports, and the year-to-year spread here is tens of
percent. The fact that `random` scored +3.7% on one run is the proof: the
noise is larger than the effect being looked for.

So the correct conclusion is **not** "momentum is dead." It is:

> Nothing in these two factors is strong enough to be visible over eight years
> on this universe — which also means nothing here is strong enough to bet on.

Both halves matter. The first says do not declare the factors broken. The
second says do not ship them either.

### What would make this test able to answer

- **More windows.** Quarterly or monthly rebalances instead of yearly turns 8
  observations into 30-100. Overlapping, so not independent, but far better
  powered.
- **Longer history.** These eight years are one regime. A factor test that has
  never seen a bear market has not been tested.
- **A benchmark, not just quartiles.** Top quartile against the index return,
  which is what an investor actually chooses between.

Until those are in, this document is a reason **not** to build a factor screen,
not evidence against factors.

---

## What this means for an ML or foundation model

The natural next thought is that a model — Qlib, Chronos, TimesFM, a fine-tune —
might find what simple factors miss. Two things follow from the numbers above,
and they point in opposite directions.

**The bar is low.** Momentum scored IC +0.003 and was beaten by random. Anything
with a genuine edge would clear that easily.

**But the measurement cannot yet certify one.** If eight windows cannot
distinguish momentum from a coin flip, they cannot distinguish a trained model
from one either — and a model has vastly more ways to fit noise. Running one
through this harness today would produce a number, and that number would not
mean anything.

**So the order is: fix the harness first, then test models.** Quarterly
rebalances, a longer history, and a benchmark comparison. That is a day of work
and it is the difference between a result and a story. A model evaluated on a
harness that cannot detect a real effect is exactly how people end up
confidently trading noise.

---

*Reproduce: `python backend/scripts/validate_factors.py --index "NIFTY 50" --limit 50`
and `--index "NIFTY 500" --limit 220`.*
