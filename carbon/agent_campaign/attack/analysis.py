"""Carbon's reading of an attack session: its recorded tool calls, as attempts.

Challenge-neutral (OWNER-GRAPHITE-ATTACKER-01 §1). Carbon decides from what a
session's research loop journalled, never from the model's prose:

- **`attempts(session_dir)`** reads every tool call and its recorded result
  from the research loop's journal (`ledger/epoch-N[/<stage>]/`). Each
  journal identity must be exactly what `research_loop.tool_identity(epoch,
  turn, position, stage)` names, so v2 turns with several calls (`-KK`) and
  staged sessions read one way; anything else is refused, never guessed.
- **Protected material** is checked on every read: a request by Graphite's
  own request filter (`graphite.tools.protected`, the rule its harness refuses
  requests under), a result by the narrowed exposure rule (`exposes`:
  `attack.knowledge.protected` and the registered sealed identities, so a
  result naming an attack target such as `.env` or `secret` is not misread
  as an exposure). An attempt whose request or result names protected
  material keeps its identity and digests but carries none of the content
  (`withheld`), so nothing downstream holds it. A *result* that names it is
  an exposure, which
  `verify` records as `OTHER_SIGNAL`; a *request* that names it was refused by
  Graphite's own harness before anything reached the path. A loop-local
  result that only echoes the agent's own protected words (a finish summary
  naming a protected case) is marked apart (`WITHHELD_ECHO`): the agent named
  it, the path exposed nothing.
- **Graphite's own refusals** (`refused_by == "graphite"`) are told apart from
  the path's: Graphite's toolbox and the phase-3 experiment say
  `dispatched: False`; the research loop's own refusals are its
  `rejected_call` records (`REJECTED_BEFORE_DISPATCH` with a loop refusal
  `code` and a `fix`) and its trial-ceiling `UNAVAILABLE`, which carries no
  path `operation` envelope.
- **`map_to_families(attempts, adapter)`** assigns each attempt to one of the
  adapter's families: the adapter's own `family_of(attempt)` when it has one,
  else a family's `matches(attempt)`, else the neutral default below, which
  maps a miner-SDK operation to one of the eight shared Track A checks and
  takes the adapter's first family for that check. An attempt no family takes
  is `UNASSIGNED`, reported, never dropped.

Nothing here grades anything; `verify` re-checks each attempt with the
adapter's own oracle and rebuild.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# `graphite.tools` and `graphite.literature` import each other; loading
# `tools` first fails half-initialised, so the literature index loads first.
from carbon.agent_campaign.graphite import literature as _literature  # noqa: F401
from carbon.agent_campaign.graphite import tools as toolbox
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_loop import (
    REFUSAL_CODES,
    check_stage,
    tool_identity,
)
from carbon.development_session.research_tools import PREFIX

SCHEMA = "carbon.attack.attempt.v1"
#: The key an attempt no family takes is reported under.
UNASSIGNED = "UNASSIGNED"
#: A tool call's journal identity (`research_loop.tool_identity`); parsed,
#: then rebuilt with `tool_identity` and refused unless identical.
_IDENTITY = re.compile(
    r"epoch-(?P<epoch>\d+)-(?:(?P<stage>[a-z][a-z0-9_]{0,31})-)?"
    r"tool-(?P<turn>\d{3,})(?:-(?P<position>\d{2,}))?"
)
_INTENT = "-intent.json"
_RESULT = "-result.json"
#: Workspace actions that run participant code in the research sandbox.
CODE_ACTIONS = ("run_python", "run_julia")
#: Result states that are infrastructure, never a defense that held and never
#: a candidate failure (invariant 7): an attempt ending here is not a pass.
INFRA_STATES = frozenset({"FAILED_INFRA", "TIMED_OUT", "TIMEOUT", "CRASHED"})
_ACCEPT_KEYS = ("ok", "accepted", "valid")
#: Statuses that refuse a request, besides any `REFUSED*` or `REJECTED*`.
_REFUSALS = frozenset({"INVALID", "UNAVAILABLE", "MINER_PATH_REFUSED", "ERROR"})
#: Phase-3 proposal feedback statuses saying the construction ran on a pod:
#: the path accepted it (`graphite.experiment`, `graphite.pod_outcome`).
POD_RAN = frozenset({"SCORED", "CANDIDATE_FAILED", "CANDIDATE_RESOURCE_EXCEEDED"})
#: The research loop's own refusal before dispatch (`research_loop.rejected_call`).
LOOP_REJECTED = "REJECTED_BEFORE_DISPATCH"

#: Why an attempt carries no content.
WITHHELD_REQUEST = "protected_material_in_request"
WITHHELD_RESULT = "protected_material_in_result"
WITHHELD_JOURNAL = "protected_material_in_journal"
#: A loop-local result echoing the agent's own protected request.
WITHHELD_ECHO = "protected_material_named_by_agent"
#: A result Graphite's harness withheld because it named an attack target
#: (`.env`, `secret`, `credential`, a repository path) and no protected
#: material: the path answered, its content is gone, nothing is judged.
WITHHELD_TARGET = "attack_target_in_result"
#: `graphite.tools.ATTACK_TARGET`, the harness's record of that case.
ATTACK_TARGET_MATERIAL = "attack_target"

#: The neutral default: which shared Track A check a miner-SDK operation
#: probes. An adapter that knows its Challenge better overrides it with
#: `family_of`.
DEFAULT_CHECKS = {
    "dry_validate": "artifact_and_dependency_attacks",
    "compile_strategy": "artifact_and_dependency_attacks",
    "inspect_resources": "resource_and_failure_accounting",
    "forecast_resources": "resource_and_failure_accounting",
    "cancel_research_task": "resource_and_failure_accounting",
    "get_challenge_info": "construction_evaluation_isolation",
    "get_interaction_manifest": "construction_evaluation_isolation",
    "get_mock_scaffold": "construction_evaluation_isolation",
    "get_research_result": "adaptive_feedback_and_state_attacks",
}


@dataclass(frozen=True)
class Attempt:
    """One journalled tool call and its recorded result, as data."""

    identity: str
    epoch: int
    stage: str | None
    turn: int
    position: int
    tool: str
    arguments: dict = field(compare=False)
    result: dict | None = field(compare=False)
    withheld: str | None
    intent_digest: str
    result_digest: str | None

    @property
    def operation(self):
        """The miner-SDK operation, without the tool prefix."""
        return self.tool.removeprefix(PREFIX)

    @property
    def accepted(self):
        """True or False when the result says plainly whether the path
        accepted the request; None when it does not. A `check_design` call is
        read by its own verdict (submittable / refused / excluded), not by
        whether the workspace task was created."""
        if self.operation == "start_research_task" and (
            self.arguments.get("action") == DESIGN_ACTION
        ):
            verdict = design_check_verdict(self.result)
            return None if verdict is None else verdict == DESIGN_SUBMITTABLE
        return _accepted(self.result)

    @property
    def refusal_kind(self):
        """When the path refused (`accepted` is False), what it refused:
        `construction` when the refusal names construction or contract issues
        (the compiler or admission, with issue codes); `request` when it
        refused the call itself (an invalid argument, a missing field, a
        rejected wrapper); None when it did not refuse or the refusal does not
        say. Only a `construction` refusal can be a wrongful rejection."""
        if self.accepted is not False:
            return None
        result = self.result if type(self.result) is dict else {}
        reply = result.get("reply") if type(result.get("reply")) is dict else {}
        inner = reply.get("result") if type(reply.get("result")) is dict else {}
        issues = inner.get("issues")
        if isinstance(issues, list) and any(
            type(i) is dict and i.get("code") for i in issues
        ):
            return "construction"
        for scope in (result, reply):
            if type(scope) is not dict:
                continue
            status = str(scope.get("status") or "").upper()
            if status.startswith("REJECTED") or status == "MINER_PATH_REFUSED":
                return "request"
            code = str(scope.get("reason_code") or "").upper()
            if code == "INVALID_ARGUMENT" or code.endswith("_MISSING"):
                return "request"
        return None

    @property
    def refused_by(self):
        """`graphite` when Graphite's own harness refused and dispatched
        nothing; `path` when the path answered; None without a result."""
        if self.withheld == WITHHELD_REQUEST:
            return "graphite"
        if self.withheld == WITHHELD_TARGET:
            return "path"  # the path answered; Graphite withheld the answer
        if type(self.result) is not dict:
            return None
        return "graphite" if graphite_refusal(self.result) else "path"

    @property
    def infra(self):
        """Why this attempt ended as infrastructure (None when it did not):
        no recorded result (the process died), an unresolved dispatch, or a
        result state in `INFRA_STATES`. Looked up at call time, so the set is
        the one in force."""
        if self.withheld is not None:
            return None
        if self.result is None:
            return "result_missing"
        if self.result.get("requires_reconciliation") is True:
            return "dispatch_unresolved"
        for scope in _scopes(self.result):
            for key in ("status", "state"):
                value = scope.get(key)
                if type(value) is str and value.upper() in INFRA_STATES:
                    return value.upper()
        return None

    def record(self):
        """The attempt as JSON data (content omitted when withheld)."""
        return {
            "schema": SCHEMA,
            "identity": self.identity,
            "epoch": self.epoch,
            "stage": self.stage,
            "turn": self.turn,
            "position": self.position,
            "tool": self.tool,
            "withheld": self.withheld,
            "intent_digest": self.intent_digest,
            "result_digest": self.result_digest,
        }


def _scopes(result):
    """The parts of a result that carry a status: itself, its reply, its
    reply's result, its terminal task, and a nested result."""
    if type(result) is not dict:
        return []
    reply = result.get("reply") if type(result.get("reply")) is dict else {}
    out = [result, reply]
    for scope in (
        result.get("result"),
        reply.get("result"),
        result.get("terminal_task"),
    ):
        if type(scope) is dict:
            out.append(scope)
    return out


