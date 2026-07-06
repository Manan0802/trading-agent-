def calculate_risk_score(answers: list[int]) -> int:
    return round(sum(answers) / len(answers))


def risk_profile_from_score(score: int) -> str:
    if score <= 4:
        return "conservative"
    if score <= 7:
        return "moderate"
    return "aggressive"


# (timeline_bucket, risk_profile) -> (equity, debt, gold)
_MATRIX = {
    ("short", "conservative"): (20, 70, 10),
    ("short", "moderate"): (20, 70, 10),
    ("short", "aggressive"): (20, 70, 10),
    ("mid", "conservative"): (30, 60, 10),
    ("mid", "moderate"): (50, 40, 10),
    ("mid", "aggressive"): (65, 25, 10),
    ("long", "conservative"): (50, 40, 10),
    ("long", "moderate"): (65, 25, 10),
    ("long", "aggressive"): (75, 15, 10),
    ("verylong", "conservative"): (65, 25, 10),
    ("verylong", "moderate"): (75, 15, 10),
    ("verylong", "aggressive"): (85, 10, 5),
}


def _timeline_bucket(years: float) -> str:
    if years < 2:
        return "short"
    if years <= 5:
        return "mid"
    if years <= 10:
        return "long"
    return "verylong"


def get_allocation(years: float, risk_profile: str) -> dict:
    eq, debt, gold = _MATRIX[(_timeline_bucket(years), risk_profile)]
    return {"equity": eq, "debt": debt, "gold": gold}


_PRODUCTS = {
    "equity": ["Nifty 50 Index Fund (Direct Growth)", "NIFTYBEES (ETF)"],
    "debt": ["HDFC Short Duration Fund", "Parag Parikh Liquid Fund"],
    "gold": ["Nippon India Gold ETF (GOLDBEES)", "Sovereign Gold Bond (SGB)"],
}


def recommended_products(allocation: dict) -> dict[str, list[str]]:
    return {asset: _PRODUCTS[asset] for asset, pct in allocation.items() if pct > 0}
