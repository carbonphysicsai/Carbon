"""Prospective miner orchestration policy; no new execution authority."""

from .burgers_research_prompt import BURGERS_PROMPT as PROMPT
from .contracts import strategy_limits
from .model_provider import DEFAULT_SELECTION
from .profile import canonical, digest
from .research_agent import CONTEXT_RESERVE_TOKENS
from .research_tools import _schema

LEGACY = "carbon.autoresearch.agent-policy.v1"
AUTONOMOUS = "carbon.autoresearch.agent-policy.v2"
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


def argument_limits():
    """The v2 statement of the argument bounds and of what a malformed call
    gets back (a typed refusal, never a stopped epoch)."""
    return (
        f"A tool call's arguments are at most {MAX_TOOL_ARGUMENT_BYTES} bytes of "
        "JSON, and a workspace task's arguments_json at most "
        f"{MAX_WORKSPACE_ARGUMENT_BYTES} bytes. A tool that takes no arguments "
        "takes {}. A malformed call is answered REJECTED_BEFORE_DISPATCH with the "
        "field and the fix; nothing ran, no slot was spent and the epoch goes on."
    )


#: The v2 selection rule (LP-PROD-A): Carbon's own agent selects only a
#: recipe that has a completed practice, the same predicate the trusted
#: controller applies before it submits one.
SELECTION_RULE = (
    "Selection. carbon_autoresearch_select_recipe accepts only a recipe you "
    "practiced to completion in this campaign, exactly as practiced. Any other "
    "is refused with your practiced recipes listed, and the epoch goes on."
)
FREE_TEXT_RULE = (
    "Free text. A turn with no tool call is answered once with a reminder; a "
    "second such turn in a row stops the epoch. Any tool call renews the "
    "reminder."
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
    limits = strategy_limits()
    default = DEFAULT_SELECTION.settings.max_input_tokens
    rules = (
        every_call_per_turn() if v2 else one_call_per_turn(),
        _budget_rule(parallel_calls),
        (
            "Context ceiling. A request is admitted only while its input stays under "
            f"your model's max_input_tokens minus {CONTEXT_RESERVE_TOKENS} tokens "
            f"({default - CONTEXT_RESERVE_TOKENS} tokens at the default {default}). "
            "After the first turn it is measured with the provider's reported input "
            "tokens plus what was added since. Past the ceiling the epoch stops; "
            "history is never silently dropped."
        ),
        _ARGUMENTS + (" " + argument_limits() if v2 else ""),
        *((SELECTION_RULE, FREE_TEXT_RULE) if v2 else ()),
        (
            "Strategy capture limits. A recipe beyond any of these is refused with "
            "strategy.identity_invalid, and check_design names the limit: at most "
            f"{limits.max_object_members} members in any JSON object, "
            f"{limits.max_list_items} items in any list, "
            f"{limits.max_total_value_nodes} values in total, "
            f"{limits.max_string_utf8_bytes} UTF-8 bytes in any string, "
            f"{limits.max_object_key_utf8_bytes} UTF-8 bytes in any object key, and "
            f"{limits.max_strategy_identity_bytes} bytes of canonical strategy "
            "identity."
        ),
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


def binding(policy, challenge=None, parallel_calls=None):
    prompt = prompt_for(policy, challenge, parallel_calls)
    challenge_fields = (
        {}
        if challenge is None
        else {"challenge": {"id": challenge.challenge_id, "version": challenge.version}}
    )
    return {
        **challenge_fields,
        "version": policy,
        "prompt_digest": digest(prompt.encode()),
        "stop_tool_digest": None if policy == LEGACY else digest(canonical(STOP_TOOL)),
        "free_text_reminders": 0 if policy == LEGACY else 1,
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
