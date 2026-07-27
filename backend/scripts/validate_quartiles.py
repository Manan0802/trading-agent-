"""Can the score at least avoid the worst funds, even if it cannot pick winners?

A different and weaker claim than "our picks beat the market", and one worth
testing separately: a screen that reliably filters the bottom tail is useful
even when it cannot rank the top.
"""
import statistics, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.advisor.backtest import forward_return
from app.services.advisor.fund_catalogue import BROWSABLE_CATEGORIES, funds_in_category
from app.services.advisor.fund_evidence import build_evidence
from app.services.advisor.fund_score import score_peer_group_v2
from app.services.marketdata import mutual_fund

HOLD = 3
def dates(n=6):
    latest = date.today() - timedelta(days=round(HOLD*365.25)+30)
    out=[]
    for i in range(n):
        m=latest.month-(i*12)%12; y=latest.year-(i*12)//12
        if m<=0: m+=12; y-=1
        out.append(date(y,m,1))
    return sorted(out)

rows=[]
for cat in [c for c in BROWSABLE_CATEGORIES if c.startswith("Equity Scheme")]:
    entries=funds_in_category(cat)
    def f(e):
        try: return e.code, mutual_fund.get_nav_history(e.code)
        except Exception: return e.code, []
    with ThreadPoolExecutor(24) as p: uni={c:n for c,n in p.map(f,entries) if n}
    if len(uni)<12: continue
    for d in dates():
        ev=[]
        for code,navs in uni.items():
            h=[x for x in navs if x.date<=d]
            if len(h)<2 or (h[-1].date-h[0].date).days<400: continue
            b=build_evidence(code,code,cat,h)
            if b: ev.append(b)
        r=score_peer_group_v2(ev)
        if len(r.ranked)<12: continue
        fwd={c.scheme_code: forward_return(uni[c.scheme_code], d, HOLD) for c in r.ranked}
        fwd={k:v for k,v in fwd.items() if v is not None}
        if len(fwd)<12: continue
        n=len(r.ranked); q=max(2,n//4)
        top=[fwd[c.scheme_code] for c in r.ranked[:q] if c.scheme_code in fwd]
        bot=[fwd[c.scheme_code] for c in r.ranked[-q:] if c.scheme_code in fwd]
        med=statistics.median(fwd.values())
        if top and bot:
            rows.append((cat,d,statistics.mean(top),statistics.mean(bot),med))

print(f"{len(rows)} category-windows measured\n")
t=[r[2] for r in rows]; b=[r[3] for r in rows]; m=[r[4] for r in rows]
print(f"top quartile by our score   : median forward return {statistics.median(t):+.1%}")
print(f"category median             : {statistics.median(m):+.1%}")
print(f"bottom quartile by our score: {statistics.median(b):+.1%}")
print(f"\ntop minus bottom spread     : {statistics.median(t)-statistics.median(b):+.1%} a year")
wins=sum(1 for r in rows if r[2]>r[3])
print(f"top beat bottom in {wins}/{len(rows)} windows = {wins/len(rows):.0%}")
