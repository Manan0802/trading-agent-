# Does the fund score actually predict anything?

Measured 2026-07-27 with `scripts/validate_score.py` and
`scripts/validate_quartiles.py`, over real NAV history, picking only with what
was knowable on each decision date.

**The answer is no, and this document exists because that needed writing down
rather than quietly not being tested.**

---

## Method

Six decision dates a year apart, ending far enough back that a three-year
holding period has closed. On each date the real scorer is handed NAV history
truncated at that date, ranks the category, and its picks are then measured
against what every other fund in the same category actually returned over the
next three years.

The picker cannot see a day beyond the decision date, and a fund that had not
launched is not offered to it at all. A fund that stopped publishing mid-window
has no forward return and is counted as unmeasurable rather than valued at its
last NAV.

## Result 1 — the top picks against the category median

```
ELSS                   beat the median in   0% of 6 windows   median spread -3.5%
Flexi Cap                                  83%                              +0.3%
Focused                                    33%                              -1.6%
Large & Mid Cap                            67%                              +1.5%
Large Cap                                  33%                              -1.3%
Mid Cap                                    33%                              -2.5%
Multi Cap                                  67%                              +1.2%
Sectoral / Thematic                        17%                              -1.0%
Small Cap                                  67%                              +1.8%
Value                                      83%                              +1.8%

Across 10 categories and 60 windows: median hit rate 50%, median spread -0.4%/yr
```

A 50% hit rate is a coin flip. The spread across categories, from -3.5% to
+1.8% on six windows each, is the shape of noise rather than of skill.

## Result 2 — top quartile against bottom quartile

The weaker claim, and the one worth testing separately: even a score that cannot
name the winner is useful if it reliably filters the bottom tail.

```
54 category-windows measured

top quartile by our score    : median forward return  +17.2%
category median              :                        +18.1%
bottom quartile by our score :                        +19.4%

top minus bottom             : -2.3% a year
top beat bottom in 25 of 54 windows = 46%
```

The funds our score ranked *worst* went on to return **more** than the ones it
ranked best. The gap is small enough to be noise in either direction, which is
the point: there is no signal here to lean on.

## And this is the flattering version

Our catalogue is built from funds that are alive today. Every fund wound up or
merged since a decision date is missing from the measurement, and those are
disproportionately the ones that did badly. The true numbers are worse than the
ones above by an unknown margin.

## What this actually means

It is the most replicated finding in the whole literature, now confirmed on
Indian data with our own code: **ranking funds by their past record does not
predict their future record.** Nothing about the way this particular score was
built rescues it. Rolling windows instead of point-to-point, dispersion instead
of averages, horizon-weighted normalisation — all of it is a better description
of the past, and none of it is a prediction of the future.

Set that against the one lever we can measure with certainty:

| | Worth per year | Certain? |
|---|---|---|
| Picking the "right" fund by our score | **-0.4%** | no, and the sign is wrong |
| Buying the direct plan instead of regular | **+0.64%** | **yes, it is a published fee** |

Choosing the cheaper share class of the *same fund* is worth more than fund
selection, and unlike fund selection it is not a bet. On ₹15,000 a month over
fifteen years that gap is about ₹4.2 lakh, and it arrives whether or not the
manager has a good decade.

## What has to change in the product

1. **The score must stop implying it predicts.** It is a description of what a
   fund's record looks like — how often a three-year holding made money, how bad
   the worst one was, what it costs — and every one of those is a fact about the
   past stated honestly. Ranking by a composite and calling the top one the best
   choice claims something the evidence does not support.

2. **Cost becomes the headline, not a pillar.** It is the only input that is
   knowable in advance, the only one whose effect is arithmetic rather than
   probabilistic, and it is worth more than everything else here combined.

3. **The worst-window figure keeps its place, for a different reason.** "This
   fund never lost money over any three-year holding period, worst still +0.8%"
   is not a forecast either. It is the honest answer to "what has holding this
   actually felt like", which is the question that decides whether somebody
   stays invested through a bad year. Behaviour is a real lever even when
   selection is not.

4. **Everything the app already does that is not fund picking gets more
   important, not less:** the regime-free allocation, goal-specific inflation,
   the tax-regime comparison, EPF and PPF in the balance sheet, real XIRR on
   real transactions. Those are arithmetic. They work.

None of this makes the scoring engine wasted. It made the evidence legible, and
the evidence turned out to say something worth knowing.
