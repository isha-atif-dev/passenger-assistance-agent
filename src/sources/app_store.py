"""Collects recent app reviews from Apple's public customer reviews feed."""

import json
import logging
from dataclasses import asdict

import requests

from src import config
from src.models import Post

logger = logging.getLogger(__name__)

REVIEWS_URL = "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy={sort}/json"
# The most recent feed is occasionally empty, so the most helpful feed is tried next
SORT_ORDERS = ("mostRecent", "mostHelpful")
CACHE_FILE = config.OUTPUTS_DIR / "app_store_cache.json"


def _fetch_entries(app_id: int, country: str, sort: str) -> list[dict]:
    response = requests.get(
        REVIEWS_URL.format(country=country, app_id=app_id, sort=sort), timeout=config.REQUEST_TIMEOUT
    )
    response.raise_for_status()
    entries = response.json().get("feed", {}).get("entry", [])
    # The feed returns a single object instead of a list when there is only one review
    return [entries] if isinstance(entries, dict) else entries


def _to_post(entry: dict, app_url: str) -> Post:
    return Post(
        source="app_store",
        post_id=entry["id"]["label"],
        url=app_url,
        text=f"{entry['title']['label']}. {entry['content']['label']}",
        created_at=entry["updated"]["label"],
        metadata={"rating": int(entry["im:rating"]["label"])},
    )


def _load_cache() -> list[Post]:
    if not CACHE_FILE.exists():
        return []
    logger.warning("Using App Store reviews from the last successful fetch")
    return [Post(**item) for item in json.loads(CACHE_FILE.read_text(encoding="utf-8"))]


def _save_cache(posts: list[Post]) -> None:
    config.OUTPUTS_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps([asdict(post) for post in posts], ensure_ascii=False), encoding="utf-8")


def fetch_app_store_reviews(app_id: int = config.APP_STORE_APP_ID, country: str = "gb") -> list[Post]:
    """Return recent reviews for the app. Falls back to the last successful fetch if the feed is empty."""
    entries = []
    for sort in SORT_ORDERS:
        try:
            entries = _fetch_entries(app_id, country, sort)
        except (requests.RequestException, ValueError) as error:
            logger.warning("App Store %s feed failed: %s", sort, error)
            continue
        if entries:
            break
        logger.warning("App Store %s feed returned no reviews", sort)

    app_url = f"https://apps.apple.com/{country}/app/id{app_id}"
    posts = [_to_post(entry, app_url) for entry in entries[: config.MAX_ITEMS_PER_SOURCE]]
    if posts:
        _save_cache(posts)
        return posts
    return _load_cache()