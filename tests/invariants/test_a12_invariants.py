"""Dedicated public-surface proofs for the twelve ratified A12 invariants."""

from __future__ import annotations

import ast
import base64
import dataclasses
import hashlib
import inspect
import json
import textwrap
from pathlib import Path

import a12_support as support
import pytest

from carbon import cards, leaderboard, mcp, observability, scoring, traineval
from carbon.cards import (
    CardConflictError,
    CardRecordKey,
    CardStore,
    CardWriteDisposition,
    RequesterAuthorizationKey,
)
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    FeeEvent,
    FeeEventKind,
    FeeOperationKey,
    FixtureExecutionEnvelope,
    RequesterIdentity,
    StrategyHash,
    SubmissionIntegrationError,
    SubmissionService,
    SubmissionState,
)
from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeKey,
    ChallengeRecord,
    ChallengeRegistry,
    LiveActivationError,
    QualificationEvidence,
    QualificationManifest,
)
from carbon.schema import dry_validate
from carbon.scoring import (
    BooleanInput,
    NumericInput,
    ScoreEngine,
    ScoreInputError,
    ScorePackInputError,
    ScorePackPin,
    ScoreStatus,
    load_score_pack,
)
from carbon.seeding import (
    DeterministicFixtureProvider,
    EvaluationBinding,
    FixtureOfficialEntropy,
    MockContext,
    MockEntropy,
    OfficialEntropy,
    RoleKey,
    SeedDomain,
    SeedPin,
    SeedValidationError,
    acquire_fixture_official_context,
    acquire_official_context,
    create_official_exam_projection,
    derive_fixture_official_seed,
    derive_mock_seed,
    derive_official_seed,
    serialize_exam_projection,
)
from carbon.traineval import FixtureStubProfile
from carbon.traineval.model import (
    CompletedFixtureRun,
    InfrastructureCause,
    InfrastructureFailedRun,
)

pytestmark = pytest.mark.invariant

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCORE_PACK_ROOT = REPOSITORY_ROOT / "tests/fixtures/score_packs"
SCORE_PACK_PATH = "a5_fixture_v1.json"
NUMERIC_VALUES = (
    ("gate_error", 0.25),
    ("diagnostic_error", 0.5),
    ("physics_error", 0.25),
    ("robust_mean_a", 0.25),
    ("robust_tail_a", 0.5),
    ("robust_mean_b", 0.5),
    ("robust_tail_b", 0.75),
    ("accuracy_error_a", 0.25),
    ("accuracy_error_b", 0.5),
)
BOOLEAN_VALUES = (("finite_ok", True),)


class SyntheticOfficialProvider:
    """Local protocol implementation carrying synthetic canary entropy only."""

    def __init__(self, entropy: bytes) -> None:
        self._entropy = OfficialEntropy(entropy)

    def observe_entropy(self) -> OfficialEntropy:
        return self._entropy


class HostilePracticeField:
    """Canary whose Python protocol hooks must not run for unavailable tools."""

    def __repr__(self) -> str:
        raise AssertionError("unavailable practice field was rendered")

    def __str__(self) -> str:
        raise AssertionError("unavailable practice field was stringified")

    def __iter__(self) -> object:
        raise AssertionError("unavailable practice field was iterated")

    def __hash__(self) -> int:
        raise AssertionError("unavailable practice field was hashed")


def _material(label: bytes) -> bytes:
    return support.material(label)


def _fixture_profile_and_pack() -> tuple[FixtureStubProfile, scoring.LoadedScorePack]:
    return support.fixture_profile_and_pack()


def _seed_pin(
    profile: FixtureStubProfile,
    *,
    binding_label: bytes = b"a12-synthetic-evaluation-binding",
) -> SeedPin:
    return SeedPin(
        challenge_key=profile.challenge_key,
        generator_version=profile.generator_version_required,
        generator_digest=profile.generator_digest_required,
        scoring_version=profile.scoring_version,
        scoring_digest=profile.scoring_digest,
        evaluation_binding=EvaluationBinding(_material(binding_label)),
    )


def _fixture_score_input(
    pack: scoring.LoadedScorePack,
    *,
    gate_error: float = 0.25,
) -> scoring.ScoreInput:
    numeric_values = tuple(
        (key, gate_error if key == "gate_error" else value)
        for key, value in NUMERIC_VALUES
    )
    return pack.fixture_score_input(
        numeric_inputs=tuple(NumericInput(key, value) for key, value in numeric_values),
        boolean_inputs=tuple(BooleanInput(key, value) for key, value in BOOLEAN_VALUES),
    )


def _changed_score_pack(tmp_path: Path) -> scoring.LoadedScorePack:
    profile, _ = _fixture_profile_and_pack()
    source = SCORE_PACK_ROOT / SCORE_PACK_PATH
    document = json.loads(source.read_text(encoding="utf-8"))
    assert type(document) is dict
    document["scoring_version"] = "fixture-2.0"
    payload = (json.dumps(document, indent=2) + "\n").encode()
    target = tmp_path / "a12-score-pack-v2.json"
    target.write_bytes(payload)
    digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    pin = ScorePackPin(
        challenge_key=profile.challenge_key,
        scoring_version="fixture-2.0",
        scoring_digest=digest,
        generator_version_required=profile.generator_version_required,
        generator_digest_required=profile.generator_digest_required,
        schema_version=profile.schema_version,
        numerical_profile=profile.numerical_profile,
        fixture_origin=True,
    )
    return load_score_pack(tmp_path, target.name, pin)


