"""Real public DEVELOPMENT composition of the existing B-07 provider seams."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from carbon import measurement, research
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY

from .contracts import strategy_limits
from .profile import CHALLENGE, canonical, digest
from .research_authoring import measurement_contract, population_and_sampling
from .research_catalog import (
    RecipeRejected,
    compile_recipe,
    public_catalog,
    research_contracts,
)
from .research_profile import document
from .research_resources import resources
from .research_tasks import PublicDevelopmentResearchTasks, PublicResearchExecutor


class Compiler(research.B02BCompilationProvider):
    def _compile(self, request):
        # Also check actual installed Model/TrainConfig and architecture-specific
        # applicability. The B-07 public service sanitizes rejected internals.
        if (
            request.challenge_key != getattr(self, "challenge_key", CHALLENGE)
            or request.expected_training_support_ref
            != self._assembly.training_support_ref
        ):
            raise ValueError("research compilation binding differs")
        try:
            return getattr(self, "recipe_compiler", compile_recipe)(request.strategy)[0]
        except RecipeRejected as rejected:
            # Returned, not raised: the protocol reports each named issue as a
            # rejected compile result instead of a generic internal failure.
            return rejected.rejected


class Discovery:
    def __init__(self, info, manifest, key=CHALLENGE):
        self.info, self.manifest, self.key = info, manifest, key

    def get_challenge_info(self, key):
        if key != self.key:
            raise KeyError("challenge unavailable")
        return self.info

    def get_interaction_manifest(self, key):
        if key != self.key:
            raise KeyError("challenge unavailable")
        return self.manifest


class NoPrior:
    def get_prior(self, request):
        raise KeyError("no registered public prior pack")

    def inspect_prior_alignment(self, request):
        raise KeyError("no registered public prior pack")

    def resolve_prior(self, request):
        raise KeyError("no registered public prior pack")


#: The Burgers unexecuted template, unchanged.
BURGERS_SCAFFOLD = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE.challenge_id,
    "backbone": "fno",
    "parameters": {
        "steps": 512,
        "width": 24,
        "depth": 2,
        "n_modes": 16,
        "hard_initial_condition": True,
        "enforce_mean": True,
    },
}


class Scaffold:
    def __init__(self, contracts, strategy=None, key=CHALLENGE):
        self.contracts = contracts
        self.strategy = BURGERS_SCAFFOLD if strategy is None else strategy
        self.key = key

    def get_mock_scaffold(self, request):
        if (
            request.challenge_key != self.key
            or request.training_support_ref
            != self.contracts.assembly.training_support_ref
            or request.prior_pack_ref is not None
        ):
            raise ValueError("scaffold binding differs")
        strategy = json.loads(canonical(self.strategy))
        return research.MockScaffold(
            research.MockScaffoldRef(
                self.key, content_digest=digest(canonical(strategy))
            ),
            strategy,
            ("MOCK_ONLY", "UNEXECUTED_TEMPLATE", "NOT_AN_OBSERVED_MODEL_RESULT"),
        )


class ResourceBinding:
    def __init__(self, inspection, key=CHALLENGE):
        self.inspection, self.key = inspection, key

    def validate_resource_request(self, key, policy, resource):
        if (key, policy, resource) != (
            self.key,
            self.inspection.policy_ref,
            self.inspection.resource_class_ref,
        ):
            raise ValueError("resource binding differs")


class Queue:
    def enqueue(self, task):
        # Durable provider owns QUEUED state. The supervised tool bridge runs it
        # once and waits without calling the model for status polls.
        pass


@dataclass
class ResearchComposition:
    service: research.LocalResearchService
    tasks: PublicDevelopmentResearchTasks
    executor: PublicResearchExecutor
    discovery: Discovery
    inspection: object
    contracts: object
    population: object
    sampling: object
    measurements: object
    #: The Challenge this composition serves. Every request it answers must
    #: name exactly this key; there is no fallback to another Challenge.
    challenge: object = CHALLENGE


@dataclass(frozen=True)
class ChallengeParts:
    """What one Challenge contributes to the shared B-07 composition.

    The composition itself - compiler seam, discovery, scaffold, resource
    binding, durable tasks, executor and the twelve operations - is shared.
    A Challenge supplies only these, from its own executable registrations.
    """

    key: object
    contracts: object
    recipe_compiler: object
    #: compiler -> (inspection, forecast, policy, resource class)
    resources: object
    population: object
    sampling: object
    measurements: object
    score_document: object
    strategy_schema: object
    practice_scope: object
    scaffold_catalog: object
    scaffold_strategy: dict
    implementation_files: tuple
    disclosure: bytes = b"carbon.autoresearch.public-result.v1"
    on_inspection: object = None


def make_research_service(
    *,
    root,
    ledger,
    owner,
    image,
    public_material,
    practice,
    julia_image=None,
    cleanup_only=False,
    demand=None,
):
    from .gpu_research import PublicGPUPractice, gpu_catalog
    from .julia_research import JuliaPublicMaterial

    gpu = type(practice) is PublicGPUPractice
    if gpu and (practice.data.ledger is not ledger or practice.data.owner != owner):
        raise ValueError("GPU callback principal/ledger differs")
    scaffold_catalog = (
        public_material.catalogue()
        if type(public_material) is JuliaPublicMaterial
        else public_catalog()
    )
    implementation_files = sorted(Path(__file__).parent.glob("research_*.py"))
    if type(public_material) is JuliaPublicMaterial:
        implementation_files.append(Path(__file__).with_name("julia_research.py"))
    if julia_image is not None:
        implementation_files.append(Path(__file__).with_name("julia_analysis.py"))
    if gpu:
        from .advection_research import PublicAdvectionMaterial
        from .julia_envelope import JuliaEnvelopeMaterial

        scientific_catalogue = (
            public_material.catalogue()
            if type(public_material) in (JuliaPublicMaterial, JuliaEnvelopeMaterial)
            else None
        )
        if type(public_material) is PublicAdvectionMaterial:
            scientific_catalogue = {"scientific_tasks": [public_material.scope]}
        scaffold_catalog = {
            "schema": "carbon.gpu-scientific-scaffold.v1",
            "recipes": gpu_catalog(),
            "scientific_catalogue": scientific_catalogue,
        }
        practice.scaffold_digest = digest(canonical(scaffold_catalog))
        implementation_files.append(Path(__file__).with_name("gpu_research.py"))
    contracts = practice.contracts if gpu else research_contracts()
    population, sampling = population_and_sampling()
    parts = ChallengeParts(
        key=CHALLENGE,
        contracts=contracts,
        recipe_compiler=practice.compile if gpu else compile_recipe,
        resources=lambda compiler: resources(contracts, compiler, gpu=gpu),
        population=population,
        sampling=sampling,
        measurements=measurement_contract(),
        score_document=(
            {"score": None, "scope": practice.scope}
            if gpu
            else document()["objective_math"]
        ),
        strategy_schema=gpu_catalog() if gpu else public_catalog(),
        practice_scope=document(),
        scaffold_catalog=scaffold_catalog,
        scaffold_strategy=BURGERS_SCAFFOLD,
        implementation_files=tuple(implementation_files),
        on_inspection=(
            (lambda inspection: setattr(practice, "inspection", inspection))
            if gpu
            else None
        ),
    )
    return compose_research_service(
        parts,
        root=root,
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=public_material,
        practice=practice,
        julia_image=julia_image,
        cleanup_only=cleanup_only,
        demand=demand,
    )


def compose_research_service(
    parts,
    *,
    root,
    ledger,
    owner,
    image,
    public_material,
    practice,
    julia_image=None,
    cleanup_only=False,
    demand=None,
):
    """The shared B-07 composition over one Challenge's parts."""
    if type(parts) is not ChallengeParts:
        raise TypeError("ChallengeParts are required")
    key, contracts = parts.key, parts.contracts
    compiler = Compiler(
        candidate_assembly=contracts.assembly,
        candidate_assembly_ref=contracts.assembly.to_ref(),
        parameter_catalog=contracts.catalog,
        parameter_catalog_ref=contracts.catalog.to_ref(
            candidate_assembly=contracts.assembly
        ),
        authoring_origin=contracts.origin,
        authoring_artifacts=contracts.artifacts,
        compiler_identity=SUPPORTED_COMPILER_IDENTITY,
        strategy_limits=strategy_limits(),
    )
    compiler.recipe_compiler = parts.recipe_compiler
    compiler.challenge_key = key
    inspection, forecast, _policy, _resource = parts.resources(compiler)
    if parts.on_inspection is not None:
        parts.on_inspection(inspection)
    population, sampling = parts.population, parts.sampling
    measurements = parts.measurements
    measure_ref = measurement.measurement_ref(measurements)
    score = research.PublicScorePolicyRef(
        key, content_digest=digest(canonical(parts.score_document))
    )
    info = research.ChallengeInfo(
        research.RESEARCH_SCHEMA_VERSION,
        key,
        key.version,
        contracts.assembly.physical_system_ref,
        contracts.assembly.candidate_output_ref,
        population.to_ref(),
        sampling.to_ref(),
        contracts.assembly.training_support_ref,
        measure_ref,
        score,
        research.DisclosureClass.PUBLIC_RESEARCH,
    )
    manifest = research.InteractionManifest(
        research.RESEARCH_SCHEMA_VERSION,
        key,
        info.to_ref(),
        info.physical_system_ref,
        info.candidate_output_ref,
        info.instance_distribution_ref,
        info.sampling_plan_ref,
        info.training_support_ref,
        info.measurement_contract_ref,
        info.public_score_policy_ref,
        contracts.assembly.to_ref(),
        research.StrategySchemaRef(
            key, content_digest=digest(canonical(parts.strategy_schema))
        ),
        contracts.catalog.to_ref(candidate_assembly=contracts.assembly),
        research.CompilerIdentity(
            SUPPORTED_COMPILER_IDENTITY.compiler_id,
            SUPPORTED_COMPILER_IDENTITY.compiler_version,
            SUPPORTED_COMPILER_IDENTITY.implementation_digest,
            research.CompilerEnvironmentRef(
                key,
                content_digest=contracts.assembly.environment_pins[0].content_digest,
            ),
        ),
        (),
        research.PracticeScopeStatementRef(
            key, content_digest=digest(canonical(parts.practice_scope))
        ),
        (),
        research.PublicScaffoldCatalogRef(
            key, content_digest=digest(canonical(parts.scaffold_catalog))
        ),
        research.NoPriorAvailability(),
        inspection.policy_ref,
        research.DisclosurePolicyRef(key, content_digest=digest(parts.disclosure)),
        research.SUPPORTED_OPERATIONS,
        research.PROTOCOL_LIMITS,
        (),
    )
    discovery = Discovery(info, manifest, key)
    prior = NoPrior()
    executor = PublicResearchExecutor(
        demand=demand,
        cleanup_only=cleanup_only,
        julia_image=julia_image,
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=public_material,
        practice=practice,
    )
    tasks = PublicDevelopmentResearchTasks(
        root=root,
        requester=owner,
        challenge_catalog_provider=discovery,
        manifest_provider=discovery,
        compilation_resolver=compiler,
        prior_resolver=prior,
        resource_resolver=ResourceBinding(inspection, key),
        executor=executor,
        task_queue=Queue(),
        worker_implementation_digest=digest(
            canonical(
                {
                    name.name: digest(name.read_bytes())
                    for name in parts.implementation_files
                }
            )
        ),
        environment_digest=contracts.assembly.environment_pins[0].content_digest,
        receipt_limitations=(
            "LOCAL_RESEARCH_ONLY",
            "NOT_OFFICIAL_EVIDENCE",
            "NOT_SCIENTIFICALLY_QUALIFIED",
            "NO_LEARNED_AGGREGATION_AUTHORITY",
        ),
    )
    executor.request_resolver = tasks.request_for_execution
    service = research.LocalResearchService(
        research.ExternalPublicResearchContext(
            discovery,
            discovery,
            prior,
            Scaffold(contracts, parts.scaffold_strategy, key),
            research.A2ValidationProvider(),
            compiler,
            prior,
            inspection,
            forecast,
            tasks,
        )
    )
    return ResearchComposition(
        service,
        tasks,
        executor,
        discovery,
        inspection,
        contracts,
        population,
        sampling,
        measurements,
        key,
    )
