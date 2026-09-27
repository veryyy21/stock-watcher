"""PNG charts for the Discord daily summary.

Dark theme to sit naturally in Discord's default dark mode. Colours are the
validated reference palette (dark steps): the first three categorical slots are
safe together for colour-blind readers, and up/down use the blue<->red diverging
pair (never green vs red, the classic colour-blind trap). Every coloured mark also
carries a text label, so colour is never the only cue.
"""
import io

import matplotlib

matplotlib.use("Agg")  # no screen needed (GitHub Actions)
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

BG = "#1a1a19"
INK = "#ffffff"
INK2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
SERIES = ["#3987e5", "#d95926", "#199e70"]  # blue, orange, aqua
UP, DOWN = "#3987e5", "#e66767"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.facecolor": BG,
    "figure.facecolor": BG,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.titlecolor": INK,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
})


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return buf.getvalue()


def _date_axis(ax):
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator())
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)


def market_pulse(series: dict[str, pd.Series], days: int = 92) -> bytes:
    """Benchmarks over the last ~3 months, each indexed to 100 so they share one axis."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ends = []
    for (name, close), color in zip(series.items(), SERIES):
        s = close[close.index >= close.index[-1] - pd.Timedelta(days=days)]
        s = s / s.iloc[0] * 100
        ax.plot(s.index, s.values, color=color, linewidth=2, label=name, solid_capstyle="round")
        ax.scatter([s.index[-1]], [s.iloc[-1]], color=color, s=36, zorder=3, edgecolors=BG, linewidths=2)
        ends.append([s.iloc[-1], s.index[-1], f"{name} {s.iloc[-1] - 100:+.1f}%"])
    ax.axhline(100, color=AXIS, linewidth=1)

    # Direct labels at the line ends, nudged apart so they never overlap.
    ends.sort()
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.07
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
    for y_label, x, text in ends:
        ax.annotate(text, (x, y_label), xytext=(10, 0), textcoords="offset points",
                    va="center", color=INK2, fontsize=10.5)
    ax.set_xlim(right=ax.get_xlim()[1] + (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.22)

    ax.set_title("Markets, last 3 months  (start = 100)", pad=12)
    ax.legend(loc="upper left", frameon=False, labelcolor=INK2, ncols=len(series), fontsize=10)
    _date_axis(ax)
    return _png(fig)


def movers(rows: list[dict], market: str) -> bytes:
    """Today's % move for every watched asset in one market, sorted."""
    rows = sorted((r for r in rows if r["market"] == market and r["chg_1d"] is not None),
                  key=lambda r: r["chg_1d"])
    vals = [r["chg_1d"] * 100 for r in rows]
    names = [r["ticker"].replace(".AX", "") for r in rows]
    fig, ax = plt.subplots(figsize=(8, 0.9 + 0.3 * len(rows)))
    ax.barh(names, vals, height=0.62, color=[UP if v >= 0 else DOWN for v in vals])
    ax.axvline(0, color=AXIS, linewidth=1)
    span = max(abs(v) for v in vals) if vals else 1
    for i, v in enumerate(vals):
        ax.text(v + (span * 0.02 if v >= 0 else -span * 0.02), i,
                f"{'▲' if v >= 0 else '▼'} {abs(v):.1f}%", va="center",
                ha="left" if v >= 0 else "right", color=INK2, fontsize=9.5)
    ax.set_axisbelow(True)
    ax.set_xlim(-span * 1.35, span * 1.35)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:+.0f}%"))
    ax.grid(axis="y", visible=False)
    ax.tick_params(length=0)
    ax.tick_params(axis="y", colors=INK2)
    ax.set_title(f"{market}: today's moves", pad=12)
    return _png(fig)


def rebound_panels(cands: list[dict], hist: dict[str, pd.DataFrame], limit: int = 6) -> bytes | None:
    """Small multiples: 6-month price for each top rebound candidate vs its 200-day average and 52w high."""
    cands = cands[:limit]
    if not cands:
        return None
    cols = 2 if len(cands) > 1 else 1
    nrows = -(-len(cands) // cols)
    fig, axes = plt.subplots(nrows, cols, figsize=(8, 2.5 * nrows + 0.6), squeeze=False)
    for ax, r in zip(axes.flat, cands):
        close = hist[r["ticker"]]["Close"]
        sma200 = close.rolling(200, min_periods=150).mean()
        window = close.index >= close.index[-1] - pd.Timedelta(days=183)
        ax.plot(close.index[window], close[window], color=SERIES[0], linewidth=1.8, label="Price")
        ax.plot(sma200.index[window], sma200[window], color=MUTED, linewidth=1.2,
                linestyle=(0, (4, 3)), label="200-day average")
        ax.axhline(r["high_52w"], color=INK2, linewidth=0.8, linestyle=":", label="52-week high")
        ax.set_title(f"{r['ticker']}   score {r['rebound_score']}   {abs(r['drawdown'])*100:.0f}% below high",
                     fontsize=10.5, pad=6)
        _date_axis(ax)
        ax.tick_params(labelsize=8.5)
    for ax in list(axes.flat)[len(cands):]:
        ax.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncols=3, frameon=False, labelcolor=INK2, fontsize=9.5,
               bbox_to_anchor=(1, 1.0))
    fig.suptitle("Rebound candidates, last 6 months", x=0.01, ha="left", color=INK,
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _png(fig)
