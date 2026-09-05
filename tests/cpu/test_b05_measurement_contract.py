from __future__ import annotations

from dataclasses import replace

import pytest

from carbon import measurement
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.registry import ChallengeKey

_DIGEST_A = "sha256:" + "a" * 64
_DIGEST_B = "sha256:" + "b" * 64
_CLAIMS = set(measurement.MeasurementClaimClass)


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


def evidence_item(
    role: measurement.MeasurementEvidenceRole = (
        measurement.MeasurementEvidenceRole.ANALYTIC_OR_MANUFACTURED_VERIFICATION
    ),
    supported: set[measurement.MeasurementClaimClass] | None = None,
    *,
    evidence_id: str = "mms-verification",
    fixture_origin: bool = True,
) -> measurement.MeasurementEvidenceItem:
    supported_claims = supported or {
        measurement.MeasurementClaimClass.IMPLEMENTATION_CORRECTNESS
    }
    return measurement.MeasurementEvidenceItem(
        evidence_id,
        definition(measurement.MeasurementDefinitionKind.EVIDENCE_SOURCE, "mms-source"),
        role,
        tuple(supported_claims),
        tuple(_CLAIMS - supported_claims),
        (
            definition(
                measurement.MeasurementDefinitionKind.CASE_SCOPE, "manufactured-case"
            ),
        ),
        (definition(measurement.MeasurementDefinitionKind.STRATUM, "fixture-stratum"),),
        fixture_origin,
    )


def contract(*, fixture_origin: bool = True) -> measurement.MeasurementContract:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    return measurement.MeasurementContract(
        challenge,
        "fixture-residual",
        "1.0",
        definition(
            measurement.MeasurementDefinitionKind.SCIENTIFIC_PROPERTY,
            "residual-property",
        ),
        (
            definition(
                measurement.MeasurementDefinitionKind.OBSERVABLE,
                "solution-u",
                digest=_DIGEST_B,
            ),
            definition(measurement.MeasurementDefinitionKind.OBSERVABLE, "forcing-f"),
        ),
        definition(
            measurement.MeasurementDefinitionKind.COORDINATE_SYSTEM, "space-time"
        ),
        definition(measurement.MeasurementDefinitionKind.UNIT, "synthetic-unit"),
        definition(
            measurement.MeasurementDefinitionKind.NUMERICAL_OPERATOR,
            "fixture-residual-op",
        ),
        definition(
            measurement.MeasurementDefinitionKind.DISCRETIZATION, "fixture-grid"
        ),
        definition(
            measurement.MeasurementDefinitionKind.SAMPLING_QUADRATURE,
            "fixture-quadrature",
        ),
        definition(
            measurement.MeasurementDefinitionKind.NORMALIZATION, "fixture-normalization"
        ),
        definition(
            measurement.MeasurementDefinitionKind.AGGREGATION, "fixture-aggregation"
        ),
        definition(measurement.MeasurementDefinitionKind.PRECISION, "binary64-fixture"),
        ReferencePolicyRef(challenge, _DIGEST_B),
        measurement.ScientificValueBinding(
            measurement.ScientificValueState.HUMAN_INPUT
        ),
        definition(
            measurement.MeasurementDefinitionKind.APPLICABILITY_POLICY,
            "fixture-applicability",
        ),
        measurement.UncertaintyPolicyBinding(
            measurement.ScientificValueState.HUMAN_INPUT
        ),
        (
            measurement.StratumApplicabilityBinding(
                definition(
                    measurement.MeasurementDefinitionKind.STRATUM, "fixture-stratum"
                ),
                measurement.StratumApplicabilityStatus.HUMAN_INPUT,
            ),
        ),
        (
            definition(
                measurement.MeasurementDefinitionKind.KNOWN_LIMITATION, "fixture-only"
            ),
        ),
        (
            definition(
                measurement.MeasurementDefinitionKind.IMPLEMENTATION, "fixture-python"
            ),
        ),
        measurement.MeasurementRole.MANDATORY,
        fixture_origin,
    )


def qualification(
    *, fixture_origin: bool = True
) -> measurement.MeasurementQualificationEvidence:
    value = contract(fixture_origin=fixture_origin)
    return measurement.MeasurementQualificationEvidence(
        value.challenge_key,
        "fixture-residual-evidence",
        "1.0",
        measurement.measurement_ref(value),
        (evidence_item(fixture_origin=fixture_origin),),
        fixture_origin,
    )