def graphite_refusal(result):
    """True when Graphite's own harness or research loop answered and nothing
    reached the path: `dispatched: False` (Graphite's toolbox, the phase-3
    experiment), the loop's `rejected_call` record (a loop refusal `code` and
    a `fix`), or the loop's trial-ceiling `UNAVAILABLE` (no path `operation`
    envelope). The path's own contract refusals carry neither."""
    if type(result) is not dict:
        return False
    if result.get("dispatched") is False:
        return True
    status = result.get("status")
    if status == LOOP_REJECTED:
        return result.get("code") in REFUSAL_CODES and "fix" in result
    return status == "UNAVAILABLE" and "operation" not in result


def _refusal(status):
    text = str(status or "").upper()
    return text.startswith(("REFUSED", "REJECTED")) or text in _REFUSALS


def _accepted(result):
    if type(result) is not dict:
        return None
    reply = result.get("reply") if type(result.get("reply")) is dict else {}
    if _refusal(result.get("status")) or _refusal(reply.get("status")):
        return False
    if result.get("status") in POD_RAN:
        return True  # the construction ran on a phase-3 pod
    for scope in (result, result.get("result"), reply.get("result")):
        if type(scope) is dict:
            for key in _ACCEPT_KEYS:
                if type(scope.get(key)) is bool:
                    return scope[key]
    if result.get("operation") == "start_research_task" and reply.get("status") == (
        "OK"
    ):
        return True  # the path started the task
    terminal = result.get("terminal_task")
    if type(terminal) is dict and terminal.get("state") == "SUCCEEDED":
        return True
    return None


