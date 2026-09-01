"""Closed positive-only admission boundaries frozen by B-04-D11."""

from __future__ import annotations

import inspect
import pickle
from dataclasses import fields

import pytest

import carbon.evaluation.admission as admission_module
from carbon.authoring.canonical import tagged_sha256
from carbon.authoring.refs import ChallengeScope, owner_ref
from carbon.evaluation.admission import (
    AdmissionGrantIssuanceEcho,
    TruthAsset,
    TruthAssetAdmissionDecisionRecord,
    TruthAssetAdmissionEcho,
    TruthAssetAdmissionGrant,
    TruthAssetAdmissionGrantIssuanceRecord,
    create_truth_asset,
    create_truth_asset_admission_grant,
    decide_truth_asset_admission,
    issue_truth_asset_admission_grant_record,
    select_admission_grant_issuance_terminal,
    select_truth_asset_admission_terminal,
)
from carbon.evaluation.canonical import canonical_bytes, decode_canonical_bytes
from carbon.evaluation.enums import (
    ADMISSION_ISSUANCE_OUTCOME_REASON_COMPATIBILITY,
    ADMISSION_ISSUANCE_REASON_PRECEDENCE,
    ADMISSION_OUTCOME_REASON_COMPATIBILITY,
    ADMISSION_REASON_PRECEDENCE,
    AdmissionGrantIssuanceOutcome,
    AdmissionGrantIssuanceReason,
    ReferenceIdentityKind,
    TruthAssetAdmissionOutcome,
    TruthAssetAdmissionReason,
)
from carbon.evaluation.errors import (
    ReferenceCanonicalDecodingError,
    ReferenceInputCode,
    ReferenceServiceCode,
    ReferenceServiceError,
    ReferenceValidationError,
)
from carbon.evaluation.fixtures import build_b04_fixture_reference_graph
from carbon.evaluation.model import (
    AdmissionArtifactBinding,
    AdmissionAttemptBinding,
    OptionalBinding,
    PinnedReferenceIdentity,
    QualificationBinding,
)
from carbon.evaluation.refs import (
    TruthAssetAdmissionDecisionRecordRef,
    TruthAssetAdmissionGrantIssuanceRecordRef,
    TruthAssetAdmissionGrantRef,
)


def test_admission_record_declaration_order_matches_d11() -> None:
    expected = {
        TruthAssetAdmissionGrantIssuanceRecord: (
            "attempt_binding",
            "challenge_key",
            "issuance_id",
            "issuance_token",
            "issuance_version",
            "issuer_ref",
            "outcome",
            "reason",
        ),
        TruthAssetAdmissionGrant: (
            "attempt_binding",
            "capability_ref",
            "challenge_key",
            "grant_id",
            "grant_version",
            "issuance_record_ref",
            "issuance_token",
            "issuer_ref",
        ),
        TruthAssetAdmissionDecisionRecord: (
            "admission_authority_ref",
            "attempt_binding",
            "challenge_key",
            "consumed_grant_receipt_ref",
            "decision_id",
            "decision_version",
            "grant_ref",
            "issuance_record_ref",
            "outcome",
            "reason",
        ),
        TruthAsset: (
            "admission_decision_ref",
            "admission_grant_ref",
            "admission_issuance_record_ref",
            "applicability_assessment",
            "artifact_ref",
            "authority_function",
            "case_ref",
            "challenge_key",
            "comparison_refs",
            "conditioning_assessment",
            "configuration_ref",
            "dependency_disclosures",
            "disclosure_policy_ref",
            "environment_ref",
            "evidence_role_binding",
            "execution_target",
            "hardware_ref",
            "implementation_ref",
            "known_limitations",
            "method_ref",
            "policy_ref",
            "precision_ref",
            "provenance_binding",
            "qualification_evidence_ref",
            "representation_ref",
            "rights_profile_ref",
            "run_ref",
            "scope_binding",
            "source_class",
            "supersedes",
            "truth_asset_id",
            "truth_asset_version",
            "uncertainty_binding",
            "use_restrictions",
        ),
    }
    for record_type, names in expected.items():
        assert tuple(item.name for item in fields(record_type)) == names


