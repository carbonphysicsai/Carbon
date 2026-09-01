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
from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole
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
    OptionalBindingTag,
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
    ReferenceCanonicalEncodingError,
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


@pytest.mark.parametrize(
    "failure_mode",
    (
        "exception",
        "wrong_type",
        "missing_all_slots",
        "missing_token",
        "pseudo_outcome",
        "pseudo_reason",
    ),
)
def test_issuance_provider_failure_fabricates_no_record_or_capability(
    failure_mode: str,
) -> None:
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
        f"matrix_issuance_failure_issuer_{failure_mode}",
        graph.challenge_key,
    )

    class Issuer:
        issuance_calls = 0
        mode = failure_mode

        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            self.issuance_calls += 1
            if self.mode == "exception":
                raise RuntimeError("protected issuer detail")
            if self.mode == "wrong_type":
                return object()
            if self.mode == "missing_all_slots":
                return object.__new__(admission_runtime.AdmissionGrantIssuanceEcho)
            if self.mode == "missing_token":
                forged = object.__new__(admission_runtime.AdmissionGrantIssuanceEcho)
                object.__setattr__(
                    forged,
                    "outcome",
                    AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                )
                object.__setattr__(
                    forged,
                    "reason",
                    AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                )
                return forged
            if self.mode in {"pseudo_outcome", "pseudo_reason"}:
                forged = object.__new__(admission_runtime.AdmissionGrantIssuanceEcho)
                outcome = AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED
                reason = (
                    AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED
                )
                if self.mode == "pseudo_outcome":
                    outcome = str.__new__(type(outcome), outcome.value)
                else:
                    reason = str.__new__(type(reason), reason.value)
                object.__setattr__(forged, "outcome", outcome)
                object.__setattr__(forged, "reason", reason)
                object.__setattr__(
                    forged,
                    "issuance_token",
                    f"b04-matrix-pseudo-issuance-token-{failure_mode}",
                )
                return forged
            return admission_runtime.AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                f"b04-matrix-issuance-recovery-token-{failure_mode}",
            )

    issuer = Issuer()
    issuance = None
    with pytest.raises((ReferenceServiceError, ReferenceValidationError)) as captured:
        issuance = admission_runtime.issue_truth_asset_admission_grant_record(
            issuer,
            attempt,
            issuance_id=f"b04_matrix_issuance_failure_{failure_mode}",
            issuance_version="1.0",
        )
    assert issuance is None
    assert issuer.issuance_calls == 1
    if failure_mode in {"pseudo_outcome", "pseudo_reason"}:
        assert captured.value.code == ReferenceInputCode.OUTCOME_REASON_MISMATCH.value
        assert captured.value.path == "/reason"
    else:
        assert (
            captured.value.code
            == ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE.value
        )
        assert captured.value.path == (
            "/issuer_ref" if failure_mode == "exception" else "/outcome"
        )
    assert "protected issuer detail" not in repr(captured.value)

    issuer.mode = "valid"
    recovered = admission_runtime.issue_truth_asset_admission_grant_record(
        issuer,
        attempt,
        issuance_id=f"b04_matrix_issuance_failure_{failure_mode}",
        issuance_version="1.0",
    )
    assert recovered is not None
    assert issuer.issuance_calls == 2
    with pytest.raises(ReferenceValidationError) as partial_capability:
        admission_runtime.create_truth_asset_admission_grant(
            recovered,
            capability_ref=object.__new__(type(issuer_ref)),
            grant_id=f"b04_matrix_partial_capability_grant_{failure_mode}",
            grant_version="1.0",
        )
    assert partial_capability.value.code == ReferenceInputCode.WRONG_TYPE.value
    assert partial_capability.value.path == "/capability_ref"
    assert (
        admission_runtime.create_truth_asset_admission_grant(
            recovered,
            capability_ref=issuer_ref,
            grant_id=f"b04_matrix_issuance_recovery_grant_{failure_mode}",
            grant_version="1.0",
        )
        is not None
    )


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