def _registry_with_manifest(
    root: Path,
    *,
    fixture_origin: bool,
    status: str,
    mode: str,
    missing_slot: str | None = None,
    challenge_id: str = "a12_contract",
    record_version: str = "v1",
    manifest_version: str | None = None,
) -> tuple[ChallengeRegistry, Path]:
    registry_root = root / "registry"
    artifact_root = root / "artifacts"
    registry_root.mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    registry = ChallengeRegistry(registry_root, artifact_root)
    artifact_id = "a12_synthetic_evidence"
    artifact_path = f"{challenge_id}/{record_version}/evidence.bin"
    artifact = artifact_root.joinpath(*artifact_path.split("/"))
    artifact.parent.mkdir(parents=True)
    payload = b"A12 synthetic structural qualification evidence\n"
    artifact.write_bytes(payload)
    digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    slots = {
        slot: QualificationEvidence(
            state=state,
            artifact_id=artifact_id,
            reference="a12-synthetic-human-review-reference",
        )
        for slot, state in REQUIRED_QUALIFICATION_STATES
    }
    if missing_slot is not None:
        del slots[missing_slot]
    registry.save(
        ChallengeRecord(
            challenge_id=challenge_id,
            version=record_version,
            fixture_origin=fixture_origin,
            status=status,
            allowed_backbones=("fno",),
            artifacts={artifact_id: ArtifactBinding(path=artifact_path, digest=digest)},
            qualification=QualificationManifest(
                challenge_id=challenge_id,
                challenge_version=manifest_version or record_version,
                mode=mode,
                slots=slots,
            ),
        )
    )
    return registry, artifact


def _field_names(model: type[object]) -> tuple[str, ...]:
    return tuple(field.name for field in dataclasses.fields(model))


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _copy_seed_pin(pin: SeedPin, **overrides: object) -> SeedPin:
    values: dict[str, object] = {
        "challenge_key": pin.challenge_key,
        "generator_version": pin.generator_version,
        "generator_digest": pin.generator_digest,
        "scoring_version": pin.scoring_version,
        "scoring_digest": pin.scoring_digest,
        "evaluation_binding": pin.evaluation_binding,
    }
    values.update(overrides)
    return SeedPin(**values)  # type: ignore[arg-type]


def _copy_envelope(
    envelope: FixtureExecutionEnvelope,
    *,
    seed_pin: SeedPin | None = None,
    environment: ExecutionEnvironmentPin | None = None,
    strategy: dict[str, object] | None = None,
    strategy_hash: StrategyHash | None = None,
) -> FixtureExecutionEnvelope:
    selected_pin = seed_pin or envelope.handle.seed_pin
    handle = ExecutionAttemptHandle(
        submission_id=envelope.handle.submission_id,
        attempt_number=envelope.handle.attempt_number,
        admission_kind=AdmissionKind.FIXTURE,
        seed_pin=selected_pin,
        environment_pin=environment or envelope.handle.environment_pin,
    )
    return FixtureExecutionEnvelope(
        handle=handle,
        strategy=dict(envelope.strategy) if strategy is None else strategy,
        strategy_hash=strategy_hash or envelope.strategy_hash,
        challenge_key=selected_pin.challenge_key,
    )


def _published_public_surfaces(
    root: Path,
) -> tuple[
    tuple[str, float | None],
    cards.EvaluationCard,
    mcp.SubmissionResult,
    leaderboard.FixtureLeaderboardPage,
    observability.SubmissionEventSnapshot,
    observability.CounterMetricSnapshot,
    observability.DurationMetricSnapshot,
]:
    registry, submission_service = support.fixture_submission_service(root)
    submission_id, requester, envelope = support.start_fixture_submission(
        submission_service
    )
    _, pack = _fixture_profile_and_pack()
    internal_result = ScoreEngine.score(_fixture_score_input(pack), pack)
    assert internal_result.status is ScoreStatus.SCORED
    published = submission_service.complete_and_publish(
        envelope.handle,
        internal_result,
    )
    assert published.state is SubmissionState.PUBLISHED
    card = submission_service.read_published(submission_id, requester)

    mcp_result = support.mcp_service(registry, submission_service).call(
        mcp.McpCall(
            "1.0",
            "get_submission_result",
            (mcp.McpField("submission_id", submission_id.value),),
        ),
        requester,
    )
    assert type(mcp_result) is mcp.SubmissionResult
    page = support.fixture_leaderboard_page(card, submission_id, with_cursor=True)
    event, counter, duration = support.observability_snapshots(submission_id)
    result_identity = (
        internal_result.pack_pin.scoring_digest,
        internal_result.combined_score,
    )
    return result_identity, card, mcp_result, page, event, counter, duration


