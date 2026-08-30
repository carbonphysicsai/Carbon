"""Golden and hostile-input tests for B-02A canonical bytes."""

from __future__ import annotations

import os
import struct

import pytest

from carbon.authoring.canonical import (
    DERIVED_DOCUMENT_RECORD_TYPES_V1,
    DERIVED_RECORD_FIELD_REGISTRY_V1,
    CanonicalBytes,
    CanonicalFloat64,
    CanonicalInt64,
    CanonicalNominalRef,
    CanonicalRecord,
    CanonicalText,
    CanonicalTuple,
    CanonicalUInt64,
    CanonicalUnion,
    canonical_derived_document,
    canonical_document,
    challenge_key_to_canonical,
    decode_derived_document,
    decode_document,
    decode_top_level_ref,
    decode_value,
    derived_record_field_names,
    encode_top_level_ref,
    encode_value,
    make_top_level_ref,
    owner_ref_from_canonical,
    owner_ref_to_canonical,
    tagged_sha256,
    top_level_ref_from_canonical,
    top_level_ref_to_canonical,
    validate_registered_derived_record,
    verify_top_level_ref,
)
from carbon.authoring.errors import (
    AuthoringValidationError,
    CanonicalDecodingError,
    CanonicalEncodingError,
    ReferenceMismatchError,
)
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
    DERIVED_EVIDENCE_CANONICALIZATION_PROFILE,
    MAX_CANONICAL_DOCUMENT_BYTES,
    MAX_CANONICAL_NESTING_DEPTH,
    MAX_CANONICAL_PAYLOAD_BYTES,
)
from carbon.authoring.refs import (
    TOP_LEVEL_REF_TYPES,
    CanonicalChallengeCaseRef,
    ChallengeScope,
    GlobalScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    owner_ref,
)
from carbon.registry import ChallengeKey

_HEADER = b"carbon.scientific-authoring.canonical.v1\x00"
_DERIVED_HEADER = b"carbon.scientific-authoring.derived-evidence.v1\x00"
_KEY = ChallengeKey("fixture_case", "1.0")
_DIGEST = "sha256:" + "a" * 64


def _text(value: str) -> bytes:
    payload = value.encode("utf-8")
    return b"\x06" + len(payload).to_bytes(4, "big") + payload


def _minimal_record(*, reverse: bool = False) -> CanonicalRecord:
    fields = (
        ("object_kind", CanonicalText("physical_system_spec")),
        ("schema_version", CanonicalText("1.0")),
        (
            "canonicalization_profile",
            CanonicalText(CANONICALIZATION_PROFILE),
        ),
    )
    return CanonicalRecord(
        "physical_system_spec", tuple(reversed(fields)) if reverse else fields
    )


def _common_ref_metadata() -> dict[str, object]:
    return {
        "challenge_key": _KEY,
        "object_id": "physical_one",
        "object_version": "1.0",
        "schema_version": "1.0",
        "canonicalization_profile": CANONICALIZATION_PROFILE,
    }


def _derived_record(
    record_type: str, *, overrides: dict[str, object] | None = None
) -> CanonicalRecord:
    values: dict[str, object] = {
        name: CanonicalText(f"value_{index}")
        for index, name in enumerate(derived_record_field_names(record_type))
    }
    if "schema_version" in values:
        values["schema_version"] = CanonicalText(AUTHORING_SCHEMA_VERSION)
    if "canonicalization_profile" in values:
        values["canonicalization_profile"] = CanonicalText(
            DERIVED_EVIDENCE_CANONICALIZATION_PROFILE
        )
    if overrides is not None:
        values.update(overrides)
    return CanonicalRecord(record_type, tuple(values.items()))