@pytest.mark.parametrize(
    "provider_kind",
    ("noncallable", "changing_descriptor", "raising_ref"),
)
def test_noncallable_authority_is_rejected_before_grant_claim(
    provider_kind: str,
) -> None:
    graph, _attempt_binding, run, artifact, comparison, issuance, grant, delegate = (
        _positive_admission_inputs(f"preclaim_authority_{provider_kind}")
    )

    class ChangingCallback:
        reads = 0
        calls = 0

        def __get__(self, instance, owner):
            del instance, owner
            self.reads += 1
            if self.reads == 1:
                return object()

            def forbidden_callback(*args):
                del args
                self.calls += 1
                raise AssertionError("a rejected callback descriptor must not run")

            return forbidden_callback

    changing_callback = ChangingCallback()

    class NoncallableAuthority:
        @property
        def admission_authority_ref(self):
            return delegate.admission_authority_ref

        evaluate_admission = object()

    class ChangingAuthority:
        @property
        def admission_authority_ref(self):
            return delegate.admission_authority_ref

        evaluate_admission = changing_callback

    class RaisingRefAuthority:
        admission_calls = 0
        ref_reads = 0

        @property
        def admission_authority_ref(self):
            self.ref_reads += 1
            raise RuntimeError("protected authority detail")

        def evaluate_admission(self, observed_attempt, observed_grant_ref):
            del observed_attempt, observed_grant_ref
            self.admission_calls += 1
            raise AssertionError("a malformed authority callback must not run")

    invalid_authority = {
        "noncallable": NoncallableAuthority,
        "changing_descriptor": ChangingAuthority,
        "raising_ref": RaisingRefAuthority,
    }[provider_kind]()
    with pytest.raises(ReferenceServiceError) as captured:
        admission_runtime.decide_truth_asset_admission(
            invalid_authority,
            issuance,
            grant,
            policy=graph.policy,
            run=run,
            artifact=artifact,
            comparisons=(comparison,),
            decision_id=f"b04_matrix_preclaim_authority_{provider_kind}",
            decision_version="1.0",
        )
    assert (
        captured.value.code
        == ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE.value
    )
    assert captured.value.path == "/admission_authority_ref"
    if provider_kind == "changing_descriptor":
        assert changing_callback.reads == 1
        assert changing_callback.calls == 0
    if provider_kind == "raising_ref":
        assert invalid_authority.ref_reads == 1
        assert invalid_authority.admission_calls == 0

    decision = admission_runtime.decide_truth_asset_admission(
        delegate,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id=f"b04_matrix_recovered_authority_{provider_kind}",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED


def test_callable_authority_descriptor_is_snapshotted_once_before_claim() -> None:
    graph, _attempt_binding, run, artifact, comparison, issuance, grant, delegate = (
        _positive_admission_inputs("one_read_authority_callback")
    )

    class OneReadCallback:
        reads = 0
        calls = 0

        def __get__(self, instance, owner):
            del instance, owner
            self.reads += 1
            if self.reads != 1:
                return object()

            def callback(observed_attempt, observed_grant_ref):
                self.calls += 1
                return delegate.evaluate_admission(
                    observed_attempt,
                    observed_grant_ref,
                )

            return callback

    callback = OneReadCallback()

    class ChangingAuthority:
        @property
        def admission_authority_ref(self):
            return delegate.admission_authority_ref

        evaluate_admission = callback

    decision = admission_runtime.decide_truth_asset_admission(
        ChangingAuthority(),
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_one_read_authority_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert callback.reads == 1
    assert callback.calls == 1


@pytest.mark.parametrize("reentrant_seam", ("authority_ref", "callback"))
def test_authority_descriptor_reentrancy_cannot_hide_nested_admission(
    reentrant_seam: str,
) -> None:
    graph, _attempt_binding, run, artifact, comparison, issuance, grant, delegate = (
        _positive_admission_inputs(f"descriptor_reentrancy_{reentrant_seam}")
    )

    class ReentrantAuthority:
        attempted_reentry = False
        admission_calls = 0
        nested_errors: list[ReferenceValidationError]

        def __init__(self) -> None:
            self.nested_errors = []

        def attempt_nested_admission(self) -> None:
            if self.attempted_reentry:
                return
            self.attempted_reentry = True
            try:
                admission_runtime.decide_truth_asset_admission(
                    self,
                    issuance,
                    grant,
                    policy=graph.policy,
                    run=run,
                    artifact=artifact,
                    comparisons=(comparison,),
                    decision_id=f"b04_matrix_nested_descriptor_{reentrant_seam}",
                    decision_version="1.0",
                )
            except ReferenceValidationError as error:
                self.nested_errors.append(error)

        @property
        def admission_authority_ref(self):
            if reentrant_seam == "authority_ref":
                self.attempt_nested_admission()
            return delegate.admission_authority_ref

        @property
        def evaluate_admission(self):
            if reentrant_seam == "callback":
                self.attempt_nested_admission()

            def callback(observed_attempt, observed_grant_ref):
                self.admission_calls += 1
                return delegate.evaluate_admission(
                    observed_attempt,
                    observed_grant_ref,
                )

            return callback

    authority = ReentrantAuthority()
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id=f"b04_matrix_outer_descriptor_{reentrant_seam}",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert authority.admission_calls == 1
    assert len(authority.nested_errors) == 1
    assert authority.nested_errors[0].code == ReferenceInputCode.STALE_BINDING.value
    assert authority.nested_errors[0].path == "/grant_ref"


@pytest.mark.parametrize("provider_kind", ("noncallable", "changing_descriptor"))
def test_noncallable_issuer_is_rejected_before_provider_invocation(
    provider_kind: str,
) -> None:
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
        f"matrix_preclaim_issuer_{provider_kind}",
        graph.challenge_key,
    )

    class ChangingCallback:
        reads = 0
        calls = 0

        def __get__(self, instance, owner):
            del instance, owner
            self.reads += 1
            if self.reads == 1:
                return object()

            def forbidden_callback(*args):
                del args
                self.calls += 1
                raise AssertionError("a rejected issuer callback must not run")

            return forbidden_callback

    changing_callback = ChangingCallback()

    class NoncallableIssuer:
        @property
        def issuer_ref(self):
            return issuer_ref

        evaluate_grant_issuance = object()

    class ChangingIssuer:
        @property
        def issuer_ref(self):
            return issuer_ref

        evaluate_grant_issuance = changing_callback

    invalid_issuer = (
        NoncallableIssuer() if provider_kind == "noncallable" else ChangingIssuer()
    )
    with pytest.raises(ReferenceServiceError) as captured:
        admission_runtime.issue_truth_asset_admission_grant_record(
            invalid_issuer,
            attempt,
            issuance_id=f"b04_matrix_preclaim_issuance_{provider_kind}",
            issuance_version="1.0",
        )
    assert (
        captured.value.code == ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE.value
    )
    assert captured.value.path == "/issuer_ref"
    if provider_kind == "changing_descriptor":
        assert changing_callback.reads == 1
        assert changing_callback.calls == 0

    class ValidIssuer:
        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            return admission_runtime.AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                f"b04-matrix-recovered-issuance-token-{provider_kind}",
            )

    issuance = admission_runtime.issue_truth_asset_admission_grant_record(
        ValidIssuer(),
        attempt,
        issuance_id=f"b04_matrix_recovered_issuance_{provider_kind}",
        issuance_version="1.0",
    )
    assert issuance is not None
    assert issuance.outcome is AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED


