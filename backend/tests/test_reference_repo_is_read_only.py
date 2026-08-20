"""Nothing we build may ever write into the reference checkout. Enforced, not promised.

We port a method from another team's working tree. Across every phase of this
build -- scoring, NAV, metrics, screens -- that tree stays untouched. The way to
keep a rule like that true for months is not discipline, it is making the
mistake impossible to make:

  * exactly one module, `screener/reference.py`, knows where the checkout is
  * that module exposes a single reader and no writer at all
  * this test fails if any other file learns the path, or if a write verb ever
    appears in the reader

So a future accident cannot be a typo in a path string somewhere. It would have
to be someone adding a write API to a file whose whole docstring says not to,
and deleting this test on the way past.
"""

import ast
from pathlib import Path

import pytest

from app.services.screener import reference

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
REFERENCE_MODULE = BACKEND / "app" / "services" / "screener" / "reference.py"

# Knowing the filesystem location, or the env var that overrides it, is what
# makes a file capable of touching the checkout. Only one file may.
PATH_KNOWLEDGE = ("BachattDev", "SCORING_REFERENCE_DIR")

# Anything that can modify a filesystem, matched as an actual call rather than
# as a word -- the module's own docstring names several of these while promising
# not to use them.
WRITE_CALLS = frozenset({
    "write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir",
    "rename", "replace", "remove", "rmtree", "copy", "copytree", "move",
    "chmod", "symlink_to", "hardlink_to", "truncate", "writelines", "write",
})

SCANNED_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".sh", ".mjs"}
SKIP_DIRS = {"node_modules", "venv", ".parity-venv", "__pycache__", ".git", "dist", "logs"}


def _source_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        if SKIP_DIRS & set(path.parts):
            continue
        yield path


def test_only_one_module_knows_where_the_reference_lives():
    offenders = []
    for path in _source_files(REPO):
        if path == REFERENCE_MODULE or path == Path(__file__):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in PATH_KNOWLEDGE:
            if token in text:
                offenders.append(f"{path.relative_to(REPO)} mentions {token!r}")
    assert not offenders, (
        "Only screener/reference.py may know the reference location. Route the "
        "access through reference.read_source() instead.\n  " + "\n  ".join(offenders)
    )


def _called_names(tree: ast.AST) -> set[str]:
    """Every function/method name actually invoked -- not words in prose.

    The first version of this test matched raw text and flagged the module's own
    docstring, which says "no mkdir". Scanning source as text cannot tell a
    promise from a call; the AST can.
    """
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                names.add(func.attr)
            elif isinstance(func, ast.Name):
                names.add(func.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_the_reader_has_no_way_to_write():
    called = _called_names(ast.parse(REFERENCE_MODULE.read_text()))
    found = sorted(called & WRITE_CALLS)
    assert not found, (
        f"screener/reference.py gained a write path: {found}. It exists to be "
        "the one door to a tree we must never modify."
    )


def test_the_reader_opens_nothing_in_write_mode():
    """Belt to the braces above: no `open(..., 'w')` in any form."""
    tree = ast.parse(REFERENCE_MODULE.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if name == "open":
                mode = next((a for a in node.args[1:2]), None)
                assert mode is None or getattr(mode, "value", "r").startswith("r"), \
                    "reference.py opened a file for writing"


def test_reading_outside_the_reference_root_is_refused():
    with pytest.raises(ValueError, match="escapes"):
        reference.read_source("../../../etc/passwd")


@pytest.mark.skipif(not reference.available(), reason="reference checkout not present")
def test_reading_inside_the_root_still_works():
    assert "def _hybrid" in reference.read_source("scripts/fill_metrics.py")


@pytest.mark.skipif(not reference.available(), reason="reference checkout not present")
def test_the_checkout_is_actually_unmodified():
    """The claim itself, checked against git rather than asserted.

    Skips when the checkout is not a git repo. Reports the user's own edits too,
    which is the point -- if this goes red, look before assuming it was us.
    """
    import subprocess

    root = reference.root()
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip("reference checkout is not a git repository")
    assert not result.stdout.strip(), (
        "The reference checkout has uncommitted changes:\n" + result.stdout
        + "\nIf we did this, it is a bug. If you did, this test is just telling you."
    )


def test_the_guard_can_actually_fail(tmp_path):
    """This suite has been fooled before by a check that could only pass."""
    planted = tmp_path / "oops.py"
    planted.write_text('P = Path.home() / "BachattDev" / "sip-optimizer"\n')
    hits = [p for p in _source_files(tmp_path)
            if any(t in p.read_text() for t in PATH_KNOWLEDGE)]
    assert hits, "the scanner cannot detect the thing it exists to detect"
