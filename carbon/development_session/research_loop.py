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
"""

from __future__ import annotations

import asyncio
import json

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
    FINISH_NOTICE_CALLS,
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
    check_parallel_rule,
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
#:   complete (`cut_calls`), so it did not run.
ARGUMENTS_INVALID = "arguments_invalid"
SELECTION_INVALID = "selection_invalid"
CANDIDATE_INVALID = "candidate_invalid"
SELECTION_NOT_PRACTICED = "selection_not_practiced"
CALL_TRUNCATED = "call_truncated"
REFUSAL_CODES = (
    ARGUMENTS_INVALID,
    SELECTION_INVALID,
    CANDIDATE_INVALID,
    SELECTION_NOT_PRACTICED,
    CALL_TRUNCATED,
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


def tool_identity(epoch, turn, position=0):
    """A tool call's journal identity: the turn's first call keeps the
    historical `epoch-N-tool-NNN`; a later call in the same turn, under
    `PARALLEL_CALLS_V2`, adds its position (`-KK`)."""
    base = f"epoch-{epoch}-tool-{turn:03d}"
    return base if position == 0 else f"{base}-{position:02d}"


def turn_status(
    root, turn, *, calls_left, call_limit, slots_left, trial_limit, unit, offered
):
    """The budget a v2 agent sees before each turn (LP-PROD-A): model calls
    left, counting this turn, and research-trial slots left, with a notice to
    finish at `FINISH_NOTICE_CALLS`. Journalled once, before the request, so
    a replay sends the same request; a later count never rewrites it."""
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
        ways = [
            "select a practiced recipe" if SELECT in offered else None,
            "stop with " + STOP if STOP in offered else None,
        ]
        how = " or ".join(w for w in ways if w) or "finish your work"
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


def _epoch_paths(ledger, epoch):
    if type(epoch) is not int or epoch not in (1, 2):
        raise ValueError("two finite epochs only")
    root = ledger.root / ("epoch-" + str(epoch))
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
    """
    check_parallel_rule(parallel_calls)
    every_call = parallel_calls == PARALLEL_CALLS_V2
    if miner_guidance is not None and miner_guidance not in guidance.RULES:
        raise ValueError("unknown miner guidance rule")
    if miner_guidance is not None and (
        agent_policy != AUTONOMOUS or instructions is not None
    ):
        raise ValueError("miner guidance reaches Carbon's autonomous agent only")
    if (instructions is None) != (tools is None):
        raise ValueError("a role supplies both its instructions and its tools")
    if instructions is not None and (agent_policy != LEGACY or challenge is not None):
        raise ValueError("role instructions run under the legacy policy only")
    if max_provider_calls is not None:
        if instructions is None:
            raise ValueError("only a role's instructions carry their own call cap")
        if type(max_provider_calls) is not int or max_provider_calls < 1:
            raise ValueError("a role's call cap is a positive integer")
    call_limit = (
        MAX_PROVIDER_CALLS if max_provider_calls is None else max_provider_calls
    )
    root = _epoch_paths(ledger, epoch)
    policy = binding(agent_policy, challenge, parallel_calls)
    autonomous = agent_policy == AUTONOMOUS
    if instructions is None:
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
        prompt = instructions
        tools = json.loads(canonical(tools))
    offered = {tool["name"] for tool in tools}
    schemas = {tool["name"]: tool for tool in tools}
    unit = "epoch" if instructions is None else "session"
    # A v2 selection by Carbon's own agent needs a completed practice; a
    # role's caller owns what its selection means.
    select_check = (
        practice_check(ledger, owner) if every_call and instructions is None else None
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
        "max_research_trials": MAX_RESEARCH_TRIALS,
        "rule_change": False,
        "selection_is_final_evidence": False,
    }
    if autonomous:
        plan["agent_policy"] = policy
    if not provider.is_historical_default:
        plan["model_selection"] = provider.record()
    if parallel_calls is not None:
        plan["parallel_calls"] = parallel_calls
    if miner_guidance is not None:
        plan["miner_guidance"] = miner_guidance
    if "research_guidance" in initial_observation:
        plan["effective_input_digest"] = effective_digest(policy, initial_observation)
    write_once(root / "plan.json", canonical(plan))
    start_id = "research-epoch-" + str(epoch)
    admitted = ledger.reserve(
        start_id, owner=owner, phase="selection", request=plan, resources={"epochs": 1}
    )
    if admitted["dispatch"]:
        ledger.finish(
            start_id,
            owner=owner,
            state="SUCCEEDED",
            actual={"epochs": 1},
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
    terminal = {"SELECTED", "STOPPED"} if autonomous else {"SELECTED"}
    # The current turn's trial ceiling; `dispatch` reads it when it runs.
    trial_limit = MAX_RESEARCH_TRIALS

    async def dispatch(name, arguments, identity):
        """One call that leaves this epoch's folder, after its intent."""
        if (
            miner_guidance is not None
            and name == guidance.REPLY
            and guidance.REPLY in offered
        ):
            return guidance.reply(ledger, owner=owner, arguments=arguments)
        numerical = name == PREFIX + "start_research_task" and (
            arguments.get("kind") == "practice"
            or arguments.get("action") in NUMERICAL_ACTIONS
        )
        # Re-read before every numerical call, so a later call in a turn sees
        # the slots the earlier ones spent and a turn cannot overspend.
        if numerical and (
            ledger.status(owner=owner)["used"]["research_trials"] - trial_start
            >= trial_limit
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
        stop = autonomous and call["name"] == STOP and STOP in offered
        select = call["name"] == SELECT and SELECT in offered
        # A rejection, a stop and a selection dispatch nothing outside this
        # folder; each result is a function of the call and the ledger alone.
        # It is computed before the intent is written, and recomputed when an
        # interruption left an intent without a result.
        local = rejection is not None or stop or select
        if intent_file.exists() and not local:
            raise ValueError("tool dispatch incomplete; reconcile without duplication")
        if rejection is not None:
            result = rejection
        elif stop:
            result = stop_result(arguments)
        elif select:
            result = selection_result(arguments, check=select_check)
        ledger.checkpoint()
        write_once(intent_file, canonical(intent))
        if not local:
            result = await dispatch(call["name"], arguments, identity)
        elif result.get("status") == "SELECTED":
            write_once(root / "selected-recipe.json", canonical(result))
        write_once(result_file, canonical(result))
        return result

    for index in range(call_limit):
        ledger.checkpoint()
        status = ledger.status(owner=owner)
        trials = status["used"]["research_trials"] - trial_start
        # Eight per epoch regardless; a miner's budget can only lower it, and
        # its absence is not a reason to invent a different number.
        budgeted = (status.get("budget") or {}).get("research_trials")
        trial_limit = (
            min(MAX_RESEARCH_TRIALS, max(0, budgeted - trial_start))
            if ledger.admission is not None and budgeted is not None
            else MAX_RESEARCH_TRIALS
        )
        call_id = f"epoch-{epoch}-provider-{index:03d}"
        if miner_guidance is not None:
            # The step boundary: read once from the journal, recorded before
            # the request; a replay reads the record, so the turn is the same.
            record = guidance.step(
                ledger,
                owner=owner,
                epoch_root=root,
                turn=call_id,
                rule=miner_guidance,
                previous=guidance_chain,
            )
            guidance_chain = record["chain"]
            message = guidance.for_model(record)
            if message is not None:
                history.append(message)
        if every_call:
            history.append(
                turn_status(
                    root,
                    call_id,
                    calls_left=call_limit - index,
                    call_limit=call_limit,
                    slots_left=max(0, trial_limit - trials),
                    trial_limit=trial_limit,
                    unit=unit,
                    offered=offered,
                )
            )
        effort = provider.settings.reasoning_effort
        request = {
            "model": provider.model_id,
            "instructions": prompt,
            "input": history,
            "tools": tools,
            "parallel_tool_calls": every_call,
            "store": False,
            "max_output_tokens": provider.settings.max_output_tokens,
            "reasoning": None if effort is None else {"effort": effort},
        }
        request_bytes = len(canonical(request))
        if (
            input_token_bound(request_bytes, anchor)
            > provider.settings.max_input_tokens - CONTEXT_RESERVE_TOKENS
        ):
            outcome = {
                "status": "STOPPED",
                "reason": "context admission ceiling; no history silently discarded",
            }
            break
        print(
            f"Research epoch {epoch}: agent call {index + 1}/{call_limit}; trial slots used {trials}/{trial_limit}",
            flush=True,
        )
        phase_path = root / (call_id + "-admission.json")
        if not phase_path.exists():
            write_once(
                phase_path,
                canonical(
                    {"phase": "research" if trials < trial_limit else "selection"}
                ),
            )
        phase = json.loads(phase_path.read_bytes())["phase"]
        # A reply the provider ended early comes back metered (LP-PROD-A).
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
        # The turn's cost, tokens and serving identity, journalled beside the
        # epoch so a view shows spend per turn as it happens.
        turns = provider_turns(ledger.status(owner=owner)["operations"])
        turn = next(t for t in turns if t["turn"] == call_id)
        write_once(root / (call_id + "-turn.json"), canonical(turn))
        if type(turn["input_tokens"]) is int and turn["input_tokens"] >= 0:
            anchor = (turn["input_tokens"], request_bytes)
        caching = caching_status(
            [t for t in turns if t["turn"].startswith(f"epoch-{epoch}-")]
        )
        print(
            f"Research epoch {epoch}: turn {index + 1} charge "
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
            if autonomous and reminders < policy["free_text_reminders"]:
                reminders += 1
                correction = {"role": "user", "content": REMINDER}
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
                    if autonomous
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
                                "tool": tool_identity(epoch, index, position),
                            }
                            for position, item in enumerate(running)
                        ],
                    }
                ),
            )
        for position, call in enumerate(running):
            identity = tool_identity(epoch, index, position)
            result = await run_call(
                call, identity, cut=incomplete if position in cut else None
            )
            if result.get("requires_reconciliation"):
                outcome = {
                    "status": "RECONCILIATION_REQUIRED",
                    "reason": "tool dispatch unresolved",
                    "tool": identity,
                }
            elif result.get("status") in terminal:
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
                                            epoch, index, position + 1 + offset
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
                        result if challenge is None else model_view(result)
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
    turns = [
        t
        for t in provider_turns(ledger.status(owner=owner)["operations"])
        if t["turn"].startswith(f"epoch-{epoch}-")
    ]
    report = {
        "schema": "carbon.autoresearch.epoch-outcome.v1",
        "epoch": epoch,
        **outcome,
        "provider_turns": turns,
        "caching": caching_status(turns),
        "accounting": ledger.status(owner=owner),
        "chain_transactions": 0,
    }
    if miner_guidance is not None:
        # The messages this epoch read, bound into its recorded input.
        report["miner_guidance"] = {
            "rule": miner_guidance,
            "chain": guidance.verify(root, plan),
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
