"""One full market scan: fetch -> analyse -> detect changes -> alert."""
import logging
import threading
import time

from . import analysis, data, indicators, notify, store

log = logging.getLogger(__name__)

TAG_EVENTS = {"rebound": "entered_rebound", "stable": "entered_stable"}
TAG_TEXT = {
    "rebound": "Now a REBOUND candidate: {dd:.0f}% below 52w high, RSI {rsi:.0f}, still above 200-day avg (score {score})",
    "stable": "Now in the STABLE bucket: low volatility, max 1y drawdown {mdd:.0f}% (score {sscore})",
}
EMOJI = {
    "entered_rebound": "🟢", "entered_stable": "🔵", "rsi_oversold": "🟠", "rsi_recovery": "🟢",
    "golden_cross": "✨", "death_cross": "🔻", "big_move": "⚡",
}
_scan_lock = threading.Lock()


def run_scan(cfg: dict) -> dict:
    if not _scan_lock.acquire(blocking=False):
        return {"status": "busy"}
    try:
        return _scan(cfg)
    finally:
        _scan_lock.release()


def _scan(cfg: dict) -> dict:
    started = time.time()
    market_of = {t: m for m, ts in cfg["watchlist"].items() for t in ts}
    hist = data.fetch_history(list(market_of))

    rows = []
    for t, df in hist.items():
        try:
            m = indicators.compute(df)
        except Exception:
            log.exception("Indicator calc failed for %s", t)
            continue
        m.update(ticker=t, market=market_of[t])
        rows.append(m)

    # Volatility percentile is relative to the asset's own market (crypto vs crypto, etc).
    for market in cfg["watchlist"]:
        group = sorted((r for r in rows if r["market"] == market), key=lambda r: r["volatility"])
        for i, r in enumerate(group):
            r["vol_pct"] = 100 * i / max(1, len(group) - 1)

    for r in rows:
        analysis.enrich(r)
        r["tags"] = analysis.classify(r, cfg["rules"])

    if not rows:
        result = {"status": "error", "assets": 0, "missing": sorted(market_of), "new_alerts": 0,
                  "seconds": round(time.time() - started, 1), "finished": store.now()}
        store.set_meta("last_scan", result)
        log.error("Scan got no data at all - check internet connection")
        return result

    prev = store.previous_tags()
    first_run = not prev
    enabled = cfg["alerts"]["enabled"]
    new_alerts = []

    for r in rows:
        events = analysis.bar_events(r, cfg["alerts"]["big_move_sigma"])
        if not first_run:
            for tag, ev in TAG_EVENTS.items():
                if tag in r["tags"] and tag not in prev.get(r["ticker"], []):
                    events.append((ev, TAG_TEXT[tag].format(
                        dd=r["drawdown"] * 100, rsi=r["rsi"], score=r["rebound_score"],
                        mdd=r["max_drawdown_1y"] * 100, sscore=r["stability_score"])))
        for ev, msg in events:
            if enabled.get(ev, True) and store.record_alert(r["ticker"], r["market"], ev, msg, r["date"]):
                new_alerts.append((r, ev, msg))

    store.save_assets(rows)

    # Welcome summary goes out once, the first time Discord is actually reachable.
    if not store.get_meta("welcome_sent") and _send_first_run_summary(rows):
        store.set_meta("welcome_sent", True)
    if new_alerts:
        lines = [f"{EMOJI.get(ev, '•')} **{r['ticker']}** ({r['market']}) {r['price']:,.2f} — {msg}"
                 for r, ev, msg in new_alerts]
        notify.send_discord(lines, header=f"**Stock Watcher — {len(new_alerts)} new signal(s)**")

    result = {
        "status": "ok",
        "assets": len(rows),
        "missing": sorted(set(market_of) - set(hist)),
        "new_alerts": len(new_alerts),
        "seconds": round(time.time() - started, 1),
        "finished": store.now(),
    }
    store.set_meta("last_scan", result)
    log.info("Scan done: %s", result)
    return result


def _send_first_run_summary(rows):
    reb = sorted((r for r in rows if "rebound" in r["tags"]), key=lambda r: -r["rebound_score"])
    stb = sorted((r for r in rows if "stable" in r["tags"]), key=lambda r: -r["stability_score"])
    lines = ["**Stock Watcher is live.** Watching %d assets. From now on you'll get a ping when something changes." % len(rows)]
    lines.append("\n__Rebound candidates__")
    lines += [f"🟢 {r['ticker']} — {r['drawdown']*100:.0f}% off high, RSI {r['rsi']:.0f}, score {r['rebound_score']}"
              for r in reb[:10]] or ["(none right now)"]
    lines.append("\n__Stable__")
    lines += [f"🔵 {r['ticker']} — vol {r['volatility']*100:.0f}%, score {r['stability_score']}" for r in stb[:10]] or ["(none right now)"]
    return notify.send_discord(lines)


def start_background(cfg: dict):
    """Scan now, then every scan_interval_minutes, forever (daemon thread)."""
    interval = cfg["scan_interval_minutes"] * 60

    def loop():
        while True:
            try:
                run_scan(cfg)
            except Exception:
                log.exception("Scan failed")
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="scanner").start()
