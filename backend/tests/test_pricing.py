from datetime import date

import pytest

from app.services.marketdata import mutual_fund, pricing, stock


def test_mutual_fund_is_priced_from_its_latest_nav(monkeypatch):
    monkeypatch.setattr(
        mutual_fund,
        "get_latest_nav",
        lambda code: mutual_fund.NavPoint(date=date(2026, 7, 17), nav=91.46),
    )
    assert pricing.get_current_price("MF", "122639") == pytest.approx(91.46)


def test_stock_is_priced_from_its_quote(monkeypatch):
    monkeypatch.setattr(stock, "get_stock_price", lambda ticker: 1323.1)
    assert pricing.get_current_price("STOCK", "RELIANCE.NS") == pytest.approx(1323.1)


def test_unknown_asset_type_is_rejected():
    with pytest.raises(ValueError, match="Unsupported asset type"):
        pricing.get_current_price("CRYPTO", "BTC")
