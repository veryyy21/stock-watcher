"""Discord webhook notifications."""
import logging
import os

import requests

log = logging.getLogger(__name__)
MAX_LEN = 1900  # Discord hard limit is 2000 chars per message


def webhook_url() -> str:
    return os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def send_discord(lines: list[str], header: str = "") -> bool:
    """Post lines to Discord, splitting into several messages if needed."""
    url = webhook_url()
    if not url:
        log.info("DISCORD_WEBHOOK_URL not set - skipping Discord (%d lines)", len(lines))
        return False
    chunks, cur = [], header
    for line in lines:
        if len(cur) + len(line) + 1 > MAX_LEN:
            chunks.append(cur)
            cur = ""
        cur += ("\n" if cur else "") + line
    if cur:
        chunks.append(cur)
    ok = True
    for chunk in chunks:
        try:
            r = requests.post(url, json={"content": chunk, "username": "Stock Watcher"}, timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            log.error("Discord send failed: %s", e)
            ok = False
    return ok
