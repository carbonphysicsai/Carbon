"""Fixed, data-only fixture-agent proposal policies for B-E4 preflight.

These policies do not execute generated text, inspect repository files, or own
research-task/official lifecycle execution.  They transform an exact scaffold
received through B-07S into bounded Strategy data for a trusted orchestrator.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

from carbon.construction import ParameterCatalogRef
from carbon.registry import ChallengeKey
from carbon.research import (
    CanonicalWireError,
    DryValidateRequest,
    canonical_bytes,
    load_canonical,
)

from .meter import PolicyWorkKind, PolicyWorkMeter
from .model import AgentProfile

DRIVER_RUNTIME_ID = "carbon_be4_fixture_policy_runtime"
DRIVER_RUNTIME_VERSION = "2.0"
DRIVER_RUNTIME_DIGEST = (
    "sha256:"
    + hashlib.sha256(
        b"carbon.be4.fixture-policy-runtime.v2\x00"
        b"data-only-no-code-execution;replicate-bound-rng;"
        b"invalid-attempt-fails-closed"
    ).hexdigest()
)
FIXTURE_CORPUS_ID = "be4_frozen_fixture_method_corpus"
FIXTURE_CORPUS_VERSION = "1.0"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
_PROPOSAL_DOMAIN = b"carbon.be4.data-only-proposal.v1\x00"
_RNG_DOMAIN = b"carbon.be4.common-arm-rng.v2\x00"
_DRIVER_TRANSCRIPT_DOMAIN = b"carbon.be4.driver-transcript.v2\x00"


class ProposalDirection(str, Enum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    TOGGLE = "TOGGLE"


@dataclass(frozen=True, slots=True)
class ProposalHint:
    """Arm material normalized to a data-only proposal preference."""

    surface_id: str
    direction: ProposalDirection
    replacement_token: str | None = None

    def __post_init__(self) -> None:
        if (
            type(self) is not ProposalHint
            or type(self.surface_id) is not str
            or _IDENTIFIER.fullmatch(self.surface_id) is None
            or type(self.direction) is not ProposalDirection
            or (
                self.replacement_token is not None
                and (
                    type(self.replacement_token) is not str
                    or _IDENTIFIER.fullmatch(self.replacement_token) is None
                )
            )
        ):
            raise TypeError("proposal hint requires exact bounded values")


@dataclass(frozen=True, slots=True)
class FixtureMethodCorpusEntry:
    method_id: str
    surface_keyword: str
    direction: ProposalDirection

    def __post_init__(self) -> None:
        if (
            type(self) is not FixtureMethodCorpusEntry
            or type(self.method_id) is not str
            or _IDENTIFIER.fullmatch(self.method_id) is None
            or type(self.surface_keyword) is not str
            or not self.surface_keyword
            or not self.surface_keyword.isascii()
            or type(self.direction) is not ProposalDirection
        ):
            raise TypeError("fixture corpus entry is invalid")


FIXTURE_METHOD_CORPUS = (
    FixtureMethodCorpusEntry(
        "bounded_sampling_probe", "sampling", ProposalDirection.INCREASE
    ),
    FixtureMethodCorpusEntry(
        "bounded_curriculum_probe", "curriculum", ProposalDirection.INCREASE
    ),
    FixtureMethodCorpusEntry(
        "bounded_feature_probe", "feature", ProposalDirection.INCREASE
    ),
)
FIXTURE_CORPUS_DIGEST = (
    "sha256:"
    + hashlib.sha256(
        b"carbon.be4.fixture-method-corpus.v1\x00"
        + b";".join(
            f"{item.method_id}:{item.surface_keyword}:{item.direction.value}".encode(
                "ascii"
            )
            for item in FIXTURE_METHOD_CORPUS
        )
    ).hexdigest()
)

REGISTERED_EFFECTFUL_SURFACES = (
    "fixture_sampling_level",
    "fixture_curriculum_emphasis",
    "fixture_feature_degree",
)


@dataclass(frozen=True, slots=True)
class UInt64SurfaceDomain:
    surface_id: str
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if (
            type(self) is not UInt64SurfaceDomain
            or type(self.surface_id) is not str
            or _IDENTIFIER.fullmatch(self.surface_id) is None
            or type(self.minimum) is not int
            or type(self.maximum) is not int
            or self.minimum != 1
            or self.maximum != 2
        ):
            raise TypeError("fixture surface domain must be exact UINT64 1..2")


def _strategy_domain_digest(
    parameter_catalog_ref: ParameterCatalogRef,
    surfaces: tuple[UInt64SurfaceDomain, ...],
) -> str:
    ref = parameter_catalog_ref
    payload = "|".join(
        (
            ref.challenge_key.challenge_id,
            ref.challenge_key.version,
            ref.object_id,
            ref.object_version,
            ref.schema_version,
            ref.canonicalization_profile,
            ref.content_digest,
            *(f"{item.surface_id}:{item.minimum}:{item.maximum}" for item in surfaces),
        )
    ).encode("ascii")
    return (
        "sha256:"
        + hashlib.sha256(
            b"carbon.be4.fixture-strategy-domain.v1\x00" + payload
        ).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class FixtureStrategyDomain:
    """Arm-neutral public fixture vocabulary bound to the B-02B catalog ref."""

    parameter_catalog_ref: ParameterCatalogRef
    surfaces: tuple[UInt64SurfaceDomain, ...]
    content_digest: str

    def __post_init__(self) -> None:
        if (
            type(self) is not FixtureStrategyDomain
            or type(self.parameter_catalog_ref) is not ParameterCatalogRef
            or type(self.surfaces) is not tuple
            or any(type(item) is not UInt64SurfaceDomain for item in self.surfaces)
            or tuple(item.surface_id for item in self.surfaces)
            != REGISTERED_EFFECTFUL_SURFACES
            or type(self.content_digest) is not str
            or _DIGEST.fullmatch(self.content_digest) is None
        ):
            raise TypeError(
                "fixture strategy domain is not the registered exact family"
            )
        if self.content_digest != _strategy_domain_digest(
            self.parameter_catalog_ref, self.surfaces
        ):
            raise ValueError("fixture strategy domain digest does not bind its content")


def fixture_strategy_domain(
    parameter_catalog_ref: ParameterCatalogRef,
) -> FixtureStrategyDomain:
    if type(parameter_catalog_ref) is not ParameterCatalogRef:
        raise TypeError("strategy domain requires an exact ParameterCatalogRef")
    surfaces = tuple(
        UInt64SurfaceDomain(surface, 1, 2) for surface in REGISTERED_EFFECTFUL_SURFACES
    )
    return FixtureStrategyDomain(
        parameter_catalog_ref,
        surfaces,
        _strategy_domain_digest(parameter_catalog_ref, surfaces),
    )


@dataclass(frozen=True, slots=True)
class FixtureDriverRef:
    profile: AgentProfile
    driver_id: str
    driver_version: str
    runtime_id: str
    runtime_version: str
    runtime_digest: str
    policy_digest: str
    corpus_digest: str | None

    def __post_init__(self) -> None:
        if (
            type(self) is not FixtureDriverRef
            or type(self.profile) is not AgentProfile
            or any(
                type(value) is not str or _IDENTIFIER.fullmatch(value) is None
                for value in (
                    self.driver_id,
                    self.driver_version,
                    self.runtime_id,
                    self.runtime_version,
                )
            )
            or any(
                type(value) is not str or _DIGEST.fullmatch(value) is None
                for value in (self.runtime_digest, self.policy_digest)
            )
            or (
                self.corpus_digest is not None
                and (
                    type(self.corpus_digest) is not str
                    or _DIGEST.fullmatch(self.corpus_digest) is None
                )
            )
            or self.runtime_id != DRIVER_RUNTIME_ID
            or self.runtime_version != DRIVER_RUNTIME_VERSION
            or self.runtime_digest != DRIVER_RUNTIME_DIGEST
            or (self.profile is AgentProfile.LITERATURE_GROUNDED)
            != (self.corpus_digest == FIXTURE_CORPUS_DIGEST)
        ):
            raise TypeError("fixture driver reference is invalid")


class CommonArmRng:
    """Domain-separated replicate stream whose seed has no arm field."""

    __slots__ = ("__block_id", "__design_digest", "__profile", "__replicate")

    def __init__(
        self,
        design_digest: str,
        profile: AgentProfile,
        block_id: str,
        replicate: int = 0,
    ) -> None:
        if (
            type(self) is not CommonArmRng
            or type(design_digest) is not str
            or _DIGEST.fullmatch(design_digest) is None
            or type(profile) is not AgentProfile
            or type(block_id) is not str
            or _IDENTIFIER.fullmatch(block_id) is None
            or type(replicate) is not int
            or not 0 <= replicate < 1 << 63
        ):
            raise TypeError("common-arm RNG identity is invalid")
        object.__setattr__(self, "_CommonArmRng__design_digest", design_digest)
        object.__setattr__(self, "_CommonArmRng__profile", profile)
        object.__setattr__(self, "_CommonArmRng__block_id", block_id)
        object.__setattr__(self, "_CommonArmRng__replicate", replicate)

    def draw_uint64(self, role: str, draw_index: int, meter: PolicyWorkMeter) -> int:
        if (
            type(role) is not str
            or _IDENTIFIER.fullmatch(role) is None
            or type(draw_index) is not int
            or not 0 <= draw_index < 1 << 63
            or type(meter) is not PolicyWorkMeter
        ):
            raise TypeError("RNG draw identity is invalid")
        meter.record(PolicyWorkKind.RNG_DRAW)
        fields = (
            object.__getattribute__(self, "_CommonArmRng__design_digest"),
            object.__getattribute__(self, "_CommonArmRng__profile").value,
            object.__getattribute__(self, "_CommonArmRng__block_id"),
            str(object.__getattribute__(self, "_CommonArmRng__replicate")),
            role,
            str(draw_index),
        )
        digest = hashlib.sha256(
            _RNG_DOMAIN + b"\x00".join(item.encode("ascii") for item in fields)
        ).digest()
        return int.from_bytes(digest[:8], "big")

    @property
    def stream_digest(self) -> str:
        fields = (
            object.__getattribute__(self, "_CommonArmRng__design_digest"),
            object.__getattribute__(self, "_CommonArmRng__profile").value,
            object.__getattribute__(self, "_CommonArmRng__block_id"),
            str(object.__getattribute__(self, "_CommonArmRng__replicate")),
        )
        return (
            "sha256:"
            + hashlib.sha256(
                _RNG_DOMAIN + b"\x00".join(item.encode("ascii") for item in fields)
            ).hexdigest()
        )


class DataOnlyStrategyProposal:
    """Owned canonical Strategy data; it cannot contain executable behavior."""

    __slots__ = (
        "__attempt",
        "__challenge_key",
        "__payload",
        "__strategy_digest",
        "__surface_id",
    )

    def __init__(
        self,
        challenge_key: ChallengeKey,
        attempt: int,
        surface_id: str,
        strategy: dict[str, object],
    ) -> None:
        if (
            type(self) is not DataOnlyStrategyProposal
            or type(challenge_key) is not ChallengeKey
            or type(attempt) is not int
            or not 1 <= attempt <= 8
            or type(surface_id) is not str
            or _IDENTIFIER.fullmatch(surface_id) is None
            or type(strategy) is not dict
        ):
            raise TypeError("data-only proposal identity is invalid")
        try:
            request = DryValidateRequest(challenge_key, strategy)
            payload = canonical_bytes(request)
            owned = load_canonical(payload, DryValidateRequest)
        except (CanonicalWireError, TypeError, ValueError):
            raise TypeError("proposal must be canonical Strategy data") from None
        if type(owned) is not DryValidateRequest:
            raise TypeError("proposal reconstruction failed")
        object.__setattr__(
            self, "_DataOnlyStrategyProposal__challenge_key", owned.challenge_key
        )
        object.__setattr__(self, "_DataOnlyStrategyProposal__attempt", attempt)
        object.__setattr__(self, "_DataOnlyStrategyProposal__surface_id", surface_id)
        object.__setattr__(self, "_DataOnlyStrategyProposal__payload", payload)
        object.__setattr__(
            self,
            "_DataOnlyStrategyProposal__strategy_digest",
            "sha256:" + hashlib.sha256(_PROPOSAL_DOMAIN + payload).hexdigest(),
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("data-only proposal state is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("data-only proposal state is immutable")

    @property
    def challenge_key(self) -> ChallengeKey:
        return object.__getattribute__(self, "_DataOnlyStrategyProposal__challenge_key")

    @property
    def attempt(self) -> int:
        return object.__getattribute__(self, "_DataOnlyStrategyProposal__attempt")

    @property
    def surface_id(self) -> str:
        return object.__getattribute__(self, "_DataOnlyStrategyProposal__surface_id")

    @property
    def strategy_digest(self) -> str:
        return object.__getattribute__(
            self, "_DataOnlyStrategyProposal__strategy_digest"
        )

    @property
    def strategy(self) -> dict[str, object]:
        request = load_canonical(
            object.__getattribute__(self, "_DataOnlyStrategyProposal__payload"),
            DryValidateRequest,
        )
        assert type(request) is DryValidateRequest and type(request.strategy) is dict
        return request.strategy

    def __repr__(self) -> str:
        return "DataOnlyStrategyProposal(<canonical-strategy>)"


def _framed(parts: tuple[bytes, ...]) -> bytes:
    return b"".join(len(part).to_bytes(8, "big") + part for part in parts)


def _validated_proposal_payload(proposal: DataOnlyStrategyProposal) -> bytes:
    if type(proposal) is not DataOnlyStrategyProposal:
        raise TypeError("driver transcript requires exact data-only proposals")
    try:
        challenge_key = proposal.challenge_key
        attempt = proposal.attempt
        surface_id = proposal.surface_id
        strategy_digest = proposal.strategy_digest
        payload = object.__getattribute__(
            proposal, "_DataOnlyStrategyProposal__payload"
        )
    except AttributeError:
        raise ValueError("data-only proposal state is incomplete") from None
    if (
        type(challenge_key) is not ChallengeKey
        or type(attempt) is not int
        or not 1 <= attempt <= 8
        or type(surface_id) is not str
        or _IDENTIFIER.fullmatch(surface_id) is None
        or type(strategy_digest) is not str
        or _DIGEST.fullmatch(strategy_digest) is None
        or type(payload) is not bytes
    ):
        raise ValueError("data-only proposal state is invalid")
    try:
        request = load_canonical(payload, DryValidateRequest)
    except (CanonicalWireError, TypeError, ValueError):
        raise ValueError("data-only proposal payload is not canonical") from None
    if (
        type(request) is not DryValidateRequest
        or request.challenge_key != challenge_key
    ):
        raise ValueError("data-only proposal identity does not bind its payload")
    expected_digest = "sha256:" + hashlib.sha256(_PROPOSAL_DOMAIN + payload).hexdigest()
    if strategy_digest != expected_digest:
        raise ValueError("data-only proposal digest does not bind its payload")
    return payload


def _driver_transcript_digest(
    driver_ref: FixtureDriverRef,
    rng_stream_digest: str,
    proposals: tuple[DataOnlyStrategyProposal, ...],
) -> str:
    if type(driver_ref) is not FixtureDriverRef:
        raise TypeError("driver transcript requires an exact driver reference")
    try:
        checked_ref = FixtureDriverRef(
            driver_ref.profile,
            driver_ref.driver_id,
            driver_ref.driver_version,
            driver_ref.runtime_id,
            driver_ref.runtime_version,
            driver_ref.runtime_digest,
            driver_ref.policy_digest,
            driver_ref.corpus_digest,
        )
    except (TypeError, ValueError):
        raise ValueError("driver transcript reference is invalid") from None
    if checked_ref != driver_ref:
        raise ValueError("driver transcript reference is not nominal")
    if (
        type(rng_stream_digest) is not str
        or _DIGEST.fullmatch(rng_stream_digest) is None
        or type(proposals) is not tuple
        or not proposals
        or len(proposals) > 8
    ):
        raise TypeError("driver transcript structure is invalid")

    ref_parts = (
        checked_ref.profile.value.encode("ascii"),
        checked_ref.driver_id.encode("ascii"),
        checked_ref.driver_version.encode("ascii"),
        checked_ref.runtime_id.encode("ascii"),
        checked_ref.runtime_version.encode("ascii"),
        checked_ref.runtime_digest.encode("ascii"),
        checked_ref.policy_digest.encode("ascii"),
        (checked_ref.corpus_digest or "NONE").encode("ascii"),
        rng_stream_digest.encode("ascii"),
    )
    proposal_parts: list[bytes] = []
    for proposal in proposals:
        payload = _validated_proposal_payload(proposal)
        proposal_parts.append(
            _framed(
                (
                    proposal.challenge_key.challenge_id.encode("ascii"),
                    proposal.challenge_key.version.encode("ascii"),
                    str(proposal.attempt).encode("ascii"),
                    proposal.surface_id.encode("ascii"),
                    proposal.strategy_digest.encode("ascii"),
                    payload,
                )
            )
        )
    transcript = _framed((*ref_parts, *proposal_parts))
    return (
        "sha256:" + hashlib.sha256(_DRIVER_TRANSCRIPT_DOMAIN + transcript).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class DriverProposalBatch:
    driver_ref: FixtureDriverRef
    rng_stream_digest: str
    proposals: tuple[DataOnlyStrategyProposal, ...]
    transcript_digest: str

    def __post_init__(self) -> None:
        if (
            type(self) is not DriverProposalBatch
            or type(self.driver_ref) is not FixtureDriverRef
            or type(self.rng_stream_digest) is not str
            or _DIGEST.fullmatch(self.rng_stream_digest) is None
            or type(self.proposals) is not tuple
            or not self.proposals
            or len(self.proposals) > 8
            or any(
                type(item) is not DataOnlyStrategyProposal for item in self.proposals
            )
            or tuple(item.attempt for item in self.proposals)
            != tuple(range(1, len(self.proposals) + 1))
            or type(self.transcript_digest) is not str
            or _DIGEST.fullmatch(self.transcript_digest) is None
        ):
            raise TypeError("driver proposal batch is invalid")
        if self.transcript_digest != _driver_transcript_digest(
            self.driver_ref, self.rng_stream_digest, self.proposals
        ):
            raise ValueError(
                "driver proposal batch transcript does not bind its exact content"
            )


_POLICY_LABELS = {
    AgentProfile.PLANNER: "one-factor-agenda-then-canonical-selection",
    AgentProfile.CODE_GENERATING: "typed-strategy-data-with-compile-feedback",
    AgentProfile.EVOLUTIONARY: "fixed-population-common-rng-mutation",
    AgentProfile.LITERATURE_GROUNDED: "frozen-corpus-to-scaffold-family-map",
    AgentProfile.MINIMALIST: "first-canonical-applicable-proposal",
}


def _policy_digest(profile: AgentProfile) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            b"carbon.be4.fixture-driver-policy.v2\x00"
            + profile.value.encode("ascii")
            + b"\x00"
            + _POLICY_LABELS[profile].encode("ascii")
        ).hexdigest()
    )


def fixture_driver_ref(profile: AgentProfile) -> FixtureDriverRef:
    if type(profile) is not AgentProfile:
        raise TypeError("profile must use the exact B-E4 enum")
    return FixtureDriverRef(
        profile,
        "be4_" + profile.value.lower() + "_fixture_driver",
        "2.0",
        DRIVER_RUNTIME_ID,
        DRIVER_RUNTIME_VERSION,
        DRIVER_RUNTIME_DIGEST,
        _policy_digest(profile),
        FIXTURE_CORPUS_DIGEST if profile is AgentProfile.LITERATURE_GROUNDED else None,
    )


def _direction_for(
    surface: str, hints: tuple[ProposalHint, ...], fallback: ProposalDirection
) -> ProposalDirection:
    return next(
        (item.direction for item in hints if item.surface_id == surface), fallback
    )


def _replacement_for(surface: str, hints: tuple[ProposalHint, ...]) -> str | None:
    return next(
        (
            item.replacement_token
            for item in hints
            if item.surface_id == surface and item.replacement_token is not None
        ),
        None,
    )


def _changed_value(
    value: object,
    direction: ProposalDirection,
    replacement: str | None,
    domain: UInt64SurfaceDomain,
) -> object:
    del replacement
    if (
        type(value) is not int
        or type(value) is bool
        or not domain.minimum <= value <= domain.maximum
    ):
        raise TypeError("scaffold value conflicts with the registered UINT64 domain")
    selected = (
        domain.minimum if direction is ProposalDirection.DECREASE else domain.maximum
    )
    if selected == value:
        selected = domain.maximum if value == domain.minimum else domain.minimum
    return selected


class FixtureAgentDriver:
    """One of five trusted fixture preflight policies, reused across arms.

    This in-process policy is not an agent sandbox and does not execute
    participant-provided code.
    """

    __slots__ = ("__profile", "__ref")

    def __init__(self, profile: AgentProfile) -> None:
        if type(self) is not FixtureAgentDriver or type(profile) is not AgentProfile:
            raise TypeError("fixture driver identity is invalid")
        object.__setattr__(self, "_FixtureAgentDriver__profile", profile)
        object.__setattr__(
            self, "_FixtureAgentDriver__ref", fixture_driver_ref(profile)
        )

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("fixture driver state is immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("fixture driver state is immutable")

    @property
    def profile(self) -> AgentProfile:
        return object.__getattribute__(self, "_FixtureAgentDriver__profile")

    @property
    def ref(self) -> FixtureDriverRef:
        return object.__getattribute__(self, "_FixtureAgentDriver__ref")

    def propose(
        self,
        *,
        challenge_key: ChallengeKey,
        scaffold_strategy: dict[str, object],
        strategy_domain: FixtureStrategyDomain,
        hints: tuple[ProposalHint, ...],
        rng: CommonArmRng,
        meter: PolicyWorkMeter,
        attempt_limit: int = 8,
    ) -> DriverProposalBatch:
        if (
            type(challenge_key) is not ChallengeKey
            or type(scaffold_strategy) is not dict
            or type(strategy_domain) is not FixtureStrategyDomain
            or type(hints) is not tuple
            or any(type(item) is not ProposalHint for item in hints)
            or len({item.surface_id for item in hints}) != len(hints)
            or type(rng) is not CommonArmRng
            or type(meter) is not PolicyWorkMeter
            or type(attempt_limit) is not int
            or not 1 <= attempt_limit <= 8
        ):
            raise TypeError("driver proposal inputs are invalid")
        profile = self.profile
        driver_ref = self.ref
        if driver_ref != fixture_driver_ref(profile):
            raise ValueError(
                "fixture driver state does not match its canonical profile"
            )
        meter.record(PolicyWorkKind.POLICY_TRANSITION)
        for _ in hints:
            meter.record(PolicyWorkKind.PRIOR_ITEM_INSPECTION)
        try:
            owned = load_canonical(
                canonical_bytes(DryValidateRequest(challenge_key, scaffold_strategy)),
                DryValidateRequest,
            ).strategy
            parameters = owned["parameters"]
        except (CanonicalWireError, KeyError, TypeError, ValueError):
            raise TypeError(
                "driver requires one exact B-07S scaffold Strategy"
            ) from None
        if type(parameters) is not dict or not parameters:
            raise TypeError("scaffold must expose registered parameter data")
        if strategy_domain.parameter_catalog_ref.challenge_key != challenge_key or any(
            item.surface_id not in parameters for item in strategy_domain.surfaces
        ):
            raise ValueError("arm-neutral strategy domain does not match the scaffold")
        domains = {item.surface_id: item for item in strategy_domain.surfaces}
        surfaces = list(REGISTERED_EFFECTFUL_SURFACES)
        for _ in surfaces:
            meter.record(PolicyWorkKind.SCAFFOLD_PARAMETER_INSPECTION)

        hinted = [item.surface_id for item in hints if item.surface_id in parameters]
        remaining = [item for item in surfaces if item not in hinted]
        if profile is AgentProfile.EVOLUTIONARY:
            ranked = sorted(
                remaining,
                key=lambda item: (
                    rng.draw_uint64(
                        "evolutionary_surface_order", surfaces.index(item), meter
                    ),
                    item,
                ),
            )
            order = hinted + ranked
        elif profile is AgentProfile.LITERATURE_GROUNDED:
            literature: list[str] = []
            for entry in FIXTURE_METHOD_CORPUS:
                meter.record(PolicyWorkKind.CORPUS_ITEM_INSPECTION)
                literature.extend(
                    item
                    for item in remaining
                    if entry.surface_keyword in item.casefold()
                    and item not in literature
                )
            order = (
                hinted
                + literature
                + [item for item in remaining if item not in literature]
            )
        elif profile is AgentProfile.CODE_GENERATING:
            order = hinted + list(reversed(remaining))
        else:
            order = hinted + remaining
        if profile is AgentProfile.MINIMALIST:
            order = order[:1]

        proposals: list[DataOnlyStrategyProposal] = []
        for attempt_slot, surface in enumerate(order, start=1):
            if attempt_slot > attempt_limit:
                break
            fallback = ProposalDirection.INCREASE
            if profile is AgentProfile.EVOLUTIONARY:
                fallback = (
                    ProposalDirection.INCREASE
                    if rng.draw_uint64(
                        "evolutionary_mutation_direction",
                        surfaces.index(surface),
                        meter,
                    )
                    % 2
                    else ProposalDirection.DECREASE
                )
            elif profile is AgentProfile.LITERATURE_GROUNDED:
                fallback = next(
                    (
                        item.direction
                        for item in FIXTURE_METHOD_CORPUS
                        if item.surface_keyword in surface.casefold()
                    ),
                    ProposalDirection.INCREASE,
                )
            direction = _direction_for(surface, hints, fallback)
            # Charge the declared slot before interpreting the scaffold value.
            # A malformed value therefore consumes its one-use attempt and
            # terminates this preflight instead of being skipped and renumbered.
            meter.record(PolicyWorkKind.ATTEMPT)
            try:
                value = _changed_value(
                    parameters[surface],
                    direction,
                    _replacement_for(surface, hints),
                    domains[surface],
                )
            except TypeError:
                raise ValueError(
                    f"preflight attempt {attempt_slot} was consumed by an invalid "
                    "registered scaffold value"
                ) from None
            candidate = dict(owned)
            candidate["parameters"] = {**parameters, surface: value}
            meter.record(PolicyWorkKind.CANDIDATE_PROPOSAL)
            proposal = DataOnlyStrategyProposal(
                challenge_key, attempt_slot, surface, candidate
            )
            proposals.append(proposal)
        if not proposals:
            raise ValueError("fixed driver could not form any data-only proposal")
        comparisons = max(0, len(proposals) - 1)
        if comparisons:
            meter.record(PolicyWorkKind.CANDIDATE_COMPARISON, comparisons)
        proposal_tuple = tuple(proposals)
        return DriverProposalBatch(
            driver_ref,
            rng.stream_digest,
            proposal_tuple,
            _driver_transcript_digest(driver_ref, rng.stream_digest, proposal_tuple),
        )


def fixture_agent_drivers() -> tuple[FixtureAgentDriver, ...]:
    return tuple(FixtureAgentDriver(profile) for profile in AgentProfile)


__all__ = (
    "DRIVER_RUNTIME_DIGEST",
    "DRIVER_RUNTIME_ID",
    "DRIVER_RUNTIME_VERSION",
    "FIXTURE_CORPUS_DIGEST",
    "FIXTURE_CORPUS_ID",
    "FIXTURE_CORPUS_VERSION",
    "FIXTURE_METHOD_CORPUS",
    "REGISTERED_EFFECTFUL_SURFACES",
    "CommonArmRng",
    "DataOnlyStrategyProposal",
    "DriverProposalBatch",
    "FixtureAgentDriver",
    "FixtureDriverRef",
    "FixtureMethodCorpusEntry",
    "FixtureStrategyDomain",
    "ProposalDirection",
    "ProposalHint",
    "UInt64SurfaceDomain",
    "fixture_agent_drivers",
    "fixture_driver_ref",
    "fixture_strategy_domain",
)
