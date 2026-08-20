"""Fill the NAV store with every catalogue fund's full published history.

This is a build step, not runtime code, and it is the one that turns an empty
`.navstore/nav.db` into something the screener can serve from. Run it once, and
again whenever the catalogue is rebuilt:

    venv/bin/python scripts/backfill_nav_history.py

Roughly 4,957 funds and ~5.2M rows, five to thirty minutes depending on mfapi.
It is safe to interrupt: `--resume` is the default, the resume ledger commits in
the same transaction as the rows it describes, and inserts are DO NOTHING, so
re-running a finished backfill costs bandwidth and nothing else.

    --resume            skip funds already marked done (DEFAULT)
    --force             refetch everything in scope, ignoring the ledger
    --only CODE [CODE]  just these scheme codes
    --limit N           just the first N of the catalogue
    --api-pause SECS    override the between-chunk pause

Exit status 1 means the integrity anchors did not survive the crawl. Unlike
build_fund_catalogue.py -- which refuses to *write* when its canary fails --
this keeps whatever it fetched, because discarding hours of crawling is the
expensive wrong move. The run is simply not accepted, and the report says which
anchor failed and what was expected versus found.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.advisor.fund_catalogue import all_funds  # noqa: E402
from app.services.screener import backfill, navstore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--resume",
        action="store_true",
        help="skip funds already marked done in nav_source (the default)",
    )
    mode.add_argument(
        "--force",
        action="store_true",
        help="refetch every fund in scope, ignoring the resume ledger",
    )
    ap.add_argument("--only", nargs="+", metavar="CODE", help="just these scheme codes")
    ap.add_argument("--limit", type=int, help="just the first N catalogue funds")
    ap.add_argument(
        "--api-pause",
        type=float,
        default=backfill._PAUSE_SECONDS,
        metavar="SECONDS",
        help=f"pause between chunks (default {backfill._PAUSE_SECONDS})",
    )
    args = ap.parse_args()

    navstore.ensure_schema()
    catalogue = [f.code for f in all_funds()]

    with navstore.session() as s:
        plan = backfill.plan_run(
            s, catalogue, force=args.force, only=args.only, limit=args.limit
        )

    print(
        f"{len(catalogue)} catalogue funds, {len(plan.targeted)} in scope, "
        f"{plan.already_done} already done, {len(plan.todo)} to fetch",
        flush=True,
    )
    if not plan.todo:
        print("nothing to do", flush=True)

    report = backfill.run(plan, pause=args.api_pause)

    with navstore.session() as s:
        acceptance = backfill.accept(s, plan)
        print(backfill.render_report(s, plan, report, acceptance))

    return 0 if acceptance.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
