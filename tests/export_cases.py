"""Exports a random sample of real posts from the latest run for hand labelling.

The file goes to outputs/, which Git ignores because it holds real people's posts.
Agent decisions are not exported, so the labels are made independently.

Run from the project root:
    python -m tests.export_cases
"""

import json
import random

from src import config

SAMPLE_SIZE = 15
SEED = 42
OUTPUT_FILE = config.OUTPUTS_DIR / "real_cases.json"


def main() -> None:
    runs = sorted(config.OUTPUTS_DIR.glob("run_*.json"))
    if not runs:
        print("No runs found. Run python main.py first.")
        return

    items = json.loads(runs[-1].read_text(encoding="utf-8"))["items"]
    sample = random.Random(SEED).sample(items, min(SAMPLE_SIZE, len(items)))
    cases = [
        {
            "id": f"r{index:02d}",
            "source": item["post"]["source"],
            "url": item["post"]["url"],
            "text": item["post"]["text"],
            "expected": "",
        }
        for index, item in enumerate(sample, start=1)
    ]
    OUTPUT_FILE.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUTPUT_FILE}. Fill in 'expected' for each one.")


if __name__ == "__main__":
    main()