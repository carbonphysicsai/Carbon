"""Trusted provider protocols for the bounded Wave-A MCP service."""

from __future__ import annotations

from typing import Protocol

from carbon.fees import RequesterIdentity
from carbon.registry import ChallengeKey
from carbon.schema import ValidationResult

from .model import McpTool, PublishedPrior, PublishedScaffold, StructuralEstimate


class PriorProvider(Protocol):
    """Publish one coarse public prior for an exact Challenge."""

    def get_prior(self, challenge_key: ChallengeKey) -> PublishedPrior: ...


class ScaffoldProvider(Protocol):
    """Publish one declarative starter Strategy for an exact Challenge."""

    def get_scaffold(
        self,
        challenge_key: ChallengeKey,
        scaffold_id: str | None,
    ) -> PublishedScaffold: ...


class EstimateProvider(Protocol):
    """Interpret an exact A2-valid Strategy against a published prior."""

    def estimate(
        self,
        challenge_key: ChallengeKey,
        prior: PublishedPrior,
        strategy: dict[str, object],
        validation: ValidationResult,
    ) -> StructuralEstimate: ...


class QueryBudgetGate(Protocol):
    """Apply trusted requester policy before one result lookup."""

    def consume(self, requester: RequesterIdentity, tool: McpTool) -> None: ...
