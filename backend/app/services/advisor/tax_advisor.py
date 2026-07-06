def _tax_rate(income: float) -> float:
    if income <= 250000:
        return 0.0
    if income <= 500000:
        return 0.05
    if income <= 1000000:
        return 0.20
    return 0.30


def generate_tax_saving_plan(
    annual_income: float,
    existing_80c: float = 0,
    existing_80d: float = 0,
    has_nps: bool = False,
) -> dict:
    remaining_80c = max(0.0, 150000 - existing_80c)
    elss_suggestion = min(remaining_80c, 150000)
    rate = _tax_rate(annual_income)
    nps_suggestion = 50000 if annual_income > 500000 and not has_nps else 0
    health_gap = max(0.0, 25000 - existing_80d)

    return {
        "elss_recommended": elss_suggestion,
        "tax_saved_via_elss": round(elss_suggestion * rate),
        "nps_recommended": nps_suggestion,
        "tax_saved_via_nps": round(nps_suggestion * rate),
        "health_insurance_gap": health_gap,
        "tax_saved_via_80d": round(health_gap * rate),
        "total_potential_tax_saving": round(
            (elss_suggestion + nps_suggestion + health_gap) * rate
        ),
        "priority_order": ["ELSS (80C)", "Health Insurance (80D)", "NPS (80CCD1B)"],
    }
