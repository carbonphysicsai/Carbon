"""Focused deterministic fixture-runtime proofs for B-04."""

from __future__ import annotations

import pickle
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace

import pytest

import carbon.evaluation.execution as execution_runtime
import carbon.evaluation.fixtures as fixture_runtime
from carbon.authoring.primitives import MAX_CANONICAL_TUPLE_ITEMS
from carbon.evaluation.canonical import canonical_bytes, decode_canonical_bytes
from carbon.evaluation.comparison import create_reference_comparison_record
from carbon.evaluation.enums import (
    DependencyRelation,
    ReferenceArtifactOrigin,
    ReferenceAuthorityFunction,
    ReferenceComparisonOutcome,
    ReferenceComparisonReason,
    ReferenceFailureReason,
    ReferenceIdentityKind,
    ReferenceRunOutcome,
)
from carbon.evaluation.errors import (
    ReferenceInputCode,
    ReferenceValidationError,
)
from carbon.evaluation.fixtures import (
    B04FixtureReferenceGraph,
    ConditioningLimitedPrimaryFixtureRunner,
    InfrastructureFailurePrimaryFixtureRunner,
    MalformedPrimaryFixtureRunner,
    NumericalFailurePrimaryFixtureRunner,
    SupportedPrimaryFixtureRunner,
    SupportedWitnessFixtureRunner,
    build_b04_fixture_reference_graph,
)
from carbon.evaluation.policy import validate_reference_policy_graph
from carbon.evaluation.runners import PrimaryReferenceRunner, WitnessReferenceRunner


def _fresh_primary_fixture_attempt(
    graph: B04FixtureReferenceGraph,
    *,
    label: str,
) -> tuple[object, object, object, SupportedPrimaryFixtureRunner]:
    request = fixture_runtime._request(
        label=label,
        policy=graph.policy,
        case_ref=graph.case_ref,
        witness=False,
    )
    assert type(request) is execution_runtime.PrimaryReferenceRequest
    grant = fixture_runtime._grant(
        label=label,
        request=request,
        component_entry_refs=graph.compositions[0].member_entry_refs,
    )
    assert type(grant) is execution_runtime.PrimaryRunGrant
    resolution = fixture_runtime._resolution(
        label=label,
        request=request,
        grant=grant,
        policy=graph.policy,
        entries=graph.entries,
        compositions=graph.compositions,
        manifest=graph.precomputed_manifest,
    )
    runner = SupportedPrimaryFixtureRunner(
        resolution,
        graph.precomputed_manifest.source_ref,
        graph.policy.rights_profile_ref,
        _token=fixture_runtime._RUNNER_TOKEN,
    )
    return request, grant, resolution, runner


def _attempt_direct_run(
    graph: B04FixtureReferenceGraph,
    request: object,
    grant: object,
    resolution: object,
):
    run = graph.primary_run
    components = tuple(
        replace(
            component,
            configuration_ref=grant.configuration_ref,
            environment_ref=grant.environment_ref,
            hardware_ref=grant.hardware_ref,
            implementation_ref=grant.implementation_ref,
            method_ref=grant.method_ref,
            precision_ref=grant.precision_ref,
        )
        for component in run.component_bindings
    )
    provenance = replace(
        run.provenance_binding,
        environment_ref=grant.environment_ref,
        implementation_ref=grant.implementation_ref,
        method_ref=grant.method_ref,
    )
    return execution_runtime.create_reference_run_record(
        request=request,
        grant=grant,
        resolution=resolution,
        observed_reasons=(),
        artifact_content=run.artifact_binding.value,
        applicability_assessment=run.applicability_assessment,
        component_bindings=components,
        conditioning_assessment=run.conditioning_assessment,
        diagnostics_ref=run.diagnostics_ref,
        provenance_binding=provenance,
        resource_receipt_ref=run.resource_receipt_ref,
        run_id="b04_fixture_direct_run_attempt",
        run_version="1.0",
        uncertainty_binding=run.uncertainty_binding,
    )