def test_admission_selectors_enforce_exact_total_precedence() -> None:
    assert select_admission_grant_issuance_terminal(
        tuple(reversed(ADMISSION_ISSUANCE_REASON_PRECEDENCE))
    ) == (
        AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_UNAVAILABLE,
        AdmissionGrantIssuanceReason.ADMISSION_GRAPH_CROSS_BINDING_MISMATCH,
    )
    assert select_truth_asset_admission_terminal(
        tuple(reversed(ADMISSION_REASON_PRECEDENCE))
    ) == (
        TruthAssetAdmissionOutcome.REJECTED,
        TruthAssetAdmissionReason.GRANT_INVALID_OR_CONSUMED,
    )


def test_admission_selector_maps_are_immutable_reversals_of_d11_matrices() -> None:
    expected_issuance = {
        reason: outcome
        for outcome, reasons in ADMISSION_ISSUANCE_OUTCOME_REASON_COMPATIBILITY.items()
        for reason in reasons
    }
    expected_admission = {
        reason: outcome
        for outcome, reasons in ADMISSION_OUTCOME_REASON_COMPATIBILITY.items()
        for reason in reasons
    }
    assert dict(admission_module._ADMISSION_ISSUANCE_OUTCOMES) == expected_issuance
    assert dict(admission_module._ADMISSION_OUTCOMES) == expected_admission
    with pytest.raises(TypeError):
        admission_module._ADMISSION_ISSUANCE_OUTCOMES[
            AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED
        ] = AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_UNAVAILABLE
    with pytest.raises(TypeError):
        admission_module._ADMISSION_OUTCOMES[
            TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED
        ] = TruthAssetAdmissionOutcome.REJECTED


@pytest.mark.parametrize(
    "selector",
    (
        select_admission_grant_issuance_terminal,
        select_truth_asset_admission_terminal,
    ),
)
def test_admission_selectors_reject_empty_open_or_duplicate_inputs(selector) -> None:
    with pytest.raises(ReferenceValidationError):
        selector(())
    with pytest.raises(ReferenceValidationError) as captured:
        selector([])
    assert captured.value.code == ReferenceInputCode.WRONG_TYPE.value
    reason = (
        AdmissionGrantIssuanceReason.ADMISSION_GRANT_SCOPE_UNAVAILABLE
        if selector is select_admission_grant_issuance_terminal
        else TruthAssetAdmissionReason.RUN_NOT_SUPPORTED
    )
    with pytest.raises(ReferenceValidationError) as captured:
        selector((reason, reason))
    assert captured.value.code == ReferenceInputCode.DUPLICATE_IDENTITY.value
    pseudo_reason = str.__new__(type(reason), reason.value)
    assert pseudo_reason is not reason
    with pytest.raises(ReferenceValidationError) as captured:
        selector((pseudo_reason,))
    assert captured.value.code == ReferenceInputCode.INVALID_VALUE.value
    assert captured.value.path == "/reason"


def test_absent_issuer_or_authority_fabricates_no_terminal_record() -> None:
    attempt = object.__new__(AdmissionAttemptBinding)
    assert (
        issue_truth_asset_admission_grant_record(
            None,
            attempt,
            issuance_id="b04_absent_issuer",
            issuance_version="1.0",
        )
        is None
    )


def _identity(
    challenge_key,
    identity_kind: ReferenceIdentityKind,
    label: str,
) -> PinnedReferenceIdentity:
    return PinnedReferenceIdentity(
        challenge_key,
        tagged_sha256(label.encode("ascii")),
        f"b04_admission_{label}",
        identity_kind,
        "1.0",
    )


def _owner(challenge_key, kind: str, label: str) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(challenge_key),
        object_id=f"b04_admission_{label}_{kind}",
        object_version="1.0",
        content_digest=tagged_sha256(f"{kind}:{label}".encode("ascii")),
    )


