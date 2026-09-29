"""Prospective miner orchestration policy; no new execution authority."""

from .burgers_research_prompt import BURGERS_PROMPT as PROMPT
from .contracts import strategy_limits
from .model_provider import DEFAULT_SELECTION
from .profile import canonical, digest
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
#: Input tokens held back from the model's max_input_tokens for its reply.
CONTEXT_RESERVE_TOKENS = 4096


def operating_rules():
    """Every operating rule an agent can otherwise only discover by breaking
    it, built from the values that enforce each one
    (OWNER-BATTERY-V2-DISCLOSURE-01, items 3-6: "Give it everything it needs
    to know"). Operating rules only: no exam material."""
    limits = strategy_limits()
    default = DEFAULT_SELECTION.settings.max_input_tokens
    rules = (
        (
            "One tool call per turn. If you return several, only the first runs; "
            "every other one is answered REFUSED_NOT_RUN and did not happen. After "
            f"{PARALLEL_CALLS['consecutive_limit']} consecutive turns with several "
            "calls, the epoch stops."
        ),
        (
            f"Budget. This epoch allows {MAX_PROVIDER_CALLS} model calls, and every "
            "turn spends one, whatever it does, including a refused call. Starting a "
            f"practice or run_python task spends one of {MAX_RESEARCH_TRIALS} "
            "research-trial slots (fewer if the miner set a lower budget). A request "
            "refused before any task starts spends no slot."
        ),
        (
            "Context ceiling. A request is admitted only while its input stays under "
            f"your model's max_input_tokens minus {CONTEXT_RESERVE_TOKENS} tokens "
            f"({default - CONTEXT_RESERVE_TOKENS} tokens at the default {default}). "
            "After the first turn it is measured with the provider's reported input "
            "tokens plus what was added since. Past the ceiling the epoch stops; "
            "history is never silently dropped."
        ),
        (
            'Arguments. null means JSON null (unquoted), never the string "null". A '
            "refused argument names the field that broke the contract."
        ),
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
AUTONOMOUS_PROMPT = (
    PROMPT
    + """

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
)
#: The autonomous policy's prompt for a Challenge other than Burgers. Same
#: execution direction and stop discipline; the task statement comes from the
#: Challenge's own discovery document in the initial observation, not from
#: text written for Burgers.
CHALLENGE_PROMPT = """You are an authenticated Carbon DEVELOPMENT miner researcher.
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

Use the twelve namespaced research functions. JSON-string fields contain
ordinary JSON objects. Workspace actions: public_material (objective,
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
""" + operating_rules()
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


def prompt_for(policy, challenge=None):
    """The prompt a policy runs with. `challenge` is None for the historical
    Burgers campaign, whose prompts are unchanged; any other Challenge runs
    only under the autonomous policy, with the Challenge-neutral prompt."""
    if policy not in (LEGACY, AUTONOMOUS):
        raise ValueError("unknown research agent policy")
    if challenge is None:
        return PROMPT if policy == LEGACY else AUTONOMOUS_PROMPT
    if policy != AUTONOMOUS:
        raise ValueError("only the autonomous policy serves another Challenge")
    return CHALLENGE_PROMPT


def binding(policy, challenge=None):
    prompt = prompt_for(policy, challenge)
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
