"""B-E4 orchestration guards over the existing research and official planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from carbon.mcp.service import McpService
from carbon.research import LocalResearchService, ServiceCall, ServiceReply

from .model import (
    AgentProfile,
    ExperimentalArm,
    GauntletPreregistration,
    MatchedBudget,
    RunIdentity,
)


class AgentDriver(Protocol):
    profile: AgentProfile

    def run(
        self, session: AgentSession, identity: RunIdentity, budget: MatchedBudget
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class AgentSession:
    """The only two planes available to a B-E4 agent driver."""

    research_service: LocalResearchService
    official_fixture_service: McpService

    def __post_init__(self) -> None:
        if (
            type(self) is not AgentSession
            or type(self.research_service) is not LocalResearchService
            or type(self.official_fixture_service) is not McpService
        ):
            raise TypeError("session requires exact B-07G and Wave-A services")

    def research_call(self, call: ServiceCall) -> ServiceReply:
        return self.research_service.call(call)

    def official_call(self, operation: str, payload: dict[str, object]) -> object:
        if operation not in ("submit", "get_submission_result"):
            raise GauntletPreflightError(
                "only the unchanged official operations are available"
            )
        return self.official_fixture_service.call(operation, payload)


class GauntletPreflightError(ValueError):
    pass


def validate_experiment_matrix(
    *,
    preregistration: GauntletPreregistration,
    budgets: tuple[MatchedBudget, ...],
    runs: tuple[RunIdentity, ...],
) -> None:
    """Validate a declared non-qualifying matrix without interpreting values.

    This structural check neither verifies owner ratification nor validates the
    B-07D3 pack-to-receipt authorization. Both remain separate owner seams.
    """

    if type(preregistration) is not GauntletPreregistration:
        raise TypeError("exact preregistration is required")
    if not preregistration.is_complete:
        raise GauntletPreflightError(
            "declared experiment matrix blocked: "
            + ",".join(preregistration.missing_inputs)
        )
    if type(budgets) is not tuple or any(
        type(item) is not MatchedBudget for item in budgets
    ):
        raise TypeError("budgets require exact MatchedBudget values")
    if {item.profile for item in budgets} != set(AgentProfile) or len(budgets) != len(
        AgentProfile
    ):
        raise GauntletPreflightError(
            "one preregistered budget per representative profile is required"
        )
    if type(runs) is not tuple or any(type(item) is not RunIdentity for item in runs):
        raise TypeError("runs require exact RunIdentity values")
    try:
        runs = tuple(
            RunIdentity(
                item.profile,
                item.arm,
                item.replicate,
                item.prior_pack_ref,
                item.test_only_authorization_ref,
            )
            for item in runs
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise GauntletPreflightError(
            "every run identity must survive exact nested reconstruction"
        ) from exc
    replicates = {item.replicate for item in runs}
    expected = {
        (profile, arm, replicate)
        for profile in AgentProfile
        for arm in ExperimentalArm
        for replicate in replicates
    }
    actual = {(item.profile, item.arm, item.replicate) for item in runs}
    if not replicates or actual != expected or len(runs) != len(expected):
        raise GauntletPreflightError(
            "the profile-by-arm replicate matrix must be exact and complete"
        )
    v2 = tuple(item for item in runs if item.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR)
    pins = {(item.prior_pack_ref, item.test_only_authorization_ref) for item in v2}
    if len(pins) != 1:
        raise GauntletPreflightError(
            "every v2 run must freeze one exact TEST_ONLY pack/receipt pair"
        )


def validate_integrity_matrix(observations: tuple[object, ...]) -> None:
    """Require one fixture observation for every ticket-named attack class."""

    from .model import IntegrityCase, IntegrityObservation

    if type(observations) is not tuple or any(
        type(item) is not IntegrityObservation for item in observations
    ):
        raise TypeError("integrity matrix requires exact observations")
    cases = tuple(item.case for item in observations)
    if len(cases) != len(IntegrityCase) or set(cases) != set(IntegrityCase):
        raise GauntletPreflightError("the exact B-E4 integrity matrix is incomplete")