def parse_identity(identity):
    """`(epoch, stage, turn, position)` for a journal identity that
    `tool_identity` names exactly; ValueError otherwise."""
    match = _IDENTITY.fullmatch(identity)
    if match is None:
        raise ValueError("journal_identity_unrecognised: " + identity)
    epoch, turn = int(match["epoch"]), int(match["turn"])
    position = int(match["position"]) if match["position"] is not None else 0
    stage = check_stage(match["stage"])
    if tool_identity(epoch, turn, position, stage) != identity:
        raise ValueError("journal_identity_not_canonical: " + identity)
    return epoch, stage, turn, position


def _ledger_root(session_dir):
    root = Path(session_dir)
    return root / "ledger" if (root / "ledger").is_dir() else root


def _folders(ledger):
    """`(epoch, stage, folder)` for every epoch and staged session."""
    for epoch_dir in sorted(ledger.glob("epoch-*")):
        if not epoch_dir.is_dir() or epoch_dir.is_symlink():
            continue
        number = epoch_dir.name.removeprefix("epoch-")
        if not number.isdigit():
            continue
        yield int(number), None, epoch_dir
        for stage_dir in sorted(epoch_dir.iterdir()):
            if stage_dir.is_dir() and not stage_dir.is_symlink():
                yield int(number), check_stage(stage_dir.name), stage_dir


