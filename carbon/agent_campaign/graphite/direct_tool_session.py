"""Prospective Graphite consumer of the miner's direct DEVELOPMENT tool session.

The session is opened by the normal Launchpad route. This adapter supplies the
existing research loop's ``tools`` and ``sdk.call`` interface; it owns neither
the signed construction transport nor a historical Graphite edition identity.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import math
import re
import time
import uuid
from copy import deepcopy
from pathlib import Path

from carbon.development_session.research_tools import (
    DIRECT_PREFIX,
    DirectResearchMinerTools,
)

from .miner.toolbox import protected, refusal

SESSION = "direct-development-1.3"
SUBMIT = DIRECT_PREFIX + "submit_construction"
STAGE_GRAPH = DIRECT_PREFIX + "stage_construction_graph"
_START = DIRECT_PREFIX + "start_research_task"
_OBSERVE = DIRECT_PREFIX + "get_research_result"
_CANCEL = DIRECT_PREFIX + "cancel_research_task"
_NEW_WORK = {DIRECT_PREFIX + "stage_research_source", _START, STAGE_GRAPH, SUBMIT}
_ACTIVE_TASK_STATES = {"QUEUED", "RUNNING", "CANCEL_REQUESTED"}
_TERMINAL_TASK_STATES = {
    "SUCCEEDED",
    "REFUSED",
    "UNRESOLVED",
    "FAILED_INFRA",
    "CANCELLED",
}
_KEEPALIVE_SECONDS = 240
_TASK_POLL_SECONDS = 2
_IDENTITY = re.compile(r"[A-Za-z0-9._:-]{16,114}\Z")
_CAMPAIGN_IDENTITY = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TASK_ID = re.compile(r"rtsk_[0-9a-f]{64}\Z")
_MAX_RECIPE_JSON = 32768


def _schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_RECIPE = {
    "type": "string",
    "minLength": 2,
    "maxLength": _MAX_RECIPE_JSON,
    "description": "Complete registered construction recipe as one JSON object.",
}
_TEXT = {"type": "string"}
_DIRECT_PARAMETERS = {
    "get_challenge_info": _schema({}),
    "get_interaction_manifest": _schema({}),
    "stage_research_source": _schema(
        {
            "name": _TEXT,
            "offset": {"type": "integer", "minimum": 0},
            "total_bytes": {"type": "integer", "minimum": 1},
            "content_digest": _TEXT,
            "expected_digest": {"type": ["string", "null"]},
            "chunk_base64": _TEXT,
        }
    ),
    "start_research_task": _schema({"recipe_json": _RECIPE}),
    "get_research_result": _schema({"task_id": _TEXT}),
    "cancel_research_task": _schema({"task_id": _TEXT}),
}
_CONSTRUCTION_TOOLS = (
    {
        "type": "function",
        "name": STAGE_GRAPH,
        "description": (
            "Stage the graph source already saved in this owner's DEVELOPMENT "
            "workspace to the profile-pinned receiver before submitting its recipe."
        ),
        "strict": True,
        "parameters": _schema(
            {
                "recipe_json": _RECIPE,
                "expected_manifest_digest": {
                    "type": ["string", "null"],
                    "description": "Previously published receiver manifest digest, or null.",
                },
            }
        ),
    },
    {
        "type": "function",
        "name": SUBMIT,
        "description": (
            "Submit one registered construction recipe through the miner's "
            "profile-pinned signed DEVELOPMENT intake. The resulting task is "
            "not an official grade."
        ),
        "strict": True,
        "parameters": _schema({"recipe_json": _RECIPE}),
    },
)


def _recipe(raw):
    if type(raw) is not str or len(raw.encode("utf-8")) > _MAX_RECIPE_JSON:
        raise ValueError("bounded recipe JSON required")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate recipe field")
            value[key] = item
        return value

    value = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    if type(value) is not dict:
        raise ValueError("recipe object required")
    return value


def _public_task_id(task):
    """Read the nominal ResearchTaskId projection on the public wire."""
    if type(task) is not dict or type(task.get("task_id")) is not dict:
        return None
    value = task["task_id"]
    if set(value) != {"value"} or type(value["value"]) is not str:
        return None
    return value["value"] if _TASK_ID.fullmatch(value["value"]) else None


def _operation_id(campaign_identity, identity):
    return (
        "graphite-direct-"
        + hashlib.sha256(
            (campaign_identity + "\0" + identity).encode("utf-8")
        ).hexdigest()
    )


def _campaign_lease_token(ledger, campaign_identity):
    """Recover the private Tools lease after an interrupted direct epoch."""
    from carbon.development_session.data import write_once
    from carbon.development_session.profile import canonical

    path = ledger.root / "direct-agent-tools-lease.json"
    if not path.exists() and not path.is_symlink():
        payload = canonical(
            {
                "schema": "carbon.autoresearch.direct-tools-lease.v1",
                "campaign_identity": campaign_identity,
                "token": uuid.uuid4().hex,
            }
        )
        try:
            write_once(path, payload)
        except ValueError as error:
            if str(error) != "immutable session artifact conflict":
                raise
            # A concurrent owner may have won the atomic create. Read its
            # exact campaign-bound token; never replace a retained lease.
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256:
        raise ValueError("direct Tools lease custody differs")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, UnicodeError):
        raise ValueError("direct Tools lease custody differs") from None
    if (
        type(value) is not dict
        or set(value) != {"schema", "campaign_identity", "token"}
        or raw != canonical(value)
        or value["schema"] != "carbon.autoresearch.direct-tools-lease.v1"
        or value["campaign_identity"] != campaign_identity
        or type(value["token"]) is not str
        or re.fullmatch(r"[0-9a-f]{32}", value["token"]) is None
    ):
        raise ValueError("direct Tools lease custody differs")
    return value["token"]


def _dispatch_request(name, arguments, operation_id):
    """Build only a request that passes the local pre-route argument checks."""
    if name in (STAGE_GRAPH, SUBMIT):
        expected = (
            {"recipe_json", "expected_manifest_digest"}
            if name == STAGE_GRAPH
            else {"recipe_json"}
        )
        if set(arguments) != expected:
            raise ValueError("construction arguments differ")
        value = {"recipe": _recipe(arguments["recipe_json"])}
        if name == STAGE_GRAPH:
            expected_digest = arguments["expected_manifest_digest"]
            if expected_digest is not None and type(expected_digest) is not str:
                raise ValueError("manifest digest must be text or null")
            value["expected_manifest_digest"] = expected_digest
        action = (
            "stage_construction_graph" if name == STAGE_GRAPH else "submit_construction"
        )
    else:
        if "operation_id" in arguments:
            raise ValueError("operation identity is loop-owned")
        if name == _START:
            if set(arguments) != {"recipe_json"}:
                raise ValueError("direct start arguments differ")
            arguments = {"recipe": _recipe(arguments["recipe_json"])}
        action = "call"
        value = {
            "tool": name,
            "arguments": {**arguments, "operation_id": operation_id},
        }
    return action, value


def _journaled_tasks(
    ledger, campaign_identity, *, before_epoch=None, offered_names=None
):
    """Restore only tasks from the loop's canonical intent/result pairs."""
    from carbon.development_session.profile import canonical

    known = {}
    count = 0
    for epoch in (1, 2):
        if before_epoch is not None and epoch >= before_epoch:
            continue
        directory = ledger.root / f"epoch-{epoch}" / "direct"
        if not directory.exists():
            continue
        if directory.is_symlink():
            raise ValueError("direct agent journal path differs")
        intents = sorted(directory.glob("epoch-*-direct-tool-*-intent.json"))
        plan_path = directory / "plan.json"
        if not plan_path.is_file() or plan_path.is_symlink():
            if not intents and not plan_path.exists():
                continue
            raise ValueError("direct agent journal plan required")
        raw_plan = plan_path.read_bytes()
        plan = json.loads(raw_plan)
        tools = plan.get("tools") if type(plan) is dict else None
        if (
            raw_plan != canonical(plan)
            or type(tools) is not list
            or any(
                type(tool) is not dict or type(tool.get("name")) is not str
                for tool in tools
            )
        ):
            raise ValueError("direct agent journal plan differs")
        planned_names = {tool["name"] for tool in tools}
        if offered_names is not None and planned_names != offered_names:
            raise ValueError("direct agent journal offered tools differ")
        for intent_file in intents:
            count += 1
            if count > 4096 or intent_file.is_symlink():
                raise ValueError("direct agent journal exceeds bounded custody")
            identity = intent_file.name.removesuffix("-intent.json")
            raw_intent = intent_file.read_bytes()
            if len(raw_intent) > 4 * 1024 * 1024:
                raise ValueError("direct agent journal record exceeds bound")
            intent = json.loads(raw_intent)
            if raw_intent != canonical(intent):
                raise ValueError("direct agent journal canonical record differs")
            name = intent.get("name") if type(intent) is dict else None
            result_file = directory / (identity + "-result.json")
            if not result_file.is_file() or result_file.is_symlink():
                arguments = intent.get("arguments") if type(intent) is dict else None
                if (
                    type(name) is str
                    and name.startswith(DIRECT_PREFIX)
                    and name in planned_names
                    and type(arguments) is dict
                    and not protected(arguments)
                    and _IDENTITY.fullmatch(identity) is not None
                ):
                    try:
                        _dispatch_request(
                            name, arguments, _operation_id(campaign_identity, identity)
                        )
                    except (ValueError, TypeError, json.JSONDecodeError):
                        pass  # This intent could only have produced a local refusal.
                    else:
                        raise UncertainDirectToolDispatch(
                            "direct tool intent requires reconciliation"
                        )
                continue
            raw_result = result_file.read_bytes()
            if len(raw_result) > 4 * 1024 * 1024:
                raise ValueError("direct agent journal record exceeds bound")
            result = json.loads(raw_result)
            if raw_result != canonical(result):
                raise ValueError("direct agent journal canonical record differs")
            if name not in {_START, _OBSERVE, _CANCEL}:
                continue
            if type(result) is not dict or result.get("ok") is not True:
                continue
            direct = result.get("result")
            if not _direct_result(
                direct, name, _operation_id(campaign_identity, identity)
            ):
                raise ValueError("direct agent journal result binding differs")
            if result.get("requires_reconciliation") is True:
                raise UncertainDirectToolDispatch(
                    "direct task journal requires reconciliation"
                )
            if direct["reply"].get("status") != "OK":
                continue
            task = direct["task"]
            task_id = _public_task_id(task)
            state = task.get("state") if type(task) is dict else None
            if (
                task_id is None
                or type(state) is not str
                or state not in _ACTIVE_TASK_STATES | _TERMINAL_TASK_STATES
            ):
                raise UncertainDirectToolDispatch(
                    "direct task journal state requires reconciliation"
                )
            if name == _START or (
                task_id in known
                and type(intent.get("arguments")) is dict
                and intent["arguments"].get("task_id") == task_id
            ):
                known[task_id] = state
    directory = ledger.root / "direct-task-observations"
    if directory.exists():
        if directory.is_symlink():
            raise ValueError("direct task observation path differs")
        for path in sorted(directory.glob("rtsk_*.json")):
            if path.is_symlink() or path.stat().st_size > 4096:
                raise ValueError("direct task observation record differs")
            raw = path.read_bytes()
            record = json.loads(raw)
            if (
                raw != canonical(record)
                or type(record) is not dict
                or set(record) != {"schema", "campaign_identity", "task_id", "state"}
                or record["schema"] != "carbon.autoresearch.direct-task-observation.v1"
                or record["campaign_identity"] != campaign_identity
                or type(record["task_id"]) is not str
                or _TASK_ID.fullmatch(record["task_id"]) is None
                or path.name != record["task_id"] + ".json"
                or type(record["state"]) is not str
                or record["state"] not in _TERMINAL_TASK_STATES
            ):
                raise ValueError("direct task observation binding differs")
            if record["task_id"] not in known:
                if before_epoch is not None:
                    continue
                raise ValueError("direct task observation binding differs")
            known[record["task_id"]] = record["state"]
    return known


