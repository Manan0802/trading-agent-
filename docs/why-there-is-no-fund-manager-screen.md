# Why there is no Fund Manager screen

`wealth.bachatt.app` has four surfaces. This app has three. This is the fourth
one and why it is not here.

## What it would show

A list of fund managers, each with the schemes they run and how those schemes
have performed — so you can ask "is this fund good, or is this *manager* good",
which is a reasonable question and one the fund industry markets heavily on.

## Why it is not built

**There is no free source for who manages an Indian mutual fund.** Checked
again on 2026-08-21:

| source | result |
|---|---|
| `api.mfapi.in/mf/{code}` | 200, and the response has **no manager field at all** — only code, name, fund house, scheme type and category |
| `amfiindia.com` fund-manager details page | **404** |
| `api.kuvera.in/mf/api/v4/fund_schemes/{isin}.json` | 200, and the body is **2 bytes** |

The reference implementation does have manager data. It comes from **60 local
`.xls` files** — category and manager dumps someone downloaded by hand and
committed. That is not a feed. Reproducing it would mean reproducing somebody's
manual collection, and it would be stale from the day it was copied.

## What would unblock it

AMFI's Scheme Information Documents carry manager names, and they are public.
They are also **one PDF per scheme per AMC**, with no consistent layout — so it
is a parser per fund house, re-checked whenever any of them changes their
template. That is a project, not a data source, and it is worth doing only if
the answer turns out to matter.

## Whether the answer would matter

Worth stating plainly, because it affects how much the missing screen costs.
This project has measured fund *selection* three times and found it weak:
50%, 38%, and most recently 68% over 235 category-years with **three of seven
years at or below chance** (`docs/does-the-score-work.md`). Cost predicted at
87%. Manager identity is a narrower claim than fund selection and would have to
clear a higher bar than either.

So: not built, because the data does not exist for free; and not urgent,
because nothing measured so far suggests it would earn its place.

A screen full of `—` would have been worse than no screen.
