from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from .trading212 import Position


class SnapshotStore:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                account_value REAL NOT NULL,
                cash REAL NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                snapshot_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                average_price REAL NOT NULL,
                current_price REAL NOT NULL,
                value REAL NOT NULL,
                unrealized_pnl REAL NOT NULL,
                currency TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def previous_snapshot(self) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM snapshots ORDER BY captured_at DESC LIMIT 1").fetchone()

    def previous_positions_by_symbol(self) -> dict[str, sqlite3.Row]:
        row = self.previous_snapshot()
        if not row:
            return {}
        rows = self.conn.execute("SELECT * FROM positions WHERE snapshot_id = ?", (row["id"],)).fetchall()
        return {str(item["symbol"]): item for item in rows}

    def save(self, positions: list[Position], account_summary: dict[str, Any], account_value: float, cash: float) -> int:
        captured_at = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "INSERT INTO snapshots (captured_at, account_value, cash, payload_json) VALUES (?, ?, ?, ?)",
            (captured_at, account_value, cash, json.dumps(account_summary, sort_keys=True)),
        )
        snapshot_id = int(cursor.lastrowid)
        self.conn.executemany(
            """
            INSERT INTO positions (
                snapshot_id, ticker, symbol, name, quantity, average_price, current_price,
                value, unrealized_pnl, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot_id,
                    p.ticker,
                    p.symbol,
                    p.name,
                    p.quantity,
                    p.average_price,
                    p.current_price,
                    p.value,
                    p.unrealized_pnl,
                    p.currency,
                )
                for p in positions
            ],
        )
        self.conn.commit()
        return snapshot_id

