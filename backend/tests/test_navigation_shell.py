"""The trail and ⌘K — the two pieces §15's navigation was missing.

Navigation, deep links and back already worked. What did not exist was any way
to see the path you took, or to reach a destination without the nav.

Structural checks, and the docstring says so: there is no React test runner
here. `scripts/sweep.mjs` and `scripts/a11y.mjs` walk the live app.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


def _read(rel: str) -> str:
    return (SRC / rel).read_text()


class TestTheTrailNamesEveryHop:
    def test_the_middle_hop_travels_in_router_state(self):
        """It cannot come from the URL.

        `/screener/stock/HDFCBANK` says nothing about which fund you were
        looking at, and reconstructing it from history is wrong the moment
        somebody opens the link directly.
        """
        trail = _read("components/Trail.tsx")
        assert "location.state" in trail
        assert "via" in trail

    def test_a_deep_link_gets_a_shorter_trail_rather_than_a_wrong_one(self):
        trail = _read("components/Trail.tsx")
        assert "if (via && via.to !== pathname) hops.push" in trail, (
            "a deep link has no middle hop, and inventing one is worse than "
            "showing two crumbs instead of three"
        )

    def test_a_top_level_page_gets_no_trail_at_all(self):
        """One crumb is not a trail; it renders as a stray word above the heading."""
        trail = _read("components/Trail.tsx")
        assert "if (pathname === root.to) return []" in trail

    def test_the_last_crumb_is_a_name_not_an_identifier(self):
        """`122639` is what the app calls the fund. It is not what the reader
        recognises as the fund they just clicked."""
        trail = _read("components/Trail.tsx")
        assert "useTrailLeaf" in trail
        for page in ("pages/FundAnalysis.tsx", "pages/StockAnalysis.tsx"):
            assert "useTrailLeaf(data?.name)" in _read(page), f"{page} never names itself"

    def test_leaving_a_page_clears_its_name(self):
        trail = _read("components/Trail.tsx")
        assert "return () => setLeaf(null)" in trail, (
            "without the cleanup the previous fund's name stays in the trail on "
            "the next page"
        )

    def test_the_fund_page_carries_itself_forward_to_a_company(self):
        """The two-hop case this exists for: Screener → a fund → a company."""
        fund = _read("pages/FundAnalysis.tsx")
        assert "state={{ via }}" in fund
        assert "const via = { label: data.name" in fund

    def test_every_hop_but_the_last_is_clickable(self):
        trail = _read("components/Trail.tsx")
        assert "<Link" in trail
        assert 'aria-current="page"' in trail, "the current page must not be a link"
        assert 'aria-label="Breadcrumb"' in trail


class TestTheCommandPaletteReachesEverything:
    def test_it_is_fed_the_same_list_as_the_nav(self):
        """A palette that reaches five of six is worse than none: the missing
        one is the one somebody will hunt for."""
        app = _read("App.tsx")
        assert "<CommandPalette destinations={NAV} />" in app

    def test_every_destination_is_in_that_list(self):
        """Pinned as a set, not a count. A destination added to the nav and
        missing from ⌘K is exactly the drift this list exists to prevent, and a
        count would let a swap through."""
        app = _read("App.tsx")
        block = app[app.index("const NAV = ["):]
        block = block[: block.index("]")]
        routes = set(re.findall(r"to: '([^']+)'", block))
        assert routes == {
            "/portfolio",
            "/portfolio/holdings",
            "/research",
            "/why",
            "/decide",
            "/screener",
            "/goals",
            "/profile",
        }, routes

    def test_every_destination_in_the_list_is_actually_routed(self):
        """A palette entry that 404s is worse than a missing one."""
        app = _read("App.tsx")
        block = app[app.index("const NAV = ["):]
        block = block[: block.index("]")]
        for route in re.findall(r"to: '([^']+)'", block):
            assert f'path="{route}"' in app, f"{route} is in the nav and not routed"

    def test_it_opens_on_both_cmd_k_and_ctrl_k(self):
        palette = _read("components/CommandPalette.tsx")
        assert "event.metaKey || event.ctrlKey" in palette, (
            "⌘K on a Mac and Ctrl+K everywhere else — one of the two is not a "
            "keyboard shortcut, it is a Mac feature"
        )
        assert "event.preventDefault()" in palette, "the browser's own ⌘K would win"

    def test_escape_closes_it(self):
        palette = _read("components/CommandPalette.tsx")
        assert "event.key === 'Escape'" in palette

    def test_it_is_navigable_without_a_mouse(self):
        palette = _read("components/CommandPalette.tsx")
        for key in ("ArrowDown", "ArrowUp", "Enter"):
            assert key in palette, f"{key} does nothing"
        assert 'role="dialog"' in palette and 'aria-modal="true"' in palette
        assert 'role="listbox"' in palette and 'aria-selected=' in palette

    def test_it_says_when_nothing_matches(self):
        palette = _read("components/CommandPalette.tsx")
        assert "Nothing here by that name" in palette, (
            "an empty list is indistinguishable from a broken palette"
        )
