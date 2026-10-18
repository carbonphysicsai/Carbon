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


#: The B-02B compiler's own code for a strategy naming another Challenge
#: than the one compiled for (`construction.compiler.compile_strategy`).
CHALLENGE_MISMATCH = "strategy.challenge_mismatch"


def names_another_challenge(strategy, challenge):
    """Whether `strategy` names, as a well-formed id, a Challenge other than
    `challenge`. A missing or malformed id is not this: the contract's own
    structural check names it."""
    from carbon.schema.strategy import _IDENTIFIER

    named = strategy.get("challenge_id") if type(strategy) is dict else None
    return (
        type(named) is str
        and _IDENTIFIER.fullmatch(named) is not None
        and named != challenge
    )


def submission_issues(strategy, challenge):
    """Every issue the submission path refuses `strategy` with, for the
    Challenge `challenge`, or () when it would admit it.

    The same compile a submission meets (`challenge_contracts.compile_submission`):
    structural validation, the named Challenge's contract
    (`validate_for_challenge`), then that Challenge's own compiler and its
    backend rules - each issue with the code and path that path names. A
    strategy naming another Challenge is refused as the B-02B compiler
    refuses it (`strategy.challenge_mismatch`), never compiled under that
    other contract. A dry run: it compiles in memory and dispatches, admits,
    scores and stores nothing."""
    from carbon.construction.compiler import _ISSUE_MESSAGES as COMPILE_MESSAGES
    from carbon.construction.compiler import CompileIssue
    from carbon.reconstruction.challenge_contracts import (
        SubmissionRefused,
        compile_submission,
    )

    if names_another_challenge(strategy, challenge):
        return (
            CompileIssue(
                CHALLENGE_MISMATCH,
                "/challenge_id",
                COMPILE_MESSAGES[CHALLENGE_MISMATCH],
            ),
        )
    try:
        compile_submission(strategy)
    except SubmissionRefused as refused:
        return refused.issues
    except RecipeRejected as rejected:
        return rejected.rejected.issues
    return ()


class ChallengeContractValidation:
    """dry_validate as the named Challenge's submission path answers it
    (RESEARCH-TOOL-USABILITY-01): the issues `submission_issues` names, with
    the codes the authoritative compile refuses with, rather than A2's
    structural check alone, which called valid what that compile refuses."""

    __slots__ = ("key",)

    def __init__(self, key=CHALLENGE):
        self.key = key

    def dry_validate(self, request):
        from carbon.research.service import dry_validation_result

        if type(request) is not research.DryValidateRequest:
            raise TypeError("exact DryValidateRequest required")
        if request.challenge_key != self.key:
            raise ValueError("research validation binding differs")
        return dry_validation_result(
            request, tuple(submission_issues(request.strategy, self.key.challenge_id))
        )


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


