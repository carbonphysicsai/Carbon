"""Closed, cross-module canonical identity for the B-03 generator runtime.

The domain spans several owning modules.  Those modules register only the
literal types assigned to them below, with explicit fixed-order field schemas.
There is no dataclass reflection, dynamic import, or caller-extensible codec.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import NamedTuple

from carbon.authoring.canonical import (
    CanonicalBytes,
    CanonicalFloat64,
    CanonicalInt64,
    CanonicalNominalRef,
    CanonicalRecord,
    CanonicalText,
    CanonicalTuple,
    CanonicalUInt64,
    CanonicalUnion,
    CanonicalValue,
    challenge_key_from_canonical,
    challenge_key_to_canonical,
    decode_value,
    encode_value,
    owner_ref_from_canonical,
    owner_ref_to_canonical,
    tagged_sha256,
    top_level_ref_from_canonical,
    top_level_ref_to_canonical,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.model import ApplicabilityBinding, ApplicabilityTag
from carbon.authoring.primitives import MAX_CANONICAL_DOCUMENT_BYTES
from carbon.authoring.refs import is_owner_ref, is_top_level_ref
from carbon.registry.model import ChallengeKey

from .errors import (
    GeneratorCanonicalDecodingError,
    GeneratorCanonicalEncodingError,
    GeneratorInputCode,
    GeneratorReferenceMismatchError,
    GeneratorValidationError,
)
from .refs import (
    GENERATOR_RUNTIME_CANONICALIZATION_PROFILE,
    GENERATOR_RUNTIME_REF_TYPES,
    GENERATOR_RUNTIME_SCHEMA_VERSION,
    GeneratorRuntimeRef,
    generator_ref_from_canonical,
    generator_ref_to_canonical,
    is_generator_ref,
    reconstruct_generator_ref,
    replay_ref_from_canonical,
    replay_ref_to_canonical,
)

GENERATOR_RUNTIME_DOCUMENT_HEADER = b"carbon.generator.runtime.canonical.v1\x00"
GENERATOR_IMPLEMENTATION_MANIFEST_HEADER = (
    b"carbon.generator.implementation-manifest.v1\x00"
)

# Contract section 11's complete standalone-record set.  The owning class map
# is literal so registration cannot turn this into an open plugin codec.
_CANONICAL_TYPE_OWNERS = MappingProxyType(
    {
        "generator_implementation_manifest": (
            "carbon.generators.model",
            "GeneratorImplementationManifest",
        ),
        "generator_descriptor": ("carbon.generators.model", "GeneratorDescriptor"),
        "generator_environment": (
            "carbon.generators.model",
            "GeneratorEnvironmentDescriptor",
        ),
        "burgers_fixture_configuration": (
            "carbon.generators.burgers",
            "BurgersFixtureConfiguration",
        ),
        "generator_request": ("carbon.generators.model", "GeneratorRequestIdentity"),
        "intended_unit_link_decision": (
            "carbon.generators.authorities",
            "IntendedUnitLinkDecision",
        ),
        "generation_source_event": (
            "carbon.generators.model",
            "GenerationSourceEvent",
        ),
        "support_exclusion_decision": (
            "carbon.generators.authorities",
            "SupportExclusionDecision",
        ),
        "generator_censoring_verdict": (
            "carbon.generators.authorities",
            "CensoringVerdict",
        ),
        "generator_censoring_decision": (
            "carbon.generators.authorities",
            "CensoringDecision",
        ),
        "attempt_accounting_directive": (
            "carbon.generators.accounting",
            "AttemptAccountingDirective",
        ),
        "attempt_accounting_decision": (
            "carbon.generators.accounting",
            "AttemptAccountingDecision",
        ),
        "pending_generation_attempt": (
            "carbon.generators.accounting",
            "PendingGenerationAttemptRecord",
        ),
        "generator_failure_reason": (
            "carbon.generators.model",
            "GeneratorFailureReason",
        ),
        "generator_failure_occurrence": (
            "carbon.generators.model",
            "GeneratorFailureOccurrence",
        ),
        "generator_result": ("carbon.generators.model", "GeneratorResultRecord"),
        "generation_attempt_record": (
            "carbon.generators.accounting",
            "GenerationAttemptRecord",
        ),
        "intended_unit_accounting": (
            "carbon.generators.accounting",
            "IntendedUnitAccounting",
        ),
        "generation_accounting_summary": (
            "carbon.generators.accounting",
            "GenerationAccountingSummary",
        ),
        "generator_conformance_facts": (
            "carbon.generators.conformance",
            "GeneratorConformanceFacts",
        ),
        "protected_fixture_payload": (
            "carbon.generators.burgers",
            "ProtectedBurgersFixturePayload",
        ),
        "physical_payload_fingerprint": (
            "carbon.generators.burgers",
            "PhysicalPayloadFingerprint",
        ),
        "fixture_replay_probe": (
            "carbon.generators.conformance",
            "FixtureReplayProbeRecord",
        ),
        "deterministic_replay_comparison": (
            "carbon.generators.conformance",
            "DeterministicReplayComparison",
        ),
        "comparison_corpus_decision": (
            "carbon.generators.conformance",
            "ComparisonCorpusDecision",
        ),
        "duplicate_conformance_facts": (
            "carbon.generators.conformance",
            "DuplicateConformanceFacts",
        ),
        "external_distribution_fact_set": (
            "carbon.generators.conformance",
            "ExternalDistributionFactSet",
        ),
    }
)
GENERATOR_RUNTIME_CANONICAL_OBJECT_KINDS = tuple(_CANONICAL_TYPE_OWNERS)

# Exact named nested records from section 11 plus the implementation's closed
# binding variants.  More names may not be registered without a schema change.
_NESTED_TYPE_OWNERS = frozenset(
    {
        ("carbon.generators.model", name)
        for name in (
            "GenerationRoleBinding",
            "ResolvedGeneratorAuthoringBundle",
            "CaseConstructionBinding",
            "FixtureLoadingBinding",
            "GeneratorFailureCatalogEntry",
            "RecordRefPair",
            "RecordRefBinding",
            "TerminalReasonNotApplicable",
            "TerminalReasonSupportDecision",
            "TerminalReasonCensoringDecision",
            "TerminalReasonFailure",
            "AttemptAccountingFallback",
            "NamedApplicabilityReason",
            "NamedConformanceFallback",
            "DispositionConstructionBinding",
            "LoadedDependencyIdentity",
        )
    }
    | {
        ("carbon.generators.authorities", name)
        for name in (
            "IntendedUnitLinkRequest",
            "SupportExclusionRequest",
            "PopulationSupportAssessment",
            "GeneratorCensoringRequest",
            "CensoringRecordBasis",
        )
    }
    | {
        ("carbon.generators.accounting", name)
        for name in (
            "AttemptAccountingRequest",
            "SuccessorAuthorization",
            "SuccessorExecutionEvidence",
            "GeneratorOutcomeCount",
        )
    }
    | {
        ("carbon.generators.burgers", name)
        for name in (
            "FixtureDegeneracyFacts",
            "FixturePayloadFacts",
            "ValidatedCaseFacts",
        )
    }
    | {
        ("carbon.generators.conformance", name)
        for name in (
            "ReplayIdentityFacts",
            "PostResultDuplicateRequest",
            "DuplicateComparisonRequest",
            "NearDuplicateRequest",
            "NearDuplicateDecision",
            "ExternalDistributionFactRequest",
            "ExternalDistributionFactDecision",
            "ExternalFactAvailability",
        )
    }
)


class _FieldCodec(NamedTuple):
    kind: str
    argument: object = None
    set_like: bool = False


_TEXT = _FieldCodec("text")
_BYTES = _FieldCodec("bytes")
_BOOL = _FieldCodec("bool")
_INT64 = _FieldCodec("int64")
_UINT64 = _FieldCodec("uint64")
_FLOAT64 = _FieldCodec("float64")
_CHALLENGE_KEY = _FieldCodec("challenge_key")
_REPLAY_REF = _FieldCodec("replay_ref")
_ANY_OWNER_REF = _FieldCodec("any_owner_ref")
_ANY_TOP_REF = _FieldCodec("any_top_ref")
_ANY_GENERATOR_REF = _FieldCodec("any_generator_ref")
_ANY_REF = _FieldCodec("any_ref")
_ANY_RECORD = _FieldCodec("any_record")
_ROLE_KEY = _FieldCodec("role_key")


def _enum(enum_type: type[Enum]) -> _FieldCodec:
    if not isinstance(enum_type, type) or not issubclass(enum_type, Enum):
        raise TypeError("enum_type must be an exact Enum class")
    return _FieldCodec("enum", enum_type)


def _owner(expected_kind: str) -> _FieldCodec:
    if type(expected_kind) is not str or not expected_kind:
        raise TypeError("expected owner kind must be nonempty text")
    return _FieldCodec("owner_ref", expected_kind)


def _top_ref(expected_type: type) -> _FieldCodec:
    return _FieldCodec("top_ref", expected_type)


def _generator_ref(expected_type: type) -> _FieldCodec:
    if expected_type not in GENERATOR_RUNTIME_REF_TYPES:
        raise TypeError("expected_type must be a B-03 ref type")
    return _FieldCodec("generator_ref", expected_type)


def _nested(expected_type: type) -> _FieldCodec:
    return _FieldCodec("nested", expected_type)


def _record(expected_type: type) -> _FieldCodec:
    """Embed one registered standalone record as a nested exact value."""

    return _FieldCodec("record", expected_type)


def _authoring(expected_type: type) -> _FieldCodec:
    """Bind one explicitly named B-02A nested type through its exact codec."""

    return _FieldCodec("authoring", expected_type)


def _tuple_of(item_codec: _FieldCodec, *, set_like: bool = False) -> _FieldCodec:
    if type(item_codec) is not _FieldCodec:
        raise TypeError("item_codec must be one exact field codec")
    return _FieldCodec("tuple", item_codec, set_like)


def _optional(item_codec: _FieldCodec) -> _FieldCodec:
    if type(item_codec) is not _FieldCodec:
        raise TypeError("item_codec must be one exact field codec")
    return _FieldCodec("optional", item_codec)


def _applicability(item_codec: _FieldCodec) -> _FieldCodec:
    if type(item_codec) is not _FieldCodec:
        raise TypeError("item_codec must be one exact field codec")
    return _FieldCodec("applicability", item_codec)


def _closed_union(*expected_types: type) -> _FieldCodec:
    if not expected_types or any(type(item) is not type for item in expected_types):
        raise TypeError("closed union requires exact classes")
    return _FieldCodec("union", tuple(expected_types))


@dataclass(frozen=True, slots=True)
class _Schema:
    record_type: str
    fields: tuple[tuple[str, _FieldCodec], ...]
    exact_type: type
    top_level: bool
    include_identity_fields: bool
    document_header: bytes
    union_tag: str | None = None
    builder: Callable[..., object] | None = None


_TOP_SCHEMAS_BY_TYPE: dict[type, _Schema] = {}
_TOP_SCHEMAS_BY_KIND: dict[str, _Schema] = {}
_NESTED_SCHEMAS_BY_TYPE: dict[type, _Schema] = {}
_NESTED_SCHEMAS_BY_TAG: dict[str, _Schema] = {}


def _validate_registration_type(exact_type: object) -> type:
    if type(exact_type) is not type:
        raise TypeError("canonical registration requires one exact class")
    return exact_type


def _validate_fields(fields: object) -> tuple[tuple[str, _FieldCodec], ...]:
    if type(fields) is not tuple or any(
        type(item) is not tuple
        or len(item) != 2
        or type(item[0]) is not str
        or not item[0]
        or type(item[1]) is not _FieldCodec
        for item in fields
    ):
        raise TypeError("canonical fields must be exact (name, codec) tuples")
    names = tuple(item[0] for item in fields)
    if len(set(names)) != len(names):
        raise ValueError("canonical field names must be unique")
    return fields


def _register_canonical_type(
    exact_type: type,
    *,
    object_kind: str,
    fields: tuple[tuple[str, _FieldCodec], ...],
    document_header: bytes = GENERATOR_RUNTIME_DOCUMENT_HEADER,
    include_identity_fields: bool = True,
    builder: Callable[..., object] | None = None,
) -> None:
    """Register one literal standalone type assigned by the merged contract."""

    checked_type = _validate_registration_type(exact_type)
    owner = _CANONICAL_TYPE_OWNERS.get(object_kind)
    if owner != (checked_type.__module__, checked_type.__name__):
        raise ValueError("canonical type is outside the closed B-03 owner registry")
    if checked_type in _TOP_SCHEMAS_BY_TYPE or object_kind in _TOP_SCHEMAS_BY_KIND:
        raise ValueError("canonical type is already registered")
    if type(document_header) is not bytes or document_header not in {
        GENERATOR_RUNTIME_DOCUMENT_HEADER,
        GENERATOR_IMPLEMENTATION_MANIFEST_HEADER,
    }:
        raise ValueError("canonical document header is outside the closed profile")
    schema = _Schema(
        object_kind,
        _validate_fields(fields),
        checked_type,
        True,
        include_identity_fields,
        document_header,
        builder=builder,
    )
    _TOP_SCHEMAS_BY_TYPE[checked_type] = schema
    _TOP_SCHEMAS_BY_KIND[object_kind] = schema


def _register_nested_canonical_type(
    exact_type: type,
    *,
    record_type: str,
    fields: tuple[tuple[str, _FieldCodec], ...],
    union_tag: str | None = None,
    builder: Callable[..., object] | None = None,
) -> None:
    """Register one literal nested-only type; it can never be framed alone."""

    checked_type = _validate_registration_type(exact_type)
    if (checked_type.__module__, checked_type.__name__) not in _NESTED_TYPE_OWNERS:
        raise ValueError("nested type is outside the closed B-03 owner registry")
    if checked_type in _NESTED_SCHEMAS_BY_TYPE:
        raise ValueError("nested canonical type is already registered")
    if type(record_type) is not str or not record_type:
        raise TypeError("nested record_type must be nonempty text")
    if union_tag is not None and (type(union_tag) is not str or not union_tag):
        raise TypeError("union_tag must be nonempty text when supplied")
    if union_tag is not None and union_tag in _NESTED_SCHEMAS_BY_TAG:
        raise ValueError("nested union tag is already registered")
    schema = _Schema(
        record_type,
        _validate_fields(fields),
        checked_type,
        False,
        False,
        b"",
        union_tag=union_tag,
        builder=builder,
    )
    _NESTED_SCHEMAS_BY_TYPE[checked_type] = schema
    if union_tag is not None:
        _NESTED_SCHEMAS_BY_TAG[union_tag] = schema


def _encoding_error(path: str = "") -> GeneratorCanonicalEncodingError:
    return GeneratorCanonicalEncodingError(path=path)


def _decoding_error(path: str = "") -> GeneratorCanonicalDecodingError:
    return GeneratorCanonicalDecodingError(path=path)


def _encode_authoring(value: object, expected_type: type) -> CanonicalValue:
    if type(value) is not expected_type:
        raise _encoding_error()
    # B-02A owns these fixed adapters.  The B-03 registry supplies the exact
    # expected type, so this cannot become an open arbitrary-object codec.
    from carbon.authoring.model import _canonical_value

    encoding_failed = False
    try:
        result = _canonical_value(value)
    except (AuthoringError, TypeError, ValueError):
        encoding_failed = True
        result = None
    if encoding_failed:
        raise _encoding_error()
    return result


def _decode_authoring(value: object, expected_type: type) -> object:
    from carbon.authoring.canonical import CanonicalUnion
    from carbon.authoring.model import _decode_canonical_value, _decode_union

    decoding_failed = False
    try:
        result = (
            _decode_union(value, expected_type)
            if type(value) is CanonicalUnion
            else _decode_canonical_value(value)
        )
    except (AuthoringError, TypeError, ValueError):
        decoding_failed = True
        result = None
    if decoding_failed:
        raise _decoding_error()
    if type(result) is not expected_type:
        raise _decoding_error()
    return result


def _authoring_derived_ref_types() -> tuple[type, ...]:
    """Return B-02A's literal closed set of non-owner derived record refs."""

    from carbon.authoring.evidence import (
        CanonicalCaseDispositionRef,
        CensoringRecordRef,
        RealizedValidEvidenceRecordRef,
    )

    return (
        CanonicalCaseDispositionRef,
        CensoringRecordRef,
        RealizedValidEvidenceRecordRef,
    )


