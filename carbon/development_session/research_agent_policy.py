"""Prospective miner orchestration policy; no new execution authority."""

from .burgers_research_prompt import BURGERS_PROMPT as PROMPT
from .contracts import strategy_limits
from .model_provider import DEFAULT_SELECTION
from .profile import canonical, digest
from .research_agent import CONTEXT_RESERVE_TOKENS
from .research_tools import _schema

LEGACY = "carbon.autoresearch.agent-policy.v1"
AUTONOMOUS = "carbon.autoresearch.agent-policy.v2"
#: The Graphite miner edition's policy (OWNER-GRAPHITE-MINER-01): a closed
#: role's own instructions and tools, which may run with a Challenge, under
#: `PARALLEL_CALLS_V2`. As for Carbon's autonomous agent, a Challenge result
#: reaches the model as `research_loop.model_view` shows it, a selection needs
#: a completed practice (`research_loop.practice_check`), the stop tool ends
#: the session, one free-text reminder is given (renewed by any tool call) and
#: the miner's messages are read (`miner_guidance`). The loop states its
#: operating rules after the role's instructions (`graphite_miner_rules`).
GRAPHITE_MINER = "carbon.autoresearch.agent-policy.graphite-miner.v1"
POLICIES = (LEGACY, AUTONOMOUS, GRAPHITE_MINER)
STOP = "carbon_autoresearch_stop"
REASONS = (
    "budget",
    "plateau",
    "no_feasible_action",
    "unresolved_failure",
    "cancellation",
)
#: How the loop treats a provider that returns several tool calls in one turn
#: despite `parallel_tool_calls: false` (owner decision, 28 September 2026).
#: A campaign freezes this in its provider plan; one frozen before it existed
#: has no such field and keeps the historical rule - such output stops the
#: epoch - so its retained turns keep the meaning they were recorded with.
PARALLEL_CALLS = {
    "schema": "carbon.autoresearch.parallel-calls.v1",
    "rule": "FIRST_RUN_REST_REFUSED",
    "consecutive_limit": 3,
}
#: The rule new campaigns freeze from 3 October 2026 (OWNER-LAUNCHPAD-PROD-01,
#: LP-PROD-A). Every function call of a turn runs, one after another in the
#: model's order, each journalled before and after dispatch as a single call
#: is; the request allows parallel tool calls and there is no consecutive-turn
#: stop. A call that ends the epoch (a selection, a stop) or needs
#: reconciliation ends it at once, and the turn's later calls are journalled
#: as not run. A plan frozen under `PARALLEL_CALLS`, or under no rule, keeps
#: its own rule and replays byte-identically.
PARALLEL_CALLS_V2 = {
    "schema": "carbon.autoresearch.parallel-calls.v2",
    "rule": "EVERY_CALL_RUN_IN_ORDER",
}
#: Every rule a campaign may freeze. None, the historical rule, is the absence
#: of a frozen rule rather than a member.
PARALLEL_CALL_RULES = (PARALLEL_CALLS, PARALLEL_CALLS_V2)
PARALLEL_REFUSAL = {
    "status": "REFUSED_NOT_RUN",
    "reason": (
        "One tool call per turn: only the first call in this turn ran. "
        "Call this one again in a later turn if you still need it."
    ),
    "authority_granted": False,
}
#: An epoch's model calls and research-trial slots; the loop enforces these.
MAX_PROVIDER_CALLS = 48
MAX_RESEARCH_TRIALS = 8
#: The argument bounds a v2 agent is told: a tool call's JSON arguments
#: (`research_tools._json`) and a workspace task's `arguments_json`
#: (`carbon.research.model`). They are stated here, not enforced here; the
#: tests check each against the code that enforces it.
MAX_TOOL_ARGUMENT_BYTES = 16384
MAX_WORKSPACE_ARGUMENT_BYTES = 12288
#: Model calls left, counting the next one, at which a v2 agent is told to
#: finish (OWNER-LAUNCHPAD-PROD-01: it should be able to select or stop
#: rather than run out).
FINISH_NOTICE_CALLS = 2

