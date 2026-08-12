"""Client abstraction for Carbon mining.

This provides a clean interface that the AgenticMiner and Docker
environment can use. In production, this would be replaced by (or
wrap) the real CarbonClient.
"""

from typing import Dict, Any, Optional


class BaseCarbonClient:
    """Base interface for Carbon clients."""

    async def get_active_challenges(self) -> list:
        raise NotImplementedError

    async def get_priors(self, challenge_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    async def validate_locally(self, strategy: dict, challenge_id: str, quick: bool = True) -> Dict[str, Any]:
        raise NotImplementedError

    async def submit(self, challenge_id: str, strategy: dict) -> Dict[str, Any]:
        raise NotImplementedError


class MockCarbonClient(BaseCarbonClient):
    """Mock client for development and Docker testing.

    In production, replace this with the real CarbonClient.
    """

    async def get_active_challenges(self) -> list:
        return ["poisson_2d_v1", "darcy_2d_v1", "burgers_v1"]

    async def get_priors(self, challenge_id: str) -> Dict[str, Any]:
        # Simulated priors with internal noise
        base = {
            "pde_residual": 1.0,
            "boundary": 0.67,
            "conservation_mass": 1.18
        }
        import random
        return {k: round(v * (1 + random.gauss(0, 0.035)), 3) for k, v in base.items()}

    async def validate_locally(self, strategy: dict, challenge_id: str, quick: bool = True) -> Dict[str, Any]:
        import random
        # Simulate realistic validation
        base_score = 0.055 + random.uniform(0.0, 0.04)
        return {
            "estimated_score": round(base_score, 4),
            "physics_gates_passed": True,
            "diagnostics": "Simulated validation"
        }

    async def submit(self, challenge_id: str, strategy: dict) -> Dict[str, Any]:
        return {
            "status": "submitted",
            "challenge": challenge_id,
            "estimated_rank": 3
        }


# Future: RealCarbonClient would go here
# class RealCarbonClient(BaseCarbonClient):
#     ...