def _encode_field(value: object, codec: _FieldCodec) -> CanonicalValue:
    kind = codec.kind
    preserved_error = None
    try:
        if kind == "text" and type(value) is str:
            return CanonicalText(value)
        if kind == "bytes" and type(value) is bytes:
            return CanonicalBytes(value)
        if kind == "bool" and type(value) is bool:
            return value
        if kind == "int64" and type(value) is int:
            return CanonicalInt64(value)
        if kind == "uint64" and type(value) is int:
            return CanonicalUInt64(value)
        if kind == "float64" and type(value) is float:
            return CanonicalFloat64(value)
        if kind == "challenge_key":
            return challenge_key_to_canonical(value)
        if kind == "enum" and type(value) is codec.argument:
            return CanonicalUnion(
                value.name,
                CanonicalRecord("enum_value", ()),
            )
        if kind == "owner_ref" and is_owner_ref(value):
            if value.ref_kind != codec.argument:
                raise _encoding_error()
            return owner_ref_to_canonical(value)
        if kind == "any_owner_ref" and is_owner_ref(value):
            return owner_ref_to_canonical(value)
        if kind == "top_ref" and type(value) is codec.argument:
            return top_level_ref_to_canonical(value)
        if kind == "any_top_ref" and is_top_level_ref(value):
            return top_level_ref_to_canonical(value)
        if kind == "generator_ref" and type(value) is codec.argument:
            return generator_ref_to_canonical(value)
        if kind == "any_generator_ref" and is_generator_ref(value):
            return generator_ref_to_canonical(value)
        if kind == "any_ref":
            if is_generator_ref(value):
                return generator_ref_to_canonical(value)
            if is_owner_ref(value):
                return owner_ref_to_canonical(value)
            if is_top_level_ref(value):
                return top_level_ref_to_canonical(value)
            if type(value) in _authoring_derived_ref_types():
                return _encode_authoring(value, type(value))
            raise _encoding_error()
        if kind == "replay_ref":
            return replay_ref_to_canonical(value)
        if kind == "role_key":
            from carbon.seeding.model import RoleKey

            if type(value) is RoleKey:
                return CanonicalText(value.value)
            raise _encoding_error()
        if kind == "nested":
            if type(value) is not codec.argument:
                raise _encoding_error()
            return _nested_to_canonical(value)
        if kind == "record":
            schema = _TOP_SCHEMAS_BY_TYPE.get(codec.argument)
            if schema is None or type(value) is not codec.argument:
                raise _encoding_error()
            return _schema_record(value, schema)
        if kind == "any_record":
            schema = _TOP_SCHEMAS_BY_TYPE.get(type(value))
            if schema is not None:
                return _schema_record(value, schema)
            return _encode_authoring(value, type(value))
        if kind == "authoring":
            return _encode_authoring(value, codec.argument)
        if kind == "tuple" and type(value) is tuple:
            encoded = tuple(_encode_field(item, codec.argument) for item in value)
            if codec.set_like:
                encoded = tuple(sorted(encoded, key=encode_value))
                if len({encode_value(item) for item in encoded}) != len(encoded):
                    raise _encoding_error()
            return CanonicalTuple(encoded, set_like=codec.set_like)
        if kind == "optional":
            if value is None:
                return CanonicalUnion("ABSENT", CanonicalRecord("empty_payload", ()))
            return CanonicalUnion("PRESENT", _encode_field(value, codec.argument))
        if kind == "applicability" and type(value) is ApplicabilityBinding:
            if value.tag is ApplicabilityTag.BOUND:
                return CanonicalUnion(
                    "BOUND", _encode_field(value.value, codec.argument)
                )
            if value.tag is ApplicabilityTag.NOT_APPLICABLE:
                return CanonicalUnion(
                    "NOT_APPLICABLE", owner_ref_to_canonical(value.value)
                )
            raise _encoding_error()
        if kind == "union" and type(value) in codec.argument:
            nested = _nested_to_canonical(value)
            schema = _NESTED_SCHEMAS_BY_TYPE[type(value)]
            return CanonicalUnion(
                schema.union_tag or schema.record_type.upper(), nested
            )
    except (AuthoringError, GeneratorValidationError, TypeError, ValueError) as exc:
        if type(exc) is GeneratorCanonicalEncodingError:
            preserved_error = exc
    if preserved_error is not None:
        raise preserved_error
    raise _encoding_error()


