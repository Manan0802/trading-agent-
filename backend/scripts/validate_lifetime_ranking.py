"""Manan's hypothesis: score funds on their whole lifetime record.

The 3-year test failed. Lifetime is a different claim -- a longer record, more
market cycles, arguably a truer picture of the manager. Worth testing rather
than dismissing.

Same harness as validate_quartiles: rank on the decision date using only what
was knowable then, measure the forward 3 years.
"""
import statistics, sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path('/Users/beastathome/Desktop/manan/traa/backend')))
from concurrent.futures import ThreadPoolExecutor
from app.services.advisor.backtest import forward_return
from app.services.advisor.fund_catalogue import BROWSABLE_CATEGORIES, funds_in_category
from app.services.marketdata import mutual_fund
from app.services.marketdata.mutual_fund import nav_on_or_before

HOLD = 3
def dates(n=6):
    latest = date.today() - timedelta(days=round(HOLD*365.25)+30)
    out=[]
    for i in range(n):
        m = latest.month - (i*12)%12; y = latest.year - (i*12)//12
        if m<=0: m+=12; y-=1
        out.append(date(y,m,1))
    return sorted(out)

rows=[]
for cat in [c for c in BROWSABLE_CATEGORIES if c.startswith("Equity Scheme")]:
    entries = list(funds_in_category(cat))
    if len(entries) < 12: continue
    def fetch(e):
        try: return e.code, mutual_fund.get_nav_history(e.code)
        except Exception: return e.code, []
    with ThreadPoolExecutor(24) as pool:
        navs = {c:n for c,n in pool.map(fetch, entries) if n}
    for d in dates():
        fwd={}; lifetime={}
        for code, series in navs.items():
            if series[0].date > d - timedelta(days=365*5): continue
            f = forward_return(series, d, HOLD)
            first = series[0]; at = nav_on_or_before(series, d)
            if f is None or at is None or first.nav <= 0: continue
            years = (d - first.date).days / 365.25
            if years < 5: continue
            fwd[code] = f
            lifetime[code] = (at.nav/first.nav) ** (1/years) - 1
        if len(fwd) < 12: continue
        order = sorted(lifetime, key=lambda c: -lifetime[c])
        q = max(2, len(order)//4)
        rows.append((statistics.fmean(fwd[c] for c in order[:q]),
                     statistics.fmean(fwd[c] for c in order[-q:])))

if not rows:
    print("nothing measurable"); sys.exit(1)
top=[r[0] for r in rows]; bot=[r[1] for r in rows]
wins=sum(1 for r in rows if r[0]>r[1])
print(f"\n  Lifetime (since-inception CAGR) se rank karke, {len(rows)} windows:\n")
print(f"    best lifetime record  ->  next 3y:  {statistics.fmean(top):>6.1%}")
print(f"    worst lifetime record ->  next 3y:  {statistics.fmean(bot):>6.1%}")
print(f"    best beat worst in:                 {wins}/{len(rows)}  ({wins/len(rows):.0%})")
