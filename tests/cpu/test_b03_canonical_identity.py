"""Focused B-03 closed canonical-profile tests."""

from __future__ import annotations

from dataclasses import fields, replace

import pytest
from b03_fixtures import make_b03_fixture

from carbon.authoring.refs import ChallengeScope
from carbon.generators.burgers import burgers_fixture_configuration_ref
from carbon.generators.canonical import (
    GENERATOR_IMPLEMENTATION_MANIFEST_HEADER,
    GENERATOR_RUNTIME_CANONICAL_OBJECT_KINDS,
    GENERATOR_RUNTIME_DOCUMENT_HEADER,
    canonical_bytes,
    decode_canonical_bytes,
    verify_canonical_ref,
)
from carbon.generators.errors import (
    GeneratorCanonicalDecodingError,
    GeneratorInputCode,
    GeneratorValidationError,
)
from carbon.generators.model import (
    GenerationSourceEvent,
    GeneratorEnvironmentClass,
    GeneratorEnvironmentDescriptor,
    GeneratorImplementationManifest,
    SourceMaterializationState,
)
from carbon.generators.service import build_generation_source_event
from carbon.registry.model import ChallengeKey


def _challenge() -> ChallengeKey:
    return ChallengeKey("b03_canonical_fixture", "1.0")


def _environment() -> GeneratorEnvironmentDescriptor:
    return GeneratorEnvironmentDescriptor(
        _challenge(),
        "b03_fixture_environment",
        "1.0",
        "cpython",
        "3.11.16",
        "manylinux_2_17_x86_64",
        "sha256:" + "4" * 64,
        GeneratorEnvironmentClass.FIXTURE_ONLY,
    )


def test_contract_registry_contains_exact_twenty_seven_standalone_kinds() -> None:
    assert len(GENERATOR_RUNTIME_CANONICAL_OBJECT_KINDS) == 27
    assert GENERATOR_RUNTIME_CANONICAL_OBJECT_KINDS[0] == (
        "generator_implementation_manifest"
    )
    assert GENERATOR_RUNTIME_CANONICAL_OBJECT_KINDS[-1] == (
        "external_distribution_fact_set"
    )


def test_environment_canonical_round_trip_tamper_and_trailing_rejection() -> None:
    environment = _environment()
    payload = canonical_bytes(environment)

    assert payload.startswith(GENERATOR_RUNTIME_DOCUMENT_HEADER)
    assert (
        decode_canonical_bytes(payload, GeneratorEnvironmentDescriptor) == environment
    )
    verify_canonical_ref(environment, environment.to_ref())

    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(payload + b"\x00", GeneratorEnvironmentDescriptor)
    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(b"wrong" + payload, GeneratorEnvironmentDescriptor)


def test_manifest_uses_distinct_header_and_is_deterministic() -> None:
    manifest = GeneratorImplementationManifest(
        "carbon_generators_burgers_fixture",
        "1.0",
        "carbon.generators.burgers",
        "0.1",
        "carbon_generator_runtime_canonical_v1",
        burgers_fixture_configuration_ref(_challenge()),
        "carbon.b03.burgers.fixture-latent.v1",
    )
    first = manifest.canonical_bytes()
    second = manifest.canonical_bytes()

    assert first.startswith(GENERATOR_IMPLEMENTATION_MANIFEST_HEADER)
    assert first == second
    assert decode_canonical_bytes(first, GeneratorImplementationManifest) == manifest
    assert manifest.implementation_digest.startswith("sha256:")


def test_decoder_requires_an_explicit_registered_exact_type() -> None:
    with pytest.raises(TypeError):
        decode_canonical_bytes(canonical_bytes(_environment()), object)


def _constructor_bypass(value: object, **changes: object) -> object:
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            forged,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return forged


@pytest.mark.parametrize("field_name", ("replay_ref", "role_binding"))
def test_source_event_decoder_rejects_nested_cross_challenge_identity(
    field_name: str,
) -> None:
    fixture = make_b03_fixture()
    event = build_generation_source_event(
        fixture.request,
        payload_ref=None,
        materialization_state=SourceMaterializationState.NO_PAYLOAD,
    )
    other = ChallengeKey("b03_other_challenge", "1.0")
    if field_name == "replay_ref":
        other_issuer = replace(
            event.replay_ref.reservation_issuer_ref,
            scope_binding=ChallengeScope(other),
        )
        replacement = replace(
            event.replay_ref,
            challenge_key=other,
            reservation_issuer_ref=other_issuer,
        )
    else:
        other_plan = replace(event.sampling_plan_ref, challenge_key=other)
        replacement = replace(event.role_binding, sampling_plan_ref=other_plan)
    forged = _constructor_bypass(event, **{field_name: replacement})

    with pytest.raises(GeneratorValidationError) as constructed:
        replace(event, **{field_name: replacement})
    assert constructed.value.code == GeneratorInputCode.CROSS_CHALLENGE.value
    with pytest.raises(GeneratorCanonicalDecodingError):
        decode_canonical_bytes(
            canonical_bytes(forged),
            GenerationSourceEvent,
        )
