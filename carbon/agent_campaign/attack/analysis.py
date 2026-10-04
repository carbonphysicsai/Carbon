"""Carbon's reading of an attack session: its recorded tool calls, as attempts.

Challenge-neutral (OWNER-GRAPHITE-ATTACKER-01 §1). Carbon decides from what a
session's research loop journalled, never from the model's prose:

- **`attempts(session_dir)`** reads every tool call and its recorded result
  from the research loop's journal (`ledger/epoch-N[/<stage>]/`). Each
  journal identity must be exactly what `research_loop.tool_identity(epoch,
  turn, position, stage)` names, so v2 turns with several calls (`-KK`) and
  staged sessions read one way; anything else is refused, never guessed.
- **Protected material** (`graphite.tools.protected`) is checked on every
  read. An attempt whose request or result names protected material keeps its
  identity and digests but carries none of the content (`withheld`), so
  nothing downstream holds it. A *result* that names it is an exposure, which
  `verify` records as `OTHER_SIGNAL`; a *request* that names it was refused by
  Graphite's own harness before anything reached the path.
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
from carbon.development_session.research_loop import check_stage, tool_identity
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

#: Why an attempt carries no content.
WITHHELD_REQUEST = "protected_material_in_request"
WITHHELD_RESULT = "protected_material_in_result"
WITHHELD_JOURNAL = "protected_material_in_journal"

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
        accepted the request; None when it does not."""
        return _accepted(self.result)

    @property
    def refused_by(self):
        """`graphite` when Graphite's own harness refused and dispatched
        nothing; `path` when the path answered; None without a result."""
        if self.withheld == WITHHELD_REQUEST:
            return "graphite"
        if type(self.result) is not dict:
            return None
        return "graphite" if self.result.get("dispatched") is False else "path"

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


def _refusal(status):
    text = str(status or "").upper()
    return text.startswith(("REFUSED", "REJECTED")) or text in _REFUSALS


def _accepted(result):
    if type(result) is not dict:
        return None
    reply = result.get("reply") if type(result.get("reply")) is dict else {}
    if _refusal(result.get("status")) or _refusal(reply.get("status")):
        return False
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
        withheld = WITHHELD_RESULT
    elif result is not None and toolbox.protected(result):
        # The harness withholds such results; one in the journal is itself
        # an exposure, read no further.
        withheld = WITHHELD_JOURNAL
    if result is not None and type(result) is not dict:
        result = {"status": "MALFORMED_RESULT"}
    if withheld is not None:
        arguments, result = {}, (None if withheld == WITHHELD_JOURNAL else result)
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
    """The name of the adapter family an attempt probes, or `UNASSIGNED`."""
    families = tuple(adapter.families())
    names = {family_name(f) for f in families}
    own = getattr(adapter, "family_of", None)
    if callable(own):
        chosen = own(attempt)
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
    """The construction an attempt carries: the parsed `strategy_json`;
    None when it carries none; `UNPARSEABLE` when it is not a JSON object."""
    raw = attempt.arguments.get("strategy_json")
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return UNPARSEABLE
    return value if type(value) is dict else UNPARSEABLE


#: A construction that is not a JSON object: never rebuildable.
UNPARSEABLE = "UNPARSEABLE"


def attempts_digest(found):
    """The digest of a list of attempts' records (bound into reports)."""
    return digest(canonical([a.record() for a in found]))
