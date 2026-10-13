# Passenger Assistance Agent

A local demo agent that finds where passengers talk about rail passenger assistance online, decides which posts need a response, and drafts replies for a human to review. Nothing is ever posted automatically.

Built for the Transreport AI Agent Builder Intern case study, within the 4-hour time box.

![Decision flow](docs/decision_flow.png)

## Context: UK rail

I focused on passenger assistance on UK rail, for three reasons:

- It is where the Passenger Assistance app is used, so the output speaks directly to Transreport's own users and operators.
- There is real, reachable feedback: public App Store reviews of the app and first-hand posts on social media.
- Rail has clear, public rules (booking notice, Turn Up and Go, operators' Accessible Travel Policies), so replies can be grounded in facts instead of being generic.

The design is not rail-specific. Moving to airports or ferries means changing the search terms in `src/config.py` and the guidelines in `inputs/response_guidelines.md`, not the code.

## Quick start

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac or Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your own keys (Gemini, Groq, Tavily, Bluesky handle and app password, and optionally Langfuse).

| Command | What it does |
|---|---|
| `python main.py` | Runs the agent on posts it has not handled before, and writes a report to `outputs/` |
| `python main.py --fresh` | Runs the agent on every post again, ignoring the history |
| `streamlit run app.py` | Opens the review screen: read, edit, approve or reject drafts, or test a single post |
| `python -m tests.evaluate --runs 3` | Scores the agent's decisions against hand-labelled cases |
| `python tests/test_setup.py` | Checks every API key and connection |

## How it works

1. **Collect** posts from three sources and convert them to one shared format. Usernames are never stored.
2. **Pre-filter** for free: the post must mention assistance, be at least 40 characters long, and be from the last 180 days.
3. **Skip anything already handled.** Post IDs and outcomes are kept in a local history, so each post is judged and answered once. Pending posts and failed drafts come back on the next run.
4. **Label** with an LLM in batches of 10: relevance, whether it is a passenger's own experience, category, sentiment, urgency and the operator named.
5. **Decide** with plain rules in code:
   - not relevant, or not a passenger's own experience: **skip**
   - a web page: **lead** for a human to open (official pages such as gov.uk and PDFs are skipped)
   - a high-urgency failure posted in the last 24 hours: **escalate**
   - everything else: **draft**
6. **Prioritise**: the reply queue is sorted by urgency, then by how negative the post is. The top 12 are drafted, and the rest are marked pending for the next run.
7. **Gather context** when a failure post names an operator (that operator's official accessible travel policy), or when a passenger asks a question the guidelines may not answer. Searches are limited to official sites (National Rail, ORR, gov.uk, Passenger Assistance), with at most 4 per run.
8. **Draft** each reply from the guidelines and any context. Every draft carries a confidence level and a note for the reviewer.
9. **Review**: a human approves, edits or rejects each draft in the review screen. Decisions are saved to a review file.
10. **Trace**: every run is recorded in Langfuse, including each model call with its prompt, output, model, latency and token usage.

The full decision flow is in `docs/decision_flow.md`.

## Sources

| Source | Why | How |
|---|---|---|
| App Store reviews | Highest signal: every review is about the Passenger Assistance app or the service | Apple's public reviews feed for the app's fixed ID. If the feed comes back empty, it tries a second feed order, then the last successful fetch (logged when used) |
| Bluesky | First-hand posts, often written during or just after a journey | Authenticated search with an app password. Unauthenticated public search returned 403 |
| Web search (Tavily) | Reaches forums, Facebook groups and other community threads | Results become leads, because a snippet is not a full thread |

**Not used, and why**

- **Hacker News:** connected and working, but it is a tech forum with very little about rail assistance.
- **YouTube:** the key works. I left it out to keep the scope small and handle three sources well. The source design makes it a single new file.
- **Google Play:** the only free route is an unofficial scraper that can break without warning.
- **Reddit and X:** no free API for new developers. I do not scrape them. Public threads can still surface through web search results, which arrive as leads for a human to open. With a business case, the paid official APIs would be the right route.

## Inputs that shape the responses

`inputs/response_guidelines.md` sets:

- who we reply as (the Passenger Assistance support team, which does not deliver assistance on the ground)
- tone and length (warm, plain British English, under 80 words)
- the facts replies may use
- channel rules (App Store replies cannot invite private messages, Bluesky replies can)
- hard rules: only respond to what the person actually said, never promise compensation, never ask for personal details in public, never blame named staff

Changing this file changes the agent's behaviour without touching code.

## Key decisions

- **The model labels, the code decides.** Skip, lead, escalate and draft are rules in `src/respond.py`, so every outcome can be explained and tested.
- **Cheap checks before paid ones.** The pre-filter and the history check run before any model call, and posts are labelled 10 at a time to stay within free-tier limits.
- **Escalation needs three conditions:** high urgency, a real failure, and a post less than 24 hours old. The model cannot see when a post was written, but the code can. Posts with an unknown age still escalate, because missing a stranded passenger is worse than a false alarm.
- **Context lookups are spent where they change the reply.** The model's own search suggestions were sometimes off-target, so they are only used for direct passenger questions.
- **Resilience:** Gemini is the main model and Groq the fallback. A rate limit gets one short retry first. Timeouts, errors and malformed JSON all fall through to the fallback. If both fail, the draft says "reply manually" and the post goes back in the queue. A source that fails returns nothing instead of stopping the run.
- **Data care:** usernames are never stored, `outputs/` is excluded from Git because it holds real posts, the committed evaluation set is synthetic, and the real-post evaluation file stays local.

## Evaluation

| Set | Cases | Runs | Correct decisions | Stable across runs |
|---|---|---|---|---|
| Synthetic, written to cover every outcome and known traps | 16 | 3 | 47/48 (98%) | 15/16 |
| Real posts, labelled by me without seeing the agent's decisions | 15 | 2 | 29/30 (97%) | 14/15 |

Both misses were inconsistent rather than consistently wrong: a staff-conduct complaint escalated once, and an international journey got a draft once. These sets are small, and I wrote the synthetic one, so I treat the scores as a regression check rather than a real accuracy figure.

## What reviewing the output changed

The first full run worked, but reading the report showed four problems, each now fixed:

1. A post about travelling tomorrow was escalated. Urgency now requires an actual failure.
2. A government PDF was treated as a passenger post. Web results are now leads, and official pages are skipped.
3. A journey from Brussels to Darmstadt got a reply. Relevance is now limited to Great Britain.
4. App Store replies invited private messages, which the App Store does not support. The guidelines now include channel rules.

Later runs led to four more changes:

- A post that was days old, but written in the present tense, was escalated. That led to the 24-hour rule.
- Context lookups were spent on unhelpful searches such as station codes. Model-suggested lookups are now limited to direct questions.
- The App Store feed came back empty twice in a row. The source now uses the app's fixed ID (one call instead of two) and a second feed order.
- When both models failed on one draft, the post was recorded as handled and would never have been retried. Failed drafts now go back in the queue, and rate limits get a retry.
- Apple's feed stopped returning reviews after many test runs. The source now falls back to the last successful fetch and says so in the log.
- Some drafts apologised for a failure the person never described, or added details such as "today". The classifier's labels were being treated as facts. The drafting prompt now treats labels as hints and sticks to what the post says, and the guidelines gained a rule to the same effect.

## Limitations

- The evaluation sets are small, and borderline cases can get different answers on different runs.
- Web results are page snippets, so the agent never sees the full thread.
- Search terms are fixed, so recall is unknown: relevant posts that use other words are missed.
- Only the latest page of App Store reviews is read, and Apple's feed is sometimes empty or throttled. When that happens, the cached reviews may be out of date.
- Drafts can still occasionally assume details that are not in the post. The reviewer note and human review are the safety net.
- Context lookups return short snippets, which may not contain the exact redress process for a given operator.
- Post text is sent to Gemini, Groq and Langfuse. A real deployment would need agreements with those providers, or self-hosting and masking of personal details.
- Model calls run one after another, so a run takes one to two minutes on the free tier.

## What I would do next

1. For borderline urgency, run the label twice and send disagreements to a human.
2. Label a few hundred real posts with the support team, and track escalation precision and recall over time.
3. Use reviewers' edits as feedback to refine the guidelines and prompts.
4. Keep a small directory of operators with links to their official Accessible Travel Policies, so replies can point to the exact policy.
5. Add YouTube comments as a fourth source.
6. Run on a schedule, and send escalations straight to the team's chat channel.
7. Score drafts automatically in Langfuse (tone, length, rule breaches) before they reach a reviewer.

## Project structure

```
main.py                        runs the agent once and saves the report
app.py                         review screen (Streamlit)
inputs/response_guidelines.md  tone, facts, channel rules and hard rules for replies
src/
  config.py                    settings, search terms and limits
  models.py                    shared Post format
  llm.py                       Gemini with Groq fallback, retries, JSON output, tracing
  sources/                     app_store.py, bluesky.py, web_search.py
  classify.py                  pre-filter and LLM labelling
  respond.py                   decision rules, context rule and drafting
  context.py                   guidelines loader and official-site search
  state.py                     history of processed posts
  agent.py                     runs the full pipeline
  report.py                    JSON and Markdown outputs
tests/
  test_setup.py                API connection checks
  eval_cases.json              synthetic hand-labelled cases
  evaluate.py                  decision accuracy and stability
  export_cases.py              exports real posts for local hand labelling
docs/decision_flow.md          decision flow diagram
```

## How I used the time

| Share of time | Work |
|---|---|
| About 5% | Reading the brief, choosing the context and sources, planning |
| About 30% | Building the pipeline: sources, labelling, decision rules, drafting |
| About 35% | Reviewing real output and fixing what it showed |
| About 30% | Evaluation, review screen, tracing, diagram and this README |

## AI coding tool declaration 
I used Claude as a coding assistant to help me implement, structure, and refine the code more efficiently, while I focused on designing the agent's workflow, making key technical decisions, testing its functionality, identifying issues, and evaluating its performance.