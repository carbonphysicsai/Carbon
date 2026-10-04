"""Finite, durable model-backed research epoch; no numerical or chain shortcuts.

The selected recipe is frozen here. A separate trusted controller performs the
registered authenticated final submission. Selection is not final evidence.

A model's own mistakes - arguments that are not a JSON object, a malformed
selection, a recipe Carbon cannot rebuild, a tool call with no identity - are
answered, never raised. A provider reply is journalled under a fixed identity
and replayed on every resume, so an exception raised on it would stop the
epoch again on every resume. A malformed call gets a typed
REJECTED_BEFORE_DISPATCH result naming the field and the fix, and the epoch
goes on; a call with no identity cannot be answered, so the epoch stops with a
typed STOPPED outcome.

A reply the provider ended early - cut off at its output limit, paused, or
refused - is a turn like any other (LP-PROD-A): it spent one model call and is
metered exactly. The tool calls it finished run; one it did not finish is
answered `call_truncated` without running; and a journalled note tells the
model how its reply ended and to continue, more concisely when it hit the
limit. A second such reply in a row in which no tool call was complete stops
the epoch typed (`replies_truncated`), so a model that is always cut off does
not spend the epoch's model calls for nothing. A provider failure is the
provider layer's (`research_agent`): it propagates, the epoch keeps no
outcome, and a resume carries on from the same turn.

New sessions may freeze four versioned additions (OWNER-GRAPHITE-MINER-01);
each defaults to None, which reproduces every earlier plan, prompt, identity
and journal byte for byte:

* a `stage` namespaces a session inside its epoch (`epoch-N/<stage>/`,
  identities `epoch-N-<stage>-...`), so several sessions share one epoch;
* a `finish` tool is a caller's own local terminal tool, computed before its
  intent like the selection;
* `limits` (`LIMITS_V2`) makes the per-epoch call and trial caps optional:
  money and time, the ledger's ceilings, bind;
* `compaction` (`COMPACTION_V1`) replaces the stop at the context ceiling
  with an explicit, journalled compaction call.

The Graphite miner policy (`GRAPHITE_MINER`) runs a role's own instructions
and tools with a Challenge under the rules Carbon's autonomous agent has.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import re

from carbon.reconstruction.capability_registry import contract_digest

from . import miner_guidance as guidance
from .data import write_once
from .model_provider import DEFAULT_SELECTION
from .profile import CHALLENGE, canonical, digest
from .research_agent import (
    CONTEXT_RESERVE_TOKENS,
    caching_status,
    incomplete_reply,
    input_token_bound,
    provider_turns,
    request_model,
)
from .research_agent_policy import (
    AUTONOMOUS,
    COMPACT,
    COMPACTION_ATTEMPTS,
    COMPACTION_BYTES_PER_CHARACTER,
    COMPACTION_FIELDS,
    COMPACTION_HEADROOM_TOKENS,
    COMPACTION_MIN_SUMMARY_CHARACTERS,
    COMPACTION_SUMMARY_CHARACTERS,
    COMPACTION_TOOL,
    FINISH_NOTICE_CALLS,
    GRAPHITE_MINER,
    LEGACY,
    MAX_PROVIDER_CALLS,
    MAX_RESEARCH_TRIALS,
    MAX_TOOL_ARGUMENT_BYTES,
    PARALLEL_CALLS_V2,
    PARALLEL_REFUSAL,
    REMINDER,
    STOP,
    STOP_TOOL,
    binding,
    check_compaction,
    check_limits,
    check_parallel_rule,
    graphite_miner_binding,
    graphite_miner_prompt,
    graphite_miner_reminder,
    prompt_for,
    stop_result,
)
from .research_catalog import compile_recipe
from .research_guidance import effective_digest
from .research_tools import PREFIX, _json, _schema, tools_for_sdk

SELECT = "carbon_autoresearch_select_recipe"
SELECTION_TOOL = {
    "type": "function",
    "name": SELECT,
    "strict": True,
    "description": "Freeze the best eligible recipe using only research information and finish this epoch. This selects a candidate; the trusted controller separately submits it for independent reconstruction. Explain evidence, limitations, and why another trial is not useful.",
    "parameters": _schema(
        {
            "strategy_json": {"type": "string"},
            "reason": {"type": "string"},
            "used_feedback": {"type": "boolean"},
        }
    ),
}


class CandidateChallengeRequired(ValueError):
    """A candidate must name its Challenge; none is assumed for it."""


def candidate_record(strategy, reason, used_feedback):
    """The frozen-candidate record, whoever freezes it: the agent's SELECT tool
    or a miner's own freeze. One builder, so the two cannot differ in shape.

    The recipe's own `challenge_id` chooses the contract it compiles under. A
    recipe that names none is refused rather than compiled as Burgers."""
    if type(reason) is not str or not 1 <= len(reason) <= 4096:
        raise ValueError("a bounded selection reason is required")
    if type(used_feedback) is not bool:
        raise ValueError("used_feedback is a Boolean")
    if (
        type(strategy) is not dict
        or type(strategy.get("challenge_id")) is not str
        or not strategy["challenge_id"]
    ):
        raise CandidateChallengeRequired(
            "a candidate recipe must name its challenge_id"
        )
    if strategy["challenge_id"] != CHALLENGE.challenge_id:
        # Another Challenge compiles under its own contract, never Burgers'.
        from carbon.reconstruction.challenge_contracts import compile_submission

        admitted = compile_submission(strategy)
        compiled, rebuilt = admitted.compiled, admitted.construction.recipe_digest
    else:
        compiled, profile = compile_recipe(strategy)
        rebuilt = profile.profile_digest
    return {
        "status": "SELECTED",
        "strategy": strategy,
        "reason": reason,
        "used_feedback": used_feedback,
        "strategy_hash": compiled.construction_plan.strategy_hash.value,
        "construction_plan_digest": compiled.construction_plan.to_ref().content_digest,
        "reconstruction_profile_digest": rebuilt,
        # The Challenge contract this candidate was compiled under (OD-8); a
        # validator refuses a submission recorded against a different one.
        "contract_digest": contract_digest(strategy["challenge_id"]),
        "final_evidence": False,
    }


#: Integrity metadata a task result repeats: the retained result file keeps
#: it; a Challenge campaign's model sees each result without it.
MODEL_VIEW_OMITS = frozenset({"immutable_bindings", "terminal_receipt"})


def model_view(result):
    """A tool result as a Challenge campaign's model sees it.

    The full result is retained unchanged in the epoch's result file. The
    model's copy drops only the receipt and binding metadata listed in
    `MODEL_VIEW_OMITS`, which task replies repeat several times and which
    would otherwise exhaust the fixed request ceiling within a few calls. The
    historical Burgers campaign is unchanged.
    """
    if type(result) is dict:
        return {
            key: model_view(value)
            for key, value in result.items()
            if key not in MODEL_VIEW_OMITS
        }
    if type(result) is list:
        return [model_view(value) for value in result]
    return result


#: Workspace actions that start a numerical task and spend a research-trial
#: slot, as practice does. `research_tools.ResearchMinerTools.call` charges
#: both; the loop's per-epoch ceiling counts both (LP-PROD-A).
NUMERICAL_ACTIONS = ("run_python", "run_julia")

#: The loop's own refusal codes for a model's malformed call. Each comes back
#: as a REJECTED_BEFORE_DISPATCH tool result naming the field and the fix:
#: - `arguments_invalid`: the call's arguments are not one bounded JSON
#:   object (not JSON, a duplicate key, NaN or Infinity, over
#:   `MAX_TOOL_ARGUMENT_BYTES`, or not an object);
#: - `selection_invalid`: the selection's own fields are missing, extra or of
#:   the wrong type;
#: - `candidate_invalid`: the selected recipe does not parse, names no
#:   Challenge, or does not compile;
#: - `selection_not_practiced`: under `PARALLEL_CALLS_V2`, Carbon's own agent
#:   selected a recipe with no completed practice; the reply lists the
#:   recipes that have one;
#: - `call_truncated`: the provider ended the reply before this call was
#:   complete (`cut_calls`), so it did not run;
#: - `finish_invalid`: a caller's finish tool refused the call without a
#:   refusal of its own;
#: - `compaction_not_requested`: the compaction tool was called when Carbon
#:   had not asked for a compaction.
ARGUMENTS_INVALID = "arguments_invalid"
SELECTION_INVALID = "selection_invalid"
CANDIDATE_INVALID = "candidate_invalid"
SELECTION_NOT_PRACTICED = "selection_not_practiced"
CALL_TRUNCATED = "call_truncated"
FINISH_INVALID = "finish_invalid"
COMPACTION_NOT_REQUESTED = "compaction_not_requested"
REFUSAL_CODES = (
    ARGUMENTS_INVALID,
    SELECTION_INVALID,
    CANDIDATE_INVALID,
    SELECTION_NOT_PRACTICED,
    CALL_TRUNCATED,
    FINISH_INVALID,
    COMPACTION_NOT_REQUESTED,
)
#: The typed outcome of a turn whose tool call has no call_id or name: it
#: cannot be answered, so the epoch stops, retained.
TOOL_CALL_MALFORMED = "tool_call_malformed"
#: The typed outcome of replies the provider ended early, in a row, in which
#: no tool call was complete (LP-PROD-A): the first is answered with a note
#: (`truncation_note`); at `MAX_TRUNCATED_TURNS` the epoch stops, retained,
#: so a model or provider that is always cut off cannot spend every model
#: call of the epoch for nothing.
REPLIES_TRUNCATED = "replies_truncated"
MAX_TRUNCATED_TURNS = 2
#: At most this many practiced recipes are listed in a
#: `selection_not_practiced` reply, newest last; the reply also gives the
#: count.
LISTED_PRACTICED_RECIPES = 8
_SELECTION_FIELDS = ("strategy_json", "reason", "used_feedback")
#: The typed outcomes of a session under `COMPACTION_V1`: no valid summary
#: was recorded after `COMPACTION_ATTEMPTS` requests, or a request could not
#: be admitted under the context ceiling even with compaction. Retained,
#: never raised; nothing was dropped.
COMPACTION_FAILED = "compaction_failed"
CONTEXT_CEILING = "context_ceiling"


class CeilingReached(ValueError):
    """A ledger's typed refusal to admit a session's next model call, raised
    from its `reserve` (for example the miner edition's stage ledger, whose
    reserve refuses past a stage's share of the campaign budget). The session
    ends STOPPED with `code`, before anything of that call was reserved; the
    campaign itself goes on. Nothing raised it before OWNER-GRAPHITE-MINER-01,
    so no earlier session reads differently.

    `code` is a closed snake_case code (`research_share_reached`); `dimension`
    names the ledger dimension that bound, when one did.

    It is raised only from the reservation of a model call, one that reserves
    provider_attempts or provider_nanodollars. The loop turns it into a typed
    stop around its own model calls; a tool's own reservation (a research
    trial) is the tool's to refuse, and this raised from inside a tool
    dispatch, after the call's intent is journalled, would leave that
    dispatch for reconciliation like any other exception there."""

    def __init__(self, code, *, dimension=None):
        if type(code) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code):
            raise ValueError("a ceiling code is a closed snake_case code")
        if dimension is not None and (
            type(dimension) is not str or not re.fullmatch(r"[a-z_]{1,64}", dimension)
        ):
            raise ValueError("a ceiling dimension is a ledger dimension name")
        super().__init__(code)
        self.code, self.dimension = code, dimension

    def outcome(self):
        return {
            "status": "STOPPED",
            "code": self.code,
            "reason": (
                "the ledger refused the next model call: "
                + self.code
                + "; nothing of it was reserved or sent"
            ),
            "dimension": self.dimension,
        }


def rejected_call(code, field, reason, fix, **extra):
    """A model's malformed call, answered: nothing ran and nothing was spent."""
    if code not in REFUSAL_CODES:
        raise ValueError("unknown loop refusal code")
    return {
        "status": "REJECTED_BEFORE_DISPATCH",
        "code": code,
        "field": field,
        "reason": reason,
        "fix": fix,
        "detail": (
            "Nothing ran and no research-trial slot was spent. Correct the call "
            "and send it again."
        ),
        "authority_granted": False,
        **extra,
    }


