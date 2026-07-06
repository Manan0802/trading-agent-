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
