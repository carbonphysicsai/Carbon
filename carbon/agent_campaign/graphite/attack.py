"""Graphite's Attacker, version 1: its brief and Carbon's side of a session
(CHALLENGE-PROTOCOL-04; Graphite phase 4).

Challenge-neutral. An Attacker session probes one Challenge's miner path
(`challenge.py`) against test suite v1's eight Track A vectors, at the
construction level its campaign runs at. The owner allows it to run code
inside the research sandbox (OWNER-CHALLENGE-STEP4-01). It reports what each
attempt showed. Its claims are data, never verdicts. The session itself runs
on #504's harness (`phase4.AttackerProvider`).

Carbon then analyses the session on its own side, from the session's
recorded tool calls, never from the model's prose:
- **`attempts`** reads every tool call and its recorded result from the
  research loop's journal, and assigns each to a vector.
- **`reverify`** re-checks each attempt that carried a recipe, outside the
  agent, with the Challenge's own admission gate (its adapter's
  `admission_refusals`; for battery, #504's reconstruction gate
  `experiment.admit`).
  - `FAIL_OPEN`: the miner path plainly accepted what Carbon's gate refuses.
    That is a reproduced fail-open, and the only kind of finding
    (OWNER-CHALLENGE-STEP4-01). It is recorded on the controller as a
    `FAILING_TRIGGER` (OWNER-CHALLENGE-ADMISSION-01 §3.2).
  - `HELD`: the path refused, or accepted only what Carbon admits. A refusal
    by Graphite's own harness (its manifest, protected-material and code-run
    rules) never reached the path; it is marked `refused_by: graphite` and
    counted apart, so it is never reported as the path's defense.
  - `UNDETERMINED`: the result does not say plainly whether the path
    accepted, Graphite withheld it for naming protected material, or the
    Challenge's contract record is not current. Reported, never a finding.
  - `NOT_APPLICABLE`: no recipe to re-check. Left to the suite's checks and
    the controller's canary scan.
- **`coverage`** merges the sessions' attempts and verified fail-opens with
  the Challenge's test suite v1 coverage report (`challenge_pipeline.suite`),
  vector by vector. It is bound to the suite's digest and to the Challenge's
  suite map digest, and it states the construction level the sessions ran
  at, which must be the level the suite report ran at. Every level above it
  is NOT_RUN, and so is a vector's participant-code part until its level is
  reached (the suite's `ladder` block): carried through as NOT_RUN, never a
  pass (Challenge Roadmap rev 2.2 §03).

Grading every finding stays with the technical owner. Nothing here is
security acceptance.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.challenge_pipeline import ladder as construction_ladder
from carbon.development_session.research_tools import PREFIX

from . import tools as toolbox

SCHEMA = "carbon.graphite.attack-coverage.v2"
ROWS_SCHEMA = "carbon.graphite.attack-rows.v2"
#: The controller condition a reproduced fail-open is recorded under: an
#: admission check that should have fired did not.
FINDING_CONDITION = "FAILING_TRIGGER"
#: The refusal a Challenge's gate returns first when its own contract record
#: is not current, so it can re-check nothing.
CONTRACT_UNRECORDED = "construction_contract_unrecorded"
#: Which vector a tool call probes, by tool and, for tasks, by kind or action.
_TOOL_VECTOR = {
    "dry_validate": "A1",
    "compile_strategy": "A1",
    "get_challenge_info": "A3",
    "get_interaction_manifest": "A3",
    "get_research_result": "A8",
    "cancel_research_task": "A4",
}
_ACCEPT_KEYS = ("ok", "accepted", "valid")
#: Statuses that refuse a request, besides any `REFUSED*` or `REJECTED*`.
_REFUSALS = frozenset({"INVALID", "UNAVAILABLE", "MINER_PATH_REFUSED", "ERROR"})
#: Code runs: the same definition the miner SDK charges a research trial for
#: (`research_tools.ResearchMinerTools.call`).
CODE_ACTIONS = ("run_python", "run_julia")


#: What each suite v1 vector asks, worded for the Attacker, for any
#: Challenge. The suite's own text names material Graphite's boundary refuses
#: to show any agent (for example, "credential"), so this wording carries the
#: same question without it. A Challenge's record may reword a vector with its
#: own specifics (`challenge.attack_goals`). A test checks that every suite
#: vector has one and that the brief passes the boundary.
ATTACK_GOALS = {
    "A1": "Does the path refuse undeclared inputs, unsupported recipes, pretrained "
    "payloads, executables outside the contract's backends and disguised "
    "executable content?",
    "A2": "From the research sandbox, can code reach files, the network, other "
    "processes, account keys or other jobs it should not?",
    "A3": "Can you observe or influence the seeds, references, exam batches, the "
    "held-out pool or the evaluation services?",
    "A4": "Are time, memory, storage and compute overruns stopped, and is a partial "
    "result ever graded as valid?",
    "A5": "Does a recipe rebuild the same from its declaration on a fresh worker, "
    "and how much do repeated seeds vary?",
    "A6": "Are recipe, data, dependency, model and report identities bound? Can "
    "you substitute one, reuse a stale cache or replay a request?",
    "A7": "Can outputs or metrics be forged or altered, provenance dropped, or "
    "workers made to disagree without the grade being held?",
    "A8": "Can repeated queries against a rotating batch, memorization or leakage "
    "across cases reveal more than the disclosure budget allows?",
}


def suite_vectors(challenge):
    from carbon.challenge_pipeline.suite import load_suite

    goals = {**ATTACK_GOALS, **challenge.attack_goals}
    return [
        {"id": v["id"], "name": v["name"], "goal": goals[v["id"]]}
        for v in load_suite()["track_a"]
    ]


def brief_observation(challenge, *, stage, limits):
    """The Attacker's starting observation: the Challenge's public development
    identity, the suite's eight vectors and the limits it works under.
    Refused if it names protected material."""
    observation = {
        "challenge": challenge.public_identity(),
        "stage": stage,
        "objective": (
            f"Probe {challenge.label}'s research path for each vector below, "
            "through the tools you are given. Try well-formed attempts that a "
            "careful attacker would try; you may run code inside the research "
            "sandbox. For each attempt, say what you tried and what the path did. "
            "A suspected fail-open is a report for Carbon to verify, never a "
            "verdict."
        ),
        "vectors": suite_vectors(challenge),
        "limits": dict(limits),
    }
    if toolbox.protected(observation):
        raise ValueError("refused: the attacker brief names protected material")
    return observation


def is_code_run(name, arguments):
    """A task that trains or runs code: practice, `run_python`, `run_julia`."""
    return (
        name == PREFIX + "start_research_task"
        and type(arguments) is dict
        and (
            arguments.get("kind") == "practice"
            or arguments.get("action") in CODE_ACTIONS
        )
    )


def _vector(tool, arguments):
    name = tool.removeprefix(PREFIX)
    if name == "start_research_task":
        if arguments.get("kind") == "practice":
            return "A4"
        if arguments.get("action") in CODE_ACTIONS:
            return "A2"
        return "A3"
    return _TOOL_VECTOR.get(name)


def attempts(run_dir):
    """Every tool call a session made, with its recorded result and vector,
    from the research loop's journal (`ledger/epoch-1`)."""
    epoch = Path(run_dir) / "ledger" / "epoch-1"
    found = []
    for intent_path in sorted(epoch.glob("epoch-1-tool-*-intent.json")):
        intent = json.loads(intent_path.read_bytes())
        result_path = intent_path.with_name(
            intent_path.name.replace("-intent.json", "-result.json")
        )
        result = json.loads(result_path.read_bytes()) if result_path.is_file() else None
        arguments = intent.get("arguments")
        arguments = arguments if type(arguments) is dict else {}
        found.append(
            {
                "identity": intent_path.name.removesuffix("-intent.json"),
                "tool": intent["name"],
                "arguments": arguments,
                "result": result,
                "vector": _vector(intent["name"], arguments),
            }
        )
    return found


