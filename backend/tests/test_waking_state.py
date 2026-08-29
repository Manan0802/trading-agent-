"""The cold start is the modal experience, and it had no state of its own.

Render's free tier sleeps after fifteen minutes idle and takes about a minute
to wake. For an app opened a few times a week that makes the cold start the
COMMON case, not an edge case -- and `api.ts` had no timeout at all, so a
waking container was indistinguishable from a hung one.

§13.5 tabled ten UI states under the heading "the half that was entirely
missing" and this was the eleventh. Its rule for loading -- "skeletons, no
spinner" -- is the worst available presentation of a sixty-second wait, because
a skeleton promises data is arriving now.

The frontend has no unit-test layer (no vitest, no jest, no .test.tsx), so this
pins the contract from here rather than not at all. When a runner exists these
become component tests and this file goes.
"""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"
API = FRONTEND / "lib" / "api.ts"
NOTICE = FRONTEND / "components" / "WakingNotice.tsx"
APP = FRONTEND / "App.tsx"


def test_the_client_cannot_hang_forever():
    source = API.read_text()
    timeout = re.search(r"WAKE_TIMEOUT_MS\s*=\s*([\d_]+)", source)
    assert timeout, "api.ts declares no request timeout"
    ms = int(timeout.group(1).replace("_", ""))
    assert ms >= 60_000, (
        f"{ms}ms is under the ~60s the host takes to wake — a real wake would "
        "be reported as a failure"
    )
    assert ms <= 180_000, f"{ms}ms is long enough that a genuine hang looks normal"
    assert "timeout: WAKE_TIMEOUT_MS" in source, "the timeout is declared and not used"


def test_a_slow_request_announces_itself_before_it_finishes():
    """Announcing only on completion would mean announcing after the wait."""
    source = API.read_text()
    threshold = re.search(r"WAKING_AFTER_MS\s*=\s*([\d_]+)", source)
    assert threshold, "api.ts has no threshold for 'this is probably a cold start'"
    assert int(threshold.group(1).replace("_", "")) <= 5_000
    assert "export function onWaking" in source, "nothing can subscribe to the state"
    assert "setTimeout(() => announce(true), WAKING_AFTER_MS)" in source, (
        "the waking state is announced on a timer, not on completion"
    )
    assert source.count("settled()") >= 2, (
        "both the success and the error path must clear the state, or one "
        "failed request leaves the notice up forever"
    )


def test_the_notice_says_what_is_happening_and_is_not_a_spinner():
    source = NOTICE.read_text()
    assert "role=\"status\"" in source and "aria-live" in source, (
        "a state that appears without focus has to be announced to a screen "
        "reader — a11y.mjs is a real gate here"
    )
    assert "Waking the server" in source, "the notice does not say what is happening"
    assert "Nothing is wrong" in source, (
        "a sixty-second wait reads as a fault unless the copy says otherwise"
    )
    assert "animate-spin" not in source and "Spinner" not in source, (
        "§13.7 forbids motion without a user action behind it"
    )


def test_it_is_mounted_above_the_page_not_inside_one():
    source = APP.read_text()
    assert "<WakingNotice />" in source, "the notice is never rendered"
    main = re.search(r"<main[^>]*>(.{0,300})", source, re.S)
    assert main and "<WakingNotice />" in main.group(1), (
        "the server wakes for every request on the page, not for one panel, so "
        "the notice belongs above the page rather than inside a route"
    )
