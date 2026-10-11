"""Public-only resolution/cost audit. No Carbon imports, network or solver calls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import re
from statistics import mean

BASE = "0d1370d01ec4bf76c38627c85b9426910d8be3a3"
INPUTS = {
    "ev4.json": ("docs/development/evidence/ev4-2026-10-01/results.json", "67ca13b966a2f6fb4b2e68b084e2909657e7ba7f"),
    "ev5.json": ("docs/development/evidence/ev5-2026-10-03/results.json", "7d6ccf75a47c2df56c66d0b223300e5fd9398512"),
    "run5.json": ("docs/development/evidence/graphite-run5-q1/results.json", "2ea791a0c8dd8badd41a9d5823d491ec39ee9ed8"),
    "run5-refined.json": ("docs/development/evidence/graphite-run5-q1-refined/results.json", "91505359446f3a13163a1371590fcad0b2a4041b"),
    "settling.json": ("docs/development/evidence/ev4-dev-refined-v1/settling.json", "28bd84370ec3e07cfbfe4627c85559fd09409b30"),
    "refined-records.jsonl.gz": ("docs/development/evidence/ev4-dev-refined-v1/records.jsonl.gz", "c2840676909bae6585e92402a3bc7b86d6b59c27"),
    "grid-resolution.json": ("docs/development/evidence/battery-quiz-designs/grid-resolution-v1/grid-resolution.json", "68221beb898560f3cf3fbe8ff626f0ff95ef8d4b"),
}
HOURS = {"low": .66, "base": .73, "high": .80}  # OWNER estimate base; ASSUMPTION sensitivity endpoints.
TARGET = 150  # Owner's interim target, inherited from #1055; not a new acceptance decision.


def read_inputs(directory):
    data, provenance = {}, {}
    for name, (source, expected) in INPUTS.items():
        raw = (directory / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != expected:
            raise ValueError(f"Public input hash mismatch: {name}")
        if name.endswith(".gz"):
            data[name] = [json.loads(line) for line in gzip.decompress(raw).decode().splitlines() if line.strip()]
        else:
            data[name] = json.loads(raw)
        provenance[name] = {"path": source, "source_commit": BASE, "git_blob": blob, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return data, provenance


def numeric(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def members(results, all_eligible=False):
    return sorted(m for m, r in results["summary"]["members"].items() if r["eligible"] and (all_eligible or r["kind"] == "RECONSTRUCTED"))


def recipe(member):
    return re.sub(r"-s[0-9]+$", "", member).replace("graphite-run5-p-fa70c075f903", "graphite-run5-p-69268f1b74ec")


def question_rows(results, panel):
    rows = []
    for q, ref in sorted(results["references"].items()):
        kinds, missing, ambiguous_choices = Counter(), [], Counter()
        resolved = 0
        for m in panel:
            d = results["decisions"].get(m, {}).get(q)
            if d is None:
                missing.append(m)
                kinds["MISSING_MEMBER_RECORD"] += 1
                continue
            o = d["outcome"]
            kinds[o["kind"]] += 1
            resolved += numeric(o.get("decision_loss"))
            if not numeric(o.get("decision_loss")) and o.get("selected") is not None:
                ambiguous_choices[o["selected"]] += 1
        counts = ref["status_counts"]
        total = sum(counts.values())
        unknown = counts["UNRESOLVED"] + counts["REFERENCE_UNAVAILABLE"]
        rows.append({"question": q, "split": ref["split"], "temperature_block": q.split("-S")[0],
                     "reference_status_counts": counts, "resolved_member_records": resolved,
                     "members": len(panel), "common_resolved": resolved == len(panel),
                     "missing_member_records": len(missing), "outcome_kinds": dict(kinds),
                     "fully_all_infeasible": counts["INFEASIBLE"] == total,
                     "no_known_feasible_but_uncertain": counts["FEASIBLE"] == 0 and unknown > 0,
                     "all_reference_actions_resolved": unknown == 0,
                     "contested_known_feasible_and_infeasible": counts["FEASIBLE"] > 0 and counts["INFEASIBLE"] > 0,
                     "selected_ambiguous_actions": dict(ambiguous_choices)})
    return rows


def summarize(rows):
    n = len(rows)
    resolved = sum(r["common_resolved"] for r in rows)
    kinds = Counter()
    for r in rows:
        kinds.update(r["outcome_kinds"])
    return {"offered": n, "common_resolved": resolved, "rate": resolved / n if n else None,
            "excluded_questions": [r["question"] for r in rows if not r["common_resolved"]],
            "fully_all_infeasible": sum(r["fully_all_infeasible"] for r in rows),
            "no_known_feasible_but_uncertain": sum(r["no_known_feasible_but_uncertain"] for r in rows),
            "all_reference_actions_resolved": sum(r["all_reference_actions_resolved"] for r in rows),
            "member_records": sum(r["members"] for r in rows),
            "numeric_member_records": sum(r["resolved_member_records"] for r in rows),
            "missing_member_records": sum(r["missing_member_records"] for r in rows),
            "outcome_kinds": dict(kinds)}


def campaign(results):
    ms = members(results)
    rows = question_rows(results, ms)
    output = {"members": len(ms), "recipes": len({recipe(m) for m in ms}), "summary": summarize(rows),
              "splits": {s: summarize([r for r in rows if r["split"] == s]) for s in ("development", "verification")},
              "questions": rows, "all_eligible_panel": summarize(question_rows(results, members(results, True)))}
    output["coverage_rules_diagnostics_not_adoption"] = {
        str(threshold): {"questions": sum(r["resolved_member_records"] / len(ms) >= threshold for r in rows),
                        "excluded_incomplete_rows_retained_as_unknown": sum(r["resolved_member_records"] / len(ms) >= threshold and not r["common_resolved"] for r in rows)}
        for threshold in (.8, .9, .95, 1.0)}
    coverage = [sum(numeric(results["decisions"][m][q]["outcome"].get("decision_loss")) for q in results["references"]) / len(rows) for m in ms]
    output["member_numeric_coverage"] = {"min": min(coverage), "mean": mean(coverage), "max": max(coverage)}
    # Cohorts use only public recipe identity, never observed performance.
    output["preassigned_cohort_diagnostics"] = {}
    for k in (2, 4, 8):
        cohorts = [[m for m in ms if int(hashlib.sha256(recipe(m).encode()).hexdigest(), 16) % k == j] for j in range(k)]
        output["preassigned_cohort_diagnostics"][str(k)] = [
            {"members": len(c), "recipes": len({recipe(m) for m in c}), **summarize(question_rows(results, c))} for c in cohorts if c]
    return output


def offers(rate):
    return math.ceil(TARGET / rate - 1e-12)


def budget(rate, extra_hours_per_offer=0.0):
    n = offers(rate)
    return {"offered_for_150": n, "CPU_hours_ASSUMPTION": {k: n * (v + extra_hours_per_offer) for k, v in HOURS.items()}}


def run(data, provenance):
    campaigns = {name.removesuffix(".json"): campaign(data[name]) for name in ("ev4.json", "ev5.json", "run5.json", "run5-refined.json")}
    pooled_rows = campaigns["ev4"]["questions"] + campaigns["ev5"]["questions"]
    pooled = summarize(pooled_rows)
    base_rate = pooled["rate"]
    original, refined = data["run5.json"], data["run5-refined.json"]
    changes = []
    critical = set()
    for m in members(original):
        for q, d in original["decisions"][m].items():
            new = refined["decisions"][m][q]["outcome"]
            if d["outcome"]["kind"] != new["kind"]:
                changes.append({"member": m, "question": q, "before": d["outcome"]["kind"], "after": new["kind"], "selected": d["outcome"].get("selected")})
                critical.add("ev4:" + q + ":" + d["outcome"]["selected"] + ":0")
    records = data["refined-records.jsonl.gz"]
    full_time = sum(r["wall_s"] for r in records) / 3600
    critical_time = sum(r["wall_s"] for r in records if r["case_id"] in critical) / 3600
    # Timing is observed elapsed sums. CPU conversion below assumes ONE busy core.
    old_rate = campaigns["run5"]["splits"]["development"]["rate"]
    new_rate = campaigns["run5-refined"]["splits"]["development"]["rate"]
    refinement = {"cases": len(records), "status_counts": dict(Counter(r["status"] for r in records)),
        "settling_resolved": sum(r["resolved"] for r in data["settling.json"]),
        "sum_elapsed_hours_measured": full_time,
        "sum_solver_elapsed_hours_measured": sum(r.get("timing_s", {}).get("solve", 0) for r in records) / 3600,
        "failure_elapsed_hours_measured": sum(r["wall_s"] for r in records if r["status"] != "OK") / 3600,
        "before_development": campaigns["run5"]["splits"]["development"],
        "after_development": campaigns["run5-refined"]["splits"]["development"],
        "outcome_changes": changes, "critical_cases_hindsight": sorted(critical), "critical_elapsed_hours_hindsight": critical_time,
        "counterfactual_CPU_model": {"assumption": "One busy core; historical 12-question mix and same improvement repeat; not a sealed-run measurement or achievable-rate promise", "old": budget(old_rate),
            "new_all_27_cases": budget(new_rate, full_time / 12), "new_hindsight_critical_case_only": budget(new_rate, critical_time / 12)}}
    baseline = budget(base_rate)
    rows = []
    for yield_rate in (.6, .65, .7, .75, .8, .9, 1.0):
        b = budget(yield_rate)
        rows.append({"yield_ASSUMPTION": yield_rate, **b,
            "gross_CPU_hours_saved_ASSUMPTION": {k: baseline["CPU_hours_ASSUMPTION"][k] - b["CPU_hours_ASSUMPTION"][k] for k in HOURS},
            "break_even_extra_CPU_hours_per_offer": {k: baseline["CPU_hours_ASSUMPTION"][k] / b["offered_for_150"] - v for k, v in HOURS.items()}})
    filters = {"drop_fully_all_infeasible": [r for r in pooled_rows if not r["fully_all_infeasible"]],
               "known_contested_only": [r for r in pooled_rows if r["contested_known_feasible_and_infeasible"]],
               "fully_resolved_references_only": [r for r in pooled_rows if r["all_reference_actions_resolved"]]}
    transfer_rate = base_rate + new_rate - old_rate
    transfer = {"assumption": "Transport the historical +1/12 recovery to the EV4/EV5 pooled mix; one busy core; selection/refinement pattern repeats. Hindsight target is an optimistic diagnostic, not a promised policy.",
                "yield_assumption": transfer_rate,
                "targeted_hindsight": budget(transfer_rate, critical_time / 12),
                "blanket_all_cases": budget(transfer_rate, full_time / 12)}
    for key in ("targeted_hindsight", "blanket_all_cases"):
        transfer[key]["net_CPU_hours_saved_ASSUMPTION"] = {k: baseline["CPU_hours_ASSUMPTION"][k] - transfer[key]["CPU_hours_ASSUMPTION"][k] for k in HOURS}
    contested_rate = summarize(filters["known_contested_only"])["rate"]
    mixture = [{"epsilon_ASSUMPTION": eps, "public_support_raw_yield_diagnostic": eps * base_rate + (1 - eps) * contested_rate,
                **budget(eps * base_rate + (1 - eps) * contested_rate)} for eps in (.2, .5, .8)]
    grid = data["grid-resolution.json"]
    output = {"schema": "carbon.research.question-resolution-rate.v1", "label": "PUBLIC DEVELOPMENT RESEARCH; NO QUALIFICATION", "sources": provenance,
        "numeric_policy": "Measured counts/timings/point fractions low=base=high; forward CPU estimates and yield scenarios explicitly ASSUMPTION. Owner supplied base 0.73 CPU-h/offered question and target 150; sensitivity endpoints 0.66/0.80 are ASSUMPTION, not measured confidence bounds.",
        "runtime": {"python": platform.python_version(), "canonical": False}, "campaigns": campaigns,
        "pooled_EV4_EV5": pooled, "reference_refinement": refinement,
        "cost_model": {"target_owner": TARGET, "hours_per_offered_question": HOURS, "baseline": baseline, "yield_scenarios": rows,
                       "refinement_transport_scenario": transfer,
                       "known_contested_defensive_Q_raw_yield_diagnostic": mixture,
                       "drop_all_infeasible_counterexample": budget(summarize(filters["drop_fully_all_infeasible"])["rate"]),
                       "95pct_member_coverage_counterexample": budget(sum(r["resolved_member_records"] / r["members"] >= .95 for r in pooled_rows) / len(pooled_rows)),
                       "117_action_grid_same_yield_counterexample": {k: baseline["CPU_hours_ASSUMPTION"][k] * 117 / 35 for k in HOURS},
                       "max_gross_saving_at_perfect_resolution": {k: baseline["CPU_hours_ASSUMPTION"][k] - TARGET * v for k, v in HOURS.items()},
                       "sealed_run_measured": False, "spend_or_euro_quote": False},
        "biased_filter_diagnostics_never_adopted": {k: summarize(rs) for k, rs in filters.items()},
        "grid_refinement_diagnostic": {"coarse_actions": grid["grid"]["coarse"], "refined_actions": grid["grid"]["refined"],
            "pick_shift_rate": grid["pick_shift_rate"], "verdict_change_rate": grid["verdict_change_rate"], "verdicts_judged": grid["verdicts_judged"],
            "verdict_changes": grid["verdict_changes"], "resolution_gain": "NOT_ESTABLISHED: diagnostic changes selections/feasibility labels, not common-question resolution"},
        "unmeasured": {"ties": "No TIE_UNRESOLVED outcome; deterministic objective/c1/c2 tie break in pinned decision.py. Number of objective ties not exposed by aggregate inputs.",
                       "future_frontier_Q_yield": "NOT_IDENTIFIABLE: public label-selected subset is not a deployable unbiased prescreen",
                       "importance_weighted_tau_power": "NOT_IDENTIFIABLE: changing Q and member masks changes variance and the estimand; 150 count not automatically effective questions"}}
    excluded = [r for r in pooled_rows if not r["common_resolved"]]
    output["cause_summary"] = {"excluded": len(excluded),
        "with_unresolved_reference_actions": sum(r["reference_status_counts"]["UNRESOLVED"] > 0 for r in excluded),
        "with_unavailable_reference_actions": sum(r["reference_status_counts"]["REFERENCE_UNAVAILABLE"] > 0 for r in excluded),
        "with_no_known_feasible_action_but_uncertainty": sum(r["no_known_feasible_but_uncertain"] for r in excluded),
        "with_missing_member_records": sum(r["missing_member_records"] > 0 for r in excluded),
        "distinct_selected_ambiguous_actions_across_questions": sum(len(r["selected_ambiguous_actions"]) for r in excluded),
        "unresolved_reference_actions_across_all_questions": sum(r["reference_status_counts"]["UNRESOLVED"] for r in pooled_rows),
        "member_losses_missing_reference_ambiguity": pooled["member_records"] - pooled["numeric_member_records"]}
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data, provenance = read_inputs(args.inputs)
    result = run(data, provenance)
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pooled": result["pooled_EV4_EV5"], "baseline": result["cost_model"]["baseline"], "refinement_hours": result["reference_refinement"]["sum_elapsed_hours_measured"]}))


if __name__ == "__main__":
    main()
