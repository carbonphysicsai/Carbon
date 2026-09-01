"""Adversarial byte-level and cross-process proof for the B-03 codec."""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys

import pytest
from b03_fixtures import make_b03_fixture

from carbon.authoring.canonical import (
    CanonicalText,
    CanonicalUInt64,
    encode_value,
)
from carbon.generators.burgers import (
    BURGERS_FIXTURE_GRID_POINTS,
    BURGERS_FIXTURE_PERIOD,
    BURGERS_FIXTURE_VISCOSITY,
    ProtectedBurgersFixturePayload,
    _new_protected_payload,
    burgers_fixture_configuration_ref,
)
from carbon.generators.canonical import (
    GENERATOR_RUNTIME_DOCUMENT_HEADER,
    canonical_bytes,
    canonical_record,
    decode_canonical_bytes,
)
from carbon.generators.errors import (
    GeneratorCanonicalDecodingError,
    GeneratorInputCode,
)
from carbon.generators.model import GeneratorEnvironmentDescriptor
from carbon.registry.model import ChallengeKey


def _encoded_record(
    record_type: str,
    fields: tuple[tuple[str, object], ...],
) -> bytes:
    """Encode a raw record without normalizing order or duplicate names."""

    chunks = [b"\x09", encode_value(CanonicalText(record_type))]
    chunks.append(len(fields).to_bytes(4, "big"))
    for name, value in fields:
        chunks.append(encode_value(CanonicalText(name)))
        chunks.append(value if type(value) is bytes else encode_value(value))
    return b"".join(chunks)


def _document(record_type: str, fields: tuple[tuple[str, object], ...]) -> bytes:
    return GENERATOR_RUNTIME_DOCUMENT_HEADER + _encoded_record(record_type, fields)


def _environment() -> GeneratorEnvironmentDescriptor:
    return make_b03_fixture().request.environment


@pytest.mark.parametrize("mutation", ("missing", "extra", "reordered", "duplicate"))
def test_top_level_schema_rejects_nonexact_field_manifests(mutation: str) -> None:
    environment = _environment()
    record = canonical_record(environment)
    fields = list(record.fields)
    if mutation == "missing":
        fields.pop()
    elif mutation == "extra":
        fields.append(("zz_unregistered_field", CanonicalText("forbidden")))
        fields.sort(key=lambda item: item[0].encode("utf-8"))
    elif mutation == "reordered":
        fields[0], fields[1] = fields[1], fields[0]
    else:
        fields.insert(1, fields[0])

    with pytest.raises(GeneratorCanonicalDecodingError) as caught:
        decode_canonical_bytes(
            _document(record.record_type, tuple(fields)),
            GeneratorEnvironmentDescriptor,
        )

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_decoder_rejects_wrong_primitive_tag() -> None:
    environment = _environment()
    record = canonical_record(environment)
    fields = tuple(
        (name, CanonicalUInt64(311) if name == "python_version" else value)
        for name, value in record.fields
    )

    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(
            _document(record.record_type, fields),
            GeneratorEnvironmentDescriptor,
        )


def _protected_payload() -> ProtectedBurgersFixturePayload:
    challenge = ChallengeKey("b03_canonical_adversarial", "1.0")
    return _new_protected_payload(
        fixture_configuration_ref=burgers_fixture_configuration_ref(challenge),
        period=BURGERS_FIXTURE_PERIOD,
        grid_points=BURGERS_FIXTURE_GRID_POINTS,
        viscosity=BURGERS_FIXTURE_VISCOSITY,
        initial_values=(0.0,) * BURGERS_FIXTURE_GRID_POINTS,
    )


def test_decoder_rejects_boolean_for_uint64_field() -> None:
    payload = _protected_payload()
    record = canonical_record(payload)
    fields = tuple(
        (name, True if name == "grid_points" else value)
        for name, value in record.fields
    )

    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(
            _document(record.record_type, fields),
            ProtectedBurgersFixturePayload,
        )


def test_decoder_rejects_nonfinite_float64_bits() -> None:
    payload = _protected_payload()
    record = canonical_record(payload)
    nan_value = b"\x05" + struct.pack(">d", float("nan"))
    fields = tuple(
        (name, nan_value if name == "period" else value)
        for name, value in record.fields
    )

    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(
            _document(record.record_type, fields),
            ProtectedBurgersFixturePayload,
        )


def test_decoder_marks_trailing_bytes_without_retaining_authoring_error() -> None:
    payload = canonical_bytes(_environment()) + b"\x00"

    with pytest.raises(GeneratorCanonicalDecodingError) as caught:
        decode_canonical_bytes(payload, GeneratorEnvironmentDescriptor)

    assert caught.value.code == GeneratorInputCode.TRAILING_BYTES.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


_CROSS_PROCESS_SCRIPT = r"""
import json
import sys

sys.path.insert(0, "tests/cpu")

from b03_fixtures import make_b03_fixture
from carbon.generators.refs import encode_generator_ref
from carbon.generators.service import generate_fixture_case

fixture = make_b03_fixture()
result = generate_fixture_case(
    fixture.request,
    fixture_authority=fixture.fixture_authority,
    support_authority=fixture.support_authority,
    censoring_authority=fixture.censoring_authority,
    accounting_authority=fixture.accounting_authority,
).payload
documents = (
    fixture.request.identity().canonical_bytes(),
    encode_generator_ref(fixture.request.to_ref()),
    result.record.canonical_bytes(),
    encode_generator_ref(result.ref),
    result.artifact.case.canonical_bytes(),
)
print(json.dumps([item.hex() for item in documents], separators=(",", ":")))
"""


def _cross_process_documents(hash_seed: str) -> list[str]:
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = hash_seed
    environment["PYTHONPATH"] = "."
    completed = subprocess.run(
        [sys.executable, "-c", _CROSS_PROCESS_SCRIPT],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return json.loads(completed.stdout)


def test_complete_request_result_and_case_are_hash_seed_deterministic() -> None:
    first = _cross_process_documents("1")
    second = _cross_process_documents("8675309")

    assert len(first) == 5
    assert first == second