#: Tunable limits (OWNER-GRAPHITE-MINER-01, item 6: "generous and tunable
#: limits"; money and time are the limits, not call counts). A session that
#: freezes this rule has no per-epoch model-call or research-trial cap unless
#: one is set here; `None` means only the campaign ledger's own ceilings bind
#: (provider spend, provider calls, research trials, elapsed time). The loop
#: stays finite through the ledger: a session with no per-epoch call cap
#: needs a finite provider_attempts ceiling, or a provider_nanodollars one
#: with a priced selection, and refuses to start otherwise. A plan frozen
#: without the rule keeps `MAX_PROVIDER_CALLS` and `MAX_RESEARCH_TRIALS`
#: exactly. This is the generous default; `limits_v2` sets the optional caps.
LIMITS_V2 = {
    "schema": "carbon.autoresearch.limits.v2",
    "calls_per_epoch": None,
    "trials_per_epoch": None,
}
#: The largest optional cap a limits rule takes; a cap is a bound, not a
#: target, so this only refuses nonsense.
MAX_TUNABLE_CAP = 100000


def limits_v2(calls_per_epoch=None, trials_per_epoch=None):
    """A `LIMITS_V2` rule with the optional per-epoch caps set."""
    return check_limits(
        {
            **LIMITS_V2,
            "calls_per_epoch": calls_per_epoch,
            "trials_per_epoch": trials_per_epoch,
        }
    )


def check_limits(limits):
    """A frozen limits rule: `LIMITS_V2`'s schema, a model-call cap that is
    None or 1 to `MAX_TUNABLE_CAP`, and a trial cap that is None or 0 to
    `MAX_TUNABLE_CAP`."""
    if (
        type(limits) is not dict
        or set(limits) != set(LIMITS_V2)
        or limits["schema"] != LIMITS_V2["schema"]
    ):
        raise ValueError("unknown limits rule")
    for key, low in (("calls_per_epoch", 1), ("trials_per_epoch", 0)):
        value = limits[key]
        if value is not None and (
            type(value) is not int or not low <= value <= MAX_TUNABLE_CAP
        ):
            raise ValueError(
                f"{key} is null or a whole number from {low} to {MAX_TUNABLE_CAP}"
            )
    return limits


#: Explicit, recorded context compaction (OWNER-GRAPHITE-MINER-01, item 6), a
#: versioned rule for new runs; a plan without it keeps the historical stop at
#: the context ceiling. When a turn's request would pass `trigger_fraction` of
#: the admission ceiling (the model's max_input_tokens minus
#: `CONTEXT_RESERVE_TOKENS`) while the conversation holds more than
#: `keep_last_turns` turns, the loop makes one journalled model call asking
#: for a summary in a closed schema (`COMPACTION_TOOL`), then continues with
#: the initial observation, that summary - labelled as the model's own
#: summary - and the last `keep_last_turns` turns. The compaction call is
#: metered and replayed like any model call, its record names what left the
#: context, and nothing is dropped silently.
COMPACTION_V1 = {
    "schema": "carbon.autoresearch.compaction.v1",
    "trigger_fraction": 0.85,
    "keep_last_turns": 6,
}
COMPACTION_RULES = (COMPACTION_V1,)
COMPACT = "carbon_autoresearch_compact_context"
#: The closed summary schema: every field is text.
COMPACTION_FIELDS = (
    "findings",
    "open_hypotheses",
    "best_recipes",
    "constraints",
    "next_steps",
)
#: The most a summary holds, in characters over all fields: a summary has to
#: fit the context headroom the trigger leaves.
COMPACTION_SUMMARY_CHARACTERS = 12000
#: Compaction calls per compaction: the request, and one firmer request when
#: the first reply recorded no valid summary. Then the session stops typed.
COMPACTION_ATTEMPTS = 2
COMPACTION_TOOL = {
    "type": "function",
    "name": COMPACT,
    "strict": True,
    "description": (
        "Only when Carbon asks you to compact the context: record your own "
        "summary of the conversation so far - findings, open hypotheses, best "
        "recipes (exact JSON where you have them), constraints and next steps - "
        f"at most {COMPACTION_SUMMARY_CHARACTERS} characters in all. Carbon then "
        "continues with the initial observation, this summary and your last "
        "turns. At any other time it is refused and nothing happens."
    ),
    "parameters": _schema({field: {"type": "string"} for field in COMPACTION_FIELDS}),
}


