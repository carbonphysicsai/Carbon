"""Landscape Agent with CATE + Novelty + Automatic Prior Generation.

After successful distillation, improved (noisy) priors are generated.
"""

import time
from typing import Dict, Any, List, Optional

import numpy as np

import json

import os

from .causal_knowledge_base import CausalKnowledgeBase
from .storage import save_symbolic_artifact, load_symbolic_artifacts
from hydrogen.specialist.distillation import distill_strategy_to_specialist, regression_test_specialist
from hydrogen.specialist.bank import SpecialistBank

bank = SpecialistBank()


class LandscapeAgent:
    def __init__(self, storage_dir: str = "./data/landscape"):
        self.storage_dir = storage_dir
        self.kb = CausalKnowledgeBase(storage_dir=storage_dir)
        self.last_update = None

    def ingest_observation(
        self,
        challenge_id: str,
        backbone: str = "PINO",
        features: Dict[str, float] = None,
        treatment: Dict[str, float] = None,
        outcome: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.kb.add_observation(
            challenge_id=challenge_id,
            backbone=backbone,
            features=features,
            treatment=treatment,
            outcome=outcome,
            metadata=metadata,
        )

    def run_daily_update(self, challenge_ids: List[str] = None):
        if challenge_ids is None:
            challenge_ids = [
                "poisson_2d_v1",
                "darcy_2d_v1",
                "burgers_v1",
                "heat_v1",
                "elasticity_2d_v1",
                "ns_2d_laminar_v1",
            ]

        print(f"[Landscape] Running daily causal + symbolic update...")

        for challenge_id in challenge_ids:
            for backbone in ["PINO"]:
                causal_result = self.kb.estimate_causal_effects(
                    challenge_id, backbone=backbone
                )
                if causal_result.get("status") == "success":
                    print(f"  [{challenge_id}/{backbone}] Causal ATE: {causal_result.get('ate', 0):.4f}")

                cate_result = self.kb.estimate_heterogeneous_effects(
                    challenge_id, backbone=backbone
                )
                if cate_result.get("status") == "success":
                    print(f"  [{challenge_id}/{backbone}] CATE estimated")

        self.last_update = int(time.time())
        print("[Landscape] Daily update complete.")

    def propose_distillation_candidates(
        self,
        challenge_id: str,
        backbone: str = "PINO",
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        candidates = []

        weight_artifacts = load_symbolic_artifacts(
            artifact_type="evolved_loss_weights",
            challenge_id=challenge_id,
            limit=25,
        )

        causal = self.kb.causal_estimates.get(
            self.kb._make_key(challenge_id, backbone), {}
        )
        causal_ate = causal.get("ate", 0.0)

        if causal_ate <= 0.01:
            print(f"[{challenge_id}] Weak causal signal. Skipping distillation.")
            return []

        for i, artifact in enumerate(weight_artifacts[:top_k]):
            content = artifact.get("content", {})
            loss_vector = content.get("loss_vector", {})

            novelty = 0.0
            if loss_vector:
                avg_dev = np.mean([abs(v - 1.0) for v in loss_vector.values()])
                novelty = min(1.0, avg_dev)

            combined_score = causal_ate * 0.7 + novelty * 0.3

            candidate = {
                "rank": i + 1,
                "challenge_id": challenge_id,
                "backbone": backbone,
                "loss_vector": loss_vector,
                "causal_ate": causal_ate,
                "novelty_score": novelty,
                "combined_score": combined_score,
                "recommended_for_distillation": True,
            }
            candidates.append(candidate)

        candidates = sorted(candidates, key=lambda x: x["combined_score"], reverse=True)
        return candidates[:top_k]

    def generate_improved_priors(self, challenge_id: str, backbone: str = "PINO", noise_level: float = 0.025):
        """
        Generate improved (noisy) priors after successful distillation.
        """
        best_specialist = bank.get_best_for_challenge(challenge_id, backbone)
        if not best_specialist:
            return None

        loss_vector = best_specialist.get("strategy_config", {}).get("pino", {}).get("loss_vector", {})
        if not loss_vector:
            return None

        import random
        improved = {}
        for k, v in loss_vector.items():
            noise = random.gauss(0, noise_level)
            improved[k] = max(0.05, v * (1 + noise))

        # Save as published prior
        os.makedirs("./data/published_priors", exist_ok=True)
        filepath = f"./data/published_priors/{challenge_id}_{backbone}_improved.json"
        with open(filepath, "w") as f:
            json.dump({
                "challenge_id": challenge_id,
                "backbone": backbone,
                "loss_vector": improved,
                "source": "auto_generated_after_distillation",
                "timestamp": int(time.time()),
            }, f, indent=2)

        print(f"[Landscape] Generated improved priors for {challenge_id} -> {filepath}")
        return improved

    def run_full_daily_cycle(self):
        print("\n[Landscape] === Starting Full Daily Cycle (Causal + Novelty + Auto-Priors) ===")

        self.run_daily_update()

        challenges = [
            "poisson_2d_v1",
            "darcy_2d_v1",
            "burgers_v1",
            "heat_v1",
            "elasticity_2d_v1",
            "ns_2d_laminar_v1",
        ]

        for challenge_id in challenges:
            candidates = self.propose_distillation_candidates(challenge_id)

            if not candidates:
                continue

            print(f"[{challenge_id}] Distilling {len(candidates)} cause + novelty backed candidates...")

            for candidate in candidates:
                strategy = {
                    "backbone": candidate["backbone"],
                    "pino": {
                        "loss_vector": candidate.get("loss_vector", {})
                    },
                }

                specialist = distill_strategy_to_specialist(
                    challenge_id=challenge_id,
                    strategy=strategy,
                )

                test_result = regression_test_specialist(
                    specialist=specialist,
                    challenge_id=challenge_id,
                )

                if test_result.get("regression_passed"):
                    print(f"  ✓ Registered specialist {specialist['specialist_id']}")
                    bank.register(specialist)

                    save_symbolic_artifact(
                        artifact_type="specialist",
                        challenge_id=challenge_id,
                        content=specialist,
                        metadata={
                            "source": "LandscapeAgent",
                            "causal_ate": candidate.get("causal_ate"),
                            "novelty_score": candidate.get("novelty_score"),
                        },
                    )

                    # NEW: Generate improved priors after successful distillation
                    self.generate_improved_priors(challenge_id, candidate["backbone"])

        print("[Landscape] === Daily Cycle Complete ===\n")

    def get_status(self) -> Dict[str, Any]:
        return {
            "last_update": self.last_update,
            "storage_dir": self.storage_dir,
            "causal_estimates_tracked": len(self.kb.causal_estimates),
        }
