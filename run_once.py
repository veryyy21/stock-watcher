"""Run a single market scan and exit (used by GitHub Actions every 15 minutes).

State (previous buckets, alerts already sent) lives in data/watcher.db, which the
workflow carries from one run to the next using the Actions cache.
"""
import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from watcher import scanner, store
from watcher.certs import build_bundle

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
build_bundle()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("yfinance").setLevel(logging.ERROR)

cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
store.init()
result = scanner.run_scan(cfg)
sys.exit(0 if result["status"] == "ok" else 1)
