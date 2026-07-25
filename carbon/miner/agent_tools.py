"""MCP-style Tool Interface for AgenticMiner (with JSON schemas).

This module provides well-structured, LLM-friendly tools for mining.
It includes proper input/output schemas and rich descriptions.

Designed to be easily used directly or wrapped as MCP / LangChain tools.
"""

from typing import Dict, Any, Optional

from pydantic import BaseModel, Field

from carbon.miner.agent import AgenticMiner


# ============================================================
# Input / Output Schemas
# ============================================================

class ListChallengesOutput(BaseModel):
    challenges: list[str] = Field(..., description="List of currently active challenge IDs")


class GetPriorsInput(BaseModel):
    challenge_id: str = Field(..., description="ID of the challenge to get priors for (e.g. 'poisson_2d_v1')")


class GetPriorsOutput(BaseModel):
    recommended_backbone: Optional[str] = Field(None, description="Recommended neural operator backbone")
    loss_vector: Optional[dict] = Field(None, description="Symbolically/causally recommended loss weights")
    curriculum: Optional[dict] = Field(None, description="Recommended curriculum settings")
    notes: Optional[str] = Field(None, description="Additional guidance from the Landscape Agent")


class ProposeStrategyInput(BaseModel):
    challenge_id: str = Field(..., description="Challenge to generate a strategy for")
    base_strategy: Optional[dict] = Field(None, description="Optional existing strategy to mutate from")


class ProposeStrategyOutput(BaseModel):
    strategy: dict = Field(..., description="Proposed training strategy JSON")
    rationale: Optional[str] = Field(None, description="Why this strategy was proposed (from priors or mutation)")


class ValidateStrategyInput(BaseModel):
    strategy: dict = Field(..., description="Strategy JSON to validate locally")
    challenge_id: str = Field(..., description="Challenge this strategy is for")
    quick: bool = Field(True, description="Whether to run a fast/approximate validation")


class ValidateStrategyOutput(BaseModel):
    estimated_score: float = Field(..., description="Estimated performance score from local validation")
    physics_gates_passed: bool = Field(..., description="Whether all hard physics gates passed")
    diagnostics: Optional[str] = Field(None, description="Additional feedback or warnings")


class SubmitStrategyInput(BaseModel):
    strategy: dict = Field(..., description="Strategy to submit to the network")
    challenge_id: str = Field(..., description="Challenge to submit for")


class SubmitStrategyOutput(BaseModel):
    status: str = Field(..., description="Submission status (submitted, rejected, etc.)")
    rank: Optional[int] = Field(None, description="Current rank after submission")
    reward: Optional[float] = Field(None, description="Estimated reward from this submission")


class GetRecentResultsInput(BaseModel):
    limit: int = Field(10, description="Number of recent results to return")


class GetRecentResultsOutput(BaseModel):
    recent_results: list[dict] = Field(..., description="List of recent submission results and scores")


# ============================================================
# Tool Wrapper Class
# ============================================================

class CarbonMiningTools:
    """
    Structured, LLM-friendly tools for participating in Carbon as an agent.

    These tools are designed with clear schemas and rich descriptions
    so that language models and agent frameworks can use them reliably.
    """

    def __init__(self, miner: AgenticMiner):
        self.miner = miner

    async def list_challenges(self) -> ListChallengesOutput:
        """List all currently active challenges in the subnet."""
        challenges = await self.miner.get_challenges()
        return ListChallengesOutput(challenges=challenges)

    async def get_priors(self, challenge_id: str) -> GetPriorsOutput:
        """
        Retrieve symbolically and causally recommended configuration priors
        for a given challenge. These come from the Landscape Agent's analysis
        of past successful strategies.
        """
        priors = await self.miner.get_priors(challenge_id)
        return GetPriorsOutput(**priors)

    async def propose_strategy(
        self, challenge_id: str, base_strategy: Optional[dict] = None
    ) -> ProposeStrategyOutput:
        """
        Generate a new strategy for a challenge.

        If no base_strategy is provided, the tool starts from Landscape priors
        and applies intelligent mutation for exploration.
        """
        strategy = await self.miner.propose_strategy(
            challenge_id=challenge_id,
            base_strategy=base_strategy,
        )
        return ProposeStrategyOutput(strategy=strategy, rationale="Generated from priors + light mutation")

    async def validate_strategy(
        self, strategy: dict, challenge_id: str, quick: bool = True
    ) -> ValidateStrategyOutput:
        """
        Perform fast local validation of a strategy before submitting.

        Returns estimated score and whether the strategy passes basic
        physics gate checks. Use this to iterate without paying fees.
        """
        result = await self.miner.validate_locally(
            strategy=strategy,
            challenge_id=challenge_id,
            quick=quick,
        )
        return ValidateStrategyOutput(**result)

    async def submit_strategy(self, strategy: dict, challenge_id: str) -> SubmitStrategyOutput:
        """
        Submit a validated strategy to the Carbon network.

        Only call this after using `validate_strategy` and confirming
        the estimated score looks promising.
        """
        result = await self.miner.submit(strategy=strategy, challenge_id=challenge_id)
        return SubmitStrategyOutput(**result)

    async def get_my_recent_results(self, limit: int = 10) -> GetRecentResultsOutput:
        """
        Retrieve recent submission results and scores for this miner.

        Useful for learning and improving future strategies.
        """
        results = await self.miner.get_recent_performance(limit=limit)
        return GetRecentResultsOutput(recent_results=results)