def test_fixed_graph_builds_every_policy_family_and_both_nominal_roles() -> None:
    graph = build_b04_fixture_reference_graph()

    assert isinstance(graph, B04FixtureReferenceGraph)
    validate_reference_policy_graph(
        graph.policy,
        entries=graph.entries,
        compositions=graph.compositions,
        precomputed_manifests=(graph.precomputed_manifest,),
    )
    assert len(graph.entries) == 3
    assert len(graph.compositions) == 1
    assert len(graph.primary_grant.component_entry_refs) == 2
    assert len(graph.witness_grant.component_entry_refs) == 1
    assert not set(graph.primary_grant.component_entry_refs) & set(
        graph.witness_grant.component_entry_refs
    )
    assert graph.primary_grant.authority_function is ReferenceAuthorityFunction.PRIMARY
    assert (
        graph.witness_grant.authority_function
        is ReferenceAuthorityFunction.CORROBORATING_WITNESS
    )
    assert isinstance(graph.primary_path.runner, PrimaryReferenceRunner)
    assert not isinstance(graph.primary_path.runner, WitnessReferenceRunner)
    assert isinstance(graph.witness_path.runner, WitnessReferenceRunner)
    assert not isinstance(graph.witness_path.runner, PrimaryReferenceRunner)


def test_supported_fixture_outputs_are_exact_distinct_and_never_authoritative() -> None:
    graph = build_b04_fixture_reference_graph()

    assert graph.primary_run.outcome is ReferenceRunOutcome.SUPPORTED
    assert graph.witness_run.outcome is ReferenceRunOutcome.SUPPORTED
    assert graph.primary_run.artifact_binding.is_bound
    assert graph.witness_run.artifact_binding.is_bound
    assert (
        graph.primary_run.artifact_binding.value.artifact_origin
        is ReferenceArtifactOrigin.FIXTURE_ONLY
    )
    assert (
        graph.witness_run.artifact_binding.value.artifact_origin
        is ReferenceArtifactOrigin.FIXTURE_ONLY
    )
    assert (
        graph.primary_fixture_asset.payload_bytes
        != graph.witness_fixture_asset.payload_bytes
    )
    for asset in (graph.primary_fixture_asset, graph.witness_fixture_asset):
        assert asset.live_eligible is False
        assert asset.scientific_qualification_eligible is False


@pytest.mark.parametrize(
    ("path_name", "runner_type", "outcome", "reason"),
    (
        (
            "conditioning_path",
            ConditioningLimitedPrimaryFixtureRunner,
            ReferenceRunOutcome.CONDITIONING_UNRESOLVED,
            ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
        ),
        (
            "numerical_path",
            NumericalFailurePrimaryFixtureRunner,
            ReferenceRunOutcome.NUMERICAL_FAILURE,
            ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
        ),
        (
            "malformed_path",
            MalformedPrimaryFixtureRunner,
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
            ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
        ),
        (
            "infrastructure_path",
            InfrastructureFailurePrimaryFixtureRunner,
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
            ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
        ),
    ),
)
def test_fixed_failure_runners_preserve_typed_terminal_separation(
    path_name: str,
    runner_type: type,
    outcome: ReferenceRunOutcome,
    reason: ReferenceFailureReason,
) -> None:
    graph = build_b04_fixture_reference_graph()
    path = object.__getattribute__(graph, path_name)

    assert type(path.runner) is runner_type
    assert path.run.outcome is outcome
    assert path.run.reason.value is reason
    assert not path.run.artifact_binding.is_bound
    assert path.run.artifact_binding.value is reason
    assert path.run.authority_function is ReferenceAuthorityFunction.PRIMARY


def test_contested_correlated_witness_is_not_averaged_or_promoted() -> None:
    graph = build_b04_fixture_reference_graph()

    assert graph.comparison.outcome is ReferenceComparisonOutcome.CONTESTED_DISAGREEMENT
    assert (
        graph.comparison.reason
        is ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED
    )
    assert all(
        item.relation is DependencyRelation.SHARED
        for item in graph.comparison.dependency_disclosures
    )
    assert graph.primary_run.authority_function is ReferenceAuthorityFunction.PRIMARY
    assert (
        graph.witness_run.authority_function
        is ReferenceAuthorityFunction.CORROBORATING_WITNESS
    )
    assert graph.comparison.primary_run_ref == graph.primary_run.to_ref()
    assert graph.comparison.witness_run_ref == graph.witness_run.to_ref()


