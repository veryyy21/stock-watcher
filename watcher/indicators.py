"""Technical indicators computed from a daily price series."""
import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index (0-100). <30 oversold, >70 overbought."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def macd_hist(close: pd.Series) -> pd.Series:
    """MACD histogram (12/26/9). Rising histogram = downward momentum fading."""
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    return macd - macd.ewm(span=9, adjust=False).mean()


def max_drawdown(close: pd.Series) -> float:
    """Worst peak-to-trough fall over the series, as a negative fraction."""
    return float((close / close.cummax() - 1).min())


def compute(df: pd.DataFrame) -> dict:
    """Snapshot of every metric the analyser needs, for the latest bar and the one before."""
    close = df["Close"]
    r = rsi(close)
    mh = macd_hist(close)
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200, min_periods=150).mean()
    rets = np.log(close).diff().dropna()
    daily_std = float(rets.tail(60).std())

    def pct(n):
        return float(close.iloc[-1] / close.iloc[-1 - n] - 1) if len(close) > n else None

    last = float(close.iloc[-1])
    high_52w = float(close.tail(252).max())
    low_52w = float(close.tail(252).min())
    return {
        "price": last,
        "date": close.index[-1].strftime("%Y-%m-%d"),
        "chg_1d": pct(1),
        "chg_5d": pct(5),
        "chg_1m": pct(21),
        "chg_3m": pct(63),
        "high_52w": high_52w,
        "low_52w": low_52w,
        "drawdown": last / high_52w - 1,
        "max_drawdown_1y": max_drawdown(close.tail(252)),
        "volatility": daily_std * np.sqrt(252),
        "daily_std": daily_std,
        "rsi": float(r.iloc[-1]),
        "rsi_prev": float(r.iloc[-2]),
        "rsi_3ago": float(r.iloc[-4]),
        "macd_hist": float(mh.iloc[-1]),
        "macd_hist_prev": float(mh.iloc[-2]),
        "sma50": _f(sma50.iloc[-1]),
        "sma200": _f(sma200.iloc[-1]),
        "sma50_prev": _f(sma50.iloc[-2]),
        "sma200_prev": _f(sma200.iloc[-2]),
        "spark": [round(float(x), 4) for x in close.tail(90)],
    }


def _f(x):
    return None if pd.isna(x) else float(x)