def check_compaction(rule):
    """A frozen compaction rule is one of `COMPACTION_RULES`, exactly: the
    same canonical bytes, so 6.0 is not 6."""
    if type(rule) is not dict or canonical(rule) not in {
        canonical(known) for known in COMPACTION_RULES
    }:
        raise ValueError("unknown context compaction rule")
    return rule


def check_parallel_rule(rule):
    """A frozen parallel-call rule is one of `PARALLEL_CALL_RULES`, or None."""
    if rule is not None and rule not in PARALLEL_CALL_RULES:
        raise ValueError("unknown parallel tool call rule")
    return rule


def one_call_per_turn(unit="epoch"):
    """`PARALLEL_CALLS` as an agent is told it. `unit` names what stops: the
    epoch here, the session for a Graphite role (GRAPHITE-D33)."""
    return (
        "One tool call per turn. If you return several, only the first runs; "
        "every other one is answered REFUSED_NOT_RUN and did not happen. After "
        f"{PARALLEL_CALLS['consecutive_limit']} consecutive turns with several "
        f"calls, the {unit} stops."
    )


def every_call_per_turn(unit="epoch"):
    """`PARALLEL_CALLS_V2` as an agent is told it. `unit` names what ends: the
    epoch for Carbon's agent, the session for a Graphite role."""
    return (
        "Several tool calls per turn. Every call you return in one turn runs, one "
        "after another in the order you returned them, and each is answered; a "
        "later call sees what the earlier ones spent. A call that ends the "
        f"{unit}, such as a selection, ends it at once, and so does a call whose "
        "outcome needs reconciliation: the calls after it in that turn do not run "
        "and are recorded as not run. All the calls of one turn share that turn's "
        "one model call."
    )


def _budget_rule(rule):
    if rule != PARALLEL_CALLS_V2:
        return (
            f"Budget. This epoch allows {MAX_PROVIDER_CALLS} model calls, and every "
            "turn spends one, whatever it does, including a refused call. Starting a "
            f"practice or run_python task spends one of {MAX_RESEARCH_TRIALS} "
            "research-trial slots (fewer if the miner set a lower budget). A request "
            "refused before any task starts spends no slot."
        )
    return (
        f"Budget. This epoch allows {MAX_PROVIDER_CALLS} model calls, and every "
        "turn spends one, whatever it does and however many tool calls it "
        "carries. Starting a practice, run_python or run_julia task spends one of "
        f"{MAX_RESEARCH_TRIALS} research-trial slots (fewer if the miner set a lower "
        "budget). A request refused before any task starts spends no slot. Before "
        "every turn Carbon tells you the model calls and trial slots left; with "
        f"{FINISH_NOTICE_CALLS} model calls left it says so, so you can select or "
        "stop before they run out."
    )


_ARGUMENTS = (
    'Arguments. null means JSON null (unquoted), never the string "null". '
    "A field ending in _json is a string holding encoded JSON, for "
    'example arguments_json: "{\\"name\\":\\"objective\\"}", never a '
    "JSON object. A refused argument names the field that broke the "
    "contract."
)