def test_callable_issuer_descriptor_is_snapshotted_once_before_invocation() -> None:
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
        "matrix_one_read_issuer",
        graph.challenge_key,
    )

    class OneReadCallback:
        reads = 0
        calls = 0

        def __get__(self, instance, owner):
            del instance, owner
            self.reads += 1
            if self.reads != 1:
                return object()

            def callback(observed_attempt):
                assert observed_attempt == attempt
                self.calls += 1
                return admission_runtime.AdmissionGrantIssuanceEcho(
                    AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                    AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                    "b04-matrix-one-read-issuance-token",
                )

            return callback

    callback = OneReadCallback()

    class ChangingIssuer:
        @property
        def issuer_ref(self):
            return issuer_ref

        evaluate_grant_issuance = callback

    issuance = admission_runtime.issue_truth_asset_admission_grant_record(
        ChangingIssuer(),
        attempt,
        issuance_id="b04_matrix_one_read_issuance",
        issuance_version="1.0",
    )
    assert issuance is not None
    assert issuance.outcome is AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED
    assert callback.reads == 1
    assert callback.calls == 1


@pytest.mark.parametrize("reentrant_seam", ("issuer_ref", "callback"))
def test_issuer_descriptor_reentrancy_cannot_hide_nested_issuance(
    reentrant_seam: str,
) -> None:
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
        f"matrix_reentrant_issuer_{reentrant_seam}",
        graph.challenge_key,
    )
    issuance_id = f"b04_matrix_reentrant_issuance_{reentrant_seam}"

    class ReentrantIssuer:
        attempted_reentry = False
        issuance_calls = 0
        nested_errors: list[ReferenceValidationError]

        def __init__(self) -> None:
            self.nested_errors = []

        def attempt_nested_issuance(self) -> None:
            if self.attempted_reentry:
                return
            self.attempted_reentry = True
            try:
                admission_runtime.issue_truth_asset_admission_grant_record(
                    self,
                    attempt,
                    issuance_id=issuance_id,
                    issuance_version="1.0",
                )
            except ReferenceValidationError as error:
                self.nested_errors.append(error)

        @property
        def issuer_ref(self):
            if reentrant_seam == "issuer_ref":
                self.attempt_nested_issuance()
            return issuer_ref

        @property
        def evaluate_grant_issuance(self):
            if reentrant_seam == "callback":
                self.attempt_nested_issuance()

            def callback(observed_attempt):
                assert observed_attempt == attempt
                self.issuance_calls += 1
                return admission_runtime.AdmissionGrantIssuanceEcho(
                    AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                    AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                    f"b04-matrix-reentrant-token-{reentrant_seam}",
                )

            return callback

    issuer = ReentrantIssuer()
    issuance = admission_runtime.issue_truth_asset_admission_grant_record(
        issuer,
        attempt,
        issuance_id=issuance_id,
        issuance_version="1.0",
    )
    assert issuance is not None
    assert issuance.outcome is AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED
    assert issuer.issuance_calls == 1
    assert len(issuer.nested_errors) == 1
    assert issuer.nested_errors[0].code == ReferenceInputCode.STALE_BINDING.value
    assert issuer.nested_errors[0].path == "/issuance_record_ref"


@pytest.mark.parametrize("concurrent", (False, True))
def test_exact_issuance_operation_is_permanently_single_use(
    concurrent: bool,
) -> None:
    label = "concurrent" if concurrent else "sequential"
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
        f"matrix_single_use_issuer_{label}",
        graph.challenge_key,
    )
    issuance_id = f"b04_matrix_single_use_issuance_{label}"

    class ChangingTokenIssuer:
        issuance_calls = 0

        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            self.issuance_calls += 1
            return admission_runtime.AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                f"b04-matrix-changing-token-{label}-{self.issuance_calls}",
            )

    issuer = ChangingTokenIssuer()

    def issue():
        try:
            return admission_runtime.issue_truth_asset_admission_grant_record(
                issuer,
                attempt,
                issuance_id=issuance_id,
                issuance_version="1.0",
            )
        except ReferenceValidationError as error:
            return error

    if concurrent:
        start = threading.Barrier(2)

        def concurrent_issue():
            start.wait()
            return issue()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = tuple(pool.map(lambda _index: concurrent_issue(), (1, 2)))
    else:
        results = (issue(), issue())

    records = tuple(
        item
        for item in results
        if type(item) is admission_runtime.TruthAssetAdmissionGrantIssuanceRecord
    )
    failures = tuple(item for item in results if type(item) is ReferenceValidationError)
    assert len(records) == 1
    assert len(failures) == 1
    assert failures[0].code == ReferenceInputCode.STALE_BINDING.value
    assert failures[0].path == "/issuance_record_ref"
    assert issuer.issuance_calls == 1

    grant = admission_runtime.create_truth_asset_admission_grant(
        records[0],
        capability_ref=issuer_ref,
        grant_id=f"b04_matrix_single_use_grant_{label}",
        grant_version="1.0",
    )
    assert grant.issuance_record_ref == records[0].to_ref()
    replay = issue()
    assert type(replay) is ReferenceValidationError
    assert replay.code == ReferenceInputCode.STALE_BINDING.value
    assert replay.path == "/issuance_record_ref"
    assert issuer.issuance_calls == 1