def _record_terminal_task(ledger, campaign_identity, task_id, state):
    from carbon.development_session.data import write_once
    from carbon.development_session.profile import canonical

    if _TASK_ID.fullmatch(task_id) is None or state not in _TERMINAL_TASK_STATES:
        raise ValueError("terminal direct task observation required")
    directory = ledger.root / "direct-task-observations"
    if directory.is_symlink():
        raise ValueError("direct task observation path differs")
    directory.mkdir(mode=0o700, exist_ok=True)
    write_once(
        directory / (task_id + ".json"),
        canonical(
            {
                "schema": "carbon.autoresearch.direct-task-observation.v1",
                "campaign_identity": campaign_identity,
                "task_id": task_id,
                "state": state,
            }
        ),
    )


async def _supervise_active_tasks(
    session, ledger, campaign_identity, campaign_digest, elapsed_seconds, *, sleep=None
):
    """Observe known direct work while holding its attached owner session."""
    sleep = asyncio.sleep if sleep is None else sleep
    observed = {}
    with ledger.db() as db:
        row = db.execute("SELECT started FROM campaign WHERE id=1").fetchone()
    if row is None or type(row[0]) not in (float, int):
        raise ValueError("started finite direct agent campaign required")
    remaining = max(0, row[0] + elapsed_seconds - ledger.clock())
    monotonic_deadline = time.monotonic() + remaining
    while session._active_tasks:
        expired = (
            not _new_work_within_deadline(ledger, campaign_digest, elapsed_seconds)
            or time.monotonic() >= monotonic_deadline
        )
        for task_id in sorted(session._active_tasks):
            operation = _CANCEL if expired else _OBSERVE
            result = await session.call(
                operation,
                {"task_id": task_id},
                "direct-agent-supervise-" + task_id,
            )
            if type(result) is not dict or result.get("ok") is not True:
                raise UncertainDirectToolDispatch(
                    "direct task supervision requires reconciliation"
                )
            if result.get("requires_reconciliation") is True:
                raise UncertainDirectToolDispatch(
                    "direct task supervision requires reconciliation"
                )
            direct = result["result"]
            if direct["reply"].get("status") != "OK":
                raise UncertainDirectToolDispatch(
                    "direct task supervision requires reconciliation"
                )
            task = direct["task"]
            state = task["state"]
            if state in _TERMINAL_TASK_STATES:
                _record_terminal_task(ledger, campaign_identity, task_id, state)
                observed[task_id] = state
        if expired:
            # The installed attachment's close supervises cancellation and
            # waits for owned workers even when the cancel reply is pending.
            return observed, True
        if session._active_tasks:
            await sleep(_TASK_POLL_SECONDS)
    return observed, False


