"""Collects recent app reviews from Apple's public customer reviews feed."""

import logging

import requests

from src import config
from src.models import Post

logger = logging.getLogger(__name__)

SEARCH_URL = "https://itunes.apple.com/search"
REVIEWS_URL = "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"


def _find_app_id(term: str, country: str) -> int | None:
    params = {"term": term, "country": country, "entity": "software", "limit": 1}
    response = requests.get(SEARCH_URL, params=params, timeout=config.REQUEST_TIMEOUT)
    response.raise_for_status()
    results = response.json().get("results", [])
    return results[0]["trackId"] if results else None


def fetch_app_store_reviews(term: str = config.APP_STORE_TERM, country: str = "gb") -> list[Post]:
    """Return the most recent reviews for the first app matching the search term."""
    try:
        app_id = _find_app_id(term, country)
        if app_id is None:
            logger.warning("No App Store app found for %r", term)
            return []
        response = requests.get(
            REVIEWS_URL.format(country=country, app_id=app_id), timeout=config.REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.warning("App Store request failed: %s", error)
        return []

    entries = response.json()["feed"].get("entry", [])
    # The feed returns a single object instead of a list when there is only one review
    if isinstance(entries, dict):
        entries = [entries]

    app_url = f"https://apps.apple.com/{country}/app/id{app_id}"
    return [
        Post(
            source="app_store",
            post_id=entry["id"]["label"],
            url=app_url,
            text=f"{entry['title']['label']}. {entry['content']['label']}",
            created_at=entry["updated"]["label"],
            metadata={"rating": int(entry["im:rating"]["label"])},
        )
        for entry in entries[: config.MAX_ITEMS_PER_SOURCE]
    ]