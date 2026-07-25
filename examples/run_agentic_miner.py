"""Example: Running an Agentic Miner

This script shows how an autonomous agent (LLM-based, evolutionary, RL, etc.)
can participate in Carbon using the AgenticMiner + tool interface.

It demonstrates the full loop:
- Get challenges
- Get symbolically recommended priors
- Propose + locally validate strategies
- Submit when confident
- Learn from results over time
"""

import asyncio

from carbon.miner.agent import AgenticMiner
from carbon.miner.agent_tools import CarbonMiningTools


async def main():
    # In a real setup, you would initialize the CarbonClient with your hotkey/wallet
    # from carbon.miner.client import CarbonClient
    # client = CarbonClient(hotkey="5F...")

    # For this example we use a mock or placeholder client
    # Replace this with a real client in production
    class MockClient:
        async def get_active_challenges(self):
            return ["poisson_2d_v1", "darcy_2d_v1", "burgers_v1"]

        async def get_priors(self, challenge_id):
            return {
                "recommended_backbone": "fno",
                "loss_vector": {
                    "pde_residual": 1.0,
                    "conservation_mass": 1.2,
                    "boundary": 0.65,
                },
            }

        async def validate_locally(self, strategy, challenge_id, quick=True):
            # Simulate local validation
            return {
                "estimated_score": 0.09,
                "physics_gates_passed": True,
                "diagnostics": "Looks promising",
            }

        async def submit(self, challenge_id, strategy):
            return {"status": "submitted", "rank": 2, "reward": 12.4}

    client = MockClient()
    miner = AgenticMiner(client)
    tools = CarbonMiningTools(miner)

    print("=== Starting Agentic Mining Loop ===\n")

    challenges = await tools.list_challenges()
    print("Active challenges:", challenges["challenges"])

    for challenge_id in challenges["challenges"]:
        print(f"\n--- Working on {challenge_id} ---")

        # Get recommended priors
        priors = await tools.get_priors(challenge_id)
        print("Using priors:", priors)

        # Propose a strategy (starts from priors + light mutation)
        strategy = await tools.propose_strategy(challenge_id)

        # Self-test locally first
        validation = await tools.validate_strategy(strategy, challenge_id)
        print("Local validation result:", validation)

        # Only submit if it looks good
        if validation.get("estimated_score", 0) > 0.06:
            print("Submitting promising strategy...")
            result = await tools.submit_strategy(strategy, challenge_id)
            print("Submission result:", result)
        else:
            print("Strategy not strong enough yet. Skipping submission.")

    print("\n=== Agentic Mining Loop Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
