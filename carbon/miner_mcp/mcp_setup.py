"""The MCP door onto miner setup (OWNER-MINER-SETUP-AGENT-FIRST-01).

The owner, 2026-10-02: "yes make this more agent first and easy for an agent
to automate". Every setup step is one tool here, generated from the same
table as the browser's `/api/v1/setup/<step>` routes
(`scripts.dev.miner_launchpad.setup_operations`), calling the same `perform`
over the same `EnvironmentSetup` and setup records. This module defines no
step and no gate, so it cannot come to hold one the browser lacks.

`carbon_setup_status` drives the loop: the steps done, the next one, what it
is missing, and the exact next call with its arguments schema. The
`carbon_setup_workflow_v1` prompt states the loop.

**The tools follow the tiers (C-MLP-02-D10: absent, not refusing).** Status,
the signer check and the registration confirmation are in the open tier: a
miner who has nothing yet needs them. The steps after registration (agent,
quote, inference, compute, send_worker, review) are absent until setup has
confirmed the registration, and are added to the live server when it does.
When review writes the runner profile, the registered tier's operations
(launch, observe, practice, freeze, submit, halt, resume, attach) are added
the same way (`open_tier.attach_operations`), so the agent goes on to launch
without reconnecting. The pinned SDK sends no list-changed notification, so
each result that adds tools names them and a client re-lists.

Refusals are closed codes, with the field and a next step. Starting the
signer and signing the registration stay the miner's: those calls answer a
closed `human_action_required` result. No tool takes or returns key material;
a model key arrives only as the path to an owner-only file.
"""

from __future__ import annotations

import asyncio
import json

PREFIX = "carbon_setup_"
STATUS = PREFIX + "status"
WORKFLOW_PROMPT = "carbon_setup_workflow_v1"

WORKFLOW = """Carbon miner setup, for an agent (carbon_setup_workflow_v1).

Loop until launch:
1. Call carbon_setup_status. It returns `done`, `next.step`, `next.missing`
   (closed codes) and `next.call`: the tool and its arguments schema, with
   `next.options` listing the ids a step may name.
2. If `next.human_action_required` is present, tell the miner exactly its
   `instruction` and `command`, wait for them, then make `next.call` (for the
   signer, with their public hotkey address). Never ask for, accept or repeat
   a key, seed phrase, mnemonic or password.
3. Otherwise make `next.call`. For inference, call `next.before`
   (carbon_setup_quote) first and send its max_cost_nano as consent only
   with the miner's agreement to that charge; send the model key only as
   `model_key_file`, the absolute path to an owner-only file the miner made.
4. A refusal is a closed `error` with `field` and `next_step`; a result that
   adds tools names them in `tools_added`: list the tools again.
5. When `next.step` is "launch", setup is done: carbon_launch is available
   in this session.

Order: start your signer, register on the subnet, who researches, inference
(skipped for your own agent: it uses its own model), compute, review and
launch. Carbon rents no compute: a remote machine is the miner's own, reached
over their own SSH. DEVELOPMENT, testnet 567; nothing here is qualified.
"""