def argument_limits(unit="epoch"):
    """The v2 statement of the argument bounds and of what a malformed call
    gets back (a typed refusal, never a stopped epoch). `unit` names what
    goes on: the epoch, or a role's session."""
    return (
        f"A tool call's arguments are at most {MAX_TOOL_ARGUMENT_BYTES} bytes of "
        "JSON, and a workspace task's arguments_json at most "
        f"{MAX_WORKSPACE_ARGUMENT_BYTES} bytes. A tool that takes no arguments "
        "takes {}. A malformed call is answered REJECTED_BEFORE_DISPATCH with the "
        f"field and the fix; nothing ran, no slot was spent and the {unit} goes on."
    )


def selection_rule(unit="epoch"):
    """The v2 selection rule (LP-PROD-A): the agent selects only a recipe
    that has a completed practice, the same predicate the trusted controller
    applies before it submits one."""
    return (
        "Selection. carbon_autoresearch_select_recipe accepts only a recipe you "
        "practiced to completion in this campaign, exactly as practiced. Any other "
        f"is refused with your practiced recipes listed, and the {unit} goes on."
    )


def free_text_rule(unit="epoch"):
    """The renewed free-text reminder, as the agent is told it."""
    return (
        "Free text. A turn with no tool call is answered once with a reminder; a "
        f"second such turn in a row stops the {unit}. Any tool call renews the "
        "reminder."
    )


SELECTION_RULE = selection_rule()
FREE_TEXT_RULE = free_text_rule()


def capture_limits_rule():
    """The strategy capture limits, from the values that enforce them."""
    limits = strategy_limits()
    return (
        "Strategy capture limits. A recipe beyond any of these is refused with "
        "strategy.identity_invalid, and check_design names the limit: at most "
        f"{limits.max_object_members} members in any JSON object, "
        f"{limits.max_list_items} items in any list, "
        f"{limits.max_total_value_nodes} values in total, "
        f"{limits.max_string_utf8_bytes} UTF-8 bytes in any string, "
        f"{limits.max_object_key_utf8_bytes} UTF-8 bytes in any object key, and "
        f"{limits.max_strategy_identity_bytes} bytes of canonical strategy "
        "identity."
    )


def context_rule(unit="epoch"):
    """The context admission ceiling with no compaction rule: past it the
    epoch (or session) stops."""
    default = DEFAULT_SELECTION.settings.max_input_tokens
    return (
        "Context ceiling. A request is admitted only while its input stays under "
        f"your model's max_input_tokens minus {CONTEXT_RESERVE_TOKENS} tokens "
        f"({default - CONTEXT_RESERVE_TOKENS} tokens at the default {default}). "
        "After the first turn it is measured with the provider's reported input "
        f"tokens plus what was added since. Past the ceiling the {unit} stops; "
        "history is never silently dropped."
    )


def compaction_rule(compaction, unit="session"):
    """`COMPACTION_V1` as the agent is told it, from the values that enforce
    it."""
    check_compaction(compaction)
    percent = round(compaction["trigger_fraction"] * 100)
    kept = compaction["keep_last_turns"]
    return (
        "Context and compaction. A request is admitted only while its input stays "
        f"under your model's max_input_tokens minus {CONTEXT_RESERVE_TOKENS} tokens, "
        "measured after the first turn with the provider's reported input tokens "
        f"plus what was added since. When a request would pass {percent}% of that "
        f"ceiling while the conversation holds more than {kept} turns, Carbon asks "
        f"you to compact: call {COMPACT}, and only it, with your summary "
        "of findings, open hypotheses, best recipes, constraints and next steps, at "
        f"most {COMPACTION_SUMMARY_CHARACTERS} characters in all. That call is one "
        "model call. Carbon then continues with the initial observation, your "
        f"summary, labelled as your summary, and the last {kept} turns unchanged; "
        "the earlier turns leave your context but stay in Carbon's record. Call "
        f"{COMPACT} only when asked; at any other time it is refused and nothing "
        f"happens. If no valid summary is recorded after {COMPACTION_ATTEMPTS} "
        f"requests, or a request cannot fit under the ceiling, the {unit} stops; "
        "history is never silently dropped."
    )