def _kind(value):
    return {
        list: "array",
        str: "string",
        int: "number",
        float: "number",
        bool: "Boolean",
    }.get(type(value), "null")


def argument_problem(raw, field="arguments"):
    """What is wrong with `raw`, JSON text `research_tools._json` refused, as
    (reason, fix). It only diagnoses: a value the loop accepts is always
    `_json`'s own, so an intent journalled before this existed replays
    unchanged. Model text is never echoed back beyond one key name."""
    if type(raw) is not str:
        return (
            f"{field} must be one JSON object encoded as a string",
            f'send {field} as a string holding a JSON object, for example "{{}}"',
        )
    try:
        size = len(raw.encode())
    except UnicodeError:
        return (f"{field} is not valid UTF-8 text", "send plain UTF-8 JSON text")
    if size > MAX_TOOL_ARGUMENT_BYTES:
        return (
            (
                f"{field} is {size} bytes; the limit is {MAX_TOOL_ARGUMENT_BYTES} "
                "bytes of JSON"
            ),
            f"shorten {field} to at most {MAX_TOOL_ARGUMENT_BYTES} bytes",
        )
    duplicates, constants = [], []

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                duplicates.append(key)
            value[key] = item
        return value

    try:
        value = json.loads(
            raw, object_pairs_hook=pairs, parse_constant=constants.append
        )
    except RecursionError:
        return (f"{field} is nested too deeply to read", "send a flatter JSON object")
    except json.JSONDecodeError as error:
        return (
            (
                f"{field} is not valid JSON ({error.msg} at line {error.lineno} "
                f"column {error.colno})"
            ),
            "send one JSON object, every string quoted, with nothing after it",
        )
    if duplicates:
        return (
            (
                f"{field} names the key {json.dumps(duplicates[0][:64])} more "
                "than once in one object"
            ),
            "send each key once",
        )
    if constants:
        return (
            f"{field} holds {constants[0]}, which is not a JSON number",
            "send a finite number, or null",
        )
    if type(value) is not dict:
        return (
            f"{field} is a JSON {_kind(value)}, not an object",
            "send one JSON object, for example {}",
        )
    return (f"{field} was refused", "send one JSON object")


def _takes_no_arguments(schema):
    parameters = schema.get("parameters")
    return type(parameters) is dict and not parameters.get("properties")


def tool_arguments(call, schemas):
    """A call's arguments as (value, None), or (None, rejection).

    The value is `research_tools._json`'s own, unchanged. A tool whose schema
    takes no arguments also takes no arguments at all, "" or JSON null as {}:
    models send all three for an empty call."""
    raw = call.get("arguments")
    schema = schemas.get(call["name"])
    empty = raw is None or (type(raw) is str and raw.strip() in ("", "null"))
    if empty and schema is not None and _takes_no_arguments(schema):
        return {}, None
    try:
        return _json(raw), None
    except (ValueError, RecursionError):
        reason, fix = argument_problem(raw)
        return None, rejected_call(ARGUMENTS_INVALID, "arguments", reason, fix)


def selection_result(arguments, *, check=None):
    """The selection tool's result, computed before anything is journalled:
    the frozen-candidate record, or a typed rejection naming the field.

    `check`, when given, is a last refusal over the parsed recipe (the v2
    practice requirement, `practice_check`); it returns None to accept."""
    missing = [name for name in _SELECTION_FIELDS if name not in arguments]
    if missing:
        return rejected_call(
            SELECTION_INVALID,
            missing[0],
            f"{missing[0]} is required",
            "send strategy_json, reason and used_feedback",
        )
    extra = sorted(name for name in arguments if name not in _SELECTION_FIELDS)
    if extra:
        return rejected_call(
            SELECTION_INVALID,
            extra[0][:64],
            "a selection takes strategy_json, reason and used_feedback only",
            "send only those three fields",
        )
    if type(arguments["used_feedback"]) is not bool:
        return rejected_call(
            SELECTION_INVALID,
            "used_feedback",
            "used_feedback must be true or false",
            "send a JSON Boolean, unquoted",
        )
    reason = arguments["reason"]
    if type(reason) is not str or not 1 <= len(reason) <= 4096:
        return rejected_call(
            SELECTION_INVALID,
            "reason",
            "reason must be text of 1 to 4096 characters",
            "explain the evidence in at most 4096 characters",
        )
    try:
        strategy = _json(arguments["strategy_json"])
    except (ValueError, RecursionError):
        problem, fix = argument_problem(arguments["strategy_json"], "strategy_json")
        return rejected_call(CANDIDATE_INVALID, "strategy_json", problem, fix)
    try:
        record = candidate_record(strategy, reason, arguments["used_feedback"])
    except CandidateChallengeRequired:
        return rejected_call(
            CANDIDATE_INVALID,
            "strategy_json",
            "the recipe names no challenge_id",
            "name the Challenge's challenge_id in the recipe",
        )
    except (ValueError, TypeError, KeyError) as error:
        rejected = getattr(error, "rejected", None)
        issues = getattr(rejected, "issues", None) or getattr(error, "issues", ())
        return rejected_call(
            CANDIDATE_INVALID,
            "strategy_json",
            "Carbon cannot rebuild this recipe: "
            + (
                str(error)[:300]
                if isinstance(error, ValueError)
                else "it does not have a recipe's structure"
            ),
            "check it with check_design or dry_validate, which name every issue, "
            "then select a recipe Carbon can rebuild",
            issues=[{"code": i.code, "path": i.path} for i in issues],
        )
    refusal = None if check is None else check(strategy)
    return record if refusal is None else refusal


def _has_practice_results(ledger):
    with ledger.db() as db:
        return (
            db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='research_results'"
            ).fetchone()
            is not None
        )


def practiced_recipes(ledger, owner):
    """The distinct recipes with a completed practice in this campaign,
    oldest first, by the provenances the trusted controller accepts
    (`research_campaign.PRACTICE_PROVENANCES`)."""
    from .research_campaign import PRACTICE_PROVENANCES

    if not _has_practice_results(ledger):
        return []
    with ledger.db() as db:
        rows = db.execute(
            "SELECT body,digest FROM research_results WHERE owner=? ORDER BY rowid",
            (owner,),
        ).fetchall()
    recipes = []
    for body, fingerprint in rows:
        if digest(body) != fingerprint:
            raise ValueError("retained practice result changed")
        result = json.loads(body)
        recipe = result.get("recipe")
        if (
            result.get("provenance") in PRACTICE_PROVENANCES
            and type(recipe) is dict
            and recipe not in recipes
        ):
            recipes.append(recipe)
    return recipes


def practice_check(ledger, owner):
    """The v2 selection rule for Carbon's own agent (LP-PROD-A): a recipe with
    no completed practice is refused here, by the same predicate the trusted
    controller applies before it submits one
    (`research_campaign.trial_supports_selection`), so the agent learns it
    while it can still practise or choose another, instead of after the epoch
    is spent."""

    def check(strategy):
        from .research_campaign import trial_supports_selection

        if _has_practice_results(ledger) and trial_supports_selection(
            ledger, owner, strategy
        ):
            return None
        recipes = practiced_recipes(ledger, owner)
        return rejected_call(
            SELECTION_NOT_PRACTICED,
            "strategy_json",
            "this recipe has no completed practice in this campaign; only a "
            "practiced recipe, exactly as practiced, can be selected",
            "select one of practiced_recipes as it is listed, practise this "
            "recipe first, or stop",
            practiced_recipes=recipes[-LISTED_PRACTICED_RECIPES:],
            practiced_recipe_count=len(recipes),
        )

    return check


#: A stage name: short, lowercase, no hyphen, so an identity parses one way.
#: `provider`, `tool` and `compact` name identity kinds, never a stage.
_STAGE = re.compile(r"[a-z][a-z0-9_]{0,31}")
RESERVED_STAGES = frozenset({"provider", "tool", "compact"})
#: A turn of a staged session; an unstaged turn is `epoch-N-provider-NNN` or
#: `epoch-N-compact-NNN` and never matches.
_STAGED_TURN = re.compile(
    r"epoch-\d+-(?!provider-|tool-|compact-)[a-z][a-z0-9_]{0,31}-"
)


def check_stage(stage):
    """A session's stage: None (the historical unstaged epoch) or a name."""
    if stage is not None and (
        type(stage) is not str
        or not _STAGE.fullmatch(stage)
        or stage in RESERVED_STAGES
    ):
        raise ValueError(
            "a stage is a lowercase name of at most 32 characters, [a-z][a-z0-9_]*, "
            "and not provider, tool or compact"
        )
    return stage


def session_prefix(epoch, stage=None):
    """The identity prefix of a session: `epoch-N`, or `epoch-N-<stage>` for a
    staged one, so two sessions in one epoch never share an identity."""
    return f"epoch-{epoch}" if stage is None else f"epoch-{epoch}-{stage}"


def tool_identity(epoch, turn, position=0, stage=None):
    """A tool call's journal identity: the turn's first call keeps the
    historical `epoch-N-tool-NNN`; a later call in the same turn, under
    `PARALLEL_CALLS_V2`, adds its position (`-KK`). A staged session's
    identities carry its stage (`epoch-N-<stage>-tool-NNN`)."""
    base = f"{session_prefix(epoch, stage)}-tool-{turn:03d}"
    return base if position == 0 else f"{base}-{position:02d}"


def compaction_identity(epoch, turn, attempt=0, stage=None):
    """A compaction call's ledger identity: `epoch-N[-<stage>]-compact-NNN`
    for the compaction before turn NNN, `-KK` for a later attempt."""
    base = f"{session_prefix(epoch, stage)}-compact-{turn:03d}"
    return base if attempt == 0 else f"{base}-{attempt + 1:02d}"


def session_turns(turns, epoch, stage=None):
    """The provider turns (`research_agent.provider_turns`) of one session:
    a staged session's by its prefix; the unstaged epoch's by its own prefix,
    without any staged session's (an unstaged epoch's turns are all
    `epoch-N-provider-NNN`, so an epoch without stages reads exactly as
    before)."""
    prefix = session_prefix(epoch, stage) + "-"
    return [
        t
        for t in turns
        if t["turn"].startswith(prefix)
        and (stage is not None or not _STAGED_TURN.match(t["turn"]))
    ]


