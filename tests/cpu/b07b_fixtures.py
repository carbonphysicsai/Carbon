"""Deterministic B-07B lifecycle fixtures over the real B-02B compiler."""

from __future__ import annotations

from dataclasses import dataclass, replace

from b02b_fixtures import strategy_limits
from b02c_fixtures import ResourcePolicyFixture, make_resource_policy_fixture
from b07a_fixtures import digest, discovery_resources

from carbon.authoring.model import EvidenceRole
from carbon.construction.compiler import (
    SUPPORTED_COMPILER_IDENTITY,
    CompileAccepted,
    compile_strategy,
)
from carbon.research import (
    AuthorizedResearchOutcome,
    EvidenceContext,
    EvidenceQualityMetadata,
    InMemoryResearchTaskProvider,
    NoPriorSelector,
    PairedPracticeTaskSpec,
    PracticeScopeStatementRef,
    PracticeTaskSpec,
    PrivateIdentityRef,
    PublicFindingEvidenceClass,
    PublicResearchFinding,
    ReceiptFindingDefinition,
    ResearchCensoringStatus,
    ResearchEvidenceClass,
    ResearchRetentionScope,
    ResolvedStrategy,
    RetentionReuseBinding,
    StartResearchTaskRequest,
)
from carbon.resource_policy.service import validate_research_resource_policy_bundle


class Catalog:
    def __init__(self, info):
        self.info = info

    def get_challenge_info(self, challenge_key):
        if challenge_key != self.info.challenge_key:
            raise KeyError(challenge_key)
        return self.info


class Manifests:
    def __init__(self, manifest):
        self.manifest = manifest

    def get_interaction_manifest(self, challenge_key):
        if challenge_key != self.manifest.challenge_key:
            raise KeyError(challenge_key)
        return self.manifest


class Compiler:
    def __init__(self, fixture: ResourcePolicyFixture):
        self.fixture = fixture
        self.calls = 0

    def resolve_strategy(self, request):
        self.calls += 1
        source = self.fixture.compile_fixture
        result = compile_strategy(
            request.strategy,
            challenge_key=request.challenge_key,
            candidate_assembly=source.assembly,
            candidate_assembly_ref=source.assembly.to_ref(),
            parameter_catalog=source.catalog,
            parameter_catalog_ref=source.catalog.to_ref(
                candidate_assembly=source.assembly
            ),
            authoring_origin=source.authoring_origin,
            authoring_artifacts=source.authoring_artifacts,
            compiler_identity=SUPPORTED_COMPILER_IDENTITY,
            strategy_limits=strategy_limits(),
        )
        if type(result) is not CompileAccepted:
            raise ValueError("fixture strategy rejected")
        return ResolvedStrategy(
            result.construction_plan.strategy_hash,
            result.training_policy_ref,
            result.construction_plan_ref,
            result.construction_plan,
            result.training_policy,
        )


class NoPriors:
    def resolve_prior(self, request):
        raise AssertionError("no-prior selectors must not invoke prior resolution")


class Resources:
    def __init__(self, fixture: ResourcePolicyFixture):
        self.fixture = fixture
        self.calls = 0

    def validate_resource_request(self, challenge_key, policy_ref, class_ref):
        self.calls += 1
        if (
            challenge_key != self.fixture.policy.challenge_key
            or policy_ref != self.fixture.policy_ref
            or class_ref != self.fixture.resource_class_ref
        ):
            raise ValueError("resource request mismatch")
        validate_research_resource_policy_bundle(
            self.fixture.policy, class_bundle=self.fixture.class_bundle
        )


class Queue:
    def __init__(self):
        self.items = []

    def enqueue(self, task_id):
        self.items.append(task_id)


class Clock:
    def __init__(self):
        self.value = 1_000_000

    def __call__(self):
        self.value += 1
        return self.value


class Executor:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.attempts = []

    def execute(self, attempt):
        self.attempts.append(attempt)
        return self.outcomes.pop(0)


def private_ref(kind: str, character: str = "d") -> PrivateIdentityRef:
    return PrivateIdentityRef(kind, digest(character))


