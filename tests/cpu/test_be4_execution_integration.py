"""End-to-end integration evidence for the bounded B-E4 readiness graph."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from b02b_fixtures import CompileFixture, strategy_limits
from b02c_fixtures import ResourcePolicyFixture
from b07b_fixtures import Catalog, Compiler, Manifests
from b07c_fixtures import make_fixture as make_practice_fixture
from test_b07f_resolved_fixture_adapter import (
    BOOLEAN_KEYS,
    ENVIRONMENT_DIGEST,
    GENERATOR_DIGEST,
    MEASUREMENT_DIGEST,
    NUMERIC_KEYS,
    REFERENCE_DIGEST,
    _registry,
    _runtime_policy,
    _score_pack,
)
from test_b07g_research_service import _UnavailableAlignment
from test_be4_fixture_families import _prior_inputs
from test_mcp_skeleton import _Gate, _mcp_limits

from carbon import research
from carbon.construction.catalog import catalog_entries_by_surface
from carbon.construction.compiler import (
    SUPPORTED_COMPILER_IDENTITY,
    CompileAccepted,
    compile_strategy,
)
from carbon.evaluation.refs import FixtureReferenceAssetRef
from carbon.fees import (
    ExecutionEnvironmentPin,
    FeeOperationKey,
    FeePolicyKey,
    FixtureSubmissionPolicy,
    RequesterIdentity,
    SubmissionService,
    SubmissionState,
)
from carbon.gauntlet import execution as gauntlet_execution
from carbon.gauntlet.agents import (
    REGISTERED_EFFECTFUL_SURFACES,
    fixture_agent_drivers,
    fixture_strategy_domain,
)
from carbon.gauntlet.execution import (
    OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING,
    PREFLIGHT_AUTHORITY_CEILING,
    FrozenArmArtifact,
    OfficialFixtureSubmission,
    build_nonqualifying_four_arm_block,
    build_nonqualifying_preflight_arm_artifacts,
    prepare_nonqualifying_run,
    read_official_fixture_result,
    submit_prepared_fixture_run,
)
from carbon.gauntlet.fixture import (
    ThreeFamilyTestOnlyPackBuilder,
    extend_toy_parameter_catalog,
    fixture_executable_semantics,
)
from carbon.gauntlet.harness import AgentSession
from carbon.gauntlet.meter import PolicyWorkKind, PolicyWorkMeter
from carbon.gauntlet.model import AgentProfile, ExperimentalArm, MatchedBudget
from carbon.generators.refs import BurgersFixtureConfigurationRef
from carbon.mcp import McpService
from carbon.practice import InMemoryScaffoldProvider, RegisteredMockScaffold
from carbon.registry import ChallengeKey
from carbon.resource_policy.canonical import research_resource_policy_to_ref
from carbon.seeding import DeterministicFixtureProvider, FixtureOfficialEntropy
from carbon.traineval.resolved_fixture import (
    FixtureToyAsset,
    ResolvedFixtureCompletedRun,
    ResolvedPlanFixtureTrainEvalService,
)

_DESIGN_DIGEST = "sha256:" + "d" * 64
_REQUESTER = RequesterIdentity("be4-readiness-integration")
_FAMILIES = REGISTERED_EFFECTFUL_SURFACES


def _material(label: bytes) -> bytes:
    return hashlib.sha256(label).digest()


def _extended_resource_fixture(root: Path) -> ResourcePolicyFixture:
    practice = make_practice_fixture(root / "base")
    base = practice.domain
    source = base.compile_fixture
    sampling = catalog_entries_by_surface(source.catalog)[_FAMILIES[0]]
    curriculum_clause = replace(
        sampling.semantic_owner_binding.semantic_clause_ref,
        object_id="fixture_curriculum_clause",
        content_digest="sha256:" + "b" * 64,
    )
    curriculum_executable = replace(
        sampling.training_lever_binding.executable_semantics_ref,
        object_id="fixture_curriculum_executable",
        content_digest="sha256:" + "c" * 64,
    )
    feature_clause = replace(
        sampling.semantic_owner_binding.semantic_clause_ref,
        object_id="fixture_feature_clause",
        content_digest="sha256:" + "d" * 64,
    )
    feature_executable = replace(
        sampling.training_lever_binding.executable_semantics_ref,
        object_id="fixture_feature_executable",
        content_digest="sha256:" + "e" * 64,
    )
    catalog = extend_toy_parameter_catalog(
        base_catalog=source.catalog,
        candidate_assembly=source.assembly,
        curriculum_semantic_clause_ref=curriculum_clause,
        curriculum_executable_semantics_ref=curriculum_executable,
        feature_semantic_clause_ref=feature_clause,
        feature_executable_semantics_ref=feature_executable,
    )
    strategy = {
        **source.strategy,
        "parameters": {surface: 1 for surface in _FAMILIES},
    }
    compiled = compile_strategy(
        strategy,
        challenge_key=source.key,
        candidate_assembly=source.assembly,
        candidate_assembly_ref=source.assembly.to_ref(),
        parameter_catalog=catalog,
        parameter_catalog_ref=catalog.to_ref(candidate_assembly=source.assembly),
        authoring_origin=source.authoring_origin,
        authoring_artifacts=source.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )
    assert type(compiled) is CompileAccepted
    compile_fixture = CompileFixture(
        source.key,
        source.assembly,
        catalog,
        source.authoring_origin,
        source.authoring_artifacts,
        strategy,
    )
    binding = base.policy.class_bindings[0]
    policy = replace(
        base.policy,
        object_id="be4_fixture_resource_policy",
        object_version="2.0",
        parameter_catalog_ref=catalog.to_ref(candidate_assembly=source.assembly),
        class_bindings=(
            replace(
                binding,
                ceilings=tuple(
                    replace(item, maximum_quantity=15) for item in binding.ceilings
                ),
                supported_impact_tags=tuple(
                    sorted(
                        {
                            *binding.supported_impact_tags,
                            "curriculum_impact",
                            "feature_impact",
                        }
                    )
                ),
            ),
        ),
    )
    policy_ref = research_resource_policy_to_ref(policy, class_bundle=base.class_bundle)
    return ResourcePolicyFixture(
        compile_fixture,
        compiled,
        base.context,
        base.resource_class,
        base.resource_class_ref,
        policy,
        policy_ref,
    )


def _published_prior(root: Path, domain: ResourcePolicyFixture) -> tuple[
    research.PriorPackStore,
    research.StaticTestOnlyPriorProvider,
    research.PriorLookupResult,
]:
    source = domain.compile_fixture
    template, registry, estimand, aggregate = _prior_inputs(source, source.catalog)
    records = tuple(
        research.SyntheticPriorRecord(
            f"private_record_{index}_{polarity}",
            source.key,
            surface,
            estimand,
            f"private_lineage_{index}_{polarity}",
            f"private_cell_{index}_{polarity}",
            10,
            research.SyntheticFinding.MIXED,
            effect,
            True,
            True,
            private_canary=f"private_canary_{index}_{polarity}",
            public_context_id="fixture_context",
            public_backbone_id="fno",
            public_provenance_ref=aggregate,
        )
        for index, surface in enumerate(sorted(_FAMILIES))
        for polarity, effect in (("negative", -1.0), ("positive", 1.0))
    )
    store = research.PriorPackStore(root / "prior.sqlite", registry)
    store.initialize_disclosure_ledger("be4_fixture_disclosure")
    publisher = research.SyntheticPriorPublisher(
        store,
        ThreeFamilyTestOnlyPackBuilder(
            catalog=source.catalog,
            candidate_assembly=source.assembly,
            template_pack=template,
            template_pack_ref=research.prior_pack_ref(template),
        ),
        research.ExactHashFixtureAuthorizer("be4_fixture_authorization"),
        research.DeterministicTestOnlySigner("be4_fixture_key", b"fixture-secret"),
        research.FixturePublishingPolicy(1, 1, 1, 1, 10),
        ledger_key="be4_fixture_disclosure",
    )
    snapshot_ref = publisher.publish(
        research.SyntheticEvidenceSnapshot(source.key, "be4_fixture_snapshot", records),
        publication_sequence=0,
        activation_epoch=12,
        expires_at_micros=1_000,
        fixture_suite_id="be4_fixture_suite",
        expected_previous=None,
    )
    pack_ref = store.read_snapshot(snapshot_ref).active_prior_pack_ref
    assert pack_ref is not None
    provider = research.StaticTestOnlyPriorProvider.for_test_fixture(
        store, now_micros=lambda: 999
    )
    lookup = provider.get_prior(
        research.GetPriorRequest(source.key, research.ExactPriorSelector(pack_ref))
    )
    return store, provider, lookup


def _research_graph(
    root: Path,
    domain: ResourcePolicyFixture,
    store: research.PriorPackStore,
    prior_provider: research.StaticTestOnlyPriorProvider,
    prior_lookup: research.PriorLookupResult,
) -> tuple[
    research.LocalResearchService, research.MockScaffoldRef, research.PracticePackRef
]:
    fixture = make_practice_fixture(root / "practice")
    source = domain.compile_fixture
    info = replace(
        fixture.info,
        physical_system_ref=source.assembly.physical_system_ref,
        candidate_output_ref=source.assembly.candidate_output_ref,
        training_support_ref=source.assembly.training_support_ref,
    )
    manifest = replace(
        fixture.manifest,
        challenge_info_ref=info.to_ref(),
        physical_system_ref=info.physical_system_ref,
        candidate_output_ref=info.candidate_output_ref,
        training_support_ref=info.training_support_ref,
        candidate_assembly_ref=source.assembly.to_ref(),
        parameter_catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        resource_policy_ref=domain.policy_ref,
    )
    registrations = tuple(
        RegisteredMockScaffold(
            source.key,
            "2.0",
            info.training_support_ref,
            prior_ref,
            source.strategy,
        )
        for prior_ref in (None, prior_lookup.prior_pack_ref)
    )
    scaffold = InMemoryScaffoldProvider(registrations)
    scaffold_ref = registrations[0].resource().scaffold_ref
    assert registrations[1].resource().scaffold_ref == scaffold_ref
    compiler = research.B02BCompilationProvider(
        candidate_assembly=source.assembly,
        candidate_assembly_ref=source.assembly.to_ref(),
        parameter_catalog=source.catalog,
        parameter_catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        authoring_origin=source.authoring_origin,
        authoring_artifacts=source.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )
    inspection = research.StaticResourceInspectionProvider(
        compilation_resolver=Compiler(domain),
        expected_training_support_ref=source.assembly.training_support_ref,
        policy=domain.policy,
        policy_ref=domain.policy_ref,
        class_bundle=domain.class_bundle,
        selected_resource_class=domain.resource_class,
        selected_resource_class_ref=domain.resource_class_ref,
        authority_context=domain.context,
    )
    context = research.FixtureResearchContext(
        Catalog(info),
        Manifests(manifest),
        research.StaticPublicPriorProvider(store),
        prior_provider,
        store,
        scaffold,
        research.A2ValidationProvider(),
        compiler,
        _UnavailableAlignment(),
        inspection,
        research.UncalibratedResourceForecastProvider(inspection),
        fixture.provider,
    )
    return (
        research.LocalResearchService(context),
        scaffold_ref,
        fixture.pack.to_ref(),
    )


def _arm_artifacts(
    pack_ref: research.PriorPackRef,
) -> tuple[FrozenArmArtifact, ...]:
    return build_nonqualifying_preflight_arm_artifacts(pack_ref)


def _official_graph(
    root: Path, domain: ResourcePolicyFixture
) -> tuple[McpService, SubmissionService, ResolvedPlanFixtureTrainEvalService]:
    source = domain.compile_fixture
    pack = _score_pack(root, domain)
    environment = ExecutionEnvironmentPin("b07f-fixture-adapter-v1", ENVIRONMENT_DIGEST)
    asset = FixtureToyAsset(
        challenge_key=source.key,
        generator_configuration_ref=BurgersFixtureConfigurationRef(
            source.key, GENERATOR_DIGEST
        ),
        reference_asset_ref=FixtureReferenceAssetRef(source.key, REFERENCE_DIGEST),
        measurement_contract_ref=research.MeasurementContractRef(
            source.key, MEASUREMENT_DIGEST
        ),
    )
    semantics = dict(fixture_executable_semantics(source.catalog))
    adapter = ResolvedPlanFixtureTrainEvalService(
        challenge_key=source.key,
        candidate_assembly=source.assembly,
        candidate_assembly_ref=source.assembly.to_ref(),
        parameter_catalog=source.catalog,
        parameter_catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        authoring_origin=source.authoring_origin,
        authoring_artifacts=source.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
        resource_policy=domain.policy,
        resource_policy_ref=domain.policy_ref,
        class_bundle=domain.class_bundle,
        selected_resource_class=domain.resource_class,
        selected_resource_class_ref=domain.resource_class_ref,
        expected_active_policy_ref=domain.policy_ref,
        expected_active_resource_class_ref=domain.resource_class_ref,
        provider=DeterministicFixtureProvider(
            FixtureOfficialEntropy(_material(b"be4 fixture entropy"))
        ),
        score_pack=pack,
        runtime_policy=_runtime_policy(environment),
        declared_environment=environment,
        fixture_asset=asset,
        lever_executable_semantics_ref=semantics[_FAMILIES[0]],
        numeric_input_keys=NUMERIC_KEYS,
        boolean_input_keys=BOOLEAN_KEYS,
        curriculum_executable_semantics_ref=semantics[_FAMILIES[1]],
        feature_executable_semantics_ref=semantics[_FAMILIES[2]],
    )
    registry = _registry(root, domain)
    lifecycle = SubmissionService(
        strategy_limits(max_retained_submission_records=64),
        registry,
        FixtureSubmissionPolicy(
            FeePolicyKey("be4-fixture-fee-v1"),
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
    return (
        McpService(registry, lifecycle, _mcp_limits(), _Gate(), None, None, None),
        lifecycle,
        adapter,
    )


def _count(meter: PolicyWorkMeter, kind: PolicyWorkKind) -> int:
    return next(item.count for item in meter.snapshot().counts if item.kind is kind)


def _rebind_hostile_preflight(prepared: object) -> None:
    """Model a caller that recomputes every caller-controlled outer digest."""

    reply_digests = gauntlet_execution._prepared_service_reply_digests(
        challenge_info=prepared.challenge_info,
        interaction_manifest=prepared.interaction_manifest,
        prior_lookup=prepared.prior_lookup,
        scaffold=prepared.scaffold,
        candidates=prepared.candidates,
    )
    object.__setattr__(prepared, "service_reply_digests", reply_digests)
    try:
        request_digests = gauntlet_execution._prepared_service_request_digests(
            plan=prepared.plan,
            challenge_info=prepared.challenge_info,
            interaction_manifest=prepared.interaction_manifest,
            scaffold=prepared.scaffold,
            candidates=prepared.candidates,
        )
    except (TypeError, ValueError):
        # A malformed nested request may fail before it can be canonically
        # reconstructed; retaining the old request transcript still exercises
        # the outer-digest bypass attempt and must fail closed at submission.
        request_digests = prepared.service_request_digests
    object.__setattr__(prepared, "service_request_digests", request_digests)
    object.__setattr__(
        prepared,
        "transcript_digest",
        gauntlet_execution._prepared_transcript_digest(
            plan=prepared.plan,
            strategy_domain_digest=prepared.strategy_domain_digest,
            challenge_info=prepared.challenge_info,
            interaction_manifest=prepared.interaction_manifest,
            prior_lookup=prepared.prior_lookup,
            scaffold=prepared.scaffold,
            proposal_batch=prepared.proposal_batch,
            candidates=prepared.candidates,
            first_preflight_executable_attempt=(
                prepared.first_preflight_executable_attempt
            ),
            service_request_digests=prepared.service_request_digests,
            service_reply_digests=prepared.service_reply_digests,
            preflight_compute=prepared.preflight_compute,
        ),
    )


def _expected_counts(
    *,
    profile: AgentProfile,
    proposal_count: int,
    hint_count: int,
    service_calls: int,
) -> dict[PolicyWorkKind, int]:
    return {
        PolicyWorkKind.ATTEMPT: proposal_count,
        PolicyWorkKind.CANDIDATE_COMPARISON: max(0, proposal_count - 1),
        PolicyWorkKind.CANDIDATE_PROPOSAL: proposal_count,
        PolicyWorkKind.CORPUS_ITEM_INSPECTION: (
            3 if profile is AgentProfile.LITERATURE_GROUNDED else 0
        ),
        PolicyWorkKind.POLICY_TRANSITION: 1,
        PolicyWorkKind.PRIOR_ITEM_INSPECTION: hint_count,
        PolicyWorkKind.RNG_DRAW: (
            3 - hint_count + proposal_count
            if profile is AgentProfile.EVOLUTIONARY
            else 0
        ),
        PolicyWorkKind.SCAFFOLD_PARAMETER_INSPECTION: 3,
        PolicyWorkKind.SERVICE_OPERATION: service_calls,
    }


def test_complete_readiness_graph_is_nonqualifying_and_exposes_prior_limit(
    tmp_path: Path,
) -> None:
    domain = _extended_resource_fixture(tmp_path / "domain")
    store, prior_provider, lookup = _published_prior(tmp_path / "prior", domain)
    research_service, scaffold_ref, practice_pack_ref = _research_graph(
        tmp_path / "research", domain, store, prior_provider, lookup
    )
    official, lifecycle, adapter = _official_graph(tmp_path / "official", domain)
    strategy_domain = fixture_strategy_domain(
        domain.compile_fixture.catalog.to_ref(
            candidate_assembly=domain.compile_fixture.assembly
        )
    )
    authorization_ref = lookup.authorization.receipt_ref
    artifacts = _arm_artifacts(lookup.prior_pack_ref)
    prepared = {}

    for driver in fixture_agent_drivers():
        block = build_nonqualifying_four_arm_block(
            design_digest=_DESIGN_DIGEST,
            block_id=f"integration-{driver.profile.value.lower()}",
            profile=driver.profile,
            replicate=0,
            driver_ref=driver.ref,
            artifacts=artifacts,
            budget=MatchedBudget(driver.profile, 30.0, 1_000.0, 8),
            fixture_resource_ceiling=15,
            scaffold_ref=scaffold_ref,
            practice_pack_ref=practice_pack_ref,
            v2_prior_pack_ref=lookup.prior_pack_ref,
            v2_authorization_ref=authorization_ref,
        )
        for plan in block.runs:
            meter = PolicyWorkMeter()
            session = AgentSession(research_service, official, _REQUESTER, meter)
            result = prepare_nonqualifying_run(
                session=session,
                plan=plan,
                driver=driver,
                strategy_domain=strategy_domain,
                parameter_catalog=domain.compile_fixture.catalog,
                candidate_assembly=domain.compile_fixture.assembly,
                meter=meter,
            )
            prepared[(driver.profile, plan.identity.arm)] = (result, session, meter)
            proposal_count = len(result.proposal_batch.proposals)
            assert tuple(item.proposal.attempt for item in result.candidates) == tuple(
                range(1, proposal_count + 1)
            )
            assert all(item.executable for item in result.candidates)
            expected_service_calls = 3 + 3 * proposal_count
            if plan.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR:
                expected_service_calls += 1
                assert result.prior_lookup is not None
                assert result.prior_lookup.prior_pack_ref == lookup.prior_pack_ref
                hint_count = len(result.prior_lookup.prior_pack.items)
            else:
                assert result.prior_lookup is None
                assert plan.identity.prior_pack_ref is None
                assert plan.identity.test_only_authorization_ref is None
                hint_count = len(plan.arm_artifact.proposal_hints)
            receipt = meter.snapshot()
            assert {
                item.kind: item.count for item in receipt.counts
            } == _expected_counts(
                profile=driver.profile,
                proposal_count=proposal_count,
                hint_count=hint_count,
                service_calls=expected_service_calls,
            )
            assert receipt.total_work_units == sum(
                item.count for item in receipt.counts
            )
            for item in result.candidates:
                assert item.resource_inspection is not None
                assert len(item.resource_inspection.line_items) == 1
                line = item.resource_inspection.line_items[0]
                expected_quantity = (
                    15.0 if item.proposal.surface_id == _FAMILIES[0] else 11.0
                )
                assert line.quantity == expected_quantity
                assert line.confidence_band == (expected_quantity, expected_quantity)
                assert line.quantity <= plan.fixture_resource_ceiling
            assert result.authority_ceiling == PREFLIGHT_AUTHORITY_CEILING
            assert result.qualifying_execution_ready is False

    for profile in AgentProfile:
        no_prior = prepared[(profile, ExperimentalArm.NO_PRIOR)][0]
        v2 = prepared[(profile, ExperimentalArm.V2_TEST_ONLY_PRIOR)][0]
        no_prior_by_surface = {
            item.surface_id: item.strategy_digest
            for item in no_prior.proposal_batch.proposals
        }
        v2_by_surface = {
            item.surface_id: item.strategy_digest
            for item in v2.proposal_batch.proposals
        }
        v2_order = tuple(item.surface_id for item in v2.proposal_batch.proposals)
        no_prior_order = tuple(
            item.surface_id for item in no_prior.proposal_batch.proposals
        )
        assert v2_order != no_prior_order
        if profile is AgentProfile.MINIMALIST:
            assert len(v2_by_surface) == len(no_prior_by_surface) == 1
            assert v2_by_surface != no_prior_by_surface
        else:
            # The prior materially controls which of the three otherwise-equal
            # one-factor candidates is attempted first; binary mutation content
            # for an already-present family remains arm-neutral.
            assert set(v2_order) == set(_FAMILIES)
            assert v2_by_surface == no_prior_by_surface

    hostile_service_evidence, hostile_service_session, hostile_service_meter = prepared[
        (AgentProfile.CODE_GENERATING, ExperimentalArm.V1_DIRECTIVE_PRIOR)
    ]
    object.__setattr__(
        hostile_service_evidence.candidates[0].validation.validation_result_ref,
        "challenge_key",
        ChallengeKey("be4_cross_challenge_fixture", "1.0"),
    )
    object.__setattr__(
        hostile_service_evidence,
        "transcript_digest",
        gauntlet_execution._prepared_transcript_digest(
            plan=hostile_service_evidence.plan,
            strategy_domain_digest=hostile_service_evidence.strategy_domain_digest,
            challenge_info=hostile_service_evidence.challenge_info,
            interaction_manifest=hostile_service_evidence.interaction_manifest,
            prior_lookup=hostile_service_evidence.prior_lookup,
            scaffold=hostile_service_evidence.scaffold,
            proposal_batch=hostile_service_evidence.proposal_batch,
            candidates=hostile_service_evidence.candidates,
            first_preflight_executable_attempt=(
                hostile_service_evidence.first_preflight_executable_attempt
            ),
            service_request_digests=hostile_service_evidence.service_request_digests,
            service_reply_digests=hostile_service_evidence.service_reply_digests,
            preflight_compute=hostile_service_evidence.preflight_compute,
        ),
    )
    service_calls_before = _count(
        hostile_service_meter, PolicyWorkKind.SERVICE_OPERATION
    )
    with pytest.raises(ValueError, match="structurally invalid"):
        submit_prepared_fixture_run(
            session=hostile_service_session, prepared=hostile_service_evidence
        )
    assert (
        _count(hostile_service_meter, PolicyWorkKind.SERVICE_OPERATION)
        == service_calls_before
    )

    for profile, arm, mutation in (
        (
            AgentProfile.LITERATURE_GROUNDED,
            ExperimentalArm.NO_PRIOR,
            "wrong-unit",
        ),
        (
            AgentProfile.EVOLUTIONARY,
            ExperimentalArm.GENERIC_PRIOR,
            "above-ceiling",
        ),
    ):
        hostile_resource, hostile_resource_session, hostile_resource_meter = prepared[
            (profile, arm)
        ]
        inspection = hostile_resource.candidates[0].resource_inspection
        assert inspection is not None
        assert (
            inspection.static_assessment_ref.challenge_key
            == hostile_resource.plan.scaffold_ref.challenge_key
        )
        line = inspection.line_items[0]
        if mutation == "wrong-unit":
            object.__setattr__(line, "unit", "abstract_units:wrong")
        else:
            hostile_quantity = float(hostile_resource.plan.fixture_resource_ceiling + 1)
            object.__setattr__(line, "quantity", hostile_quantity)
            object.__setattr__(
                line, "confidence_band", (hostile_quantity, hostile_quantity)
            )
        object.__setattr__(
            hostile_resource,
            "transcript_digest",
            gauntlet_execution._prepared_transcript_digest(
                plan=hostile_resource.plan,
                strategy_domain_digest=hostile_resource.strategy_domain_digest,
                challenge_info=hostile_resource.challenge_info,
                interaction_manifest=hostile_resource.interaction_manifest,
                prior_lookup=hostile_resource.prior_lookup,
                scaffold=hostile_resource.scaffold,
                proposal_batch=hostile_resource.proposal_batch,
                candidates=hostile_resource.candidates,
                first_preflight_executable_attempt=(
                    hostile_resource.first_preflight_executable_attempt
                ),
                service_request_digests=hostile_resource.service_request_digests,
                service_reply_digests=hostile_resource.service_reply_digests,
                preflight_compute=hostile_resource.preflight_compute,
            ),
        )
        service_calls_before = _count(
            hostile_resource_meter, PolicyWorkKind.SERVICE_OPERATION
        )
        with pytest.raises(ValueError, match="structurally invalid"):
            submit_prepared_fixture_run(
                session=hostile_resource_session,
                prepared=hostile_resource,
            )
        assert (
            _count(hostile_resource_meter, PolicyWorkKind.SERVICE_OPERATION)
            == service_calls_before
        )

    planner_v2, session, meter = prepared[
        (AgentProfile.PLANNER, ExperimentalArm.V2_TEST_ONLY_PRIOR)
    ]
    assert {item.surface_id for item in planner_v2.proposal_batch.proposals} == set(
        _FAMILIES
    )

    hostile_payload, hostile_payload_session, hostile_payload_meter = prepared[
        (AgentProfile.PLANNER, ExperimentalArm.NO_PRIOR)
    ]
    object.__setattr__(
        hostile_payload.candidates[0].proposal,
        "_DataOnlyStrategyProposal__payload",
        b"{}",
    )
    service_calls_before = _count(
        hostile_payload_meter, PolicyWorkKind.SERVICE_OPERATION
    )
    with pytest.raises(ValueError, match="structurally invalid"):
        submit_prepared_fixture_run(
            session=hostile_payload_session, prepared=hostile_payload
        )
    assert (
        _count(hostile_payload_meter, PolicyWorkKind.SERVICE_OPERATION)
        == service_calls_before
    )

    hostile_selection, hostile_selection_session, hostile_selection_meter = prepared[
        (AgentProfile.PLANNER, ExperimentalArm.GENERIC_PRIOR)
    ]
    object.__setattr__(
        hostile_selection,
        "first_preflight_executable_attempt",
        hostile_selection.first_preflight_executable_attempt + 1,
    )
    service_calls_before = _count(
        hostile_selection_meter, PolicyWorkKind.SERVICE_OPERATION
    )
    with pytest.raises(ValueError, match="structurally invalid"):
        submit_prepared_fixture_run(
            session=hostile_selection_session, prepared=hostile_selection
        )
    assert (
        _count(hostile_selection_meter, PolicyWorkKind.SERVICE_OPERATION)
        == service_calls_before
    )

    hostile_header, hostile_header_session, hostile_header_meter = prepared[
        (AgentProfile.CODE_GENERATING, ExperimentalArm.NO_PRIOR)
    ]
    object.__setattr__(
        hostile_header.challenge_info.training_support_ref,
        "challenge_key",
        ChallengeKey("be4_cross_challenge_header", "1.0"),
    )
    _rebind_hostile_preflight(hostile_header)
    service_calls_before = _count(
        hostile_header_meter, PolicyWorkKind.SERVICE_OPERATION
    )
    with pytest.raises(ValueError, match="structurally invalid"):
        submit_prepared_fixture_run(
            session=hostile_header_session, prepared=hostile_header
        )
    assert (
        _count(hostile_header_meter, PolicyWorkKind.SERVICE_OPERATION)
        == service_calls_before
    )

    hostile_compute, hostile_compute_session, hostile_compute_meter = prepared[
        (AgentProfile.CODE_GENERATING, ExperimentalArm.GENERIC_PRIOR)
    ]
    first_count = hostile_compute.preflight_compute.counts[0]
    overage = int(hostile_compute.plan.budget.compute_units) + 1
    object.__setattr__(first_count, "count", first_count.count + overage)
    object.__setattr__(
        hostile_compute.preflight_compute,
        "total_work_units",
        hostile_compute.preflight_compute.total_work_units + overage,
    )
    _rebind_hostile_preflight(hostile_compute)
    service_calls_before = _count(
        hostile_compute_meter, PolicyWorkKind.SERVICE_OPERATION
    )
    with pytest.raises(ValueError, match="structurally invalid"):
        submit_prepared_fixture_run(
            session=hostile_compute_session, prepared=hostile_compute
        )
    assert (
        _count(hostile_compute_meter, PolicyWorkKind.SERVICE_OPERATION)
        == service_calls_before
    )

    hostile_prior, hostile_prior_session, hostile_prior_meter = prepared[
        (AgentProfile.MINIMALIST, ExperimentalArm.V2_TEST_ONLY_PRIOR)
    ]
    assert hostile_prior.prior_lookup is not None
    assert (
        type(hostile_prior.prior_lookup.authorization)
        is research.FixturePriorAuthorization
    )
    object.__setattr__(
        hostile_prior.prior_lookup.authorization.receipt_ref,
        "content_digest",
        "sha256:" + "0" * 64,
    )
    _rebind_hostile_preflight(hostile_prior)
    service_calls_before = _count(hostile_prior_meter, PolicyWorkKind.SERVICE_OPERATION)
    with pytest.raises(ValueError, match="structurally invalid"):
        submit_prepared_fixture_run(
            session=hostile_prior_session, prepared=hostile_prior
        )
    assert (
        _count(hostile_prior_meter, PolicyWorkKind.SERVICE_OPERATION)
        == service_calls_before
    )

    hostile_replies, hostile_replies_session, hostile_replies_meter = prepared[
        (AgentProfile.MINIMALIST, ExperimentalArm.NO_PRIOR)
    ]
    object.__setattr__(
        hostile_replies,
        "service_reply_digests",
        ("sha256:" + "0" * 64, *hostile_replies.service_reply_digests[1:]),
    )
    object.__setattr__(
        hostile_replies,
        "transcript_digest",
        gauntlet_execution._prepared_transcript_digest(
            plan=hostile_replies.plan,
            strategy_domain_digest=hostile_replies.strategy_domain_digest,
            challenge_info=hostile_replies.challenge_info,
            interaction_manifest=hostile_replies.interaction_manifest,
            prior_lookup=hostile_replies.prior_lookup,
            scaffold=hostile_replies.scaffold,
            proposal_batch=hostile_replies.proposal_batch,
            candidates=hostile_replies.candidates,
            first_preflight_executable_attempt=(
                hostile_replies.first_preflight_executable_attempt
            ),
            service_request_digests=hostile_replies.service_request_digests,
            service_reply_digests=hostile_replies.service_reply_digests,
            preflight_compute=hostile_replies.preflight_compute,
        ),
    )
    service_calls_before = _count(
        hostile_replies_meter, PolicyWorkKind.SERVICE_OPERATION
    )
    with pytest.raises(ValueError, match="structurally invalid"):
        submit_prepared_fixture_run(
            session=hostile_replies_session, prepared=hostile_replies
        )
    assert (
        _count(hostile_replies_meter, PolicyWorkKind.SERVICE_OPERATION)
        == service_calls_before
    )

    submitted = submit_prepared_fixture_run(session=session, prepared=planner_v2)
    assert submitted.authority_ceiling == OFFICIAL_FIXTURE_SUBMISSION_AUTHORITY_CEILING
    service_calls_after_submit = _count(meter, PolicyWorkKind.SERVICE_OPERATION)
    with pytest.raises(ValueError, match="exact preflight work state"):
        submit_prepared_fixture_run(session=session, prepared=planner_v2)
    assert _count(meter, PolicyWorkKind.SERVICE_OPERATION) == service_calls_after_submit
    submission_id = submitted.receipt.status.submission_id
    lifecycle.mark_validated(submission_id, _REQUESTER)
    lifecycle.admit_fixture(submission_id, _REQUESTER)
    started = lifecycle.start_fixture_attempt(
        submission_id,
        _REQUESTER,
        FeeOperationKey("be4-integration-charge"),
        FeeOperationKey("be4-integration-refund"),
    )
    outcome = adapter.run_fixture(started.envelope)
    assert type(outcome) is ResolvedFixtureCompletedRun
    assert outcome.emission_capable is False
    assert (
        outcome.reconstruction_receipt.authority_marker
        == "TEST_ONLY_FIXTURE_NOT_QUALIFIED"
    )
    assert outcome.result_receipt.authority_marker == "TEST_ONLY_FIXTURE_NOT_QUALIFIED"
    lifecycle.complete_and_publish(
        outcome.completed_run.handle, outcome.completed_run.internal_result
    )
    result = read_official_fixture_result(session=session, submission=submitted)
    assert result.status.state is SubmissionState.PUBLISHED
    assert submitted.qualifying_execution_ready is False
    assert _count(meter, PolicyWorkKind.SERVICE_OPERATION) == (
        4 + 3 * len(planner_v2.candidates) + 2
    )

    with pytest.raises(TypeError, match="binding is invalid"):
        OfficialFixtureSubmission(
            submitted.authority_ceiling,
            submitted.plan_slot_digest,
            submitted.proposal_digest,
            submitted.receipt,
            submitted.association_digest,
            object(),
        )

    service_calls_before = _count(meter, PolicyWorkKind.SERVICE_OPERATION)
    original_proposal_digest = submitted.proposal_digest
    object.__setattr__(submitted, "proposal_digest", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="structurally invalid"):
        read_official_fixture_result(session=session, submission=submitted)
    assert _count(meter, PolicyWorkKind.SERVICE_OPERATION) == service_calls_before
    object.__setattr__(submitted, "proposal_digest", original_proposal_digest)

    original_submission_id = submitted.receipt.status.submission_id.value
    object.__setattr__(
        submitted.receipt.status.submission_id,
        "value",
        "123e4567-e89b-42d3-a456-426614174001",
    )
    with pytest.raises(ValueError, match="structurally invalid"):
        read_official_fixture_result(session=session, submission=submitted)
    assert _count(meter, PolicyWorkKind.SERVICE_OPERATION) == service_calls_before
    object.__setattr__(
        submitted.receipt.status.submission_id, "value", original_submission_id
    )

    original_state = submitted.receipt.status.state
    object.__setattr__(submitted.receipt.status, "state", SubmissionState.VALIDATED)
    with pytest.raises(ValueError, match="structurally invalid"):
        read_official_fixture_result(session=session, submission=submitted)
    assert _count(meter, PolicyWorkKind.SERVICE_OPERATION) == service_calls_before
    object.__setattr__(submitted.receipt.status, "state", original_state)
