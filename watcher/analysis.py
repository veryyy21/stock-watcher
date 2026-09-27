"""Turns raw indicator snapshots into buckets, scores and alert events.

These are rule-of-thumb technical signals, not predictions. A high rebound
score means "has the typical shape of a dip that often recovers", nothing more.
"""


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def rebound_score(m: dict) -> int:
    """0-100 heuristic: how much this looks like a dip inside a healthy uptrend."""
    oversold = clamp((45 - m["rsi"]) / 25) * 35           # RSI 45 -> 0pts, RSI 20 -> 35pts
    dip = clamp(-m["drawdown"] / 0.25) * 25                # 25%+ below 52w high -> 25pts
    trend = 0
    if m["sma200"] and m["price"] > m["sma200"]:
        trend = 20 if m["sma50"] and m["sma50"] > m["sma200"] else 12
    turning = 10 * m["bounce_rsi"] + 10 * m["bounce_macd"]  # momentum starting to turn up
    return round(oversold + dip + trend + turning)


def stability_score(m: dict) -> int:
    """0-100: calm price action, shallow drawdowns, above its long-term average."""
    calm = (1 - m["vol_pct"] / 100) * 50
    shallow = clamp(1 + m["max_drawdown_1y"] / 0.4) * 30   # 0% dd -> 30pts, 40%+ dd -> 0
    trend = 20 if m["sma200"] and m["price"] > m["sma200"] else 0
    return round(calm + shallow + trend)


def classify(m: dict, rules: dict) -> list[str]:
    """Tags for one asset. `m` must already include vol_pct (volatility percentile within its market)."""
    tags = []
    above200 = bool(m["sma200"]) and m["price"] > m["sma200"]

    rb = rules["rebound"]
    if (m["drawdown"] <= -rb["min_drawdown_pct"] / 100
            and m["rsi"] <= rb["max_rsi"]
            and (above200 or not rb["require_above_sma200"])):
        tags.append("rebound")

    st = rules["stable"]
    if (m["vol_pct"] <= st["max_volatility_percentile"]
            and m["max_drawdown_1y"] >= -st["max_1y_drawdown_pct"] / 100
            and (above200 or not st["require_above_sma200"])):
        tags.append("stable")

    # Falling hard AND below its long-term average: the classic "falling knife".
    if m["sma200"] and not above200 and m["drawdown"] <= -0.20 and m["chg_1m"] is not None and m["chg_1m"] < 0:
        tags.append("downtrend")
    return tags


def enrich(m: dict) -> dict:
    m["bounce_rsi"] = m["rsi"] > m["rsi_3ago"] and m["rsi"] < 50
    m["bounce_macd"] = m["macd_hist"] < 0 and m["macd_hist"] > m["macd_hist_prev"]
    m["rebound_score"] = rebound_score(m)
    m["stability_score"] = stability_score(m)
    return m


def bar_events(m: dict, big_move_sigma: float) -> list[tuple[str, str]]:
    """Events visible from the last two daily bars. Returns [(event, human text)]."""
    ev = []
    if m["rsi_prev"] >= 30 > m["rsi"]:
        ev.append(("rsi_oversold", f"RSI dropped below 30 ({m['rsi']:.0f}) - oversold"))
    if m["rsi_prev"] < 30 <= m["rsi"]:
        ev.append(("rsi_recovery", f"RSI climbed back above 30 ({m['rsi']:.0f}) - possible bounce starting"))
    if all(m[k] for k in ("sma50", "sma200", "sma50_prev", "sma200_prev")):
        if m["sma50_prev"] <= m["sma200_prev"] and m["sma50"] > m["sma200"]:
            ev.append(("golden_cross", "Golden cross: 50-day average moved above 200-day (bullish trend signal)"))
        if m["sma50_prev"] >= m["sma200_prev"] and m["sma50"] < m["sma200"]:
            ev.append(("death_cross", "Death cross: 50-day average fell below 200-day (bearish trend signal)"))
    if m["chg_1d"] is not None and m["daily_std"] > 0 and abs(m["chg_1d"]) > big_move_sigma * m["daily_std"]:
        word = "jumped" if m["chg_1d"] > 0 else "fell"
        ev.append(("big_move", f"Unusual move: {word} {m['chg_1d']*100:+.1f}% today "
                               f"({abs(m['chg_1d'])/m['daily_std']:.1f}x a normal day)"))
    return ev
