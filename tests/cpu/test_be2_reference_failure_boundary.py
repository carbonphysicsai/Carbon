"""Focused B-E2 reference-service failure and identity proofs."""

from __future__ import annotations

import pickle
from dataclasses import replace

import pytest

from carbon.authoring.canonical import tagged_sha256
from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole
from carbon.evaluation import service_fixtures
from carbon.evaluation.enums import (
    ConditioningStatus,
    ReferenceArtifactOrigin,
    ReferenceAuthorityFunction,
    ReferenceComparisonOutcome,
    ReferenceFailureReason,
    ReferenceIdentityKind,
    ReferenceRunOutcome,
    SupportApplicabilityStatus,
    UncertaintyStatus,
)
from carbon.evaluation.errors import ReferenceInputCode, ReferenceValidationError
from carbon.evaluation.fixtures import build_b04_fixture_reference_graph
from carbon.evaluation.policy import (
    primary_target_for_entry,
    validate_reference_policy_graph,
)
from carbon.evaluation.service_boundary import (
    ReferenceServiceAttemptHistory,
    RegisteredPrimaryReferenceServiceRunner,
)
from carbon.evaluation.service_fixtures import (
    build_be2_reference_failure_fixture_graph,
)
from carbon.registry.model import ChallengeKey


@pytest.mark.parametrize(
    ("path_name", "outcome", "reason"),
    (
        ("supported", ReferenceRunOutcome.SUPPORTED, None),
        (
            "uncertainty",
            ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED,
            ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED,
        ),
        (
            "conditioning",
            ReferenceRunOutcome.CONDITIONING_UNRESOLVED,
            ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
        ),
        (
            "not_applicable",
            ReferenceRunOutcome.NOT_APPLICABLE,
            ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE,
        ),
        (
            "unsupported",
            ReferenceRunOutcome.UNSUPPORTED,
            ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED,
        ),
        (
            "numerical_failure",
            ReferenceRunOutcome.NUMERICAL_FAILURE,
            ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
        ),
        (
            "malformed",
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
            ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
        ),
        (
            "provenance_failure",
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
            ReferenceFailureReason.PROVENANCE_INVALID,
        ),
        (
            "identity_mismatch",
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
            ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
        ),
        (
            "dependency_unavailable",
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
            ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
        ),
        (
            "process_failure",
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
            ReferenceFailureReason.PROCESS_FAILURE,
        ),
        (
            "timeout",
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
            ReferenceFailureReason.TIMEOUT,
        ),
        (
            "transport_failure",
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
            ReferenceFailureReason.TRANSPORT_FAILURE,
        ),
    ),
)
def test_every_required_service_terminal_remains_distinguishable(
    path_name: str,
    outcome: ReferenceRunOutcome,
    reason: ReferenceFailureReason | None,
) -> None:
    graph = build_be2_reference_failure_fixture_graph()
    run = getattr(graph, path_name).attempt.run

    assert run.outcome is outcome
    assert run.reason.value is reason
    assert run.artifact_binding.is_bound is (outcome is ReferenceRunOutcome.SUPPORTED)
    if outcome is not ReferenceRunOutcome.SUPPORTED:
        assert run.artifact_binding.value is reason


def test_supported_response_preserves_every_registered_execution_binding() -> None:
    path = build_be2_reference_failure_fixture_graph().supported
    attempt = path.attempt
    request = attempt.request
    grant = attempt.grant
    run = attempt.run

    assert run.request_binding.value == request.to_ref()
    assert run.grant_binding.value == grant.to_ref()
    assert run.resolution_ref == attempt.resolution.to_ref()
    assert run.case_ref == request.case_ref
    assert run.policy_ref == request.policy_ref
    assert run.answer_key_authority_target == request.answer_key_authority_target
    assert run.execution_target.value == request.execution_target
    assert run.authority_function is grant.authority_function
    assert run.evidence_role_binding == grant.evidence_role_binding
    assert run.implementation_ref == grant.implementation_ref
    assert run.environment_ref == grant.environment_ref
    assert run.method_ref == grant.method_ref
    assert run.configuration_ref == grant.configuration_ref
    assert run.precision_ref == grant.precision_ref
    assert run.hardware_ref == grant.hardware_ref
    assert run.representation_ref == grant.representation_ref
    assert run.scope_binding == request.scope_binding
    assert run.provenance_binding.environment_ref == grant.environment_ref
    assert run.provenance_binding.implementation_ref == grant.implementation_ref
    assert run.provenance_binding.method_ref == grant.method_ref
    assert (
        run.applicability_assessment.status
        is SupportApplicabilityStatus.SUPPORTED_AND_APPLICABLE
    )
    assert (
        run.conditioning_assessment.status
        is ConditioningStatus.ASSESSED_WITHIN_REGISTERED_SCOPE
    )
    assert run.uncertainty_binding.status is UncertaintyStatus.RESOLVED
    assert (
        run.artifact_binding.value.artifact_origin
        is ReferenceArtifactOrigin.FIXTURE_ONLY
    )


