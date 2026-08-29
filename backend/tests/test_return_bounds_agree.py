"""The return slider's range must come from the server, not from a literal.

`portfolio.py` returns `return_bounds` with the comment that the assumed return
"may have been clamped" -- the field exists so the UI does not have to guess the
range. `Decide.tsx` guessed it anyway, as `min={4} max={16}`. They agreed, and
nothing kept them agreeing: move `RETURN_BOUNDS` and the slider would go on
offering the old range while the backend clamped to a different one, so the user
drags to a number the app then does not use.

The earlier version of this test pinned the two literals to each other. That was
right while the literal existed, and BUILD.md's slice 0.5 said to delete this
file once it did not. Deleting it would leave nothing watching for the literal
coming back, so it checks the stronger thing instead: that the slider reads the
field.
"""

import re
from pathlib import Path

from app.services.advisor import levers

DECIDE = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend" / "src" / "pages" / "Decide.tsx"
)


def test_the_slider_reads_the_bounds_the_server_sends():
    source = DECIDE.read_text()
    assert "data?.return_bounds" in source, (
        "Decide.tsx no longer reads `return_bounds` from the levers response"
    )
    slider = re.search(r"type=\"range\"(.{0,200}?)step=", source, re.S)
    assert slider, "the assumed-return slider is gone or restructured"
    body = slider.group(1)
    for bound in ("min", "max"):
        literal = re.search(rf"{bound}=\{{(\d+(?:\.\d+)?)\}}", body)
        assert not literal, (
            f"{bound} is a literal again ({literal.group(1)}). The server sends "
            "the range it will honour; a second copy of it drifts silently."
        )


def test_the_fallback_matches_what_the_backend_would_clamp_to():
    """The slider needs a range before the first response lands.

    That fallback is a second copy of the bounds and so has the same drift
    problem, in the narrow window before data arrives. It is pinned rather than
    removed because a range input needs numbers on first paint.
    """
    source = DECIDE.read_text()
    fallback = re.search(r"return_bounds \?\? \[([\d.]+), ([\d.]+)\]", source)
    assert fallback, "the pre-response fallback for return_bounds is gone"
    assert (float(fallback.group(1)), float(fallback.group(2))) == tuple(
        levers.RETURN_BOUNDS
    ), (
        f"fallback offers {fallback.group(1)}-{fallback.group(2)}, backend "
        f"clamps to {levers.RETURN_BOUNDS}"
    )


def test_clamp_actually_uses_those_bounds():
    """So the tests above are pinned to the thing that does the clamping."""
    assert levers.clamp_return(0.40) == levers.RETURN_BOUNDS[1]
    assert levers.clamp_return(0.001) == levers.RETURN_BOUNDS[0]
