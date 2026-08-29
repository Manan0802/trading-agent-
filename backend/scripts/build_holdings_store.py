"""Fill the holdings store from the AMCs' own monthly disclosures.

    PYTHONPATH=. venv/bin/python scripts/build_holdings_store.py [--limit N]

Public regulatory filings, not a scraped API: SEBI requires every AMC to publish
a monthly portfolio spreadsheet. `fund_holdings.py` downloads and parses them;
this walks every buyable fund whose AMC has a verified source, stores what comes
back, and writes the gzipped SQL dump that is the store's actual backup.

**It prints coverage as a fraction, always.** Seven AMCs are verified, covering
482 of the 1,659 buyable funds. A run that stored 400 portfolios has covered
24% of what the user can buy, and a report that says "400 funds stored" without
the denominator reads like completeness.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.advisor import buyable  # noqa: E402
from app.services.advisor.fund_catalogue import all_funds  # noqa: E402
from app.services.marketdata import holdings_store  # noqa: E402
from app.services.marketdata.fund_holdings import (  # noqa: E402
    HoldingsUnavailable,
    _amc_for,
    covered_amcs,
    portfolio_for,
)

DUMPS = Path(__file__).resolve().parent.parent.parent / "data" / "holdings-dumps"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, help="just the first N covered funds")
    ap.add_argument("--no-dump", action="store_true", help="skip writing the backup")
    args = ap.parse_args()

    names = {f.code: f.name for f in all_funds()}
    codes = sorted(buyable.buyable_codes())
    targets = [(c, names[c]) for c in codes if c in names and _amc_for(names[c])]
    if args.limit:
        targets = targets[: args.limit]

    print(f"{len(covered_amcs())} AMCs verified: {', '.join(sorted(covered_amcs()))}")
    print(
        f"{len(targets)} of {len(codes)} buyable funds have a covered AMC "
        f"({len(targets) / len(codes) * 100:.0f}%)\n"
    )

    stored = rows = 0
    unavailable: list[str] = []
    for i, (code, name) in enumerate(targets, 1):
        try:
            portfolio = portfolio_for(name)
        except (HoldingsUnavailable, Exception) as exc:  # noqa: BLE001
            unavailable.append(f"{code} {name[:44]} — {type(exc).__name__}")
            continue
        rows += holdings_store.save(portfolio)
        stored += 1
        if i % 50 == 0:
            print(f"  {i}/{len(targets)} · {stored} stored · {rows:,} rows", flush=True)

    funds, total_rows = holdings_store.counts()
    print(f"\nstore now holds {funds} funds and {total_rows:,} holding rows")
    print(
        f"coverage: {funds} of {len(codes)} buyable funds "
        f"({funds / len(codes) * 100:.0f}%) — the rest report holdings n/a"
    )
    if unavailable:
        print(f"\n{len(unavailable)} covered funds returned nothing:")
        for line in unavailable[:15]:
            print(f"  {line}")

    if not args.no_dump and funds:
        out = holdings_store.dump_to(DUMPS / "holdings.sql.gz")
        size = out.stat().st_size / 1024
        print(f"\nbackup -> {out}  ({size:,.0f} KB)")
        print("  git is not this database's backup; that file is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
