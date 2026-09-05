from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from carbon import measurement
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.registry import ChallengeKey
from carbon.resource_policy import (
    NoBuildStarted,
    NoReuse,
    ReplicateNotApplicable,
    ReplicateNotApplicableReason,
    ResourceStopCause,
)
from carbon.scoring.model import ScorePackPin
from carbon.scoring.pack import load_score_pack

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = Path("tests/fixtures/score_packs/a5_fixture_v1.json")
PACK_DIGEST = "sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57"
GENERATOR_DIGEST = "sha256:" + "1" * 64
KEY = ChallengeKey("a5_fixture", "fixture-1.0")
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64

EXPECTED = (
    (
        "gate_error",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.MANDATORY_GATE,
        measurement.ScoreAggregationRole.MANDATORY_ADMISSIBILITY,
        measurement.ScoreRankingRole.ADMISSIBILITY_ONLY,
        measurement.A5DestinationKind.MANDATORY_GATE,
        "synthetic_error_gate",
    ),
    (
        "finite_ok",
        measurement.ScoreScalarKind.BOOLEAN,
        measurement.ScoreUseRole.MANDATORY_GATE,
        measurement.ScoreAggregationRole.MANDATORY_ADMISSIBILITY,
        measurement.ScoreRankingRole.ADMISSIBILITY_ONLY,
        measurement.A5DestinationKind.MANDATORY_GATE,
        "synthetic_finite_gate",
    ),
    (
        "diagnostic_error",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.DIAGNOSTIC,
        measurement.ScoreAggregationRole.NONE,
        measurement.ScoreRankingRole.NON_RANKING_DIAGNOSTIC,
        measurement.A5DestinationKind.DIAGNOSTIC_GATE,
        "synthetic_optional_diagnostic",
    ),
    (
        "physics_error",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreAggregationRole.PHYSICS,
        measurement.ScoreRankingRole.RANKING_INPUT,
        measurement.A5DestinationKind.PHYSICS_COMPONENT,
        "synthetic_residual",
    ),
    (
        "robust_mean_a",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreAggregationRole.ROBUSTNESS_MEAN,
        measurement.ScoreRankingRole.RANKING_INPUT,
        measurement.A5DestinationKind.ROBUSTNESS_MEAN,
        "synthetic_category_a",
    ),
    (
        "robust_tail_a",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreAggregationRole.ROBUSTNESS_TAIL,
        measurement.ScoreRankingRole.RANKING_INPUT,
        measurement.A5DestinationKind.ROBUSTNESS_TAIL,
        "synthetic_category_a",
    ),
    (
        "robust_mean_b",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreAggregationRole.ROBUSTNESS_MEAN,
        measurement.ScoreRankingRole.RANKING_INPUT,
        measurement.A5DestinationKind.ROBUSTNESS_MEAN,
        "synthetic_category_b",
    ),
    (
        "robust_tail_b",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreAggregationRole.ROBUSTNESS_TAIL,
        measurement.ScoreRankingRole.RANKING_INPUT,
        measurement.A5DestinationKind.ROBUSTNESS_TAIL,
        "synthetic_category_b",
    ),
    (
        "accuracy_error_a",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreAggregationRole.ACCURACY,
        measurement.ScoreRankingRole.RANKING_INPUT,
        measurement.A5DestinationKind.ACCURACY_COMPONENT,
        "synthetic_accuracy_a",
    ),
    (
        "accuracy_error_b",
        measurement.ScoreScalarKind.NUMERIC,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreAggregationRole.ACCURACY,
        measurement.ScoreRankingRole.RANKING_INPUT,
        measurement.A5DestinationKind.ACCURACY_COMPONENT,
        "synthetic_accuracy_b",
    ),
)

UNCERTAINTY_KINDS = {
    "sampling_unit_binding": measurement.MeasurementDefinitionKind.SAMPLING_UNIT,
    "resampling_unit_binding": measurement.MeasurementDefinitionKind.RESAMPLING_UNIT,
    "independence_unit_binding": measurement.MeasurementDefinitionKind.INDEPENDENCE_UNIT,
    "common_case_pairing_binding": measurement.MeasurementDefinitionKind.COMMON_CASE_PAIRING,
    "reconstruction_case_interaction_binding": measurement.MeasurementDefinitionKind.RECONSTRUCTION_CASE_INTERACTION,
    "reconstruction_stratum_interaction_binding": measurement.MeasurementDefinitionKind.RECONSTRUCTION_STRATUM_INTERACTION,
    "joint_reference_uncertainty_binding": measurement.MeasurementDefinitionKind.JOINT_REFERENCE_UNCERTAINTY,
    "reference_candidate_covariance_binding": measurement.MeasurementDefinitionKind.REFERENCE_CANDIDATE_COVARIANCE,
    "representation_dependence_binding": measurement.MeasurementDefinitionKind.REPRESENTATION_DEPENDENCE,
    "execution_dependence_binding": measurement.MeasurementDefinitionKind.EXECUTION_DEPENDENCE,
    "censoring_accounting_binding": measurement.MeasurementDefinitionKind.CENSORING_ACCOUNTING,
    "minimum_evidence_binding": measurement.MeasurementDefinitionKind.EVIDENCE_MINIMUM,
    "stopping_rule_binding": measurement.MeasurementDefinitionKind.STOPPING_RULE,
    "evidence_extension_rule_binding": measurement.MeasurementDefinitionKind.EVIDENCE_EXTENSION_RULE,
    "interval_error_control_binding": measurement.MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL,
    "multiplicity_policy_binding": measurement.MeasurementDefinitionKind.MULTIPLICITY_POLICY,
}