def test_material_dependence_without_evidence_is_comparison_indeterminate() -> None:
    graph = build_b04_fixture_reference_graph()
    comparison = graph.comparison
    empty_material_evidence = tuple(
        replace(disclosure, evidence_refs=())
        for disclosure in comparison.dependency_disclosures
    )

    result = create_reference_comparison_record(
        primary_run=graph.primary_run,
        witness_run=graph.witness_run,
        observed_reasons=(ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED,),
        applicability_evidence_refs=comparison.applicability_evidence_refs,
        comparison_id="b04_fixture_unsubstantiated_dependence",
        comparison_method_ref=comparison.comparison_method_ref,
        comparison_policy_ref=comparison.comparison_policy_ref,
        comparison_version="1.0",
        dependency_disclosures=empty_material_evidence,
        evidence_refs=comparison.evidence_refs,
        uncertainty_treatment_ref=comparison.uncertainty_treatment_ref,
        witness_target=comparison.witness_target,
    )

    assert result.outcome is ReferenceComparisonOutcome.COMPARISON_INDETERMINATE
    assert result.reason is ReferenceComparisonReason.COMPARISON_DEPENDENCE_UNRESOLVED


def test_comparison_factory_rejects_duplicate_observed_reasons() -> None:
    graph = build_b04_fixture_reference_graph()
    comparison = graph.comparison
    duplicate = ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED

    with pytest.raises(ReferenceValidationError) as captured:
        create_reference_comparison_record(
            primary_run=graph.primary_run,
            witness_run=graph.witness_run,
            observed_reasons=(duplicate, duplicate),
            applicability_evidence_refs=comparison.applicability_evidence_refs,
            comparison_id="b04_fixture_duplicate_comparison_reason",
            comparison_method_ref=comparison.comparison_method_ref,
            comparison_policy_ref=comparison.comparison_policy_ref,
            comparison_version="1.0",
            dependency_disclosures=comparison.dependency_disclosures,
            evidence_refs=comparison.evidence_refs,
            uncertainty_treatment_ref=comparison.uncertainty_treatment_ref,
            witness_target=comparison.witness_target,
        )
    assert captured.value.code == ReferenceInputCode.DUPLICATE_IDENTITY.value


def test_fixture_graph_and_assets_are_byte_stable_and_reconstruct_exactly() -> None:
    first = build_b04_fixture_reference_graph()
    second = build_b04_fixture_reference_graph()

    records = (
        first.precomputed_manifest,
        *first.entries,
        *first.compositions,
        first.policy,
        first.primary_request,
        first.primary_grant,
        first.primary_resolution,
        first.primary_run,
        first.witness_request,
        first.witness_grant,
        first.witness_resolution,
        first.witness_run,
        first.comparison,
        first.primary_artifact,
        first.primary_fixture_asset,
    )
    corresponding = (
        second.precomputed_manifest,
        *second.entries,
        *second.compositions,
        second.policy,
        second.primary_request,
        second.primary_grant,
        second.primary_resolution,
        second.primary_run,
        second.witness_request,
        second.witness_grant,
        second.witness_resolution,
        second.witness_run,
        second.comparison,
        second.primary_artifact,
        second.primary_fixture_asset,
    )
    assert len(records) == len(corresponding)
    for left, right in zip(records, corresponding, strict=True):
        payload = canonical_bytes(left)
        assert payload == canonical_bytes(right)
        assert decode_canonical_bytes(payload, type(left)) == left
        assert left.to_ref() == right.to_ref()


