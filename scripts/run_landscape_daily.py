"""Daily Landscape update runner.

This script should be run once per day (via cron or scheduler).
It triggers the LandscapeAgent's daily causal + symbolic update cycle.
"""

import argparse

from carbon.landscape.agent import LandscapeAgent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--challenges",
        nargs="+",
        default=None,
        help="List of challenges to update (default: all)",
    )
    args = parser.parse_args()

    agent = LandscapeAgent()

    print("[Landscape] Starting daily update...")
    agent.run_daily_update(challenge_ids=args.challenges)
    print("[Landscape] Daily update finished.")


if __name__ == "__main__":
    main()