RECONSTRUCTION_KINDS = {
    "complete_base_minimum_binding": measurement.MeasurementDefinitionKind.COMPLETE_BASE_MINIMUM,
    "build_completeness_criteria_binding": measurement.MeasurementDefinitionKind.BUILD_COMPLETENESS_CRITERIA,
    "frozen_artifact_reuse_policy_binding": measurement.MeasurementDefinitionKind.FROZEN_ARTIFACT_REUSE_POLICY,
    "nomination_criteria_binding": measurement.MeasurementDefinitionKind.NOMINATION_CRITERIA,
    "promotion_criteria_binding": measurement.MeasurementDefinitionKind.PROMOTION_CRITERIA,
    "case_coverage_requirement_binding": measurement.MeasurementDefinitionKind.CASE_COVERAGE_REQUIREMENT,
    "stratum_coverage_requirement_binding": measurement.MeasurementDefinitionKind.STRATUM_COVERAGE_REQUIREMENT,
    "evidence_extension_rule_binding": measurement.MeasurementDefinitionKind.EVIDENCE_EXTENSION_RULE,
    "scientific_stopping_rule_binding": measurement.MeasurementDefinitionKind.STOPPING_RULE,
    "stability_audit_rate_binding": measurement.MeasurementDefinitionKind.STABILITY_AUDIT_RATE,
    "audit_selection_policy_binding": measurement.MeasurementDefinitionKind.AUDIT_SELECTION_POLICY,
    "error_control_binding": measurement.MeasurementDefinitionKind.INTERVAL_ERROR_CONTROL,
    "power_requirement_binding": measurement.MeasurementDefinitionKind.POWER_REQUIREMENT,
    "minimum_resolvable_improvement_binding": measurement.MeasurementDefinitionKind.MINIMUM_RESOLVABLE_IMPROVEMENT,
    "sequential_stopping_rule_binding": measurement.MeasurementDefinitionKind.SEQUENTIAL_STOPPING_RULE,
}


@dataclass(frozen=True, slots=True)
class SyntheticB05AuthoringGraph:
    """One test-owned graph; it is not a production authoring constructor."""

    measurements: tuple[measurement.MeasurementContract, ...]
    qualification_evidence: tuple[measurement.MeasurementQualificationEvidence, ...]
    uncertainty_policies: tuple[measurement.UncertaintyPolicy, ...]
    reconstruction_policy: measurement.ReconstructionEvidencePolicy
    reconstruction_status: measurement.ReconstructionEvidenceStatus
    score_pack_authoring: measurement.ScorePackAuthoringContract
    score_pack_projection: measurement.ScorePackProjection


def definition(kind: measurement.MeasurementDefinitionKind, object_id: str):
    return measurement.MeasurementDefinitionRef(KEY, kind, object_id, "1.0", DIGEST_A)


def pin() -> ScorePackPin:
    return ScorePackPin(
        KEY,
        "fixture-1.0",
        PACK_DIGEST,
        "fixture-1.0",
        GENERATOR_DIGEST,
        "1.0",
        "python_binary64_v1",
        True,
    )


def pack():
    return load_score_pack(REPOSITORY_ROOT, str(PACK_PATH), pin())


def bound(kind: measurement.MeasurementDefinitionKind, object_id: str):
    return measurement.UncertaintyComponentBinding(
        measurement.ScientificValueState.BOUND, definition(kind, object_id)
    )


def measurement_contract(
    input_key: str,
    role: measurement.MeasurementRole,
    uncertainty_policy_ref: measurement.UncertaintyPolicyRef,
):
    return measurement.MeasurementContract(
        challenge_key=KEY,
        measurement_id=f"fixture-measurement-{input_key}",
        measurement_version="1.0",
        scientific_property_ref=definition(
            measurement.MeasurementDefinitionKind.SCIENTIFIC_PROPERTY,
            f"fixture-property-{input_key}",
        ),
        observable_refs=(
            definition(
                measurement.MeasurementDefinitionKind.OBSERVABLE,
                f"fixture-observable-{input_key}",
            ),
        ),
        coordinate_system_ref=definition(
            measurement.MeasurementDefinitionKind.COORDINATE_SYSTEM,
            "fixture-coordinates",
        ),
        unit_ref=definition(measurement.MeasurementDefinitionKind.UNIT, "fixture-unit"),
        numerical_operator_ref=definition(
            measurement.MeasurementDefinitionKind.NUMERICAL_OPERATOR,
            "fixture-operator",
        ),
        discretization_ref=definition(
            measurement.MeasurementDefinitionKind.DISCRETIZATION,
            "fixture-discretization",
        ),
        sampling_quadrature_ref=definition(
            measurement.MeasurementDefinitionKind.SAMPLING_QUADRATURE,
            "fixture-quadrature",
        ),
        normalization_ref=definition(
            measurement.MeasurementDefinitionKind.NORMALIZATION,
            "fixture-normalization",
        ),
        aggregation_ref=definition(
            measurement.MeasurementDefinitionKind.AGGREGATION,
            "fixture-measurement-aggregation",
        ),
        precision_ref=definition(
            measurement.MeasurementDefinitionKind.PRECISION, "fixture-binary64"
        ),
        reference_policy_ref=ReferencePolicyRef(KEY, DIGEST_B),
        numerical_floor_binding=measurement.ScientificValueBinding(
            measurement.ScientificValueState.BOUND,
            definition(
                measurement.MeasurementDefinitionKind.SCIENTIFIC_VALUE,
                f"fixture-synthetic-numerical-floor-{input_key}",
            ),
        ),
        applicability_policy_ref=definition(
            measurement.MeasurementDefinitionKind.APPLICABILITY_POLICY,
            "fixture-applicability-policy",
        ),
        uncertainty_policy_binding=measurement.UncertaintyPolicyBinding(
            measurement.ScientificValueState.BOUND,
            uncertainty_policy_ref,
        ),
        stratum_applicability=(
            measurement.StratumApplicabilityBinding(
                definition(
                    measurement.MeasurementDefinitionKind.STRATUM,
                    "fixture-stratum",
                ),
                measurement.StratumApplicabilityStatus.APPLICABLE,
                definition(
                    measurement.MeasurementDefinitionKind.APPLICABILITY_EVIDENCE,
                    "fixture-applicability-evidence",
                ),
            ),
        ),
        known_limitation_refs=(),
        implementation_refs=(
            definition(
                measurement.MeasurementDefinitionKind.IMPLEMENTATION,
                "fixture-implementation",
            ),
        ),
        intended_role=role,
        fixture_origin=True,
    )


