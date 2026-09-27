"""Price data fetching (Yahoo Finance via yfinance - free, no API key)."""
import logging

import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl_requests

from .certs import build_bundle

log = logging.getLogger(__name__)
_session = None


def session():
    """Shared HTTP session that trusts the Windows certificate store (see certs.py)."""
    global _session
    if _session is None:
        _session = curl_requests.Session(impersonate="chrome", verify=build_bundle())
    return _session


def fetch_history(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    # 2 years so the 200-day average is fully formed across every chart window.
    """Download daily OHLCV for many tickers in one request.

    Returns {ticker: DataFrame[Open, High, Low, Close, Volume]}; tickers that
    failed or returned too little data are skipped.
    """
    raw = yf.download(
        tickers,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
        session=session(),
    )
    out = {}
    for t in tickers:
        try:
            df = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            log.warning("No data returned for %s", t)
            continue
        df = df.dropna(subset=["Close"])
        if len(df) < 60:
            log.warning("Too little history for %s (%d rows)", t, len(df))
            continue
        out[t] = df
    return out