def test_a12_r01_no_seed_leakage_across_public_surfaces(tmp_path: Path) -> None:
    profile, _ = _fixture_profile_and_pack()
    entropy = _material(b"a12-r1-synthetic-official-entropy")
    context = acquire_official_context(
        SyntheticOfficialProvider(entropy),
        _seed_pin(profile),
    )
    draw_index = 0xA12A12A12A12
    derived = derive_official_seed(
        context,
        SeedDomain.OFFICIAL_EVAL,
        RoleKey("a12_probe"),
        draw_index,
    )
    projection = serialize_exam_projection(create_official_exam_projection(context))
    assert tuple(projection) == (
        "exam_commitment",
        "challenge_id",
        "challenge_version",
        "generator_version",
        "generator_digest",
        "scoring_version",
        "scoring_digest",
        "fixture",
    )

    registry, submission_service = support.fixture_submission_service(
        tmp_path / "causal-a8"
    )
    submission_id, requester, envelope = support.start_fixture_submission(
        submission_service
    )
    fixture_context = acquire_fixture_official_context(
        DeterministicFixtureProvider(FixtureOfficialEntropy(entropy)),
        envelope.handle.seed_pin,
    )
    fixture_derived = derive_fixture_official_seed(
        fixture_context,
        SeedDomain.OFFICIAL_EVAL,
        RoleKey("a12_fixture_probe"),
        draw_index,
    )
    _, train_eval = support.fixture_train_eval_service(entropy=entropy)
    outcome = train_eval.run_fixture(envelope)
    assert type(outcome) is CompletedFixtureRun
    published = submission_service.complete_and_publish(
        outcome.handle,
        outcome.internal_result,
    )
    assert published.state is SubmissionState.PUBLISHED
    card = submission_service.read_published(submission_id, requester)
    mcp_result = support.mcp_service(registry, submission_service).call(
        mcp.McpCall(
            "1.0",
            "get_submission_result",
            (mcp.McpField("submission_id", submission_id.value),),
        ),
        requester,
    )
    assert type(mcp_result) is mcp.SubmissionResult
    _, _, _, page, _, _, _ = _published_public_surfaces(tmp_path / "a10")
    event, counter, duration = support.observability_snapshots(submission_id)
    assert mcp_result.card == card and mcp_result.card is not card
    assert len(page.rows) == 1
    assert page.next_cursor is not None
    component_strings = (
        ()
        if card.component_scores is None
        else (
            str(card.component_scores.physics),
            str(card.component_scores.robustness),
            str(card.component_scores.accuracy),
        )
    )

    surface_strings = (
        *(str(value) for value in projection.values()),
        card.schema_version,
        card.result_id,
        card.status,
        card.scoring_pack_hash,
        str(card.overall_score),
        *component_strings,
        *(gate.gate_id for gate in card.gate_results),
        *(str(gate.passed) for gate in card.gate_results),
        *card.failure_tags,
        *card.public_diagnostics,
        card.disclosure_tier,
        mcp_result.schema_version,
        mcp_result.status.submission_id.value,
        mcp_result.status.state.value,
        page.schema_version,
        page.challenge_key.challenge_id,
        page.challenge_key.version,
        page.scoring_pack_hash,
        *(row.challenge_key.challenge_id for row in page.rows),
        *(row.challenge_key.version for row in page.rows),
        *(row.scoring_pack_hash for row in page.rows),
        *(str(row.rank) for row in page.rows),
        *(str(row.overall_score) for row in page.rows),
        *(str(row.publication_sequence.value) for row in page.rows),
        page.next_cursor.value,
        event.kind,
        event.submission_id,
        event.submission_state,
        event.score_status or "",
        counter.metric_name,
        duration.stage,
        str(duration.duration_ns),
    )
    for synthetic_secret in (
        entropy,
        derived.as_backend_bytes(),
        fixture_derived.as_backend_bytes(),
    ):
        secret_forms = {
            synthetic_secret.hex(),
            base64.b64encode(synthetic_secret).decode("ascii"),
            base64.urlsafe_b64encode(synthetic_secret).decode("ascii"),
            str(int.from_bytes(synthetic_secret, "big")),
        }
        assert all(
            secret_form not in public_value
            for secret_form in secret_forms
            for public_value in surface_strings
        )
    for hidden_identifier in (
        str(draw_index),
        support.LEADERBOARD_HIDDEN_SUBMISSION_ID,
        support.LEADERBOARD_HIDDEN_RESULT_ID,
    ):
        assert all(hidden_identifier not in value for value in surface_strings)

    assert _field_names(cards.EvaluationCard) == (
        "schema_version",
        "result_id",
        "status",
        "scoring_pack_hash",
        "overall_score",
        "component_scores",
        "gate_results",
        "failure_tags",
        "fixture_origin",
        "eligible_for_emission",
        "public_diagnostics",
        "disclosure_tier",
    )
    assert _field_names(mcp.SubmissionResult) == ("schema_version", "status", "card")
    assert _field_names(leaderboard.FixtureLeaderboardRow) == (
        "rank",
        "challenge_key",
        "scoring_pack_hash",
        "overall_score",
        "mandatory_gates_passed",
        "publication_sequence",
        "fixture_origin",
        "eligible_for_emission",
    )
    assert observability.SubmissionEventSnapshot.__slots__ == (
        "kind",
        "submission_id",
        "submission_state",
        "score_status",
    )

    forbidden_modules = {"carbon.seeding", "carbon.traineval"}
    forbidden_names = {
        "DerivedSeed",
        "EvaluationBinding",
        "FixtureOfficialContext",
        "FixtureOfficialEntropy",
        "OfficialContext",
        "OfficialEntropy",
        "SeedPin",
        "acquire_fixture_official_context",
        "acquire_official_context",
        "derive_fixture_official_seed",
        "derive_official_seed",
    }
    for package_name in ("cards", "leaderboard", "mcp", "observability"):
        for path in REPOSITORY_ROOT.joinpath("carbon", package_name).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert all(
                        not any(
                            alias.name == module or alias.name.startswith(f"{module}.")
                            for module in forbidden_modules
                        )
                        for alias in node.names
                    )
                if isinstance(node, ast.ImportFrom):
                    assert node.module is None or not any(
                        node.module == module or node.module.startswith(f"{module}.")
                        for module in forbidden_modules
                    )
                    assert all(
                        alias.name not in forbidden_names | {"seeding", "traineval"}
                        for alias in node.names
                    )
                if isinstance(node, ast.Call):
                    assert _called_name(node) not in forbidden_names