def _unadmitted_truth_asset_bytes(graph: object) -> bytes:
    """Encode a schema-shaped hostile carrier without admitting an asset."""

    challenge_key = graph.challenge_key
    run = graph.primary_run

    def nominal(ref_type: type, label: str) -> object:
        return ref_type(challenge_key, tagged_sha256(label.encode("ascii")))

    values = {
        "admission_decision_ref": nominal(
            TruthAssetAdmissionDecisionRecordRef,
            "b04_unadmitted_decision",
        ),
        "admission_grant_ref": nominal(
            TruthAssetAdmissionGrantRef,
            "b04_unadmitted_grant",
        ),
        "admission_issuance_record_ref": nominal(
            TruthAssetAdmissionGrantIssuanceRecordRef,
            "b04_unadmitted_issuance",
        ),
        "applicability_assessment": run.applicability_assessment,
        "artifact_ref": graph.primary_artifact.to_ref(),
        "authority_function": run.authority_function,
        "case_ref": run.case_ref,
        "challenge_key": challenge_key,
        "comparison_refs": (graph.comparison.to_ref(),),
        "conditioning_assessment": run.conditioning_assessment,
        "configuration_ref": run.configuration_ref,
        "dependency_disclosures": run.provenance_binding.dependency_disclosures,
        "disclosure_policy_ref": graph.policy.disclosure_policy_ref,
        "environment_ref": run.environment_ref,
        "evidence_role_binding": run.evidence_role_binding,
        "execution_target": run.answer_key_authority_target,
        "hardware_ref": run.hardware_ref,
        "implementation_ref": run.implementation_ref,
        "known_limitations": (),
        "method_ref": run.method_ref,
        "policy_ref": run.policy_ref,
        "precision_ref": run.precision_ref,
        "provenance_binding": run.provenance_binding,
        "qualification_evidence_ref": _owner(
            challenge_key,
            "qualification_evidence_bundle",
            "unadmitted",
        ),
        "representation_ref": run.representation_ref,
        "rights_profile_ref": graph.policy.rights_profile_ref,
        "run_ref": run.to_ref(),
        "scope_binding": run.scope_binding,
        "source_class": run.source_class,
        "supersedes": OptionalBinding.absent(),
        "truth_asset_id": "b04_unadmitted_truth_asset",
        "truth_asset_version": "1.0",
        "uncertainty_binding": run.uncertainty_binding,
        "use_restrictions": (_owner(challenge_key, "permitted_use", "unadmitted"),),
    }
    carrier = object.__new__(TruthAsset)
    for name, value in values.items():
        object.__setattr__(carrier, name, value)
    return canonical_bytes(carrier)


def test_truth_asset_direct_private_and_canonical_bypasses_fail_closed() -> None:
    graph = build_b04_fixture_reference_graph()
    payload = _unadmitted_truth_asset_bytes(graph)

    assert not hasattr(admission_module, "_TRUTH_ASSET_TOKEN")
    assert not hasattr(admission_module, "_new_truth_asset")
    assert not hasattr(admission_module, "_build_truth_asset_authority_operations")
    assert "_token" not in inspect.signature(create_truth_asset).parameters
    with pytest.raises(TypeError):
        TruthAsset()
    with pytest.raises(ReferenceValidationError) as private_lookup:
        admission_module._reconstruct_admitted_truth_asset(
            _canonical_content_digest=tagged_sha256(payload),
            challenge_key=graph.challenge_key,
        )
    assert private_lookup.value.code == ReferenceInputCode.INCOMPLETE_BINDING.value
    with pytest.raises(ReferenceCanonicalDecodingError) as canonical_bypass:
        decode_canonical_bytes(payload, TruthAsset)
    assert canonical_bypass.value.__cause__ is None
    assert canonical_bypass.value.__context__ is None