def _decode_field(value: object, codec: _FieldCodec) -> object:
    kind = codec.kind
    preserved_error = None
    try:
        if kind == "text" and type(value) is CanonicalText:
            return value.value
        if kind == "bytes" and type(value) is CanonicalBytes:
            return value.value
        if kind == "bool" and type(value) is bool:
            return value
        if kind == "int64" and type(value) is CanonicalInt64:
            return value.value
        if kind == "uint64" and type(value) is CanonicalUInt64:
            return value.value
        if kind == "float64" and type(value) is CanonicalFloat64:
            return value.value
        if kind == "challenge_key":
            return challenge_key_from_canonical(value)
        if kind == "enum" and type(value) is CanonicalUnion:
            if (
                type(value.payload) is not CanonicalRecord
                or value.payload.record_type != "enum_value"
                or value.payload.fields
            ):
                raise _decoding_error()
            return codec.argument[value.tag]
        if kind == "owner_ref":
            return owner_ref_from_canonical(value, expected_kind=codec.argument)
        if kind == "any_owner_ref":
            if type(value) is not CanonicalNominalRef:
                raise _decoding_error()
            return owner_ref_from_canonical(value, expected_kind=value.ref_type)
        if kind == "top_ref":
            decoded = top_level_ref_from_canonical(value)
            if type(decoded) is not codec.argument:
                raise _decoding_error()
            return decoded
        if kind == "any_top_ref":
            return top_level_ref_from_canonical(value)
        if kind == "generator_ref":
            return generator_ref_from_canonical(value, expected_type=codec.argument)
        if kind == "any_generator_ref":
            return generator_ref_from_canonical(value)
        if kind == "any_ref":
            if type(value) is not CanonicalNominalRef:
                raise _decoding_error()
            generator_types = tuple(
                item
                for item in GENERATOR_RUNTIME_REF_TYPES
                if f"{item.RECORD_TYPE}_ref" == value.ref_type
            )
            if len(generator_types) == 1:
                return generator_ref_from_canonical(
                    value, expected_type=generator_types[0]
                )
            derived_types = {
                "canonical_case_disposition_ref": _authoring_derived_ref_types()[0],
                "censoring_record_ref": _authoring_derived_ref_types()[1],
                "realized_valid_evidence_record_ref": (
                    _authoring_derived_ref_types()[2]
                ),
            }
            derived_type = derived_types.get(value.ref_type)
            if derived_type is not None:
                return _decode_authoring(value, derived_type)
            try:
                return top_level_ref_from_canonical(value)
            except AuthoringError:
                return owner_ref_from_canonical(value, expected_kind=value.ref_type)
        if kind == "replay_ref":
            return replay_ref_from_canonical(value)
        if kind == "role_key" and type(value) is CanonicalText:
            from carbon.seeding.model import RoleKey

            return RoleKey(value.value)
        if kind == "nested":
            return _nested_from_canonical(value, codec.argument)
        if kind == "record":
            schema = _TOP_SCHEMAS_BY_TYPE.get(codec.argument)
            if schema is None:
                raise _decoding_error()
            return _decode_schema_record(value, schema)
        if kind == "any_record":
            if type(value) is not CanonicalRecord:
                raise _decoding_error()
            schema = _TOP_SCHEMAS_BY_KIND.get(value.record_type)
            if schema is not None:
                return _decode_schema_record(value, schema)
            from carbon.authoring.model import _decode_canonical_value

            result = _decode_canonical_value(value)
            return result
        if kind == "authoring":
            return _decode_authoring(value, codec.argument)
        if kind == "tuple" and type(value) is CanonicalTuple:
            result = tuple(_decode_field(item, codec.argument) for item in value.items)
            if codec.set_like:
                ordered = tuple(sorted(value.items, key=encode_value))
                if ordered != value.items or len(
                    set(map(encode_value, ordered))
                ) != len(ordered):
                    raise _decoding_error()
            return result
        if kind == "optional" and type(value) is CanonicalUnion:
            if value.tag == "ABSENT":
                if (
                    type(value.payload) is not CanonicalRecord
                    or value.payload.record_type != "empty_payload"
                    or value.payload.fields
                ):
                    raise _decoding_error()
                return None
            if value.tag == "PRESENT":
                return _decode_field(value.payload, codec.argument)
            raise _decoding_error()
        if kind == "applicability" and type(value) is CanonicalUnion:
            if value.tag == "BOUND":
                return ApplicabilityBinding.bound(
                    _decode_field(value.payload, codec.argument)
                )
            if value.tag == "NOT_APPLICABLE":
                reason = owner_ref_from_canonical(
                    value.payload, expected_kind="applicability_reason"
                )
                return ApplicabilityBinding.not_applicable(reason)
            raise _decoding_error()
        if kind == "union" and type(value) is CanonicalUnion:
            candidates = tuple(
                candidate
                for candidate in codec.argument
                if _NESTED_SCHEMAS_BY_TYPE.get(candidate) is not None
                and (
                    _NESTED_SCHEMAS_BY_TYPE[candidate].union_tag
                    or _NESTED_SCHEMAS_BY_TYPE[candidate].record_type.upper()
                )
                == value.tag
            )
            if len(candidates) != 1:
                raise _decoding_error()
            return _nested_from_canonical(value.payload, candidates[0])
    except (AuthoringError, GeneratorValidationError, TypeError, ValueError) as exc:
        if type(exc) is GeneratorCanonicalDecodingError:
            preserved_error = exc
    if preserved_error is not None:
        raise preserved_error
    raise _decoding_error()


