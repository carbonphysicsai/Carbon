"""Prospective miner orchestration policy; no new execution authority."""

from .profile import canonical, digest
from .research_tools import PROMPT, _schema

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


def binding(policy):
    if policy not in (LEGACY, AUTONOMOUS):
        raise ValueError("unknown research agent policy")
    prompt = PROMPT if policy == LEGACY else AUTONOMOUS_PROMPT
    return {
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
