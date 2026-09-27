"""Stock Watcher: background market scanner + web dashboard.

Run with start.bat (visible window) or autostart-on.bat (hidden, at every login),
then open http://127.0.0.1:5000
"""
import hmac
import logging
import os
import socket
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory

from watcher import notify, scanner, store
from watcher.certs import build_bundle

ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "data" / "watcher.log"
LOG_FILE.parent.mkdir(exist_ok=True)

handlers = [RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")]
if sys.stdout is None:
    # pythonw.exe (hidden mode) has no console; discard stray prints instead of crashing.
    sys.stdout = sys.stderr = open(os.devnull, "w")
else:
    handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)
sys.excepthook = lambda *exc: logging.critical("Crashed", exc_info=exc)
threading.excepthook = lambda a: logging.error("Thread %s crashed", a.thread.name,
                                               exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("werkzeug").setLevel(logging.WARNING)  # don't log every dashboard request

load_dotenv(ROOT / ".env")
build_bundle()  # must run before any HTTPS request (antivirus TLS scanning fix)

CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
# The server overrides these in its own .env (e.g. WATCHER_HOST=0.0.0.0).
CFG["host"] = os.getenv("WATCHER_HOST", CFG["host"])
CFG["port"] = int(os.getenv("WATCHER_PORT", CFG["port"]))
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

app = Flask(__name__, static_folder=None)


@app.before_request
def require_password():
    """Optional login (any username + DASHBOARD_PASSWORD) for when the dashboard is reachable remotely."""
    if not DASHBOARD_PASSWORD:
        return None
    auth = request.authorization
    if auth and hmac.compare_digest(auth.password or "", DASHBOARD_PASSWORD):
        return None
    return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Stock Watcher"'})


@app.get("/")
def index():
    return send_from_directory(ROOT / "web", "index.html")


@app.get("/api/assets")
def assets():
    return jsonify(store.load_assets())


@app.get("/api/alerts")
def alerts():
    return jsonify(store.recent_alerts())


@app.get("/api/status")
def status():
    return jsonify({
        "last_scan": store.get_meta("last_scan"),
        "interval_minutes": CFG["scan_interval_minutes"],
        "discord_configured": bool(notify.webhook_url()),
        "markets": list(CFG["watchlist"]),
    })


@app.post("/api/scan")
def scan_now():
    threading.Thread(target=scanner.run_scan, args=(CFG,), daemon=True).start()
    return jsonify({"status": "started"})


@app.post("/api/test-discord")
def test_discord():
    ok = notify.send_discord(["✅ Test message from Stock Watcher — alerts are working."])
    return jsonify({"ok": ok})


def already_running(host, port) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1" if host == "0.0.0.0" else host, port)) == 0


if __name__ == "__main__":
    if already_running(CFG["host"], CFG["port"]):
        # Autostart and start.bat can both fire; only one copy may scan, or alerts double up.
        logging.info("Stock Watcher is already running on port %s - exiting this copy", CFG["port"])
        print(f"\n  Already running - open http://{CFG['host']}:{CFG['port']}\n")
        sys.exit(0)
    logging.info("Stock Watcher starting")
    store.init()
    scanner.start_background(CFG)
    print(f"\n  Dashboard: http://{CFG['host']}:{CFG['port']}\n")
    app.run(host=CFG["host"], port=CFG["port"], debug=False, use_reloader=False)