def _schema_record(value: object, schema: _Schema) -> CanonicalRecord:
    if type(value) is not schema.exact_type:
        raise _encoding_error()
    fields: list[tuple[str, CanonicalValue]] = []
    if schema.include_identity_fields:
        fields.extend(
            (
                ("object_kind", CanonicalText(schema.record_type)),
                ("schema_version", CanonicalText(GENERATOR_RUNTIME_SCHEMA_VERSION)),
                (
                    "canonicalization_profile",
                    CanonicalText(GENERATOR_RUNTIME_CANONICALIZATION_PROFILE),
                ),
            )
        )
    for name, codec in schema.fields:
        fields.append((name, _encode_field(getattr(value, name), codec)))
    record = CanonicalRecord(schema.record_type, tuple(fields))
    return record


def _decode_schema_record(value: object, schema: _Schema) -> object:
    if type(value) is not CanonicalRecord or value.record_type != schema.record_type:
        raise _decoding_error()
    prefix = (
        (
            "object_kind",
            "schema_version",
            "canonicalization_profile",
        )
        if schema.include_identity_fields
        else ()
    )
    expected_names = tuple(
        sorted(
            prefix + tuple(name for name, _ in schema.fields),
            key=lambda item: item.encode("utf-8"),
        )
    )
    actual_names = tuple(name for name, _ in value.fields)
    if actual_names != expected_names:
        raise _decoding_error()
    fields = value.field_map()
    if schema.include_identity_fields:
        identity = tuple(fields[name] for name in prefix)
        if (
            type(identity[0]) is not CanonicalText
            or identity[0].value != schema.record_type
            or type(identity[1]) is not CanonicalText
            or identity[1].value != GENERATOR_RUNTIME_SCHEMA_VERSION
            or type(identity[2]) is not CanonicalText
            or identity[2].value != GENERATOR_RUNTIME_CANONICALIZATION_PROFILE
        ):
            raise _decoding_error()
    kwargs = {name: _decode_field(fields[name], codec) for name, codec in schema.fields}
    construction_failed = False
    try:
        result = (
            schema.builder(**kwargs)
            if schema.builder is not None
            else schema.exact_type(**kwargs)
        )
    except (GeneratorValidationError, TypeError, ValueError):
        construction_failed = True
        result = None
    if construction_failed:
        raise _decoding_error()
    if type(result) is not schema.exact_type:
        raise _decoding_error()
    return result