def uncertainty_policy(input_key: str) -> measurement.UncertaintyPolicy:
    components = {
        name: bound(kind, f"fixture-{kind.value.casefold().replace('_', '-')}")
        for name, kind in UNCERTAINTY_KINDS.items()
    }
    return measurement.UncertaintyPolicy(
        challenge_key=KEY,
        policy_id=f"fixture-uncertainty-{input_key}",
        policy_version="1.0",
        estimand_binding=bound(
            measurement.MeasurementDefinitionKind.ESTIMAND,
            f"fixture-estimand-{input_key}",
        ),
        measurement_output_binding=bound(
            measurement.MeasurementDefinitionKind.MEASUREMENT_OUTPUT,
            f"fixture-output-{input_key}",
        ),
        **components,
        stratum_minimum_bindings=(
            measurement.StratumEvidenceMinimumBinding(
                definition(
                    measurement.MeasurementDefinitionKind.STRATUM,
                    "fixture-stratum",
                ),
                bound(
                    measurement.MeasurementDefinitionKind.STRATUM_EVIDENCE_MINIMUM,
                    "fixture-stratum-minimum",
                ),
            ),
        ),
        dependence_shortcuts=(),
        fixture_origin=True,
    )


def fixture_objects():
    uncertainties = tuple(uncertainty_policy(input_key) for input_key, *_ in EXPECTED)
    measurements = tuple(
        measurement_contract(
            input_key,
            {
                measurement.ScoreUseRole.MANDATORY_GATE: measurement.MeasurementRole.MANDATORY,
                measurement.ScoreUseRole.SOFT_COMPONENT: measurement.MeasurementRole.SOFT,
                measurement.ScoreUseRole.DIAGNOSTIC: measurement.MeasurementRole.DIAGNOSTIC,
            }[use_role],
            measurement.measurement_ref(uncertainty_value),
        )
        for uncertainty_value, (input_key, _, use_role, *_) in zip(
            uncertainties, EXPECTED, strict=True
        )
    )
    bindings = tuple(
        measurement.ScorePackInputBinding(
            measurement_contract_ref=measurement.measurement_ref(measurement_value),
            measurement_output_ref=uncertainty_value.measurement_output_binding.component_ref,
            input_key=input_key,
            scalar_kind=scalar_kind,
            use_role=use_role,
            estimand_ref=uncertainty_value.estimand_binding.component_ref,
            case_scope_ref=definition(
                measurement.MeasurementDefinitionKind.CASE_SCOPE, "fixture-case-scope"
            ),
            stratum_ref=definition(
                measurement.MeasurementDefinitionKind.STRATUM, "fixture-stratum"
            ),
            uncertainty_policy_ref=measurement.measurement_ref(uncertainty_value),
            admissibility_policy_ref=definition(
                measurement.MeasurementDefinitionKind.SCORE_ADMISSIBILITY_POLICY,
                "fixture-admissibility-policy",
            ),
            admissibility_evidence_ref=definition(
                measurement.MeasurementDefinitionKind.SCORE_ADMISSIBILITY_EVIDENCE,
                "fixture-admissibility-evidence",
            ),
            aggregation_role=aggregation_role,
            ranking_role=ranking_role,
            disclosure_class=measurement.ScoreDisclosureClass.PROTECTED,
            disclosure_policy_ref=definition(
                measurement.MeasurementDefinitionKind.SCORE_DISCLOSURE_POLICY,
                "fixture-disclosure-policy",
            ),
            eligibility_role={
                measurement.ScoreUseRole.MANDATORY_GATE: measurement.ScoreEligibilityRole.MANDATORY_ADMISSIBILITY,
                measurement.ScoreUseRole.SOFT_COMPONENT: measurement.ScoreEligibilityRole.ELIGIBLE_AFTER_MANDATORY_ADMISSIBILITY,
                measurement.ScoreUseRole.DIAGNOSTIC: measurement.ScoreEligibilityRole.NON_SCORE_DIAGNOSTIC,
            }[use_role],
            destination_kind=destination_kind,
            destination_id=destination_id,
            applicability_evidence_ref=definition(
                measurement.MeasurementDefinitionKind.APPLICABILITY_EVIDENCE,
                "fixture-applicability-evidence",
            ),
            qualification_ref=definition(
                measurement.MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
                "fixture-dossier-qualification",
            ),
            provenance_ref=definition(
                measurement.MeasurementDefinitionKind.EVIDENCE_SOURCE,
                f"fixture-provenance-{input_key}",
            ),
            fixture_origin=True,
        )
        for measurement_value, uncertainty_value, (
            input_key,
            scalar_kind,
            use_role,
            aggregation_role,
            ranking_role,
            destination_kind,
            destination_id,
        ) in zip(measurements, uncertainties, EXPECTED, strict=True)
    )
    authoring = measurement.ScorePackAuthoringContract(
        challenge_key=KEY,
        contract_id="fixture-a5-score-pack-authoring",
        contract_version="1.0",
        score_pack_pin=pin(),
        input_bindings=bindings,
        threshold_authority_binding=bound(
            measurement.MeasurementDefinitionKind.SCORE_THRESHOLD_POLICY,
            "fixture-threshold-authority",
        ),
        transform_authority_binding=bound(
            measurement.MeasurementDefinitionKind.SCORE_TRANSFORM_POLICY,
            "fixture-transform-authority",
        ),
        weight_authority_binding=bound(
            measurement.MeasurementDefinitionKind.SCORE_WEIGHT_POLICY,
            "fixture-weight-authority",
        ),
        fixture_origin=True,
    )
    return measurements, uncertainties, authoring


