"""Public production-surface composition helpers for the A12 integration judge."""

from __future__ import annotations

import hashlib
from pathlib import Path

from carbon import leaderboard, mcp, observability, scoring
from carbon.cards import EvaluationCard
from carbon.fees import (
    ExecutionEnvironmentPin,
    FeeOperationKey,
    FeePolicyKey,
    FixtureExecutionEnvelope,
    FixtureSubmissionPolicy,
    RequesterIdentity,
    SubmissionId,
    SubmissionResourceLimits,
    SubmissionService,
    SubmissionState,
)
from carbon.registry import (
    REQUIRED_QUALIFICATION_STATES,
    ArtifactBinding,
    ChallengeRecord,
    ChallengeRegistry,
    QualificationEvidence,
    QualificationManifest,
)
from carbon.scoring import ScoreStatus, load_score_pack
from carbon.seeding import DeterministicFixtureProvider, FixtureOfficialEntropy
from carbon.traineval import (
    FixtureRuntimePolicy,
    FixtureStubBackend,
    FixtureStubProfile,
    FixtureTrainEvalService,
)
from carbon.traineval.model import InfrastructureCause, InfrastructureRetryClass

SCORE_PACK_ROOT = Path(__file__).resolve().parents[2] / "tests/fixtures/score_packs"
SCORE_PACK_PATH = "a5_fixture_v1.json"
DEFAULT_BACKEND_PROFILE = "a8-fixture-backend-v1"
DEFAULT_CONTAINER_DIGEST = "sha256:" + "2" * 64
LEADERBOARD_HIDDEN_SUBMISSION_ID = "123e4567-e89b-42d3-a456-426614174001"
LEADERBOARD_HIDDEN_RESULT_ID = "123e4567-e89b-42d3-a456-426614174002"


class SyntheticQueryBudgetGate:
    """Bounded local implementation of the public MCP budget-gate protocol."""

    def consume(self, requester: RequesterIdentity, tool: mcp.McpTool) -> None:
        assert type(requester) is RequesterIdentity
        assert type(tool) is mcp.McpTool


class SyntheticLeaderboardProvider:
    """Return one immutable synthetic candidate snapshot."""

    def __init__(
        self,
        snapshot: leaderboard.FixtureLeaderboardCandidateSnapshot,
    ) -> None:
        self._snapshot = snapshot

    def get_snapshot(
        self,
        challenge_key: object,
        snapshot_sequence: object,
    ) -> leaderboard.FixtureLeaderboardCandidateSnapshot:
        del challenge_key, snapshot_sequence
        return self._snapshot


class RecordingEventSink:
    """Record only public A11 event snapshots delivered by the service."""

    def __init__(self) -> None:
        self.events: list[
            observability.SubmissionEventSnapshot | observability.BoundaryErrorSnapshot
        ] = []

    def emit_event(
        self,
        event: (
            observability.SubmissionEventSnapshot | observability.BoundaryErrorSnapshot
        ),
        /,
    ) -> None:
        self.events.append(event)


class RecordingMetricSink:
    """Record only public A11 metric snapshots delivered by the service."""

    def __init__(self) -> None:
        self.counters: list[observability.CounterMetricSnapshot] = []
        self.durations: list[observability.DurationMetricSnapshot] = []

    def increment_counter(
        self,
        metric: observability.CounterMetricSnapshot,
        /,
    ) -> None:
        self.counters.append(metric)

    def observe_duration(
        self,
        metric: observability.DurationMetricSnapshot,
        /,
    ) -> None:
        self.durations.append(metric)


def material(label: bytes) -> bytes:
    """Return deterministic synthetic 32-byte material."""

    return hashlib.sha256(label).digest()


def fixture_profile_and_pack() -> tuple[
    FixtureStubProfile,
    scoring.LoadedScorePack,
]:
    """Load the pinned tracked A5 fixture through its public loader."""

    profile = FixtureStubProfile()
    pack = load_score_pack(SCORE_PACK_ROOT, SCORE_PACK_PATH, profile.score_pack_pin())
    return profile, pack


def execution_environment(
    *,
    backend_profile_id: str = DEFAULT_BACKEND_PROFILE,
    container_digest: str = DEFAULT_CONTAINER_DIGEST,
) -> ExecutionEnvironmentPin:
    """Build one exact safe environment identity, not runtime configuration."""

    return ExecutionEnvironmentPin(backend_profile_id, container_digest)


def submission_limits() -> SubmissionResourceLimits:
    """Build bounded synthetic A7 resource limits."""

    return SubmissionResourceLimits(
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
    )


