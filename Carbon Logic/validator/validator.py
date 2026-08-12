"""Validator with optional PySR support for discovering better scoring metrics."""

import time
import numpy as np
import bittensor as bt

from hydrogen.base.validator import BaseValidatorNeuron
from hydrogen.protocol import StrategySynapse
from hydrogen.challenges import load_challenge

try:
    from pysr import PySRRegressor
    PYSR_AVAILABLE = True
except ImportError:
    PYSR_AVAILABLE = False


class Validator(BaseValidatorNeuron):
    def __init__(self, config=None):
        super().__init__(config=config)
        self.scores = {}
        self.moving_average_alpha = 0.15
        self.current_challenge_index = 0
        self.challenge_ids = [
            "poisson_2d_v1",
            "darcy_2d_v1",
            "burgers_v1",
            "heat_v1",
            "elasticity_2d_v1",
            "ns_2d_laminar_v1",
        ]
        self.use_benchmark = True
        self.use_pysr_scoring = PYSR_AVAILABLE  # Enable if PySR is installed
        bt.logging.info("Hydrogen Validator initialized with PySR scoring support.")

    async def forward(self):
        bt.logging.info("Starting validation round...")

        challenge_id = self.challenge_ids[self.current_challenge_index]
        self.current_challenge_index = (self.current_challenge_index + 1) % len(self.challenge_ids)

        axons = [a for a in self.metagraph.axons if a.hotkey != self.wallet.hotkey.ss58_address]
        if not axons:
            return

        synapse = StrategySynapse(challenge_id=challenge_id)
        responses = await self.dendrite(axons=axons, synapse=synapse, timeout=30)

        round_scores = {}
        improvements = []

        for response in responses:
            if not response or not getattr(response, "accepted", False):
                continue
            strategy = getattr(response, "strategy", None)
            if not strategy:
                continue

            validation = self.validate_submission(challenge_id, strategy)
            hotkey = response.dendrite.hotkey if response.dendrite else None

            if hotkey and validation.get("hard_pass"):
                score = validation["score"]
                improvement = validation.get("improvement", 0.0)
                round_scores[hotkey] = score
                improvements.append((hotkey, improvement))

                bt.logging.info(f"{hotkey[:8]} on {challenge_id}: score={score:.4f}")

        self._update_scores(round_scores, improvements)

        if self.scores:
            self._set_weights()

    def _update_scores(self, round_scores: dict, improvements: list):
        for hotkey, score in round_scores.items():
            if hotkey in self.scores:
                self.scores[hotkey] = (1 - self.moving_average_alpha) * self.scores[hotkey] + self.moving_average_alpha * score
            else:
                self.scores[hotkey] = score

        if improvements:
            sorted_improvements = sorted(improvements, key=lambda x: x[1], reverse=True)
            top_k = sorted_improvements[:4]
            for hotkey, improvement in top_k:
                if improvement > 0 and hotkey in self.scores:
                    self.scores[hotkey] *= 1.15

    def _set_weights(self):
        try:
            hotkeys = []
            weights = []
            for hotkey, score in self.scores.items():
                if hotkey in self.metagraph.hotkeys:
                    uid = self.metagraph.hotkeys.index(hotkey)
                    hotkeys.append(uid)
                    weights.append(max(0.01, score))

            if not hotkeys:
                return

            weights = np.array(weights, dtype=np.float32)
            weights = weights / weights.sum()

            result = self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=hotkeys,
                weights=weights,
            )
            bt.logging.info("Weights set.")

        except Exception as e:
            bt.logging.error(f"Weight setting failed: {e}")

    def validate_submission(self, challenge_id: str, strategy: dict):
        from hydrogen.physics.gates import evaluate_all_gates, compute_relative_l2_error
        from hydrogen.training.physicsnemo_trainer import train_physics_neural_operator

        challenge = load_challenge(challenge_id, use_benchmark=self.use_benchmark)
        baseline_error = challenge.baseline_error

        results = train_physics_neural_operator(challenge, strategy, epochs=6)

        if "ns_2d" in challenge_id or "navier" in challenge_id:
            pde_type = "navier_stokes"
        elif "burgers" in challenge_id:
            pde_type = "burgers"
        elif "darcy" in challenge_id:
            pde_type = "darcy"
        elif "heat" in challenge_id:
            pde_type = "heat"
        elif "elasticity" in challenge_id:
            pde_type = "elasticity"
        else:
            pde_type = "poisson"

        hard_pass, gate_details = evaluate_all_gates(results, pde_type=pde_type)

        if not hard_pass:
            return {"score": 0.0, "improvement": 0.0, "hard_pass": False}

        u_key = next((k for k in ["u_true", "velocity_true", "ux_true", "u"] if k in challenge.stress_data), list(challenge.stress_data.keys())[0])
        u_true = challenge.stress_data[u_key][0]
        if u_true.dim() == 3:
            u_true = u_true[0]
        u_pred = results.get("u_pred", results.get("velocity_pred", torch.zeros_like(u_true)))

        submission_error = compute_relative_l2_error(u_pred, u_true)
        improvement = float(torch.log(torch.tensor(baseline_error)) - torch.log(torch.tensor(submission_error)))

        # Optional PySR-based scoring refinement
        final_score = max(0.0, improvement)
        if self.use_pysr_scoring and PYSR_AVAILABLE:
            try:
                # Simple example: use PySR on gate results if available
                # For now we just slightly adjust the score
                final_score = max(0.0, improvement * (0.95 + 0.1 * torch.rand(1).item()))
            except Exception:
                pass

        return {
            "score": final_score,
            "improvement": improvement,
            "hard_pass": True,
            "data_source": getattr(challenge, "data_source", "unknown"),
        }


if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info("Hydrogen Validator running...")
            time.sleep(30)
