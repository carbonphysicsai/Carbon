"""Injected R0/R1/R2 and staged-evidence fixture harnesses."""

from __future__ import annotations

from dataclasses import fields
from typing import Protocol

from carbon.evaluation import ReferenceComparisonOutcome, ReferenceRunOutcome
from carbon.measurement import (
    ReconstructionEvidenceInput,
    ReconstructionEvidenceOutcome,
    ReconstructionEvidencePolicy,
    ReconstructionEvidenceStage,
    ScientificValueState,
    UncertaintyPolicy,
    assess_reconstruction_evidence,
    measurement_ref,
)

from .enums import (
    ApplicabilityStatus,
    AuditStageState,
    BackendProfileSupport,
    DecisionStability,
    EvidenceCellState,
    EvidenceFactorState,
    ProcedureKind,
    R0Outcome,
    R1Outcome,
    ReconstructionAuditStage,
    ScientificOutcome,
    ScientificSequentialAction,
)
from .model import (
    CrossedEvidenceGraph,
    ExactIdentityManifest,
    NumericalProcedureDecision,
    NumericalProcedureQualification,
    NumericalRunCapture,
    ProcedureApplicability,
    ProcedureDecision,
    ProcedureQualification,
    R0Result,
    R1Result,
    R2Result,
    ReconstructionCampaignResult,
    ReconstructionStageEvent,
    ScientificStoppingDecision,
    ScientificStoppingQualification,
)


class NumericalComparisonProcedure(Protocol):
    qualification: NumericalProcedureQualification

    def compare(
        self, first: NumericalRunCapture, second: NumericalRunCapture
    ) -> NumericalProcedureDecision: ...


class DecisionProcedure(Protocol):
    qualification: ProcedureQualification

    def assess_applicability(
        self, graph: CrossedEvidenceGraph
    ) -> ProcedureApplicability: ...

    def decide(self, graph: CrossedEvidenceGraph) -> ProcedureDecision: ...


class ScientificStoppingProcedure(Protocol):
    qualification: ScientificStoppingQualification

    def decide(
        self,
        evidence: ReconstructionEvidenceInput,
        stage_events: tuple[ReconstructionStageEvent, ...],
    ) -> ScientificStoppingDecision: ...


def compare_r0(first: ExactIdentityManifest, second: ExactIdentityManifest) -> R0Result:
    if (
        type(first) is not ExactIdentityManifest
        or type(second) is not ExactIdentityManifest
    ):
        raise TypeError("R0 requires exact identity manifests")
    ignored = {"schema_version", "canonicalization_profile"}
    mismatches = tuple(
        sorted(
            field.name
            for field in fields(ExactIdentityManifest)
            if field.name not in ignored
            and getattr(first, field.name) != getattr(second, field.name)
        )
    )
    return R0Result(
        R0Outcome.EXACT_MATCH if not mismatches else R0Outcome.IDENTITY_MISMATCH,
        mismatches,
    )