def test_issuance_provider_receives_an_isolated_attempt_snapshot() -> None:
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
    attempt_snapshot = admission_runtime._copy_admission_attempt(attempt)
    issuer_ref = fixture_runtime._identity(
        ReferenceIdentityKind.ADMISSION_ISSUER,
        "matrix_isolated_attempt_issuer",
        graph.challenge_key,
    )

    class MutatingIssuer:
        issuance_calls = 0

        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            assert observed_attempt is not attempt
            assert (
                observed_attempt.decision_profile_ref
                is not attempt.decision_profile_ref
            )
            provider_profile = observed_attempt.decision_profile_ref
            object.__setattr__(
                provider_profile,
                "identity_id",
                "b04_provider_mutated_profile",
            )
            object.__setattr__(observed_attempt, "decision_profile_ref", object())
            self.issuance_calls += 1
            return admission_runtime.AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                "b04-matrix-isolated-attempt-token",
            )

    issuer = MutatingIssuer()
    issuance = admission_runtime.issue_truth_asset_admission_grant_record(
        issuer,
        attempt,
        issuance_id="b04_matrix_isolated_attempt_issuance",
        issuance_version="1.0",
    )
    assert issuance is not None
    assert issuer.issuance_calls == 1
    assert attempt == attempt_snapshot
    assert issuance.attempt_binding == attempt
    issuance_bytes = canonical_bytes(issuance)
    grant = admission_runtime.create_truth_asset_admission_grant(
        issuance,
        capability_ref=issuer_ref,
        grant_id="b04_matrix_isolated_attempt_grant",
        grant_version="1.0",
    )
    assert canonical_bytes(issuance) == issuance_bytes
    assert grant.attempt_binding == attempt


def test_admission_provider_receives_isolated_attempt_and_grant_ref_snapshots() -> None:
    graph, attempt, run, artifact, comparison, issuance, grant, _ = (
        _positive_admission_inputs("isolated_authority_inputs")
    )
    attempt_snapshot = admission_runtime._copy_admission_attempt(attempt)
    issuance_bytes = canonical_bytes(issuance)
    grant_bytes = canonical_bytes(grant)
    issuance_ref = issuance.to_ref()
    grant_ref = grant.to_ref()
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "matrix_isolated_authority_receipt",
        graph.challenge_key,
    )

    class MutatingAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, observed_grant_ref):
            assert observed_attempt == attempt
            assert observed_attempt is not grant.attempt_binding
            assert (
                observed_attempt.decision_profile_ref
                is not grant.attempt_binding.decision_profile_ref
            )
            assert observed_grant_ref == grant_ref
            provider_profile = observed_attempt.decision_profile_ref
            object.__setattr__(
                provider_profile,
                "identity_id",
                "b04_authority_mutated_profile",
            )
            object.__setattr__(observed_attempt, "decision_profile_ref", object())
            object.__setattr__(
                observed_grant_ref,
                "content_digest",
                "sha256:" + ("0" * 64),
            )
            self.admission_calls += 1
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.ADMITTED,
                TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                receipt_ref,
            )

    authority = MutatingAuthority()
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_isolated_authority_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert authority.admission_calls == 1
    assert attempt == attempt_snapshot
    assert canonical_bytes(issuance) == issuance_bytes
    assert canonical_bytes(grant) == grant_bytes
    assert issuance.to_ref() == issuance_ref
    assert grant.to_ref() == grant_ref


@pytest.mark.parametrize(
    "failure_mode",
    (
        "exception",
        "wrong_type",
        "missing_all_slots",
        "missing_receipt",
        "graph_incompatible_echo",
        "matrix_incompatible_echo",
        "pseudo_outcome",
        "pseudo_reason",
        "partial_receipt",
        "invalid_receipt",
    ),
)
def test_admission_authority_failure_burns_at_most_once_grant(
    failure_mode: str,
) -> None:
    graph, attempt, run, artifact, comparison, issuance, grant, _ = (
        _positive_admission_inputs(f"authority_failure_burn_{failure_mode}")
    )
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        f"matrix_authority_failure_receipt_{failure_mode}",
        graph.challenge_key,
    )
    invalid_receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.ADMISSION_PROFILE,
        f"matrix_authority_failure_invalid_receipt_{failure_mode}",
        graph.challenge_key,
    )

    class FailingAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            self.admission_calls += 1
            if failure_mode == "exception":
                raise RuntimeError("protected provider detail")
            if failure_mode == "wrong_type":
                return object()
            if failure_mode == "missing_all_slots":
                return object.__new__(admission_runtime.TruthAssetAdmissionEcho)
            if failure_mode == "missing_receipt":
                forged = object.__new__(admission_runtime.TruthAssetAdmissionEcho)
                object.__setattr__(
                    forged,
                    "outcome",
                    TruthAssetAdmissionOutcome.ADMITTED,
                )
                object.__setattr__(
                    forged,
                    "reason",
                    TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                )
                return forged
            if failure_mode == "graph_incompatible_echo":
                return admission_runtime.TruthAssetAdmissionEcho(
                    TruthAssetAdmissionOutcome.REJECTED,
                    TruthAssetAdmissionReason.RUN_NOT_SUPPORTED,
                    receipt_ref,
                )
            if failure_mode == "matrix_incompatible_echo":
                forged = object.__new__(admission_runtime.TruthAssetAdmissionEcho)
                object.__setattr__(
                    forged,
                    "outcome",
                    TruthAssetAdmissionOutcome.ADMITTED,
                )
                object.__setattr__(
                    forged,
                    "reason",
                    TruthAssetAdmissionReason.RUN_NOT_SUPPORTED,
                )
                object.__setattr__(
                    forged,
                    "consumed_grant_receipt_ref",
                    receipt_ref,
                )
                return forged
            if failure_mode in {"pseudo_outcome", "pseudo_reason"}:
                forged = object.__new__(admission_runtime.TruthAssetAdmissionEcho)
                outcome = TruthAssetAdmissionOutcome.ADMITTED
                reason = TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED
                if failure_mode == "pseudo_outcome":
                    outcome = str.__new__(type(outcome), outcome.value)
                else:
                    reason = str.__new__(type(reason), reason.value)
                object.__setattr__(forged, "outcome", outcome)
                object.__setattr__(forged, "reason", reason)
                object.__setattr__(
                    forged,
                    "consumed_grant_receipt_ref",
                    receipt_ref,
                )
                return forged
            if failure_mode == "partial_receipt":
                return admission_runtime.TruthAssetAdmissionEcho(
                    TruthAssetAdmissionOutcome.ADMITTED,
                    TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                    object.__new__(type(receipt_ref)),
                )
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.ADMITTED,
                TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                invalid_receipt_ref,
            )

    failing = FailingAuthority()
    decision = None
    with pytest.raises((ReferenceServiceError, ReferenceValidationError)) as captured:
        decision = admission_runtime.decide_truth_asset_admission(
            failing,
            issuance,
            grant,
            policy=graph.policy,
            run=run,
            artifact=artifact,
            comparisons=(comparison,),
            decision_id="b04_matrix_failed_authority_decision",
            decision_version="1.0",
        )
    assert decision is None
    assert failing.admission_calls == 1
    if failure_mode == "exception":
        assert (
            captured.value.code
            == ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE.value
        )
        assert captured.value.path == "/admission_authority_ref"
        assert "protected provider detail" not in repr(captured.value)
    elif failure_mode in {"pseudo_outcome", "pseudo_reason"}:
        assert captured.value.code == ReferenceInputCode.OUTCOME_REASON_MISMATCH.value
        assert captured.value.path == "/reason"
    elif failure_mode in {
        "wrong_type",
        "missing_all_slots",
        "missing_receipt",
        "partial_receipt",
    }:
        assert (
            captured.value.code
            == ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE.value
        )
        assert captured.value.path == "/outcome"

    class ReplayAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            del observed_attempt, grant_ref
            self.admission_calls += 1
            raise AssertionError("consumed-grant authority callback must not run")

    replay_authority = ReplayAuthority()
    with pytest.raises(ReferenceValidationError) as replay:
        admission_runtime.decide_truth_asset_admission(
            replay_authority,
            issuance,
            grant,
            policy=graph.policy,
            run=run,
            artifact=artifact,
            comparisons=(comparison,),
            decision_id=f"b04_matrix_consumed_authority_decision_{failure_mode}",
            decision_version="1.0",
        )
    assert replay.value.code == ReferenceInputCode.STALE_BINDING.value
    assert replay.value.path == "/grant_ref"
    assert replay_authority.admission_calls == 0


