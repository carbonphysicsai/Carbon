"""Direct D11 matrix, history, artifact, and admission boundary regressions."""

from __future__ import annotations

import inspect
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
from itertools import pairwise

import pytest

import carbon.evaluation.admission as admission_runtime
import carbon.evaluation.fixtures as fixture_runtime
from carbon.authoring.canonical import (
    CanonicalRecord,
    CanonicalTuple,
    encode_value,
    tagged_sha256,
)
from carbon.evaluation.assets import (
    FixtureReferenceAsset,
    ReferenceArtifact,
    create_fixture_reference_asset,
    create_reference_artifact,
    validate_reference_artifact,
)
from carbon.evaluation.canonical import (
    canonical_bytes,
    canonical_record,
    decode_canonical_bytes,
)
from carbon.evaluation.enums import (
    RESOLUTION_OUTCOME_REASON_COMPATIBILITY,
    RUN_OUTCOME_REASON_COMPATIBILITY,
    AdmissionArtifactAbsenceReason,
    AdmissionGrantIssuanceOutcome,
    AdmissionGrantIssuanceReason,
    ConditioningStatus,
    DependencyCategory,
    DependencyRelation,
    QualificationAbsenceReason,
    ReferenceArtifactOrigin,
    ReferenceComparisonOutcome,
    ReferenceComparisonReason,
    ReferenceFailureReason,
    ReferenceGrantBindingKind,
    ReferenceIdentityKind,
    ReferenceRunOutcome,
    ResolutionOutcome,
    ResolutionReason,
    SupportApplicabilityStatus,
    TruthAssetAdmissionOutcome,
    TruthAssetAdmissionReason,
    UncertaintyStatus,
)
from carbon.evaluation.errors import (
    ReferenceCanonicalDecodingError,
    ReferenceInputCode,
    ReferenceServiceCode,
    ReferenceServiceError,
    ReferenceValidationError,
)
from carbon.evaluation.execution import (
    ReferenceResolutionRecord,
    ReferenceRunRecord,
    create_reference_resolution_record,
    create_reference_run_record,
)
from carbon.evaluation.fixtures import build_b04_fixture_reference_graph
from carbon.evaluation.model import (
    AdmissionArtifactBinding,
    AdmissionAttemptBinding,
    OptionalBinding,
    QualificationBinding,
    ReferenceGrantBinding,
    ReferenceWitnessTarget,
    RunArtifactBinding,
)
from carbon.evaluation.policy import validate_reference_policy_graph
from carbon.evaluation.refs import REFERENCE_TRUTH_DOCUMENT_HEADER
from carbon.registry.model import ChallengeKey

_NON_SUCCESS_RESOLUTION_CASES = tuple(
    (outcome, reason)
    for outcome, reasons in RESOLUTION_OUTCOME_REASON_COMPATIBILITY.items()
    if outcome
    not in {
        ResolutionOutcome.PRIMARY_GRANT_ISSUED,
        ResolutionOutcome.WITNESS_GRANT_ISSUED,
    }
    for reason in reasons
)

_RUN_STATUS_CASES = (
    (
        ReferenceRunOutcome.NOT_APPLICABLE,
        ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE,
        SupportApplicabilityStatus.NOT_APPLICABLE,
        ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE,
        UncertaintyStatus.RESOLVED,
    ),
    (
        ReferenceRunOutcome.UNSUPPORTED,
        ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED,
        SupportApplicabilityStatus.UNSUPPORTED,
        ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE,
        UncertaintyStatus.RESOLVED,
    ),
    (
        ReferenceRunOutcome.APPLICABILITY_UNRESOLVED,
        ReferenceFailureReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
        SupportApplicabilityStatus.ASSESSMENT_UNAVAILABLE,
        ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE,
        UncertaintyStatus.RESOLVED,
    ),
    (
        ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED,
        ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED,
        SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE,
        ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE,
        UncertaintyStatus.UNRESOLVED,
    ),
    (
        ReferenceRunOutcome.CONDITIONING_UNRESOLVED,
        ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
        SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE,
        ConditioningStatus.UNRESOLVED,
        UncertaintyStatus.RESOLVED,
    ),
    (
        ReferenceRunOutcome.CANCELLED,
        ReferenceFailureReason.TRUSTED_CANCELLATION,
        SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE,
        ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE,
        UncertaintyStatus.RESOLVED,
    ),
)


def _assert_code(captured: pytest.ExceptionInfo, code: ReferenceInputCode) -> None:
    assert captured.value.code == code.value


def _resolution_applicability(graph, outcome: ResolutionOutcome):
    status = {
        ResolutionOutcome.NOT_APPLICABLE: SupportApplicabilityStatus.NOT_APPLICABLE,
        ResolutionOutcome.UNSUPPORTED: SupportApplicabilityStatus.UNSUPPORTED,
        ResolutionOutcome.APPLICABILITY_UNRESOLVED: (
            SupportApplicabilityStatus.ASSESSMENT_UNAVAILABLE
        ),
    }.get(outcome, SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE)
    return replace(graph.primary_resolution.applicability_assessment, status=status)


def _non_success_resolution(
    graph, outcome: ResolutionOutcome, reason: ResolutionReason
) -> ReferenceResolutionRecord:
    qualification = (
        QualificationBinding.absent(QualificationAbsenceReason.UNAVAILABLE)
        if outcome is ResolutionOutcome.QUALIFICATION_UNAVAILABLE
        else graph.primary_resolution.qualification_binding
    )
    return create_reference_resolution_record(
        request=graph.primary_request,
        grant=None,
        observed_reasons=(reason,),
        applicability_assessment=_resolution_applicability(graph, outcome),
        authority_function=graph.primary_resolution.authority_function,
        evidence_role_binding=graph.primary_resolution.evidence_role_binding,
        qualification_binding=qualification,
        resolution_id=f"b04_matrix_{reason.value.lower()}",
        resolution_version="1.0",
        resolver_ref=graph.primary_resolution.resolver_ref,
        resource_policy_ref=graph.primary_resolution.resource_policy_ref,
        source_class=graph.primary_resolution.source_class,
    )