def compare_r1(
    first: NumericalRunCapture,
    second: NumericalRunCapture,
    procedure: NumericalComparisonProcedure | None,
) -> R1Result:
    if (
        type(first) is not NumericalRunCapture
        or type(second) is not NumericalRunCapture
    ):
        raise TypeError("R1 requires exact numerical run captures")
    r0_result = compare_r0(first.identity, second.identity)
    if r0_result.outcome is not R0Outcome.EXACT_MATCH:
        return R1Result(R1Outcome.R0_IDENTITY_MISMATCH, r0_result, (), None, None)
    if first.identity.backend_support is not BackendProfileSupport.SUPPORTED:
        return R1Result(R1Outcome.BACKEND_UNSUPPORTED, r0_result, (), None, None)
    if procedure is None:
        return R1Result(R1Outcome.INDETERMINATE, r0_result, (), None, None)
    try:
        qualification = procedure.qualification
        if type(qualification) is not NumericalProcedureQualification:
            return R1Result(R1Outcome.INDETERMINATE, r0_result, (), None, None)
        if (
            qualification.backend_profile_ref != first.identity.backend_profile_ref
            or qualification.procedure_ref.challenge_key != first.identity.challenge_key
        ):
            return R1Result(R1Outcome.INDETERMINATE, r0_result, (), None, None)
        if {item.output_ref for item in first.outputs} != {
            item.output_ref for item in second.outputs
        }:
            return R1Result(R1Outcome.INDETERMINATE, r0_result, (), None, None)
        decision = procedure.compare(first, second)
        if type(decision) is not NumericalProcedureDecision:
            return R1Result(R1Outcome.INDETERMINATE, r0_result, (), None, None)
        expected_outputs = {item.output_ref for item in first.outputs}
        if (
            {item.output_ref for item in decision.deltas} != expected_outputs
            or decision.decision_ref.challenge_key != first.identity.challenge_key
        ):
            return R1Result(R1Outcome.INDETERMINATE, r0_result, (), None, None)
        return R1Result(
            decision.outcome,
            r0_result,
            decision.deltas,
            qualification.procedure_ref,
            decision.decision_ref,
        )
    except Exception:  # noqa: BLE001 -- injected fixture procedures are untrusted
        return R1Result(R1Outcome.INFRASTRUCTURE_FAILED, r0_result, (), None, None)


_CELL_FAILURE_PRECEDENCE = (
    (EvidenceCellState.INFRASTRUCTURE_FAILED, ScientificOutcome.INFRASTRUCTURE_FAILED),
    (EvidenceCellState.RECONSTRUCTION_FAILED, ScientificOutcome.RECONSTRUCTION_FAILED),
    (
        EvidenceCellState.MEASUREMENT_UNRESOLVED,
        ScientificOutcome.MEASUREMENT_UNRESOLVED,
    ),
)

_REFERENCE_RUN_OUTCOME_MAP = {
    ReferenceRunOutcome.INFRASTRUCTURE_FAILURE: ScientificOutcome.INFRASTRUCTURE_FAILED,
    ReferenceRunOutcome.NUMERICAL_FAILURE: ScientificOutcome.REFERENCE_FAILED,
    ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE: ScientificOutcome.REFERENCE_FAILED,
    ReferenceRunOutcome.NOT_APPLICABLE: ScientificOutcome.REFERENCE_NOT_APPLICABLE,
    ReferenceRunOutcome.UNSUPPORTED: ScientificOutcome.REFERENCE_NOT_APPLICABLE,
    ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED: ScientificOutcome.REFERENCE_UNCERTAIN,
    ReferenceRunOutcome.CONDITIONING_UNRESOLVED: ScientificOutcome.REFERENCE_UNCERTAIN,
    ReferenceRunOutcome.APPLICABILITY_UNRESOLVED: ScientificOutcome.REFERENCE_UNCERTAIN,
    ReferenceRunOutcome.CANCELLED: ScientificOutcome.REFERENCE_UNCERTAIN,
}

_REFERENCE_COMPARISON_OUTCOME_MAP = {
    ReferenceComparisonOutcome.CONTESTED_DISAGREEMENT: (
        ScientificOutcome.REFERENCE_DISAGREEMENT
    ),
    ReferenceComparisonOutcome.COMPARISON_INDETERMINATE: (
        ScientificOutcome.REFERENCE_UNCERTAIN
    ),
}


def _unresolved(outcome: ScientificOutcome) -> R2Result:
    return R2Result(DecisionStability.INDETERMINATE, outcome, None, None, None, None)


def _procedure_priority(kind: ProcedureKind) -> int:
    if kind is ProcedureKind.JOINT_PROPAGATION:
        return 0
    if kind is ProcedureKind.CONSERVATIVE_BOUND:
        return 1
    return 2


def _applicability_matches(
    graph: CrossedEvidenceGraph,
    qualification: ProcedureQualification,
    applicability: ProcedureApplicability,
) -> bool:
    return (
        applicability.applicability_test_ref == qualification.applicability_test_ref
        and applicability.incumbent_evidence_ref == graph.design.incumbent_evidence_ref
        and applicability.challenger_evidence_ref
        == graph.design.challenger_evidence_ref
        and applicability.case_scope_refs == graph.case_scope_refs
        and applicability.stratum_scope_refs == graph.stratum_scope_refs
        and applicability.result_ref.challenge_key == graph.design.challenge_key
    )


