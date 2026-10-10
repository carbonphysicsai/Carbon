"""Brief-to-product ledger generator (ONBOARDING-PIPELINE-01, extension).

Reads repository artefacts and writes one ledger per Challenge with four record
types: INPUTS, PROCESS, OUTPUTS and NETWORK. A field is one of

    {"value": ..., "source": "<repo path>"}               read from an artefact;
    {"value": "UNMEASURED", "kind": "measurement",
     "owner": ..., "tool": ...}                           a measurement not yet made,
                                                          with who measures it and with what;
    {"value": "UNMEASURED", "kind": "decision",
     "owner": ..., "question": ...}                       a real owner decision.

Nothing is estimated. The only per-Challenge input is the pointer registry
(`ledger_sources.json`), which also holds the shared measurement tools. The output is
deterministic: sorted keys, no clock, no host state.

    python scripts/dev/onboarding/build_ledger.py --challenge <id> [--out PATH]
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
ONBOARDING = "docs/development/challenge_pipeline/onboarding"
REGISTRY = f"{ONBOARDING}/ledger_sources.json"
SCHEMA = "carbon.challenge-pipeline.brief-product-ledger.v1"
UNMEASURED = "UNMEASURED"
REQUIRED_FOR_TESTED = "required for TESTED"
REQUIRED_FOR_VALUE = "required for PASSES VALUE"
REQUIRED_FOR_REFERENCE = "required for the reference stage exit"
SCORECARDS = "docs/development/challenge_pipeline/value-cost/analysis.md"
HARNESS = "carbon/design_search/track_b.py"

# The six inputs a brief must resolve, mapped to the sections of
# COMMON_DESIGN_PACKET_V1 that hold them. The mapping is a template constant.
INPUT_KINDS = (
    ("decision_definition", (1,)),
    ("requirements", (1, 4)),
    ("design_space", (3,)),
    ("material_data", (2,)),
    ("solver", (5,)),
    ("acceptance_criteria", (6,)),
)
SUPPLY_QUESTION = (
    "Would a customer supply this input, or would Carbon source it publicly? "
    "No artefact records the choice."
)


def _read(path):
    return (REPOSITORY / path).read_text(encoding="utf-8")


def _exists(path):
    return bool(path) and (REPOSITORY / path).is_file()


def measured(value, source):
    return {"value": value, "source": source}


def decision(owner, question):
    """A real owner decision that no artefact records."""
    return {
        "value": UNMEASURED,
        "kind": "decision",
        "owner": owner,
        "question": question,
    }


_REGISTRY_CACHE = {}


def _registry():
    if "document" not in _REGISTRY_CACHE:
        _REGISTRY_CACHE["document"] = json.loads(_read(REGISTRY))
    return _REGISTRY_CACHE["document"]


def to_measure(key):
    """A measurement not yet made: who measures it and with which tool or PR."""
    tool = _registry()["measurements"][key]
    return {
        "value": UNMEASURED,
        "kind": "measurement",
        "owner": tool["owner"],
        "tool": tool["tool"],
    }


def load_registry(challenge):
    registry = _registry()
    if challenge not in registry["challenges"]:
        raise SystemExit(f"{challenge} has no entry in {REGISTRY}")
    return registry["challenges"][challenge]


def packet_sections(path):
    """`{number: text}` for the `## N.` sections of a design packet."""
    sections, number, lines = {}, None, []
    for line in _read(path).splitlines():
        found = re.match(r"^## (\d+)\.", line)
        if found:
            if number is not None:
                sections[number] = "\n".join(lines)
            number, lines = int(found.group(1)), []
        elif number is not None:
            lines.append(line)
    if number is not None:
        sections[number] = "\n".join(lines)
    return sections


def build_inputs(entry):
    packet = entry.get("packet")
    if not _exists(packet):
        return {kind: to_measure("packet") for kind, _ in INPUT_KINDS}
    if entry.get("packet_template") != "common-v1":
        return {kind: to_measure("packet_sections") for kind, _ in INPUT_KINDS}
    sections = packet_sections(packet)
    inputs = {}
    for kind, numbers in INPUT_KINDS:
        present = [n for n in numbers if n in sections]
        if not present:
            inputs[kind] = to_measure("packet_sections")
            continue
        open_markers = sum(len(re.findall(r"\bOPEN\b", sections[n])) for n in present)
        inputs[kind] = {
            "packet_sections": measured(present, packet),
            "open_markers": measured(open_markers, packet),
            "customer_supplies": decision("Test Lead", SUPPLY_QUESTION),
            "time_to_obtain": to_measure("input_time_to_obtain"),
        }
    return inputs


def _history(entry):
    path = f"docs/development/challenge_pipeline/readiness/{entry['challenge']}/history.jsonl"
    rows = []
    if _exists(path):
        rows = [json.loads(x) for x in _read(path).splitlines() if x.strip()]
    return path, rows


def _lessons(entry):
    names = set(entry["lesson_challenges"])
    count, stages, recorded = 0, {}, []
    for path in sorted(
        glob.glob(str(REPOSITORY / "carbon/challenge_pipeline/lessons/*.json"))
    ):
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if document.get("challenge") in names:
            count += 1
            stages[document["stage"]] = stages.get(document["stage"], 0) + 1
            recorded.append(document["recorded_at"])
    return count, stages, sorted(recorded)


def build_process(entry):
    challenge = entry["challenge"]
    metrics_path = f"{ONBOARDING}/cycle_metrics.jsonl"
    rows = [json.loads(x) for x in _read(metrics_path).splitlines() if x.strip()]
    dated = [
        {"stage": r["stage"], "event": r["event"], "date": r["date"]}
        for r in rows
        if r["challenge"] == challenge
    ]
    taxonomy_path = f"{ONBOARDING}/blocker_taxonomy.json"
    blockers = [
        {
            "id": b["id"],
            "name": b["name"],
            "fix_status": b["fix_status"],
            "time_lost": b["time_lost"],
        }
        for b in json.loads(_read(taxonomy_path))["blockers"]
    ]
    history_path, history = _history(entry)
    process = {
        "dated_stage_records": (
            measured(
                sorted(dated, key=lambda r: (r["date"], r["stage"], r["event"])),
                metrics_path,
            )
            if dated
            else to_measure("dated_stage_records")
        ),
        "blockers": measured(blockers, taxonomy_path),
        "cost_per_stage": to_measure("cost_per_stage"),
        "cycle_days_per_stage": decision(
            "Test Lead",
            "A first dated record is not the time spent. Which entry and exit records define each stage's cycle time?",
        ),
    }
    if history:
        first = history[0]
        latest = {}
        for row in history:
            latest[row["level"]] = row
        process["readiness_first_run"] = measured(
            {"counts": first["counts"], "utc": first["utc"], "level": first["level"]},
            history_path,
        )
        process["readiness_latest_by_level"] = measured(
            {
                str(level): {
                    "counts": row["counts"],
                    "utc": row["utc"],
                    "green": row["green"],
                }
                for level, row in sorted(latest.items())
            },
            history_path,
        )
    count, stages, recorded = _lessons(entry)
    if count:
        process["lessons_entries"] = measured(
            {
                "count": count,
                "by_stage": stages,
                "first": recorded[0],
                "last": recorded[-1],
            },
            "carbon/challenge_pipeline/lessons",
        )
    grants = []
    for pattern in entry.get("grant_globs", []):
        for path in sorted(glob.glob(str(REPOSITORY / pattern))):
            relative = Path(path).relative_to(REPOSITORY).as_posix()
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            grants.append(
                {
                    "grant_id": document["grant_id"],
                    "cap": document["monetary_ceiling"],
                    "permitted_runs": document["permitted_runs"],
                    "source": relative,
                }
            )
    if grants:
        process["grant_caps"] = {
            "value": grants,
            "source": "docs/development/graphite/grants",
            "note": "Caps and run counts only, never a balance or an account.",
        }
    else:
        process["grant_caps"] = to_measure("grant_caps")
    return process


def build_outputs(entry):
    outputs = {
        "model_accuracy": to_measure("model_accuracy"),
        "speed_up_against_reference": to_measure("speed_up"),
        "passes_value": build_passes_value(),
        "credibility_layers": build_credibility(entry),
    }
    baseline = entry.get("cheap_baseline")
    v4 = to_measure("cheap_baseline_v4")
    if _exists(baseline) and "NOT_MEASURED" in _read(baseline):
        v4["source"] = baseline
    outputs["decision_quality_vs_cheap_baseline"] = dict(
        v4, required_for_tested=True, flag=REQUIRED_FOR_TESTED
    )
    q1 = entry.get("q1_report")
    if _exists(q1):
        report = json.loads(_read(q1))
        alignment = report["alignment"]
        outputs["score_value_alignment"] = measured(
            {
                "kendall_tau_b": alignment["kendall_tau_b"],
                "spearman_rho": alignment["spearman_rho"],
                "members": len(report["members"]),
                "level": report["level"],
                "reference_provenance": report["reference"]["provenance"],
                "note": "one seed per recipe; a measurement only",
            },
            q1,
        )
    else:
        outputs["score_value_alignment"] = to_measure("score_value_alignment")
    return outputs


def build_credibility(entry):
    """The three credibility layers per pinned solver; UNMEASURED unless an artefact holds one."""
    solvers = {}
    for solver in entry.get("solvers", []):
        named = solver["named_in"]
        if not (_exists(named) and solver["name"].lower() in _read(named).lower()):
            continue
        solvers[solver["name"]] = {
            "named_in": measured(solver["name"], named),
            "code_verification": dict(
                to_measure("code_verification"),
                required_for="reference stage exit",
                flag=REQUIRED_FOR_REFERENCE,
            ),
            "solution_verification": to_measure("solution_verification"),
            "validation": to_measure("validation"),
        }
    return {
        "rule": (
            "Code verification is a required exit criterion of the reference stage "
            "(Test Lead, from the owner, 2026-10-10): a Method of Manufactured Solutions test, "
            "or an exact analytic-solution test where MMS is not practical, showing the observed "
            "order of accuracy matches the scheme's theoretical order, re-run on any image "
            "rebuild or re-pin. Recorded beside solution verification and validation."
        ),
        "solvers": solvers,
    }


def _value_condition(key, condition):
    return dict(
        to_measure(key),
        condition=condition,
        required_for="PASSES VALUE",
        flag=REQUIRED_FOR_VALUE,
    )


def build_passes_value():
    """The PASSES VALUE conditions. Each is UNMEASURED until an artefact holds it."""
    return {
        "set_by": (
            "Conditions a to d: Test Lead, delegated by the owner, 2026-10-10. "
            "Condition e: Test Lead, from the owner, 2026-10-10."
        ),
        "framing": (
            "Models never beat the solver on accuracy; the solver is the reference."
        ),
        "a_real_buyer_decision_two_sources": _value_condition(
            "value_a", "A real buyer decision with at least two sources."
        ),
        "b_regret_below_cheap_baseline_paired_bootstrap_ci": _value_condition(
            "value_b",
            "Buyer-unit regret lower than the strongest cheap baseline's at matched "
            "admissibility, paired bootstrap 95% interval excluding 0.",
        ),
        "c_speed_up_100x_per_decision_query": _value_condition(
            "value_c", "At least 100x faster than the reference per decision query."
        ),
        "d_value_and_volume_ranges": _value_condition(
            "value_d", "Sourced or assumption ranges for value and volume."
        ),
        "e_equal_budget_screen_then_verify_beats_solver": dict(
            _value_condition(
                "value_e",
                "At equal time and compute, the model-screen-then-solver-verify "
                "workflow finds a better design than the solver alone.",
            ),
            harness=HARNESS,
        ),
    }


def build_brief(entry):
    """The Challenge's current decision, read from the value-cost scorecard table."""
    name = entry.get("scorecard")
    if name and _exists(SCORECARDS):
        for line in _read(SCORECARDS).splitlines():
            if line.startswith(f"| [{name}]"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                return {
                    "current_decision": measured(cells[1], SCORECARDS),
                    "unresolved_or_adverse_evidence": measured(cells[3], SCORECARDS),
                    "scorecard_disposition": measured(cells[2], SCORECARDS),
                }
    return {"current_decision": to_measure("scorecard")}


def build_network():
    return {
        "leaderboard_improvement_over_time": to_measure("network_leaderboard"),
        "graphite_agents_vs_real_miners": to_measure("network_agents_vs_miners"),
        "incentive_canary_payout_correctness": to_measure("network_canary"),
    }


def build(challenge):
    entry = dict(load_registry(challenge))
    entry["challenge"] = challenge
    ledger = {
        "schema": SCHEMA,
        "challenge": challenge,
        "rules": [
            "A field is read from a cited artefact, or it is UNMEASURED: a measurement names its owner and tool, and only a real owner decision carries a question. Nothing is estimated.",
            "Caps and rates only. No balance, account, spend ledger or hidden-pool material.",
        ],
        "inputs": build_inputs(entry),
        "process": build_process(entry),
        "brief": build_brief(entry),
        "outputs": build_outputs(entry),
        "network": build_network(),
    }
    return ledger


def render(ledger):
    return json.dumps(ledger, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--out", help="write here instead of stdout")
    args = parser.parse_args(argv)
    text = render(build(args.challenge))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
