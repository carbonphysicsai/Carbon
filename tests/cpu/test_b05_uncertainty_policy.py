from __future__ import annotations

import json
from dataclasses import replace

import pytest

from carbon import measurement
from carbon.registry import ChallengeKey

_DIGEST_A = "sha256:" + "a" * 64
_DIGEST_B = "sha256:" + "b" * 64

_COMPONENT_FIELDS = {
    "estimand_binding": measurement.MeasurementDefinitionKind.ESTIMAND,
    "measurement_output_binding": (
        measurement.MeasurementDefinitionKind.MEASUREMENT_OUTPUT
    ),
    "sampling_unit_binding": measurement.MeasurementDefinitionKind.SAMPLING_UNIT,
    "resampling_unit_binding": measurement.MeasurementDefinitionKind.RESAMPLING_UNIT,
    "independence_unit_binding": (
        measurement.MeasurementDefinitionKind.INDEPENDENCE_UNIT
    ),
    "common_case_pairing_binding": (
        measurement.MeasurementDefinitionKind.COMMON_CASE_PAIRING
    ),
    "reconstruction_case_interaction_binding": (
        measurement.MeasurementDefinitionKind.RECONSTRUCTION_CASE_INTERACTION
    ),
    "reconstruction_stratum_interaction_binding": (
        measurement.MeasurementDefinitionKind.RECONSTRUCTION_STRATUM_INTERACTION
    ),
    "joint_reference_uncertainty_binding": (
        measurement.MeasurementDefinitionKind.JOINT_REFERENCE_UNCERTAINTY
    ),
    "reference_candidate_covariance_binding": (
        measurement.MeasurementDefinitionKind.REFERENCE_CANDIDATE_COVARIANCE
    ),
    "representation_dependence_binding": (
        measurement.MeasurementDefinitionKind.REPRESENTATION_DEPENDENCE
    ),
    "execution_dependence_binding": (
        measurement.MeasurementDefinitionKind.EXECUTION_DEPENDENCE
    ),
    "censoring_accounting_binding": (
        measurement.MeasurementDefinitionKind.CENSORING_ACCOUNTING
    ),
    "minimum_evidence_binding": (
        measurement.MeasurementDefinitionKind.EVIDENCE_MINIMUM
    ),
    "stopping_rule_binding": measurement.MeasurementDefinitionKind.STOPPING_RULE,
    "evidence_extension_rule_binding": (
        measurement.MeasurementDefinitionKind.EVIDENCE_EXTENSION_RULE
    ),
    "interval_error_control_binding": (
        measurement.MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL
    ),
    "multiplicity_policy_binding": (
        measurement.MeasurementDefinitionKind.MULTIPLICITY_POLICY
    ),
}


def definition(
    kind: measurement.MeasurementDefinitionKind,
    object_id: str,
    *,
    challenge: ChallengeKey | None = None,
    digest: str = _DIGEST_A,
) -> measurement.MeasurementDefinitionRef:
    return measurement.MeasurementDefinitionRef(
        challenge or ChallengeKey("fixture-burgers", "1.0"),
        kind,
        object_id,
        "1.0",
        digest,
    )


def unresolved() -> measurement.UncertaintyComponentBinding:
    return measurement.UncertaintyComponentBinding(
        measurement.ScientificValueState.HUMAN_INPUT
    )


def shortcut(
    *,
    shortcut_id: str = "fixture-paired-quadrature",
    fixture_origin: bool = True,
    challenge: ChallengeKey | None = None,
) -> measurement.DependenceShortcutBinding:
    challenge = challenge or ChallengeKey("fixture-burgers", "1.0")
    return measurement.DependenceShortcutBinding(
        shortcut_id,
        "1.0",
        measurement.DependenceShortcutKind.QUADRATURE,
        definition(
            measurement.MeasurementDefinitionKind.EVIDENCE_SET,
            "fixture-incumbent-evidence",
            challenge=challenge,
        ),
        definition(
            measurement.MeasurementDefinitionKind.EVIDENCE_SET,
            "fixture-challenger-evidence",
            challenge=challenge,
            digest=_DIGEST_B,
        ),
        (
            definition(
                measurement.MeasurementDefinitionKind.CASE_SCOPE,
                "fixture-case",
                challenge=challenge,
            ),
        ),
        (
            definition(
                measurement.MeasurementDefinitionKind.STRATUM,
                "fixture-stratum",
                challenge=challenge,
            ),
        ),
        definition(
            measurement.MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION,
            "fixture-covariance-assumption",
            challenge=challenge,
        ),
        definition(
            measurement.MeasurementDefinitionKind.APPLICABILITY_TEST,
            "fixture-applicability-test",
            challenge=challenge,
        ),
        definition(
            measurement.MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
            "fixture-b06-dossier-qualification",
            challenge=challenge,
        ),
        fixture_origin,
    )