@pytest.mark.parametrize(("outcome", "reason"), _NON_SUCCESS_RESOLUTION_CASES)
def test_every_non_success_resolution_has_exact_reason_and_no_grant(
    outcome: ResolutionOutcome,
    reason: ResolutionReason,
) -> None:
    graph = build_b04_fixture_reference_graph()
    record = _non_success_resolution(graph, outcome, reason)

    assert record.outcome is outcome
    assert record.reason is reason
    assert record.grant_binding.kind is ReferenceGrantBindingKind.ABSENT
    assert record.grant_binding.value is reason
    assert record.applicability_assessment.status is (
        _resolution_applicability(graph, outcome).status
    )
    assert record.qualification_binding.is_bound is (
        outcome is not ResolutionOutcome.QUALIFICATION_UNAVAILABLE
    )

    with pytest.raises(ReferenceValidationError) as bound:
        replace(
            record,
            grant_binding=ReferenceGrantBinding.primary(graph.primary_grant.to_ref()),
        )
    _assert_code(bound, ReferenceInputCode.OUTCOME_REASON_MISMATCH)

    with pytest.raises(ReferenceValidationError) as factory_bound:
        create_reference_resolution_record(
            request=graph.primary_request,
            grant=graph.primary_grant,
            observed_reasons=(reason,),
            applicability_assessment=record.applicability_assessment,
            authority_function=record.authority_function,
            evidence_role_binding=record.evidence_role_binding,
            qualification_binding=record.qualification_binding,
            resolution_id=f"b04_matrix_bound_{reason.value.lower()}",
            resolution_version="1.0",
            resolver_ref=record.resolver_ref,
            resource_policy_ref=record.resource_policy_ref,
            source_class=record.source_class,
        )
    _assert_code(factory_bound, ReferenceInputCode.OUTCOME_REASON_MISMATCH)


def _run_for_status_case(
    outcome: ReferenceRunOutcome,
    reason: ReferenceFailureReason,
    applicability: SupportApplicabilityStatus,
    conditioning: ConditioningStatus,
    uncertainty: UncertaintyStatus,
) -> ReferenceRunRecord:
    graph = build_b04_fixture_reference_graph()
    return replace(
        graph.primary_run,
        applicability_assessment=replace(
            graph.primary_run.applicability_assessment,
            status=applicability,
        ),
        artifact_binding=RunArtifactBinding.absent(reason),
        conditioning_assessment=replace(
            graph.primary_run.conditioning_assessment,
            status=conditioning,
        ),
        outcome=outcome,
        reason=OptionalBinding.present(reason),
        uncertainty_binding=replace(
            graph.primary_run.uncertainty_binding,
            status=uncertainty,
        ),
    )


@pytest.mark.parametrize(
    ("outcome", "reason", "applicability", "conditioning", "uncertainty"),
    _RUN_STATUS_CASES,
)
def test_limited_or_cancelled_runs_have_exact_status_and_no_artifact(
    outcome: ReferenceRunOutcome,
    reason: ReferenceFailureReason,
    applicability: SupportApplicabilityStatus,
    conditioning: ConditioningStatus,
    uncertainty: UncertaintyStatus,
) -> None:
    record = _run_for_status_case(
        outcome,
        reason,
        applicability,
        conditioning,
        uncertainty,
    )
    assert RUN_OUTCOME_REASON_COMPATIBILITY[outcome] == (reason,)
    assert record.outcome is outcome
    assert record.reason.value is reason
    assert record.applicability_assessment.status is applicability
    assert record.conditioning_assessment.status is conditioning
    assert record.uncertainty_binding.status is uncertainty
    assert record.artifact_binding.is_bound is False
    assert record.artifact_binding.value is reason

    with pytest.raises(ReferenceValidationError) as bound:
        replace(
            record,
            artifact_binding=build_b04_fixture_reference_graph().primary_run.artifact_binding,
        )
    _assert_code(bound, ReferenceInputCode.OUTCOME_REASON_MISMATCH)


@pytest.mark.parametrize(
    ("outcome", "reason", "applicability", "conditioning", "uncertainty"),
    _RUN_STATUS_CASES[:-1],
)
def test_limited_run_rejects_the_corresponding_success_status(
    outcome: ReferenceRunOutcome,
    reason: ReferenceFailureReason,
    applicability: SupportApplicabilityStatus,
    conditioning: ConditioningStatus,
    uncertainty: UncertaintyStatus,
) -> None:
    del applicability, conditioning, uncertainty
    with pytest.raises(ReferenceValidationError) as captured:
        _run_for_status_case(
            outcome,
            reason,
            SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE,
            ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE,
            UncertaintyStatus.RESOLVED,
        )
    _assert_code(captured, ReferenceInputCode.OUTCOME_REASON_MISMATCH)


def _attempt(
    graph,
    *,
    artifact_binding: AdmissionArtifactBinding,
    qualification_binding: QualificationBinding,
    run_ref=None,
    comparison_refs=None,
    provenance_policy_ref=None,
) -> AdmissionAttemptBinding:
    challenge = graph.challenge_key
    return AdmissionAttemptBinding(
        fixture_runtime._identity(
            ReferenceIdentityKind.ADMISSION_AUTHORITY,
            "matrix_admission_authority",
            challenge,
        ),
        graph.policy.answer_key_authority_target.value,
        artifact_binding,
        graph.case_ref,
        (
            comparison_refs
            if comparison_refs is not None
            else (graph.comparison.to_ref(),)
        ),
        fixture_runtime._identity(
            ReferenceIdentityKind.ADMISSION_PROFILE,
            "matrix_admission_profile",
            challenge,
        ),
        graph.policy.disclosure_policy_ref,
        graph.policy.answer_key_authority_target.value,
        (
            provenance_policy_ref
            if provenance_policy_ref is not None
            else graph.policy.provenance_policy_ref
        ),
        qualification_binding,
        graph.policy.rights_profile_ref,
        run_ref if run_ref is not None else graph.primary_run.to_ref(),
        (fixture_runtime._owner("permitted_use", "matrix", challenge),),
        graph.policy.registered_witness_targets,
    )


