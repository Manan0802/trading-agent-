"""Every third-party module `app/` imports must be declared in requirements.txt.

Written after the third instance of the same failure, not the first:

    numpy      imported directly, undeclared, arrived via yfinance   (fixed earlier)
    pandas     imported by SEVEN files, undeclared, via mftool/yfinance
    requests   imported by marketdata/nse_delivery.py, undeclared, via mftool

Each was found by accident. None would have failed a test, because the module
was always present -- some other package happened to pull it in. That is the
whole hazard: the dependency is satisfied by luck, and the luck is a package the
Phase 1 plan intends to REMOVE. `yfinance` is retired for prices, and it is one
of the two suppliers for all three of the above.

So this test does not check that imports work. It checks that they are ASKED
FOR. Those are different questions and only the second one survives a
dependency being dropped.
"""

import ast
import pathlib
import re
import sys
from importlib import metadata

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_LOCAL = {"app", "tests", "scripts"}

# import name -> distribution name, where they differ.
_ALIAS = {
    "dotenv": "python-dotenv",
    "jose": "python-jose",
    "multipart": "python-multipart",
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
    "jwt": "pyjwt",
    "bs4": "beautifulsoup4",
    "fitz": "pymupdf",
}

# Guaranteed by a declared package's own pin. Pinning these ourselves invites a
# resolver conflict for no benefit -- starlette's version is fastapi's business.
_GUARANTEED_BY = {"starlette": "fastapi"}


def _imported_modules() -> set[str]:
    found: set[str] = set()
    for path in (_ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return {m for m in found if m not in sys.stdlib_module_names and m not in _LOCAL}


def _declared() -> set[str]:
    """Distribution names asked for, INCLUDING what a declared extra pulls in.

    `fastapi-users[sqlalchemy]` explicitly requests the sqlalchemy extra, which
    installs `fastapi-users-db-sqlalchemy`. That module is asked for -- just not
    by name -- and treating it as undeclared is a false positive. Note the line
    this does NOT cross: a package that arrives because some *other* dependency
    happens to need it is exactly the hazard, and stays undeclared.
    """
    out: set[str] = set()
    for line in (_ROOT / "requirements.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        base = re.split(r"[<>=\[\s]", line)[0].lower().replace("_", "-")
        out.add(base)
        extras = re.search(r"\[([^\]]+)\]", line)
        if not extras:
            continue
        try:
            reqs = metadata.requires(base) or []
        except metadata.PackageNotFoundError:
            continue
        wanted = {e.strip() for e in extras.group(1).split(",")}
        for req in reqs:
            marker = re.search(r'extra\s*==\s*[\'"]([^\'"]+)', req)
            if marker and marker.group(1) in wanted:
                out.add(re.split(r"[<>=\[\s;]", req)[0].lower().replace("_", "-"))
    return out


def test_every_third_party_import_is_declared():
    declared = _declared()
    missing = []
    for mod in sorted(_imported_modules()):
        if mod in _GUARANTEED_BY:
            assert _GUARANTEED_BY[mod] in declared, (
                f"{mod} is exempt only because {_GUARANTEED_BY[mod]} declares it, "
                "and that is no longer in requirements.txt"
            )
            continue
        name = _ALIAS.get(mod, mod).lower().replace("_", "-")
        if name not in declared:
            missing.append(mod)
    assert not missing, (
        f"imported by app/ but not in requirements.txt: {missing}. "
        "They may import fine today because another package pulls them in -- "
        "that is the bug, not the defence."
    )
