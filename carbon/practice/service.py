"""Coherent in-process B-07C mock execution over registered resolved plans."""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
from dataclasses import dataclass
from typing import Protocol

from carbon.authoring.model import EvidenceRole
from carbon.construction import (
    ConsumerTarget,
    DefaultedSurface,
    SelectedSurface,
    SurfaceValue,
    SurfaceValueType,
)
from carbon.research import (
    AuthorizedResearchOutcome,
    EvidenceContext,
    EvidenceQualityMetadata,
    FindingMeasurement,
    InfrastructureExecutionFailure,
    InfrastructureFailureClass,
    InteractionManifest,
    PrivateIdentityRef,
    ResearchCensoringStatus,
    ResearchEvidenceClass,
    ResearchExecutionAttempt,
    ResearchFailureCategory,
    ResearchRetentionScope,
    ResearchTaskKind,
    ResourceObservation,
    RetentionReuseBinding,
)
from carbon.resource_policy.refs import ObservedResourceReceiptRef
from carbon.seeding import (
    EvaluationBinding,
    MockContext,
    MockEntropy,
    RoleKey,
    SeedPin,
    derive_mock_seed,
)
from carbon.toy import (
    FIXTURE_CURRICULUM_SURFACE_ID,
    FIXTURE_FEATURE_SURFACE_ID,
    FIXTURE_HELDOUT_OBSERVATIONS,
    FIXTURE_SAMPLING_SURFACE_ID,
    FIXTURE_TRAINING_OBSERVATIONS,
    FixtureModelConfiguration,
    construct_fixture_model,
)

from .model import (
    MockFixtureBehavior,
    MockPracticePack,
    PracticeAggregate,
    PracticeAggregateKind,
)
from .registry import VersionedMockPackRegistry

_TOY_LEVER_CONSUMERS = {
    FIXTURE_SAMPLING_SURFACE_ID: ConsumerTarget("fixture_training", "sampling_level"),
    FIXTURE_CURRICULUM_SURFACE_ID: ConsumerTarget(
        "fixture_training", "curriculum_emphasis"
    ),
    FIXTURE_FEATURE_SURFACE_ID: ConsumerTarget("fixture_training", "feature_degree"),
}


class PracticeExecutionError(ValueError):
    """Stable non-echoing practice failure used at the private adapter seam."""


class MockContextFactory(Protocol):
    def make_context(
        self, task_id_value: str, pack: MockPracticePack
    ) -> MockContext: ...


class ObservedResourceRecorder(Protocol):
    def record_observations(
        self,
        attempt: ResearchExecutionAttempt,
        observations: tuple[ResourceObservation, ...],
        *,
        completed: bool,
    ) -> ObservedResourceReceiptRef: ...


class FreshMockContextFactory:
    """Process-local fresh root; task identity makes replay deterministic."""

    __slots__ = ("_root",)

    def __init__(self, root: bytes | None = None) -> None:
        material = secrets.token_bytes(32) if root is None else root
        if type(material) is not bytes or len(material) != 32:
            raise TypeError("mock root must be exactly 32 private bytes")
        self._root = bytes(material)

    def make_context(self, task_id_value: str, pack: MockPracticePack) -> MockContext:
        if type(task_id_value) is not str or type(pack) is not MockPracticePack:
            raise PracticeExecutionError("mock context request is invalid")
        task_root = hmac.new(
            self._root,
            b"carbon.practice.task.v1\x00" + task_id_value.encode("ascii"),
            hashlib.sha256,
        ).digest()
        evaluation_binding = EvaluationBinding(
            hmac.new(task_root, b"evaluation-binding", hashlib.sha256).digest()
        )
        pin = SeedPin(
            pack.challenge_key,
            pack.version,
            pack.generator_implementation_ref.content_digest,
            pack.measurement_pack.version,
            pack.measurement_pack.to_private_ref().content_digest,
            evaluation_binding,
        )
        return MockContext(MockEntropy(task_root), pin)


