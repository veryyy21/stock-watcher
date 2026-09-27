# Stock Watcher

Scans US stocks, ASX stocks and crypto every 15 minutes, sorts them into
**Rebound candidates**, **Stable**, and **Falling**, and pings Discord when
something changes.

## Run it

| | |
|---|---|
| `autostart-on.bat` | Runs hidden in the background at every login, auto-restarts if it stops (checks every 15 min). **Normal way to run it.** Run it again to restart after editing `.env` or `config.yaml`. |
| `autostart-off.bat` | Removes autostart and stops the watcher. |
| `start.bat` | Runs in a visible window (for debugging). Exits if already running. |

Dashboard: http://127.0.0.1:5000 · Log: `data\watcher.log`

Status / stop without removing autostart:
`powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1 -Status` (or `-Stop`)

It only runs while the laptop is on and awake, with the external drive plugged in.
If the drive is plugged in after login, it picks up within 15 minutes.

## 24/7 alerts (GitHub Actions, free)

`.github/workflows/scan.yml` runs `run_once.py` on GitHub's servers every 15 minutes
and sends Discord alerts, even when the laptop is off. The Discord webhook is stored
as the repository secret `DISCORD_WEBHOOK_URL` (Settings → Secrets and variables →
Actions), never in the code. State between runs is kept in the Actions cache.

- Push changes (e.g. after editing `config.yaml`): `push.bat`
- See runs / trigger a scan manually: the repo's **Actions** tab → Market scan → Run workflow

GitHub cron can start a few minutes late at busy times; that's normal.
The laptop copy has Discord turned off (blank webhook in `.env`) so alerts aren't doubled;
its dashboard still works when the laptop is on.

## Discord alerts (one-time setup)

1. In Discord: Server Settings → Integrations → Webhooks → New Webhook → pick a channel → **Copy Webhook URL**
2. Copy `.env.example` to `.env` and paste the URL after `DISCORD_WEBHOOK_URL=`
3. Restart `start.bat`, then click **Test Discord** on the dashboard.

## What the buckets mean

| Bucket | Rule (editable in `config.yaml`) |
|---|---|
| Rebound candidate | ≥10% below 52-week high, RSI ≤ 40, still above 200-day average |
| Stable | Calmest 35% of its market, worst 1-year drop ≤ 20%, above 200-day average |
| Falling | ≥20% below high, below 200-day average, down over the last month |

## Daily summary (with charts)

On trading days Discord gets a summary with three charts: the S&P 500, ASX 200 and
Bitcoin over 3 months, today's moves for that market, and 6-month price charts of the
top rebound candidates.

| Summary | Market time | Melbourne time |
|---|---|---|
| ASX open | 10:20 Sydney | 10:20 am Mon–Fri |
| US close | 16:20 New York | about 6–7 am Tue–Sat (shifts with daylight saving) |

Skipped on weekends and market holidays. Times, benchmarks and your time zone are
in `config.yaml` under `digest:`. To preview one now: GitHub → Actions → Market scan →
**Run workflow** → pick a summary → Run.

## Alerts sent

Entered rebound / stable bucket · RSI crossed below 30 · RSI recovered above 30 ·
golden cross · death cross · unusually large daily move. Each alert fires once per
asset per trading day.

## Layout

```
app.py              web server + starts the background scanner (laptop)
run_once.py         single scan, used by GitHub Actions
config.yaml         watchlist, rules, alert switches
watcher/data.py     Yahoo Finance download
watcher/indicators.py  RSI, MACD, moving averages, volatility, drawdown
watcher/analysis.py    buckets, scores, alert events
watcher/scanner.py     scan loop + change detection
watcher/notify.py      Discord
watcher/store.py       SQLite (data/watcher.db)
web/index.html         dashboard
python/             local Python 3.12 install
.venv/              project libraries
tools/git/          portable Git (for push.bat)
```

Signals are technical rules of thumb, not forecasts or financial advice.