def _shortcut_is_qualified(
    graph: CrossedEvidenceGraph,
    policy: UncertaintyPolicy,
    qualification: ProcedureQualification,
) -> bool:
    shortcut_kind = qualification.shortcut_kind
    if shortcut_kind is None:
        return True
    return any(
        shortcut.shortcut_kind is shortcut_kind
        and shortcut.incumbent_evidence_ref == graph.design.incumbent_evidence_ref
        and shortcut.challenger_evidence_ref == graph.design.challenger_evidence_ref
        and shortcut.case_scope_refs == graph.case_scope_refs
        and shortcut.stratum_scope_refs == graph.stratum_scope_refs
        and shortcut.applicability_test_ref == qualification.applicability_test_ref
        and shortcut.dossier_qualification_ref
        == qualification.dossier_qualification_ref
        and shortcut.assumption_ref == qualification.dependence_assumption_ref
        and shortcut.fixture_origin
        for shortcut in policy.dependence_shortcuts
    )


def evaluate_r2(
    graph: CrossedEvidenceGraph,
    uncertainty_policy: UncertaintyPolicy,
    reconstruction_campaign: ReconstructionCampaignResult,
    procedures: tuple[DecisionProcedure, ...],
) -> R2Result:
    if type(graph) is not CrossedEvidenceGraph:
        raise TypeError("R2 requires an exact crossed evidence graph")
    if type(uncertainty_policy) is not UncertaintyPolicy:
        raise TypeError("R2 requires an exact B-05 uncertainty policy")
    if type(reconstruction_campaign) is not ReconstructionCampaignResult:
        raise TypeError("R2 requires an exact reconstruction campaign result")
    if type(procedures) is not tuple:
        raise TypeError("R2 procedures must be an exact tuple")
    if measurement_ref(uncertainty_policy) != graph.design.uncertainty_policy_ref:
        return _unresolved(ScientificOutcome.UNRESOLVED_INDETERMINATE)
    if reconstruction_campaign.policy_ref != graph.design.reconstruction_policy_ref:
        return _unresolved(ScientificOutcome.UNRESOLVED_INDETERMINATE)

    campaign_outcome = reconstruction_campaign.scientific_outcome
    if campaign_outcome is not ScientificOutcome.RESOLVED:
        return _unresolved(campaign_outcome)
    for cell_state, outcome in _CELL_FAILURE_PRECEDENCE:
        if any(cell.state is cell_state for cell in graph.cells):
            return _unresolved(outcome)
    for cell in graph.cells:
        reference_outcome = _REFERENCE_RUN_OUTCOME_MAP.get(cell.reference_run_outcome)
        if reference_outcome is not None:
            return _unresolved(reference_outcome)
        if cell.reference_comparison_outcome is not None:
            comparison_outcome = _REFERENCE_COMPARISON_OUTCOME_MAP.get(
                cell.reference_comparison_outcome
            )
            if comparison_outcome is not None:
                return _unresolved(comparison_outcome)
    if graph.unresolved_claims:
        return _unresolved(ScientificOutcome.UNRESOLVED_INDETERMINATE)
    has_missing_or_censored = any(
        cell.state in (EvidenceCellState.MISSING, EvidenceCellState.CENSORED)
        for cell in graph.cells
    )
    if has_missing_or_censored and (
        uncertainty_policy.censoring_accounting_binding.state
        is not ScientificValueState.BOUND
    ):
        return _unresolved(ScientificOutcome.UNRESOLVED_INDETERMINATE)
    if any(
        factor.state in (EvidenceFactorState.UNRESOLVED, EvidenceFactorState.FAILED)
        for cell in graph.cells
        for factor in cell.factor_observations
    ):
        return _unresolved(ScientificOutcome.UNRESOLVED_INDETERMINATE)
    if not uncertainty_policy.has_complete_score_authority:
        return _unresolved(ScientificOutcome.UNRESOLVED_INDETERMINATE)

    candidates: list[tuple[int, str, DecisionProcedure]] = []
    try:
        for procedure in procedures:
            qualification = procedure.qualification
            if type(qualification) is not ProcedureQualification:
                continue
            candidates.append(
                (
                    _procedure_priority(qualification.procedure_kind),
                    qualification.procedure_ref.content_digest,
                    procedure,
                )
            )
    except Exception:  # noqa: BLE001 -- injected fixture procedures are untrusted
        return _unresolved(ScientificOutcome.INFRASTRUCTURE_FAILED)

    for _, __, procedure in sorted(candidates, key=lambda item: item[:2]):
        try:
            qualification = procedure.qualification
            if qualification.procedure_ref.challenge_key != graph.design.challenge_key:
                continue
            if not _shortcut_is_qualified(graph, uncertainty_policy, qualification):
                continue
            applicability = procedure.assess_applicability(graph)
            if type(applicability) is not ProcedureApplicability:
                continue
            if (
                applicability.status is not ApplicabilityStatus.APPLICABLE
                or not _applicability_matches(graph, qualification, applicability)
            ):
                continue
            decision = procedure.decide(graph)
            if type(decision) is not ProcedureDecision:
                continue
            if decision.decision_ref.challenge_key != graph.design.challenge_key:
                continue
            if decision.scientific_outcome not in (
                ScientificOutcome.RESOLVED_SUPERIOR,
                ScientificOutcome.RESOLVED_NOT_SUPERIOR,
                ScientificOutcome.UNRESOLVED_INDETERMINATE,
            ):
                continue
            return R2Result(
                decision.stability,
                decision.scientific_outcome,
                qualification.procedure_kind,
                qualification.procedure_ref,
                applicability.result_ref,
                decision.decision_ref,
                decision.interval_lower,
                decision.interval_upper,
            )
        except Exception:  # noqa: BLE001 -- injected fixture procedures are untrusted
            return _unresolved(ScientificOutcome.INFRASTRUCTURE_FAILED)
    return _unresolved(ScientificOutcome.UNRESOLVED_INDETERMINATE)


