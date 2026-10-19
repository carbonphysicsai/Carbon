"""Authenticated tunnel to the unchanged twelve-operation research protocol.

The trusted composition installs one service per authenticated requester. This
adds no public listener and never sends research results through A7 submission.
"""

from __future__ import annotations

import asyncio
import base64
import binascii

from carbon.research.canonical import canonical_bytes, load_canonical
from carbon.research.model import (
    RESEARCH_NAMESPACE,
    CancelResearchTaskResult,
    DirectCancelTaskResultV3,
    DirectGetTaskResultV3,
    DirectStartTaskResultV3,
    DirectTaskStateV3,
    GetResearchResultResult,
    ReplyStatus,
    ResearchTaskState,
    ServiceCall,
    StartResearchTaskResult,
)
from carbon.research.service import LocalResearchService
from carbon.transport.gateway import AuthenticatedGateway


def decode_research_call(call):
    """Decode the existing research envelope after a gateway verified its caller.

    This helper grants no identity or execution authority. Receivers must bind
    the returned Challenge and operation to their authenticated service before
    dispatching it.
    """
    if (
        call.tool != RESEARCH_NAMESPACE
        or len(call.fields) != 1
        or call.fields[0].name != "call_base64"
    ):
        raise ValueError("research namespace and exact canonical call required")
    payload = call.fields[0].value
    if type(payload) is not str or len(payload.encode()) > 1024**2:
        raise ValueError("bounded canonical research call required")
    try:
        encoded = payload.encode("ascii")
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeError, binascii.Error):
        raise ValueError("canonical base64 research envelope required") from None
    if base64.b64encode(raw) != encoded:
        raise ValueError("noncanonical base64 research envelope")
    decoded = load_canonical(raw, ServiceCall)
    if decoded.namespace != RESEARCH_NAMESPACE:
        raise ValueError("research namespace mismatch")
    return decoded