def test_admission_graph_requires_primary_role_and_every_registered_witness() -> None:
    graph = build_b04_fixture_reference_graph()
    challenge = graph.challenge_key
    authority_ref = _identity(
        challenge,
        ReferenceIdentityKind.ADMISSION_AUTHORITY,
        "role_check_authority",
    )
    qualification = QualificationBinding.bound(
        _owner(challenge, "qualification_evidence_bundle", "role_check")
    )
    use_restrictions = (_owner(challenge, "permitted_use", "role_check"),)

    witness_attempt = AdmissionAttemptBinding(
        authority_ref,
        graph.policy.answer_key_authority_target.value,
        AdmissionArtifactBinding.bound(graph.witness_artifact.to_ref()),
        graph.case_ref,
        (),
        _identity(
            challenge,
            ReferenceIdentityKind.ADMISSION_PROFILE,
            "witness_role_profile",
        ),
        graph.policy.disclosure_policy_ref,
        graph.policy.answer_key_authority_target.value,
        graph.policy.provenance_policy_ref,
        qualification,
        graph.policy.rights_profile_ref,
        graph.witness_run.to_ref(),
        use_restrictions,
        graph.policy.registered_witness_targets,
    )
    witness_failures = admission_module._validate_admission_graph(
        witness_attempt,
        graph.policy,
        graph.witness_run,
        graph.witness_artifact,
        (),
    )
    assert TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH in witness_failures

    omitted_witness_attempt = AdmissionAttemptBinding(
        authority_ref,
        graph.policy.answer_key_authority_target.value,
        AdmissionArtifactBinding.bound(graph.primary_artifact.to_ref()),
        graph.case_ref,
        (),
        _identity(
            challenge,
            ReferenceIdentityKind.ADMISSION_PROFILE,
            "omitted_witness_profile",
        ),
        graph.policy.disclosure_policy_ref,
        graph.policy.answer_key_authority_target.value,
        graph.policy.provenance_policy_ref,
        qualification,
        graph.policy.rights_profile_ref,
        graph.primary_run.to_ref(),
        use_restrictions,
        (),
    )
    omitted_failures = admission_module._validate_admission_graph(
        omitted_witness_attempt,
        graph.policy,
        graph.primary_run,
        graph.primary_artifact,
        (),
    )
    assert TruthAssetAdmissionReason.POLICY_OR_IDENTITY_MISMATCH in omitted_failures


