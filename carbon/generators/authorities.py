"""Nominal B-03 authority boundaries and fixture execution capability.

Raw callbacks and Boolean verdicts are intentionally absent.  The concrete
fixture authority below owns only conspicuous, deterministic fixture issuance;
the exact scientific/statistical authority echoes are defined later in this
module and remain injected by callers with their own evidence refs.
"""

from __future__ import annotations

import hashlib
from _thread import LockType, allocate_lock
from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol

from carbon.authoring.canonical import (
    CanonicalRecord,
    CanonicalText,
    CanonicalUInt64,
    challenge_key_to_canonical,
    encode_value,
    owner_ref_to_canonical,
)
from carbon.authoring.cases import (
    CanonicalChallengeCase,
    CaseSourceKind,
    GeneratedCaseSource,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.evidence import (
    CensoringRecord,
    CensoringRecordRef,
    CensoringTrigger,
    CensoringTriggerKind,
    EvidenceScopeBinding,
    InfrastructureCensoringTrigger,
    ReplacementDecision,
    validate_censoring_against_plan,
)
from carbon.authoring.loading import (
    FixtureAuthoringCapability,
    FixtureOrigin,
)
from carbon.authoring.model import (
    ApplicabilityBinding,
    CensoringReason,
    canonical_set_tuple,
)
from carbon.authoring.populations import ExclusionContract, SupportContract
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    require_owner_ref,
)
from carbon.authoring.sampling import SamplingPlan
from carbon.registry.model import ChallengeKey
from carbon.seeding.commitment import create_fixture_official_exam_projection
from carbon.seeding.derive import derive_fixture_official_seed
from carbon.seeding.model import (
    DerivedSeed,
    FixtureOfficialContext,
    FixtureOfficialExamProjection,
    SeedPin,
)
from carbon.seeding.provider import (
    DeterministicFixtureProvider,
    acquire_fixture_official_context,
)

from .errors import (
    GeneratorInputCode,
    GeneratorServiceCode,
    GeneratorServiceError,
    GeneratorValidationError,
)
from .refs import (
    AttemptAccountingDecisionRef,
    CensoringDecisionRef,
    CensoringVerdictRef,
    GeneratorReplayCommitmentRef,
    IntendedUnitLinkDecisionRef,
    SupportExclusionDecisionRef,
)

_REPLAY_SCHEME_ID = "carbon_generator_fixture_replay"
_REPLAY_SCHEME_VERSION = "1.0"
_MAX_UINT64 = (1 << 64) - 1
_GENERATION_GRANT_TOKEN = object()
_REPLAY_DERIVATION_CAPABILITY_TOKEN = object()
_REPLAY_PROBE_AUTHORITY_TOKEN = object()


def _exact(value: object, expected: type, path: str) -> object:
    if type(value) is not expected:
        raise GeneratorValidationError(GeneratorInputCode.WRONG_TYPE, path=path)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise GeneratorValidationError(GeneratorInputCode.WRONG_TYPE, path=path)
    malformed = False
    try:
        result = ChallengeKey(value.challenge_id, value.version)
    except (TypeError, ValueError):
        malformed = True
        result = None
    if malformed:
        raise GeneratorValidationError(
            GeneratorInputCode.INVALID_VALUE,
            path=path,
        )
    return result


def _owner(
    value: object,
    kind: str,
    *,
    challenge_key: ChallengeKey | None = None,
    path: str,
) -> object:
    malformed = False
    try:
        result = require_owner_ref(value, kind)
    except (TypeError, ValueError):
        malformed = True
        result = None
    if malformed:
        raise GeneratorValidationError(
            GeneratorInputCode.WRONG_TYPE,
            path=path,
        )
    if challenge_key is not None:
        scope = result.scope_binding
        if type(scope) is not ChallengeScope or scope.challenge_key != challenge_key:
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path=path,
            )
    return result


def _owner_tuple(
    value: object,
    kind: str,
    *,
    challenge_key: ChallengeKey,
    path: str,
    nonempty: bool = True,
) -> tuple[object, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise GeneratorValidationError(
            GeneratorInputCode.WRONG_TYPE,
            path=path,
        )
    result = tuple(
        _owner(item, kind, challenge_key=challenge_key, path=path) for item in value
    )
    if len(set(result)) != len(result):
        raise GeneratorValidationError(
            GeneratorInputCode.INVALID_VALUE,
            path=path,
        )
    return result


def _top(
    value: object,
    expected: type,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> object:
    result = _exact(value, expected, path)
    if result.challenge_key != challenge_key:
        raise GeneratorValidationError(
            GeneratorInputCode.CROSS_CHALLENGE,
            path=path,
        )
    return result


def _exact_ref_pair(
    value: object,
    ref: object,
    expected_value_type: type,
    expected_ref_type: type,
    *,
    challenge_key: ChallengeKey | None,
    path: str,
) -> tuple[object, object]:
    checked = _exact(value, expected_value_type, path)
    checked_ref = _exact(ref, expected_ref_type, f"{path}_ref")
    if challenge_key is not None:
        for candidate in (checked, checked_ref):
            candidate_key = getattr(candidate, "challenge_key", challenge_key)
            if candidate_key != challenge_key:
                raise GeneratorValidationError(
                    GeneratorInputCode.CROSS_CHALLENGE,
                    path=path,
                )
    stale = False
    try:
        recomputed = checked.to_ref()
    except (AuthoringError, GeneratorValidationError, TypeError, ValueError):
        stale = True
        recomputed = None
    if stale:
        raise GeneratorValidationError(
            GeneratorInputCode.STALE_BINDING,
            path=path,
        )
    if recomputed != checked_ref:
        raise GeneratorValidationError(
            GeneratorInputCode.STALE_BINDING,
            path=path,
        )
    return checked, checked_ref


def _applicability_owner(
    value: object,
    bound_kind: str,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> ApplicabilityBinding:
    binding = _exact(value, ApplicabilityBinding, path)
    _owner(
        binding.value,
        bound_kind if binding.is_bound else "applicability_reason",
        challenge_key=challenge_key,
        path=path,
    )
    return binding


def _redacted_reduce(type_name: str) -> TypeError:
    return TypeError(f"{type_name} does not support generic serialization")


class FixtureReplayDerivationCapability:
    """Private one-use A4 replay derivation over exact context and draw."""

    __slots__ = ("__context", "__draw_index", "__lock", "__used")

    def __init__(
        self,
        *,
        _context: object = None,
        _draw_index: object = None,
        _token: object = None,
    ) -> None:
        if (
            type(self) is not FixtureReplayDerivationCapability
            or _token is not _REPLAY_DERIVATION_CAPABILITY_TOKEN
            or type(_context) is not FixtureOfficialContext
            or type(_draw_index) is not int
            or not 0 <= _draw_index <= _MAX_UINT64
        ):
            raise TypeError(
                "FixtureReplayDerivationCapability must be issued by "
                "FixtureGenerationAuthority"
            )
        object.__setattr__(
            self,
            "_FixtureReplayDerivationCapability__context",
            _context,
        )
        object.__setattr__(
            self,
            "_FixtureReplayDerivationCapability__draw_index",
            _draw_index,
        )
        object.__setattr__(
            self,
            "_FixtureReplayDerivationCapability__lock",
            allocate_lock(),
        )
        object.__setattr__(
            self,
            "_FixtureReplayDerivationCapability__used",
            False,
        )

    def __repr__(self) -> str:
        return "FixtureReplayDerivationCapability(<protected>)"

    __str__ = __repr__

    def __reduce__(self) -> object:
        raise _redacted_reduce("FixtureReplayDerivationCapability")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("FixtureReplayDerivationCapability")

    def _matches_generation_binding(
        self,
        *,
        context: object,
        draw_index: object,
        projection: object,
    ) -> bool:
        """Validate exact issuance echoes without returning protected values."""

        if (
            type(self) is not FixtureReplayDerivationCapability
            or type(context) is not FixtureOfficialContext
            or type(draw_index) is not int
            or type(projection) is not FixtureOfficialExamProjection
        ):
            return False
        with self.__lock:
            if self.__used:
                return False
            try:
                expected_projection = create_fixture_official_exam_projection(
                    self.__context
                )
            except Exception:  # noqa: BLE001 - keep protected state opaque.
                return False
            return (
                context is self.__context
                and draw_index == self.__draw_index
                and projection == expected_projection
            )

    def _matches_projection(self, projection: object) -> bool:
        """Validate the value-only projection without exposing A4 state."""

        if (
            type(self) is not FixtureReplayDerivationCapability
            or type(projection) is not FixtureOfficialExamProjection
        ):
            return False
        with self.__lock:
            if self.__used:
                return False
            try:
                return projection == create_fixture_official_exam_projection(
                    self.__context
                )
            except Exception:  # noqa: BLE001 - keep protected state opaque.
                return False

    def _derive_once(self, role_binding: object) -> DerivedSeed:
        """Consume the private replay derivation exactly once."""

        from .model import GenerationRoleBinding

        _exact(role_binding, GenerationRoleBinding, "/role_binding")
        with self.__lock:
            if self.__used:
                raise GeneratorServiceError(GeneratorServiceCode.REPLAY_UNAVAILABLE)
            object.__setattr__(
                self,
                "_FixtureReplayDerivationCapability__used",
                True,
            )
            context = self.__context
            draw_index = self.__draw_index
        derivation_failed = False
        try:
            result = derive_fixture_official_seed(
                context,
                role_binding.seed_domain,
                role_binding.role_key,
                draw_index,
            )
        except Exception:  # noqa: BLE001 - sanitize the protected A4 boundary.
            derivation_failed = True
            result = None
        finally:
            context = None
            draw_index = None
        if derivation_failed or type(result) is not DerivedSeed:
            raise GeneratorServiceError(GeneratorServiceCode.REPLAY_UNAVAILABLE)
        return result


@dataclass(slots=True, repr=False)
class _ReplayReservation:
    replay_ref: GeneratorReplayCommitmentRef
    reservation_ordinal: int | None
    consumed: bool = False
    grant_issued: bool = False
    grant_validated: bool = False
    issued_grant: FixtureGenerationGrant | None = None
    projection: FixtureOfficialExamProjection | None = None
    replay_capability: FixtureReplayDerivationCapability | None = None
    issued_request: object | None = None
    request_identity: object | None = None
    request_ref: object | None = None
    baseline_result: object | None = None
    baseline_result_ref: object | None = None
    probe_available: bool = False

    def __repr__(self) -> str:
        return "_ReplayReservation(<protected>)"

    __str__ = __repr__

    def __reduce__(self) -> object:
        raise _redacted_reduce("_ReplayReservation")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("_ReplayReservation")


class FixtureGenerationGrant:
    """One-use protected grant returned only after request admission."""

    __slots__ = (
        "__lock",
        "__used",
        "authoring_capability",
        "context",
        "draw_index",
        "origin",
        "projection",
        "replay_ref",
        "request",
    )

    def __init__(
        self,
        *,
        request: object,
        replay_ref: GeneratorReplayCommitmentRef,
        authoring_capability: FixtureAuthoringCapability,
        origin: FixtureOrigin,
        context: FixtureOfficialContext,
        draw_index: int,
        projection: object,
        _token: object = None,
    ) -> None:
        from .model import GeneratorRequest

        if (
            type(self) is not FixtureGenerationGrant
            or _token is not _GENERATION_GRANT_TOKEN
        ):
            raise TypeError(
                "FixtureGenerationGrant must be issued by FixtureGenerationAuthority"
            )
        _exact(request, GeneratorRequest, "/request")
        _exact(replay_ref, GeneratorReplayCommitmentRef, "/replay_ref")
        _exact(
            authoring_capability,
            FixtureAuthoringCapability,
            "/authoring_capability",
        )
        _exact(origin, FixtureOrigin, "/origin")
        _exact(context, FixtureOfficialContext, "/context")
        checked_projection = _exact(
            projection,
            FixtureOfficialExamProjection,
            "/projection",
        )
        if type(draw_index) is not int or not 0 <= draw_index <= _MAX_UINT64:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/draw_index",
            )
        if (
            replay_ref != request.replay_ref
            or origin.fixture_registration_ref
            != request.generator.fixture_registration_ref
            or origin.source_provenance_refs != request.generator.source_provenance_refs
            or context.pin.challenge_key != request.challenge_key
            or context.pin.generator_version != request.generator.generator_version
            or context.pin.generator_digest != request.generator.implementation_digest
            or checked_projection != create_fixture_official_exam_projection(context)
            or checked_projection.challenge_id != request.challenge_key.challenge_id
            or checked_projection.challenge_version != request.challenge_key.version
            or checked_projection.generator_version
            != request.generator.generator_version
            or checked_projection.generator_digest
            != request.generator.implementation_digest
            or checked_projection.fixture is not True
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/grant",
            )
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "replay_ref", replay_ref)
        object.__setattr__(self, "authoring_capability", authoring_capability)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "draw_index", draw_index)
        object.__setattr__(self, "projection", checked_projection)
        object.__setattr__(
            self,
            "_FixtureGenerationGrant__lock",
            allocate_lock(),
        )
        object.__setattr__(self, "_FixtureGenerationGrant__used", False)

    def __repr__(self) -> str:
        return "FixtureGenerationGrant(<protected>)"

    __str__ = __repr__

    def __reduce__(self) -> object:
        raise _redacted_reduce("FixtureGenerationGrant")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("FixtureGenerationGrant")

    def derive_once(self, role_binding: object) -> DerivedSeed:
        """Consume this execution grant for exactly one A4 derivation."""

        from .model import GenerationRoleBinding

        _exact(role_binding, GenerationRoleBinding, "/role_binding")
        if role_binding != self.request.role_binding:
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/role_binding",
            )
        with self.__lock:
            if self.__used:
                raise GeneratorServiceError(GeneratorServiceCode.INTERNAL_FAILURE)
            object.__setattr__(self, "_FixtureGenerationGrant__used", True)
        derivation_failed = False
        try:
            result = derive_fixture_official_seed(
                self.context,
                role_binding.seed_domain,
                role_binding.role_key,
                self.draw_index,
            )
        except Exception:  # noqa: BLE001 - sanitize the foreign A4 boundary.
            derivation_failed = True
            result = None
        if derivation_failed:
            raise GeneratorServiceError(
                GeneratorServiceCode.INTERNAL_FAILURE,
            )
        if type(result) is not DerivedSeed:
            raise GeneratorServiceError(GeneratorServiceCode.INTERNAL_FAILURE)
        return result