class DirectToolSession:
    """Closed, prospective SDK over an already opened public Launchpad route.

    ``route(action, value)`` is the same authenticated ``tool_door.route``
    path the miner's Tools page uses, bound to its host and SESSION campaign.
    ``run_epoch`` can consume ``tools`` and ``call`` without changing its
    provider, ledger, retry, or journal semantics.
    """

    def __init__(
        self,
        route,
        opened,
        *,
        campaign_identity,
        admit_new_work=None,
        known_tasks=None,
        lease_token=None,
    ):
        if lease_token is None:
            lease_token = uuid.uuid4().hex
        if (
            not callable(route)
            or type(opened) is not dict
            or opened.get("campaign") != SESSION
            or opened.get("open") is not True
            or opened.get("development_only") is not True
            or opened.get("official_eligible") is not False
            or type(opened.get("tools")) is not list
            or type(opened.get("challenge")) is not dict
            or set(opened["challenge"]) != {"id", "version"}
            or any(
                type(opened["challenge"][key]) is not str
                or not opened["challenge"][key]
                for key in ("id", "version")
            )
            or type(campaign_identity) is not str
            or _CAMPAIGN_IDENTITY.fullmatch(campaign_identity) is None
            or (known_tasks is not None and type(known_tasks) is not dict)
            or type(lease_token) is not str
            or re.fullmatch(r"[0-9a-f]{32}", lease_token) is None
        ):
            raise ValueError("open direct DEVELOPMENT tool session required")
        if known_tasks is not None and any(
            type(task_id) is not str
            or _TASK_ID.fullmatch(task_id) is None
            or type(state) is not str
            or state not in _ACTIVE_TASK_STATES | _TERMINAL_TASK_STATES
            for task_id, state in known_tasks.items()
        ):
            raise ValueError("verified direct task custody required")
        self._route = lambda action, value: route(
            action, {**value, "exclusive_token": lease_token}
        )
        self._campaign_identity = campaign_identity
        self._admit_new_work = admit_new_work
        self.challenge = dict(opened["challenge"])
        self._opened_unix = opened.get("opened_unix")
        self._keepalive_error = None
        self._closed = False
        self._active_tasks = {
            task_id
            for task_id, state in (known_tasks or {}).items()
            if state in _ACTIVE_TASK_STATES
        }
        self._offered = {}
        tools = []
        for entry in opened["tools"]:
            if type(entry) is not dict:
                raise ValueError("malformed direct tool description")
            name, schema = entry.get("name"), entry.get("input_schema")
            if (
                type(name) is not str
                or not name.startswith(DIRECT_PREFIX)
                or name.removeprefix(DIRECT_PREFIX)
                not in DirectResearchMinerTools.OPERATIONS
                or type(schema) is not dict
                or schema.get("type") != "object"
                or name in self._offered
                or name in (SUBMIT, STAGE_GRAPH)
            ):
                raise ValueError("malformed direct tool description")
            self._offered[name] = True
            operation = name.removeprefix(DIRECT_PREFIX)
            if operation not in _DIRECT_PARAMETERS:
                raise ValueError("unknown direct agent tool")
            tools.append(
                {
                    "type": "function",
                    "name": name,
                    "description": entry.get("description", "Direct DEVELOPMENT tool"),
                    "strict": True,
                    "parameters": deepcopy(_DIRECT_PARAMETERS[operation]),
                }
            )
        if opened.get("construction_intake_configured") is True:
            tools.extend(deepcopy(_CONSTRUCTION_TOOLS))
            self._offered.update({STAGE_GRAPH: True, SUBMIT: True})
        self.tools = tools

    @classmethod
    def open(
        cls,
        route,
        *,
        campaign_identity,
        admit_new_work=None,
        known_tasks=None,
        lease_token=None,
    ):
        """Open through admission and bind a trusted frozen campaign digest."""
        if lease_token is None:
            lease_token = uuid.uuid4().hex
        opened = route("open", {"exclusive_token": lease_token})
        try:
            return cls(
                route,
                opened,
                campaign_identity=campaign_identity,
                admit_new_work=admit_new_work,
                known_tasks=known_tasks,
                lease_token=lease_token,
            )
        except ValueError:
            if not any(
                state in _ACTIVE_TASK_STATES for state in (known_tasks or {}).values()
            ):
                with contextlib.suppress(Exception):
                    route("close", {"exclusive_token": lease_token})
            raise

    def close(self):
        """Release the lock after the direct attachment supervises owned tasks."""
        if not self._closed:
            closed = self._route("close", {})
            if type(closed) is not dict or closed.get("closed") is not True:
                raise UncertainDirectToolDispatch(
                    "direct owned task shutdown requires reconciliation"
                )
            self._closed = True
            self._active_tasks.clear()

    async def keepalive(self, stop, *, interval=_KEEPALIVE_SECONDS):
        """Refresh the owned Tools attachment during slow model turns."""
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                break
            except TimeoutError:
                pass
            try:
                opened = await asyncio.to_thread(self._route, "open", {})
                if (
                    type(opened) is not dict
                    or opened.get("open") is not True
                    or opened.get("challenge") != self.challenge
                    or (
                        self._opened_unix is not None
                        and opened.get("opened_unix") != self._opened_unix
                    )
                ):
                    raise ValueError("direct Tools attachment changed")
            except Exception:  # noqa: BLE001 - outcome of attachment refresh is private
                self._keepalive_error = True
                return

    async def call(self, name, arguments, identity):
        if self._keepalive_error:
            raise UncertainDirectToolDispatch(
                "direct Tools attachment needs reconciliation"
            )
        if self._closed:
            return refusal("UNAVAILABLE", "direct_tool_session_closed")
        if name not in self._offered:
            return refusal("REFUSED_NOT_IN_MANIFEST", "tool_not_offered")
        if type(arguments) is not dict or protected(arguments):
            return refusal("REFUSED_PROTECTED_MATERIAL", "invalid_or_protected_args")
        if type(identity) is not str or _IDENTITY.fullmatch(identity) is None:
            return refusal("REJECTED_BEFORE_DISPATCH", "invalid_operation_identity")
        operation_id = _operation_id(self._campaign_identity, identity)
        try:
            action, value = _dispatch_request(name, arguments, operation_id)
        except (ValueError, TypeError, json.JSONDecodeError):
            return refusal("REJECTED_BEFORE_DISPATCH", "invalid_tool_arguments")
        if (
            name in _NEW_WORK
            and self._admit_new_work is not None
            and not self._admit_new_work()
        ):
            return refusal("UNAVAILABLE", "direct_agent_elapsed")
        try:
            result = await asyncio.to_thread(self._route, action, value)
        except Exception:  # noqa: BLE001 - route failures may carry private detail
            raise UncertainDirectToolDispatch(
                "direct tool outcome requires reconciliation"
            ) from None
        if (
            type(result) is not dict
            or result.get("ok") is not True
            or protected(result)
        ):
            raise UncertainDirectToolDispatch(
                "direct tool outcome requires reconciliation"
            )
        direct = result.get("result")
        if action == "call" and not _direct_result(direct, name, operation_id):
            raise UncertainDirectToolDispatch(
                "direct tool outcome requires reconciliation"
            )
        if action == "call" and name in {_START, _OBSERVE, _CANCEL}:
            task = direct["task"]
            task_id = _public_task_id(task)
            state = task.get("state") if type(task) is dict else None
            if direct["reply"].get("status") == "OK" and task_id is None:
                raise UncertainDirectToolDispatch(
                    "direct task identity requires reconciliation"
                )
            if type(task) is dict and (
                type(state) is not str
                or state not in _ACTIVE_TASK_STATES | _TERMINAL_TASK_STATES
            ):
                raise UncertainDirectToolDispatch(
                    "direct task state requires reconciliation"
                )
            expected = arguments.get("task_id") if name != _START else task_id
            if (
                direct["reply"].get("status") == "OK"
                and task_id is not None
                and task_id == expected
            ):
                if name == _START and state in _ACTIVE_TASK_STATES:
                    self._active_tasks.add(task_id)
                elif state not in _ACTIVE_TASK_STATES:
                    self._active_tasks.discard(task_id)
                if (
                    direct["requires_reconciliation"] is True
                    and state in _ACTIVE_TASK_STATES
                    and task_id in self._active_tasks
                ):
                    return {
                        **result,
                        "requires_reconciliation": False,
                        "task_observation_pending": True,
                    }
        if (
            result.get("ok") is True
            and type(direct) is dict
            and direct.get("requires_reconciliation") is True
        ):
            return {**result, "requires_reconciliation": True}
        return result