def test_a12_r02_practice_isolation_is_fail_closed(tmp_path: Path) -> None:
    profile, _ = _fixture_profile_and_pack()
    pin = _seed_pin(profile)
    mock_context = MockContext(
        MockEntropy(_material(b"a12-r2-synthetic-mock-entropy")),
        pin,
    )
    fixture_context = acquire_fixture_official_context(
        DeterministicFixtureProvider(
            FixtureOfficialEntropy(_material(b"a12-r2-synthetic-fixture-entropy"))
        ),
        pin,
    )
    mock_seed = derive_mock_seed(mock_context, RoleKey("practice_probe"), 0)
    fixture_seed = derive_fixture_official_seed(
        fixture_context,
        SeedDomain.OFFICIAL_EVAL,
        RoleKey("fixture_probe"),
        0,
    )
    assert mock_seed != fixture_seed
    with pytest.raises(SeedValidationError):
        derive_official_seed(
            mock_context,  # type: ignore[arg-type]
            SeedDomain.OFFICIAL_EVAL,
            RoleKey("practice_probe"),
            0,
        )
    with pytest.raises(SeedValidationError):
        derive_mock_seed(fixture_context, RoleKey("practice_probe"), 0)  # type: ignore[arg-type]

    assert tuple(traineval.__all__) == (
        "FixtureRunIdentityError",
        "FixtureRunRequestError",
        "FixtureRuntimePolicy",
        "FixtureStubBackend",
        "FixtureStubProfile",
        "FixtureTrainEvalService",
    )
    registry, submission_service = support.fixture_submission_service(tmp_path)
    service = support.mcp_service(registry, submission_service)
    for unavailable_tool in ("light_train", "light_compare", "practice"):
        with pytest.raises(mcp.McpToolUnavailableError):
            service.call(
                mcp.McpCall(
                    "1.0",
                    unavailable_tool,
                    (
                        mcp.McpField(
                            "unknown_semantic_field",
                            HostilePracticeField(),
                        ),
                    ),
                ),
                RequesterIdentity("a12-practice-requester-v1"),
            )

    traineval_files = tuple(
        path.name
        for path in sorted(REPOSITORY_ROOT.joinpath("carbon/traineval").glob("*.py"))
    )
    assert traineval_files == (
        "__init__.py",
        "model.py",
        "service.py",
        "stub.py",
    )
    forbidden_owner_modules = {
        "carbon.cards",
        "carbon.mcp",
        "carbon.registry",
    }
    forbidden_official_or_practice_names = {
        "ChallengeRecord",
        "ChallengeRegistry",
        "MockContext",
        "MockEntropy",
        "OfficialContext",
        "OfficialEntropy",
        "OfficialExamProjection",
        "QualificationManifest",
        "acquire_official_context",
        "create_official_exam_projection",
        "derive_mock_seed",
        "derive_official_seed",
        "load_score_pack",
        "read_verified_artifact",
        "read_verified_artifact_bytes",
        "serialize_exam_projection",
    }
    forbidden_definition_fragments = ("light", "mock", "practice", "research")
    for path in REPOSITORY_ROOT.joinpath("carbon/traineval").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not any(
                        alias.name == module or alias.name.startswith(f"{module}.")
                        for module in forbidden_owner_modules
                    )
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom):
                if node.module == "carbon.registry":
                    assert tuple(
                        (alias.name, alias.asname) for alias in node.names
                    ) == (("ChallengeKey", None),)
                else:
                    assert node.module is None or not any(
                        node.module == module or node.module.startswith(f"{module}.")
                        for module in forbidden_owner_modules
                    )
                assert all(
                    alias.name
                    not in forbidden_official_or_practice_names
                    | {"cards", "mcp", "registry"}
                    for alias in node.names
                )
            if isinstance(node, ast.Call):
                assert _called_name(node) not in forbidden_official_or_practice_names
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                definition_name = node.name.lower().replace("preflight", "")
                assert not any(
                    fragment in definition_name
                    for fragment in forbidden_definition_fragments
                )


