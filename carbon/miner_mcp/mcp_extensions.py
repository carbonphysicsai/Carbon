"""Negotiated MCP Tasks view of Carbon's existing durable research operations.

No task store or execution state lives here. The trusted adapter owns admission,
current authorized projection and supervised cleanup. Optional SDK imports occur
only when the standard server factory is called.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

from carbon.development_session.research_tools import PREFIX
from carbon.miner_mcp.standard import AdapterFailure, ResearchToolRequest

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


def make_tasks_extension(adapter, *, guard, validate_start):
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
            projected = task_projection(result, detailed=True)
            if projected is None or projected["taskId"] != params.task_id:
                raise ValueError("unavailable task")
            return projected
        except (AdapterFailure, ValueError, KeyError, TypeError, OverflowError):
            # Do not reveal foreign task existence, paths or controller errors.
            raise MCPError(
                -32602, "Task unavailable; reconcile through the operator"
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
            try:
                arguments = validate_start(params.arguments)
            except ValidationError:
                return {
                    "resultType": "complete",
                    "content": [{"type": "text", "text": "INVALID_ARGUMENTS"}],
                    "isError": True,
                }
            identity = arguments.pop("operation_id")
            try:
                result = await adapter.start_task(
                    ResearchToolRequest("start_research_task", identity, arguments)
                )
                return task_projection(result, detailed=False) or tool_result(result)
            except (AdapterFailure, ValueError, KeyError, TypeError, OverflowError):
                return {
                    "resultType": "complete",
                    "content": [
                        {
                            "type": "text",
                            "text": "OPERATIONAL_STOP; reconcile before retry",
                        }
                    ],
                    "isError": True,
                }

    return ResearchTasks()