def test_independent_golden_document_vector_and_field_sorting() -> None:
    record = _minimal_record()
    actual = canonical_document("physical_system_spec", "1.0", record)
    expected_record = (
        b"\x09"
        + _text("physical_system_spec")
        + (3).to_bytes(4, "big")
        + _text("canonicalization_profile")
        + _text(CANONICALIZATION_PROFILE)
        + _text("object_kind")
        + _text("physical_system_spec")
        + _text("schema_version")
        + _text("1.0")
    )
    expected = _HEADER + _text("physical_system_spec") + _text("1.0") + expected_record
    assert actual == expected
    assert (
        canonical_document("physical_system_spec", "1.0", _minimal_record(reverse=True))
        == expected
    )
    assert tagged_sha256(actual) == (
        "sha256:58118395063cbbaa2bf7c17ccc6b859fd22c8c8198455a3f13cdb0d3c4fffb91"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (False, b"\x01"),
        (True, b"\x02"),
        (CanonicalInt64(-2), b"\x03" + (-2).to_bytes(8, "big", signed=True)),
        (CanonicalUInt64(2), b"\x04" + (2).to_bytes(8, "big")),
        (CanonicalFloat64(1.5), b"\x05" + struct.pack(">d", 1.5)),
        (CanonicalFloat64(-0.0), b"\x05" + b"\x00" * 8),
        (CanonicalText("A"), b"\x06\x00\x00\x00\x01A"),
        (CanonicalBytes(b"A"), b"\x07\x00\x00\x00\x01A"),
        (
            CanonicalTuple((True, False)),
            b"\x08\x00\x00\x00\x02\x02\x01",
        ),
        (
            CanonicalUnion("BOUND", CanonicalText("x")),
            b"\x0a" + _text("BOUND") + _text("x"),
        ),
    ),
)
def test_primitive_golden_vectors(value: object, expected: bytes) -> None:
    assert encode_value(value) == expected
    assert encode_value(decode_value(expected)) == expected


def test_record_and_nominal_ref_golden_vectors() -> None:
    record = CanonicalRecord("empty_payload", ())
    assert encode_value(record) == b"\x09" + _text("empty_payload") + b"\x00" * 4
    nominal = CanonicalNominalRef("unit", CanonicalRecord("owner_ref", ()))
    assert encode_value(nominal) == (
        b"\x0b" + _text("unit") + b"\x09" + _text("owner_ref") + b"\x00" * 4
    )


def test_integer_bool_float_and_tuple_order_are_distinct() -> None:
    encodings = {
        encode_value(True),
        encode_value(CanonicalInt64(1)),
        encode_value(CanonicalUInt64(1)),
        encode_value(CanonicalFloat64(1.0)),
    }
    assert len(encodings) == 4
    assert encode_value(CanonicalTuple((CanonicalText("a"), CanonicalText("b")))) != (
        encode_value(CanonicalTuple((CanonicalText("b"), CanonicalText("a"))))
    )


def test_set_like_tuple_sorts_complete_bytes_and_rejects_duplicates() -> None:
    left = CanonicalTuple((CanonicalText("z"), CanonicalText("a")), set_like=True)
    right = CanonicalTuple((CanonicalText("a"), CanonicalText("z")), set_like=True)
    assert left.items == right.items
    assert encode_value(left) == encode_value(right)
    with pytest.raises(CanonicalEncodingError):
        CanonicalTuple((CanonicalText("same"), CanonicalText("same")), set_like=True)


def test_canonical_bytes_ignore_environment_and_object_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_record = _minimal_record(reverse=True)
    first = canonical_document("physical_system_spec", "1.0", first_record)
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    monkeypatch.setenv("PYTHONHASHSEED", "different")
    monkeypatch.chdir(os.path.dirname(__file__))
    second_record = _minimal_record()
    second = canonical_document("physical_system_spec", "1.0", second_record)
    assert first_record is not second_record
    assert first == second