def policy(
    *,
    fixture_origin: bool = True,
    shortcuts: tuple[measurement.DependenceShortcutBinding, ...] = (),
) -> measurement.UncertaintyPolicy:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    return measurement.UncertaintyPolicy(
        challenge_key=challenge,
        policy_id="fixture-uncertainty",
        policy_version="1.0",
        **{name: unresolved() for name in _COMPONENT_FIELDS},
        stratum_minimum_bindings=(
            measurement.StratumEvidenceMinimumBinding(
                definition(
                    measurement.MeasurementDefinitionKind.STRATUM,
                    "fixture-stratum",
                ),
                unresolved(),
            ),
        ),
        dependence_shortcuts=shortcuts,
        fixture_origin=fixture_origin,
    )


def test_uncertainty_policy_canonical_round_trip_and_pin_are_exact() -> None:
    value = policy()
    source = measurement.canonical_bytes(value)
    loaded = measurement.load_canonical_document(source)

    assert loaded == value
    assert measurement.canonical_bytes(loaded) == source
    assert measurement.measurement_ref(value) == measurement.UncertaintyPolicyRef(
        value.challenge_key, measurement.canonical_digest(value)
    )
    assert len(source) == 2175
    assert measurement.canonical_digest(value) == (
        "sha256:77b76335e5be7256f055675ab1917eddd357d21353ae754fdef61e0d9e90b9d9"
    )
    assert b'"measurement_contract_ref"' not in source
    assert value.schema_version == measurement.MEASUREMENT_SCHEMA_VERSION == "1.0"


def test_every_scientific_component_remains_explicitly_human_owned() -> None:
    value = policy()
    assert value.dependence_shortcuts == ()
    assert all(
        getattr(value, name).state is measurement.ScientificValueState.HUMAN_INPUT
        for name in _COMPONENT_FIELDS
    )
    assert all(
        item.minimum_binding.state is measurement.ScientificValueState.HUMAN_INPUT
        for item in value.stratum_minimum_bindings
    )


@pytest.mark.parametrize(("field_name", "expected_kind"), _COMPONENT_FIELDS.items())
def test_each_component_accepts_only_its_exact_definition_kind(
    field_name, expected_kind
) -> None:
    value = policy()
    bound = measurement.UncertaintyComponentBinding(
        measurement.ScientificValueState.BOUND,
        definition(expected_kind, f"fixture-{expected_kind.value.casefold()}"),
    )
    assert getattr(replace(value, **{field_name: bound}), field_name) == bound

    wrong = measurement.UncertaintyComponentBinding(
        measurement.ScientificValueState.BOUND,
        definition(measurement.MeasurementDefinitionKind.UNIT, "wrong-role"),
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(value, **{field_name: wrong})
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION


def test_not_applicable_component_requires_an_exact_reason() -> None:
    reason = definition(
        measurement.MeasurementDefinitionKind.APPLICABILITY_REASON,
        "fixture-not-applicable-reason",
    )
    binding = measurement.UncertaintyComponentBinding(
        measurement.ScientificValueState.NOT_APPLICABLE, reason
    )
    assert replace(policy(), execution_dependence_binding=binding)

    with pytest.raises(measurement.MeasurementValidationError):
        measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.NOT_APPLICABLE,
            definition(measurement.MeasurementDefinitionKind.UNIT, "not-a-reason"),
        )


def test_cross_challenge_component_refs_reject() -> None:
    other = ChallengeKey("other-fixture", "1.0")
    binding = measurement.UncertaintyComponentBinding(
        measurement.ScientificValueState.BOUND,
        definition(
            measurement.MeasurementDefinitionKind.ESTIMAND,
            "other-estimand",
            challenge=other,
        ),
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(policy(), estimand_binding=binding)
    assert exc_info.value.code is measurement.MeasurementInputCode.CROSS_CHALLENGE


def test_stratum_minima_are_explicit_sorted_and_unique() -> None:
    value = policy()
    first = value.stratum_minimum_bindings[0]
    second = measurement.StratumEvidenceMinimumBinding(
        definition(measurement.MeasurementDefinitionKind.STRATUM, "another-stratum"),
        measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.BOUND,
            definition(
                measurement.MeasurementDefinitionKind.STRATUM_EVIDENCE_MINIMUM,
                "fixture-minimum",
            ),
        ),
    )
    forward = replace(value, stratum_minimum_bindings=(first, second))
    reverse = replace(value, stratum_minimum_bindings=(second, first))
    assert forward == reverse
    assert measurement.canonical_bytes(forward) == measurement.canonical_bytes(reverse)

    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(value, stratum_minimum_bindings=(first, first))
    assert exc_info.value.code is measurement.MeasurementInputCode.DUPLICATE_IDENTITY