def test_measurement_contract_canonical_round_trip_and_pin_are_exact() -> None:
    value = contract()
    source = measurement.canonical_bytes(value)
    loaded = measurement.load_canonical_document(source)

    assert loaded == value
    assert measurement.canonical_bytes(loaded) == source
    assert measurement.measurement_ref(loaded) == measurement.measurement_ref(value)
    assert measurement.canonical_digest(value).startswith("sha256:")
    assert source.startswith(measurement.MEASUREMENT_DOCUMENT_HEADER)
    assert len(source) == 6730
    assert measurement.canonical_digest(value) == (
        "sha256:4eaee7e1853fe6912fe604acef5c0994f38f28254f32f29747e3929d7aaf9577"
    )


def test_qualification_canonical_round_trip_and_fixture_store() -> None:
    value = qualification()
    store = measurement.MeasurementFixtureStore()

    ref = store.put(value)

    assert len(store) == 1
    assert store.get(ref) == value
    assert (
        measurement.load_canonical_document(measurement.canonical_bytes(value)) == value
    )
    assert len(measurement.canonical_bytes(value)) == 2186
    assert measurement.canonical_digest(value) == (
        "sha256:5a8ee6bda97d136c2210476908db9f8ce4d5e73b9abfc303e468a8c767af9d79"
    )


def test_set_like_refs_and_items_have_stable_canonical_order() -> None:
    value = contract()
    reordered = replace(
        value,
        observable_refs=tuple(reversed(value.observable_refs)),
    )
    assert reordered == value
    assert measurement.canonical_bytes(reordered) == measurement.canonical_bytes(value)

    item_b = replace(evidence_item(), evidence_id="second-evidence")
    qualification_a = replace(qualification(), evidence_items=(item_b, evidence_item()))
    qualification_b = replace(qualification(), evidence_items=(evidence_item(), item_b))
    assert measurement.canonical_bytes(qualification_a) == measurement.canonical_bytes(
        qualification_b
    )


@pytest.mark.parametrize(
    "claim",
    [
        measurement.MeasurementClaimClass.PHYSICAL_MODEL_VALIDITY,
        measurement.MeasurementClaimClass.TARGET_WORKLOAD_APPLICABILITY,
        measurement.MeasurementClaimClass.ENGINEERING_CONTEXT_OF_USE,
    ],
)
def test_mms_verification_cannot_support_validation_or_context_claims(claim) -> None:
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        evidence_item(supported={claim})
    assert (
        exc_info.value.code is measurement.MeasurementInputCode.CLAIM_MATRIX_VIOLATION
    )


@pytest.mark.parametrize(
    ("role", "allowed"),
    list(measurement.MEASUREMENT_EVIDENCE_ROLE_CLAIMS.items()),
)
def test_each_evidence_role_accepts_only_its_closed_claim_set(role, allowed) -> None:
    selected = {next(iter(allowed))}
    assert evidence_item(role, selected).supported_claims == tuple(
        sorted(selected, key=lambda item: item.value)
    )
    forbidden = _CLAIMS - allowed
    if forbidden:
        with pytest.raises(measurement.MeasurementValidationError):
            evidence_item(role, {next(iter(forbidden))})


def test_supported_and_unsupported_claims_must_be_complete_and_disjoint() -> None:
    item = evidence_item()
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(item, unsupported_claims=())
    assert exc_info.value.code is measurement.MeasurementInputCode.WRONG_TYPE

    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            item,
            unsupported_claims=(
                measurement.MeasurementClaimClass.IMPLEMENTATION_CORRECTNESS,
            ),
        )
    assert (
        exc_info.value.code is measurement.MeasurementInputCode.CLAIM_MATRIX_VIOLATION
    )


def test_floor_is_explicit_and_not_applicable_is_forbidden() -> None:
    assert (
        contract().numerical_floor_binding.state
        is measurement.ScientificValueState.HUMAN_INPUT
    )
    reason = definition(
        measurement.MeasurementDefinitionKind.APPLICABILITY_REASON, "no-floor-reason"
    )
    with pytest.raises(measurement.MeasurementValidationError):
        replace(
            contract(),
            numerical_floor_binding=measurement.ScientificValueBinding(
                measurement.ScientificValueState.NOT_APPLICABLE, reason
            ),
        )


