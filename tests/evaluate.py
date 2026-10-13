"""Measures how often the agent's decisions match hand-labelled expectations.

Run from the project root:
    python -m tests.evaluate
    python -m tests.evaluate --runs 3
    python -m tests.evaluate --cases outputs/real_cases.json --runs 2
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from src.classify import classify, pre_filter
from src.models import Post
from src.respond import decide

DEFAULT_CASES = Path(__file__).parent / "eval_cases.json"


def load_cases(path: Path) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    # Cases without an expected action have not been labelled yet
    return [case for case in cases if case.get("expected")]


def predict(posts: list[Post]) -> dict[str, str]:
    """Run the pre-filter, labelling and decision rules, and return an action per post."""
    kept = {post.post_id for post in pre_filter(posts)}
    labels = classify([post for post in posts if post.post_id in kept])

    predictions = {}
    for post in posts:
        if post.post_id not in kept:
            predictions[post.post_id] = "skip"
        elif post.post_id in labels:
            predictions[post.post_id] = decide(labels[post.post_id], post)
        else:
            predictions[post.post_id] = "unlabelled"
    return predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate agent decisions against hand-labelled cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--runs", type=int, default=1, help="repeat to check decisions are stable")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    posts = [
        Post(source=case["source"], post_id=case["id"], url=case.get("url", ""), text=case["text"])
        for case in cases
    ]
    runs = [predict(posts) for _ in range(args.runs)]

    totals, correct = Counter(), Counter()
    mistakes, unstable = [], 0
    for case in cases:
        expected = case["expected"]
        answers = [run[case["id"]] for run in runs]
        totals[expected] += len(answers)
        correct[expected] += answers.count(expected)
        if len(set(answers)) > 1:
            unstable += 1
        if any(answer != expected for answer in answers):
            mistakes.append((case["id"], expected, answers, case["text"][:70]))

    total, right = sum(totals.values()), sum(correct.values())
    print(f"\nCases: {len(cases)}, runs: {args.runs}")
    print(f"Overall: {right}/{total} decisions correct ({right / total:.0%})")
    print(f"Stable across runs: {len(cases) - unstable}/{len(cases)} cases\n")
    for action in sorted(totals):
        print(f"  {action:<9} {correct[action]}/{totals[action]}")

    if mistakes:
        print("\nMismatches:")
        for case_id, expected, answers, text in mistakes:
            print(f"  {case_id}: expected {expected}, got {', '.join(answers)} | {text}")


if __name__ == "__main__":
    main()