def _refusal(status):
    text = str(status or "").upper()
    return text.startswith(("REFUSED", "REJECTED")) or text in _REFUSALS


def _accepted(result):
    """True or False when the result says plainly whether the path accepted
    the request; None when it does not."""
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


def _refused_by(result):
    """Who refused: Graphite's own harness (nothing was dispatched to the
    path), or the path."""
    if type(result) is dict and result.get("dispatched") is False:
        return "graphite"
    return "path"


def _carbon_refuses(strategy, challenge):
    """Carbon's own, independent admission of a recipe, by the Challenge's
    gate. Returns the refusal codes, empty when Carbon would rebuild it."""
    if type(strategy) is not dict:
        return ["strategy_not_an_object"]
    return challenge.admission_refusals(strategy)


def _strategy(arguments):
    raw = arguments.get("strategy_json")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return "unparseable"


def reverify(attempt, challenge):
    """Carbon's verdict on one attempt, from Carbon's own checks:
    `FAIL_OPEN`, `HELD`, `UNDETERMINED` or `NOT_APPLICABLE` (module
    docstring)."""
    strategy = _strategy(attempt["arguments"])
    if strategy is None:
        return {"verdict": "NOT_APPLICABLE", "basis": "no recipe in the request"}
    result = attempt["result"]
    refusals = _carbon_refuses(strategy, challenge)
    if refusals[:1] == [CONTRACT_UNRECORDED]:
        # Carbon's own record is not current, so Carbon cannot re-check
        # anything: never a finding against the path.
        return {"verdict": "UNDETERMINED", "carbon_refusals": refusals}
    if type(result) is dict and result.get("reason_code") == (
        "protected_material_in_result"
    ):
        return {
            "verdict": "UNDETERMINED",
            "basis": "Graphite withheld the path's result for naming protected "
            "material",
            "withheld": True,
            "carbon_refusals": refusals,
        }
    accepted = _accepted(result)
    if accepted is None:
        return {"verdict": "UNDETERMINED", "carbon_refusals": refusals}
    if accepted and refusals:
        return {
            "verdict": "FAIL_OPEN",
            "basis": "the path accepted a recipe Carbon's own gate refuses",
            "carbon_refusals": refusals,
        }
    held = {"verdict": "HELD", "path_accepted": accepted, "carbon_refusals": refusals}
    if not accepted:
        held["refused_by"] = _refused_by(result)
    return held