def test_document_domain_separation_and_common_field_binding() -> None:
    physical = canonical_document("physical_system_spec", "1.0", _minimal_record())
    candidate_record = CanonicalRecord(
        "candidate_output_contract",
        (
            ("object_kind", CanonicalText("candidate_output_contract")),
            ("schema_version", CanonicalText("1.0")),
            (
                "canonicalization_profile",
                CanonicalText(CANONICALIZATION_PROFILE),
            ),
        ),
    )
    candidate = canonical_document("candidate_output_contract", "1.0", candidate_record)
    assert physical != candidate
    assert tagged_sha256(physical) != tagged_sha256(candidate)
    with pytest.raises(CanonicalEncodingError):
        canonical_document("candidate_output_contract", "1.0", _minimal_record())
    with pytest.raises(CanonicalEncodingError):
        canonical_document("physical_system_spec", "2.0", _minimal_record())


def test_document_decode_rejects_missing_unknown_or_extra_closed_fields() -> None:
    payload = canonical_document("physical_system_spec", "1.0", _minimal_record())
    decoded = decode_document(
        payload,
        expected_object_kind="physical_system_spec",
        expected_schema_version="1.0",
        allowed_record_fields=(
            "object_kind",
            "schema_version",
            "canonicalization_profile",
        ),
    )
    assert decoded.record == _minimal_record()
    with pytest.raises(CanonicalDecodingError):
        decode_document(payload, allowed_record_fields=("object_kind",))
    with pytest.raises(CanonicalDecodingError):
        decode_document(payload, expected_object_kind="sampling_plan")
    with pytest.raises(CanonicalDecodingError):
        decode_document(payload, expected_schema_version="2.0")


def test_explicit_derived_registry_has_only_contract_field_sets() -> None:
    assert set(DERIVED_RECORD_FIELD_REGISTRY_V1) == {
        "protected_case_identity_projection",
        "internal_case_identity_projection",
        "public_case_identity_projection",
        "case_evidence_binding",
        "replacement_decision",
        "canonical_case_disposition",
        "censoring_record",
        "realized_valid_evidence_record",
    }
    assert DERIVED_DOCUMENT_RECORD_TYPES_V1 == (
        "canonical_case_disposition",
        "censoring_record",
        "realized_valid_evidence_record",
    )
    for record_type, fields in DERIVED_RECORD_FIELD_REGISTRY_V1.items():
        assert fields == tuple(sorted(fields))
        assert derived_record_field_names(record_type) == fields
        assert validate_registered_derived_record(_derived_record(record_type))
    with pytest.raises(CanonicalEncodingError):
        derived_record_field_names("unknown_record")
    with pytest.raises(CanonicalEncodingError):
        derived_record_field_names("censoring_record", schema_version="2.0")


@pytest.mark.parametrize("record_type", DERIVED_DOCUMENT_RECORD_TYPES_V1)
def test_derived_document_round_trip_is_exact_closed_and_versioned(
    record_type: str,
) -> None:
    record = _derived_record(record_type)
    payload = canonical_derived_document(record_type, "1.0", record)
    assert payload.startswith(_DERIVED_HEADER)
    decoded = decode_derived_document(
        payload,
        expected_record_type=record_type,
        expected_schema_version="1.0",
        expected_record_fields=derived_record_field_names(record_type),
    )
    assert decoded.record_type == record_type
    assert decoded.schema_version == AUTHORING_SCHEMA_VERSION
    assert decoded.canonicalization_profile == DERIVED_EVIDENCE_CANONICALIZATION_PROFILE
    assert decoded.record == record
    assert (
        canonical_derived_document(
            decoded.record_type, decoded.schema_version, decoded.record
        )
        == payload
    )


@pytest.mark.parametrize(
    "record_type",
    (
        "protected_case_identity_projection",
        "internal_case_identity_projection",
        "public_case_identity_projection",
        "case_evidence_binding",
        "replacement_decision",
    ),
)
def test_subordinate_registered_records_cannot_claim_derived_document_framing(
    record_type: str,
) -> None:
    with pytest.raises(CanonicalEncodingError):
        canonical_derived_document(record_type, "1.0", _derived_record(record_type))
    with pytest.raises(CanonicalEncodingError):
        validate_registered_derived_record(
            _derived_record(record_type), document_record=True
        )


