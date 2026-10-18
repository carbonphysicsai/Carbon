"""The page's door to the research tools an MCP agent gets (RSURF-D15, D16).

OWNER-MINER-RESEARCH-SURFACE-03: a miner uses the toolbox from the Control
Center, not only reads about it. The page is one more client of the same
research tools, and holds nothing of its own:
- **Same attachment.** A session attaches through `standard_cli.attached`,
  the path `carbon_attach_campaign` takes. That holds the campaign's
  ownership lock and checks the authenticated owner, the run state and
  unresolved consumption.
- **Same tools.** The tools are the Tool objects `standard_server._create_server`
  builds for that adapter. The page lists each tool's own input schema and
  validates every call with that tool's own argument model (`Tool.run`), so
  the two doors cannot drift.
- **Same tasks.** Long work starts, reports progress and cancels through
  the adapter's task calls, with the projection the MCP Tasks extension
  returns.
- **One holder at a time.** If the lock is held by an attached agent,
  Carbon's agent or an operation in progress, opening is refused as
  `campaign_busy`, with what to do. An open session ends on close, when the
  server stops, and after `IDLE_SECONDS` idle.

Every result is the tools' own JSON. The page shows it as text, never as
HTML.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
import threading
import time
from dataclasses import dataclass

IDLE_SECONDS = 600
#: How long a blocking tool call may take before the page stops waiting
#: (the work itself is the tool's and keeps its own deadline).
CALL_SECONDS = 120
OPEN_SECONDS = 90
#: Workspace actions the page runs as tasks, with progress and cancel.
TASK_ACTIONS = frozenset({"run_python", "run_julia"})
#: What the page says when the lock is held, by who can hold it (RSURF-D16).
BUSY = {
    "carbon_agent_or_operation": (
        "Carbon's agent is researching in this campaign, or an operation "
        "(practice, freeze, submit, resume) is running. Pause Carbon's agent "
        "from Controls, or wait for the operation to finish, then open the "
        "tools again."
    ),
    "carbon_agent_paused": (
        "Carbon's agent is paused, but its run still holds this campaign "
        "while it waits to be resumed. A background supervisor lets it go "
        "within seconds of the Control Center starting: try again shortly. "
        "If it still holds it, restart the Control Center: the campaign "
        "stays paused, and the tools open on it then."
    ),
    "another_session": (
        "Another session holds this campaign: most likely your own agent "
        "attached it with carbon_attach_campaign. Ask it to call "
        "carbon_detach_campaign, or let it run the tools for you; then open "
        "the tools here."
    ),
}


class Busy(Exception):
    """The campaign's ownership lock is held by someone else."""


def operation_id():
    """A fresh business id for one page call: `page-` and 24 hex digits."""
    return "page-" + secrets.token_hex(12)


