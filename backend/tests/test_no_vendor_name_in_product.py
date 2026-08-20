"""The vendor's name may live in our engineering notes. It must never reach a user.

Manan's rule, and it is the right one: comments and docstrings can say where a
method came from -- that is provenance, and losing it would make the port
unverifiable six months from now. But nothing a person sees inside traa should
carry another company's name. Not a column header, not an API field, not a
tooltip.

A promise decays; a test does not. This walks the two surfaces that actually
reach a user -- the API contract (schemas + routers) and the frontend -- and
fails if the name appears in either. If a future response field gets called
`bachatt_score` because it was convenient, this goes red before it ships.

Deliberately NOT scanned: services, scripts and tests. That is where the
provenance belongs and where it is useful.
"""

from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND = BACKEND.parent / "frontend" / "src"

# Surfaces a user can actually observe.
USER_FACING = (
    BACKEND / "app" / "schemas",   # every API response shape
    BACKEND / "app" / "routers",   # paths, query params, error strings
    FRONTEND,                      # every rendered string
)

VENDOR_NAMES = ("bachatt",)


def _offending_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if any(name in low for name in VENDOR_NAMES):
            try:
                shown = path.relative_to(BACKEND.parent)
            except ValueError:      # a path outside the repo, e.g. the self-test fixture
                shown = path
            hits.append(f"{shown}:{i}: {line.strip()[:100]}")
    return hits


def _scan(root: Path) -> list[str]:
    if not root.exists():
        return []
    suffixes = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json"}
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if "node_modules" in path.parts or "__pycache__" in path.parts:
            continue
        hits.extend(_offending_lines(path))
    return hits


@pytest.mark.parametrize("root", USER_FACING, ids=lambda p: p.name)
def test_vendor_name_never_reaches_a_user(root):
    hits = _scan(root)
    assert not hits, (
        "A vendor name reached a user-facing surface. Rename the field or the copy "
        "-- provenance belongs in services/ and scripts/, not in what the app renders.\n  "
        + "\n  ".join(hits)
    )


def test_the_guard_can_actually_fail(tmp_path):
    """This suite has been fooled before by a check that could only pass."""
    planted = tmp_path / "Fake.tsx"
    planted.write_text('export const label = "Bachatt Score";\n')
    assert _scan(tmp_path), "the scanner cannot detect the thing it exists to detect"
