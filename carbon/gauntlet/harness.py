"""B-E4 orchestration guards over the existing research and official planes."""

from __future__ import annotations

import hashlib
from typing import Protocol

from carbon.fees import RequesterIdentity, SubmissionRequestError
from carbon.mcp.model import McpCall
from carbon.mcp.service import McpService
from carbon.research import LocalResearchService, ServiceCall, ServiceReply

from .meter import NormalizedComputeReceipt, PolicyWorkKind, PolicyWorkMeter
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


class AgentSession:
    """Opaque two-plane facade for fixed, trusted fixture-policy drivers.

    This is a capability-reducing in-process facade, not a Python sandbox.  No
    arbitrary participant program is executed by the B-E4 fixture harness.
    """

    __slots__ = (
        "__meter",
        "__official_fixture_service",
        "__requester_identity",
        "__research_service",
    )

    def __init__(
        self,
        research_service: LocalResearchService,
        official_fixture_service: McpService,
        requester_identity: RequesterIdentity,
        meter: PolicyWorkMeter,
    ) -> None:
        if (
            type(self) is not AgentSession
            or type(research_service) is not LocalResearchService
            or type(official_fixture_service) is not McpService
            or type(requester_identity) is not RequesterIdentity
            or type(meter) is not PolicyWorkMeter
        ):
            raise TypeError(
                "session requires exact B-07G, Wave-A, requester, and meter values"
            )
        try:
            requester = RequesterIdentity(requester_identity.value)
        except (AttributeError, SubmissionRequestError, TypeError, ValueError):
            raise TypeError("session requester identity is invalid") from None
        object.__setattr__(self, "_AgentSession__research_service", research_service)
        object.__setattr__(
            self, "_AgentSession__official_fixture_service", official_fixture_service
        )
        object.__setattr__(self, "_AgentSession__requester_identity", requester)
        object.__setattr__(self, "_AgentSession__meter", meter)

    def __repr__(self) -> str:
        return "AgentSession(<bounded-fixture-capabilities>)"

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("AgentSession is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("AgentSession is immutable")

    def __getstate__(self) -> object:
        raise TypeError("AgentSession does not support serialization")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("AgentSession does not support serialization")

    def research_call(self, call: ServiceCall) -> ServiceReply:
        if type(call) is not ServiceCall:
            raise TypeError("research calls require the exact B-07S envelope")
        meter = object.__getattribute__(self, "_AgentSession__meter")
        meter.record(PolicyWorkKind.SERVICE_OPERATION)
        service = object.__getattribute__(self, "_AgentSession__research_service")
        return service.call(call)

    def official_call(self, call: McpCall) -> object:
        if type(call) is not McpCall:
            raise TypeError("official calls require the exact Wave-A envelope")
        try:
            operation = call.tool
        except AttributeError:
            raise GauntletPreflightError("official call is malformed") from None
        if type(operation) is not str or operation not in (
            "submit",
            "get_submission_result",
        ):
            raise GauntletPreflightError(
                "only the unchanged official operations are available"
            )
        meter = object.__getattribute__(self, "_AgentSession__meter")
        meter.record(PolicyWorkKind.SERVICE_OPERATION)
        service = object.__getattribute__(
            self, "_AgentSession__official_fixture_service"
        )
        requester = object.__getattribute__(self, "_AgentSession__requester_identity")
        return service.call(call, RequesterIdentity(requester.value))

    def normalized_compute(self) -> NormalizedComputeReceipt:
        meter = object.__getattribute__(self, "_AgentSession__meter")
        return meter.snapshot()

    def binds_meter(self, meter: PolicyWorkMeter) -> bool:
        """Return whether a trusted orchestrator supplied this run's meter.

        This reveals no service or requester capability.  It prevents a driver
        from reporting work into a different counter than the one attached to
        its exact service session.
        """

        if type(meter) is not PolicyWorkMeter:
            raise TypeError("meter binding checks require the exact meter type")
        return meter is object.__getattribute__(self, "_AgentSession__meter")

    def binds_research_service(self, service: LocalResearchService) -> bool:
        """Check trusted orchestration correlation without exposing capability."""

        if type(service) is not LocalResearchService:
            raise TypeError("research binding checks require the exact service")
        return service is object.__getattribute__(
            self, "_AgentSession__research_service"
        )

    def binds_official_service(
        self, service: McpService, requester: RequesterIdentity
    ) -> bool:
        """Check the exact A7 facade/requester installed for this session."""

        if type(service) is not McpService or type(requester) is not RequesterIdentity:
            raise TypeError("official binding checks require exact values")
        current = object.__getattribute__(self, "_AgentSession__requester_identity")
        return (
            service
            is object.__getattribute__(self, "_AgentSession__official_fixture_service")
            and requester == current
        )

    def correlation_digest(self, plan_slot_digest: str) -> str:
        """Bind the non-secret session composition to one immutable run slot.

        The digest records which requester and concrete owner implementations
        were installed after the identity-only bridge checks succeeded.  It is
        correlation evidence, not a credential or an authorization receipt.
        """

        if (
            type(plan_slot_digest) is not str
            or not plan_slot_digest.startswith("sha256:")
            or len(plan_slot_digest) != 71
        ):
            raise TypeError("session correlation requires an exact plan digest")
        research = object.__getattribute__(self, "_AgentSession__research_service")
        official = object.__getattribute__(
            self, "_AgentSession__official_fixture_service"
        )
        requester = object.__getattribute__(self, "_AgentSession__requester_identity")
        meter = object.__getattribute__(self, "_AgentSession__meter")
        fields = (
            plan_slot_digest,
            requester.value,
            f"{type(research).__module__}.{type(research).__qualname__}",
            f"{type(official).__module__}.{type(official).__qualname__}",
            f"{type(meter).__module__}.{type(meter).__qualname__}",
        )
        return (
            "sha256:"
            + hashlib.sha256(
                b"carbon.be4.session-correlation.v1\x00"
                + b"\x00".join(item.encode("utf-8") for item in fields)
            ).hexdigest()
        )


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
