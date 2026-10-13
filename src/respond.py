"""Decides what to do with each labelled post and drafts replies for human review."""

import logging
from datetime import datetime, timezone

from langfuse import observe

from src.llm import ask_json
from src.models import Post

logger = logging.getLogger(__name__)

FAILURE_CATEGORIES = {"assistance_no_show", "accessibility_barrier", "booking_problem", "staff_conduct"}
OFFICIAL_MARKERS = (".gov.uk", ".pdf")
ESCALATION_WINDOW_HOURS = 24
# Model-suggested lookups are only trusted for direct questions the guidelines may not answer
MODEL_LOOKUP_CATEGORIES = {"question"}

PROMPT = """You draft public replies for a UK rail passenger assistance team.
A human will review every draft before anything is posted.

Guidelines:
{guidelines}

Extra context from official sources (may be empty):
{context}

Post from {source}:
{text}

Labels from an automatic classifier (category: {category}, sentiment: {sentiment}, urgency: {urgency}).
These labels are hints and can be wrong. Base the reply only on what the post itself says.
Do not say that something happened to the person unless the post says so, and do not add details
such as dates, times or places that the post does not mention. If the person is commenting in general
rather than describing their own experience, acknowledge their point instead of apologising for a failure.

Write a reply that follows the guidelines, including the rules for the {source} channel,
and only uses facts from the guidelines or the extra context.
Return JSON with exactly this shape:
{{"reply": "...", "confidence": "high", "reviewer_note": "..."}}
- confidence: "high", "medium" or "low" depending on how sure you are the reply is accurate and appropriate.
- reviewer_note: one sentence on anything the reviewer should check before sending.
"""


def _is_official_page(url: str) -> bool:
    return any(marker in url.lower() for marker in OFFICIAL_MARKERS)


def _is_live(post: Post) -> bool:
    """True if the post is recent enough that the person may still need help now."""
    try:
        created = datetime.fromisoformat(post.created_at)
    except ValueError:
        # Unknown age is treated as live, so a possible emergency is never downgraded
        return True
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    hours_old = (datetime.now(timezone.utc) - created).total_seconds() / 3600
    return hours_old <= ESCALATION_WINDOW_HOURS


def decide(label: dict, post: Post) -> str:
    """Rule-based action: skip, lead, escalate or draft."""
    if not label.get("relevant") or not label.get("passenger_voice"):
        return "skip"
    if post.source == "web":
        # Web results are page snippets, not single comments, so a human opens them first
        return "skip" if _is_official_page(post.url) else "lead"
    if label.get("urgency") == "high" and label.get("category") in FAILURE_CATEGORIES:
        return "escalate" if _is_live(post) else "draft"
    return "draft"


def context_query(label: dict) -> str:
    """Return a search query when a reply needs facts beyond the guidelines, otherwise an empty string."""
    category = label.get("category")
    operator = (label.get("operator") or "").strip()
    if category in FAILURE_CATEGORIES and operator:
        return f"{operator} accessible travel policy passenger assist redress"
    if category in MODEL_LOOKUP_CATEGORIES and label.get("needs_context"):
        return (label.get("context_query") or "").strip()
    return ""


@observe(name="draft_reply")
def draft_reply(post: Post, label: dict, guidelines: str, context: str = "") -> dict:
    """Return the drafted reply, or a placeholder result if every LLM provider fails."""
    prompt = PROMPT.format(
        guidelines=guidelines,
        context=context or "None",
        source=post.source,
        category=label.get("category"),
        sentiment=label.get("sentiment"),
        urgency=label.get("urgency"),
        text=post.text,
    )
    try:
        return ask_json(prompt)
    except RuntimeError as error:
        logger.warning("Drafting failed for %s: %s", post.post_id, error)
        return {"reply": "", "confidence": "low", "reviewer_note": "Drafting failed, reply manually."}