def test_derived_encoder_rejects_wrong_version_profile_and_field_set() -> None:
    correct = _derived_record("censoring_record")
    with pytest.raises(CanonicalEncodingError):
        canonical_derived_document("censoring_record", "2.0", correct)

    wrong_schema = _derived_record(
        "censoring_record",
        overrides={"schema_version": CanonicalText("2.0")},
    )
    with pytest.raises(CanonicalEncodingError):
        canonical_derived_document("censoring_record", "1.0", wrong_schema)

    wrong_profile = _derived_record(
        "censoring_record",
        overrides={"canonicalization_profile": CanonicalText("wrong_profile")},
    )
    with pytest.raises(CanonicalEncodingError):
        canonical_derived_document("censoring_record", "1.0", wrong_profile)

    fields = dict(correct.fields)
    fields.pop("accounting_binding")
    with pytest.raises(CanonicalEncodingError):
        canonical_derived_document(
            "censoring_record",
            "1.0",
            CanonicalRecord("censoring_record", tuple(fields.items())),
        )
    fields["accounting_binding"] = CanonicalText("restored")
    fields["unknown_field"] = CanonicalText("extra")
    with pytest.raises(CanonicalEncodingError):
        canonical_derived_document(
            "censoring_record",
            "1.0",
            CanonicalRecord("censoring_record", tuple(fields.items())),
        )


def test_derived_decoder_rejects_malformed_framing() -> None:
    record_type = "censoring_record"
    record = _derived_record(record_type)
    encoded_record = encode_value(record)
    valid = canonical_derived_document(record_type, "1.0", record)

    with pytest.raises(CanonicalDecodingError):
        decode_derived_document(valid.replace(_DERIVED_HEADER, _HEADER, 1))
    with pytest.raises(CanonicalDecodingError):
        decode_derived_document(
            _DERIVED_HEADER + _text("unknown_record") + _text("1.0") + encoded_record
        )
    with pytest.raises(CanonicalDecodingError):
        decode_derived_document(
            _DERIVED_HEADER + _text(record_type) + _text("2.0") + encoded_record
        )
    with pytest.raises(CanonicalDecodingError):
        decode_derived_document(valid + b"trailing")
    with pytest.raises(CanonicalDecodingError):
        decode_derived_document(
            valid, expected_record_type="canonical_case_disposition"
        )
    with pytest.raises(CanonicalDecodingError):
        decode_derived_document(valid, expected_schema_version="2.0")
    with pytest.raises(CanonicalDecodingError):
        decode_derived_document(valid, expected_record_fields=("schema_version",))


def test_zero_payload_record_rejects_garbage_on_encode_and_decode() -> None:
    with pytest.raises(CanonicalEncodingError):
        CanonicalRecord("empty_payload", (("garbage", CanonicalText("value")),))
    malformed = (
        b"\x09"
        + _text("empty_payload")
        + (1).to_bytes(4, "big")
        + _text("garbage")
        + _text("value")
    )
    with pytest.raises(CanonicalDecodingError):
        decode_value(malformed)


