from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HoldingCreate(BaseModel):
    name: str
    asset_type: Literal["MF", "STOCK"]
    # AMFI scheme code for a fund, yfinance ticker (e.g. RELIANCE.NS) for a stock.
    identifier: str
    category: str | None = None


class TransactionCreate(BaseModel):
    txn_date: date
    txn_type: Literal["BUY", "SELL"]
    units: float = Field(gt=0)
    price: float = Field(gt=0)


class TransactionOut(BaseModel):
    id: str
    txn_date: date
    txn_type: str
    units: float
    price: float
    amount: float

    model_config = ConfigDict(from_attributes=True)


class HoldingOut(BaseModel):
    id: str
    name: str
    asset_type: str
    identifier: str
    category: str | None
    transactions: list[TransactionOut]

    model_config = ConfigDict(from_attributes=True)


class HoldingSummaryOut(BaseModel):
    holding_id: str
    name: str
    asset_type: str
    identifier: str
    category: str | None
    units_held: float
    invested: float
    current_price: float | None
    current_value: float | None
    unrealised_gain: float | None
    realised_gain: float
    absolute_return: float | None
    xirr: float | None
    price_error: str | None

    # Reads the valuation dataclass directly, computed properties included.
    model_config = ConfigDict(from_attributes=True)


class PortfolioSummaryOut(BaseModel):
    holdings: list[HoldingSummaryOut]
    total_invested: float
    total_current_value: float
    total_unrealised_gain: float
    total_realised_gain: float
    absolute_return: float
    xirr: float | None
    unpriced_invested: float
    has_pricing_errors: bool

    model_config = ConfigDict(from_attributes=True)