def limits_rule(limits, unit="session", *, compaction=False):
    """The budget an agent is told under a limits rule (`LIMITS_V2`), or the
    historical per-epoch caps when `limits` is None, from the values that
    enforce it."""
    if limits is None:
        calls, trials = MAX_PROVIDER_CALLS, MAX_RESEARCH_TRIALS
        lead = (
            f"Budget. This {unit} allows {calls} model calls and {trials} "
            "research-trial slots (fewer if the miner set a lower budget), "
            "within the miner's own campaign ceilings."
        )
    else:
        check_limits(limits)
        calls, trials = limits["calls_per_epoch"], limits["trials_per_epoch"]
        lead = (
            "Budget. Money and time are your limits: the miner's own campaign "
            "ceilings on provider spend, provider calls, research trials and "
            f"elapsed time bind this {unit}. "
            + (
                f"There is no separate per-{unit} model-call cap"
                if calls is None
                else f"This {unit} also allows at most {calls} model calls"
            )
            + (
                f" and no separate per-{unit} research-trial cap."
                if trials is None
                else f" and at most {trials} research-trial slots."
            )
        )
    return lead + (
        " Every turn spends one model call, whatever it does and however many "
        "tool calls it carries"
        + (", and so does each compaction request" if compaction else "")
        + ". Starting a practice, run_python or run_julia task spends one "
        "research trial. A request refused before any task starts spends no "
        "trial. Before every turn Carbon tells you what is left; when at most "
        f"{FINISH_NOTICE_CALLS} model calls are left, or the campaign budget "
        f"guarantees at most {FINISH_NOTICE_CALLS} more, it says so, so you can "
        "finish before they run out."
    )


def operating_rules(parallel_calls=None):
    """Every operating rule an agent can otherwise only discover by breaking
    it, built from the values that enforce each one
    (OWNER-BATTERY-V2-DISCLOSURE-01, items 3-6: "Give it everything it needs
    to know"). Operating rules only: no exam material.

    `parallel_calls` is the campaign's frozen rule. Under `PARALLEL_CALLS_V2`
    the rules state that rule, the argument bounds, the per-turn budget
    status, the selection rule and the renewed reminder (LP-PROD-A). Under
    `PARALLEL_CALLS` or no rule the text is the historical one, byte for byte.
    """
    v2 = check_parallel_rule(parallel_calls) == PARALLEL_CALLS_V2
    rules = (
        every_call_per_turn() if v2 else one_call_per_turn(),
        _budget_rule(parallel_calls),
        context_rule(),
        _ARGUMENTS + (" " + argument_limits() if v2 else ""),
        *((SELECTION_RULE, FREE_TEXT_RULE) if v2 else ()),
        capture_limits_rule(),
        (
            "Priors. No prior pack is registered in this profile. get_prior takes no "
            "selector and returns no prior, and inspect_prior_alignment has nothing "
            "to align with; neither is worth a call."
        ),
    )
    return (
        "\nOperating rules. These are all of Carbon's rules for this session, "
        "stated so you never have to discover one by breaking it.\n"
        + "".join("- " + rule + "\n" for rule in rules)
    )


