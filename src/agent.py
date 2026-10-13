"""Runs the full pipeline: collect, filter, judge, gather context, decide and draft."""

import logging

from langfuse import get_client, observe

from src import state
from src.classify import classify, pre_filter
from src.context import load_guidelines, lookup_context
from src.models import Post
from src.respond import context_query, decide, draft_reply
from src.sources.app_store import fetch_app_store_reviews
from src.sources.bluesky import fetch_bluesky_posts
from src.sources.web_search import fetch_web_results
from src.sources.youtube import fetch_youtube_comments

logger = logging.getLogger(__name__)

SOURCES = {
    "app_store": fetch_app_store_reviews,
    "bluesky": fetch_bluesky_posts,
    "web": fetch_web_results,
    "youtube": fetch_youtube_comments,
}
REPLY_ACTIONS = {"draft", "escalate"}
MAX_DRAFTS = 12
MAX_CONTEXT_LOOKUPS = 4
URGENCY_ORDER = {"high": 0, "medium": 1, "low": 2}
SENTIMENT_ORDER = {"negative": 0, "neutral": 1, "positive": 2}


def collect() -> list[Post]:
    posts = []
    for name, fetch in SOURCES.items():
        found = fetch()
        logger.info("Collected %d posts from %s", len(found), name)
        posts.extend(found)
    return posts


def _priority(item: dict) -> tuple:
    label = item["label"]
    return URGENCY_ORDER.get(label.get("urgency"), 3), SENTIMENT_ORDER.get(label.get("sentiment"), 3)


@observe(as_type="agent", name="passenger_assistance_run", capture_output=False)
def _run(use_history: bool) -> dict:
    posts = collect()
    candidates = pre_filter(posts)
    logger.info("%d of %d posts passed the pre-filter", len(candidates), len(posts))

    processed = state.load()
    new_posts = [
        post for post in candidates
        if not (use_history and state.is_done(processed, post.post_id))
    ]
    logger.info("%d new posts to judge, %d already handled", len(new_posts), len(candidates) - len(new_posts))

    labels = classify(new_posts)
    items = [
        {"post": post, "label": labels[post.post_id], "action": decide(labels[post.post_id], post)}
        for post in new_posts
        if post.post_id in labels
    ]

    # Most urgent and most negative posts are answered first
    queue = sorted((item for item in items if item["action"] in REPLY_ACTIONS), key=_priority)
    guidelines = load_guidelines()
    lookups = 0

    for position, item in enumerate(queue[:MAX_DRAFTS], start=1):
        context = ""
        query = context_query(item["label"])
        if query and lookups < MAX_CONTEXT_LOOKUPS:
            logger.info("Looking up context: %s", query)
            context = lookup_context(query)
            lookups += 1
        logger.info("Drafting reply %d of %d", position, min(len(queue), MAX_DRAFTS))
        item["context"] = context
        item["draft"] = draft_reply(item["post"], item["label"], guidelines, context)
        if not item["draft"].get("reply") and item["action"] == "draft":
            # A failed draft goes back in the queue instead of being marked as handled
            item["action"] = "pending"

    for item in queue[MAX_DRAFTS:]:
        item["action"] = "pending"

    state.save(state.record(processed, items))

    stats = {
        "collected": len(posts),
        "removed_by_pre_filter": len(posts) - len(candidates),
        "already_handled": len(candidates) - len(new_posts),
        "labelled": len(items),
        "context_lookups": lookups,
    }
    for item in items:
        stats[item["action"]] = stats.get(item["action"], 0) + 1
    get_client().update_current_span(output=stats)
    return {"stats": stats, "items": items}


def run(use_history: bool = True) -> dict:
    """Run one pass of the agent and return run statistics plus every labelled item.

    With use_history, posts handled in earlier runs are not judged again.
    """
    try:
        return _run(use_history)
    finally:
        # Send the trace before a short-lived process exits
        get_client().flush()