def _nested_to_canonical(value: object) -> CanonicalRecord:
    schema = _NESTED_SCHEMAS_BY_TYPE.get(type(value))
    if schema is None:
        raise _encoding_error()
    return _schema_record(value, schema)


def _nested_from_canonical(value: object, expected_type: type) -> object:
    schema = _NESTED_SCHEMAS_BY_TYPE.get(expected_type)
    if schema is None:
        raise _decoding_error()
    return _decode_schema_record(value, schema)


def canonical_record(value: object) -> CanonicalRecord:
    """Return the exact registered standalone record for *value*."""

    schema = _TOP_SCHEMAS_BY_TYPE.get(type(value))
    if schema is None:
        raise _encoding_error()
    return _schema_record(value, schema)


def canonical_bytes(value: object) -> bytes:
    """Frame one exact registered B-03 record with domain separation."""

    schema = _TOP_SCHEMAS_BY_TYPE.get(type(value))
    if schema is None:
        raise _encoding_error()
    encoding_failed = False
    preserved_error = None
    try:
        document = schema.document_header + encode_value(_schema_record(value, schema))
    except (AuthoringError, GeneratorValidationError, TypeError, ValueError) as exc:
        if type(exc) is GeneratorCanonicalEncodingError:
            preserved_error = exc
        else:
            encoding_failed = True
        document = b""
    if preserved_error is not None:
        raise preserved_error
    if encoding_failed:
        raise _encoding_error()
    if len(document) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _encoding_error()
    return document


