"""Linearizable local B-07B research-task lifecycle."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from carbon.fees import StrategyHash
from carbon.registry import ChallengeKey
from carbon.resource_policy.refs import ObservedResourceReceiptRef

from .canonical import (
    _canonical_record_payload_without,
    _canonical_tuple_payload,
    canonical_bytes,
    load_canonical,
)
from .errors import ResearchServiceError, ResearchServiceErrorCode, public_error
from .model import (
    ActivePriorSelector,
    AvailablePriorAvailability,
    CancellationDisposition,
    CancelResearchTaskRequest,
    CancelResearchTaskResult,
    ChallengeInfo,
    CompileStrategyRequest,
    ExactPriorSelector,
    GetPriorRequest,
    GetResearchResultRequest,
    GetResearchResultResult,
    InfrastructureFailureClass,
    InteractionManifest,
    NoPriorAvailability,
    NoPriorSelector,
    PairedPracticeTaskSpec,
    PracticeTaskSpec,
    PublicResearchFinding,
    ReconstructionRehearsalSpec,
    ResearchReceipt,
    ResearchTaskBindings,
    ResearchTaskKind,
    ResearchTaskState,
    ResearchTaskView,
    ResourceCalibrationTaskSpec,
    StartResearchTaskRequest,
    StartResearchTaskResult,
    StrategyTaskBinding,
    StrategyTaskRole,
)
from .providers import ChallengeCatalogProvider, ManifestProvider
from .records import (
    AuthorizedResearchOutcome,
    ExecutionIdentity,
    ExperimentRecord,
    InfrastructureExecutionFailure,
    PriorResolution,
    ResearchExecutionAttempt,
    ResearchExecutor,
    ResearchRetentionScope,
    ResolvedStrategy,
    resolved_plan_difference,
)
from .refs import ResearchReceiptRef, ResearchTaskId

_TASK_ID_DOMAIN = b"carbon.research-task-id.v2\x00"
_START_REQUEST_DOMAIN = b"carbon.research-start-request.v2\x00"
_RECEIPT_DOMAIN = b"carbon.research-receipt.v2\x00"
_TERMINAL = frozenset(
    {
        ResearchTaskState.SUCCEEDED,
        ResearchTaskState.FAILED_INFRA,
        ResearchTaskState.CANCELLED,
    }
)
_TRANSITIONS = frozenset(
    {
        (ResearchTaskState.QUEUED, ResearchTaskState.RUNNING),
        (ResearchTaskState.QUEUED, ResearchTaskState.CANCELLED),
        (ResearchTaskState.QUEUED, ResearchTaskState.FAILED_INFRA),
        (ResearchTaskState.RUNNING, ResearchTaskState.CANCEL_REQUESTED),
        (ResearchTaskState.RUNNING, ResearchTaskState.SUCCEEDED),
        (ResearchTaskState.RUNNING, ResearchTaskState.FAILED_INFRA),
        (ResearchTaskState.CANCEL_REQUESTED, ResearchTaskState.CANCELLED),
        (ResearchTaskState.CANCEL_REQUESTED, ResearchTaskState.SUCCEEDED),
        (ResearchTaskState.CANCEL_REQUESTED, ResearchTaskState.FAILED_INFRA),
    }
)


class ResearchTaskProviderError(RuntimeError):
    """Closed provider failure suitable for later B-07G wire mapping."""

    def __init__(self, code: ResearchServiceErrorCode):
        if type(code) is not ResearchServiceErrorCode:
            raise TypeError("code must use its exact enum")
        self.error: ResearchServiceError = public_error(code)
        super().__init__(self.error.message)

    @property
    def code(self) -> ResearchServiceErrorCode:
        return self.error.code


class ResearchCompilationResolver(Protocol):
    def resolve_strategy(self, request: CompileStrategyRequest) -> ResolvedStrategy: ...


class ResearchPriorResolver(Protocol):
    def resolve_prior(self, request: GetPriorRequest) -> PriorResolution: ...


class ResearchResourceResolver(Protocol):
    def validate_resource_request(
        self,
        challenge_key: ChallengeKey,
        resource_policy_ref: object,
        requested_resource_class_ref: object,
    ) -> None: ...


class ResearchTaskQueue(Protocol):
    def enqueue(self, task_id: ResearchTaskId) -> None: ...


@dataclass(frozen=True, slots=True)
class ReceiptFindingDefinition:
    finding_id: str
    finding: PublicResearchFinding

    def __post_init__(self) -> None:
        from carbon.authoring.primitives import validate_canonical_id

        if type(self) is not ReceiptFindingDefinition:
            raise TypeError("finding definition subclasses are rejected")
        validate_canonical_id(self.finding_id, "finding_id")
        if type(self.finding) is not PublicResearchFinding:
            raise TypeError("finding must use the exact wire record")


@dataclass(slots=True)
class _Task:
    task_id: ResearchTaskId
    challenge_key: ChallengeKey
    request_digest: bytes
    bindings: ResearchTaskBindings
    info: ChallengeInfo
    strategies: tuple[ResolvedStrategy, ...]
    parents: tuple[StrategyHash | None, ...]
    prior: PriorResolution
    state: ResearchTaskState
    revision: int
    created_at_micros: int
    updated_at_micros: int
    cancellation_id: str | None = None
    receipt: ResearchReceipt | None = None
    record: ExperimentRecord | None = None
    last_poll_sequence: int | None = None
    last_poll_result: GetResearchResultResult | None = None


class InMemoryResearchTaskProvider:
    """One constructor-bound local requester session.

    This class is a provider behind the shared ``ResearchTaskProvider``
    protocol.  It is not a dispatcher, listener, authentication system, or v1
    submission service.
    """

    def __init__(
        self,
        *,
        challenge_catalog_provider: ChallengeCatalogProvider,
        manifest_provider: ManifestProvider,
        compilation_resolver: ResearchCompilationResolver,
        prior_resolver: ResearchPriorResolver,
        resource_resolver: ResearchResourceResolver,
        executor: ResearchExecutor,
        task_queue: ResearchTaskQueue,
        finding_definitions: tuple[ReceiptFindingDefinition, ...] = (),
        receipt_limitations: tuple[str, ...] = (
            "LOCAL_RESEARCH_ONLY",
            "NOT_OFFICIAL_EVIDENCE",
            "NOT_SCIENTIFICALLY_QUALIFIED",
        ),
        clock: Callable[[], int] | None = None,
        worker_implementation_digest: str = "sha256:" + "0" * 64,
        environment_digest: str = "sha256:" + "0" * 64,
    ) -> None:
        from carbon.authoring.primitives import validate_tagged_sha256

        if type(finding_definitions) is not tuple or any(
            type(item) is not ReceiptFindingDefinition for item in finding_definitions
        ):
            raise TypeError("finding definitions must use exact records")
        ids = tuple(item.finding_id for item in finding_definitions)
        if len(ids) != len(set(ids)):
            raise ValueError("finding definition ids must be unique")
        if (
            type(receipt_limitations) is not tuple
            or not receipt_limitations
            or any(type(item) is not str for item in receipt_limitations)
        ):
            raise TypeError("receipt limitations must be a nonempty text tuple")
        if len(receipt_limitations) > 64:
            raise ValueError("receipt limitations exceed the wire bound")
        validate_tagged_sha256(
            worker_implementation_digest, "worker_implementation_digest"
        )
        validate_tagged_sha256(environment_digest, "environment_digest")
        self._catalog = challenge_catalog_provider
        self._manifests = manifest_provider
        self._compiler = compilation_resolver
        self._priors = prior_resolver
        self._resources = resource_resolver
        self._executor = executor
        self._queue = task_queue
        self._findings = {item.finding_id: item.finding for item in finding_definitions}
        self._limitations = receipt_limitations
        self._clock = clock or (lambda: time.time_ns() // 1_000)
        self._worker_digest = worker_implementation_digest
        self._environment_digest = environment_digest
        self._service_instance_id = secrets.token_bytes(32)
        self._requester_binding = secrets.token_bytes(32)
        self._lock = threading.RLock()
        self._tasks: dict[ResearchTaskId, _Task] = {}
        self._idempotency: dict[tuple[ChallengeKey, str], ResearchTaskId] = {}

    def _now(self, floor: int | None = None) -> int:
        value = self._clock()
        if type(value) is not int or not -(1 << 63) <= value <= (1 << 63) - 1:
            raise ResearchTaskProviderError(ResearchServiceErrorCode.INTERNAL_FAILURE)
        return value if floor is None or value >= floor else floor

    @staticmethod
    def _start_digest(request: StartResearchTaskRequest) -> bytes:
        return hashlib.sha256(
            _START_REQUEST_DOMAIN
            + _canonical_record_payload_without(request, frozenset({"idempotency_key"}))
        ).digest()

    def _task_id(self, request: StartResearchTaskRequest) -> ResearchTaskId:
        digest = hashlib.sha256(
            _TASK_ID_DOMAIN
            + _canonical_tuple_payload(
                (
                    self._service_instance_id,
                    self._requester_binding,
                    request.challenge_key,
                    request.idempotency_key,
                )
            )
        ).hexdigest()
        return ResearchTaskId("rtsk_" + digest)

    @staticmethod
    def _spec_parts(request: StartResearchTaskRequest) -> tuple[
        ResearchTaskKind,
        tuple[StrategyTaskRole, ...],
        tuple[dict[str, object], ...],
        tuple[StrategyHash | None, ...],
    ]:
        spec = request.task_spec
        if type(spec) is ReconstructionRehearsalSpec:
            return (
                ResearchTaskKind.RECONSTRUCTION_REHEARSAL,
                (StrategyTaskRole.PRIMARY,),
                (spec.strategy,),
                (spec.parent_strategy_hash,),
            )
        if type(spec) is PracticeTaskSpec:
            return (
                ResearchTaskKind.PRACTICE,
                (StrategyTaskRole.PRIMARY,),
                (spec.strategy,),
                (spec.parent_strategy_hash,),
            )
        if type(spec) is PairedPracticeTaskSpec:
            return (
                ResearchTaskKind.PAIRED_PRACTICE,
                (StrategyTaskRole.BASELINE, StrategyTaskRole.INTERVENTION),
                (spec.baseline_strategy, spec.intervention_strategy),
                (None, None),
            )
        if type(spec) is ResourceCalibrationTaskSpec:
            return (
                ResearchTaskKind.RESOURCE_CALIBRATION,
                (StrategyTaskRole.PRIMARY,),
                (spec.strategy,),
                (None,),
            )
        raise ResearchTaskProviderError(ResearchServiceErrorCode.REQUEST_TYPE_INVALID)

    @staticmethod
    def _check_discovery(
        request: StartResearchTaskRequest,
        info: ChallengeInfo,
        manifest: InteractionManifest,
    ) -> None:
        if (
            type(info) is not ChallengeInfo
            or type(manifest) is not InteractionManifest
            or info.challenge_key != request.challenge_key
            or manifest.challenge_key != request.challenge_key
            or manifest.challenge_info_ref != info.to_ref()
            or manifest.physical_system_ref != info.physical_system_ref
            or manifest.candidate_output_ref != info.candidate_output_ref
            or manifest.instance_distribution_ref != info.instance_distribution_ref
            or manifest.sampling_plan_ref != info.sampling_plan_ref
            or manifest.training_support_ref != info.training_support_ref
            or manifest.measurement_contract_ref != info.measurement_contract_ref
            or manifest.public_score_policy_ref != info.public_score_policy_ref
            or request.training_support_ref != manifest.training_support_ref
            or request.resource_policy_ref != manifest.resource_policy_ref
        ):
            raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        if request.practice_scope_ref != manifest.practice_scope_ref:
            raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)

    def _resolve_start(self, request: StartResearchTaskRequest) -> tuple[
        ChallengeInfo,
        InteractionManifest,
        ResearchTaskKind,
        tuple[ResolvedStrategy, ...],
        tuple[StrategyHash | None, ...],
        PriorResolution,
        ResearchTaskBindings,
    ]:
        try:
            info = self._catalog.get_challenge_info(request.challenge_key)
            manifest = self._manifests.get_interaction_manifest(request.challenge_key)
            self._check_discovery(request, info, manifest)
            kind, roles, strategies, parents = self._spec_parts(request)
            availability = manifest.prior_availability
            if type(availability) is NoPriorAvailability:
                if type(request.prior_selector) is not NoPriorSelector:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
            elif type(availability) is AvailablePriorAvailability:
                if type(request.prior_selector) is NoPriorSelector:
                    pass
                elif type(request.prior_selector) is ActivePriorSelector:
                    if (
                        request.prior_selector.channel
                        is not availability.prior_channel_ref.channel
                    ):
                        raise ResearchTaskProviderError(
                            ResearchServiceErrorCode.REFERENCE_MISMATCH
                        )
                elif (
                    type(request.prior_selector) is ExactPriorSelector
                    and request.prior_selector.prior_pack_ref.channel
                    is not availability.prior_channel_ref.channel
                ):
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
            else:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.REFERENCE_MISMATCH
                )
            resolved = tuple(
                self._compiler.resolve_strategy(
                    CompileStrategyRequest(
                        challenge_key=request.challenge_key,
                        strategy=strategy,
                        expected_training_support_ref=request.training_support_ref,
                    )
                )
                for strategy in strategies
            )
            for item in resolved:
                if (
                    type(item) is not ResolvedStrategy
                    or item.resolved_plan.challenge_key != request.challenge_key
                    or item.resolved_plan.physical_system_ref
                    != manifest.physical_system_ref
                    or item.resolved_plan.candidate_output_ref
                    != manifest.candidate_output_ref
                    or item.resolved_plan.training_support_ref
                    != request.training_support_ref
                    or item.resolved_plan.candidate_assembly_ref
                    != manifest.candidate_assembly_ref
                    or item.resolved_plan.parameter_catalog_ref
                    != manifest.parameter_catalog_ref
                ):
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
            if kind is ResearchTaskKind.PAIRED_PRACTICE:
                resolved_plan_difference(
                    resolved[0].resolved_plan, resolved[1].resolved_plan
                )
            if type(request.prior_selector) is NoPriorSelector:
                prior = PriorResolution(None, None)
            else:
                prior = self._priors.resolve_prior(
                    GetPriorRequest(request.challenge_key, request.prior_selector)
                )
                if type(prior) is not PriorResolution:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
                if (
                    prior.prior_pack_ref is None
                    or prior.prior_pack_ref.challenge_key != request.challenge_key
                    or prior.index_snapshot_ref is None
                    or prior.index_snapshot_ref.challenge_key != request.challenge_key
                ):
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
                if type(request.prior_selector) is ExactPriorSelector and (
                    prior.prior_pack_ref != request.prior_selector.prior_pack_ref
                ):
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
                if type(request.prior_selector) is ActivePriorSelector and (
                    prior.prior_pack_ref.channel is not request.prior_selector.channel
                    or prior.index_snapshot_ref.channel
                    is not request.prior_selector.channel
                ):
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
            self._resources.validate_resource_request(
                request.challenge_key,
                request.resource_policy_ref,
                request.requested_resource_class_ref,
            )
            strategy_bindings = tuple(
                StrategyTaskBinding(
                    role=role,
                    strategy_hash=item.strategy_hash,
                    training_sampling_policy_ref=item.training_sampling_policy_ref,
                    resolved_plan_ref=item.resolved_plan_ref,
                )
                for role, item in zip(roles, resolved, strict=True)
            )
            bindings = ResearchTaskBindings(
                task_kind=kind,
                challenge_info_ref=info.to_ref(),
                interaction_manifest_ref=manifest.to_ref(),
                strategy_bindings=strategy_bindings,
                training_support_ref=request.training_support_ref,
                prior_index_snapshot_ref=prior.index_snapshot_ref,
                prior_pack_ref=prior.prior_pack_ref,
                resource_policy_ref=request.resource_policy_ref,
                requested_resource_class_ref=request.requested_resource_class_ref,
                practice_scope_ref=request.practice_scope_ref,
            )
            return info, manifest, kind, resolved, parents, prior, bindings
        except ResearchTaskProviderError:
            raise
        except (KeyError, LookupError):
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REFERENCE_NOT_FOUND
            ) from None
        except (TypeError, ValueError):
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REFERENCE_MISMATCH
            ) from None
        except Exception:  # noqa: BLE001 - provider failures map to one closed error.
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.PROVIDER_UNAVAILABLE
            ) from None

    @staticmethod
    def _view(task: _Task) -> ResearchTaskView:
        return ResearchTaskView(
            task_id=task.task_id,
            challenge_key=task.challenge_key,
            state=task.state,
            revision=task.revision,
            created_at_micros=task.created_at_micros,
            updated_at_micros=task.updated_at_micros,
            immutable_bindings=task.bindings,
            progress=None,
            terminal_receipt=task.receipt,
        )

    def _receipt(
        self,
        task: _Task,
        state: ResearchTaskState,
        completed_at: int,
        *,
        outcome: AuthorizedResearchOutcome | None = None,
        failure_class: InfrastructureFailureClass | None = None,
        observed_resource_receipt_ref: ObservedResourceReceiptRef | None = None,
    ) -> ResearchReceipt:
        if state is ResearchTaskState.SUCCEEDED:
            if (
                type(outcome) is not AuthorizedResearchOutcome
                or failure_class is not None
            ):
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INTERNAL_FAILURE
                )
            try:
                findings = tuple(self._findings[item] for item in outcome.finding_ids)
            except KeyError:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.DISCLOSURE_REJECTED
                ) from None
            if any(
                finding.measurement_ref != task.info.measurement_contract_ref
                for finding in findings
            ):
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.DISCLOSURE_REJECTED
                )
            observed = outcome.observed_resource_receipt_ref
            if observed is not None and observed.challenge_key != task.challenge_key:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.REFERENCE_MISMATCH
                )
        elif state is ResearchTaskState.FAILED_INFRA:
            if type(failure_class) is not InfrastructureFailureClass:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INTERNAL_FAILURE
                )
            findings = ()
            observed = observed_resource_receipt_ref
            if (
                observed is not None
                and type(observed) is not ObservedResourceReceiptRef
            ):
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INTERNAL_FAILURE
                )
            if observed is not None and observed.challenge_key != task.challenge_key:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.REFERENCE_MISMATCH
                )
        elif state is ResearchTaskState.CANCELLED:
            if outcome is not None or failure_class is not None:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INTERNAL_FAILURE
                )
            findings = ()
            observed = None
        else:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.INVALID_TASK_TRANSITION
            )
        placeholder = ResearchReceipt(
            receipt_ref=ResearchReceiptRef(task.task_id, "sha256:" + "0" * 64),
            task_id=task.task_id,
            terminal_state=state,
            immutable_bindings=task.bindings,
            public_findings=findings,
            observed_resource_receipt_ref=observed,
            infrastructure_failure_class=failure_class,
            limitations=self._limitations,
            completed_at_micros=completed_at,
        )
        digest = (
            "sha256:"
            + hashlib.sha256(
                _RECEIPT_DOMAIN
                + _canonical_record_payload_without(
                    placeholder, frozenset({"receipt_ref"})
                )
            ).hexdigest()
        )
        return ResearchReceipt(
            receipt_ref=ResearchReceiptRef(task.task_id, digest),
            task_id=task.task_id,
            terminal_state=state,
            immutable_bindings=task.bindings,
            public_findings=findings,
            observed_resource_receipt_ref=observed,
            infrastructure_failure_class=failure_class,
            limitations=self._limitations,
            completed_at_micros=completed_at,
        )

    def _transition(
        self,
        task: _Task,
        state: ResearchTaskState,
        *,
        receipt: ResearchReceipt | None = None,
    ) -> None:
        if (task.state, state) not in _TRANSITIONS:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.INVALID_TASK_TRANSITION
            )
        if (state in _TERMINAL) != (receipt is not None):
            raise ResearchTaskProviderError(ResearchServiceErrorCode.INTERNAL_FAILURE)
        task.state = state
        task.revision += 1
        task.updated_at_micros = self._now(task.updated_at_micros)
        task.receipt = receipt

    def start_research_task(
        self, request: StartResearchTaskRequest
    ) -> StartResearchTaskResult:
        if type(request) is not StartResearchTaskRequest:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        try:
            snapshot = load_canonical(
                canonical_bytes(request), StartResearchTaskRequest
            )
        except Exception as exc:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            ) from exc
        assert type(snapshot) is StartResearchTaskRequest
        digest = self._start_digest(snapshot)
        idem = (snapshot.challenge_key, snapshot.idempotency_key)
        created = False
        with self._lock:
            existing_id = self._idempotency.get(idem)
            if existing_id is not None:
                existing = self._tasks[existing_id]
                if existing.request_digest != digest:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
                    )
                return StartResearchTaskResult(False, self._view(existing))
            info, _manifest, _kind, resolved, parents, prior, bindings = (
                self._resolve_start(snapshot)
            )
            task_id = self._task_id(snapshot)
            if task_id in self._tasks:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INTERNAL_FAILURE
                )
            created_at = self._now()
            task = _Task(
                task_id=task_id,
                challenge_key=snapshot.challenge_key,
                request_digest=digest,
                bindings=bindings,
                info=info,
                strategies=resolved,
                parents=parents,
                prior=prior,
                state=ResearchTaskState.QUEUED,
                revision=0,
                created_at_micros=created_at,
                updated_at_micros=created_at,
            )
            self._tasks[task_id] = task
            self._idempotency[idem] = task_id
            created = True
        try:
            self._queue.enqueue(task_id)
        except Exception:  # noqa: BLE001 - queue details must not cross the boundary.
            with self._lock:
                if task.state is ResearchTaskState.QUEUED:
                    completed_at = self._now(task.updated_at_micros)
                    receipt = self._receipt(
                        task,
                        ResearchTaskState.FAILED_INFRA,
                        completed_at,
                        failure_class=InfrastructureFailureClass.QUEUE_LOST,
                    )
                    self._transition(
                        task, ResearchTaskState.FAILED_INFRA, receipt=receipt
                    )
        with self._lock:
            return StartResearchTaskResult(created, self._view(task))

    def get_research_result(
        self, request: GetResearchResultRequest
    ) -> GetResearchResultResult:
        if type(request) is not GetResearchResultRequest:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        with self._lock:
            task = self._tasks.get(request.task_id)
            if task is None or task.challenge_key != request.challenge_key:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
            sequence = request.poll_sequence
            if task.last_poll_sequence is None:
                if sequence != 0:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.POLL_SEQUENCE_INVALID
                    )
            elif sequence == task.last_poll_sequence:
                assert task.last_poll_result is not None
                return task.last_poll_result
            elif sequence != task.last_poll_sequence + 1:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.POLL_SEQUENCE_INVALID
                )
            result = GetResearchResultResult(self._view(task))
            task.last_poll_sequence = sequence
            task.last_poll_result = result
            return result

    def cancel_research_task(
        self, request: CancelResearchTaskRequest
    ) -> CancelResearchTaskResult:
        if type(request) is not CancelResearchTaskRequest:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.REQUEST_TYPE_INVALID
            )
        with self._lock:
            task = self._tasks.get(request.task_id)
            if task is None or task.challenge_key != request.challenge_key:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
            if task.state in _TERMINAL:
                return CancelResearchTaskResult(
                    self._view(task), CancellationDisposition.TOO_LATE
                )
            if task.state is ResearchTaskState.CANCEL_REQUESTED:
                if task.cancellation_id != request.cancellation_id:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.INVALID_TASK_TRANSITION
                    )
                return CancelResearchTaskResult(
                    self._view(task), CancellationDisposition.ALREADY_ACCEPTED
                )
            task.cancellation_id = request.cancellation_id
            if task.state is ResearchTaskState.QUEUED:
                completed_at = self._now(task.updated_at_micros)
                receipt = self._receipt(task, ResearchTaskState.CANCELLED, completed_at)
                self._transition(task, ResearchTaskState.CANCELLED, receipt=receipt)
            elif task.state is ResearchTaskState.RUNNING:
                self._transition(task, ResearchTaskState.CANCEL_REQUESTED)
            else:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INVALID_TASK_TRANSITION
                )
            return CancelResearchTaskResult(
                self._view(task), CancellationDisposition.ACCEPTED
            )

    def run_queued_task(self, task_id: ResearchTaskId) -> ResearchTaskView:
        """Trusted worker entry point; never exposed as a v2 operation."""

        if type(task_id) is not ResearchTaskId:
            raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
            if task.state in _TERMINAL:
                return self._view(task)
            if task.state is not ResearchTaskState.QUEUED:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.INVALID_TASK_TRANSITION
                )
            self._transition(task, ResearchTaskState.RUNNING)

        attempt_number = 0
        while attempt_number < 3:
            attempt_number += 1
            with self._lock:
                if task.state is ResearchTaskState.CANCEL_REQUESTED:
                    completed_at = self._now(task.updated_at_micros)
                    receipt = self._receipt(
                        task, ResearchTaskState.CANCELLED, completed_at
                    )
                    self._transition(task, ResearchTaskState.CANCELLED, receipt=receipt)
                    return self._view(task)
            try:
                outcome = self._executor.execute(
                    ResearchExecutionAttempt(
                        task_id=task.task_id,
                        attempt=attempt_number,
                        challenge_key=task.challenge_key,
                        training_support_ref=task.bindings.training_support_ref,
                        sampling_plan_ref=task.info.sampling_plan_ref,
                        measurement_contract_ref=task.info.measurement_contract_ref,
                        resolved_strategies=task.strategies,
                        parent_strategy_hashes=task.parents,
                        prior_resolution=task.prior,
                    )
                )
            except Exception:  # noqa: BLE001 - worker details become typed infra state.
                outcome = InfrastructureExecutionFailure(
                    InfrastructureFailureClass.INTERNAL, True
                )
            if type(outcome) not in (
                AuthorizedResearchOutcome,
                InfrastructureExecutionFailure,
            ):
                outcome = InfrastructureExecutionFailure(
                    InfrastructureFailureClass.INTERNAL, False
                )
            with self._lock:
                if task.state is ResearchTaskState.CANCEL_REQUESTED:
                    completed_at = self._now(task.updated_at_micros)
                    receipt = self._receipt(
                        task, ResearchTaskState.CANCELLED, completed_at
                    )
                    self._transition(task, ResearchTaskState.CANCELLED, receipt=receipt)
                    return self._view(task)
                if task.state is not ResearchTaskState.RUNNING:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.INVALID_TASK_TRANSITION
                    )
                if type(outcome) is InfrastructureExecutionFailure:
                    if outcome.retryable and attempt_number < 3:
                        continue
                    completed_at = self._now(task.updated_at_micros)
                    receipt = self._receipt(
                        task,
                        ResearchTaskState.FAILED_INFRA,
                        completed_at,
                        failure_class=outcome.failure_class,
                        observed_resource_receipt_ref=(
                            outcome.observed_resource_receipt_ref
                        ),
                    )
                    self._transition(
                        task, ResearchTaskState.FAILED_INFRA, receipt=receipt
                    )
                    return self._view(task)
                try:
                    if outcome.evidence_context.epistemic_status is not None:
                        raise ValueError("epistemic interpretation unavailable")
                    difference = (
                        resolved_plan_difference(
                            task.strategies[0].resolved_plan,
                            task.strategies[1].resolved_plan,
                        )
                        if len(task.strategies) == 2
                        else None
                    )
                    completed_at = self._now(task.updated_at_micros)
                    record = ExperimentRecord(
                        task_id=task.task_id,
                        challenge_key=task.challenge_key,
                        training_support_ref=task.bindings.training_support_ref,
                        sampling_plan_ref=task.info.sampling_plan_ref,
                        measurement_contract_ref=task.info.measurement_contract_ref,
                        resolved_strategies=task.strategies,
                        parent_strategy_hashes=task.parents,
                        prior_resolution=task.prior,
                        plan_difference=difference,
                        evidence_class=outcome.evidence_class,
                        evidence_context=outcome.evidence_context,
                        execution_identity=ExecutionIdentity(
                            self._worker_digest,
                            self._environment_digest,
                            attempt_number,
                        ),
                        scientific_failure_category=outcome.scientific_failure_category,
                        resource_observations=outcome.resource_observations,
                        observed_resource_receipt_ref=(
                            outcome.observed_resource_receipt_ref
                        ),
                        aggregate_outcome_refs=outcome.aggregate_outcome_refs,
                        retention=outcome.retention,
                        completed_at_micros=completed_at,
                    )
                    receipt = self._receipt(
                        task,
                        ResearchTaskState.SUCCEEDED,
                        completed_at,
                        outcome=outcome,
                    )
                except Exception:  # noqa: BLE001 - invalid private output fails closed.
                    completed_at = self._now(task.updated_at_micros)
                    receipt = self._receipt(
                        task,
                        ResearchTaskState.FAILED_INFRA,
                        completed_at,
                        failure_class=InfrastructureFailureClass.INTERNAL,
                    )
                    self._transition(
                        task, ResearchTaskState.FAILED_INFRA, receipt=receipt
                    )
                    return self._view(task)
                task.record = record
                self._transition(task, ResearchTaskState.SUCCEEDED, receipt=receipt)
                return self._view(task)
        raise ResearchTaskProviderError(ResearchServiceErrorCode.INTERNAL_FAILURE)

    def get_experiment_record(self, task_id: ResearchTaskId) -> ExperimentRecord:
        """Trusted local retrieval; the private record has no wire operation."""

        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.record is None:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.TASK_NOT_FOUND)
            return task.record

    def records_authorized_for_learned_aggregation(
        self,
    ) -> tuple[ExperimentRecord, ...]:
        """Return only records with an explicit rights-owned reuse binding."""

        with self._lock:
            return tuple(
                task.record
                for task in self._tasks.values()
                if task.record is not None
                and task.record.retention.scope
                is ResearchRetentionScope.LEARNED_AGGREGATION_AUTHORIZED
            )


__all__ = (
    "InMemoryResearchTaskProvider",
    "ReceiptFindingDefinition",
    "ResearchCompilationResolver",
    "ResearchPriorResolver",
    "ResearchResourceResolver",
    "ResearchTaskProviderError",
    "ResearchTaskQueue",
)