class ToolDoor:
    """The research tools for one attached adapter, as the page calls them."""

    def __init__(self, adapter):
        from carbon.development_session.research_tools import PREFIX
        from carbon.miner_mcp.standard_server import _create_server

        self.adapter = adapter
        self.prefix = PREFIX
        self.server = _create_server(adapter)
        self.tools = dict(self.server._tool_manager._tools)

    def describe(self):
        """Every tool with its own input schema, and the workspace actions
        with their fields, as the agent's tool list holds them."""
        from carbon.development_session.research_tasks import workspace_fields
        from carbon.research.model import DEVELOPMENT_WORKSPACE_ACTIONS

        actions = list(DEVELOPMENT_WORKSPACE_ACTIONS)
        julia = self.adapter.authored_julia_available
        if julia:
            actions.append("run_julia")
        return {
            "tools": [
                {
                    "name": name,
                    "operation": name.removeprefix(self.prefix),
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for name, tool in sorted(self.tools.items())
            ],
            "workspace": [
                {
                    "action": action,
                    "required": sorted(workspace_fields(action)[0]),
                    "optional": sorted(workspace_fields(action)[1]),
                    "runs_as_task": action in TASK_ACTIONS,
                }
                for action in actions
            ],
            "run_julia_available": julia,
            # The campaign's GPU lane for the code cell, or None (RSURF-D20).
            "gpu_lane": self.adapter.gpu_lane,
        }

    async def call(self, name, arguments):
        """One tool call through the tool itself: its own validation, gates
        and refusal text, which an MCP agent would get."""
        from mcp.server.mcpserver.exceptions import ToolError

        from scripts.dev.miner_launchpad.controller import Rejected

        tool = self.tools.get(name)
        if tool is None:
            raise Rejected("tool_unknown", 404)
        if type(arguments) is not dict:
            raise Rejected("tool_arguments_object_required")
        try:
            result = await tool.run(arguments, None)
        except ToolError as refused:
            return {"ok": False, "error": str(refused)[:2000]}
        except Exception:  # noqa: BLE001 - a crash's own text stays here
            return {"ok": False, "error": "Error executing tool " + name}
        return {"ok": True, "result": result.model_dump(mode="json")}

    async def start(self, arguments):
        """Start a research task and return at once: the adapter's task
        call, validated by the start tool's own argument model."""
        from pydantic import ValidationError

        from carbon.miner_mcp.mcp_extensions import task_projection, tool_result
        from carbon.miner_mcp.standard import AdapterFailure, ResearchToolRequest

        tool = self.tools[self.prefix + "start_research_task"]
        if type(arguments) is not dict:
            return {"ok": False, "error": "INVALID_ARGUMENTS"}
        try:
            validated = tool.fn_metadata.arg_model.model_validate(
                arguments
            ).model_dump()
        except ValidationError:
            return {"ok": False, "error": "INVALID_ARGUMENTS"}
        identity = validated.pop("operation_id")
        try:
            result = await self.adapter.start_task(
                ResearchToolRequest("start_research_task", identity, validated)
            )
        except AdapterFailure as exc:
            return {"ok": False, "error": _refusal(exc)}
        task = task_projection(result, detailed=False)
        if task is None:
            # Refused before admission: the tool's own complete result.
            return {"ok": True, "task": None, "result": tool_result(result)}
        return {"ok": True, "task": task, "operation_id": identity}

    async def observe(self, task_id, *, cancel=False):
        """A task's progress, or its cancellation, as MCP Tasks reports it."""
        from carbon.miner_mcp.mcp_extensions import task_projection
        from carbon.miner_mcp.standard import AdapterFailure

        if type(task_id) is not str:
            return {"ok": False, "error": "INVALID_ARGUMENTS"}
        try:
            result = await (
                self.adapter.cancel_task(task_id)
                if cancel
                else self.adapter.observe_task(task_id)
            )
            if result.payload.get("status") == "REJECTED_BEFORE_DISPATCH":
                # Refused before anything happened: say so, as it was said.
                return {
                    "ok": False,
                    "error": result.payload["reason"] + ": " + result.payload["detail"],
                }
            projected = task_projection(result, detailed=True)
        except (AdapterFailure, ValueError, KeyError, TypeError, OverflowError):
            return {
                "ok": False,
                "error": "Task unavailable; reconcile through the operator",
            }
        if projected is None or projected["taskId"] != task_id:
            return {
                "ok": False,
                "error": "Task unavailable; reconcile through the operator",
            }
        return {"ok": True, "task": projected}


def _direct_task_projection(view, public_result=None):
    """Browser-readable progress from the direct provider's public view."""
    if type(view) is not dict or type(view.get("task_id")) is not dict:
        return None
    identity = view["task_id"].get("value")
    state = view.get("state")
    if type(identity) is not str or type(state) is not str:
        return None
    status = (
        "working"
        if state in {"QUEUED", "RUNNING", "CANCEL_REQUESTED"}
        else (
            "completed"
            if state == "SUCCEEDED"
            else "cancelled" if state == "CANCELLED" else "failed"
        )
    )
    return {
        "taskId": identity,
        "status": status,
        "statusMessage": state,
        "result": public_result,
        "official_eligible": False,
    }


@dataclass(frozen=True)
class DirectToolsAttachment:
    adapter: object
    intake_target: dict | None


class DirectToolDoor:
    """One local page session on an explicitly supplied direct-v3 adapter."""

    def __init__(self, adapter, *, intake_target=None):
        from carbon.development_session.research_tools import (
            DIRECT_PREFIX,
            DirectResearchMinerTools,
        )
        from carbon.miner_mcp.standard_server import _create_direct_server

        if type(adapter) is not DirectResearchMinerTools:
            raise TypeError("trusted direct DEVELOPMENT adapter required")
        if intake_target is not None:
            from carbon.development_session.intake_targets import validate

            intake_target = validate([intake_target])[0]
        self.adapter = adapter
        self.intake_target = intake_target
        self.prefix = DIRECT_PREFIX
        self.server = _create_direct_server(adapter)
        self.tools = dict(self.server._tool_manager._tools)

    def describe(self):
        return {
            "tools": [
                {
                    "name": name,
                    "operation": name.removeprefix(self.prefix),
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for name, tool in sorted(self.tools.items())
            ],
            "workspace": [],
            "run_julia_available": False,
            "gpu_lane": None,
            "development_only": True,
            "challenge": {
                "id": self.adapter.challenge.challenge_id,
                "version": self.adapter.challenge.version,
            },
            "official_eligible": False,
            "construction_intake_configured": self.intake_target is not None,
        }

    async def submit_construction(self, value):
        return await self._construction(value, observe_only=False)

    async def observe_construction(self, value):
        """Read only the exact recipe's previously admitted remote task."""
        return await self._construction(value, observe_only=True)

    async def _construction(self, value, *, observe_only):
        """One exact 1.3 recipe through its profile-pinned signed receiver.

        The local research tools remain a separate workspace. In particular,
        graph source staged locally is not claimed to be present remotely.
        """
        from carbon.development_session.construction_recipe import (
            ConstructionRecipe,
            RecipeRefused,
        )
        from carbon.development_session.direct_submission import (
            DirectIntakeRefusal,
            _record_path,
            submit_and_wait,
        )
        from carbon.reconstruction.served_recipe_contract import registered

        if self.intake_target is None:
            return {"ok": False, "error": "construction_intake_unconfigured"}
        if type(value) is not dict or set(value) != {"recipe"}:
            return {"ok": False, "error": "construction_recipe_required"}
        try:
            recipe = ConstructionRecipe.from_dict(value["recipe"])
            if (
                self.adapter.challenge.challenge_id,
                self.adapter.challenge.version,
            ) != (
                recipe.to_dict()["challenge"]["id"],
                recipe.to_dict()["challenge"]["version"],
            ):
                raise DirectIntakeRefusal("construction_recipe_challenge_mismatch")
            contract = registered(
                self.adapter.challenge.challenge_id, self.adapter.challenge.version
            )
            epoch = int(recipe.digest[7:23], 16)
            root = self.adapter.composition.tasks.ledger.root
            result = await asyncio.to_thread(
                submit_and_wait,
                self.intake_target["intake_url"],
                self.adapter.connection.miner_key,
                root=root,
                epoch=epoch,
                recipe=recipe,
                contract_digest=contract.digest,
                receiver=self.intake_target["receiver_hotkey"],
                context=self.adapter.connection.chain_context,
                wait_s=10 if observe_only else 0,
                **({"observe_only": True} if observe_only else {}),
            )
            return {
                "ok": True,
                "result": result,
                "score_status": "SCORE_UNAVAILABLE",
                "official_eligible": False,
            }
        except DirectIntakeRefusal as refused:
            if refused.code == "construction_task_queued":
                record = _record_path(root, epoch)
                if record.exists():
                    import json

                    saved = json.loads(record.read_bytes())
                    return {
                        "ok": True,
                        "result": {
                            "state": "ADMITTED",
                            "task_id": saved["submission_id"],
                        },
                        "score_status": "SCORE_UNAVAILABLE",
                        "official_eligible": False,
                    }
            return {"ok": False, "error": refused.code}
        except RecipeRefused as refused:
            return {"ok": False, "error": refused.code}
        except (OSError, ValueError, LookupError):
            return {"ok": False, "error": "construction_intake_unavailable"}

    async def stage_construction_graph(self, value):
        """Copy this owner's locally staged graph to the pinned receiver."""
        from carbon.development_session.construction_recipe import (
            ConstructionRecipe,
            RecipeRefused,
        )
        from carbon.development_session.direct_source_submission import stage_graph
        from carbon.development_session.direct_submission import DirectIntakeRefusal
        from carbon.reconstruction.served_recipe_contract import registered

        if self.intake_target is None:
            return {"ok": False, "error": "construction_intake_unconfigured"}
        if (
            type(value) is not dict
            or not {"recipe"} <= set(value)
            or set(value)
            - {
                "recipe",
                "expected_manifest_digest",
            }
        ):
            return {"ok": False, "error": "construction_recipe_required"}
        try:
            recipe = ConstructionRecipe.from_dict(value["recipe"])
            if (
                self.adapter.challenge.challenge_id,
                self.adapter.challenge.version,
            ) != (
                recipe.to_dict()["challenge"]["id"],
                recipe.to_dict()["challenge"]["version"],
            ):
                raise DirectIntakeRefusal("construction_recipe_challenge_mismatch")
            contract = registered(
                self.adapter.challenge.challenge_id, self.adapter.challenge.version
            )
            result = await asyncio.to_thread(
                stage_graph,
                self.intake_target["intake_url"],
                self.adapter.connection.miner_key,
                ledger=self.adapter.composition.tasks.ledger,
                owner=self.adapter.owner,
                recipe=recipe,
                contract_digest=contract.digest,
                receiver=self.intake_target["receiver_hotkey"],
                context=self.adapter.connection.chain_context,
                expected_manifest_digest=value.get("expected_manifest_digest"),
            )
            return {"ok": True, "result": result, "official_eligible": False}
        except (DirectIntakeRefusal, RecipeRefused) as refused:
            return {"ok": False, "error": refused.code}
        except (OSError, ValueError, LookupError):
            return {"ok": False, "error": "construction_source_staging_unavailable"}

    async def call(self, name, arguments):
        from mcp.server.mcpserver.exceptions import ToolError

        from scripts.dev.miner_launchpad.controller import Rejected

        tool = self.tools.get(name)
        if tool is None:
            raise Rejected("tool_unknown", 404)
        if type(arguments) is not dict:
            raise Rejected("tool_arguments_object_required")
        try:
            value = await tool.run(arguments, None)
        except ToolError as refused:
            return {"ok": False, "error": str(refused)[:2000]}
        except Exception:  # noqa: BLE001 - never expose trusted controls
            return {"ok": False, "error": "DIRECT_OPERATIONAL_STOP"}
        return {"ok": True, "result": value.model_dump(mode="json")}

    async def start(self, arguments):
        if type(arguments) is not dict:
            return {"ok": False, "error": "INVALID_ARGUMENTS"}
        result = await self.call(self.prefix + "start_research_task", arguments)
        if not result["ok"]:
            return result
        value = result["result"]
        task = _direct_task_projection(value["task"], value["public_result"])
        return {
            "ok": True,
            "task": task,
            "result": value,
            "operation_id": value["operation_id"],
        }

    async def observe(self, task_id, *, cancel=False):
        if type(task_id) is not str:
            return {"ok": False, "error": "INVALID_ARGUMENTS"}
        name = "cancel_research_task" if cancel else "get_research_result"
        result = await self.call(self.prefix + name, {"task_id": task_id})
        if not result["ok"]:
            return result
        value = result["result"]
        task = _direct_task_projection(value["task"], value["public_result"])
        if task is None or task["taskId"] != task_id:
            return {
                "ok": False,
                "error": "Task unavailable; reconcile through the operator",
            }
        return {"ok": True, "task": task, "result": value}


def _refusal(exc):
    from carbon.miner_mcp import serving

    return (
        f"{exc.code.value}; dispatch_may_have_occurred="
        f"{str(exc.dispatch_may_have_occurred).lower()}; "
        f"next_action={serving.NEXT_ACTION[exc.code.value]}"
    )


class _Session:
    """One open tool session: its own event loop thread, holding the
    attachment (and so the campaign's lock) until closed."""

    def __init__(self, campaign):
        self.campaign = campaign
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self.loop.run_forever, name="carbon-tools-" + campaign, daemon=True
        )
        self.thread.start()
        self.stack = None
        self.door = None
        self.opened = time.time()
        self.used = time.monotonic()
        self.tasks = []

    def run(self, coroutine, timeout):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout)

    async def _enter(self, manager):
        stack = contextlib.AsyncExitStack()
        try:
            adapter = await stack.enter_async_context(manager)
            from carbon.development_session.research_tools import (
                DirectResearchMinerTools,
            )

            direct = type(adapter) is DirectToolsAttachment
            door = (
                DirectToolDoor(
                    adapter.adapter if direct else adapter,
                    intake_target=adapter.intake_target if direct else None,
                )
                if direct or type(adapter) is DirectResearchMinerTools
                else ToolDoor(adapter)
            )
        except BaseException:
            await stack.aclose()
            raise
        self.stack, self.door = stack, door

    def enter(self, manager):
        try:
            self.run(self._enter(manager), OPEN_SECONDS)
        except BaseException:
            self.stop()
            raise

    def close(self):
        try:
            if self.stack is not None:
                self.run(self.stack.aclose(), OPEN_SECONDS)
        finally:
            self.stack = self.door = None
            self.stop()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=10)