def replace_graph_input(
    measurements,
    uncertainties,
    authoring,
    *,
    index=0,
    measurement_changes=None,
    uncertainty_changes=None,
):
    binding = authoring.input_bindings[index]
    measurement_index = next(
        item_index
        for item_index, item in enumerate(measurements)
        if measurement.measurement_ref(item) == binding.measurement_contract_ref
    )
    uncertainty_index = next(
        item_index
        for item_index, item in enumerate(uncertainties)
        if measurement.measurement_ref(item) == binding.uncertainty_policy_ref
    )
    changed_uncertainty = replace(
        uncertainties[uncertainty_index], **(uncertainty_changes or {})
    )
    selected_policy = measurement.UncertaintyPolicyBinding(
        measurement.ScientificValueState.BOUND,
        measurement.measurement_ref(changed_uncertainty),
    )
    changes = {"uncertainty_policy_binding": selected_policy}
    changes.update(measurement_changes or {})
    changed_measurement = replace(measurements[measurement_index], **changes)
    changed_binding = replace(
        binding,
        measurement_contract_ref=measurement.measurement_ref(changed_measurement),
        uncertainty_policy_ref=measurement.measurement_ref(changed_uncertainty),
    )
    return (
        measurements[:measurement_index]
        + (changed_measurement,)
        + measurements[measurement_index + 1 :],
        uncertainties[:uncertainty_index]
        + (changed_uncertainty,)
        + uncertainties[uncertainty_index + 1 :],
        replace(
            authoring,
            input_bindings=authoring.input_bindings[:index]
            + (changed_binding,)
            + authoring.input_bindings[index + 1 :],
        ),
    )


def qualification_evidence(
    value: measurement.MeasurementContract, input_key: str
) -> measurement.MeasurementQualificationEvidence:
    supported = (measurement.MeasurementClaimClass.IMPLEMENTATION_CORRECTNESS,)
    unsupported = tuple(
        claim for claim in measurement.MeasurementClaimClass if claim not in supported
    )
    return measurement.MeasurementQualificationEvidence(
        challenge_key=KEY,
        evidence_id=f"fixture-qualification-inventory-{input_key}",
        evidence_version="1.0",
        measurement_contract_ref=measurement.measurement_ref(value),
        evidence_items=(
            measurement.MeasurementEvidenceItem(
                evidence_id=f"fixture-mms-verification-{input_key}",
                source_ref=definition(
                    measurement.MeasurementDefinitionKind.EVIDENCE_SOURCE,
                    f"fixture-mms-source-{input_key}",
                ),
                role=measurement.MeasurementEvidenceRole.ANALYTIC_OR_MANUFACTURED_VERIFICATION,
                supported_claims=supported,
                unsupported_claims=unsupported,
                case_scope_refs=(
                    definition(
                        measurement.MeasurementDefinitionKind.CASE_SCOPE,
                        "fixture-case-scope",
                    ),
                ),
                stratum_scope_refs=(
                    definition(
                        measurement.MeasurementDefinitionKind.STRATUM,
                        "fixture-stratum",
                    ),
                ),
                fixture_origin=True,
            ),
        ),
        fixture_origin=True,
    )


def reconstruction_policy() -> measurement.ReconstructionEvidencePolicy:
    return measurement.ReconstructionEvidencePolicy(
        challenge_key=KEY,
        policy_id="fixture-reconstruction-evidence-policy",
        policy_version="1.0",
        construction_family_ref=definition(
            measurement.MeasurementDefinitionKind.CONSTRUCTION_FAMILY,
            "fixture-construction-family",
        ),
        **{
            name: measurement.UncertaintyComponentBinding(
                measurement.ScientificValueState.HUMAN_INPUT
            )
            for name in RECONSTRUCTION_KINDS
        },
        fixture_origin=True,
    )


def fixture_graph() -> SyntheticB05AuthoringGraph:
    measurements, uncertainties, authoring = fixture_objects()
    qualifications = tuple(
        qualification_evidence(value, input_key)
        for value, (input_key, *_) in zip(measurements, EXPECTED, strict=True)
    )
    reconstruction = reconstruction_policy()
    reconstruction_input = measurement.ReconstructionEvidenceInput(
        policy_ref=measurement.measurement_ref(reconstruction),
        construction_family_ref=reconstruction.construction_family_ref,
        resource_facts=measurement.ReconstructionResourceFacts(
            build_completion=NoBuildStarted(),
            frozen_artifact_reuse=NoReuse(),
            reconstruction_replicate=ReplicateNotApplicable(
                ReplicateNotApplicableReason.NO_WORK_STARTED
            ),
            resource_stop_cause=ResourceStopCause.EVIDENCE_DEFERRED,
            static_assessment_ref=None,
            fixture_decision_ref=None,
            observed_receipt_ref=None,
        ),
        complete_base_evidence_ref=None,
        nomination_evidence_ref=None,
        extension_evidence_ref=None,
        promotion_evidence_ref=None,
        remaining_requirement_refs=(
            definition(
                measurement.MeasurementDefinitionKind.REMAINING_EVIDENCE_REQUIREMENT,
                "fixture-human-scientific-authority-required",
            ),
        ),
        stop_kind=measurement.ReconstructionStopKind.NONE,
    )
    projection = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )
    return SyntheticB05AuthoringGraph(
        measurements,
        qualifications,
        uncertainties,
        reconstruction,
        measurement.assess_reconstruction_evidence(
            reconstruction, reconstruction_input
        ),
        authoring,
        projection,
    )


