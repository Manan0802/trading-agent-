from app.services.advisor.asset_allocator import (
    calculate_risk_score,
    risk_profile_from_score,
    get_allocation,
)


def test_risk_score_mean():
    assert calculate_risk_score([10, 9, 8, 10]) == 9


def test_profile_buckets():
    assert risk_profile_from_score(3) == "conservative"
    assert risk_profile_from_score(6) == "moderate"
    assert risk_profile_from_score(9) == "aggressive"


def test_short_horizon_is_defensive():
    a = get_allocation(1.0, "aggressive")
    assert a["equity"] == 20 and a["debt"] == 70 and a["gold"] == 10


def test_allocation_sums_to_100():
    for yrs in (1, 3, 7, 15):
        for prof in ("conservative", "moderate", "aggressive"):
            a = get_allocation(yrs, prof)
            assert a["equity"] + a["debt"] + a["gold"] == 100
