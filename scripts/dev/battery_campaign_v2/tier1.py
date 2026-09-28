"""Battery agent campaign v2, tier 1: does the environment teach its own best
strategy? (docs/development/BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2.md §5)

A model is given the battery public material (as in tier 0), the tools an
agent is offered (the base research tools with their full descriptions, plus
SELECT and STOP), and the run plan's caps. It is asked to plan one epoch as a
JSON list of tool calls. Nothing is executed.

DISCLOSED DEVIATION. v2 §5 says the plan framing texts are "fixed at
approval". They were not written into v2 before approval. They are fixed here,
on 2026-09-27 at about 22:45Z, before any tier-1 call was made, and are
reported as fixed after approval but before any output.

Scoring is mechanical, which is blind by construction, per §5's six items and
the ordering statistic:
  1 queries before spending  - a query step comes before the first trial
  2 finds check_design       - a workspace action check_design is planned
  3 finds roadmap            - a workspace action roadmap is planned
  4 knows its labelled data  - it reads training_data or practice_data, and
                               plans no run of the reference solver (keyword
                               proxy, recorded as such)
  5 budgets real costs       - at most 48 steps and at most 8 trials
  6 reserves                 - it plans a SELECT or STOP, with fewer than 8
                               trials or fewer than 48 steps
  ordering: the first practice comes after a check_design (None when either
  is absent)
A trial is kind=practice or action=run_python.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tier0

FRAMINGS = {
    "P1": (
        "Here is a challenge's public material and the research tools available "
        "to you. Plan how you would use this epoch's budget: list each tool call "
        "you would make, in order, as JSON."
    ),
    "P2": (
        "You are a miner with one research epoch on this challenge. Using only "
        "this material and these tools, give your plan for the epoch as a JSON "
        "list of tool calls, in order, with the purpose of each."
    ),
    "P3": "Plan your research epoch. Output only a JSON list of tool calls.",
}
FORMAT = (
    'Each list item: {"tool": tool name, "kind": "practice"|"workspace"|null, '
    '"action": workspace action or null, "arguments": object or null, '
    '"purpose": text}.'
)
RUN_PLAN = {
    "max_provider_calls_per_epoch": 48,
    "max_research_trials_per_epoch": 8,
    "epochs": 2,
}
QUERY_TOOLS = (
    "get_challenge_info",
    "get_interaction_manifest",
    "get_prior",
    "get_mock_scaffold",
    "dry_validate",
    "compile_strategy",
    "inspect_resources",
    "forecast_resources",
)
QUERY_ACTIONS = ("public_material", "inventory", "read_file", "check_design", "roadmap")
REFERENCE_WORDS = ("reference solve", "run pybamm", "pybamm solve", "generate labels")


def offered_tools():
    from carbon.development_session.research_agent_policy import STOP_TOOL
    from carbon.development_session.research_loop import SELECTION_TOOL
    from carbon.development_session.research_tools import TOOLS

    return [*TOOLS, SELECTION_TOOL, STOP_TOOL]


def first_json_list(text):
    start = text.find("[")
    while start != -1:
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "[":
                depth += 1
            elif text[index] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start : index + 1])
                        if isinstance(value, list):
                            return value
                    except json.JSONDecodeError:
                        pass
                    break
        start = text.find("[", start + 1)
    return None


def _short(name):
    return str(name or "").split("__")[-1]


def score(plan):
    if not isinstance(plan, list) or not plan:
        return {"parsed": False}
    steps = [s for s in plan if isinstance(s, dict)]
    tools = [_short(s.get("tool")) for s in steps]
    actions = [str(s.get("action") or "") for s in steps]
    kinds = [str(s.get("kind") or "") for s in steps]
    texts = [json.dumps(s).lower() for s in steps]
    trial = [k == "practice" or a == "run_python" for k, a in zip(kinds, actions)]
    query = [t in QUERY_TOOLS or (a in QUERY_ACTIONS) for t, a in zip(tools, actions)]
    first_trial = trial.index(True) if any(trial) else None
    first_check = actions.index("check_design") if "check_design" in actions else None
    first_practice = kinds.index("practice") if "practice" in kinds else None
    n_trials = sum(trial)
    ends = any("select_recipe" in t or t.endswith("_stop") for t in tools)
    return {
        "parsed": True,
        "steps": len(steps),
        "trials": n_trials,
        "1_queries_before_spending": (
            any(query) if first_trial is None else any(query[:first_trial])
        ),
        "2_finds_check_design": first_check is not None,
        "3_finds_roadmap": "roadmap" in actions,
        "4_knows_labelled_data": any(
            "training_data" in x or "practice_data" in x for x in texts
        )
        and not any(w in x for x in texts for w in REFERENCE_WORDS),
        "5_budgets_real_costs": len(steps) <= 48 and n_trials <= 8,
        "6_reserves": ends and (n_trials < 8 or len(steps) < 48),
        "ordering_practice_after_check_design": (
            None
            if first_check is None or first_practice is None
            else first_check < first_practice
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--models", default=",".join(tier0.DEFAULT_MODELS))
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--max-charged-micro", type=int, default=250000)
    parser.add_argument("--max-output-tokens", type=int, default=16384)
    args = parser.parse_args(argv)
    os.umask(0o077)  # records carry account charges: owner-only files
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; refusing to overwrite a run")
    os.makedirs(args.out, mode=0o700)
    given = {
        "material": tier0.public_material(),
        "tools": offered_tools(),
        "run_plan": RUN_PLAN,
    }
    given_json = json.dumps(given, sort_keys=True, default=str)
    (args.out / "given.json").write_text(given_json)
    available = tier0.live_models()
    models = [m for m in args.models.split(",") if m]
    conditions = [
        (m, f, s)
        for m in models
        if m in available
        for f in FRAMINGS
        for s in range(args.samples)
    ]
    random.SystemRandom().shuffle(conditions)
    spent = 0
    log = (args.out / "records.jsonl").open("x")
    from carbon.development_session.model_provider import SelectionTransport, select

    for model, framing, sample in conditions:
        if spent >= args.max_charged_micro:
            print(json.dumps({"stopped": "charge cap reached", "spent_micro": spent}))
            break
        record = {"model": model, "framing": framing, "sample": sample}
        request = {
            "model": model,
            "instructions": FRAMINGS[framing] + " " + FORMAT,
            "input": [{"role": "user", "content": given_json}],
            "tools": [],
            "parallel_tool_calls": False,
            "max_output_tokens": args.max_output_tokens,
        }
        try:
            selection = select(
                provider_id=tier0.PROVIDER,
                model_id=model,
                credential={"kind": "file", "reference": str(args.credential)},
            )
            response = SelectionTransport(selection)(request)
        except Exception as failed:  # noqa: BLE001 - recorded, typed by name
            record.update(
                outcome="PROVIDER_FAILURE",
                error=type(failed).__name__,
                message=str(failed)[:300],
            )
            log.write(json.dumps(record) + "\n")
            log.flush()
            continue
        x_engy = response.get("x_engy") or {}
        charged = x_engy.get("charged_micro")
        if charged is None:
            record.update(outcome="NO_CHARGE_REPORT")
            log.write(json.dumps(record) + "\n")
            print(json.dumps({"stopped": "provider returned no charged_micro"}))
            break
        spent += charged
        text = tier0.reply_text(response)
        plan = first_json_list(text)
        usage = response.get("usage") or {}
        record.update(
            plan=plan,
            score=score(plan),
            reply_text=text,
            charged_micro=charged,
            usage={
                k: usage.get(k)
                for k in (
                    "input_tokens",
                    "output_tokens",
                    "output_tokens_details",
                    "input_tokens_details",
                )
            },
            provenance={k: x_engy.get(k) for k in ("request_id", "miner", "worker")},
        )
        log.write(json.dumps(record, default=str) + "\n")
        log.flush()
    log.close()
    (args.out / "summary.json").write_text(json.dumps({"spent_micro": spent}))
    print(json.dumps({"spent_micro": spent}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
