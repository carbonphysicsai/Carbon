"""Integrated B-07C fixtures over the real B-02B and B-07B owners."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from b02c_fixtures import make_resource_policy_fixture
from b07a_fixtures import digest, discovery_resources
from b07b_fixtures import (
    Catalog,
    Clock,
    Compiler,
    Manifests,
    NoPriors,
    Queue,
    Resources,
)

from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY
from carbon.practice import (
    InMemoryScaffoldProvider,
    MockFixtureBehavior,
    MockPracticePack,
    MockReferenceCapability,
    MockTrainEvalService,
    PracticeDisclosureRule,
    PracticeMeasurementPack,
    PracticeOmission,
    PracticePopulationRelationship,
    PracticeScopeStatement,
    PracticeUncertaintyRule,
    RegisteredMockScaffold,
    VersionedMockPackRegistry,
)
from carbon.research import (
    CompilerEnvironmentRef,
    CompilerIdentity,
    InMemoryResearchTaskProvider,
    NoPriorSelector,
    PairedPracticeTaskSpec,
    PracticeTaskSpec,
    PrivateIdentityRef,
    PublicFindingEvidenceClass,
    PublicResearchFinding,
    ReceiptFindingDefinition,
    ReconstructionRehearsalSpec,
    ResourceCalibrationTaskSpec,
    StartResearchTaskRequest,
)
from carbon.resource_policy.refs import ObservedResourceReceiptRef


def private_ref(kind: str, label: str) -> PrivateIdentityRef:
    value = hashlib.sha256(label.encode("ascii")).hexdigest()
    return PrivateIdentityRef(kind, "sha256:" + value)


class Recorder:
    def __init__(self):
        self.calls = []

    def record_observations(self, attempt, observations, *, completed):
        self.calls.append((attempt, observations, completed))
        payload = attempt.task_id.value.encode() + repr(observations).encode()
        return ObservedResourceReceiptRef(
            attempt.challenge_key,
            content_digest="sha256:" + hashlib.sha256(payload).hexdigest(),
        )


@dataclass(slots=True)
class Fixture:
    provider: InMemoryResearchTaskProvider
    practice: MockTrainEvalService
    scaffold: InMemoryScaffoldProvider
    manifest: object
    info: object
    domain: object
    scope: PracticeScopeStatement
    pack: MockPracticePack
    recorder: Recorder
    queue: Queue
    strategy: dict[str, object]

    def request(self, kind, *, key="b07c-fixture-idempotency-0001"):
        baseline = {**self.strategy, "parameters": {"fixture_sampling_level": 1}}
        intervention = {
            **self.strategy,
            "parameters": {"fixture_sampling_level": 2},
        }
        if kind == "reconstruction":
            task_spec = ReconstructionRehearsalSpec(intervention, None)
            scope_ref = self.scope.to_ref()
        elif kind == "practice":
            task_spec = PracticeTaskSpec(intervention, None)
            scope_ref = self.scope.to_ref()
        elif kind == "paired":
            task_spec = PairedPracticeTaskSpec(baseline, intervention)
            scope_ref = self.scope.to_ref()
        elif kind == "calibration":
            task_spec = ResourceCalibrationTaskSpec(intervention)
            scope_ref = None
        else:
            raise ValueError(kind)
        return StartResearchTaskRequest(
            self.info.challenge_key,
            key,
            task_spec,
            self.info.training_support_ref,
            NoPriorSelector(),
            self.domain.policy_ref,
            self.domain.resource_class_ref,
            scope_ref,
        )


def make_fixture(tmp_path, *, behavior=MockFixtureBehavior.COMPLETE):
    domain = make_resource_policy_fixture(tmp_path)
    source = domain.compile_fixture
    base_info, base_manifest = discovery_resources(challenge_id=source.key.challenge_id)
    info = replace(
        base_info,
        physical_system_ref=source.assembly.physical_system_ref,
        candidate_output_ref=source.assembly.candidate_output_ref,
        training_support_ref=source.assembly.training_support_ref,
    )
    scope = PracticeScopeStatement(
        source.key,
        "synthetic_fixture_scope",
        "1.0",
        PracticePopulationRelationship.SYNTHETIC_FIXTURE_ONLY,
        tuple(PracticeOmission),
        ("FIXTURE_ONLY", "NOT_OFFICIAL_SCOPE"),
    )
    measurement_pack = PracticeMeasurementPack(
        source.key,
        "synthetic_measurement_pack",
        "1.0",
        info.measurement_contract_ref,
        private_ref("measurement_implementation", "measurement"),
        private_ref("practice_measurement_configuration", "configuration"),
        private_ref("practice_measurement_rights", "rights"),
        PracticeUncertaintyRule.OBSERVED_RANGE_ONLY,
        PracticeDisclosureRule.AGGREGATE_ONLY,
        ("NO_OFFICIAL_THRESHOLDS", "NO_SCORE_PACK", "FIXTURE_ONLY"),
    )
    compiler_environment = CompilerEnvironmentRef(
        source.key, content_digest=digest("8")
    )
    pack = MockPracticePack(
        source.key,
        "synthetic_mock_pack",
        "1.0",
        scope.to_ref(),
        measurement_pack,
        compiler_environment,
        private_ref("mock_generator", "generator"),
        private_ref("mock_reference", "reference"),
        MockReferenceCapability.SYNTHETIC_MOCK_ONLY,
        2,
        8,
        behavior,
        ("MOCK_ONLY", "SYNTHETIC_FIXTURE", "NOT_SCIENTIFICALLY_QUALIFIED"),
    )
    compiler_identity = CompilerIdentity(
        SUPPORTED_COMPILER_IDENTITY.compiler_id,
        SUPPORTED_COMPILER_IDENTITY.compiler_version,
        SUPPORTED_COMPILER_IDENTITY.implementation_digest,
        compiler_environment,
    )
    manifest = replace(
        base_manifest,
        challenge_info_ref=info.to_ref(),
        physical_system_ref=info.physical_system_ref,
        candidate_output_ref=info.candidate_output_ref,
        training_support_ref=info.training_support_ref,
        candidate_assembly_ref=source.assembly.to_ref(),
        parameter_catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        compiler_identity=compiler_identity,
        practice_scope_ref=scope.to_ref(),
        practice_pack_refs=(pack.to_ref(),),
        resource_policy_ref=domain.policy_ref,
    )
    registry = VersionedMockPackRegistry(scopes=(scope,), packs=(pack,))
    recorder = Recorder()
    practice = MockTrainEvalService(
        registry=registry,
        interaction_manifest=manifest,
        context_factory=None,
        resource_recorder=recorder,
    )
    strategy = {
        **source.strategy,
        "parameters": {"fixture_sampling_level": 1},
    }
    scaffold = InMemoryScaffoldProvider(
        (
            RegisteredMockScaffold(
                source.key,
                "1.0",
                info.training_support_ref,
                None,
                strategy,
            ),
        )
    )
    definitions = (
        ReceiptFindingDefinition(
            "practice_observed_range",
            PublicResearchFinding(
                "practice_observed_range",
                "Observed aggregate fixture-practice error under the registered mock pack.",
                PublicFindingEvidenceClass.TEST_ONLY,
                info.measurement_contract_ref,
                (0.0, 0.0),
                ("PRACTICE_NON_AUTHORITATIVE", "NOT_A_CONFIDENCE_INTERVAL"),
            ),
        ),
        ReceiptFindingDefinition(
            "paired_practice_observed_difference",
            PublicResearchFinding(
                "paired_practice_observed_difference",
                "Observed paired aggregate difference on common fresh fixture cases.",
                PublicFindingEvidenceClass.TEST_ONLY,
                info.measurement_contract_ref,
                (0.0, 0.0),
                ("PRACTICE_NON_AUTHORITATIVE", "NOT_A_CONFIDENCE_INTERVAL"),
            ),
        ),
    )
    queue = Queue()
    provider = InMemoryResearchTaskProvider(
        challenge_catalog_provider=Catalog(info),
        manifest_provider=Manifests(manifest),
        compilation_resolver=Compiler(domain),
        prior_resolver=NoPriors(),
        resource_resolver=Resources(domain),
        executor=practice,
        task_queue=queue,
        finding_definitions=definitions,
        receipt_limitations=(
            "LOCAL_RESEARCH_ONLY",
            "MOCK_ONLY",
            "NOT_OFFICIAL_EVIDENCE",
            "NOT_SCIENTIFICALLY_QUALIFIED",
        ),
        clock=Clock(),
        worker_implementation_digest=digest("b"),
        environment_digest=digest("c"),
    )
    return Fixture(
        provider,
        practice,
        scaffold,
        manifest,
        info,
        domain,
        scope,
        pack,
        recorder,
        queue,
        strategy,
    )


__all__ = ["Fixture", "Recorder", "make_fixture", "private_ref"]