class UncertainDirectToolDispatch(RuntimeError):
    """The route may have dispatched; retain the loop intent for reconciliation."""


def _direct_result(value, name, operation_id):
    """Validate the actual DirectToolDoor.call success envelope, not a guess."""
    return (
        type(value) is dict
        and set(value)
        == {
            "schema",
            "operation",
            "operation_id",
            "reply",
            "task",
            "public_result",
            "requires_reconciliation",
            "official_eligible",
        }
        and value["schema"] == "carbon.direct-mcp-result.v3"
        and value["operation"] == name.removeprefix(DIRECT_PREFIX)
        and value["operation_id"] == operation_id
        and type(value["reply"]) is dict
        and (value["task"] is None or type(value["task"]) is dict)
        and (value["public_result"] is None or type(value["public_result"]) is dict)
        and type(value["requires_reconciliation"]) is bool
        and value["official_eligible"] is False
    )


DIRECT_AGENT_INSTRUCTIONS = (
    "Research the public DEVELOPMENT Challenge described by the offered tools. "
    "Read its Challenge and interaction material before choosing a construction "
    "recipe. Form your own hypothesis. Practice may use your own data, including "
    "data you generate with the provided solver. Independent reconstruction "
    "and evaluation use the Challenge-owned fixed TRAIN material. Respect the "
    "registered construction limits. If a task is running, observe or cancel "
    "it by its returned task_id before starting more work. "
    "Stage owner graph source before remote "
    "graph staging when your recipe needs it. Submit only through the offered "
    "direct construction action. A result is DEVELOPMENT evidence, not an "
    "official grade or scientific qualification. Stop when no safe action remains."
)


