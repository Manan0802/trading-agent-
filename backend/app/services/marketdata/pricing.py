"""Single entry point for "what is this worth right now", whatever it is.

Portfolio valuation should not care whether a holding is a mutual fund or a
listed stock, so the asset-type dispatch lives here rather than in the
valuation logic.
"""

from app.services.marketdata import mutual_fund, stock


def get_current_price(asset_type: str, identifier: str) -> float:
    """Latest price per unit. Raises if the instrument cannot be priced."""
    if asset_type == "MF":
        return mutual_fund.get_latest_nav(identifier).nav
    if asset_type == "STOCK":
        return stock.get_stock_price(identifier)
    raise ValueError(f"Unsupported asset type: {asset_type}")
