"""Focused proof for the B-03 fixed Burgers structural fixture."""

from __future__ import annotations

import hashlib
import math
import pickle
from dataclasses import FrozenInstanceError, fields

import pytest

from carbon.authoring.loading import GraphOriginTag
from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.generators.burgers import (
    BurgersFixtureConfiguration,
    BurgersProductionInputsUnavailable,
    FixtureDegeneracyFacts,
    FixturePayloadFacts,
    GeneratedFixtureArtifact,
    PhysicalPayloadFingerprint,
    ProductionInputAvailability,
    ProtectedBurgersFixturePayload,
    ValidatedCaseFacts,
    _decode_burgers_fixture_configuration,
    _materialize_burgers_fixture_payload,
    _new_protected_payload,
    build_fixture_payload_facts,
    build_generated_fixture_artifact,
    build_physical_payload_fingerprint,
    burgers_fixture_configuration,
    burgers_fixture_configuration_ref,
    burgers_production_inputs_unavailable,
)
from carbon.generators.canonical import (
    GENERATOR_RUNTIME_DOCUMENT_HEADER,
    canonical_content_digest,
    decode_canonical_bytes,
    verify_canonical_ref,
)
from carbon.generators.errors import GeneratorInputCode, GeneratorValidationError
from carbon.generators.refs import (
    BurgersFixtureConfigurationRef,
    PhysicalPayloadFingerprintRef,
)
from carbon.registry import ChallengeKey
from carbon.seeding.model import DerivedSeed

_CONFIGURATION_FIELDS = (
    "configuration_id",
    "configuration_version",
    "boundary_shape",
    "period",
    "grid_points",
    "viscosity",
    "latent_codec_id",
    "basis_1",
    "basis_2",
)
_PRODUCTION_INPUT_FIELDS = (
    "primary_population_law",
    "selection_population_law",
    "selection_density_or_mass",
    "importance_weight",
    "viscosity",
    "parameter_ranges",
    "forcing_law",
    "initial_condition_law",
    "grid_specification",
    "horizon_specification",
    "stratification",
    "exclusions",
    "conformance_estimands",
    "conformance_thresholds",
    "qualification_evidence",
)
_PAYLOAD_FIELDS = (
    "fixture_configuration_ref",
    "period",
    "grid_points",
    "viscosity",
    "initial_values",
)
_BASIS_1 = (0, 1, 1, 0, -1, -1, 0, 0)
_BASIS_2 = (1, 1, 0, -1, -1, 0, 1, 0)


class _TextSubclass(str):
    pass


class _IntSubclass(int):
    pass


def _challenge(version: str = "1.0") -> ChallengeKey:
    return ChallengeKey("b03_burgers_fixture", version)


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode('ascii')).hexdigest()}"


def _challenge_owner(kind: str, label: str, key: ChallengeKey) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(key),
        object_id=label,
        object_version="1.0",
        content_digest=_digest(f"{kind}:{label}"),
    )


def _payload(
    material: bytes = bytes(range(32)),
    *,
    key: ChallengeKey | None = None,
) -> ProtectedBurgersFixturePayload:
    challenge = key if key is not None else _challenge()
    return _materialize_burgers_fixture_payload(
        DerivedSeed(material),
        fixture_configuration_ref=burgers_fixture_configuration_ref(challenge),
    )


def _fingerprint(
    payload: ProtectedBurgersFixturePayload,
    *,
    key: ChallengeKey | None = None,
) -> PhysicalPayloadFingerprint:
    challenge = key if key is not None else _challenge()
    return build_physical_payload_fingerprint(
        challenge_key=challenge,
        case_representation_ref=_challenge_owner(
            "representation", "periodic_float64_grid_8", challenge
        ),
        fixture_configuration_ref=payload.fixture_configuration_ref,
        protected_payload=payload,
    )


def _payload_ref(
    payload: ProtectedBurgersFixturePayload,
    *,
    label: str,
) -> object:
    key = payload.fixture_configuration_ref.challenge_key
    return owner_ref(
        "protected_case_payload",
        scope_binding=ChallengeScope(key),
        object_id=label,
        object_version="1.0",
        content_digest=canonical_content_digest(payload),
    )


def _independent_oracle(material: bytes) -> tuple[float, ...]:
    w1 = int.from_bytes(material[0:8], "big", signed=False)
    w2 = int.from_bytes(material[8:16], "big", signed=False)
    n1 = (w1 % 2001) - 1000
    n2 = (w2 % 2001) - 1000
    return tuple(
        (n1 * basis_1 + n2 * basis_2) / 4096.0
        for basis_1, basis_2 in zip(_BASIS_1, _BASIS_2, strict=True)
    )