def _frozen_agent_campaign(ledger, owner):
    """Read the finite campaign the trusted preparation froze."""
    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.research_ledger import (
        DIRECT_AGENT,
        CampaignLedger,
        _check_direct_agent,
    )

    if type(ledger) is not CampaignLedger or type(owner) is not str or not owner:
        raise ValueError("trusted finite agent campaign required")
    with ledger.db() as db:
        row = db.execute("SELECT manifest,digest FROM campaign WHERE id=1").fetchone()
    if row is None:
        raise ValueError("frozen finite agent campaign required")
    manifest = json.loads(row[0])
    if (
        type(manifest) is not dict
        or digest(canonical(manifest)) != row[1]
        or manifest.get("owner") != owner
        or manifest.get("schema") != DIRECT_AGENT
        or manifest.get("canonical_root") != str(ledger.root.resolve(strict=True))
    ):
        raise ValueError("frozen finite direct agent campaign differs")
    _check_direct_agent(manifest)
    identity = digest(canonical([owner, manifest["campaign_id"]]))
    return manifest, identity


def _installed_provider(profile):
    from carbon.development_session.model_provider import DEFAULT_SELECTION
    from scripts.dev.miner_launchpad.runner import (
        provider_credential,
        setup_selection,
    )

    selection = (
        setup_selection(profile) if "model_selection" in profile else DEFAULT_SELECTION
    )
    if selection.reservation_nano is None:
        raise ValueError("finite direct agent requires a priced model selection")
    credential_file = provider_credential(profile, selection.provider_id)
    if type(credential_file) is not str or not credential_file:
        raise ValueError("installed model provider credential file required")
    return selection, credential_file


