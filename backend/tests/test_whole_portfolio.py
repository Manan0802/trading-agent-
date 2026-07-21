import pytest

from app.services.advisor.whole_portfolio import (
    ExternalAsset,
    classify_asset,
    plan_new_money,
)

TARGET = {"equity": 65, "debt": 25, "gold": 10}


def test_epf_and_ppf_are_debt_not_savings():
    """The most common Indian blind spot: a large guaranteed-return balance
    treated as 'savings' rather than as the debt allocation it already is."""
    assert classify_asset("EPF") == "debt"
    assert classify_asset("PPF") == "debt"
    assert classify_asset("Sukanya Samriddhi") == "debt"
    assert classify_asset("Fixed Deposit") == "debt"


def test_equity_and_gold_instruments_classify_correctly():
    assert classify_asset("ESOP") == "equity"
    assert classify_asset("Sovereign Gold Bond") == "gold"
    assert classify_asset("Gold jewellery") == "gold"


def test_unknown_instrument_is_not_silently_guessed():
    assert classify_asset("some structured note") is None


def test_with_no_existing_assets_new_money_follows_the_target():
    plan = plan_new_money(TARGET, existing={}, monthly=10_000)
    assert plan.allocation["equity"] == pytest.approx(6_500, abs=1)
    assert plan.allocation["debt"] == pytest.approx(2_500, abs=1)
    assert plan.allocation["gold"] == pytest.approx(1_000, abs=1)


def test_a_large_epf_balance_pushes_new_money_out_of_debt():
    """This is the defect. 8L EPF + 4L equity is a 67% debt portfolio, and the
    old advice still routed 25% of every rupee into more debt."""
    plan = plan_new_money(
        TARGET, existing={"equity": 400_000, "debt": 800_000}, monthly=20_000
    )
    assert plan.allocation["debt"] == 0
    assert plan.allocation["equity"] > plan.allocation["gold"]


def test_new_money_never_asks_the_user_to_sell():
    """EPF cannot be redeemed, so an over-weight class gets zero, never negative."""
    plan = plan_new_money(
        TARGET, existing={"equity": 0, "debt": 5_000_000}, monthly=10_000
    )
    assert all(amount >= 0 for amount in plan.allocation.values())


def test_the_month_is_fully_allocated():
    for existing in ({}, {"debt": 800_000}, {"equity": 9_000_000, "debt": 100}):
        plan = plan_new_money(TARGET, existing=existing, monthly=25_000)
        assert sum(plan.allocation.values()) == pytest.approx(25_000, abs=1)


def test_current_mix_is_reported_so_the_user_can_check_the_reasoning():
    plan = plan_new_money(
        TARGET, existing={"equity": 400_000, "debt": 800_000}, monthly=20_000
    )
    assert plan.current_mix["debt"] == pytest.approx(66.7, abs=0.1)
    assert plan.current_mix["equity"] == pytest.approx(33.3, abs=0.1)


def test_an_over_weight_class_is_called_out_in_words():
    plan = plan_new_money(
        TARGET, existing={"equity": 400_000, "debt": 800_000}, monthly=20_000
    )
    assert any("debt" in insight.lower() for insight in plan.insights)


def test_a_dominant_single_holding_is_flagged_as_concentration_risk():
    """Employer stock is the classic case — the salary and the holding fail together."""
    plan = plan_new_money(
        TARGET,
        existing={"equity": 900_000, "debt": 100_000},
        monthly=10_000,
        assets=[
            ExternalAsset(name="Employer ESOP", amount=900_000, asset_class="equity"),
            ExternalAsset(name="EPF", amount=100_000, asset_class="debt"),
        ],
    )
    assert any("ESOP" in insight for insight in plan.insights)


def test_zero_monthly_investment_returns_zeroes_not_an_error():
    plan = plan_new_money(TARGET, existing={"debt": 100_000}, monthly=0)
    assert sum(plan.allocation.values()) == 0
    assert plan.current_mix["debt"] == 100.0