def decode_canonical_bytes(payload: object, expected_type: type) -> object:
    """Decode one exact type; callers cannot request an inferred/open schema."""

    if type(payload) is not bytes:
        raise GeneratorCanonicalDecodingError(path="/canonical_bytes")
    if type(expected_type) is not type:
        raise TypeError("expected_type must be one exact registered class")
    schema = _TOP_SCHEMAS_BY_TYPE.get(expected_type)
    if schema is None:
        raise TypeError("expected_type must be one exact registered class")
    if len(payload) > MAX_CANONICAL_DOCUMENT_BYTES or not payload.startswith(
        schema.document_header
    ):
        raise GeneratorCanonicalDecodingError(path="/canonical_bytes")
    decode_failed = False
    trailing = False
    try:
        value = decode_value(payload[len(schema.document_header) :])
    except AuthoringError as exc:
        decode_failed = True
        trailing = "trailing" in exc.code
        value = None
    if decode_failed:
        raise GeneratorCanonicalDecodingError(
            trailing=trailing,
            path="/canonical_bytes",
        )
    result = _decode_schema_record(value, schema)
    reencoding_failed = False
    try:
        reencoded = canonical_bytes(result)
    except GeneratorValidationError:
        reencoding_failed = True
        reencoded = b""
    if reencoding_failed:
        raise GeneratorCanonicalDecodingError(path="/canonical_bytes")
    if not hmac.compare_digest(reencoded, payload):
        raise GeneratorCanonicalDecodingError(path="/canonical_bytes")
    return result


