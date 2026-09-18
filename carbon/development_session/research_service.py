"""Real public DEVELOPMENT composition of the existing B-07 provider seams."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from carbon import measurement, research
from carbon.construction.compiler import SUPPORTED_COMPILER_IDENTITY

from .contracts import strategy_limits
from .profile import CHALLENGE, canonical, digest
from .research_authoring import measurement_contract, population_and_sampling
from .research_catalog import compile_recipe, public_catalog, research_contracts
from .research_profile import document
from .research_resources import resources
from .research_tasks import PublicDevelopmentResearchTasks, PublicResearchExecutor


class Compiler(research.B02BCompilationProvider):
    def _compile(self, request):
        # Also check actual installed Model/TrainConfig and architecture-specific
        # applicability. The B-07 public service sanitizes rejected internals.
        if (
            request.challenge_key != CHALLENGE
            or request.expected_training_support_ref
            != self._assembly.training_support_ref
        ):
            raise ValueError("research compilation binding differs")
        return getattr(self, "recipe_compiler", compile_recipe)(request.strategy)[0]


class Discovery:
    def __init__(self, info, manifest):
        self.info, self.manifest = info, manifest

    def get_challenge_info(self, key):
        if key != CHALLENGE:
            raise KeyError("challenge unavailable")
        return self.info

    def get_interaction_manifest(self, key):
        if key != CHALLENGE:
            raise KeyError("challenge unavailable")
        return self.manifest


class NoPrior:
    def get_prior(self, request):
        raise KeyError("no registered public prior pack")

    def inspect_prior_alignment(self, request):
        raise KeyError("no registered public prior pack")

    def resolve_prior(self, request):
        raise KeyError("no registered public prior pack")


class Scaffold:
    def __init__(self, contracts):
        self.contracts = contracts

    def get_mock_scaffold(self, request):
        if (
            request.challenge_key != CHALLENGE
            or request.training_support_ref
            != self.contracts.assembly.training_support_ref
            or request.prior_pack_ref is not None
        ):
            raise ValueError("scaffold binding differs")
        strategy = {
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
        return research.MockScaffold(
            research.MockScaffoldRef(
                CHALLENGE, content_digest=digest(canonical(strategy))
            ),
            strategy,
            ("MOCK_ONLY", "UNEXECUTED_TEMPLATE", "NOT_AN_OBSERVED_MODEL_RESULT"),
        )


class ResourceBinding:
    def __init__(self, inspection):
        self.inspection = inspection

    def validate_resource_request(self, key, policy, resource):
        if (key, policy, resource) != (
            CHALLENGE,
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
    if gpu:
        compiler.recipe_compiler = practice.compile
    inspection, forecast, _policy, _resource = resources(contracts, compiler, gpu=gpu)
    if gpu:
        practice.inspection = inspection
    population, sampling = population_and_sampling()
    measurements = measurement_contract()
    measure_ref = measurement.measurement_ref(measurements)
    score = research.PublicScorePolicyRef(
        CHALLENGE,
        content_digest=digest(
            canonical(
                {"score": None, "scope": practice.scope}
                if gpu
                else document()["objective_math"]
            )
        ),
    )
    info = research.ChallengeInfo(
        research.RESEARCH_SCHEMA_VERSION,
        CHALLENGE,
        CHALLENGE.version,
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
        CHALLENGE,
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
            CHALLENGE,
            content_digest=digest(
                canonical(gpu_catalog() if gpu else public_catalog())
            ),
        ),
        contracts.catalog.to_ref(candidate_assembly=contracts.assembly),
        research.CompilerIdentity(
            SUPPORTED_COMPILER_IDENTITY.compiler_id,
            SUPPORTED_COMPILER_IDENTITY.compiler_version,
            SUPPORTED_COMPILER_IDENTITY.implementation_digest,
            research.CompilerEnvironmentRef(
                CHALLENGE,
                content_digest=contracts.assembly.environment_pins[0].content_digest,
            ),
        ),
        (),
        research.PracticeScopeStatementRef(
            CHALLENGE, content_digest=digest(canonical(document()))
        ),
        (),
        research.PublicScaffoldCatalogRef(
            CHALLENGE, content_digest=digest(canonical(scaffold_catalog))
        ),
        research.NoPriorAvailability(),
        inspection.policy_ref,
        research.DisclosurePolicyRef(
            CHALLENGE, content_digest=digest(b"carbon.autoresearch.public-result.v1")
        ),
        research.SUPPORTED_OPERATIONS,
        research.PROTOCOL_LIMITS,
        (),
    )
    discovery = Discovery(info, manifest)
    prior = NoPrior()
    executor = PublicResearchExecutor(
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
        resource_resolver=ResourceBinding(inspection),
        executor=executor,
        task_queue=Queue(),
        worker_implementation_digest=digest(
            canonical(
                {name.name: digest(name.read_bytes()) for name in implementation_files}
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
            Scaffold(contracts),
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
    )