def _new_work_within_deadline(ledger, campaign_digest, elapsed_seconds):
    """Admit only new direct work while this frozen agent campaign is live.

    Observing, cancelling and reconciling known work remain callable after the
    deadline. The direct task ledger separately owns task execution limits.
    """
    with ledger.db() as db:
        row = db.execute("SELECT digest,started FROM campaign WHERE id=1").fetchone()
    if row is None or row[0] != campaign_digest or type(row[1]) not in (float, int):
        return False
    now = ledger.clock()
    return math.isfinite(now) and row[1] <= now < row[1] + elapsed_seconds


async def _public_material(session):
    """Digest actual public 1.3 discovery, never a legacy Challenge alias."""
    from carbon.development_session.profile import canonical, digest

    values = []
    for operation in ("get_challenge_info", "get_interaction_manifest"):
        name = DIRECT_PREFIX + operation
        if name not in {tool["name"] for tool in session.tools}:
            raise ValueError("direct public discovery tool unavailable")
        result = await session.call(name, {}, "direct-agent-prepare-" + operation)
        if result.get("requires_reconciliation") is True:
            raise UncertainDirectToolDispatch(
                "direct public discovery requires reconciliation"
            )
        direct = result["result"]
        reply = direct["reply"]
        material = reply.get("result") if type(reply) is dict else None
        if (
            type(reply) is not dict
            or reply.get("status") != "OK"
            or type(material) is not dict
        ):
            raise ValueError("direct public discovery unavailable")
        values.append(digest(canonical(material)))
    return tuple(values)


async def prepare_direct_agent_campaign(
    host,
    root,
    *,
    provider_attempts,
    provider_nanodollars,
    retained_bytes,
    elapsed_seconds,
):
    """Freeze one finite, non-scientific campaign from the installed 1.3 kit.

    All four limits are supplied by the operator. The retained-bytes ceiling
    covers the existing provider journal reservation/check, not direct task
    artifacts or owner workspace files, whose own installed limits apply.
    No model call or candidate submission occurs here. A retry at the same
    root must match the frozen owner, profile, Challenge, material and limits.
    """
    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.research_ledger import (
        DIRECT_AGENT,
        CampaignLedger,
    )
    from scripts.dev.miner_launchpad.tool_door import route

    limits = (provider_attempts, provider_nanodollars, retained_bytes, elapsed_seconds)
    if any(type(value) is not int or value < 1 for value in limits):
        raise ValueError("operator-supplied finite direct agent limits required")
    profile = host.configured()
    if type(profile) is not dict:
        raise ValueError("installed direct profile required")
    owner = profile.get("principal")
    campaigns_root = profile.get("campaigns_root")
    if (
        type(owner) is not str
        or not owner
        or type(campaigns_root) is not str
        or not isinstance(root, Path)
        or not root.is_absolute()
        or root.is_symlink()
        or not root.name.startswith("direct-agent-")
        or root.parent.resolve(strict=True) != Path(campaigns_root).resolve(strict=True)
    ):
        raise ValueError("direct agent root must be in installed campaigns root")
    selection, _credential_file = _installed_provider(profile)
    ledger = CampaignLedger(root)
    with ledger.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    old = json.loads(row[0]) if row is not None else None
    campaign_id = old["campaign_id"] if type(old) is dict else uuid.uuid4().hex
    identity = digest(canonical([owner, campaign_id]))
    bound_route = lambda action, value: route(host, SESSION, action, value)
    session = await asyncio.to_thread(
        DirectToolSession.open, bound_route, campaign_identity=identity
    )
    try:
        challenge_info, interaction_manifest = await _public_material(session)
        manifest = {
            "schema": DIRECT_AGENT,
            "campaign_id": campaign_id,
            "canonical_root": str(ledger.root.resolve(strict=True)),
            "owner": owner,
            "agent": "graphite-direct",
            "challenge": session.challenge,
            "direct_development_session": SESSION,
            "profile_digest": digest(canonical(profile)),
            "implementation": profile["accepted_revision"],
            "challenge_info_digest": challenge_info,
            "interaction_manifest_digest": interaction_manifest,
            "provider": selection.manifest_record(),
            "ceilings": {
                "provider_attempts": provider_attempts,
                "provider_nanodollars": provider_nanodollars,
                "retained_bytes": retained_bytes,
            },
            "retained_bytes_scope": "agent_provider_journal_reservation",
            "elapsed_seconds": elapsed_seconds,
        }
        ledger.freeze(manifest)
    finally:
        await asyncio.to_thread(session.close)
    return ledger


async def run_direct_epoch(
    host,
    ledger,
    *,
    epoch,
    max_provider_calls,
    transport=None,
):
    """Hold one OS-owned campaign run from recovery through owned task close."""
    from carbon.development_session.research_ledger import CampaignLedger
    from scripts.dev.miner_launchpad.controller import owner_lock

    if (
        type(ledger) is not CampaignLedger
        or not ledger.root.is_absolute()
        or ledger.root.is_symlink()
    ):
        raise ValueError("trusted direct agent ledger required")
    with owner_lock(ledger.root / "direct-agent-run-owner"):
        # Cancellation of a to_thread route does not stop its worker. Keep the
        # OS run fence until the owned epoch and every awaited route settle;
        # otherwise a retry can share this campaign lease with that worker.
        owned = asyncio.create_task(
            _run_direct_epoch_owned(
                host,
                ledger,
                epoch=epoch,
                max_provider_calls=max_provider_calls,
                transport=transport,
            )
        )
        try:
            return await asyncio.shield(owned)
        except asyncio.CancelledError:
            while not owned.done():
                try:
                    await asyncio.shield(owned)
                except asyncio.CancelledError:
                    continue
                except BaseException:  # noqa: BLE001 - owned failure is reaped below
                    break
            with contextlib.suppress(BaseException):
                owned.result()
            raise