def test_registered_witness_service_preserves_the_distinct_b04_role() -> None:
    attempt = build_be2_reference_failure_fixture_graph().witness_supported.attempt

    assert attempt.run.outcome is ReferenceRunOutcome.SUPPORTED
    assert (
        attempt.run.authority_function
        is ReferenceAuthorityFunction.CORROBORATING_WITNESS
    )
    assert attempt.run.execution_target.value == attempt.request.execution_target
    assert attempt.run.request_binding.value == attempt.request.to_ref()
    assert attempt.run.grant_binding.value == attempt.grant.to_ref()
    assert (
        attempt.run.artifact_binding.value.artifact_origin
        is ReferenceArtifactOrigin.FIXTURE_ONLY
    )


def _fresh_response(label: str):
    graph = build_b04_fixture_reference_graph()
    request, grant, resolution, context = service_fixtures._unstarted_attempt(
        graph, label
    )
    response = service_fixtures._response(request, grant, resolution, context)
    return graph, request, grant, resolution, context, response


class _ResponseProvider:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls = 0

    def execute_primary(self, grant, request):
        del grant, request
        self.calls += 1
        return self.response


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    (
        ("case", ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH),
        ("challenge", ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH),
        ("role", ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH),
        ("policy", ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH),
        ("version", ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH),
        ("environment", ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH),
        ("configuration", ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH),
        ("provenance", ReferenceFailureReason.PROVENANCE_INVALID),
        ("stale_request", ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH),
    ),
)
def test_wrong_or_stale_service_response_fails_closed(
    mutation: str,
    expected_reason: ReferenceFailureReason,
) -> None:
    graph, request, grant, resolution, context, response = _fresh_response(
        f"wrong_{mutation}"
    )
    if mutation == "case":
        response = replace(
            response,
            case_ref=service_fixtures.b04_fixtures._case_ref(
                ChallengeKey("be2_wrong_case", "1.0")
            ),
        )
    elif mutation == "challenge":
        response = replace(
            response,
            request_ref=replace(
                response.request_ref,
                challenge_key=ChallengeKey("be2_wrong_challenge", "1.0"),
            ),
        )
    elif mutation == "role":
        response = replace(
            response,
            authority_function=ReferenceAuthorityFunction.CORROBORATING_WITNESS,
        )
    elif mutation == "policy":
        response = replace(
            response,
            policy_ref=replace(
                response.policy_ref,
                content_digest=tagged_sha256(b"wrong policy"),
            ),
        )
    elif mutation == "version":
        response = replace(response, run_version="2.0")
    elif mutation == "environment":
        response = replace(
            response,
            environment_ref=service_fixtures.b04_fixtures._identity(
                ReferenceIdentityKind.ENVIRONMENT,
                "wrong_environment",
                graph.challenge_key,
            ),
        )
    elif mutation == "configuration":
        response = replace(
            response,
            configuration_ref=service_fixtures.b04_fixtures._identity(
                ReferenceIdentityKind.CONFIGURATION,
                "wrong_configuration",
                graph.challenge_key,
            ),
        )
    elif mutation == "provenance":
        response = replace(
            response,
            provenance_binding=replace(
                response.provenance_binding,
                source_ref=graph.witness_run.provenance_binding.source_ref,
            ),
        )
    else:
        response = replace(
            response,
            request_ref=replace(
                response.request_ref,
                content_digest=tagged_sha256(b"stale response"),
            ),
        )
    provider = _ResponseProvider(response)
    runner = RegisteredPrimaryReferenceServiceRunner(
        provider, request, grant, resolution, context
    )

    run = runner.run_primary(grant, request)

    assert run.outcome is ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE
    assert run.reason.value is expected_reason
    assert not run.artifact_binding.is_bound
    assert provider.calls == 1


@pytest.mark.parametrize(
    ("label", "payload"),
    (
        ("none", None),
        ("empty_mapping", {}),
        ("callable", {"callable": lambda: None}),
        ("path", {"path": "/tmp/protected"}),
        ("url", {"url": "https://example.invalid/secret"}),
        ("bytes", b"partial-provider-bytes"),
    ),
)
def test_malformed_or_ambient_authority_payload_never_executes_or_becomes_artifact(
    label: str,
    payload: object,
) -> None:
    _, request, grant, resolution, context, _ = _fresh_response(
        f"hostile_payload_{label}"
    )
    provider = _ResponseProvider(payload)
    runner = RegisteredPrimaryReferenceServiceRunner(
        provider, request, grant, resolution, context
    )

    run = runner.run_primary(grant, request)

    assert run.outcome is ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE
    assert run.reason.value is ReferenceFailureReason.PROVIDER_RESULT_MALFORMED
    assert not run.artifact_binding.is_bound


def test_duplicate_response_is_rejected_before_a_second_provider_call() -> None:
    _, request, grant, resolution, context, response = _fresh_response("duplicate")
    provider = _ResponseProvider(response)
    runner = RegisteredPrimaryReferenceServiceRunner(
        provider, request, grant, resolution, context
    )

    first = runner.run_primary(grant, request)
    assert first.outcome is ReferenceRunOutcome.SUPPORTED
    with pytest.raises(ReferenceValidationError) as duplicate:
        runner.run_primary(grant, request)

    assert duplicate.value.code == ReferenceInputCode.STALE_BINDING.value
    assert provider.calls == 1