def materials(
    authoring, measurements, *, state=measurement.MeasurementMaterialState.COMPLETE
):
    measurements_by_ref = {
        measurement.measurement_ref(item): item for item in measurements
    }
    return tuple(
        measurement.MeasurementMaterial(
            measurement_contract_ref=binding.measurement_contract_ref,
            measurement_output_ref=binding.measurement_output_ref,
            case_scope_ref=binding.case_scope_ref,
            stratum_ref=binding.stratum_ref,
            reference_policy_ref=measurements_by_ref[
                binding.measurement_contract_ref
            ].reference_policy_ref,
            uncertainty_policy_ref=binding.uncertainty_policy_ref,
            applicability_evidence_ref=binding.applicability_evidence_ref,
            qualification_ref=(
                None
                if state
                is measurement.MeasurementMaterialState.QUALIFICATION_UNRESOLVED
                else binding.qualification_ref
            ),
            admissibility_evidence_ref=(
                None
                if state
                is measurement.MeasurementMaterialState.QUALIFICATION_UNRESOLVED
                else binding.admissibility_evidence_ref
            ),
            provenance_ref=binding.provenance_ref,
            source=measurement.MeasurementMaterialSource.QUALIFIED_MEASUREMENT,
            state=state,
            scalar_kind=binding.scalar_kind,
            numeric_scalar=(
                0.25
                if state is measurement.MeasurementMaterialState.COMPLETE
                and binding.scalar_kind is measurement.ScoreScalarKind.NUMERIC
                else None
            ),
            boolean_scalar=(
                True
                if state is measurement.MeasurementMaterialState.COMPLETE
                and binding.scalar_kind is measurement.ScoreScalarKind.BOOLEAN
                else None
            ),
            reason_ref=(
                None
                if state is measurement.MeasurementMaterialState.COMPLETE
                else definition(
                    measurement.MeasurementDefinitionKind.MEASUREMENT_MATERIAL_REASON,
                    f"fixture-{state.value.casefold().replace('_', '-')}",
                )
            ),
            fixture_origin=True,
        )
        for binding in authoring.input_bindings
    )


def input_index_for_role(authoring, use_role):
    return next(
        index
        for index, binding in enumerate(authoring.input_bindings)
        if binding.use_role is use_role
    )


def stratum_minimum(
    stratum_id: str,
    *,
    state: measurement.ScientificValueState = measurement.ScientificValueState.BOUND,
):
    return measurement.StratumEvidenceMinimumBinding(
        definition(measurement.MeasurementDefinitionKind.STRATUM, stratum_id),
        measurement.UncertaintyComponentBinding(
            state,
            (
                definition(
                    measurement.MeasurementDefinitionKind.STRATUM_EVIDENCE_MINIMUM,
                    f"fixture-minimum-{stratum_id}",
                )
                if state is measurement.ScientificValueState.BOUND
                else None
            ),
        ),
    )


def test_complete_synthetic_authoring_graph_is_exact_and_non_authoritative() -> None:
    graph = fixture_graph()
    store = measurement.MeasurementFixtureStore()
    authoring_objects = (
        graph.measurements
        + graph.qualification_evidence
        + graph.uncertainty_policies
        + (graph.reconstruction_policy, graph.score_pack_authoring)
    )
    refs = tuple(store.put(value) for value in authoring_objects)

    assert len(refs) == len(authoring_objects) == len(set(refs))
    for value, ref in zip(authoring_objects, refs, strict=True):
        source = measurement.canonical_bytes(value)
        assert store.get(ref) == value
        assert measurement.load_canonical_document(source) == value
        assert measurement.measurement_ref(value) == ref
        assert measurement.canonical_digest(value) == (
            "sha256:" + hashlib.sha256(source).hexdigest()
        )

    assert tuple(
        evidence.measurement_contract_ref for evidence in graph.qualification_evidence
    ) == tuple(measurement.measurement_ref(value) for value in graph.measurements)
    unsupported_by_mms = {
        measurement.MeasurementClaimClass.PHYSICAL_MODEL_VALIDITY,
        measurement.MeasurementClaimClass.TARGET_WORKLOAD_APPLICABILITY,
        measurement.MeasurementClaimClass.ENGINEERING_CONTEXT_OF_USE,
    }
    assert all(
        unsupported_by_mms <= set(evidence.evidence_items[0].unsupported_claims)
        for evidence in graph.qualification_evidence
    )

    assert not graph.reconstruction_policy.has_complete_human_authority
    assert (
        graph.reconstruction_status.outcome
        is measurement.ReconstructionEvidenceOutcome.EVIDENCE_DEFERRED
    )
    assert (
        graph.reconstruction_status.stage
        is measurement.ReconstructionEvidenceStage.BASE_REQUIRED
    )
    assert graph.score_pack_projection.pack_pin == pin()
    assert (
        graph.score_pack_projection.outcome
        is measurement.MeasurementMaterialState.COMPLETE
    )
    for role, values in (
        (
            measurement.ScoreUseRole.MANDATORY_GATE,
            graph.score_pack_projection.mandatory_scalars,
        ),
        (
            measurement.ScoreUseRole.SOFT_COMPONENT,
            graph.score_pack_projection.soft_scalars,
        ),
        (
            measurement.ScoreUseRole.DIAGNOSTIC,
            graph.score_pack_projection.diagnostic_scalars,
        ),
    ):
        assert tuple(item.input_key for item in values) == tuple(
            item[0] for item in EXPECTED if item[2] is role
        )
    assert all(value.fixture_origin is True for value in authoring_objects)
    assert all(
        binding.disclosure_class is measurement.ScoreDisclosureClass.PROTECTED
        for binding in graph.score_pack_authoring.input_bindings
    )
    assert "ScoreInput" not in type(graph.score_pack_projection).__name__


def test_authoring_contract_is_canonical_content_addressed_and_stored() -> None:
    _, _, authoring = fixture_objects()
    source = measurement.canonical_bytes(authoring)
    loaded = measurement.load_canonical_document(source)
    store = measurement.MeasurementFixtureStore()
    ref = store.put(authoring)

    assert loaded == authoring
    assert measurement.canonical_bytes(loaded) == source
    assert type(ref) is measurement.ScorePackAuthoringContractRef
    assert store.get(ref) == authoring
    assert measurement.canonical_digest(authoring) == (
        "sha256:" + hashlib.sha256(source).hexdigest()
    )


def test_ready_a5_pack_has_exact_complete_binding_coverage() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    ordered = measurement.validate_score_pack_coverage(
        authoring, pack(), measurements, uncertainties
    )
    assert tuple(item.input_key for item in ordered) == tuple(
        item[0] for item in EXPECTED
    )


def test_complete_material_projects_by_mandatory_soft_diagnostic_role() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )
    assert result.outcome is measurement.MeasurementMaterialState.COMPLETE
    assert [item.input_key for item in result.mandatory_scalars] == [
        "gate_error",
        "finite_ok",
    ]
    assert len(result.soft_scalars) == 7
    assert [item.input_key for item in result.diagnostic_scalars] == [
        "diagnostic_error"
    ]
    assert "ScoreInput" not in type(result).__name__


