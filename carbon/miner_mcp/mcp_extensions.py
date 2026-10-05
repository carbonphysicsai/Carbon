"""Negotiated MCP Tasks view of Carbon's existing durable research operations.

No task store or execution state lives here. The trusted adapter owns admission,
current authorized projection and supervised cleanup. Optional SDK imports occur
only when the standard server factory is called.

Refusals read exactly as the plain tools' do (`serving.refusal`): the adapter's
own closed code, whether anything may have started, the field to blame for an
invalid argument, and the fixed next action (LP-PROD-B). A task observation
tells "this task is unavailable" (unknown, or not yours: one answer for both)
apart from "this observation failed" by JSON-RPC error code, and says whether
the same observation is worth retrying (`observation_error`).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

from carbon.development_session.research_tools import PREFIX
from carbon.miner_mcp import serving
from carbon.miner_mcp.standard import (
    AdapterCode,
    AdapterFailure,
    ResearchToolRequest,
)

TASKS_EXTENSION = "io.modelcontextprotocol/tasks"
PROTOCOL_VERSIONS = frozenset({"2026-07-28"})
_TASK_ID = re.compile(r"^rtsk_[a-f0-9]{64}$")
_STATES = {
    "QUEUED": "working",
    "RUNNING": "working",
    "CANCEL_REQUESTED": "working",
    "SUCCEEDED": "completed",
    "FAILED_INFRA": "completed",
    "CANCELLED": "cancelled",
}


def tool_result(result):
    """Preserve the fallback tool's public structured result and text equivalent."""
    structured = {
        "operation": result.operation,
        "operation_id": result.operation_id,
        "payload": result.payload,
        "requires_reconciliation": result.requires_reconciliation,
        "official_eligible": result.official_eligible,
    }
    return {
        "resultType": "complete",
        "content": [{"type": "text", "text": json.dumps(structured, allow_nan=False)}],
        "structuredContent": structured,
        "isError": False,
    }


def task_projection(result, *, detailed):
    """Return no handle for an admission rejection; never fabricate task state."""
    payload = result.payload
    view = payload.get("terminal_task")
    if view is None:
        view = payload.get("reply", {}).get("result", {}).get("task")
    if view is None:
        return None
    identity = view["task_id"]["value"]
    if type(identity) is not str or _TASK_ID.fullmatch(identity) is None:
        raise ValueError("invalid public task identity")
    state = view["state"]
    status = _STATES[state]

    def timestamp(field):
        micros = view[field]
        if type(micros) is not int:
            raise ValueError("invalid public task timestamp")
        instant = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=micros)
        return instant.isoformat(timespec="microseconds").replace("+00:00", "Z")

    task = {
        "resultType": "complete" if detailed else "task",
        "taskId": identity,
        "status": status,
        "createdAt": timestamp("created_at_micros"),
        "lastUpdatedAt": timestamp("updated_at_micros"),
        # The bounded existing store does not evict tasks on grant expiry.
        "ttlMs": None,
        "pollIntervalMs": 1000,
        "statusMessage": state,
    }
    if detailed and status == "completed":
        task["result"] = tool_result(result)
    return task


#: JSON-RPC error codes for a failed task observation: the task itself is
#: unavailable (invalid params), or this observation failed (internal error).
TASK_UNAVAILABLE_ERROR = -32602
OBSERVATION_FAILED_ERROR = -32603


def observation_error(code):
    """(JSON-RPC code, message) for a failed tasks/get or tasks/cancel.

    One answer for every way the task can be unavailable - unknown, or
    another miner's - so the two cannot be told apart (`-32602
    TASK_NOT_FOUND`). Every other failure keeps its own code (`-32603`): it
    says nothing about whether the task exists, so it is never reported as a
    missing task, which could send an agent to start its running work again.
    `retry=true` only for the codes after which the same observation may
    succeed (`serving.OBSERVATION_RETRYABLE`: a stopped signer, a campaign not
    admitting, a dropped registration read); an observation changes nothing,
    and a cancellation reuses one cancellation identity. Everything else -
    a result this server will not forward, the server's binding, a spent
    limit - is `retry=false`.
    """
    if code in serving.TASK_UNAVAILABLE:
        return TASK_UNAVAILABLE_ERROR, (
            "TASK_NOT_FOUND; retry=false; next_action="
            + serving.NEXT_ACTION[AdapterCode.TASK_NOT_FOUND.value]
        )
    retry = "true" if code in serving.OBSERVATION_RETRYABLE else "false"
    return OBSERVATION_FAILED_ERROR, (
        code + "; retry=" + retry + "; next_action=" + serving.observation_action(code)
    )


def invalid_field(error, fields):
    """The schema field a validation error is about, or None: only a name
    this server declared, never a key the caller invented."""
    for detail in error.errors():
        location = detail.get("loc") or ()
        if location and location[0] in fields:
            return location[0]
    return None