REMINDER = (
    "This is an already authorized autonomous campaign, not an interactive planning "
    "consultation. Continue with a feasible research tool, select a practiced recipe, "
    "or call carbon_autoresearch_stop with the observed reason and evidence. "
    "No additional permission for an in-scope trial is needed. You may stop without "
    "a trial or improvement; do not invent results. This is the only reminder."
)
AUTONOMOUS_PROMPT = PROMPT + """

Execution direction: the owner already authorized this finite campaign and its
ordinary in-scope experiments. Do the research now. Do not ask the owner to pick
hyperparameters, approve a practice run, or confirm continuation. The supplied
initial observation already includes the public objective, catalog and control;
use discovery only for information you still need. Record a concise testable plan,
then execute a useful short practice trial, inspect its measured results and
decide whether to revise, deepen, abandon, select or stop. Choose the recipe and
screening duration yourself under the existing admission controls. A plan or
data download alone is not a completed research objective.

The practice service obtains its registered public training and validation data;
separate public_material requests are optional when you want to inspect those
files. Static resource inspection is not a guarantee of dynamic completion.
Do not compare a trial with an unexecuted scaffold as if the scaffold was measured.

Finish using carbon_autoresearch_select_recipe for a practiced candidate or
carbon_autoresearch_stop for budget, plateau, no feasible action, unresolved
failure or cancellation. Explain the observed evidence and remaining uncertainty.
The stop explanation is your report, not verified scientific evidence. You may
stop immediately for a real constraint. Do not run pointless trials or fabricate
a winner. Free text alone receives one clarification, then a recorded protocol
stop; it never grants more calls, trials, time, money or authority.
"""
#: The autonomous policy's prompt for a Challenge other than Burgers. Same
#: execution direction and stop discipline; the task statement comes from the
#: Challenge's own discovery document in the initial observation, not from
#: text written for Burgers.
_CHALLENGE_TASK = """You are an authenticated Carbon DEVELOPMENT miner researcher.
The initial observation names the Challenge and gives its discovery document:
the task, interface, public material, rebuildable model families and controls,
limits, exam rule and the feedback you may receive. Treat that document as the
Challenge's definition; do not assume another Challenge's task, model family,
metrics or rules. Your job is to learn a stronger reconstructable recipe, not
just make a valid submission.

A recipe is declarative JSON: schema_version, challenge_id, backbone and
parameters. Carbon rebuilds it itself, with its own seed, through the
Challenge's approved runtime on the public TRAIN data. You never supply model
weights, predictions, reference labels or code that runs at evaluation. A model
that calls or reuses the Challenge's reference solver is not a submission. The
public TRAIN data itself is yours to study. A capability the discovery document
lists as unsupported, or a backend it does not name, requires a
capability_request (its reason is one of missing_adapter, missing_data_support,
resource_ceiling, host_limitation, contract_incompatibility or
prohibited_authority_or_data); never disguise it as a supported family.

Use the twelve namespaced research functions. A field whose name ends in _json
carries a JSON object encoded as a string, never the object itself. Workspace actions: public_material (objective,
capabilities, training_data, practice_data, reference_method), check_design
(can I submit this?), roadmap, notebook, capability_request, run_python. Before
every materially new trial state a falsifiable hypothesis and expected effect.
Practice runs your recipe on public PRACTICE cases and returns service-produced
diagnostics; it is adaptive public evidence, not the exam. The exam is private
and independent: you never see its cases, references or seeds, and you must
not seek them. The scientific rule stays fixed.

Execution direction: the owner already authorized this finite campaign and its
ordinary in-scope experiments. Do the research now. Do not ask for approval.
Record a concise testable plan, run a useful short practice, inspect measured
results and decide whether to revise, deepen, abandon, select or stop. If work
is running the supervisor waits; do not repeatedly poll it. Do not ask for repository, evaluator, wallet
or credential access.

Finish using carbon_autoresearch_select_recipe for a recipe you actually
practiced, or carbon_autoresearch_stop for budget, plateau, no feasible action,
unresolved failure or cancellation. Explain the observed evidence and remaining
uncertainty. You may stop without a trial or an improvement; do not run
pointless trials or fabricate a winner. Free text alone receives one
clarification, then a recorded protocol stop; it never grants more calls,
trials, time, money or authority. No chain writes, payment, reward or
scientific qualification occur in this campaign.
"""
#: The prompt a campaign frozen under `PARALLEL_CALLS` or no rule runs with,
#: byte for byte as before LP-PROD-A.
CHALLENGE_PROMPT = _CHALLENGE_TASK + operating_rules()
#: The prompt a campaign frozen under `PARALLEL_CALLS_V2` runs with: the same
#: task, with the v2 operating rules.
CHALLENGE_PROMPT_V2 = _CHALLENGE_TASK + operating_rules(PARALLEL_CALLS_V2)