@pytest.mark.parametrize("absence_reason", tuple(AdmissionArtifactAbsenceReason))
def test_every_artifact_absence_reason_fails_closed_before_admission(
    absence_reason: AdmissionArtifactAbsenceReason,
) -> None:
    graph = build_b04_fixture_reference_graph()
    binding = AdmissionArtifactBinding.absent(absence_reason)
    attempt = _attempt(
        graph,
        artifact_binding=binding,
        qualification_binding=QualificationBinding.absent(
            QualificationAbsenceReason.UNAVAILABLE
        ),
    )
    failures = admission_runtime._validate_admission_graph(
        attempt,
        graph.policy,
        graph.primary_run,
        None,
        (graph.comparison,),
    )

    assert binding.value is absence_reason
    assert TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE in failures
    assert admission_runtime.select_truth_asset_admission_terminal(failures) == (
        TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE,
    )


def test_one_dual_protocol_provider_cannot_issue_and_admit_its_own_grant() -> None:
    graph = build_b04_fixture_reference_graph()
    issuer_ref = fixture_runtime._identity(
        ReferenceIdentityKind.ADMISSION_ISSUER,
        "matrix_dual_provider_issuer",
        graph.challenge_key,
    )
    attempt = _attempt(
        graph,
        artifact_binding=AdmissionArtifactBinding.absent(
            AdmissionArtifactAbsenceReason.MISSING
        ),
        qualification_binding=QualificationBinding.absent(
            QualificationAbsenceReason.UNAVAILABLE
        ),
    )

    class DualProvider:
        @property
        def issuer_ref(self):
            return issuer_ref

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            return admission_runtime.AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                "b04-matrix-dual-provider-token",
            )

        def evaluate_admission(self, observed_attempt, grant_ref):
            del observed_attempt, grant_ref
            raise AssertionError("self-admission callback must not run")

    provider = DualProvider()
    issuance = None
    with pytest.raises(ReferenceServiceError) as captured:
        issuance = admission_runtime.issue_truth_asset_admission_grant_record(
            provider,
            attempt,
            issuance_id="b04_matrix_dual_provider_issuance",
            issuance_version="1.0",
        )
    assert issuance is None
    assert (
        captured.value.code == ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE.value
    )


def test_primary_and_witness_runners_cannot_issue_admission_grants() -> None:
    graph = build_b04_fixture_reference_graph()
    attempt = _attempt(
        graph,
        artifact_binding=AdmissionArtifactBinding.absent(
            AdmissionArtifactAbsenceReason.MISSING
        ),
        qualification_binding=QualificationBinding.absent(
            QualificationAbsenceReason.UNAVAILABLE
        ),
    )
    issuer_ref = fixture_runtime._identity(
        ReferenceIdentityKind.ADMISSION_ISSUER,
        "matrix_runner_issuer",
        graph.challenge_key,
    )

    class Issuer:
        issuance_calls = 0
        issuer_ref_reads = 0

        @property
        def issuer_ref(self):
            self.issuer_ref_reads += 1
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            del observed_attempt
            self.issuance_calls += 1
            raise AssertionError("runner issuer callback must not run")

    class PrimaryIssuer(Issuer):
        def run_primary(self, grant, request):
            del grant, request
            raise AssertionError("primary runner callback must not run")

    class WitnessIssuer(Issuer):
        def run_witness(self, grant, request):
            del grant, request
            raise AssertionError("witness runner callback must not run")

    for label, provider in (
        ("primary", PrimaryIssuer()),
        ("witness", WitnessIssuer()),
    ):
        issuance = None
        with pytest.raises(ReferenceServiceError) as captured:
            issuance = admission_runtime.issue_truth_asset_admission_grant_record(
                provider,
                attempt,
                issuance_id=f"b04_matrix_{label}_runner_issuance",
                issuance_version="1.0",
            )
        assert issuance is None
        assert (
            captured.value.code
            == ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE.value
        )
        assert provider.issuance_calls == 0
        assert provider.issuer_ref_reads == 0


def _registered_structural_graph(graph):
    provenance = replace(
        graph.primary_run.provenance_binding,
        provenance_refs=(
            *graph.primary_run.provenance_binding.provenance_refs,
            graph.policy.provenance_policy_ref,
        ),
    )
    content = replace(
        graph.primary_run.artifact_binding.value,
        artifact_origin=ReferenceArtifactOrigin.REGISTERED_REFERENCE,
    )
    run = replace(
        graph.primary_run,
        artifact_binding=RunArtifactBinding.bound(content),
        provenance_binding=provenance,
        run_id="b04_matrix_registered_structural_run",
    )
    run = decode_canonical_bytes(canonical_bytes(run), ReferenceRunRecord)
    artifact = create_reference_artifact(
        run,
        artifact_id="b04_matrix_registered_structural_artifact",
        artifact_version="1.0",
    )
    comparison = replace(
        graph.comparison,
        comparison_id="b04_matrix_registered_structural_comparison",
        outcome=ReferenceComparisonOutcome.AGREEMENT_WITHIN_REGISTERED_POLICY,
        primary_run_ref=run.to_ref(),
        reason=ReferenceComparisonReason.COMPARISON_REQUIREMENTS_SATISFIED,
    )
    return run, artifact, comparison