class FixtureReplayProbeAuthority:
    """Token-gated one-use replay façade over the generation issuance store."""

    __slots__ = ("__claim_lock", "__reservations")

    def __init__(
        self,
        *,
        _claim_lock: object = None,
        _reservations: object = None,
        _token: object = None,
    ) -> None:
        if (
            _token is not _REPLAY_PROBE_AUTHORITY_TOKEN
            or type(_claim_lock) is not LockType
            or type(_reservations) is not dict
        ):
            raise TypeError(
                "FixtureReplayProbeAuthority must be issued by "
                "FixtureGenerationAuthority"
            )
        object.__setattr__(
            self,
            "_FixtureReplayProbeAuthority__reservations",
            _reservations,
        )
        object.__setattr__(
            self,
            "_FixtureReplayProbeAuthority__claim_lock",
            _claim_lock,
        )

    def __repr__(self) -> str:
        return "FixtureReplayProbeAuthority(<protected>)"

    __str__ = __repr__

    def __reduce__(self) -> object:
        raise _redacted_reduce("FixtureReplayProbeAuthority")

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("FixtureReplayProbeAuthority")

    def probe(
        self,
        *,
        baseline_result: object,
        baseline_result_ref: object,
        baseline_request: object,
    ) -> object:
        """Validate the complete baseline, atomically claim, and replay once."""

        if type(self) is not FixtureReplayProbeAuthority:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/replay_authority",
            )

        from .burgers import _materialize_burgers_fixture_payload
        from .conformance import (
            FixtureReplayProbe,
            _build_fixture_replay_probe_from_payload,
            _prepare_fixture_replay_probe,
        )

        prepared = _prepare_fixture_replay_probe(
            baseline_result=baseline_result,
            baseline_result_ref=baseline_result_ref,
            baseline_request=baseline_request,
        )
        request, identity, request_ref = prepared[:3]
        state_valid = False
        with self.__claim_lock:
            state = self.__reservations.get(identity.replay_ref)
            try:
                if (
                    type(state) is _ReplayReservation
                    and state.consumed
                    and state.grant_issued
                    and state.grant_validated
                    and state.probe_available
                    and type(state.projection) is FixtureOfficialExamProjection
                    and type(state.replay_capability)
                    is FixtureReplayDerivationCapability
                ):
                    state_valid = (
                        state.replay_capability._matches_projection(state.projection)
                        and state.issued_request is baseline_request
                        and state.request_identity == identity
                        and state.request_ref == request_ref
                        and state.baseline_result is baseline_result
                        and state.baseline_result_ref == baseline_result_ref
                        and state.replay_ref == identity.replay_ref
                        and state.projection.challenge_id
                        == identity.challenge_key.challenge_id
                        and state.projection.challenge_version
                        == identity.challenge_key.version
                        and state.projection.generator_version
                        == request.generator.generator_version
                        and state.projection.generator_digest
                        == request.generator.implementation_digest
                        and state.projection.fixture is True
                    )
            except Exception:  # noqa: BLE001 - sanitize protected private state.
                state_valid = False
            if state_valid:
                # The validation and flip share one authority-owned critical
                # section, so two callers cannot both observe availability.
                state.probe_available = False
        if not state_valid:
            raise GeneratorServiceError(GeneratorServiceCode.REPLAY_UNAVAILABLE)

        # The claim precedes every protected or potentially failing operation,
        # so post-claim failure cannot become a retry.
        post_claim_failed = False
        probe = None
        derived = None
        try:
            derived = state.replay_capability._derive_once(identity.role_binding)
            if type(derived) is not DerivedSeed:
                raise TypeError("unexpected replay derivation result")
            payload = _materialize_burgers_fixture_payload(
                derived,
                fixture_configuration_ref=identity.fixture_configuration_ref,
            )
            probe = _build_fixture_replay_probe_from_payload(prepared, payload)
            if type(probe) is not FixtureReplayProbe:
                raise TypeError("unexpected replay probe result")
        except Exception:  # noqa: BLE001 - sanitize all post-claim boundaries.
            post_claim_failed = True
            probe = None
        finally:
            derived = None
        if post_claim_failed:
            raise GeneratorServiceError(GeneratorServiceCode.REPLAY_UNAVAILABLE)
        return probe


def _new_fixture_replay_probe_authority(
    reservations: dict[object, _ReplayReservation],
    claim_lock: LockType,
) -> FixtureReplayProbeAuthority:
    return FixtureReplayProbeAuthority(
        _claim_lock=claim_lock,
        _reservations=reservations,
        _token=_REPLAY_PROBE_AUTHORITY_TOKEN,
    )


