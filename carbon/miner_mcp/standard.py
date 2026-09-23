"""Object-valued adapter for a trusted, requester-bound research SDK.

This is a transport-neutral boundary, not an MCP server or an authentication
mechanism. An operator composes one adapter with the existing admitted controller.
External transports must resolve identity to that adapter before every call.
No caller chooses a principal, grant, filesystem root, or internal session here.

Operation IDs are durable business keys supplied again on retry/reconnect. The
existing SDK, gateway, task provider and campaign ledger retain all execution,
ownership, idempotency and accounting authority. This adapter has no task store.
"""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass
from enum import Enum

from carbon import research
from carbon.development_session.profile import canonical
from carbon.development_session.research_tools import (
    FIELDS,
    PREFIX,
    TASK_CORRECTIONS,
    PreDispatchRefusal,
    ResearchMinerTools,
)
from carbon.research.model import DEVELOPMENT_WORKSPACE_ACTIONS

# Leave room for the existing SDK's "trial-attempt-" ledger identity prefix.
_TOKEN = re.compile(r"[A-Za-z0-9._:-]{16,114}\Z", re.ASCII)
_ARGUMENT_BYTES = 32768
_RESULT_BYTES = 1024 * 1024
_STRATEGY_OPERATIONS = frozenset(
    {
        "dry_validate",
        "compile_strategy",
        "inspect_prior_alignment",
        "inspect_resources",
        "forecast_resources",
    }
)