@pytest.mark.parametrize(
    "state",
    (
        measurement.ScientificValueState.HUMAN_INPUT,
        measurement.ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET,
    ),
)
@pytest.mark.parametrize(
    "use_role",
    (
        measurement.ScoreUseRole.MANDATORY_GATE,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreUseRole.DIAGNOSTIC,
    ),
)
def test_unresolved_numerical_floor_overrides_complete_material(
    state, use_role
) -> None:
    measurements, uncertainties, authoring = fixture_objects()
    index = next(
        item_index
        for item_index, item in enumerate(authoring.input_bindings)
        if item.use_role is use_role
    )
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        index=index,
        measurement_changes={
            "numerical_floor_binding": measurement.ScientificValueBinding(state)
        },
    )
    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )
    assert (
        result.outcome
        is measurement.MeasurementMaterialState.NUMERICAL_FLOOR_UNRESOLVED
    )
    assert result.blocking_input_keys == (authoring.input_bindings[index].input_key,)
    assert (
        result.mandatory_scalars
        == result.soft_scalars
        == result.diagnostic_scalars
        == ()
    )


def test_resolved_synthetic_numerical_floor_permits_complete_projection() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    assert all(
        item.numerical_floor_binding.state is measurement.ScientificValueState.BOUND
        and item.numerical_floor_binding.value_ref.object_id.startswith(
            "fixture-synthetic-numerical-floor-"
        )
        for item in measurements
    )
    assert (
        measurement.project_score_scalars(
            authoring,
            pack(),
            measurements,
            uncertainties,
            materials(authoring, measurements),
        ).outcome
        is measurement.MeasurementMaterialState.COMPLETE
    )


@pytest.mark.parametrize(
    "state",
    (
        measurement.ScientificValueState.HUMAN_INPUT,
        measurement.ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET,
    ),
)
def test_unresolved_measurement_policy_selection_has_no_scalar(state) -> None:
    measurements, uncertainties, authoring = fixture_objects()
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        measurement_changes={
            "uncertainty_policy_binding": measurement.UncertaintyPolicyBinding(state)
        },
    )
    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )
    assert result.outcome is measurement.MeasurementMaterialState.UNCERTAINTY_UNRESOLVED
    assert result.blocking_input_keys == (authoring.input_bindings[0].input_key,)
    assert (
        result.mandatory_scalars
        == result.soft_scalars
        == result.diagnostic_scalars
        == ()
    )


@pytest.mark.parametrize("field_name", tuple(UNCERTAINTY_KINDS))
@pytest.mark.parametrize(
    "state",
    (
        measurement.ScientificValueState.HUMAN_INPUT,
        measurement.ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET,
    ),
)
def test_every_unresolved_required_uncertainty_component_has_no_scalar(
    field_name, state
) -> None:
    measurements, uncertainties, authoring = fixture_objects()
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        uncertainty_changes={
            field_name: measurement.UncertaintyComponentBinding(state)
        },
    )
    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )
    assert result.outcome is measurement.MeasurementMaterialState.UNCERTAINTY_UNRESOLVED
    assert result.blocking_input_keys == (authoring.input_bindings[0].input_key,)
    assert (
        result.mandatory_scalars
        == result.soft_scalars
        == result.diagnostic_scalars
        == ()
    )


@pytest.mark.parametrize(
    "state",
    (
        measurement.ScientificValueState.HUMAN_INPUT,
        measurement.ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET,
    ),
)
@pytest.mark.parametrize(
    "use_role",
    (
        measurement.ScoreUseRole.MANDATORY_GATE,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreUseRole.DIAGNOSTIC,
    ),
)
def test_unresolved_exact_stratum_minimum_has_no_scalar(state, use_role) -> None:
    measurements, uncertainties, authoring = fixture_objects()
    index = input_index_for_role(authoring, use_role)
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        index=index,
        uncertainty_changes={
            "stratum_minimum_bindings": (
                stratum_minimum("fixture-stratum", state=state),
            )
        },
    )
    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )
    assert result.outcome is measurement.MeasurementMaterialState.UNCERTAINTY_UNRESOLVED
    assert result.blocking_input_keys == (authoring.input_bindings[index].input_key,)
    assert (
        result.mandatory_scalars
        == result.soft_scalars
        == result.diagnostic_scalars
        == ()
    )


@pytest.mark.parametrize(
    "use_role",
    (
        measurement.ScoreUseRole.MANDATORY_GATE,
        measurement.ScoreUseRole.SOFT_COMPONENT,
        measurement.ScoreUseRole.DIAGNOSTIC,
    ),
)
def test_foreign_stratum_minimum_cannot_substitute_for_exact_binding(
    use_role,
) -> None:
    measurements, uncertainties, authoring = fixture_objects()
    index = input_index_for_role(authoring, use_role)
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        index=index,
        uncertainty_changes={
            "stratum_minimum_bindings": (stratum_minimum("fixture-foreign-stratum"),)
        },
    )

    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )

    assert result.outcome is measurement.MeasurementMaterialState.UNCERTAINTY_UNRESOLVED
    assert result.blocking_input_keys == (authoring.input_bindings[index].input_key,)
    assert (
        result.mandatory_scalars
        == result.soft_scalars
        == result.diagnostic_scalars
        == ()
    )


def test_absent_target_stratum_is_not_inferred_from_other_minima() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        uncertainty_changes={
            "stratum_minimum_bindings": (
                stratum_minimum("fixture-foreign-stratum-a"),
                stratum_minimum("fixture-foreign-stratum-b"),
            )
        },
    )

    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )

    assert result.outcome is measurement.MeasurementMaterialState.UNCERTAINTY_UNRESOLVED
    assert result.blocking_input_keys == (authoring.input_bindings[0].input_key,)
    assert (
        result.mandatory_scalars
        == result.soft_scalars
        == result.diagnostic_scalars
        == ()
    )


