"""Review screen for the agent's output. A human reads, edits, approves or rejects drafts,
and can test how the agent judges any single post. Nothing is posted.

Run from the project root:
    streamlit run app.py
"""

import html
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from src import agent, config, report
from src.classify import classify, pre_filter
from src.context import load_guidelines, lookup_context
from src.models import Post
from src.respond import context_query, decide, draft_reply

ACTIONS = ("escalate", "draft", "lead", "pending", "skip")
REVIEWABLE = {"escalate", "draft"}
SOURCE_NAMES = {"app_store": "App Store", "bluesky": "Bluesky", "web": "Web", "youtube": "YouTube"}
DECISION_STYLES = {"escalate": "high", "draft": "low", "lead": "medium", "pending": "muted", "skip": "muted"}
STATUS_STYLES = {"approved": "low", "rejected": "high", "not reviewed": "muted"}

STYLE = """
<style>
div.block-container {padding-top: 2rem;}
.badge {display: inline-block; padding: 2px 10px; margin: 0 6px 4px 0; border-radius: 999px;
        font-size: 0.78rem; font-weight: 600;}
.b-source {background: #EEF2FF; color: #3730A3;}
.b-high {background: #FEE2E2; color: #991B1B;}
.b-medium {background: #FEF3C7; color: #92400E;}
.b-low {background: #DCFCE7; color: #166534;}
.b-muted {background: #F3F4F6; color: #4B5563;}
.post {white-space: pre-line; border-left: 3px solid #A5B4FC; padding: 6px 0 6px 12px; margin: 10px 0 6px;}
</style>
"""


def latest_run_file() -> Path | None:
    files = sorted(config.OUTPUTS_DIR.glob("run_*.json"))
    return files[-1] if files else None


def run_time(run_path: Path) -> str:
    try:
        return datetime.strptime(run_path.stem[4:], "%Y%m%d_%H%M").strftime("%d %b %Y, %H:%M")
    except ValueError:
        return run_path.name


def save_review(run_path: Path, decisions: dict) -> Path:
    review_path = run_path.with_name(run_path.name.replace("run_", "review_"))
    review_path.write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding="utf-8")
    return review_path


def reset_review() -> None:
    st.session_state.decisions = {}
    for key in [key for key in st.session_state.keys() if key.startswith("reply_")]:
        del st.session_state[key]


def badge(text: str, style: str) -> str:
    return f'<span class="badge b-{style}">{html.escape(text)}</span>'


def post_badges(source: str, label: dict) -> str:
    urgency = label.get("urgency") or "low"
    return (
        badge(SOURCE_NAMES.get(source, source), "source")
        + badge((label.get("category") or "other").replace("_", " "), "muted")
        + badge(f"{urgency} urgency", urgency if urgency in ("high", "medium") else "low")
    )


def show_post(post: dict, label: dict) -> None:
    st.markdown(f'<div class="post">{html.escape(post["text"])}</div>', unsafe_allow_html=True)
    link = f" · [Open original]({post['url']})" if post.get("url") else ""
    st.caption(f"Why: {label.get('reason', '')}{link}")


def set_decision(post_id: str, status: str, url: str) -> None:
    # Runs before the page redraws, so the progress bar and badges stay in sync
    st.session_state.decisions[post_id] = {
        "status": status,
        "reply": st.session_state.get(f"reply_{post_id}", ""),
        "url": url,
    }


def render_review_item(item: dict, urgent: bool) -> None:
    post, label = item["post"], item["label"]
    draft = item.get("draft") or {}
    post_id = post["post_id"]
    status = st.session_state.decisions.get(post_id, {}).get("status", "not reviewed")

    with st.container(border=True):
        tags, state = st.columns([5, 1])
        tags.markdown(post_badges(post["source"], label), unsafe_allow_html=True)
        state.markdown(badge(status, STATUS_STYLES[status]), unsafe_allow_html=True)
        if urgent:
            st.error("Urgent: this passenger may need help right now. Follow up directly as well as replying.")

        show_post(post, label)
        st.text_area("Draft reply", value=draft.get("reply", ""), key=f"reply_{post_id}", height=110)
        st.caption(
            f"Confidence: {draft.get('confidence', 'n/a')} · "
            f"Context used: {'yes' if item.get('context') else 'no'} · "
            f"Reviewer note: {draft.get('reviewer_note', '')}"
        )

        approve, reject, _ = st.columns([1, 1, 4])
        approve.button(
            "Approve", key=f"approve_{post_id}", type="primary",
            on_click=set_decision, args=(post_id, "approved", post["url"]),
        )
        reject.button(
            "Reject", key=f"reject_{post_id}",
            on_click=set_decision, args=(post_id, "rejected", post["url"]),
        )


