#!/usr/bin/env python3
"""Run the exact B-E4 40-slot development pilot sequentially.

The default ``--offline`` transport traverses Carbon's real TEST_ONLY research,
practice, construction, submission, reference, measurement, and public-result
services. It replaces only provider inference with a deterministic structured
response transport. ``--responses`` additionally requires a freshly
authenticated DEVELOPMENT-approver issuance, one durable authorization claim, and the
bound external configuration. Neither mode can start calibration or
qualification.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import platform
import sys
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
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
    ControlledOpenAIResponsesTransport,
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
from carbon.gauntlet.development_authority import (
    DEVELOPMENT_APPROVER_GITHUB_LOGIN,
    DEVELOPMENT_APPROVER_GITHUB_USER_ID,
    DEVELOPMENT_RETENTION_SELECTION,
    ControlledDevelopmentAuthorizationStore,
    DevelopmentApprovalUnavailable,
    DevelopmentAuthenticationError,
    DevelopmentAuthorizationBindings,
    DevelopmentAuthorizationError,
    DevelopmentAuthorizationStore,
    provider_identity_digest,
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

DEFAULT_JOURNAL = REPOSITORY_ROOT / ".agent" / "runtime" / "be4-development-v3.sqlite"
DEFAULT_OFFLINE_JOURNAL = (
    REPOSITORY_ROOT / ".carbon-artifacts" / "be4-development-offline-v3.sqlite"
)
DEFAULT_AUTHORIZATION_STORE = (
    REPOSITORY_ROOT / ".agent" / "runtime" / "be4-development-authority-v1.sqlite"
)
DEFAULT_PROCESS_LOCK = (
    REPOSITORY_ROOT / ".agent" / "runtime" / "be4-development-v3.lock"
)
DEFAULT_OFFLINE_REPORT = (
    REPOSITORY_ROOT
    / ".agent"
    / "evidence"
    / "wave_b"
    / "b-e4-development-offline-integration-v3.json"
)
DEFAULT_REAL_REPORT = (
    REPOSITORY_ROOT / ".agent" / "runtime" / "be4-development-provider-report-v2.json"
)
DEFAULT_REQUEST = (
    REPOSITORY_ROOT
    / ".agent"
    / "preregistrations"
    / "B-E4_development_execution_request_v3.json"
)
OWNER_DECISIONS_PATH = (
    REPOSITORY_ROOT
    / ".agent"
    / "preregistrations"
    / "B-E4_development_owner_decisions_v2.json"
)
OWNER_DECISIONS_DIGEST = (
    "sha256:8a4ff68bed32cdd5e757b853a40682760a0f36c5e1b97d7e2898b125e89523ba"
)
DESIGN_DIGEST = (
    "sha256:11a2b6b7e3817cea62631dfbdd0e5b59393d70f0cb9617776b8996ed535d1538"
)
_EXECUTION_REQUEST_DOMAIN = b"carbon.be4.development-execution-request.v3\x00"
_ARTIFACT_MANIFEST_DOMAIN = b"carbon.be4.development-artifacts.v2\x00"
_OWNER_DECISIONS_DOMAIN = b"carbon.be4.development-owner-decisions.v2\x00"
_RETENTION_CONTRACT_DOMAIN = b"carbon.be4.development-retention-contract.v1\x00"
_REAL_REPORT_DOMAIN = b"carbon.be4.development-provider-report.v1\x00"
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


def owner_decision_record() -> dict[str, object]:
    try:
        value = json.loads(OWNER_DECISIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentFixtureError("owner decision record is unavailable") from error
    if type(value) is not dict:
        raise DevelopmentFixtureError("owner decision record is not an object")
    supplied = value.get("content_digest")
    source = dict(value)
    source.pop("content_digest", None)
    if (
        supplied != OWNER_DECISIONS_DIGEST
        or supplied != _domain_digest(_OWNER_DECISIONS_DOMAIN, source)
        or value.get("schema_version") != "carbon.be4.development-owner-decisions.v2"
        or value.get("scope") != "ONE_40_SLOT_NONQUALIFYING_DEVELOPMENT_CAMPAIGN_ONLY"
        or value.get("status")
        != (
            "OWNER_DECISIONS_CORRECTED_RUNTIME_AUTHENTICATION_AND_ONE_USE_"
            "ISSUANCE_REQUIRED"
        )
        or value.get("development_approver_principal")
        != {
            "github_login": DEVELOPMENT_APPROVER_GITHUB_LOGIN,
            "github_user_id": DEVELOPMENT_APPROVER_GITHUB_USER_ID,
        }
    ):
        raise DevelopmentFixtureError("owner decision record is invalid or stale")
    return value


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
            _source_component(
                "canonical_python_runtime",
                (".python-version", "pyproject.toml", "uv.lock"),
            ),
        ],
        "schema_version": "carbon.be4.development-implementation.v2",
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
            "owner_decision_record": owner_decision_record(),
            "implementation_components": implementation_manifest(),
            "profile_prompt_policies": list(development_profile_policy_artifacts()),
            "resource_policy_ref": self._domain.policy_ref.content_digest,
            "schema_version": "carbon.be4.development-artifacts.v2",
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
        owner_decisions_digest=OWNER_DECISIONS_DIGEST,
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
        "owner_decision_record",
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
        value["schema_version"] != "carbon.be4.development-artifacts.v2"
        or not _is_digest(value["candidate_assembly_ref"])
        or not _is_digest(value["parameter_catalog_ref"])
        or not _is_digest(value["resource_policy_ref"])
    ):
        raise DevelopmentFixtureError("artifact owner references are invalid")
    if value["implementation_components"] != implementation_manifest():
        raise DevelopmentFixtureError("implementation source identities are stale")
    if value["owner_decision_record"] != owner_decision_record():
        raise DevelopmentFixtureError("owner decision identity is stale")
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
            value["owner_decisions_digest"],
            tasks,  # type: ignore[arg-type]
            schedule,
            value["content_digest"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise DevelopmentFixtureError("development manifest is invalid") from error
    if parsed.to_json() != value:
        raise DevelopmentFixtureError("development manifest has unsupported fields")
    return parsed


def _retention_contract() -> dict[str, object]:
    value: dict[str, object] = {
        "api_data_training_or_data_sharing_opt_in": False,
        "background": False,
        "provider_prompt_cache_retention_accepted": True,
        "prompt_cache_mode": "EXPLICIT",
        "prompt_cache_ttl": "30m",
        "prompt_cache_ttl_claims_deletion": False,
        "retention_selection": DEVELOPMENT_RETENTION_SELECTION,
        "standard_abuse_monitoring_retention_days_maximum": 30,
        "store": False,
        "zdr_or_modified_abuse_monitoring_required": False,
    }
    value["content_digest"] = _domain_digest(_RETENTION_CONTRACT_DOMAIN, value)
    return value


def _approval_request_value() -> dict[str, object]:
    return {
        "authenticated_issuer": {
            "github_login": DEVELOPMENT_APPROVER_GITHUB_LOGIN,
            "github_user_id": DEVELOPMENT_APPROVER_GITHUB_USER_ID,
            "verification": "FRESH_AUTHENTICATED_GITHUB_REST_USER_REQUIRED",
        },
        "development_monetary_ceiling_usd": "14.42",
        "execution_authorization": (
            "ONE_DURABLE_CLAIM_DEVELOPMENT_STAGE_ONLY_RESTART_PRESERVES_CLAIM"
        ),
        "owner_decisions_digest": OWNER_DECISIONS_DIGEST,
        "owner_role_policy": {
            "independent_multidisciplinary_ratification_claimed": False,
            "principal_count": 1,
            "roles": [
                "RESEARCH",
                "EXACT_PROTOCOL",
                "SCIENCE",
                "STATISTICS",
                "SECURITY",
            ],
        },
        "overall_pilot_ceiling_unchanged_usd": "98.304",
        "provider_account_configuration": {
            "api_key_source": "OPENAI_API_KEY",
            "credential_values_recorded": False,
            "organization_id_source": "OPENAI_ORGANIZATION_ID_OPTIONAL",
            "project_id_source": "OPENAI_PROJECT_ID",
            "raw_project_identity_in_public_evidence": False,
        },
        "provider_payload_egress": ("EXACT_SIX_FIELD_ALLOWLIST_IN_BOUND_MANIFEST_ONLY"),
        "requested_status": (
            "OWNER_DECISIONS_CORRECTED_AWAITING_AUTHENTICATED_ISSUANCE_AND_"
            "BOUND_EXTERNAL_CONFIGURATION"
        ),
    }


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
        "approval_request": _approval_request_value(),
        "artifact_identities": artifact_identities,
        "change_record": {
            "historical_request_digest": (
                "sha256:900997cbbc5ab9cbe4ea6d9f1355cfc4cbca4e11de660cd02c7bee6461f2cd62"
            ),
            "historical_request_preserved": True,
            "historical_owner_decisions_digest": (
                "sha256:6c3bd8cbd13eb7c667b62836dd350c3cc6891223c396e80da708c52409e18a5a"
            ),
            "historical_owner_decisions_preserved": True,
            "reason": (
                "CORRECT_DEVELOPMENT_APPROVER_IDENTITY_AND_REBIND_FINAL_"
                "IMPLEMENTATION_ARTIFACTS"
            ),
        },
        "current_admission_status": (
            "READY_REQUIRES_AUTHENTICATED_DEVELOPMENT_APPROVER_ISSUANCE_AND_"
            "BOUND_CONFIGURATION"
        ),
        "historical_design_digest_non_authority": DESIGN_DIGEST,
        "manifest": manifest.to_json(),
        "owner_decisions": owner_decision_record(),
        "paid_execution_occurred": False,
        "qualifying_execution_ready": False,
        "retention_contract": _retention_contract(),
        "schema_version": "carbon.be4.development-execution-request.v3",
    }
    value["content_digest"] = _domain_digest(_EXECUTION_REQUEST_DOMAIN, value)
    return value


def validate_execution_request(value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise DevelopmentFixtureError("development execution request is not an object")
    required = {
        "approval_request",
        "artifact_identities",
        "change_record",
        "content_digest",
        "current_admission_status",
        "historical_design_digest_non_authority",
        "manifest",
        "owner_decisions",
        "paid_execution_occurred",
        "qualifying_execution_ready",
        "retention_contract",
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
        or value["schema_version"] != "carbon.be4.development-execution-request.v3"
        or value["historical_design_digest_non_authority"] != DESIGN_DIGEST
        or value["current_admission_status"]
        != (
            "READY_REQUIRES_AUTHENTICATED_DEVELOPMENT_APPROVER_ISSUANCE_AND_"
            "BOUND_CONFIGURATION"
        )
        or value["paid_execution_occurred"] is not False
        or value["qualifying_execution_ready"] is not False
        or type(approval) is not dict
        or approval != _approval_request_value()
        or value["change_record"]
        != {
            "historical_request_digest": (
                "sha256:900997cbbc5ab9cbe4ea6d9f1355cfc4cbca4e11de660cd02c7bee6461f2cd62"
            ),
            "historical_request_preserved": True,
            "historical_owner_decisions_digest": (
                "sha256:6c3bd8cbd13eb7c667b62836dd350c3cc6891223c396e80da708c52409e18a5a"
            ),
            "historical_owner_decisions_preserved": True,
            "reason": (
                "CORRECT_DEVELOPMENT_APPROVER_IDENTITY_AND_REBIND_FINAL_"
                "IMPLEMENTATION_ARTIFACTS"
            ),
        }
        or value["owner_decisions"] != owner_decision_record()
        or value["retention_contract"] != _retention_contract()
        or checked_manifest.proposal_digest
        != "sha256:86979a14c38239fdad84c1f9fa190fc6a49e70fc31a996ae6ee61e844dfaff31"
        or manifest.get("approval_boundary")
        != {
            "actual_execution_evidence": False,
            "authenticated_five_owner_approval": False,
            "owner_decisions_recorded": True,
            "one_use_execution_authorization": False,
            "paid_provider_execution": False,
        }
        or checked_manifest.artifact_manifest_digest
        != _domain_digest(_ARTIFACT_MANIFEST_DOMAIN, checked_artifacts)
        or checked_manifest.implementation_digest != implementation_digest()
        or checked_manifest.owner_decisions_digest != OWNER_DECISIONS_DIGEST
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
        "provider_execution_status",
        "provider_operation_summary",
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
        or value["provider_execution_status"] != "SIMULATED_OFFLINE_ONLY"
        or not _valid_operation_summary(value["provider_operation_summary"])
        or value["provider_operation_summary"]["operation_states"]["COMPLETED"] <= 0
        or any(
            value["provider_operation_summary"]["operation_states"][state] != 0
            for state in ("INTENT", "UNKNOWN", "VERIFIED_NOT_EXECUTED")
        )
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


def _valid_operation_summary(value: object) -> bool:
    if type(value) is not dict or set(value) != {
        "confirmed_cost_usd",
        "confirmed_input_tokens",
        "confirmed_output_tokens",
        "conservative_cost_usd",
        "dispatched_operation_count",
        "operation_states",
        "reserved_cost_usd",
        "reserved_input_tokens",
        "reserved_output_tokens",
    }:
        return False
    states = value.get("operation_states")
    if type(states) is not dict or set(states) != {
        "COMPLETED",
        "INTENT",
        "UNKNOWN",
        "VERIFIED_NOT_EXECUTED",
    }:
        return False
    integers = (
        value["confirmed_input_tokens"],
        value["confirmed_output_tokens"],
        value["dispatched_operation_count"],
        value["reserved_input_tokens"],
        value["reserved_output_tokens"],
        *states.values(),
    )
    if any(type(item) is not int or item < 0 for item in integers):
        return False
    try:
        confirmed = Decimal(value["confirmed_cost_usd"])
        reserved = Decimal(value["reserved_cost_usd"])
        conservative = Decimal(value["conservative_cost_usd"])
    except (TypeError, ValueError, ArithmeticError):
        return False
    return (
        confirmed.is_finite()
        and reserved.is_finite()
        and conservative.is_finite()
        and confirmed >= 0
        and reserved >= 0
        and conservative == confirmed + reserved
        and value["dispatched_operation_count"] == sum(states.values())
    )


def _valid_real_run_rows(
    rows: object, *, manifest: DevelopmentCampaignManifest
) -> bool:
    if type(rows) is not list or len(rows) > len(manifest.schedule):
        return False
    provider_keys = {
        "completed_at_utc",
        "content_digest",
        "outcome",
        "raw_response_digest",
        "request_id",
        "requested_model",
        "requested_service_tier",
        "returned_model",
        "returned_service_tier",
        "started_at_utc",
        "usage",
    }
    usage_keys = {
        "cache_write_input_tokens",
        "cached_input_tokens",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
    }
    for slot, row in zip(manifest.schedule[: len(rows)], rows, strict=True):
        if type(row) is not dict:
            return False
        if (
            row.get("arm") != slot.arm.value
            or row.get("authority_ceiling") != DEVELOPMENT_AUTHORITY_CEILING
            or row.get("block_id") != slot.block_id
            or row.get("campaign_manifest_digest") != manifest.content_digest
            or row.get("profile") != slot.profile.value
            or row.get("qualifying_evidence") is not False
            or row.get("run_id") != slot.run_id
            or row.get("run_ordinal") != slot.ordinal
            or row.get("schema_version") != "carbon.be4.development-pilot.v2"
            or row.get("status") not in {"COMPLETED", "STOPPED", "FAILED"}
            or row.get("task_id") != slot.task_id
        ):
            return False
        status = row["status"]
        provider_results = row.get("provider_results")
        if status == "FAILED":
            if (
                type(row.get("failure_kind")) is not str
                or type(row.get("diagnostic")) is not str
                or provider_results is not None
            ):
                return False
            continue
        if type(provider_results) is not list:
            return False
        for provider in provider_results:
            if type(provider) is not dict or set(provider) != provider_keys:
                return False
            usage = provider.get("usage")
            provider_text = (
                provider.get("request_id"),
                provider.get("requested_model"),
                provider.get("requested_service_tier"),
                provider.get("returned_model"),
                provider.get("returned_service_tier"),
                provider.get("started_at_utc"),
                provider.get("completed_at_utc"),
            )
            if (
                type(usage) is not dict
                or set(usage) != usage_keys
                or any(type(item) is not str or not item for item in provider_text)
                or provider["request_id"].startswith("offline-")
                or provider.get("outcome")
                not in {"STRUCTURED", "REFUSAL", "TRUNCATED", "MALFORMED"}
                or not _is_digest(provider.get("content_digest"))
                or not _is_digest(provider.get("raw_response_digest"))
                or any(
                    type(usage[key]) is not int or usage[key] < 0
                    for key in (
                        "cache_write_input_tokens",
                        "cached_input_tokens",
                        "input_tokens",
                        "output_tokens",
                        "reasoning_tokens",
                    )
                )
                or usage["cache_write_input_tokens"] + usage["cached_input_tokens"]
                > usage["input_tokens"]
                or usage["reasoning_tokens"] > usage["output_tokens"]
            ):
                return False
        if status == "COMPLETED":
            if (
                type(row.get("official_endpoint")) is not dict
                or type(row.get("selected_candidate_id")) is not str
            ):
                return False
        elif (
            row.get("official_endpoint") is not None
            or row.get("selected_candidate_id") is not None
        ):
            return False
    return True


def authorization_bindings(
    request: object,
    *,
    journal_binding: str,
    project_id: str,
    organization_id: str | None,
) -> DevelopmentAuthorizationBindings:
    checked = validate_execution_request(request)
    manifest = checked["manifest"]
    retention = checked["retention_contract"]
    assert type(manifest) is dict and type(retention) is dict
    return DevelopmentAuthorizationBindings(
        checked["content_digest"],
        manifest["content_digest"],
        manifest["proposal_digest"],
        manifest["implementation_digest"],
        manifest["artifact_manifest_digest"],
        checked["owner_decisions"]["content_digest"],
        retention["content_digest"],
        journal_binding,
        provider_identity_digest(project_id, kind="OPENAI_PROJECT_ID"),
        (
            None
            if organization_id is None
            else provider_identity_digest(
                organization_id, kind="OPENAI_ORGANIZATION_ID"
            )
        ),
        Decimal("14.42"),
    )


@contextmanager
def _campaign_process_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise DevelopmentApprovalUnavailable(
                "another process already owns the development campaign"
            ) from error
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _real_report(
    report: dict[str, object],
    *,
    request: dict[str, Any],
    authorization_record: dict[str, object],
    project_id_digest: str,
) -> dict[str, object]:
    if report.get("offline_integration_only") is not False:
        raise DevelopmentFixtureError("real report cannot relabel offline evidence")
    summary = report.get("provider_operation_summary")
    if not _valid_operation_summary(summary):
        raise DevelopmentFixtureError("real provider operation summary is invalid")
    assert type(summary) is dict
    states = summary["operation_states"]
    assert type(states) is dict
    if states["COMPLETED"] > 0:
        project_access = "CONFIRMED_BY_ACCEPTED_PROVIDER_RESPONSE"
    elif states["INTENT"] + states["UNKNOWN"] > 0:
        project_access = "UNRECONCILED_AFTER_DISPATCH"
    else:
        project_access = "NOT_CONFIRMED_NO_ACCEPTED_PROVIDER_RESPONSE"
    value = dict(report)
    value.update(
        {
            "authorization": authorization_record,
            "content_digest": None,
            "execution_request_digest": request["content_digest"],
            "provider_project": {
                "access_status": project_access,
                "project_id_digest": project_id_digest,
                "raw_project_id_recorded": False,
            },
            "report_schema_version": ("carbon.be4.development-provider-report.v1"),
            "retention_contract_digest": request["retention_contract"][
                "content_digest"
            ],
        }
    )
    value["content_digest"] = _domain_digest(
        _REAL_REPORT_DOMAIN,
        {key: item for key, item in value.items() if key != "content_digest"},
    )
    return value


def _valid_live_authorization_record(
    value: object,
    *,
    request: dict[str, Any],
    project_id_digest: str,
) -> bool:
    if type(value) is not dict or set(value) != {
        "approval_act_digest",
        "authorization_id",
        "bindings",
        "bindings_digest",
        "environment",
        "expires_at_utc",
        "independent_multidisciplinary_ratification_claimed",
        "issued_at_utc",
        "issuer_github_login",
        "issuer_github_user_id",
        "journal_binding",
        "monetary_ceiling_usd",
        "organization_id_digest",
        "principal_count",
        "project_id_digest",
        "request_digest",
        "stage",
        "state",
        "terminal_report_digest",
    }:
        return False
    try:
        bindings = DevelopmentAuthorizationBindings.from_json(value["bindings"])
    except DevelopmentAuthorizationError:
        return False
    manifest = request["manifest"]
    retention = request["retention_contract"]
    if type(manifest) is not dict or type(retention) is not dict:
        return False
    return (
        type(value["authorization_id"]) is str
        and value["authorization_id"].startswith("be4-development-")
        and _is_digest(value["approval_act_digest"])
        and value["bindings_digest"] == bindings.content_digest
        and value["environment"] == "LIVE_OPENAI_RESPONSES"
        and type(value["issued_at_utc"]) is str
        and bool(value["issued_at_utc"])
        and type(value["expires_at_utc"]) is str
        and bool(value["expires_at_utc"])
        and value["independent_multidisciplinary_ratification_claimed"] is False
        and value["issuer_github_login"] == DEVELOPMENT_APPROVER_GITHUB_LOGIN
        and value["issuer_github_user_id"] == DEVELOPMENT_APPROVER_GITHUB_USER_ID
        and value["journal_binding"] == bindings.journal_binding
        and value["monetary_ceiling_usd"] == "14.42"
        and value["organization_id_digest"] == bindings.organization_id_digest
        and value["principal_count"] == 1
        and value["project_id_digest"] == project_id_digest
        and value["project_id_digest"] == bindings.project_id_digest
        and value["request_digest"] == request["content_digest"]
        and value["request_digest"] == bindings.request_digest
        and value["stage"] == "DEVELOPMENT"
        and value["stage"] == bindings.stage
        and value["state"] == "CLAIMED"
        and value["terminal_report_digest"] is None
        and bindings.campaign_manifest_digest == manifest["content_digest"]
        and bindings.proposal_digest == manifest["proposal_digest"]
        and bindings.implementation_digest == manifest["implementation_digest"]
        and bindings.artifact_manifest_digest == manifest["artifact_manifest_digest"]
        and bindings.owner_decisions_digest
        == request["owner_decisions"]["content_digest"]
        and bindings.retention_contract_digest == retention["content_digest"]
    )


def validate_real_report(value: object, *, request: object) -> dict[str, Any]:
    checked_request = validate_execution_request(request)
    if type(value) is not dict:
        raise DevelopmentFixtureError("real development report is not an object")
    base_keys = {
        "authority_ceiling",
        "campaign_manifest_digest",
        "completed_run_count",
        "model_inference_executed",
        "offline_integration_only",
        "paid_execution_occurred",
        "provider_execution_status",
        "provider_operation_summary",
        "qualifying_execution_ready",
        "recorded_run_count",
        "remaining_run_count",
        "run_results",
        "schema_version",
        "stage",
        "stop_reason",
    }
    required = base_keys | {
        "authorization",
        "content_digest",
        "execution_request_digest",
        "provider_project",
        "report_schema_version",
        "retention_contract_digest",
    }
    manifest = checked_request["manifest"]
    checked_manifest = _validated_manifest(manifest)
    summary = value.get("provider_operation_summary")
    authorization = value.get("authorization")
    project = value.get("provider_project")
    rows = value.get("run_results")
    if not _valid_operation_summary(summary):
        raise DevelopmentFixtureError("real provider operation summary is invalid")
    assert type(summary) is dict
    states = summary["operation_states"]
    assert type(states) is dict
    confirmed = states["COMPLETED"]
    unresolved = states["INTENT"] + states["UNKNOWN"]
    expected_status = (
        "CONFIRMED"
        if confirmed and not unresolved
        else (
            "CONFIRMED_WITH_UNRECONCILED_DISPATCH"
            if confirmed and unresolved
            else "POSSIBLE_UNRECONCILED" if unresolved else "NO_PROVIDER_INFERENCE"
        )
    )
    expected_inference: bool | None = (
        True if confirmed else None if unresolved else False
    )
    expected_project_access = (
        "CONFIRMED_BY_ACCEPTED_PROVIDER_RESPONSE"
        if confirmed
        else (
            "UNRECONCILED_AFTER_DISPATCH"
            if unresolved
            else "NOT_CONFIRMED_NO_ACCEPTED_PROVIDER_RESPONSE"
        )
    )
    stop_reasons = {
        "DEVELOPMENT_MATRIX_COMPLETE",
        "DEVELOPMENT_STAGE_DEADLINE_EXHAUSTED",
        "RUNNER_OR_LIFECYCLE_FAILURE",
        "UNRESOLVED_PROVIDER_DISPATCH",
    }
    if (
        set(value) != required
        or value["report_schema_version"] != "carbon.be4.development-provider-report.v1"
        or value["authority_ceiling"] != DEVELOPMENT_AUTHORITY_CEILING
        or value["schema_version"] != "carbon.be4.development-pilot.v2"
        or value["stage"] != "DEVELOPMENT"
        or value["offline_integration_only"] is not False
        or value["qualifying_execution_ready"] is not False
        or value["campaign_manifest_digest"] != manifest["content_digest"]
        or value["execution_request_digest"] != checked_request["content_digest"]
        or value["retention_contract_digest"]
        != checked_request["retention_contract"]["content_digest"]
        or value["provider_execution_status"] != expected_status
        or value["model_inference_executed"] is not expected_inference
        or value["paid_execution_occurred"] is not expected_inference
        or type(value["recorded_run_count"]) is not int
        or not 0 <= value["recorded_run_count"] <= 40
        or value["remaining_run_count"] != 40 - value["recorded_run_count"]
        or type(value["completed_run_count"]) is not int
        or not 0 <= value["completed_run_count"] <= value["recorded_run_count"]
        or not _valid_real_run_rows(rows, manifest=checked_manifest)
        or len(rows) != value["recorded_run_count"]
        or sum(item["status"] == "COMPLETED" for item in rows)
        != value["completed_run_count"]
        or value["stop_reason"] not in stop_reasons
        or (unresolved > 0) != (value["stop_reason"] == "UNRESOLVED_PROVIDER_DISPATCH")
        or Decimal(summary["conservative_cost_usd"]) > Decimal("14.42")
        or type(project) is not dict
        or set(project)
        != {"access_status", "project_id_digest", "raw_project_id_recorded"}
        or project["raw_project_id_recorded"] is not False
        or not _is_digest(project["project_id_digest"])
        or project["access_status"] != expected_project_access
        or not _valid_live_authorization_record(
            authorization,
            request=checked_request,
            project_id_digest=project["project_id_digest"],
        )
    ):
        raise DevelopmentFixtureError("real development report boundary is invalid")
    source = dict(value)
    supplied = source.pop("content_digest")
    if supplied != _domain_digest(_REAL_REPORT_DOMAIN, source):
        raise DevelopmentFixtureError("real development report digest is invalid")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _verify_canonical_runtime() -> None:
    try:
        expected = (
            (REPOSITORY_ROOT / ".python-version").read_text(encoding="utf-8").strip()
        )
    except (OSError, UnicodeError) as error:
        raise DevelopmentFixtureError(
            "canonical Python runtime is unavailable"
        ) from error
    if not expected or platform.python_version() != expected:
        raise DevelopmentFixtureError(
            "live development execution requires the frozen canonical Python runtime"
        )


def _current_request_from_source(root: Path) -> tuple[
    tuple[DevelopmentTask, DevelopmentTask],
    FixtureServiceFactory,
    DevelopmentCampaignManifest,
    dict[str, Any],
]:
    tasks, factory, manifest = _build(root)
    request = validate_execution_request(
        execution_request(manifest, factory.artifact_manifest)
    )
    return tasks, factory, manifest, request


def _load_frozen_request(path: Path, *, expected: dict[str, Any]) -> dict[str, Any]:
    try:
        supplied = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentFixtureError(
            "frozen execution request is unavailable"
        ) from error
    checked = validate_execution_request(supplied)
    if checked != expected:
        raise DevelopmentFixtureError(
            "frozen execution request does not bind the current implementation"
        )
    return checked


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


def run_controlled_responses_fixture(
    *,
    endpoint: str,
    journal_path: Path,
    authorization_store_path: Path,
    report_path: Path | None,
) -> dict[str, Any]:
    """Exercise the real HTTP body/parser path with loopback-only authority."""

    project_id = "fixture-project-never-valid-for-live-provider"
    with tempfile.TemporaryDirectory(prefix="carbon-be4-controlled-fixture-") as raw:
        tasks, factory, manifest, request = _current_request_from_source(Path(raw))
        with (
            DevelopmentJournal(
                journal_path, manifest_digest=manifest.content_digest
            ) as journal,
            ControlledDevelopmentAuthorizationStore(
                authorization_store_path
            ) as authorization_store,
        ):
            journal_binding = journal.authorization_binding(request["content_digest"])
            bindings = authorization_bindings(
                request,
                journal_binding=journal_binding,
                project_id=project_id,
                organization_id=None,
            )
            authorization_id = authorization_store.issue_fixture(bindings)
            admission = authorization_store.claim_fixture(
                authorization_id,
                bindings=bindings,
                journal_binding=journal_binding,
            )
            journal.bind_execution_authorization(
                authorization_id=authorization_id,
                execution_request_digest=bindings.request_digest,
                provider_project_digest=bindings.project_id_digest,
                journal_binding=journal_binding,
            )
            report = DevelopmentPilotRunner(
                manifest=manifest,
                tasks={item.task_id: item for item in tasks},
                journal=journal,
                transport=ControlledOpenAIResponsesTransport(
                    endpoint=endpoint,
                    api_key="fixture-key-never-valid-for-live-provider",
                    project_id=project_id,
                    organization_id=None,
                    admission=admission,
                ),
                service_factory=factory,
            ).run()
            validated = validate_report(report)
            authorization_store.finalize_fixture(
                admission,
                report_digest=_domain_digest(_REAL_REPORT_DOMAIN, validated),
            )
    if report_path is not None:
        _write_json(report_path, validated)
    return validated


def run_responses(
    *,
    request_path: Path,
    journal_path: Path,
    report_path: Path,
    authorization_store_path: Path,
    process_lock_path: Path,
    approve_exact_request_digest: str | None,
) -> dict[str, Any]:
    """Run or safely resume the one authorized real DEVELOPMENT campaign."""

    expected_runtime_paths = (
        (journal_path, DEFAULT_JOURNAL),
        (report_path, DEFAULT_REAL_REPORT),
        (authorization_store_path, DEFAULT_AUTHORIZATION_STORE),
        (process_lock_path, DEFAULT_PROCESS_LOCK),
    )
    if any(
        actual.resolve() != expected.resolve()
        for actual, expected in expected_runtime_paths
    ):
        raise DevelopmentApprovalUnavailable(
            "live execution must use the repository's single durable runtime paths"
        )
    _verify_canonical_runtime()
    api_key = os.environ.get("OPENAI_API_KEY")
    project_id = os.environ.get("OPENAI_PROJECT_ID")
    organization_id = os.environ.get("OPENAI_ORGANIZATION_ID")
    if not api_key or not project_id:
        raise DevelopmentApprovalUnavailable(
            "OPENAI_API_KEY and OPENAI_PROJECT_ID must be supplied outside Carbon"
        )
    with tempfile.TemporaryDirectory(prefix="carbon-be4-live-fixture-") as raw:
        tasks, factory, manifest, expected_request = _current_request_from_source(
            Path(raw)
        )
        request = _load_frozen_request(request_path, expected=expected_request)
        with (
            _campaign_process_lock(process_lock_path),
            DevelopmentJournal(
                journal_path, manifest_digest=manifest.content_digest
            ) as journal,
            DevelopmentAuthorizationStore(
                authorization_store_path
            ) as authorization_store,
        ):
            journal_binding = journal.authorization_binding(request["content_digest"])
            bindings = authorization_bindings(
                request,
                journal_binding=journal_binding,
                project_id=project_id,
                organization_id=organization_id,
            )
            if approve_exact_request_digest is not None:
                authorization_id = authorization_store.issue(
                    bindings,
                    approve_exact_request_digest=approve_exact_request_digest,
                )
            else:
                authorization_id = authorization_store.existing_authorization_id(
                    bindings
                )
            admission = authorization_store.claim(
                authorization_id,
                bindings=bindings,
                journal_binding=journal_binding,
            )
            journal.bind_execution_authorization(
                authorization_id=authorization_id,
                execution_request_digest=bindings.request_digest,
                provider_project_digest=bindings.project_id_digest,
                journal_binding=journal_binding,
            )
            report = DevelopmentPilotRunner(
                manifest=manifest,
                tasks={item.task_id: item for item in tasks},
                journal=journal,
                transport=OpenAIResponsesTransport(
                    api_key=api_key,
                    project_id=project_id,
                    organization_id=organization_id,
                    admission=admission,
                ),
                service_factory=factory,
            ).run()
            real_report = validate_real_report(
                _real_report(
                    report,
                    request=request,
                    authorization_record=authorization_store.public_record(
                        authorization_id
                    ),
                    project_id_digest=bindings.project_id_digest,
                ),
                request=request,
            )
            _write_json(report_path, real_report)
            states = real_report["provider_operation_summary"]["operation_states"]
            authorization_store.finalize(
                admission,
                report_digest=real_report["content_digest"],
                unresolved=bool(states["INTENT"] or states["UNKNOWN"]),
            )
    return real_report


def revoke_responses_authorization(*, request_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="carbon-be4-revoke-fixture-") as raw:
        _tasks, _factory, _manifest, expected_request = _current_request_from_source(
            Path(raw)
        )
        request = _load_frozen_request(request_path, expected=expected_request)
        with DevelopmentAuthorizationStore(DEFAULT_AUTHORIZATION_STORE) as store:
            store.revoke_request_digest(request["content_digest"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--responses", action="store_true")
    mode.add_argument("--controlled-responses-fixture", action="store_true")
    mode.add_argument("--check-report", action="store_true")
    mode.add_argument("--check-real-report", action="store_true")
    mode.add_argument("--check-request", action="store_true")
    mode.add_argument("--write-request", action="store_true")
    mode.add_argument("--revoke-responses-authorization", action="store_true")
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--controlled-endpoint")
    parser.add_argument("--controlled-authorization-store", type=Path)
    parser.add_argument("--authorize-exact-request-digest")
    args = parser.parse_args(argv)
    if args.check_report:
        report_path = args.report or DEFAULT_OFFLINE_REPORT
        value = validate_report(json.loads(report_path.read_text(encoding="utf-8")))
        print(value["campaign_manifest_digest"])
        return 0
    if args.check_real_report:
        report_path = args.report or DEFAULT_REAL_REPORT
        request = json.loads(args.request.read_text(encoding="utf-8"))
        value = validate_real_report(
            json.loads(report_path.read_text(encoding="utf-8")), request=request
        )
        print(value["content_digest"])
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
        try:
            value = run_responses(
                request_path=args.request,
                journal_path=args.journal or DEFAULT_JOURNAL,
                report_path=args.report or DEFAULT_REAL_REPORT,
                authorization_store_path=DEFAULT_AUTHORIZATION_STORE,
                process_lock_path=DEFAULT_PROCESS_LOCK,
                approve_exact_request_digest=args.authorize_exact_request_digest,
            )
        except (
            DevelopmentApprovalUnavailable,
            DevelopmentAuthenticationError,
            DevelopmentAuthorizationError,
            DevelopmentFixtureError,
        ) as error:
            print(f"PAID_EXECUTION_BLOCKED: {error}")
            return 2
        print(value["content_digest"])
        return 0
    if args.revoke_responses_authorization:
        try:
            revoke_responses_authorization(request_path=args.request)
        except (
            DevelopmentApprovalUnavailable,
            DevelopmentAuthenticationError,
            DevelopmentAuthorizationError,
            DevelopmentFixtureError,
        ) as error:
            print(f"REVOCATION_BLOCKED: {error}")
            return 2
        print("DEVELOPMENT_AUTHORIZATION_REVOKED")
        return 0
    if args.controlled_responses_fixture:
        if args.controlled_endpoint is None:
            parser.error(
                "--controlled-responses-fixture requires --controlled-endpoint"
            )
        value = run_controlled_responses_fixture(
            endpoint=args.controlled_endpoint,
            journal_path=args.journal
            or REPOSITORY_ROOT
            / ".carbon-artifacts"
            / "be4-development-controlled-v2.sqlite",
            authorization_store_path=args.controlled_authorization_store
            or REPOSITORY_ROOT
            / ".carbon-artifacts"
            / "be4-development-controlled-authority-v1.sqlite",
            report_path=args.report,
        )
        print(value["campaign_manifest_digest"])
        return 0
    value = run_offline(
        journal_path=args.journal or DEFAULT_OFFLINE_JOURNAL,
        report_path=args.report or DEFAULT_OFFLINE_REPORT,
    )
    print(value["campaign_manifest_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
