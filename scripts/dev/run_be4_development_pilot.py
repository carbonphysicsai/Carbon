#!/usr/bin/env python3
"""Run the exact B-E4 40-slot development pilot sequentially.

The default ``--offline`` transport traverses Carbon's real TEST_ONLY research,
practice, construction, submission, reference, measurement, and public-result
services.  It replaces only provider inference with a deterministic structured
response transport.  ``--responses`` remains fail closed because Carbon does
not yet have an authenticated five-owner approval and one-use execution-
authorization verifier.  Neither mode can start calibration or qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CPU_FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "cpu"
for import_root in (REPOSITORY_ROOT, CPU_FIXTURE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from b02b_fixtures import strategy_limits
from b02c_fixtures import ResourcePolicyFixture
from b07b_fixtures import (
    Catalog,
    Clock,
    Compiler,
    Manifests,
    Queue,
    Resources,
)
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
from test_be4_execution_integration import (
    _extended_resource_fixture,
    _published_prior,
)
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
    FeePolicyKey,
    FixtureSubmissionPolicy,
    RequesterIdentity,
    SubmissionService,
)
from carbon.gauntlet.agents import (
    FIXTURE_CORPUS_DIGEST,
    FIXTURE_CORPUS_ID,
    FIXTURE_CORPUS_VERSION,
    FIXTURE_METHOD_CORPUS,
    REGISTERED_EFFECTFUL_SURFACES,
    fixture_agent_drivers,
    fixture_strategy_domain,
)
from carbon.gauntlet.development import (
    DEVELOPMENT_AUTHORITY_CEILING,
    DeterministicOfflineTransport,
    DevelopmentCampaignManifest,
    DevelopmentJournal,
    DevelopmentPilotRunner,
    DevelopmentRunServices,
    DevelopmentRunSlot,
    DevelopmentTask,
    OpenAIResponsesTransport,
    build_development_manifest,
    development_profile_policy_artifacts,
    development_treatment_payload,
)
from carbon.gauntlet.execution import (
    GENERIC_WORKFLOW_STEPS,
    build_nonqualifying_lifecycle_four_arm_block,
)
from carbon.gauntlet.fixture import fixture_executable_semantics
from carbon.gauntlet.harness import AgentSession
from carbon.gauntlet.lifecycle import (
    OfficialLifecycleBridge,
    ResearchLifecycleBridge,
)
from carbon.gauntlet.meter import PolicyWorkMeter
from carbon.gauntlet.model import AgentProfile, ExperimentalArm, MatchedBudget
from carbon.gauntlet.pilot_contract import (
    proposed_synthetic_task_cells,
    realize_synthetic_task,
)
from carbon.generators.refs import BurgersFixtureConfigurationRef
from carbon.mcp import McpService
from carbon.practice import (
    FreshMockContextFactory,
    InMemoryScaffoldProvider,
    MockTrainEvalService,
    RegisteredMockScaffold,
    VersionedMockPackRegistry,
)
from carbon.resource_policy.canonical import (
    research_resource_policy_to_ref,
)
from carbon.seeding import (
    DeterministicFixtureProvider,
    FixtureOfficialEntropy,
)
from carbon.toy.physics import FixtureObservationSet
from carbon.traineval.resolved_fixture import (
    FixtureToyAsset,
    ResolvedPlanFixtureTrainEvalService,
)

DEFAULT_JOURNAL = REPOSITORY_ROOT / ".agent" / "runtime" / "be4-development.sqlite"
DEFAULT_REPORT = (
    REPOSITORY_ROOT
    / ".agent"
    / "evidence"
    / "wave_b"
    / "b-e4-development-offline-integration-v1.json"
)
DEFAULT_MANIFEST = (
    REPOSITORY_ROOT
    / ".agent"
    / "preregistrations"
    / "B-E4_development_execution_request_v1.json"
)
DESIGN_DIGEST = (
    "sha256:11a2b6b7e3817cea62631dfbdd0e5b59393d70f0cb9617776b8996ed535d1538"
)
_EXECUTION_REQUEST_DOMAIN = b"carbon.be4.development-execution-request.v1\x00"
_ARTIFACT_MANIFEST_DOMAIN = b"carbon.be4.development-artifacts.v1\x00"
TASK_ORDINALS = (4, 7)
REQUESTER = RequesterIdentity("be4-development-pilot-v1")
_FIXTURE_BUILDER_SOURCE_PATHS = (
    "tests/cpu/b02b_fixtures.py",
    "tests/cpu/b02c_fixtures.py",
    "tests/cpu/b07b_fixtures.py",
    "tests/cpu/b07c_fixtures.py",
    "tests/cpu/test_b07f_resolved_fixture_adapter.py",
    "tests/cpu/test_b07g_research_service.py",
    "tests/cpu/test_be4_execution_integration.py",
    "tests/cpu/test_mcp_skeleton.py",
)


class DevelopmentFixtureError(RuntimeError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _domain_digest(domain: bytes, value: object) -> str:
    return "sha256:" + hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def _source_component(component_id: str, paths: tuple[str, ...]) -> dict[str, object]:
    source_files = [
        {
            "path": relative,
            "sha256": hashlib.sha256(
                (REPOSITORY_ROOT / relative).read_bytes()
            ).hexdigest(),
        }
        for relative in paths
    ]
    return {
        "component_id": component_id,
        "content_digest": _domain_digest(
            b"carbon.be4.development-source-component.v1\x00", source_files
        ),
        "file_count": len(source_files),
    }


def implementation_manifest() -> dict[str, object]:
    carbon_paths = tuple(
        str(path.relative_to(REPOSITORY_ROOT))
        for path in sorted((REPOSITORY_ROOT / "carbon").rglob("*.py"))
    )
    return {
        "components": [
            _source_component("carbon_python_package", carbon_paths),
            _source_component(
                "development_runner",
                ("scripts/dev/run_be4_development_pilot.py",),
            ),
            _source_component("reused_fixture_builders", _FIXTURE_BUILDER_SOURCE_PATHS),
        ],
        "schema_version": "carbon.be4.development-implementation.v1",
    }


def implementation_digest() -> str:
    return _domain_digest(
        b"carbon.be4.development-implementation.v1\x00", implementation_manifest()
    )


def _balanced_resource_fixture(root: Path) -> ResourcePolicyFixture:
    """Wrap B-02B/B-02C fixture ownership with the v2 BALANCED unit recipe."""

    base = _extended_resource_fixture(root)
    source = base.compile_fixture
    sampling = catalog_entries_by_surface(source.catalog)[
        REGISTERED_EFFECTFUL_SURFACES[0]
    ]
    contribution = sampling.static_resource_contributions[0]
    balanced = replace(
        contribution,
        cases=tuple(replace(item, quantity=10) for item in contribution.cases),
    )
    balanced_sampling = replace(sampling, static_resource_contributions=(balanced,))
    catalog = replace(
        source.catalog,
        object_id="be4_development_balanced_parameter_catalog",
        object_version="3.0",
        entries=tuple(
            balanced_sampling if item.surface_id == sampling.surface_id else item
            for item in source.catalog.entries
        ),
    )
    compiled = compile_strategy(
        source.strategy,
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
    if type(compiled) is not CompileAccepted:
        raise DevelopmentFixtureError("balanced fixture catalog did not compile")
    policy = replace(
        base.policy,
        object_id="be4_development_balanced_resource_policy",
        object_version="3.0",
        parameter_catalog_ref=catalog.to_ref(candidate_assembly=source.assembly),
        class_bindings=tuple(
            replace(
                binding,
                ceilings=tuple(
                    replace(item, maximum_quantity=17) for item in binding.ceilings
                ),
            )
            for binding in base.policy.class_bindings
        ),
    )
    policy_ref = research_resource_policy_to_ref(policy, class_bundle=base.class_bundle)
    return ResourcePolicyFixture(
        replace(source, catalog=catalog),
        compiled,
        base.context,
        base.resource_class,
        base.resource_class_ref,
        policy,
        policy_ref,
    )


def _task_material() -> (
    tuple[tuple[DevelopmentTask, DevelopmentTask], dict[str, FixtureObservationSet]]
):
    tasks: list[DevelopmentTask] = []
    observations: dict[str, FixtureObservationSet] = {}
    cells = proposed_synthetic_task_cells()
    for ordinal in TASK_ORDINALS:
        cell = cells[ordinal]
        evaluator_seed = hashlib.sha256(
            b"carbon.be4.development-public-task.v1\x00" + cell.cell_id.encode("ascii")
        ).digest()
        realized = realize_synthetic_task(cell, evaluator_seed=evaluator_seed)
        observation_set = FixtureObservationSet(
            f"development-{cell.cell_id}",
            realized.training_observations,
            realized.heldout_observations,
            realized.transfer_observations,
        )
        task = DevelopmentTask(
            cell.cell_id,
            cell.cell_id,
            {
                "candidate_space": "EIGHT_REGISTERED_BINARY_CONFIGURATIONS",
                "noise_class": cell.noise_id,
                "registered_strategy_schema": "CARBON_STRATEGY_1_0_FNO",
                "resource_regime": cell.resource_regime,
                "target_family": (
                    "Y_EQUALS_X" if cell.target_degree == 1 else "Y_EQUALS_X_SQUARED"
                ),
                "training_observation_count": len(cell.training_x),
                "transfer_class": cell.transfer_id,
            },
            observation_set.content_digest,
            cell.candidate_fixture_units,
            9 * cell.candidate_fixture_units,
        )
        tasks.append(task)
        observations[task.task_id] = observation_set
    result = tuple(tasks)
    assert len(result) == 2
    return result, observations  # type: ignore[return-value]


def _research_graph(
    root: Path,
    domain: ResourcePolicyFixture,
    store: research.PriorPackStore,
    prior_provider: research.StaticTestOnlyPriorProvider,
    prior_lookup: research.PriorLookupResult,
    observation_set: FixtureObservationSet,
) -> tuple[
    research.LocalResearchService,
    research.InMemoryResearchTaskProvider,
    research.MockScaffoldRef,
    research.PracticePackRef,
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
            "4.0",
            info.training_support_ref,
            prior_ref,
            source.strategy,
        )
        for prior_ref in (None, prior_lookup.prior_pack_ref)
    )
    scaffold = InMemoryScaffoldProvider(registrations)
    scaffold_ref = registrations[0].resource().scaffold_ref
    if registrations[1].resource().scaffold_ref != scaffold_ref:
        raise DevelopmentFixtureError("four-arm scaffold identity diverged")
    registry = VersionedMockPackRegistry(scopes=(fixture.scope,), packs=(fixture.pack,))
    practice = MockTrainEvalService(
        registry=registry,
        interaction_manifest=manifest,
        context_factory=FreshMockContextFactory(
            hashlib.sha256(
                b"carbon.be4.development-practice.v1\x00"
                + observation_set.content_digest.encode("ascii")
            ).digest()
        ),
        observation_set=observation_set,
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
        provider,
    )
    return (
        research.LocalResearchService(context),
        provider,
        scaffold_ref,
        fixture.pack.to_ref(),
    )


def _official_graph(
    root: Path,
    domain: ResourcePolicyFixture,
    observation_set: FixtureObservationSet,
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
        observation_set=observation_set,
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
            FixtureOfficialEntropy(
                hashlib.sha256(
                    b"carbon.be4.development-official.v1\x00"
                    + observation_set.content_digest.encode("ascii")
                ).digest()
            )
        ),
        score_pack=pack,
        runtime_policy=_runtime_policy(environment),
        declared_environment=environment,
        fixture_asset=asset,
        lever_executable_semantics_ref=semantics[REGISTERED_EFFECTFUL_SURFACES[0]],
        numeric_input_keys=NUMERIC_KEYS,
        boolean_input_keys=BOOLEAN_KEYS,
        curriculum_executable_semantics_ref=semantics[REGISTERED_EFFECTFUL_SURFACES[1]],
        feature_executable_semantics_ref=semantics[REGISTERED_EFFECTFUL_SURFACES[2]],
    )
    registry = _registry(root, domain)
    lifecycle = SubmissionService(
        strategy_limits(max_retained_submission_records=64),
        registry,
        FixtureSubmissionPolicy(
            FeePolicyKey("be4-development-fixture-fee-v1"),
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


class FixtureServiceFactory:
    """Exact per-run composition of existing Carbon TEST_ONLY owners."""

    def __init__(
        self,
        root: Path,
        *,
        tasks: tuple[DevelopmentTask, DevelopmentTask],
        observations: dict[str, FixtureObservationSet],
    ) -> None:
        self._root = root
        self._tasks = {item.task_id: item for item in tasks}
        self._observations = observations
        self._domain = _balanced_resource_fixture(root / "domain")
        self._store, self._prior_provider, self._lookup = _published_prior(
            root / "prior", self._domain
        )
        self._prior_pack = self._store.read_pack(self._lookup.prior_pack_ref)
        self._drivers = {item.profile: item for item in fixture_agent_drivers()}
        self._strategy_domain = fixture_strategy_domain(
            self._domain.compile_fixture.catalog.to_ref(
                candidate_assembly=self._domain.compile_fixture.assembly
            )
        )
        self._research: dict[str, tuple[object, object, object, object]] = {}
        for task in tasks:
            self._research[task.task_id] = _research_graph(
                root / "research" / task.task_id,
                self._domain,
                self._store,
                self._prior_provider,
                self._lookup,
                observations[task.task_id],
            )
        self._blocks: dict[tuple[object, str], tuple[object, object]] = {}

    @property
    def artifact_manifest(self) -> dict[str, object]:
        source = self._domain.compile_fixture
        tasks = tuple(self._tasks.values())
        representative = DevelopmentRunSlot(
            0,
            f"be4-development-planner-{tasks[0].task_id.lower()}-no_prior",
            f"be4-development-planner-{tasks[0].task_id.lower()}",
            next(iter(self._drivers)),
            ExperimentalArm.NO_PRIOR,
            tasks[0].task_id,
            0,
        )
        block, projection = self._block(representative, tasks[0])
        task_assets = []
        for task in tasks:
            _service, _provider, scaffold_ref, practice_pack_ref = self._research[
                task.task_id
            ]
            seed = hashlib.sha256(
                b"carbon.be4.development-public-task.v1\x00"
                + task.cell_id.encode("ascii")
            ).digest()
            task_assets.append(
                {
                    "evaluator_seed_commitment": "sha256:"
                    + hashlib.sha256(seed).hexdigest(),
                    "evaluator_seed_egress": False,
                    "observation_set_digest": self._observations[
                        task.task_id
                    ].content_digest,
                    "practice_pack_ref": practice_pack_ref.content_digest,
                    "scaffold_ref": scaffold_ref.content_digest,
                    "task_digest": task.content_digest,
                    "task_id": task.task_id,
                }
            )
        lookup_ref = self._lookup.prior_pack_ref
        authorization_ref = self._lookup.authorization.receipt_ref
        return {
            "candidate_assembly_ref": source.assembly.to_ref().content_digest,
            "fixture_method_corpus": {
                "content_digest": FIXTURE_CORPUS_DIGEST,
                "corpus_id": FIXTURE_CORPUS_ID,
                "entries": [
                    {
                        "direction": item.direction.value,
                        "method_id": item.method_id,
                        "surface_keyword": item.surface_keyword,
                    }
                    for item in FIXTURE_METHOD_CORPUS
                ],
                "version": FIXTURE_CORPUS_VERSION,
            },
            "parameter_catalog_ref": source.catalog.to_ref(
                candidate_assembly=source.assembly
            ).content_digest,
            "implementation_components": implementation_manifest(),
            "profile_prompt_policies": list(development_profile_policy_artifacts()),
            "resource_policy_ref": self._domain.policy_ref.content_digest,
            "schema_version": "carbon.be4.development-artifacts.v1",
            "tasks": task_assets,
            "treatments": [
                development_treatment_payload(
                    plan=plan,
                    projection=projection,
                    prior_lookup=(
                        self._lookup
                        if plan.identity.arm.value == "V2_TEST_ONLY_PRIOR"
                        else None
                    ),
                )
                for plan in block.runs
            ],
            "v2_test_only_authorization_ref": {
                "authorization_id": authorization_ref.authorization_id,
                "challenge_id": authorization_ref.challenge_key.challenge_id,
                "challenge_version": authorization_ref.challenge_key.version,
                "content_digest": authorization_ref.content_digest,
            },
            "v2_test_only_prior_pack_ref": {
                "challenge_id": lookup_ref.challenge_key.challenge_id,
                "challenge_version": lookup_ref.challenge_key.version,
                "channel": lookup_ref.channel.value,
                "content_hash": lookup_ref.content_hash,
                "publication_sequence": lookup_ref.publication_sequence,
            },
        }

    @property
    def artifact_manifest_digest(self) -> str:
        return _domain_digest(_ARTIFACT_MANIFEST_DOMAIN, self.artifact_manifest)

    def _block(self, slot: DevelopmentRunSlot, task: DevelopmentTask):
        key = (slot.profile, task.task_id)
        current = self._blocks.get(key)
        if current is None:
            service, _provider, scaffold_ref, practice_pack_ref = self._research[
                task.task_id
            ]
            del service
            driver = self._drivers[slot.profile]
            current = build_nonqualifying_lifecycle_four_arm_block(
                design_digest=DESIGN_DIGEST,
                block_id=slot.block_id,
                profile=slot.profile,
                replicate=slot.task_ordinal,
                driver_ref=driver.ref,
                budget=MatchedBudget(slot.profile, 900.0, 64.0, 4),
                fixture_resource_ceiling=task.maximum_run_fixture_units,
                scaffold_ref=scaffold_ref,
                practice_pack_ref=practice_pack_ref,
                v2_prior_pack=self._prior_pack,
                v2_authorization_ref=self._lookup.authorization.receipt_ref,
            )
            self._blocks[key] = current
        return current

    def create(
        self, slot: DevelopmentRunSlot, task: DevelopmentTask
    ) -> DevelopmentRunServices:
        if self._tasks.get(task.task_id) != task:
            raise DevelopmentFixtureError("run requested an unregistered task")
        block, projection = self._block(slot, task)
        plan = next(item for item in block.runs if item.identity.arm is slot.arm)
        service, provider, _scaffold, _pack = self._research[task.task_id]
        official, submission, adapter = _official_graph(
            self._root / "official" / slot.run_id,
            self._domain,
            self._observations[task.task_id],
        )
        meter = PolicyWorkMeter()
        session = AgentSession(service, official, REQUESTER, meter)
        return DevelopmentRunServices(
            plan,
            projection,
            session,
            meter,
            ResearchLifecycleBridge(service, provider),
            OfficialLifecycleBridge(official, submission, adapter, REQUESTER),
            self._strategy_domain,
            self._domain.compile_fixture.catalog,
            self._domain.compile_fixture.assembly,
        )


def _build(
    root: Path,
) -> tuple[
    tuple[DevelopmentTask, DevelopmentTask],
    FixtureServiceFactory,
    DevelopmentCampaignManifest,
]:
    tasks, observations = _task_material()
    factory = FixtureServiceFactory(root, tasks=tasks, observations=observations)
    manifest = build_development_manifest(
        implementation_digest=implementation_digest(),
        artifact_manifest_digest=factory.artifact_manifest_digest,
        tasks=tasks,
    )
    return tasks, factory, manifest


def _is_digest(value: object) -> bool:
    return (
        type(value) is str
        and value.startswith("sha256:")
        and len(value) == 71
        and all(item in "0123456789abcdef" for item in value[7:])
    )


def _validated_artifact_identities(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "candidate_assembly_ref",
        "fixture_method_corpus",
        "implementation_components",
        "parameter_catalog_ref",
        "profile_prompt_policies",
        "resource_policy_ref",
        "schema_version",
        "tasks",
        "treatments",
        "v2_test_only_authorization_ref",
        "v2_test_only_prior_pack_ref",
    }:
        raise DevelopmentFixtureError("artifact identity schema is invalid")
    if (
        value["schema_version"] != "carbon.be4.development-artifacts.v1"
        or not _is_digest(value["candidate_assembly_ref"])
        or not _is_digest(value["parameter_catalog_ref"])
        or not _is_digest(value["resource_policy_ref"])
    ):
        raise DevelopmentFixtureError("artifact owner references are invalid")
    if value["implementation_components"] != implementation_manifest():
        raise DevelopmentFixtureError("implementation source identities are stale")
    expected_corpus = {
        "content_digest": FIXTURE_CORPUS_DIGEST,
        "corpus_id": FIXTURE_CORPUS_ID,
        "entries": [
            {
                "direction": item.direction.value,
                "method_id": item.method_id,
                "surface_keyword": item.surface_keyword,
            }
            for item in FIXTURE_METHOD_CORPUS
        ],
        "version": FIXTURE_CORPUS_VERSION,
    }
    if value["fixture_method_corpus"] != expected_corpus:
        raise DevelopmentFixtureError("frozen fixture corpus is invalid")
    if value["profile_prompt_policies"] != list(development_profile_policy_artifacts()):
        raise DevelopmentFixtureError("frozen profile prompts are invalid")

    tasks = value["tasks"]
    if type(tasks) is not list or len(tasks) != 2:
        raise DevelopmentFixtureError("artifact task identities are invalid")
    task_ids: set[str] = set()
    for task in tasks:
        if (
            type(task) is not dict
            or set(task)
            != {
                "evaluator_seed_commitment",
                "evaluator_seed_egress",
                "observation_set_digest",
                "practice_pack_ref",
                "scaffold_ref",
                "task_digest",
                "task_id",
            }
            or task["evaluator_seed_egress"] is not False
            or type(task["task_id"]) is not str
            or not task["task_id"]
            or any(
                not _is_digest(task[item])
                for item in (
                    "evaluator_seed_commitment",
                    "observation_set_digest",
                    "practice_pack_ref",
                    "scaffold_ref",
                    "task_digest",
                )
            )
        ):
            raise DevelopmentFixtureError("artifact task binding is invalid")
        task_ids.add(task["task_id"])
    if task_ids != {"be4-pilot-v2-04", "be4-pilot-v2-07"}:
        raise DevelopmentFixtureError("artifact task set is invalid")

    pack_ref = value["v2_test_only_prior_pack_ref"]
    authorization_ref = value["v2_test_only_authorization_ref"]
    if (
        type(pack_ref) is not dict
        or set(pack_ref)
        != {
            "challenge_id",
            "challenge_version",
            "channel",
            "content_hash",
            "publication_sequence",
        }
        or pack_ref["channel"] != "TEST_ONLY_FIXTURE"
        or not _is_digest(pack_ref["content_hash"])
        or type(pack_ref["publication_sequence"]) is not int
        or pack_ref["publication_sequence"] < 0
        or type(authorization_ref) is not dict
        or set(authorization_ref)
        != {
            "authorization_id",
            "challenge_id",
            "challenge_version",
            "content_digest",
        }
        or not _is_digest(authorization_ref["content_digest"])
        or authorization_ref["challenge_id"] != pack_ref["challenge_id"]
        or authorization_ref["challenge_version"] != pack_ref["challenge_version"]
    ):
        raise DevelopmentFixtureError(
            "TEST_ONLY pack authorization identity is invalid"
        )

    treatments = value["treatments"]
    if type(treatments) is not list or len(treatments) != 4:
        raise DevelopmentFixtureError("treatment artifact set is invalid")
    treatment_by_arm: dict[str, dict[str, object]] = {}
    common_keys = {
        "arm",
        "artifact_digest",
        "artifact_id",
        "artifact_version",
        "limitations",
        "material",
        "suggested_surfaces",
    }
    for item in treatments:
        if (
            type(item) is not dict
            or set(item) not in (common_keys, common_keys | {"pack_ref"})
            or type(item.get("arm")) is not str
            or item["arm"] in treatment_by_arm
            or not _is_digest(item.get("artifact_digest"))
            or type(item.get("artifact_id")) is not str
            or not item["artifact_id"]
            or type(item.get("artifact_version")) is not str
            or not item["artifact_version"]
            or item.get("limitations")
            != ["TEST_ONLY", "NOT_UTILITY_QUALIFIED", "NONQUALIFYING_DEVELOPMENT"]
            or type(item.get("suggested_surfaces")) is not list
            or any(type(surface) is not str for surface in item["suggested_surfaces"])
            or len(item["suggested_surfaces"]) != len(set(item["suggested_surfaces"]))
            or any(
                surface not in REGISTERED_EFFECTFUL_SURFACES
                for surface in item["suggested_surfaces"]
            )
        ):
            raise DevelopmentFixtureError("treatment artifact is invalid")
        treatment_by_arm[item["arm"]] = item
    if set(treatment_by_arm) != {item.value for item in ExperimentalArm}:
        raise DevelopmentFixtureError("treatment arm set is invalid")
    v1_material = treatment_by_arm["V1_DIRECTIVE_PRIOR"]["material"]
    v2_material = treatment_by_arm["V2_TEST_ONLY_PRIOR"]["material"]
    if (
        treatment_by_arm["NO_PRIOR"]["material"] is not None
        or treatment_by_arm["NO_PRIOR"]["suggested_surfaces"] != []
        or treatment_by_arm["GENERIC_PRIOR"]["material"] != list(GENERIC_WORKFLOW_STEPS)
        or treatment_by_arm["GENERIC_PRIOR"]["suggested_surfaces"] != []
        or type(v1_material) is not list
        or not v1_material
        or any(
            type(item) is not dict
            or set(item) != {"kind", "subject", "tokens"}
            or type(item["kind"]) is not str
            or item["subject"] not in REGISTERED_EFFECTFUL_SURFACES
            or type(item["tokens"]) is not list
            or any(type(token) is not str for token in item["tokens"])
            for item in v1_material
        )
        or type(v2_material) is not list
        or not v2_material
        or any(
            type(item) is not dict
            or set(item)
            != {
                "action",
                "baseline_ref",
                "expected_directions",
                "guidance_kind",
                "item_id",
                "surface_id",
                "to_ref",
            }
            or any(
                type(item[field]) is not str
                for field in (
                    "action",
                    "baseline_ref",
                    "guidance_kind",
                    "item_id",
                    "surface_id",
                    "to_ref",
                )
            )
            or item["surface_id"] not in REGISTERED_EFFECTFUL_SURFACES
            or type(item["expected_directions"]) is not list
            or any(
                type(direction) is not str for direction in item["expected_directions"]
            )
            for item in v2_material
        )
        or treatment_by_arm["V2_TEST_ONLY_PRIOR"].get("pack_ref") != pack_ref
        or treatment_by_arm["V2_TEST_ONLY_PRIOR"]["artifact_digest"]
        != pack_ref["content_hash"]
        or any(
            "pack_ref" in treatment_by_arm[arm]
            for arm in ("NO_PRIOR", "GENERIC_PRIOR", "V1_DIRECTIVE_PRIOR")
        )
    ):
        raise DevelopmentFixtureError("treatment semantics are invalid")
    return value


def _validated_manifest(value: object) -> DevelopmentCampaignManifest:
    if type(value) is not dict:
        raise DevelopmentFixtureError("development manifest is not an object")
    try:
        raw_tasks = value["tasks"]
        raw_schedule = value["schedule"]
        if type(raw_tasks) is not list or type(raw_schedule) is not list:
            raise TypeError
        tasks = tuple(
            DevelopmentTask(
                item["task_id"],
                item["cell_id"],
                item["agent_visible_description"],
                item["observation_set_digest"],
                item["candidate_fixture_units"],
                item["maximum_run_fixture_units"],
            )
            for item in raw_tasks
        )
        if any(
            item["content_digest"] != task.content_digest
            for item, task in zip(raw_tasks, tasks)
        ):
            raise ValueError
        schedule = tuple(
            DevelopmentRunSlot(
                item["ordinal"],
                item["run_id"],
                item["block_id"],
                AgentProfile(item["profile"]),
                ExperimentalArm(item["arm"]),
                item["task_id"],
                item["task_ordinal"],
            )
            for item in raw_schedule
        )
        parsed = DevelopmentCampaignManifest(
            value["campaign_id"],
            value["proposal_digest"],
            value["implementation_digest"],
            value["artifact_manifest_digest"],
            tasks,  # type: ignore[arg-type]
            schedule,
            value["content_digest"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise DevelopmentFixtureError("development manifest is invalid") from error
    if parsed.to_json() != value:
        raise DevelopmentFixtureError("development manifest has unsupported fields")
    return parsed


def execution_request(
    manifest: DevelopmentCampaignManifest,
    artifact_identities: dict[str, object],
) -> dict[str, object]:
    checked_artifacts = _validated_artifact_identities(artifact_identities)
    if (
        _domain_digest(_ARTIFACT_MANIFEST_DOMAIN, checked_artifacts)
        != manifest.artifact_manifest_digest
        or manifest.implementation_digest != implementation_digest()
    ):
        raise DevelopmentFixtureError("artifact identities do not bind the manifest")
    value: dict[str, object] = {
        "approval_request": {
            "account_retention_control": (
                "RECOMMEND_VERIFIED_ZERO_DATA_RETENTION_PROJECT_BLOCK_IF_UNAVAILABLE_"
                "UNLESS_SECURITY_OWNER_APPROVES_A_NAMED_ALTERNATIVE"
            ),
            "authenticated_owner_roles_required": [
                "RESEARCH",
                "EXACT_PROTOCOL",
                "SCIENCE",
                "STATISTICS",
                "SECURITY",
            ],
            "development_monetary_ceiling_usd": "14.42",
            "execution_authorization": "ONE_USE_DEVELOPMENT_STAGE_REQUIRED",
            "overall_pilot_ceiling_unchanged_usd": "98.304",
            "provider_account_configuration": {
                "api_key_source": "OPENAI_API_KEY",
                "credential_values_recorded": False,
                "organization_id_source": "OPENAI_ORGANIZATION_ID_OPTIONAL",
                "project_id_source": "OPENAI_PROJECT_ID",
            },
            "provider_payload_egress": (
                "APPROVE_EXACT_SIX_FIELD_ALLOWLIST_IN_BOUND_MANIFEST_ONLY"
            ),
            "proposal_and_design": (
                "APPROVE_EXACT_DESIGN_PROPOSAL_IMPLEMENTATION_ARTIFACT_AND_MANIFEST_"
                "DIGESTS"
            ),
            "requested_status": "PROPOSED_NOT_APPROVED_NOT_AUTHORIZED",
        },
        "artifact_identities": artifact_identities,
        "design_digest": DESIGN_DIGEST,
        "current_admission_status": (
            "BLOCKED_NO_REPOSITORY_NATIVE_AUTHENTICATED_FIVE_OWNER_AND_ONE_USE_VERIFIER"
        ),
        "manifest": manifest.to_json(),
        "paid_execution_occurred": False,
        "qualifying_execution_ready": False,
        "schema_version": "carbon.be4.development-execution-request.v1",
    }
    value["content_digest"] = _domain_digest(_EXECUTION_REQUEST_DOMAIN, value)
    return value


def validate_execution_request(value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise DevelopmentFixtureError("development execution request is not an object")
    required = {
        "approval_request",
        "artifact_identities",
        "content_digest",
        "current_admission_status",
        "design_digest",
        "manifest",
        "paid_execution_occurred",
        "qualifying_execution_ready",
        "schema_version",
    }
    approval = value.get("approval_request")
    artifacts = value.get("artifact_identities")
    manifest = value.get("manifest")
    supplied_digest = value.get("content_digest")
    digest_source = dict(value)
    digest_source.pop("content_digest", None)
    try:
        checked_artifacts = _validated_artifact_identities(artifacts)
        checked_manifest = _validated_manifest(manifest)
    except DevelopmentFixtureError as error:
        raise DevelopmentFixtureError(
            "development execution request boundary is invalid"
        ) from error
    if (
        set(value) != required
        or value["schema_version"] != "carbon.be4.development-execution-request.v1"
        or value["design_digest"] != DESIGN_DIGEST
        or value["current_admission_status"]
        != "BLOCKED_NO_REPOSITORY_NATIVE_AUTHENTICATED_FIVE_OWNER_AND_ONE_USE_VERIFIER"
        or value["paid_execution_occurred"] is not False
        or value["qualifying_execution_ready"] is not False
        or type(approval) is not dict
        or approval
        != {
            "account_retention_control": (
                "RECOMMEND_VERIFIED_ZERO_DATA_RETENTION_PROJECT_BLOCK_IF_UNAVAILABLE_"
                "UNLESS_SECURITY_OWNER_APPROVES_A_NAMED_ALTERNATIVE"
            ),
            "authenticated_owner_roles_required": [
                "RESEARCH",
                "EXACT_PROTOCOL",
                "SCIENCE",
                "STATISTICS",
                "SECURITY",
            ],
            "development_monetary_ceiling_usd": "14.42",
            "execution_authorization": "ONE_USE_DEVELOPMENT_STAGE_REQUIRED",
            "overall_pilot_ceiling_unchanged_usd": "98.304",
            "provider_account_configuration": {
                "api_key_source": "OPENAI_API_KEY",
                "credential_values_recorded": False,
                "organization_id_source": "OPENAI_ORGANIZATION_ID_OPTIONAL",
                "project_id_source": "OPENAI_PROJECT_ID",
            },
            "provider_payload_egress": (
                "APPROVE_EXACT_SIX_FIELD_ALLOWLIST_IN_BOUND_MANIFEST_ONLY"
            ),
            "proposal_and_design": (
                "APPROVE_EXACT_DESIGN_PROPOSAL_IMPLEMENTATION_ARTIFACT_AND_MANIFEST_"
                "DIGESTS"
            ),
            "requested_status": "PROPOSED_NOT_APPROVED_NOT_AUTHORIZED",
        }
        or checked_manifest.proposal_digest
        != "sha256:86979a14c38239fdad84c1f9fa190fc6a49e70fc31a996ae6ee61e844dfaff31"
        or manifest.get("approval_boundary")
        != {
            "actual_execution_evidence": False,
            "authenticated_five_owner_approval": False,
            "one_use_execution_authorization": False,
            "paid_provider_execution": False,
        }
        or checked_manifest.artifact_manifest_digest
        != _domain_digest(_ARTIFACT_MANIFEST_DOMAIN, checked_artifacts)
        or checked_manifest.implementation_digest != implementation_digest()
        or supplied_digest != _domain_digest(_EXECUTION_REQUEST_DOMAIN, digest_source)
    ):
        raise DevelopmentFixtureError(
            "development execution request boundary is invalid"
        )
    return value


def validate_report(value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise DevelopmentFixtureError("development report is not an object")
    required = {
        "authority_ceiling",
        "campaign_manifest_digest",
        "completed_run_count",
        "model_inference_executed",
        "offline_integration_only",
        "paid_execution_occurred",
        "qualifying_execution_ready",
        "recorded_run_count",
        "remaining_run_count",
        "run_results",
        "schema_version",
        "stage",
        "stop_reason",
    }
    if (
        set(value) != required
        or value["authority_ceiling"] != DEVELOPMENT_AUTHORITY_CEILING
        or value["offline_integration_only"] is not True
        or value["model_inference_executed"] is not False
        or value["paid_execution_occurred"] is not False
        or value["qualifying_execution_ready"] is not False
        or value["completed_run_count"] != 40
        or value["recorded_run_count"] != 40
        or value["remaining_run_count"] != 0
        or value["stop_reason"] != "DEVELOPMENT_MATRIX_COMPLETE"
        or type(value["run_results"]) is not list
        or any(item.get("status") != "COMPLETED" for item in value["run_results"])
    ):
        raise DevelopmentFixtureError("development report boundary is invalid")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def run_offline(*, journal_path: Path, report_path: Path | None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="carbon-be4-development-fixture-") as raw:
        tasks, factory, manifest = _build(Path(raw))
        with DevelopmentJournal(
            journal_path, manifest_digest=manifest.content_digest
        ) as journal:
            report = DevelopmentPilotRunner(
                manifest=manifest,
                tasks={item.task_id: item for item in tasks},
                journal=journal,
                transport=DeterministicOfflineTransport(),
                service_factory=factory,
            ).run()
    validated = validate_report(report)
    if report_path is not None:
        _write_json(report_path, validated)
    return validated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--responses", action="store_true")
    mode.add_argument("--check-report", action="store_true")
    mode.add_argument("--check-request", action="store_true")
    mode.add_argument("--write-request", action="store_true")
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--request", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    if args.check_report:
        value = validate_report(json.loads(args.report.read_text(encoding="utf-8")))
        print(value["campaign_manifest_digest"])
        return 0
    if args.check_request:
        value = validate_execution_request(
            json.loads(args.request.read_text(encoding="utf-8"))
        )
        print(value["content_digest"])
        return 0
    with tempfile.TemporaryDirectory(prefix="carbon-be4-development-build-") as raw:
        tasks, factory, manifest = _build(Path(raw))
        artifact_identities = factory.artifact_manifest
        del tasks, factory
        if args.write_request:
            _write_json(
                args.request,
                validate_execution_request(
                    execution_request(manifest, artifact_identities)
                ),
            )
            print(args.request)
            return 0
    if args.responses:
        # Construction is allowed for request preview and offline tests.  The
        # transport has no public admission issuer and dispatch remains closed.
        print(repr(OpenAIResponsesTransport()))
        print("PAID_EXECUTION_BLOCKED")
        return 2
    value = run_offline(journal_path=args.journal, report_path=args.report)
    print(value["campaign_manifest_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
