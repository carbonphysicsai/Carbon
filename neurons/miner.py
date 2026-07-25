"""Carbon Miner with Landscape prior integration.

Miners can now optionally load the latest published (noisy) priors
from the Landscape to build stronger strategies.
"""

import time
import typing
import json
import os
import random
import bittensor as bt

from carbon.protocol import StrategySynapse
from carbon.base.miner import BaseMinerNeuron
from carbon.miner.strategy_generator import generate_strategy, get_local_validation_score


class Miner(BaseMinerNeuron):
    """
    Improved Carbon Miner that can use Landscape-published priors.
    """

    def __init__(self, config=None):
        super().__init__(config=config)
        self.local_validation_enabled = True
        self.use_landscape_priors = True
        self.published_priors_dir = "./data/published_priors"
        bt.logging.info("Carbon Miner initialized with Landscape prior support.")

    def _load_latest_priors(self, challenge_id: str, backbone: str = "PINO") -> dict:
        """Load the latest published (noisy) priors for this challenge."""
        if not self.use_landscape_priors:
            return {}

        filename = f"{challenge_id}_{backbone}_daily.json"
        filepath = os.path.join(self.published_priors_dir, filename)

        if os.path.exists(filepath):
            try:
                with open(filepath) as f:
                    priors = json.load(f)
                bt.logging.info(f"Loaded published priors for {challenge_id}")
                return priors.get("loss_vector", {})
            except Exception as e:
                bt.logging.warning(f"Failed to load priors: {e}")
        return {}

    async def forward(self, synapse: StrategySynapse) -> StrategySynapse:
        bt.logging.info(f"Received request for challenge: {synapse.challenge_id}")

        try:
            if synapse.strategy is None:
                # Generate base strategy
                strategy = generate_strategy(synapse.challenge_id)

                # Try to improve using latest Landscape priors
                if self.use_landscape_priors:
                    published_loss = self._load_latest_priors(synapse.challenge_id)
                    if published_loss:
                        # Blend published priors with generated strategy
                        current = strategy.get("pino", {}).get("loss_vector", {})
                        blended = {**current, **published_loss}  # published takes precedence
                        strategy.setdefault("pino", {})["loss_vector"] = blended
                        bt.logging.info("Blended strategy with Landscape published priors")

                # Local validation
                if self.local_validation_enabled:
                    improvement, hard_pass, gate_details = get_local_validation_score(
                        synapse.challenge_id,
                        strategy,
                        use_real_training=True,
                        quick_epochs=5,
                    )

                    if hard_pass:
                        bt.logging.info(f"Local validation PASSED. Est. improvement: {improvement:+.4f}")
                        synapse.strategy = strategy
                        synapse.accepted = True
                        synapse.message = f"Validated (improvement ~{improvement:.3f})"
                    else:
                        bt.logging.warning("Local validation failed gates.")
                        synapse.strategy = strategy
                        synapse.accepted = False
                        synapse.message = "Local validation failed"
                else:
                    synapse.strategy = strategy
                    synapse.accepted = True
                    synapse.message = "Strategy generated"

            else:
                synapse.accepted = True
                synapse.message = "Strategy submission acknowledged"
                synapse.submission_id = f"sub_{int(time.time())}"

        except Exception as e:
            bt.logging.error(f"Error in miner forward: {e}")
            synapse.accepted = False
            synapse.message = f"Internal error"

        return synapse

    async def blacklist(self, synapse: StrategySynapse) -> typing.Tuple[bool, str]:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return True, "Missing dendrite or hotkey"

        if synapse.dendrite.hotkey not in self.metagraph.hotkeys:
            return True, "Unrecognized hotkey"

        return False, "Hotkey recognized"

    async def priority(self, synapse: StrategySynapse) -> float:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return 0.0
        try:
            uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
            return float(self.metagraph.S[uid])
        except Exception:
            return 0.0


if __name__ == "__main__":
    with Miner() as miner:
        while True:
            bt.logging.info("Carbon Miner running...")
            time.sleep(10)
