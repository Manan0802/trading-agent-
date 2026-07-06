from app.services.llm.advisor_prompts import get_goal_explanation


def test_fallback_explanation_mentions_projected():
    out = get_goal_explanation(
        {"goal_name": "House", "target_amount": 2000000, "years": 5},
        {"required_monthly_sip": 25000, "wealth_created": 500000},
        {"equity": 50, "debt": 40, "gold": 10},
    )
    assert "projected" in out.lower()
    assert "guaranteed nahi" in out.lower() or "guaranteed" in out.lower()