class FixtureGenerationAuthority:
    """In-memory fixture-only reservation, grant, and replay issuer.

    Reservation creates only an opaque identity.  Provider acquisition happens
    once, after admission, and the reservation is consumed before acquisition
    so a failure cannot become an implicit retry under the same attempt.
    """

    __slots__ = (
        "__authoring_capability",
        "__counter",
        "__fixture_registration_ref",
        "__generator",
        "__generator_ref",
        "__pin",
        "__provider",
        "__replay_claim_lock",
        "__replay_probe_authority",
        "__reservation_issuer_ref",
        "__reservations",
        "__source_provenance_refs",
    )

    def __init__(
        self,
        *,
        provider: DeterministicFixtureProvider,
        pin: SeedPin,
        generator: object,
        generator_ref: object,
        reservation_issuer_ref: object,
        fixture_registration_ref: object,
        source_provenance_refs: tuple[object, ...],
    ) -> None:
        from .model import GeneratorDescriptor

        _exact(provider, DeterministicFixtureProvider, "/provider")
        _exact(pin, SeedPin, "/pin")
        checked_generator = _exact(generator, GeneratorDescriptor, "/generator")
        key = _challenge(pin.challenge_key)
        checked_generator_ref = _owner(
            generator_ref,
            "generator",
            challenge_key=key,
            path="/generator_ref",
        )
        issuer = _owner(
            reservation_issuer_ref,
            "authority_evidence",
            challenge_key=key,
            path="/reservation_issuer_ref",
        )
        fixture = _owner(
            fixture_registration_ref,
            "fixture_registration",
            challenge_key=key,
            path="/fixture_registration_ref",
        )
        provenance = _owner_tuple(
            source_provenance_refs,
            "provenance",
            challenge_key=key,
            path="/source_provenance_refs",
        )
        if (
            checked_generator.challenge_key != key
            or checked_generator.to_ref() != checked_generator_ref
            or checked_generator.generator_version != pin.generator_version
            or checked_generator.implementation_digest != pin.generator_digest
            or checked_generator.fixture_registration_ref != fixture
            or checked_generator.source_provenance_refs != provenance
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/generator",
            )
        object.__setattr__(self, "_FixtureGenerationAuthority__provider", provider)
        object.__setattr__(self, "_FixtureGenerationAuthority__pin", pin)
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__reservation_issuer_ref",
            issuer,
        )
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__fixture_registration_ref",
            fixture,
        )
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__source_provenance_refs",
            provenance,
        )
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__generator",
            checked_generator,
        )
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__generator_ref",
            checked_generator_ref,
        )
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__authoring_capability",
            FixtureAuthoringCapability(),
        )
        reservations: dict[object, _ReplayReservation] = {}
        replay_claim_lock = allocate_lock()
        object.__setattr__(self, "_FixtureGenerationAuthority__counter", 0)
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__reservations",
            reservations,
        )
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__replay_claim_lock",
            replay_claim_lock,
        )
        object.__setattr__(
            self,
            "_FixtureGenerationAuthority__replay_probe_authority",
            _new_fixture_replay_probe_authority(reservations, replay_claim_lock),
        )

    def __repr__(self) -> str:
        return "FixtureGenerationAuthority(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("FixtureGenerationAuthority")

    def reserve_replay(self) -> GeneratorReplayCommitmentRef:
        """Issue one replay reservation without touching provider or entropy."""

        with self.__replay_claim_lock:
            counter = self.__counter
            if counter > _MAX_UINT64:
                raise GeneratorServiceError(GeneratorServiceCode.REPLAY_UNAVAILABLE)
            key = self.__pin.challenge_key
            document = encode_value(
                CanonicalRecord(
                    "fixture_replay_reservation_private_preimage",
                    (
                        ("challenge_key", challenge_key_to_canonical(key)),
                        ("counter", CanonicalUInt64(counter)),
                        (
                            "replay_scheme_id",
                            CanonicalText(_REPLAY_SCHEME_ID),
                        ),
                        (
                            "replay_scheme_version",
                            CanonicalText(_REPLAY_SCHEME_VERSION),
                        ),
                        (
                            "reservation_issuer_ref",
                            owner_ref_to_canonical(self.__reservation_issuer_ref),
                        ),
                    ),
                )
            )
            digest = f"sha256:{hashlib.sha256(document).hexdigest()}"
            replay_ref = GeneratorReplayCommitmentRef(
                key,
                _REPLAY_SCHEME_ID,
                _REPLAY_SCHEME_VERSION,
                self.__reservation_issuer_ref,
                digest,
            )
            self.__reservations[replay_ref] = _ReplayReservation(
                replay_ref,
                counter,
            )
            object.__setattr__(
                self,
                "_FixtureGenerationAuthority__counter",
                counter + 1,
            )
        return replay_ref

    def require_available(self, replay_ref: object) -> None:
        """Admission check with no provider, context, or entropy access."""

        if type(replay_ref) is not GeneratorReplayCommitmentRef:
            raise GeneratorValidationError(
                GeneratorInputCode.REPLAY_RESERVATION_INVALID,
                path="/replay_ref",
            )
        with self.__replay_claim_lock:
            state = self.__reservations.get(replay_ref)
            available = (
                type(state) is _ReplayReservation
                and state.replay_ref == replay_ref
                and not state.consumed
            )
        if not available:
            raise GeneratorValidationError(
                GeneratorInputCode.REPLAY_RESERVATION_INVALID,
                path="/replay_ref",
            )

    def claim_attempt(self, request: object) -> None:
        """Atomically consume and bind one admitted post-admission attempt."""

        from .model import GeneratorRequest

        checked = _exact(request, GeneratorRequest, "/request")
        if checked.challenge_key != self.__pin.challenge_key:
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path="/challenge_key",
            )
        if (
            checked.generator != self.__generator
            or checked.generator_ref != self.__generator_ref
            or checked.generator.generator_version != self.__pin.generator_version
            or checked.generator.implementation_digest != self.__pin.generator_digest
            or checked.generator.fixture_registration_ref
            != self.__fixture_registration_ref
            or checked.generator.source_provenance_refs != self.__source_provenance_refs
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/generator",
            )

        identity = checked.identity()
        request_ref = identity.to_ref()
        with self.__replay_claim_lock:
            state = self.__reservations.get(checked.replay_ref)
            if (
                type(state) is not _ReplayReservation
                or state.replay_ref
                is not checked.intended_unit_link_decision.request.replay_ref
                or state.consumed
            ):
                raise GeneratorValidationError(
                    GeneratorInputCode.REPLAY_RESERVATION_INVALID,
                    path="/replay_ref",
                )
            # This is the post-admission attempt transition.  All deterministic
            # request reconstruction precedes it and every terminal path follows
            # it.  The same private lock makes check-and-flip indivisible.
            state.consumed = True
            state.issued_request = checked
            state.request_identity = identity
            state.request_ref = request_ref

    def issue_grant(self, request: object) -> FixtureGenerationGrant:
        """Acquire context for one already claimed admitted reservation."""

        from .model import GeneratorRequest

        checked = _exact(request, GeneratorRequest, "/request")
        if checked.challenge_key != self.__pin.challenge_key:
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path="/challenge_key",
            )
        if (
            checked.generator != self.__generator
            or checked.generator_ref != self.__generator_ref
            or checked.generator.generator_version != self.__pin.generator_version
            or checked.generator.implementation_digest != self.__pin.generator_digest
            or checked.generator.fixture_registration_ref
            != self.__fixture_registration_ref
            or checked.generator.source_provenance_refs != self.__source_provenance_refs
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/generator",
            )

        identity = checked.identity()
        request_ref = identity.to_ref()
        with self.__replay_claim_lock:
            state = self.__reservations.get(checked.replay_ref)
            if (
                type(state) is not _ReplayReservation
                or state.replay_ref
                is not checked.intended_unit_link_decision.request.replay_ref
                or not state.consumed
                or state.grant_issued
                or state.issued_request is not checked
                or state.request_identity != identity
                or state.request_ref != request_ref
                or type(state.reservation_ordinal) is not int
            ):
                raise GeneratorValidationError(
                    GeneratorInputCode.REPLAY_RESERVATION_INVALID,
                    path="/replay_ref",
                )
            # Fail closed before touching the protected provider boundary.
            state.grant_issued = True
            draw_index = state.reservation_ordinal
            state.reservation_ordinal = None
        acquisition_failed = False
        try:
            context = acquire_fixture_official_context(self.__provider, self.__pin)
            projection = create_fixture_official_exam_projection(context)
            origin = self.__authoring_capability.issue_origin(
                fixture_registration_ref=self.__fixture_registration_ref,
                source_provenance_refs=self.__source_provenance_refs,
            )
            replay_capability = FixtureReplayDerivationCapability(
                _context=context,
                _draw_index=draw_index,
                _token=_REPLAY_DERIVATION_CAPABILITY_TOKEN,
            )
            grant = FixtureGenerationGrant(
                request=checked,
                replay_ref=checked.replay_ref,
                authoring_capability=self.__authoring_capability,
                origin=origin,
                context=context,
                draw_index=draw_index,
                projection=projection,
                _token=_GENERATION_GRANT_TOKEN,
            )
        except Exception:  # noqa: BLE001 - sanitize the foreign A4 boundary.
            acquisition_failed = True
            context = None
            projection = None
            origin = None
            replay_capability = None
            grant = None
        if acquisition_failed:
            raise GeneratorServiceError(
                GeneratorServiceCode.AUTHORITY_UNAVAILABLE,
            )
        with self.__replay_claim_lock:
            state.projection = projection
            state.replay_capability = replay_capability
            state.probe_available = True
            state.issued_grant = grant
        return grant

    def validate_grant(
        self,
        request: object,
        grant: object,
    ) -> FixtureGenerationGrant:
        """Reconstruct an issued grant and verify every private-store echo."""

        from .model import GeneratorRequest

        checked_request = _exact(request, GeneratorRequest, "/request")
        checked_grant = grant if type(grant) is FixtureGenerationGrant else None
        identity = checked_request.identity()
        request_ref = identity.to_ref()
        grant_valid = False
        with self.__replay_claim_lock:
            state = self.__reservations.get(checked_request.replay_ref)
            state_matches_request = (
                type(state) is _ReplayReservation
                and state.replay_ref
                is checked_request.intended_unit_link_decision.request.replay_ref
                and state.consumed
                and state.grant_issued
                and not state.grant_validated
                and state.issued_request is checked_request
                and state.request_identity == identity
                and state.request_ref == request_ref
            )
            if state_matches_request:
                try:
                    grant_lock = checked_grant._FixtureGenerationGrant__lock
                except AttributeError:
                    grant_lock = None
                if (
                    checked_grant is not None
                    and state.issued_grant is checked_grant
                    and type(grant_lock) is LockType
                    and type(state.projection) is FixtureOfficialExamProjection
                    and type(state.replay_capability)
                    is FixtureReplayDerivationCapability
                ):
                    reconstruction_failed = False
                    reconstructed = None
                    with grant_lock:
                        try:
                            grant_used = checked_grant._FixtureGenerationGrant__used
                            reconstructed = FixtureGenerationGrant(
                                request=checked_grant.request,
                                replay_ref=checked_grant.replay_ref,
                                authoring_capability=(
                                    checked_grant.authoring_capability
                                ),
                                origin=checked_grant.origin,
                                context=checked_grant.context,
                                draw_index=checked_grant.draw_index,
                                projection=checked_grant.projection,
                                _token=_GENERATION_GRANT_TOKEN,
                            )
                        except Exception:  # noqa: BLE001 - sanitize grant graph.
                            reconstruction_failed = True
                            grant_used = None
                            reconstructed = None
                    if not reconstruction_failed and grant_used is False:
                        grant_valid = (
                            reconstructed.request is checked_request
                            and reconstructed.replay_ref == state.replay_ref
                            and reconstructed.authoring_capability
                            is self.__authoring_capability
                            and reconstructed.projection == state.projection
                            and state.replay_capability._matches_generation_binding(
                                context=reconstructed.context,
                                draw_index=reconstructed.draw_index,
                                projection=reconstructed.projection,
                            )
                            and reconstructed.origin.fixture_registration_ref
                            == self.__fixture_registration_ref
                            and reconstructed.origin.source_provenance_refs
                            == self.__source_provenance_refs
                            and reconstructed.request.generator_ref
                            == state.request_identity.generator_ref
                            and reconstructed.request.environment_ref
                            == state.request_identity.environment_ref
                            and reconstructed.request.fixture_configuration_ref
                            == state.request_identity.fixture_configuration_ref
                            and reconstructed.request.role_binding
                            == state.request_identity.role_binding
                        )
                # The store retains a context-bearing grant only until this one
                # validation attempt.  A clone, repeated call, or malformed echo
                # therefore cannot leave a second derivation handle behind.
                state.issued_grant = None
                if grant_valid:
                    state.grant_validated = True
        if not grant_valid:
            raise GeneratorServiceError(GeneratorServiceCode.AUTHORITY_UNAVAILABLE)
        # Return the exact issued object. Reconstructing a replacement would
        # reset its private one-use derivation state.
        return checked_grant

    def register_replay_baseline(self, request: object, result: object) -> None:
        """Privately bind the exact issued result wrapper to its replay store."""

        from .model import GeneratorOutcomeKind, GeneratorRequest, GeneratorResult

        checked_request = _exact(request, GeneratorRequest, "/request")
        checked_result = _exact(result, GeneratorResult, "/result")
        identity = checked_request.identity()
        request_ref = identity.to_ref()
        result_ref = checked_result.record.to_ref()
        with self.__replay_claim_lock:
            state = self.__reservations.get(checked_request.replay_ref)
            if (
                type(state) is not _ReplayReservation
                or state.replay_ref
                is not checked_request.intended_unit_link_decision.request.replay_ref
                or not state.consumed
                or not state.grant_issued
                or not state.grant_validated
                or not state.probe_available
                or state.issued_request is not checked_request
                or state.request_identity != identity
                or state.request_ref != request_ref
                or state.baseline_result is not None
                or state.baseline_result_ref is not None
                or checked_result.record.outcome_kind
                not in {
                    GeneratorOutcomeKind.VALID_GENERATED,
                    GeneratorOutcomeKind.CENSORED_CASE,
                }
                or checked_result.record.request_ref != state.request_ref
                or checked_result.ref != result_ref
            ):
                raise GeneratorServiceError(GeneratorServiceCode.AUTHORITY_UNAVAILABLE)
            state.baseline_result = checked_result
            state.baseline_result_ref = checked_result.ref

    def replay_probe_authority(self) -> FixtureReplayProbeAuthority:
        """Return the cached nominal façade without exposing private state."""

        return self.__replay_probe_authority


