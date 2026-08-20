"""The one place that knows where the reference implementation lives, and it can only read.

We port a method from another team's repository. Their working tree is not ours
to touch -- not a file, not a byte, not once -- and "I'll be careful" is not a
control. So the path lives here and nowhere else, and this module exposes no way
to write through it. There is no `write`, no `open(..., "w")`, no `mkdir`. A
future mistake would have to add one, and `test_reference_repo_is_read_only.py`
fails the moment anything outside this file mentions the path at all.

Configurable through `SCORING_REFERENCE_DIR` so a checkout somewhere else still
works, and absent entirely on a machine that has no copy -- callers ask
`available()` and skip, rather than crashing a suite that has nothing to do with
the reference.

Stdlib only, deliberately: `scripts/verify_scoring_parity.py` imports this while
running under a pinned pandas-2 interpreter that has none of our dependencies.
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT = Path.home() / "BachattDev" / "sip-optimizer" / "server"


def root() -> Path:
    """Where the reference checkout is. Never created, only looked at."""
    configured = os.getenv("SCORING_REFERENCE_DIR", "").strip()
    return Path(configured).expanduser() if configured else _DEFAULT


def available() -> bool:
    return root().is_dir()


def read_source(relative_path: str) -> str:
    """Read one file out of the reference tree. The only door in this module.

    Refuses to resolve outside the reference root -- a caller passing
    `"../../.ssh/id_rsa"` gets an error rather than a file.
    """
    base = root().resolve()
    target = (base / relative_path).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"{relative_path!r} escapes the reference root")
    if not target.is_file():
        raise FileNotFoundError(target)
    return target.read_text(encoding="utf-8")
