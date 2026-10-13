"""Remembers which posts have already been handled, so each post is processed once."""

import json
from datetime import datetime, timezone

from src import config

STATE_FILE = config.OUTPUTS_DIR / "processed_posts.json"
# Pending posts were never drafted, so they are picked up again on the next run
RETRY_ACTIONS = {"pending"}


def load() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save(processed: dict) -> None:
    config.OUTPUTS_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(processed, indent=2), encoding="utf-8")


def is_done(processed: dict, post_id: str) -> bool:
    entry = processed.get(post_id)
    return entry is not None and entry["action"] not in RETRY_ACTIONS


def record(processed: dict, items: list[dict]) -> dict:
    """Add this run's outcomes to the history and return it."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for item in items:
        processed[item["post"].post_id] = {"action": item["action"], "processed_at": now}
    return processed