@dataclass(frozen=True, slots=True)
class MockExecutionRequest:
    attempt: ResearchExecutionAttempt

    def __post_init__(self) -> None:
        if (
            type(self) is not MockExecutionRequest
            or type(self.attempt) is not ResearchExecutionAttempt
        ):
            raise TypeError("mock execution requires an exact private attempt")


@dataclass(frozen=True, slots=True)
class MockRunOutcome:
    outcome: AuthorizedResearchOutcome | InfrastructureExecutionFailure

    def __post_init__(self) -> None:
        if type(self) is not MockRunOutcome or type(self.outcome) not in (
            AuthorizedResearchOutcome,
            InfrastructureExecutionFailure,
        ):
            raise TypeError("mock outcome must use a closed research outcome")


class MockTrainEvalService:
    """Fixture-only practice executor; it has no A5, A6, or A7 dependency."""

    __slots__ = (
        "_aggregates",
        "_contexts",
        "_manifest",
        "_registry",
        "_resource_recorder",
    )

    def __init__(
        self,
        *,
        registry: VersionedMockPackRegistry,
        interaction_manifest: InteractionManifest,
        context_factory: MockContextFactory | None = None,
        resource_recorder: ObservedResourceRecorder | None = None,
    ) -> None:
        if type(registry) is not VersionedMockPackRegistry:
            raise TypeError("practice service requires the exact mock registry")
        if type(interaction_manifest) is not InteractionManifest:
            raise TypeError("practice service requires the exact shared manifest")
        self._registry = registry
        self._manifest = interaction_manifest
        self._contexts = context_factory or FreshMockContextFactory()
        self._resource_recorder = resource_recorder
        self._aggregates: dict[PrivateIdentityRef, PracticeAggregate] = {}

    @staticmethod
    def _private_ref(kind: str, *payloads: bytes) -> PrivateIdentityRef:
        digest = hashlib.sha256(b"carbon.practice.private.v1\x00" + b"".join(payloads))
        return PrivateIdentityRef(kind, "sha256:" + digest.hexdigest())

    def _pack_for(self, attempt: ResearchExecutionAttempt) -> MockPracticePack:
        bindings = attempt.task_bindings
        if bindings.task_kind is ResearchTaskKind.RESOURCE_CALIBRATION:
            if bindings.practice_scope_ref is not None:
                raise PracticeExecutionError(
                    "resource calibration has no practice scope"
                )
            pack = self._registry.resolve_calibration(attempt.challenge_key)
        else:
            if bindings.practice_scope_ref is None:
                raise PracticeExecutionError("practice scope is missing")
            pack = self._registry.resolve_scope(bindings.practice_scope_ref)
        if (
            pack.to_ref() not in self._manifest.practice_pack_refs
            or self._manifest.to_ref() != bindings.interaction_manifest_ref
            or self._manifest.challenge_key != attempt.challenge_key
            or pack.challenge_key != attempt.challenge_key
            or pack.measurement_pack.measurement_contract_ref
            != attempt.measurement_contract_ref
            or pack.compiler_environment_ref
            != self._manifest.compiler_identity.environment_ref
        ):
            raise PracticeExecutionError("practice material pins do not match")
        expected_compiler = self._manifest.compiler_identity
        for resolved in attempt.resolved_strategies:
            compiler = resolved.resolved_plan.compiler_identity
            if (
                compiler.compiler_id != expected_compiler.name
                or compiler.compiler_version != expected_compiler.version
                or compiler.implementation_digest
                != expected_compiler.implementation_digest
                or resolved.resolved_plan.parameter_catalog_ref
                != self._manifest.parameter_catalog_ref
                or not resolved.resolved_plan.environment_pins
            ):
                raise PracticeExecutionError("compiler or environment pin mismatch")
        return pack

    @staticmethod
    def _unit_interval(seed) -> float:
        material = seed.as_backend_bytes()
        return int.from_bytes(material[:8], "big") / float(1 << 64)

    @staticmethod
    def _toy_configuration(plan) -> FixtureModelConfiguration:
        by_id: dict[str, object] = {}
        for surface in plan.resolved_surfaces:
            surface_id = getattr(surface, "surface_id", None)
            if surface_id in (
                FIXTURE_SAMPLING_SURFACE_ID,
                FIXTURE_CURRICULUM_SURFACE_ID,
                FIXTURE_FEATURE_SURFACE_ID,
            ):
                if surface_id in by_id:
                    raise PracticeExecutionError("registered toy lever is duplicated")
                by_id[surface_id] = surface

        sampling = by_id.get(FIXTURE_SAMPLING_SURFACE_ID)
        if sampling is None:
            raise PracticeExecutionError("registered toy lever is unavailable")

        def value(surface_id: str, surface: object | None, default: int) -> int:
            if surface is None:
                return default
            if (
                type(surface) not in (SelectedSurface, DefaultedSurface)
                or surface.consumer_target != _TOY_LEVER_CONSUMERS[surface_id]
                or type(surface.value) is not SurfaceValue
                or surface.value.value_type is not SurfaceValueType.UINT64
                or type(surface.value.value) is not int
                or surface.value.value not in (1, 2)
            ):
                raise PracticeExecutionError(
                    "registered toy lever binding is unsupported"
                )
            return surface.value.value

        try:
            return FixtureModelConfiguration(
                value(FIXTURE_SAMPLING_SURFACE_ID, sampling, 1),
                value(
                    FIXTURE_CURRICULUM_SURFACE_ID,
                    by_id.get(FIXTURE_CURRICULUM_SURFACE_ID),
                    1,
                ),
                value(
                    FIXTURE_FEATURE_SURFACE_ID,
                    by_id.get(FIXTURE_FEATURE_SURFACE_ID),
                    1,
                ),
            )
        except ArithmeticError:
            raise PracticeExecutionError(
                "registered toy lever value is unsupported"
            ) from None

    def _context(
        self, attempt: ResearchExecutionAttempt, pack: MockPracticePack
    ) -> MockContext:
        context = self._contexts.make_context(attempt.task_id.value, pack)
        if (
            type(context) is not MockContext
            or context.pin.challenge_key != pack.challenge_key
        ):
            raise PracticeExecutionError("only an exact mock context is accepted")
        if (
            context.pin.generator_digest
            != pack.generator_implementation_ref.content_digest
            or context.pin.scoring_digest
            != pack.measurement_pack.to_private_ref().content_digest
        ):
            raise PracticeExecutionError("mock context pack identity is substituted")
        return context

    def _reconstruct(
        self,
        attempt: ResearchExecutionAttempt,
        pack: MockPracticePack,
        context: MockContext,
    ) -> tuple[bytes, ...]:
        artifacts: list[bytes] = []
        for strategy_index, resolved in enumerate(attempt.resolved_strategies):
            purposes = resolved.training_sampling_policy.randomness_purposes
            if not purposes:
                raise PracticeExecutionError("training randomness purposes are missing")
            material = hashlib.sha256(resolved.resolved_plan.canonical_bytes())
            for purpose in purposes:
                role = RoleKey(purpose.role_key_label)
                for draw_index in range(pack.training_case_count):
                    seed = derive_mock_seed(
                        context,
                        role,
                        strategy_index * pack.training_case_count + draw_index,
                    )
                    material.update(seed.as_backend_bytes())
            artifacts.append(material.digest())
        return tuple(artifacts)

    @staticmethod
    def _observations(
        attempt: ResearchExecutionAttempt,
    ) -> tuple[ResourceObservation, ...]:
        quantities: dict[str, float] = {}
        for resolved in attempt.resolved_strategies:
            for requirement in resolved.resolved_plan.static_resource_requirements:
                quantities[requirement.dimension_id] = quantities.get(
                    requirement.dimension_id, 0.0
                ) + float(requirement.quantity)
        if not quantities:
            quantities["fixture_work_units"] = float(len(attempt.resolved_strategies))
        return tuple(
            ResourceObservation(dimension, quantity, "fixture_units")
            for dimension, quantity in sorted(quantities.items())
        )

    def _store_aggregate(self, aggregate: PracticeAggregate) -> PrivateIdentityRef:
        ref = aggregate.to_private_ref()
        previous = self._aggregates.setdefault(ref, aggregate)
        if previous != aggregate:
            raise PracticeExecutionError("aggregate identity collision")
        return ref

    def get_private_aggregate(self, ref: PrivateIdentityRef) -> PracticeAggregate:
        if type(ref) is not PrivateIdentityRef or ref.ref_type != "practice_aggregate":
            raise KeyError("private aggregate reference is invalid")
        try:
            return self._aggregates[ref]
        except KeyError:
            raise KeyError("private aggregate is unavailable") from None

    def _evidence_context(self, pack: MockPracticePack) -> EvidenceContext:
        limitation_refs = tuple(
            self._private_ref("practice_limitation", item.encode("utf-8"))
            for item in pack.limitations
        )
        return EvidenceContext(
            evidence_role=EvidenceRole.NUMERICAL,
            evidence_origin_ref=self._private_ref(
                "research_evidence_origin", b"synthetic-fixture"
            ),
            reference_policy_ref=pack.reference_implementation_ref,
            applicability_ref=self._private_ref(
                "evidence_applicability",
                pack.practice_scope_ref.content_digest.encode(),
            ),
            uncertainty_ref=self._private_ref(
                "uncertainty_statement",
                pack.measurement_pack.uncertainty_rule.value.encode(),
            ),
            limitation_refs=limitation_refs,
            population_ref=self._private_ref(
                "practice_population", pack.practice_scope_ref.content_digest.encode()
            ),
            verification_campaign_ref=None,
            censoring_status=ResearchCensoringStatus.UNCENSORED,
            evidence_quality=EvidenceQualityMetadata(),
        )

    def _authorized(
        self,
        *,
        pack: MockPracticePack,
        aggregate: PracticeAggregate,
        observations: tuple[ResourceObservation, ...],
        resource_ref: ObservedResourceReceiptRef | None = None,
        finding_id: str | None = None,
    ) -> AuthorizedResearchOutcome:
        aggregate_ref = self._store_aggregate(aggregate)
        measurements = (
            ()
            if finding_id is None or aggregate.observed_range is None
            else (FindingMeasurement(finding_id, aggregate.observed_range),)
        )
        evidence_class = (
            ResearchEvidenceClass.STRUCTURAL_ONLY
            if aggregate.kind is PracticeAggregateKind.RECONSTRUCTION
            else ResearchEvidenceClass.PRACTICE_NON_AUTHORITATIVE
        )
        return AuthorizedResearchOutcome(
            evidence_class=evidence_class,
            evidence_context=self._evidence_context(pack),
            retention=RetentionReuseBinding(ResearchRetentionScope.LOCAL_PRIVATE_ONLY),
            finding_ids=(),
            aggregate_outcome_refs=(
                aggregate_ref,
                pack.measurement_pack.to_private_ref(),
                self._private_ref(
                    "mock_practice_pack", pack.to_ref().content_digest.encode()
                ),
            ),
            observed_resource_receipt_ref=resource_ref,
            resource_observations=observations,
            scientific_failure_category=aggregate.scientific_failure_category,
            finding_measurements=measurements,
        )

    def run_mock(self, request: MockExecutionRequest) -> MockRunOutcome:
        if type(request) is not MockExecutionRequest:
            raise TypeError("run_mock requires its exact nominal request")
        attempt = request.attempt
        pack = self._pack_for(attempt)
        context = self._context(attempt, pack)
        observations = self._observations(attempt)
        kind = attempt.task_bindings.task_kind
        behavior = pack.fixture_behavior
        if behavior is MockFixtureBehavior.INFRASTRUCTURE_FAILURE:
            return MockRunOutcome(
                InfrastructureExecutionFailure(
                    InfrastructureFailureClass.DEPENDENCY_UNAVAILABLE, False
                )
            )
        if behavior is MockFixtureBehavior.RESOURCE_KILL:
            resource_ref = None
            if self._resource_recorder is not None:
                resource_ref = self._resource_recorder.record_observations(
                    attempt, observations, completed=False
                )
            return MockRunOutcome(
                InfrastructureExecutionFailure(
                    InfrastructureFailureClass.RESOURCE_LIMIT, False, resource_ref
                )
            )
        artifacts = self._reconstruct(attempt, pack, context)
        plan_digests = tuple(
            item.resolved_plan_ref.content_digest
            for item in attempt.resolved_strategies
        )
        if (
            behavior is MockFixtureBehavior.REFERENCE_FAILURE
            and kind is not ResearchTaskKind.RESOURCE_CALIBRATION
        ):
            aggregate_kind = (
                PracticeAggregateKind.PAIRED_DIFFERENCE
                if kind is ResearchTaskKind.PAIRED_PRACTICE
                else (
                    PracticeAggregateKind.RECONSTRUCTION
                    if kind is ResearchTaskKind.RECONSTRUCTION_REHEARSAL
                    else PracticeAggregateKind.SINGLE_PRACTICE
                )
            )
            aggregate = PracticeAggregate(
                aggregate_kind,
                pack.to_ref(),
                pack.measurement_pack.to_private_ref(),
                plan_digests,
                0,
                None,
                None,
                len(plan_digests) == 2,
                ResearchFailureCategory.REFERENCE,
                (*pack.limitations, "REFERENCE_FAILURE_NOT_CANDIDATE_FAILURE"),
            )
            return MockRunOutcome(
                self._authorized(
                    pack=pack, aggregate=aggregate, observations=observations
                )
            )
        if (
            behavior is MockFixtureBehavior.MEASUREMENT_FAILURE
            and kind is not ResearchTaskKind.RESOURCE_CALIBRATION
        ):
            aggregate_kind = (
                PracticeAggregateKind.PAIRED_DIFFERENCE
                if kind is ResearchTaskKind.PAIRED_PRACTICE
                else (
                    PracticeAggregateKind.RECONSTRUCTION
                    if kind is ResearchTaskKind.RECONSTRUCTION_REHEARSAL
                    else PracticeAggregateKind.SINGLE_PRACTICE
                )
            )
            aggregate = PracticeAggregate(
                aggregate_kind,
                pack.to_ref(),
                pack.measurement_pack.to_private_ref(),
                plan_digests,
                0,
                None,
                None,
                len(plan_digests) == 2,
                ResearchFailureCategory.MEASUREMENT,
                (*pack.limitations, "MEASUREMENT_UNRESOLVED"),
            )
            return MockRunOutcome(
                self._authorized(
                    pack=pack, aggregate=aggregate, observations=observations
                )
            )
        if kind is ResearchTaskKind.RECONSTRUCTION_REHEARSAL:
            aggregate = PracticeAggregate(
                PracticeAggregateKind.RECONSTRUCTION,
                pack.to_ref(),
                pack.measurement_pack.to_private_ref(),
                plan_digests,
                0,
                float(len(artifacts)),
                None,
                False,
                None,
                (*pack.limitations, "RECONSTRUCTION_ONLY"),
            )
            return MockRunOutcome(
                self._authorized(
                    pack=pack, aggregate=aggregate, observations=observations
                )
            )
        if kind is ResearchTaskKind.RESOURCE_CALIBRATION:
            if self._resource_recorder is None:
                raise PracticeExecutionError(
                    "resource calibration recorder is unavailable"
                )
            resource_ref = self._resource_recorder.record_observations(
                attempt, observations, completed=True
            )
            aggregate = PracticeAggregate(
                PracticeAggregateKind.RESOURCE_CALIBRATION,
                pack.to_ref(),
                pack.measurement_pack.to_private_ref(),
                plan_digests,
                0,
                None,
                None,
                False,
                None,
                (*pack.limitations, "RESOURCE_FACTS_ONLY"),
            )
            return MockRunOutcome(
                self._authorized(
                    pack=pack,
                    aggregate=aggregate,
                    observations=observations,
                    resource_ref=resource_ref,
                )
            )
        eval_values: list[tuple[float, float]] = []
        coefficients = []
        configurations = []
        for strategy_index, item in enumerate(attempt.resolved_strategies):
            seed = derive_mock_seed(
                context, RoleKey("practice_training_role"), strategy_index
            ).as_backend_bytes()
            configuration = self._toy_configuration(item.resolved_plan)
            coefficient, _ = construct_fixture_model(
                FIXTURE_TRAINING_OBSERVATIONS,
                configuration.sampling_level,
                seed,
                curriculum_emphasis=configuration.curriculum_emphasis,
                feature_degree=configuration.feature_degree,
            )
            coefficients.append(coefficient)
            configurations.append(configuration)
        for index in range(pack.evaluation_case_count):
            x = self._unit_interval(
                derive_mock_seed(context, RoleKey("practice_evaluation_case"), index)
            )
            fixture_x, fixture_y = FIXTURE_HELDOUT_OBSERVATIONS[
                index % len(FIXTURE_HELDOUT_OBSERVATIONS)
            ]
            # Fresh mock cases jitter the public toy coordinates without exposing
            # B-07F's fixture-official seed or result path.
            shifted_x = float(fixture_x) + x / 100.0
            reference = float(fixture_y) + (2.0 * fixture_x * x / 100.0)
            errors = tuple(
                abs(coefficient * (shifted_x**configuration.feature_degree) - reference)
                for coefficient, configuration in zip(
                    coefficients, configurations, strict=True
                )
            )
            if len(errors) == 1:
                eval_values.append((errors[0], errors[0]))
            else:
                eval_values.append((errors[0], errors[1] - errors[0]))
        if kind is ResearchTaskKind.PAIRED_PRACTICE:
            values = [item[1] for item in eval_values]
            aggregate_kind = PracticeAggregateKind.PAIRED_DIFFERENCE
            finding = "paired_practice_observed_difference"
            common_cases = True
        else:
            values = [item[0] for item in eval_values]
            aggregate_kind = PracticeAggregateKind.SINGLE_PRACTICE
            finding = "practice_observed_range"
            common_cases = False
        aggregate_value = math.fsum(values) / len(values)
        observed_range = (float(min(values)), float(max(values)))
        aggregate = PracticeAggregate(
            aggregate_kind,
            pack.to_ref(),
            pack.measurement_pack.to_private_ref(),
            plan_digests,
            pack.evaluation_case_count,
            float(aggregate_value),
            observed_range,
            common_cases,
            None,
            (
                *pack.limitations,
                "OBSERVED_RANGE_NOT_CONFIDENCE_INTERVAL",
                "UNCERTAINTY_POLICY_UNRESOLVED_FOR_REAL_PRACTICE",
            ),
        )
        return MockRunOutcome(
            self._authorized(
                pack=pack,
                aggregate=aggregate,
                observations=observations,
                finding_id=finding,
            )
        )

    def execute(self, attempt: ResearchExecutionAttempt):
        """B-07B ``ResearchExecutor`` adapter; errors remain private infra facts."""

        return self.run_mock(MockExecutionRequest(attempt)).outcome


__all__ = (
    "FreshMockContextFactory",
    "MockContextFactory",
    "MockExecutionRequest",
    "MockRunOutcome",
    "MockTrainEvalService",
    "ObservedResourceRecorder",
    "PracticeExecutionError",
)
