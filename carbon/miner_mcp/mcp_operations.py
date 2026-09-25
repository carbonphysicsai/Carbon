"""The MCP door onto the shared miner operations table.

Every operation in `scripts.dev.miner_launchpad.operations.OPERATIONS` becomes
one tool here, generated from the table: its name, description, arguments and
gates all come from there. This module defines no operation and no gate, so it
cannot come to hold one the browser lacks. The browser's routes are generated
from the same table.

Two tools are not operations. `carbon_attach_campaign` binds this session to one
campaign for deeper research - the workspace, run_python, Julia - and
`carbon_detach_campaign` releases it. They are how an MCP session reaches the
research tools, which the browser does not host; the journey itself - launch,
practice, observe, freeze, submit, halt, resume - needs neither.

Nothing here is Carbon-issued. A miner's own client, their own runner profile
and their own registered hotkey are the whole of it.
"""

from __future__ import annotations

import asyncio
import contextlib

PREFIX = "carbon_"


def operation_tool_names():
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    return tuple(PREFIX + name for name in OPERATIONS)


def _field_type(kind):
    from pydantic import JsonValue, StrictBool, StrictStr

    return {
        "string": StrictStr,
        "boolean": StrictBool,
        # A strategy or budget arrives as an object, or as JSON text from a
        # client that sends strings; the operation parses either the same way.
        "object": JsonValue,
    }[kind]


def make_operation_tools(host, *, guard=None):
    """One tool per operation in the shared table, calling `perform`."""
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.mcpserver.tools import Tool
    from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
    from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model

    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.operations import FIELDS, OPERATIONS, perform

    class StrictArguments(ArgModelBase):
        model_config = ConfigDict(strict=True, extra="forbid")

    class ExactMetadata(FuncMetadata):
        def pre_parse_json(self, data):
            return data

    class OperationResult(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        operation: str
        payload: JsonValue
        official_eligible: bool = False

    def tool_for(op):
        parameters = {}
        for field in sorted(op.required | op.optional):
            kind, meaning = FIELDS[field]
            default = ... if field in op.required else None
            annotation = _field_type(kind)
            if field not in op.required:
                annotation = annotation | None
            parameters[field] = (annotation, Field(default, description=meaning))
        model = create_model(
            "operation_" + op.name, __base__=StrictArguments, **parameters
        )

        async def invoke(**arguments):
            if guard is not None:
                guard()
            request = {k: v for k, v in arguments.items() if v is not None}
            try:
                payload = await asyncio.to_thread(perform, host, op.name, request)
            except Rejected as refused:
                # A closed code a client can branch on; never an argument back.
                raise ToolError(refused.code) from None
            return OperationResult(operation=op.name, payload=payload)

        gates = ", ".join(op.gates)
        return Tool(
            fn=invoke,
            name=PREFIX + op.name,
            description=f"{op.summary} Gates: {gates}.",
            parameters=model.model_json_schema(),
            fn_metadata=ExactMetadata(arg_model=model, output_model=OperationResult),
            is_async=True,
        )

    return [tool_for(op) for op in OPERATIONS.values()]


class Attachment:
    """This session's one research attachment, if any.

    Attaching holds the campaign's ownership lock for as long as it lasts, so
    the operations that take that lock - practice, freeze, submit - answer
    campaign_busy until the session detaches. One session, one campaign.
    """

    def __init__(self, server, configuration):
        self.server = server
        self.configuration = configuration
        self.stack = None
        self.campaign = None
        self.tools = ()
        self.resources = ()

    async def attach(self, campaign):
        from carbon.miner_mcp.open_tier import CampaignAlreadyAttached, attach_campaign
        from carbon.miner_mcp.standard_cli import attached

        if self.stack is not None:
            raise CampaignAlreadyAttached("this session already owns a campaign")
        stack = contextlib.AsyncExitStack()
        before = set(self.server._resource_manager._resources)
        try:
            adapter, _ = await stack.enter_async_context(
                attached(self.configuration, campaign)
            )
            self.tools = attach_campaign(self.server, adapter)
        except BaseException:
            await stack.aclose()
            raise
        self.resources = tuple(set(self.server._resource_manager._resources) - before)
        self.stack, self.campaign = stack, campaign
        return {"attached": campaign, "research_tools": list(self.tools)}

    async def detach(self):
        if self.stack is None:
            return {"attached": None}
        tools = self.server._tool_manager._tools
        for name in self.tools:
            tools.pop(name, None)
        resources = self.server._resource_manager._resources
        for uri in self.resources:
            resources.pop(uri, None)
        self.server._carbon_attached = False
        stack, campaign = self.stack, self.campaign
        self.stack = self.campaign = None
        self.tools = self.resources = ()
        await stack.aclose()
        return {"detached": campaign}


def make_attachment_tools(attachment, *, guard=None):
    """Attach and detach: the MCP session's way into the research tools."""
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.mcpserver.tools import Tool
    from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
    from pydantic import (
        BaseModel,
        ConfigDict,
        Field,
        JsonValue,
        StrictStr,
        create_model,
    )

    class StrictArguments(ArgModelBase):
        model_config = ConfigDict(strict=True, extra="forbid")

    class ExactMetadata(FuncMetadata):
        def pre_parse_json(self, data):
            return data

    class AttachmentResult(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        payload: dict[str, JsonValue]

    attach_model = create_model(
        "attach_campaign",
        __base__=StrictArguments,
        campaign=(StrictStr, Field(..., description="The campaign id to research in.")),
    )
    detach_model = create_model("detach_campaign", __base__=StrictArguments)

    async def attach(campaign):
        if guard is not None:
            guard()
        try:
            return AttachmentResult(payload=await attachment.attach(campaign))
        except Exception:  # noqa: BLE001 - closed refusal, never a trace or path
            raise ToolError(
                "attach_unavailable; the campaign must be yours, unfinished, "
                "not busy with another operation, and your hotkey registered"
            ) from None

    async def detach():
        if guard is not None:
            guard()
        return AttachmentResult(payload=await attachment.detach())

    return [
        Tool(
            fn=attach,
            name=PREFIX + "attach_campaign",
            description=(
                "Bind this session to one of your campaigns for deeper research: "
                "the workspace, run_python and Julia tools appear. Practice, "
                "freeze and submit answer campaign_busy until you detach."
            ),
            parameters=attach_model.model_json_schema(),
            fn_metadata=ExactMetadata(
                arg_model=attach_model, output_model=AttachmentResult
            ),
            is_async=True,
        ),
        Tool(
            fn=detach,
            name=PREFIX + "detach_campaign",
            description="Release this session's campaign and its research tools.",
            parameters=detach_model.model_json_schema(),
            fn_metadata=ExactMetadata(
                arg_model=detach_model, output_model=AttachmentResult
            ),
            is_async=True,
        ),
    ]
