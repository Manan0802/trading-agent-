from app.jobs.scheduler import run_rebalancing_check


def test_no_alert_when_balanced():
    assert (
        run_rebalancing_check(
            {"equity": 75, "debt": 15, "gold": 10},
            {"equity": 75, "debt": 15, "gold": 10},
            "+910000000000",
        )
        is False
    )


def test_alert_when_drifted():
    # no Twilio creds -> send returns None but function still reports triggered
    assert (
        run_rebalancing_check(
            {"equity": 85, "debt": 10, "gold": 5},
            {"equity": 75, "debt": 15, "gold": 10},
            "+910000000000",
        )
        is True
    )