class ToolSessions:
    """The page's tool sessions on this host: at most one per campaign.

    `opener(campaign)` returns an async context manager that yields one
    attached research adapter and holds the campaign's ownership lock while
    it is open; it raises `Busy` when the lock is held elsewhere.
    `busy_hint(campaign)` says who can hold it (a key of `BUSY`).
    """

    def __init__(
        self, opener, *, busy_hint=None, idle=IDLE_SECONDS, clock=None, seed_tasks=()
    ):
        self.opener = opener
        # Tasks a new session lists from the start (the demo's finished run).
        self.seed_tasks = list(seed_tasks)
        self.busy_hint = busy_hint or (lambda campaign: "another_session")
        self.idle = idle
        self.clock = clock or time.monotonic
        self.sessions = {}
        self.lock = threading.RLock()

    def reap(self):
        """Close every session idle for `idle` seconds."""
        now = self.clock()
        with self.lock:
            stale = [
                c
                for c, s in self.sessions.items()
                if getattr(s, "exclusive_token", None) is None
                and now - s.used >= self.idle
            ]
            for campaign in stale:
                self.sessions.pop(campaign).close()

    def state(self, campaign):
        self.reap()
        with self.lock:
            session = self.sessions.get(campaign)
            if session is None:
                return {"open": False, "idle_close_seconds": self.idle}
            return {
                "open": True,
                "opened_unix": int(session.opened),
                "idle_close_seconds": self.idle,
                "idle_seconds": int(self.clock() - session.used),
                **session.door.describe(),
                "tasks": list(session.tasks),
                "holds": (
                    "This page holds the local DEVELOPMENT construction session "
                    "while the tools are open. Your MCP agent can use it after "
                    "you close this page's tools."
                    if campaign in DIRECT_DEVELOPMENT_VERSIONS
                    else "This page holds the campaign while the tools are open: "
                    "your agent's carbon_attach_campaign, practice, freeze "
                    "and submit answer campaign_busy until you close them."
                ),
            }

    def open(self, campaign, *, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        if exclusive_token is None:
            self.reap()
        with self.lock:
            if campaign in self.sessions:
                session = self.sessions[campaign]
                if getattr(session, "exclusive_token", None) != exclusive_token:
                    raise Rejected("tools_session_already_open", 409)
                session.used = self.clock()
                return self.state(campaign)
            session = _Session(campaign)
            try:
                session.enter(self.opener(campaign))
            except Busy:
                hint = self.busy_hint(campaign)
                raise Rejected("campaign_busy_" + hint, 409) from None
            except Rejected:
                raise
            except Exception as exc:  # noqa: BLE001 - a closed code, never a trace
                # Which check refused the attachment, when it names one
                # (`standard_cli.refusal_code`: task_left_running, a stale
                # checkout, a signer code ...), so the page can say what to
                # do; otherwise the historical generic code (LP-PROD-C).
                from carbon.miner_mcp.standard_cli import refusal_code

                raise Rejected(
                    refusal_code(exc) or "tools_unavailable_for_campaign", 409
                ) from None
            session.used = self.clock()
            session.tasks = list(self.seed_tasks)
            session.exclusive_token = exclusive_token
            self.sessions[campaign] = session
            return self.state(campaign)

    def close(self, campaign, *, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        with self.lock:
            session = self.sessions.get(campaign)
            if (
                session is not None
                and getattr(session, "exclusive_token", None) != exclusive_token
            ):
                raise Rejected("tools_session_owned_elsewhere", 409)
            self.sessions.pop(campaign, None)
        if session is not None:
            session.close()
        return {"open": False, "closed": session is not None}

    def close_all(self):
        with self.lock:
            sessions, self.sessions = list(self.sessions.values()), {}
        for session in sessions:
            with contextlib.suppress(Exception):
                session.close()

    def _session(self, campaign, *, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        self.reap()
        with self.lock:
            session = self.sessions.get(campaign)
            if session is None:
                raise Rejected("tools_session_not_open", 409)
            if getattr(session, "exclusive_token", None) != exclusive_token:
                raise Rejected("tools_session_owned_elsewhere", 409)
            session.used = self.clock()
            return session

    def call(self, campaign, value, *, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        if type(value) is not dict or set(value) != {"tool", "arguments"}:
            raise Rejected("closed_tool_call_required")
        session = self._session(campaign, exclusive_token=exclusive_token)
        return session.run(
            session.door.call(value["tool"], value["arguments"]), CALL_SECONDS
        )

    def start(self, campaign, value, *, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        if type(value) is not dict or set(value) != {"arguments"}:
            raise Rejected("closed_task_start_required")
        session = self._session(campaign, exclusive_token=exclusive_token)
        result = session.run(session.door.start(value["arguments"]), CALL_SECONDS)
        if result.get("ok") and result.get("task"):
            with self.lock:
                # Newest first, as the page lists them.
                session.tasks = ([result["task"]["taskId"]] + session.tasks)[:50]
        return result

    def observe(self, campaign, value, *, cancel=False, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        if type(value) is not dict or set(value) != {"task_id"}:
            raise Rejected("closed_task_id_required")
        session = self._session(campaign, exclusive_token=exclusive_token)
        return session.run(
            session.door.observe(value["task_id"], cancel=cancel), CALL_SECONDS
        )

    def submit_construction(self, campaign, value, *, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        session = self._session(campaign, exclusive_token=exclusive_token)
        if type(session.door) is not DirectToolDoor:
            raise Rejected("construction_session_required", 409)
        return session.run(session.door.submit_construction(value), CALL_SECONDS)

    def observe_construction(self, campaign, value, *, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        session = self._session(campaign, exclusive_token=exclusive_token)
        if type(session.door) is not DirectToolDoor:
            raise Rejected("construction_session_required", 409)
        return session.run(session.door.observe_construction(value), CALL_SECONDS)

    def stage_construction_graph(self, campaign, value, *, exclusive_token=None):
        from scripts.dev.miner_launchpad.controller import Rejected

        session = self._session(campaign, exclusive_token=exclusive_token)
        if type(session.door) is not DirectToolDoor:
            raise Rejected("construction_session_required", 409)
        return session.run(session.door.stage_construction_graph(value), CALL_SECONDS)


ACTIONS = (
    "state",
    "open",
    "close",
    "call",
    "start",
    "observe",
    "cancel",
    "submit_construction",
    "observe_construction",
    "stage_construction_graph",
)
DIRECT_DEVELOPMENT_SESSION = "direct-development"
DIRECT_DEVELOPMENT_V13_SESSION = "direct-development-1.3"
DIRECT_DEVELOPMENT_VERSIONS = {
    DIRECT_DEVELOPMENT_SESSION: "1.2",
    DIRECT_DEVELOPMENT_V13_SESSION: "1.3",
}


def route(host, campaign, action, value):
    """The page's tools route. Opening passes the shared operation gates
    first: an enabled profile, registration and a reachable signer, and the
    miner's own product campaign (RSURF-D15)."""
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.operations import (
        _registered,
        _signer_reachable,
    )

    sessions = getattr(host, "tool_sessions", None)
    if sessions is None:
        raise Rejected("tools_unavailable", 409)
    if action not in ACTIONS:
        raise Rejected("unknown_tools_action", 404)
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    direct = campaign in DIRECT_DEVELOPMENT_VERSIONS and type(host) is RunnerAdapter
    row = None if direct else host.owned_campaign(campaign)
    if action == "state":
        return {"campaign": campaign, **sessions.state(campaign)}
    exclusive_token = None
    if direct and type(value) is dict and "exclusive_token" in value:
        exclusive_token = value["exclusive_token"]
        if (
            type(exclusive_token) is not str
            or len(exclusive_token) != 32
            or any(char not in "0123456789abcdef" for char in exclusive_token)
        ):
            raise Rejected("invalid_tools_session_token", 409)
        value = {key: item for key, item in value.items() if key != "exclusive_token"}
    if action == "close":
        if value != {}:
            raise Rejected("control_body_must_be_empty_object")
        return sessions.close(campaign, exclusive_token=exclusive_token)
    if action == "open":
        if value != {}:
            raise Rejected("control_body_must_be_empty_object")
        if direct:
            if host.configuration is None:
                raise Rejected("research_profile_unavailable", 409)
            return {
                "campaign": campaign,
                **sessions.open(campaign, exclusive_token=exclusive_token),
            }
        if row.get("kind") == "fixture":
            # The demo's synthetic session (RSURF-D18): no profile, chain or
            # lock exists to check, and it runs nothing.
            return {"campaign": campaign, **sessions.open(campaign)}
        if row.get("kind") != "product":
            raise Rejected("retired_grant_campaign", 409)
        try:
            profile = host.configured()
        except Rejected:
            raise
        except Exception:  # noqa: BLE001 - an unreadable profile, never its content
            raise Rejected("research_profile_unavailable", 409) from None
        _registered(host, profile)
        _signer_reachable(host, profile)
        return {"campaign": campaign, **sessions.open(campaign)}
    if action == "call":
        return sessions.call(campaign, value, exclusive_token=exclusive_token)
    if action == "start":
        return sessions.start(campaign, value, exclusive_token=exclusive_token)
    if action == "submit_construction":
        if campaign != DIRECT_DEVELOPMENT_V13_SESSION:
            raise Rejected("construction_session_required", 409)
        return sessions.submit_construction(
            campaign, value, exclusive_token=exclusive_token
        )
    if action == "observe_construction":
        if campaign != DIRECT_DEVELOPMENT_V13_SESSION:
            raise Rejected("construction_session_required", 409)
        return sessions.observe_construction(
            campaign, value, exclusive_token=exclusive_token
        )
    if action == "stage_construction_graph":
        if campaign != DIRECT_DEVELOPMENT_V13_SESSION:
            raise Rejected("construction_session_required", 409)
        return sessions.stage_construction_graph(
            campaign, value, exclusive_token=exclusive_token
        )
    return sessions.observe(
        campaign, value, cancel=action == "cancel", exclusive_token=exclusive_token
    )


def runner_opener(host):
    """The real opener for a `RunnerAdapter`: the campaign's attachment, as
    `carbon_attach_campaign` makes it."""
    from pathlib import Path

    @contextlib.asynccontextmanager
    async def opener(campaign):
        from carbon.miner_mcp.standard_cli import (
            attached,
            attached_installed_direct_development,
        )

        if campaign in DIRECT_DEVELOPMENT_VERSIONS:
            if host.configuration is None:
                raise RuntimeError("no runner profile")
            from scripts.dev.miner_launchpad.controller import LockHeld

            try:
                async with attached_installed_direct_development(
                    Path(host.configuration),
                    version=DIRECT_DEVELOPMENT_VERSIONS[campaign],
                ) as (adapter, _selected):
                    target = host._configuration().get("direct_intake_target")
                    yield DirectToolsAttachment(adapter, target)
            except LockHeld:
                raise Busy() from None
            return

        row = host.owned_campaign(campaign)
        if host.configuration is None:
            raise RuntimeError("no runner profile")
        from scripts.dev.miner_launchpad.controller import LockHeld

        try:
            manager = attached(Path(host.configuration), Path(row["root"]).name)
            async with manager as (adapter, _profile):
                yield adapter
        except LockHeld:
            # `owner_lock` refuses a held lock with this RuntimeError.
            raise Busy() from None

    return opener
