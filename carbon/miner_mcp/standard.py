"""Object-valued adapter for a trusted, requester-bound research SDK.

This is a transport-neutral boundary, not an MCP server or an authentication
mechanism. An operator composes one adapter with the existing admitted controller.
External transports must resolve identity to that adapter before every call.
No caller chooses a principal, grant, filesystem root, or internal session here.

Operation IDs are durable business keys supplied again on retry/reconnect. The
existing SDK, gateway, task provider and campaign ledger retain all execution,
ownership, idempotency and accounting authority. This adapter has no task store.

Every failure is a closed code with an honest `dispatch_may_have_occurred`.
"Nothing was dispatched" is reported only where it is a fact: a typed
pre-dispatch refusal, a signer failure before any signature, or a refusal
raised at one of the two SDK sites that run before anything is signed (the
operation-id binding and the campaign's admission check; `_pre_dispatch_stop`).
Everything else keeps the conservative answer (LP-PROD-B).
"""

from __future__ import annotations

import itertools
import json
import math
import re
import uuid
from dataclasses import dataclass
from enum import Enum

from carbon import research
from carbon.chain.external_signer import SignerFailure
from carbon.development_session.profile import canonical
from carbon.development_session.research_control import DispatchStopped
from carbon.development_session.research_tools import (
    FIELDS,
    NULLABLE_TASK_FIELDS,
    PREFIX,
    TASK_CORRECTIONS,
    PreDispatchRefusal,
    ResearchMinerTools,
    task_correction,
)
from carbon.development_session.research_tools import (
    _registered_argument as registered_argument,
)
from carbon.research.model import DEVELOPMENT_WORKSPACE_ACTIONS

# Leave room for the SDK's ledger identity prefixes ("trial-attempt-", "task-request-").
OPERATION_ID_PATTERN = r"[A-Za-z0-9._:-]{16,114}"
_TOKEN = re.compile(OPERATION_ID_PATTERN + r"\Z", re.ASCII)
_ARGUMENT_BYTES = 32768
#: What one research result may occupy on the wire. A larger result is cut to
#: fit, with an explicit record of what was cut (`_fit`), never refused: the
#: work it reports has already happened.
_RESULT_BYTES = 1024 * 1024
#: A controller value beyond this is not a result this server forwards at all.
_RESULT_HARD_BYTES = 16 * 1024 * 1024
#: Strings and lists at or below these sizes are never cut: identities, states
#: and codes are short, so only bulk content is ever shortened.
_KEEP_STRING = 1024
_KEEP_LIST = 16
#: Room kept for the truncation record itself (`_truncation`): at most 16
#: notes, each a printable-ASCII path of at most 160 characters and three
#: integers, plus fixed text - about 4.5 KiB at most.
_RECORD_BYTES = 8192
#: Passes `_fit` makes. Each cuts every node it needs that is not inside one
#: it already cut, so a further pass is only for content nested in a cut.
_FIT_PASSES = 8
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
    # The miner's own signer (`carbon-miner-signer`) could not sign this call:
    # one code per condition, so the miner is told which. Carbon holds no key.
    SIGNER_NOT_RUNNING = "SIGNER_NOT_RUNNING"
    SIGNER_REFUSED = "SIGNER_REFUSED"
    SIGNER_WRONG_HOTKEY = "SIGNER_WRONG_HOTKEY"
    SIGNER_TIMEOUT = "SIGNER_TIMEOUT"
    SIGNER_INVALID_SIGNATURE = "SIGNER_INVALID_SIGNATURE"
    SIGNER_PROTOCOL = "SIGNER_PROTOCOL"
    # Refused before anything was signed (LP-PROD-B), each its own code so a
    # client is told which limit stopped it and that nothing started - never
    # folded into OPERATIONAL_STOP, whose guidance is "do not retry".
    #: The campaign's time limit is reached: the elapsed budget its miner set,
    #: or a development grant's expiry (or the host clock moved backwards).
    CAMPAIGN_ELAPSED_BUDGET_REACHED = "CAMPAIGN_ELAPSED_BUDGET_REACHED"
    #: The campaign is paused, stopping, stopped, completed or awaiting
    #: reconciliation, or another holder took its control generation.
    CAMPAIGN_ADMISSION_STOPPED = "CAMPAIGN_ADMISSION_STOPPED"
    #: This operation_id already names a different request in this campaign.
    OPERATION_ID_REUSED = "OPERATION_ID_REUSED"
    #: tasks/get or tasks/cancel named a task this campaign does not hold:
    #: unknown, or another miner's - the two are indistinguishable by design.
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    #: tasks/get on a task already observed the most times the task provider
    #: allows (its typed BOUND_EXCEEDED): a permanent answer for that task,
    #: never a transient one a client should retry.
    OBSERVATION_LIMIT_REACHED = "OBSERVATION_LIMIT_REACHED"


