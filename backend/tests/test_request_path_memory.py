"""The request path must not import pandas.

This is the only defence for an invariant that is otherwise invisible. The
deferred `import pandas` inside `marketdata/fund_holdings._open_workbook` is
what keeps the serving process small enough for a free tier, and moving it to
the top of the file -- the tidier form, which any linter suggests -- breaks
nothing that anyone would notice until the host starts being killed.

    baseline python             13 MB
    + fund_overlap (numpy)      49 MB   <- the request path
    + pandas                    80 MB   (+30, a 66% rise on the 46 MB measured
                                         in deploy/FREE-NO-CARD.md)

Commit 8a5e4d2 moved the pandas-heavy work onto a 16 GB GitHub runner, and that
is the reason this project deploys without a credit card at all. This test is
that decision, written where it can fail.
"""

import subprocess
import sys


def _imports_pandas(module: str) -> bool:
    """Import `module` in a FRESH interpreter and report whether pandas came in.

    A subprocess, not an `in sys.modules` check: by the time pytest reaches this
    file some other test has almost certainly imported pandas already, and the
    in-process check would pass while the invariant was broken.
    """
    code = (
        "import sys;"
        f"__import__('{module}');"
        "sys.exit(1 if 'pandas' in sys.modules else 0)"
    )
    return subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 1


def test_the_overlap_path_does_not_pull_pandas_onto_the_host():
    assert not _imports_pandas("app.services.advisor.fund_overlap"), (
        "importing fund_overlap now loads pandas, which adds ~30 MB to every "
        "serving process. Check for a hoisted `import pandas` in "
        "marketdata/fund_holdings.py -- see the comment at that import."
    )


def test_the_holdings_module_itself_stays_clean_at_import_time():
    """Importing the module is fine; only calling the Excel reader may pay for pandas."""
    assert not _imports_pandas("app.services.marketdata.fund_holdings")