class AdapterCode(str, Enum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    OWNER_BINDING = "OWNER_BINDING"
    OPERATIONAL_STOP = "OPERATIONAL_STOP"
    INVALID_RESULT = "INVALID_RESULT"
    # Refused before anything could be dispatched. Distinct from
    # OPERATIONAL_STOP, which is a campaign declining work: this one means there
    # is no campaign, so the miner has nothing to reconcile and should not be
    # sent looking for consumption that cannot exist.
    NO_CAMPAIGN = "NO_CAMPAIGN"


class AdapterFailure(ValueError):
    """Closed public error; details from trusted services never cross the wire."""

    def __init__(self, code: AdapterCode, *, dispatch_may_have_occurred=False):
        super().__init__(code.value)
        self.code = code
        self.dispatch_may_have_occurred = dispatch_may_have_occurred


@dataclass(frozen=True)
class ResearchToolRequest:
    operation: str
    operation_id: str
    arguments: dict


@dataclass(frozen=True)
class ResearchToolResult:
    operation: str
    operation_id: str
    payload: dict
    requires_reconciliation: bool
    official_eligible: bool = False


def _invalid():
    raise AdapterFailure(AdapterCode.INVALID_ARGUMENT)


def _snapshot(value, *, limit):
    """Copy exact finite JSON values without custom serializers or coercion."""

    remaining = [limit]

    def visit(item, depth):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 32:
            _invalid()
        kind = type(item)
        if item is None or kind in (bool, int):
            return
        if kind is float:
            if not math.isfinite(item):
                _invalid()
            return
        if kind is str:
            remaining[0] -= len(item)
        elif kind is list:
            for child in item:
                visit(child, depth + 1)
        elif kind is dict:
            for key, child in item.items():
                if type(key) is not str:
                    _invalid()
                visit(key, depth + 1)
                visit(child, depth + 1)
        else:
            _invalid()
        if remaining[0] < 0:
            _invalid()

    visit(value, 0)
    try:
        encoded = canonical(value)
        if len(encoded) > limit:
            _invalid()
        return json.loads(encoded)
    except (ValueError, UnicodeError, RecursionError):
        _invalid()


def _object_json(value):
    if type(value) is not dict:
        _invalid()
    encoded = canonical(value)
    if len(encoded) > 16384:
        _invalid()
    return encoded.decode("utf-8")


def _arguments(operation, supplied):
    if type(supplied) is not dict:
        _invalid()
    expected = {
        (
            "strategy"
            if key == "strategy_json"
            else "arguments"
            if key == "arguments_json"
            else key
        )
        for key in FIELDS[operation]
    }
    if set(supplied) != expected:
        _invalid()
    args = _snapshot(supplied, limit=_ARGUMENT_BYTES)
    if operation in _STRATEGY_OPERATIONS:
        args["strategy_json"] = _object_json(args.pop("strategy"))
    if operation == "forecast_resources" and (
        type(args["seconds"]) is not int or not 1 <= args["seconds"] <= 600
    ):
        _invalid()
    if operation in {"get_research_result", "cancel_research_task"}:
        try:
            research.ResearchTaskId(args["task_id"])
        except (TypeError, ValueError):
            _invalid()
    if operation == "get_research_result" and (
        type(args["poll_sequence"]) is not int or not 0 <= args["poll_sequence"] <= 9999
    ):
        _invalid()
    if operation == "start_research_task":
        for key in ("hypothesis", "expected_effect"):
            if type(args[key]) is not str or not 1 <= len(args[key]) <= 2048:
                _invalid()
        if args["kind"] == "practice":
            if args["action"] is not None or args["arguments"] is not None:
                _invalid()
            args["strategy_json"] = _object_json(args.pop("strategy"))
            args["arguments_json"] = args.pop("arguments")
        elif args["kind"] == "workspace":
            if args["strategy"] is not None or args["action"] not in (
                *DEVELOPMENT_WORKSPACE_ACTIONS,
                "run_julia",
            ):
                _invalid()
            args["strategy_json"] = args.pop("strategy")
            args["arguments_json"] = _object_json(args.pop("arguments"))
        else:
            _invalid()
    # Escaping an object into the legacy string fields can increase its size.
    if len(canonical(args)) > _ARGUMENT_BYTES:
        _invalid()
    return args


def _result(operation, value):
    try:
        value = _snapshot(value, limit=_RESULT_BYTES)
        if type(value) is not dict:
            _invalid()
        if value.get("status") == "REJECTED_BEFORE_DISPATCH":
            fields = {"status", "reason", "detail", "authority_granted"}
            if set(value) not in (fields, fields | {"correction_code", "correction"}):
                _invalid()
            if (
                value["authority_granted"] is not False
                or type(value["reason"]) is not str
                or type(value["detail"]) is not str
            ):
                _invalid()
            if "correction_code" in value:
                code = value["correction_code"]
                if (
                    operation != "start_research_task"
                    or type(code) is not str
                    or code not in TASK_CORRECTIONS
                    or value["correction"] != TASK_CORRECTIONS[code]
                ):
                    _invalid()
                # Translate only registered guidance, never arbitrary solver or
                # exception text. External clients use objects at this boundary.
                value["correction"] = (
                    TASK_CORRECTIONS[code]
                    .replace("recipe JSON string", "recipe object")
                    .replace("strategy_json", "strategy")
                    .replace("arguments_json", "arguments")
                )
            return value, False
        if value.get("status") == "UNAVAILABLE":
            if set(value) != {
                "operation",
                "status",
                "reason",
                "detail",
                "authority_granted",
            }:
                _invalid()
            if (
                value["operation"] != operation
                or value["authority_granted"] is not False
            ):
                _invalid()
            return value, False
        if set(value) != {
            "protocol",
            "operation",
            "reply",
            "terminal_task",
            "public_result",
            "requires_reconciliation",
        } or (
            value["protocol"] != research.RESEARCH_NAMESPACE
            or value["operation"] != operation
            or type(value["reply"]) is not dict
            or type(value["requires_reconciliation"]) is not bool
        ):
            _invalid()
        return value, value["requires_reconciliation"]
    except AdapterFailure:
        raise AdapterFailure(
            AdapterCode.INVALID_RESULT, dispatch_may_have_occurred=True
        ) from None


class ResearchToolAdapter:
    """Wrap an already authenticated/admitted SDK; never issue a new grant.

    Reopening uses the controller's existing persisted composition and journal.
    Creating a new output directory or adapter does not authorize a campaign.
    Protocol disconnect is not proof of cancellation; only the domain task and
    carrier can report observed cancellation/cleanup. No automatic retries occur.

    Each transmission uses a new internal transport ID. The supplied business
    operation ID still binds task idempotency and the existing proposal charge;
    a repeated start returns the existing task without admitting new work.
    """

    def __init__(self, sdk: ResearchMinerTools, *, principal: str):
        if (
            type(sdk) is not ResearchMinerTools
            or type(principal) is not str
            or not 1 <= len(principal) <= 128
            or sdk.owner != principal
            or getattr(getattr(sdk.composition, "executor", None), "owner", None)
            != principal
        ):
            raise AdapterFailure(AdapterCode.OWNER_BINDING)
        self._sdk = sdk
        self._principal = principal
        self._binding = (sdk.connection, sdk.wrapper, sdk.composition, sdk.ledger)
        self._task_api_used = False

    @property
    def principal(self) -> str:
        """Operator-selected identity; never supplied by a transport caller."""
        return self._principal

    def _check_binding(self):
        sdk = self._sdk
        if (
            sdk.owner != self._principal
            or getattr(getattr(sdk.composition, "executor", None), "owner", None)
            != self._principal
            or any(
                current is not expected
                for current, expected in zip(
                    (sdk.connection, sdk.wrapper, sdk.composition, sdk.ledger),
                    self._binding,
                )
            )
        ):
            raise AdapterFailure(AdapterCode.OWNER_BINDING)

    @property
    def authored_julia_available(self):
        """Discovery reflects the bound operator grant; execution rechecks it."""
        from carbon.development_session.julia_analysis import authorize_julia

        self._check_binding()
        try:
            authorize_julia(
                self._sdk.ledger,
                self._principal,
                getattr(self._sdk.composition.executor, "julia_image", None),
            )
        except (ValueError, TypeError, AttributeError):
            return False
        return True

    async def call(self, request: ResearchToolRequest) -> ResearchToolResult:
        self._check_binding()
        if (
            type(request) is not ResearchToolRequest
            or type(request.operation) is not str
            or request.operation not in research.SUPPORTED_OPERATIONS
            or type(request.operation_id) is not str
            or _TOKEN.fullmatch(request.operation_id) is None
        ):
            _invalid()
        args = _arguments(request.operation, request.arguments)
        try:
            value = await self._sdk.call(
                PREFIX + request.operation,
                args,
                request.operation_id,
                transport_request_id="mcp-" + uuid.uuid4().hex,
            )
        except PreDispatchRefusal:
            # Caught before the blanket handler below, and reported with
            # dispatch_may_have_occurred=False. That is a fact here rather than
            # an optimistic default: the refusal is raised at the top of the
            # call, before any reservation is possible. Folding it into the
            # conservative case would tell a miner their work may have started
            # when nothing could have.
            raise AdapterFailure(
                AdapterCode.NO_CAMPAIGN, dispatch_may_have_occurred=False
            ) from None
        except Exception:  # noqa: BLE001
            # The controller retains ambiguous reservations and dispatch intents.
            # Never label an authentication/execution failure as candidate failure.
            raise AdapterFailure(
                AdapterCode.OPERATIONAL_STOP, dispatch_may_have_occurred=True
            ) from None
        payload, reconcile = _result(request.operation, value)
        return ResearchToolResult(
            request.operation, request.operation_id, payload, reconcile
        )

    async def start_task(self, request: ResearchToolRequest) -> ResearchToolResult:
        """Acknowledge the existing durable task before owned execution ends."""
        self._check_binding()
        if (
            type(request) is not ResearchToolRequest
            or request.operation != "start_research_task"
            or type(request.operation_id) is not str
            or _TOKEN.fullmatch(request.operation_id) is None
        ):
            _invalid()
        args = _arguments(request.operation, request.arguments)
        return await self._task_call("start", args, request.operation_id)

    async def observe_task(self, task_id: str) -> ResearchToolResult:
        self._check_binding()
        args = _arguments(
            "get_research_result", {"task_id": task_id, "poll_sequence": 0}
        )
        return await self._task_call("observe", args, "mcp-observe-" + task_id)

    async def cancel_task(self, task_id: str) -> ResearchToolResult:
        self._check_binding()
        args = _arguments("cancel_research_task", {"task_id": task_id})
        return await self._task_call("cancel", args, "mcp-cancel-" + task_id)

    async def _task_call(self, mode, args, identity):
        self._task_api_used = True
        try:
            value = await self._sdk.task_call(mode, args, identity)
        except Exception:  # noqa: BLE001
            raise AdapterFailure(
                AdapterCode.OPERATIONAL_STOP, dispatch_may_have_occurred=True
            ) from None
        if mode != "start":
            if (
                type(value) is not dict
                or type(value.get("original_operation_id")) is not str
            ):
                raise AdapterFailure(
                    AdapterCode.INVALID_RESULT, dispatch_may_have_occurred=True
                )
            identity = value.pop("original_operation_id")
            value["operation"] = "start_research_task"
        payload, reconcile = _result("start_research_task", value)
        return ResearchToolResult("start_research_task", identity, payload, reconcile)

    async def shutdown_tasks(self):
        self._check_binding()
        shutdown = getattr(self._sdk.wrapper, "shutdown_tasks", None)
        if callable(shutdown):
            await shutdown()
        elif self._task_api_used:
            raise AdapterFailure(AdapterCode.OWNER_BINDING)
