def calculate_required_sip(
    target_amount: float,
    years: float,
    annual_return_rate: float,
    current_savings: float = 0.0,
    inflation_rate: float = 0.06,
) -> dict:
    """Every figure is continuous in `years`, so fractional horizons are exact.

    The callers used to cast to int first. A goal 16.8 years away was priced
    over 16, which quietly asks for a larger monthly figure than the goal needs
    and made the live preview on the edit form disagree with what got saved.
    """
    inflation_adjusted_target = target_amount * ((1 + inflation_rate) ** years)
    r_monthly = annual_return_rate / 12
    n = years * 12
    fv_existing = current_savings * ((1 + r_monthly) ** n)
    remaining_target = max(0.0, inflation_adjusted_target - fv_existing)

    if n <= 0:
        # A goal due today. There is no monthly instalment that reaches it, and
        # the formula divides by the number of months, so this used to be a 500
        # rather than an answer. The shortfall is the whole honest reply.
        return {
            "required_monthly_sip": 0.0,
            "inflation_adjusted_target": round(inflation_adjusted_target, 0),
            "future_value_of_existing_savings": round(current_savings, 0),
            "net_target_to_achieve": round(remaining_target, 0),
            "total_invested": 0.0,
            "wealth_created": 0.0,
            "unreachable": remaining_target > 0,
        }

    if r_monthly == 0:
        sip = remaining_target / n
    else:
        sip = remaining_target * r_monthly / (((1 + r_monthly) ** n - 1) * (1 + r_monthly))

    return {
        "required_monthly_sip": round(sip, 0),
        "inflation_adjusted_target": round(inflation_adjusted_target, 0),
        "future_value_of_existing_savings": round(fv_existing, 0),
        "net_target_to_achieve": round(remaining_target, 0),
        "total_invested": round(sip * n, 0),
        "wealth_created": round(remaining_target - (sip * n), 0),
        # Always present so callers never have to guess whether the key exists.
        "unreachable": False,
    }
