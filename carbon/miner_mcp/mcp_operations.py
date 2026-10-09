"""The MCP door onto the shared miner operations table.

Every operation in `scripts.dev.miner_launchpad.operations.OPERATIONS` becomes
one tool here, generated from the table: its name, description, arguments and
gates all come from there. This module defines no operation and no gate, so it
cannot come to hold one the browser lacks. The browser's routes are generated
from the same table.

Two tools are not operations. `carbon_attach_campaign` binds this session to one
campaign for deeper research - the workspace, run_python, Julia - and
`carbon_detach_campaign` releases it. They are how an MCP session reaches the
research tools; the Control Center's Tools tab reaches the same tools through
the same attachment and the same ownership lock (RSURF-D15), so one holder at a
time uses them. The journey itself - launch, practice, observe, freeze,
submit, halt, resume - needs neither.

What this door adds, and only as a door (LP-PROD-B): schemas that state the
table's closed values and the fields a body cannot run without; a launch
idempotency key generated when the client sends none, and returned; refusals as
JSON with the code, the field to correct and the next step - the refusal's
own step when it carries one, otherwise the refusal catalog's, so the step is
the one the browser's door gives for the same refusal (W1, repair); a
run's images as MCP image content rather than base64 inside JSON; and, while
this session is attached to a campaign, an up-front `campaign_busy` for the
calls whose body needs that campaign's lock, instead of a run that cannot take
it.

Nothing here is Carbon-issued. A miner's own client, their own runner profile
and their own registered hotkey are the whole of it.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets

PREFIX = "carbon_"
DETACH = PREFIX + "detach_campaign"
#: Operations whose idempotency key this door generates when none is sent:
#: launch needs one, and a lost response is otherwise unrecoverable.
GENERATES_KEY = frozenset({"launch"})
#: Raster images `run_output` inlines, as MCP image content.
_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
#: How this door's errors read, as every tool description states it. Two
#: layers: the MCP SDK validates arguments against the schema first and
#: reports a violation in its own words, so a missing required field (launch's
#: challenge or challenge_version) or a value outside an enum never reaches
#: the body; a refusal after that is this door's closed JSON. The SDK puts its
#: "Error executing tool <name>: " prefix before either.
REFUSAL_NOTE = (
    "Arguments that do not match the schema are refused by the MCP SDK's "
    "validation message. A refusal after validation is JSON - error (a "
    "closed code), field when one is to blame, and next_step - following the "
    "SDK's 'Error executing tool <name>: ' prefix."
)


def operation_tool_names():
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    return tuple(PREFIX + name for name in OPERATIONS)


def _field_type(kind):
    from pydantic import JsonValue, StrictBool, StrictFloat, StrictInt, StrictStr

    return {
        "string": StrictStr,
        "boolean": StrictBool,
        "integer": StrictInt,
        # A JSON number (Graphite's research_share): an integer or a float,
        # never a boolean; the operation checks its range.
        "number": StrictInt | StrictFloat,
        # A strategy or budget arrives as an object, or as JSON text from a
        # client that sends strings; the operation parses either the same way.
        "object": JsonValue,
    }[kind]


def _annotation(field, kind):
    """A field's type: its closed values as a Literal where the table states
    them (agent, halt's action, note_kind), otherwise its JSON type."""
    from typing import Literal

    from scripts.dev.miner_launchpad.operations import CHOICES

    if field in CHOICES:
        return Literal[CHOICES[field]]
    return _field_type(kind)


def generated_key():
    """A launch idempotency key from this door: `mcp-` and 32 hex digits,
    within the table's 16-80 letters, digits, - or _."""
    return "mcp-" + secrets.token_hex(16)


def json_refusal(body) -> str:
    """A refusal's closed JSON body, as a client parses it."""
    return json.dumps(body, sort_keys=True)


def _attachment(ctx):
    """This session's research attachment, from a tool call's context."""
    if ctx is None:
        return None
    try:
        server = ctx.mcp_server
    except (ValueError, AttributeError):  # outside a request
        return None
    return getattr(server, "_carbon_attachment", None)


def _images_as_content(result):
    """A run_output result's images as MCP image content, not base64 in JSON.

    The structured result keeps every file entry; an inlined image's
    `image_base64` becomes `image_content`, the index of the content block that
    carries it (block 0 is the JSON text). A client that renders images shows
    them; one that reads JSON is not handed megabytes of base64. Only bytes
    `run_output` already recognised as a raster image travel this way.
    """
    from mcp.types import CallToolResult, ImageContent, TextContent

    structured = result.structured_content
    if (
        result.is_error
        or type(structured) is not dict
        or structured.get("operation") != "run_output"
        or type(structured.get("payload")) is not dict
        or type(structured["payload"].get("files")) is not list
    ):
        return result
    files, images = [], []
    for entry in structured["payload"]["files"]:
        if (
            type(entry) is dict
            and type(entry.get("image_base64")) is str
            and entry.get("media_type") in _IMAGE_TYPES
        ):
            images.append(
                ImageContent(
                    type="image",
                    data=entry["image_base64"],
                    mime_type=entry["media_type"],
                )
            )
            entry = {k: v for k, v in entry.items() if k != "image_base64"}
            entry["image_content"] = len(images)
        files.append(entry)
    if not images:
        return result
    structured = {
        **structured,
        "payload": {**structured["payload"], "files": files},
    }
    return CallToolResult(
        content=[
            TextContent(type="text", text=json.dumps(structured, indent=2)),
            *images,
        ],
        structured_content=structured,
    )


def _door_notes(op):
    """What only this door adds to an operation's description."""
    from scripts.dev.miner_launchpad.operations import takes_owner_lock

    notes = []
    if op.name in GENERATES_KEY:
        notes.append(
            "idempotency_key is optional here: omitted, the server generates "
            "one and returns it as idempotency_key. Send your own to make a "
            "retry idempotent; without one, a retry after a lost response "
            "launches a second campaign."
        )
    if op.name == "launch":
        notes.append(
            "The campaign is carried out by the campaigns' supervisor, not "
            "this session, so this session may end. If carbon_observe shows "
            "in_flight.state QUEUED with supervisor_running false, nothing is "
            "carrying it out yet: carbon_observe starts a supervisor for it, "
            "so observe again after a few seconds; if it stays so, open the "
            "Control Center, which supervises while it runs."
        )
    if takes_owner_lock(op.name, {}):
        notes.append(
            "While this session is attached to the campaign "
            "(carbon_attach_campaign) this answers campaign_busy: call "
            "carbon_detach_campaign first."
        )
    elif op.name == "halt":
        notes.append(
            "action=reconcile answers campaign_busy while this session is "
            "attached to the campaign: call carbon_detach_campaign first."
        )
    notes.append(REFUSAL_NOTE)
    return " ".join(notes)


def make_operation_tools(host, *, guard=None):
    """One tool per operation in the shared table, calling `perform`."""
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.mcpserver.tools import Tool
    from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
    from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model

    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.operations import (
        BODY_REQUIRED,
        FIELDS,
        OPERATIONS,
        perform,
        refusal,
        takes_owner_lock,
    )

    class StrictArguments(ArgModelBase):
        model_config = ConfigDict(strict=True, extra="forbid")

    class ExactMetadata(FuncMetadata):
        def pre_parse_json(self, data):
            return data

        def convert_result(self, result):
            return _images_as_content(super().convert_result(result))

    class OperationResult(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        operation: str
        payload: JsonValue
        official_eligible: bool = False
        #: The key this call ran under: the client's, or the one generated.
        idempotency_key: str | None = None

    def tool_for(op):
        parameters = {}
        required = (op.required | BODY_REQUIRED.get(op.name, frozenset())) - (
            {"idempotency_key"} if op.name in GENERATES_KEY else set()
        )
        for field in sorted(op.required | op.optional):
            kind, meaning = FIELDS[field]
            default = ... if field in required else None
            annotation = _annotation(field, kind)
            if field not in required:
                annotation = annotation | None
            parameters[field] = (annotation, Field(default, description=meaning))
        model = create_model(
            "operation_" + op.name, __base__=StrictArguments, **parameters
        )

        async def invoke(ctx=None, **arguments):
            if guard is not None:
                guard()
            request = {k: v for k, v in arguments.items() if v is not None}
            if op.name in GENERATES_KEY and "idempotency_key" not in request:
                request["idempotency_key"] = generated_key()
            attachment = _attachment(ctx)
            if (
                attachment is not None
                and attachment.campaign is not None
                and request.get("campaign") == attachment.campaign
                and takes_owner_lock(op.name, request)
            ):
                # This session holds the campaign's lock itself: answered here,
                # before the body starts a run that could not take it.
                raise ToolError(
                    json_refusal(
                        {
                            **refusal("campaign_busy"),
                            "next_step": (
                                "this session is attached to the campaign: "
                                "call " + DETACH + ", then retry"
                            ),
                        }
                    )
                )
            try:
                payload = await asyncio.to_thread(perform, host, op.name, request)
            except Rejected as refused:
                # A closed code a client can branch on, the field to correct
                # and the next step - the refusal's own when it carries one,
                # as the browser's door sends it, with a compute budget
                # refusal's numbers; never an argument back.
                raise ToolError(
                    json_refusal(
                        refusal(
                            refused.code,
                            getattr(refused, "next_step", None),
                            getattr(refused, "budget", None),
                        )
                    )
                ) from None
            return OperationResult(
                operation=op.name,
                payload=payload,
                idempotency_key=request.get("idempotency_key"),
            )

        gates = ", ".join(op.gates)
        return Tool(
            fn=invoke,
            name=PREFIX + op.name,
            description=f"{op.summary} Gates: {gates}. {_door_notes(op)}",
            parameters=model.model_json_schema(),
            fn_metadata=ExactMetadata(arg_model=model, output_model=OperationResult),
            is_async=True,
            context_kwarg="ctx",
        )

    return [tool_for(op) for op in OPERATIONS.values()]


class AttachmentBusy(RuntimeError):
    """Another attach or detach is under way, or research calls are in
    flight: a closed code, so concurrent calls never interleave a change."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Attachment:
    """This session's one research attachment, if any.

    Attaching holds the campaign's ownership lock for as long as it lasts, so
    the operations that take that lock - practice, freeze, submit, resume and
    a reconcile - answer campaign_busy until the session detaches.
    One session, one campaign.

    A client may call tools in parallel. One attach or detach runs at a time
    (another gets `attachment_busy`), and a detach the session asks for waits
    for no research call: one in flight answers `research_calls_in_flight`
    instead of pulling the campaign out from under it. Releasing at the end of
    the session (`detach()` with no argument) always proceeds.
    """

    def __init__(self, server, configuration):
        self.server = server
        self.configuration = configuration
        self.stack = None
        self.campaign = None
        self.tools = ()
        self.resources = ()
        self.prompts = ()
        self.capacity = None
        self._changing = False
        # The session's attachment, as a tool call's context finds it.
        server._carbon_attachment = self

    async def attach(self, campaign):
        from carbon.miner_mcp.open_tier import CampaignAlreadyAttached, attach_campaign
        from carbon.miner_mcp.serving import Capacity
        from carbon.miner_mcp.standard_cli import attached

        if self.stack is not None:
            raise CampaignAlreadyAttached("this session already owns a campaign")
        if self._changing:
            raise AttachmentBusy("attachment_busy")
        self._changing = True
        try:
            stack = contextlib.AsyncExitStack()
            before = set(self.server._resource_manager._resources)
            prompts = set(self.server._prompt_manager._prompts)
            capacity = Capacity()
            try:
                adapter, _ = await stack.enter_async_context(
                    attached(self.configuration, campaign)
                )
                self.tools = attach_campaign(self.server, adapter, capacity=capacity)
            except BaseException:
                await stack.aclose()
                raise
            self.resources = tuple(
                set(self.server._resource_manager._resources) - before
            )
            self.prompts = tuple(set(self.server._prompt_manager._prompts) - prompts)
            self.stack, self.campaign, self.capacity = stack, campaign, capacity
        finally:
            self._changing = False
        return {
            "attached": campaign,
            "research_tools": list(self.tools),
            "research_prompts": sorted(self.prompts),
        }

    async def detach(self, *, when_idle=False):
        """Release the campaign. `when_idle`, as the detach tool asks, refuses
        while another attach/detach or a research call is under way."""
        if when_idle and self._changing:
            raise AttachmentBusy("attachment_busy")
        if self.stack is None:
            return {"attached": None}
        if when_idle and self.capacity is not None and self.capacity.in_flight:
            raise AttachmentBusy("research_calls_in_flight")
        self._changing = True
        try:
            tools = self.server._tool_manager._tools
            for name in self.tools:
                tools.pop(name, None)
            resources = self.server._resource_manager._resources
            for uri in self.resources:
                resources.pop(uri, None)
            prompts = self.server._prompt_manager._prompts
            for name in self.prompts:
                prompts.pop(name, None)
            self.server._carbon_attached = False
            stack, campaign = self.stack, self.campaign
            self.stack = self.campaign = self.capacity = None
            removed = self.tools
            self.tools = self.resources = self.prompts = ()
            await stack.aclose()
        finally:
            self._changing = False
        return {"detached": campaign, "research_tools_removed": list(removed)}


#: The closed refusals of attach and detach. Their next steps and field are
#: the refusal catalog's, as every other refusal's (`operations.refusal`).
ATTACHMENT_REFUSALS = frozenset(
    {
        "already_attached",
        "attachment_busy",
        "research_calls_in_flight",
        "attach_unavailable",
    }
)


def _attachment_refusal(code):
    from scripts.dev.miner_launchpad.operations import refusal

    return json_refusal(refusal(code))


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

    from carbon.miner_mcp.open_tier import CampaignAlreadyAttached, announce

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

    async def attach(campaign, ctx=None):
        if guard is not None:
            guard()
        try:
            payload = await attachment.attach(campaign)
        except CampaignAlreadyAttached:
            raise ToolError(_attachment_refusal("already_attached")) from None
        except AttachmentBusy as busy:
            raise ToolError(_attachment_refusal(busy.code)) from None
        except Exception:  # noqa: BLE001 - closed refusal, never a trace or path
            raise ToolError(_attachment_refusal("attach_unavailable")) from None
        announced = await announce(
            ctx,
            tools=True,
            resources=bool(attachment.resources),
            prompts=bool(attachment.prompts),
        )
        return AttachmentResult(
            payload={
                **payload,
                "tools_added": list(attachment.tools),
                # Best effort: announced on the session and the subscription
                # bus; whether a client acts on it is the client's.
                "list_changed_announced": announced,
                "next_step": (
                    "list your tools again: the research tools above are now "
                    "in this session. Practice, freeze_candidate, submit, "
                    "resume and halt action=reconcile on this campaign answer "
                    "campaign_busy until you call " + DETACH + "."
                ),
            }
        )

    async def detach(ctx=None):
        if guard is not None:
            guard()
        try:
            payload = await attachment.detach(when_idle=True)
        except AttachmentBusy as busy:
            raise ToolError(_attachment_refusal(busy.code)) from None
        if payload.get("detached") is not None:
            payload["list_changed_announced"] = await announce(
                ctx, tools=True, resources=True, prompts=True
            )
        return AttachmentResult(payload=payload)

    return [
        Tool(
            fn=attach,
            name=PREFIX + "attach_campaign",
            description=(
                "Bind this session to one of your campaigns for deeper research: "
                "the workspace, run_python and Julia tools appear (the result "
                "names them; list your tools again). While attached, practice, "
                "freeze_candidate, submit, resume and halt action=reconcile on "
                "that campaign answer campaign_busy until you call "
                + DETACH
                + "; observe, campaign_view, messages, note and run_output "
                "keep working. " + REFUSAL_NOTE
            ),
            parameters=attach_model.model_json_schema(),
            fn_metadata=ExactMetadata(
                arg_model=attach_model, output_model=AttachmentResult
            ),
            is_async=True,
            context_kwarg="ctx",
        ),
        Tool(
            fn=detach,
            name=DETACH,
            description=(
                "Release this session's campaign and its research tools. "
                "Refused (research_calls_in_flight) while one of its research "
                "calls is still running."
            ),
            parameters=detach_model.model_json_schema(),
            fn_metadata=ExactMetadata(
                arg_model=detach_model, output_model=AttachmentResult
            ),
            is_async=True,
            context_kwarg="ctx",
        ),
    ]