class IntendedUnitLinkAuthority(Protocol):
    def decide_intended_unit_link(self, request: object) -> object: ...


class SupportExclusionAuthority(Protocol):
    def assess_support_exclusion(self, request: object) -> object: ...


class GeneratorCensoringAuthority(Protocol):
    def decide_censoring(self, request: object) -> object: ...


class PopulationAssessmentRole(str, Enum):
    SELECTION_MATERIALIZATION = "SELECTION_MATERIALIZATION"
    PRIMARY_CASE = "PRIMARY_CASE"


class PopulationSupportDecisionKind(str, Enum):
    WITHIN_REGISTERED_SUPPORT = "WITHIN_REGISTERED_SUPPORT"
    REGISTERED_EXCLUSION = "REGISTERED_EXCLUSION"
    OUTSIDE_REGISTERED_SUPPORT = "OUTSIDE_REGISTERED_SUPPORT"
    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"


class SupportExclusionDecisionKind(str, Enum):
    ASSESSED = "ASSESSED"
    OWNER_UNAVAILABLE = "OWNER_UNAVAILABLE"


class CensoringVerdictKind(str, Enum):
    NOT_CENSORED = "NOT_CENSORED"
    CENSORED = "CENSORED"
    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"


def _binding_owner(
    value: object,
    kind: str,
    path: str,
    *,
    challenge_key: ChallengeKey,
) -> ApplicabilityBinding:
    binding = _exact(value, ApplicabilityBinding, path)
    if binding.is_bound:
        _owner(binding.value, kind, challenge_key=challenge_key, path=path)
    return binding


@dataclass(frozen=True, slots=True, repr=False)
class IntendedUnitLinkRequest:
    challenge_key: ChallengeKey
    sampling_plan_ref: SamplingPlanRef
    selection_population_ref: InstanceDistributionContractRef
    role_binding: object
    replay_ref: GeneratorReplayCommitmentRef
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    attempt_ref: object

    def __post_init__(self) -> None:
        from .model import GenerationRoleBinding

        if type(self) is not IntendedUnitLinkRequest:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/request",
            )
        key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", key)
        for name, expected in (
            ("sampling_plan_ref", SamplingPlanRef),
            ("selection_population_ref", InstanceDistributionContractRef),
        ):
            value = _exact(getattr(self, name), expected, f"/{name}")
            if value.challenge_key != key:
                raise GeneratorValidationError(
                    GeneratorInputCode.CROSS_CHALLENGE,
                    path=f"/{name}",
                )
        role = _exact(self.role_binding, GenerationRoleBinding, "/role_binding")
        if role.sampling_plan_ref != self.sampling_plan_ref:
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/role_binding",
            )
        replay = _exact(
            self.replay_ref,
            GeneratorReplayCommitmentRef,
            "/replay_ref",
        )
        if replay.challenge_key != key:
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path="/replay_ref",
            )
        for name, kind in (
            ("intended_slot_ref", "protected_intended_slot"),
            (
                "intended_evidence_unit_ref",
                "protected_intended_evidence_unit",
            ),
            ("attempt_ref", "protected_attempt_commitment"),
        ):
            object.__setattr__(
                self,
                name,
                _owner(
                    getattr(self, name),
                    kind,
                    challenge_key=key,
                    path=f"/{name}",
                ),
            )
        if self.intended_slot_ref == self.intended_evidence_unit_ref:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/intended_evidence_unit_ref",
            )

    def __repr__(self) -> str:
        return "IntendedUnitLinkRequest(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("protected intended-unit link requests cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class IntendedUnitLinkDecision:
    challenge_key: ChallengeKey
    request: IntendedUnitLinkRequest
    link_evidence_ref: object

    def __post_init__(self) -> None:
        if type(self) is not IntendedUnitLinkDecision:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/intended_unit_link_decision",
            )
        key = _challenge(self.challenge_key)
        request = _exact(self.request, IntendedUnitLinkRequest, "/request")
        if request.challenge_key != key:
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path="/request",
            )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(
            self,
            "link_evidence_ref",
            _owner(
                self.link_evidence_ref,
                "authority_evidence",
                challenge_key=key,
                path="/link_evidence_ref",
            ),
        )

    def __repr__(self) -> str:
        return "IntendedUnitLinkDecision(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("IntendedUnitLinkDecision")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> IntendedUnitLinkDecisionRef:
        from .canonical import _record_ref

        return _record_ref(self, IntendedUnitLinkDecisionRef)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True, repr=False)
