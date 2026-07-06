from app.services.advisor.rebalancer import check_rebalancing_needed


def test_no_drift():
    r = check_rebalancing_needed(
        {"equity": 75, "debt": 15, "gold": 10}, {"equity": 75, "debt": 15, "gold": 10}
    )
    assert r["needs_rebalancing"] is False and r["actions"] == []


def test_drift_triggers_sell():
    r = check_rebalancing_needed(
        {"equity": 85, "debt": 10, "gold": 5}, {"equity": 75, "debt": 15, "gold": 10}
    )
    assert r["needs_rebalancing"] is True
    eq = next(a for a in r["actions"] if a["asset"] == "equity")
    assert eq["action"] == "SELL" and eq["drift"] == 10