def test_a12_r03_scored_fixture_evaluation_is_exactly_pinned(
    tmp_path: Path,
) -> None:
    _, pack = _fixture_profile_and_pack()
    registry, submission_service = support.fixture_submission_service(tmp_path / "a7")
    del registry
    submission_id, requester, envelope = support.start_fixture_submission(
        submission_service
    )
    _, train_eval = support.fixture_train_eval_service(
        entropy=_material(b"a12-r3-synthetic-fixture-entropy")
    )
    outcome = train_eval.run_fixture(envelope)
    assert type(outcome) is CompletedFixtureRun
    result = outcome.internal_result
    handle = outcome.handle
    assert result.pack_pin == pack.pack_pin
    assert handle.seed_pin.challenge_key == result.pack_pin.challenge_key
    assert (
        handle.seed_pin.generator_version == result.pack_pin.generator_version_required
    )
    assert handle.seed_pin.generator_digest == result.pack_pin.generator_digest_required
    assert handle.seed_pin.scoring_version == result.pack_pin.scoring_version
    assert handle.seed_pin.scoring_digest == result.pack_pin.scoring_digest
    assert handle.environment_pin == support.execution_environment()
    published = submission_service.complete_and_publish(handle, result)
    assert published.state is SubmissionState.PUBLISHED
    assert (
        submission_service.read_published(submission_id, requester).scoring_pack_hash
        == result.pack_pin.scoring_digest
    )

    changed_pack = _changed_score_pack(tmp_path)
    with pytest.raises(ScoreInputError) as captured:
        ScoreEngine.score(_fixture_score_input(pack), changed_pack)
    assert captured.value.code == "score_input.pin_mismatch"

    base_pin = envelope.handle.seed_pin
    alternate_environment_profile = support.execution_environment(
        backend_profile_id="a8-fixture-backend-v2"
    )
    alternate_container = support.execution_environment(
        container_digest="sha256:" + "4" * 64
    )
    mismatch_cases = (
        (
            _copy_seed_pin(
                base_pin,
                challenge_key=ChallengeKey("a5_fixture_other", "fixture-1.0"),
            ),
            envelope.handle.environment_pin,
            InfrastructureCause.SCORE_PACK_MISMATCH,
        ),
        (
            _copy_seed_pin(base_pin, generator_version="fixture-2.0"),
            envelope.handle.environment_pin,
            InfrastructureCause.SCORE_PACK_MISMATCH,
        ),
        (
            _copy_seed_pin(base_pin, generator_digest="sha256:" + "6" * 64),
            envelope.handle.environment_pin,
            InfrastructureCause.SCORE_PACK_MISMATCH,
        ),
        (
            _copy_seed_pin(base_pin, scoring_version="fixture-2.0"),
            envelope.handle.environment_pin,
            InfrastructureCause.SCORE_PACK_MISMATCH,
        ),
        (
            _copy_seed_pin(base_pin, scoring_digest="sha256:" + "7" * 64),
            envelope.handle.environment_pin,
            InfrastructureCause.SCORE_PACK_MISMATCH,
        ),
        (
            base_pin,
            alternate_environment_profile,
            InfrastructureCause.ENVIRONMENT_MISMATCH,
        ),
        (
            base_pin,
            alternate_container,
            InfrastructureCause.ENVIRONMENT_MISMATCH,
        ),
    )
    for mismatched_pin, mismatched_environment, expected_cause in mismatch_cases:
        rejected = train_eval.run_fixture(
            _copy_envelope(
                envelope,
                seed_pin=mismatched_pin,
                environment=mismatched_environment,
            )
        )
        assert type(rejected) is InfrastructureFailedRun
        assert rejected.cause is expected_cause
        assert rejected.emission_capable is False


def test_a12_r04_miner_disclosure_uses_positive_allow_lists(
    tmp_path: Path,
) -> None:
    result_identity, card, mcp_result, page, event, counter, duration = (
        _published_public_surfaces(tmp_path)
    )
    assert _field_names(cards.EvaluationCard) == (
        "schema_version",
        "result_id",
        "status",
        "scoring_pack_hash",
        "overall_score",
        "component_scores",
        "gate_results",
        "failure_tags",
        "fixture_origin",
        "eligible_for_emission",
        "public_diagnostics",
        "disclosure_tier",
    )
    assert _field_names(mcp.SubmissionResult) == ("schema_version", "status", "card")
    assert _field_names(leaderboard.FixtureLeaderboardRow) == (
        "rank",
        "challenge_key",
        "scoring_pack_hash",
        "overall_score",
        "mandatory_gates_passed",
        "publication_sequence",
        "fixture_origin",
        "eligible_for_emission",
    )
    assert observability.SubmissionEventSnapshot.__slots__ == (
        "kind",
        "submission_id",
        "submission_state",
        "score_status",
    )
    assert not hasattr(scoring, "InternalResult")
    assert not hasattr(scoring, "GateDecision")
    assert not hasattr(scoring, "LegScore")
    result_digest, result_score = result_identity
    assert card.scoring_pack_hash == result_digest
    assert card.overall_score == result_score
    assert mcp_result.card == card and mcp_result.card is not card
    assert mcp_result.status.state is SubmissionState.PUBLISHED
    assert len(page.rows) == 1
    assert page.rows[0].scoring_pack_hash == card.scoring_pack_hash
    assert page.rows[0].overall_score == card.overall_score
    assert page.rows[0].fixture_origin is True
    assert page.rows[0].eligible_for_emission is False
    assert type(event) is observability.SubmissionEventSnapshot
    assert type(counter) is observability.CounterMetricSnapshot
    assert type(duration) is observability.DurationMetricSnapshot
    assert (event.kind, event.submission_state, event.score_status) == (
        "SCORE",
        "SCORED",
        "SCORED",
    )


