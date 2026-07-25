"""AgenticMiner updated to use the client abstraction."""

from typing import Dict, Any, Optional, List

import asyncio

from carbon.miner.client import BaseCarbonClient, MockCarbonClient


class AgenticMiner:
    """
    High-level interface for agentic mining.

    Now uses a pluggable client (Mock or Real).
    """

    def __init__(self, client: BaseCarbonClient = None):
        self.client = client or MockCarbonClient()
        self.history: List[Dict[str, Any]] = []

    async def get_challenges(self) -> List[str]:
        return await self.client.get_active_challenges()

    async def get_priors(self, challenge_id: str) -> Dict[str, Any]:
        return await self.client.get_priors(challenge_id)

    async def propose_strategy(
        self,
        challenge_id: str,
        base_strategy: Optional[Dict[str, Any]] = None,
        mutation_strength: float = 0.12,
    ) -> Dict[str, Any]:
        if base_strategy is None:
            priors = await self.get_priors(challenge_id)
            from carbon.miner.strategy_generator import generate_strategy
            base_strategy = generate_strategy(challenge_id=challenge_id)

        # Light mutation
        import copy, random
        mutated = copy.deepcopy(base_strategy)
        if "pino" in mutated and "loss_vector" in mutated.get("pino", {}):
            for k in mutated["pino"]["loss_vector"]:
                val = mutated["pino"]["loss_vector"][k]
                mutated["pino"]["loss_vector"][k] = max(0.1, val * (1 + random.uniform(-mutation_strength, mutation_strength)))

        return mutated

    async def validate_locally(
        self, strategy: dict, challenge_id: str, quick: bool = True
    ) -> Dict[str, Any]:
        return await self.client.validate_locally(strategy, challenge_id, quick=quick)

    async def submit(self, strategy: dict, challenge_id: str) -> Dict[str, Any]:
        result = await self.client.submit(challenge_id, strategy)
        self.history.append({
            "challenge_id": challenge_id,
            "strategy": strategy,
            "result": result
        })
        return result

    async def run_iteration(self, challenge_id: str, iterations: int = 8):
        best_score = 0.0
        best_strategy = None

        for i in range(1, iterations + 1):
            strategy = await self.propose_strategy(challenge_id)
            validation = await self.validate_locally(strategy, challenge_id)

            score = validation.get("estimated_score", 0.0)
            print(f"Iteration {i}: estimated_score = {score}")

            if score > best_score:
                best_score = score
                best_strategy = strategy

            if score >= 0.075:
                print(f"Threshold reached. Submitting...")
                if not getattr(self, "_dry_run", False):
                    result = await self.submit(best_strategy, challenge_id)
                    return result

        if best_strategy:
            return await self.submit(best_strategy, challenge_id)
        return None


# Convenience function
async def get_agentic_miner(use_real_client: bool = False):
    if use_real_client:
        # Future: return AgenticMiner(RealCarbonClient())
        print("Real client not available yet. Using Mock client.")
    return AgenticMiner()
