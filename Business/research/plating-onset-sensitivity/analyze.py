"""DEVELOPMENT public EV4 sensitivity; no solver, model or Carbon runtime import."""

from __future__ import annotations

import argparse
import ast
import collections
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau, rankdata

SOURCE_SHA = "e91f89f9cae53cd7b5e1f252910f197f8a0334adbf47e2bb492d7601dffa91ff"
REF_SHA = "72ea300b42fe1ca4e54b9c6131cb126ca7217ebddd5f1dddca8044a7bcef2dbf"
CPU_SHA = "7452a1a0ac65bfb0638743bebac2a36655dbb61d996988630d99763245e76660"
PRIOR_SHA = "a1473c98baaf2352c02db38b1aeef3938c41b2a958fd1f568cff0c5e29e975b0"
RESULT_BLOB = "67ca13b966a2f6fb4b2e68b084e2909657e7ba7f"
HELPER_BLOB = "b1d899d116317bd190ad6812f0aae5d3e8a16c0c"
CONTRACT_BLOB = "3961b89a98c8877190bc010579852497057d3518"
BINS = ("0-0.5", "0.5-1", "1-2", "2-4", ">4")
FUNCTIONS = {"candidates", "read_refs", "qdef", "ref_assessment"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def pinned(path, expected, git=False):
    raw = path.read_bytes()
    observed = blob(raw.replace(b"\r\n", b"\n")) if git else sha(raw)
    if observed != expected:
        raise ValueError(f"Pinned public input mismatch: {path.name}")
    return raw


def distance_bin(margin_v):
    """Absolute onset distance in mV; bins include their upper endpoint."""
    distance = abs(margin_v) * 1000
    for upper, label in zip((0.5, 1, 2, 4), BINS, strict=False):
        if distance <= upper:
            return label
    return BINS[-1]


def sensitive(reference, cutoff_v, mode):
    """Never changes source records; primary keeps every independent hard FAIL."""
    result = copy.deepcopy(reference)
    if "quantities" not in result:
        return result
    if not any(abs(q["plating_margin_v"]) <= cutoff_v for q in result["quantities"]):
        return result
    if mode == "literal_status_censor":
        result["status"] = "UNRESOLVED"
    elif mode == "plating_only":
        for quantities, checks in zip(
            result["quantities"], result["checks"], strict=True
        ):
            if abs(quantities["plating_margin_v"]) <= cutoff_v:
                checks["no_plating_onset"] = "UNRESOLVED"
        values = [v for checks in result["checks"] for v in checks.values()]
        result["status"] = "INFEASIBLE" if "FAIL" in values else "UNRESOLVED"
    else:
        raise ValueError("Unknown sensitivity mode")
    return result


def tau(x, y):
    if len(x) < 2 or len(y) < 2:
        return None
    value = kendalltau(x, y).statistic
    return float(value) if math.isfinite(value) else None


def numeric(value):
    return isinstance(value, (float, int)) and math.isfinite(value)


def mean(values):
    values = [v for v in values if numeric(v)]
    return float(np.mean(values)) if values else None


def prepare(args):
    source = pinned(args.res07_source, SOURCE_SHA)
    contract = json.loads(pinned(args.contract, CONTRACT_BLOB, git=True))
    historical = json.loads(pinned(args.ev4_results, RESULT_BLOB, git=True))
    pinned(args.helper, HELPER_BLOB, git=True)
    spec = importlib.util.spec_from_file_location("res12_pinned_decision", args.helper)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    definitions = [
        n
        for n in ast.parse(source.decode("utf-8")).body
        if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS
    ]
    if {n.name for n in definitions} != FUNCTIONS:
        raise ValueError("Required unchanged RES-07 functions missing")
    namespace = {
        "CON": contract,
        "PUBLIC": args.public_inputs,
        "json": json,
        "sha": sha,
        "decision": helper,
    }
    exec(  # noqa: S102 -- only exact-hash-bound retained public research functions.
        compile(
            ast.Module(definitions, type_ignores=[]), str(args.res07_source), "exec"
        ),
        namespace,
    )
    refs, observed_sha = namespace["read_refs"]()
    if observed_sha != REF_SHA:
        raise ValueError("Public EV4 reference copy changed")
    candidates = namespace["candidates"](contract)
    namespace.update(
        CAND=candidates,
        REF_INDEX={
            (
                r["inputs"]["c1"],
                r["inputs"]["c2"],
                r["inputs"]["t_amb_c"],
                r["inputs"]["soc0"],
            ): key
            for key, r in refs.items()
        },
    )
    questions = [
        {**s, "split": split}
        for split in ("development", "verification")
        for s in contract["scenarios"][split]
    ]
    truth = {q["id"]: namespace["ref_assessment"](q, refs) for q in questions}
    for q in questions:
        qid = q["id"]
        counts = dict(collections.Counter(r["status"] for r in truth[qid].values()))
        expected = {
            k: v for k, v in historical["references"][qid]["status_counts"].items() if v
        }
        if counts != expected:
            raise ValueError(f"Historical reference labels do not replay: {qid}")
        for member, decisions in historical["decisions"].items():
            original = decisions[qid]["outcome"]
            if original["kind"] == "MODEL_OUTPUT_MISSING":
                continue  # Preserve this historical missing-output bookkeeping verbatim.
            replay = helper.outcome(
                contract,
                candidates,
                original["selected"],
                truth[qid],
                original["baseline"],
            )
            if (
                replay["kind"] != original["kind"]
                or replay["decision_loss"] != original["decision_loss"]
            ):
                raise ValueError(f"Historical decision does not replay: {member}/{qid}")
    return contract, historical, helper, candidates, questions, truth


def cells():
    return {b: collections.Counter() for b in BINS}


def histograms(historical, questions, truth, cohort):
    outputs = {}
    for split in ("development", "verification", "pooled"):
        qs = [q for q in questions if split == "pooled" or q["split"] == split]
        candidates = cells()
        events = cells()
        unique_events = {b: set() for b in BINS}
        event_by_question = {q["id"]: collections.Counter() for q in qs}
        missing = 0
        kinds = collections.Counter()
        near = collections.Counter()
        for q in qs:
            qid = q["id"]
            for row in truth[qid].values():
                if "quantities" not in row:
                    missing += 1
                    continue
                quantities = row["quantities"][0]
                b = distance_bin(quantities["plating_margin_v"])
                candidates[b][row["status"]] += 1
                candidates[b][
                    "negative" if quantities["plating_margin_v"] < 0 else "nonnegative"
                ] += 1
                if abs(quantities["plating_margin_v"]) <= 0.002:
                    near["all"] += 1
                    near[row["status"]] += 1
                    for key, value in row["checks"][0].items():
                        if value == "FAIL":
                            near[f"FAIL:{key}"] += 1
            for member in cohort:
                outcome = historical["decisions"][member][qid]["outcome"]
                kinds[outcome["kind"]] += 1
                if outcome["kind"] != "SELECTED_INFEASIBLE":
                    continue
                row = truth[qid][outcome["selected"]]
                b = distance_bin(row["quantities"][0]["plating_margin_v"])
                events[b]["events"] += 1
                unique_events[b].add((qid, outcome["selected"]))
                event_by_question[qid][b] += 1
                events[b]["penalty_units"] += outcome["decision_loss"]
                failures = [k for k, v in row["checks"][0].items() if v == "FAIL"]
                for failure in failures:
                    events[b][f"FAIL:{failure}"] += 1
                events[b][
                    (
                        "plating_only_FAIL"
                        if failures == ["no_plating_onset"]
                        else "other_or_multiple_FAIL"
                    )
                ] += 1
                if abs(row["quantities"][0]["plating_margin_v"]) <= 0.002:
                    near["unsafe_selected"] += 1
        total = sum(v["events"] for v in events.values())
        penalty = sum(v["penalty_units"] for v in events.values())
        event_rows = {
            b: {
                **dict(v),
                "unique_selected_action_condition_pairs": len(unique_events[b]),
                "event_share": v["events"] / total if total else None,
                "penalty_share": v["penalty_units"] / penalty if penalty else None,
            }
            for b, v in events.items()
        }
        outputs[split] = {
            "members": len(cohort),
            "offered_questions": len(qs),
            "candidate_counts": {b: dict(v) for b, v in candidates.items()},
            "unavailable_candidates": missing,
            "events": event_rows,
            "total_unsafe_events": total,
            "total_unsafe_penalty_units": penalty,
            "outcome_counts": dict(kinds),
            "inclusive_within_2mv": dict(near),
            "unsafe_events_by_question": {
                q: dict(v) for q, v in event_by_question.items()
            },
        }
    return outputs


def rank_comparison(old, new):
    members = sorted(m for m in old if numeric(old[m]) and numeric(new[m]))
    x, y = [old[m] for m in members], [new[m] for m in members]
    ranks_x, ranks_y = rankdata(x), rankdata(y)
    reversals = ties = comparable = 0
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            a, b = np.sign(x[i] - x[j]), np.sign(y[i] - y[j])
            comparable += bool(a)
            reversals += bool(a * b < 0)
            ties += bool(a and not b)
    return {
        "members": len(members),
        "excluded_non_numeric": len(old) - len(members),
        "tau_b": tau(x, y),
        "strict_pairs_before": comparable,
        "strict_reversals": reversals,
        "strict_order_to_tie": ties,
        "maximum_average_rank_shift": (
            float(max(abs(ranks_y - ranks_x))) if members else None
        ),
    }


def sensitivities(contract, historical, helper, candidates, questions, truth, cohort):
    results = {}
    for mode in ("plating_only", "literal_status_censor"):
        alt = {
            qid: {cid: sensitive(row, 0.002, mode) for cid, row in rows.items()}
            for qid, rows in truth.items()
        }
        transitions = collections.Counter(
            f"{row['status']}->{alt[qid][cid]['status']}"
            for qid, rows in truth.items()
            for cid, row in rows.items()
            if row["status"] != alt[qid][cid]["status"]
        )
        changed = {}
        for q in questions:
            qid = q["id"]
            changed[qid] = {}
            for m in historical["decisions"]:
                old = historical["decisions"][m][qid]["outcome"]
                if old["kind"] == "MODEL_OUTPUT_MISSING":
                    changed[qid][m] = copy.deepcopy(old)
                    continue
                changed[qid][m] = helper.outcome(
                    contract, candidates, old["selected"], alt[qid], old["baseline"]
                )
        splits = {}
        for split in ("development", "verification", "pooled"):
            qs = [
                q["id"] for q in questions if split == "pooled" or q["split"] == split
            ]
            original = {
                m: [historical["decisions"][m][q]["outcome"] for q in qs]
                for m in cohort
            }
            revised = {m: [changed[q][m] for q in qs] for m in cohort}
            old_loss = {
                m: mean(o["decision_loss"] for o in original[m]) for m in cohort
            }
            new_loss = {m: mean(o["decision_loss"] for o in revised[m]) for m in cohort}
            common = [
                q
                for q in qs
                if all(
                    numeric(historical["decisions"][m][q]["outcome"]["decision_loss"])
                    and numeric(changed[q][m]["decision_loss"])
                    for m in cohort
                )
            ]
            common_old = {
                m: mean(
                    historical["decisions"][m][q]["outcome"]["decision_loss"]
                    for q in common
                )
                for m in cohort
            }
            common_new = {
                m: mean(changed[q][m]["decision_loss"] for q in common) for m in cohort
            }
            rule_taus = {}
            for rule in sorted(next(iter(historical["rule_scores"].values()))):
                scored = [
                    m
                    for m in cohort
                    if numeric(historical["rule_scores"][m][rule])
                    and numeric(old_loss[m])
                    and numeric(new_loss[m])
                ]
                if not scored:
                    continue
                scores = [historical["rule_scores"][m][rule] for m in scored]
                rule_taus[rule] = {
                    "members": len(scored),
                    "original": tau(scores, [-old_loss[m] for m in scored]),
                    "sensitivity": tau(scores, [-new_loss[m] for m in scored]),
                }
            changed_outcomes = collections.Counter(
                f"{old['kind']}->{new['kind']}"
                for m in cohort
                for old, new in zip(original[m], revised[m], strict=True)
                if old["kind"] != new["kind"]
            )
            per_member = {
                m: {
                    "original_loss": old_loss[m],
                    "sensitivity_loss": new_loss[m],
                    "original_numeric": sum(
                        numeric(o["decision_loss"]) for o in original[m]
                    ),
                    "sensitivity_numeric": sum(
                        numeric(o["decision_loss"]) for o in revised[m]
                    ),
                    "unsafe_before": sum(
                        o["kind"] == "SELECTED_INFEASIBLE" for o in original[m]
                    ),
                    "unsafe_after": sum(
                        o["kind"] == "SELECTED_INFEASIBLE" for o in revised[m]
                    ),
                }
                for m in cohort
            }
            old_rank = (
                dict(zip(cohort, rankdata([old_loss[m] for m in cohort]), strict=True))
                if all(numeric(old_loss[m]) for m in cohort)
                else {}
            )
            new_rank = (
                dict(zip(cohort, rankdata([new_loss[m] for m in cohort]), strict=True))
                if all(numeric(new_loss[m]) for m in cohort)
                else {}
            )
            for m in cohort:
                per_member[m].update(
                    original_average_rank=float(old_rank[m]) if m in old_rank else None,
                    sensitivity_average_rank=(
                        float(new_rank[m]) if m in new_rank else None
                    ),
                )
            valid = [m for m in cohort if numeric(old_loss[m]) and numeric(new_loss[m])]
            unsafe_fraction_old = [
                per_member[m]["unsafe_before"] / per_member[m]["original_numeric"]
                for m in valid
            ]
            unsafe_fraction_new = [
                per_member[m]["unsafe_after"] / per_member[m]["sensitivity_numeric"]
                for m in valid
            ]
            loss_unsafe_tau = {
                "original": tau([old_loss[m] for m in valid], unsafe_fraction_old),
                "sensitivity": tau([new_loss[m] for m in valid], unsafe_fraction_new),
            }
            common_unsafe = [
                mean(
                    float(
                        historical["decisions"][m][q]["outcome"]["kind"]
                        == "SELECTED_INFEASIBLE"
                    )
                    for q in common
                )
                for m in cohort
            ]
            common_tau = (
                tau(list(common_old.values()), common_unsafe) if common else None
            )
            splits[split] = {
                "offered_questions": len(qs),
                "rank_comparison": rank_comparison(old_loss, new_loss),
                "common_mask": {
                    "question_count": len(common),
                    "rank_comparison": rank_comparison(common_old, common_new),
                    "original_loss_vs_unsafe_fraction_tau": common_tau,
                },
                "original_mean_loss": mean(old_loss.values()),
                "sensitivity_mean_loss": mean(new_loss.values()),
                "outcome_transitions": dict(changed_outcomes),
                "rule_tau": rule_taus,
                "loss_vs_unsafe_fraction_tau": loss_unsafe_tau,
                "per_member": per_member,
            }
        controls = {
            m: {
                "original_loss": mean(
                    historical["decisions"][m][q["id"]]["outcome"]["decision_loss"]
                    for q in questions
                    if q["split"] == "verification"
                ),
                "sensitivity_loss": mean(
                    changed[q["id"]][m]["decision_loss"]
                    for q in questions
                    if q["split"] == "verification"
                ),
                "unsafe_before": sum(
                    historical["decisions"][m][q["id"]]["outcome"]["kind"]
                    == "SELECTED_INFEASIBLE"
                    for q in questions
                    if q["split"] == "verification"
                ),
                "unsafe_after": sum(
                    changed[q["id"]][m]["kind"] == "SELECTED_INFEASIBLE"
                    for q in questions
                    if q["split"] == "verification"
                ),
            }
            for m, row in historical["summary"]["members"].items()
            if row["kind"] != "RECONSTRUCTED"
        }
        results[mode] = {
            "candidate_status_transitions": dict(transitions),
            "splits": splits,
            "controls_verification": controls,
        }
    return results


def run(args):
    contract, historical, helper, candidates, questions, truth = prepare(args)
    cohorts = {
        "eligible_reconstructed_99": sorted(
            m
            for m, row in historical["summary"]["members"].items()
            if row["kind"] == "RECONSTRUCTED" and row["eligible"]
        ),
        "all_reconstructed_100": sorted(
            m
            for m, row in historical["summary"]["members"].items()
            if row["kind"] == "RECONSTRUCTED"
        ),
        "controls_5": sorted(
            m
            for m, row in historical["summary"]["members"].items()
            if row["kind"] != "RECONSTRUCTED"
        ),
    }
    result = {
        "schema": "res12.public-plating-sensitivity.v1",
        "maturity": "DEVELOPMENT",
        "cutoff_v": 0.002,
        "cutoff_status": "OWNER_REQUESTED_SENSITIVITY_NOT_A_GATE",
        "historical_plating_band_v": contract["reference"]["uncertainty"]["bands"][
            "plating_margin_v"
        ],
        "provenance": {
            "res07_sha256": SOURCE_SHA,
            "reference_sha256": REF_SHA,
            "ev4_results_git_blob": RESULT_BLOB,
            "helper_git_blob": HELPER_BLOB,
            "contract_git_blob": CONTRACT_BLOB,
        },
        "bins_mv": list(BINS),
        "bin_rule": "[0,.5], (.5,1], (1,2], (2,4], (4,infinity); inclusive <=2mV sensitivity",
        "cohorts": {
            name: {
                "histograms": histograms(historical, questions, truth, cohort),
                "sensitivity": sensitivities(
                    contract, historical, helper, candidates, questions, truth, cohort
                ),
            }
            for name, cohort in cohorts.items()
        },
    }
    cpu_rows = json.loads(pinned(args.cpu_outcomes, CPU_SHA))
    prior = json.loads(pinned(args.res07_results, PRIOR_SHA))
    inventory = prior["inventory"]
    if len(cpu_rows) != 148 or inventory["public_reference_sha256"] != REF_SHA:
        raise ValueError("Retained CPU cohort/reference mismatch")
    # Verify every retained bundle identity without running any model or reading
    # beyond the owner's explicitly public EV4 folder and committed allowlist.
    for entry in inventory["bundle_manifest"]:
        pinned(args.public_inputs / entry["folder"] / entry["file"], entry["sha256"])
    cpu = {"summary": {"members": {}}, "decisions": {}, "rule_scores": {}}
    cpu_cohorts = collections.defaultdict(list)
    for row in cpu_rows:
        member = row["member"]
        kind = row["kind"]
        cpu_cohorts[kind].append(member)
        cpu["summary"]["members"][member] = {
            "kind": "RECONSTRUCTED" if kind == "EV4_REAL_CPU_REBUILD" else kind
        }
        cpu["decisions"][member] = {
            q["id"]: row["questions"][q["id"]] for q in questions
        }
        cpu["rule_scores"][
            member
        ] = {}  # Historical A40 scores are not paired CPU evidence.
        for q in questions:
            old = cpu["decisions"][member][q["id"]]["outcome"]
            replay = helper.outcome(
                contract, candidates, old["selected"], truth[q["id"]], old["baseline"]
            )
            if (
                replay["kind"] != old["kind"]
                or replay["decision_loss"] != old["decision_loss"]
            ):
                raise ValueError(
                    "Retained CPU decision no longer matches pinned reference"
                )
        for split, family in (("development", "nominal"), ("verification", "shifted")):
            outcomes = [
                cpu["decisions"][member][q["id"]]["outcome"]
                for q in questions
                if q["split"] == split
            ]
            expected = prior["fresh_member_summary"][member][family]
            if (
                abs(mean(o["decision_loss"] for o in outcomes) - expected["loss"])
                > 1e-12
                or sum(o["kind"] == "SELECTED_INFEASIBLE" for o in outcomes)
                != expected["observed_unsafe"]
            ):
                raise ValueError(
                    "Retained CPU outcomes disagree with committed RES-07 summary"
                )
    if {k: len(v) for k, v in cpu_cohorts.items()} != inventory["cohort_counts"]:
        raise ValueError("Retained CPU cohort counts changed")
    result["provenance"].update(
        cpu_outcomes_sha256=CPU_SHA, res07_results_sha256=PRIOR_SHA
    )
    result["cpu_cohorts"] = {
        kind: {
            "histograms": histograms(cpu, questions, truth, sorted(cohort)),
            "sensitivity": sensitivities(
                contract, cpu, helper, candidates, questions, truth, sorted(cohort)
            ),
        }
        for kind, cohort in sorted(cpu_cohorts.items())
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--res07-source", type=Path, required=True)
    parser.add_argument("--public-inputs", type=Path, required=True)
    parser.add_argument("--ev4-results", type=Path, required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-outcomes", type=Path, required=True)
    parser.add_argument("--res07-results", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
