"""Exact common-value and nominal-reference tests for B-02A."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from carbon.authoring.errors import AuthoringValidationError
from carbon.authoring.primitives import (
    CANONICALIZATION_PROFILE,
    INT64_MAX,
    INT64_MIN,
    MAX_CANONICAL_PAYLOAD_BYTES,
    UINT64_MAX,
    exact_tuple,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_exact_bool,
    validate_exact_bytes,
    validate_finite_float64,
    validate_int64,
    validate_positive_uint64,
    validate_tagged_sha256,
    validate_uint64,
    validate_utf8_text,
    validate_version_token,
)
from carbon.authoring.refs import (
    TOP_LEVEL_REF_TYPES,
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    ChallengeScope,
    GlobalScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    TrainingSupportContractRef,
    is_owner_ref,
    is_top_level_ref,
    owner_ref,
    owner_ref_type,
    reconstruct_top_level_ref,
    require_owner_ref,
    top_level_ref_type,
)
from carbon.registry import ChallengeKey

_DIGEST = "sha256:" + "a" * 64
_OTHER_DIGEST = "sha256:" + "b" * 64
_KEY = ChallengeKey("fixture_case", "1.0")


class _StringSubclass(str):
    pass


class _IntSubclass(int):
    pass


class _FloatSubclass(float):
    pass


class _TupleSubclass(tuple):
    pass


class _BytesSubclass(bytes):
    pass


def _common() -> tuple[object, ...]:
    return (
        _KEY,
        "object_one",
        "1.0",
        "1.0",
        CANONICALIZATION_PROFILE,
        _DIGEST,
    )


@pytest.mark.parametrize(
    ("validator", "valid"),
    (
        (validate_canonical_id, "lower_case-1"),
        (validate_version_token, "V1.2-rc_1"),
        (validate_tagged_sha256, _DIGEST),
        (validate_utf8_text, "already NFC Ω"),
    ),
)
def test_exact_text_vocabulary_accepts_only_canonical_builtins(
    validator: object, valid: str
) -> None:
    assert validator(valid) == valid
    with pytest.raises(AuthoringValidationError):
        validator(_StringSubclass(valid))


@pytest.mark.parametrize(
    "value",
    (
        "",
        "WrongCase",
        "two words",
        "../escape",
        "nonascii_é",
        "under__score",
    ),
)
def test_canonical_identifier_rejects_non_a3_grammar(value: str) -> None:
    with pytest.raises(AuthoringValidationError):
        validate_canonical_id(value)


@pytest.mark.parametrize(
    "value",
    (
        "",
        "two words",
        "../escape",
        "slash/value",
        "vérsion",
        "a" * 65,
    ),
)
def test_version_rejects_unbounded_or_path_unsafe_values(value: str) -> None:
    with pytest.raises(AuthoringValidationError):
        validate_version_token(value)


@pytest.mark.parametrize(
    "value",
    (
        "sha256:" + "a" * 63,
        "sha256:" + "a" * 65,
        "sha256:" + "A" * 64,
        "sha512:" + "a" * 64,
        "a" * 64,
        True,
    ),
)
def test_digest_reuses_only_a3_tagged_sha256_grammar(value: object) -> None:
    with pytest.raises(AuthoringValidationError):
        validate_tagged_sha256(value)


@pytest.mark.parametrize(
    "value",
    (
        "e\u0301",
        "nul\x00",
        "c0\x1f",
        "del\x7f",
        "c1\x85",
        "surrogate\ud800",
    ),
)
def test_utf8_text_rejects_non_nfc_controls_and_surrogates(value: str) -> None:
    with pytest.raises(AuthoringValidationError):
        validate_utf8_text(value)


def test_utf8_text_and_bytes_enforce_exact_payload_bound() -> None:
    assert validate_utf8_text("a" * MAX_CANONICAL_PAYLOAD_BYTES)
    assert validate_exact_bytes(b"a" * MAX_CANONICAL_PAYLOAD_BYTES)
    with pytest.raises(AuthoringValidationError):
        validate_utf8_text("a" * (MAX_CANONICAL_PAYLOAD_BYTES + 1))
    with pytest.raises(AuthoringValidationError):
        validate_exact_bytes(b"a" * (MAX_CANONICAL_PAYLOAD_BYTES + 1))
    with pytest.raises(AuthoringValidationError):
        validate_exact_bytes(_BytesSubclass(b"a"))


def test_bool_integer_and_float_paths_are_exact_and_disjoint() -> None:
    assert validate_exact_bool(True) is True
    assert validate_int64(INT64_MIN) == INT64_MIN
    assert validate_int64(INT64_MAX) == INT64_MAX
    assert validate_uint64(0) == 0
    assert validate_uint64(UINT64_MAX) == UINT64_MAX
    assert validate_positive_uint64(1) == 1
    assert validate_finite_float64(1.5) == 1.5
    positive_zero = validate_finite_float64(-0.0)
    assert positive_zero == 0.0
    assert str(positive_zero) == "0.0"

    for value in (False, True, _IntSubclass(1), 1.0, "1"):
        with pytest.raises(AuthoringValidationError):
            validate_int64(value)
        with pytest.raises(AuthoringValidationError):
            validate_uint64(value)
    for value in (False, True, 1, _FloatSubclass(1.0), float("nan"), float("inf")):
        with pytest.raises(AuthoringValidationError):
            validate_finite_float64(value)
    with pytest.raises(AuthoringValidationError):
        validate_exact_bool(1)
    with pytest.raises(AuthoringValidationError):
        validate_int64(INT64_MIN - 1)
    with pytest.raises(AuthoringValidationError):
        validate_int64(INT64_MAX + 1)
    with pytest.raises(AuthoringValidationError):
        validate_uint64(-1)
    with pytest.raises(AuthoringValidationError):
        validate_uint64(UINT64_MAX + 1)
    with pytest.raises(AuthoringValidationError):
        validate_positive_uint64(0)


def test_exact_tuple_rejects_coercion_duplicates_and_wrong_items() -> None:
    source = ("a", "b")
    assert exact_tuple(source, field_name="items", item_type=str, unique=True) == source
    with pytest.raises(AuthoringValidationError):
        exact_tuple(["a"], field_name="items", item_type=str)
    with pytest.raises(AuthoringValidationError):
        exact_tuple(_TupleSubclass(("a",)), field_name="items", item_type=str)
    with pytest.raises(AuthoringValidationError):
        exact_tuple(("a", _StringSubclass("b")), field_name="items", item_type=str)
    with pytest.raises(AuthoringValidationError):
        exact_tuple(("a", "a"), field_name="items", unique=True)
    with pytest.raises(AuthoringValidationError):
        exact_tuple((), field_name="items", nonempty=True)


def test_challenge_key_is_defensively_reconstructed_and_subclass_rejected() -> None:
    owned = reconstruct_challenge_key(_KEY)
    assert owned == _KEY
    assert owned is not _KEY

    class ChallengeKeySubclass(ChallengeKey):
        pass

    with pytest.raises(AuthoringValidationError):
        reconstruct_challenge_key(ChallengeKeySubclass("fixture_case", "1.0"))
    with pytest.raises(AuthoringValidationError):
        reconstruct_challenge_key(("fixture_case", "1.0"))


def test_owner_ref_registry_creates_distinct_nominal_types() -> None:
    scope = ChallengeScope(_KEY)
    unit = owner_ref(
        "unit",
        scope_binding=scope,
        object_id="unit_si",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    representation = owner_ref(
        "representation",
        scope_binding=scope,
        object_id="unit_si",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    assert type(unit) is owner_ref_type("unit")
    assert type(representation) is owner_ref_type("representation")
    assert type(unit) is not type(representation)
    assert unit != representation
    assert is_owner_ref(unit)
    assert require_owner_ref(unit, "unit") == unit
    assert require_owner_ref(unit, "unit") is not unit
    with pytest.raises(AuthoringValidationError):
        require_owner_ref(unit, "representation")
    with pytest.raises(AuthoringValidationError):
        owner_ref_type("unknown_kind")


def test_evidence_binding_authority_ref_kind_is_closed_and_nominal() -> None:
    value = owner_ref(
        "evidence_binding_authority",
        scope_binding=ChallengeScope(_KEY),
        object_id="b04_history_registry",
        object_version="1.0",
        content_digest=_DIGEST,
    )

    assert type(value) is owner_ref_type("evidence_binding_authority")
    assert require_owner_ref(value, "evidence_binding_authority") == value
    with pytest.raises(AuthoringValidationError):
        require_owner_ref(value, "accounting_authority")
    with pytest.raises(AuthoringValidationError):
        owner_ref(
            "evidence_binding_authority_typo",
            scope_binding=ChallengeScope(_KEY),
            object_id="b04_history_registry",
            object_version="1.0",
            content_digest=_DIGEST,
        )


@pytest.mark.parametrize(
    "kind",
    (
        "operating_envelope",
        "evidence_binding_authority",
        "full_design_law",
        "query_observation_allocation",
        "reference_fidelity_allocation",
        "statistics_objective",
        "replication_dependence_policy",
        "draw_order_semantics",
        "inclusion_policy",
        "exclusion_policy",
        "statistical_qualification_requirement",
    ),
)
def test_material_contract_owner_ref_kinds_are_exact_and_nominal(kind: str) -> None:
    value = owner_ref(
        kind,
        scope_binding=ChallengeScope(_KEY),
        object_id="owned_contract",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    assert type(value) is owner_ref_type(kind)
    assert require_owner_ref(value, kind) == value
    assert type(value) is not owner_ref_type("unit")
    with pytest.raises(AuthoringValidationError):
        require_owner_ref(value, "unit")


@pytest.mark.parametrize(
    "kind",
    (
        "reference_unavailable",
        "reference_disputed",
        "reference_numerical_failure",
        "reference_resource_limit",
        "reference_timeout",
        "observation_missing",
        "observation_timeout",
        "measurement_unavailable",
        "measurement_resource_limit",
        "measurement_timeout",
        "experiment_corrupted",
    ),
)
def test_censoring_reason_subtype_refs_are_closed_nominal_kinds(kind: str) -> None:
    value = owner_ref(
        kind,
        scope_binding=ChallengeScope(_KEY),
        object_id="registered_failure",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    assert type(value) is owner_ref_type(kind)
    assert require_owner_ref(value, kind) == value
    with pytest.raises(AuthoringValidationError):
        require_owner_ref(value, "reference_failure")


def test_owner_ref_scope_is_closed_immutable_and_defensively_owned() -> None:
    source = ChallengeScope(_KEY)
    value = owner_ref(
        "unit",
        scope_binding=source,
        object_id="unit_si",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    assert value.scope_binding == source
    assert value.scope_binding is not source
    assert value.scope_binding.challenge_key is not _KEY
    with pytest.raises(FrozenInstanceError):
        value.object_id = "changed"

    global_value = owner_ref(
        "unit",
        scope_binding=GlobalScope(),
        object_id="unit_si",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    assert type(global_value.scope_binding) is GlobalScope


def test_owner_ref_subclass_and_cross_kind_constructor_are_rejected() -> None:
    unit_type = owner_ref_type("unit")

    class UnitSubclass(unit_type):
        pass

    with pytest.raises(AuthoringValidationError):
        UnitSubclass(GlobalScope(), "unit_si", "1.0", _DIGEST)
    with pytest.raises(AuthoringValidationError):
        unit_type(object(), "unit_si", "1.0", _DIGEST)


@pytest.mark.parametrize(
    "ref_type",
    (
        PhysicalSystemSpecRef,
        CandidateOutputContractRef,
        SamplingPlanRef,
        TrainingSupportContractRef,
    ),
)
def test_plain_top_level_refs_are_exact_immutable_and_content_addressed(
    ref_type: type,
) -> None:
    value = ref_type(*_common())
    assert type(value) is ref_type
    assert type(value.challenge_key) is ChallengeKey
    assert value.challenge_key is not _KEY
    assert value.object_kind == ref_type.OBJECT_KIND
    assert value.ref_type == f"{ref_type.OBJECT_KIND}_ref"
    assert is_top_level_ref(value)
    assert reconstruct_top_level_ref(value) == value
    assert reconstruct_top_level_ref(value) is not value
    with pytest.raises(FrozenInstanceError):
        value.content_digest = _OTHER_DIGEST


def test_distribution_ref_role_is_identity_bearing_and_training_is_forbidden() -> None:
    target = InstanceDistributionContractRef(*_common(), "TARGET_WORKLOAD_P")
    proposal = InstanceDistributionContractRef(*_common(), "OFFICIAL_PROPOSAL_Q")
    assert target != proposal
    assert reconstruct_top_level_ref(target) == target
    for role in ("TRAINING_SUPPORT", "R_strategy", "target_workload_p", True):
        with pytest.raises(AuthoringValidationError):
            InstanceDistributionContractRef(*_common(), role)


def test_case_ref_is_never_public_and_disclosure_is_identity_bearing() -> None:
    internal = CanonicalChallengeCaseRef(*_common(), "INTERNAL")
    protected = CanonicalChallengeCaseRef(*_common(), "PROTECTED")
    assert internal != protected
    assert reconstruct_top_level_ref(internal) == internal
    for disclosure in ("PUBLIC", "internal", "", True):
        with pytest.raises(AuthoringValidationError):
            CanonicalChallengeCaseRef(*_common(), disclosure)


def test_top_level_ref_nominal_kind_confusion_and_subclasses_reject() -> None:
    physical = PhysicalSystemSpecRef(*_common())
    candidate = CandidateOutputContractRef(*_common())
    assert physical != candidate
    assert len(TOP_LEVEL_REF_TYPES) == 6
    assert top_level_ref_type("physical_system_spec") is PhysicalSystemSpecRef
    with pytest.raises(AuthoringValidationError):
        top_level_ref_type("challenge")
    with pytest.raises(AuthoringValidationError):
        reconstruct_top_level_ref(object())

    class PhysicalSubclass(PhysicalSystemSpecRef):
        pass

    with pytest.raises(AuthoringValidationError):
        PhysicalSubclass(*_common())


def test_top_level_ref_direct_and_reconstruction_paths_reject_schema_2() -> None:
    fields = list(_common())
    fields[3] = "2.0"
    with pytest.raises(AuthoringValidationError):
        PhysicalSystemSpecRef(*fields)

    valid = PhysicalSystemSpecRef(*_common())
    tampered = object.__new__(PhysicalSystemSpecRef)
    for name in (
        "challenge_key",
        "object_id",
        "object_version",
        "schema_version",
        "canonicalization_profile",
        "content_digest",
    ):
        object.__setattr__(
            tampered,
            name,
            "2.0" if name == "schema_version" else getattr(valid, name),
        )
    with pytest.raises(AuthoringValidationError):
        reconstruct_top_level_ref(tampered)


@pytest.mark.parametrize(
    "field_index,bad_value",
    (
        (0, ("fixture_case", "1.0")),
        (1, _StringSubclass("object_one")),
        (2, _StringSubclass("1.0")),
        (3, _StringSubclass("1.0")),
        (4, _StringSubclass(CANONICALIZATION_PROFILE)),
        (5, _StringSubclass(_DIGEST)),
    ),
)
def test_top_level_ref_rejects_aliases_and_malformed_fields(
    field_index: int, bad_value: object
) -> None:
    values = list(_common())
    values[field_index] = bad_value
    with pytest.raises(AuthoringValidationError):
        PhysicalSystemSpecRef(*values)
