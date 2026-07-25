"""Example MCP Client for Carbon Mining Tools.

This script demonstrates how an agent (especially an LLM-based one)
can interact with the Carbon MCP-style server.

It shows tool discovery and sequential tool usage.
"""

import asyncio
import httpx


BASE_URL = "http://localhost:8000"


async def call_tool(tool_name: str, payload: dict = None):
    url = f"{BASE_URL}/tools/{tool_name}"
    async with httpx.AsyncClient() as client:
        if payload:
            response = await client.post(url, json=payload)
        else:
            response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def main():
    print("=== Carbon MCP Client Example ===\n")

    # 1. List active challenges
    challenges = await call_tool("list_challenges")
    print("Active challenges:", challenges)

    challenge_id = challenges[0] if challenges else "poisson_2d_v1"
    print(f"\nWorking on challenge: {challenge_id}")

    # 2. Get priors for the challenge
    priors = await call_tool("get_priors", {"challenge_id": challenge_id})
    print("Priors:", priors)

    # 3. Propose a strategy
    strategy_response = await call_tool(
        "propose_strategy", {"challenge_id": challenge_id}
    )
    strategy = strategy_response.get("strategy", strategy_response)
    print("Proposed strategy (truncated):", str(strategy)[:200], "...")

    # 4. Validate the strategy locally
    validation = await call_tool(
        "validate_strategy",
        {
            "strategy": strategy,
            "challenge_id": challenge_id,
            "quick": True,
        },
    )
    print("Validation result:", validation)

    score = validation.get("estimated_score", 0.0)

    # 5. Submit if score looks good
    if score >= 0.07:
        print("\nScore looks good. Submitting...")
        result = await call_tool(
            "submit_strategy",
            {"strategy": strategy, "challenge_id": challenge_id},
        )
        print("Submission result:", result)
    else:
        print("\nScore too low. Not submitting.")

    print("\n=== MCP Client Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