def test_a12_r05_live_requires_complete_exact_qualification(tmp_path: Path) -> None:
    complete_registry, artifact = _registry_with_manifest(
        tmp_path / "complete",
        fixture_origin=False,
        status="draft",
        mode="production",
    )
    activated = complete_registry.activate_live("a12_contract", "v1")
    assert activated.status == "live"
    assert complete_registry.is_effectively_live("a12_contract", "v1") is True
    artifact.write_bytes(b"mutated synthetic evidence\n")
    assert complete_registry.is_effectively_live("a12_contract", "v1") is False

    stale_registry, _ = _registry_with_manifest(
        tmp_path / "stale",
        fixture_origin=False,
        status="draft",
        mode="production",
        manifest_version="v2",
    )
    stale = stale_registry.assess_live_eligibility("a12_contract", "v1")
    assert stale.eligible is False
    assert "qualification.challenge_version_mismatch" in {
        reason.code for reason in stale.reasons
    }

    missing_slot = REQUIRED_QUALIFICATION_STATES[-1][0]
    registry, _ = _registry_with_manifest(
        tmp_path / "incomplete",
        fixture_origin=False,
        status="draft",
        mode="production",
        missing_slot=missing_slot,
    )
    assessment = registry.assess_live_eligibility("a12_contract", "v1")
    assert assessment.eligible is False
    assert any(
        reason.code == "qualification.slot_missing"
        and reason.path.endswith(f"/{missing_slot}")
        for reason in assessment.reasons
    )
    with pytest.raises(LiveActivationError):
        registry.activate_live("a12_contract", "v1")
    assert registry.is_effectively_live("a12_contract", "v1") is False


def test_a12_r06_production_execution_remains_unavailable_without_sandbox(
    tmp_path: Path,
) -> None:
    production_registry, _ = _registry_with_manifest(
        tmp_path / "production",
        fixture_origin=False,
        status="draft",
        mode="production",
    )
    production_registry.activate_live("a12_contract", "v1")
    production_service = support.submission_service_for_registry(production_registry)
    production_requester = RequesterIdentity("a12-production-requester-v1")
    production_submission = production_service.submit(
        production_requester,
        ChallengeKey("a12_contract", "v1"),
        {
            "schema_version": "1.0",
            "challenge_id": "a12_contract",
            "backbone": "fno",
            "parameters": {"synthetic": True},
        },
    )
    production_service.mark_validated(
        production_submission,
        production_requester,
    )
    with pytest.raises(SubmissionIntegrationError):
        production_service.admit_production(
            production_submission,
            production_requester,
        )

    _, fixture_service = support.fixture_submission_service(tmp_path / "fixture")
    requester = RequesterIdentity("a12-fixture-requester-v1")
    submission_id = fixture_service.submit(
        requester,
        FixtureStubProfile().challenge_key,
        {
            "schema_version": "1.0",
            "challenge_id": "a5_fixture",
            "backbone": "fno",
            "parameters": {"synthetic": True},
        },
    )
    fixture_service.mark_validated(submission_id, requester)
    fixture_service.admit_fixture(submission_id, requester)
    with pytest.raises(SubmissionIntegrationError):
        fixture_service.start_production_attempt(
            submission_id,
            requester,
            FeeOperationKey("a12-production-charge-v1"),
            FeeOperationKey("a12-production-refund-v1"),
        )
    with pytest.raises(SubmissionIntegrationError):
        fixture_service.start_production_retry_attempt(submission_id, requester)

    started = fixture_service.start_fixture_attempt(
        submission_id,
        requester,
        FeeOperationKey("a12-fixture-charge-v1"),
        FeeOperationKey("a12-fixture-refund-v1"),
    )
    assert type(started.envelope) is FixtureExecutionEnvelope
    _, train_eval = support.fixture_train_eval_service(
        entropy=_material(b"a12-r6-synthetic-fixture-entropy")
    )
    first = train_eval.run_fixture(
        _copy_envelope(
            started.envelope,
            strategy={"synthetic_strategy": {"left": [1, 2, 3]}},
            strategy_hash=StrategyHash("sha256:" + "3" * 64),
        )
    )
    second = train_eval.run_fixture(
        _copy_envelope(
            started.envelope,
            strategy={"synthetic_strategy": {"right": [9, 8, 7]}},
            strategy_hash=StrategyHash("sha256:" + "5" * 64),
        )
    )
    assert type(first) is type(second) is CompletedFixtureRun
    assert first.internal_result == second.internal_result

    for method_name in (
        "admit_production",
        "start_production_attempt",
        "start_production_retry_attempt",
    ):
        method = getattr(SubmissionService, method_name)
        tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
        called = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            if (name := _called_name(node)) is not None
        }
        raised = {
            _called_name(node.exc)
            for node in ast.walk(tree)
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
        }
        assert "ProductionExecutionEnvelope" not in called
        assert "SubmissionIntegrationError" in raised
        assert not any(
            isinstance(node, ast.Return) and node.value is not None
            for node in ast.walk(tree)
        )

    assert tuple(traineval.__all__) == (
        "FixtureRunIdentityError",
        "FixtureRunRequestError",
        "FixtureRuntimePolicy",
        "FixtureStubBackend",
        "FixtureStubProfile",
        "FixtureTrainEvalService",
    )
    prohibited_import_roots = {
        "bittensor",
        "docker",
        "jax",
        "multiprocessing",
        "socket",
        "subprocess",
        "torch",
    }
    prohibited_unqualified_calls = {
        "compile",
        "eval",
        "exec",
    }
    prohibited_attribute_calls = {
        "Popen",
        "execv",
        "execve",
        "popen",
        "system",
    }
    for package_name in ("fees", "traineval", "mcp"):
        for path in REPOSITORY_ROOT.joinpath("carbon", package_name).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert all(
                        alias.name.partition(".")[0] not in prohibited_import_roots
                        for alias in node.names
                    )
                if isinstance(node, ast.ImportFrom) and node.module is not None:
                    assert node.module.partition(".")[0] not in prohibited_import_roots
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        assert node.func.id not in prohibited_unqualified_calls
                    if isinstance(node.func, ast.Attribute):
                        assert node.func.attr not in prohibited_attribute_calls
    assert FixtureStubProfile().fixture_origin is True


