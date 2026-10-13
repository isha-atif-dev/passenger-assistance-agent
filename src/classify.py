"""Cheap pre-filtering and LLM labelling of collected posts."""

import json
import logging
from datetime import datetime, timedelta, timezone
from langfuse import observe
from src.llm import ask_json
from src.models import Post

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
MAX_TEXT_LENGTH = 800
MIN_TEXT_LENGTH = 40
MAX_AGE_DAYS = 180
ASSISTANCE_TERMS = (
    "assist", "wheelchair", "ramp", "disab", "accessib", "mobility",
    "turn up and go", "help to board", "booked help",
)

PROMPT = """You review public posts for a UK rail passenger assistance team.
Label every post and return JSON with exactly this shape:
{{"results": [{{"id": "...", "relevant": true, "passenger_voice": true, "category": "...",
"sentiment": "...", "urgency": "...", "operator": "", "needs_context": false, "context_query": "",
"reason": "..."}}]}}

Field rules:
- relevant: the post is about assistance for disabled or less mobile passengers on rail journeys
  in Great Britain, or about the Passenger Assistance app. Journeys entirely outside the UK are not relevant.
- passenger_voice: written by a passenger, or someone travelling with them, about their own experience.
  False for news, reports, adverts, policy pages and posts by operators.
- category: one of "assistance_no_show", "booking_problem", "app_problem", "staff_conduct",
  "accessibility_barrier", "praise", "question", "other".
- sentiment: "negative", "neutral" or "positive".
- urgency: "high" only if someone is stranded, unsafe, or their assistance is failing right now.
  "medium" for a recent failure or a problem with a journey in the next few days. "low" otherwise.
  Simply planning to travel soon is not high urgency.
- operator: the UK train operator named in the post, such as "Avanti West Coast", or "" if none.
- needs_context: true if a good reply depends on facts that are not in the post.
- context_query: a short web search query for those facts, or "" when needs_context is false.
- reason: one short sentence explaining the labels, based only on what the post says.

Posts:
{posts}
"""


def _is_recent(created_at: str) -> bool:
    # Posts without a readable date are kept rather than silently dropped
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return True
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created <= timedelta(days=MAX_AGE_DAYS)


def _mentions_assistance(post: Post) -> bool:
    # App reviews are always about the assistance app, so they skip the term check
    return post.source == "app_store" or any(term in post.text.lower() for term in ASSISTANCE_TERMS)


def pre_filter(posts: list[Post]) -> list[Post]:
    """Free checks before any LLM call: on topic, long enough to act on, and recent."""
    return [
        post for post in posts
        if _mentions_assistance(post)
        and len(post.text) >= MIN_TEXT_LENGTH
        and _is_recent(post.created_at)
    ]

@observe(name="classify")
def classify(posts: list[Post]) -> dict[str, dict]:
    """Return labels keyed by post_id. Posts the model fails to label are left out."""
    labels = {}
    for start in range(0, len(posts), BATCH_SIZE):
        batch = {str(index): post for index, post in enumerate(posts[start : start + BATCH_SIZE])}
        items = [
            {"id": key, "source": post.source, "text": post.text[:MAX_TEXT_LENGTH]}
            for key, post in batch.items()
        ]
        try:
            reply = ask_json(PROMPT.format(posts=json.dumps(items, ensure_ascii=False)))
        except RuntimeError as error:
            logger.warning("Classification failed for a batch: %s", error)
            continue

        # Models occasionally return the list itself instead of wrapping it in "results"
        results = reply.get("results", []) if isinstance(reply, dict) else reply
        for result in results:
            if not isinstance(result, dict):
                continue
            post = batch.get(str(result.get("id")))
            if post:
                labels[post.post_id] = result
    return labels