class PopulationSupportAssessment:
    assessment_role: PopulationAssessmentRole
    population_ref: InstanceDistributionContractRef
    support_contract: SupportContract
    exclusion_contract_binding: ApplicabilityBinding[ExclusionContract]
    decision_kind: PopulationSupportDecisionKind
    applicability_evidence_binding: ApplicabilityBinding[object]
    membership_evidence_binding: ApplicabilityBinding[object]
    exclusion_contract_ref_binding: ApplicabilityBinding[object]
    prospective_exclusion_contract_ref_binding: ApplicabilityBinding[object]
    exclusion_assessment_ref_binding: ApplicabilityBinding[object]
    screening_design_ref_binding: ApplicabilityBinding[object]
    inclusion_probability_accounting_ref_binding: ApplicabilityBinding[object]
    infrastructure_failure_binding: ApplicabilityBinding[object]

    def __post_init__(self) -> None:
        if type(self) is not PopulationSupportAssessment:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/assessments",
            )
        if type(self.assessment_role) is not PopulationAssessmentRole:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/assessment_role",
            )
        population_ref = _exact(
            self.population_ref,
            InstanceDistributionContractRef,
            "/population_ref",
        )
        challenge = population_ref.challenge_key
        _exact(self.support_contract, SupportContract, "/support_contract")
        exclusion = _exact(
            self.exclusion_contract_binding,
            ApplicabilityBinding,
            "/exclusion_contract_binding",
        )
        if exclusion.is_bound:
            _exact(
                exclusion.value,
                ExclusionContract,
                "/exclusion_contract_binding",
            )
        if type(self.decision_kind) is not PopulationSupportDecisionKind:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/decision_kind",
            )
        bindings = {
            "applicability": _binding_owner(
                self.applicability_evidence_binding,
                "applicability_evidence",
                "/applicability_evidence_binding",
                challenge_key=challenge,
            ),
            "membership": _binding_owner(
                self.membership_evidence_binding,
                "membership_evidence",
                "/membership_evidence_binding",
                challenge_key=challenge,
            ),
            "exclusion_contract": _binding_owner(
                self.exclusion_contract_ref_binding,
                "exclusion_contract",
                "/exclusion_contract_ref_binding",
                challenge_key=challenge,
            ),
            "prospective_exclusion": _binding_owner(
                self.prospective_exclusion_contract_ref_binding,
                "prospective_exclusion_contract",
                "/prospective_exclusion_contract_ref_binding",
                challenge_key=challenge,
            ),
            "exclusion_assessment": _binding_owner(
                self.exclusion_assessment_ref_binding,
                "exclusion_assessment",
                "/exclusion_assessment_ref_binding",
                challenge_key=challenge,
            ),
            "screening": _binding_owner(
                self.screening_design_ref_binding,
                "screening_design",
                "/screening_design_ref_binding",
                challenge_key=challenge,
            ),
            "inclusion": _binding_owner(
                self.inclusion_probability_accounting_ref_binding,
                "inclusion_probability_accounting",
                "/inclusion_probability_accounting_ref_binding",
                challenge_key=challenge,
            ),
            "infrastructure": _binding_owner(
                self.infrastructure_failure_binding,
                "infrastructure_failure",
                "/infrastructure_failure_binding",
                challenge_key=challenge,
            ),
        }
        expected_bound = {
            PopulationSupportDecisionKind.WITHIN_REGISTERED_SUPPORT: {
                "applicability",
                "membership",
            },
            PopulationSupportDecisionKind.REGISTERED_EXCLUSION: {
                "exclusion_contract",
                "prospective_exclusion",
                "exclusion_assessment",
                "screening",
                "inclusion",
            },
            PopulationSupportDecisionKind.OUTSIDE_REGISTERED_SUPPORT: {
                "applicability",
                "membership",
            },
            PopulationSupportDecisionKind.AUTHORITY_UNAVAILABLE: {
                "infrastructure",
            },
        }[self.decision_kind]
        actual_bound = {name for name, binding in bindings.items() if binding.is_bound}
        if actual_bound != expected_bound:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/decision_kind",
            )
        if self.decision_kind is PopulationSupportDecisionKind.REGISTERED_EXCLUSION:
            if not exclusion.is_bound:
                raise GeneratorValidationError(
                    GeneratorInputCode.INCOMPLETE_BINDING,
                    path="/exclusion_contract_binding",
                )
        elif exclusion.is_bound:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/exclusion_contract_binding",
            )

    def __repr__(self) -> str:
        return "PopulationSupportAssessment(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("protected support assessments cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class SupportExclusionRequest:
    challenge_key: ChallengeKey
    generator_request_ref: object
    source_event: object
    source_event_ref: object
    protected_payload: object
    protected_payload_ref: object
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    generator_ref: object
    environment_ref: object
    fixture_configuration_ref: object
    role_binding: object
    replay_ref: GeneratorReplayCommitmentRef
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    attempt_ref: object
    fixture_payload_facts: object

    def __post_init__(self) -> None:
        from .burgers import (
            FixturePayloadFacts,
            ProtectedBurgersFixturePayload,
            _new_protected_payload,
            build_fixture_payload_facts,
            build_physical_payload_fingerprint,
        )
        from .model import (
            GenerationRoleBinding,
            GenerationSourceEvent,
            SourceMaterializationState,
        )
        from .refs import (
            BurgersFixtureConfigurationRef,
            GeneratorEnvironmentRef,
            GeneratorRequestRef,
        )

        if type(self) is not SupportExclusionRequest:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/support_exclusion_request",
            )
        key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", key)
        for name, expected in (
            ("generator_request_ref", GeneratorRequestRef),
            ("source_event", GenerationSourceEvent),
            ("protected_payload", ProtectedBurgersFixturePayload),
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_ref", CandidateOutputContractRef),
            ("primary_population_ref", InstanceDistributionContractRef),
            ("selection_population_ref", InstanceDistributionContractRef),
            ("sampling_plan_ref", SamplingPlanRef),
            ("environment_ref", GeneratorEnvironmentRef),
            ("fixture_configuration_ref", BurgersFixtureConfigurationRef),
            ("role_binding", GenerationRoleBinding),
            ("replay_ref", GeneratorReplayCommitmentRef),
            ("fixture_payload_facts", FixturePayloadFacts),
        ):
            value = _exact(getattr(self, name), expected, f"/{name}")
            challenge = getattr(value, "challenge_key", key)
            if type(challenge) is ChallengeKey and challenge != key:
                raise GeneratorValidationError(
                    GeneratorInputCode.CROSS_CHALLENGE,
                    path=f"/{name}",
                )
        _owner(
            self.source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/source_event_ref",
        )
        _owner(
            self.protected_payload_ref,
            "protected_case_payload",
            challenge_key=key,
            path="/protected_payload_ref",
        )
        _owner(
            self.generator_ref,
            "generator",
            challenge_key=key,
            path="/generator_ref",
        )
        for name, kind in (
            ("intended_slot_ref", "protected_intended_slot"),
            (
                "intended_evidence_unit_ref",
                "protected_intended_evidence_unit",
            ),
            ("attempt_ref", "protected_attempt_commitment"),
        ):
            _owner(
                getattr(self, name),
                kind,
                challenge_key=key,
                path=f"/{name}",
            )

        source_event = replace(self.source_event)
        protected_payload = _new_protected_payload(
            fixture_configuration_ref=self.protected_payload.fixture_configuration_ref,
            period=self.protected_payload.period,
            grid_points=self.protected_payload.grid_points,
            viscosity=self.protected_payload.viscosity,
            initial_values=self.protected_payload.initial_values,
        )
        payload_facts = self.fixture_payload_facts
        fingerprint = build_physical_payload_fingerprint(
            challenge_key=key,
            case_representation_ref=(
                payload_facts.physical_payload_fingerprint.case_representation_ref
            ),
            fixture_configuration_ref=self.fixture_configuration_ref,
            protected_payload=protected_payload,
        )
        expected_facts = build_fixture_payload_facts(
            protected_payload=protected_payload,
            protected_payload_ref=self.protected_payload_ref,
            physical_payload_fingerprint=fingerprint,
            physical_payload_fingerprint_ref=fingerprint.to_ref(),
        )
        expected_echoes = (
            (self.generator_request_ref, source_event.request_ref),
            (self.source_event_ref, source_event.to_ref()),
            (self.protected_payload_ref, source_event.payload_ref_binding.value),
            (self.protected_payload_ref, expected_facts.protected_payload_ref),
            (self.physical_system_ref, source_event.physical_system_ref),
            (self.candidate_output_ref, source_event.candidate_output_ref),
            (self.primary_population_ref, source_event.primary_population_ref),
            (self.selection_population_ref, source_event.selection_population_ref),
            (self.sampling_plan_ref, source_event.sampling_plan_ref),
            (self.generator_ref, source_event.generator_ref),
            (self.environment_ref, source_event.environment_ref),
            (self.fixture_configuration_ref, source_event.fixture_configuration_ref),
            (self.role_binding, source_event.role_binding),
            (self.replay_ref, source_event.replay_ref),
            (self.intended_slot_ref, source_event.intended_slot_ref),
            (
                self.intended_evidence_unit_ref,
                source_event.intended_evidence_unit_ref,
            ),
            (self.attempt_ref, source_event.attempt_ref),
            (self.fixture_payload_facts, expected_facts),
        )
        if (
            source_event.materialization_state
            is not SourceMaterializationState.PAYLOAD_AVAILABLE
            or not source_event.payload_ref_binding.is_bound
            or protected_payload != self.protected_payload
            or any(actual != expected for actual, expected in expected_echoes)
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/support_exclusion_request",
            )

    def __repr__(self) -> str:
        return "SupportExclusionRequest(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("protected support requests cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class SupportExclusionDecision:
    challenge_key: ChallengeKey
    request: SupportExclusionRequest
    decision_kind: SupportExclusionDecisionKind
    assessments: tuple[PopulationSupportAssessment, ...]
    terminal_resolution: PopulationSupportDecisionKind
    effective_assessment_role: PopulationAssessmentRole | None
    resolution_policy_ref: object | None
    resolution_evidence_ref: object | None
    infrastructure_failure_ref: object | None

    def __post_init__(self) -> None:
        if type(self) is not SupportExclusionDecision:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/support_decision",
            )
        key = _challenge(self.challenge_key)
        request = _exact(self.request, SupportExclusionRequest, "/request")
        if request.challenge_key != key:
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path="/request",
            )
        object.__setattr__(self, "challenge_key", key)
        if type(self.decision_kind) is not SupportExclusionDecisionKind:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/decision_kind",
            )
        if type(self.terminal_resolution) is not PopulationSupportDecisionKind:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/terminal_resolution",
            )
        if type(self.assessments) is not tuple or any(
            type(item) is not PopulationSupportAssessment for item in self.assessments
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/assessments",
            )
        if self.decision_kind is SupportExclusionDecisionKind.OWNER_UNAVAILABLE:
            if (
                self.assessments
                or self.terminal_resolution
                is not PopulationSupportDecisionKind.AUTHORITY_UNAVAILABLE
                or self.effective_assessment_role is not None
                or self.resolution_policy_ref is not None
                or self.resolution_evidence_ref is not None
            ):
                raise GeneratorValidationError(
                    GeneratorInputCode.INVALID_VALUE,
                    path="/decision_kind",
                )
            _owner(
                self.infrastructure_failure_ref,
                "infrastructure_failure",
                challenge_key=key,
                path="/infrastructure_failure_ref",
            )
            return
        if self.infrastructure_failure_ref is not None:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/infrastructure_failure_ref",
            )
        if tuple(item.assessment_role for item in self.assessments) != (
            PopulationAssessmentRole.SELECTION_MATERIALIZATION,
            PopulationAssessmentRole.PRIMARY_CASE,
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/assessments",
            )
        expected_refs = (
            request.selection_population_ref,
            request.primary_population_ref,
        )
        if tuple(item.population_ref for item in self.assessments) != expected_refs:
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/assessments",
            )
        within = all(
            item.decision_kind
            is PopulationSupportDecisionKind.WITHIN_REGISTERED_SUPPORT
            for item in self.assessments
        )
        if within:
            if (
                self.terminal_resolution
                is not PopulationSupportDecisionKind.WITHIN_REGISTERED_SUPPORT
                or self.effective_assessment_role is not None
                or self.resolution_policy_ref is not None
                or self.resolution_evidence_ref is not None
            ):
                raise GeneratorValidationError(
                    GeneratorInputCode.INVALID_VALUE,
                    path="/terminal_resolution",
                )
            return
        if type(self.effective_assessment_role) is not PopulationAssessmentRole:
            raise GeneratorValidationError(
                GeneratorInputCode.INCOMPLETE_BINDING,
                path="/effective_assessment_role",
            )
        effective = next(
            item
            for item in self.assessments
            if item.assessment_role is self.effective_assessment_role
        )
        if (
            effective.decision_kind is not self.terminal_resolution
            or self.terminal_resolution
            is PopulationSupportDecisionKind.WITHIN_REGISTERED_SUPPORT
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/terminal_resolution",
            )
        _owner(
            self.resolution_policy_ref,
            "policy_authority",
            challenge_key=key,
            path="/resolution_policy_ref",
        )
        _owner(
            self.resolution_evidence_ref,
            "membership_decision",
            challenge_key=key,
            path="/resolution_evidence_ref",
        )

    def __repr__(self) -> str:
        return "SupportExclusionDecision(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("SupportExclusionDecision")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> SupportExclusionDecisionRef:
        from .canonical import _record_ref

        return _record_ref(self, SupportExclusionDecisionRef)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorCensoringRequest:
    """Exact post-case request supplied to one nominal censoring authority."""

    challenge_key: ChallengeKey
    case: CanonicalChallengeCase
    case_ref: CanonicalChallengeCaseRef
    source_event: GenerationSourceEvent
    source_event_ref: object
    sampling_plan: SamplingPlan
    sampling_plan_ref: SamplingPlanRef
    prospective_censoring_policy_ref: object
    intended_evidence_unit_ref: object
    evidence_scope: EvidenceScopeBinding
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    generator_ref: object
    role_binding: GenerationRoleBinding

    def __post_init__(self) -> None:
        from .model import GenerationRoleBinding, GenerationSourceEvent

        if type(self) is not GeneratorCensoringRequest:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/request",
            )
        key = _challenge(self.challenge_key)
        case, case_ref = _exact_ref_pair(
            self.case,
            self.case_ref,
            CanonicalChallengeCase,
            CanonicalChallengeCaseRef,
            challenge_key=key,
            path="/case",
        )
        source_event = _exact(
            self.source_event,
            GenerationSourceEvent,
            "/source_event",
        )
        source_event_ref = _owner(
            self.source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/source_event_ref",
        )
        try:
            event_pair_matches = source_event.to_ref() == source_event_ref
        except (AuthoringError, GeneratorValidationError, TypeError, ValueError):
            event_pair_matches = False
        if not event_pair_matches:
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/source_event",
            )
        sampling_plan, sampling_plan_ref = _exact_ref_pair(
            self.sampling_plan,
            self.sampling_plan_ref,
            SamplingPlan,
            SamplingPlanRef,
            challenge_key=key,
            path="/sampling_plan",
        )
        primary = _top(
            self.primary_population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/primary_population_ref",
        )
        selection = _top(
            self.selection_population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/selection_population_ref",
        )
        policy_ref = _owner(
            self.prospective_censoring_policy_ref,
            "censoring_policy",
            challenge_key=key,
            path="/prospective_censoring_policy_ref",
        )
        intended_unit_ref = _owner(
            self.intended_evidence_unit_ref,
            "protected_intended_evidence_unit",
            challenge_key=key,
            path="/intended_evidence_unit_ref",
        )
        scope = _exact(self.evidence_scope, EvidenceScopeBinding, "/evidence_scope")
        generator_ref = _owner(
            self.generator_ref,
            "generator",
            challenge_key=key,
            path="/generator_ref",
        )
        role = _exact(self.role_binding, GenerationRoleBinding, "/role_binding")

        if (
            sampling_plan.primary_population_ref != primary
            or sampling_plan.selection_population_ref != selection
            or sampling_plan.censoring_policy_ref != policy_ref
            or role.sampling_plan_ref != sampling_plan_ref
            or role.sampling_role is not sampling_plan.sampling_role
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/sampling_plan",
            )
        if (
            source_event.primary_population_ref != primary
            or source_event.selection_population_ref != selection
            or source_event.sampling_plan_ref != sampling_plan_ref
            or source_event.generator_ref != generator_ref
            or source_event.role_binding != role
            or source_event.intended_evidence_unit_ref != intended_unit_ref
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/source_event",
            )
        case_source = case.case_source
        if (
            case.primary_population_ref != primary
            or not case.sampling_plan_binding.is_bound
            or case.sampling_plan_binding.value != sampling_plan_ref
            or not case.prospective_censoring_policy_binding.is_bound
            or case.prospective_censoring_policy_binding.value != policy_ref
            or type(case_source.payload) is not GeneratedCaseSource
            or case_source.kind is not CaseSourceKind.GENERATED
            or case_source.payload.generation_event_ref != source_event_ref
            or case_source.payload.generator_ref != generator_ref
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/case",
            )
        if (
            scope.evidence_campaign_binding != sampling_plan.evidence_campaign_binding
            or scope.query_population_binding != sampling_plan.query_population_binding
            or scope.observation_population_binding
            != sampling_plan.observation_population_binding
            or scope.intended_estimand_or_reporting_ref
            != sampling_plan.intended_estimand_or_reporting_ref
            or case.evidence_campaign_binding != scope.evidence_campaign_binding
            or case.query_population_binding != scope.query_population_binding
            or case.observation_population_binding
            != scope.observation_population_binding
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/evidence_scope",
            )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "case", case)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "source_event", source_event)
        object.__setattr__(self, "source_event_ref", source_event_ref)
        object.__setattr__(self, "sampling_plan", sampling_plan)
        object.__setattr__(self, "sampling_plan_ref", sampling_plan_ref)
        object.__setattr__(self, "prospective_censoring_policy_ref", policy_ref)
        object.__setattr__(self, "intended_evidence_unit_ref", intended_unit_ref)
        object.__setattr__(self, "generator_ref", generator_ref)

    def __repr__(self) -> str:
        return "GeneratorCensoringRequest(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("GeneratorCensoringRequest")