def test_fixture_runners_are_one_use_role_specific_and_protected() -> None:
    graph = build_b04_fixture_reference_graph()
    primary_runner = graph.primary_path.runner
    witness_runner = graph.witness_path.runner

    assert type(primary_runner) is SupportedPrimaryFixtureRunner
    assert type(witness_runner) is SupportedWitnessFixtureRunner
    with pytest.raises(ReferenceValidationError):
        primary_runner.run_primary(graph.primary_grant, graph.primary_request)
    with pytest.raises(ReferenceValidationError):
        primary_runner.run_primary(graph.witness_grant, graph.witness_request)
    with pytest.raises(ReferenceValidationError):
        witness_runner.run_witness(graph.primary_grant, graph.primary_request)
    for protected in (graph, graph.primary_path, primary_runner, witness_runner):
        assert "<protected>" in repr(protected)
        with pytest.raises(TypeError):
            pickle.dumps(protected)
    with pytest.raises(FrozenInstanceError):
        primary_runner._resolution = graph.witness_resolution


def test_run_attempt_authority_rejects_direct_and_sequential_replay() -> None:
    graph = build_b04_fixture_reference_graph()
    request, grant, resolution, runner = _fresh_primary_fixture_attempt(
        graph,
        label="direct_replay_guard",
    )

    assert not hasattr(execution_runtime, "RunGrantLedger")
    with pytest.raises(ReferenceValidationError) as direct:
        _attempt_direct_run(graph, request, grant, resolution)
    assert direct.value.code == ReferenceInputCode.AUTHORITY_INTERFACE_INVALID.value

    terminal = runner.run_primary(grant, request)
    assert terminal.outcome is ReferenceRunOutcome.SUPPORTED
    with pytest.raises(ReferenceValidationError) as replay:
        runner.run_primary(grant, request)
    assert replay.value.code == ReferenceInputCode.STALE_BINDING.value


def test_run_attempt_authority_accepts_exactly_one_concurrent_terminal() -> None:
    graph = build_b04_fixture_reference_graph()
    request, grant, _, runner = _fresh_primary_fixture_attempt(
        graph,
        label="concurrent_replay_guard",
    )
    worker_count = 8
    barrier = threading.Barrier(worker_count)

    def invoke() -> object:
        barrier.wait()
        try:
            return runner.run_primary(grant, request)
        except ReferenceValidationError as error:
            return error

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        results = tuple(pool.map(lambda _: invoke(), range(worker_count)))

    terminals = tuple(
        result for result in results if not isinstance(result, ReferenceValidationError)
    )
    rejections = tuple(
        result for result in results if isinstance(result, ReferenceValidationError)
    )
    assert len(terminals) == 1
    assert terminals[0].outcome is ReferenceRunOutcome.SUPPORTED
    assert len(rejections) == worker_count - 1
    assert all(
        error.code == ReferenceInputCode.STALE_BINDING.value for error in rejections
    )
    for error in rejections:
        traceback = error.__traceback__
        while traceback is not None:
            frame = traceback.tb_frame
            if frame.f_code.co_filename.endswith(("/execution.py", "/fixtures.py")):
                assert all(
                    type(value) is not execution_runtime.ReferenceRunRecord
                    for value in frame.f_locals.values()
                )
            traceback = traceback.tb_next


def test_low_level_attribute_replacement_cannot_swap_runner_capability_state() -> None:
    graph = build_b04_fixture_reference_graph()
    request, grant, _, runner = _fresh_primary_fixture_attempt(
        graph,
        label="attribute_replacement_guard",
    )

    replacements = {
        "_ledger": object(),
        "_resolution": graph.witness_resolution,
        "_source_ref": graph.precomputed_manifest.source_ref,
        "_rights_profile_ref": graph.policy.rights_profile_ref,
        "_attempt_capability": object(),
        "FAILURE_REASON": ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
    }
    for name, replacement in replacements.items():
        with pytest.raises(AttributeError):
            object.__setattr__(runner, name, replacement)
        if name.startswith("_"):
            with pytest.raises(AttributeError):
                object.__getattribute__(runner, name)

    terminal = runner.run_primary(grant, request)
    assert terminal.outcome is ReferenceRunOutcome.SUPPORTED

    for name in (
        "_RUN_ATTEMPT_AUTHORITY",
        "_RunAttemptAuthority",
        "_RegisteredRunAttempt",
        "_create_run_attempt_state",
    ):
        assert not hasattr(execution_runtime, name)
    for name in (
        "_FIXTURE_RUNNER_STATES",
        "_FIXTURE_RUNNER_STATES_LOCK",
        "_FixtureRunnerState",
        "_fixture_runner_state",
        "_create_fixture_runner_state",
    ):
        assert not hasattr(fixture_runtime, name)