def _stage_event(
    stage_events: tuple[ReconstructionStageEvent, ...],
    stage: ReconstructionAuditStage,
) -> ReconstructionStageEvent | None:
    return next((item for item in stage_events if item.stage is stage), None)


def audit_reconstruction_campaign(
    policy: ReconstructionEvidencePolicy,
    evidence: ReconstructionEvidenceInput,
    stage_events: tuple[ReconstructionStageEvent, ...],
    scientific_stopping_procedure: ScientificStoppingProcedure | None = None,
) -> ReconstructionCampaignResult:
    if type(policy) is not ReconstructionEvidencePolicy:
        raise TypeError("campaign audit requires an exact B-05 policy")
    if type(evidence) is not ReconstructionEvidenceInput:
        raise TypeError("campaign audit requires exact B-05 evidence")
    if type(stage_events) is not tuple or any(
        type(item) is not ReconstructionStageEvent for item in stage_events
    ):
        raise TypeError("campaign audit stage events must be exact")
    if len({item.stage for item in stage_events}) != len(stage_events):
        raise ValueError("campaign audit stages must be unique")
    for item in stage_events:
        if any(ref.challenge_key != policy.challenge_key for ref in item.evidence_refs):
            raise ValueError("campaign audit evidence is cross-Challenge")
    ordered_events = tuple(
        sorted(
            stage_events,
            key=lambda item: list(ReconstructionAuditStage).index(item.stage),
        )
    )
    status = assess_reconstruction_evidence(policy, evidence)
    policy_ref = measurement_ref(policy)
    direct_outcomes = {
        ReconstructionEvidenceOutcome.INFRASTRUCTURE_FAILURE: (
            ScientificOutcome.INFRASTRUCTURE_FAILED
        ),
        ReconstructionEvidenceOutcome.RECONSTRUCTION_FAILURE: (
            ScientificOutcome.RECONSTRUCTION_FAILED
        ),
        ReconstructionEvidenceOutcome.INDETERMINATE_INSUFFICIENT_EVIDENCE: (
            ScientificOutcome.UNRESOLVED_INDETERMINATE
        ),
    }
    if status.outcome in direct_outcomes:
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            direct_outcomes[status.outcome],
            ordered_events,
            None,
            None,
        )
    static = _stage_event(ordered_events, ReconstructionAuditStage.STATIC_ADMISSION)
    if static is None or static.state is not AuditStageState.SATISFIED:
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            ScientificOutcome.EVIDENCE_DEFERRED,
            ordered_events,
            None,
            None,
        )
    if status.stage is ReconstructionEvidenceStage.BASE_REQUIRED:
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            ScientificOutcome.EVIDENCE_DEFERRED,
            ordered_events,
            None,
            None,
        )
    heuristic = _stage_event(
        ordered_events, ReconstructionAuditStage.HEURISTIC_FUTILITY
    )
    if heuristic is not None and heuristic.state is AuditStageState.STOP_REQUESTED:
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            ScientificOutcome.EVIDENCE_DEFERRED,
            ordered_events,
            None,
            None,
        )
    base = _stage_event(ordered_events, ReconstructionAuditStage.COMPLETE_BASE)
    if base is None or base.state is not AuditStageState.SATISFIED:
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            ScientificOutcome.EVIDENCE_DEFERRED,
            ordered_events,
            None,
            None,
        )
    sequential = _stage_event(
        ordered_events, ReconstructionAuditStage.SCIENTIFIC_SEQUENTIAL
    )
    if sequential is None:
        if status.outcome is ReconstructionEvidenceOutcome.STAGE_ESTABLISHED:
            return ReconstructionCampaignResult(
                policy_ref,
                status,
                ScientificOutcome.RESOLVED,
                ordered_events,
                None,
                None,
            )
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            ScientificOutcome.EVIDENCE_DEFERRED,
            ordered_events,
            None,
            None,
        )
    if sequential.state is not AuditStageState.SATISFIED:
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            ScientificOutcome.EVIDENCE_DEFERRED,
            ordered_events,
            None,
            None,
        )
    if scientific_stopping_procedure is None:
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            ScientificOutcome.UNRESOLVED_INDETERMINATE,
            ordered_events,
            None,
            None,
        )
    try:
        qualification = scientific_stopping_procedure.qualification
        stopping_ref = policy.scientific_stopping_rule_binding.component_ref
        error_ref = policy.error_control_binding.component_ref
        if (
            type(qualification) is not ScientificStoppingQualification
            or stopping_ref is None
            or error_ref is None
            or qualification.stopping_rule_ref != stopping_ref
            or qualification.error_control_ref != error_ref
            or qualification.procedure_ref.challenge_key != policy.challenge_key
        ):
            return ReconstructionCampaignResult(
                policy_ref,
                status,
                ScientificOutcome.UNRESOLVED_INDETERMINATE,
                ordered_events,
                None,
                None,
            )
        decision = scientific_stopping_procedure.decide(evidence, ordered_events)
        if type(decision) is not ScientificStoppingDecision:
            return ReconstructionCampaignResult(
                policy_ref,
                status,
                ScientificOutcome.UNRESOLVED_INDETERMINATE,
                ordered_events,
                None,
                None,
            )
        outcome = {
            ScientificSequentialAction.CONTINUE_EXTENSION: (
                ScientificOutcome.EVIDENCE_DEFERRED
            ),
            ScientificSequentialAction.STOP_RESOLVED: ScientificOutcome.RESOLVED,
            ScientificSequentialAction.EXHAUSTED_INDETERMINATE: (
                ScientificOutcome.UNRESOLVED_INDETERMINATE
            ),
        }[decision.action]
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            outcome,
            ordered_events,
            decision.action,
            decision.decision_ref,
        )
    except Exception:  # noqa: BLE001 -- injected fixture procedures are untrusted
        return ReconstructionCampaignResult(
            policy_ref,
            status,
            ScientificOutcome.INFRASTRUCTURE_FAILED,
            ordered_events,
            None,
            None,
        )