@dataclass(frozen=True, slots=True, repr=False)
class CensoringRecordBasis:
    """All externally owned censoring fields except replacement decision."""

    intended_evidence_unit_ref: object
    evidence_scope: EvidenceScopeBinding
    censoring_reason: CensoringReason
    trigger_failure_binding: CensoringTrigger
    actor_authority_ref: object
    population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    evidence_campaign_binding: ApplicabilityBinding[object]
    query_observation_provenance: tuple[object, ...]
    accounting_binding: object
    missingness_adjustment_binding: ApplicabilityBinding[object]
    audit_evidence_refs: tuple[object, ...]
    downstream_use_restrictions: tuple[object, ...]

    def __post_init__(self) -> None:
        if type(self) is not CensoringRecordBasis:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/basis",
            )
        plan_ref = _exact(
            self.sampling_plan_ref,
            SamplingPlanRef,
            "/sampling_plan_ref",
        )
        key = _challenge(plan_ref.challenge_key)
        intended_unit_ref = _owner(
            self.intended_evidence_unit_ref,
            "protected_intended_evidence_unit",
            challenge_key=key,
            path="/intended_evidence_unit_ref",
        )
        scope = _exact(self.evidence_scope, EvidenceScopeBinding, "/evidence_scope")
        if type(
            self.censoring_reason
        ) is not CensoringReason or self.censoring_reason not in {
            CensoringReason.EXPERIMENT_CORRUPTED,
            CensoringReason.EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER,
        }:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/censoring_reason",
            )
        trigger = _exact(
            self.trigger_failure_binding,
            CensoringTrigger,
            "/trigger_failure_binding",
        )
        expected_trigger_kind = {
            CensoringReason.EXPERIMENT_CORRUPTED: CensoringTriggerKind.EXPERIMENT,
            CensoringReason.EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER: (
                CensoringTriggerKind.EVIDENCE_ACQUISITION_INFRASTRUCTURE
            ),
        }[self.censoring_reason]
        if trigger.kind is not expected_trigger_kind:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/trigger_failure_binding",
            )
        if trigger.kind is CensoringTriggerKind.EXPERIMENT:
            _owner(
                trigger.payload,
                "experiment_corrupted",
                challenge_key=key,
                path="/trigger_failure_binding",
            )
        else:
            infrastructure = _exact(
                trigger.payload,
                InfrastructureCensoringTrigger,
                "/trigger_failure_binding",
            )
            _owner(
                infrastructure.acquisition_operation_ref,
                "evidence_acquisition_operation",
                challenge_key=key,
                path="/trigger_failure_binding",
            )
            _owner(
                infrastructure.infrastructure_failure_ref,
                "infrastructure_failure",
                challenge_key=key,
                path="/trigger_failure_binding",
            )
        actor = _owner(
            self.actor_authority_ref,
            "censoring_authority",
            challenge_key=key,
            path="/actor_authority_ref",
        )
        population_ref = _top(
            self.population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/population_ref",
        )
        campaign = _applicability_owner(
            self.evidence_campaign_binding,
            "evidence_campaign",
            challenge_key=key,
            path="/evidence_campaign_binding",
        )
        if campaign != scope.evidence_campaign_binding:
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/evidence_campaign_binding",
            )
        if (
            self.censoring_reason is CensoringReason.EXPERIMENT_CORRUPTED
            and not campaign.is_bound
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.INCOMPLETE_BINDING,
                path="/evidence_campaign_binding",
            )
        provenance = _owner_tuple(
            self.query_observation_provenance,
            "query_observation_provenance",
            challenge_key=key,
            path="/query_observation_provenance",
            nonempty=False,
        )
        provenance = canonical_set_tuple(provenance)
        query_or_observation = (
            scope.query_population_binding.is_bound
            or scope.observation_population_binding.is_bound
        )
        if bool(provenance) is not query_or_observation:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/query_observation_provenance",
            )
        accounting = _owner(
            self.accounting_binding,
            "censoring_accounting",
            challenge_key=key,
            path="/accounting_binding",
        )
        missingness = _applicability_owner(
            self.missingness_adjustment_binding,
            "missingness_adjustment",
            challenge_key=key,
            path="/missingness_adjustment_binding",
        )
        audit = _owner_tuple(
            self.audit_evidence_refs,
            "audit_evidence",
            challenge_key=key,
            path="/audit_evidence_refs",
        )
        audit = canonical_set_tuple(audit)
        restrictions = _owner_tuple(
            self.downstream_use_restrictions,
            "restriction",
            challenge_key=key,
            path="/downstream_use_restrictions",
        )
        restrictions = canonical_set_tuple(restrictions)
        object.__setattr__(self, "intended_evidence_unit_ref", intended_unit_ref)
        object.__setattr__(self, "actor_authority_ref", actor)
        object.__setattr__(self, "population_ref", population_ref)
        object.__setattr__(self, "query_observation_provenance", provenance)
        object.__setattr__(self, "accounting_binding", accounting)
        object.__setattr__(self, "missingness_adjustment_binding", missingness)
        object.__setattr__(self, "audit_evidence_refs", audit)
        object.__setattr__(self, "downstream_use_restrictions", restrictions)

    def __repr__(self) -> str:
        return "CensoringRecordBasis(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("CensoringRecordBasis")


