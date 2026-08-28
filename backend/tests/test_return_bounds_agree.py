"""The return slider's range is defined twice, and nothing keeps the two equal.

`portfolio.py` returns `return_bounds` to the client with the comment that the
assumed return "may have been clamped" — the field exists so the UI does not
have to guess the range. `Decide.tsx` guesses it anyway, as `min={4} max={16}`.

They agree today. If `RETURN_BOUNDS` moves, the slider keeps offering the old
range, the backend silently clamps, and the user drags to a number the app then
does not use — the one failure `return_bounds` was added to prevent.
"""

import re
from pathlib import Path

from app.services.advisor import levers

SLIDER = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend" / "src" / "pages" / "Decide.tsx"
)


def test_the_hardcoded_slider_matches_the_backend_bounds():
    source = SLIDER.read_text()
    lo = re.search(r"min=\{(\d+(?:\.\d+)?)\}", source)
    hi = re.search(r"max=\{(\d+(?:\.\d+)?)\}", source)
    assert lo and hi, "Decide.tsx no longer hardcodes slider bounds — good; delete this test"

    backend = (levers.RETURN_BOUNDS[0] * 100, levers.RETURN_BOUNDS[1] * 100)
    assert (float(lo.group(1)), float(hi.group(1))) == backend, (
        f"slider offers {lo.group(1)}-{hi.group(1)}%, backend clamps to "
        f"{backend[0]}-{backend[1]}%. Read `return_bounds` from the API instead."
    )


def test_clamp_actually_uses_those_bounds():
    """So the test above is pinned to the thing that does the clamping."""
    assert levers.clamp_return(0.40) == levers.RETURN_BOUNDS[1]
    assert levers.clamp_return(0.001) == levers.RETURN_BOUNDS[0]
