from datetime import date

import pytest

from app.services.marketdata import announcements as ann


def _row(desc: str, when: str = "24-Jul-2026 18:01:00", symbol: str = "TATASTEEL") -> dict:
    return {
        "an_dt": when,
        "desc": desc,
        "symbol": symbol,
        "sm_name": "Tata Steel Limited",
        "attchmntText": f"Tata Steel Limited has informed the Exchange about {desc}.",
        "attchmntFile": "https://nsearchives.nseindia.com/corporate/x.pdf",
    }


class TestTheFilterIsTheProduct:
    """NSE published a hundred announcements for Tata Steel in seven months, of
    which twenty were conference-call notices and thirteen were copies of
    newspaper advertisements. A list of a hundred is worse than no list."""

    @pytest.mark.parametrize(
        "category",
        [
            "Credit Rating",
            "Resignation of Independent director",
            "Change in Directors/Key Managerial Personnel",
            "Acquisition",
            "Scheme of Arrangement",
            "Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company",
            "Disclosure under SEBI Takeover Regulations",
            "Dividend",
            "Buyback",
        ],
    )
    def test_things_that_change_what_you_own_are_kept(self, category):
        assert ann.is_material(category)

    @pytest.mark.parametrize(
        "category",
        [
            "Analysts/Institutional Investor Meet/Con. Call Updates",
            "Copy of Newspaper Publication",
            "Investor Presentation",
            "Trading Window",
            "News Verification",
            "Certificate under SEBI (Depositories and Participants) Regulations, 2018",
        ],
    )
    def test_noise_is_dropped(self, category):
        assert not ann.is_material(category)

    def test_a_newspaper_copy_of_a_dividend_notice_is_still_a_copy(self):
        """The exclusions beat the inclusions on purpose. A newspaper
        publication of a dividend notice is the notice we already have,
        printed again."""
        assert ann.is_material("Dividend")
        assert not ann.is_material("Copy of Newspaper Publication - Dividend")

    def test_an_unrecognised_category_is_dropped_rather_than_guessed(self):
        assert not ann.is_material("Some Category NSE Invented This Morning")
        assert not ann.is_material("")


class TestReadingTheFeed:
    def test_material_rows_come_back_newest_first_with_a_dropped_count(
        self, monkeypatch
    ):
        rows = [
            _row("Credit Rating", "10-Mar-2026 09:00:00"),
            _row("Copy of Newspaper Publication", "11-Mar-2026 09:00:00"),
            _row("Acquisition", "20-Jun-2026 09:00:00"),
            _row("Investor Presentation", "21-Jun-2026 09:00:00"),
            _row("Trading Window", "22-Jun-2026 09:00:00"),
        ]
        monkeypatch.setattr(ann, "_cached_fetch", lambda *a, **k: rows)

        kept, dropped = ann.material_announcements("TATASTEEL", today=date(2026, 7, 27))
        assert [a.category for a in kept] == ["Acquisition", "Credit Rating"]
        assert dropped == 3

    def test_a_row_with_an_unreadable_date_is_counted_not_crashed_on(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            ann,
            "_cached_fetch",
            lambda *a, **k: [_row("Credit Rating", "not a date"), _row("Acquisition")],
        )
        kept, dropped = ann.material_announcements("X", today=date(2026, 7, 27))
        assert [a.category for a in kept] == ["Acquisition"]
        assert dropped == 1

    def test_the_company_name_is_carried_so_a_row_can_be_read_alone(
        self, monkeypatch
    ):
        monkeypatch.setattr(ann, "_cached_fetch", lambda *a, **k: [_row("Credit Rating")])
        kept, _ = ann.material_announcements("TATASTEEL", today=date(2026, 7, 27))
        assert kept[0].company == "Tata Steel Limited"
        assert kept[0].published == date(2026, 7, 24)
        assert kept[0].attachment

    def test_an_empty_feed_is_not_an_error(self, monkeypatch):
        monkeypatch.setattr(ann, "_cached_fetch", lambda *a, **k: [])
        kept, dropped = ann.material_announcements("X", today=date(2026, 7, 27))
        assert kept == []
        assert dropped == 0

    def test_an_unreachable_exchange_raises_rather_than_returning_silence(
        self, monkeypatch
    ):
        """An empty list would read as 'nothing happened', which is a different
        and much worse claim than 'we could not check'."""

        def boom(*a, **k):
            raise ann.AnnouncementError("NSE announcements unavailable for X: timeout")

        monkeypatch.setattr(ann, "_cached_fetch", boom)
        with pytest.raises(ann.AnnouncementError):
            ann.material_announcements("X", today=date(2026, 7, 27))