def test_fixture_artifact_is_rejected_after_structural_grant_issuance() -> None:
    graph = build_b04_fixture_reference_graph()
    challenge = graph.challenge_key
    authority_ref = _identity(
        challenge,
        ReferenceIdentityKind.ADMISSION_AUTHORITY,
        "authority",
    )
    issuer_ref = _identity(
        challenge,
        ReferenceIdentityKind.ADMISSION_ISSUER,
        "issuer",
    )
    attempt = AdmissionAttemptBinding(
        authority_ref,
        graph.policy.answer_key_authority_target.value,
        AdmissionArtifactBinding.bound(graph.primary_artifact.to_ref()),
        graph.case_ref,
        (graph.comparison.to_ref(),),
        _identity(
            challenge,
            ReferenceIdentityKind.ADMISSION_PROFILE,
            "profile",
        ),
        graph.policy.disclosure_policy_ref,
        graph.policy.answer_key_authority_target.value,
        graph.policy.provenance_policy_ref,
        QualificationBinding.bound(
            _owner(challenge, "qualification_evidence_bundle", "qualification")
        ),
        graph.policy.rights_profile_ref,
        graph.primary_run.to_ref(),
        (_owner(challenge, "permitted_use", "fixture_tests"),),
        graph.policy.registered_witness_targets,
    )

    class Issuer:
        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            return AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                "b04-fixture-admission-issuance",
            )

    issuance = issue_truth_asset_admission_grant_record(
        Issuer(),
        attempt,
        issuance_id="b04_fixture_admission_issuance",
        issuance_version="1.0",
    )
    assert issuance is not None
    with pytest.raises(ReferenceValidationError) as mismatched_capability:
        create_truth_asset_admission_grant(
            issuance,
            capability_ref=_identity(
                challenge,
                ReferenceIdentityKind.ADMISSION_ISSUER,
                "different_capability",
            ),
            grant_id="b04_mismatched_admission_grant",
            grant_version="1.0",
        )
    assert mismatched_capability.value.code == ReferenceInputCode.STALE_BINDING.value
    grant = create_truth_asset_admission_grant(
        issuance,
        capability_ref=issuer_ref,
        grant_id="b04_fixture_admission_grant",
        grant_version="1.0",
    )
    with pytest.raises(ReferenceValidationError) as repeated_grant:
        create_truth_asset_admission_grant(
            issuance,
            capability_ref=issuer_ref,
            grant_id="b04_fixture_admission_grant",
            grant_version="1.0",
        )
    assert repeated_grant.value.code == ReferenceInputCode.STALE_BINDING.value
    receipt_ref = _identity(
        challenge,
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "receipt",
    )

    class Authority:
        @property
        def admission_authority_ref(self):
            return authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            return TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.REJECTED,
                TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE,
                receipt_ref,
            )

    decision = decide_truth_asset_admission(
        Authority(),
        issuance,
        grant,
        policy=graph.policy,
        run=graph.primary_run,
        artifact=graph.primary_artifact,
        comparisons=(graph.comparison,),
        decision_id="b04_fixture_admission_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.REJECTED
    assert decision.reason is TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE
    with pytest.raises(ReferenceValidationError) as mismatched_decision_authority:
        admission_module._new_admission_decision(
            admission_authority_ref=_identity(
                challenge,
                ReferenceIdentityKind.ADMISSION_AUTHORITY,
                "mismatched_decision_authority",
            ),
            attempt_binding=decision.attempt_binding,
            challenge_key=decision.challenge_key,
            consumed_grant_receipt_ref=decision.consumed_grant_receipt_ref,
            decision_id="b04_mismatched_authority_decision",
            decision_version="1.0",
            grant_ref=decision.grant_ref,
            issuance_record_ref=decision.issuance_record_ref,
            outcome=decision.outcome,
            reason=decision.reason,
        )
    assert (
        mismatched_decision_authority.value.code
        == ReferenceInputCode.STALE_BINDING.value
    )
    assert mismatched_decision_authority.value.path == "/admission_authority_ref"

    class ReplayAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            del observed_attempt, grant_ref
            self.admission_calls += 1
            raise AssertionError("consumed-grant authority callback must not run")

    replay_authority = ReplayAuthority()
    with pytest.raises(ReferenceValidationError) as replayed_grant:
        decide_truth_asset_admission(
            replay_authority,
            decode_canonical_bytes(canonical_bytes(issuance), type(issuance)),
            decode_canonical_bytes(canonical_bytes(grant), type(grant)),
            policy=graph.policy,
            run=graph.primary_run,
            artifact=graph.primary_artifact,
            comparisons=(graph.comparison,),
            decision_id="b04_replayed_admission_decision",
            decision_version="1.0",
        )
    assert replayed_grant.value.code == ReferenceInputCode.STALE_BINDING.value
    assert replayed_grant.value.path == "/grant_ref"
    assert replay_authority.admission_calls == 0
    for record in (issuance, grant, decision):
        reconstructed = decode_canonical_bytes(canonical_bytes(record), type(record))
        assert reconstructed == record
        assert reconstructed.to_ref() == record.to_ref()
    with pytest.raises(ReferenceValidationError):
        create_truth_asset(
            decision,
            issuance,
            grant,
            graph.primary_artifact,
            graph.primary_run,
            truth_asset_id="b04_forbidden_fixture_truth",
            truth_asset_version="1.0",
        )
    assert (
        decide_truth_asset_admission(
            None,
            object.__new__(TruthAssetAdmissionGrantIssuanceRecord),
            object.__new__(TruthAssetAdmissionGrant),
            policy=object(),
            run=object(),
            artifact=None,
            comparisons=(),
            decision_id="b04_absent_authority",
            decision_version="1.0",
        )
        is None
    )

    class MalformedAuthority:
        admission_calls = 0
        ref_reads = 0

        @property
        def admission_authority_ref(self):
            self.ref_reads += 1
            raise RuntimeError("untrusted authority detail")

        def evaluate_admission(self, observed_attempt, grant_ref):
            del observed_attempt, grant_ref
            self.admission_calls += 1
            raise AssertionError("malformed authority callback must not run")

    malformed = MalformedAuthority()
    malformed_decision = None
    with pytest.raises(ReferenceValidationError) as malformed_authority:
        malformed_decision = decide_truth_asset_admission(
            malformed,
            issuance,
            grant,
            policy=graph.policy,
            run=graph.primary_run,
            artifact=graph.primary_artifact,
            comparisons=(graph.comparison,),
            decision_id="b04_malformed_authority",
            decision_version="1.0",
        )
    assert malformed_decision is None
    assert malformed_authority.value.code == ReferenceInputCode.STALE_BINDING.value
    assert malformed_authority.value.path == "/grant_ref"
    assert malformed.ref_reads == 0
    assert malformed.admission_calls == 0


def test_one_provider_cannot_issue_and_decide_its_own_admission() -> None:
    graph = build_b04_fixture_reference_graph()
    challenge = graph.challenge_key
    issuer_ref = _identity(
        challenge,
        ReferenceIdentityKind.ADMISSION_ISSUER,
        "dual_protocol_issuer",
    )
    authority_ref = _identity(
        challenge,
        ReferenceIdentityKind.ADMISSION_AUTHORITY,
        "dual_protocol_authority",
    )
    attempt = AdmissionAttemptBinding(
        authority_ref,
        graph.policy.answer_key_authority_target.value,
        AdmissionArtifactBinding.bound(graph.primary_artifact.to_ref()),
        graph.case_ref,
        (graph.comparison.to_ref(),),
        _identity(
            challenge,
            ReferenceIdentityKind.ADMISSION_PROFILE,
            "dual_protocol_profile",
        ),
        graph.policy.disclosure_policy_ref,
        graph.policy.answer_key_authority_target.value,
        graph.policy.provenance_policy_ref,
        QualificationBinding.bound(
            _owner(
                challenge,
                "qualification_evidence_bundle",
                "dual_protocol",
            )
        ),
        graph.policy.rights_profile_ref,
        graph.primary_run.to_ref(),
        (_owner(challenge, "permitted_use", "dual_protocol"),),
        graph.policy.registered_witness_targets,
    )

    class DualProvider:
        admission_calls = 0

        @property
        def issuer_ref(self):
            return issuer_ref

        @property
        def admission_authority_ref(self):
            return authority_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            return AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                "b04-dual-protocol-issuance-token",
            )

        def evaluate_admission(self, observed_attempt, grant_ref):
            del observed_attempt, grant_ref
            self.admission_calls += 1
            raise AssertionError("self-admission authority must not be called")

    provider = DualProvider()
    issuance = None
    with pytest.raises(ReferenceServiceError) as dual_protocol:
        issuance = issue_truth_asset_admission_grant_record(
            provider,
            attempt,
            issuance_id="b04_dual_protocol_issuance",
            issuance_version="1.0",
        )
    assert issuance is None
    assert (
        dual_protocol.value.code
        == ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE.value
    )
    assert provider.admission_calls == 0

    class IssuerOnly:
        admission_calls = 0

        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            assert observed_attempt == attempt
            return AdmissionGrantIssuanceEcho(
                AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
                AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
                "b04-role-changing-issuance-token",
            )

    provider = IssuerOnly()
    issuance = issue_truth_asset_admission_grant_record(
        provider,
        attempt,
        issuance_id="b04_role_changing_issuance",
        issuance_version="1.0",
    )
    assert issuance is not None
    grant = create_truth_asset_admission_grant(
        issuance,
        capability_ref=issuer_ref,
        grant_id="b04_role_changing_grant",
        grant_version="1.0",
    )

    def admission_authority_ref(_provider):
        return authority_ref

    def evaluate_admission(_provider, observed_attempt, grant_ref):
        del observed_attempt, grant_ref
        _provider.admission_calls += 1
        raise AssertionError("self-admission authority must not be called")

    IssuerOnly.admission_authority_ref = property(admission_authority_ref)
    IssuerOnly.evaluate_admission = evaluate_admission
    with pytest.raises(ReferenceServiceError) as self_admission:
        decide_truth_asset_admission(
            provider,
            issuance,
            grant,
            policy=graph.policy,
            run=graph.primary_run,
            artifact=graph.primary_artifact,
            comparisons=(graph.comparison,),
            decision_id="b04_forbidden_self_admission",
            decision_version="1.0",
        )
    assert (
        self_admission.value.code
        == ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE.value
    )
    assert self_admission.value.path == "/admission_authority_ref"
    assert provider.admission_calls == 0

    receipt_ref = _identity(
        challenge,
        ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
        "dual_protocol_distinct_receipt",
    )

    class DistinctDualAuthority:
        admission_calls = 0

        @property
        def admission_authority_ref(self):
            return authority_ref

        @property
        def issuer_ref(self):
            return issuer_ref

        def evaluate_grant_issuance(self, observed_attempt):
            del observed_attempt
            raise AssertionError("dual-role authority issuer callback must not run")

        def evaluate_admission(self, observed_attempt, grant_ref):
            del observed_attempt, grant_ref
            self.admission_calls += 1
            raise AssertionError("dual-role authority callback must not run")

    dual_authority = DistinctDualAuthority()
    with pytest.raises(ReferenceServiceError) as authority_role_conflict:
        decide_truth_asset_admission(
            dual_authority,
            issuance,
            grant,
            policy=graph.policy,
            run=graph.primary_run,
            artifact=graph.primary_artifact,
            comparisons=(graph.comparison,),
            decision_id="b04_forbidden_dual_role_authority",
            decision_version="1.0",
        )
    assert (
        authority_role_conflict.value.code
        == ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE.value
    )
    assert dual_authority.admission_calls == 0

    class DistinctAuthority:
        @property
        def admission_authority_ref(self):
            return authority_ref

        def evaluate_admission(self, observed_attempt, grant_ref):
            assert observed_attempt == attempt
            assert grant_ref == grant.to_ref()
            return TruthAssetAdmissionEcho(
                TruthAssetAdmissionOutcome.REJECTED,
                TruthAssetAdmissionReason.ARTIFACT_ABSENT_OR_INELIGIBLE,
                receipt_ref,
            )

    decision = decide_truth_asset_admission(
        DistinctAuthority(),
        issuance,
        grant,
        policy=graph.policy,
        run=graph.primary_run,
        artifact=graph.primary_artifact,
        comparisons=(graph.comparison,),
        decision_id="b04_distinct_authority_decision",
        decision_version="1.0",
    )
    assert decision is not None
    assert decision.outcome is TruthAssetAdmissionOutcome.REJECTED


