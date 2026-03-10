from __future__ import annotations

import argparse

from config import configure_logging, load_settings
from core import AutonomousNIRA


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NIRA Stage 3 autonomous AI assistant")
    parser.add_argument("--goal", help="Execute a multi-step autonomous goal")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    configure_logging(settings)
    platform = AutonomousNIRA(settings)

    if args.goal:
        result = platform.run_goal(args.goal)
        print(result.summary)
        return 0

    print("NIRA Stage 3 interactive mode. Use /goal <task>, /metrics, /knowledge, /quit.")
    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user_input:
            continue
        if user_input in {"/quit", "/exit"}:
            return 0
        if user_input == "/metrics":
            print(platform.metrics.summary())
            continue
        if user_input == "/knowledge":
            print([entry.topic for entry in platform.knowledge_base.all()])
            continue
        if user_input.startswith("/goal "):
            result = platform.run_goal(user_input[6:].strip())
            print(f"NIRA> {result.summary}")
            continue
        print(f"NIRA> {platform.chat(user_input)}")

if __name__ == "__main__":
    raise SystemExit(main())