def test_retry_trace_preserves_original_failure_and_all_exact_identities() -> None:
    history = build_be2_reference_failure_fixture_graph().retry_history
    first, second = history.attempts

    assert first.run.outcome is ReferenceRunOutcome.INFRASTRUCTURE_FAILURE
    assert first.run.reason.value is ReferenceFailureReason.DEPENDENCY_UNAVAILABLE
    assert second.run.outcome is ReferenceRunOutcome.SUPPORTED
    assert first.request.to_ref() != second.request.to_ref()
    assert first.grant.to_ref() != second.grant.to_ref()
    assert first.run.to_ref() != second.run.to_ref()
    assert first.request.idempotency_ref == second.request.idempotency_ref
    assert first.request.case_ref == second.request.case_ref
    assert first.request.policy_ref == second.request.policy_ref
    assert first.request.execution_target == second.request.execution_target
    assert first.grant.implementation_ref == second.grant.implementation_ref
    assert first.grant.environment_ref == second.grant.environment_ref
    assert first.grant.configuration_ref == second.grant.configuration_ref

    with pytest.raises(ReferenceValidationError) as duplicate:
        ReferenceServiceAttemptHistory((first, first))
    assert duplicate.value.code == ReferenceInputCode.DUPLICATE_IDENTITY.value

    unrelated = build_be2_reference_failure_fixture_graph().supported.attempt
    with pytest.raises(ReferenceValidationError) as drift:
        ReferenceServiceAttemptHistory((first, unrelated))
    assert drift.value.code == ReferenceInputCode.STALE_BINDING.value


def test_disagreement_stays_contested_and_has_no_combined_artifact() -> None:
    comparison = build_be2_reference_failure_fixture_graph().comparison

    assert comparison.outcome is ReferenceComparisonOutcome.CONTESTED_DISAGREEMENT
    assert not hasattr(comparison, "artifact_binding")
    assert not hasattr(comparison, "average")
    assert not hasattr(comparison, "score")


def test_mms_anchor_cannot_be_relabelled_as_primary_or_validation() -> None:
    fixture = build_be2_reference_failure_fixture_graph()
    anchor = fixture.manufactured_verification_anchor
    graph = build_b04_fixture_reference_graph()

    assert (
        anchor.evidence_role_binding.role
        is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
    )
    assert anchor.authority_function is ReferenceAuthorityFunction.VERIFICATION_ANCHOR
    for authority in (
        ReferenceAuthorityFunction.PRIMARY,
        ReferenceAuthorityFunction.CORROBORATING_WITNESS,
        ReferenceAuthorityFunction.VALIDATION_ANCHOR,
    ):
        with pytest.raises(ReferenceValidationError) as relabel:
            replace(anchor, authority_function=authority)
        assert relabel.value.code == ReferenceInputCode.ROLE_MISMATCH.value
    with pytest.raises(ReferenceValidationError):
        primary_target_for_entry(anchor)

    fabricated_validation = replace(
        anchor,
        authority_function=ReferenceAuthorityFunction.VALIDATION_ANCHOR,
        evidence_role_binding=EvidenceRoleBinding(EvidenceRole.EXPERIMENTAL),
    )
    with pytest.raises(ReferenceValidationError) as unregistered:
        validate_reference_policy_graph(
            graph.policy,
            entries=(*graph.entries, fabricated_validation),
            compositions=graph.compositions,
            precomputed_manifests=(graph.precomputed_manifest,),
        )
    assert unregistered.value.code == ReferenceInputCode.STALE_BINDING.value


def test_protected_service_objects_do_not_disclose_or_pickle() -> None:
    path = build_be2_reference_failure_fixture_graph().supported
    for value in (
        path,
        path.runner,
        path.response,
        path.attempt,
        build_be2_reference_failure_fixture_graph().retry_history,
    ):
        assert "<protected>" in repr(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)


def test_no_failure_path_manufactures_truth_candidate_or_economic_authority() -> None:
    graph = build_be2_reference_failure_fixture_graph()
    failure_paths = (
        graph.uncertainty,
        graph.conditioning,
        graph.not_applicable,
        graph.unsupported,
        graph.numerical_failure,
        graph.malformed,
        graph.provenance_failure,
        graph.identity_mismatch,
        graph.dependency_unavailable,
        graph.process_failure,
        graph.timeout,
        graph.transport_failure,
    )
    forbidden = {
        "candidate",
        "fallback",
        "frontier",
        "leaderboard",
        "promotion",
        "rank",
        "score",
        "settlement",
        "truth_asset",
        "weight",
    }
    for path in failure_paths:
        run = path.attempt.run
        assert not run.artifact_binding.is_bound
        assert forbidden.isdisjoint(set(run.__dataclass_fields__))