class AdapterFailure(ValueError):
    """Closed public error; details from trusted services never cross the wire."""

    def __init__(self, code: AdapterCode, *, dispatch_may_have_occurred=False):
        super().__init__(code.value)
        self.code = code
        self.dispatch_may_have_occurred = dispatch_may_have_occurred


def _signer_failure(failure, issued_before, key):
    """A signer failure, honest about whether a signed request can exist.

    Each tool call signs once, before its request leaves Carbon, so a failed
    signature normally means nothing was sent. If this call had already
    obtained a signature, a signed request may exist and that is reported.
    """
    issued = getattr(key, "issued", None)
    return AdapterFailure(
        AdapterCode(failure.code.upper()),
        dispatch_may_have_occurred=issued is None or issued != issued_before,
    )


def _refused_before_dispatch(refusal):
    """Map a pre-dispatch refusal to its closed code; nothing can have run."""
    code = (
        AdapterCode.NO_CAMPAIGN
        if refusal.reason == "NO_CAMPAIGN"
        else AdapterCode.OPERATIONAL_STOP
    )
    return AdapterFailure(code, dispatch_may_have_occurred=False)


#: The SDK's two sites that run before anything is signed, identified by code
#: object rather than by name, so a lookalike elsewhere cannot qualify:
#: `call` binds the operation id to its request (`ledger.reserve`), and `_call`
#: runs the campaign's admission check (`check_registration`) before it signs.
_SDK_ENTRY = ResearchMinerTools.call.__code__
_SDK_BODY = ResearchMinerTools._call.__code__
_ADMISSION_CHECKS = frozenset({"check_registration", "check_cleanup_registration"})
#: The admission check's own refusals (the attached campaign's connection),
#: by the exact text its raising site uses.
_ADMISSION_STOPS = {
    "campaign elapsed budget reached": AdapterCode.CAMPAIGN_ELAPSED_BUDGET_REACHED,
    "campaign admission stopped": AdapterCode.CAMPAIGN_ADMISSION_STOPPED,
}
#: The binding reservation's own refusals (`CampaignLedger._reserve`).
_BINDING_STOPS = {
    "operation replay conflict": AdapterCode.OPERATION_ID_REUSED,
    "campaign elapsed-time exhausted or clock regressed": (
        AdapterCode.CAMPAIGN_ELAPSED_BUDGET_REACHED
    ),
}
#: Campaign control's own refusals at the binding. On a controlled campaign -
#: every product and development grant campaign - `ledger.reserve` runs
#: `CampaignControl.checkpoint` before `_reserve`, so a spent time limit is
#: refused there first, as this deadline; any other fence (stop, a lost
#: generation, reconciliation) is admission stopped. Without this a numerical
#: start and a read on the same expired campaign reported two different codes.
_CONTROL_STOPS = {
    "original campaign deadline reached": AdapterCode.CAMPAIGN_ELAPSED_BUDGET_REACHED,
}