def test_top_level_v1_framing_and_ref_codec_reject_other_schema_versions() -> None:
    record = CanonicalRecord(
        "physical_system_spec",
        (
            ("object_kind", CanonicalText("physical_system_spec")),
            ("schema_version", CanonicalText("2.0")),
            (
                "canonicalization_profile",
                CanonicalText(CANONICALIZATION_PROFILE),
            ),
        ),
    )
    with pytest.raises(CanonicalEncodingError):
        canonical_document("physical_system_spec", "2.0", record)
    raw = _HEADER + _text("physical_system_spec") + _text("2.0") + encode_value(record)
    with pytest.raises(CanonicalDecodingError):
        decode_document(raw)
    with pytest.raises(CanonicalEncodingError):
        make_top_level_ref(
            PhysicalSystemSpecRef,
            canonical_bytes=b"canonical",
            challenge_key=_KEY,
            object_id="physical_one",
            object_version="1.0",
            schema_version="2.0",
            canonicalization_profile=CANONICALIZATION_PROFILE,
        )

    valid_ref = PhysicalSystemSpecRef(
        _KEY,
        "physical_one",
        "1.0",
        "1.0",
        CANONICALIZATION_PROFILE,
        _DIGEST,
    )
    node = top_level_ref_to_canonical(valid_ref)
    fields = dict(node.record.fields)
    fields["schema_version"] = CanonicalText("2.0")
    unsupported_payload = encode_value(
        CanonicalNominalRef(
            node.ref_type,
            CanonicalRecord(node.record.record_type, tuple(fields.items())),
        )
    )
    with pytest.raises(CanonicalDecodingError):
        decode_top_level_ref(unsupported_payload)


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"\xff",
        b"\x00",
        b"\x06\x00\x01\x00\x00",
        b"\x06\x00\x00\x00\x02a",
        b"\x06\x00\x00\x00\x02\xc3(",
        b"\x06\x00\x00\x00\x03e\xcc\x81",
        b"\x06\x00\x00\x00\x01\x00",
        b"\x01trailing",
        b"\x08\x00\x00\x00\x02\x01",
    ),
)
def test_decoder_rejects_unknown_truncated_noncanonical_or_trailing_bytes(
    payload: bytes,
) -> None:
    with pytest.raises(CanonicalDecodingError):
        decode_value(payload)


def test_decoder_rejects_negative_zero_and_nonfinite_float_bits() -> None:
    with pytest.raises(CanonicalDecodingError):
        decode_value(b"\x05" + struct.pack(">d", -0.0))
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalDecodingError):
            decode_value(b"\x05" + struct.pack(">d", value))


def test_decoder_rejects_non_increasing_and_duplicate_record_fields() -> None:
    unsorted = (
        b"\x09"
        + _text("record")
        + (2).to_bytes(4, "big")
        + _text("z")
        + b"\x01"
        + _text("a")
        + b"\x02"
    )
    duplicate = (
        b"\x09"
        + _text("record")
        + (2).to_bytes(4, "big")
        + _text("a")
        + b"\x01"
        + _text("a")
        + b"\x02"
    )
    with pytest.raises(CanonicalDecodingError):
        decode_value(unsorted)
    with pytest.raises(CanonicalDecodingError):
        decode_value(duplicate)


def test_text_bytes_tuple_and_depth_bounds_are_enforced() -> None:
    assert encode_value(CanonicalText("a" * MAX_CANONICAL_PAYLOAD_BYTES))
    assert encode_value(CanonicalBytes(b"a" * MAX_CANONICAL_PAYLOAD_BYTES))
    with pytest.raises(AuthoringValidationError):
        CanonicalText("a" * (MAX_CANONICAL_PAYLOAD_BYTES + 1))
    with pytest.raises(AuthoringValidationError):
        CanonicalBytes(b"a" * (MAX_CANONICAL_PAYLOAD_BYTES + 1))

    value: object = CanonicalText("leaf")
    for _ in range(MAX_CANONICAL_NESTING_DEPTH + 1):
        value = CanonicalUnion("BOUND", value)
    with pytest.raises(CanonicalEncodingError):
        encode_value(value)


def test_document_bound_rejects_before_returning_attacker_sized_payload() -> None:
    large_field = CanonicalBytes(b"a" * MAX_CANONICAL_PAYLOAD_BYTES)
    large_tuple = CanonicalTuple((large_field,) * 257)
    record = CanonicalRecord(
        "physical_system_spec",
        (
            ("object_kind", CanonicalText("physical_system_spec")),
            ("schema_version", CanonicalText("1.0")),
            (
                "canonicalization_profile",
                CanonicalText(CANONICALIZATION_PROFILE),
            ),
            ("payload", large_tuple),
        ),
    )
    with pytest.raises(CanonicalEncodingError):
        canonical_document("physical_system_spec", "1.0", record)
    with pytest.raises(CanonicalDecodingError):
        decode_value(b"\x01" * (MAX_CANONICAL_DOCUMENT_BYTES + 1))


