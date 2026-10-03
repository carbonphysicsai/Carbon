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
            door = ToolDoor(adapter)
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
            stale = [c for c, s in self.sessions.items() if now - s.used >= self.idle]
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
                    "This page holds the campaign while the tools are open: "
                    "your agent's carbon_attach_campaign, practice, freeze "
                    "and submit answer campaign_busy until you close them."
                ),
            }

    def open(self, campaign):
        from scripts.dev.miner_launchpad.controller import Rejected

        self.reap()
        with self.lock:
            if campaign in self.sessions:
                self.sessions[campaign].used = self.clock()
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
            self.sessions[campaign] = session
            return self.state(campaign)

    def close(self, campaign):
        with self.lock:
            session = self.sessions.pop(campaign, None)
        if session is not None:
            session.close()
        return {"open": False, "closed": session is not None}

    def close_all(self):
        with self.lock:
            sessions, self.sessions = list(self.sessions.values()), {}
        for session in sessions:
            with contextlib.suppress(Exception):
                session.close()

    def _session(self, campaign):
        from scripts.dev.miner_launchpad.controller import Rejected

        self.reap()
        with self.lock:
            session = self.sessions.get(campaign)
            if session is None:
                raise Rejected("tools_session_not_open", 409)
            session.used = self.clock()
            return session

    def call(self, campaign, value):
        from scripts.dev.miner_launchpad.controller import Rejected

        if type(value) is not dict or set(value) != {"tool", "arguments"}:
            raise Rejected("closed_tool_call_required")
        session = self._session(campaign)
        return session.run(
            session.door.call(value["tool"], value["arguments"]), CALL_SECONDS
        )

    def start(self, campaign, value):
        from scripts.dev.miner_launchpad.controller import Rejected

        if type(value) is not dict or set(value) != {"arguments"}:
            raise Rejected("closed_task_start_required")
        session = self._session(campaign)
        result = session.run(session.door.start(value["arguments"]), CALL_SECONDS)
        if result.get("ok") and result.get("task"):
            with self.lock:
                # Newest first, as the page lists them.
                session.tasks = ([result["task"]["taskId"]] + session.tasks)[:50]
        return result

    def observe(self, campaign, value, *, cancel=False):
        from scripts.dev.miner_launchpad.controller import Rejected

        if type(value) is not dict or set(value) != {"task_id"}:
            raise Rejected("closed_task_id_required")
        session = self._session(campaign)
        return session.run(
            session.door.observe(value["task_id"], cancel=cancel), CALL_SECONDS
        )


ACTIONS = ("state", "open", "close", "call", "start", "observe", "cancel")


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
    row = host.owned_campaign(campaign)
    if action == "state":
        return {"campaign": campaign, **sessions.state(campaign)}
    if action == "close":
        if value != {}:
            raise Rejected("control_body_must_be_empty_object")
        return sessions.close(campaign)
    if action == "open":
        if value != {}:
            raise Rejected("control_body_must_be_empty_object")
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
        return sessions.call(campaign, value)
    if action == "start":
        return sessions.start(campaign, value)
    return sessions.observe(campaign, value, cancel=action == "cancel")


def runner_opener(host):
    """The real opener for a `RunnerAdapter`: the campaign's attachment, as
    `carbon_attach_campaign` makes it."""
    from pathlib import Path

    @contextlib.asynccontextmanager
    async def opener(campaign):
        from carbon.miner_mcp.standard_cli import attached

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