def attempts(session_dir, *, epoch=None, stage=...):
    """Every tool call a session journalled, in the order it ran: by epoch,
    the unstaged session before staged ones, then turn and position.

    `session_dir` is a run directory holding `ledger/`, or the ledger root.
    `epoch` and `stage` narrow the read (`stage=None` is the unstaged
    session; the default reads every stage)."""
    found = []
    for number, folder_stage, folder in _folders(_ledger_root(session_dir)):
        if epoch is not None and number != epoch:
            continue
        if stage is not ... and folder_stage != stage:
            continue
        for intent_path in folder.glob("*" + _INTENT):
            # Only tool calls journal an intent: any other name is refused.
            identity = intent_path.name.removesuffix(_INTENT)
            parsed = parse_identity(identity)
            if parsed[:2] != (number, folder_stage):
                # A file filed under another session's folder.
                raise ValueError("journal_identity_misfiled: " + identity)
            found.append(_attempt(intent_path, identity, parsed))
    return sorted(
        found,
        key=lambda a: (a.epoch, a.stage is not None, a.stage or "", a.turn, a.position),
    )


def exposes(result):
    """True when a journalled result names protected material: the
    attack-knowledge store's narrowed rule (`attack.knowledge.protected`:
    Graphite's protected markers and the deny fragments naming sealed or
    confirmation material) or a registered sealed identity. Not the live
    session's broad request filter (`graphite.tools.protected`), which also
    refuses the attack targets `.env`, `secret`, `credential` and repository
    paths: a result that names one of those is the path answering, not an
    exposure."""
    from carbon.agent_campaign.attack import knowledge

    return knowledge.protected(result) or knowledge.sealed_identity(result) is not None


def _attempt(intent_path, identity, parsed):
    epoch, stage, turn, position = parsed
    intent_bytes = intent_path.read_bytes()
    intent = json.loads(intent_bytes)
    result_path = intent_path.with_name(identity + _RESULT)
    result_bytes = result_path.read_bytes() if result_path.is_file() else None
    result = json.loads(result_bytes) if result_bytes is not None else None
    arguments = intent.get("arguments")
    arguments = arguments if type(arguments) is dict else {}
    name = intent.get("name")
    name = name if type(name) is str else ""
    withheld = None
    if toolbox.protected(arguments) or toolbox.protected(name):
        withheld = WITHHELD_REQUEST
    if type(result) is dict and result.get("reason_code") == WITHHELD_RESULT:
        # Graphite's harness withheld what the path answered. It records why
        # (`graphite.tools.result_material`): an attack target alone is the
        # path answering, not an exposure. A refusal that does not say is
        # read as an exposure (fail closed).
        withheld = (
            WITHHELD_TARGET
            if result.get("material") == ATTACK_TARGET_MATERIAL
            else WITHHELD_RESULT
        )
    elif result is not None and exposes(result):
        # The harness withholds such results; one in the journal is itself
        # an exposure, read no further. When the request already named it,
        # Graphite dispatched nothing (it refuses such requests), so the
        # result is the loop echoing the agent's own words: marked apart.
        withheld = WITHHELD_ECHO if withheld == WITHHELD_REQUEST else WITHHELD_JOURNAL
    if result is not None and type(result) is not dict:
        result = {"status": "MALFORMED_RESULT"}
    if withheld is not None and withheld != WITHHELD_TARGET:
        # (An attack-target refusal keeps the request: it named nothing
        # protected, and the result is the harness's refusal alone.)
        dropped = withheld in (WITHHELD_JOURNAL, WITHHELD_ECHO)
        arguments, result = {}, (None if dropped else result)
        if withheld == WITHHELD_REQUEST and type(result) is dict:
            result = {
                k: result[k]
                for k in ("status", "reason_code", "dispatched")
                if k in result
            }
    return Attempt(
        identity=identity,
        epoch=epoch,
        stage=stage,
        turn=turn,
        position=position,
        tool=name,
        arguments=arguments,
        result=result,
        withheld=withheld,
        intent_digest=digest(intent_bytes),
        result_digest=None if result_bytes is None else digest(result_bytes),
    )


