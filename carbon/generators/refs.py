"""Exact nominal references for B-03 generator-runtime records."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import ClassVar, TypeAlias

from carbon.authoring.canonical import (
    CanonicalNominalRef,
    CanonicalRecord,
    CanonicalText,
    challenge_key_from_canonical,
    challenge_key_to_canonical,
    decode_value,
    encode_value,
    owner_ref_from_canonical,
    owner_ref_to_canonical,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import (
    MAX_CANONICAL_PAYLOAD_BYTES,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.authoring.refs import ChallengeScope, owner_ref, require_owner_ref
from carbon.registry.model import ChallengeKey

from .errors import (
    GeneratorCanonicalDecodingError,
    GeneratorInputCode,
    GeneratorValidationError,
)

GENERATOR_RUNTIME_SCHEMA_VERSION = "1.0"
GENERATOR_RUNTIME_CANONICALIZATION_PROFILE = "carbon_generator_runtime_canonical_v1"


def _wrong(code: GeneratorInputCode, path: str) -> GeneratorValidationError:
    return GeneratorValidationError(code, path=path)


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        result = reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError):
        pass
    else:
        return result
    raise _wrong(GeneratorInputCode.WRONG_TYPE, path)


def _identifier(value: object, path: str) -> str:
    try:
        checked = validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        checked = None
    if checked is None:
        raise _wrong(GeneratorInputCode.INVALID_VALUE, path)
    if len(checked.encode("ascii")) > MAX_CANONICAL_PAYLOAD_BYTES:
        raise _wrong(GeneratorInputCode.INVALID_VALUE, path)
    return checked


def _version(value: object, path: str) -> str:
    try:
        result = validate_version_token(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    else:
        return result
    raise _wrong(GeneratorInputCode.INVALID_VALUE, path)


def _digest(value: object, path: str = "/content_digest") -> str:
    try:
        result = validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    else:
        return result
    raise _wrong(GeneratorInputCode.INVALID_VALUE, path)


def _schema_profile(schema: object, profile: object) -> tuple[str, str]:
    checked_schema = _version(schema, "/schema_version")
    if (
        checked_schema != GENERATOR_RUNTIME_SCHEMA_VERSION
        or type(profile) is not str
        or profile != GENERATOR_RUNTIME_CANONICALIZATION_PROFILE
    ):
        raise _wrong(GeneratorInputCode.INVALID_VALUE, "/schema_version")
    return checked_schema, profile


@dataclass(frozen=True, slots=True, repr=False)
class _GeneratorRuntimeRefBase:
    challenge_key: ChallengeKey
    content_digest: str
    schema_version: str = GENERATOR_RUNTIME_SCHEMA_VERSION
    canonicalization_profile: str = GENERATOR_RUNTIME_CANONICALIZATION_PROFILE

    RECORD_TYPE: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _REF_TYPES_BY_RECORD_TYPE.get(self.RECORD_TYPE)
        if expected is None or type(self) is not expected:
            raise _wrong(GeneratorInputCode.WRONG_TYPE, "/ref_type")
        schema, profile = _schema_profile(
            self.schema_version, self.canonicalization_profile
        )
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "content_digest", _digest(self.content_digest))
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)

    @property
    def record_type(self) -> str:
        return self.RECORD_TYPE

    @property
    def ref_type(self) -> str:
        return f"{self.RECORD_TYPE}_ref"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected generator refs cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected generator refs cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorEnvironmentRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generator_environment"


@dataclass(frozen=True, slots=True, repr=False)
class BurgersFixtureConfigurationRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "burgers_fixture_configuration"


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorRequestRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generator_request"


@dataclass(frozen=True, slots=True, repr=False)
class IntendedUnitLinkDecisionRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "intended_unit_link_decision"


@dataclass(frozen=True, slots=True, repr=False)
class SupportExclusionDecisionRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "support_exclusion_decision"


@dataclass(frozen=True, slots=True, repr=False)
class CensoringVerdictRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generator_censoring_verdict"


@dataclass(frozen=True, slots=True, repr=False)
class CensoringDecisionRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generator_censoring_decision"


@dataclass(frozen=True, slots=True, repr=False)
class AttemptAccountingDirectiveRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "attempt_accounting_directive"


@dataclass(frozen=True, slots=True, repr=False)
class AttemptAccountingDecisionRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "attempt_accounting_decision"


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorFailureReasonRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generator_failure_reason"


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorFailureOccurrenceRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generator_failure_occurrence"


@dataclass(frozen=True, slots=True, repr=False)
class PendingGenerationAttemptRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "pending_generation_attempt"


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorResultRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generator_result"


@dataclass(frozen=True, slots=True, repr=False)
class GenerationAttemptRecordRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generation_attempt_record"


@dataclass(frozen=True, slots=True, repr=False)
class IntendedUnitAccountingRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "intended_unit_accounting"


@dataclass(frozen=True, slots=True, repr=False)
class GenerationAccountingSummaryRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generation_accounting_summary"


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorConformanceFactsRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "generator_conformance_facts"


@dataclass(frozen=True, slots=True, repr=False)
class PhysicalPayloadFingerprintRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "physical_payload_fingerprint"


@dataclass(frozen=True, slots=True, repr=False)
class FixtureReplayProbeRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "fixture_replay_probe"


@dataclass(frozen=True, slots=True, repr=False)
class DeterministicReplayComparisonRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "deterministic_replay_comparison"


@dataclass(frozen=True, slots=True, repr=False)
class ComparisonCorpusDecisionRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "comparison_corpus_decision"


@dataclass(frozen=True, slots=True, repr=False)
class DuplicateConformanceFactsRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "duplicate_conformance_facts"


@dataclass(frozen=True, slots=True, repr=False)
class ExternalDistributionFactSetRef(_GeneratorRuntimeRefBase):
    RECORD_TYPE: ClassVar[str] = "external_distribution_fact_set"


GENERATOR_RUNTIME_REF_TYPES = (
    GeneratorEnvironmentRef,
    BurgersFixtureConfigurationRef,
    GeneratorRequestRef,
    IntendedUnitLinkDecisionRef,
    SupportExclusionDecisionRef,
    CensoringVerdictRef,
    CensoringDecisionRef,
    AttemptAccountingDirectiveRef,
    AttemptAccountingDecisionRef,
    GeneratorFailureReasonRef,
    GeneratorFailureOccurrenceRef,
    PendingGenerationAttemptRef,
    GeneratorResultRef,
    GenerationAttemptRecordRef,
    IntendedUnitAccountingRef,
    GenerationAccountingSummaryRef,
    GeneratorConformanceFactsRef,
    PhysicalPayloadFingerprintRef,
    FixtureReplayProbeRef,
    DeterministicReplayComparisonRef,
    ComparisonCorpusDecisionRef,
    DuplicateConformanceFactsRef,
    ExternalDistributionFactSetRef,
)
_REF_TYPES_BY_RECORD_TYPE = {
    ref_type.RECORD_TYPE: ref_type for ref_type in GENERATOR_RUNTIME_REF_TYPES
}

GeneratorRuntimeRef: TypeAlias = (
    GeneratorEnvironmentRef
    | BurgersFixtureConfigurationRef
    | GeneratorRequestRef
    | IntendedUnitLinkDecisionRef
    | SupportExclusionDecisionRef
    | CensoringVerdictRef
    | CensoringDecisionRef
    | AttemptAccountingDirectiveRef
    | AttemptAccountingDecisionRef
    | GeneratorFailureReasonRef
    | GeneratorFailureOccurrenceRef
    | PendingGenerationAttemptRef
    | GeneratorResultRef
    | GenerationAttemptRecordRef
    | IntendedUnitAccountingRef
    | GenerationAccountingSummaryRef
    | GeneratorConformanceFactsRef
    | PhysicalPayloadFingerprintRef
    | FixtureReplayProbeRef
    | DeterministicReplayComparisonRef
    | ComparisonCorpusDecisionRef
    | DuplicateConformanceFactsRef
    | ExternalDistributionFactSetRef
)


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorReplayCommitmentRef:
    """Opaque, capability-issued replay reservation identity."""

    challenge_key: ChallengeKey
    replay_scheme_id: str
    replay_scheme_version: str
    reservation_issuer_ref: object
    commitment_digest: str

    def __post_init__(self) -> None:
        if type(self) is not GeneratorReplayCommitmentRef:
            raise _wrong(GeneratorInputCode.WRONG_TYPE, "/replay_ref")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self,
            "replay_scheme_id",
            _identifier(self.replay_scheme_id, "/replay_scheme_id"),
        )
        object.__setattr__(
            self,
            "replay_scheme_version",
            _version(self.replay_scheme_version, "/replay_scheme_version"),
        )
        try:
            issuer = require_owner_ref(
                self.reservation_issuer_ref, "authority_evidence"
            )
        except (AuthoringError, TypeError, ValueError):
            issuer = None
        if issuer is None:
            raise _wrong(GeneratorInputCode.WRONG_TYPE, "/reservation_issuer_ref")
        scope = object.__getattribute__(issuer, "scope_binding")
        if (
            type(scope) is not ChallengeScope
            or scope.challenge_key != self.challenge_key
        ):
            raise _wrong(GeneratorInputCode.CROSS_CHALLENGE, "/reservation_issuer_ref")
        object.__setattr__(self, "reservation_issuer_ref", issuer)
        object.__setattr__(
            self,
            "commitment_digest",
            _digest(self.commitment_digest, "/commitment_digest"),
        )

    def __repr__(self) -> str:
        return "GeneratorReplayCommitmentRef(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected replay commitments cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected replay commitments cannot be pickled")


def is_generator_ref(value: object) -> bool:
    return type(value) in GENERATOR_RUNTIME_REF_TYPES


def reconstruct_generator_ref(value: object) -> GeneratorRuntimeRef:
    if not is_generator_ref(value):
        raise _wrong(GeneratorInputCode.WRONG_TYPE, "/ref_type")
    return type(value)(
        value.challenge_key,
        value.content_digest,
        value.schema_version,
        value.canonicalization_profile,
    )


def generator_ref_to_canonical(value: object) -> CanonicalNominalRef:
    ref = reconstruct_generator_ref(value)
    return CanonicalNominalRef(
        ref.ref_type,
        CanonicalRecord(
            ref.ref_type,
            (
                (
                    "canonicalization_profile",
                    CanonicalText(ref.canonicalization_profile),
                ),
                ("challenge_key", challenge_key_to_canonical(ref.challenge_key)),
                ("content_digest", CanonicalText(ref.content_digest)),
                ("record_type", CanonicalText(ref.record_type)),
                ("schema_version", CanonicalText(ref.schema_version)),
            ),
        ),
    )


def generator_ref_from_canonical(
    value: object,
    *,
    expected_type: type | None = None,
) -> GeneratorRuntimeRef:
    if type(value) is not CanonicalNominalRef:
        raise GeneratorCanonicalDecodingError(path="/ref")
    candidates = tuple(
        ref_type
        for ref_type in GENERATOR_RUNTIME_REF_TYPES
        if f"{ref_type.RECORD_TYPE}_ref" == value.ref_type
    )
    if expected_type is not None:
        if (
            type(expected_type) is not type
            or expected_type not in GENERATOR_RUNTIME_REF_TYPES
        ):
            raise TypeError(
                "expected_type must be an exact generator-runtime ref class"
            )
        candidates = tuple(item for item in candidates if item is expected_type)
    if len(candidates) != 1 or value.record.record_type != value.ref_type:
        raise GeneratorCanonicalDecodingError(path="/ref")
    fields = value.record.field_map()
    if set(fields) != {
        "canonicalization_profile",
        "challenge_key",
        "content_digest",
        "record_type",
        "schema_version",
    }:
        raise GeneratorCanonicalDecodingError(path="/ref")

    def text(name: str) -> str:
        item = fields[name]
        if type(item) is not CanonicalText:
            raise GeneratorCanonicalDecodingError(path=f"/ref/{name}")
        return item.value

    ref_type = candidates[0]
    if text("record_type") != ref_type.RECORD_TYPE:
        raise GeneratorCanonicalDecodingError(path="/ref/record_type")
    try:
        result = ref_type(
            challenge_key_from_canonical(fields["challenge_key"]),
            text("content_digest"),
            text("schema_version"),
            text("canonicalization_profile"),
        )
    except (AuthoringError, GeneratorValidationError, TypeError, ValueError):
        result = None
    if result is None:
        raise GeneratorCanonicalDecodingError(path="/ref")
    if not hmac.compare_digest(
        encode_value(generator_ref_to_canonical(result)), encode_value(value)
    ):
        raise GeneratorCanonicalDecodingError(path="/ref")
    return result


def encode_generator_ref(value: object) -> bytes:
    try:
        result = encode_value(generator_ref_to_canonical(value))
    except (AuthoringError, GeneratorValidationError):
        pass
    else:
        return result
    raise GeneratorValidationError(GeneratorInputCode.INVALID_VALUE, path="/ref")


def decode_generator_ref(
    payload: object,
    expected_type: type | None = None,
) -> GeneratorRuntimeRef:
    if type(payload) is not bytes:
        raise _wrong(GeneratorInputCode.WRONG_TYPE, "/canonical_bytes")
    decode_failed = False
    trailing = False
    try:
        value = decode_value(payload)
    except AuthoringError as exc:
        decode_failed = True
        trailing = "trailing" in exc.code
        value = None
    if decode_failed:
        raise GeneratorCanonicalDecodingError(
            trailing=trailing,
            path="/canonical_bytes",
        )
    return generator_ref_from_canonical(value, expected_type=expected_type)


def generator_ref(descriptor: object) -> object:
    """Compute the existing B-02A ``generator`` owner ref for a descriptor."""

    from .model import GeneratorDescriptor

    if type(descriptor) is not GeneratorDescriptor:
        raise _wrong(GeneratorInputCode.WRONG_TYPE, "/generator")
    from .canonical import canonical_content_digest

    return owner_ref(
        "generator",
        scope_binding=ChallengeScope(descriptor.challenge_key),
        object_id=descriptor.generator_id,
        object_version=descriptor.generator_version,
        content_digest=canonical_content_digest(descriptor),
    )


def verify_generator_ref(record: object, ref: object) -> None:
    """Verify one exact B-03 record/ref pair."""

    from .canonical import verify_canonical_ref

    verify_canonical_ref(record, ref)


def replay_ref_to_canonical(value: object) -> CanonicalRecord:
    if type(value) is not GeneratorReplayCommitmentRef:
        raise _wrong(GeneratorInputCode.WRONG_TYPE, "/replay_ref")
    return CanonicalRecord(
        "generator_replay_commitment_ref",
        (
            ("challenge_key", challenge_key_to_canonical(value.challenge_key)),
            ("commitment_digest", CanonicalText(value.commitment_digest)),
            ("replay_scheme_id", CanonicalText(value.replay_scheme_id)),
            (
                "replay_scheme_version",
                CanonicalText(value.replay_scheme_version),
            ),
            (
                "reservation_issuer_ref",
                owner_ref_to_canonical(value.reservation_issuer_ref),
            ),
        ),
    )


def replay_ref_from_canonical(value: object) -> GeneratorReplayCommitmentRef:
    if (
        type(value) is not CanonicalRecord
        or value.record_type != "generator_replay_commitment_ref"
    ):
        raise GeneratorCanonicalDecodingError(path="/replay_ref")
    fields = value.field_map()
    if set(fields) != {
        "challenge_key",
        "commitment_digest",
        "replay_scheme_id",
        "replay_scheme_version",
        "reservation_issuer_ref",
    }:
        raise GeneratorCanonicalDecodingError(path="/replay_ref")

    def text(name: str) -> str:
        item = fields[name]
        if type(item) is not CanonicalText:
            raise GeneratorCanonicalDecodingError(path=f"/replay_ref/{name}")
        return item.value

    try:
        result = GeneratorReplayCommitmentRef(
            challenge_key_from_canonical(fields["challenge_key"]),
            text("replay_scheme_id"),
            text("replay_scheme_version"),
            owner_ref_from_canonical(
                fields["reservation_issuer_ref"], expected_kind="authority_evidence"
            ),
            text("commitment_digest"),
        )
    except (AuthoringError, GeneratorValidationError, TypeError, ValueError):
        result = None
    if result is None:
        raise GeneratorCanonicalDecodingError(path="/replay_ref")
    return result


__all__ = [
    "GENERATOR_RUNTIME_CANONICALIZATION_PROFILE",
    "GENERATOR_RUNTIME_REF_TYPES",
    "GENERATOR_RUNTIME_SCHEMA_VERSION",
    "AttemptAccountingDecisionRef",
    "AttemptAccountingDirectiveRef",
    "BurgersFixtureConfigurationRef",
    "CensoringDecisionRef",
    "CensoringVerdictRef",
    "ComparisonCorpusDecisionRef",
    "DeterministicReplayComparisonRef",
    "DuplicateConformanceFactsRef",
    "ExternalDistributionFactSetRef",
    "FixtureReplayProbeRef",
    "GenerationAccountingSummaryRef",
    "GenerationAttemptRecordRef",
    "GeneratorConformanceFactsRef",
    "GeneratorEnvironmentRef",
    "GeneratorFailureOccurrenceRef",
    "GeneratorFailureReasonRef",
    "GeneratorReplayCommitmentRef",
    "GeneratorRequestRef",
    "GeneratorResultRef",
    "GeneratorRuntimeRef",
    "IntendedUnitAccountingRef",
    "IntendedUnitLinkDecisionRef",
    "PendingGenerationAttemptRef",
    "PhysicalPayloadFingerprintRef",
    "SupportExclusionDecisionRef",
    "decode_generator_ref",
    "encode_generator_ref",
    "generator_ref",
    "generator_ref_from_canonical",
    "generator_ref_to_canonical",
    "is_generator_ref",
    "reconstruct_generator_ref",
    "replay_ref_from_canonical",
    "replay_ref_to_canonical",
    "verify_generator_ref",
]
