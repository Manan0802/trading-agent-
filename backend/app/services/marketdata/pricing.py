"""Single entry point for "what is this worth right now", whatever it is.

Portfolio valuation should not care whether a holding is a mutual fund or a
listed stock, so the asset-type dispatch lives here rather than in the
valuation logic.
"""

from datetime import date

from app.services.marketdata import mutual_fund, stock


def get_current_price(asset_type: str, identifier: str) -> float:
    """Latest price per unit. Raises if the instrument cannot be priced."""
    if asset_type == "MF":
        return mutual_fund.get_latest_nav(identifier).nav
    if asset_type == "STOCK":
        return stock.get_stock_price(identifier)
    raise ValueError(f"Unsupported asset type: {asset_type}")


def price_as_of(asset_type: str, identifier: str) -> date | None:
    """The date the price above is actually from.

    `get_current_price` returns the last NAV in the series, whenever that was.
    Normally that is yesterday, because NAVs publish around 11 PM IST. But if a
    scheme merges, winds up, or simply drops out of the feed, the series stops
    and the last NAV is returned forever -- so a portfolio keeps showing a value
    as though it were current, with nothing anywhere saying otherwise.

    That is the failure this exists to make visible. It is deliberately a
    separate call rather than a change to the price contract: valuation stays
    pure arithmetic over a price, and the lookup is cached, so asking twice
    costs nothing.

    Returns None for stocks. yfinance does not hand back a trade date with the
    price, and inventing one would be worse than admitting we do not have it.
    """
    if asset_type != "MF":
        return None
    try:
        return mutual_fund.get_latest_nav(identifier).date
    except Exception:  # noqa: BLE001 - an unpriceable holding is already flagged
        return None