def _positive_admission_inputs(label: str):
    graph = build_b04_fixture_reference_graph()
    run, artifact, comparison = _registered_structural_graph(graph)
    attempt = _attempt(
        graph,
        artifact_binding=AdmissionArtifactBinding.bound(artifact.to_ref()),
        qualification_binding=QualificationBinding.bound(
            fixture_runtime._owner(
                "qualification_evidence_bundle",
                f"matrix_positive_{label}",
                graph.challenge_key,
            )
        ),
        run_ref=run.to_ref(),
        comparison_refs=(comparison.to_ref(),),
    )
    issuer_ref = fixture_runtime._identity(
        ReferenceIdentityKind.ADMISSION_ISSUER,
        f"matrix_positive_issuer_{label}",
        graph.challenge_key,
    )

    class Issuer:
        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            return admission_runtime.AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                f"b04-matrix-positive-issuance-token-{label}",
            )

    issuance = admission_runtime.issue_truth_asset_admission_grant_record(
        Issuer(),
        attempt,
        issuance_id=f"b04_matrix_positive_issuance_{label}",
        issuance_version="1.0",
    )
    assert issuance is not None
    grant = admission_runtime.create_truth_asset_admission_grant(
        issuance,
        capability_ref=issuer_ref,
        grant_id=f"b04_matrix_positive_grant_{label}",
        grant_version="1.0",
    )
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        f"matrix_positive_receipt_{label}",
        graph.challenge_key,
    )

    class Authority:
        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.ADMITTED,
                TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                receipt_ref,
            )

    assert (
        admission_runtime._validate_admission_graph(
            attempt,
            graph.policy,
            run,
            artifact,
            (comparison,),
        )
        == ()
    )
    return graph, attempt, run, artifact, comparison, issuance, grant, Authority()


def test_admission_records_snapshot_attempt_and_nested_binding_layers() -> None:
    graph, attempt, run, artifact, comparison, issuance, grant, authority = (
        _positive_admission_inputs("attempt_snapshot")
    )
    decision = admission_runtime._decide_truth_asset_admission_record(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_attempt_snapshot_decision",
        decision_version="1.0",
    )
    assert decision is not None
    layers = (
        attempt,
        issuance.attempt_binding,
        grant.attempt_binding,
        decision.attempt_binding,
    )
    for source, snapshot in pairwise(layers):
        assert snapshot == source
        assert snapshot is not source
        assert snapshot.answer_key_authority_target is not (
            source.answer_key_authority_target
        )
        assert snapshot.answer_key_authority_target.value is not (
            source.answer_key_authority_target.value
        )
        assert snapshot.primary_execution_target is not source.primary_execution_target
        assert snapshot.artifact_binding is not source.artifact_binding
        assert snapshot.artifact_binding.value is not source.artifact_binding.value
        assert snapshot.qualification_binding is not source.qualification_binding
        assert (
            snapshot.qualification_binding.value
            is not source.qualification_binding.value
        )
        assert snapshot.witness_targets[0] is not source.witness_targets[0]
        assert snapshot.witness_targets[0].value is not source.witness_targets[0].value

    downstream = (
        (attempt, canonical_bytes(issuance), issuance),
        (issuance.attempt_binding, canonical_bytes(grant), grant),
        (grant.attempt_binding, canonical_bytes(decision), decision),
    )
    for index, (source, frozen_bytes, snapshot) in enumerate(downstream):
        object.__setattr__(
            source.answer_key_authority_target.value,
            "content_digest",
            tagged_sha256(f"attempt-target-{index}".encode("ascii")),
        )
        object.__setattr__(
            source.artifact_binding.value,
            "content_digest",
            tagged_sha256(f"attempt-artifact-{index}".encode("ascii")),
        )
        object.__setattr__(
            source.qualification_binding.value,
            "object_id",
            f"b04_mutated_qualification_{index}",
        )
        object.__setattr__(
            source.witness_targets[0].value,
            "content_digest",
            tagged_sha256(f"attempt-witness-{index}".encode("ascii")),
        )
        assert canonical_bytes(snapshot) == frozen_bytes