def outcome(
    *,
    finding_ids=("stable_negative",),
    role=EvidenceRole.NUMERICAL,
    evidence_class=ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE,
    retention=None,
    epistemic_status=None,
    population_ref=None,
    verification_campaign_ref=None,
    failure=None,
    evidence_quality=None,
    evidence_quality_authorization_ref=None,
):
    return AuthorizedResearchOutcome(
        evidence_class=evidence_class,
        evidence_context=EvidenceContext(
            evidence_role=role,
            evidence_origin_ref=private_ref("research_evidence_origin"),
            reference_policy_ref=private_ref("reference_policy"),
            applicability_ref=private_ref("evidence_applicability"),
            uncertainty_ref=private_ref("uncertainty_statement"),
            limitation_refs=(private_ref("evidence_limitation"),),
            population_ref=population_ref,
            verification_campaign_ref=verification_campaign_ref,
            censoring_status=ResearchCensoringStatus.UNCENSORED,
            evidence_quality=evidence_quality or EvidenceQualityMetadata(),
            evidence_quality_authorization_ref=(evidence_quality_authorization_ref),
            epistemic_status=epistemic_status,
        ),
        retention=retention
        or RetentionReuseBinding(ResearchRetentionScope.LOCAL_PRIVATE_ONLY),
        finding_ids=finding_ids,
        aggregate_outcome_refs=(private_ref("aggregate_outcome"),),
        observed_resource_receipt_ref=None,
        resource_observations=(),
        scientific_failure_category=failure,
    )


@dataclass(slots=True)
class Fixture:
    domain: ResourcePolicyFixture
    provider: InMemoryResearchTaskProvider
    compiler: Compiler
    resources: Resources
    queue: Queue
    executor: Executor
    practice_scope: PracticeScopeStatementRef

    def request(self, *, key="idem-fixture-0001", paired=True, strategies=None):
        source = self.domain.compile_fixture
        if strategies is None:
            baseline = {
                **source.strategy,
                "parameters": {"fixture_sampling_level": 1},
            }
            intervention = {
                **source.strategy,
                "parameters": {"fixture_sampling_level": 2},
            }
        else:
            baseline, intervention = strategies
        spec = (
            PairedPracticeTaskSpec(baseline, intervention)
            if paired
            else PracticeTaskSpec(intervention, None)
        )
        return StartResearchTaskRequest(
            challenge_key=source.key,
            idempotency_key=key,
            task_spec=spec,
            training_support_ref=source.assembly.training_support_ref,
            prior_selector=NoPriorSelector(),
            resource_policy_ref=self.domain.policy_ref,
            requested_resource_class_ref=self.domain.resource_class_ref,
            practice_scope_ref=self.practice_scope,
        )


def make_fixture(tmp_path, *, outcomes=None, queue=None) -> Fixture:
    domain = make_resource_policy_fixture(tmp_path)
    source = domain.compile_fixture
    base_info, base_manifest = discovery_resources(challenge_id=source.key.challenge_id)
    info = replace(
        base_info,
        physical_system_ref=source.assembly.physical_system_ref,
        candidate_output_ref=source.assembly.candidate_output_ref,
        training_support_ref=source.assembly.training_support_ref,
    )
    practice_scope = PracticeScopeStatementRef(source.key, content_digest=digest("e"))
    manifest = replace(
        base_manifest,
        challenge_info_ref=info.to_ref(),
        physical_system_ref=info.physical_system_ref,
        candidate_output_ref=info.candidate_output_ref,
        training_support_ref=info.training_support_ref,
        candidate_assembly_ref=source.assembly.to_ref(),
        parameter_catalog_ref=source.catalog.to_ref(candidate_assembly=source.assembly),
        practice_scope_ref=practice_scope,
        resource_policy_ref=domain.policy_ref,
    )
    finding = PublicResearchFinding(
        kind="negative_result",
        claim="No improvement was observed in this bounded local practice run.",
        evidence_class=PublicFindingEvidenceClass.TEST_ONLY,
        measurement_ref=info.measurement_contract_ref,
        uncertainty_band=(-0.1, 0.1),
        limitations=("PRACTICE_NON_AUTHORITATIVE",),
    )
    compiler = Compiler(domain)
    resources = Resources(domain)
    task_queue = queue or Queue()
    executor = Executor(outcomes or [outcome()])
    provider = InMemoryResearchTaskProvider(
        challenge_catalog_provider=Catalog(info),
        manifest_provider=Manifests(manifest),
        compilation_resolver=compiler,
        prior_resolver=NoPriors(),
        resource_resolver=resources,
        executor=executor,
        task_queue=task_queue,
        finding_definitions=(ReceiptFindingDefinition("stable_negative", finding),),
        clock=Clock(),
        worker_implementation_digest=digest("b"),
        environment_digest=digest("c"),
    )
    return Fixture(
        domain, provider, compiler, resources, task_queue, executor, practice_scope
    )


__all__ = ["Executor", "Fixture", "Queue", "make_fixture", "outcome", "private_ref"]
