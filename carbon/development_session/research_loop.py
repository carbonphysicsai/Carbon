"""Finite, durable model-backed research epoch; no numerical or chain shortcuts.

The selected recipe is frozen here. A separate trusted controller performs the
registered authenticated final submission. Selection is not final evidence.
"""

from __future__ import annotations

import asyncio
import json

from carbon.reconstruction.capability_registry import contract_digest

from .data import write_once
from .model_provider import DEFAULT_SELECTION
from .profile import CHALLENGE, canonical, digest
from .research_agent import request_model
from .research_agent_policy import (
    AUTONOMOUS,
    LEGACY,
    REMINDER,
    STOP,
    STOP_TOOL,
    binding,
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
):
    """Run once or resume completed provider/tool observations without resends.

    `provider` is the campaign's model selection (`model_provider`); the
    historical pinned selection produces the same plan and requests as before
    selection existed.

    An interrupted tool with unknown side effects stops for reconciliation.
    Successfully journalled replies can be replayed without another model call.
    """
    root = _epoch_paths(ledger, epoch)
    policy = binding(agent_policy, challenge)
    autonomous = agent_policy == AUTONOMOUS
    prompt = prompt_for(agent_policy, challenge)
    tools = tools_for_sdk(sdk) + [SELECTION_TOOL] + ([STOP_TOOL] if autonomous else [])
    plan = {
        "schema": "carbon.autoresearch.epoch-plan.v1",
        "epoch": epoch,
        "owner": owner,
        "model": provider.model_id,
        "prompt": prompt,
        "tools": tools,
        "initial_observation": initial_observation,
        "max_provider_calls": 48,
        "max_research_trials": 8,
        "rule_change": False,
        "selection_is_final_evidence": False,
    }
    if autonomous:
        plan["agent_policy"] = policy
    if not provider.is_historical_default:
        plan["model_selection"] = provider.record()
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
    for index in range(48):
        ledger.checkpoint()
        status = ledger.status(owner=owner)
        trials = status["used"]["research_trials"] - trial_start
        # Eight per epoch regardless; a miner's budget can only lower it, and
        # its absence is not a reason to invent a different number.
        budgeted = (status.get("budget") or {}).get("research_trials")
        trial_limit = (
            min(8, max(0, budgeted - trial_start))
            if ledger.admission is not None and budgeted is not None
            else 8
        )
        call_id = f"epoch-{epoch}-provider-{index:03d}"
        effort = provider.settings.reasoning_effort
        request = {
            "model": provider.model_id,
            "instructions": prompt,
            "input": history,
            "tools": tools,
            "parallel_tool_calls": False,
            "store": False,
            "max_output_tokens": provider.settings.max_output_tokens,
            "reasoning": None if effort is None else {"effort": effort},
        }
        if len(canonical(request)) > provider.settings.max_input_tokens - 4096:
            outcome = {
                "status": "STOPPED",
                "reason": "context admission ceiling; no history silently discarded",
            }
            break
        print(
            f"Research epoch {epoch}: agent call {index + 1}/48; trial slots used {trials}/{trial_limit}",
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
        )
        output = response.get("output")
        if type(output) is not list:
            raise ValueError("provider output malformed; retained and stopped")
        calls = [
            item
            for item in output
            if type(item) is dict and item.get("type") == "function_call"
        ]
        if len(calls) > 1:
            raise ValueError("parallel tool output prohibited; retained and stopped")
        history.extend(output)
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
        call = calls[0]
        if type(call.get("call_id")) is not str or type(call.get("name")) is not str:
            raise ValueError("provider tool identity malformed")
        arguments = _json(call.get("arguments"))
        tool_identity = f"epoch-{epoch}-tool-{index:03d}"
        intent = {
            "name": call["name"],
            "arguments": arguments,
            "call_id": call["call_id"],
        }
        intent_file = root / (tool_identity + "-intent.json")
        result_file = root / (tool_identity + "-result.json")
        if result_file.exists():
            if not intent_file.exists() or intent_file.read_bytes() != canonical(
                intent
            ):
                raise ValueError("tool replay conflict")
            result = json.loads(result_file.read_bytes())
        else:
            if intent_file.exists():
                raise ValueError(
                    "tool dispatch incomplete; reconcile without duplication"
                )
            ledger.checkpoint()
            write_once(intent_file, canonical(intent))
            if autonomous and call["name"] == STOP:
                result = stop_result(arguments)
            elif call["name"] == SELECT:
                if (
                    set(arguments) != {"strategy_json", "reason", "used_feedback"}
                    or type(arguments["used_feedback"]) is not bool
                    or type(arguments["reason"]) is not str
                    or not 1 <= len(arguments["reason"]) <= 4096
                ):
                    raise ValueError("closed selection required")
                result = candidate_record(
                    _json(arguments["strategy_json"]),
                    arguments["reason"],
                    arguments["used_feedback"],
                )
                write_once(root / "selected-recipe.json", canonical(result))
            else:
                numerical = call["name"] == PREFIX + "start_research_task" and (
                    arguments.get("kind") == "practice"
                    or arguments.get("action") == "run_python"
                )
                if numerical and trials >= trial_limit:
                    result = {
                        "status": "UNAVAILABLE",
                        "reason": "epoch research trial ceiling; select retained recipe or stop",
                        "authority_granted": False,
                    }
                    ledger.note(owner=owner, kind="capability_request", body=result)
                else:
                    result = await sdk.call(call["name"], arguments, tool_identity)
            write_once(result_file, canonical(result))
        if result.get("requires_reconciliation"):
            outcome = {
                "status": "RECONCILIATION_REQUIRED",
                "reason": "tool dispatch unresolved",
                "tool": tool_identity,
            }
            break
        if result.get("status") in (
            {"SELECTED", "STOPPED"} if autonomous else {"SELECTED"}
        ):
            outcome = result
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
    if outcome is None:
        outcome = {"status": "STOPPED", "reason": "epoch provider-call ceiling"}
    report = {
        "schema": "carbon.autoresearch.epoch-outcome.v1",
        "epoch": epoch,
        **outcome,
        "accounting": ledger.status(owner=owner),
        "chain_transactions": 0,
    }
    write_once(root / "outcome.json", canonical(report))
    return report