async def _run_direct_epoch_owned(
    host,
    ledger,
    *,
    epoch,
    max_provider_calls,
    transport=None,
):
    """Run one finite agent epoch through the installed 1.3 miner Tools route.

    The caller supplies the ledger returned by preparation. The installed
    Launchpad host supplies the signer, profile, model provider and direct tools;
    the model cannot change either binding. A provider-call cap reached while
    a known task is still running keeps the owned Tools session open and polls
    through its terminal state or the finite campaign deadline before return.
    Verified journals restore task identity after interrupted execution.
    Unknown outcomes retain custody for operator reconciliation; the loop
    journal prevents duplicate dispatch on resume.
    """
    from carbon.development_session.model_provider import selection_from_record
    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.research_agent_policy import (
        GRAPHITE_MINER,
        PARALLEL_CALLS_V2,
        STOP_TOOL,
    )
    from carbon.development_session.research_loop import run_epoch
    from scripts.dev.miner_launchpad.tool_door import route

    if (
        type(epoch) is not int
        or epoch not in (1, 2)
        or type(max_provider_calls) is not int
        or max_provider_calls < 1
    ):
        raise ValueError("finite direct agent epoch required")
    profile = host.configured()
    if type(profile) is not dict or type(profile.get("principal")) is not str:
        raise ValueError("installed direct profile required")
    owner = profile["principal"]
    manifest, identity = _frozen_agent_campaign(ledger, owner)
    if (
        manifest["profile_digest"] != digest(canonical(profile))
        or max_provider_calls > manifest["ceilings"]["provider_attempts"]
    ):
        raise ValueError("direct agent profile or provider cap differs")
    configured, credential_file = _installed_provider(profile)
    if configured.manifest_record() != manifest["provider"]:
        raise ValueError("direct agent model selection changed")
    selection = selection_from_record(
        manifest["provider"], credential_file=credential_file
    )
    campaign_digest = digest(canonical(manifest))
    admit_new_work = lambda: _new_work_within_deadline(
        ledger, campaign_digest, manifest["elapsed_seconds"]
    )
    bound_route = lambda action, value: route(host, SESSION, action, value)
    # Validate retained custody before taking an attachment whose close can
    # cancel tasks. A corrupt journal must never trigger that close.
    known_tasks = _journaled_tasks(ledger, identity)
    prior_tasks = _journaled_tasks(ledger, identity, before_epoch=epoch)
    lease_token = _campaign_lease_token(ledger, identity)
    session = await asyncio.to_thread(
        DirectToolSession.open,
        bound_route,
        campaign_identity=identity,
        admit_new_work=admit_new_work,
        known_tasks=known_tasks,
        lease_token=lease_token,
    )
    try:
        offered_names = {tool["name"] for tool in [*session.tools, STOP_TOOL]}
        checked = _journaled_tasks(ledger, identity, offered_names=offered_names)
        checked_prior = _journaled_tasks(
            ledger, identity, before_epoch=epoch, offered_names=offered_names
        )
        if checked != known_tasks or checked_prior != prior_tasks:
            raise ValueError("direct agent journal changed during attachment")
    except BaseException as error:
        if (
            isinstance(error, Exception)
            and not isinstance(error, UncertainDirectToolDispatch)
            and not session._active_tasks
        ):
            await asyncio.to_thread(session.close)
        raise
    try:
        challenge_info, interaction_manifest = await _public_material(session)
        if (
            session.challenge != manifest["challenge"]
            or challenge_info != manifest["challenge_info_digest"]
            or interaction_manifest != manifest["interaction_manifest_digest"]
        ):
            raise ValueError("direct agent public Challenge binding changed")
    except BaseException:
        if not session._active_tasks:
            await asyncio.to_thread(session.close)
        raise
    limits = {
        "schema": "carbon.autoresearch.limits.v2",
        "calls_per_epoch": max_provider_calls,
        "trials_per_epoch": None,
    }
    observation = {
        "challenge": session.challenge,
        "direct_development_session": SESSION,
        "challenge_info_digest": challenge_info,
        "interaction_manifest_digest": interaction_manifest,
        "retained_bytes_scope": manifest["retained_bytes_scope"],
        "official_eligible": False,
    }
    plan_path = ledger.root / f"epoch-{epoch}" / "direct" / "plan.json"
    try:
        if plan_path.exists():
            if plan_path.is_symlink():
                raise ValueError("direct agent plan path differs")
            plan = json.loads(plan_path.read_bytes())
            prior = plan.get("initial_observation") if type(plan) is dict else None
            if type(prior) is not dict or any(
                prior.get(field) != value for field, value in observation.items()
            ):
                raise ValueError("direct agent prior observation binding differs")
            records = prior.get("known_tasks")
            if (
                set(prior) != set(observation) | {"known_tasks"}
                or type(records) is not list
                or any(
                    type(item) is not dict
                    or set(item) != {"task_id", "state"}
                    or type(item["task_id"]) is not str
                    or type(item["state"]) is not str
                    or item["state"] not in _ACTIVE_TASK_STATES | _TERMINAL_TASK_STATES
                    for item in records
                )
                or [item["task_id"] for item in records] != list(prior_tasks)[-50:]
            ):
                raise ValueError("direct agent prior task observation differs")
            observation = prior
        else:
            observation["known_tasks"] = [
                {"task_id": task_id, "state": state}
                for task_id, state in list(prior_tasks.items())[-50:]
            ]
    except BaseException:
        if not session._active_tasks:
            await asyncio.to_thread(session.close)
        raise
    keepalive_stop = asyncio.Event()
    keepalive = asyncio.create_task(
        session.keepalive(keepalive_stop, interval=_KEEPALIVE_SECONDS)
    )
    supervised = None
    supervised_ids = None
    try:
        result = await run_epoch(
            ledger,
            owner=owner,
            epoch=epoch,
            sdk=session,
            credential_file=credential_file,
            initial_observation=observation,
            agent_policy=GRAPHITE_MINER,
            provider=selection,
            parallel_calls=PARALLEL_CALLS_V2,
            instructions=DIRECT_AGENT_INSTRUCTIONS,
            tools=[*session.tools, STOP_TOOL],
            limits=limits,
            stage="direct",
            transport=transport,
        )
        if result.get("status") != "RECONCILIATION_REQUIRED" and session._active_tasks:
            supervised_ids = sorted(session._active_tasks)
            supervised = await _supervise_active_tasks(
                session,
                ledger,
                identity,
                campaign_digest,
                manifest["elapsed_seconds"],
            )
    except BaseException as error:
        keepalive_stop.set()
        await keepalive
        if (
            not isinstance(error, Exception)
            or isinstance(error, UncertainDirectToolDispatch)
            or session._keepalive_error
            or session._active_tasks
        ):
            raise
        await asyncio.to_thread(session.close)
        raise
    keepalive_stop.set()
    await keepalive
    if session._keepalive_error:
        raise UncertainDirectToolDispatch(
            "direct Tools attachment needs reconciliation"
        )
    if result.get("status") == "RECONCILIATION_REQUIRED":
        return result
    await asyncio.to_thread(session.close)
    if supervised is not None:
        observed, expired = supervised
        return {
            "status": "TASK_EXPIRED" if expired else "TASK_OBSERVED",
            "task_ids": supervised_ids,
            "task_states": observed,
            "cancellation_requested": expired,
            "epoch_outcome": result,
            "official_eligible": False,
        }
    return result