def test_fixture_runner_family_and_behavior_are_sealed() -> None:
    graph = build_b04_fixture_reference_graph()

    with pytest.raises(TypeError):
        type(
            "CallerSelectedFixtureRunner",
            (SupportedPrimaryFixtureRunner,),
            {"__slots__": (), "PAYLOAD": b"caller-selected"},
        )
    with pytest.raises(TypeError):
        SupportedPrimaryFixtureRunner.PAYLOAD = b"caller-selected"

    type.__setattr__(
        SupportedPrimaryFixtureRunner,
        "PAYLOAD",
        b"low-level caller-selected payload",
    )
    type.__setattr__(
        SupportedPrimaryFixtureRunner,
        "FAILURE_REASON",
        ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
    )
    try:
        request, grant, _, runner = _fresh_primary_fixture_attempt(
            graph,
            label="sealed_fixture_behavior",
        )
        terminal = runner.run_primary(grant, request)
    finally:
        type.__delattr__(SupportedPrimaryFixtureRunner, "PAYLOAD")
        type.__delattr__(SupportedPrimaryFixtureRunner, "FAILURE_REASON")

    assert terminal.outcome is ReferenceRunOutcome.SUPPORTED
    assert (
        terminal.artifact_binding.value.artifact_content_digest
        == graph.primary_run.artifact_binding.value.artifact_content_digest
    )


@pytest.mark.parametrize(
    ("case", "expected_code"),
    (
        ("wrong_type", ReferenceInputCode.WRONG_TYPE),
        ("over_limit", ReferenceInputCode.INVALID_VALUE),
        ("wrong_member", ReferenceInputCode.STALE_BINDING),
    ),
)
def test_invalid_component_input_rejects_before_claim_without_burning_grant(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_code: ReferenceInputCode,
) -> None:
    graph = build_b04_fixture_reference_graph()
    request, grant, _, runner = _fresh_primary_fixture_attempt(
        graph,
        label=f"component_preclaim_{case}",
    )
    original = fixture_runtime._component_bindings
    valid_components = original(grant)
    if case == "wrong_type":
        hostile = list(valid_components)
    elif case == "over_limit":
        hostile = (valid_components[0],) * (MAX_CANONICAL_TUPLE_ITEMS + 1)
    else:
        hostile = (
            replace(
                valid_components[0],
                entry_ref=graph.witness_grant.component_entry_refs[0],
            ),
            *valid_components[1:],
        )

    with monkeypatch.context() as patch:
        patch.setattr(fixture_runtime, "_component_bindings", lambda _: hostile)
        with pytest.raises(ReferenceValidationError) as captured:
            runner.run_primary(grant, request)
    assert captured.value.code == expected_code.value

    terminal = runner.run_primary(grant, request)
    assert terminal.outcome is ReferenceRunOutcome.SUPPORTED