def test_private_or_decoded_positive_decision_cannot_mint_truth_asset() -> None:
    graph, _attempt_binding, run, artifact, comparison, issuance, grant, authority = (
        _positive_admission_inputs("unregistered")
    )
    decision = admission_runtime._decide_truth_asset_admission_record(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_unregistered_positive_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    decoded = tuple(
        decode_canonical_bytes(canonical_bytes(record), type(record))
        for record in (decision, issuance, grant, artifact, run)
    )
    with pytest.raises(ReferenceValidationError) as captured:
        admission_runtime.create_truth_asset(
            decoded[0],
            decoded[1],
            decoded[2],
            decoded[3],
            decoded[4],
            truth_asset_id="b04_matrix_unregistered_truth_asset",
            truth_asset_version="1.0",
        )
    _assert_code(captured, ReferenceInputCode.STALE_BINDING)
    assert captured.value.path == "/admission_decision_ref"


def test_public_positive_decision_registers_one_exact_reconstructable_asset() -> None:
    graph, _attempt_binding, run, artifact, comparison, issuance, grant, authority = (
        _positive_admission_inputs("registered")
    )
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_registered_positive_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    decoded = tuple(
        decode_canonical_bytes(canonical_bytes(record), type(record))
        for record in (decision, issuance, grant, artifact, run)
    )
    asset = admission_runtime.create_truth_asset(
        decoded[0],
        decoded[1],
        decoded[2],
        decoded[3],
        decoded[4],
        truth_asset_id="b04_matrix_registered_truth_asset",
        truth_asset_version="1.0",
    )
    assert asset.admission_decision_ref == decision.to_ref()
    assert asset.admission_grant_ref == grant.to_ref()
    assert asset.admission_issuance_record_ref == issuance.to_ref()
    assert asset.artifact_ref == artifact.to_ref()
    assert asset.run_ref == run.to_ref()
    admitted_payload = canonical_bytes(asset)
    reconstructed = decode_canonical_bytes(
        admitted_payload,
        admission_runtime.TruthAsset,
    )
    assert reconstructed == asset
    assert reconstructed.to_ref() == asset.to_ref()
    assert reconstructed is not asset
    assert asset.applicability_assessment is not run.applicability_assessment
    assert asset.conditioning_assessment is not run.conditioning_assessment
    assert asset.provenance_binding is not run.provenance_binding
    assert asset.scope_binding is not run.scope_binding
    assert asset.uncertainty_binding is not run.uncertainty_binding
    assert asset.execution_target is not run.execution_target.value
    assert asset.dependency_disclosures[0] is not (
        run.provenance_binding.dependency_disclosures[0]
    )
    assert asset.dependency_disclosures[0] is not (
        asset.provenance_binding.dependency_disclosures[0]
    )

    object.__setattr__(
        run.applicability_assessment.method_ref,
        "content_digest",
        tagged_sha256(b"mutated-run-applicability"),
    )
    object.__setattr__(
        run.provenance_binding.dependency_disclosures[0].evidence_refs[0],
        "object_id",
        "b04_mutated_run_provenance",
    )
    object.__setattr__(
        run.execution_target.value.value,
        "content_digest",
        tagged_sha256(b"mutated-run-target"),
    )
    assert canonical_bytes(asset) == admitted_payload

    object.__setattr__(
        asset.applicability_assessment.method_ref,
        "content_digest",
        tagged_sha256(b"mutated-returned-truth-asset"),
    )
    fresh = decode_canonical_bytes(admitted_payload, admission_runtime.TruthAsset)
    assert fresh == reconstructed
    assert fresh.to_ref() == reconstructed.to_ref()
    assert fresh is not reconstructed
    assert fresh is not asset
    assert canonical_bytes(fresh) == admitted_payload
    with pytest.raises(ReferenceValidationError) as consumed:
        admission_runtime.create_truth_asset(
            decision,
            issuance,
            grant,
            artifact,
            run,
            truth_asset_id="b04_matrix_second_truth_asset",
            truth_asset_version="1.0",
        )
    _assert_code(consumed, ReferenceInputCode.STALE_BINDING)
    assert consumed.value.path == "/admission_decision_ref"


def test_positive_decision_is_atomically_single_use_under_concurrency() -> None:
    graph, _attempt_binding, run, artifact, comparison, issuance, grant, authority = (
        _positive_admission_inputs("concurrent")
    )
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_concurrent_positive_decision",
        decision_version="1.0",
    )
    assert decision is not None
    barrier = threading.Barrier(2)

    def construct(index: int):
        barrier.wait(timeout=5)
        try:
            return admission_runtime.create_truth_asset(
                decision,
                issuance,
                grant,
                artifact,
                run,
                truth_asset_id=f"b04_matrix_concurrent_truth_asset_{index}",
                truth_asset_version="1.0",
            )
        except ReferenceValidationError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(construct, (1, 2)))
    assets = tuple(
        result for result in results if isinstance(result, admission_runtime.TruthAsset)
    )
    failures = tuple(
        result for result in results if isinstance(result, ReferenceValidationError)
    )
    assert len(assets) == 1
    assert len(failures) == 1
    assert failures[0].code == ReferenceInputCode.STALE_BINDING.value
    assert failures[0].path == "/admission_decision_ref"


def test_absent_qualification_selects_unavailable_without_truth_asset() -> None:
    graph = build_b04_fixture_reference_graph()
    run, artifact, comparison = _registered_structural_graph(graph)
    attempt = _attempt(
        graph,
        artifact_binding=AdmissionArtifactBinding.bound(artifact.to_ref()),
        qualification_binding=QualificationBinding.absent(
            QualificationAbsenceReason.OUT_OF_SCOPE
        ),
        run_ref=run.to_ref(),
        comparison_refs=(comparison.to_ref(),),
    )
    failures = admission_runtime._validate_admission_graph(
        attempt,
        graph.policy,
        run,
        artifact,
        (comparison,),
    )

    assert failures == (TruthAssetAdmissionReason.QUALIFICATION_UNAVAILABLE,)
    assert admission_runtime.select_truth_asset_admission_terminal(failures) == (
        TruthAssetAdmissionOutcome.UNAVAILABLE,
        TruthAssetAdmissionReason.QUALIFICATION_UNAVAILABLE,
    )