def test_challenge_owner_and_top_level_ref_round_trips_are_exact_nominal() -> None:
    assert challenge_key_to_canonical(_KEY).record_type == "challenge_key"
    unit = owner_ref(
        "unit",
        scope_binding=ChallengeScope(_KEY),
        object_id="unit_si",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    encoded_owner = encode_value(owner_ref_to_canonical(unit))
    decoded_owner = owner_ref_from_canonical(
        decode_value(encoded_owner), expected_kind="unit"
    )
    assert type(decoded_owner) is type(unit)
    assert decoded_owner == unit
    with pytest.raises(CanonicalDecodingError):
        owner_ref_from_canonical(
            decode_value(encoded_owner), expected_kind="representation"
        )

    document = canonical_document("physical_system_spec", "1.0", _minimal_record())
    for ref_type in TOP_LEVEL_REF_TYPES:
        kwargs = _common_ref_metadata()
        extension: dict[str, object] = {}
        if ref_type is InstanceDistributionContractRef:
            extension["expected_population_role"] = "TARGET_WORKLOAD_P"
        if ref_type is CanonicalChallengeCaseRef:
            extension["disclosure_class"] = "PROTECTED"
        ref = make_top_level_ref(
            ref_type, canonical_bytes=document, **kwargs, **extension
        )
        node = top_level_ref_to_canonical(ref)
        assert type(top_level_ref_from_canonical(node)) is ref_type
        assert top_level_ref_from_canonical(node) == ref
        assert decode_top_level_ref(encode_top_level_ref(ref)) == ref


def test_global_owner_scope_round_trip() -> None:
    value = owner_ref(
        "unit",
        scope_binding=GlobalScope(),
        object_id="unit_si",
        object_version="1.0",
        content_digest=_DIGEST,
    )
    assert (
        owner_ref_from_canonical(
            decode_value(encode_value(owner_ref_to_canonical(value))),
            expected_kind="unit",
        )
        == value
    )


def test_ref_digest_pin_and_every_identity_field_are_verified() -> None:
    document = canonical_document("physical_system_spec", "1.0", _minimal_record())
    metadata = _common_ref_metadata()
    expected = make_top_level_ref(
        PhysicalSystemSpecRef, canonical_bytes=document, **metadata
    )
    assert (
        verify_top_level_ref(expected, canonical_bytes=document, **metadata) == expected
    )
    tampered = bytearray(document)
    tampered[-1] ^= 1
    with pytest.raises(ReferenceMismatchError):
        verify_top_level_ref(expected, canonical_bytes=bytes(tampered), **metadata)
    for name, value in (
        ("challenge_key", ChallengeKey("other_case", "1.0")),
        ("object_id", "different"),
        ("object_version", "2.0"),
        ("schema_version", "2.0"),
    ):
        changed = dict(metadata)
        changed[name] = value
        with pytest.raises(ReferenceMismatchError):
            verify_top_level_ref(expected, canonical_bytes=document, **changed)


def test_ref_kind_and_extension_confusion_rejects() -> None:
    document = canonical_document("physical_system_spec", "1.0", _minimal_record())
    metadata = _common_ref_metadata()
    with pytest.raises(CanonicalEncodingError):
        make_top_level_ref(
            PhysicalSystemSpecRef,
            canonical_bytes=document,
            expected_population_role="TARGET_WORKLOAD_P",
            **metadata,
        )
    with pytest.raises(AuthoringValidationError):
        make_top_level_ref(
            InstanceDistributionContractRef,
            canonical_bytes=document,
            expected_population_role="TRAINING_SUPPORT",
            **metadata,
        )
    with pytest.raises(AuthoringValidationError):
        make_top_level_ref(
            CanonicalChallengeCaseRef,
            canonical_bytes=document,
            disclosure_class="PUBLIC",
            **metadata,
        )


def test_digest_is_outside_authored_content_and_input_must_be_exact_bytes() -> None:
    document = canonical_document("physical_system_spec", "1.0", _minimal_record())
    digest = tagged_sha256(document)
    assert digest.encode() not in document
    with pytest.raises(CanonicalEncodingError):
        tagged_sha256(bytearray(document))
