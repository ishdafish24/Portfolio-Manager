from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .http import HttpError, get_json


POSITIVE_WORDS = {
    "beat", "beats", "bull", "bullish", "buy", "growth", "guidance", "upgrade",
    "strong", "record", "surge", "profit", "outperform", "raised",
}
NEGATIVE_WORDS = {
    "miss", "misses", "bear", "bearish", "sell", "lawsuit", "probe", "downgrade",
    "weak", "fall", "drop", "loss", "underperform", "cut",
}


@dataclass(frozen=True)
class NewsItem:
    headline: str
    source: str
    url: str
    published_at: str


@dataclass(frozen=True)
class EarningsItem:
    symbol: str
    date: str
    hour: str
    estimate: str


@dataclass(frozen=True)
class XSummary:
    symbol: str
    post_count: int
    positive_hits: int
    negative_hits: int
    sample_posts: list[str]

    @property
    def tone(self) -> str:
        if self.positive_hits > self.negative_hits * 1.4:
            return "leans positive"
        if self.negative_hits > self.positive_hits * 1.4:
            return "leans negative"
        return "mixed/neutral"


class FinnhubClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def company_news(self, symbol: str, days: int = 3, limit: int = 3) -> list[NewsItem]:
        if not self.enabled or not symbol:
            return []
        end = date.today()
        start = end - timedelta(days=days)
        try:
            rows = get_json(
                "https://finnhub.io/api/v1/company-news",
                params={"symbol": symbol, "from": start.isoformat(), "to": end.isoformat(), "token": self.api_key},
            )
        except HttpError:
            return []
        items = []
        for row in (rows or [])[:limit]:
            items.append(
                NewsItem(
                    headline=str(row.get("headline") or ""),
                    source=str(row.get("source") or ""),
                    url=str(row.get("url") or ""),
                    published_at=str(row.get("datetime") or ""),
                )
            )
        return items

    def earnings(self, symbols: list[str], days_ahead: int = 14) -> list[EarningsItem]:
        if not self.enabled or not symbols:
            return []
        end = date.today() + timedelta(days=days_ahead)
        try:
            data = get_json(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={"from": date.today().isoformat(), "to": end.isoformat(), "token": self.api_key},
            )
        except HttpError:
            return []
        wanted = {symbol.upper() for symbol in symbols}
        events = []
        for row in (data or {}).get("earningsCalendar", []):
            symbol = str(row.get("symbol") or "").upper()
            if symbol in wanted:
                events.append(
                    EarningsItem(
                        symbol=symbol,
                        date=str(row.get("date") or ""),
                        hour=str(row.get("hour") or ""),
                        estimate=str(row.get("epsEstimate") or ""),
                    )
                )
        return sorted(events, key=lambda item: item.date)


class XClient:
    def __init__(self, bearer_token: str, posts_per_symbol: int):
        self.bearer_token = bearer_token
        self.posts_per_symbol = posts_per_symbol

    @property
    def enabled(self) -> bool:
        return bool(self.bearer_token)

    def summarize_symbol(self, symbol: str, company_name: str = "") -> XSummary:
        if not self.enabled or not symbol:
            return XSummary(symbol=symbol, post_count=0, positive_hits=0, negative_hits=0, sample_posts=[])
        query_parts = [f"${symbol}", symbol]
        if company_name:
            query_parts.append(f'"{company_name}"')
        query = f"({' OR '.join(query_parts)}) lang:en -is:retweet"
        try:
            data = get_json(
                "https://api.x.com/2/tweets/search/recent",
                headers={"Authorization": f"Bearer {self.bearer_token}"},
                params={
                    "query": query,
                    "max_results": max(10, min(self.posts_per_symbol, 100)),
                    "tweet.fields": "created_at,public_metrics",
                },
            )
        except HttpError:
            return XSummary(symbol=symbol, post_count=0, positive_hits=0, negative_hits=0, sample_posts=[])
        posts = [str(row.get("text") or "") for row in (data or {}).get("data", [])]
        positive = sum(count_hits(text, POSITIVE_WORDS) for text in posts)
        negative = sum(count_hits(text, NEGATIVE_WORDS) for text in posts)
        return XSummary(symbol=symbol, post_count=len(posts), positive_hits=positive, negative_hits=negative, sample_posts=posts[:3])


def count_hits(text: str, words: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for word in words if word in lowered)

