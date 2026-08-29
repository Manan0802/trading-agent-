"""The eight devices, and the two states every chart in this app used to skip.

§13.5 lists ten states a surface can be in. Loading and empty were missing from
every chart here, and in practice that means a blank rectangle — which is
indistinguishable from "this fund had no drawdown", "we could not fetch it", and
"the component threw". The reader cannot tell a fact from an outage.

**These are structural checks, and that is stated rather than implied.** There is
no React test runner in this repo and adding one is not this slice. What they
catch is the realistic regression: a device that stops routing through
`ChartFrame` and goes back to rendering nothing. What they cannot catch is a
`ChartFrame` that renders the wrong thing — `scripts/a11y.mjs` walks the live app
for that.
"""

import re
from pathlib import Path

import pytest

CHARTS = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "components" / "charts"

# §13.6's eight. The step used to say five, which implied three were done.
DEVICES = [
    "Bullet",
    "DotGrid",
    "Fan",
    "RebasedLine",
    "Slope",
    "SortedStackedBar",
    "Sparkline",
    "Underwater",
]


def test_all_eight_devices_exist():
    """Zero of eight existed. The count is eight, not five."""
    missing = [d for d in DEVICES if not (CHARTS / f"{d}.tsx").exists()]
    assert not missing, f"missing devices: {missing}"


@pytest.mark.parametrize("device", DEVICES)
def test_a_device_cannot_render_a_blank_box(device):
    source = (CHARTS / f"{device}.tsx").read_text()
    assert "ChartFrame" in source, (
        f"{device} does not route through ChartFrame, so its empty state is a "
        "blank rectangle that looks exactly like an outage"
    )
    assert "chartState(" in source, f"{device} never computes which state it is in"
    assert re.search(r"\bloading\b", source), f"{device} has no loading state"


@pytest.mark.parametrize("device", DEVICES)
def test_a_device_says_why_it_is_empty(device):
    """"No data" is not a reason. An empty chart has to say which kind of empty."""
    source = (CHARTS / f"{device}.tsx").read_text()
    assert "emptyNote" in source, (
        f"{device} falls back to the generic empty note; say what is missing"
    )


@pytest.mark.parametrize("device", DEVICES)
def test_a_device_is_reachable_without_sight(device):
    source = (CHARTS / f"{device}.tsx").read_text()
    assert "label" in source, f"{device} has no accessible label"


def test_the_frame_handles_all_three_states():
    source = (CHARTS / "ChartFrame.tsx").read_text()
    for state in ("loading", "empty"):
        assert f"state === '{state}'" in source, f"the frame ignores {state}"
    assert 'role="status"' in source, (
        "loading and empty must announce themselves; a screen reader on a "
        "silent div hears the previous content"
    )


def test_the_pie_is_deleted_not_deprecated():
    """§13.6: never a pie. A donut asks people to compare angles, which they are
    measurably bad at, and it needs a legend — so reading it is a lookup.

    Leaving the component in place means allocation is shown two ways on two
    screens, which is how a design rule quietly stops being one.
    """
    src = CHARTS.parent.parent
    assert not (src / "components" / "AllocationPie.tsx").exists(), (
        "AllocationPie.tsx is back"
    )
    offenders = [
        path.relative_to(src)
        for path in src.rglob("*.tsx")
        if "AllocationPie" in path.read_text()
    ]
    assert not offenders, f"still imported by: {offenders}"


def test_the_rebasing_function_the_plan_said_was_missing_now_exists():
    """`lib/chart.ts` had UTC dates, axis ticks, padded domains and a tooltip
    style, and no way to put two series on the same starting line — which is
    what the rebased-line device is."""
    chart = (CHARTS.parent.parent / "lib" / "chart.ts").read_text()
    assert "export function rebase(" in chart
    assert "export function underwater(" in chart
    assert "r.own !== null && r.peer !== null" in chart, (
        "rebasing each series to its own first point silently compares "
        "different periods when one starts earlier, and looks entirely normal"
    )
