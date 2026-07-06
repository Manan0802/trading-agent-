def check_rebalancing_needed(
    current_allocation: dict,
    target_allocation: dict,
    drift_threshold: float = 5.0,
) -> dict:
    actions = []
    needs = False
    for asset, target in target_allocation.items():
        current = current_allocation.get(asset, 0)
        drift = abs(current - target)
        if drift > drift_threshold:
            needs = True
            actions.append(
                {
                    "asset": asset,
                    "current_pct": current,
                    "target_pct": target,
                    "drift": drift,
                    "action": "SELL" if current > target else "BUY",
                    "action_amount_pct": drift,
                }
            )
    return {"needs_rebalancing": needs, "actions": actions}
