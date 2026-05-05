from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .enrichers import EarningsItem, NewsItem, XSummary
from .trading212 import Position, number


@dataclass(frozen=True)
class PositionChange:
    position: Position
    value_change: float
    value_change_pct: float
    price_change: float
    price_change_pct: float


def extract_cash(summary: dict[str, Any]) -> float:
    for key in ("cash", "free", "totalCash", "availableCash", "blocked"):
        if key in summary and key != "blocked":
            return number(summary.get(key))
    return 0.0


def extract_account_value(summary: dict[str, Any], positions: list[Position]) -> float:
    for key in ("accountValue", "totalValue", "portfolioValue", "equity"):
        value = number(summary.get(key))
        if value:
            return value
    return sum(position.value for position in positions) + extract_cash(summary)


def build_position_changes(positions: list[Position], previous: dict[str, Any]) -> list[PositionChange]:
    changes = []
    for position in positions:
        prior = previous.get(position.symbol)
        prior_value = number(prior["value"]) if prior else 0.0
        prior_price = number(prior["current_price"]) if prior else 0.0
        value_change = position.value - prior_value if prior else 0.0
        price_change = position.current_price - prior_price if prior else 0.0
        changes.append(
            PositionChange(
                position=position,
                value_change=value_change,
                value_change_pct=percent_change(position.value, prior_value),
                price_change=price_change,
                price_change_pct=percent_change(position.current_price, prior_price),
            )
        )
    return changes


def render_report(
    positions: list[Position],
    account_summary: dict[str, Any],
    previous_snapshot: Any,
    position_changes: list[PositionChange],
    news: dict[str, list[NewsItem]],
    earnings: list[EarningsItem],
    x_summaries: dict[str, XSummary],
    currency_symbol: str,
    top_movers: int,
) -> str:
    account_value = extract_account_value(account_summary, positions)
    cash = extract_cash(account_summary)
    previous_value = number(previous_snapshot["account_value"]) if previous_snapshot else 0.0
    daily_change = account_value - previous_value if previous_snapshot else 0.0
    daily_change_pct = percent_change(account_value, previous_value)
    total_unrealized = sum(position.unrealized_pnl for position in positions)
    movers = sorted(position_changes, key=lambda item: abs(item.value_change), reverse=True)[:top_movers]

    lines = [
        f"# Daily Portfolio Report - {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Account",
        f"- Account value: {money(account_value, currency_symbol)} ({signed_money(daily_change, currency_symbol)} / {signed_pct(daily_change_pct)} vs previous snapshot)",
        f"- Cash: {money(cash, currency_symbol)}",
        f"- Invested value: {money(sum(position.value for position in positions), currency_symbol)}",
        f"- Unrealized P/L: {signed_money(total_unrealized, currency_symbol)}",
        f"- Open positions: {len(positions)}",
        "",
        "## Biggest Movers",
    ]
    if movers:
        for change in movers:
            p = change.position
            lines.append(
                f"- {p.symbol} ({p.name}): value {signed_money(change.value_change, currency_symbol)} "
                f"({signed_pct(change.value_change_pct)}), price {signed_money(change.price_change, currency_symbol)} "
                f"({signed_pct(change.price_change_pct)}), current value {money(p.value, currency_symbol)}"
            )
    else:
        lines.append("- No previous snapshot yet. Tomorrow's report will show daily movers.")

    lines.extend(["", "## Positions"])
    for position in sorted(positions, key=lambda p: p.value, reverse=True):
        allocation = (position.value / account_value * 100) if account_value else 0
        lines.append(
            f"- {position.symbol}: {money(position.value, currency_symbol)} ({allocation:.1f}% allocation), "
            f"{position.quantity:g} shares, avg {money(position.average_price, currency_symbol)}, "
            f"current {money(position.current_price, currency_symbol)}, P/L {signed_money(position.unrealized_pnl, currency_symbol)}"
        )

    lines.extend(["", "## Upcoming Earnings"])
    if earnings:
        for item in earnings:
            estimate = f", EPS est. {item.estimate}" if item.estimate else ""
            hour = f" ({item.hour})" if item.hour else ""
            lines.append(f"- {item.symbol}: {item.date}{hour}{estimate}")
    else:
        lines.append("- No upcoming earnings found, or earnings provider is not configured.")

    lines.extend(["", "## News"])
    any_news = False
    for symbol, items in news.items():
        if not items:
            continue
        any_news = True
        lines.append(f"- {symbol}:")
        for item in items:
            source = f" - {item.source}" if item.source else ""
            lines.append(f"  - {item.headline}{source} ({item.url})")
    if not any_news:
        lines.append("- No recent headlines found, or news provider is not configured.")

    lines.extend(["", "## X Conversation"])
    any_x = False
    for symbol, summary in x_summaries.items():
        if summary.post_count == 0:
            continue
        any_x = True
        lines.append(
            f"- {symbol}: {summary.post_count} recent posts, tone {summary.tone} "
            f"(positive hits {summary.positive_hits}, negative hits {summary.negative_hits})"
        )
        for post in summary.sample_posts[:2]:
            lines.append(f"  - {clean_post(post)}")
    if not any_x:
        lines.append("- No X summary available, or X API access is not configured.")

    lines.extend(
        [
            "",
            "## Watchlist Flags",
            *watchlist_flags(positions, account_value, position_changes, earnings, x_summaries, currency_symbol),
            "",
            "_Monitoring report only. Not financial advice._",
        ]
    )
    return "\n".join(lines)


def watchlist_flags(
    positions: list[Position],
    account_value: float,
    changes: list[PositionChange],
    earnings: list[EarningsItem],
    x_summaries: dict[str, XSummary],
    currency_symbol: str,
) -> list[str]:
    flags = []
    for position in positions:
        allocation = (position.value / account_value * 100) if account_value else 0
        if allocation >= 25:
            flags.append(f"- Concentration: {position.symbol} is {allocation:.1f}% of account value.")
    for change in changes:
        if abs(change.price_change_pct) >= 5:
            flags.append(f"- Price move: {change.position.symbol} moved {signed_pct(change.price_change_pct)} since the previous snapshot.")
        if abs(change.value_change) >= 500:
            flags.append(f"- Value move: {change.position.symbol} changed by {signed_money(change.value_change, currency_symbol)} since the previous snapshot.")
    for item in earnings:
        flags.append(f"- Earnings soon: {item.symbol} reports on {item.date}.")
    for symbol, summary in x_summaries.items():
        if summary.post_count >= 20 and summary.tone != "mixed/neutral":
            flags.append(f"- X chatter: {symbol} has {summary.post_count} recent posts and sentiment {summary.tone}.")
    return flags or ["- No major flags based on current thresholds."]


def percent_change(current: float, previous: float) -> float:
    if not previous:
        return 0.0
    return ((current - previous) / abs(previous)) * 100


def money(value: float, currency_symbol: str) -> str:
    return f"{currency_symbol}{value:,.2f}"


def signed_money(value: float, currency_symbol: str) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{currency_symbol}{abs(value):,.2f}"


def signed_pct(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{abs(value):.2f}%"


def clean_post(text: str) -> str:
    return " ".join(text.split())[:240]