def test_wrong_policy_role_and_stale_provenance_select_closed_failures() -> None:
    graph = build_b04_fixture_reference_graph()
    qualification = QualificationBinding.bound(
        fixture_runtime._owner(
            "qualification_evidence_bundle",
            "matrix_qualification",
            graph.challenge_key,
        )
    )
    run, artifact, comparison = _registered_structural_graph(graph)
    attempt = _attempt(
        graph,
        artifact_binding=AdmissionArtifactBinding.bound(artifact.to_ref()),
        qualification_binding=qualification,
        run_ref=run.to_ref(),
        comparison_refs=(comparison.to_ref(),),
    )

    wrong_policy = replace(graph.policy, policy_id="b04_matrix_wrong_policy")
    wrong_policy_failures = admission_runtime._validate_admission_graph(
        attempt,
        wrong_policy,
        run,
        artifact,
        (comparison,),
    )
    assert admission_runtime.select_truth_asset_admission_terminal(
        wrong_policy_failures
    ) == (
        TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH,
    )

    wrong_role_failures = admission_runtime._validate_admission_graph(
        attempt,
        graph.policy,
        graph.witness_run,
        graph.witness_artifact,
        (graph.comparison,),
    )
    assert admission_runtime.select_truth_asset_admission_terminal(
        wrong_role_failures
    ) == (
        TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH,
    )

    stale_provenance = replace(
        run.provenance_binding,
        rights_profile_ref=fixture_runtime._owner(
            "rights_profile",
            "matrix_stale_rights",
            graph.challenge_key,
        ),
    )
    stale_run = replace(
        run,
        provenance_binding=stale_provenance,
        run_id="b04_matrix_stale_provenance_run",
    )
    stale_artifact = create_reference_artifact(
        stale_run,
        artifact_id="b04_matrix_stale_provenance_artifact",
        artifact_version="1.0",
    )
    stale_comparison = replace(
        comparison,
        comparison_id="b04_matrix_stale_provenance_comparison",
        primary_run_ref=stale_run.to_ref(),
    )
    stale_attempt = _attempt(
        graph,
        artifact_binding=AdmissionArtifactBinding.bound(stale_artifact.to_ref()),
        qualification_binding=qualification,
        run_ref=stale_run.to_ref(),
        comparison_refs=(stale_comparison.to_ref(),),
    )
    stale_failures = admission_runtime._validate_admission_graph(
        stale_attempt,
        graph.policy,
        stale_run,
        stale_artifact,
        (stale_comparison,),
    )
    assert admission_runtime.select_truth_asset_admission_terminal(stale_failures) == (
        TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.PROVENANCE_OR_RIGHTS_INVALID,
    )


def test_cross_challenge_admission_binding_rejects_before_an_attempt_exists() -> None:
    graph = build_b04_fixture_reference_graph()
    wrong_ref = type(graph.primary_artifact.to_ref())(
        ChallengeKey("b04_matrix_other", "1.0"),
        graph.primary_artifact.to_ref().content_digest,
    )
    with pytest.raises(ReferenceValidationError) as captured:
        _attempt(
            graph,
            artifact_binding=AdmissionArtifactBinding.bound(wrong_ref),
            qualification_binding=QualificationBinding.absent(
                QualificationAbsenceReason.UNAVAILABLE
            ),
        )
    _assert_code(captured, ReferenceInputCode.CROSS_CHALLENGE)


def test_artifact_record_field_order_is_exactly_d11() -> None:
    assert tuple(item.name for item in fields(ReferenceArtifact)) == (
        "applicability_assessment",
        "artifact_content_digest",
        "artifact_descriptor_ref",
        "artifact_id",
        "artifact_origin",
        "artifact_version",
        "case_ref",
        "challenge_key",
        "conditioning_assessment",
        "configuration_ref",
        "environment_ref",
        "execution_target",
        "hardware_ref",
        "implementation_ref",
        "method_ref",
        "policy_ref",
        "precision_ref",
        "provenance_binding",
        "representation_ref",
        "run_ref",
        "scope_binding",
        "uncertainty_binding",
    )
    assert tuple(item.name for item in fields(FixtureReferenceAsset)) == (
        "artifact_ref",
        "case_ref",
        "challenge_key",
        "fixture_asset_id",
        "fixture_asset_version",
        "fixture_provenance_ref",
        "live_eligible",
        "payload_bytes",
        "policy_ref",
        "run_ref",
        "scientific_qualification_eligible",
    )