class DirectFixtureDiscovery:
    """Registered public Challenge facts on the shared service.

    Reads the source bytes again at use, so a changed TRAIN, practice array,
    physics document, or resource fact cannot silently retain its old identity.
    This is DEVELOPMENT discovery, not a qualified Challenge.
    """

    def __init__(
        self,
        material,
        *,
        task_admission=False,
        pack_check=None,
        evaluation_pack_digest=None,
        evaluation_pack_snapshot=None,
        evaluation_pack_public_root=None,
        evaluation_pack_private_root=None,
    ):
        if type(task_admission) is not bool:
            raise TypeError("exact direct task admission selection required")
        if evaluation_pack_digest is not None:
            from carbon.challenge_validator.evaluation_pack import (
                EvaluationPackSnapshot,
            )
            from carbon.registry.digest import is_sha256_digest

            if (
                pack_check is None
                or not is_sha256_digest(evaluation_pack_digest)
                or type(evaluation_pack_snapshot) is not EvaluationPackSnapshot
                or evaluation_pack_snapshot.manifest_digest != evaluation_pack_digest
                or not isinstance(evaluation_pack_public_root, Path)
                or not evaluation_pack_public_root.is_absolute()
                or not isinstance(evaluation_pack_private_root, Path)
                or not evaluation_pack_private_root.is_absolute()
            ):
                raise ValueError("verified evaluation pack binding required")
        elif (
            evaluation_pack_snapshot is not None
            or evaluation_pack_public_root is not None
            or evaluation_pack_private_root is not None
        ):
            raise ValueError("verified evaluation pack binding required")
        self._material = material
        self._task_admission = task_admission
        self._pack_check = pack_check
        self.evaluation_pack_digest = evaluation_pack_digest
        self.evaluation_pack_snapshot = evaluation_pack_snapshot
        self.evaluation_pack_public_root = evaluation_pack_public_root
        self.evaluation_pack_private_root = evaluation_pack_private_root
        self.info, self.manifest = self._snapshot()

    def _snapshot(self):
        import numpy as np

        from carbon.battery import challenge as battery_challenge
        from carbon.battery import construction_material as battery_tensors
        from carbon.battery import domain as battery_domain
        from carbon.battery import practice as battery_practice
        from carbon.battery.construction_bundle_material import (
            bundle_material as battery_bundle_material,
        )
        from carbon.challenge_kit.synthetic_linear_field_2d import (
            bundle_material,
            bundle_material_v3,
            bundle_material_v4,
            bundle_material_v5,
        )

        material = self._material
        if type(material) is not dict:
            raise ValueError("direct public material must be a dictionary")
        key, kit, train = (
            material.get("challenge_key"),
            material.get("construction_kit"),
            material.get("train"),
        )
        if (
            type(key) is not research.ChallengeKey
            or type(kit) is not dict
            or type(train) is not bytes
            or kit.get("id") != key.challenge_id
            or kit.get("version") != key.version
            or kit.get("train_digest") != digest(train)
            or kit.get("interface_digest")
            != digest(canonical(material.get("interface_document")))
            or kit.get("construction_limits_digest")
            != digest(canonical(material.get("construction_limits_document")))
            or material.get("physics_digest")
            != digest(canonical(material.get("physics_contract")))
        ):
            raise ValueError("direct Challenge kit or fixed public TRAIN differs")
        practice = material.get("practice_inputs")
        reference = material.get("practice_reference")
        train_ids = material.get("train_case_ids")
        practice_ids = material.get("practice_case_ids")
        battery = key == battery_challenge.CHALLENGE
        if type(practice) is not np.ndarray or type(reference) is not np.ndarray:
            practice_shape_invalid = True
        elif battery:
            practice_shape_invalid = practice.shape != (
                battery_practice.PRACTICE_CASES,
                len(battery_domain.INPUTS),
            ) or reference.shape != (
                battery_practice.PRACTICE_CASES,
                battery_tensors.OUTPUT_WIDTH,
            )
        else:
            practice_shape_invalid = practice.shape != reference.shape
        if (
            type(practice) is not np.ndarray
            or type(reference) is not np.ndarray
            or practice.dtype != (np.float64 if battery else np.float32)
            or reference.dtype != (np.float64 if battery else np.float32)
            or practice_shape_invalid
            or practice.ndim < 2
            or not np.isfinite(practice).all()
            or not np.isfinite(reference).all()
            or type(train_ids) is not tuple
            or type(practice_ids) is not tuple
            or len(practice_ids) != practice.shape[0]
        ):
            raise ValueError("direct public practice bytes or case IDs differ")
        registered_material = (
            battery_bundle_material
            if battery
            else {
                "1.0": bundle_material,
                "1.1": bundle_material_v3,
                "1.2": bundle_material_v4,
                "1.3": bundle_material_v5,
            }.get(key.version)
        )
        if registered_material is None:
            raise ValueError("direct public Challenge version is unregistered")
        if (
            self._task_admission
            and not battery
            and key.version
            not in (
                "1.1",
                "1.2",
                "1.3",
            )
        ):
            raise ValueError("direct task admission requires prospective kit")
        registered = registered_material()
        if (
            key != registered["challenge_key"]
            or kit != registered["construction_kit"]
            or train != registered["train"]
            or material.get("allowlist_bytes") != registered["allowlist_bytes"]
            or material.get("allowlist_digest") != registered["allowlist_digest"]
            or train_ids != registered["train_case_ids"]
            or practice_ids != registered["practice_case_ids"]
            or not np.array_equal(material.get("example"), registered["example"])
            or not np.array_equal(practice, registered["practice_inputs"])
            or not np.array_equal(reference, registered["practice_reference"])
            or material.get("expected_output_shape")
            != registered["expected_output_shape"]
            or any(
                material.get(name) != registered[name]
                for name in (
                    "interface_document",
                    "construction_limits_document",
                    "physics_contract",
                    "resource_facts",
                    "disclosure",
                )
            )
        ):
            raise ValueError("direct public material differs from registered fixture")
        if self._pack_check is not None:
            self._pack_check(material)

        def array_digest(array):
            return digest(
                canonical({"dtype": str(array.dtype), "shape": list(array.shape)})
                + array.tobytes(order="C")
            )

        info = research.DirectChallengeInfo(
            "3.0",
            key,
            key.challenge_id + "-train",
            digest(train),
            train_ids,
            key.challenge_id + "-practice",
            array_digest(practice),
            array_digest(reference),
            practice_ids,
            kit["interface_digest"],
            kit["construction_limits_digest"],
            material["physics_digest"],
            digest(canonical(material.get("resource_facts"))),
            digest(canonical(material.get("disclosure"))),
            research.DisclosureClass.PUBLIC_RESEARCH,
        )
        manifest = research.DirectRecipeManifest(
            "3.0",
            key,
            research.canonical_digest(info),
            digest(canonical(kit)),
            info.public_train_digest,
            info.practice_inputs_digest,
            info.practice_reference_digest,
            info.interface_digest,
            info.construction_limits_digest,
            info.physics_digest,
            info.resource_facts_digest,
            info.disclosure_digest,
            (
                research.DIRECT_RECIPE_SOURCE_TASK_OPERATIONS
                if self._task_admission and (battery or key.version == "1.3")
                else (
                    research.DIRECT_RECIPE_TASK_OPERATIONS
                    if self._task_admission
                    else research.DIRECT_RECIPE_OPERATIONS
                )
            ),
            research.PROTOCOL_LIMITS,
        )
        return info, manifest

    def _checked(self, key):
        info, manifest = self._snapshot()
        if key != info.challenge_key or (info, manifest) != (
            self.info,
            self.manifest,
        ):
            raise ValueError("direct public material identity changed")
        return info, manifest

    def graph_adapter_for(self, key):
        """Return the exact registered 1.3 graph adapter, or no capability.

        The selector follows the existing full fixture recheck. A caller's
        recipe or an unverified material flag cannot select an adapter.
        """
        if (
            type(key) is not research.ChallengeKey
            or key.version != "1.3"
            or key != self.info.challenge_key
        ):
            return None
        self._checked(key)
        adapter = self._material["construction_limits_document"].get(
            "graph_training_adapter"
        )
        expected = {
            "schema": "carbon.synthetic-linear-field-2d.graph-training-adapter.v1",
            "id": "synthetic-linear-field-2d-public-jax-graph-v1",
            "source_kind": "graph",
            "train_use_dataset": "synthetic-linear-field-2d-public-train",
            "procedure_schema": "carbon.construction-recipe.v1",
            "output_format": "carbon.numeric-graph.v1",
            "state_schema": "carbon.development.graph-source-state.v1",
        }
        return expected["id"] if adapter == expected else None

    def get_challenge_info(self, key):
        return self._checked(key)[0]

    def get_interaction_manifest(self, key):
        return self._checked(key)[1]


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
    #: dry_validate answers with the Challenge's submission path
    #: (`ChallengeContractValidation`). False keeps A2's structural check:
    #: the GPU practice composition, whose recipes are its own catalogue's,
    #: not submissions under the Challenge contract.
    contract_validation: bool = True


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
        contract_validation=not gpu,
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
            (
                ChallengeContractValidation(key)
                if parts.contract_validation
                else research.A2ValidationProvider()
            ),
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