def test_unrelated_resolved_minimum_does_not_replace_unresolved_exact_minimum() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        uncertainty_changes={
            "stratum_minimum_bindings": (
                stratum_minimum(
                    "fixture-stratum",
                    state=measurement.ScientificValueState.HUMAN_INPUT,
                ),
                stratum_minimum("fixture-foreign-stratum"),
            )
        },
    )

    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )

    assert result.outcome is measurement.MeasurementMaterialState.UNCERTAINTY_UNRESOLVED
    assert result.blocking_input_keys == (authoring.input_bindings[0].input_key,)
    assert (
        result.mandatory_scalars
        == result.soft_scalars
        == result.diagnostic_scalars
        == ()
    )


def test_exact_resolved_minimum_with_unrelated_minimum_remains_complete() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    exact_minimum = uncertainties[0].stratum_minimum_bindings[0]
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        uncertainty_changes={
            "stratum_minimum_bindings": (
                exact_minimum,
                stratum_minimum("fixture-foreign-stratum"),
            )
        },
    )

    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )

    assert result.outcome is measurement.MeasurementMaterialState.COMPLETE


def test_exact_not_applicable_uncertainty_component_remains_resolved() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    reason = definition(
        measurement.MeasurementDefinitionKind.APPLICABILITY_REASON,
        "fixture-execution-dependence-not-applicable",
    )
    measurements, uncertainties, authoring = replace_graph_input(
        measurements,
        uncertainties,
        authoring,
        uncertainty_changes={
            "execution_dependence_binding": measurement.UncertaintyComponentBinding(
                measurement.ScientificValueState.NOT_APPLICABLE, reason
            )
        },
    )
    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements),
    )
    assert result.outcome is measurement.MeasurementMaterialState.COMPLETE