def burgers_v2_rules(policy):
    """The v2 rules a historical Burgers prompt gains when a campaign freezes
    `PARALLEL_CALLS_V2`. The Burgers prompts state no operating rules of their
    own, so only what v2 changes is added: the call rule, the budget status,
    the argument bounds, the selection rule and, for the autonomous policy,
    the renewed reminder."""
    rules = (
        every_call_per_turn(),
        _budget_rule(PARALLEL_CALLS_V2),
        argument_limits(),
        SELECTION_RULE,
        *((FREE_TEXT_RULE,) if policy == AUTONOMOUS else ()),
    )
    return "\nOperating rules for tool calls.\n" + "".join(
        "- " + rule + "\n" for rule in rules
    )


STOP_TOOL = {
    "type": "function",
    "name": STOP,
    "strict": True,
    "description": "End this epoch without a candidate. Give the observed stop reason and supporting public/own evidence; stopping without improvement is allowed.",
    "parameters": _schema(
        {
            "reason": {"type": "string", "enum": list(REASONS)},
            "evidence": {"type": "string"},
            "used_feedback": {"type": "boolean"},
        }
    ),
}


def prompt_for(policy, challenge=None, parallel_calls=None):
    """The prompt a policy runs with. `challenge` is None for the historical
    Burgers campaign, whose prompts are unchanged; any other Challenge runs
    only under the autonomous policy, with the Challenge-neutral prompt.

    `parallel_calls` is the campaign's frozen rule. `PARALLEL_CALLS_V2` states
    the v2 rules (LP-PROD-A); `PARALLEL_CALLS` and None return the prompt a
    campaign frozen under them recorded, byte for byte."""
    if policy not in (LEGACY, AUTONOMOUS):
        raise ValueError("unknown research agent policy")
    v2 = check_parallel_rule(parallel_calls) == PARALLEL_CALLS_V2
    if challenge is None:
        prompt = PROMPT if policy == LEGACY else AUTONOMOUS_PROMPT
        return prompt + burgers_v2_rules(policy) if v2 else prompt
    if policy != AUTONOMOUS:
        raise ValueError("only the autonomous policy serves another Challenge")
    return CHALLENGE_PROMPT_V2 if v2 else CHALLENGE_PROMPT


def _challenge_fields(challenge):
    return (
        {}
        if challenge is None
        else {"challenge": {"id": challenge.challenge_id, "version": challenge.version}}
    )


def binding(policy, challenge=None, parallel_calls=None):
    prompt = prompt_for(policy, challenge, parallel_calls)
    challenge_fields = _challenge_fields(challenge)
    return {
        **challenge_fields,
        "version": policy,
        "prompt_digest": digest(prompt.encode()),
        "stop_tool_digest": None if policy == LEGACY else digest(canonical(STOP_TOOL)),
        "free_text_reminders": 0 if policy == LEGACY else 1,
        "changed_scientific_rule": False,
    }


# -- the Graphite miner edition's policy (OWNER-GRAPHITE-MINER-01) ------------


def _either(items, word):
    """A list in prose: one item, "a or b", or "a, b or c"."""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {word} " + items[-1]