def make_tasks_extension(adapter, *, guard, validate_start, fields=frozenset()):
    from mcp.server.extension import Extension, MethodBinding
    from mcp.server.mcpserver import require_client_extension
    from mcp.shared.exceptions import MCPError
    from mcp.types import InputResponses, RequestParams
    from pydantic import ConfigDict, Field, ValidationError, field_validator

    class TaskParams(RequestParams):
        model_config = ConfigDict(strict=True, extra="forbid")
        task_id: str = Field(alias="taskId", pattern=r"^rtsk_[a-f0-9]{64}$")

    class UpdateParams(TaskParams):
        input_responses: InputResponses = Field(alias="inputResponses", max_length=64)

        @field_validator("input_responses", mode="before")
        @classmethod
        def bounded_responses(cls, value):
            if len(json.dumps(value, allow_nan=False).encode("utf-8")) > 65536:
                raise ValueError("bounded input responses required")
            return value

    def check(ctx):
        if guard is not None:
            guard()
        require_client_extension(ctx, TASKS_EXTENSION)

    async def existing(ctx, params, *, cancel=False):
        check(ctx)
        try:
            result = await (
                adapter.cancel_task(params.task_id)
                if cancel
                else adapter.observe_task(params.task_id)
            )
        except AdapterFailure as failure:
            # Never foreign task existence, paths or controller errors: only
            # the closed code, read as unavailable or as worth a retry.
            raise MCPError(*observation_error(failure.code.value)) from None
        try:
            projected = task_projection(result, detailed=True)
            if projected is None or projected["taskId"] != params.task_id:
                raise ValueError("unprojectable task")
            return projected
        except (ValueError, KeyError, TypeError, OverflowError):
            # The adapter answered for this campaign's own task, so it is not
            # a missing task; on a cancel the cancellation has already run.
            # INVALID_RESULT, retry=false, and never "nothing changed".
            raise MCPError(
                *observation_error(AdapterCode.INVALID_RESULT.value)
            ) from None

    class ResearchTasks(Extension):
        identifier = TASKS_EXTENSION

        def methods(self):
            return (
                MethodBinding("tasks/get", TaskParams, self.get, PROTOCOL_VERSIONS),
                MethodBinding(
                    "tasks/cancel", TaskParams, self.cancel, PROTOCOL_VERSIONS
                ),
                MethodBinding(
                    "tasks/update", UpdateParams, self.update, PROTOCOL_VERSIONS
                ),
            )

        async def get(self, ctx, params):
            return await existing(ctx, params)

        async def cancel(self, ctx, params):
            await existing(ctx, params, cancel=True)
            # An intent acknowledgement is not evidence of worker release.
            return {"resultType": "complete"}

        async def update(self, ctx, params):
            await existing(ctx, params)
            # Carbon requests no client-supplied grant/science decisions here.
            # Released Tasks semantics ignore responses to nonexistent requests.
            return {"resultType": "complete"}

        async def intercept_tool_call(self, params, ctx, call_next):
            capabilities = ctx.session.client_capabilities
            declared = capabilities.extensions if capabilities else None
            if (
                ctx.protocol_version not in PROTOCOL_VERSIONS
                or not declared
                or TASKS_EXTENSION not in declared
                or params.name != PREFIX + "start_research_task"
            ):
                return await call_next(ctx)
            check(ctx)

            def refused(text):
                return {
                    "resultType": "complete",
                    "content": [{"type": "text", "text": text}],
                    "isError": True,
                }

            try:
                arguments = validate_start(params.arguments or {})
            except ValidationError as error:
                # Named the way the plain tool would be, with the one field to
                # correct when the schema can name it; nothing was dispatched.
                return refused(
                    serving.refusal(
                        AdapterCode.INVALID_ARGUMENT.value,
                        dispatch_may_have_occurred=False,
                        field=invalid_field(error, fields),
                    )
                )
            identity = arguments.pop("operation_id")
            try:
                result = await adapter.start_task(
                    ResearchToolRequest("start_research_task", identity, arguments)
                )
            except AdapterFailure as failure:
                # The adapter's own code - SIGNER_NOT_RUNNING, NO_CAMPAIGN,
                # OPERATION_ID_REUSED ... - and its honest dispatch flag; a
                # refusal carrying a registered correction names its field.
                return refused(
                    serving.refusal(
                        failure.code.value,
                        dispatch_may_have_occurred=failure.dispatch_may_have_occurred,
                        field=failure.field,
                    )
                )
            try:
                return task_projection(result, detailed=False) or tool_result(result)
            except (ValueError, KeyError, TypeError, OverflowError):
                # The start returned, so the task may exist: never "nothing ran".
                return refused(
                    serving.refusal(
                        AdapterCode.INVALID_RESULT.value,
                        dispatch_may_have_occurred=True,
                    )
                )

    return ResearchTasks()
