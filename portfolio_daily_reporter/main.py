from __future__ import annotations

import argparse
from datetime import datetime
import sys

from .config import get_settings
from .emailer import send_email
from .enrichers import FinnhubClient, XClient
from .report import build_position_changes, extract_account_value, extract_cash, render_report
from .storage import SnapshotStore
from .trading212 import Trading212Client


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a daily Trading 212 portfolio report.")
    parser.add_argument("--dry-run", action="store_true", help="Print the report and do not send email.")
    parser.add_argument("--no-save", action="store_true", help="Do not store this run as a historical snapshot.")
    parser.add_argument("--sample-data", action="store_true", help="Render a sample report without calling external APIs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    settings = get_settings()

    store = SnapshotStore(settings.db_path)
    previous_snapshot = store.comparison_snapshot()
    previous_positions = store.comparison_positions_by_symbol(previous_snapshot)

    if args.sample_data:
        account_summary, positions = sample_portfolio()
    else:
        try:
            client = Trading212Client(settings)
            account_summary = client.account_summary()
            positions = client.positions()
        except Exception as exc:
            print(f"Could not load Trading 212 data: {exc}", file=sys.stderr)
            print("Check .env for T212_ENV, T212_API_KEY, and optional T212_API_SECRET.", file=sys.stderr)
            return 2
    account_value = extract_account_value(account_summary, positions)
    cash = extract_cash(account_summary)
    position_changes = build_position_changes(positions, previous_positions)

    symbols = [position.symbol for position in positions if position.symbol]
    finnhub = FinnhubClient(settings.finnhub_api_key)
    x_client = XClient(settings.x_bearer_token, settings.x_posts_per_symbol)

    if args.sample_data:
        earnings, news, x_summaries = sample_enrichment()
    else:
        earnings = finnhub.earnings(symbols)
        news = {symbol: finnhub.company_news(symbol) for symbol in symbols}
        x_summaries = {
            position.symbol: x_client.summarize_symbol(position.symbol, position.name)
            for position in positions
            if position.symbol
        }

    report = render_report(
        positions=positions,
        account_summary=account_summary,
        previous_snapshot=previous_snapshot,
        position_changes=position_changes,
        news=news,
        earnings=earnings,
        x_summaries=x_summaries,
        currency_symbol=settings.currency_symbol,
        top_movers=settings.report_top_movers,
    )

    if not args.no_save and not args.sample_data:
        store.save(positions, account_summary, account_value, cash)

    subject = f"Trading 212 Daily Report - {datetime.now().strftime('%Y-%m-%d')}"
    if args.dry_run or not settings.email_enabled:
        print(report)
        if not settings.email_enabled and not args.dry_run:
            print("\nEmail is not configured, so the report was printed instead.")
        return 0

    send_email(settings, subject, report)
    print(f"Sent report to {settings.smtp_to}")
    return 0


def sample_portfolio():
    from .trading212 import Position

    account_summary = {"accountValue": 24350.25, "cash": 1310.50}
    positions = [
        Position("AAPL_US_EQ", "AAPL", "Apple", 20, 175.20, 188.44, 3768.80, 264.80, "USD"),
        Position("MSFT_US_EQ", "MSFT", "Microsoft", 12, 407.50, 421.90, 5062.80, 172.80, "USD"),
        Position("NVDA_US_EQ", "NVDA", "NVIDIA", 35, 91.30, 103.70, 3629.50, 434.00, "USD"),
    ]
    return account_summary, positions


def sample_enrichment():
    from .enrichers import EarningsItem, NewsItem, XSummary

    earnings = [EarningsItem("NVDA", "2026-05-20", "amc", "0.86")]
    news = {
        "AAPL": [NewsItem("Apple supplier commentary points to steady iPhone demand", "Sample News", "https://example.com/aapl", "")],
        "MSFT": [NewsItem("Microsoft cloud growth remains a focus before earnings", "Sample News", "https://example.com/msft", "")],
        "NVDA": [NewsItem("AI chip demand keeps NVIDIA in focus", "Sample News", "https://example.com/nvda", "")],
    }
    x_summaries = {
        "AAPL": XSummary("AAPL", 18, 5, 3, ["$AAPL traders are watching services growth and China demand."]),
        "MSFT": XSummary("MSFT", 14, 6, 1, ["$MSFT chatter is focused on Azure and AI copilots."]),
        "NVDA": XSummary("NVDA", 32, 11, 4, ["$NVDA discussion is hot around data center demand and earnings."]),
    }
    return earnings, news, x_summaries


if __name__ == "__main__":
    raise SystemExit(main())