def graphite_miner_rules(
    *, limits=None, compaction=None, select=False, stop=False, finish=None
):
    """The operating rules the loop states after a Graphite miner role's own
    instructions, built from the values that enforce each one, as
    `operating_rules` does for Carbon's autonomous agent. Every miner role
    runs under `PARALLEL_CALLS_V2` and its unit is the session.

    `select`, `stop` and `finish` (a finish tool's name, or None) say which
    ways to end the session the role offers."""
    unit = "session"
    ways = [
        *(("select a practiced recipe",) if select else ()),
        *((f"finish with {finish}",) if finish else ()),
        *((f"stop with {STOP}",) if stop else ()),
    ]
    rules = (
        every_call_per_turn(unit),
        limits_rule(limits, unit, compaction=compaction is not None),
        context_rule(unit) if compaction is None else compaction_rule(compaction),
        _ARGUMENTS + " " + argument_limits(unit),
        *((selection_rule(unit),) if select else ()),
        free_text_rule(unit),
        *(
            (
                "Ending. The session ends when you "
                + _either(ways, "or")
                + "; a malformed ending call is refused and the session goes on.",
            )
            if ways
            else ()
        ),
        capture_limits_rule(),
    )
    return (
        "\nOperating rules. These are all of Carbon's rules for this session, "
        "stated so you never have to discover one by breaking it.\n"
        + "".join("- " + rule + "\n" for rule in rules)
    )


def graphite_miner_prompt(
    instructions,
    *,
    limits=None,
    compaction=None,
    select=False,
    stop=False,
    finish=None,
):
    """The prompt a Graphite miner role runs with: the role's own
    instructions, then `graphite_miner_rules`. The plan records it and its
    policy binding records both digests (`graphite_miner_binding`)."""
    if type(instructions) is not str or not instructions:
        raise ValueError("role instructions are a non-empty string")
    return instructions + graphite_miner_rules(
        limits=limits, compaction=compaction, select=select, stop=stop, finish=finish
    )


def graphite_miner_reminder(*, select=False, stop=False, finish=None):
    """The one free-text reminder of a Graphite miner role, naming only the
    ways to continue or end that the role offers."""
    ways = [
        "Continue with a feasible tool call",
        *(("select a practiced recipe",) if select else ()),
        *((f"finish with {finish}",) if finish else ()),
        *((f"call {STOP} with the observed reason and evidence",) if stop else ()),
    ]
    return (
        "This is a campaign the miner already authorized and launched, not an "
        f"interactive consultation. {_either(ways, 'or')}. No additional permission for an "
        "in-scope step is needed. You may end without a trial or an improvement; "
        "do not invent results. This is the only reminder until your next tool "
        "call; another turn with no tool call ends the session."
    )


def graphite_miner_binding(prompt, instructions, reminder, challenge=None):
    """The policy record a Graphite miner role's epoch plan carries: the full
    prompt's digest, the role instructions' own digest, the stop tool, the
    one reminder and its digest, and the Challenge when there is one."""
    return {
        **_challenge_fields(challenge),
        "version": GRAPHITE_MINER,
        "prompt_digest": digest(prompt.encode()),
        "instructions_digest": digest(instructions.encode()),
        "stop_tool_digest": digest(canonical(STOP_TOOL)),
        "free_text_reminders": 1,
        "reminder_digest": digest(reminder.encode()),
        "changed_scientific_rule": False,
    }


def stop_result(arguments):
    if (
        type(arguments) is not dict
        or set(arguments) != {"reason", "evidence", "used_feedback"}
        or type(arguments["reason"]) is not str
        or arguments["reason"] not in REASONS
        or type(arguments["evidence"]) is not str
        or not 1 <= len(arguments["evidence"].strip()) <= 4096
        or type(arguments["used_feedback"]) is not bool
    ):
        return {
            "status": "REJECTED_BEFORE_DISPATCH",
            "reason": "closed stop reason, nonempty evidence and feedback flag required",
            "authority_granted": False,
        }
    return {
        "status": "STOPPED",
        "reason": "agent reported " + arguments["reason"],
        "stop_evidence": arguments["evidence"],
        "used_feedback": arguments["used_feedback"],
        "evidence_basis": "AGENT_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
        "final_evidence": False,
    }