@dataclass(frozen=True, slots=True, repr=False)
class CensoringVerdict:
    challenge_key: ChallengeKey
    request: GeneratorCensoringRequest
    verdict_kind: CensoringVerdictKind
    basis: CensoringRecordBasis | None
    infrastructure_failure_ref: object | None

    def __post_init__(self) -> None:
        if type(self) is not CensoringVerdict:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/censoring_verdict",
            )
        key = _challenge(self.challenge_key)
        request = replace(
            _exact(
                self.request,
                GeneratorCensoringRequest,
                "/request",
            )
        )
        if request.challenge_key != key:
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path="/request",
            )
        if type(self.verdict_kind) is not CensoringVerdictKind:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/verdict_kind",
            )
        if self.verdict_kind is CensoringVerdictKind.CENSORED:
            basis = replace(_exact(self.basis, CensoringRecordBasis, "/basis"))
            failure_ref = None
            if self.infrastructure_failure_ref is not None:
                raise GeneratorValidationError(
                    GeneratorInputCode.INVALID_VALUE,
                    path="/infrastructure_failure_ref",
                )
            if (
                basis.intended_evidence_unit_ref != request.intended_evidence_unit_ref
                or basis.evidence_scope != request.evidence_scope
                or basis.population_ref != request.primary_population_ref
                or basis.sampling_plan_ref != request.sampling_plan_ref
            ):
                raise GeneratorValidationError(
                    GeneratorInputCode.STALE_BINDING,
                    path="/basis",
                )
        elif self.verdict_kind is CensoringVerdictKind.NOT_CENSORED:
            if self.basis is not None or self.infrastructure_failure_ref is not None:
                raise GeneratorValidationError(
                    GeneratorInputCode.INVALID_VALUE,
                    path="/verdict_kind",
                )
            basis = None
            failure_ref = None
        else:
            if self.basis is not None:
                raise GeneratorValidationError(
                    GeneratorInputCode.INVALID_VALUE,
                    path="/basis",
                )
            failure_ref = _owner(
                self.infrastructure_failure_ref,
                "infrastructure_failure",
                challenge_key=key,
                path="/infrastructure_failure_ref",
            )
            basis = None
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "basis", basis)
        object.__setattr__(self, "infrastructure_failure_ref", failure_ref)

    def __repr__(self) -> str:
        return "CensoringVerdict(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("CensoringVerdict")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> CensoringVerdictRef:
        from .canonical import _record_ref

        return _record_ref(self, CensoringVerdictRef)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True, repr=False)
class CensoringDecision:
    challenge_key: ChallengeKey
    request: GeneratorCensoringRequest
    verdict: CensoringVerdict
    verdict_ref: CensoringVerdictRef
    accounting_decision: AttemptAccountingDecision
    accounting_decision_ref: AttemptAccountingDecisionRef
    censoring_record: CensoringRecord | None
    censoring_record_ref: CensoringRecordRef | None

    def __post_init__(self) -> None:
        from .accounting import AttemptAccountingDecision
        from .model import GeneratorOutcomeKind, GeneratorTerminalStage

        if type(self) is not CensoringDecision:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/censoring_decision",
            )
        key = _challenge(self.challenge_key)
        request = _exact(
            self.request,
            GeneratorCensoringRequest,
            "/request",
        )
        if request.challenge_key != key:
            raise GeneratorValidationError(
                GeneratorInputCode.CROSS_CHALLENGE,
                path="/request",
            )
        verdict, verdict_ref = _exact_ref_pair(
            self.verdict,
            self.verdict_ref,
            CensoringVerdict,
            CensoringVerdictRef,
            challenge_key=key,
            path="/verdict",
        )
        accounting, accounting_ref = _exact_ref_pair(
            self.accounting_decision,
            self.accounting_decision_ref,
            AttemptAccountingDecision,
            AttemptAccountingDecisionRef,
            challenge_key=key,
            path="/accounting_decision",
        )
        if verdict.request != request:
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/verdict",
            )
        if (
            accounting.request_ref != request.source_event.request_ref
            or accounting.source_event_ref != request.source_event_ref
            or accounting.attempt_ref != request.source_event.attempt_ref
            or accounting.intended_evidence_unit_ref
            != request.intended_evidence_unit_ref
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.STALE_BINDING,
                path="/accounting_decision",
            )

        terminal = (accounting.final_outcome, accounting.final_stage)
        if verdict.verdict_kind is CensoringVerdictKind.CENSORED:
            expected = (
                GeneratorOutcomeKind.CENSORED_CASE,
                GeneratorTerminalStage.CENSORING_COMPLETION,
            )
            if (
                terminal != expected
                or not accounting.outcome_replacement_binding.is_bound
            ):
                raise GeneratorValidationError(
                    GeneratorInputCode.STALE_BINDING,
                    path="/accounting_decision",
                )
            record, record_ref = _exact_ref_pair(
                self.censoring_record,
                self.censoring_record_ref,
                CensoringRecord,
                CensoringRecordRef,
                challenge_key=None,
                path="/censoring_record",
            )
            basis = _exact(verdict.basis, CensoringRecordBasis, "/verdict/basis")
            if (
                record.intended_evidence_unit_ref != basis.intended_evidence_unit_ref
                or record.evidence_scope != basis.evidence_scope
                or record.censoring_reason is not basis.censoring_reason
                or record.trigger_failure_binding != basis.trigger_failure_binding
                or record.actor_authority_ref != basis.actor_authority_ref
                or record.population_ref != basis.population_ref
                or record.sampling_plan_ref != basis.sampling_plan_ref
                or record.evidence_campaign_binding != basis.evidence_campaign_binding
                or record.query_observation_provenance
                != basis.query_observation_provenance
                or record.replacement_decision
                != accounting.outcome_replacement_binding.value
                or record.accounting_binding != basis.accounting_binding
                or record.missingness_adjustment_binding
                != basis.missingness_adjustment_binding
                or record.audit_evidence_refs != basis.audit_evidence_refs
                or record.downstream_use_restrictions
                != basis.downstream_use_restrictions
            ):
                raise GeneratorValidationError(
                    GeneratorInputCode.STALE_BINDING,
                    path="/censoring_record",
                )
            invalid_record = False
            try:
                validate_censoring_against_plan(record, request.sampling_plan)
            except (AuthoringError, TypeError, ValueError):
                invalid_record = True
            if invalid_record:
                raise GeneratorValidationError(
                    GeneratorInputCode.INVALID_VALUE,
                    path="/censoring_record",
                )
        else:
            if (
                self.censoring_record is not None
                or self.censoring_record_ref is not None
            ):
                raise GeneratorValidationError(
                    GeneratorInputCode.INVALID_VALUE,
                    path="/censoring_record",
                )
            record = None
            record_ref = None
            allowed = {
                CensoringVerdictKind.NOT_CENSORED: {
                    (
                        GeneratorOutcomeKind.VALID_GENERATED,
                        GeneratorTerminalStage.CENSORING_COMPLETION,
                    ),
                    (
                        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                        GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
                    ),
                },
                CensoringVerdictKind.AUTHORITY_UNAVAILABLE: {
                    (
                        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                        GeneratorTerminalStage.CENSORING_AUTHORITY,
                    ),
                    (
                        GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                        GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
                    ),
                },
            }[verdict.verdict_kind]
            if terminal not in allowed:
                raise GeneratorValidationError(
                    GeneratorInputCode.STALE_BINDING,
                    path="/accounting_decision",
                )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(self, "verdict_ref", verdict_ref)
        object.__setattr__(self, "accounting_decision", accounting)
        object.__setattr__(self, "accounting_decision_ref", accounting_ref)
        object.__setattr__(self, "censoring_record", record)
        object.__setattr__(self, "censoring_record_ref", record_ref)

    def __repr__(self) -> str:
        return "CensoringDecision(<protected>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise _redacted_reduce("CensoringDecision")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> CensoringDecisionRef:
        from .canonical import _record_ref

        return _record_ref(self, CensoringDecisionRef)  # type: ignore[return-value]


def finalize_censoring_decision(
    *,
    request: GeneratorCensoringRequest,
    verdict: CensoringVerdict,
    verdict_ref: CensoringVerdictRef,
    accounting_decision: AttemptAccountingDecision,
    accounting_decision_ref: AttemptAccountingDecisionRef,
) -> tuple[CensoringDecision, CensoringDecisionRef]:
    """Finalize the acyclic verdict -> accounting -> censoring record path."""

    from .accounting import AttemptAccountingDecision

    checked_request = _exact(
        request,
        GeneratorCensoringRequest,
        "/request",
    )
    checked_verdict, checked_verdict_ref = _exact_ref_pair(
        verdict,
        verdict_ref,
        CensoringVerdict,
        CensoringVerdictRef,
        challenge_key=checked_request.challenge_key,
        path="/verdict",
    )
    checked_accounting, checked_accounting_ref = _exact_ref_pair(
        accounting_decision,
        accounting_decision_ref,
        AttemptAccountingDecision,
        AttemptAccountingDecisionRef,
        challenge_key=checked_request.challenge_key,
        path="/accounting_decision",
    )
    record: CensoringRecord | None = None
    record_ref: CensoringRecordRef | None = None
    if checked_verdict.verdict_kind is CensoringVerdictKind.CENSORED:
        basis = _exact(checked_verdict.basis, CensoringRecordBasis, "/basis")
        replacement = checked_accounting.outcome_replacement_binding
        if (
            not replacement.is_bound
            or type(replacement.value) is not ReplacementDecision
        ):
            raise GeneratorValidationError(
                GeneratorInputCode.INCOMPLETE_BINDING,
                path="/accounting_decision/outcome_replacement_binding",
            )
        invalid_record = False
        try:
            record = CensoringRecord(
                schema_version=AUTHORING_SCHEMA_VERSION,
                canonicalization_profile=(DERIVED_EVIDENCE_CANONICALIZATION_PROFILE),
                intended_evidence_unit_ref=basis.intended_evidence_unit_ref,
                evidence_scope=basis.evidence_scope,
                censoring_reason=basis.censoring_reason,
                trigger_failure_binding=basis.trigger_failure_binding,
                actor_authority_ref=basis.actor_authority_ref,
                population_ref=basis.population_ref,
                sampling_plan_ref=basis.sampling_plan_ref,
                evidence_campaign_binding=basis.evidence_campaign_binding,
                query_observation_provenance=(basis.query_observation_provenance),
                replacement_decision=replacement.value,
                accounting_binding=basis.accounting_binding,
                missingness_adjustment_binding=(basis.missingness_adjustment_binding),
                audit_evidence_refs=basis.audit_evidence_refs,
                downstream_use_restrictions=(basis.downstream_use_restrictions),
            )
            validate_censoring_against_plan(record, checked_request.sampling_plan)
            record_ref = record.to_ref()
        except (AuthoringError, TypeError, ValueError):
            invalid_record = True
            record = None
            record_ref = None
        if invalid_record:
            raise GeneratorValidationError(
                GeneratorInputCode.INVALID_VALUE,
                path="/censoring_record",
            )
    decision = CensoringDecision(
        challenge_key=checked_request.challenge_key,
        request=checked_request,
        verdict=checked_verdict,
        verdict_ref=checked_verdict_ref,
        accounting_decision=checked_accounting,
        accounting_decision_ref=checked_accounting_ref,
        censoring_record=record,
        censoring_record_ref=record_ref,
    )
    return decision, decision.to_ref()