def canonical_content_digest(value: object) -> str:
    """Return the tagged digest of one fully framed exact record."""

    preserved_error = None
    try:
        return tagged_sha256(canonical_bytes(value))
    except (AuthoringError, GeneratorValidationError) as exc:
        if type(exc) is GeneratorCanonicalEncodingError:
            preserved_error = exc
    if preserved_error is not None:
        raise preserved_error
    raise _encoding_error()


_INTRINSIC_CHALLENGE_PATHS = MappingProxyType(
    {
        "fixture_replay_probe": ("baseline_result", "challenge_key"),
        "deterministic_replay_comparison": (
            "baseline_result_ref",
            "challenge_key",
        ),
        "comparison_corpus_decision": ("request", "challenge_key"),
    }
)


def _record_ref(
    value: object,
    expected_ref_type: type,
    *,
    challenge_key: ChallengeKey | None = None,
) -> GeneratorRuntimeRef:
    """Construct the one exact nominal B-03 ref assigned to a record kind."""

    if expected_ref_type not in GENERATOR_RUNTIME_REF_TYPES:
        raise TypeError("expected_ref_type must be an exact B-03 ref class")
    schema = _TOP_SCHEMAS_BY_TYPE.get(type(value))
    if schema is None or expected_ref_type.RECORD_TYPE != schema.record_type:
        raise GeneratorReferenceMismatchError(path="/ref_type")
    scope = None
    if schema.record_type != "burgers_fixture_configuration":
        path = _INTRINSIC_CHALLENGE_PATHS.get(
            schema.record_type,
            ("challenge_key",),
        )
        scope = value
        try:
            for segment in path:
                scope = object.__getattribute__(scope, segment)
        except (AttributeError, TypeError):
            scope = None
        if type(scope) is not ChallengeKey:
            raise GeneratorValidationError(
                GeneratorInputCode.WRONG_TYPE,
                path="/challenge_key",
            )
        if challenge_key is not None and challenge_key != scope:
            raise GeneratorReferenceMismatchError(path="/challenge_key")
    else:
        scope = challenge_key
    if type(scope) is not ChallengeKey:
        raise GeneratorValidationError(
            GeneratorInputCode.WRONG_TYPE, path="/challenge_key"
        )
    return expected_ref_type(scope, canonical_content_digest(value))