def test_bound_floor_requires_a_scientific_value_ref() -> None:
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.ScientificValueBinding(
            measurement.ScientificValueState.BOUND,
            definition(measurement.MeasurementDefinitionKind.UNIT, "wrong-kind"),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION


@pytest.mark.parametrize(
    ("status", "detail_kind"),
    [
        (
            measurement.StratumApplicabilityStatus.APPLICABLE,
            measurement.MeasurementDefinitionKind.APPLICABILITY_EVIDENCE,
        ),
        (
            measurement.StratumApplicabilityStatus.NOT_APPLICABLE,
            measurement.MeasurementDefinitionKind.APPLICABILITY_REASON,
        ),
    ],
)
def test_stratum_applicability_requires_status_specific_evidence(
    status, detail_kind
) -> None:
    binding = measurement.StratumApplicabilityBinding(
        definition(measurement.MeasurementDefinitionKind.STRATUM, "fixture-stratum"),
        status,
        definition(detail_kind, "fixture-detail"),
    )
    assert binding.status is status

    with pytest.raises(measurement.MeasurementValidationError):
        replace(binding, evidence_or_reason_ref=None)


def test_human_input_stratum_cannot_carry_evidence() -> None:
    with pytest.raises(measurement.MeasurementValidationError):
        measurement.StratumApplicabilityBinding(
            definition(
                measurement.MeasurementDefinitionKind.STRATUM, "fixture-stratum"
            ),
            measurement.StratumApplicabilityStatus.HUMAN_INPUT,
            definition(
                measurement.MeasurementDefinitionKind.APPLICABILITY_EVIDENCE,
                "premature-evidence",
            ),
        )


def test_duplicate_strata_and_cross_challenge_refs_reject() -> None:
    value = contract()
    duplicate = value.stratum_applicability[0]
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(value, stratum_applicability=(duplicate, duplicate))
    assert exc_info.value.code is measurement.MeasurementInputCode.DUPLICATE_IDENTITY

    other = ChallengeKey("other-fixture", "1.0")
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            value,
            unit_ref=definition(
                measurement.MeasurementDefinitionKind.UNIT, "unit", challenge=other
            ),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.CROSS_CHALLENGE


def test_definition_kind_confusion_rejects() -> None:
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            contract(),
            unit_ref=definition(
                measurement.MeasurementDefinitionKind.OBSERVABLE, "not-a-unit"
            ),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION


def test_nonfixture_evidence_cannot_contain_fixture_item() -> None:
    value = qualification()
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(value, fixture_origin=False)
    assert exc_info.value.code is measurement.MeasurementInputCode.FIXTURE_REQUIRED


def test_fixture_store_rejects_nonfixture_records_and_unknown_refs() -> None:
    store = measurement.MeasurementFixtureStore()
    with pytest.raises(measurement.MeasurementStoreError) as exc_info:
        store.put(contract(fixture_origin=False))
    assert exc_info.value.code is measurement.MeasurementInputCode.FIXTURE_REQUIRED

    with pytest.raises(measurement.MeasurementStoreError) as exc_info:
        store.get(measurement.measurement_ref(contract()))
    assert exc_info.value.code is measurement.MeasurementInputCode.UNKNOWN_OBJECT


def test_canonical_loader_rejects_noncanonical_and_duplicate_json() -> None:
    source = measurement.canonical_bytes(contract())
    with pytest.raises(measurement.MeasurementCanonicalError):
        measurement.load_canonical_document(source + b" ")

    duplicate = (
        measurement.MEASUREMENT_DOCUMENT_HEADER
        + b'{"record_type":"measurement_contract","record_type":"measurement_contract"}'
    )
    with pytest.raises(measurement.MeasurementCanonicalError) as exc_info:
        measurement.load_canonical_document(duplicate)
    assert exc_info.value.code is measurement.MeasurementInputCode.DUPLICATE_IDENTITY


def test_canonical_loader_rejects_wrong_source_type_and_header() -> None:
    with pytest.raises(measurement.MeasurementCanonicalError) as exc_info:
        measurement.load_canonical_document("not-bytes")
    assert exc_info.value.code is measurement.MeasurementInputCode.WRONG_TYPE
    with pytest.raises(measurement.MeasurementCanonicalError):
        measurement.load_canonical_document(b"{}")


def test_measurement_root_is_an_exact_closed_allow_list() -> None:
    expected = tuple(sorted(measurement.__all__))
    assert len(expected) == len(set(expected))
    assert measurement.__all__ == expected
    assert "ScoreInput" not in measurement.__all__
    assert "ScoreEngine" not in measurement.__all__
