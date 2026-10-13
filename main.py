"""Entry point: runs the passenger assistance agent and saves drafts for human review.

Run from the project root:
    python main.py            only judge posts not handled in earlier runs
    python main.py --fresh    judge every post again
"""

import argparse
import logging

from src import agent, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the passenger assistance agent once.")
    parser.add_argument("--fresh", action="store_true", help="re-check posts handled in earlier runs")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run = agent.run(use_history=not args.fresh)
    json_path, report_path = report.save(run)

    print("\nRun complete. Nothing has been posted.")
    for key, value in run["stats"].items():
        print(f"  {key.replace('_', ' ')}: {value}")
    print(f"\nReport: {report_path}\nData:   {json_path}")


if __name__ == "__main__":
    main()