def test_authority_can_reject_invalid_grant_on_its_first_claim() -> None:
    graph, attempt, run, artifact, comparison, issuance, grant, _ = (
        _positive_admission_inputs("first_claim_invalid_grant")
    )
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "matrix_first_claim_invalid_grant_receipt",
        graph.challenge_key,
    )

    class RejectingAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            self.admission_calls += 1
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.REJECTED,
                TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED,
                receipt_ref,
            )

    authority = RejectingAuthority()
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_first_claim_invalid_grant_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.REJECTED
    assert decision.reason is TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED
    assert authority.admission_calls == 1


def test_first_claim_invalid_grant_precedes_local_structural_failures() -> None:
    graph, attempt, run, _, comparison, issuance, grant, _ = _positive_admission_inputs(
        "invalid_grant_precedence"
    )
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "matrix_invalid_grant_precedence_receipt",
        graph.challenge_key,
    )

    class RejectingAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            self.admission_calls += 1
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.REJECTED,
                TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED,
                receipt_ref,
            )

    authority = RejectingAuthority()
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=None,
        comparisons=(comparison,),
        decision_id="b04_matrix_invalid_grant_precedence_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.REJECTED
    assert decision.reason is TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED
    assert authority.admission_calls == 1


def test_reentrant_admission_replay_is_rejected_before_second_callback() -> None:
    graph, attempt, run, artifact, comparison, issuance, grant, _ = (
        _positive_admission_inputs("reentrant_grant_claim")
    )
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "matrix_reentrant_grant_receipt",
        graph.challenge_key,
    )

    class ReentrantAuthority:
        admission_calls = 0
        nested_failure: tuple[str, str | None] | None = None

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            self.admission_calls += 1
            with pytest.raises(ReferenceValidationError) as nested:
                admission_runtime.decide_truth_asset_admission(
                    self,
                    issuance,
                    grant,
                    policy=graph.policy,
                    run=run,
                    artifact=artifact,
                    comparisons=(comparison,),
                    decision_id="b04_matrix_nested_reentrant_decision",
                    decision_version="1.0",
                )
            self.nested_failure = (nested.value.code, nested.value.path)
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.ADMITTED,
                TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                receipt_ref,
            )

    authority = ReentrantAuthority()
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_outer_reentrant_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert authority.admission_calls == 1
    assert authority.nested_failure == (
        ReferenceInputCode.STALE_BINDING.value,
        "/grant_ref",
    )


def test_concurrent_admission_replay_has_one_terminal_callback() -> None:
    graph, attempt, run, artifact, comparison, issuance, grant, _ = (
        _positive_admission_inputs("concurrent_grant_claim")
    )
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "matrix_concurrent_grant_receipt",
        graph.challenge_key,
    )
    worker_count = 8
    start = threading.Barrier(worker_count)
    call_lock = threading.Lock()

    class ConcurrentAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            with call_lock:
                self.admission_calls += 1
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.ADMITTED,
                TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                receipt_ref,
            )

    authority = ConcurrentAuthority()

    def claim(worker: int):
        start.wait()
        try:
            return admission_runtime.decide_truth_asset_admission(
                authority,
                issuance,
                grant,
                policy=graph.policy,
                run=run,
                artifact=artifact,
                comparisons=(comparison,),
                decision_id=f"b04_matrix_concurrent_decision_{worker}",
                decision_version="1.0",
            )
        except ReferenceValidationError as error:
            return error.code, error.path

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        results = tuple(pool.map(claim, range(worker_count)))

    decisions = tuple(
        result
        for result in results
        if isinstance(result, admission_runtime.TruthAssetAdmissionDecisionRecord)
    )
    failures = tuple(result for result in results if isinstance(result, tuple))
    assert len(decisions) == 1
    assert decisions[0].outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert failures == ((ReferenceInputCode.STALE_BINDING.value, "/grant_ref"),) * (
        worker_count - 1
    )
    assert authority.admission_calls == 1


