"""Scaffolding for deliberately non-conforming MCP servers.

These stubs exist only to be rejected by the conformance runner. Each one is a
plausible-looking endpoint that violates exactly one published requirement, so
that "the suite rejects it" is evidence about that requirement and not about
some unrelated defect.

This is not a second Carbon MCP server. There is no campaign ledger, no task
store, no research service and no domain logic: the operation map below exists
only so replay and conflict semantics can be expressed well enough to be got
wrong on purpose.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.tools import Tool
from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model

PREFIX = "carbon_research_v2__"
OPERATIONS = (
    "get_challenge_info",
    "get_interaction_manifest",
    "get_prior",
    "get_mock_scaffold",
    "dry_validate",
    "compile_strategy",
    "inspect_prior_alignment",
    "inspect_resources",
    "forecast_resources",
    "start_research_task",
    "get_research_result",
    "cancel_research_task",
)
FIELDS = {
    "dry_validate": ("strategy",),
    "compile_strategy": ("strategy",),
    "inspect_prior_alignment": ("strategy",),
    "inspect_resources": ("strategy",),
    "forecast_resources": ("strategy", "seconds"),
    "start_research_task": (
        "kind",
        "strategy",
        "action",
        "arguments",
        "hypothesis",
        "expected_effect",
    ),
    "get_research_result": ("task_id", "poll_sequence"),
    "cancel_research_task": ("task_id",),
}


class StrictArguments(ArgModelBase):
    model_config = ConfigDict(strict=True, extra="forbid")


class ExactMetadata(FuncMetadata):
    """Reject encoded JSON strings where an object is required, as Carbon does."""

    def pre_parse_json(self, data):
        return data


class Result(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    operation: str
    operation_id: str
    payload: dict[str, JsonValue]
    requires_reconciliation: bool
    official_eligible: Literal[False]


def _field_types():
    return {
        "operation_id": (
            Annotated[str, Field(pattern=r"^[A-Za-z0-9._:-]{16,114}$")],
            ...,
        ),
        "strategy": (dict[str, JsonValue] | None, ...),
        "seconds": (Annotated[int, Field(ge=1, le=600)], ...),
        "task_id": (Annotated[str, Field(pattern=r"^rtsk_[a-f0-9]{64}$")], ...),
        "poll_sequence": (Annotated[int, Field(ge=0, le=9999)], ...),
        "kind": (Literal["practice", "workspace"], ...),
        "action": (Literal["public_material", "notebook"] | None, ...),
        "arguments": (dict[str, JsonValue] | None, ...),
        "hypothesis": (Annotated[str, Field(min_length=1, max_length=2048)], ...),
        "expected_effect": (Annotated[str, Field(min_length=1, max_length=2048)], ...),
    }


def build(handler, *, name="carbon-nonconforming-stub", resources=None, identity=True):
    """Assemble a stub whose every tool defers to one handler.

    ``handler(operation, operation_id, arguments) -> dict`` returns the payload,
    or raises ToolError. The scaffold supplies only catalogue shape so a stub
    reaches the semantic checks it is meant to fail.

    ``identity=True`` adds conforming replay and conflict bookkeeping around the
    handler, so that a stub fails the one check it targets rather than tripping
    every identity check by omission. A stub whose violation *is* identity
    passes ``identity=False`` and does its own bookkeeping.
    """
    import json as _json

    first_call = {}

    def wrap(inner):
        def bookkeeping(operation, operation_id, arguments):
            if operation != "start_research_task":
                return inner(operation, operation_id, arguments)
            fingerprint = _json.dumps(arguments, sort_keys=True, default=str)
            if operation_id in first_call:
                recorded, payload = first_call[operation_id]
                if recorded != fingerprint:
                    refuse("INVALID_ARGUMENT", False)
                return payload
            payload = inner(operation, operation_id, arguments)
            first_call[operation_id] = (fingerprint, payload)
            return payload

        return bookkeeping

    if identity:
        handler = wrap(handler)
    types = _field_types()
    tools = []
    for operation in OPERATIONS:
        parameters = {"operation_id": types["operation_id"]}
        for field in FIELDS.get(operation, ()):
            parameters[field] = types[field]
        model = create_model(
            operation + "Arguments", __base__=StrictArguments, **parameters
        )

        def invoke(_operation=operation, **arguments):
            operation_id = arguments.pop("operation_id")
            payload = handler(_operation, operation_id, arguments)
            return Result(
                operation=_operation,
                operation_id=operation_id,
                payload=payload,
                requires_reconciliation=False,
                official_eligible=False,
            )

        tools.append(
            Tool(
                fn=invoke,
                name=PREFIX + operation,
                description=f"Stub {operation}; exists only to be rejected.",
                parameters=model.model_json_schema(),
                fn_metadata=ExactMetadata(arg_model=model, output_model=Result),
                is_async=False,
            )
        )
    server = MCPServer(name, version="0.0.0", tools=tools)
    from mcp.server.mcpserver.resources import FunctionResource

    for uri, text in (resources or {"carbon://research/v1/capabilities": "{}"}).items():
        server.add_resource(
            FunctionResource(
                uri=uri, name=uri, mime_type="text/plain", fn=(lambda _t=text: _t)
            )
        )
    return server


def serve(server):
    asyncio.run(server.run_stdio_async())


def refuse(code, dispatch):
    """Raise the coded failure shape the published error contract requires."""
    raise ToolError(f"{code}; dispatch_may_have_occurred={str(dispatch).lower()}")
