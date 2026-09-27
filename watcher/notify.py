"""Discord webhook notifications."""
import json
import logging
import os

import requests

log = logging.getLogger(__name__)
MAX_LEN = 1900  # Discord hard limit is 2000 chars per message


def webhook_url() -> str:
    return os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def _annotate(level: str, msg: str):
    """On GitHub Actions, surface a message as a notice/warning/error on the run's summary page."""
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::{level}::{msg}", flush=True)


def send_discord(lines: list[str], header: str = "") -> bool:
    """Post lines to Discord, splitting into several messages if needed."""
    url = webhook_url()
    if not url:
        log.info("DISCORD_WEBHOOK_URL not set - skipping Discord (%d lines)", len(lines))
        _annotate("warning", "DISCORD_WEBHOOK_URL secret is not set - no Discord message sent")
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
            if not r.ok:
                # Only the status code: error text from requests would include the webhook URL.
                log.error("Discord send failed: HTTP %s", r.status_code)
                _annotate("error", f"Discord rejected the message (HTTP {r.status_code}) - check the webhook secret")
                ok = False
        except requests.RequestException as e:
            log.error("Discord send failed: %s", type(e).__name__)
            _annotate("error", f"Could not reach Discord ({type(e).__name__})")
            ok = False
    if ok:
        _annotate("notice", f"Sent {len(chunks)} Discord message(s)")
    return ok


def send_discord_images(text: str, images: list[tuple[str, bytes]]) -> bool:
    """Post a message with PNG attachments (Discord shows them inline, max 10 per message)."""
    url = webhook_url()
    if not url:
        return send_discord([text])  # logs + annotates the missing secret
    if len(text) > MAX_LEN:
        if not send_discord(text.split("\n")):
            return False
        text = ""
    files = {f"files[{i}]": (name, data, "image/png") for i, (name, data) in enumerate(images[:10])}
    try:
        r = requests.post(url, data={"payload_json": json.dumps({"content": text, "username": "Stock Watcher"})},
                          files=files, timeout=60)
    except requests.RequestException as e:
        log.error("Discord send failed: %s", type(e).__name__)
        _annotate("error", f"Could not reach Discord ({type(e).__name__})")
        return False
    if not r.ok:
        log.error("Discord send failed: HTTP %s", r.status_code)
        _annotate("error", f"Discord rejected the summary (HTTP {r.status_code})")
        return False
    _annotate("notice", f"Sent daily summary with {len(files)} chart(s)")
    return True
