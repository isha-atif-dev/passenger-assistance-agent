"""Searches public Bluesky posts using an authenticated app password session."""

import logging

import requests

from src import config
from src.models import Post

logger = logging.getLogger(__name__)

LOGIN_URL = "https://bsky.social/xrpc/com.atproto.server.createSession"
SEARCH_URL = "https://bsky.social/xrpc/app.bsky.feed.searchPosts"


def _login() -> str:
    credentials = {"identifier": config.BLUESKY_HANDLE, "password": config.BLUESKY_APP_PASSWORD}
    response = requests.post(LOGIN_URL, json=credentials, timeout=config.REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()["accessJwt"]


def _to_web_url(uri: str) -> str:
    # at://<did>/app.bsky.feed.post/<rkey> becomes https://bsky.app/profile/<did>/post/<rkey>
    did, _, rkey = uri.removeprefix("at://").split("/")
    return f"https://bsky.app/profile/{did}/post/{rkey}"


def fetch_bluesky_posts(queries: list[str] = config.BLUESKY_QUERIES) -> list[Post]:
    """Return recent English posts matching any of the queries, without duplicates."""
    try:
        headers = {"Authorization": f"Bearer {_login()}"}
    except requests.RequestException as error:
        logger.warning("Bluesky login failed: %s", error)
        return []

    posts: dict[str, Post] = {}
    for query in queries:
        params = {"q": query, "lang": "en", "sort": "latest", "limit": config.BLUESKY_RESULTS_PER_QUERY}
        try:
            response = requests.get(
                SEARCH_URL, headers=headers, params=params, timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("Bluesky search failed for %r: %s", query, error)
            continue

        for item in response.json().get("posts", []):
            uri = item["uri"]
            if uri in posts:
                continue
            record = item.get("record", {})
            posts[uri] = Post(
                source="bluesky",
                post_id=uri,
                url=_to_web_url(uri),
                text=record.get("text", ""),
                created_at=record.get("createdAt", ""),
            )

    return list(posts.values())