def _positive_cli_integer(raw):
    import argparse

    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("a positive integer is required") from None
    if value < 1:
        raise argparse.ArgumentTypeError("a positive integer is required")
    return value


def cli_parser():
    """The finite operator entry for the installed direct-development route."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m carbon.agent_campaign.graphite direct-agent"
    )
    modes = parser.add_subparsers(dest="action", required=True)
    for action in ("prepare", "run"):
        mode = modes.add_parser(action)
        mode.add_argument("--profile", type=Path, required=True)
        mode.add_argument("--database", type=Path, required=True)
        mode.add_argument("--root", type=Path, required=True)
        if action == "prepare":
            for flag in (
                "provider-attempts",
                "provider-nanodollars",
                "retained-bytes",
                "elapsed-seconds",
            ):
                mode.add_argument(
                    "--" + flag, type=_positive_cli_integer, required=True
                )
        else:
            mode.add_argument("--epoch", type=int, choices=(1, 2), required=True)
            mode.add_argument(
                "--max-provider-calls", type=_positive_cli_integer, required=True
            )
    return parser


def cli_main(argv=None):
    """Use the normal installed host; never choose budgets or a provider."""
    from carbon.development_session.research_ledger import CampaignLedger
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    args = cli_parser().parse_args(argv)
    if not args.root.is_absolute():
        print(
            json.dumps(
                {"direct_agent": "REFUSED", "reason_code": "absolute_root_required"}
            )
        )
        return 2
    try:
        host = RunnerAdapter(args.database, configuration=args.profile)
        if args.action == "prepare":
            asyncio.run(
                prepare_direct_agent_campaign(
                    host,
                    args.root,
                    provider_attempts=args.provider_attempts,
                    provider_nanodollars=args.provider_nanodollars,
                    retained_bytes=args.retained_bytes,
                    elapsed_seconds=args.elapsed_seconds,
                )
            )
            print(json.dumps({"direct_agent": "PREPARED", "official_eligible": False}))
            return 0
        result = asyncio.run(
            run_direct_epoch(
                host,
                CampaignLedger(args.root),
                epoch=args.epoch,
                max_provider_calls=args.max_provider_calls,
            )
        )
        status = result.get("status") if type(result) is dict else None
        if type(status) is not str:
            raise ValueError("direct agent epoch result required")
        print(json.dumps({"direct_agent": status, "official_eligible": False}))
        return 0 if status in {"STOPPED", "TASK_OBSERVED"} else 2
    except UncertainDirectToolDispatch:
        print(
            json.dumps(
                {"direct_agent": "RECONCILIATION_REQUIRED", "official_eligible": False}
            )
        )
        return 2
    except Exception as error:  # noqa: BLE001 - no private exception text on CLI
        from carbon.miner_mcp.standard_cli import refusal_code

        print(
            json.dumps(
                {
                    "direct_agent": "REFUSED",
                    "reason_code": refusal_code(error) or "direct_agent_unavailable",
                    "official_eligible": False,
                }
            )
        )
        return 2