def _pre_dispatch_stop(exc):
    """The closed code for a failure raised before anything was signed, or None.

    Decided by where the exception was raised, read from its own traceback:
    inside the operation-id binding that `ResearchMinerTools.call` makes before
    `_call`, or inside the admission check `_call` makes before it signs. A
    failure at either site is a fact that no signed request exists, so nothing
    can have been dispatched. The message then only picks which closed code -
    a limit the miner can act on - and any other failure there is still an
    OPERATIONAL_STOP that started nothing. A failure anywhere else, including
    the same text raised deeper in a dispatch, is not matched here and keeps
    the conservative answer.
    """
    codes = []
    trace = exc.__traceback__
    while trace is not None:
        codes.append(trace.tb_frame.f_code)
        trace = trace.tb_next
    message = str(exc) if type(exc) is ValueError else None
    for outer, inner in itertools.pairwise(codes):
        if outer is _SDK_BODY and inner.co_name in _ADMISSION_CHECKS:
            return _ADMISSION_STOPS.get(message, AdapterCode.OPERATIONAL_STOP)
        if outer is _SDK_ENTRY and inner.co_name == "reserve":
            if isinstance(exc, DispatchStopped):
                return _CONTROL_STOPS.get(
                    str(exc), AdapterCode.CAMPAIGN_ADMISSION_STOPPED
                )
            return _BINDING_STOPS.get(message, AdapterCode.OPERATIONAL_STOP)
    return None


def _operational(exc):
    """An unexpected controller failure as a closed code: pre-dispatch when its
    raising site proves it (`_pre_dispatch_stop`), otherwise conservative."""
    code = _pre_dispatch_stop(exc)
    if code is not None:
        return AdapterFailure(code, dispatch_may_have_occurred=False)
    # The controller retains ambiguous reservations and dispatch intents.
    # Never label an authentication/execution failure as candidate failure.
    return AdapterFailure(AdapterCode.OPERATIONAL_STOP, dispatch_may_have_occurred=True)


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
            else "arguments" if key == "arguments_json" else key
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


#: Corrections whose registered text describes the SDK's JSON-string wire and
#: would be wrong guidance on this object-valued one.
_OBJECT_CORRECTIONS = {
    "json_string_required": (
        "This field takes a JSON object (or null where the description allows "
        "it), not a string, list or number."
    ),
}


def object_wording(text):
    """The SDK's JSON-string field names in this wire's object-valued terms."""
    return (
        text.replace("recipe JSON string", "recipe object")
        .replace("strategy_json", "strategy")
        .replace("arguments_json", "arguments")
    )


def _correction(operation, value):
    """A registered correction for the object-valued wire, or a refusal.

    The SDK builds a correction from a registered code and the one field that
    broke the contract (`task_correction`), or, on an older shape, the
    registered text alone. Only text this module can rebuild from those passes:
    the code must be registered, the field must be one the SDK may name, and
    the text must equal what `task_correction` makes for them. So no solver
    message or exception text can ride along, whatever the shape.
    """
    code, text = value["correction_code"], value["correction"]
    if (
        operation != "start_research_task"
        or type(code) is not str
        or code not in TASK_CORRECTIONS
        or type(text) is not str
    ):
        _invalid()
    field = value.get("field")
    if "field" in value:
        if type(field) is not str or not (
            field in NULLABLE_TASK_FIELDS or registered_argument(field)
        ):
            _invalid()
        # The SDK passes the field's own value; only whether it is the string
        # "null" changes the text, so these two are every text it can make.
        expected = {
            task_correction(code, field, None),
            task_correction(code, field, "null"),
        }
    else:
        expected = {TASK_CORRECTIONS[code]}
    if text not in expected:
        _invalid()
    if code in _OBJECT_CORRECTIONS:
        text = text.replace(TASK_CORRECTIONS[code], _OBJECT_CORRECTIONS[code])
    projected = {"correction_code": code, "correction": object_wording(text)}
    if field is not None:
        projected["field"] = object_wording(field)
    return projected