def test_admission_one_use_state_is_not_caller_replaceable() -> None:
    assert not hasattr(admission_module, "AdmissionGrantLedger")
    assert "ledger" not in inspect.signature(decide_truth_asset_admission).parameters


def test_admission_provider_echoes_are_redacted_and_not_pickleable() -> None:
    graph = build_b04_fixture_reference_graph()
    issuance_echo = AdmissionGrantIssuanceEcho(
        AdmissionGrantIssuanceOutcome.ADMISSION_GRANT_AUTHORIZED,
        AdmissionGrantIssuanceReason.ADMISSION_GRANT_REQUIREMENTS_SATISFIED,
        "b04-secret-one-use-token",
    )
    admission_echo = TruthAssetAdmissionEcho(
        TruthAssetAdmissionOutcome.ADMITTED,
        TruthAssetAdmissionReason.ADMISSION_REQUIREMENTS_SATISFIED,
        _identity(
            graph.challenge_key,
            ReferenceIdentityKind.CONSUMED_GRANT_RECEIPT,
            "protected-provider-echo-receipt",
        ),
    )

    for value in (issuance_echo, admission_echo):
        assert repr(value) == f"{type(value).__name__}(<protected>)"
        assert str(value) == repr(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)


@pytest.mark.parametrize(
    "protected_type",
    (
        TruthAssetAdmissionGrantIssuanceRecord,
        TruthAssetAdmissionGrant,
        TruthAssetAdmissionDecisionRecord,
        TruthAsset,
    ),
)
def test_admission_records_are_redacted_and_not_pickleable(
    protected_type: type,
) -> None:
    value = object.__new__(protected_type)
    assert repr(value) == f"{protected_type.__name__}(<protected>)"
    with pytest.raises(TypeError):
        pickle.dumps(value)
