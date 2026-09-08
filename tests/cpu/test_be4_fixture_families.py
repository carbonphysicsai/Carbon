"""Focused B-E4 tests for the closed three-family synthetic fixture."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from b02b_fixtures import make_compile_fixture, strategy_limits
from b07c_fixtures import make_fixture as make_practice_fixture

from carbon import research
from carbon.construction import (
    ConsumerTarget,
    SelectedSurface,
    SurfaceValue,
    SurfaceValueType,
)
from carbon.construction.catalog import catalog_entries_by_surface
from carbon.construction.compiler import (
    SUPPORTED_COMPILER_IDENTITY,
    CompileAccepted,
    CompileRejected,
    compile_strategy,
)
from carbon.gauntlet.agents import (
    CommonArmRng,
    FixtureAgentDriver,
    ProposalDirection,
    fixture_strategy_domain,
)
from carbon.gauntlet.design import (
    analyze_recorded_intervention_diversity,
    canonical_intervention_from_experiment_record,
)
from carbon.gauntlet.fixture import (
    BE4_FIXTURE_LIMITATIONS,
    BE4_FIXTURE_PRIOR_ID,
    BE4_FIXTURE_PRIOR_VERSION,
    BE4_FIXTURE_TEMPLATE_BUILDER_VERSION,
    ThreeFamilyTestOnlyPackBuilder,
    extend_toy_parameter_catalog,
    proposal_hints_from_test_only_lookup,
)
from carbon.gauntlet.meter import PolicyWorkMeter
from carbon.gauntlet.model import AgentProfile, ExperimentalArm, RunIdentity
from carbon.practice.service import MockTrainEvalService, PracticeExecutionError
from carbon.resource_policy.refs import (
    RESOURCE_POLICY_CANONICALIZATION_PROFILE,
    ResourceClassRef,
)
from carbon.toy import (
    FIXTURE_CURRICULUM_SURFACE_ID,
    FIXTURE_FEATURE_SURFACE_ID,
    FIXTURE_HELDOUT_OBSERVATIONS,
    FIXTURE_SAMPLING_SURFACE_ID,
    FIXTURE_TRAINING_OBSERVATIONS,
    FIXTURE_TRANSFER_OBSERVATIONS,
    construct_fixture_model,
    evaluate_fixture_reference,
)

_DIGEST = "sha256:" + "a" * 64
_FAMILIES = (
    FIXTURE_SAMPLING_SURFACE_ID,
    FIXTURE_CURRICULUM_SURFACE_ID,
    FIXTURE_FEATURE_SURFACE_ID,
)
_THREE_FAMILY_FIXTURE_ASSET_DIGEST = (
    "sha256:1d92c7d8e3ae0e9dbfe36731860a4a892788464fa5215b855180e8ce14d20c36"
)


def _extended(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    sampling = catalog_entries_by_surface(fixture.catalog)[FIXTURE_SAMPLING_SURFACE_ID]
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
        base_catalog=fixture.catalog,
        candidate_assembly=fixture.assembly,
        curriculum_semantic_clause_ref=curriculum_clause,
        curriculum_executable_semantics_ref=curriculum_executable,
        feature_semantic_clause_ref=feature_clause,
        feature_executable_semantics_ref=feature_executable,
    )
    return fixture, catalog


def _compile(fixture, catalog, parameters):
    strategy = {**fixture.strategy, "parameters": parameters}
    return compile_strategy(
        strategy,
        challenge_key=fixture.key,
        candidate_assembly=fixture.assembly,
        candidate_assembly_ref=fixture.assembly.to_ref(),
        parameter_catalog=catalog,
        parameter_catalog_ref=catalog.to_ref(candidate_assembly=fixture.assembly),
        authoring_origin=fixture.authoring_origin,
        authoring_artifacts=fixture.authoring_artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )


def _result(configuration, seed=b"\x00fixture-seed"):
    sampling, curriculum, degree = configuration
    coefficient, digest = construct_fixture_model(
        FIXTURE_TRAINING_OBSERVATIONS,
        sampling,
        seed,
        curriculum_emphasis=curriculum,
        feature_degree=degree,
    )
    return (
        digest,
        evaluate_fixture_reference(
            coefficient, FIXTURE_HELDOUT_OBSERVATIONS, feature_degree=degree
        ),
        evaluate_fixture_reference(
            coefficient, FIXTURE_TRANSFER_OBSERVATIONS, feature_degree=degree
        ),
    )


def test_legacy_call_and_absent_extensions_preserve_sampling_semantics(tmp_path):
    legacy = construct_fixture_model(FIXTURE_TRAINING_OBSERVATIONS, 2, b"\x00seed")
    defaulted = construct_fixture_model(
        FIXTURE_TRAINING_OBSERVATIONS,
        2,
        b"\x00seed",
        curriculum_emphasis=1,
        feature_degree=1,
    )
    assert legacy == defaulted

    fixture, catalog = _extended(tmp_path)
    accepted = _compile(fixture, catalog, {FIXTURE_SAMPLING_SURFACE_ID: 2})
    assert type(accepted) is CompileAccepted
    assert MockTrainEvalService._toy_configuration(accepted.construction_plan) == (
        MockTrainEvalService._toy_configuration(accepted.construction_plan)
    )
    configuration = MockTrainEvalService._toy_configuration(accepted.construction_plan)
    assert (
        configuration.sampling_level,
        configuration.curriculum_emphasis,
        configuration.feature_degree,
    ) == (2, 1, 1)


@pytest.mark.parametrize(
    ("baseline", "intervention"),
    (
        ((1, 1, 1), (2, 1, 1)),
        ((1, 1, 1), (1, 2, 1)),
        ((1, 1, 1), (1, 1, 2)),
    ),
)
@pytest.mark.parametrize("seed", (b"\x00fixture-seed", b"\x01fixture-seed"))
def test_each_registered_family_independently_changes_model_and_both_endpoints(
    baseline, intervention, seed
):
    before = _result(baseline, seed)
    after = _result(intervention, seed)
    assert before[0] != after[0]
    assert before[1] != after[1]
    assert before[2] != after[2]


def test_seed_order_can_reverse_direction_so_prior_remains_exploratory() -> None:
    def heldout(seed: bytes, sampling: int, curriculum: int) -> float:
        coefficient, _digest_value = construct_fixture_model(
            FIXTURE_TRAINING_OBSERVATIONS,
            sampling,
            seed,
            curriculum_emphasis=curriculum,
        )
        return evaluate_fixture_reference(coefficient, FIXTURE_HELDOUT_OBSERVATIONS)

    assert heldout(b"\x00", 2, 1) < heldout(b"\x00", 1, 1)
    assert heldout(b"\x01", 2, 1) > heldout(b"\x01", 1, 1)
    assert heldout(b"\x00", 2, 2) > heldout(b"\x00", 2, 1)
    assert heldout(b"\x01", 2, 2) < heldout(b"\x01", 2, 1)


@pytest.mark.parametrize("intervention_surface", _FAMILIES)
def test_each_family_executes_through_b07f_fixture_lifecycle(
    tmp_path, intervention_surface
):
    # Runtime imports avoid a collection cycle: the integration fixture imports
    # this module's prior template helper.
    from test_b07f_resolved_fixture_adapter import _start
    from test_be4_execution_integration import (
        _extended_resource_fixture,
        _official_graph,
    )

    from carbon.fees import SubmissionState
    from carbon.traineval.resolved_fixture import ResolvedFixtureCompletedRun

    domain = _extended_resource_fixture(tmp_path / "domain")
    _service, lifecycle, adapter = _official_graph(tmp_path / "official", domain)
    strategy = {
        **domain.compile_fixture.strategy,
        "parameters": {
            surface: 2 if surface == intervention_surface else 1
            for surface in _FAMILIES
        },
    }
    requester, submission, envelope = _start(lifecycle, domain, strategy)
    outcome = adapter.run_fixture(envelope)
    assert type(outcome) is ResolvedFixtureCompletedRun
    reconstruction = outcome.reconstruction_receipt
    result_receipt = outcome.result_receipt
    assert {
        item.surface_id: item.value for item in reconstruction.consumed_levers
    } == strategy["parameters"]
    assert reconstruction.authority_marker == "TEST_ONLY_FIXTURE_NOT_QUALIFIED"
    assert reconstruction.fixture_asset_digest == _THREE_FAMILY_FIXTURE_ASSET_DIGEST
    assert reconstruction.identity_version == "2.0"
    assert result_receipt.identity_version == "2.0"
    reconstruction_value = json.loads(reconstruction.canonical_bytes())
    assert reconstruction_value["identity_version"] == "2.0"
    assert len(reconstruction_value["consumed_levers"]) == len(_FAMILIES)
    assert "surface" not in reconstruction_value
    assert json.loads(result_receipt.canonical_bytes())["identity_version"] == "2.0"
    published = lifecycle.complete_and_publish(
        outcome.completed_run.handle, outcome.completed_run.internal_result
    )
    assert published.state is SubmissionState.PUBLISHED
    assert lifecycle.read_published(submission, requester).status in {
        "SCORED",
        "MANDATORY_GATE_FAILED",
    }


def test_catalog_compiler_and_practice_consume_only_closed_exact_levers(tmp_path):
    fixture, catalog = _extended(tmp_path)
    accepted = _compile(
        fixture,
        catalog,
        {
            FIXTURE_SAMPLING_SURFACE_ID: 2,
            FIXTURE_CURRICULUM_SURFACE_ID: 2,
            FIXTURE_FEATURE_SURFACE_ID: 2,
        },
    )
    assert type(accepted) is CompileAccepted
    assert tuple(
        binding.surface_id for binding in accepted.training_policy.bindings
    ) == tuple(sorted(_FAMILIES))
    configuration = MockTrainEvalService._toy_configuration(accepted.construction_plan)
    assert (
        configuration.sampling_level,
        configuration.curriculum_emphasis,
        configuration.feature_degree,
    ) == (2, 2, 2)

    for hostile in (True, 1.0, "2", [2]):
        rejected = _compile(
            fixture,
            catalog,
            {
                FIXTURE_SAMPLING_SURFACE_ID: 2,
                FIXTURE_CURRICULUM_SURFACE_ID: hostile,
            },
        )
        assert type(rejected) is CompileRejected


def test_practice_rejects_wrong_toy_consumer_type_and_surface_variant(tmp_path):
    fixture, catalog = _extended(tmp_path)
    wrong_entries = tuple(
        (
            replace(
                entry,
                consumer_target=ConsumerTarget(
                    "fixture_training", "wrong_feature_field"
                ),
            )
            if entry.surface_id == FIXTURE_FEATURE_SURFACE_ID
            else entry
        )
        for entry in catalog.entries
    )
    wrong_catalog = replace(
        catalog, object_id="wrong_feature_consumer_catalog", entries=wrong_entries
    )
    accepted = _compile(
        fixture,
        wrong_catalog,
        {
            FIXTURE_SAMPLING_SURFACE_ID: 1,
            FIXTURE_CURRICULUM_SURFACE_ID: 1,
            FIXTURE_FEATURE_SURFACE_ID: 2,
        },
    )
    assert type(accepted) is CompileAccepted
    with pytest.raises(PracticeExecutionError, match="binding is unsupported"):
        MockTrainEvalService._toy_configuration(accepted.construction_plan)

    sampling_consumer = ConsumerTarget("fixture_training", "sampling_level")
    hostile_surfaces = (
        SimpleNamespace(
            surface_id=FIXTURE_SAMPLING_SURFACE_ID,
            consumer_target=sampling_consumer,
            value=SurfaceValue(SurfaceValueType.UINT64, 1),
        ),
        SelectedSurface(
            FIXTURE_SAMPLING_SURFACE_ID,
            sampling_consumer,
            SurfaceValue(SurfaceValueType.INT64, 1),
        ),
    )
    for surface in hostile_surfaces:
        with pytest.raises(PracticeExecutionError, match="binding is unsupported"):
            MockTrainEvalService._toy_configuration(
                SimpleNamespace(resolved_surfaces=(surface,))
            )


def test_extension_requires_distinct_semantics_and_declares_resource_delta(tmp_path):
    fixture = make_compile_fixture(tmp_path)
    sampling = catalog_entries_by_surface(fixture.catalog)[FIXTURE_SAMPLING_SURFACE_ID]
    with pytest.raises(ValueError, match="distinct owner semantic"):
        extend_toy_parameter_catalog(
            base_catalog=fixture.catalog,
            candidate_assembly=fixture.assembly,
            curriculum_semantic_clause_ref=(
                sampling.semantic_owner_binding.semantic_clause_ref
            ),
            curriculum_executable_semantics_ref=(
                sampling.training_lever_binding.executable_semantics_ref
            ),
            feature_semantic_clause_ref=(
                sampling.semantic_owner_binding.semantic_clause_ref
            ),
            feature_executable_semantics_ref=(
                sampling.training_lever_binding.executable_semantics_ref
            ),
        )

    fixture, catalog = _extended(tmp_path / "distinct")
    base = _compile(
        fixture,
        fixture.catalog,
        {FIXTURE_SAMPLING_SURFACE_ID: 2},
    )
    extended = _compile(
        fixture,
        catalog,
        {FIXTURE_SAMPLING_SURFACE_ID: 2},
    )
    assert type(base) is CompileAccepted
    assert type(extended) is CompileAccepted
    assert base.construction_plan.static_resource_requirements[0].quantity == 13
    assert extended.construction_plan.static_resource_requirements[0].quantity == 15
    assert {"curriculum_impact", "feature_impact"}.issubset(
        extended.construction_plan.resource_impact_tags
    )
    expected_units = {
        (1, 1, 1): 11,
        (2, 1, 1): 15,
        (1, 2, 1): 11,
        (1, 1, 2): 11,
        (2, 2, 2): 15,
    }
    for levels, units in expected_units.items():
        compiled = _compile(fixture, catalog, dict(zip(_FAMILIES, levels, strict=True)))
        assert type(compiled) is CompileAccepted
        assert (
            compiled.construction_plan.static_resource_requirements[0].quantity == units
        )


def _prior_inputs(fixture, catalog):
    key = fixture.key
    catalog_ref = catalog.to_ref(candidate_assembly=fixture.assembly)
    estimand = research.PublicEstimandRef(key, content_digest="sha256:" + "2" * 64)
    search = research.PublicSearchScopeRef(key, content_digest="sha256:" + "3" * 64)
    aggregate = research.PublicAggregatePublicationRef(
        key, content_digest="sha256:" + "4" * 64
    )
    policy_ref = research.PriorPolicyBundleRef(key, content_digest="sha256:" + "5" * 64)
    resource = ResourceClassRef(
        key,
        "fixture_resource",
        "1.0",
        "1.0",
        RESOURCE_POLICY_CANONICALIZATION_PROFILE,
        "sha256:" + "6" * 64,
    )
    scope = research.PriorScope(("fno",), ("fixture_context",), (resource,))
    evidence = research.PriorEvidence(
        research.EvidenceOrigin.SYNTHETIC_TEST_FIXTURE,
        research.EpistemicType.OBSERVED,
        research.EvidenceBand.MEDIUM,
        research.EvidenceBand.MEDIUM,
        research.EvidenceBand.MEDIUM,
        research.EvidenceBand.LOW,
        research.EvidenceBand.MEDIUM,
        research.EvidenceBand.LOW,
        ("fixture_selection",),
        ("synthetic_only",),
    )
    counter = research.CounterevidenceEntries(
        (
            research.CounterevidenceEntry(
                estimand,
                research.CounterevidenceFinding.MIXED,
                scope,
                research.EvidenceOrigin.SYNTHETIC_TEST_FIXTURE,
                research.EpistemicType.OBSERVED,
                research.EvidenceBand.LOW,
                research.EvidenceBand.MEDIUM,
                research.EvidenceBand.LOW,
                ("fixture_scope",),
                ("not_utility_qualified",),
                ("synthetic_only",),
            ),
        )
    )
    template_item = research.PriorGuidanceItem(
        "fixture_guidance_template",
        research.PriorGuidanceKind.EXPLORE,
        research.PriorIntervention(
            FIXTURE_SAMPLING_SURFACE_ID,
            research.PriorAction.COMPARE,
            "uint64_1",
            None,
            "uint64_2",
        ),
        scope,
        (
            research.PriorExpectedOutcome(
                estimand, research.OutcomeDirection.MIXED, "fixture_effect"
            ),
        ),
        evidence,
        counter,
        research.PriorFalsification((), ()),
        research.PriorProvenance((aggregate,)),
    )
    pack = research.PriorPack(
        research.RESEARCH_SCHEMA_VERSION,
        research.RESEARCH_CANONICALIZATION_PROFILE,
        key,
        BE4_FIXTURE_PRIOR_ID,
        BE4_FIXTURE_PRIOR_VERSION,
        research.PriorChannel.TEST_ONLY_FIXTURE,
        0,
        research.PriorPublicationClass.TEST_ONLY,
        10,
        11,
        12,
        research.InteractionManifestRef(key, content_digest="sha256:" + "7" * 64),
        catalog_ref,
        policy_ref,
        BE4_FIXTURE_TEMPLATE_BUILDER_VERSION,
        None,
        (template_item,),
        research.DisclosurePolicyRef(key, content_digest="sha256:" + "8" * 64),
        BE4_FIXTURE_LIMITATIONS,
    )
    registry = research.PriorValidationRegistry(
        catalog,
        catalog_ref,
        policy_ref,
        (
            research.PublicEstimandDefinition(
                estimand,
                "fixture_baseline",
                "fixture_population",
                "lower_is_better",
                "median",
                "abstract_unit",
                "fixture_lineage",
                "bootstrap_interval",
            ),
        ),
        (
            research.PublicSearchScopeDefinition(
                search, (estimand,), ("fixture_context",), 10
            ),
        ),
        (aggregate,),
        (
            (
                research.EvidenceOrigin.SYNTHETIC_TEST_FIXTURE,
                research.EpistemicType.OBSERVED,
            ),
        ),
    )
    return pack, registry, estimand, aggregate


def test_three_family_pack_flows_through_existing_publisher_store_and_provider(
    tmp_path,
):
    fixture, catalog = _extended(tmp_path)
    template, registry, estimand, aggregate = _prior_inputs(fixture, catalog)
    records = tuple(
        research.SyntheticPriorRecord(
            f"private_record_{index}_{polarity}",
            fixture.key,
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
    store = research.PriorPackStore(tmp_path / "be4-prior.sqlite", registry)
    store.initialize_disclosure_ledger("be4_fixture_disclosure")
    publisher = research.SyntheticPriorPublisher(
        store,
        ThreeFamilyTestOnlyPackBuilder(
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            template_pack=template,
            template_pack_ref=research.prior_pack_ref(template),
        ),
        research.ExactHashFixtureAuthorizer("be4_fixture_authorization"),
        research.DeterministicTestOnlySigner("be4_fixture_key", b"fixture-secret"),
        research.FixturePublishingPolicy(1, 1, 1, 1, 10),
        ledger_key="be4_fixture_disclosure",
    )
    snapshot_ref = publisher.publish(
        research.SyntheticEvidenceSnapshot(
            fixture.key, "be4_fixture_snapshot", records
        ),
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
        research.GetPriorRequest(fixture.key, research.ExactPriorSelector(pack_ref))
    )
    assert all(
        item.kind is research.PriorGuidanceKind.EXPLORE
        for item in lookup.prior_pack.items
    )
    assert all(
        item.intervention.action is research.PriorAction.COMPARE
        and item.intervention.baseline_ref == "uint64_1"
        and item.intervention.from_ref is None
        and item.intervention.to_ref == "uint64_2"
        and all(
            outcome.direction is research.OutcomeDirection.MIXED
            for outcome in item.expected_outcomes
        )
        for item in lookup.prior_pack.items
    )
    hints = proposal_hints_from_test_only_lookup(
        lookup,
        catalog=catalog,
        candidate_assembly=fixture.assembly,
        expected_prior_pack_ref=lookup.prior_pack_ref,
        expected_authorization_ref=lookup.authorization.receipt_ref,
    )
    assert tuple(hint.surface_id for hint in hints) == tuple(sorted(_FAMILIES))
    assert all(hint.direction is ProposalDirection.TOGGLE for hint in hints)

    strategy = {
        **fixture.strategy,
        "parameters": {surface: 1 for surface in _FAMILIES},
    }
    domain = fixture_strategy_domain(
        catalog.to_ref(candidate_assembly=fixture.assembly)
    )
    no_prior = FixtureAgentDriver(AgentProfile.PLANNER).propose(
        challenge_key=fixture.key,
        scaffold_strategy=strategy,
        strategy_domain=domain,
        hints=(),
        rng=CommonArmRng(_DIGEST, AgentProfile.PLANNER, "no-prior-block"),
        meter=PolicyWorkMeter(),
    )
    v2 = FixtureAgentDriver(AgentProfile.PLANNER).propose(
        challenge_key=fixture.key,
        scaffold_strategy=strategy,
        strategy_domain=domain,
        hints=hints,
        rng=CommonArmRng(_DIGEST, AgentProfile.PLANNER, "no-prior-block"),
        meter=PolicyWorkMeter(),
    )
    assert no_prior.proposals[0].surface_id == FIXTURE_SAMPLING_SURFACE_ID
    assert v2.proposals[0].surface_id == FIXTURE_CURRICULUM_SURFACE_ID
    assert {item.surface_id for item in v2.proposals} == set(_FAMILIES)

    wrong = replace(
        lookup.prior_pack.items[0],
        intervention=replace(
            lookup.prior_pack.items[0].intervention,
            baseline_ref="uint64_2",
            to_ref="uint64_1",
        ),
    )
    hostile_pack = replace(
        lookup.prior_pack, items=(wrong, *lookup.prior_pack.items[1:])
    )
    hostile_lookup = replace(
        lookup,
        prior_pack=hostile_pack,
        prior_pack_ref=research.prior_pack_ref(hostile_pack),
    )
    with pytest.raises(ValueError):
        proposal_hints_from_test_only_lookup(
            hostile_lookup,
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            expected_prior_pack_ref=lookup.prior_pack_ref,
            expected_authorization_ref=lookup.authorization.receipt_ref,
        )

    wrong_challenge = research.ChallengeKey("wrong_fixture", "1.0")
    wrong_authorization = research.TestOnlyPriorAuthorizationReceiptRef(
        wrong_challenge, "wrong_fixture_authorization", "sha256:" + "9" * 64
    )
    hostile_lookup = replace(
        lookup,
        authorization=research.FixturePriorAuthorization(wrong_authorization),
    )
    with pytest.raises(ValueError, match="closed B-E4 fixture prior"):
        proposal_hints_from_test_only_lookup(
            hostile_lookup,
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            expected_prior_pack_ref=lookup.prior_pack_ref,
            expected_authorization_ref=lookup.authorization.receipt_ref,
        )

    directional_item = replace(
        lookup.prior_pack.items[0],
        expected_outcomes=tuple(
            replace(outcome, direction=research.OutcomeDirection.IMPROVE)
            for outcome in lookup.prior_pack.items[0].expected_outcomes
        ),
    )
    directional_pack = replace(
        lookup.prior_pack,
        items=(directional_item, *lookup.prior_pack.items[1:]),
    )
    directional_ref = research.prior_pack_ref(directional_pack)
    directional_lookup = replace(
        lookup,
        prior_pack=directional_pack,
        prior_pack_ref=directional_ref,
    )
    with pytest.raises(ValueError, match="registered 1-to-2 intervention"):
        proposal_hints_from_test_only_lookup(
            directional_lookup,
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            expected_prior_pack_ref=directional_ref,
            expected_authorization_ref=lookup.authorization.receipt_ref,
        )

    magnitude_item = replace(
        lookup.prior_pack.items[0],
        expected_outcomes=tuple(
            replace(outcome, effect_magnitude_band="protected_margin_hint")
            for outcome in lookup.prior_pack.items[0].expected_outcomes
        ),
    )
    magnitude_pack = replace(
        lookup.prior_pack,
        items=(magnitude_item, *lookup.prior_pack.items[1:]),
    )
    magnitude_ref = research.prior_pack_ref(magnitude_pack)
    with pytest.raises(ValueError, match="registered 1-to-2 intervention"):
        proposal_hints_from_test_only_lookup(
            replace(
                lookup,
                prior_pack=magnitude_pack,
                prior_pack_ref=magnitude_ref,
            ),
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            expected_prior_pack_ref=magnitude_ref,
            expected_authorization_ref=lookup.authorization.receipt_ref,
        )

    unrelated_authorization = research.TestOnlyPriorAuthorizationReceiptRef(
        fixture.key, "unrelated_fixture_authorization", "sha256:" + "0" * 64
    )
    with pytest.raises(ValueError, match="closed B-E4 fixture prior"):
        proposal_hints_from_test_only_lookup(
            replace(
                lookup,
                authorization=research.FixturePriorAuthorization(
                    unrelated_authorization
                ),
            ),
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            expected_prior_pack_ref=lookup.prior_pack_ref,
            expected_authorization_ref=lookup.authorization.receipt_ref,
        )

    with pytest.raises(ValueError, match="closed B-E4 fixture prior"):
        proposal_hints_from_test_only_lookup(
            lookup,
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            expected_prior_pack_ref=replace(
                lookup.prior_pack_ref, channel=research.PriorChannel.PUBLIC
            ),
            expected_authorization_ref=lookup.authorization.receipt_ref,
        )


def test_prior_builder_freezes_template_and_rejects_adverse_associations(tmp_path):
    fixture, catalog = _extended(tmp_path)
    template, _registry, estimand, aggregate = _prior_inputs(fixture, catalog)
    with pytest.raises(TypeError, match="exact TEST_ONLY"):
        ThreeFamilyTestOnlyPackBuilder(
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            template_pack=replace(
                template,
                limitations=(*BE4_FIXTURE_LIMITATIONS, "HIDDEN_SEED_MATERIAL"),
            ),
            template_pack_ref=research.prior_pack_ref(template),
        )

    directional_item = replace(
        template.items[0],
        expected_outcomes=tuple(
            replace(outcome, direction=research.OutcomeDirection.IMPROVE)
            for outcome in template.items[0].expected_outcomes
        ),
    )
    directional_template = replace(template, items=(directional_item,))
    with pytest.raises(TypeError, match="exact TEST_ONLY"):
        ThreeFamilyTestOnlyPackBuilder(
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            template_pack=directional_template,
            template_pack_ref=research.prior_pack_ref(directional_template),
        )

    magnitude_item = replace(
        template.items[0],
        expected_outcomes=tuple(
            replace(outcome, effect_magnitude_band="protected_margin_hint")
            for outcome in template.items[0].expected_outcomes
        ),
    )
    magnitude_template = replace(template, items=(magnitude_item,))
    with pytest.raises(TypeError, match="exact TEST_ONLY"):
        ThreeFamilyTestOnlyPackBuilder(
            catalog=catalog,
            candidate_assembly=fixture.assembly,
            template_pack=magnitude_template,
            template_pack_ref=research.prior_pack_ref(magnitude_template),
        )

    builder = ThreeFamilyTestOnlyPackBuilder(
        catalog=catalog,
        candidate_assembly=fixture.assembly,
        template_pack=template,
        template_pack_ref=research.prior_pack_ref(template),
    )
    associations = tuple(
        research.CoarsenedSyntheticAssociation(
            surface,
            estimand,
            "fixture_context",
            "fno",
            aggregate,
            research.SyntheticFinding.NEGATIVE,
            "negative",
            "small",
            "single",
        )
        for surface in _FAMILIES
    )
    summary = research.SyntheticEvidenceSummary(
        fixture.key, "negative_fixture_snapshot", 10, associations, ("private_cell",)
    )
    with pytest.raises(ValueError, match="genesis family set"):
        builder.build(summary, publication_sequence=0, activation_epoch=12)


def _recorded_intervention(tmp_path, *, replicate: int = 0):
    fixture = make_practice_fixture(tmp_path)
    started = fixture.provider.start_research_task(
        fixture.request("paired", key=f"recorded-diversity-{replicate:04d}")
    )
    fixture.provider.run_queued_task(started.task.task_id)
    record = fixture.provider.get_experiment_record(started.task.task_id)
    key = record.challenge_key
    pack_ref = research.PriorPackRef(
        key, research.PriorChannel.TEST_ONLY_FIXTURE, 0, "sha256:" + "7" * 64
    )
    index_ref = research.PriorIndexSnapshotRef(
        key,
        research.PriorChannel.TEST_ONLY_FIXTURE,
        0,
        content_digest="sha256:" + "8" * 64,
    )
    bindings = replace(
        record.task_bindings,
        prior_index_snapshot_ref=index_ref,
        prior_pack_ref=pack_ref,
    )
    record = replace(
        record,
        task_bindings=bindings,
        prior_resolution=research.PriorResolution(index_ref, pack_ref),
    )
    authorization_ref = research.TestOnlyPriorAuthorizationReceiptRef(
        key, "recorded_diversity_authorization", "sha256:" + "9" * 64
    )
    run = RunIdentity(
        AgentProfile.PLANNER,
        ExperimentalArm.V2_TEST_ONLY_PRIOR,
        replicate,
        pack_ref,
        authorization_ref,
    )
    source = fixture.domain.compile_fixture
    extracted = canonical_intervention_from_experiment_record(
        record,
        catalog=source.catalog,
        candidate_assembly=source.assembly,
        catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        run_identity=run,
    )
    return record, run, source, extracted


def test_recorded_intervention_extracts_owner_record_and_rejects_binding_mismatch(
    tmp_path,
):
    record, run, source, extracted = _recorded_intervention(tmp_path)
    assert extracted.intervention.profile is AgentProfile.PLANNER
    assert extracted.intervention.replicate == 0
    assert extracted.experiment_task_identity.startswith("sha256:")
    assert record.task_id.value not in repr(extracted)
    assert not extracted.has_authoritative_task_to_run_binding

    first, second = record.task_bindings.strategy_bindings
    mismatched_bindings = replace(
        record.task_bindings,
        strategy_bindings=(replace(first, strategy_hash=second.strategy_hash), second),
    )
    with pytest.raises(ValueError, match="admissible v2 paired-practice"):
        canonical_intervention_from_experiment_record(
            replace(record, task_bindings=mismatched_bindings),
            catalog=source.catalog,
            candidate_assembly=source.assembly,
            catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
            run_identity=run,
        )


def test_recorded_diversity_rejects_task_replay_and_parent_lineage_splitting(tmp_path):
    record, _run, source, first = _recorded_intervention(tmp_path)
    pack_ref = record.prior_resolution.prior_pack_ref
    assert pack_ref is not None
    second_run = RunIdentity(
        AgentProfile.CODE_GENERATING,
        ExperimentalArm.V2_TEST_ONLY_PRIOR,
        1,
        pack_ref,
        research.TestOnlyPriorAuthorizationReceiptRef(
            record.challenge_key,
            "recorded_diversity_authorization",
            "sha256:" + "9" * 64,
        ),
    )
    split_record = replace(
        record,
        parent_strategy_hashes=(record.resolved_strategies[0].strategy_hash, None),
    )
    split = canonical_intervention_from_experiment_record(
        split_record,
        catalog=source.catalog,
        candidate_assembly=source.assembly,
        catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        run_identity=second_run,
    )
    assert split.experiment_record_digest != first.experiment_record_digest
    with pytest.raises(ValueError, match="task-to-run identity binding is unavailable"):
        analyze_recorded_intervention_diversity(
            (first, split),
            expected_replicates_per_profile=2,
            matrix_complete=True,
        )


def test_recorded_diversity_rejects_caller_relabeling_without_task_run_authority(
    tmp_path,
):
    record, _run, source, first = _recorded_intervention(tmp_path)
    pack_ref = record.prior_resolution.prior_pack_ref
    assert pack_ref is not None
    relabeled_run = RunIdentity(
        AgentProfile.LITERATURE_GROUNDED,
        ExperimentalArm.V2_TEST_ONLY_PRIOR,
        1,
        pack_ref,
        research.TestOnlyPriorAuthorizationReceiptRef(
            record.challenge_key,
            "recorded_diversity_authorization",
            "sha256:" + "9" * 64,
        ),
    )
    relabeled = canonical_intervention_from_experiment_record(
        replace(record, task_id=research.ResearchTaskId("rtsk_" + "f" * 64)),
        catalog=source.catalog,
        candidate_assembly=source.assembly,
        catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        run_identity=relabeled_run,
    )
    assert relabeled.intervention.profile is AgentProfile.LITERATURE_GROUNDED
    assert not relabeled.has_authoritative_task_to_run_binding
    with pytest.raises(ValueError, match="task-to-run identity binding is unavailable"):
        analyze_recorded_intervention_diversity(
            (first, relabeled),
            expected_replicates_per_profile=2,
            matrix_complete=True,
        )