def test_artifact_factories_reject_stale_origin_payload_and_failure_paths() -> None:
    graph = build_b04_fixture_reference_graph()
    artifact = create_reference_artifact(
        graph.primary_run,
        artifact_id="b04_matrix_direct_artifact",
        artifact_version="1.0",
    )
    validate_reference_artifact(artifact, graph.primary_run)

    with pytest.raises(ReferenceValidationError) as stale:
        validate_reference_artifact(artifact, graph.witness_run)
    _assert_code(stale, ReferenceInputCode.STALE_BINDING)
    with pytest.raises(ReferenceValidationError) as failed_run:
        create_reference_artifact(
            graph.numerical_path.run,
            artifact_id="b04_matrix_failure_artifact",
            artifact_version="1.0",
        )
    _assert_code(failed_run, ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    with pytest.raises(ReferenceValidationError) as payload:
        create_fixture_reference_asset(
            artifact,
            graph.primary_run,
            fixture_asset_id="b04_matrix_wrong_payload",
            fixture_asset_version="1.0",
            fixture_provenance_ref=graph.primary_fixture_asset.fixture_provenance_ref,
            payload_bytes=b"NOT THE REGISTERED FIXTURE PAYLOAD",
        )
    _assert_code(payload, ReferenceInputCode.STALE_BINDING)

    registered_content = replace(
        graph.primary_run.artifact_binding.value,
        artifact_origin=ReferenceArtifactOrigin.REGISTERED_REFERENCE,
    )
    registered_run = replace(
        graph.primary_run,
        artifact_binding=RunArtifactBinding.bound(registered_content),
        run_id="b04_matrix_registered_origin_run",
    )
    registered_artifact = create_reference_artifact(
        registered_run,
        artifact_id="b04_matrix_registered_origin_artifact",
        artifact_version="1.0",
    )
    with pytest.raises(ReferenceValidationError) as origin:
        create_fixture_reference_asset(
            registered_artifact,
            registered_run,
            fixture_asset_id="b04_matrix_registered_origin_fixture",
            fixture_asset_version="1.0",
            fixture_provenance_ref=graph.primary_fixture_asset.fixture_provenance_ref,
            payload_bytes=graph.primary_fixture_asset.payload_bytes,
        )
    _assert_code(origin, ReferenceInputCode.ROLE_MISMATCH)

    drifted_provenance = replace(
        graph.primary_run.provenance_binding,
        reviewer_authority_refs=(
            *graph.primary_run.provenance_binding.reviewer_authority_refs,
            fixture_runtime._owner(
                "authority_evidence",
                "matrix_additional_reviewer",
                graph.challenge_key,
            ),
        ),
    )
    drifted_run = replace(
        graph.primary_run,
        provenance_binding=drifted_provenance,
        run_id="b04_matrix_drifted_provenance_run",
    )
    with pytest.raises(ReferenceValidationError) as provenance:
        validate_reference_artifact(artifact, drifted_run)
    _assert_code(provenance, ReferenceInputCode.STALE_BINDING)

    for protected in (artifact, graph.primary_fixture_asset):
        assert repr(protected) == f"{type(protected).__name__}(<protected>)"
        with pytest.raises(TypeError):
            pickle.dumps(protected)


def test_uncertainty_is_exactly_artifact_bound_and_rejects_cross_challenge() -> None:
    graph = build_b04_fixture_reference_graph()
    changed_uncertainty = replace(
        graph.primary_run.uncertainty_binding,
        evidence_refs=(
            *graph.primary_run.uncertainty_binding.evidence_refs,
            fixture_runtime._owner(
                "audit_evidence",
                "matrix_additional_uncertainty",
                graph.challenge_key,
            ),
        ),
    )
    changed_run = replace(
        graph.primary_run,
        run_id="b04_matrix_uncertainty_bound_run",
        uncertainty_binding=changed_uncertainty,
    )
    changed_artifact = create_reference_artifact(
        changed_run,
        artifact_id="b04_matrix_uncertainty_bound_artifact",
        artifact_version="1.0",
    )
    assert changed_artifact.uncertainty_binding == changed_uncertainty
    validate_reference_artifact(changed_artifact, changed_run)
    with pytest.raises(ReferenceValidationError) as stale:
        validate_reference_artifact(graph.primary_artifact, changed_run)
    _assert_code(stale, ReferenceInputCode.STALE_BINDING)

    wrong_challenge = ChallengeKey("b04_matrix_uncertainty_other", "1.0")
    with pytest.raises(ReferenceValidationError) as cross_challenge:
        replace(
            graph.primary_run.uncertainty_binding,
            method_ref=fixture_runtime._identity(
                ReferenceIdentityKind.UNCERTAINTY_METHOD,
                "matrix_cross_challenge_uncertainty",
                wrong_challenge,
            ),
        )
    _assert_code(cross_challenge, ReferenceInputCode.CROSS_CHALLENGE)


def test_reference_artifact_owns_deep_nested_copies_of_run_state() -> None:
    graph = build_b04_fixture_reference_graph()
    run = graph.primary_run
    artifact = create_reference_artifact(
        run,
        artifact_id="b04_matrix_copy_isolation_artifact",
        artifact_version="1.0",
    )
    nested_names = (
        "applicability_assessment",
        "conditioning_assessment",
        "execution_target",
        "provenance_binding",
        "scope_binding",
        "uncertainty_binding",
    )
    for name in nested_names:
        artifact_value = object.__getattribute__(artifact, name)
        run_value = object.__getattribute__(run, name)
        assert artifact_value == run_value
        assert artifact_value is not run_value
    assert artifact.execution_target.value is not run.execution_target.value
    assert (
        artifact.provenance_binding.source_ref is not run.provenance_binding.source_ref
    )
    assert all(
        artifact_disclosure is not run_disclosure
        for artifact_disclosure, run_disclosure in zip(
            artifact.provenance_binding.dependency_disclosures,
            run.provenance_binding.dependency_disclosures,
            strict=True,
        )
    )

    original_run_bytes = canonical_bytes(run)
    original_target_ref = run.execution_target.value.value
    original_source_ref = run.provenance_binding.source_ref
    original_claim_scope_ref = run.scope_binding.claim_scope_ref
    object.__setattr__(
        artifact.applicability_assessment,
        "status",
        SupportApplicabilityStatus.NOT_APPLICABLE,
    )
    object.__setattr__(
        artifact.conditioning_assessment,
        "status",
        ConditioningStatus.UNRESOLVED,
    )
    object.__setattr__(
        artifact.execution_target.value,
        "value",
        graph.witness_run.execution_target.value.value,
    )
    object.__setattr__(
        artifact.provenance_binding,
        "source_ref",
        fixture_runtime._identity(
            ReferenceIdentityKind.SOURCE,
            "artifact_isolation_source",
            graph.challenge_key,
        ),
    )
    object.__setattr__(
        artifact.provenance_binding.dependency_disclosures[0],
        "relation",
        DependencyRelation.DISTINCT,
    )
    object.__setattr__(
        artifact.scope_binding,
        "claim_scope_ref",
        fixture_runtime._owner(
            "claim_scope",
            "artifact_isolation_scope",
            graph.challenge_key,
        ),
    )
    object.__setattr__(
        artifact.uncertainty_binding,
        "status",
        UncertaintyStatus.UNRESOLVED,
    )

    assert (
        run.applicability_assessment.status
        is SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE
    )
    assert (
        run.conditioning_assessment.status
        is ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE
    )
    assert run.execution_target.value.value == original_target_ref
    assert run.provenance_binding.source_ref == original_source_ref
    assert (
        run.provenance_binding.dependency_disclosures[0].relation
        is DependencyRelation.SHARED
    )
    assert run.scope_binding.claim_scope_ref == original_claim_scope_ref
    assert run.uncertainty_binding.status is UncertaintyStatus.RESOLVED
    assert canonical_bytes(run) == original_run_bytes


def test_dependency_inventory_has_all_ten_nonempty_shared_evidence_facts() -> None:
    graph = build_b04_fixture_reference_graph()
    disclosures = graph.primary_run.provenance_binding.dependency_disclosures
    assert tuple(item.category for item in disclosures) == tuple(DependencyCategory)
    assert len(disclosures) == len(DependencyCategory) == 10
    for disclosure in disclosures:
        assert disclosure.relation is DependencyRelation.SHARED
        assert disclosure.evidence_refs
        assert len(disclosure.evidence_refs) == len(set(disclosure.evidence_refs))
        assert all(item.ref_kind == "provenance" for item in disclosure.evidence_refs)
        assert all(
            item.scope_binding.challenge_key == graph.challenge_key
            for item in disclosure.evidence_refs
        )
        assert not hasattr(disclosure, "independent")


def test_semantically_duplicate_witness_wrappers_are_rejected() -> None:
    graph = build_b04_fixture_reference_graph()
    target = graph.policy.registered_witness_targets[0]
    duplicate = ReferenceWitnessTarget(target.kind, target.value)
    assert duplicate == target
    assert duplicate is not target

    with pytest.raises(ReferenceValidationError) as captured:
        replace(
            graph.policy,
            registered_witness_targets=(target, duplicate),
        )
    _assert_code(captured, ReferenceInputCode.DUPLICATE_IDENTITY)


def test_supersession_is_same_challenge_and_cannot_reinterpret_old_graph() -> None:
    graph = build_b04_fixture_reference_graph()
    old_policy_bytes = canonical_bytes(graph.policy)
    old_policy_ref = graph.policy.to_ref()
    new_policy = replace(
        graph.policy,
        policy_version="1.1",
        supersedes=OptionalBinding.present(old_policy_ref),
    )
    assert new_policy.supersedes.value == old_policy_ref
    assert new_policy.challenge_key == graph.challenge_key
    assert canonical_bytes(graph.policy) == old_policy_bytes
    assert graph.policy.to_ref() == old_policy_ref
    assert new_policy.to_ref() != old_policy_ref

    with pytest.raises(ReferenceValidationError) as history_drift:
        validate_reference_policy_graph(
            new_policy,
            entries=graph.entries,
            compositions=graph.compositions,
            precomputed_manifests=(graph.precomputed_manifest,),
        )
    _assert_code(history_drift, ReferenceInputCode.STALE_BINDING)

    cross_ref = type(old_policy_ref)(
        ChallengeKey("b04_matrix_policy_other", "1.0"),
        old_policy_ref.content_digest,
    )
    with pytest.raises(ReferenceValidationError) as cross_challenge:
        replace(graph.policy, supersedes=OptionalBinding.present(cross_ref))
    _assert_code(cross_challenge, ReferenceInputCode.CROSS_CHALLENGE)


def _mutate_nested_set(
    record: CanonicalRecord,
    *,
    outer_name: str,
    set_name: str,
    duplicate: bool,
) -> CanonicalRecord:
    top_fields = list(record.fields)
    outer_index = next(
        index for index, (name, _value) in enumerate(top_fields) if name == outer_name
    )
    outer = top_fields[outer_index][1]
    assert type(outer) is CanonicalRecord
    nested_fields = list(outer.fields)
    set_index = next(
        index for index, (name, _value) in enumerate(nested_fields) if name == set_name
    )
    encoded_set = nested_fields[set_index][1]
    assert type(encoded_set) is CanonicalTuple
    assert len(encoded_set.items) >= 2
    items = (
        (*encoded_set.items, encoded_set.items[0])
        if duplicate
        else tuple(reversed(encoded_set.items))
    )
    nested_fields[set_index] = (set_name, CanonicalTuple(tuple(items)))
    top_fields[outer_index] = (
        outer_name,
        CanonicalRecord(outer.record_type, tuple(nested_fields)),
    )
    return CanonicalRecord(record.record_type, tuple(top_fields))


@pytest.mark.parametrize("duplicate", (False, True))
def test_noncanonical_set_like_reordering_or_duplication_rejects(
    duplicate: bool,
) -> None:
    graph = build_b04_fixture_reference_graph()
    expanded_uncertainty = replace(
        graph.primary_run.uncertainty_binding,
        evidence_refs=(
            *graph.primary_run.uncertainty_binding.evidence_refs,
            fixture_runtime._owner(
                "audit_evidence",
                "matrix_set_like_second",
                graph.challenge_key,
            ),
        ),
    )
    expanded_run = replace(
        graph.primary_run,
        run_id="b04_matrix_set_like_run",
        uncertainty_binding=expanded_uncertainty,
    )
    mutated = _mutate_nested_set(
        canonical_record(expanded_run),
        outer_name="uncertainty_binding",
        set_name="evidence_refs",
        duplicate=duplicate,
    )
    payload = REFERENCE_TRUTH_DOCUMENT_HEADER + encode_value(mutated)
    with pytest.raises(ReferenceCanonicalDecodingError):
        decode_canonical_bytes(payload, ReferenceRunRecord)


def test_runtime_surface_has_no_cache_fallback_or_caller_selected_execution() -> None:
    graph = build_b04_fixture_reference_graph()
    callables = (
        create_reference_resolution_record,
        create_reference_run_record,
        create_reference_artifact,
        create_fixture_reference_asset,
        type(graph.primary_path.runner).run_primary,
        type(graph.witness_path.runner).run_witness,
    )
    forbidden = {
        "cache",
        "cache_key",
        "fallback",
        "fallback_runner",
        "filesystem_path",
        "mode",
        "network",
        "solver",
        "source_code",
    }
    for callable_value in callables:
        assert forbidden.isdisjoint(inspect.signature(callable_value).parameters)
    for value in (graph.primary_run, graph.primary_artifact, graph.primary_path.runner):
        assert not hasattr(value, "cache")
        assert not hasattr(value, "fallback")
        assert not hasattr(value, "fallback_result")
