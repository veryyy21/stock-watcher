"""SQLite persistence: latest snapshot, per-asset tags, and alert history."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "watcher.db"
_lock = threading.Lock()


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS assets (
                ticker TEXT PRIMARY KEY,
                market TEXT,
                tags TEXT,
                metrics TEXT,
                updated TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                ticker TEXT,
                market TEXT,
                event TEXT,
                message TEXT,
                bar_date TEXT,
                UNIQUE(ticker, event, bar_date)
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        """)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def previous_tags() -> dict[str, list[str]]:
    with _lock, _conn() as c:
        return {r["ticker"]: json.loads(r["tags"]) for r in c.execute("SELECT ticker, tags FROM assets")}


def save_assets(rows: list[dict]):
    with _lock, _conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO assets VALUES (?,?,?,?,?)",
            [(r["ticker"], r["market"], json.dumps(r["tags"]), json.dumps(r), now()) for r in rows],
        )


def load_assets() -> list[dict]:
    with _lock, _conn() as c:
        return [json.loads(r["metrics"]) for r in c.execute("SELECT metrics FROM assets")]


def record_alert(ticker, market, event, message, bar_date) -> bool:
    """Store an alert. Returns False if this exact alert was already sent for that bar (dedupe)."""
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO alerts (ts, ticker, market, event, message, bar_date) VALUES (?,?,?,?,?,?)",
            (now(), ticker, market, event, message, bar_date),
        )
        return cur.rowcount == 1


def recent_alerts(limit=200) -> list[dict]:
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))]


def set_meta(key, value):
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))


def get_meta(key, default=None):
    with _lock, _conn() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default
