# Trading 212 Daily Reporter

Daily portfolio reporter for a Trading 212 Invest account. It records positions and account value in SQLite, compares today against prior snapshots, enriches holdings with optional news, earnings, and X conversation signals, then emails a concise daily report.

## What It Does

- Pulls account summary and open positions from the Trading 212 API.
- Stores every run in `portfolio_snapshots.sqlite3`.
- Calculates account value change, position value change, unrealized P/L, allocation, and biggest movers.
- Adds optional company news and earnings calendar items with Finnhub.
- Adds optional X recent-search conversation summaries when an X API bearer token is available.
- Sends the report by SMTP, or prints it to the terminal if email is not configured.

This app is for monitoring and personal reporting only. It does not place trades and does not provide financial advice.

## Setup

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Copy the environment template:

```bash
cp .env.example .env
```

3. Fill in `.env`:

- `T212_ENV`: `demo` while testing, `live` when ready.
- `T212_API_KEY` and, if your account uses key-pair auth, `T212_API_SECRET`.
- `FINNHUB_API_KEY` for news and earnings.
- `X_BEARER_TOKEN` for X recent-search summaries.
- SMTP values if you want email delivery.

4. Run a dry test:

```bash
python3 -m portfolio_daily_reporter.main --dry-run
```

To preview the report without any API keys:

```bash
python3 -m portfolio_daily_reporter.main --sample-data --dry-run
```

5. Run and send:

```bash
python3 -m portfolio_daily_reporter.main
```

## Daily Scheduling On macOS

The most macOS-native option is `launchd`. Create this file:

`~/Library/LaunchAgents/com.ishaan.portfolio-reporter.plist`

Example for a daily 4:00 AM email:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.ishaan.portfolio-reporter</string>

  <key>WorkingDirectory</key>
  <string>/Users/ishaan/Documents/New project</string>

  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/python3</string>
    <string>-m</string>
    <string>portfolio_daily_reporter.main</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>/Users/ishaan/Documents/New project</string>
  </dict>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>4</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/Users/ishaan/Documents/New project/reporter.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/ishaan/Documents/New project/reporter.err.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.ishaan.portfolio-reporter.plist
```

Run it immediately for a test:

```bash
launchctl start com.ishaan.portfolio-reporter
```

Unload it if you want to pause the daily email:

```bash
launchctl unload ~/Library/LaunchAgents/com.ishaan.portfolio-reporter.plist
```

Cron also works if you prefer it.

Open your crontab:

```bash
crontab -e
```

Add a daily run, for example 4:00 AM:

```cron
30 7 * * * cd "/Users/ishaan/Documents/New project" && /usr/bin/python3 -m portfolio_daily_reporter.main >> reporter.log 2>&1
```

Cron has a small environment, so keep credentials in `.env` in this project folder.

## API Notes

- Trading 212’s public API is in beta and supports Invest and Stocks ISA account types. This project reads account summary and positions only.
- X search uses the recent search endpoint, which covers recent posts and depends on your X developer access.
- Finnhub is optional. Without it, the report still tracks portfolio movement from Trading 212 data.

## Good Next Features

- Push notifications via Telegram, Slack, or iMessage.
- A small dashboard for charts and historical account value.
- Risk flags for oversized positions, earnings within 7 days, and unusually high X/news volume.
- CSV/PDF report export.
- Tax-lot and dividend tracking using Trading 212 history endpoints.