def _cut(path, node, size, excess):
    """Shorten one string or list in place by about `excess` bytes; a note.

    A string keeps its head and says how much was cut, inside itself; a list
    keeps a prefix of whole elements. Never below `_KEEP_STRING`/`_KEEP_LIST`.
    """
    container, key = path[-1]
    if type(node) is str:
        keep = max(_KEEP_STRING, len(node) - excess - 64)
        if keep >= len(node):
            return None
        container[key] = (
            node[:keep] + f" [{len(node) - keep} characters truncated by Carbon MCP]"
        )
        return {"kind": "string", "kept": keep, "original": len(node)}
    budget, kept = size - excess, 0
    for child in node:
        budget -= len(canonical(child)) + 1
        if budget < 0:
            break
        kept += 1
    kept = max(_KEEP_LIST, kept)
    if kept >= len(node):
        return None
    container[key] = node[:kept]
    return {"kind": "list", "kept": kept, "original": len(node)}


def _long(value):
    """Every string longer than `_KEEP_STRING` and list longer than
    `_KEEP_LIST` in `value`: (encoded size, path, node). A path is the
    (container, key) pairs from the root, so a cut can replace in place."""
    found = []
    pending = [(value, ())]
    while pending:
        node, path = pending.pop()
        if type(node) is str and len(node) > _KEEP_STRING:
            found.append((len(canonical(node)), path, node))
        elif type(node) is list:
            if len(node) > _KEEP_LIST:
                found.append((len(canonical(node)), path, node))
            pending.extend(
                (child, (*path, (node, index))) for index, child in enumerate(node)
            )
        elif type(node) is dict:
            pending.extend((child, (*path, (node, key))) for key, child in node.items())
    return found


def _path_text(path):
    """A cut's path for the record: printable ASCII only, at most 160
    characters, so each note's encoded size is bounded by its length."""
    text = ".".join(str(key) for _, key in path)
    return "".join(c if " " <= c <= "~" and c not in '"\\' else "?" for c in text[:160])


def _fit(value, limit):
    """Cut bulk content until the canonical encoding fits; what was cut.

    Each pass shortens the largest strings and lists, largest first, until the
    bytes it has saved cover the excess; content nested inside something cut
    in this pass waits for the next pass, which measures again. Protocol fields
    - identities, states, statuses, flags - are short and so are never
    touched. A few passes at most, and a pass that cuts nothing ends the
    attempt, so a value that cannot fit is refused without re-encoding it over
    and over. Returns the notes (`path`, `kind`, `kept`, `original`), or None
    when nothing was cut; raises INVALID_RESULT only when cutting cannot make
    the value fit.
    """
    notes = []
    for _ in range(_FIT_PASSES):
        size = len(canonical(value))
        if size <= limit:
            return notes or None
        excess = size - limit
        cut = []
        for node_size, path, node in sorted(
            _long(value), key=lambda item: item[0], reverse=True
        ):
            if excess <= 0:
                break
            if any(container is done for container, _ in path for done in cut):
                continue
            note = _cut(path, node, node_size, excess)
            if note is None:
                continue
            cut.append(node)
            container, key = path[-1]
            excess -= node_size - len(canonical(container[key]))
            note["path"] = _path_text(path)
            notes.append(note)
        if not cut:
            break
    _invalid()


def _truncation(notes):
    """The record a cut result carries: what was cut, bounded in size
    (`_RECORD_BYTES` holds it), so a client can tell partial content."""
    return {
        "marker": "truncated by Carbon MCP",
        "limit_bytes": _RESULT_BYTES,
        "cut": notes[:16],
        "cut_total": len(notes),
        "note": (
            "This result exceeded the wire limit, so its largest strings and "
            "lists were shortened: each path names one, with how much was "
            "kept (the first 16 cuts are listed; cut_total counts them all). "
            "Read the full content in smaller pieces (read_file takes offset "
            "and count)."
        ),
    }