def test_a12_r07_infrastructure_cannot_be_scored_as_science(
    tmp_path: Path,
) -> None:
    mismatched_environment = support.execution_environment(
        backend_profile_id="a8-fixture-backend-v2"
    )
    _, submission_service = support.fixture_submission_service(
        tmp_path,
        max_attempts=2,
        environment=mismatched_environment,
    )
    submission_id, requester, first_envelope = support.start_fixture_submission(
        submission_service
    )
    _, train_eval = support.fixture_train_eval_service(
        entropy=_material(b"a12-r7-synthetic-fixture-entropy")
    )
    first_outcome = train_eval.run_fixture(first_envelope)
    assert type(first_outcome) is InfrastructureFailedRun
    assert first_outcome.cause is InfrastructureCause.ENVIRONMENT_MISMATCH
    assert first_outcome.emission_capable is False
    assert not hasattr(first_outcome, "internal_result")
    queued = submission_service.retry_infrastructure(first_outcome.handle)
    assert queued.state is SubmissionState.QUEUED

    second_envelope = submission_service.start_fixture_retry_attempt(
        submission_id,
        requester,
    )
    second_outcome = train_eval.run_fixture(second_envelope)
    assert type(second_outcome) is InfrastructureFailedRun
    refund = submission_service.retry_infrastructure(second_outcome.handle)
    assert type(refund) is FeeEvent
    assert refund.kind is FeeEventKind.REFUND
    assert (
        submission_service.get_status(submission_id, requester).state
        is SubmissionState.FAILED_INFRA
    )

    _, pack = _fixture_profile_and_pack()
    with pytest.raises(ScoreInputError) as captured:
        ScoreEngine.score({"infrastructure_failure": "oom"}, pack)  # type: ignore[arg-type]
    assert captured.value.code == "score_input.type"

    scientific_failure = ScoreEngine.score(
        _fixture_score_input(pack, gate_error=1.0),
        pack,
    )
    assert scientific_failure.status is ScoreStatus.MANDATORY_GATE_FAILED
    assert scientific_failure.eligible_for_emission is False
    assert scientific_failure.gate_decisions


def test_a12_r08_pinned_fixture_reexecution_is_exactly_reproducible(
    tmp_path: Path,
) -> None:
    entropy = _material(b"a12-r8-synthetic-fixture-entropy")
    _, submission_service = support.fixture_submission_service(tmp_path)
    _, _, envelope = support.start_fixture_submission(submission_service)
    first_policy, first_service = support.fixture_train_eval_service(entropy=entropy)
    second_policy, second_service = support.fixture_train_eval_service(entropy=entropy)
    second_envelope = _copy_envelope(envelope)
    first = first_service.run_fixture(envelope)
    second = second_service.run_fixture(second_envelope)
    assert type(first) is type(second) is CompletedFixtureRun
    assert first_policy == second_policy and first_policy is not second_policy
    assert first.handle == second.handle and first.handle is not second.handle
    assert first.internal_result == second.internal_result
    assert first.internal_result is not second.internal_result
    assert first.internal_result.pack_pin == second.internal_result.pack_pin


def test_a12_r09_fixture_values_cannot_gain_live_or_emission_authority(
    tmp_path: Path,
) -> None:
    registry, _ = _registry_with_manifest(
        tmp_path,
        fixture_origin=True,
        status="fixture",
        mode="fixture",
    )
    assert registry.can_go_live("a12_contract", "v1") is False
    assert registry.is_effectively_live("a12_contract", "v1") is False

    _, pack = _fixture_profile_and_pack()
    result = ScoreEngine.score(_fixture_score_input(pack), pack)
    assert result.pack_pin.fixture_origin is True
    assert result.eligible_for_emission is False
    assert FixtureStubProfile().fixture_origin is True

    placeholder_registry, _ = _registry_with_manifest(
        tmp_path / "placeholder",
        fixture_origin=False,
        status="draft",
        mode="production",
        record_version="TODO",
    )
    placeholder = placeholder_registry.assess_live_eligibility("a12_contract", "TODO")
    assert placeholder.eligible is False
    assert "record.version_placeholder" in {
        reason.code for reason in placeholder.reasons
    }

    _, card, _, page, _, _, _ = _published_public_surfaces(tmp_path / "leaderboard")
    assert card.fixture_origin is page.fixture_origin is True
    assert card.eligible_for_emission is page.eligible_for_emission is False
    assert all(
        row.fixture_origin is True and row.eligible_for_emission is False
        for row in page.rows
    )
    for package_name in ("registry", "scoring", "leaderboard"):
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in REPOSITORY_ROOT.joinpath("carbon", package_name).glob("*.py")
        )
        assert "MockContext" not in source
        assert "MockEntropy" not in source


