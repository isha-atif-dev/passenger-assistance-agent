"""Loads the response guidelines and looks up extra facts from official sources when needed."""

import logging

import requests
from langfuse import observe

from src import config

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.tavily.com/search"
GUIDELINES_FILE = config.INPUTS_DIR / "response_guidelines.md"
OFFICIAL_DOMAINS = ["nationalrail.co.uk", "orr.gov.uk", "passengerassistance.com", "gov.uk"]
MAX_SNIPPET_LENGTH = 600


def load_guidelines() -> str:
    return GUIDELINES_FILE.read_text(encoding="utf-8")


@observe(as_type="tool", name="context_lookup")
def lookup_context(query: str) -> str:
    """Search official sites only and return short snippets with their sources."""
    body = {"query": query, "max_results": 2, "include_domains": OFFICIAL_DOMAINS}
    headers = {"Authorization": f"Bearer {config.TAVILY_API_KEY}"}
    try:
        response = requests.post(SEARCH_URL, headers=headers, json=body, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as error:
        logger.warning("Context lookup failed for %r: %s", query, error)
        return ""

    return "\n".join(
        f"- {result.get('content', '')[:MAX_SNIPPET_LENGTH]} (source: {result['url']})"
        for result in response.json().get("results", [])
    )