def test_caller_metadata_is_validated_before_admission_capabilities() -> None:
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
        "matrix_metadata_issuer",
        graph.challenge_key,
    )

    class CountingIssuer:
        issuance_calls = 0

        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            self.issuance_calls += 1
            return admission_runtime.AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                "b04-matrix-metadata-issuance-token",
            )

    issuer = CountingIssuer()
    with pytest.raises(ReferenceValidationError) as invalid_issuance_id:
        admission_runtime.issue_truth_asset_admission_grant_record(
            issuer,
            attempt,
            issuance_id="",
            issuance_version="1.0",
        )
    assert invalid_issuance_id.value.path == "/issuance_id"
    assert issuer.issuance_calls == 0
    assert (
        admission_runtime.issue_truth_asset_admission_grant_record(
            issuer,
            attempt,
            issuance_id="b04_matrix_metadata_issuance",
            issuance_version="1.0",
        )
        is not None
    )
    assert issuer.issuance_calls == 1

    (
        graph,
        attempt,
        run,
        artifact,
        comparison,
        issuance,
        grant,
        _,
    ) = _positive_admission_inputs("decision_metadata")
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "matrix_decision_metadata_receipt",
        graph.challenge_key,
    )

    class CountingAuthority:
        admission_calls = 0
        authority_ref_reads = 0

        @property
        def admission_authority_ref(self):
            self.authority_ref_reads += 1
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            self.admission_calls += 1
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.ADMITTED,
                TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                receipt_ref,
            )

    authority = CountingAuthority()
    with pytest.raises(ReferenceValidationError) as invalid_decision_id:
        admission_runtime.decide_truth_asset_admission(
            authority,
            issuance,
            grant,
            policy=graph.policy,
            run=run,
            artifact=artifact,
            comparisons=(comparison,),
            decision_id="",
            decision_version="1.0",
        )
    assert invalid_decision_id.value.path == "/decision_id"
    assert authority.admission_calls == 0
    assert authority.authority_ref_reads == 0

    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_validated_metadata_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert authority.admission_calls == 1
    assert authority.authority_ref_reads > 0


def test_partial_admission_carriers_fail_before_capability_or_claim() -> None:
    graph, attempt, run, artifact, comparison, issuance, grant, _ = (
        _positive_admission_inputs("partial_carriers")
    )
    with pytest.raises(ReferenceValidationError) as partial_issuance_for_grant:
        admission_runtime.create_truth_asset_admission_grant(
            object.__new__(admission_runtime.TruthAssetAdmissionGrantIssuanceRecord),
            capability_ref=issuance.issuer_ref,
            grant_id="b04_matrix_partial_issuance_grant",
            grant_version="1.0",
        )
    assert partial_issuance_for_grant.value.code == ReferenceInputCode.WRONG_TYPE.value
    assert partial_issuance_for_grant.value.path == "/issuance_record_ref"

    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "matrix_partial_carrier_receipt",
        graph.challenge_key,
    )

    class CountingAuthority:
        admission_calls = 0
        authority_ref_reads = 0

        @property
        def admission_authority_ref(self):
            self.authority_ref_reads += 1
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            self.admission_calls += 1
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.ADMITTED,
                TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                receipt_ref,
            )

    authority = CountingAuthority()
    with pytest.raises(ReferenceValidationError) as partial_grant:
        admission_runtime.decide_truth_asset_admission(
            authority,
            issuance,
            object.__new__(admission_runtime.TruthAssetAdmissionGrant),
            policy=graph.policy,
            run=run,
            artifact=artifact,
            comparisons=(comparison,),
            decision_id="b04_matrix_partial_grant_decision",
            decision_version="1.0",
        )
    assert partial_grant.value.code == ReferenceInputCode.WRONG_TYPE.value
    assert partial_grant.value.path == "/grant_ref"
    assert authority.authority_ref_reads == 0
    assert authority.admission_calls == 0

    with pytest.raises(ReferenceValidationError) as partial_issuance:
        admission_runtime.decide_truth_asset_admission(
            authority,
            object.__new__(admission_runtime.TruthAssetAdmissionGrantIssuanceRecord),
            grant,
            policy=graph.policy,
            run=run,
            artifact=artifact,
            comparisons=(comparison,),
            decision_id="b04_matrix_partial_issuance_decision",
            decision_version="1.0",
        )
    assert partial_issuance.value.code == ReferenceInputCode.WRONG_TYPE.value
    assert partial_issuance.value.path == "/issuance_record_ref"
    assert authority.authority_ref_reads == 0
    assert authority.admission_calls == 0

    partial_graph_inputs = (
        (
            "policy",
            object.__new__(type(graph.policy)),
            run,
            artifact,
            (comparison,),
            "/policy_ref",
        ),
        (
            "run",
            graph.policy,
            object.__new__(type(run)),
            artifact,
            (comparison,),
            "/run_ref",
        ),
        (
            "artifact",
            graph.policy,
            run,
            object.__new__(type(artifact)),
            (comparison,),
            "/artifact_ref",
        ),
        (
            "comparison",
            graph.policy,
            run,
            artifact,
            (object.__new__(type(comparison)),),
            "/comparison_refs",
        ),
    )
    for (
        label,
        supplied_policy,
        supplied_run,
        supplied_artifact,
        supplied_comparisons,
        expected_path,
    ) in partial_graph_inputs:
        with pytest.raises(ReferenceValidationError) as partial_graph:
            admission_runtime.decide_truth_asset_admission(
                authority,
                issuance,
                grant,
                policy=supplied_policy,
                run=supplied_run,
                artifact=supplied_artifact,
                comparisons=supplied_comparisons,
                decision_id=f"b04_matrix_partial_{label}_decision",
                decision_version="1.0",
            )
        assert partial_graph.value.code == ReferenceInputCode.WRONG_TYPE.value
        assert partial_graph.value.path == expected_path
        assert authority.authority_ref_reads == 0
        assert authority.admission_calls == 0

    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id="b04_matrix_valid_after_partial_carriers_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert authority.authority_ref_reads > 0
    assert authority.admission_calls == 1


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


