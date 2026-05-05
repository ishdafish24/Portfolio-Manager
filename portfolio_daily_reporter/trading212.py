from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .http import get_json


@dataclass(frozen=True)
class Position:
    ticker: str
    symbol: str
    name: str
    quantity: float
    average_price: float
    current_price: float
    value: float
    unrealized_pnl: float
    currency: str
    price_currency: str = ""


class Trading212Client:
    def __init__(self, settings: Settings):
        if not settings.t212_api_key:
            raise ValueError("T212_API_KEY is required")
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        if self.settings.t212_api_secret:
            token = f"{self.settings.t212_api_key}:{self.settings.t212_api_secret}"
            encoded = base64.b64encode(token.encode("utf-8")).decode("ascii")
            return {"Authorization": f"Basic {encoded}"}
        return {"Authorization": self.settings.t212_api_key}

    def account_summary(self) -> dict[str, Any]:
        return get_json(f"{self.settings.t212_base_url}/equity/account/summary", headers=self._headers())

    def positions(self) -> list[Position]:
        data = get_json(f"{self.settings.t212_base_url}/equity/positions", headers=self._headers())
        return [self._parse_position(item) for item in data or []]

    def _parse_position(self, item: dict[str, Any]) -> Position:
        instrument = item.get("instrument") or {}
        ticker = str(instrument.get("ticker") or item.get("ticker") or "")
        symbol = simplify_t212_ticker(ticker)
        name = str(instrument.get("name") or instrument.get("shortName") or symbol or ticker)
        quantity = number(item.get("quantity"))
        average_price = number(item.get("averagePricePaid") or item.get("averagePrice"))
        current_price = number(item.get("currentPrice"))
        wallet = item.get("walletImpact") or {}
        value = number(wallet.get("currentValue"))
        if value == 0 and quantity and current_price:
            value = quantity * current_price
        unrealized_pnl = number(
            wallet.get("unrealizedProfitLoss")
            or wallet.get("ppl")
            or wallet.get("unrealizedPnl")
        )
        if unrealized_pnl == 0 and quantity and current_price and average_price:
            unrealized_pnl = (current_price - average_price) * quantity
        value_currency = str(wallet.get("currency") or wallet.get("currencyCode") or "")
        price_currency = str(instrument.get("currency") or instrument.get("currencyCode") or value_currency)
        return Position(
            ticker,
            symbol,
            name,
            quantity,
            average_price,
            current_price,
            value,
            unrealized_pnl,
            value_currency,
            price_currency,
        )


def number(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def simplify_t212_ticker(ticker: str) -> str:
    # Trading 212 tickers commonly look like AAPL_US_EQ.
    if not ticker:
        return ""
    return ticker.split("_", 1)[0].replace("/", ".")