def _models():
    from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
    from pydantic import BaseModel, ConfigDict, JsonValue

    class StrictArguments(ArgModelBase):
        model_config = ConfigDict(strict=True, extra="forbid")

    class ExactMetadata(FuncMetadata):
        def pre_parse_json(self, data):
            return data

    class SetupResult(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        operation: str
        payload: JsonValue
        tools_added: list[str] = []

    return StrictArguments, ExactMetadata, SetupResult


def _field_type(kind):
    from pydantic import JsonValue, StrictBool, StrictStr

    return {"string": StrictStr, "boolean": StrictBool, "object": JsonValue}[kind]


def _refusal(code, field=None, next_step=None) -> str:
    """A closed refusal a client can branch on: never an argument back."""
    body = {"error": code}
    if field is not None:
        body["field"] = field
    if next_step is not None:
        body["next_step"] = next_step
    return json.dumps(body, sort_keys=True)


def make_setup_tools(setup, *, tier, guard=None, after=None):
    """One tool per setup operation of `tier`, calling the shared `perform`."""
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.mcpserver.tools import Tool
    from pydantic import Field, create_model

    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.environment_setup import SetupRefused
    from scripts.dev.miner_launchpad.setup_operations import (
        FIELDS,
        MCP,
        SETUP_OPERATIONS,
        perform,
    )

    strict, exact, result_model = _models()

    def tool_for(op):
        parameters = {}
        for field in sorted(op.required | op.optional):
            kind, meaning = FIELDS[field]
            annotation = _field_type(kind)
            default = ... if field in op.required else None
            if field not in op.required:
                annotation = annotation | None
            parameters[field] = (annotation, Field(default, description=meaning))
        model = create_model("setup_" + op.name, __base__=strict, **parameters)

        async def invoke(**arguments):
            if guard is not None:
                guard()
            request = {k: v for k, v in arguments.items() if v is not None}
            try:
                payload = await asyncio.to_thread(
                    perform, setup, op.name, request, door=MCP
                )
            except SetupRefused as refused:
                raise ToolError(
                    _refusal(refused.code, refused.field, refused.next_step)
                ) from None
            except Rejected as refused:
                raise ToolError(_refusal(refused.code)) from None
            added = list(await after(op.name, payload)) if after is not None else []
            return result_model(operation=op.name, payload=payload, tools_added=added)

        return Tool(
            fn=invoke,
            name=PREFIX + op.name,
            description=op.summary + " Same gates as the Control Center's setup.",
            parameters=model.model_json_schema(),
            fn_metadata=exact(arg_model=model, output_model=result_model),
            is_async=True,
        )

    return [tool_for(op) for op in SETUP_OPERATIONS.values() if op.tier == tier]


def make_status_tool(setup, *, guard=None, campaigns=None):
    """`carbon_setup_status`: where setup stands and the exact next call."""
    from mcp.server.mcpserver.tools import Tool
    from pydantic import BaseModel, ConfigDict, JsonValue, create_model

    from scripts.dev.miner_launchpad.setup_operations import MCP, status

    strict, exact, _ = _models()

    class StatusResult(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        payload: JsonValue

    model = create_model("setup_status", __base__=strict)

    async def invoke():
        if guard is not None:
            guard()
        count = campaigns() if campaigns is not None else None
        return StatusResult(
            payload=await asyncio.to_thread(status, setup, door=MCP, campaigns=count)
        )

    return Tool(
        fn=invoke,
        name=STATUS,
        description=(
            "Where your setup stands: the steps done, the next step, what it "
            "is missing, and the exact next call with its arguments schema. "
            "Loop on it until launch."
        ),
        parameters=model.model_json_schema(),
        fn_metadata=exact(arg_model=model, output_model=StatusResult),
        is_async=True,
    )


class SetupDoor:
    """Setup on one live MCP server, growing with the miner's progress.

    `attach_operations(profile_path)` adds the registered tier once review
    writes the profile and returns the tool names it added; None leaves the
    tier to a restart with `--configuration`.
    """

    def __init__(self, server, setup, *, guard=None, attach_operations=None):
        self.server = server
        self.setup = setup
        self.guard = guard
        self.attach_operations = attach_operations
        self.registered = False
        self.operations = False
        #: How many campaigns the attached profile has, once one is attached.
        self.count = None

    def _add(self, tools):
        from carbon.miner_mcp.open_tier import _assert_strict

        registry = self.server._tool_manager._tools
        added = []
        for tool in tools:
            if tool.name in registry:
                continue
            _assert_strict(tool.name, tool)
            registry[tool.name] = tool
            added.append(tool.name)
        return added

    def install(self):
        """Status and the open-tier steps now; the registered steps too when
        setup has already confirmed the registration."""
        from scripts.dev.miner_launchpad.setup_operations import OPEN

        added = self._add(
            [
                make_status_tool(
                    self.setup,
                    guard=self.guard,
                    campaigns=lambda: self.count() if self.count else None,
                ),
                *make_setup_tools(
                    self.setup, tier=OPEN, guard=self.guard, after=self.after
                ),
            ]
        )

        @self.server.prompt(name=WORKFLOW_PROMPT)
        def workflow() -> str:
            if self.guard is not None:
                self.guard()
            return WORKFLOW

        if self.setup.state()["registered_hotkey"] is not None:
            added += self._registered()
        return added

    def _registered(self):
        from scripts.dev.miner_launchpad.setup_operations import REGISTERED

        self.registered = True
        return self._add(
            make_setup_tools(
                self.setup, tier=REGISTERED, guard=self.guard, after=self.after
            )
        )

    async def after(self, name, payload):
        """Grow the tiers when a step crosses one; the names added."""
        if (
            type(payload) is not dict
            or payload.get("result") == "human_action_required"
        ):
            return []
        if name == "begin" and payload.get("registered_hotkey") and not self.registered:
            return self._registered()
        written = payload.get("steps", {}).get("review", {}).get("profile_written")
        if name == "review" and written and not self.operations:
            if self.attach_operations is None:
                return []
            names = await asyncio.to_thread(
                self.attach_operations, self.setup.profile_path
            )
            self.operations = True
            return list(names)
        return []