def _finish_how(offered, finish=None):
    """How the agent can end its epoch or session, as a notice says it: the
    selection, a caller's finish tool and the stop tool it is offered."""
    ways = [
        "select a practiced recipe" if SELECT in offered else None,
        f"finish with {finish}" if finish is not None else None,
        "stop with " + STOP if STOP in offered else None,
    ]
    return " or ".join(w for w in ways if w) or "finish your work"


def turn_status(
    root,
    turn,
    *,
    calls_left,
    call_limit,
    slots_left,
    trial_limit,
    unit,
    offered,
    finish=None,
):
    """The budget a v2 agent sees before each turn (LP-PROD-A): model calls
    left, counting this turn, and research-trial slots left, with a notice to
    finish at `FINISH_NOTICE_CALLS`. Journalled once, before the request, so
    a replay sends the same request; a later count never rewrites it.
    `finish` names a caller's finish tool, which the notice then offers."""
    path = root / (turn + "-status.json")
    if path.exists():
        return json.loads(path.read_bytes())["message"]
    parts = [
        f"{calls_left} of {call_limit} model calls left in this {unit}, "
        + "counting this turn"
    ]
    if PREFIX + "start_research_task" in offered:
        parts.append(f"{slots_left} of {trial_limit} research-trial slots left")
    text = "Carbon status before this turn: " + "; ".join(parts) + "."
    if calls_left <= FINISH_NOTICE_CALLS:
        how = _finish_how(offered, finish)
        text += (
            f" Notice: only {calls_left} model "
            f"{'call' if calls_left == 1 else 'calls'} left, counting this turn. "
            f"{how[0].upper() + how[1:]} now; when they run out the {unit} stops"
            + (" without a candidate." if SELECT in offered else ".")
        )
    message = {"role": "user", "content": text}
    write_once(
        path,
        canonical(
            {
                "schema": "carbon.autoresearch.turn-status.v1",
                "turn": turn,
                "model_calls_left": calls_left,
                "model_calls": call_limit,
                "trial_slots_left": slots_left,
                "trial_slots": trial_limit,
                "message": message,
            }
        ),
    )
    return message


def _usd(nanodollars):
    return f"USD {nanodollars / 10**9:.4f}"