def test_fixed_configuration_is_exact_challenge_neutral_and_immutable() -> None:
    configuration = burgers_fixture_configuration()

    assert type(configuration) is BurgersFixtureConfiguration
    assert tuple(field.name for field in fields(configuration)) == _CONFIGURATION_FIELDS
    assert configuration.configuration_id == "b03_burgers_structural_fixture"
    assert configuration.configuration_version == "1.0"
    assert configuration.boundary_shape == "PERIODIC_1D"
    assert configuration.period == 1.0
    assert type(configuration.period) is float
    assert configuration.grid_points == 8
    assert type(configuration.grid_points) is int
    assert configuration.viscosity == 1.0
    assert type(configuration.viscosity) is float
    assert configuration.latent_codec_id == "carbon.b03.burgers.fixture-latent.v1"
    assert configuration.basis_1 == _BASIS_1
    assert configuration.basis_2 == _BASIS_2
    assert not hasattr(configuration, "challenge_key")
    assert burgers_fixture_configuration() is configuration

    with pytest.raises(TypeError):
        BurgersFixtureConfiguration()  # type: ignore[call-arg]
    with pytest.raises(FrozenInstanceError):
        configuration.viscosity = 0.005  # type: ignore[misc]


def test_fixed_configuration_canonical_round_trip_and_scoped_ref() -> None:
    configuration = burgers_fixture_configuration()
    encoded = configuration.canonical_bytes()
    key = _challenge()
    other_key = _challenge("2.0")

    assert encoded.startswith(GENERATOR_RUNTIME_DOCUMENT_HEADER)
    assert decode_canonical_bytes(encoded, BurgersFixtureConfiguration) is configuration
    ref = configuration.to_ref(key)
    other_ref = configuration.to_ref(other_key)
    assert type(ref) is BurgersFixtureConfigurationRef
    assert ref.challenge_key == key
    assert other_ref.challenge_key == other_key
    assert ref.content_digest == other_ref.content_digest
    verify_canonical_ref(configuration, ref)

    with pytest.raises(GeneratorValidationError) as caught:
        decode_canonical_bytes(encoded + b"\x00", BurgersFixtureConfiguration)
    assert caught.value.code in {
        GeneratorInputCode.INVALID_CANONICAL_BYTES.value,
        GeneratorInputCode.TRAILING_BYTES.value,
    }


@pytest.mark.parametrize(
    ("field_name", "hostile_value"),
    (
        ("configuration_id", _TextSubclass("b03_burgers_structural_fixture")),
        ("period", True),
        ("grid_points", 8.0),
        ("grid_points", _IntSubclass(8)),
        ("viscosity", True),
        ("basis_1", (False, 1, 1, 0, -1, -1, 0, 0)),
        ("basis_2", (1.0, 1, 0, -1, -1, 0, 1, 0)),
    ),
)
def test_private_configuration_builder_rejects_numeric_type_confusion(
    field_name: str,
    hostile_value: object,
) -> None:
    configuration = burgers_fixture_configuration()
    values = {name: getattr(configuration, name) for name in _CONFIGURATION_FIELDS}
    values[field_name] = hostile_value

    with pytest.raises(GeneratorValidationError) as caught:
        _decode_burgers_fixture_configuration(**values)

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_production_inputs_are_all_typed_human_input_required() -> None:
    report = burgers_production_inputs_unavailable()

    assert type(report) is BurgersProductionInputsUnavailable
    assert tuple(field.name for field in fields(report)) == _PRODUCTION_INPUT_FIELDS
    assert all(
        getattr(report, name) is ProductionInputAvailability.HUMAN_INPUT_REQUIRED
        for name in _PRODUCTION_INPUT_FIELDS
    )
    assert burgers_production_inputs_unavailable() is report
    assert ProductionInputAvailability.HUMAN_INPUT_REQUIRED.value == (
        "HUMAN_INPUT_REQUIRED"
    )
    with pytest.raises(TypeError):
        BurgersProductionInputsUnavailable()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        BurgersProductionInputsUnavailable(  # type: ignore[call-arg]
            viscosity="HUMAN_INPUT_REQUIRED"
        )


def test_private_sampler_uses_exact_two_word_big_endian_codec_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    material = bytes(range(32))
    original = DerivedSeed.as_backend_bytes
    calls: list[DerivedSeed] = []

    def counted(seed: DerivedSeed) -> bytes:
        calls.append(seed)
        return original(seed)

    monkeypatch.setattr(DerivedSeed, "as_backend_bytes", counted)
    payload = _payload(material)

    assert len(calls) == 1
    assert tuple(field.name for field in fields(payload)) == _PAYLOAD_FIELDS
    assert payload.period == 1.0
    assert payload.grid_points == 8
    assert payload.viscosity == 1.0
    assert payload.initial_values == _independent_oracle(material)
    assert len(payload.initial_values) == 8
    assert all(
        type(value) is float and math.isfinite(value)
        for value in payload.initial_values
    )
    assert all((value * 4096.0).is_integer() for value in payload.initial_values)


