from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from carbon import measurement, reproducibility
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
)
from carbon.construction import EnvironmentPin, ResolvedConstructionPlanRef
from carbon.evaluation import (
    ReferenceComparisonOutcome,
    ReferenceRunOutcome,
)
from carbon.evaluation.refs import ReferencePolicyRef
from carbon.registry import ChallengeKey
from carbon.resource_policy import (
    CompleteBuild,
    CompleteBuildIdentity,
    NoReuse,
    ReplicateNotApplicable,
    ReplicateNotApplicableReason,
    ResearchResourcePolicyRef,
    ResourceClassRef,
    ResourceStopCause,
)

KEY = ChallengeKey("fixture-burgers", "1.0")
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64

UNCERTAINTY_COMPONENTS = {
    "estimand_binding": measurement.MeasurementDefinitionKind.ESTIMAND,
    "measurement_output_binding": measurement.MeasurementDefinitionKind.MEASUREMENT_OUTPUT,
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

RECONSTRUCTION_COMPONENTS = {
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


def digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()


def definition(
    kind: measurement.MeasurementDefinitionKind,
    object_id: str,
    *,
    content_digest: str | None = None,
) -> measurement.MeasurementDefinitionRef:
    return measurement.MeasurementDefinitionRef(
        KEY, kind, object_id, "1.0", content_digest or digest(object_id)
    )


def ref(
    kind: reproducibility.ReproducibilityRefKind, object_id: str
) -> reproducibility.ReproducibilityRef:
    return reproducibility.ReproducibilityRef(
        KEY, kind, object_id, "1.0", digest(object_id)
    )


def top_ref(ref_type, object_id: str, *extra):
    return ref_type(
        KEY,
        object_id,
        "1.0",
        AUTHORING_SCHEMA_VERSION,
        CANONICALIZATION_PROFILE,
        digest(object_id),
        *extra,
    )


def bound(kind: measurement.MeasurementDefinitionKind, label: str):
    return measurement.UncertaintyComponentBinding(
        measurement.ScientificValueState.BOUND,
        definition(kind, label),
    )


def fixed_scope_refs():
    return (
        (
            definition(
                measurement.MeasurementDefinitionKind.CASE_SCOPE, "case-scope-one"
            ),
            definition(
                measurement.MeasurementDefinitionKind.CASE_SCOPE, "case-scope-two"
            ),
        ),
        (
            definition(measurement.MeasurementDefinitionKind.STRATUM, "stratum-one"),
            definition(measurement.MeasurementDefinitionKind.STRATUM, "stratum-two"),
        ),
    )


def uncertainty_policy(
    *, shortcut_kind: measurement.DependenceShortcutKind | None = None
) -> measurement.UncertaintyPolicy:
    case_scopes, strata = fixed_scope_refs()
    shortcuts = ()
    if shortcut_kind is not None:
        shortcuts = (
            measurement.DependenceShortcutBinding(
                "fixture-shortcut",
                "1.0",
                shortcut_kind,
                definition(
                    measurement.MeasurementDefinitionKind.EVIDENCE_SET,
                    "incumbent-evidence",
                ),
                definition(
                    measurement.MeasurementDefinitionKind.EVIDENCE_SET,
                    "challenger-evidence",
                ),
                case_scopes,
                strata,
                definition(
                    measurement.MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION,
                    "dependence-assumption",
                ),
                definition(
                    measurement.MeasurementDefinitionKind.APPLICABILITY_TEST,
                    "applicability-test",
                ),
                definition(
                    measurement.MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
                    "dossier-qualification",
                ),
                True,
            ),
        )
    return measurement.UncertaintyPolicy(
        challenge_key=KEY,
        policy_id="fixture-uncertainty-policy",
        policy_version="1.0",
        **{
            name: bound(kind, f"uncertainty-{name.replace('_', '-')}")
            for name, kind in UNCERTAINTY_COMPONENTS.items()
        },
        stratum_minimum_bindings=tuple(
            measurement.StratumEvidenceMinimumBinding(
                stratum,
                bound(
                    measurement.MeasurementDefinitionKind.STRATUM_EVIDENCE_MINIMUM,
                    f"minimum-{index}",
                ),
            )
            for index, stratum in enumerate(strata)
        ),
        dependence_shortcuts=shortcuts,
        fixture_origin=True,
    )


def reconstruction_policy() -> measurement.ReconstructionEvidencePolicy:
    return measurement.ReconstructionEvidencePolicy(
        challenge_key=KEY,
        policy_id="fixture-reconstruction-policy",
        policy_version="1.0",
        construction_family_ref=definition(
            measurement.MeasurementDefinitionKind.CONSTRUCTION_FAMILY,
            "construction-family",
        ),
        **{
            name: bound(kind, f"reconstruction-{name.replace('_', '-')}")
            for name, kind in RECONSTRUCTION_COMPONENTS.items()
        },
        fixture_origin=True,
    )


def identity_manifest(
    *,
    backend_support: reproducibility.BackendProfileSupport = (
        reproducibility.BackendProfileSupport.SUPPORTED
    ),
):
    reconstruction = reconstruction_policy()
    uncertainty = uncertainty_policy()
    return reproducibility.ExactIdentityManifest(
        challenge_key=KEY,
        candidate_artifact_ref=ref(
            reproducibility.ReproducibilityRefKind.CANDIDATE_ARTIFACT,
            "candidate-artifact",
        ),
        physical_system_ref=top_ref(PhysicalSystemSpecRef, "physical-system"),
        candidate_output_contract_ref=top_ref(
            CandidateOutputContractRef, "candidate-output"
        ),
        target_distribution_ref=top_ref(
            InstanceDistributionContractRef,
            "target-distribution",
            "TARGET_WORKLOAD_P",
        ),
        sampling_plan_ref=top_ref(SamplingPlanRef, "sampling-plan"),
        resolved_plan_ref=ResolvedConstructionPlanRef(KEY, content_digest=DIGEST_A),
        uncertainty_policy_ref=measurement.measurement_ref(uncertainty),
        reconstruction_policy_ref=measurement.measurement_ref(reconstruction),
        reference_policy_ref=ReferencePolicyRef(KEY, DIGEST_A),
        generator_ref=ref(
            reproducibility.ReproducibilityRefKind.GENERATOR, "generator"
        ),
        scoring_ref=ref(reproducibility.ReproducibilityRefKind.SCORING, "scoring"),
        backend_profile_ref=ref(
            reproducibility.ReproducibilityRefKind.BACKEND_PROFILE,
            "backend-profile",
        ),
        backend_support=backend_support,
        environment_ref=ref(
            reproducibility.ReproducibilityRefKind.ENVIRONMENT, "environment"
        ),
        execution_limits_ref=ref(
            reproducibility.ReproducibilityRefKind.EXECUTION_LIMITS,
            "execution-limits",
        ),
        seed_role_structure_ref=ref(
            reproducibility.ReproducibilityRefKind.SEED_ROLE_STRUCTURE,
            "seed-role-structure",
        ),
        receipt_construction_ref=ref(
            reproducibility.ReproducibilityRefKind.RECEIPT_CONSTRUCTION,
            "receipt-construction",
        ),
        hardware_role_ref=ref(
            reproducibility.ReproducibilityRefKind.HARDWARE_ROLE,
            "identity-hardware-role",
        ),
        fixture_origin=True,
    )


class NumericalProcedure:
    def __init__(self, manifest, *, fail: bool = False):
        self.fail = fail
        self.qualification = reproducibility.NumericalProcedureQualification(
            ref(reproducibility.ReproducibilityRefKind.PROCEDURE, "r1-procedure"),
            ref(
                reproducibility.ReproducibilityRefKind.TOLERANCE_POLICY,
                "r1-tolerance",
            ),
            definition(
                measurement.MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
                "r1-dossier",
            ),
            manifest.backend_profile_ref,
            True,
        )

    def compare(self, first, second):
        if self.fail:
            raise RuntimeError("fixture procedure failure")
        second_by_ref = {item.output_ref: item.value for item in second.outputs}
        deltas = tuple(
            reproducibility.NumericalDelta(
                item.output_ref, abs(item.value - second_by_ref[item.output_ref])
            )
            for item in first.outputs
        )
        outcome = (
            reproducibility.R1Outcome.REPRODUCIBLE
            if all(item.absolute_delta <= 0.01 for item in deltas)
            else reproducibility.R1Outcome.NOT_REPRODUCIBLE
        )
        return reproducibility.NumericalProcedureDecision(
            outcome,
            deltas,
            ref(reproducibility.ReproducibilityRefKind.EVIDENCE, "r1-decision"),
        )


def run_capture(manifest, values=(1.0, 2.0)):
    return reproducibility.NumericalRunCapture(
        manifest,
        tuple(
            reproducibility.NumericalDatum(
                ref(
                    reproducibility.ReproducibilityRefKind.NUMERICAL_OUTPUT,
                    f"output-{index}",
                ),
                value,
            )
            for index, value in enumerate(values)
        ),
    )


def test_r0_is_exact_identity_and_stays_separate_from_r1() -> None:
    manifest = identity_manifest()
    assert (
        reproducibility.compare_r0(manifest, manifest).outcome
        is reproducibility.R0Outcome.EXACT_MATCH
    )

    changed = replace(
        manifest,
        environment_ref=ref(
            reproducibility.ReproducibilityRefKind.ENVIRONMENT,
            "changed-environment",
        ),
    )
    result = reproducibility.compare_r1(
        run_capture(manifest), run_capture(changed), NumericalProcedure(manifest)
    )
    assert result.outcome is reproducibility.R1Outcome.R0_IDENTITY_MISMATCH
    assert result.r0_result.mismatched_fields == ("environment_ref",)
    assert result.deltas == ()


def test_r1_uses_only_the_injected_backend_qualified_procedure() -> None:
    manifest = identity_manifest()
    first = run_capture(manifest)
    assert (
        reproducibility.compare_r1(
            first, run_capture(manifest, (1.005, 2.0)), NumericalProcedure(manifest)
        ).outcome
        is reproducibility.R1Outcome.REPRODUCIBLE
    )
    assert (
        reproducibility.compare_r1(
            first, run_capture(manifest, (1.02, 2.0)), NumericalProcedure(manifest)
        ).outcome
        is reproducibility.R1Outcome.NOT_REPRODUCIBLE
    )
    assert (
        reproducibility.compare_r1(first, first, None).outcome
        is reproducibility.R1Outcome.INDETERMINATE
    )
    assert (
        reproducibility.compare_r1(
            first, first, NumericalProcedure(manifest, fail=True)
        ).outcome
        is reproducibility.R1Outcome.INFRASTRUCTURE_FAILED
    )

    unsupported = identity_manifest(
        backend_support=reproducibility.BackendProfileSupport.UNSUPPORTED
    )
    assert (
        reproducibility.compare_r1(
            run_capture(unsupported),
            run_capture(unsupported),
            NumericalProcedure(unsupported),
        ).outcome
        is reproducibility.R1Outcome.BACKEND_UNSUPPORTED
    )


def test_numerical_values_fail_closed_and_canonical_encoding_is_deterministic() -> None:
    with pytest.raises(reproducibility.ReproducibilityValidationError):
        reproducibility.NumericalDatum(
            ref(reproducibility.ReproducibilityRefKind.NUMERICAL_OUTPUT, "bad-output"),
            float("nan"),
        )
    manifest = identity_manifest()
    assert reproducibility.canonical_bytes(manifest) == reproducibility.canonical_bytes(
        manifest
    )
    assert reproducibility.canonical_digest(manifest).startswith("sha256:")


def evidence_factors(cell_index: int):
    return tuple(
        reproducibility.EvidenceFactorObservation(
            factor,
            reproducibility.EvidenceFactorState.OBSERVED,
            ref(
                reproducibility.ReproducibilityRefKind.EVIDENCE,
                f"factor-{cell_index}-{factor_index}",
            ),
            float(cell_index + factor_index + 1) / 100.0,
        )
        for factor_index, factor in enumerate(reproducibility.REQUIRED_EVIDENCE_FACTORS)
    )


def crossed_graph(policy: measurement.UncertaintyPolicy):
    reconstruction = reconstruction_policy()
    case_scopes, strata = fixed_scope_refs()
    cases = tuple(
        reproducibility.CaseDesignUnit(
            top_ref(CanonicalChallengeCaseRef, f"case-{index}", "INTERNAL"),
            case_scopes[index],
            strata[index],
        )
        for index in range(2)
    )
    incumbent_reconstructions = tuple(
        ref(
            reproducibility.ReproducibilityRefKind.RECONSTRUCTION, f"incumbent-r{index}"
        )
        for index in range(2)
    )
    challenger_reconstructions = tuple(
        ref(
            reproducibility.ReproducibilityRefKind.RECONSTRUCTION,
            f"challenger-r{index}",
        )
        for index in range(2)
    )
    design = reproducibility.CrossedEvidenceDesign(
        KEY,
        definition(
            measurement.MeasurementDefinitionKind.EVIDENCE_SET, "incumbent-evidence"
        ),
        definition(
            measurement.MeasurementDefinitionKind.EVIDENCE_SET, "challenger-evidence"
        ),
        measurement.measurement_ref(policy),
        measurement.measurement_ref(reconstruction),
        incumbent_reconstructions,
        challenger_reconstructions,
        cases,
        tuple(reproducibility.SharedDependencyKind),
        True,
    )
    reference_realizations = tuple(
        ref(
            reproducibility.ReproducibilityRefKind.REFERENCE_REALIZATION,
            f"reference-{i}",
        )
        for i in range(2)
    )
    random_roles = tuple(
        ref(reproducibility.ReproducibilityRefKind.RANDOMNESS_ROLE, f"random-role-{i}")
        for i in range(2)
    )
    seed_roles = tuple(
        ref(reproducibility.ReproducibilityRefKind.TRAINING_SEED_ROLE, f"seed-role-{i}")
        for i in range(2)
    )
    hardware = ref(
        reproducibility.ReproducibilityRefKind.HARDWARE_ROLE, "shared-hardware"
    )
    representation = ref(
        reproducibility.ReproducibilityRefKind.REPRESENTATION, "shared-representation"
    )
    execution = ref(
        reproducibility.ReproducibilityRefKind.EXECUTION, "shared-execution"
    )
    cells = []
    for arm, reconstructions in (
        (reproducibility.ComparisonArm.INCUMBENT, incumbent_reconstructions),
        (reproducibility.ComparisonArm.CHALLENGER, challenger_reconstructions),
    ):
        for reconstruction in reconstructions:
            for case_index, case in enumerate(cases):
                cell_index = len(cells)
                cells.append(
                    reproducibility.EvidenceCell(
                        arm,
                        reconstruction,
                        reproducibility.ProducerRole.PRODUCER_INDEPENDENT,
                        case.case_ref,
                        case.stratum_ref,
                        reference_realizations[case_index],
                        random_roles[case_index],
                        seed_roles[case_index],
                        hardware,
                        representation,
                        execution,
                        ref(
                            reproducibility.ReproducibilityRefKind.PROVENANCE,
                            f"provenance-{cell_index}",
                        ),
                        ReferenceRunOutcome.SUPPORTED,
                        ReferenceComparisonOutcome.AGREEMENT_WITHIN_REGISTERED_POLICY,
                        reproducibility.EvidenceCellState.OBSERVED,
                        0.5 + cell_index / 10.0,
                        evidence_factors(cell_index),
                    )
                )
    shared_members = {
        reproducibility.SharedDependencyKind.COMMON_CASE: tuple(
            case.case_ref for case in cases
        ),
        reproducibility.SharedDependencyKind.JOINT_REFERENCE_REALIZATION: reference_realizations,
        reproducibility.SharedDependencyKind.COMMON_RANDOM_NUMBERS: random_roles,
        reproducibility.SharedDependencyKind.PAIRED_TRAINING_SEED: seed_roles,
        reproducibility.SharedDependencyKind.HARDWARE_ROLE: (hardware,),
        reproducibility.SharedDependencyKind.REPRESENTATION: (representation,),
        reproducibility.SharedDependencyKind.EXECUTION: (execution,),
        reproducibility.SharedDependencyKind.DATA: (
            ref(reproducibility.ReproducibilityRefKind.EVIDENCE, "data-dependency"),
        ),
        reproducibility.SharedDependencyKind.BACKBONE: (
            ref(reproducibility.ReproducibilityRefKind.EVIDENCE, "backbone-dependency"),
        ),
        reproducibility.SharedDependencyKind.IMPLEMENTATION: (
            ref(
                reproducibility.ReproducibilityRefKind.EVIDENCE,
                "implementation-dependency",
            ),
        ),
    }
    disclosures = tuple(
        reproducibility.DependencyDisclosure(
            ref(
                reproducibility.ReproducibilityRefKind.SHARED_DEPENDENCY,
                f"dependency-{kind.value.casefold().replace('_', '-')}",
            ),
            kind,
            reproducibility.DependencyRelation.SHARED,
            shared_members[kind],
            case_scopes,
            strata,
        )
        for kind in reproducibility.SharedDependencyKind
    )
    return reproducibility.CrossedEvidenceGraph(
        design,
        tuple(cells),
        disclosures,
        (
            reproducibility.VerificationAnchor(
                ref(
                    reproducibility.ReproducibilityRefKind.VERIFICATION_ANCHOR,
                    "manufactured-anchor",
                ),
                True,
                (),
            ),
        ),
        (),
    )


def campaign(graph):
    return reproducibility.ReconstructionCampaignResult(
        graph.design.reconstruction_policy_ref,
        measurement.ReconstructionEvidenceStatus(
            measurement.ReconstructionEvidenceStage.BASE_COMPLETE,
            measurement.ReconstructionEvidenceOutcome.STAGE_ESTABLISHED,
            (),
            None,
        ),
        reproducibility.ScientificOutcome.RESOLVED,
        (),
        None,
        None,
    )


class DecisionProcedure:
    def __init__(
        self,
        graph,
        kind,
        *,
        applicable=True,
        outcome=reproducibility.ScientificOutcome.RESOLVED_SUPERIOR,
    ):
        self.graph = graph
        self.applicable = applicable
        self.calls = 0
        self.qualification = reproducibility.ProcedureQualification(
            kind,
            ref(
                reproducibility.ReproducibilityRefKind.PROCEDURE,
                f"procedure-{kind.value.casefold().replace('_', '-')}",
            ),
            definition(
                measurement.MeasurementDefinitionKind.APPLICABILITY_TEST,
                "applicability-test",
            ),
            definition(
                measurement.MeasurementDefinitionKind.DOSSIER_QUALIFICATION,
                "dossier-qualification",
            ),
            (
                definition(
                    measurement.MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION,
                    "dependence-assumption",
                )
                if kind
                in (
                    reproducibility.ProcedureKind.QUALIFIED_QUADRATURE,
                    reproducibility.ProcedureKind.QUALIFIED_INDEPENDENCE,
                    reproducibility.ProcedureKind.QUALIFIED_ZERO_COVARIANCE,
                )
                else None
            ),
            ref(
                reproducibility.ReproducibilityRefKind.COVERAGE_QUALIFICATION,
                "coverage-qualification",
            ),
            ref(
                reproducibility.ReproducibilityRefKind.POWER_QUALIFICATION,
                "power-qualification",
            ),
            True,
        )
        self.outcome = outcome

    def assess_applicability(self, graph):
        self.calls += 1
        return reproducibility.ProcedureApplicability(
            (
                reproducibility.ApplicabilityStatus.APPLICABLE
                if self.applicable
                else reproducibility.ApplicabilityStatus.NOT_APPLICABLE
            ),
            ref(
                reproducibility.ReproducibilityRefKind.APPLICABILITY_RESULT,
                f"applicability-{self.qualification.procedure_kind.value.casefold().replace('_', '-')}",
            ),
            self.qualification.applicability_test_ref,
            graph.design.incumbent_evidence_ref,
            graph.design.challenger_evidence_ref,
            graph.case_scope_refs,
            graph.stratum_scope_refs,
        )

    def decide(self, graph):
        del graph
        stable = self.outcome in (
            reproducibility.ScientificOutcome.RESOLVED_SUPERIOR,
            reproducibility.ScientificOutcome.RESOLVED_NOT_SUPERIOR,
        )
        return reproducibility.ProcedureDecision(
            (
                reproducibility.DecisionStability.STABLE
                if stable
                else reproducibility.DecisionStability.INDETERMINATE
            ),
            self.outcome,
            -0.2 if stable else None,
            -0.1 if stable else None,
            ref(
                reproducibility.ReproducibilityRefKind.EVIDENCE,
                f"decision-{self.qualification.procedure_kind.value.casefold().replace('_', '-')}",
            ),
        )


def test_crossed_graph_is_full_factorial_stratified_and_dependency_explicit() -> None:
    graph = crossed_graph(uncertainty_policy())
    assert len(graph.cells) == 8
    assert len(graph.design.case_units) == 2
    assert len({cell.reconstruction_ref for cell in graph.cells}) == 4
    assert all(
        {factor.factor_kind for factor in cell.factor_observations}
        == set(reproducibility.REQUIRED_EVIDENCE_FACTORS)
        for cell in graph.cells
    )
    assert {item.dependency_kind for item in graph.dependency_disclosures} == set(
        reproducibility.SharedDependencyKind
    )
    assert len({cell.value for cell in graph.cells}) == len(graph.cells)
    for arm in reproducibility.ComparisonArm:
        arm_cells = tuple(cell for cell in graph.cells if cell.arm is arm)
        assert (
            len({(cell.reconstruction_ref, cell.case_ref) for cell in arm_cells}) == 4
        )
        assert len({cell.stratum_ref for cell in arm_cells}) == 2

    with pytest.raises(reproducibility.ReproducibilityValidationError) as exc_info:
        replace(graph, dependency_disclosures=graph.dependency_disclosures[1:])
    assert (
        exc_info.value.code
        is reproducibility.ReproducibilityErrorCode.DEPENDENCY_UNDISCLOSED
    )


def test_crossed_graph_and_factor_canonicalization_are_order_invariant() -> None:
    graph = crossed_graph(uncertainty_policy())
    reversed_cells = tuple(
        replace(cell, factor_observations=tuple(reversed(cell.factor_observations)))
        for cell in reversed(graph.cells)
    )
    reordered = reproducibility.CrossedEvidenceGraph(
        graph.design,
        reversed_cells,
        tuple(reversed(graph.dependency_disclosures)),
        tuple(reversed(graph.verification_anchors)),
        tuple(reversed(graph.unresolved_claims)),
    )
    assert reordered == graph
    assert reproducibility.canonical_bytes(
        reordered
    ) == reproducibility.canonical_bytes(graph)


def test_r2_prefers_joint_then_conservative_and_never_defaults_to_quadrature() -> None:
    policy = uncertainty_policy()
    graph = crossed_graph(policy)
    joint = DecisionProcedure(
        graph, reproducibility.ProcedureKind.JOINT_PROPAGATION, applicable=False
    )
    conservative = DecisionProcedure(
        graph, reproducibility.ProcedureKind.CONSERVATIVE_BOUND
    )
    result = reproducibility.evaluate_r2(
        graph, policy, campaign(graph), (conservative, joint)
    )
    assert result.procedure_kind is reproducibility.ProcedureKind.CONSERVATIVE_BOUND
    assert (
        result.scientific_outcome is reproducibility.ScientificOutcome.RESOLVED_SUPERIOR
    )
    assert joint.calls == conservative.calls == 1

    unqualified_quadrature = DecisionProcedure(
        graph, reproducibility.ProcedureKind.QUALIFIED_QUADRATURE
    )
    result = reproducibility.evaluate_r2(
        graph, policy, campaign(graph), (unqualified_quadrature,)
    )
    assert (
        result.scientific_outcome
        is reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE
    )
    assert unqualified_quadrature.calls == 0


def test_r2_accepts_only_an_exact_b05_qualified_shortcut() -> None:
    policy = uncertainty_policy(
        shortcut_kind=measurement.DependenceShortcutKind.QUADRATURE
    )
    graph = crossed_graph(policy)
    quadrature = DecisionProcedure(
        graph, reproducibility.ProcedureKind.QUALIFIED_QUADRATURE
    )
    result = reproducibility.evaluate_r2(graph, policy, campaign(graph), (quadrature,))
    assert result.procedure_kind is reproducibility.ProcedureKind.QUALIFIED_QUADRATURE
    assert quadrature.calls == 1

    mismatched = DecisionProcedure(
        graph, reproducibility.ProcedureKind.QUALIFIED_QUADRATURE
    )
    mismatched.qualification = replace(
        mismatched.qualification,
        dependence_assumption_ref=definition(
            measurement.MeasurementDefinitionKind.DEPENDENCE_ASSUMPTION,
            "different-dependence-assumption",
        ),
    )
    result = reproducibility.evaluate_r2(graph, policy, campaign(graph), (mismatched,))
    assert (
        result.scientific_outcome
        is reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE
    )
    assert mismatched.calls == 0


def test_r2_null_coverage_and_power_fixture_outcomes_remain_typed() -> None:
    policy = uncertainty_policy()
    graph = crossed_graph(policy)
    null_procedure = DecisionProcedure(
        graph,
        reproducibility.ProcedureKind.JOINT_PROPAGATION,
        outcome=reproducibility.ScientificOutcome.RESOLVED_NOT_SUPERIOR,
    )
    result = reproducibility.evaluate_r2(
        graph, policy, campaign(graph), (null_procedure,)
    )
    assert (
        result.scientific_outcome
        is reproducibility.ScientificOutcome.RESOLVED_NOT_SUPERIOR
    )
    assert result.stability is reproducibility.DecisionStability.STABLE
    assert (
        null_procedure.qualification.coverage_qualification_ref.ref_kind
        is reproducibility.ReproducibilityRefKind.COVERAGE_QUALIFICATION
    )
    assert (
        null_procedure.qualification.power_qualification_ref.ref_kind
        is reproducibility.ReproducibilityRefKind.POWER_QUALIFICATION
    )

    no_qualified_procedure = reproducibility.evaluate_r2(
        graph, policy, campaign(graph), ()
    )
    assert (
        no_qualified_procedure.scientific_outcome
        is reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE
    )
    assert no_qualified_procedure.interval_lower is None
    assert no_qualified_procedure.interval_upper is None
    assert not hasattr(no_qualified_procedure, "rank")
    assert not hasattr(no_qualified_procedure, "frontier_event")


@pytest.mark.parametrize(
    ("run_outcome", "comparison_outcome", "expected"),
    (
        (
            ReferenceRunOutcome.NUMERICAL_FAILURE,
            None,
            reproducibility.ScientificOutcome.REFERENCE_FAILED,
        ),
        (
            ReferenceRunOutcome.SUPPORTED,
            ReferenceComparisonOutcome.CONTESTED_DISAGREEMENT,
            reproducibility.ScientificOutcome.REFERENCE_DISAGREEMENT,
        ),
        (
            ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED,
            None,
            reproducibility.ScientificOutcome.REFERENCE_UNCERTAIN,
        ),
        (
            ReferenceRunOutcome.NOT_APPLICABLE,
            None,
            reproducibility.ScientificOutcome.REFERENCE_NOT_APPLICABLE,
        ),
        (
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
            None,
            reproducibility.ScientificOutcome.INFRASTRUCTURE_FAILED,
        ),
    ),
)
def test_r2_preserves_b04_typed_reference_outcomes(
    run_outcome, comparison_outcome, expected
) -> None:
    policy = uncertainty_policy()
    graph = crossed_graph(policy)
    changed_cell = replace(
        graph.cells[0],
        reference_run_outcome=run_outcome,
        reference_comparison_outcome=comparison_outcome,
    )
    changed = replace(graph, cells=(changed_cell, *graph.cells[1:]))
    result = reproducibility.evaluate_r2(
        changed,
        policy,
        campaign(changed),
        (DecisionProcedure(changed, reproducibility.ProcedureKind.JOINT_PROPAGATION),),
    )
    assert result.scientific_outcome is expected


def test_missing_censored_and_unresolved_anchor_evidence_fail_closed() -> None:
    policy = uncertainty_policy()
    graph = crossed_graph(policy)
    reason = ref(reproducibility.ReproducibilityRefKind.REASON, "missing-reason")
    missing_cell = replace(
        graph.cells[0],
        state=reproducibility.EvidenceCellState.MISSING,
        value=None,
        factor_observations=(),
        reason_ref=reason,
    )
    missing = replace(graph, cells=(missing_cell, *graph.cells[1:]))
    procedure = DecisionProcedure(
        missing, reproducibility.ProcedureKind.JOINT_PROPAGATION
    )
    assert (
        reproducibility.evaluate_r2(
            missing, policy, campaign(missing), (procedure,)
        ).scientific_outcome
        is reproducibility.ScientificOutcome.RESOLVED_SUPERIOR
    )

    unresolved = replace(
        graph,
        verification_anchors=(
            reproducibility.VerificationAnchor(
                ref(
                    reproducibility.ReproducibilityRefKind.VERIFICATION_ANCHOR,
                    "unresolved-anchor",
                ),
                True,
                (reproducibility.UnresolvedClaimKind.POPULATION_ADEQUACY,),
            ),
        ),
    )
    result = reproducibility.evaluate_r2(
        unresolved,
        policy,
        campaign(unresolved),
        (
            DecisionProcedure(
                unresolved, reproducibility.ProcedureKind.JOINT_PROPAGATION
            ),
        ),
    )
    assert (
        result.scientific_outcome
        is reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE
    )

    unbound_policy = replace(
        policy,
        censoring_accounting_binding=measurement.UncertaintyComponentBinding(
            measurement.ScientificValueState.HUMAN_INPUT
        ),
    )
    unbound_graph = crossed_graph(unbound_policy)
    missing_cell = replace(
        unbound_graph.cells[0],
        state=reproducibility.EvidenceCellState.CENSORED,
        value=None,
        factor_observations=(),
        reason_ref=reason,
    )
    unbound_missing = replace(
        unbound_graph, cells=(missing_cell, *unbound_graph.cells[1:])
    )
    result = reproducibility.evaluate_r2(
        unbound_missing,
        unbound_policy,
        campaign(unbound_missing),
        (
            DecisionProcedure(
                unbound_missing, reproducibility.ProcedureKind.JOINT_PROPAGATION
            ),
        ),
    )
    assert (
        result.scientific_outcome
        is reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    (
        (
            reproducibility.EvidenceCellState.RECONSTRUCTION_FAILED,
            reproducibility.ScientificOutcome.RECONSTRUCTION_FAILED,
        ),
        (
            reproducibility.EvidenceCellState.MEASUREMENT_UNRESOLVED,
            reproducibility.ScientificOutcome.MEASUREMENT_UNRESOLVED,
        ),
        (
            reproducibility.EvidenceCellState.INFRASTRUCTURE_FAILED,
            reproducibility.ScientificOutcome.INFRASTRUCTURE_FAILED,
        ),
    ),
)
def test_cell_failure_classes_cannot_manufacture_candidate_evidence(
    state, expected
) -> None:
    policy = uncertainty_policy()
    graph = crossed_graph(policy)
    changed_cell = replace(
        graph.cells[0],
        state=state,
        value=None,
        factor_observations=(),
        reason_ref=ref(
            reproducibility.ReproducibilityRefKind.REASON,
            f"reason-{state.value.casefold().replace('_', '-')}",
        ),
    )
    changed = replace(graph, cells=(changed_cell, *graph.cells[1:]))
    result = reproducibility.evaluate_r2(
        changed,
        policy,
        campaign(changed),
        (DecisionProcedure(changed, reproducibility.ProcedureKind.JOINT_PROPAGATION),),
    )
    assert result.scientific_outcome is expected
    assert result.stability is reproducibility.DecisionStability.INDETERMINATE
    assert result.procedure_ref is None


def test_r2_rejects_wrong_policy_provenance_and_unresolved_intervals() -> None:
    policy = uncertainty_policy()
    graph = crossed_graph(policy)
    other_reconstruction = measurement.ReconstructionEvidencePolicyRef(KEY, DIGEST_B)
    mismatched_campaign = replace(campaign(graph), policy_ref=other_reconstruction)
    result = reproducibility.evaluate_r2(
        graph,
        policy,
        mismatched_campaign,
        (DecisionProcedure(graph, reproducibility.ProcedureKind.JOINT_PROPAGATION),),
    )
    assert (
        result.scientific_outcome
        is reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE
    )

    with pytest.raises(reproducibility.ReproducibilityValidationError):
        reproducibility.ProcedureDecision(
            reproducibility.DecisionStability.INDETERMINATE,
            reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE,
            -0.1,
            0.1,
            ref(reproducibility.ReproducibilityRefKind.EVIDENCE, "crossing-interval"),
        )


def test_cross_challenge_provenance_and_hostile_container_inputs_fail_closed() -> None:
    graph = crossed_graph(uncertainty_policy())
    other_key = ChallengeKey("fixture-other", "1.0")
    bad_provenance = reproducibility.ReproducibilityRef(
        other_key,
        reproducibility.ReproducibilityRefKind.PROVENANCE,
        "other-provenance",
        "1.0",
        DIGEST_A,
    )
    with pytest.raises(reproducibility.ReproducibilityValidationError):
        replace(graph.cells[0], provenance_ref=bad_provenance)
    with pytest.raises(TypeError):
        reproducibility.evaluate_r2(graph, uncertainty_policy(), campaign(graph), [])


def complete_evidence(policy, *, stop_kind=measurement.ReconstructionStopKind.NONE):
    plan_ref = ResolvedConstructionPlanRef(KEY, content_digest=DIGEST_A)
    build = CompleteBuild(
        CompleteBuildIdentity(
            KEY,
            plan_ref,
            ResearchResourcePolicyRef(
                KEY, "resource-policy", "1.0", content_digest=DIGEST_A
            ),
            ResourceClassRef(KEY, "resource-class", "1.0", content_digest=DIGEST_A),
            EnvironmentPin("fixture-environment", "1.0", DIGEST_A),
            "fixture-build",
            DIGEST_A,
        )
    )
    facts = measurement.ReconstructionResourceFacts(
        build,
        NoReuse(),
        ReplicateNotApplicable(
            ReplicateNotApplicableReason.NOT_A_RECONSTRUCTION_REPLICATE
        ),
        ResourceStopCause.COMPLETED_RESOURCE_ACCOUNTING,
        None,
        None,
        None,
    )
    failure_ref = (
        definition(
            measurement.MeasurementDefinitionKind.RECONSTRUCTION_EXECUTION_FAILURE,
            "reconstruction-failure",
        )
        if stop_kind
        is measurement.ReconstructionStopKind.RECONSTRUCTION_EXECUTION_FAILURE
        else None
    )
    return measurement.ReconstructionEvidenceInput(
        measurement.measurement_ref(policy),
        policy.construction_family_ref,
        facts,
        definition(
            measurement.MeasurementDefinitionKind.COMPLETE_BASE_EVIDENCE,
            "complete-base-evidence",
        ),
        None,
        None,
        None,
        (),
        stop_kind,
        failure_ref,
    )


def stage(stage, state):
    return reproducibility.ReconstructionStageEvent(
        stage,
        state,
        (
            ref(
                reproducibility.ReproducibilityRefKind.EVIDENCE,
                f"stage-{stage.value.casefold().replace('_', '-')}",
            ),
        ),
    )


def test_reconstruction_audit_separates_base_evidence_from_heuristic_stopping() -> None:
    policy = reconstruction_policy()
    events = (
        stage(
            reproducibility.ReconstructionAuditStage.STATIC_ADMISSION,
            reproducibility.AuditStageState.SATISFIED,
        ),
        stage(
            reproducibility.ReconstructionAuditStage.COMPLETE_BASE,
            reproducibility.AuditStageState.SATISFIED,
        ),
    )
    result = reproducibility.audit_reconstruction_campaign(
        policy, complete_evidence(policy), events
    )
    assert result.scientific_outcome is reproducibility.ScientificOutcome.RESOLVED
    assert result.policy_ref == measurement.measurement_ref(policy)

    heuristic = stage(
        reproducibility.ReconstructionAuditStage.HEURISTIC_FUTILITY,
        reproducibility.AuditStageState.STOP_REQUESTED,
    )
    stopped = reproducibility.audit_reconstruction_campaign(
        policy, complete_evidence(policy), (*events, heuristic)
    )
    assert (
        stopped.scientific_outcome
        is reproducibility.ScientificOutcome.EVIDENCE_DEFERRED
    )

    pre_base = replace(complete_evidence(policy), complete_base_evidence_ref=None)
    pre_base_stop = reproducibility.audit_reconstruction_campaign(
        policy, pre_base, (heuristic,)
    )
    assert (
        pre_base_stop.scientific_outcome
        is reproducibility.ScientificOutcome.EVIDENCE_DEFERRED
    )


def test_reconstruction_audit_preserves_every_distinct_stage_record() -> None:
    policy = reconstruction_policy()
    events = tuple(
        stage(
            stage_kind,
            (
                reproducibility.AuditStageState.STOP_REQUESTED
                if stage_kind
                is reproducibility.ReconstructionAuditStage.HEURISTIC_FUTILITY
                else reproducibility.AuditStageState.SATISFIED
            ),
        )
        for stage_kind in reversed(tuple(reproducibility.ReconstructionAuditStage))
    )
    result = reproducibility.audit_reconstruction_campaign(
        policy, complete_evidence(policy), events
    )
    assert {event.stage for event in result.stage_events} == set(
        reproducibility.ReconstructionAuditStage
    )
    assert (
        result.scientific_outcome is reproducibility.ScientificOutcome.EVIDENCE_DEFERRED
    )


def test_reconstruction_execution_failure_remains_typed() -> None:
    policy = reconstruction_policy()
    result = reproducibility.audit_reconstruction_campaign(
        policy,
        complete_evidence(
            policy,
            stop_kind=measurement.ReconstructionStopKind.RECONSTRUCTION_EXECUTION_FAILURE,
        ),
        (),
    )
    assert (
        result.scientific_outcome
        is reproducibility.ScientificOutcome.RECONSTRUCTION_FAILED
    )


class SequentialProcedure:
    def __init__(self, policy, action):
        self.action = action
        self.qualification = reproducibility.ScientificStoppingQualification(
            ref(
                reproducibility.ReproducibilityRefKind.PROCEDURE, "sequential-procedure"
            ),
            policy.scientific_stopping_rule_binding.component_ref,
            ref(
                reproducibility.ReproducibilityRefKind.COVERAGE_QUALIFICATION,
                "sequential-coverage",
            ),
            policy.error_control_binding.component_ref,
            True,
        )

    def decide(self, evidence, stage_events):
        del evidence, stage_events
        return reproducibility.ScientificStoppingDecision(
            self.action,
            ref(
                reproducibility.ReproducibilityRefKind.EVIDENCE,
                f"sequential-{self.action.value.casefold().replace('_', '-')}",
            ),
        )


@pytest.mark.parametrize(
    ("action", "expected"),
    (
        (
            reproducibility.ScientificSequentialAction.CONTINUE_EXTENSION,
            reproducibility.ScientificOutcome.EVIDENCE_DEFERRED,
        ),
        (
            reproducibility.ScientificSequentialAction.STOP_RESOLVED,
            reproducibility.ScientificOutcome.RESOLVED,
        ),
        (
            reproducibility.ScientificSequentialAction.EXHAUSTED_INDETERMINATE,
            reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE,
        ),
    ),
)
def test_scientific_sequential_stopping_is_qualified_and_typed(
    action, expected
) -> None:
    policy = reconstruction_policy()
    events = (
        stage(
            reproducibility.ReconstructionAuditStage.SCIENTIFIC_SEQUENTIAL,
            reproducibility.AuditStageState.SATISFIED,
        ),
        stage(
            reproducibility.ReconstructionAuditStage.COMPLETE_BASE,
            reproducibility.AuditStageState.SATISFIED,
        ),
        stage(
            reproducibility.ReconstructionAuditStage.STATIC_ADMISSION,
            reproducibility.AuditStageState.SATISFIED,
        ),
    )
    result = reproducibility.audit_reconstruction_campaign(
        policy,
        complete_evidence(policy),
        events,
        SequentialProcedure(policy, action),
    )
    assert result.scientific_outcome is expected
    assert result.sequential_action is action
    assert tuple(event.stage for event in result.stage_events) == tuple(
        sorted(
            (event.stage for event in events),
            key=lambda item: list(reproducibility.ReconstructionAuditStage).index(item),
        )
    )


def test_missing_scientific_stopping_authority_fails_closed() -> None:
    policy = reconstruction_policy()
    events = (
        stage(
            reproducibility.ReconstructionAuditStage.STATIC_ADMISSION,
            reproducibility.AuditStageState.SATISFIED,
        ),
        stage(
            reproducibility.ReconstructionAuditStage.COMPLETE_BASE,
            reproducibility.AuditStageState.SATISFIED,
        ),
        stage(
            reproducibility.ReconstructionAuditStage.SCIENTIFIC_SEQUENTIAL,
            reproducibility.AuditStageState.SATISFIED,
        ),
    )
    result = reproducibility.audit_reconstruction_campaign(
        policy, complete_evidence(policy), events
    )
    assert (
        result.scientific_outcome
        is reproducibility.ScientificOutcome.UNRESOLVED_INDETERMINATE
    )