def test_bound_measurement_policy_mismatch_rejects() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    binding = authoring.input_bindings[0]
    measurement_index = next(
        index
        for index, item in enumerate(measurements)
        if measurement.measurement_ref(item) == binding.measurement_contract_ref
    )
    mismatched = replace(
        measurements[measurement_index],
        uncertainty_policy_binding=measurement.UncertaintyPolicyBinding(
            measurement.ScientificValueState.BOUND,
            measurement.UncertaintyPolicyRef(KEY, DIGEST_A),
        ),
    )
    changed_binding = replace(
        binding,
        measurement_contract_ref=measurement.measurement_ref(mismatched),
    )
    changed_authoring = replace(
        authoring,
        input_bindings=(changed_binding,) + authoring.input_bindings[1:],
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.validate_score_pack_coverage(
            changed_authoring,
            pack(),
            measurements[:measurement_index]
            + (mismatched,)
            + measurements[measurement_index + 1 :],
            uncertainties,
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION


def test_bound_policy_ref_without_matching_supplied_policy_rejects() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    binding = authoring.input_bindings[0]
    measurement_index = next(
        index
        for index, item in enumerate(measurements)
        if measurement.measurement_ref(item) == binding.measurement_contract_ref
    )
    foreign_ref = measurement.UncertaintyPolicyRef(KEY, DIGEST_A)
    changed_measurement = replace(
        measurements[measurement_index],
        uncertainty_policy_binding=measurement.UncertaintyPolicyBinding(
            measurement.ScientificValueState.BOUND, foreign_ref
        ),
    )
    changed_binding = replace(
        binding,
        measurement_contract_ref=measurement.measurement_ref(changed_measurement),
        uncertainty_policy_ref=foreign_ref,
    )
    changed_authoring = replace(
        authoring,
        input_bindings=(changed_binding,) + authoring.input_bindings[1:],
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.validate_score_pack_coverage(
            changed_authoring,
            pack(),
            measurements[:measurement_index]
            + (changed_measurement,)
            + measurements[measurement_index + 1 :],
            uncertainties,
        )
    assert (
        exc_info.value.code is measurement.MeasurementInputCode.PACK_COVERAGE_MISMATCH
    )


@pytest.mark.parametrize(
    "state",
    tuple(
        item
        for item in measurement.MeasurementMaterialState
        if item.value != "COMPLETE"
    ),
)
def test_every_noncomplete_material_state_has_no_scalar_projection(state) -> None:
    measurements, uncertainties, authoring = fixture_objects()
    result = measurement.project_score_scalars(
        authoring,
        pack(),
        measurements,
        uncertainties,
        materials(authoring, measurements, state=state),
    )
    assert result.outcome is state
    assert result.blocking_input_keys
    assert result.mandatory_scalars == ()
    assert result.soft_scalars == ()
    assert result.diagnostic_scalars == ()


def test_unresolved_mandatory_prevents_all_soft_projection() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    complete = list(materials(authoring, measurements))
    mandatory_index = next(
        index
        for index, binding in enumerate(authoring.input_bindings)
        if binding.use_role is measurement.ScoreUseRole.MANDATORY_GATE
    )
    complete[mandatory_index] = replace(
        complete[mandatory_index],
        state=measurement.MeasurementMaterialState.QUALIFICATION_UNRESOLVED,
        numeric_scalar=None,
        boolean_scalar=None,
        qualification_ref=None,
        admissibility_evidence_ref=None,
        reason_ref=definition(
            measurement.MeasurementDefinitionKind.MEASUREMENT_MATERIAL_REASON,
            "fixture-qualification-unresolved",
        ),
    )
    result = measurement.project_score_scalars(
        authoring, pack(), measurements, uncertainties, tuple(complete)
    )
    assert (
        result.outcome is measurement.MeasurementMaterialState.QUALIFICATION_UNRESOLVED
    )
    assert (
        result.mandatory_scalars
        == result.soft_scalars
        == result.diagnostic_scalars
        == ()
    )


def test_missing_soft_material_is_not_silently_renormalized() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    incomplete = tuple(
        item
        for item in materials(authoring, measurements)
        if item.measurement_output_ref
        != next(
            binding.measurement_output_ref
            for binding in authoring.input_bindings
            if binding.use_role is measurement.ScoreUseRole.SOFT_COMPONENT
        )
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.project_score_scalars(
            authoring, pack(), measurements, uncertainties, incomplete
        )
    assert (
        exc_info.value.code is measurement.MeasurementInputCode.PACK_COVERAGE_MISMATCH
    )


@pytest.mark.parametrize(
    "source",
    tuple(
        item
        for item in measurement.MeasurementMaterialSource
        if item is not measurement.MeasurementMaterialSource.QUALIFIED_MEASUREMENT
    ),
)
def test_forbidden_sources_reject_regardless_of_scalar_shape(source) -> None:
    measurements, uncertainties, authoring = fixture_objects()
    candidate = list(materials(authoring, measurements))
    candidate[0] = replace(candidate[0], source=source)
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.project_score_scalars(
            authoring, pack(), measurements, uncertainties, tuple(candidate)
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.FORBIDDEN_SOURCE


def test_duplicate_unknown_and_role_confused_a5_bindings_reject() -> None:
    measurements, uncertainties, authoring = fixture_objects()
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            authoring,
            input_bindings=authoring.input_bindings + (authoring.input_bindings[0],),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.DUPLICATE_IDENTITY

    wrong_key_binding = replace(authoring.input_bindings[0], input_key="unknown-key")
    wrong_key = replace(
        authoring,
        input_bindings=(wrong_key_binding,) + authoring.input_bindings[1:],
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.validate_score_pack_coverage(
            wrong_key, pack(), measurements, uncertainties
        )
    assert (
        exc_info.value.code is measurement.MeasurementInputCode.PACK_COVERAGE_MISMATCH
    )

    soft = next(
        item
        for item in authoring.input_bindings
        if item.use_role is measurement.ScoreUseRole.SOFT_COMPONENT
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            soft,
            ranking_role=measurement.ScoreRankingRole.NON_RANKING_DIAGNOSTIC,
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION

    diagnostic = next(
        item
        for item in authoring.input_bindings
        if item.use_role is measurement.ScoreUseRole.DIAGNOSTIC
    )
    relabeled_diagnostic = replace(
        diagnostic,
        use_role=measurement.ScoreUseRole.SOFT_COMPONENT,
        aggregation_role=measurement.ScoreAggregationRole.PHYSICS,
        ranking_role=measurement.ScoreRankingRole.RANKING_INPUT,
        eligibility_role=measurement.ScoreEligibilityRole.ELIGIBLE_AFTER_MANDATORY_ADMISSIBILITY,
        destination_kind=measurement.A5DestinationKind.PHYSICS_COMPONENT,
    )
    changed = replace(
        authoring,
        input_bindings=tuple(
            relabeled_diagnostic if item is diagnostic else item
            for item in authoring.input_bindings
        ),
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.validate_score_pack_coverage(
            changed, pack(), measurements, uncertainties
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION

    relabeled_soft = replace(
        soft,
        use_role=measurement.ScoreUseRole.MANDATORY_GATE,
        aggregation_role=measurement.ScoreAggregationRole.MANDATORY_ADMISSIBILITY,
        ranking_role=measurement.ScoreRankingRole.ADMISSIBILITY_ONLY,
        eligibility_role=measurement.ScoreEligibilityRole.MANDATORY_ADMISSIBILITY,
        destination_kind=measurement.A5DestinationKind.MANDATORY_GATE,
    )
    changed = replace(
        authoring,
        input_bindings=tuple(
            relabeled_soft if item is soft else item
            for item in authoring.input_bindings
        ),
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.validate_score_pack_coverage(
            changed, pack(), measurements, uncertainties
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION


def test_cross_challenge_fixture_mismatch_and_unresolved_policy_authority_reject() -> (
    None
):
    measurements, uncertainties, authoring = fixture_objects()
    other = ChallengeKey("other-fixture", "fixture-1.0")
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            authoring.input_bindings[0],
            qualification_ref=measurement.MeasurementDefinitionRef(
                other,
                measurement.MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
                "other-qualification",
                "1.0",
                DIGEST_A,
            ),
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.CROSS_CHALLENGE

    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(authoring, fixture_origin=False)
    assert exc_info.value.code is measurement.MeasurementInputCode.FIXTURE_REQUIRED

    unresolved = replace(
        authoring,
        weight_authority_binding=measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.HUMAN_INPUT
        ),
    )
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        measurement.validate_score_pack_coverage(
            unresolved, pack(), measurements, uncertainties
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.MATERIAL_UNRESOLVED


def test_evidence_inventory_ref_cannot_masquerade_as_dossier_qualification() -> None:
    graph = fixture_graph()
    evidence_ref = measurement.measurement_ref(graph.qualification_evidence[0])
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(
            graph.score_pack_authoring.input_bindings[0],
            qualification_ref=evidence_ref,
        )
    assert exc_info.value.code is measurement.MeasurementInputCode.WRONG_TYPE


def test_missing_human_score_values_have_no_equal_or_unit_defaults() -> None:
    _, _, authoring = fixture_objects()
    unresolved = replace(
        authoring,
        threshold_authority_binding=measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.HUMAN_INPUT
        ),
        transform_authority_binding=measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.BLOCKED_FOR_LIVE_UNTIL_SET
        ),
        weight_authority_binding=measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.HUMAN_INPUT
        ),
    )
    for name in (
        "threshold_authority_binding",
        "transform_authority_binding",
        "weight_authority_binding",
    ):
        binding = getattr(unresolved, name)
        assert binding.component_ref is None
        assert not isinstance(binding, (int, float))
    assert not unresolved.has_complete_score_policy_authority


def test_noncomplete_material_cannot_carry_zero_or_any_scalar() -> None:
    measurements, _, authoring = fixture_objects()
    candidate = materials(
        authoring,
        measurements,
        state=measurement.MeasurementMaterialState.PARTIAL,
    )[0]
    with pytest.raises(measurement.MeasurementValidationError) as exc_info:
        replace(candidate, numeric_scalar=0.0)
    assert exc_info.value.code is measurement.MeasurementInputCode.ROLE_CONFUSION