def _result(operation, value):
    try:
        value = _snapshot(value, limit=_RESULT_HARD_BYTES)
        if type(value) is not dict:
            _invalid()
        if value.get("status") == "REJECTED_BEFORE_DISPATCH":
            fields = {"status", "reason", "detail", "authority_granted"}
            if set(value) not in (
                fields,
                fields | {"correction_code", "correction"},
                fields | {"correction_code", "field", "correction"},
            ):
                _invalid()
            if (
                value["authority_granted"] is not False
                or type(value["reason"]) is not str
                or type(value["detail"]) is not str
            ):
                _invalid()
            if "correction_code" in value:
                # Translate only registered guidance, never arbitrary solver or
                # exception text. External clients use objects at this boundary.
                value.update(_correction(operation, value))
            if len(canonical(value)) > _RESULT_BYTES:
                _invalid()
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
                or len(canonical(value)) > _RESULT_BYTES
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
        # A large result is cut to fit and says so, rather than refused: the
        # work it reports has happened, and refusing it would leave the miner
        # with an INVALID_RESULT and nothing to retry.
        notes = _fit(value, _RESULT_BYTES - _RECORD_BYTES)
        if notes is not None:
            value["truncation"] = _truncation(notes)
            # The record's room is sized from its bounds; checked anyway, so a
            # cut result can never leave this server over the wire limit.
            if len(canonical(value)) > _RESULT_BYTES:
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

    @property
    def sdk_tools(self):
        """The SDK's own tool list for this campaign, for descriptions only:
        the prospective `tools_for_sdk` when authored Julia is admitted,
        otherwise the fixed list. Discovery; execution rechecks everything."""
        from carbon.development_session.research_tools import TOOLS, tools_for_sdk

        return tools_for_sdk(self._sdk) if self.authored_julia_available else TOOLS

    @property
    def gpu_lane(self):
        """The campaign's GPU lane for the code cell (RSURF-D20), described,
        or None. Discovery only: execution rechecks it before dispatch."""
        self._check_binding()
        lane = getattr(getattr(self._sdk.composition, "executor", None), "gpu", None)
        return None if lane is None else lane.describe()

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
        key = getattr(getattr(self._sdk, "connection", None), "miner_key", None)
        issued_before = getattr(key, "issued", None)
        try:
            value = await self._sdk.call(
                PREFIX + request.operation,
                args,
                request.operation_id,
                transport_request_id="mcp-" + uuid.uuid4().hex,
            )
        except PreDispatchRefusal as refusal:
            # Caught before the blanket handler below, and reported with
            # dispatch_may_have_occurred=False. That is a fact here rather than
            # an optimistic default: the refusal is raised at the top of the
            # call, before any reservation is possible. Folding it into the
            # conservative case would tell a miner their work may have started
            # when nothing could have.
            raise _refused_before_dispatch(refusal) from None
        except SignerFailure as failure:
            raise _signer_failure(failure, issued_before, key) from None
        except Exception as exc:  # noqa: BLE001
            # Pre-dispatch only where the raising site proves it; otherwise the
            # controller retains ambiguous reservations and dispatch intents.
            raise _operational(exc) from None
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
        key = getattr(getattr(self._sdk, "connection", None), "miner_key", None)
        issued_before = getattr(key, "issued", None)
        try:
            value = await self._sdk.task_call(mode, args, identity)
        except PreDispatchRefusal as refusal:
            # The same fact as the synchronous path: refused before anything
            # could be reserved, so nothing can have started.
            raise _refused_before_dispatch(refusal) from None
        except SignerFailure as failure:
            raise _signer_failure(failure, issued_before, key) from None
        except research.ResearchTaskProviderError as failure:
            if (
                mode != "start"
                and failure.code is research.ResearchServiceErrorCode.TASK_NOT_FOUND
            ):
                # The campaign's own task provider holds no such task: unknown,
                # or another miner's, which this composition cannot see either.
                # An observation or cancellation of nothing dispatched nothing.
                raise AdapterFailure(
                    AdapterCode.TASK_NOT_FOUND, dispatch_may_have_occurred=False
                ) from None
            if (
                mode == "observe"
                and failure.code is research.ResearchServiceErrorCode.BOUND_EXCEEDED
            ):
                # The provider's bound on observing one task: permanent for
                # that task, so it is never reported as a retryable stop.
                raise AdapterFailure(
                    AdapterCode.OBSERVATION_LIMIT_REACHED,
                    dispatch_may_have_occurred=False,
                ) from None
            raise _operational(failure) from None
        except Exception as exc:  # noqa: BLE001
            raise _operational(exc) from None
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
