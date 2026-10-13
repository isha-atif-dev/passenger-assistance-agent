"""Saves each run as JSON and as a readable Markdown report for human reviewers."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src import config

SECTIONS = {
    "escalate": "Urgent: needs human follow-up",
    "draft": "Draft replies for review",
    "lead": "Leads to open and check manually",
    "pending": "Queued for the next run",
}
MAX_POST_PREVIEW = 400


def _format_item(item: dict) -> str:
    post, label = item["post"], item["label"]
    lines = [
        f"### {post.source} | {label.get('category')} | {label.get('sentiment')} | urgency: {label.get('urgency')}",
        f"Link: {post.url}",
        "",
        f"> {post.text[:MAX_POST_PREVIEW].replace(chr(10), ' ')}",
        "",
        f"Why: {label.get('reason')}",
    ]
    draft = item.get("draft")
    if draft:
        lines += [
            f"Extra context used: {'yes' if item.get('context') else 'no'}",
            "",
            f"**Draft reply** (confidence: {draft.get('confidence')}):",
            "",
            draft.get("reply", ""),
            "",
            f"Reviewer note: {draft.get('reviewer_note')}",
        ]
    return "\n".join(lines) + "\n"


def _markdown(run: dict) -> str:
    stats = run["stats"]
    parts = [
        "# Passenger assistance agent report",
        f"Generated {datetime.now():%d %B %Y, %H:%M}. All replies are drafts and have not been posted.",
        "",
        "## Summary",
        *(f"- {key.replace('_', ' ')}: {value}" for key, value in stats.items()),
        "",
    ]
    for action, title in SECTIONS.items():
        section = [item for item in run["items"] if item["action"] == action]
        if section:
            parts.append(f"## {title} ({len(section)})\n")
            parts.extend(_format_item(item) for item in section)
    return "\n".join(parts)


def save(run: dict) -> tuple[Path, Path]:
    """Write the JSON and Markdown outputs and return their paths."""
    config.OUTPUTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    items = [{**item, "post": asdict(item["post"])} for item in run["items"]]
    json_path = config.OUTPUTS_DIR / f"run_{stamp}.json"
    json_path.write_text(
        json.dumps({"stats": run["stats"], "items": items}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report_path = config.OUTPUTS_DIR / f"report_{stamp}.md"
    report_path.write_text(_markdown(run), encoding="utf-8")
    return json_path, report_path