def fixture_registry(root: Path) -> ChallengeRegistry:
    """Create one conspicuous fixture-only exact-version A3 registry."""

    registry_root = root / "registry"
    artifact_root = root / "artifacts"
    registry_root.mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    registry = ChallengeRegistry(registry_root, artifact_root)
    artifact_id = "a12_fixture_evidence"
    artifact_path = "a5_fixture/fixture-1.0/evidence.bin"
    artifact = artifact_root.joinpath(*artifact_path.split("/"))
    artifact.parent.mkdir(parents=True)
    payload = b"A12 conspicuous synthetic fixture evidence\n"
    artifact.write_bytes(payload)
    digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    slots = {
        slot: QualificationEvidence(
            state=state,
            artifact_id=artifact_id,
            reference="a12-synthetic-fixture-reference",
        )
        for slot, state in REQUIRED_QUALIFICATION_STATES
    }
    registry.save(
        ChallengeRecord(
            challenge_id="a5_fixture",
            version="fixture-1.0",
            fixture_origin=True,
            status="fixture",
            allowed_backbones=("fno",),
            artifacts={artifact_id: ArtifactBinding(path=artifact_path, digest=digest)},
            qualification=QualificationManifest(
                challenge_id="a5_fixture",
                challenge_version="fixture-1.0",
                mode="fixture",
                slots=slots,
            ),
        )
    )
    return registry


def fixture_submission_service(
    root: Path,
    *,
    max_attempts: int = 2,
    environment: ExecutionEnvironmentPin | None = None,
) -> tuple[ChallengeRegistry, SubmissionService]:
    """Compose the public A3/A7 fixture admission boundary."""

    registry = fixture_registry(root)
    service = submission_service_for_registry(
        registry,
        max_attempts=max_attempts,
        environment=environment,
    )
    return registry, service


def submission_service_for_registry(
    registry: ChallengeRegistry,
    *,
    max_attempts: int = 2,
    environment: ExecutionEnvironmentPin | None = None,
) -> SubmissionService:
    """Compose A7 against one caller-supplied exact A3 registry."""

    selected_environment = environment or execution_environment()
    profile = FixtureStubProfile()
    service = SubmissionService(
        resource_limits=submission_limits(),
        registry=registry,
        fixture_policy=FixtureSubmissionPolicy(
            fee_policy_key=FeePolicyKey("a12-fixture-fee-policy-v1"),
            amount_minor=1703,
            max_attempts=max_attempts,
            generator_version=profile.generator_version_required,
            generator_digest=profile.generator_digest_required,
            scoring_version=profile.scoring_version,
            scoring_digest=profile.scoring_digest,
            environment_pin=selected_environment,
        ),
    )
    return service


def start_fixture_submission(
    service: SubmissionService,
) -> tuple[SubmissionId, RequesterIdentity, FixtureExecutionEnvelope]:
    """Run the public A7 submit-to-start fixture lifecycle."""

    requester = RequesterIdentity("a12-fixture-requester-v1")
    submission_id = service.submit(
        requester,
        FixtureStubProfile().challenge_key,
        {
            "schema_version": "1.0",
            "challenge_id": "a5_fixture",
            "backbone": "fno",
            "parameters": {"fixture_note": "synthetic_non_scientific"},
        },
    )
    service.mark_validated(submission_id, requester)
    service.admit_fixture(submission_id, requester)
    started = service.start_fixture_attempt(
        submission_id,
        requester,
        FeeOperationKey("a12-fixture-charge-v1"),
        FeeOperationKey("a12-fixture-refund-v1"),
    )
    assert type(started.envelope) is FixtureExecutionEnvelope
    return submission_id, requester, started.envelope


def runtime_policy(
    environment: ExecutionEnvironmentPin,
    *,
    retry_class: InfrastructureRetryClass = InfrastructureRetryClass.RETRYABLE,
) -> FixtureRuntimePolicy:
    """Build one complete injected A8 fixture classification policy."""

    return FixtureRuntimePolicy(
        backend_profile_id=environment.backend_profile_id,
        container_digest=environment.container_digest,
        cause_retry_classes=tuple(
            (cause, retry_class) for cause in InfrastructureCause
        ),
    )


def fixture_train_eval_service(
    *,
    entropy: bytes,
    environment: ExecutionEnvironmentPin | None = None,
    retry_class: InfrastructureRetryClass = InfrastructureRetryClass.RETRYABLE,
) -> tuple[FixtureRuntimePolicy, FixtureTrainEvalService]:
    """Compose one fresh exact A8 fixture graph through its service boundary."""

    selected_environment = environment or execution_environment()
    profile, pack = fixture_profile_and_pack()
    policy = runtime_policy(selected_environment, retry_class=retry_class)
    service = FixtureTrainEvalService(
        profile=profile,
        provider=DeterministicFixtureProvider(FixtureOfficialEntropy(entropy)),
        score_pack=pack,
        policy=policy,
        declared_environment=selected_environment,
        backend=FixtureStubBackend(
            backend_profile_id=selected_environment.backend_profile_id,
            container_digest=selected_environment.container_digest,
        ),
    )
    return policy, service