class AuthenticatedResearchService:
    def __init__(self, gateway, services):
        if type(gateway) is not AuthenticatedGateway or type(services) is not dict:
            raise TypeError("trusted authenticated composition required")
        if any(
            type(k) is not str or type(v) is not LocalResearchService
            for k, v in services.items()
        ):
            raise TypeError("exact requester-bound research services required")
        if len({id(v) for v in services.values()}) != len(services):
            raise ValueError("research service cannot be shared between requesters")
        self.gateway = gateway
        self._services = dict(services)
        self._active = {}
        self._closing = False

    async def _receive(self, body, headers):
        received = await self.gateway.receive(body, headers)
        decoded = decode_research_call(received.call)
        service = self._services.get(received.requester.value)
        if service is None:
            raise ValueError("research requester unavailable")
        if decoded.request.challenge_key != self.gateway.challenge:
            raise ValueError("research challenge differs from authenticated context")
        # B-07G owns exact types, operations, bounds and disclosure. Never echo
        # the transport receipt, private provider or requester binding to agent.
        return received.requester.value, service, decoded

    async def call(self, body, headers):
        _owner, service, decoded = await self._receive(body, headers)
        return canonical_bytes(service.call(decoded))

    async def supervised_call(self, body, headers, compositions, *, task_mode=None):
        """D4 local envelope; the nominal twelve-operation v2 reply is retained.

        The trusted supervisor supplies compositions, never the caller. Waits
        happen without provider requests. An uncertain RUNNING task is returned
        for reconciliation and is never redispatched on replay.
        """
        owner, service, decoded = await self._receive(body, headers)
        composition = compositions.get(owner)
        if service.is_direct_context():
            return await self._supervised_direct(
                owner, service, decoded, composition, task_mode
            )
        if (
            composition is None
            or composition.service is not service
            or composition.executor.owner != owner
            or not service.binds_research_task_provider(composition.tasks)
        ):
            raise ValueError("exact authenticated research composition required")
        if task_mode not in {None, "start", "observe", "cancel"}:
            raise ValueError("unsupported trusted task mode")
        if task_mode in {"observe", "cancel"}:
            expected = (
                "get_research_result"
                if task_mode == "observe"
                else "cancel_research_task"
            )
            if decoded.operation != expected:
                raise ValueError("task observation operation differs")
            request = decoded.request
            if task_mode == "cancel":
                composition.tasks.cancel_observed_task(
                    request.task_id, request.challenge_key
                )
            operation_id, reply, task = composition.tasks.task_observation(
                request.task_id, request.challenge_key, count=task_mode == "observe"
            )
            from carbon.research.model import GetResearchResultRequest

            projected = service.project_task_observation(
                GetResearchResultRequest(request.challenge_key, request.task_id, 0),
                task,
                provider=composition.tasks,
            )
            if projected.status is not ReplyStatus.OK:
                raise ValueError("task observation disclosure rejected")
            initial = service.project_task_observation(
                GetResearchResultRequest(request.challenge_key, request.task_id, 0),
                reply.result.task,
                provider=composition.tasks,
            )
            if initial.status is not ReplyStatus.OK:
                raise ValueError("retained start disclosure rejected")
            return self._envelope(
                reply, projected.result.task, composition, operation_id=operation_id
            )
        if self._closing or (
            task_mode == "start" and decoded.operation != "start_research_task"
        ):
            raise ValueError("research supervisor is not accepting work")
        reply = service.call(decoded)
        task = None
        projection = None
        if reply.status is ReplyStatus.OK and type(reply.result) in {
            StartResearchTaskResult,
            GetResearchResultResult,
            CancelResearchTaskResult,
        }:
            task = reply.result.task
            if type(reply.result) is StartResearchTaskResult and hasattr(
                composition.tasks, "bind_task_observation"
            ):
                composition.tasks.bind_task_observation(reply)
            if (
                decoded.operation == "start_research_task"
                and task.state is ResearchTaskState.QUEUED
            ):
                key = (owner, task.task_id)
                if key not in self._active:
                    self._active[key] = (
                        composition,
                        asyncio.create_task(
                            asyncio.to_thread(
                                composition.tasks.run_queued_task, task.task_id
                            )
                        ),
                    )
                if task_mode is None:
                    task = await asyncio.shield(self._active[key][1])
            projection = composition.executor.public_result(task)
        return self._envelope(reply, task, composition, projection=projection)

    async def _supervised_direct(self, owner, service, decoded, composition, task_mode):
        """Versioned direct task supervision; historical v2 path is untouched."""
        import asyncio

        if (
            composition is None
            or composition.service is not service
            or composition.tasks.owner != owner
            or not service.binds_research_task_provider(composition.tasks)
        ):
            raise ValueError("exact authenticated direct composition required")
        expected = {
            "start": "start_research_task",
            "observe": "get_research_result",
            "cancel": "cancel_research_task",
        }
        if task_mode not in (None, *expected):
            raise ValueError("unsupported direct task mode")
        if task_mode is not None and decoded.operation != expected[task_mode]:
            raise ValueError("direct task operation differs")
        if self._closing and decoded.operation == "start_research_task":
            raise ValueError("direct research supervisor is not accepting work")
        reply = service.call(decoded)
        task = (
            reply.result.task
            if reply.status is ReplyStatus.OK
            and type(reply.result)
            in (
                DirectStartTaskResultV3,
                DirectGetTaskResultV3,
                DirectCancelTaskResultV3,
            )
            else None
        )
        # Hydrate retained QUEUED work on the first authenticated call after
        # restart, and dispatch a newly accepted start through the same owner.
        if not self._closing:
            for queued in composition.tasks.queued_tasks():
                key = (owner, queued)
                if key not in self._active:
                    self._active[key] = (
                        composition,
                        asyncio.create_task(
                            asyncio.to_thread(composition.tasks.run_queued_task, queued)
                        ),
                    )
        if (
            task is not None
            and type(reply.result) is DirectStartTaskResultV3
            and task_mode is None
            and task.state is DirectTaskStateV3.QUEUED
        ):
            task = await asyncio.shield(self._active[(owner, task.task_id)][1])
        projection = composition.tasks.public_result(task) if task is not None else None
        return {
            "schema": "carbon.autoresearch.supervised-direct-reply.v3",
            "protocol_reply_base64": base64.b64encode(canonical_bytes(reply)).decode(
                "ascii"
            ),
            "terminal_observation_base64": (
                base64.b64encode(canonical_bytes(task)).decode("ascii")
                if task is not None
                else None
            ),
            "public_result": projection,
            "requires_reconciliation": (
                composition.tasks.requires_reconciliation(task.task_id)
                if task is not None
                else False
            ),
            "official_eligible": False,
        }

    @staticmethod
    def _envelope(reply, task, composition, *, operation_id=None, projection=None):
        if task is not None and projection is None:
            projection = composition.executor.public_result(task)
        return {
            "schema": "carbon.autoresearch.supervised-reply.v1",
            "protocol_reply_base64": base64.b64encode(canonical_bytes(reply)).decode(
                "ascii"
            ),
            "terminal_observation_base64": (
                base64.b64encode(canonical_bytes(task)).decode("ascii")
                if task
                else None
            ),
            "public_result": projection,
            "requires_reconciliation": _requires_reconciliation(task, composition),
            "official_eligible": False,
            **(
                {"original_operation_id": operation_id}
                if operation_id is not None
                else {}
            ),
        }

    async def shutdown_tasks(self):
        """Stop owned admission, request domain cancellation, and await workers."""
        self._closing = True
        active = tuple(self._active.items())
        errors = []
        for (_owner, task_id), (composition, future) in active:
            if not future.done():
                try:
                    composition.tasks.cancel_observed_task(
                        task_id, self.gateway.challenge
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)
        if active:
            joined = asyncio.gather(
                *(future for _, (_, future) in active), return_exceptions=True
            )
            interrupted = False
            while not joined.done():
                try:
                    await asyncio.shield(joined)
                except asyncio.CancelledError:
                    interrupted = True
            outcomes = joined.result()
            if errors or any(isinstance(value, BaseException) for value in outcomes):
                raise ValueError("owned task supervision requires reconciliation")
            self._active.clear()
            if interrupted:
                raise asyncio.CancelledError
        self._active.clear()


def _requires_reconciliation(task, composition):
    """Whether this task's outcome still holds unsettled work.

    A task still running needs reconciling, and so does a terminal task whose
    ledger operation is still RESERVED: a carrier failure can end the task
    FAILED_INFRA while its worker's cleanup and accounting stay unresolved.
    The task state alone would report that as settled.
    """
    if task is None:
        return False
    if task.state in {ResearchTaskState.RUNNING, ResearchTaskState.CANCEL_REQUESTED}:
        return True
    executor = getattr(composition, "executor", None)
    ledger = getattr(executor, "ledger", None)
    if ledger is None:
        return False
    return (
        ledger.operation_state(task.task_id.value, owner=executor.owner) == "RESERVED"
    )