def budget_status(
    root,
    turn,
    *,
    calls_left,
    call_limit,
    slots_left,
    trial_limit,
    ledger_status,
    provider,
    unit,
    offered,
    finish=None,
):
    """The budget a session under `LIMITS_V2` sees before each turn: the
    optional per-session caps where set, and what the campaign ledger's own
    ceilings still hold - provider calls, provider spend and research trials.
    The notice to finish comes when the calls it can still be sure of - the
    session's own, the campaign's provider calls, and the spend left over each
    call's reservation - reach `FINISH_NOTICE_CALLS`. Journalled once, before
    the request, so a replay sends the same request (`turn_status`)."""
    path = root / (turn + "-status.json")
    if path.exists():
        return json.loads(path.read_bytes())["message"]
    budget = ledger_status.get("budget") or {}
    used = ledger_status["used"]
    parts, sure = [], []
    if call_limit is not None:
        parts.append(
            f"{calls_left} of {call_limit} model calls left in this {unit}, "
            "counting this turn"
        )
        sure.append(calls_left)
    attempts = budget.get("provider_attempts")
    attempts_left = None
    if type(attempts) is int:
        attempts_left = max(0, attempts - used["provider_attempts"])
        parts.append(
            f"{attempts_left} of {attempts} provider calls left in the campaign "
            "budget, counting this turn"
        )
        sure.append(attempts_left)
    money = budget.get("provider_nanodollars")
    reservation = provider.reservation_nano
    money_left = None
    if type(money) is int and type(reservation) is int and reservation > 0:
        money_left = max(0, money - used["provider_nanodollars"])
        parts.append(
            f"{_usd(money_left)} of {_usd(money)} provider spend left in the "
            f"campaign budget; each model call holds up to {_usd(reservation)} "
            "until it is booked"
        )
        sure.append(money_left // reservation)
    trials_budget = budget.get("research_trials")
    if PREFIX + "start_research_task" in offered:
        if trial_limit is not None:
            parts.append(
                f"{slots_left} of {trial_limit} research-trial slots left in this "
                + unit
            )
        if type(trials_budget) is int:
            parts.append(
                f"{max(0, trials_budget - used['research_trials'])} of "
                f"{trials_budget} research trials left in the campaign budget"
            )
    if not parts:
        parts.append(f"no per-{unit} cap and no campaign ceiling is set")
    text = "Carbon status before this turn: " + "; ".join(parts) + "."
    guaranteed = min(sure) if sure else None
    if guaranteed is not None and guaranteed <= FINISH_NOTICE_CALLS:
        how = _finish_how(offered, finish)
        text += (
            f" Notice: the budget is sure of only {guaranteed} more model "
            f"{'call' if guaranteed == 1 else 'calls'}, counting this turn. "
            f"{how[0].upper() + how[1:]} now; when they run out the {unit} stops."
        )
    message = {"role": "user", "content": text}
    write_once(
        path,
        canonical(
            {
                "schema": "carbon.autoresearch.turn-status.v2",
                "turn": turn,
                "model_calls_left": calls_left,
                "model_calls": call_limit,
                "campaign_provider_calls_left": attempts_left,
                "campaign_provider_nanodollars_left": money_left,
                "trial_slots_left": slots_left,
                "trial_slots": trial_limit,
                "model_calls_guaranteed": guaranteed,
                "message": message,
            }
        ),
    )
    return message


def finite_provider_bound(ledger_status, provider):
    """Whether the campaign ledger bounds a session's model calls by itself:
    a provider_attempts ceiling, or a provider_nanodollars ceiling with a
    priced selection (every call reserves its positive maximum). A session
    with no per-epoch call cap runs only under such a ledger."""
    budget = ledger_status.get("budget") or {}
    reservation = provider.reservation_nano
    return type(budget.get("provider_attempts")) is int or (
        type(budget.get("provider_nanodollars")) is int
        and type(reservation) is int
        and reservation > 0
    )


# -- a caller's finish tool ----------------------------------------------------

#: Statuses a finish tool may not claim: the loop's own.
_LOOP_STATUSES = frozenset(
    {
        "SELECTED",
        "STOPPED",
        "RECONCILIATION_REQUIRED",
        "REJECTED_BEFORE_DISPATCH",
        "UNAVAILABLE",
        "REFUSED_NOT_RUN",
    }
)


def check_finish(finish):
    """A caller's local terminal tool: {'tool': a function schema, 'validate':
    callable(arguments) -> (ok, refusal), 'status': the terminal status its
    accepted call records, such as 'PLANNED'}. Returns (tool, validate,
    status) with the tool in canonical form."""
    if type(finish) is not dict or set(finish) != {"tool", "validate", "status"}:
        raise ValueError("a finish is {tool, validate, status}")
    tool = finish["tool"]
    if (
        type(tool) is not dict
        or tool.get("type") != "function"
        or type(tool.get("name")) is not str
        or not tool["name"]
    ):
        raise ValueError("a finish tool is a local function")
    if tool["name"] in (SELECT, STOP, COMPACT, guidance.REPLY):
        raise ValueError("a finish tool has a name of its own")
    if not callable(finish["validate"]):
        raise TypeError("a finish validates its arguments")
    status = finish["status"]
    if (
        type(status) is not str
        or not re.fullmatch(r"[A-Z][A-Z_]{2,31}", status)
        or status in _LOOP_STATUSES
    ):
        raise ValueError("a finish status is its own uppercase status")
    return json.loads(canonical(tool)), finish["validate"], status


def _finish_unchecked(name):
    """The answer when a finish validator answered outside its contract: the
    caller's fault, not the model's, so said plainly; the session goes on."""
    return rejected_call(
        FINISH_INVALID,
        "arguments",
        f"Carbon could not check this {name} call: its checker answered outside "
        "its contract. This is not a fault in your arguments.",
        "continue your work, or end the session another way you are offered",
        checked=False,
    )


def finish_result(validate, status, name, arguments):
    """The finish tool's result, computed before anything is journalled: the
    terminal record with the accepted arguments, or a refusal - the
    validator's own, which must be REJECTED_BEFORE_DISPATCH, or
    `finish_invalid`.

    The model's arguments reach the caller's validator, and the reply that
    carried them is already journalled: anything raised here would be raised
    again on every resume. So a validator that raises is answered
    `finish_invalid` naming the exception's type, and one that answers
    outside its contract (not `(ok, refusal)`, or a refusal that is not a
    REJECTED_BEFORE_DISPATCH record) is answered `finish_invalid` saying so,
    with `checked: false`; the session goes on either way."""
    try:
        verdict = validate(arguments)
    except Exception as error:  # noqa: BLE001 - model-written input, answered
        return rejected_call(
            FINISH_INVALID,
            "arguments",
            f"{name} could not read these arguments ({type(error).__name__})",
            f"check that every field holds what {name} expects, for example "
            "valid JSON in a field ending in _json, and send it again",
        )
    if type(verdict) is not tuple or len(verdict) != 2 or type(verdict[0]) is not bool:
        return _finish_unchecked(name)
    ok, refusal = verdict
    if ok:
        return {
            "status": status,
            "tool": name,
            "arguments": arguments,
            "authority_granted": False,
            "final_evidence": False,
        }
    if refusal is None:
        return rejected_call(
            FINISH_INVALID,
            "arguments",
            f"{name} refused these arguments",
            f"correct the {name} call and send it again",
        )
    if type(refusal) is not dict or refusal.get("status") != "REJECTED_BEFORE_DISPATCH":
        return _finish_unchecked(name)
    try:
        return json.loads(canonical(refusal))
    except (TypeError, ValueError):
        return _finish_unchecked(name)


def session_tools(tools, *, finish_tool=None, miner_guidance=None, compaction=None):
    """A role's offered tools as the loop sends them: the role's own, then
    each tool a frozen rule adds that the role does not already offer - the
    finish tool (`finish['tool']`), the reply to the miner's messages and the
    compaction tool. A role tool with one of those names must be that tool
    exactly. The epoch plan records the result; a caller that freezes a
    manifest digest can compute it here."""
    tools = json.loads(canonical(tools))
    extra = [
        *(() if finish_tool is None else (json.loads(canonical(finish_tool)),)),
        *(() if miner_guidance is None else (guidance.REPLY_TOOL,)),
        *(() if compaction is None else (COMPACTION_TOOL,)),
    ]
    for tool in extra:
        same = [t for t in tools if t.get("name") == tool["name"]]
        if not same:
            tools.append(json.loads(canonical(tool)))
        elif any(canonical(t) != canonical(tool) for t in same):
            raise ValueError("a role tool differs from the rule's own " + tool["name"])
    return tools


def cut_calls(output, calls):
    """Positions, in `calls`, of the tool calls a reply the provider ended
    early did not finish: a call the provider marks unfinished, and the
    reply's last item when it is a call not marked completed - an early end
    cuts what came last. Every call before it was finished before the end."""
    last = output[-1] if output else None
    return [
        position
        for position, item in enumerate(calls)
        if item.get("status") in ("incomplete", "in_progress")
        or (item is last and item.get("status") != "completed")
    ]


def _ended(incomplete):
    if incomplete["reason"] == "max_output_tokens":
        return (
            "was cut off at its limit of "
            f"{incomplete['max_output_tokens']} output tokens"
        )
    return f"ended before it finished (provider reason: {incomplete['reason']})"


def truncated_call(incomplete):
    """The answer to a tool call the reply did not finish: it did not run."""
    return rejected_call(
        CALL_TRUNCATED,
        "arguments",
        f"your reply {_ended(incomplete)} before this call was complete, so it "
        "did not run",
        "send this call again in your next reply, and keep that reply shorter",
    )


def truncation_note(root, turn, response, incomplete, *, cut, ran):
    """The user note after a reply the provider ended early (LP-PROD-A): how
    it ended, which unfinished calls did not run, and to continue - more
    concisely after the output limit. Journalled once, before the next
    request, so a replay sends the same request; a later wording never
    rewrites it."""
    path = root / (turn + "-truncated.json")
    if path.exists():
        return json.loads(path.read_bytes())["message"]
    text = f"Carbon: your last reply {_ended(incomplete)}."
    if cut:
        several = len(cut) > 1
        text += (
            f" Its unfinished tool call{'s' if several else ''} did not run "
            f"({CALL_TRUNCATED}); send {'them' if several else 'it'} again."
        )
    if ran:
        text += " The tool calls it finished ran; their results are above."
    if incomplete["reason"] == "max_output_tokens":
        text += (
            " Continue from where you stopped, more concisely: keep your "
            "reasoning short and send fewer or smaller tool calls in one reply."
        )
    else:
        text += " Continue from where you stopped."
    if not ran:
        # The next such reply ends the run (`REPLIES_TRUNCATED`).
        text += (
            " If your next reply also ends before any tool call in it is "
            "complete, Carbon stops this run."
        )
    message = {"role": "user", "content": text}
    write_once(
        path,
        canonical(
            {
                "schema": "carbon.autoresearch.turn-truncated.v1",
                "turn": turn,
                "response_digest": digest(canonical(response)),
                **incomplete,
                "cut_calls": cut,
                "message": message,
            }
        ),
    )
    return message


def parallel_call_counts(root):
    """How the calls of several-call turns went in one epoch folder, read from
    the v2 journals: how many ran (their result is journalled) and how many a
    selection, a stop or an unresolved dispatch left not run."""
    ran = sum(
        (root / (item["tool"] + "-result.json")).exists()
        for path in sorted(root.glob("*-calls.json"))
        for item in json.loads(path.read_bytes())["calls"]
    )
    not_run = sum(
        len(json.loads(path.read_bytes())["not_run"])
        for path in sorted(root.glob("*-not-run.json"))
    )
    return {"parallel_calls_run": ran, "parallel_calls_not_run": not_run}


# -- explicit, journalled context compaction (COMPACTION_V1) -------------------

COMPACTION_RECORD = "carbon.autoresearch.context-compaction.v1"
COMPACTION_LABEL = "SUMMARY"


def compaction_note(
    compaction,
    unit,
    retry=None,
    *,
    characters=COMPACTION_SUMMARY_CHARACTERS,
    miner_messages=False,
):
    """The user note that asks for a compaction, the last item of a request
    that is otherwise the conversation so far. `retry` says why the reply to
    the first request recorded none: the second request is the conversation
    and this note again, not that reply, so it is admitted whenever the first
    was. `characters` is the summary size that fits the context left
    (`compaction_budget`); `miner_messages` asks the model to keep the
    miner's messages, which leave the context with their turns."""
    kept = compaction["keep_last_turns"]
    text = (
        "Carbon context compaction: this conversation is nearing your model's "
        "context ceiling. "
        + (
            ""
            if retry is None
            else (
                "Carbon asked for this once already and the reply recorded no "
                f"valid compaction ({retry}); this is the last request. "
            )
        )
        + f"Call {COMPACT} now, and only it, with your own summary of everything "
        "you need to continue: " + ", ".join(COMPACTION_FIELDS) + " as text - "
        "findings, open hypotheses, best recipes (exact JSON where you have "
        f"them), constraints and next steps - at most {characters} characters in "
        "all; plain text costs the least room. Carbon then continues with the "
        "initial observation, your summary, labelled as your summary, and the "
        f"last {kept} turns unchanged; the earlier turns leave your context but "
        "stay in Carbon's record."
        + (
            " The miner's messages and your replies in those earlier turns leave "
            "with them: keep in constraints every message of the miner's that "
            "still applies, and what you answered."
            if miner_messages
            else ""
        )
        + (
            f" This call starts nothing and does not end the {unit}."
            if retry is None
            else f" If this reply records none either, the {unit} stops."
        )
    )
    return {"role": "user", "content": text}


#: A summary with every field empty: the compacted conversation's size
#: without its summary, from which the room left for one is computed.
EMPTY_SUMMARY = {field: "" for field in COMPACTION_FIELDS}


def compaction_budget(room):
    """The characters a summary is asked for, given the request bytes `room`
    it may add (`COMPACTION_BYTES_PER_CHARACTER` a character), never more
    than `COMPACTION_SUMMARY_CHARACTERS`; below
    `COMPACTION_MIN_SUMMARY_CHARACTERS` none is worth asking for (None)."""
    characters = min(
        COMPACTION_SUMMARY_CHARACTERS, room // COMPACTION_BYTES_PER_CHARACTER
    )
    return characters if characters >= COMPACTION_MIN_SUMMARY_CHARACTERS else None


def _compaction_call(output):
    """A compaction reply's first call to the compaction tool, or None."""
    return next(
        (
            item
            for item in output
            if type(item) is dict
            and item.get("type") == "function_call"
            and item.get("name") == COMPACT
        ),
        None,
    )


def compaction_text(output):
    """What a compaction reply's call wrote, whatever its validity, to size
    the next request by: (its summary fields that are text, their characters,
    the bytes of its arguments), or None when there is no text to measure.
    Read only to measure; `compaction_summary` alone accepts a summary."""
    call = _compaction_call(output)
    raw = None if call is None else call.get("arguments")
    if type(raw) is not str:
        return None
    try:
        parsed = json.loads(raw)
        size = len(raw.encode())
    except (ValueError, RecursionError, UnicodeError):
        return None
    if type(parsed) is not dict:
        return None
    fields = {
        field: parsed[field]
        for field in COMPACTION_FIELDS
        if type(parsed.get(field)) is str
    }
    characters = sum(len(text) for text in fields.values())
    return (fields, characters, size) if characters else None


def compaction_summary(output, cut=()):
    """(summary, None) from a compaction reply's first call to the compaction
    tool, or (None, why) - one bounded JSON object (`research_tools._json`),
    the closed schema, every field text, at most
    `COMPACTION_SUMMARY_CHARACTERS` in all and nonempty findings. `cut` are
    the call ids the provider ended before they were complete."""
    call = _compaction_call(output)
    if call is None:
        return None, f"the reply did not call {COMPACT}"
    if call.get("call_id") in cut:
        return None, "the call was cut off before it was complete"
    try:
        arguments = _json(call.get("arguments"))
    except (ValueError, RecursionError):
        return None, argument_problem(call.get("arguments"))[0]
    if set(arguments) != set(COMPACTION_FIELDS):
        return None, "it must carry exactly " + ", ".join(COMPACTION_FIELDS)
    if any(type(arguments[field]) is not str for field in COMPACTION_FIELDS):
        return None, "every field is text"
    total = sum(len(arguments[field]) for field in COMPACTION_FIELDS)
    if total > COMPACTION_SUMMARY_CHARACTERS:
        return None, (
            f"it holds {total} characters; the limit is "
            f"{COMPACTION_SUMMARY_CHARACTERS}"
        )
    if not arguments["findings"].strip():
        return None, "findings is empty"
    return {field: arguments[field] for field in COMPACTION_FIELDS}, None


def compaction_message(summary, *, count, summarized, kept):
    """The compaction as the model reads it from then on: one user entry,
    JSON-encoded under one fixed key and labelled as the model's own summary,
    saying which turns left the context."""
    return {
        "role": "user",
        "content": canonical(
            {
                "carbon_context_compaction": {
                    "label": COMPACTION_LABEL,
                    "notice": (
                        "This is your own summary, written at Carbon's request, "
                        "of the conversation through turn "
                        f"{summarized[-1]}. Turns {summarized[0]} to "
                        f"{summarized[-1]} left this conversation to keep it under "
                        "your model's context ceiling; Carbon keeps every one of "
                        "them in its record. The summary is your account, not a "
                        "tool result or verified evidence. The initial observation "
                        f"above and the last {kept} turns below are unchanged."
                    ),
                    "compaction": count,
                    "turns_summarized": [summarized[0], summarized[-1]],
                    "summary": summary,
                }
            }
        ).decode(),
    }


# -- the miner's messages in a staged session ----------------------------------
#
# `miner_guidance` reads and verifies step records named for the unstaged
# epoch (`epoch-N/epoch-N-provider-NNN-miner-guidance.json`). A staged
# session's records live in its own folder under its own identities; these
# helpers give them the same semantics - one campaign cursor over every
# record, the same record shape and chain, replies to any message delivered -
# and leave a campaign without staged sessions on `miner_guidance` itself.

_STAGED_RECORD = re.compile(
    r"epoch-(\d+)-([a-z][a-z0-9_]{0,31})-provider-(\d+)"
    + re.escape(guidance.RECORD_SUFFIX)
)
_UNSTAGED_RECORD = re.compile(
    r"epoch-(\d+)-provider-(\d+)" + re.escape(guidance.RECORD_SUFFIX)
)


def staged_guidance_records(campaign_root):
    """Every staged session's step record, in (epoch, stage, step) order."""
    found = []
    for path in campaign_root.glob(
        "epoch-*/*/epoch-*-provider-*" + guidance.RECORD_SUFFIX
    ):
        match = _STAGED_RECORD.fullmatch(path.name)
        if (
            match is None
            or path.is_symlink()
            or path.parent.name != match.group(2)
            or path.parent.parent.name != "epoch-" + match.group(1)
        ):
            raise ValueError("miner guidance record name differs")
        key = (int(match.group(1)), match.group(2), int(match.group(3)))
        found.append((key, path))
    return [path for _, path in sorted(found)]


def _all_guidance_records(campaign_root):
    unstaged = sorted(
        path
        for path in campaign_root.glob(
            "epoch-*/epoch-*-provider-*" + guidance.RECORD_SUFFIX
        )
        if _UNSTAGED_RECORD.fullmatch(path.name)
    )
    return [*unstaged, *staged_guidance_records(campaign_root)]


def guidance_cursor(campaign_root):
    """The last message sequence the agent has read anywhere in this
    campaign, staged sessions included."""
    last = guidance.cursor(campaign_root)
    for path in staged_guidance_records(campaign_root):
        last = max(last, json.loads(path.read_bytes())["cursor_after"])
    return last


def guidance_delivered(campaign_root):
    """Every message sequence the agent was given in this campaign, newly
    read or carried forward, staged sessions included (`miner_guidance.
    delivered` plus the staged records)."""
    found = set(guidance.delivered(campaign_root))
    for path in staged_guidance_records(campaign_root):
        record = json.loads(path.read_bytes())
        found.update(m["sequence"] for m in record["messages"])
        found.update(m["sequence"] for m in record.get("carried") or [])
    return found


def _carried_into(ledger, owner, folder, rule):
    """`miner_guidance._carried` for a session in a campaign with staged
    sessions: the last messages the agent read in every other session, each
    with its own last replies."""
    read = {}
    for path in _all_guidance_records(ledger.root):
        if path.parent == folder:
            continue
        record = json.loads(path.read_bytes())
        for m in [*(record.get("carried") or []), *record["messages"]]:
            read[m["sequence"]] = {
                "sequence": m["sequence"],
                "digest": m["digest"],
                "text": m["text"],
            }
    chosen = sorted(read)[-rule["carry_forward_messages"] :]
    replies = {sequence: [] for sequence in chosen}
    for note in ledger.status(owner=owner)["notes"]:
        body = note.get("body")
        if (
            note.get("kind") != "notebook"
            or type(body) is not dict
            or body.get("schema") != guidance.NOTE_SCHEMA
            or body.get("note_kind") != guidance.REPLY_KIND
            or body.get("author") != "carbon_agent"
            or body.get("reply_to") not in replies
            or type(note.get("sequence")) is not int
        ):
            continue
        text = guidance.valid_text(body.get("text"))
        if text is not None:
            replies[body["reply_to"]].append(
                {
                    "sequence": note["sequence"],
                    "digest": guidance.reply_digest(text, body["reply_to"]),
                    "text": text,
                }
            )
    return [
        {
            **read[sequence],
            "replies": sorted(replies[sequence], key=lambda r: r["sequence"])[
                -rule["carry_forward_replies"] :
            ],
        }
        for sequence in chosen
    ]


def guidance_step(ledger, *, owner, folder, turn, rule, previous, stage):
    """A step's recorded guidance (`miner_guidance.step`). An unstaged epoch
    in a campaign without staged sessions is `miner_guidance.step` itself;
    otherwise the same record, read once against the campaign-wide cursor."""
    if stage is None and not staged_guidance_records(ledger.root):
        return guidance.step(
            ledger,
            owner=owner,
            epoch_root=folder,
            turn=turn,
            rule=rule,
            previous=previous,
        )
    path = folder / (turn + guidance.RECORD_SUFFIX)
    if path.exists():
        record = json.loads(path.read_bytes())
        if (
            record.get("schema") != guidance.RECORD_SCHEMA
            or record.get("turn") != turn
            or record.get("previous") != previous
            or record.get("chain")
            != guidance.chain(previous, turn, record["messages"], record.get("carried"))
        ):
            raise ValueError("miner guidance record differs; reconcile")
        return record
    if rule not in guidance.RULES:
        raise ValueError("unknown miner guidance rule")
    carried = (
        _carried_into(ledger, owner, folder, rule)
        if "carry_forward_messages" in rule and turn.endswith("-provider-000")
        else None
    )
    before = guidance_cursor(ledger.root)
    new = [
        m
        for m in guidance.messages(ledger.status(owner=owner)["notes"])
        if m[0] > before
    ]
    items = [
        {"sequence": sequence, "digest": fingerprint, "text": text}
        for sequence, text, fingerprint in new[: rule["max_messages_per_step"]]
    ]
    record = {
        "schema": guidance.RECORD_SCHEMA,
        "turn": turn,
        "rule": rule,
        "cursor_before": before,
        "cursor_after": items[-1]["sequence"] if items else before,
        "messages": items,
        "unread_after": len(new) - len(items),
        "previous": previous,
        "chain": guidance.chain(previous, turn, items, carried),
    }
    if carried is not None:
        record["carried"] = carried
    write_once(path, canonical(record))
    return record


def guidance_verify(folder, plan, stage):
    """A session's guidance chain from its plan (`miner_guidance.verify`),
    for a staged session's own record names too."""
    if stage is None:
        return guidance.verify(folder, plan)
    previous = digest(canonical(plan))
    steps = sorted(
        (int(match.group(3)), path)
        for path in folder.glob("epoch-*-provider-*" + guidance.RECORD_SUFFIX)
        if (match := _STAGED_RECORD.fullmatch(path.name))
    )
    for _, path in steps:
        record = json.loads(path.read_bytes())
        if record.get("previous") != previous or record.get("chain") != guidance.chain(
            previous,
            record.get("turn"),
            record.get("messages", []),
            record.get("carried"),
        ):
            raise ValueError("frozen effective research input differs")
        previous = record["chain"]
    return previous


def guidance_reply(ledger, *, owner, arguments):
    """The agent's reply to the miner (`miner_guidance.reply`), to any
    message delivered in this campaign, staged sessions included."""
    if not staged_guidance_records(ledger.root):
        return guidance.reply(ledger, owner=owner, arguments=arguments)
    if type(arguments) is not dict or set(arguments) != {"reply_to", "text"}:
        return {
            "status": "REFUSED",
            "reason": "reply_to and text required",
            "authority_granted": False,
        }
    reply_to, text = arguments["reply_to"], guidance.valid_text(arguments["text"])
    if type(reply_to) is not int or reply_to not in guidance_delivered(ledger.root):
        return {
            "status": "REFUSED",
            "reason": "reply_to names no message you were given",
            "authority_granted": False,
        }
    if text is None:
        return {
            "status": "REFUSED",
            "reason": "1 to 2000 characters of plain text required",
            "authority_granted": False,
        }
    ledger.note(
        owner=owner,
        kind="notebook",
        body={
            "schema": guidance.NOTE_SCHEMA,
            "note_kind": guidance.REPLY_KIND,
            "text": text,
            "reply_to": reply_to,
            "author": "carbon_agent",
        },
    )
    return {"status": "REPLIED", "reply_to": reply_to, "authority_granted": False}


def _epoch_paths(ledger, epoch, stage=None):
    if type(epoch) is not int or epoch not in (1, 2):
        raise ValueError("two finite epochs only")
    root = ledger.root / ("epoch-" + str(epoch))
    root.mkdir(mode=0o700, exist_ok=True)
    if stage is not None:
        root = root / stage
        root.mkdir(mode=0o700, exist_ok=True)
    return root


async def run_epoch(
    ledger,
    *,
    owner,
    epoch,
    sdk,
    credential_file,
    initial_observation,
    transport=None,
    agent_policy=LEGACY,
    challenge=None,
    provider=DEFAULT_SELECTION,
    parallel_calls=None,
    instructions=None,
    tools=None,
    miner_guidance=None,
    max_provider_calls=None,
    stage=None,
    finish=None,
    limits=None,
    compaction=None,
):
    """Run once or resume completed provider/tool observations without resends.

    `provider` is the campaign's model selection (`model_provider`); the
    historical pinned selection produces the same plan and requests as before
    selection existed.

    An interrupted tool with unknown side effects stops for reconciliation.
    Successfully journalled replies can be replayed without another model call.

    `parallel_calls` is the rule the campaign froze for a turn with several
    tool calls: None is the historical rule (the epoch stops, retained);
    `PARALLEL_CALLS` runs the first call, answers each other with a journalled
    refusal that consumes no trial slot, and stops only on its consecutive
    limit. `PARALLEL_CALLS_V2` (LP-PROD-A) runs every call of a turn in the
    model's order, each with its own intent and result journal
    (`tool_identity`), re-reading the trial count before each numerical call;
    a selection, a stop or an unresolved dispatch ends the epoch and the
    turn's later calls are journalled as not run. Under v2 the request allows
    parallel tool calls, the agent sees its remaining budget before each turn
    (`turn_status`), any tool call renews the one free-text reminder, and
    Carbon's own agent can select only a practiced recipe (`practice_check`).
    The rule also chooses the prompt (`prompt_for`), so v1 and None plans
    replay byte-identically.

    `instructions` and `tools` are a caller's own closed role (GRAPHITE-01):
    given together, they replace the policy prompt and the offered tool list,
    and the loop runs the selection or stop tool only when that list offers
    it; every other call goes to `sdk`, which owns refusing it. Both are
    recorded in the epoch plan. Omitted, the historical prompt and tools stand
    unchanged.

    `miner_guidance` is the rule a campaign froze for the miner's messages
    (`miner_guidance.RULE`, RSURF-D13): at each step boundary the agent reads
    the messages new since its cursor as separate user-role guidance, recorded
    with their sequences and digests and chained from this plan, and may reply
    with the reply tool. None, a plan frozen before the amendment, reads none.

    `max_provider_calls` is a role's own per-epoch model-call cap
    (GRAPHITE-D26), accepted only with `instructions` and `tools` and recorded
    in the epoch plan. Omitted, the shared `MAX_PROVIDER_CALLS` stands and the
    plan is unchanged.

    New sessions may freeze these (OWNER-GRAPHITE-MINER-01); each None keeps
    every earlier plan, prompt, identity and journal byte for byte:

    `agent_policy=GRAPHITE_MINER` runs a role's own instructions and tools,
    with or without a Challenge, under `PARALLEL_CALLS_V2`: results reach the
    model as `model_view` shows them, a selection needs a completed practice
    (`practice_check`), the stop tool ends the session, one free-text
    reminder is given and renewed by any tool call, the miner's messages may
    be read, and the loop states its operating rules after the role's
    instructions (`research_agent_policy.graphite_miner_prompt`).

    `stage` namespaces a session inside its epoch: its folder is
    `epoch-N/<stage>/`, its identities `epoch-N-<stage>-provider-NNN`,
    `epoch-N-<stage>-tool-NNN[-KK]` and `epoch-N-<stage>-compact-NNN[-KK]`,
    and its start operation `research-epoch-N-<stage>` reserves no epochs
    unit, so several sessions share one epoch.

    `finish` is a role's own local terminal tool, {'tool': its function
    schema, 'validate': callable(arguments) -> (ok, refusal), 'status': the
    status an accepted call ends the session with, such as 'PLANNED'}. Its
    result is computed before its intent is journalled, like a selection: the
    accepted arguments, or the validator's REJECTED_BEFORE_DISPATCH refusal,
    after which the session goes on.

    `limits` is `LIMITS_V2`: the per-epoch model-call and research-trial caps
    are optional, and an unset one leaves only the campaign ledger's ceilings
    to bind; a session with no call cap needs a ledger that bounds its model
    calls (`finite_provider_bound`). Before each turn the agent sees what the
    caps and the ledger still hold (`budget_status`).

    `compaction` is `COMPACTION_V1`: when a turn's request nears the context
    admission ceiling the loop makes an explicit compaction call, journalled
    and metered like any model call, for a summary sized to the context the
    kept turns leave, and continues with the initial observation, the
    model's labelled summary and the last turns; see
    `research_agent_policy.COMPACTION_V1`. A summary is accepted only when
    the compacted conversation is admitted with room to spare, and when no
    summary has room no compaction is asked for. Without the rule the session
    stops at the ceiling as before.

    A Graphite miner role states its call cap in `limits`, never
    `max_provider_calls`, so the cap its prompt states is the cap it runs
    under.

    A ledger that refuses a model call with `CeilingReached` ends the session
    STOPPED with that code.
    """
    check_parallel_rule(parallel_calls)
    every_call = parallel_calls == PARALLEL_CALLS_V2
    miner = agent_policy == GRAPHITE_MINER
    if miner_guidance is not None and miner_guidance not in guidance.RULES:
        raise ValueError("unknown miner guidance rule")
    if miner_guidance is not None and not (
        miner or (agent_policy == AUTONOMOUS and instructions is None)
    ):
        raise ValueError(
            "miner guidance reaches Carbon's autonomous agent only, or a "
            "Graphite miner role"
        )
    if (instructions is None) != (tools is None):
        raise ValueError("a role supplies both its instructions and its tools")
    if instructions is not None and not (
        miner or (agent_policy == LEGACY and challenge is None)
    ):
        raise ValueError(
            "role instructions run under the legacy policy, or the Graphite miner "
            "policy, only"
        )
    if miner and instructions is None:
        raise ValueError("the Graphite miner policy runs a role's instructions")
    if miner and not every_call:
        raise ValueError("the Graphite miner policy runs under PARALLEL_CALLS_V2")
    if miner and max_provider_calls is not None:
        # Its prompt states the cap from the limits rule, so the cap it is
        # told is always the cap it runs under.
        raise ValueError(
            "a Graphite miner role sets its call cap in limits (limits_v2), not "
            "max_provider_calls"
        )
    if max_provider_calls is not None:
        if instructions is None:
            raise ValueError("only a role's instructions carry their own call cap")
        if type(max_provider_calls) is not int or max_provider_calls < 1:
            raise ValueError("a role's call cap is a positive integer")
        if limits is not None:
            raise ValueError("a role's call cap or a limits rule, not both")
    for name, value in (
        ("limits", limits),
        ("compaction", compaction),
        ("finish", finish),
    ):
        if value is not None and instructions is None:
            raise ValueError(f"only a role's session takes {name}")
    if limits is not None:
        check_limits(limits)
    if compaction is not None:
        check_compaction(compaction)
    finish_tool = finish_validate = finish_status = finish_name = None
    if finish is not None:
        finish_tool, finish_validate, finish_status = check_finish(finish)
        finish_name = finish_tool["name"]
    check_stage(stage)
    call_limit = (
        MAX_PROVIDER_CALLS if max_provider_calls is None else max_provider_calls
    )
    if limits is not None:
        call_limit = limits["calls_per_epoch"]
    if call_limit is None and not finite_provider_bound(
        ledger.status(owner=owner), provider
    ):
        raise ValueError(
            "a session with no per-epoch model-call cap needs a finite "
            "provider_attempts ceiling, or a provider_nanodollars ceiling with a "
            "priced model selection"
        )
    root = _epoch_paths(ledger, epoch, stage)
    autonomous = agent_policy == AUTONOMOUS
    # The policies whose agent ends with the stop tool and is reminded once.
    stops = autonomous or miner
    reminder = REMINDER
    if instructions is None:
        policy = binding(agent_policy, challenge, parallel_calls)
        prompt = prompt_for(agent_policy, challenge, parallel_calls)
        tools = (
            tools_for_sdk(sdk)
            + [SELECTION_TOOL]
            + ([STOP_TOOL] if autonomous else [])
            + ([guidance.REPLY_TOOL] if miner_guidance is not None else [])
        )
    else:
        if type(instructions) is not str or not instructions:
            raise ValueError("role instructions are a non-empty string")
        if type(tools) is not list or any(
            type(t) is not dict or t.get("type") != "function" for t in tools
        ):
            raise ValueError("a role's tools are a list of local functions")
        tools = session_tools(
            tools,
            finish_tool=finish_tool,
            miner_guidance=miner_guidance,
            compaction=compaction,
        )
        if miner:
            named = {tool["name"] for tool in tools}
            ways = {
                "select": SELECT in named,
                "stop": STOP in named,
                "finish": finish_name,
            }
            prompt = graphite_miner_prompt(
                instructions, limits=limits, compaction=compaction, **ways
            )
            reminder = graphite_miner_reminder(**ways)
            policy = graphite_miner_binding(prompt, instructions, reminder, challenge)
        else:
            policy = binding(agent_policy, challenge, parallel_calls)
            prompt = instructions
    offered = {tool["name"] for tool in tools}
    schemas = {tool["name"]: tool for tool in tools}
    unit = "epoch" if instructions is None else "session"
    label = f"Research epoch {epoch}" + ("" if stage is None else f" {stage}")
    # A v2 selection by Carbon's own agent, or by a Graphite miner role, needs
    # a completed practice; a role's caller owns what its selection means.
    select_check = (
        practice_check(ledger, owner)
        if (every_call and instructions is None) or miner
        else None
    )
    plan = {
        "schema": "carbon.autoresearch.epoch-plan.v1",
        "epoch": epoch,
        "owner": owner,
        "model": provider.model_id,
        "prompt": prompt,
        "tools": tools,
        "initial_observation": initial_observation,
        "max_provider_calls": call_limit,
        "max_research_trials": (
            MAX_RESEARCH_TRIALS if limits is None else limits["trials_per_epoch"]
        ),
        "rule_change": False,
        "selection_is_final_evidence": False,
    }
    if stops:
        plan["agent_policy"] = policy
    if not provider.is_historical_default:
        plan["model_selection"] = provider.record()
    if parallel_calls is not None:
        plan["parallel_calls"] = parallel_calls
    if miner_guidance is not None:
        plan["miner_guidance"] = miner_guidance
    if stage is not None:
        plan["stage"] = stage
    if limits is not None:
        plan["limits"] = limits
    if compaction is not None:
        plan["compaction"] = compaction
    if finish_tool is not None:
        plan["finish"] = {"tool": finish_tool["name"], "status": finish_status}
    if "research_guidance" in initial_observation:
        plan["effective_input_digest"] = effective_digest(policy, initial_observation)
    write_once(root / "plan.json", canonical(plan))
    prefix = session_prefix(epoch, stage)
    # The unstaged epoch's start spends its epochs unit; a stage shares it.
    started = {"epochs": 1} if stage is None else {}
    start_id = "research-" + prefix
    admitted = ledger.reserve(
        start_id, owner=owner, phase="selection", request=plan, resources=started
    )
    if admitted["dispatch"]:
        ledger.finish(
            start_id,
            owner=owner,
            state="SUCCEEDED",
            actual=started,
            result={"status": "STARTED", "plan_digest": digest(canonical(plan))},
        )
    if (root / "outcome.json").exists():
        return json.loads((root / "outcome.json").read_bytes())
    history = [{"role": "user", "content": canonical(initial_observation).decode()}]
    trial_start_file = root / "trial-start.json"
    if not trial_start_file.exists():
        write_once(
            trial_start_file,
            canonical({"count": ledger.status(owner=owner)["used"]["research_trials"]}),
        )
    trial_start = json.loads(trial_start_file.read_bytes())["count"]
    outcome = None
    reminders = 0
    # Consecutive turns with several tool calls; recomputed identically on a
    # replay, because the retained responses replay in order.
    parallel_run = 0
    # Consecutive replies ended early with no tool call complete, likewise.
    truncated = []
    # The last turn's provider-reported input tokens and its request's bytes;
    # None until a turn reports them.
    anchor = None
    # The miner's messages read so far, chained from this frozen plan.
    guidance_chain = digest(canonical(plan)) if miner_guidance is not None else None
    # The finish status ends the session only as the finish tool's own result.
    terminal = {"SELECTED", "STOPPED"} if stops else {"SELECTED"}
    # The current turn's trial ceiling; `dispatch` reads it when it runs.
    # None under a limits rule with no trial cap: the ledger's own binds.
    trial_limit = MAX_RESEARCH_TRIALS if limits is None else limits["trials_per_epoch"]
    # Compaction state (COMPACTION_V1), recomputed identically on a replay:
    # model calls the compactions made, compactions done, due compactions not
    # asked for because no summary had room, each turn still in the context
    # with the history index it starts at, and the least input tokens any
    # turn of this session reported (every request starts with the same
    # instructions, tools and initial observation, so it bounds their tokens).
    extra_calls = 0
    compactions = 0
    deferred = 0
    live_turns = []
    base_tokens = None
    ceiling = provider.settings.max_input_tokens - CONTEXT_RESERVE_TOKENS

    def request_for(items):
        effort = provider.settings.reasoning_effort
        return {
            "model": provider.model_id,
            "instructions": prompt,
            "input": items,
            "tools": tools,
            "parallel_tool_calls": every_call,
            "store": False,
            "max_output_tokens": provider.settings.max_output_tokens,
            "reasoning": None if effort is None else {"effort": effort},
        }

    def admission_phase(identity, phase):
        """A call's ledger phase, journalled once before its request."""
        path = root / (identity + "-admission.json")
        if not path.exists():
            write_once(path, canonical({"phase": phase}))
        return json.loads(path.read_bytes())["phase"]

    async def dispatch(name, arguments, identity):
        """One call that leaves this epoch's folder, after its intent."""
        if (
            miner_guidance is not None
            and name == guidance.REPLY
            and guidance.REPLY in offered
        ):
            return guidance_reply(ledger, owner=owner, arguments=arguments)
        numerical = name == PREFIX + "start_research_task" and (
            arguments.get("kind") == "practice"
            or arguments.get("action") in NUMERICAL_ACTIONS
        )
        # Re-read before every numerical call, so a later call in a turn sees
        # the slots the earlier ones spent and a turn cannot overspend.
        if (
            numerical
            and trial_limit is not None
            and (
                ledger.status(owner=owner)["used"]["research_trials"] - trial_start
                >= trial_limit
            )
        ):
            result = {
                "status": "UNAVAILABLE",
                "reason": "epoch research trial ceiling; select retained recipe or stop",
                "authority_granted": False,
            }
            ledger.note(owner=owner, kind="refusal", body=result)
            return result
        return await sdk.call(name, arguments, identity)

    async def run_call(call, identity, cut=None):
        """One tool call, exactly once: its intent journalled before dispatch
        and its result after; a replay reads the result. `cut` is how the
        reply ended when it ended before this call was complete: the call is
        answered `call_truncated` and nothing runs."""
        arguments, rejection = tool_arguments(call, schemas)
        if cut is not None:
            rejection = truncated_call(cut)
        intent = {
            "name": call["name"],
            "arguments": arguments,
            "call_id": call["call_id"],
        }
        intent_file = root / (identity + "-intent.json")
        result_file = root / (identity + "-result.json")
        if result_file.exists():
            if not intent_file.exists() or intent_file.read_bytes() != canonical(
                intent
            ):
                raise ValueError("tool replay conflict")
            return json.loads(result_file.read_bytes())
        stop = stops and call["name"] == STOP and STOP in offered
        select = call["name"] == SELECT and SELECT in offered
        finishing = finish_tool is not None and call["name"] == finish_tool["name"]
        compacting = compaction is not None and call["name"] == COMPACT
        # A rejection, a stop, a selection, a finish and an unrequested
        # compaction dispatch nothing outside this folder; each result is a
        # function of the call and the ledger alone. It is computed before the
        # intent is written, and recomputed when an interruption left an
        # intent without a result.
        local = rejection is not None or stop or select or finishing or compacting
        if intent_file.exists() and not local:
            raise ValueError("tool dispatch incomplete; reconcile without duplication")
        if rejection is not None:
            result = rejection
        elif stop:
            result = stop_result(arguments)
        elif select:
            result = selection_result(arguments, check=select_check)
        elif finishing:
            result = finish_result(
                finish_validate, finish_status, call["name"], arguments
            )
        elif compacting:
            result = rejected_call(
                COMPACTION_NOT_REQUESTED,
                "name",
                "Carbon did not ask for a compaction now",
                "continue your work; Carbon asks for a compaction when the "
                "context nears its ceiling",
            )
        ledger.checkpoint()
        write_once(intent_file, canonical(intent))
        if not local:
            result = await dispatch(call["name"], arguments, identity)
        elif result.get("status") == "SELECTED":
            write_once(root / "selected-recipe.json", canonical(result))
        write_once(result_file, canonical(result))
        return result

    def compacted_anchor(items, message, compaction_tokens):
        """The least of three valid bounds on a compacted request's input
        tokens, and the anchor that gives it: its bytes (no anchor); the
        compaction request's tokens plus the summary message's bytes, since
        the compacted request is a subsequence of that request plus the
        message; and the least input tokens a turn of this session reported
        plus the bytes after the initial observation, since every request
        starts with the same instructions, tools and initial observation.
        Each later request appends to the compacted one, so the least stays
        the least until a turn reports its own tokens."""
        size = len(canonical(request_for(items)))
        candidates = [None]
        if compaction_tokens is not None:
            candidates.append((compaction_tokens + len(canonical(message)), size))
        if base_tokens is not None:
            candidates.append((base_tokens, len(canonical(request_for(items[:1])))))
        best = min(candidates, key=lambda candidate: input_token_bound(size, candidate))
        return input_token_bound(size, best), best

    async def compact(index, turn_id, phase, pending):
        """The compaction before turn `index` (COMPACTION_V1), when one is
        due and a summary has room: an explicit model call asking for the
        closed summary, at most `COMPACTION_ATTEMPTS` of them, journalled and
        metered like any model call. `pending` is the miner's message this
        turn appends after the compaction, counted in the room it must leave.

        The summary is asked for at the size the context left holds
        (`compaction_budget`) and accepted only when the compacted
        conversation is admitted under the ceiling with
        `COMPACTION_HEADROOM_TOKENS` and `pending` to spare
        (`compacted_anchor`); one too long is asked for again at the size its
        own text shows will fit. When no summary of
        `COMPACTION_MIN_SUMMARY_CHARACTERS` has room, or no model call would
        be left for the turn after it, none is asked for and the session goes
        on as it would without the rule. On success the history becomes the
        initial observation, the labelled summary and the last turns, and the
        record names what left the context. Returns an outcome that ends the
        session, or None."""
        nonlocal history, anchor, extra_calls, compactions, deferred, live_turns
        record_path = root / (compaction_identity(epoch, index, 0, stage) + ".json")
        threshold = int(ceiling * compaction["trigger_fraction"])
        kept_count = compaction["keep_last_turns"]
        bound = input_token_bound(len(canonical(request_for(history))), anchor)
        due = bound > threshold and len(live_turns) > kept_count
        if due:
            keep_from = live_turns[-kept_count][1]
            summarized = [turn for turn, _ in live_turns[:-kept_count]]
            kept = history[keep_from:]
            count = compactions + 1
            spare = COMPACTION_HEADROOM_TOKENS + (
                0 if pending is None else len(canonical(pending)) + 1
            )
            empty = compaction_message(
                EMPTY_SUMMARY, count=count, summarized=summarized, kept=kept_count
            )

            def room(compaction_tokens):
                """Request bytes a summary may add to the compacted
                conversation and still leave `spare` under the ceiling."""
                used, _ = compacted_anchor(
                    [history[0], empty, *kept], empty, compaction_tokens
                )
                return ceiling - spare - used

            def note(retry=None, characters=COMPACTION_SUMMARY_CHARACTERS):
                return compaction_note(
                    compaction,
                    unit,
                    retry,
                    characters=characters,
                    miner_messages=miner_guidance is not None,
                )

            def resize(output, compaction_tokens, characters):
                """The characters the last request asks for. When the
                refused reply wrote summary text, its own bytes a character
                say what fits both the context left and the tool-argument
                bound, with a tenth to spare; otherwise the planned size."""
                have = max(0, room(compaction_tokens))
                measured = compaction_text(output)
                if measured is None:
                    return compaction_budget(have) or characters
                fields, length, size = measured
                cost = len(
                    canonical(
                        compaction_message(
                            {**EMPTY_SUMMARY, **fields},
                            count=count,
                            summarized=summarized,
                            kept=kept_count,
                        )
                    )
                ) - len(canonical(empty))
                keys = len(canonical(EMPTY_SUMMARY))
                return max(
                    1,
                    min(
                        COMPACTION_SUMMARY_CHARACTERS,
                        have * length * 9 // (max(1, cost) * 10),
                        (MAX_TOOL_ARGUMENT_BYTES - keys)
                        * length
                        * 9
                        // (max(1, size - keys) * 10),
                    ),
                )

            # The note at the largest size bounds the request carrying any
            # smaller one, so the room it leaves is never overstated.
            widest = input_token_bound(
                len(canonical(request_for([*history, note()]))), anchor
            )
            characters = compaction_budget(room(widest))
            calls_left = (
                None if call_limit is None else call_limit - index - extra_calls
            )
            if characters is None or (calls_left is not None and calls_left < 2):
                due = False
                deferred += 1
        if not due:
            if record_path.exists():
                raise ValueError("context compaction replay conflict")
            return None
        items = [*history, note(characters=characters)]
        # The least valid bound on the compaction requests' input tokens.
        compaction_tokens = None
        sent, asked, why, success = [], [characters], None, None
        for attempt in range(COMPACTION_ATTEMPTS):
            if call_limit is not None and index + extra_calls >= call_limit:
                return {"status": "STOPPED", "reason": "epoch provider-call ceiling"}
            identity = compaction_identity(epoch, index, attempt, stage)
            # Each request appends a note to the conversation the last turn's
            # anchor measures, so that anchor bounds it.
            request = request_for(items)
            request_bytes = len(canonical(request))
            admitted = input_token_bound(request_bytes, anchor)
            if admitted > ceiling:
                return {
                    "status": "STOPPED",
                    "code": CONTEXT_CEILING,
                    "reason": (
                        "context admission ceiling: the compaction request does "
                        "not fit; no history silently discarded"
                    ),
                    "compaction_calls": sent,
                }
            print(
                f"{label}: context compaction before turn {index + 1} "
                f"(call {identity})",
                flush=True,
            )
            try:
                response = await asyncio.to_thread(
                    request_model,
                    ledger,
                    owner=owner,
                    identity=identity,
                    request=request,
                    credential_file=credential_file,
                    phase=admission_phase(identity, phase),
                    transport=transport,
                    provider=provider,
                    anchor=anchor,
                    accept_incomplete=True,
                )
            except CeilingReached as reached:
                return {**reached.outcome(), "compaction_calls": sent}
            extra_calls += 1
            sent.append(identity)
            turn = next(
                t
                for t in provider_turns(ledger.status(owner=owner)["operations"])
                if t["turn"] == identity
            )
            write_once(root / (identity + "-turn.json"), canonical(turn))
            tokens = turn["input_tokens"]
            if type(tokens) is int and tokens >= 0:
                admitted = min(admitted, tokens)
            compaction_tokens = (
                admitted
                if compaction_tokens is None
                else min(compaction_tokens, admitted)
            )
            output = response.get("output")
            if type(output) is not list:
                raise ValueError("provider output malformed; retained and stopped")
            calls = [
                item
                for item in output
                if type(item) is dict and item.get("type") == "function_call"
            ]
            incomplete = incomplete_reply(response, provider.settings.max_output_tokens)
            cut = (
                [calls[p].get("call_id") for p in cut_calls(output, calls)]
                if incomplete is not None
                else []
            )
            summary, why = compaction_summary(output, cut)
            if summary is not None:
                message = compaction_message(
                    summary, count=count, summarized=summarized, kept=kept_count
                )
                compacted = [history[0], message, *kept]
                admitted_bound, new_anchor = compacted_anchor(
                    compacted, message, compaction_tokens
                )
                if admitted_bound + spare <= ceiling:
                    success = (response, message, compacted, admitted_bound, new_anchor)
                    break
                # Valid, but too long for the context left.
                why = (
                    f"it needs {len(canonical(message)) - len(canonical(empty))} "
                    f"bytes of context and {max(0, room(compaction_tokens))} are "
                    f"left beside the last {kept_count} turns"
                )
            if attempt + 1 < COMPACTION_ATTEMPTS:
                characters = resize(output, compaction_tokens, characters)
                asked.append(characters)
                # The last request is the conversation and the note again,
                # saying why; the refused reply stays in the journal, not in
                # the context, so the request fits whenever the first did.
                items = [*history, note(retry=why, characters=characters)]
        if success is None:
            return {
                "status": "STOPPED",
                "code": COMPACTION_FAILED,
                "reason": (
                    f"context compaction recorded no valid summary ({why}); "
                    "retained and stopped; no history silently discarded"
                ),
                "compaction_calls": sent,
            }
        response, message, compacted, admitted_bound, new_anchor = success
        compactions += 1
        dropped = history[1:keep_from]
        write_once(
            record_path,
            canonical(
                {
                    "schema": COMPACTION_RECORD,
                    "turn": turn_id,
                    "rule": compaction,
                    "compaction": compactions,
                    "supersedes": compactions - 1 if compactions > 1 else None,
                    "calls": sent,
                    "response_digest": digest(canonical(response)),
                    "trigger": {
                        "input_token_bound": bound,
                        "threshold": threshold,
                        "ceiling": ceiling,
                    },
                    "summary_characters_asked": asked,
                    "turns_summarized": summarized,
                    "turns_kept": [turn for turn, _ in live_turns[-kept_count:]],
                    "dropped_items": len(dropped),
                    "dropped_digest": digest(canonical(dropped)),
                    "kept_items": len(kept),
                    "summary": summary,
                    "message": message,
                    "admission": {
                        "input_token_bound": admitted_bound,
                        "spare": spare,
                        "anchor": None if new_anchor is None else list(new_anchor),
                    },
                }
            ),
        )
        history, anchor = compacted, new_anchor
        live_turns = [
            (turn, 2 + start - keep_from) for turn, start in live_turns[-kept_count:]
        ]
        return None

    turn_indices = range(call_limit) if call_limit is not None else itertools.count()
    for index in turn_indices:
        if call_limit is not None and index + extra_calls >= call_limit:
            # The session's compactions spent its last model calls.
            break
        ledger.checkpoint()
        status = ledger.status(owner=owner)
        trials = status["used"]["research_trials"] - trial_start
        if limits is None:
            # Eight per epoch regardless; a miner's budget can only lower it,
            # and its absence is not a reason to invent a different number.
            budgeted = (status.get("budget") or {}).get("research_trials")
            trial_limit = (
                min(MAX_RESEARCH_TRIALS, max(0, budgeted - trial_start))
                if ledger.admission is not None and budgeted is not None
                else MAX_RESEARCH_TRIALS
            )
        call_id = f"{prefix}-provider-{index:03d}"
        phase = (
            "research" if trial_limit is None or trials < trial_limit else "selection"
        )
        pending = None
        if miner_guidance is not None:
            # The step boundary: read once from the journal, recorded before
            # the request; a replay reads the record, so the turn is the same.
            # Read before a compaction, which leaves room for it and which it
            # follows, so a new message is never summarised away unread.
            record = guidance_step(
                ledger,
                owner=owner,
                folder=root,
                turn=call_id,
                rule=miner_guidance,
                previous=guidance_chain,
                stage=stage,
            )
            guidance_chain = record["chain"]
            pending = guidance.for_model(record)
        if compaction is not None:
            outcome = await compact(index, call_id, phase, pending)
            if outcome is not None:
                break
            if call_limit is not None and index + extra_calls >= call_limit:
                break
            live_turns.append((call_id, len(history)))
        if pending is not None:
            history.append(pending)
        if every_call and limits is None:
            history.append(
                turn_status(
                    root,
                    call_id,
                    calls_left=call_limit - index - extra_calls,
                    call_limit=call_limit,
                    slots_left=max(0, trial_limit - trials),
                    trial_limit=trial_limit,
                    unit=unit,
                    offered=offered,
                    finish=finish_name,
                )
            )
        elif every_call:
            history.append(
                budget_status(
                    root,
                    call_id,
                    calls_left=(
                        None if call_limit is None else call_limit - index - extra_calls
                    ),
                    call_limit=call_limit,
                    slots_left=(
                        None if trial_limit is None else max(0, trial_limit - trials)
                    ),
                    trial_limit=trial_limit,
                    ledger_status=ledger.status(owner=owner),
                    provider=provider,
                    unit=unit,
                    offered=offered,
                    finish=finish_name,
                )
            )
        request = request_for(history)
        request_bytes = len(canonical(request))
        if (
            input_token_bound(request_bytes, anchor)
            > provider.settings.max_input_tokens - CONTEXT_RESERVE_TOKENS
        ):
            outcome = {
                "status": "STOPPED",
                "reason": "context admission ceiling; no history silently discarded",
            }
            if compaction is not None:
                outcome["code"] = CONTEXT_CEILING
            break
        print(
            f"{label}: agent call {index + 1}/"
            f"{'-' if call_limit is None else call_limit}; trial slots used "
            f"{trials}/{'-' if trial_limit is None else trial_limit}",
            flush=True,
        )
        phase = admission_phase(call_id, phase)
        # A reply the provider ended early comes back metered (LP-PROD-A).
        try:
            response = await asyncio.to_thread(
                request_model,
                ledger,
                owner=owner,
                identity=call_id,
                request=request,
                credential_file=credential_file,
                phase=phase,
                transport=transport,
                provider=provider,
                anchor=anchor,
                accept_incomplete=True,
            )
        except CeilingReached as reached:
            outcome = reached.outcome()
            break
        # The turn's cost, tokens and serving identity, journalled beside the
        # epoch so a view shows spend per turn as it happens.
        turns = provider_turns(ledger.status(owner=owner)["operations"])
        turn = next(t for t in turns if t["turn"] == call_id)
        write_once(root / (call_id + "-turn.json"), canonical(turn))
        if type(turn["input_tokens"]) is int and turn["input_tokens"] >= 0:
            anchor = (turn["input_tokens"], request_bytes)
            base_tokens = min(
                turn["input_tokens"],
                turn["input_tokens"] if base_tokens is None else base_tokens,
            )
        caching = caching_status(session_turns(turns, epoch, stage))
        print(
            f"{label}: turn {index + 1} charge "
            f"{turn['charge_nanodollars']} nanodollars ({'; '.join(turn['charge_basis'])}); "
            f"cached input {turn['cached_input_tokens']}/{turn['input_tokens']}; "
            f"caching {caching['status']}",
            flush=True,
        )
        output = response.get("output")
        if type(output) is not list:
            raise ValueError("provider output malformed; retained and stopped")
        calls = [
            item
            for item in output
            if type(item) is dict and item.get("type") == "function_call"
        ]
        incomplete = incomplete_reply(response, provider.settings.max_output_tokens)
        cut = cut_calls(output, calls) if incomplete is not None else []
        if len(calls) > 1 and parallel_calls is None:
            raise ValueError("parallel tool output prohibited; retained and stopped")
        if not every_call:
            parallel_run = parallel_run + 1 if len(calls) > 1 else 0
            if parallel_run >= (parallel_calls or {}).get("consecutive_limit", 1):
                outcome = {
                    "status": "STOPPED",
                    "reason": (
                        "provider returned several tool calls on "
                        f"{parallel_run} consecutive turns; retained and stopped"
                    ),
                    "parallel_calls": parallel_calls,
                }
                break
        history.extend(output)
        # The calls this turn runs: all of them under v2, the first otherwise.
        running = calls if every_call else calls[:1]
        refused = [] if every_call else calls[1:]
        if refused:
            # Only the first call runs. Every other one is answered, so the
            # conversation stays well formed, with a refusal that dispatched
            # nothing and consumed no trial slot - and is journalled.
            write_once(
                root / (call_id + "-parallel-refusal.json"),
                canonical(
                    {
                        "schema": "carbon.autoresearch.parallel-refusal.v1",
                        "turn": call_id,
                        "response_digest": digest(canonical(response)),
                        "ran": calls[0].get("call_id"),
                        "refused": [item.get("call_id") for item in refused],
                        "consecutive": parallel_run,
                        "rule": parallel_calls,
                    }
                ),
            )
        # A call with no call_id cannot be answered, and one that runs needs
        # its name: the turn is unrepresentable, so the epoch stops typed,
        # before any call of the turn runs. Retained, never raised.
        malformed = [
            position
            for position, item in enumerate(calls)
            if type(item.get("call_id")) is not str
            or (position < len(running) and type(item.get("name")) is not str)
        ]
        if malformed:
            outcome = {
                "status": "STOPPED",
                "code": TOOL_CALL_MALFORMED,
                "reason": (
                    "provider returned a tool call without a call_id or name; "
                    "retained and stopped"
                ),
                "malformed_calls": malformed,
            }
            break
        for item in refused:
            history.append(
                {
                    "type": "function_call_output",
                    "call_id": item["call_id"],
                    "output": canonical(PARALLEL_REFUSAL).decode(),
                }
            )
        # A reply ended early in which no call that runs was complete - it had
        # none, or every one was cut - did nothing. The first gets a note; the
        # next in a row ends the epoch typed, before anything of it runs (a
        # cut call would only be answered `call_truncated`).
        if incomplete is not None and all(p in cut for p in range(len(running))):
            truncated.append(call_id)
            if len(truncated) >= MAX_TRUNCATED_TURNS:
                outcome = {
                    "status": "STOPPED",
                    "code": REPLIES_TRUNCATED,
                    "reason": (
                        f"the provider ended {len(truncated)} replies in a row "
                        "before any tool call in them was complete; retained "
                        "and stopped"
                    ),
                    "truncated_turns": truncated,
                    "incomplete": incomplete,
                }
                break
        else:
            truncated = []
        if not calls and incomplete is not None:
            # Ended early before any call: not a choice to stop, and no
            # reminder is spent. The note asks the model to continue.
            history.append(
                truncation_note(root, call_id, response, incomplete, cut=[], ran=False)
            )
            continue
        if not calls:
            if stops and reminders < policy["free_text_reminders"]:
                reminders += 1
                correction = {"role": "user", "content": reminder}
                write_once(
                    root / (call_id + "-continuation.json"),
                    canonical(
                        {
                            "policy": policy,
                            "response_digest": digest(canonical(response)),
                            "message": correction,
                        }
                    ),
                )
                history.append(correction)
                continue
            outcome = {
                "status": "STOPPED",
                "reason": (
                    "unstructured agent stop after one clarification"
                    if stops
                    else "agent elected to stop"
                ),
                "agent_output": output,
            }
            break
        if len(running) > 1:
            # The turn's calls and their journal identities, before any runs.
            write_once(
                root / (call_id + "-calls.json"),
                canonical(
                    {
                        "schema": "carbon.autoresearch.turn-calls.v1",
                        "turn": call_id,
                        "response_digest": digest(canonical(response)),
                        "rule": parallel_calls,
                        "calls": [
                            {
                                "call_id": item["call_id"],
                                "name": item["name"],
                                "tool": tool_identity(epoch, index, position, stage),
                            }
                            for position, item in enumerate(running)
                        ],
                    }
                ),
            )
        for position, call in enumerate(running):
            identity = tool_identity(epoch, index, position, stage)
            result = await run_call(
                call, identity, cut=incomplete if position in cut else None
            )
            if result.get("requires_reconciliation"):
                outcome = {
                    "status": "RECONCILIATION_REQUIRED",
                    "reason": "tool dispatch unresolved",
                    "tool": identity,
                }
            elif result.get("status") in terminal or (
                call["name"] == finish_name and result.get("status") == finish_status
            ):
                outcome = result
            if outcome is not None:
                rest = running[position + 1 :]
                if rest:
                    write_once(
                        root / (call_id + "-not-run.json"),
                        canonical(
                            {
                                "schema": "carbon.autoresearch.calls-not-run.v1",
                                "turn": call_id,
                                "ended_by": identity,
                                "ended_with": outcome["status"],
                                "not_run": [
                                    {
                                        "call_id": item["call_id"],
                                        "name": item["name"],
                                        "tool": tool_identity(
                                            epoch, index, position + 1 + offset, stage
                                        ),
                                    }
                                    for offset, item in enumerate(rest)
                                ],
                            }
                        ),
                    )
                break
            history.append(
                {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": canonical(
                        result
                        if challenge is None and not miner
                        else model_view(result)
                    ).decode(),
                }
            )
        if outcome is not None:
            break
        if incomplete is not None:
            history.append(
                truncation_note(
                    root,
                    call_id,
                    response,
                    incomplete,
                    cut=[calls[p]["call_id"] for p in cut if p < len(running)],
                    ran=any(p not in cut for p in range(len(running))),
                )
            )
        if every_call:
            # Any tool call renews the one free-text reminder (LP-PROD-A).
            reminders = 0
    if outcome is None:
        outcome = {"status": "STOPPED", "reason": "epoch provider-call ceiling"}
    turns = session_turns(
        provider_turns(ledger.status(owner=owner)["operations"]), epoch, stage
    )
    report = {
        "schema": "carbon.autoresearch.epoch-outcome.v1",
        "epoch": epoch,
        **outcome,
        "provider_turns": turns,
        "caching": caching_status(turns),
        "accounting": ledger.status(owner=owner),
        "chain_transactions": 0,
    }
    if stage is not None:
        report["stage"] = stage
    if compaction is not None:
        report["compactions"] = compactions
        report["compactions_deferred"] = deferred
    if miner_guidance is not None:
        # The messages this epoch read, bound into its recorded input.
        report["miner_guidance"] = {
            "rule": miner_guidance,
            "chain": guidance_verify(root, plan, stage),
            "read": [
                m["sequence"]
                for path in sorted(root.glob("*" + guidance.RECORD_SUFFIX))
                for m in json.loads(path.read_bytes())["messages"]
            ],
        }
        carried = [
            m["sequence"]
            for path in sorted(root.glob("*" + guidance.RECORD_SUFFIX))
            for m in json.loads(path.read_bytes()).get("carried") or []
        ]
        if "carry_forward_messages" in miner_guidance:
            report["miner_guidance"]["carried"] = carried
    write_once(root / "outcome.json", canonical(report))
    return report
