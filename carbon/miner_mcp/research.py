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
    GetResearchResultResult,
    ReplyStatus,
    ResearchTaskState,
    ServiceCall,
    StartResearchTaskResult,
)
from carbon.research.service import LocalResearchService
from carbon.transport.gateway import AuthenticatedGateway


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
        call = received.call
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
            "requires_reconciliation": task is not None
            and task.state
            in {ResearchTaskState.RUNNING, ResearchTaskState.CANCEL_REQUESTED},
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
