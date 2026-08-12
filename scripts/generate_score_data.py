"""Generate realistic score data JSON files for leaderboards.

This script creates plausible per-challenge score data that can be
used by generate_leaderboard.py. It pulls some signal from the
CausalKnowledgeBase when available.

Usage:
    python scripts/generate_score_data.py
"""

import json
import os
import random
from datetime import datetime, timedelta

from carbon.landscape.causal_knowledge_base import CausalKnowledgeBase


CHALLENGES = [
    "poisson_2d_v1",
    "darcy_2d_v1",
    "burgers_v1",
    "heat_v1",
    "elasticity_2d_v1",
    "ns_2d_laminar_v1",
]

BACKBONES = ["PINO"]


def generate_scores_for_challenge(challenge_id: str, n_miners: int = 35) -> list:
    """Generate realistic scores for one challenge."""
    kb = CausalKnowledgeBase()
    best_priors = kb.get_best_priors(challenge_id)

    # Base performance influenced by whether we have good priors
    base_performance = 0.065
    if best_priors.get("recommended_loss_vector"):
        base_performance += 0.018  # Boost if we have evolved priors

    scores = []
    for i in range(n_miners):
        # Simulate different miner skill levels
        skill = 0.6 + (i / n_miners) * 0.55 + random.gauss(0, 0.04)

        improvement = round(max(0.002, (skill - 0.55) * 0.09 + random.gauss(0, 0.008)), 4)
        score = round(base_performance + improvement * 0.85 + random.gauss(0, 0.006), 4)

        submissions = random.randint(8, 67)
        win_rate = round(min(0.89, 0.31 + skill * 0.55 + random.gauss(0, 0.05)), 3)

        last_active = (datetime.now() - timedelta(hours=random.randint(1, 72))).strftime("%Y-%m-%d %H:%M")

        data_source = "pdebench" if random.random() > 0.28 else "synthetic"

        scores.append({
            "wallet": f"5GrwvaEF5zXb26Fz9rcQpDWS{i:02d}CtERHpNehXCPcNoHGKuty",
            "hotkey": f"5GrwvaEF5zXb26Fz9rcQpDWS{i:02d}CtERHpNehXCPcNoHGKuty",
            "score": max(0.01, score),
            "improvement": improvement,
            "data_source": data_source,
            "submissions": submissions,
            "win_rate": win_rate,
            "last_active": last_active,
        })

    # Sort by score descending
    return sorted(scores, key=lambda x: x["score"], reverse=True)


def main():
    output_dir = "./data/scores"
    os.makedirs(output_dir, exist_ok=True)

    for challenge_id in CHALLENGES:
        scores = generate_scores_for_challenge(challenge_id)

        filepath = os.path.join(output_dir, f"{challenge_id}_scores.json")
        with open(filepath, "w") as f:
            json.dump(scores, f, indent=2)

        print(f"Generated score data: {filepath} ({len(scores)} miners)")

    print("\nAll score data files generated successfully.")
    print("You can now run: python scripts/generate_leaderboard.py")


if __name__ == "__main__":
    main()
