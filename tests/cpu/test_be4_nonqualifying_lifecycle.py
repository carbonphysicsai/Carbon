"""Full non-qualifying B-E4 lifecycle integration over existing owners."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from b07b_fixtures import Catalog, Clock, Compiler, Manifests, Queue, Resources
from b07c_fixtures import make_fixture as make_practice_fixture
from test_b07g_research_service import _UnavailableAlignment
from test_be4_execution_integration import (
    _DESIGN_DIGEST,
    _REQUESTER,
    _extended_resource_fixture,
    _official_graph,
    _published_prior,
)

from carbon import research
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY
from carbon.gauntlet import (
    DETERMINISTIC_POPULATION_SCOPE,
    NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING,
    AgentSession,
    ExperimentalArm,
    MatchedBudget,
    OfficialLifecycleBridge,
    ResearchLifecycleBridge,
    build_nonqualifying_lifecycle_four_arm_block,
    fixture_agent_drivers,
    fixture_strategy_domain,
    run_nonqualifying_lifecycle,
)
from carbon.gauntlet.meter import PolicyWorkMeter
from carbon.practice import (
    FreshMockContextFactory,
    InMemoryScaffoldProvider,
    MockTrainEvalService,
    RegisteredMockScaffold,
    VersionedMockPackRegistry,
)


def _lifecycle_research_graph(
    root: Path,
    domain,
    store: research.PriorPackStore,
    prior_provider: research.StaticTestOnlyPriorProvider,
    prior_lookup: research.PriorLookupResult,
):
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
        prior_availability=research.AvailablePriorAvailability(
            research.PriorChannelRef(
                source.key,
                research.PriorChannel.TEST_ONLY_FIXTURE,
                content_digest=prior_lookup.index_snapshot_ref.content_digest,
            ),
            store.read_pack(prior_lookup.prior_pack_ref).prior_policy_bundle_ref,
        ),
    )
    registrations = tuple(
        RegisteredMockScaffold(
            source.key,
            "3.0",
            info.training_support_ref,
            prior_ref,
            source.strategy,
        )
        for prior_ref in (None, prior_lookup.prior_pack_ref)
    )
    scaffold = InMemoryScaffoldProvider(registrations)
    scaffold_ref = registrations[0].resource().scaffold_ref
    assert registrations[1].resource().scaffold_ref == scaffold_ref
    registry = VersionedMockPackRegistry(scopes=(fixture.scope,), packs=(fixture.pack,))
    practice = MockTrainEvalService(
        registry=registry,
        interaction_manifest=manifest,
        context_factory=FreshMockContextFactory(b"b" * 32),
    )
    definitions = (
        research.ReceiptFindingDefinition(
            "paired_practice_observed_difference",
            research.PublicResearchFinding(
                "paired_practice_observed_difference",
                "Observed paired aggregate difference on common fresh fixture cases.",
                research.PublicFindingEvidenceClass.TEST_ONLY,
                info.measurement_contract_ref,
                (0.0, 0.0),
                ("PRACTICE_NON_AUTHORITATIVE", "NOT_A_CONFIDENCE_INTERVAL"),
            ),
        ),
    )
    provider = research.InMemoryResearchTaskProvider(
        challenge_catalog_provider=Catalog(info),
        manifest_provider=Manifests(manifest),
        compilation_resolver=Compiler(domain),
        prior_resolver=research.StaticPriorResolver(prior_provider),
        resource_resolver=Resources(domain),
        executor=practice,
        task_queue=Queue(),
        finding_definitions=definitions,
        receipt_limitations=(
            "LOCAL_RESEARCH_ONLY",
            "PRACTICE_NON_AUTHORITATIVE",
            "NOT_OFFICIAL_EVIDENCE",
            "NOT_SCIENTIFICALLY_QUALIFIED",
            "TEST_ONLY",
            "NOT_UTILITY_QUALIFIED",
        ),
        clock=Clock(),
        worker_implementation_digest="sha256:" + "b" * 64,
        environment_digest="sha256:" + "c" * 64,
    )
    compiler = research.B02BCompilationProvider(
        candidate_assembly=source.assembly,
        candidate_assembly_ref=source.assembly.to_ref(),
        parameter_catalog=source.catalog,
        parameter_catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        authoring_origin=source.authoring_origin,
        authoring_artifacts=source.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=__import__("b02b_fixtures").strategy_limits(),
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
        provider,
    )
    return (
        research.LocalResearchService(context),
        provider,
        scaffold_ref,
        fixture.pack.to_ref(),
    )


def test_smallest_complete_profile_by_arm_lifecycle_matrix_is_nonqualifying(
    tmp_path: Path,
) -> None:
    domain = _extended_resource_fixture(tmp_path / "domain")
    store, prior_provider, lookup = _published_prior(tmp_path / "prior", domain)
    prior_pack = store.read_pack(lookup.prior_pack_ref)
    research_service, provider, scaffold_ref, practice_pack_ref = (
        _lifecycle_research_graph(
            tmp_path / "research", domain, store, prior_provider, lookup
        )
    )
    research_bridge = ResearchLifecycleBridge(research_service, provider)
    strategy_domain = fixture_strategy_domain(
        domain.compile_fixture.catalog.to_ref(
            candidate_assembly=domain.compile_fixture.assembly
        )
    )
    rows = []
    for driver in fixture_agent_drivers():
        block, projection = build_nonqualifying_lifecycle_four_arm_block(
            design_digest=_DESIGN_DIGEST,
            block_id=f"lifecycle-{driver.profile.value.lower()}",
            profile=driver.profile,
            replicate=0,
            driver_ref=driver.ref,
            budget=MatchedBudget(driver.profile, 30.0, 250.0, 8),
            fixture_resource_ceiling=223,
            scaffold_ref=scaffold_ref,
            practice_pack_ref=practice_pack_ref,
            v2_prior_pack=prior_pack,
            v2_authorization_ref=lookup.authorization.receipt_ref,
        )
        for plan in block.runs:
            official, submission_service, adapter = _official_graph(
                tmp_path
                / "official"
                / driver.profile.value.lower()
                / plan.identity.arm.value.lower(),
                domain,
            )
            meter = PolicyWorkMeter()
            session = AgentSession(research_service, official, _REQUESTER, meter)
            result = run_nonqualifying_lifecycle(
                session=session,
                plan=plan,
                driver=driver,
                projection=projection,
                strategy_domain=strategy_domain,
                parameter_catalog=domain.compile_fixture.catalog,
                candidate_assembly=domain.compile_fixture.assembly,
                meter=meter,
                research_bridge=research_bridge,
                official_bridge=OfficialLifecycleBridge(
                    official, submission_service, adapter, _REQUESTER
                ),
            )
            rows.append(result)
            assert result.authority_ceiling == NONQUALIFYING_LIFECYCLE_AUTHORITY_CEILING
            assert result.population_scope == DETERMINISTIC_POPULATION_SCOPE
            assert result.qualifying_execution_ready is False
            assert result.practice
            assert result.official_outcome.emission_capable is False
            assert result.fixture_units <= 223
            assert result.normalized_compute.total_work_units <= 250
            assert 0.0 <= result.heldout_quality_q <= 1.0
            assert 0.0 <= result.transfer_quality_q <= 1.0
            assert (
                result.selection.selected_proposal_digest
                == result.official_submission.proposal_digest
            )
            by_attempt = {item.feedback.attempt: item for item in result.practice}
            assert by_attempt[
                result.selection.selected_attempt
            ].feedback.comparison_value == min(
                item.feedback.comparison_value for item in result.practice
            )
            assert all(
                item.experiment_record.evidence_class
                is research.ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE
                for item in result.practice
            )

    assert len(rows) == 20
    assert {(item.plan.identity.profile, item.plan.identity.arm) for item in rows} == {
        (profile, arm)
        for profile in type(rows[0].plan.identity.profile)
        for arm in ExperimentalArm
    }
    assert len({item.driver_artifact.content_digest for item in rows}) == 5
    assert len({item.treatment_artifact.content_digest for item in rows}) == 4


def test_driver_and_service_substitution_fail_before_lifecycle_work(
    tmp_path: Path,
) -> None:
    domain = _extended_resource_fixture(tmp_path / "domain")
    store, provider, lookup = _published_prior(tmp_path / "prior", domain)
    research_service, task_provider, _, _ = _lifecycle_research_graph(
        tmp_path / "research", domain, store, provider, lookup
    )
    other_service, other_provider, _, _ = _lifecycle_research_graph(
        tmp_path / "other", domain, store, provider, lookup
    )
    with pytest.raises(TypeError, match="composition"):
        ResearchLifecycleBridge(research_service, other_provider)
    bridge = ResearchLifecycleBridge(research_service, task_provider)
    assert bridge is not None
    with pytest.raises(TypeError, match="composition"):
        ResearchLifecycleBridge(other_service, task_provider)