def analyse(run_dir, challenge):
    """Attempts with Carbon's verdicts, and the verified fail-opens."""
    rows = []
    for attempt in attempts(run_dir):
        rows.append(
            {
                "identity": attempt["identity"],
                "tool": attempt["tool"],
                "vector": attempt["vector"],
                **reverify(attempt, challenge),
            }
        )
    return rows, [r for r in rows if r["verdict"] == "FAIL_OPEN"]


#: Where the suite's per-Challenge maps live (`challenge_pipeline.suite`).
SUITE_MAPS = None


def check_suite_report(suite_report, challenge):
    """The suite report must be the Challenge's, pinned to the suite v1 and
    to the Challenge's suite map in this checkout, at a construction level on
    the ladder, with every participant-code part beyond that level NOT_RUN.
    Returns the report's construction level."""
    from carbon.challenge_pipeline import suite

    if type(suite_report) is not dict or suite_report.get("suite_digest") != (
        suite.digest()
    ):
        raise ValueError("suite_report_not_the_current_suite_pin")
    if suite_report.get("challenge") != challenge.token:
        raise ValueError("suite_report_for_another_challenge")
    maps = suite.MAPS if SUITE_MAPS is None else SUITE_MAPS
    if suite_report.get("map_digest") != suite.map_digest(challenge.token, maps):
        raise ValueError("suite_report_not_the_current_map_pin")
    level = suite_report.get("construction_level")
    if type(level) is not int or level not in construction_ladder.LEVELS:
        raise ValueError("suite_report_names_no_construction_level")
    for vector in suite_report["vectors"]:
        part = vector.get("participant_code")
        if part is None:
            continue
        expected = "IN_SCOPE" if level >= part["from_level"] else "NOT_RUN"
        if part.get("status") != expected:
            # Never read a part beyond the level as anything but NOT_RUN.
            raise ValueError("suite_report_participant_code_not_scoped_by_level")
    return level


def coverage(session_rows, suite_report, *, challenge, construction_level):
    """Per vector: the suite's check status, the attackers' attempts,
    refusals and verified fail-opens, and the participant-code part's status
    at this level. A report; grading stays with the technical owner."""
    if check_suite_report(suite_report, challenge) != construction_level:
        # The suite's checks and the sessions must be at one level: evidence
        # stays bound to the level it was taken at.
        raise ValueError("suite_report_at_another_construction_level")
    by_vector = {}
    for row in session_rows:
        by_vector.setdefault(row["vector"], []).append(row)
    vectors = []
    for vector in suite_report["vectors"]:
        rows = by_vector.get(vector["id"], [])
        held = [r for r in rows if r["verdict"] == "HELD"]
        vectors.append(
            {
                "id": vector["id"],
                "name": vector["name"],
                "suite_status": vector["status"],
                "attempts": len(rows),
                "held_by_path": sum(r.get("refused_by") != "graphite" for r in held),
                "refused_by_graphite": sum(
                    r.get("refused_by") == "graphite" for r in held
                ),
                "undetermined": sum(r["verdict"] == "UNDETERMINED" for r in rows),
                "withheld": sum(bool(r.get("withheld")) for r in rows),
                "not_applicable": sum(r["verdict"] == "NOT_APPLICABLE" for r in rows),
                "fail_opens": [
                    r["identity"] for r in rows if r["verdict"] == "FAIL_OPEN"
                ],
                # The suite's own scoping, carried through unchanged: NOT_RUN
                # below its level, never a pass.
                "participant_code": vector.get("participant_code"),
                "gaps": vector["gaps"],
            }
        )
    return {
        "schema": SCHEMA,
        "challenge": challenge.token,
        "construction_level": construction_level,
        "levels_not_run": [
            level for level in construction_ladder.LEVELS if level > construction_level
        ],
        "suite_digest": suite_report["suite_digest"],
        "map_digest": suite_report["map_digest"],
        "suite_commit": suite_report["commit"],
        "unassigned_attempts": len(by_vector.get(None, [])),
        "vectors": vectors,
        "claims": {"security_acceptance": False, "graded": False},
    }
