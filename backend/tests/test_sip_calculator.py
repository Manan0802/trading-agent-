from app.services.advisor.sip_calculator import calculate_required_sip


def test_zero_return_simple():
    # 12,000 in 1 year, 0% return, no inflation, no savings -> 1000/month
    r = calculate_required_sip(12000, 1, 0.0, 0.0, 0.0)
    assert r["required_monthly_sip"] == 1000


def test_inflation_adjusts_target_up():
    r = calculate_required_sip(100000, 10, 0.12, 0.0, 0.06)
    assert r["inflation_adjusted_target"] > 100000


def test_existing_savings_reduce_sip():
    high = calculate_required_sip(1000000, 10, 0.12, 0.0)["required_monthly_sip"]
    low = calculate_required_sip(1000000, 10, 0.12, 500000)["required_monthly_sip"]
    assert low < high


def test_a_goal_due_today_answers_instead_of_crashing():
    """No monthly instalment reaches a target with no months left. The formula
    divides by the number of months, so this used to be a 500."""
    result = calculate_required_sip(100_000, 0, 0.12)
    assert result["required_monthly_sip"] == 0
    assert result["unreachable"] is True
    assert result["net_target_to_achieve"] == 100_000


def test_a_goal_due_today_and_already_funded_is_not_unreachable():
    result = calculate_required_sip(100_000, 0, 0.12, current_savings=150_000)
    assert result["unreachable"] is False
    assert result["net_target_to_achieve"] == 0


def test_a_reachable_goal_says_so_explicitly():
    assert calculate_required_sip(100_000, 10, 0.12)["unreachable"] is False