def verify_canonical_ref(value: object, ref: object) -> None:
    """Recompute and constant-time verify one exact registered record/ref pair."""

    if not is_generator_ref(ref):
        raise GeneratorValidationError(GeneratorInputCode.WRONG_TYPE, path="/ref")
    validation_failure: tuple[str, str] | None = None
    try:
        checked_ref = reconstruct_generator_ref(ref)
    except GeneratorValidationError as error:
        validation_failure = (error.code, error.path)
        checked_ref = None
    except (AttributeError, AuthoringError, TypeError, ValueError):
        validation_failure = (GeneratorInputCode.INVALID_VALUE.value, "/ref")
        checked_ref = None
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    if checked_ref is None:
        raise GeneratorValidationError(GeneratorInputCode.INVALID_VALUE, path="/ref")
    expected = _record_ref(
        value,
        type(checked_ref),
        challenge_key=checked_ref.challenge_key,
    )
    if expected.challenge_key != checked_ref.challenge_key:
        raise GeneratorReferenceMismatchError(path="/challenge_key")
    if not hmac.compare_digest(
        expected.content_digest,
        checked_ref.content_digest,
    ):
        raise GeneratorReferenceMismatchError(path="/content_digest")


__all__ = [
    "GENERATOR_IMPLEMENTATION_MANIFEST_HEADER",
    "GENERATOR_RUNTIME_CANONICAL_OBJECT_KINDS",
    "GENERATOR_RUNTIME_DOCUMENT_HEADER",
    "canonical_bytes",
    "canonical_content_digest",
    "canonical_record",
    "decode_canonical_bytes",
    "verify_canonical_ref",
]