@pytest.mark.parametrize(
    ("field_name", "non_finite"),
    (
        ("period", float("nan")),
        ("viscosity", float("inf")),
        ("initial_values", float("-inf")),
    ),
)
def test_protected_payload_rejects_every_non_finite_numeric_input(
    field_name: str,
    non_finite: float,
) -> None:
    payload = _payload()
    values: dict[str, object] = {
        "fixture_configuration_ref": payload.fixture_configuration_ref,
        "period": payload.period,
        "grid_points": payload.grid_points,
        "viscosity": payload.viscosity,
        "initial_values": payload.initial_values,
    }
    if field_name == "initial_values":
        values[field_name] = (non_finite, *payload.initial_values[1:])
    else:
        values[field_name] = non_finite

    with pytest.raises(GeneratorValidationError) as caught:
        _new_protected_payload(**values)

    assert caught.value.code == GeneratorInputCode.INVALID_VALUE.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_sampler_ignores_final_sixteen_bytes_and_rejects_non_seed() -> None:
    prefix = bytes(range(16))
    first = _payload(prefix + bytes(16))
    second = _payload(prefix + bytes([255]) * 16)

    assert first == second
    with pytest.raises(GeneratorValidationError) as caught:
        _materialize_burgers_fixture_payload(  # type: ignore[arg-type]
            prefix + bytes(16),
            fixture_configuration_ref=first.fixture_configuration_ref,
        )
    assert caught.value.code == GeneratorInputCode.WRONG_TYPE.value

    stale_configuration_ref = BurgersFixtureConfigurationRef(
        _challenge(), _digest("caller_selected_configuration")
    )
    with pytest.raises(GeneratorValidationError) as caught:
        _materialize_burgers_fixture_payload(
            DerivedSeed(prefix + bytes(16)),
            fixture_configuration_ref=stale_configuration_ref,
        )
    assert caught.value.code == GeneratorInputCode.STALE_BINDING.value


def test_protected_payload_round_trip_redaction_and_closed_field_inventory() -> None:
    payload = _payload()
    encoded = payload.canonical_bytes()
    decoded = decode_canonical_bytes(encoded, ProtectedBurgersFixturePayload)

    assert decoded == payload
    assert repr(payload) == "ProtectedBurgersFixturePayload(<protected>)"
    assert str(payload) == repr(payload)
    assert all(
        forbidden not in _PAYLOAD_FIELDS
        for forbidden in (
            "seed",
            "word",
            "coefficient",
            "draw",
            "slot",
            "stratum",
            "replay",
            "reference",
            "candidate_output",
        )
    )
    with pytest.raises(TypeError):
        pickle.dumps(payload)
    with pytest.raises(TypeError):
        vars(payload)


def test_physical_fingerprint_binds_full_payload_but_not_attempt_identity() -> None:
    payload = _payload()
    fingerprint = _fingerprint(payload)
    ref = fingerprint.to_ref()

    assert type(fingerprint) is PhysicalPayloadFingerprint
    assert type(ref) is PhysicalPayloadFingerprintRef
    assert tuple(field.name for field in fields(fingerprint)) == (
        "challenge_key",
        "case_representation_ref",
        "fixture_configuration_ref",
        "protected_payload_digest",
    )
    assert fingerprint.protected_payload_digest == canonical_content_digest(payload)
    assert (
        decode_canonical_bytes(
            fingerprint.canonical_bytes(), PhysicalPayloadFingerprint
        )
        == fingerprint
    )
    verify_canonical_ref(fingerprint, ref)

    first_attempt = _payload_ref(payload, label="attempt_a")
    second_attempt = _payload_ref(payload, label="attempt_b")
    assert first_attempt != second_attempt
    assert _fingerprint(payload) == fingerprint
    assert _fingerprint(payload).to_ref() == ref

    changed_material = (1).to_bytes(8, "big") + bytes(range(8, 32))
    changed_payload = _payload(changed_material)
    assert changed_payload != payload
    assert _fingerprint(changed_payload) != fingerprint


def test_physical_fingerprint_rejects_cross_challenge_representation() -> None:
    key = _challenge()
    payload = _payload(key=key)
    other_key = _challenge("2.0")

    with pytest.raises(GeneratorValidationError) as caught:
        build_physical_payload_fingerprint(
            challenge_key=key,
            case_representation_ref=_challenge_owner(
                "representation", "wrong_challenge_representation", other_key
            ),
            fixture_configuration_ref=payload.fixture_configuration_ref,
            protected_payload=payload,
        )
    assert caught.value.code == GeneratorInputCode.CROSS_CHALLENGE.value