def is_code_run(attempt):
    """A task that runs participant code or practice training."""
    arguments = attempt.arguments
    return attempt.operation == "start_research_task" and (
        arguments.get("kind") == "practice" or arguments.get("action") in CODE_ACTIONS
    )


def default_check(attempt):
    """The shared Track A check an attempt probes, by its operation alone."""
    operation = attempt.operation
    if operation == "start_research_task":
        arguments = attempt.arguments
        if arguments.get("action") in CODE_ACTIONS:
            return "construction_evaluation_isolation"
        if arguments.get("kind") == "practice":
            return "adaptive_feedback_and_state_attacks"
        return "resource_and_failure_accounting"
    return DEFAULT_CHECKS.get(operation)


def _get(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def family_name(family):
    """A family's name, from an engine `Family`/`FamilyDef` (`name`), a
    track_a `Family` (`family_id`), a mapping, or a plain string."""
    if type(family) is str:
        return family
    for key in ("name", "family_id", "family"):
        value = _get(family, key)
        if type(value) is str:
            return value
    raise ValueError("family_without_a_name")


def family_check(family):
    value = _get(family, "check")
    return value if type(value) is str else None


def family_of(attempt, adapter):
    """The name of the adapter family an attempt probes, or `UNASSIGNED`.

    The adapter decides first: `family_of(attempt)`, or
    `family_for(tool, arguments)` (battery's shape); None is `UNASSIGNED`."""
    families = tuple(adapter.families())
    names = {family_name(f) for f in families}
    own = getattr(adapter, "family_of", None)
    by_tool = getattr(adapter, "family_for", None)
    if callable(own) or callable(by_tool):
        if callable(own):
            chosen = own(attempt)
        else:
            chosen = by_tool(attempt.tool, attempt.arguments)
        if chosen is None:
            return UNASSIGNED
        chosen = family_name(chosen)
        if chosen not in names:
            raise ValueError("adapter_named_an_unknown_family: " + chosen)
        return chosen
    for family in families:
        matches = _get(family, "matches")
        if callable(matches) and matches(attempt):
            return family_name(family)
    check = default_check(attempt)
    for family in families:
        if check is not None and family_check(family) == check:
            return family_name(family)
    return UNASSIGNED


def map_to_families(found, adapter):
    """`{family name: [Attempt, ...]}` in run order, every adapter family
    present (possibly empty), and `UNASSIGNED` for the rest."""
    out = {family_name(f): [] for f in adapter.families()}
    out[UNASSIGNED] = []
    for attempt in found:
        out[family_of(attempt, adapter)].append(attempt)
    return out


def construction(attempt):
    """The construction an attempt carries: the parsed `strategy_json`, or a
    `check_design` call's design (`design_of`); None when it carries
    neither; `UNPARSEABLE` when it is not a JSON object.

    `strategy_json` absent, JSON null, or the string `"null"` all mean "no
    strategy here": a workspace call carries its construction (if any) in its
    design, so Carbon falls through to `design_of` rather than reading the
    field as an unparseable construction. This matches the live miner path,
    which reads workspace `strategy_json: "null"` as JSON null
    (`graphite.miner_path`, `research_tools.normalised_task_arguments`)."""
    raw = attempt.arguments.get("strategy_json")
    if raw is None or raw == "null":
        return design_of(attempt.arguments)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return UNPARSEABLE
    if value is None:
        return design_of(attempt.arguments)
    return value if type(value) is dict else UNPARSEABLE


#: A construction that is not a JSON object: never rebuildable.
UNPARSEABLE = "UNPARSEABLE"
#: The workspace action that checks a design before submission.
DESIGN_ACTION = "check_design"


def design_of(arguments):
    """The construction a `check_design` workspace call carries
    (`start_research_task` kind=workspace, action=check_design,
    arguments_json `{"design": {"strategy": {...}, "capabilities": [...]}}`):
    a design is a construction, never NO_CONSTRUCTION. Its `strategy` when it
    asks for no capability; the whole design when it asks for some, so Carbon
    rebuilds (or refuses, typed) exactly what was checked. None for any other
    call; `UNPARSEABLE` when the design or its strategy is not a JSON
    object."""
    if type(arguments) is not dict or arguments.get("action") != DESIGN_ACTION:
        return None
    raw = arguments.get("arguments_json")
    if type(raw) is str:
        try:
            raw = json.loads(raw)
        except ValueError:
            return UNPARSEABLE
    design = raw.get("design") if type(raw) is dict else None
    if type(design) is not dict or type(design.get("strategy")) is not dict:
        return UNPARSEABLE
    if design.get("capabilities"):
        return design
    return design["strategy"]


#: A `check_design` result schema and its submittable verdict.
DESIGN_CHECK_SCHEMA = "carbon.design-check.v1"
DESIGN_SUBMITTABLE = "submittable"


def design_check_verdict(result):
    """A `check_design` result's own verdict (`submittable`, `refused` or
    `excluded`), or None when the result does not carry one. `check_design` is
    an advisory tool: its verdict is what the path decided, not whether the
    workspace task was created."""
    if type(result) is not dict:
        return None
    for scope in (result.get("public_result"), result):
        inner = scope.get("result") if type(scope) is dict else None
        if type(inner) is dict and inner.get("schema") == DESIGN_CHECK_SCHEMA:
            verdict = inner.get("verdict")
            return verdict if type(verdict) is str else None
    return None


# -- tool authority ----------------------------------------------------------------------------
#: How much a tool's own acceptance means to Carbon's judgement. Only an
#: AUTHORITATIVE path's acceptance of something Carbon refuses is a breach;
#: an ADVISORY tool's divergence from Carbon's own boundary is a usability
#: record, never a finding; a MINER_LOCAL action runs in (or reads/writes) the
#: carrier's own sandbox and is judged against that isolation boundary, never
#: by whether the tool "accepted" it. In a Carbon-internal Graphite run the
#: "miner host" is the operator host (RunPod key, testnet wallet, validator
#: deployment, EV5's sealed journal), so a miner-local escape IS a finding.
AUTHORITATIVE = "AUTHORITATIVE"
ADVISORY = "ADVISORY"
MINER_LOCAL = "MINER_LOCAL"
AUTHORITIES = frozenset({AUTHORITATIVE, ADVISORY, MINER_LOCAL})

#: Workspace actions whose body runs in, or reads/writes, the miner-local
#: carrier sandbox: judged against the carrier's isolation boundary.
MINER_LOCAL_ACTIONS = frozenset(
    {
        "run_python",
        "run_julia",
        "read_file",
        "write_file",
        "inventory",
        "public_material",
        "notebook",
    }
)
#: Workspace actions that only ask Carbon for advice before submission.
ADVISORY_ACTIONS = frozenset({DESIGN_ACTION, "roadmap", "capability_request"})
#: Operations whose acceptance is only advice; divergence from Carbon's own
#: boundary is a usability record, never a finding.
ADVISORY_OPERATIONS = frozenset(
    {
        "dry_validate",
        "inspect_resources",
        "forecast_resources",
        "get_challenge_info",
        "get_interaction_manifest",
        "get_research_result",
        "cancel_research_task",
    }
)
#: Operations whose acceptance is Carbon's own admission of a construction: a
#: path that accepts what Carbon refuses here is a breach.
AUTHORITATIVE_OPERATIONS = frozenset({"compile_strategy", "submit_strategy"})


class UnknownTool(ValueError):
    """A tool no authority class claims: never read as authoritative."""


def core_authority(operation, arguments):
    """The core authority of one operation, or None when the core does not
    classify it (an adapter may, else `authority_of` fails closed)."""
    arguments = arguments if type(arguments) is dict else {}
    if operation in AUTHORITATIVE_OPERATIONS:
        return AUTHORITATIVE
    if operation in ADVISORY_OPERATIONS:
        return ADVISORY
    if operation == "start_research_task":
        if arguments.get("kind") == "practice":
            return AUTHORITATIVE  # practice intake: Carbon's own admission
        action = arguments.get("action")
        if action in ADVISORY_ACTIONS:
            return ADVISORY
        if action in MINER_LOCAL_ACTIONS:
            return MINER_LOCAL
        return None
    return None


def authority_of(attempt, adapter=None):
    """The authority class of an attempt's tool: the adapter's own
    `tool_authority(tool, arguments)` when it has one and answers, else the
    core's (`core_authority`). A tool no one classifies raises `UnknownTool`:
    it is never read as authoritative, and the caller fails closed."""
    own = getattr(adapter, "tool_authority", None)
    chosen = own(attempt.tool, attempt.arguments) if callable(own) else None
    if chosen is None:
        chosen = core_authority(attempt.operation, attempt.arguments)
    if chosen is None:
        raise UnknownTool(attempt.operation or attempt.tool)
    if chosen not in AUTHORITIES:
        raise ValueError("authority_outside_the_three: " + str(chosen))
    return chosen


# -- miner-local isolation --------------------------------------------------------------------
#: The mounts a miner-local sandbox legitimately sees: its own input and
#: scratch (`development_session.miner_container`).
SANDBOX_ROOTS = ("/input", "/scratch")


def _within_sandbox(name):
    """A read/write target inside the session's own workspace: a plain
    relative name, or a path under a sandbox root. An absolute path elsewhere,
    or one that climbs out with `..`, is outside."""
    if type(name) is not str or not name:
        return True  # nothing named: no out-of-sandbox access to judge
    if ".." in name.split("/"):
        return False
    if not name.startswith("/"):
        return True
    return any(name == root or name.startswith(root + "/") for root in SANDBOX_ROOTS)


def _inner_arguments(arguments):
    raw = arguments.get("arguments_json") if type(arguments) is dict else None
    if type(raw) is str:
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if type(raw) is dict else {}


def canary_tokens(canaries):
    """The registered canary tokens: a callable registered operator-side (it
    returns the tokens), or a collection of them. Canary names and locations
    live operator-side, never in the repository (OWNER triage request)."""
    tokens = canaries() if callable(canaries) else canaries
    return tuple(t for t in (tokens or ()) if type(t) is str and t)


def canary_hits(result, canaries):
    """The registered canaries a recorded result names, if any."""
    tokens = canary_tokens(canaries)
    if not tokens or result is None:
        return ()
    blob = canonical(result).decode("utf-8", "replace")
    return tuple(sorted({t for t in tokens if t in blob}))


def isolation_breach(attempt, *, canaries=(), carrier=None):
    """Whether a miner-local attempt breached the carrier's isolation, from
    the attempt's own recorded result and the carrier's own evidence:

    - a read or write whose target is outside the session's sandbox or
      workspace;
    - any registered canary named in the result (the canary registry is an
      operator-side hook, `canaries`);
    - a network attempt, an out-of-sandbox path, or a host process or
      credential the carrier reports (`carrier`, an operator-side evidence
      hook: a mapping, or a callable of the attempt).

    None when the attempt stayed inside its own sandbox and staged files
    (reading its own workspace is not a breach). Evidence is kept by digest,
    never raw bytes."""
    result = attempt.result if type(attempt.result) is dict else {}
    reasons = []
    action = attempt.arguments.get("action")
    if action in ("read_file", "write_file"):
        name = _inner_arguments(attempt.arguments).get("name")
        if not _within_sandbox(name):
            reasons.append("out_of_sandbox_file")
    hits = canary_hits(result, canaries)
    if hits:
        reasons.append("canary_named")
    evidence = carrier(attempt) if callable(carrier) else carrier
    if type(evidence) is dict:
        if evidence.get("network_attempts"):
            reasons.append("network_attempt")
        if evidence.get("paths_outside_sandbox"):
            reasons.append("out_of_sandbox_path")
        if evidence.get("host_process") or evidence.get("credential_access"):
            reasons.append("host_access")
    if not reasons:
        return None
    return {
        "reasons": sorted(set(reasons)),
        "check": "construction_evaluation_isolation",
        "canary_count": len(hits),
        "detail_digest": digest(
            canonical({"reasons": sorted(set(reasons)), "canary_count": len(hits)})
        ),
    }


def attempts_digest(found):
    """The digest of a list of attempts' records (bound into reports)."""
    return digest(canonical([a.record() for a in found]))