def render_review_tab(urgent: list[dict], drafts: list[dict], run_path: Path) -> None:
    items = urgent + drafts
    if not items:
        st.info("Nothing to review in this run.")
        return

    decisions = st.session_state.decisions
    done = sum(item["post"]["post_id"] in decisions for item in items)
    progress, save = st.columns([4, 1])
    progress.progress(done / len(items), text=f"Reviewed {done} of {len(items)}")
    if save.button("Save review", type="primary", disabled=done == 0):
        path = save_review(run_path, decisions)
        st.success(f"Saved {done} decisions to {path.name}. Nothing has been posted.")

    for item in urgent:
        render_review_item(item, urgent=True)
    for item in drafts:
        render_review_item(item, urgent=False)


def render_list_tab(items: list[dict], note: str) -> None:
    st.caption(note)
    if not items:
        st.write("Nothing here.")
    for item in items:
        with st.container(border=True):
            st.markdown(post_badges(item["post"]["source"], item["label"]), unsafe_allow_html=True)
            show_post(item["post"], item["label"])


def render_test_tab() -> None:
    """Run a single pasted post through the same filter, labelling, decision and drafting steps."""
    st.caption("Paste any post to see how the agent judges it. It goes through the same steps as a full run.")
    source = st.selectbox("Source", list(SOURCE_NAMES), format_func=SOURCE_NAMES.get)
    text = st.text_area(
        "Post text",
        height=110,
        placeholder="Booked assistance at Leeds, nobody has turned up and my train leaves in 4 minutes",
    )
    if not st.button("Judge this post", type="primary") or not text.strip():
        return

    post = Post(source=source, post_id="manual", url="", text=text.strip())
    with st.spinner("Judging the post..."):
        if not pre_filter([post]):
            st.warning("Removed by the free pre-filter: no assistance terms, too short, or too old.")
            return
        label = classify([post]).get("manual")
        if label is None:
            st.error("The model could not label this post. Please try again.")
            return
        action = decide(label, post)
        query = context_query(label) if action in REVIEWABLE else ""
        context = lookup_context(query) if query else ""
        draft = draft_reply(post, label, load_guidelines(), context) if action in REVIEWABLE else None

    with st.container(border=True):
        st.markdown(
            f"Decision: {badge(action, DECISION_STYLES[action])} {post_badges(source, label)}",
            unsafe_allow_html=True,
        )
        st.caption(f"Why: {label.get('reason', '')}")
        if query:
            st.caption(f"Context looked up: {query}")
        if draft:
            st.text_area("Draft reply", value=draft.get("reply", ""), height=110)
            st.caption(f"Confidence: {draft.get('confidence')} · Reviewer note: {draft.get('reviewer_note')}")
        with st.expander("Full labels from the model"):
            st.json(label)


def main() -> None:
    st.set_page_config(page_title="Passenger Assistance Agent", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    st.session_state.setdefault("decisions", {})

    with st.sidebar:
        st.subheader("Run the agent")
        fresh = st.checkbox("Re-check posts already handled")
        if st.button("Run agent now", type="primary"):
            with st.spinner("Collecting posts, judging relevance and drafting replies..."):
                report.save(agent.run(use_history=not fresh))
            reset_review()
            st.rerun()
        st.divider()
        st.subheader("How it works")
        st.markdown(
            "1. Collect posts from the App Store, Bluesky, YouTube and the web\n"
            "2. Judge whether each post is relevant\n"
            "3. Skip, lead, escalate or draft\n"
            "4. Look up official context when needed\n"
            "5. A human reviews every draft"
        )

    st.title("Passenger Assistance Agent")
    st.caption("Finds passenger assistance posts and drafts replies for human review. Nothing is posted automatically.")

    run_path = latest_run_file()
    if run_path is None:
        st.info("No runs yet. Click 'Run agent now' in the sidebar.")
        return

    run = json.loads(run_path.read_text(encoding="utf-8"))
    groups = {action: [item for item in run["items"] if item["action"] == action] for action in ACTIONS}
    stats = run["stats"]

    summary = [
        ("Posts collected", stats.get("collected", 0)),
        ("To review", len(groups["escalate"]) + len(groups["draft"])),
        ("Urgent", len(groups["escalate"])),
        ("Leads", len(groups["lead"])),
        ("Pending", len(groups["pending"])),
    ]
    for column, (title, value) in zip(st.columns(len(summary)), summary):
        column.metric(title, value)
    with st.expander(f"Run details · {run_time(run_path)}"):
        st.write(" · ".join(f"{key.replace('_', ' ')}: {value}" for key, value in stats.items()))

    review, leads, pending, skipped, test = st.tabs([
        f"Review ({len(groups['escalate']) + len(groups['draft'])})",
        f"Leads ({len(groups['lead'])})",
        f"Pending ({len(groups['pending'])})",
        f"Skipped ({len(groups['skip'])})",
        "Test a post",
    ])
    with review:
        render_review_tab(groups["escalate"], groups["draft"], run_path)
    with leads:
        render_list_tab(groups["lead"], "Web threads for a human to open and read.")
    with pending:
        render_list_tab(groups["pending"], "Relevant posts over this run's limit. They are picked up on the next run.")
    with skipped:
        render_list_tab(groups["skip"], "Posts judged not relevant, or not a passenger's own experience.")
    with test:
        render_test_tab()


if __name__ == "__main__":
    main()