def test_a12_r10_new_pack_cannot_silently_overwrite_history(tmp_path: Path) -> None:
    _, original_pack = _fixture_profile_and_pack()
    changed_pack = _changed_score_pack(tmp_path)
    original_result = ScoreEngine.score(
        _fixture_score_input(original_pack),
        original_pack,
    )
    changed_result = ScoreEngine.score(
        _fixture_score_input(changed_pack),
        changed_pack,
    )
    assert original_result.pack_pin.scoring_version == "fixture-1.0"
    assert changed_result.pack_pin.scoring_version == "fixture-2.0"

    store = CardStore()
    historical_key = CardRecordKey("a12-historical-result-v1")
    future_key = CardRecordKey("a12-future-result-v2")
    requester = RequesterAuthorizationKey("a12-requester-v1")
    assert (
        store.write_internal(historical_key, requester, original_result)
        is CardWriteDisposition.INSERTED
    )
    historical_card = store.read_budgeted(historical_key, requester)
    with pytest.raises(CardConflictError):
        store.write_internal(historical_key, requester, changed_result)
    assert store.read_budgeted(historical_key, requester) == historical_card
    assert (
        store.write_internal(future_key, requester, changed_result)
        is CardWriteDisposition.INSERTED
    )
    assert (
        store.read_budgeted(future_key, requester).scoring_pack_hash
        == changed_result.pack_pin.scoring_digest
    )


def test_a12_r11_named_forbidden_signals_cannot_enter_scoring() -> None:
    _, pack = _fixture_profile_and_pack()
    forbidden_inputs = (
        "prior_similarity",
        "prior_alignment",
        "estimate",
        "resource_forecast",
        "practice_score",
        "light_score",
        "research_information_value",
        "exam_fee",
        "mock_metric",
    )
    declared_pack_input_keys = {gate.input_key for gate in pack.hard_gates}
    declared_pack_input_keys.update(
        component.input_key for component in pack.physics.components
    )
    for category in pack.robustness.categories:
        declared_pack_input_keys.add(category.mean_input_key)
        declared_pack_input_keys.add(category.tail_input_key)
    declared_pack_input_keys.update(
        component.input_key for component in pack.accuracy.components
    )
    assert set(forbidden_inputs).isdisjoint(declared_pack_input_keys)

    canonical_numeric = tuple(NumericInput(key, value) for key, value in NUMERIC_VALUES)
    canonical_boolean = tuple(BooleanInput(key, value) for key, value in BOOLEAN_VALUES)
    for forbidden_input in forbidden_inputs:
        with pytest.raises(ScorePackInputError) as captured:
            pack.fixture_score_input(
                numeric_inputs=canonical_numeric
                + (NumericInput(forbidden_input, 0.0),),
                boolean_inputs=canonical_boolean,
            )
        assert captured.value.code == "score_pack.input_key_set"
        assert captured.value.path == "/numeric_inputs"
        with pytest.raises(ScorePackInputError) as captured:
            pack.fixture_score_input(
                numeric_inputs=canonical_numeric,
                boolean_inputs=canonical_boolean
                + (BooleanInput(forbidden_input, True),),
            )
        assert captured.value.code == "score_pack.input_key_set"
        assert captured.value.path == "/boolean_inputs"
    assert tuple(inspect.signature(ScoreEngine.score).parameters) == (
        "score_input",
        "pack",
    )


def test_a12_r12_practice_is_incomplete_and_has_no_official_authority() -> None:
    tool_values = tuple(tool.value for tool in mcp.McpTool)
    assert tool_values == (
        "get_challenge_info",
        "get_prior",
        "get_mock_scaffold",
        "dry_validate",
        "estimate",
        "submit",
        "get_submission_result",
    )
    assert not any(
        token in tool
        for tool in tool_values
        for token in ("practice", "light_", "train", "execute", "schedule")
    )

    challenge = ChallengeKey("a12_contract", "v1")
    scaffold_ref = mcp.ScaffoldRef(
        challenge,
        "a12_scaffold",
        "v1",
        "sha256:" + "4" * 64,
    )
    scaffold = mcp.PublishedScaffold(
        "1.0",
        scaffold_ref,
        {"schema_version": "1.0", "backbone": "fno"},
        None,
        True,
    )
    assert scaffold.execution_deferred is True
    with pytest.raises(mcp.McpIntegrationError):
        mcp.PublishedScaffold(
            "1.0",
            scaffold_ref,
            {"schema_version": "1.0", "backbone": "fno"},
            None,
            False,
        )

    prior_ref = mcp.PriorRef(
        challenge,
        "a12_prior",
        "v1",
        "sha256:" + "5" * 64,
    )
    validation = dry_validate(
        {
            "schema_version": "1.0",
            "challenge_id": "a12_contract",
            "backbone": "fno",
            "parameters": {},
        }
    )
    assert validation.ok is True
    estimate = mcp.StructuralEstimate(
        "1.0",
        challenge,
        prior_ref,
        validation,
        (),
        "non_binding_structural_prior_only",
    )
    assert estimate.disclaimer == "non_binding_structural_prior_only"
    with pytest.raises(mcp.McpIntegrationError):
        mcp.StructuralEstimate(
            "1.0",
            challenge,
            prior_ref,
            validation,
            (),
            "authoritative_practice_score",
        )

    estimate_fields = set(_field_names(mcp.StructuralEstimate))
    assert estimate_fields == {
        "schema_version",
        "challenge_key",
        "prior_ref",
        "validation",
        "applicable_directives",
        "disclaimer",
    }
    assert not estimate_fields.intersection(
        {"score", "rank", "schedule", "official_cases", "shadow_cases"}
    )
    forbidden_authority_calls = {
        "activate_live",
        "admit_fixture",
        "admit_production",
        "complete_and_publish",
        "score",
        "start_fixture_attempt",
        "start_production_attempt",
        "submit",
    }
    for method_name in ("_get_mock_scaffold", "_estimate"):
        method = getattr(mcp.McpService, method_name)
        tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
        calls = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            if (name := _called_name(node)) is not None
        }
        assert calls.isdisjoint(forbidden_authority_calls)