# Closed authority-owned canonical schemas.  Requests and bases are nested
# only; decisions/verdicts are the literal standalone records named by B-03.
from .accounting import AttemptAccountingDecision
from .burgers import FixturePayloadFacts, ProtectedBurgersFixturePayload
from .canonical import (
    _CHALLENGE_KEY,
    _REPLAY_REF,
    _applicability,
    _authoring,
    _enum,
    _generator_ref,
    _nested,
    _optional,
    _record,
    _register_canonical_type,
    _register_nested_canonical_type,
    _top_ref,
    _tuple_of,
)
from .canonical import _owner as _owner_codec
from .model import GenerationRoleBinding, GenerationSourceEvent
from .refs import (
    BurgersFixtureConfigurationRef,
    GeneratorEnvironmentRef,
    GeneratorRequestRef,
)

_register_nested_canonical_type(
    IntendedUnitLinkRequest,
    record_type="intended_unit_link_request",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
        (
            "selection_population_ref",
            _top_ref(InstanceDistributionContractRef),
        ),
        ("role_binding", _nested(GenerationRoleBinding)),
        ("replay_ref", _REPLAY_REF),
        ("intended_slot_ref", _owner_codec("protected_intended_slot")),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("attempt_ref", _owner_codec("protected_attempt_commitment")),
    ),
)
_register_canonical_type(
    IntendedUnitLinkDecision,
    object_kind="intended_unit_link_decision",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request", _nested(IntendedUnitLinkRequest)),
        ("link_evidence_ref", _owner_codec("authority_evidence")),
    ),
)
_register_nested_canonical_type(
    PopulationSupportAssessment,
    record_type="population_support_assessment",
    fields=(
        ("assessment_role", _enum(PopulationAssessmentRole)),
        ("population_ref", _top_ref(InstanceDistributionContractRef)),
        ("support_contract", _authoring(SupportContract)),
        (
            "exclusion_contract_binding",
            _applicability(_authoring(ExclusionContract)),
        ),
        ("decision_kind", _enum(PopulationSupportDecisionKind)),
        (
            "applicability_evidence_binding",
            _applicability(_owner_codec("applicability_evidence")),
        ),
        (
            "membership_evidence_binding",
            _applicability(_owner_codec("membership_evidence")),
        ),
        (
            "exclusion_contract_ref_binding",
            _applicability(_owner_codec("exclusion_contract")),
        ),
        (
            "prospective_exclusion_contract_ref_binding",
            _applicability(_owner_codec("prospective_exclusion_contract")),
        ),
        (
            "exclusion_assessment_ref_binding",
            _applicability(_owner_codec("exclusion_assessment")),
        ),
        (
            "screening_design_ref_binding",
            _applicability(_owner_codec("screening_design")),
        ),
        (
            "inclusion_probability_accounting_ref_binding",
            _applicability(_owner_codec("inclusion_probability_accounting")),
        ),
        (
            "infrastructure_failure_binding",
            _applicability(_owner_codec("infrastructure_failure")),
        ),
    ),
)
_register_nested_canonical_type(
    SupportExclusionRequest,
    record_type="support_exclusion_request",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("generator_request_ref", _generator_ref(GeneratorRequestRef)),
        ("source_event", _record(GenerationSourceEvent)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("protected_payload", _record(ProtectedBurgersFixturePayload)),
        ("protected_payload_ref", _owner_codec("protected_case_payload")),
        ("physical_system_ref", _top_ref(PhysicalSystemSpecRef)),
        ("candidate_output_ref", _top_ref(CandidateOutputContractRef)),
        ("primary_population_ref", _top_ref(InstanceDistributionContractRef)),
        (
            "selection_population_ref",
            _top_ref(InstanceDistributionContractRef),
        ),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
        ("generator_ref", _owner_codec("generator")),
        ("environment_ref", _generator_ref(GeneratorEnvironmentRef)),
        (
            "fixture_configuration_ref",
            _generator_ref(BurgersFixtureConfigurationRef),
        ),
        ("role_binding", _nested(GenerationRoleBinding)),
        ("replay_ref", _REPLAY_REF),
        ("intended_slot_ref", _owner_codec("protected_intended_slot")),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("attempt_ref", _owner_codec("protected_attempt_commitment")),
        ("fixture_payload_facts", _nested(FixturePayloadFacts)),
    ),
)
_register_canonical_type(
    SupportExclusionDecision,
    object_kind="support_exclusion_decision",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request", _nested(SupportExclusionRequest)),
        ("decision_kind", _enum(SupportExclusionDecisionKind)),
        ("assessments", _tuple_of(_nested(PopulationSupportAssessment))),
        ("terminal_resolution", _enum(PopulationSupportDecisionKind)),
        (
            "effective_assessment_role",
            _optional(_enum(PopulationAssessmentRole)),
        ),
        ("resolution_policy_ref", _optional(_owner_codec("policy_authority"))),
        (
            "resolution_evidence_ref",
            _optional(_owner_codec("membership_decision")),
        ),
        (
            "infrastructure_failure_ref",
            _optional(_owner_codec("infrastructure_failure")),
        ),
    ),
)
_register_nested_canonical_type(
    GeneratorCensoringRequest,
    record_type="generator_censoring_request",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("case", _authoring(CanonicalChallengeCase)),
        ("case_ref", _top_ref(CanonicalChallengeCaseRef)),
        ("source_event", _record(GenerationSourceEvent)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("sampling_plan", _authoring(SamplingPlan)),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
        (
            "prospective_censoring_policy_ref",
            _owner_codec("censoring_policy"),
        ),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("evidence_scope", _authoring(EvidenceScopeBinding)),
        ("primary_population_ref", _top_ref(InstanceDistributionContractRef)),
        (
            "selection_population_ref",
            _top_ref(InstanceDistributionContractRef),
        ),
        ("generator_ref", _owner_codec("generator")),
        ("role_binding", _nested(GenerationRoleBinding)),
    ),
)
_register_nested_canonical_type(
    CensoringRecordBasis,
    record_type="censoring_record_basis",
    fields=(
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("evidence_scope", _authoring(EvidenceScopeBinding)),
        ("censoring_reason", _enum(CensoringReason)),
        ("trigger_failure_binding", _authoring(CensoringTrigger)),
        ("actor_authority_ref", _owner_codec("censoring_authority")),
        ("population_ref", _top_ref(InstanceDistributionContractRef)),
        ("sampling_plan_ref", _top_ref(SamplingPlanRef)),
        (
            "evidence_campaign_binding",
            _applicability(_owner_codec("evidence_campaign")),
        ),
        (
            "query_observation_provenance",
            _tuple_of(
                _owner_codec("query_observation_provenance"),
                set_like=True,
            ),
        ),
        ("accounting_binding", _owner_codec("censoring_accounting")),
        (
            "missingness_adjustment_binding",
            _applicability(_owner_codec("missingness_adjustment")),
        ),
        (
            "audit_evidence_refs",
            _tuple_of(_owner_codec("audit_evidence"), set_like=True),
        ),
        (
            "downstream_use_restrictions",
            _tuple_of(_owner_codec("restriction"), set_like=True),
        ),
    ),
)
_register_canonical_type(
    CensoringVerdict,
    object_kind="generator_censoring_verdict",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request", _nested(GeneratorCensoringRequest)),
        ("verdict_kind", _enum(CensoringVerdictKind)),
        ("basis", _optional(_nested(CensoringRecordBasis))),
        (
            "infrastructure_failure_ref",
            _optional(_owner_codec("infrastructure_failure")),
        ),
    ),
)
_register_canonical_type(
    CensoringDecision,
    object_kind="generator_censoring_decision",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request", _nested(GeneratorCensoringRequest)),
        ("verdict", _record(CensoringVerdict)),
        ("verdict_ref", _generator_ref(CensoringVerdictRef)),
        ("accounting_decision", _record(AttemptAccountingDecision)),
        (
            "accounting_decision_ref",
            _generator_ref(AttemptAccountingDecisionRef),
        ),
        ("censoring_record", _optional(_authoring(CensoringRecord))),
        ("censoring_record_ref", _optional(_authoring(CensoringRecordRef))),
    ),
)


__all__ = (
    "CensoringDecision",
    "CensoringRecordBasis",
    "CensoringVerdict",
    "CensoringVerdictKind",
    "FixtureGenerationAuthority",
    "FixtureGenerationGrant",
    "FixtureReplayProbeAuthority",
    "GeneratorCensoringAuthority",
    "GeneratorCensoringRequest",
    "IntendedUnitLinkAuthority",
    "IntendedUnitLinkDecision",
    "IntendedUnitLinkRequest",
    "PopulationAssessmentRole",
    "PopulationSupportAssessment",
    "PopulationSupportDecisionKind",
    "SupportExclusionAuthority",
    "SupportExclusionDecision",
    "SupportExclusionDecisionKind",
    "SupportExclusionRequest",
    "finalize_censoring_decision",
)
