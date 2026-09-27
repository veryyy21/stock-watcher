"""Daily summary: text + charts sent to Discord at fixed market times.

Called at the end of every scan. A slot fires on the first scan inside its
3-hour window (GitHub's timer can run late) and then never again that day.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import charts, data, notify, store

log = logging.getLogger(__name__)
WINDOW = timedelta(hours=3)


def maybe_send(cfg: dict, rows: list[dict], hist: dict, now: datetime | None = None):
    dcfg = cfg.get("digest", {})
    if not dcfg.get("enabled") or not notify.webhook_url():
        return
    now = now or datetime.now(timezone.utc)
    forced = os.getenv("DIGEST_FORCE", "").strip()  # set by the "Run workflow" button for testing
    forced = "" if forced == "none" else forced

    for slot in dcfg["slots"]:
        local = now.astimezone(ZoneInfo(slot["timezone"]))
        key = f"digest:{slot['name']}:{local.date()}"
        if forced:
            if forced != slot["name"]:
                continue
        else:
            h, m = map(int, slot["at"].split(":"))
            start = local.replace(hour=h, minute=m, second=0, microsecond=0)
            if local.weekday() >= 5 or not (start <= local < start + WINDOW) or store.get_meta(key):
                continue
            # Public holiday: no trading bar for today in this market -> skip quietly.
            if not any(r["market"] == slot["market"] and r["date"] == local.date().isoformat() for r in rows):
                log.info("%s: market closed today, no summary", slot["name"])
                store.set_meta(key, "closed")
                continue
        try:
            # A forced test send doesn't count, so it won't swallow that day's real summary.
            if send(cfg, slot, rows, hist, now) and not forced:
                store.set_meta(key, "sent")
        except Exception:
            log.exception("Daily summary %s failed", slot["name"])


def send(cfg, slot, rows, hist, now) -> bool:
    dcfg = cfg["digest"]
    market = slot["market"]
    mine = now.astimezone(ZoneInfo(dcfg["your_timezone"]))
    market_day = now.astimezone(ZoneInfo(slot["timezone"]))

    bench_hist = data.fetch_history(list(dcfg["benchmarks"].values()))
    bench = {name: bench_hist[t]["Close"] for name, t in dcfg["benchmarks"].items() if t in bench_hist}

    def day_chg(close):
        return close.iloc[-1] / close.iloc[-2] - 1

    reb = sorted((r for r in rows if "rebound" in r["tags"]), key=lambda r: -r["rebound_score"])
    stb = sorted((r for r in rows if "stable" in r["tags"]), key=lambda r: -r["stability_score"])
    fall = sorted((r for r in rows if "downtrend" in r["tags"]), key=lambda r: r["drawdown"])
    in_mkt = sorted((r for r in rows if r["market"] == market and r["chg_1d"] is not None), key=lambda r: r["chg_1d"])
    since = (now - timedelta(hours=24)).isoformat(timespec="seconds")
    n_alerts = sum(1 for a in store.recent_alerts(500) if a["ts"] >= since)

    def arrow(v):
        return f"{'▲' if v >= 0 else '▼'}{abs(v) * 100:.1f}%"

    lines = [
        f"📊 **{slot['name']} summary — {market_day:%a %d %b}**  ·  your time {mine:%a %I:%M %p}",
        "**Markets today:** " + " · ".join(f"{n} {arrow(day_chg(c))}" for n, c in bench.items()),
    ]
    if in_mkt:
        ups = [f"{r['ticker']} {arrow(r['chg_1d'])}" for r in reversed(in_mkt[-3:]) if r["chg_1d"] > 0]
        downs = [f"{r['ticker']} {arrow(r['chg_1d'])}" for r in in_mkt[:3] if r["chg_1d"] < 0]
        lines.append(f"**{market} biggest moves:** " + ", ".join(ups + downs))
    lines.append("🟢 **Rebound candidates:** " + (", ".join(
        f"{r['ticker']} (score {r['rebound_score']}, {abs(r['drawdown']) * 100:.0f}% off high)" for r in reb[:6])
        or "none right now"))
    lines.append("🔵 **Stable:** " + (", ".join(r["ticker"] for r in stb[:8]) or "none right now"))
    lines.append("🔻 **Falling:** " + (", ".join(r["ticker"] for r in fall[:6]) or "none right now"))
    lines.append(f"⚡ **Signals in the last 24h:** {n_alerts}")
    lines.append("-# Technical patterns from Yahoo Finance prices, not financial advice.")

    images = []
    if bench:
        images.append(("markets.png", charts.market_pulse(bench)))
    if in_mkt:
        images.append((f"{market.lower()}-moves.png", charts.movers(rows, market)))
    panels = charts.rebound_panels(reb, hist)
    if panels:
        images.append(("rebound-candidates.png", panels))

    return notify.send_discord_images("\n".join(lines), images)
