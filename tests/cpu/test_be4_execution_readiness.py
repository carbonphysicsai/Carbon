"""Focused B-E4 deterministic-driver, plan, meter, and calibration tests."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest
from test_b07g_research_service import _service_fixture as research_service_fixture
from test_be4_execution_integration import (
    _extended_resource_fixture,
    _official_graph,
    _published_prior,
    _research_graph,
)
from test_mcp_skeleton import REQUESTER
from test_mcp_skeleton import _service as official_service

from carbon.construction import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    ParameterCatalogRef,
)
from carbon.gauntlet.agents import (
    REGISTERED_EFFECTFUL_SURFACES,
    CommonArmRng,
    DataOnlyStrategyProposal,
    FixtureAgentDriver,
    ProposalDirection,
    ProposalHint,
    fixture_agent_drivers,
    fixture_strategy_domain,
)
from carbon.gauntlet.execution import (
    CALIBRATION_AUTHORITY_CEILING,
    FIXTURE_RESOURCE_DIMENSION_ID,
    FIXTURE_RESOURCE_UNIT,
    OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING,
    PREFLIGHT_AUTHORITY_CEILING,
    PROPOSED_PRIMARY_BLOCKS_PER_PROFILE,
    PROPOSED_RESERVE_BLOCKS_PER_PROFILE,
    CalibrationRunObservation,
    FrozenArmArtifact,
    PreparedCandidate,
    PreparedFixturePreflight,
    ProposedBlockSchedule,
    arm_hint_artifact_digest,
    build_nonqualifying_four_arm_block,
    build_nonqualifying_preflight_arm_artifacts,
    prepare_nonqualifying_run,
    summarize_nonqualifying_calibration,
    validate_fixture_resource_inspection,
)
from carbon.gauntlet.harness import AgentSession, GauntletPreflightError
from carbon.gauntlet.meter import (
    METER_POLICY_DIGEST,
    NormalizedComputeReceipt,
    PolicyWorkBudgetExceeded,
    PolicyWorkKind,
    PolicyWorkMeter,
    WallTimeObservation,
)
from carbon.gauntlet.model import AgentProfile, ExperimentalArm, MatchedBudget
from carbon.mcp import McpCall, McpField, SubmissionResult, SubmitReceipt
from carbon.registry import ChallengeKey
from carbon.research import (
    RESEARCH_NAMESPACE,
    GetChallengeInfoRequest,
    MockScaffoldRef,
    PracticePackRef,
    PriorChannel,
    PriorPackRef,
    ReplyStatus,
    ResourceObservation,
    ServiceCall,
)
from carbon.research import (
    TestOnlyPriorAuthorizationReceiptRef as AuthorizationReceiptRef,
)

DIGEST = "sha256:" + "a" * 64


def _catalog_ref(key: ChallengeKey) -> ParameterCatalogRef:
    return ParameterCatalogRef(
        key,
        "be4_fixture_catalog",
        "2.0",
        "1.0",
        CONSTRUCTION_CANONICALIZATION_PROFILE,
        "sha256:" + "b" * 64,
    )


def _strategy(key: ChallengeKey) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "challenge_id": key.challenge_id,
        "backbone": "fno",
        "parameters": {surface: 1 for surface in REGISTERED_EFFECTFUL_SURFACES},
    }


def _artifacts(
    pack: PriorPackRef,
) -> tuple[FrozenArmArtifact, ...]:
    return build_nonqualifying_preflight_arm_artifacts(pack)


def test_preflight_arm_artifact_factory_is_exact_test_only_and_nonqualifying() -> None:
    key = ChallengeKey("be4_fixture", "1.0")
    pack = PriorPackRef(key, PriorChannel.TEST_ONLY_FIXTURE, 1, DIGEST)
    artifacts = build_nonqualifying_preflight_arm_artifacts(pack)

    assert tuple(item.arm for item in artifacts) == tuple(ExperimentalArm)
    assert tuple(item.artifact_id for item in artifacts) == (
        "no_prior",
        "generic_prior",
        "v1_projection",
        "v2_test_only_prior",
    )
    assert artifacts[0].proposal_hints == ()
    assert artifacts[1].proposal_hints[0].surface_id == "fixture_sampling_level"
    assert artifacts[1].proposal_hints[0].direction is ProposalDirection.INCREASE
    assert artifacts[2].proposal_hints[0].surface_id == ("fixture_curriculum_emphasis")
    assert artifacts[2].source_prior_pack_ref == pack
    assert artifacts[3].content_digest == pack.content_hash
    assert artifacts[3].source_prior_pack_ref == pack

    public = PriorPackRef(key, PriorChannel.PUBLIC, 1, DIGEST)
    with pytest.raises(ValueError, match="TEST_ONLY_FIXTURE"):
        build_nonqualifying_preflight_arm_artifacts(public)
    with pytest.raises(TypeError, match="exact PriorPackRef"):
        build_nonqualifying_preflight_arm_artifacts(object())  # type: ignore[arg-type]

    hostile = PriorPackRef(key, PriorChannel.TEST_ONLY_FIXTURE, 1, DIGEST)
    object.__setattr__(hostile, "channel", "TEST_ONLY_FIXTURE")
    with pytest.raises(ValueError, match="structurally invalid"):
        build_nonqualifying_preflight_arm_artifacts(hostile)


def test_closed_meter_is_replayable_and_separate_from_wall_and_fixture_units() -> None:
    meter = PolicyWorkMeter()
    meter.record(PolicyWorkKind.ATTEMPT, 2)
    meter.record(PolicyWorkKind.SERVICE_OPERATION)
    receipt = meter.snapshot()
    assert receipt.policy_digest == METER_POLICY_DIGEST
    assert receipt.total_work_units == 3
    assert tuple(item.kind for item in receipt.counts) == tuple(PolicyWorkKind)
    assert not hasattr(receipt, "elapsed_seconds")
    assert not hasattr(receipt, "fixture_resource_observations")
    with pytest.raises(TypeError):
        meter.record("ATTEMPT")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        NormalizedComputeReceipt(
            receipt.schema_version,
            receipt.policy_id,
            receipt.policy_digest,
            receipt.counts,
            4,
        )
    assert receipt.content_digest == receipt.content_digest


def test_meter_rejects_work_before_crossing_its_immutable_ceiling() -> None:
    meter = PolicyWorkMeter()
    meter.bind_ceiling(1)
    meter.record(PolicyWorkKind.ATTEMPT)
    with pytest.raises(PolicyWorkBudgetExceeded, match="ceiling"):
        meter.record(PolicyWorkKind.SERVICE_OPERATION)
    assert meter.snapshot().total_work_units == 1
    assert meter.bound_ceiling == 1
    with pytest.raises(ValueError, match="before preflight work"):
        meter.bind_ceiling(1)


def test_common_rng_and_five_fixed_profiles_are_deterministic_and_data_only() -> None:
    key = ChallengeKey("be4_fixture", "1.0")
    domain = fixture_strategy_domain(_catalog_ref(key))
    design = "sha256:" + "c" * 64
    first_rng_meter = PolicyWorkMeter()
    second_rng_meter = PolicyWorkMeter()
    assert CommonArmRng(design, AgentProfile.EVOLUTIONARY, "block-1").draw_uint64(
        "candidate_order", 0, first_rng_meter
    ) == CommonArmRng(design, AgentProfile.EVOLUTIONARY, "block-1").draw_uint64(
        "candidate_order", 0, second_rng_meter
    )
    assert (
        CommonArmRng(design, AgentProfile.EVOLUTIONARY, "block-1", 0).stream_digest
        != CommonArmRng(design, AgentProfile.EVOLUTIONARY, "block-1", 1).stream_digest
    )

    drivers = fixture_agent_drivers()
    assert tuple(item.profile for item in drivers) == tuple(AgentProfile)
    for driver in drivers:
        meter = PolicyWorkMeter()
        batch = driver.propose(
            challenge_key=key,
            scaffold_strategy=_strategy(key),
            strategy_domain=domain,
            hints=(),
            rng=CommonArmRng(design, driver.profile, "block-1"),
            meter=meter,
        )
        assert batch.proposals
        for proposal in batch.proposals:
            parameters = proposal.strategy["parameters"]
            assert type(parameters) is dict
            assert set(parameters) == set(REGISTERED_EFFECTFUL_SURFACES)
            assert set(parameters.values()).issubset({1, 2})
            assert sum(value == 2 for value in parameters.values()) == 1
        replay = driver.propose(
            challenge_key=key,
            scaffold_strategy=_strategy(key),
            strategy_domain=domain,
            hints=(),
            rng=CommonArmRng(design, driver.profile, "block-1"),
            meter=PolicyWorkMeter(),
        )
        assert replay.transcript_digest == batch.transcript_digest
    assert (
        len(
            FixtureAgentDriver(AgentProfile.MINIMALIST)
            .propose(
                challenge_key=key,
                scaffold_strategy=_strategy(key),
                strategy_domain=domain,
                hints=(),
                rng=CommonArmRng(design, AgentProfile.MINIMALIST, "block-1"),
                meter=PolicyWorkMeter(),
            )
            .proposals
        )
        == 1
    )


def test_driver_proposal_state_is_immutable_and_transcript_binds_full_content() -> None:
    key = ChallengeKey("be4_fixture", "1.0")
    design = "sha256:" + "c" * 64
    domain = fixture_strategy_domain(_catalog_ref(key))
    driver = FixtureAgentDriver(AgentProfile.PLANNER)
    batch = driver.propose(
        challenge_key=key,
        scaffold_strategy=_strategy(key),
        strategy_domain=domain,
        hints=(),
        rng=CommonArmRng(design, driver.profile, "immutable-block", 4),
        meter=PolicyWorkMeter(),
    )
    proposal = batch.proposals[0]

    with pytest.raises(AttributeError, match="immutable"):
        driver.profile = AgentProfile.EVOLUTIONARY  # type: ignore[misc]
    with pytest.raises(AttributeError, match="immutable"):
        del driver.ref
    with pytest.raises(AttributeError, match="immutable"):
        proposal.attempt = 8  # type: ignore[misc]
    with pytest.raises(AttributeError, match="immutable"):
        del proposal.surface_id

    with pytest.raises(ValueError, match="exact content"):
        replace(
            batch,
            driver_ref=replace(batch.driver_ref, driver_id="different_driver"),
        )
    with pytest.raises(ValueError, match="exact content"):
        replace(batch, rng_stream_digest="sha256:" + "e" * 64)

    different_strategy = _strategy(key)
    different_parameters = dict(different_strategy["parameters"])
    different_parameters[proposal.surface_id] = 2
    different_parameters[REGISTERED_EFFECTFUL_SURFACES[-1]] = 2
    different_strategy["parameters"] = different_parameters
    different_proposal = DataOnlyStrategyProposal(
        key,
        proposal.attempt,
        proposal.surface_id,
        different_strategy,
    )
    with pytest.raises(ValueError, match="exact content"):
        replace(
            batch,
            proposals=(different_proposal, *batch.proposals[1:]),
        )

    compromised_driver = FixtureAgentDriver(AgentProfile.PLANNER)
    object.__setattr__(
        compromised_driver,
        "_FixtureAgentDriver__profile",
        AgentProfile.EVOLUTIONARY,
    )
    with pytest.raises(ValueError, match="canonical profile"):
        compromised_driver.propose(
            challenge_key=key,
            scaffold_strategy=_strategy(key),
            strategy_domain=domain,
            hints=(),
            rng=CommonArmRng(design, AgentProfile.PLANNER, "immutable-block", 4),
            meter=PolicyWorkMeter(),
        )


def test_invalid_registered_scaffold_value_consumes_attempt_and_fails_closed() -> None:
    key = ChallengeKey("be4_fixture", "1.0")
    domain = fixture_strategy_domain(_catalog_ref(key))
    strategy = _strategy(key)
    parameters = dict(strategy["parameters"])
    parameters[REGISTERED_EFFECTFUL_SURFACES[0]] = "not-an-uint64"
    strategy["parameters"] = parameters
    meter = PolicyWorkMeter()

    with pytest.raises(ValueError, match="attempt 1 was consumed"):
        FixtureAgentDriver(AgentProfile.PLANNER).propose(
            challenge_key=key,
            scaffold_strategy=strategy,
            strategy_domain=domain,
            hints=(),
            rng=CommonArmRng(DIGEST, AgentProfile.PLANNER, "invalid-block", 7),
            meter=meter,
        )

    counts = {item.kind: item.count for item in meter.snapshot().counts}
    assert counts[PolicyWorkKind.ATTEMPT] == 1
    assert counts[PolicyWorkKind.CANDIDATE_PROPOSAL] == 0


def test_driver_source_has_no_execution_or_external_io_imports() -> None:
    source = Path("carbon/gauntlet/agents.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if type(node) in (ast.Import, ast.ImportFrom)
        for alias in node.names
    }
    assert imported.isdisjoint(
        {"asyncio", "http", "os", "pathlib", "requests", "socket", "subprocess"}
    )
    assert "eval(" not in source and "exec(" not in source


def test_agent_session_uses_exact_research_and_official_envelopes(tmp_path) -> None:
    fixture, research_service = research_service_fixture(tmp_path / "research")
    official, *_ = official_service(tmp_path / "official")
    meter = PolicyWorkMeter()
    session = AgentSession(research_service, official, REQUESTER, meter)
    reply = session.research_call(
        ServiceCall(
            RESEARCH_NAMESPACE,
            "get_challenge_info",
            GetChallengeInfoRequest(fixture.info.challenge_key),
        )
    )
    assert reply.status is ReplyStatus.OK
    assert session.binds_meter(meter)
    assert not hasattr(session, "research_service")
    assert not hasattr(session, "official_fixture_service")
    with pytest.raises(GauntletPreflightError):
        session.official_call(McpCall("1.0", "get_challenge_info", ()))

    result = session.official_call(
        McpCall(
            "1.0",
            "submit",
            (
                McpField("challenge_id", "a9_fixture"),
                McpField("challenge_version", "fixture-1.0"),
                McpField(
                    "strategy",
                    {
                        "schema_version": "1.0",
                        "challenge_id": "a9_fixture",
                        "backbone": "fno",
                        "parameters": {},
                    },
                ),
            ),
        )
    )
    assert type(result) is SubmitReceipt
    polled = session.official_call(
        McpCall(
            "1.0",
            "get_submission_result",
            (McpField("submission_id", result.status.submission_id.value),),
        )
    )
    assert type(polled) is SubmissionResult
    assert session.normalized_compute().total_work_units == 3


def test_four_arm_plan_freezes_common_structure_and_v2_pins_only() -> None:
    key = ChallengeKey("be4_fixture", "1.0")
    pack = PriorPackRef(key, PriorChannel.TEST_ONLY_FIXTURE, 1, DIGEST)
    authorization = AuthorizationReceiptRef(key, "be4_fixture_authorization", DIGEST)
    profile = AgentProfile.PLANNER
    block = build_nonqualifying_four_arm_block(
        design_digest="sha256:" + "d" * 64,
        block_id="primary-001",
        profile=profile,
        replicate=0,
        driver_ref=FixtureAgentDriver(profile).ref,
        artifacts=_artifacts(pack),
        budget=MatchedBudget(profile, 100.0, 1_000.0, 8),
        fixture_resource_ceiling=100,
        scaffold_ref=MockScaffoldRef(key, content_digest="sha256:" + "e" * 64),
        practice_pack_ref=PracticePackRef(key, content_digest="sha256:" + "f" * 64),
        v2_prior_pack_ref=pack,
        v2_authorization_ref=authorization,
    )
    assert block.qualifying_execution_ready is False
    assert len({item.rng_stream_digest for item in block.runs}) == 1
    assert all(
        (item.identity.prior_pack_ref is not None)
        is (item.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR)
        for item in block.runs
    )
    assert len({item.final_submission_slot_digest for item in block.runs}) == 4
    replay_replicate = build_nonqualifying_four_arm_block(
        design_digest="sha256:" + "d" * 64,
        block_id="primary-001",
        profile=profile,
        replicate=1,
        driver_ref=FixtureAgentDriver(profile).ref,
        artifacts=_artifacts(pack),
        budget=MatchedBudget(profile, 100.0, 1_000.0, 8),
        fixture_resource_ceiling=100,
        scaffold_ref=MockScaffoldRef(key, content_digest="sha256:" + "e" * 64),
        practice_pack_ref=PracticePackRef(key, content_digest="sha256:" + "f" * 64),
        v2_prior_pack_ref=pack,
        v2_authorization_ref=authorization,
    )
    assert block.runs[0].rng_stream_digest != replay_replicate.runs[0].rng_stream_digest
    assert (
        block.runs[0].final_submission_slot_digest
        != replay_replicate.runs[0].final_submission_slot_digest
    )
    with pytest.raises(ValueError, match="bindings do not agree"):
        replace(
            replay_replicate.runs[0],
            final_submission_slot_digest=block.runs[0].final_submission_slot_digest,
        )
    alternate_pack = PriorPackRef(
        key, PriorChannel.TEST_ONLY_FIXTURE, 2, "sha256:" + "1" * 64
    )
    wrong_artifacts = list(_artifacts(pack))
    wrong_v1 = wrong_artifacts[2]
    wrong_artifacts[2] = replace(
        wrong_v1,
        source_prior_pack_ref=alternate_pack,
        content_digest=arm_hint_artifact_digest(
            arm=wrong_v1.arm,
            artifact_id=wrong_v1.artifact_id,
            artifact_version=wrong_v1.artifact_version,
            proposal_hints=wrong_v1.proposal_hints,
            source_prior_pack_ref=alternate_pack,
        ),
    )
    with pytest.raises(ValueError, match="registered preflight artifacts"):
        build_nonqualifying_four_arm_block(
            design_digest="sha256:" + "d" * 64,
            block_id="primary-001",
            profile=profile,
            replicate=0,
            driver_ref=FixtureAgentDriver(profile).ref,
            artifacts=tuple(wrong_artifacts),
            budget=MatchedBudget(profile, 100.0, 1_000.0, 8),
            fixture_resource_ceiling=100,
            scaffold_ref=MockScaffoldRef(key, content_digest="sha256:" + "e" * 64),
            practice_pack_ref=PracticePackRef(key, content_digest="sha256:" + "f" * 64),
            v2_prior_pack_ref=pack,
            v2_authorization_ref=authorization,
        )
    generic = block.runs[1].arm_artifact
    altered_hints = (
        ProposalHint("fixture_feature_degree", ProposalDirection.DECREASE),
    )
    altered_generic = replace(
        generic,
        proposal_hints=altered_hints,
        content_digest=arm_hint_artifact_digest(
            arm=generic.arm,
            artifact_id=generic.artifact_id,
            artifact_version=generic.artifact_version,
            proposal_hints=altered_hints,
        ),
    )
    with pytest.raises(ValueError, match="registered preflight artifacts"):
        build_nonqualifying_four_arm_block(
            design_digest="sha256:" + "d" * 64,
            block_id="primary-001",
            profile=profile,
            replicate=0,
            driver_ref=FixtureAgentDriver(profile).ref,
            artifacts=(
                block.runs[0].arm_artifact,
                altered_generic,
                block.runs[2].arm_artifact,
                block.runs[3].arm_artifact,
            ),
            budget=MatchedBudget(profile, 100.0, 1_000.0, 8),
            fixture_resource_ceiling=100,
            scaffold_ref=MockScaffoldRef(key, content_digest="sha256:" + "e" * 64),
            practice_pack_ref=PracticePackRef(key, content_digest="sha256:" + "f" * 64),
            v2_prior_pack_ref=pack,
            v2_authorization_ref=authorization,
        )
    renamed_v2 = replace(
        block.runs[3].arm_artifact,
        artifact_id="different_v2_identity",
        artifact_version="99.0",
    )
    with pytest.raises(ValueError, match="bindings do not agree"):
        replace(block.runs[3], arm_artifact=renamed_v2)
    with pytest.raises(ValueError, match="registered preflight artifacts"):
        build_nonqualifying_four_arm_block(
            design_digest="sha256:" + "d" * 64,
            block_id="primary-001",
            profile=profile,
            replicate=0,
            driver_ref=FixtureAgentDriver(profile).ref,
            artifacts=(
                block.runs[0].arm_artifact,
                block.runs[1].arm_artifact,
                block.runs[2].arm_artifact,
                renamed_v2,
            ),
            budget=MatchedBudget(profile, 100.0, 1_000.0, 8),
            fixture_resource_ceiling=100,
            scaffold_ref=MockScaffoldRef(key, content_digest="sha256:" + "e" * 64),
            practice_pack_ref=PracticePackRef(key, content_digest="sha256:" + "f" * 64),
            v2_prior_pack_ref=pack,
            v2_authorization_ref=authorization,
        )

    sequence_pack = PriorPackRef(key, PriorChannel.TEST_ONLY_FIXTURE, 2, DIGEST)
    sequence_block = build_nonqualifying_four_arm_block(
        design_digest="sha256:" + "d" * 64,
        block_id="primary-001",
        profile=profile,
        replicate=0,
        driver_ref=FixtureAgentDriver(profile).ref,
        artifacts=_artifacts(sequence_pack),
        budget=MatchedBudget(profile, 100.0, 1_000.0, 8),
        fixture_resource_ceiling=100,
        scaffold_ref=MockScaffoldRef(key, content_digest="sha256:" + "e" * 64),
        practice_pack_ref=PracticePackRef(key, content_digest="sha256:" + "f" * 64),
        v2_prior_pack_ref=sequence_pack,
        v2_authorization_ref=authorization,
    )
    assert sequence_block.runs[2].final_submission_slot_digest != (
        block.runs[2].final_submission_slot_digest
    )
    assert sequence_block.runs[3].final_submission_slot_digest != (
        block.runs[3].final_submission_slot_digest
    )

    other_authorization = AuthorizationReceiptRef(
        key, "other_fixture_authorization", DIGEST
    )
    authorization_block = build_nonqualifying_four_arm_block(
        design_digest="sha256:" + "d" * 64,
        block_id="primary-001",
        profile=profile,
        replicate=0,
        driver_ref=FixtureAgentDriver(profile).ref,
        artifacts=_artifacts(pack),
        budget=MatchedBudget(profile, 100.0, 1_000.0, 8),
        fixture_resource_ceiling=100,
        scaffold_ref=MockScaffoldRef(key, content_digest="sha256:" + "e" * 64),
        practice_pack_ref=PracticePackRef(key, content_digest="sha256:" + "f" * 64),
        v2_prior_pack_ref=pack,
        v2_authorization_ref=other_authorization,
    )
    assert authorization_block.runs[3].final_submission_slot_digest != (
        block.runs[3].final_submission_slot_digest
    )

    other_key = ChallengeKey("be4_fixture_other", "1.0")
    other_pack = PriorPackRef(other_key, PriorChannel.TEST_ONLY_FIXTURE, 1, DIGEST)
    other_challenge_block = build_nonqualifying_four_arm_block(
        design_digest="sha256:" + "d" * 64,
        block_id="primary-001",
        profile=profile,
        replicate=0,
        driver_ref=FixtureAgentDriver(profile).ref,
        artifacts=_artifacts(other_pack),
        budget=MatchedBudget(profile, 100.0, 1_000.0, 8),
        fixture_resource_ceiling=100,
        scaffold_ref=MockScaffoldRef(other_key, content_digest="sha256:" + "e" * 64),
        practice_pack_ref=PracticePackRef(
            other_key, content_digest="sha256:" + "f" * 64
        ),
        v2_prior_pack_ref=other_pack,
        v2_authorization_ref=AuthorizationReceiptRef(
            other_key, "be4_fixture_authorization", DIGEST
        ),
    )
    assert tuple(
        item.final_submission_slot_digest for item in other_challenge_block.runs
    ) != tuple(item.final_submission_slot_digest for item in block.runs)

    hostile_budget = MatchedBudget(profile, 100.0, 1_000.0, 8)
    object.__setattr__(hostile_budget, "attempt_limit", -1)
    with pytest.raises(ValueError, match="invalid nested values"):
        build_nonqualifying_four_arm_block(
            design_digest="sha256:" + "d" * 64,
            block_id="primary-001",
            profile=profile,
            replicate=0,
            driver_ref=FixtureAgentDriver(profile).ref,
            artifacts=_artifacts(pack),
            budget=hostile_budget,
            fixture_resource_ceiling=100,
            scaffold_ref=MockScaffoldRef(key, content_digest="sha256:" + "e" * 64),
            practice_pack_ref=PracticePackRef(key, content_digest="sha256:" + "f" * 64),
            v2_prior_pack_ref=pack,
            v2_authorization_ref=authorization,
        )
    schedule = ProposedBlockSchedule()
    assert schedule.primary_blocks_per_profile == PROPOSED_PRIMARY_BLOCKS_PER_PROFILE
    assert schedule.reserve_blocks_per_profile == PROPOSED_RESERVE_BLOCKS_PER_PROFILE
    assert schedule.attempts_per_profile == 688
    assert schedule.qualifying_execution_ready is False


def test_preflight_binds_catalog_replies_results_compute_and_resource_unit(
    tmp_path: Path,
) -> None:
    domain = _extended_resource_fixture(tmp_path / "domain")
    store, prior_provider, lookup = _published_prior(tmp_path / "prior", domain)
    research_service, scaffold_ref, practice_pack_ref = _research_graph(
        tmp_path / "research", domain, store, prior_provider, lookup
    )
    official, *_ = _official_graph(tmp_path / "official", domain)
    catalog_ref = domain.compile_fixture.catalog.to_ref(
        candidate_assembly=domain.compile_fixture.assembly
    )
    strategy_domain = fixture_strategy_domain(catalog_ref)
    driver = FixtureAgentDriver(AgentProfile.PLANNER)

    def plan_with_ceiling(ceiling: int):
        return build_nonqualifying_four_arm_block(
            design_digest="sha256:" + "7" * 64,
            block_id=f"preflight-{ceiling}",
            profile=driver.profile,
            replicate=3,
            driver_ref=driver.ref,
            artifacts=build_nonqualifying_preflight_arm_artifacts(
                lookup.prior_pack_ref
            ),
            budget=MatchedBudget(driver.profile, 30.0, 1_000.0, 8),
            fixture_resource_ceiling=ceiling,
            scaffold_ref=scaffold_ref,
            practice_pack_ref=practice_pack_ref,
            v2_prior_pack_ref=lookup.prior_pack_ref,
            v2_authorization_ref=lookup.authorization.receipt_ref,
        ).runs[0]

    plan = plan_with_ceiling(15)
    wrong_catalog = replace(catalog_ref, content_digest="sha256:" + "6" * 64)
    wrong_meter = PolicyWorkMeter()
    with pytest.raises(
        ValueError,
        match="fixture strategy domain does not equal the current B-02B owners",
    ):
        prepare_nonqualifying_run(
            session=AgentSession(research_service, official, REQUESTER, wrong_meter),
            plan=plan,
            driver=driver,
            strategy_domain=fixture_strategy_domain(wrong_catalog),
            parameter_catalog=domain.compile_fixture.catalog,
            candidate_assembly=domain.compile_fixture.assembly,
            meter=wrong_meter,
        )
    assert wrong_meter.snapshot().total_work_units == 0

    hostile_budget_plan = plan_with_ceiling(15)
    object.__setattr__(hostile_budget_plan.budget, "attempt_limit", 1)
    hostile_budget_meter = PolicyWorkMeter()
    with pytest.raises(ValueError, match="structurally invalid"):
        prepare_nonqualifying_run(
            session=AgentSession(
                research_service, official, REQUESTER, hostile_budget_meter
            ),
            plan=hostile_budget_plan,
            driver=driver,
            strategy_domain=strategy_domain,
            parameter_catalog=domain.compile_fixture.catalog,
            candidate_assembly=domain.compile_fixture.assembly,
            meter=hostile_budget_meter,
        )
    assert hostile_budget_meter.snapshot().total_work_units == 0
    assert hostile_budget_meter.bound_ceiling is None

    hostile_domain = fixture_strategy_domain(catalog_ref)
    object.__setattr__(hostile_domain.surfaces[0], "maximum", 3)
    hostile_domain_meter = PolicyWorkMeter()
    with pytest.raises(ValueError, match="current B-02B owners"):
        prepare_nonqualifying_run(
            session=AgentSession(
                research_service, official, REQUESTER, hostile_domain_meter
            ),
            plan=plan,
            driver=driver,
            strategy_domain=hostile_domain,
            parameter_catalog=domain.compile_fixture.catalog,
            candidate_assembly=domain.compile_fixture.assembly,
            meter=hostile_domain_meter,
        )
    assert hostile_domain_meter.snapshot().total_work_units == 0
    assert hostile_domain_meter.bound_ceiling is None

    meter = PolicyWorkMeter()
    prepared = prepare_nonqualifying_run(
        session=AgentSession(research_service, official, REQUESTER, meter),
        plan=plan,
        driver=driver,
        strategy_domain=strategy_domain,
        parameter_catalog=domain.compile_fixture.catalog,
        candidate_assembly=domain.compile_fixture.assembly,
        meter=meter,
    )
    assert prepared.preflight_only is True
    assert prepared.first_preflight_executable_attempt == prepared.selected_attempt == 1
    assert prepared.preflight_compute == meter.snapshot()
    assert prepared.preflight_compute.content_digest.startswith("sha256:")
    assert len(prepared.service_reply_digests) == 12
    with pytest.raises(ValueError, match="transcript digest"):
        replace(prepared, transcript_digest=DIGEST)

    candidate = prepared.candidates[0]
    detached_proposal = DataOnlyStrategyProposal(
        candidate.proposal.challenge_key,
        candidate.proposal.attempt,
        candidate.proposal.surface_id,
        candidate.proposal.strategy,
    )
    assert detached_proposal is not candidate.proposal
    assert detached_proposal.strategy_digest == candidate.proposal.strategy_digest
    detached_candidate = replace(candidate, proposal=detached_proposal)
    with pytest.raises(TypeError, match="proposal batch"):
        replace(
            prepared,
            candidates=(detached_candidate, *prepared.candidates[1:]),
        )

    with pytest.raises(TypeError, match="private preflight factory"):
        PreparedCandidate(
            candidate.proposal,
            candidate.validation,
            candidate.compilation,
            candidate.resource_inspection,
            _factory_token=object(),
        )
    with pytest.raises(TypeError, match="private preparation factory"):
        PreparedFixturePreflight(
            prepared.authority_ceiling,
            prepared.plan,
            prepared.challenge_info,
            prepared.interaction_manifest,
            prepared.prior_lookup,
            prepared.scaffold,
            prepared.proposal_batch,
            prepared.candidates,
            prepared.first_preflight_executable_attempt,
            prepared.strategy_domain_digest,
            prepared.service_reply_digests,
            prepared.preflight_compute,
            prepared.transcript_digest,
            _factory_token=object(),
        )

    first_inspection = prepared.candidates[0].resource_inspection
    assert first_inspection is not None
    wrong_line = replace(first_inspection.line_items[0], unit="abstract_units:wrong")
    with pytest.raises(ValueError, match="exact admissible static unit"):
        validate_fixture_resource_inspection(
            replace(first_inspection, line_items=(wrong_line,)), ceiling=15
        )
    # B-07S ResourceLineItem carries the B-07E static dimension and unit as
    # one exact ``<dimension_id>:<unit_object_id>`` label.  Preserve the unit
    # object id while changing only the encoded dimension id.
    wrong_dimension = replace(
        first_inspection.line_items[0],
        unit="unrelated_resource_dimension:fixture_abstract_count",
    )
    with pytest.raises(ValueError, match="exact admissible static unit"):
        validate_fixture_resource_inspection(
            replace(first_inspection, line_items=(wrong_dimension,)), ceiling=15
        )

    low_meter = PolicyWorkMeter()
    with pytest.raises(ValueError, match="plan ceiling"):
        prepare_nonqualifying_run(
            session=AgentSession(research_service, official, REQUESTER, low_meter),
            plan=plan_with_ceiling(10),
            driver=driver,
            strategy_domain=strategy_domain,
            parameter_catalog=domain.compile_fixture.catalog,
            candidate_assembly=domain.compile_fixture.assembly,
            meter=low_meter,
        )

    object.__setattr__(driver.ref, "policy_digest", "sha256:" + "5" * 64)
    drift_meter = PolicyWorkMeter()
    with pytest.raises(ValueError, match="current canonical profile"):
        prepare_nonqualifying_run(
            session=AgentSession(research_service, official, REQUESTER, drift_meter),
            plan=plan,
            driver=driver,
            strategy_domain=strategy_domain,
            parameter_catalog=domain.compile_fixture.catalog,
            candidate_assembly=domain.compile_fixture.assembly,
            meter=drift_meter,
        )
    assert drift_meter.snapshot().total_work_units == 0
    assert drift_meter.bound_ceiling is None


def _calibration_observations(*, failed: bool) -> tuple[CalibrationRunObservation, ...]:
    observations = []
    for profile in AgentProfile:
        for block_index in range(4):
            for arm in ExperimentalArm:
                meter = PolicyWorkMeter()
                meter.record(PolicyWorkKind.ATTEMPT, block_index + 1)
                observations.append(
                    CalibrationRunObservation(
                        profile,
                        arm,
                        f"calibration-{block_index + 1}",
                        meter.snapshot(),
                        WallTimeObservation(float(block_index + 1)),
                        (
                            ResourceObservation(
                                FIXTURE_RESOURCE_DIMENSION_ID,
                                2.0,
                                FIXTURE_RESOURCE_UNIT,
                            ),
                        ),
                        failed and profile is AgentProfile.PLANNER and block_index == 0,
                    )
                )
    return tuple(observations)


def test_calibration_is_nonqualifying_and_uses_five_percent_block_ceiling() -> None:
    design = "sha256:" + "9" * 64
    boundary = summarize_nonqualifying_calibration(
        design_digest=design, observations=_calibration_observations(failed=True)
    )
    assert boundary.authority_ceiling == CALIBRATION_AUTHORITY_CEILING
    assert boundary.complete_block_count == 20
    assert boundary.failed_block_count == 1
    assert boundary.block_infrastructure_failure_rate == 0.05
    assert boundary.block_infrastructure_failure_rate_ceiling == 0.05
    assert boundary.block_infrastructure_failure_rate_within_ceiling is True
    assert boundary.engineering_ready_for_owner_review is False
    assert boundary.practice_lifecycle_calibrated is False
    assert boundary.preflight_only is True
    assert boundary.qualifying_execution_ready is False
    assert all(item.sample_count == 4 for item in boundary.profiles)
    assert all(item.fixture_units_p99 == 2.0 for item in boundary.profiles)
    assert PREFLIGHT_AUTHORITY_CEILING != CALIBRATION_AUTHORITY_CEILING
    assert PREFLIGHT_AUTHORITY_CEILING != OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING


def test_calibration_reconstructs_nested_observations_before_use() -> None:
    meter = PolicyWorkMeter()
    receipt = meter.snapshot()
    object.__setattr__(receipt, "total_work_units", 999)
    with pytest.raises(ValueError, match="invalid nested values"):
        CalibrationRunObservation(
            AgentProfile.PLANNER,
            ExperimentalArm.NO_PRIOR,
            "hostile-calibration",
            receipt,
            WallTimeObservation(1.0),
            (
                ResourceObservation(
                    FIXTURE_RESOURCE_DIMENSION_ID,
                    2.0,
                    FIXTURE_RESOURCE_UNIT,
                ),
            ),
            False,
        )

    values = _calibration_observations(failed=False)
    object.__setattr__(values[0].compute, "total_work_units", 999)
    with pytest.raises(ValueError, match="structurally invalid observations"):
        summarize_nonqualifying_calibration(
            design_digest="sha256:" + "8" * 64, observations=values
        )


def test_calibration_rejects_duplicate_or_incomplete_four_arm_blocks() -> None:
    values = _calibration_observations(failed=False)
    with pytest.raises(ValueError, match="duplicated"):
        summarize_nonqualifying_calibration(
            design_digest="sha256:" + "8" * 64,
            observations=(*values, values[0]),
        )
    with pytest.raises(ValueError, match="complete four-arm"):
        summarize_nonqualifying_calibration(
            design_digest="sha256:" + "8" * 64, observations=values[:-1]
        )
    with pytest.raises(TypeError, match="calibration observation"):
        replace(
            values[0],
            fixture_resource_observations=(
                ResourceObservation("fixture_units", 2.0, "fixture_unit"),
            ),
        )