def mcp_limits() -> mcp.McpResourceLimits:
    """Build bounded synthetic A9 request and response limits."""

    return mcp.McpResourceLimits(
        max_call_fields=16,
        max_total_request_value_nodes=10_000,
        max_request_object_members=256,
        max_request_list_items=256,
        max_request_string_utf8_bytes=4096,
        max_request_object_key_utf8_bytes=512,
        max_request_integer_bits=4096,
        max_total_request_utf8_bytes=1_000_000,
        max_total_response_value_nodes=10_000,
        max_response_sequence_items=256,
        max_response_string_utf8_bytes=4096,
        max_response_integer_bits=4096,
        max_total_response_utf8_bytes=1_000_000,
        max_concurrent_calls=8,
    )


def mcp_service(
    registry: ChallengeRegistry,
    submission_service: SubmissionService,
) -> mcp.McpService:
    """Compose A9 with no optional prior/scaffold/estimate provider."""

    return mcp.McpService(
        registry,
        submission_service,
        mcp_limits(),
        SyntheticQueryBudgetGate(),
        None,
        None,
        None,
    )


def fixture_leaderboard_page(
    card: EvaluationCard,
    submission_id: SubmissionId,
    *,
    with_cursor: bool = False,
) -> leaderboard.FixtureLeaderboardPage:
    """Project one public A6 card through the public A10 service."""

    assert card.overall_score is not None
    challenge_key = FixtureStubProfile().challenge_key
    candidate = leaderboard.FixtureLeaderboardCandidate(
        submission_id,
        card.result_id,
        challenge_key,
        card.scoring_pack_hash,
        ScoreStatus(card.status),
        card.overall_score,
        all(gate.passed for gate in card.gate_results),
        card.fixture_origin,
        card.eligible_for_emission,
        leaderboard.PublicationSequence(1),
    )
    candidates = [candidate]
    if with_cursor:
        candidates.append(
            leaderboard.FixtureLeaderboardCandidate(
                SubmissionId(LEADERBOARD_HIDDEN_SUBMISSION_ID),
                LEADERBOARD_HIDDEN_RESULT_ID,
                challenge_key,
                card.scoring_pack_hash,
                ScoreStatus.SCORED,
                card.overall_score,
                True,
                True,
                False,
                leaderboard.PublicationSequence(2),
            )
        )
    snapshot = leaderboard.FixtureLeaderboardCandidateSnapshot(
        challenge_key,
        card.scoring_pack_hash,
        leaderboard.LeaderboardSnapshotSequence(1),
        tuple(candidates),
    )
    service = leaderboard.FixtureLeaderboardService(
        SyntheticLeaderboardProvider(snapshot),
        leaderboard.FixtureLeaderboardResourceLimits(
            max_page_size=16,
            max_snapshot_rows=16,
            max_cursor_utf8_bytes=4096,
            max_string_utf8_bytes=4096,
            max_response_utf8_bytes=65536,
            max_concurrent_calls=2,
        ),
    )
    return service.list_entries(
        leaderboard.ListFixtureLeaderboardRequest(
            challenge_key,
            1 if with_cursor else 10,
            None,
        )
    )


def observability_snapshots(
    submission_id: SubmissionId,
) -> tuple[
    observability.SubmissionEventSnapshot,
    observability.CounterMetricSnapshot,
    observability.DurationMetricSnapshot,
]:
    """Project one event and two metrics through the public A11 service."""

    event_sink = RecordingEventSink()
    metric_sink = RecordingMetricSink()
    service = observability.ObservabilityService(
        event_sink,
        metric_sink,
        observability.ObservabilityResourceLimits(2),
    )
    service.emit_event(
        observability.ObservabilityEvent(
            observability.EventKind.SCORE,
            submission_id,
            SubmissionState.SCORED,
            ScoreStatus.SCORED,
        )
    )
    service.increment_counter(observability.MetricKind.SCORE_COUNT)
    service.observe_duration(observability.DurationStage.SCORE, 17)
    assert len(event_sink.events) == 1
    assert len(metric_sink.counters) == 1
    assert len(metric_sink.durations) == 1
    event = event_sink.events[0]
    assert type(event) is observability.SubmissionEventSnapshot
    return event, metric_sink.counters[0], metric_sink.durations[0]