def test_authority_cannot_change_the_registered_graph_via_caller_aliases() -> None:
    graph, attempt, run, artifact, comparison, issuance, grant, _ = (
        _positive_admission_inputs("caller_graph_aliases")
    )
    caller_inputs = tuple(
        decode_canonical_bytes(canonical_bytes(record), type(record))
        for record in (
            issuance,
            grant,
            graph.policy,
            run,
            artifact,
            comparison,
        )
    )
    (
        caller_issuance,
        caller_grant,
        caller_policy,
        caller_run,
        caller_artifact,
        caller_comparison,
    ) = caller_inputs
    snapshots = tuple(
        decode_canonical_bytes(canonical_bytes(record), type(record))
        for record in caller_inputs
    )
    (
        issuance_snapshot,
        grant_snapshot,
        policy_snapshot,
        run_snapshot,
        artifact_snapshot,
        comparison_snapshot,
    ) = snapshots
    receipt_ref = fixture_runtime._identity(
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "matrix_caller_graph_alias_receipt",
        graph.challenge_key,
    )

    class MutatingAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return attempt.admission_authority_ref

        def evaluate_admission(self, observed_attempt, observed_grant_ref):
            assert observed_attempt == attempt
            assert observed_grant_ref == grant_snapshot.to_ref()
            self.admission_calls += 1
            object.__setattr__(
                caller_issuance,
                "issuance_id",
                "b04_mutated_caller_issuance",
            )
            object.__setattr__(
                caller_grant,
                "grant_id",
                "b04_mutated_caller_grant",
            )
            object.__setattr__(
                caller_policy,
                "policy_id",
                "b04_mutated_caller_policy",
            )
            object.__setattr__(caller_run, "run_id", "b04_mutated_caller_run")
            object.__setattr__(
                caller_artifact,
                "artifact_id",
                "b04_mutated_caller_artifact",
            )
            object.__setattr__(
                caller_comparison,
                "comparison_id",
                "b04_mutated_caller_comparison",
            )
            return admission_runtime.TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.ADMITTED,
                TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
                receipt_ref,
            )

    authority = MutatingAuthority()
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        caller_issuance,
        caller_grant,
        policy=caller_policy,
        run=caller_run,
        artifact=caller_artifact,
        comparisons=(caller_comparison,),
        decision_id="b04_matrix_caller_graph_alias_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert authority.admission_calls == 1

    with pytest.raises(ReferenceValidationError) as replay:
        admission_runtime.decide_truth_asset_admission(
            authority,
            issuance_snapshot,
            grant_snapshot,
            policy=policy_snapshot,
            run=run_snapshot,
            artifact=artifact_snapshot,
            comparisons=(comparison_snapshot,),
            decision_id="b04_matrix_caller_graph_alias_replay",
            decision_version="1.0",
        )
    assert replay.value.code == ReferenceInputCode.STALE_BINDING.value
    assert replay.value.path == "/grant_ref"
    assert authority.admission_calls == 1

    asset = admission_runtime.create_truth_asset(
        decision,
        issuance_snapshot,
        grant_snapshot,
        artifact_snapshot,
        run_snapshot,
        truth_asset_id="b04_matrix_caller_graph_alias_asset",
        truth_asset_version="1.0",
    )
    assert asset.admission_decision_ref == decision.to_ref()
    assert asset.admission_grant_ref == grant_snapshot.to_ref()
    assert asset.admission_issuance_record_ref == issuance_snapshot.to_ref()


