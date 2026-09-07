"""B-07F resolved-plan fixture-official construction acceptance tests."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest
from b02c_fixtures import ResourcePolicyFixture, make_resource_policy_fixture
from b07b_fixtures import Compiler
from b07c_fixtures import make_fixture as make_practice_fixture

from carbon import research
from carbon.construction import BoundTrainingLever
from carbon.evaluation.refs import FixtureReferenceAssetRef
from carbon.fees import (
    ExecutionEnvironmentPin,
    FeeOperationKey,
    FeePolicyKey,
    FixtureExecutionEnvelope,
    FixtureSubmissionPolicy,
    RequesterIdentity,
    StrategyHash,
    SubmissionService,
    SubmissionState,
)
from carbon.generators.refs import BurgersFixtureConfigurationRef
from carbon.measurement import MeasurementContractRef
from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeRecord,
    ChallengeRegistry,
    QualificationEvidence,
    QualificationManifest,
)
from carbon.scoring import LoadedScorePack, ScoreEngine, load_score_pack
from carbon.seeding import DeterministicFixtureProvider, FixtureOfficialEntropy
from carbon.traineval import resolved_fixture as adapter_module
from carbon.traineval.model import (
    InfrastructureCause,
    InfrastructureFailedRun,
    InfrastructureRetryClass,
)
from carbon.traineval.resolved_fixture import (
    FixtureCompilationFailed,
    FixtureConstructionCause,
    FixtureConstructionFailed,
    FixtureMeasurementCause,
    FixtureMeasurementFailed,
    FixtureReferenceCause,
    FixtureReferenceFailed,
    FixtureResourceCause,
    FixtureResourceFailed,
    FixtureRuntimePolicy,
    FixtureToyAsset,
    ResolvedFixtureCompletedRun,
    ResolvedPlanFixtureTrainEvalService,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PACK = REPOSITORY_ROOT / "tests/fixtures/score_packs/a5_fixture_v1.json"
GENERATOR_DIGEST = "sha256:" + "1" * 64
REFERENCE_DIGEST = "sha256:" + "7" * 64
MEASUREMENT_DIGEST = "sha256:" + "8" * 64
ENVIRONMENT_DIGEST = "sha256:" + "9" * 64
NUMERIC_KEYS = (
    "gate_error",
    "diagnostic_error",
    "physics_error",
    "robust_mean_a",
    "robust_tail_a",
    "robust_mean_b",
    "robust_tail_b",
    "accuracy_error_a",
    "accuracy_error_b",
)
BOOLEAN_KEYS = ("finite_ok",)


def _material(label: bytes) -> bytes:
    return hashlib.sha256(label).digest()


def _score_pack(root: Path, fixture: ResourcePolicyFixture) -> LoadedScorePack:
    document = json.loads(SOURCE_PACK.read_text(encoding="utf-8"))
    document["challenge_id"] = fixture.compile_fixture.key.challenge_id
    document["challenge_version"] = fixture.compile_fixture.key.version
    document["generator_digest_required"] = GENERATOR_DIGEST
    encoded = (json.dumps(document, indent=2) + "\n").encode()
    pack_root = root / "packs"
    pack_root.mkdir(parents=True)
    (pack_root / "b07f.json").write_bytes(encoded)
    digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
    from carbon.scoring.model import ScorePackPin

    pin = ScorePackPin(
        fixture.compile_fixture.key,
        document["scoring_version"],
        digest,
        document["generator_version_required"],
        GENERATOR_DIGEST,
        "1.0",
        "python_binary64_v1",
        True,
    )
    return load_score_pack(pack_root, "b07f.json", pin)


def _runtime_policy(environment: ExecutionEnvironmentPin) -> FixtureRuntimePolicy:
    return FixtureRuntimePolicy(
        backend_profile_id=environment.backend_profile_id,
        container_digest=environment.container_digest,
        cause_retry_classes=tuple(
            (cause, InfrastructureRetryClass.NON_RETRYABLE)
            for cause in InfrastructureCause
        ),
    )


def _adapter(
    root: Path,
    *,
    resource: ResourcePolicyFixture | None = None,
    provider: object | None = None,
) -> tuple[
    ResolvedPlanFixtureTrainEvalService,
    ResourcePolicyFixture,
    LoadedScorePack,
    ExecutionEnvironmentPin,
]:
    selected = resource or make_resource_policy_fixture(root)
    key = selected.compile_fixture.key
    pack = _score_pack(root, selected)
    environment = ExecutionEnvironmentPin("b07f-fixture-adapter-v1", ENVIRONMENT_DIGEST)
    asset = FixtureToyAsset(
        challenge_key=key,
        generator_configuration_ref=BurgersFixtureConfigurationRef(
            key, GENERATOR_DIGEST
        ),
        reference_asset_ref=FixtureReferenceAssetRef(key, REFERENCE_DIGEST),
        measurement_contract_ref=MeasurementContractRef(key, MEASUREMENT_DIGEST),
    )
    sampling_entry = next(
        entry
        for entry in selected.compile_fixture.catalog.entries
        if entry.surface_id == "fixture_sampling_level"
    )
    assert type(sampling_entry.training_lever_binding) is BoundTrainingLever
    service = ResolvedPlanFixtureTrainEvalService(
        challenge_key=key,
        candidate_assembly=selected.compile_fixture.assembly,
        candidate_assembly_ref=selected.compile_fixture.assembly.to_ref(),
        parameter_catalog=selected.compile_fixture.catalog,
        parameter_catalog_ref=selected.compile_fixture.catalog.to_ref(
            candidate_assembly=selected.compile_fixture.assembly
        ),
        authoring_origin=selected.compile_fixture.authoring_origin,
        authoring_artifacts=selected.compile_fixture.authoring_artifacts,
        compiler_identity=selected.compile_result.construction_plan.compiler_identity,
        strategy_limits=adapter_module.SubmissionResourceLimits(
            max_total_value_nodes=10_000,
            max_object_members=256,
            max_list_items=256,
            max_string_utf8_bytes=4096,
            max_object_key_utf8_bytes=512,
            max_strategy_identity_bytes=1_000_000,
            max_challenge_id_bytes=256,
            max_concurrent_identity_builds=8,
            max_retained_submission_records=64,
            max_retained_value_nodes=100_000,
            max_retained_strategy_identity_bytes=4_000_000,
        ),
        resource_policy=selected.policy,
        resource_policy_ref=selected.policy_ref,
        class_bundle=selected.class_bundle,
        selected_resource_class=selected.resource_class,
        selected_resource_class_ref=selected.resource_class_ref,
        expected_active_policy_ref=selected.policy_ref,
        expected_active_resource_class_ref=selected.resource_class_ref,
        provider=(
            DeterministicFixtureProvider(
                FixtureOfficialEntropy(_material(b"b07f fixture entropy"))
            )
            if provider is None
            else provider  # type: ignore[arg-type]
        ),
        score_pack=pack,
        runtime_policy=_runtime_policy(environment),
        declared_environment=environment,
        fixture_asset=asset,
        lever_executable_semantics_ref=sampling_entry.training_lever_binding.executable_semantics_ref,
        numeric_input_keys=NUMERIC_KEYS,
        boolean_input_keys=BOOLEAN_KEYS,
    )
    return service, selected, pack, environment


def _registry(root: Path, resource: ResourcePolicyFixture) -> ChallengeRegistry:
    registry_root = root / "registry"
    artifact_root = root / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    registry = ChallengeRegistry(registry_root, artifact_root)
    artifact_id = "b07f_fixture_bundle"
    relative = "fixture_authoring/1.0/fixture/bundle.bin"
    content = b"B-07F non-scientific fixture\n"
    target = artifact_root / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(content)
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    slots = {
        slot: QualificationEvidence(state, artifact_id, "b07f-fixture-only")
        for slot, state in REQUIRED_QUALIFICATION_STATES
    }
    key = resource.compile_fixture.key
    registry.save(
        ChallengeRecord(
            challenge_id=key.challenge_id,
            version=key.version,
            fixture_origin=True,
            status="fixture",
            allowed_backbones=("fno",),
            artifacts={artifact_id: ArtifactBinding(relative, digest)},
            qualification=QualificationManifest(
                challenge_id=key.challenge_id,
                challenge_version=key.version,
                mode="fixture",
                slots=slots,
            ),
        )
    )
    return registry


def _a7(
    root: Path,
    resource: ResourcePolicyFixture,
    pack: LoadedScorePack,
    environment: ExecutionEnvironmentPin,
) -> SubmissionService:
    return SubmissionService(
        adapter_module.SubmissionResourceLimits(
            max_total_value_nodes=10_000,
            max_object_members=256,
            max_list_items=256,
            max_string_utf8_bytes=4096,
            max_object_key_utf8_bytes=512,
            max_strategy_identity_bytes=1_000_000,
            max_challenge_id_bytes=256,
            max_concurrent_identity_builds=8,
            max_retained_submission_records=64,
            max_retained_value_nodes=100_000,
            max_retained_strategy_identity_bytes=4_000_000,
        ),
        _registry(root, resource),
        FixtureSubmissionPolicy(
            FeePolicyKey("b07f-fixture-fee-v1"),
            1,
            2,
            pack.pack_pin.generator_version_required,
            pack.pack_pin.generator_digest_required,
            pack.pack_pin.scoring_version,
            pack.pack_pin.scoring_digest,
            environment,
        ),
        _uuid_factory=lambda: uuid.UUID("123e4567-e89b-42d3-a456-426614174000"),
    )


def _start(
    service: SubmissionService,
    resource: ResourcePolicyFixture,
    strategy: dict[str, object],
) -> tuple[RequesterIdentity, object, FixtureExecutionEnvelope]:
    requester = RequesterIdentity("b07f-fixture-requester")
    submission = service.submit(requester, resource.compile_fixture.key, strategy)
    service.mark_validated(submission, requester)
    service.admit_fixture(submission, requester)
    started = service.start_fixture_attempt(
        submission,
        requester,
        FeeOperationKey("b07f-charge-v1"),
        FeeOperationKey("b07f-refund-v1"),
    )
    assert type(started.envelope) is FixtureExecutionEnvelope
    return requester, submission, started.envelope


@pytest.mark.parametrize("level", (1, 2))
def test_a7_to_plan_to_fixture_to_a5_to_publication(tmp_path: Path, level: int) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    strategy = dict(resource.compile_fixture.strategy)
    strategy["parameters"] = {"fixture_sampling_level": level}
    requester, submission, envelope = _start(lifecycle, resource, strategy)

    outcome = adapter.run_fixture(envelope)
    assert type(outcome) is ResolvedFixtureCompletedRun
    assert outcome.reconstruction_receipt.consumed_value == level
    assert outcome.reconstruction_receipt.strategy_hash == envelope.strategy_hash
    assert (
        outcome.result_receipt.reconstruction_receipt_ref
        == outcome.reconstruction_receipt.receipt_ref
    )
    assert outcome.completed_run.internal_result.pack_pin == pack.pack_pin
    assert outcome.completed_run.internal_result.eligible_for_emission is False
    assert not hasattr(outcome, "constructed_coefficient")
    assert not hasattr(outcome, "heldout_mean_squared_error")
    published = lifecycle.complete_and_publish(
        outcome.completed_run.handle, outcome.completed_run.internal_result
    )
    assert published.state is SubmissionState.PUBLISHED
    assert lifecycle.read_published(submission, requester).status in {
        "SCORED",
        "MANDATORY_GATE_FAILED",
    }


def test_registered_lever_changes_plan_construction_and_heldout_behavior(
    tmp_path: Path,
) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    outcomes = []
    for level in (1, 2):
        lifecycle = _a7(tmp_path / f"run-{level}", resource, pack, environment)
        strategy = dict(resource.compile_fixture.strategy)
        strategy["parameters"] = {"fixture_sampling_level": level}
        _, _, envelope = _start(lifecycle, resource, strategy)
        outcomes.append(adapter.run_fixture(envelope))
    first, second = outcomes
    assert type(first) is ResolvedFixtureCompletedRun
    assert type(second) is ResolvedFixtureCompletedRun
    assert first.construction_plan_ref != second.construction_plan_ref
    assert (
        first.reconstruction_receipt.constructed_artifact_digest
        != second.reconstruction_receipt.constructed_artifact_digest
    )
    assert (
        first.reconstruction_receipt.candidate_assembly_ref
        == second.reconstruction_receipt.candidate_assembly_ref
    )
    assert (
        first.reconstruction_receipt.parameter_catalog_ref
        == second.reconstruction_receipt.parameter_catalog_ref
    )
    assert (
        first.reconstruction_receipt.resource_policy_ref
        == second.reconstruction_receipt.resource_policy_ref
    )
    assert first.completed_run.internal_result != second.completed_run.internal_result
    assert first.result_receipt.result_digest != second.result_receipt.result_digest


def test_deterministic_reproduction_and_receipt_redaction(tmp_path: Path) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    left = adapter.run_fixture(envelope)
    right = adapter.run_fixture(envelope)
    assert type(left) is ResolvedFixtureCompletedRun
    assert type(right) is ResolvedFixtureCompletedRun
    assert left == right
    assert (
        left.reconstruction_receipt.canonical_bytes()
        == right.reconstruction_receipt.canonical_bytes()
    )
    receipt = left.reconstruction_receipt.canonical_bytes().lower()
    for forbidden in (
        b"entropy",
        b"seed_bytes",
        b"heldout",
        b"observation",
        b"qualification",
        b"leaderboard",
        b"frontier",
        b"settlement",
    ):
        assert forbidden not in receipt
    assert repr(left) == "ResolvedFixtureCompletedRun(<private>)"


def test_unknown_parameter_is_compilation_failure_not_score(tmp_path: Path) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    strategy = dict(resource.compile_fixture.strategy)
    strategy["parameters"] = {"fixture_sampling_level": 2, "arbitrary_code": "exec()"}
    _, _, envelope = _start(lifecycle, resource, strategy)
    outcome = adapter.run_fixture(envelope)
    assert type(outcome) is FixtureCompilationFailed
    assert outcome.emission_capable is False


def test_plan_strategy_hash_mismatch_is_construction_failure(tmp_path: Path) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    forged = object.__new__(FixtureExecutionEnvelope)
    object.__setattr__(forged, "handle", envelope.handle)
    object.__setattr__(forged, "strategy", envelope.strategy)
    object.__setattr__(forged, "strategy_hash", StrategyHash("sha256:" + "a" * 64))
    object.__setattr__(forged, "challenge_key", envelope.challenge_key)
    outcome = adapter.run_fixture(forged)
    assert outcome == FixtureConstructionFailed(
        envelope.handle, FixtureConstructionCause.PLAN_IDENTITY_MISMATCH
    )


def test_resource_failure_remains_resource_typed(tmp_path: Path) -> None:
    constrained = make_resource_policy_fixture(tmp_path, static_ceiling=1)
    adapter, resource, pack, environment = _adapter(tmp_path, resource=constrained)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    outcome = adapter.run_fixture(envelope)
    assert type(outcome) is FixtureResourceFailed
    assert outcome.cause is FixtureResourceCause.POLICY_NOT_ADMISSIBLE


def test_failure_domains_do_not_collapse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)

    monkeypatch.setattr(
        adapter_module,
        "_construct_fixture_model",
        lambda *args: (_ for _ in ()).throw(RuntimeError("private path")),
    )
    construction = adapter.run_fixture(envelope)
    assert construction == FixtureConstructionFailed(
        envelope.handle, FixtureConstructionCause.TOY_FIT_INVALID
    )
    monkeypatch.undo()

    monkeypatch.setattr(
        adapter_module,
        "_evaluate_fixture_reference",
        lambda *args: (_ for _ in ()).throw(RuntimeError("private path")),
    )
    reference = adapter.run_fixture(envelope)
    assert reference == FixtureReferenceFailed(
        envelope.handle, FixtureReferenceCause.REFERENCE_EVALUATION_FAILED
    )
    monkeypatch.undo()

    monkeypatch.setattr(
        LoadedScorePack,
        "fixture_score_input",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("private path")),
    )
    measurement = adapter.run_fixture(envelope)
    assert measurement == FixtureMeasurementFailed(
        envelope.handle, FixtureMeasurementCause.MEASUREMENT_INPUT_FAILED
    )


def test_score_engine_failure_is_measurement_not_scientific_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    monkeypatch.setattr(
        ScoreEngine,
        "score",
        lambda *args: (_ for _ in ()).throw(RuntimeError("scorer internals")),
    )
    outcome = adapter.run_fixture(envelope)
    assert outcome == FixtureMeasurementFailed(
        envelope.handle, FixtureMeasurementCause.SCORE_COMPUTATION_FAILED
    )


def test_environment_mismatch_is_infrastructure_typed(tmp_path: Path) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    forged_handle = object.__new__(type(envelope.handle))
    for name in ("submission_id", "attempt_number", "admission_kind", "seed_pin"):
        object.__setattr__(forged_handle, name, getattr(envelope.handle, name))
    object.__setattr__(
        forged_handle,
        "environment_pin",
        ExecutionEnvironmentPin("other", ENVIRONMENT_DIGEST),
    )
    forged = object.__new__(FixtureExecutionEnvelope)
    for name in ("strategy", "strategy_hash", "challenge_key"):
        object.__setattr__(forged, name, getattr(envelope, name))
    object.__setattr__(forged, "handle", forged_handle)
    outcome = adapter.run_fixture(forged)
    assert type(outcome) is InfrastructureFailedRun
    assert outcome.cause is InfrastructureCause.ENVIRONMENT_MISMATCH


def test_asset_and_service_are_fixture_only_nonserializable(tmp_path: Path) -> None:
    import pickle

    adapter, _, _, _ = _adapter(tmp_path)
    asset = adapter._ResolvedPlanFixtureTrainEvalService__fixture_asset
    with pytest.raises(TypeError):
        pickle.dumps(asset)
    with pytest.raises(TypeError):
        pickle.dumps(adapter)
    assert adapter.emission_capable is False
    assert "fixture-only" in repr(adapter)
    assert not hasattr(adapter, "mode")
    assert not hasattr(adapter, "official_context")


def test_constructor_rejects_cross_challenge_asset(tmp_path: Path) -> None:
    adapter, resource, _, _ = _adapter(tmp_path)
    asset = adapter._ResolvedPlanFixtureTrainEvalService__fixture_asset
    wrong = resource.compile_fixture.key.__class__("other", "1.0")
    with pytest.raises(ValueError):
        FixtureToyAsset(
            challenge_key=resource.compile_fixture.key,
            generator_configuration_ref=BurgersFixtureConfigurationRef(
                wrong, GENERATOR_DIGEST
            ),
            reference_asset_ref=asset.reference_asset_ref,
            measurement_contract_ref=asset.measurement_contract_ref,
        )


def test_constructor_rejects_non_fixture_entropy_provider(tmp_path: Path) -> None:
    class ProviderOriginOfficialMaterial:
        pass

    with pytest.raises(adapter_module.FixtureRunRequestError):
        _adapter(tmp_path, provider=ProviderOriginOfficialMaterial())


def test_run_rejects_cross_challenge_envelope_before_compilation(
    tmp_path: Path,
) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    forged = object.__new__(FixtureExecutionEnvelope)
    object.__setattr__(forged, "handle", envelope.handle)
    object.__setattr__(forged, "strategy", envelope.strategy)
    object.__setattr__(forged, "strategy_hash", envelope.strategy_hash)
    object.__setattr__(
        forged,
        "challenge_key",
        resource.compile_fixture.key.__class__("other", "1.0"),
    )
    with pytest.raises(adapter_module.FixtureRunIdentityError):
        adapter.run_fixture(forged)


def test_b07c_practice_and_b07f_share_exact_compiled_meaning(tmp_path: Path) -> None:
    practice = make_practice_fixture(tmp_path / "practice")
    started = practice.provider.start_research_task(
        practice.request("practice", key="b07f-practice-parity")
    )
    terminal = practice.provider.run_queued_task(started.task.task_id)
    practice_record = practice.provider.get_experiment_record(terminal.task_id)
    practice_resolved = practice_record.resolved_strategies[0]

    adapter, resource, pack, environment = _adapter(
        tmp_path / "adapter", resource=practice.domain
    )
    lifecycle = _a7(tmp_path / "official-shaped", resource, pack, environment)
    _, _, envelope = _start(
        lifecycle, resource, practice.request("practice").task_spec.strategy
    )
    outcome = adapter.run_fixture(envelope)
    assert type(outcome) is ResolvedFixtureCompletedRun
    assert outcome.construction_plan_ref == practice_resolved.resolved_plan_ref
    assert (
        outcome.reconstruction_receipt.training_policy_ref
        == practice_resolved.training_sampling_policy_ref
    )
    assert (
        outcome.reconstruction_receipt.resource_policy_ref == practice.domain.policy_ref
    )


def test_unresolved_b07e_forecast_cannot_gate_or_change_fixture_result(
    tmp_path: Path,
) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    inspection = research.StaticResourceInspectionProvider(
        compilation_resolver=Compiler(resource),
        expected_training_support_ref=resource.plan.training_support_ref,
        policy=resource.policy,
        policy_ref=resource.policy_ref,
        class_bundle=resource.class_bundle,
        selected_resource_class=resource.resource_class,
        selected_resource_class_ref=resource.resource_class_ref,
        authority_context=resource.context,
    )
    forecast = research.UncalibratedResourceForecastProvider(
        inspection
    ).forecast_resources(
        research.ForecastResourcesRequest(
            resource.compile_fixture.key,
            resource.compile_fixture.strategy,
            resource.policy_ref,
            60,
        )
    )
    assert forecast.line_items == ()
    assert "SUPPORT:UNRESOLVED" in forecast.limitations

    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    outcome = adapter.run_fixture(envelope)
    assert type(outcome) is ResolvedFixtureCompletedRun
    assert not hasattr(outcome, "forecast")
    assert not hasattr(outcome, "quote")


def test_run_has_no_context_mode_or_seed_override(tmp_path: Path) -> None:
    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    with pytest.raises(TypeError):
        adapter.run_fixture(envelope, mode="official")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        adapter.run_fixture(envelope, seed=b"x" * 32)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        adapter.run_fixture(envelope, context=object())  # type: ignore[call-arg]


def test_receipts_cannot_be_relabeled_as_production(tmp_path: Path) -> None:
    from dataclasses import FrozenInstanceError

    adapter, resource, pack, environment = _adapter(tmp_path)
    lifecycle = _a7(tmp_path, resource, pack, environment)
    _, _, envelope = _start(lifecycle, resource, resource.compile_fixture.strategy)
    outcome = adapter.run_fixture(envelope)
    assert type(outcome) is ResolvedFixtureCompletedRun
    assert (
        outcome.reconstruction_receipt.authority_marker
        == "TEST_ONLY_FIXTURE_NOT_QUALIFIED"
    )
    assert outcome.result_receipt.authority_marker == "TEST_ONLY_FIXTURE_NOT_QUALIFIED"
    with pytest.raises(FrozenInstanceError):
        outcome.result_receipt.authority_marker = "PRODUCTION"  # type: ignore[misc]


def test_a8_package_root_surface_remains_exactly_legacy() -> None:
    from carbon import traineval

    assert tuple(traineval.__all__) == (
        "FixtureRunIdentityError",
        "FixtureRunRequestError",
        "FixtureRuntimePolicy",
        "FixtureStubBackend",
        "FixtureStubProfile",
        "FixtureTrainEvalService",
    )
    assert not hasattr(traineval, "ResolvedPlanFixtureTrainEvalService")
