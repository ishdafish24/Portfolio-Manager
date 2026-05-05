from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    t212_env: str
    t212_api_key: str
    t212_api_secret: str
    db_path: Path
    finnhub_api_key: str
    x_bearer_token: str
    x_posts_per_symbol: int
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    smtp_to: str
    smtp_use_tls: bool
    report_top_movers: int
    currency_symbol: str

    @property
    def t212_base_url(self) -> str:
        env = self.t212_env.lower()
        if env == "live":
            return "https://live.trading212.com/api/v0"
        if env == "demo":
            return "https://demo.trading212.com/api/v0"
        raise ValueError("T212_ENV must be 'demo' or 'live'")

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_to)


def get_settings(cwd: Path | None = None) -> Settings:
    base = cwd or Path.cwd()
    load_dotenv(base / ".env")
    return Settings(
        t212_env=os.getenv("T212_ENV", "demo"),
        t212_api_key=os.getenv("T212_API_KEY", ""),
        t212_api_secret=os.getenv("T212_API_SECRET", ""),
        db_path=base / os.getenv("REPORT_DB_PATH", "portfolio_snapshots.sqlite3"),
        finnhub_api_key=os.getenv("FINNHUB_API_KEY", ""),
        x_bearer_token=os.getenv("X_BEARER_TOKEN", ""),
        x_posts_per_symbol=int(os.getenv("X_POSTS_PER_SYMBOL", "25")),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", ""),
        smtp_to=os.getenv("SMTP_TO", ""),
        smtp_use_tls=_bool("SMTP_USE_TLS", True),
        report_top_movers=int(os.getenv("REPORT_TOP_MOVERS", "8")),
        currency_symbol=os.getenv("REPORT_CURRENCY_SYMBOL", "$"),
    )