def test_stratum_minimum_bound_value_has_a_distinct_role() -> None:
    wrong = measurement.StratumEvidenceMinimumBinding(
        definition(measurement.MeasurementDefinitionKind.STRATUM, "fixture-stratum"),
        measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.BOUND,
            definition(measurement.MeasurementDefinitionKind.EVIDENCE_MINIMUM, "wrong"),
        ),
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(policy(), stratum_minimum_bindings=(wrong,))
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION


def test_shortcut_binds_exact_evidence_scope_assumption_test_and_dossier() -> None:
    value = policy(shortcuts=(shortcut(),))
    loaded = measurement.load_canonical_document(measurement.canonical_bytes(value))
    item = loaded.dependence_shortcuts[0]

    assert item.shortcut_kind is measurement.DependenceShortcutKind.QUADRATURE
    assert item.incumbent_evidence_ref != item.challenger_evidence_ref
    assert item.case_scope_refs
    assert item.stratum_scope_refs
    assert (
        item.dossier_qualification_ref.definition_kind
        is measurement.MeasurementDefinitionKind.DOSSIER_QUALIFICATION
    )
    assert len(measurement.canonical_bytes(value)) == 5128
    assert measurement.canonical_digest(value) == (
        "sha256:af0d5ac207169434715f0793c09cdeb66b88cf9a9a127b7a5fc188908dddf476"
    )


def test_shortcut_requires_distinct_incumbent_and_challenger_evidence() -> None:
    value = shortcut()
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(value, challenger_evidence_ref=value.incumbent_evidence_ref)
    assert exc_info.value.code is measurement.MeasurementInputCode.DUPLICATE_IDENTITY


def test_shortcut_rejects_cross_challenge_or_wrong_role() -> None:
    value = shortcut()
    other = ChallengeKey("other-fixture", "1.0")
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            value,
            assumption_ref=definition(
                measurement.MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION,
                "other-assumption",
                challenge=other,
            ),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.CROSS_CHALLENGE

    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            value,
            dossier_qualification_ref=definition(
                measurement.MeasurementDefinitionKind.APPLICABILITY_TEST,
                "not-a-dossier",
            ),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION


def test_shortcuts_are_sorted_unique_and_never_inferred() -> None:
    first = shortcut(shortcut_id="a-shortcut")
    second = shortcut(shortcut_id="b-shortcut")
    forward = policy(shortcuts=(first, second))
    reverse = policy(shortcuts=(second, first))
    assert forward == reverse
    assert measurement.canonical_bytes(forward) == measurement.canonical_bytes(reverse)

    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        policy(shortcuts=(first, first))
    assert exc_info.value.code is measurement.MeasurementInputCode.DUPLICATE_IDENTITY


def test_nonfixture_policy_cannot_embed_a_fixture_shortcut() -> None:
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        policy(fixture_origin=False, shortcuts=(shortcut(),))
    assert exc_info.value.code is measurement.MeasurementInputCode.FIXTURE_REQUIRED


def test_fixture_store_accepts_uncertainty_policy_and_checks_digest() -> None:
    value = policy(shortcuts=(shortcut(),))
    store = measurement.MeasurementFixtureStore()
    ref = store.put(value)
    assert store.get(ref) == value
    assert type(ref) is measurement.UncertaintyPolicyRef


def test_uncertainty_policy_loader_rejects_missing_or_unknown_fields() -> None:
    source = measurement.canonical_bytes(policy())
    payload = json.loads(source[len(measurement.MEASUREMENT_DOCUMENT_HEADER) :])
    del payload["independence_unit_binding"]
    malformed = (
        measurement.MEASUREMENT_DOCUMENT_HEADER
        + json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    with pytest.raises(measurement.MeasurementCanonicalError):
        measurement.load_canonical_document(malformed)

    payload = json.loads(source[len(measurement.MEASUREMENT_DOCUMENT_HEADER) :])
    payload["measurement_contract_ref"] = {
        "canonicalization_profile": "carbon_measurement_canonical_v1",
        "challenge_key": {"challenge_id": "fixture-burgers", "version": "1.0"},
        "content_digest": _DIGEST_B,
        "ref_type": "measurement_contract_ref",
        "schema_version": "1.0",
    }
    obsolete_cycle_payload = (
        measurement.MEASUREMENT_DOCUMENT_HEADER
        + json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    with pytest.raises(measurement.MeasurementCanonicalError):
        measurement.load_canonical_document(obsolete_cycle_payload)


def test_uncertainty_public_surface_is_closed_and_has_no_a5_engine() -> None:
    assert "UncertaintyPolicy" in measurement.__all__
    assert "DependenceShortcutBinding" in measurement.__all__
    assert "ScoreInput" not in measurement.__all__
    assert "ScoreEngine" not in measurement.__all__