@pytest.mark.parametrize(
    ("material", "expected_distinct", "expected_zero", "expected_identical"),
    (
        (bytes(range(32)), None, False, False),
        (
            (1000).to_bytes(8, "big") + (1000).to_bytes(8, "big") + bytes(16),
            1,
            True,
            True,
        ),
    ),
)
def test_payload_facts_derive_exact_counts_and_mechanical_degeneracy(
    material: bytes,
    expected_distinct: int | None,
    expected_zero: bool,
    expected_identical: bool,
) -> None:
    payload = _payload(material)
    fingerprint = _fingerprint(payload)
    facts = build_fixture_payload_facts(
        protected_payload=payload,
        protected_payload_ref=_payload_ref(payload, label="attempt_payload"),
        physical_payload_fingerprint=fingerprint,
        physical_payload_fingerprint_ref=fingerprint.to_ref(),
    )

    assert type(facts) is FixturePayloadFacts
    assert tuple(field.name for field in fields(facts)) == (
        "protected_payload_ref",
        "physical_payload_fingerprint",
        "physical_payload_fingerprint_ref",
        "fixture_configuration_ref",
        "spatial_point_count",
        "time_point_count",
        "initial_value_count",
        "degeneracy_facts",
    )
    assert facts.spatial_point_count == 8
    assert facts.time_point_count == 1
    assert facts.initial_value_count == 8
    degeneracy = facts.degeneracy_facts
    assert type(degeneracy) is FixtureDegeneracyFacts
    assert degeneracy.distinct_initial_value_count == (
        len(set(payload.initial_values))
        if expected_distinct is None
        else expected_distinct
    )
    assert degeneracy.all_initial_values_zero is expected_zero
    assert degeneracy.all_initial_values_identical is expected_identical
    assert tuple(field.name for field in fields(degeneracy)) == (
        "distinct_initial_value_count",
        "all_initial_values_zero",
        "all_initial_values_identical",
    )
    assert repr(degeneracy) == "FixtureDegeneracyFacts(<protected>)"
    with pytest.raises(TypeError):
        pickle.dumps(degeneracy)


def test_fixture_fact_builder_rejects_stale_fingerprint() -> None:
    payload = _payload()
    changed_material = (42).to_bytes(8, "big") + bytes(range(8, 32))
    other_fingerprint = _fingerprint(_payload(changed_material))

    with pytest.raises(GeneratorValidationError) as caught:
        build_fixture_payload_facts(
            protected_payload=payload,
            protected_payload_ref=_payload_ref(payload, label="attempt_payload"),
            physical_payload_fingerprint=other_fingerprint,
            physical_payload_fingerprint_ref=other_fingerprint.to_ref(),
        )
    assert caught.value.code == GeneratorInputCode.STALE_BINDING.value

    stale_payload_ref = owner_ref(
        "protected_case_payload",
        scope_binding=ChallengeScope(_challenge()),
        object_id="attempt_payload",
        object_version="1.0",
        content_digest=_digest("not_the_payload"),
    )
    fingerprint = _fingerprint(payload)
    with pytest.raises(GeneratorValidationError) as caught:
        build_fixture_payload_facts(
            protected_payload=payload,
            protected_payload_ref=stale_payload_ref,
            physical_payload_fingerprint=fingerprint,
            physical_payload_fingerprint_ref=fingerprint.to_ref(),
        )
    assert caught.value.code == GeneratorInputCode.STALE_BINDING.value


def test_artifact_and_validated_fact_types_have_only_contract_fields() -> None:
    assert tuple(field.name for field in fields(GeneratedFixtureArtifact)) == (
        "case",
        "case_ref",
        "loaded_case",
        "loaded_dependencies",
        "graph_origin",
    )
    assert tuple(field.name for field in fields(ValidatedCaseFacts)) == (
        "case_ref",
        "representation_ref",
        "physical_payload_ref",
        "primary_population_ref",
        "sampling_plan_ref",
        "graph_origin",
        "origin_evidence_refs",
        "composition_audit_ref",
    )
    assert GraphOriginTag.FIXTURE_DERIVED.value == "FIXTURE_DERIVED"
    with pytest.raises(GeneratorValidationError):
        build_generated_fixture_artifact(  # type: ignore[arg-type]
            case=object(),
            case_ref=object(),
            loaded_case=object(),
            loaded_dependencies=(),
            graph_origin=object(),
        )
