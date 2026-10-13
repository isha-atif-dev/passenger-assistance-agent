"""Finds forum threads, articles and reviews on the wider web through the Tavily search API."""

import logging

import requests

from src import config
from src.models import Post

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.tavily.com/search"
RESULTS_PER_QUERY = 5


def fetch_web_results(queries: list[str] = config.WEB_QUERIES) -> list[Post]:
    """Return web pages matching any of the queries, without duplicate URLs."""
    headers = {"Authorization": f"Bearer {config.TAVILY_API_KEY}"}
    posts: dict[str, Post] = {}

    for query in queries:
        body = {"query": query, "max_results": RESULTS_PER_QUERY, "time_range": "year"}
        try:
            response = requests.post(SEARCH_URL, headers=headers, json=body, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("Web search failed for %r: %s", query, error)
            continue

        for result in response.json().get("results", []):
            url = result["url"]
            if url in posts:
                continue
            posts[url] = Post(
                source="web",
                post_id=url,
                url=url,
                text=f"{result.get('title', '')}. {result.get('content', '')}",
                created_at=result.get("published_date", ""),
            )

    return list(posts.values())