@pytest.mark.parametrize(
    "case",
    ("source", "rights", "campaign", "manifest_facts"),
)
def test_unregistered_provenance_rejects_before_claim_without_burning_grant(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    graph = build_b04_fixture_reference_graph()
    request, grant, _, runner = _fresh_primary_fixture_attempt(
        graph,
        label=f"provenance_preclaim_{case}",
    )
    original = fixture_runtime._provenance

    def hostile_provenance(**kwargs):
        provenance = original(**kwargs)
        challenge = provenance.challenge_key
        if case == "source":
            return replace(
                provenance,
                source_ref=fixture_runtime._identity(
                    ReferenceIdentityKind.SOURCE,
                    "unregistered_source",
                    challenge,
                ),
            )
        if case == "rights":
            return replace(
                provenance,
                rights_profile_ref=fixture_runtime._owner(
                    "rights_profile",
                    "unregistered_rights",
                    challenge,
                ),
            )
        if case == "campaign":
            return replace(
                provenance,
                evidence_campaign_ref=fixture_runtime._owner(
                    "evidence_campaign",
                    "unregistered_campaign",
                    challenge,
                ),
            )
        return replace(
            provenance,
            generated_or_copied_code_refs=(
                fixture_runtime._owner(
                    "provenance",
                    "unregistered_generated_code",
                    challenge,
                ),
            ),
        )

    with monkeypatch.context() as patch:
        patch.setattr(fixture_runtime, "_provenance", hostile_provenance)
        with pytest.raises(ReferenceValidationError) as captured:
            runner.run_primary(grant, request)
    assert captured.value.code == ReferenceInputCode.STALE_BINDING.value

    terminal = runner.run_primary(grant, request)
    assert terminal.outcome is ReferenceRunOutcome.SUPPORTED


def test_fresh_resolution_cannot_register_an_already_registered_grant() -> None:
    graph = build_b04_fixture_reference_graph()
    request, grant, _, runner = _fresh_primary_fixture_attempt(
        graph,
        label="same_grant_resolution_guard",
    )

    with pytest.raises(ReferenceValidationError) as captured:
        fixture_runtime._resolution(
            label="same_grant_resolution_replay",
            request=request,
            grant=grant,
            policy=graph.policy,
            entries=graph.entries,
            compositions=graph.compositions,
            manifest=graph.precomputed_manifest,
        )
    assert captured.value.code == ReferenceInputCode.STALE_BINDING.value
    traceback = captured.value.__traceback__
    while traceback is not None:
        frame = traceback.tb_frame
        if frame.f_code.co_filename.endswith(("/execution.py", "/fixtures.py")):
            assert all(
                type(value) is not execution_runtime.ReferenceResolutionRecord
                for value in frame.f_locals.values()
            )
        traceback = traceback.tb_next

    terminal = runner.run_primary(grant, request)
    assert terminal.outcome is ReferenceRunOutcome.SUPPORTED


def test_decoded_resolution_reconstructs_but_cannot_reissue_capability() -> None:
    graph = build_b04_fixture_reference_graph()
    decoded = decode_canonical_bytes(
        canonical_bytes(graph.primary_resolution),
        type(graph.primary_resolution),
    )
    assert decoded == graph.primary_resolution
    with pytest.raises(ReferenceValidationError) as captured:
        SupportedPrimaryFixtureRunner(
            decoded,
            graph.precomputed_manifest.source_ref,
            graph.policy.rights_profile_ref,
            _token=fixture_runtime._RUNNER_TOKEN,
        )
    assert captured.value.code == ReferenceInputCode.STALE_BINDING.value


def test_run_grant_issuer_and_capability_must_be_the_same_identity() -> None:
    graph = build_b04_fixture_reference_graph()
    mismatched = replace(
        graph.primary_grant.issuer_ref,
        identity_id="b04_fixture_mismatched_run_issuer",
    )
    with pytest.raises(ReferenceValidationError) as captured:
        replace(graph.primary_grant, capability_ref=mismatched)
    assert captured.value.code == ReferenceInputCode.STALE_BINDING.value


def test_fixed_graph_has_no_generic_runner_or_fallback_surface() -> None:
    graph = build_b04_fixture_reference_graph()
    for runner in (graph.primary_path.runner, graph.witness_path.runner):
        assert not hasattr(runner, "run")
        assert not hasattr(runner, "fallback")
        assert not hasattr(runner, "retry")
        assert not hasattr(runner, "path")
        assert not hasattr(runner, "mode")
    assert graph.conditioning_path.run is not graph.witness_run
    assert graph.conditioning_path.run.artifact_binding.is_bound is False
