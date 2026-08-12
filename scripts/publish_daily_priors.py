"""Daily publication of noisy leading priors per challenge + backbone.

Run this script once per day (e.g. via cron).

It generates publishable (slightly noisy) versions of the current best
priors so miners can build off the leader without having direct access
to the full proprietary Landscape.
"""

import argparse
import json
import os
import sys

from carbon.landscape.causal_knowledge_base import CausalKnowledgeBase


CHALLENGES = [
    "poisson_2d_v1",
    "darcy_2d_v1",
    "burgers_v1",
    "heat_v1",
    "elasticity_2d_v1",
    "ns_2d_laminar_v1",
]

BACKBONES = ["PINO"]  # Extend later if more backbones are supported


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./data/published_priors",
        help="Where to save the daily published priors",
    )
    parser.add_argument(
        "--noise_level",
        type=float,
        default=0.03,
        help="Amount of noise to add to loss vectors",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    kb = CausalKnowledgeBase()

    published = []

    for challenge_id in CHALLENGES:
        for backbone in BACKBONES:
            try:
                priors = kb.get_publishable_priors(
                    challenge_id=challenge_id,
                    backbone=backbone,
                    noise_level=args.noise_level,
                )
                published.append(priors)

                # Save individual file
                filename = f"{challenge_id}_{backbone}_daily.json"
                filepath = os.path.join(args.output_dir, filename)

                with open(filepath, "w") as f:
                    json.dump(priors, f, indent=2)

                print(f"Published priors for {challenge_id} ({backbone}) -> {filepath}")

            except Exception as e:
                print(f"Failed to publish for {challenge_id} ({backbone}): {e}")

    # Also save a combined daily file
    combined_path = os.path.join(args.output_dir, "daily_priors_combined.json")
    with open(combined_path, "w") as f:
        json.dump(published, f, indent=2)

    print(f"\nDaily priors published to: {args.output_dir}")
    print(f"Combined file: {combined_path}")


if __name__ == "__main__":
    main()
