"""Translating upstream's slot keys into traa's categories.

Written because a port concluded the funds did not exist. They do — AMFI simply
has no Commodity category, and gold and silver sit inside
`Other Scheme - FoF Domestic` separated only by the fund's name.
"""

import pytest

from app.services.advisor import fund_catalogue, fund_universe
from app.services.screener import basket, basket_slots as bs, serve

MIN_PEERS = 8


def test_every_slot_in_every_basket_resolves_to_real_funds():
    """The claim this module exists to correct.

    A port matched upstream's slot keys literally against traa's category
    strings, found nothing, and concluded the universe was missing. Every one of
    these has funds behind it.
    """
    for basket_id in ("MAXX", "BALANCED"):
        definition = basket.get_basket(basket_id)
        for slot_key in definition["slots"]:
            codes = bs.codes_for_slot(slot_key)
            assert codes, f"{basket_id}/{slot_key} resolved to nothing"


def test_every_slot_clears_the_peer_floor_the_fund_screen_uses():
    """Eight is `serve.MIN_PEERS_TO_RANK`. A slot filled from a group smaller
    than that is "best of four", which is the group with three funds left out."""
    assert MIN_PEERS == serve.MIN_PEERS_TO_RANK
    for slot, size in bs.slot_sizes().items():
        assert size >= MIN_PEERS, f"{slot} has only {size} funds behind it"


def test_the_commodity_slots_find_gold_and_silver():
    """AMFI has no Commodity category. These are name matches inside FoF
    Domestic, and getting them wrong fills a gold sleeve with a Nasdaq tracker
    — which is exactly what `fund_universe`'s own comment warns about."""
    gold = bs.codes_for_slot("Commodity::Gold")
    silver = bs.codes_for_slot("Commodity::Silver")
    assert len(gold) >= MIN_PEERS and len(silver) >= MIN_PEERS

    by_code = {f.code: f for f in fund_catalogue.all_funds()}
    for code in gold:
        assert "gold" in by_code[code].name.lower()
    for code in silver:
        assert "silver" in by_code[code].name.lower()


def test_gold_and_silver_do_not_overlap():
    """A gold-and-silver fund is a different exposure from the one a gold sleeve
    is asking for. `fund_universe.gold_funds()` excludes them from gold, so they
    must not turn up in both."""
    gold = set(bs.codes_for_slot("Commodity::Gold"))
    silver = set(bs.codes_for_slot("Commodity::Silver"))
    assert not (gold & silver), sorted(gold & silver)[:3]


def test_the_gold_slot_reuses_traas_existing_definition():
    """Not reimplemented. A second definition of which funds are gold is how two
    screens start disagreeing about the same sleeve."""
    assert set(bs.codes_for_slot("Commodity::Gold")) == {
        f.code for f in fund_universe.gold_funds()
    }


def test_no_slot_picks_up_a_fund_from_another_slots_category():
    seen: dict[str, str] = {}
    for slot in bs.SLOT_CATEGORIES:
        for code in bs.codes_for_slot(slot):
            if code in seen and seen[code] != slot:
                # Gold/silver share a category, so only flag a genuine collision.
                assert {seen[code], slot} == {"Commodity::Gold", "Commodity::Silver"}, (
                    f"{code} is in both {seen[code]} and {slot}"
                )
            seen[code] = slot


def test_an_unknown_slot_raises_rather_than_returning_nothing():
    """An empty pool looks exactly like "no fund qualified today", which is a
    market observation. A missing mapping is a missing line in a table. The two
    must not be confused."""
    with pytest.raises(bs.UnmappedSlot, match="Commodity::Platinum"):
        bs.codes_for_slot("Commodity::Platinum")


def test_the_two_mega_bucket_slots_carry_the_screens_caveat():
    """364 index funds track wildly different indices and 246 sectoral funds bet
    on different sectors. Picking "the best" from either ranks which segment ran,
    not which fund is better run — and a basket filling a slot from one is making
    a sector bet whether or not anyone intended to."""
    assert bs.caveat_for_slot("Equity Index Fund")
    assert bs.caveat_for_slot("Sectoral/ Thematic")
    assert bs.caveat_for_slot("Debt Scheme::Liquid Fund") is None


def test_the_caveats_are_the_same_words_the_fund_screen_uses():
    """Two screens saying the same thing differently is how a reader stops
    believing either."""
    assert bs.SLOT_CAVEATS["Equity Index Fund"] == serve.CAVEATED_SUB_CATEGORIES["Index Funds"]
    assert (
        bs.SLOT_CAVEATS["Sectoral/ Thematic"]
        == serve.CAVEATED_SUB_CATEGORIES["Sectoral/ Thematic"]
    )


def test_every_mapped_category_actually_exists_in_the_catalogue():
    """Guards against a rename in the catalogue silently emptying a slot."""
    known = {f.category for f in fund_catalogue.all_funds()}
    for slot, (category, _keyword) in bs.SLOT_CATEGORIES.items():
        assert category in known, f"{slot} maps to {category!r}, which no fund has"


def test_the_slot_sizes_match_what_the_mapping_returns():
    sizes = bs.slot_sizes()
    for slot in bs.SLOT_CATEGORIES:
        assert sizes[slot] == len(bs.codes_for_slot(slot))


# --------------------------------------- the mapping itself is the content


EXPECTED = {
    "Equity Index Fund": "Other Scheme - Index Funds",
    "Sectoral/ Thematic": "Equity Scheme - Sectoral/ Thematic",
    "Flexi / Multi::Flexi Cap Fund": "Equity Scheme - Flexi Cap Fund",
    "Commodity::Gold": "Other Scheme - FoF Domestic",
    "Commodity::Silver": "Other Scheme - FoF Domestic",
    "Equity Scheme::Large & Mid Cap Fund": "Equity Scheme - Large & Mid Cap Fund",
    "Debt Scheme::Liquid Fund": "Debt Scheme - Liquid Fund",
}


def test_each_slot_maps_to_the_category_it_is_supposed_to():
    """A deliberate change-detector, because here the mapping IS the content.

    A sabotage pointed the index slot at Large Cap Fund and every other test
    stayed green: the slot still resolved, still had funds, still cleared the
    peer floor. Nothing checked it resolved to the *right* place. Silently
    filling a portfolio's index sleeve with large-cap active funds is precisely
    the failure this table exists to prevent.
    """
    assert dict(EXPECTED) == {
        slot: category for slot, (category, _kw) in bs.SLOT_CATEGORIES.items()
    }


@pytest.mark.parametrize(
    "slot,words",
    [
        ("Equity Index Fund", ("index", "nifty", "sensex", "bse", "etf")),
        ("Flexi / Multi::Flexi Cap Fund", ("flexi", "multi")),
        ("Debt Scheme::Liquid Fund", ("liquid", "cash", "money")),
        ("Equity Scheme::Large & Mid Cap Fund", ("large", "mid", "emerging", "equity")),
    ],
)
def test_the_funds_behind_a_slot_look_like_what_the_slot_asked_for(slot, words):
    """The semantic half, which survives a category being renamed.

    Checks the funds themselves rather than the category string: most of what
    fills an index slot should be recognisably an index fund. A mapping that
    points somewhere plausible-but-wrong fails here even if the new category
    exists and is large enough.
    """
    by_code = {f.code: f for f in fund_catalogue.all_funds()}
    names = [by_code[c].name.lower() for c in bs.codes_for_slot(slot)]
    hits = sum(1 for n in names if any(w in n for w in words))
    assert hits / len(names) > 0.5, (
        f"{slot}: only {hits} of {len(names)} funds look like {words}"
    )