@pytest.mark.parametrize("forgery_kind", ("run_outcome", "evidence_role"))
def test_forged_run_enum_cannot_cross_canonical_admission_snapshot(
    forgery_kind: str,
) -> None:
    graph, _attempt, run, artifact, comparison, issuance, grant, delegate = (
        _positive_admission_inputs(f"forged_run_enum_{forgery_kind}")
    )
    forged_run = decode_canonical_bytes(canonical_bytes(run), ReferenceRunRecord)
    if forgery_kind == "run_outcome":
        pseudo_supported = str.__new__(
            ReferenceRunOutcome,
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE.value,
        )
        object.__setattr__(
            pseudo_supported,
            "_name_",
            ReferenceRunOutcome.SUPPORTED.name,
        )
        object.__setattr__(
            pseudo_supported,
            "_value_",
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE.value,
        )
        assert pseudo_supported.name == ReferenceRunOutcome.SUPPORTED.name
        assert (
            pseudo_supported.value == ReferenceRunOutcome.INFRASTRUCTURE_FAILURE.value
        )
        assert pseudo_supported is not ReferenceRunOutcome.SUPPORTED
        object.__setattr__(forged_run, "outcome", pseudo_supported)
    else:
        pseudo_role = str.__new__(EvidenceRole, EvidenceRole.NUMERICAL.value)
        object.__setattr__(
            pseudo_role,
            "_name_",
            EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION.name,
        )
        object.__setattr__(
            pseudo_role,
            "_value_",
            EvidenceRole.NUMERICAL.value,
        )
        assert pseudo_role is not EvidenceRole.NUMERICAL
        forged_binding = object.__new__(EvidenceRoleBinding)
        object.__setattr__(forged_binding, "role", pseudo_role)
        object.__setattr__(forged_binding, "hybrid_role_ref", None)
        object.__setattr__(forged_run, "evidence_role_binding", forged_binding)

    with pytest.raises(ReferenceCanonicalEncodingError):
        canonical_bytes(forged_run)

    class CountingAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return delegate.admission_authority_ref

        def evaluate_admission(self, observed_attempt, observed_grant_ref):
            self.admission_calls += 1
            return delegate.evaluate_admission(
                observed_attempt,
                observed_grant_ref,
            )

    authority = CountingAuthority()
    with pytest.raises(ReferenceValidationError) as captured:
        admission_runtime.decide_truth_asset_admission(
            authority,
            issuance,
            grant,
            policy=graph.policy,
            run=forged_run,
            artifact=artifact,
            comparisons=(comparison,),
            decision_id=f"b04_matrix_forged_run_enum_decision_{forgery_kind}",
            decision_version="1.0",
        )
    assert captured.value.code == ReferenceInputCode.WRONG_TYPE.value
    assert captured.value.path == "/run_ref"
    assert authority.admission_calls == 0

    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id=f"b04_matrix_recovered_run_enum_decision_{forgery_kind}",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.ADMITTED
    assert authority.admission_calls == 1


@pytest.mark.parametrize("malformed_kind", ("false", "zero", "partial"))
def test_malformed_supersedes_does_not_consume_positive_graph(
    malformed_kind: str,
) -> None:
    graph, _attempt_binding, run, artifact, comparison, issuance, grant, authority = (
        _positive_admission_inputs(f"malformed_supersedes_{malformed_kind}")
    )
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id=f"b04_matrix_malformed_supersedes_decision_{malformed_kind}",
        decision_version="1.0",
    )
    assert decision is not None
    malformed = {
        "false": False,
        "zero": 0,
        "partial": object.__new__(OptionalBinding),
    }[malformed_kind]
    with pytest.raises(ReferenceValidationError) as captured:
        admission_runtime.create_truth_asset(
            decision,
            issuance,
            grant,
            artifact,
            run,
            truth_asset_id=f"b04_matrix_malformed_supersedes_asset_{malformed_kind}",
            truth_asset_version="1.0",
            supersedes=malformed,
        )
    assert captured.value.code == ReferenceInputCode.WRONG_TYPE.value
    assert captured.value.path == "/supersedes"

    asset = admission_runtime.create_truth_asset(
        decision,
        issuance,
        grant,
        artifact,
        run,
        truth_asset_id=f"b04_matrix_recovered_supersedes_asset_{malformed_kind}",
        truth_asset_version="1.0",
    )
    assert not asset.supersedes.is_present


@pytest.mark.parametrize(
    ("malformed_kind", "expected_code"),
    (
        ("absent_with_value", ReferenceInputCode.INCOMPLETE_BINDING),
        ("present_without_value", ReferenceInputCode.INCOMPLETE_BINDING),
        ("pseudo_absent", ReferenceInputCode.INVALID_VALUE),
        ("pseudo_present", ReferenceInputCode.INVALID_VALUE),
    ),
)
def test_invalid_exact_supersedes_binding_does_not_consume_positive_graph(
    malformed_kind: str,
    expected_code: ReferenceInputCode,
) -> None:
    graph, _attempt_binding, run, artifact, comparison, issuance, grant, authority = (
        _positive_admission_inputs(f"invalid_exact_supersedes_{malformed_kind}")
    )
    decision = admission_runtime.decide_truth_asset_admission(
        authority,
        issuance,
        grant,
        policy=graph.policy,
        run=run,
        artifact=artifact,
        comparisons=(comparison,),
        decision_id=f"b04_matrix_invalid_exact_supersedes_decision_{malformed_kind}",
        decision_version="1.0",
    )
    assert decision is not None

    malformed = object.__new__(OptionalBinding)
    tag = {
        "absent_with_value": OptionalBindingTag.ABSENT,
        "present_without_value": OptionalBindingTag.PRESENT,
        "pseudo_absent": str.__new__(
            OptionalBindingTag,
            OptionalBindingTag.ABSENT.value,
        ),
        "pseudo_present": str.__new__(
            OptionalBindingTag,
            OptionalBindingTag.PRESENT.value,
        ),
    }[malformed_kind]
    value = object() if malformed_kind == "absent_with_value" else None
    object.__setattr__(malformed, "tag", tag)
    object.__setattr__(malformed, "value", value)

    with pytest.raises(ReferenceValidationError) as captured:
        admission_runtime.create_truth_asset(
            decision,
            issuance,
            grant,
            artifact,
            run,
            truth_asset_id=f"b04_matrix_invalid_exact_supersedes_asset_{malformed_kind}",
            truth_asset_version="1.0",
            supersedes=malformed,
        )
    assert captured.value.code == expected_code.value
    assert captured.value.path == "/value"

    asset = admission_runtime.create_truth_asset(
        decision,
        issuance,
        grant,
        artifact,
        run,
        truth_asset_id=f"b04_matrix_recovered_exact_supersedes_asset_{malformed_kind}",
        truth_asset_version="1.0",
    )
    assert not asset.supersedes.is_present


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
