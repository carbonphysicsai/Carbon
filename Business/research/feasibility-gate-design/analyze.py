"""Digest-bound public aggregate research; no Carbon, solver or network imports."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import platform
import re

import numpy as np

BASE = "0d1370d01ec4bf76c38627c85b9426910d8be3a3"
INPUTS = {
    "ev5.json": ("docs/development/evidence/ev5-2026-10-03/results.json", "7d6ccf75a47c2df56c66d0b223300e5fd9398512"),
    "analysis.json": ("docs/development/evidence/ev5-2026-10-03/analysis.json", "c2131424a3d979b71b2881a114507c2b9dcd9bf6"),
    "run5-results.json": ("docs/development/evidence/graphite-run5-q1/results.json", "2ea791a0c8dd8badd41a9d5823d491ec39ee9ed8"),
    "run5-defences.json": ("docs/development/evidence/graphite-run5-q1/defences.json", "d35c544075dac3f20588ba42c27e988303aca304"),
    "run5-report.json": ("docs/development/evidence/graphite-run5-q1/q1-report.json", "bcc6e905f635b4aa08aacb870d4ee132aa5e14a2"),
}
GRID = (0.0, .005, .01, .02, .025, .05, .075, .1, .2, .5, 1.0, 1.01, 2.0)


def read_inputs(directory):
    data, provenance = {}, {}
    for name, (source, expected) in INPUTS.items():
        raw = (directory / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != expected:
            raise ValueError(f"Public input hash mismatch: {name}")
        data[name] = json.loads(raw)
        provenance[name] = {"path": source, "git_blob": blob, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "source_commit": BASE}
    return data, provenance


def recipe(member):
    key = re.sub(r"-s[0-9]+$", "", member)
    # Public run-5 alias diagnosis: merge this prediction-identical pair.
    return key.replace("graphite-run5-p-fa70c075f903", "graphite-run5-p-69268f1b74ec")


def binomial_tail(n, p, k):
    if k <= 0:
        return 1.0
    if k > n or p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    return min(1.0, math.fsum(math.exp(math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1) + x * math.log(p) + (n - x) * math.log1p(-p)) for x in range(k, n + 1)))


@lru_cache(maxsize=None)
def exact_ci(k, n):
    """Clopper-Pearson sensitivity interval; iid-recipe assumption, NOT population assurance."""
    if n == 0:
        return [None, None]
    def solve(fn, target):
        lo, hi = 0.0, 1.0
        for _ in range(55):
            mid = (lo + hi) / 2
            if fn(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    return [0.0 if not k else solve(lambda p: binomial_tail(n, p, k), .025), 1.0 if k == n else solve(lambda p: binomial_tail(n, p, k + 1), .975)]


def numeric(x):
    return isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)


def state(results, member, split):
    rows = [d for d in results["decisions"][member].values() if d["split"] == split]
    if any(d["outcome"]["kind"] == "SELECTED_INFEASIBLE" for d in rows):
        return "UNSAFE_OBSERVED"
    if rows and all(numeric(d["outcome"].get("decision_loss")) for d in rows):
        return "NO_UNSAFE_FULLY_RESOLVED"
    return "UNKNOWN_NO_UNSAFE_OBSERVED"


def fail(value, cutoff, comparison):
    if value is None:
        return True
    return value > cutoff if comparison == "exceeds" else value >= cutoff


def tau(scores, losses):
    x, y = np.asarray(scores), np.asarray(losses)
    i, j = np.triu_indices(len(x), 1)
    dx = (x[i] > x[j]).astype(int) - (x[i] < x[j]).astype(int)
    dy = (y[i] < y[j]).astype(int) - (y[i] > y[j]).astype(int)
    den = math.sqrt(float(np.count_nonzero(dx) * np.count_nonzero(dy)))
    return None if not den else float((dx * dy).sum() / den)


def common_questions(results, members, split):
    return sorted(q for q, r in results["references"].items() if r["split"] == split and all(numeric(results["decisions"][m][q]["outcome"].get("decision_loss")) for m in members))


def proxy_aq(results, members):
    """Disjoint D/V historical proxy. NOT actual Q3 or a registry score."""
    dev, ver = common_questions(results, members, "development"), common_questions(results, members, "verification")
    if not dev or not ver:
        return None
    def mean(m, qs):
        return float(np.mean([results["decisions"][m][q]["outcome"]["decision_loss"] for q in qs]))
    return {"development_questions": dev, "verification_questions": ver,
            "score": {m: math.sqrt((1 / (1 + results["components"][m]["E"])) * (1 / (1 + mean(m, dev)))) for m in members},
            "loss": {m: mean(m, ver) for m in members}}


def counts(results, members, failed, split):
    groups = defaultdict(list)
    states = {m: state(results, m, split) for m in members}
    for m in members:
        groups[recipe(m)].append(m)
    unsafe = {r: [m for m in ms if states[m] == "UNSAFE_OBSERVED"] for r, ms in groups.items() if any(states[m] == "UNSAFE_OBSERVED" for m in ms)}
    safe = {r: ms for r, ms in groups.items() if all(states[m] == "NO_UNSAFE_FULLY_RESOLVED" for m in ms)}
    unknown = {r: ms for r, ms in groups.items() if r not in unsafe and r not in safe}
    caught = sum(all(failed[m] for m in ms) for ms in unsafe.values())
    rejected = sum(any(failed[m] for m in ms) for ms in safe.values())
    um = [m for m in members if states[m] == "UNSAFE_OBSERVED"]
    sm = [m for m in members if states[m] == "NO_UNSAFE_FULLY_RESOLVED"]
    # Complement is shown but explicitly cannot be called the safe class.
    nonunsafe = [m for m in members if states[m] != "UNSAFE_OBSERVED"]
    safe_events = [(m, q) for m in members for q, d in results["decisions"][m].items()
                   if d["split"] == split and d["outcome"]["kind"] in ("SELECTED_FEASIBLE", "CORRECT_ABSTENTION")]
    return {
        "unsafe_recipes": len(unsafe), "caught_recipes_all_unsafe_seeds": caught,
        "recall": caught / len(unsafe) if unsafe else None, "recall_ci95_iid_recipe_sensitivity": exact_ci(caught, len(unsafe)),
        "fully_resolved_no_unsafe_recipes": len(safe), "rejected_recipes_any_seed": rejected,
        "safe_rejection": rejected / len(safe) if safe else None, "safe_rejection_ci95_iid_recipe_sensitivity": exact_ci(rejected, len(safe)),
        "unknown_recipes": len(unknown), "unknown_rejected_recipes_any_seed": sum(any(failed[m] for m in ms) for ms in unknown.values()),
        "unsafe_members": len(um), "caught_unsafe_members": sum(failed[m] for m in um),
        "fully_resolved_no_unsafe_members": len(sm), "rejected_safe_members": sum(failed[m] for m in sm),
        "no_observed_unsafe_members_including_unknown": len(nonunsafe), "rejected_no_observed_unsafe_members_including_unknown": sum(failed[m] for m in nonunsafe),
        "safe_decision_events": len(safe_events), "rejected_safe_decision_events": sum(failed[m] for m, q in safe_events),
        "safe_event_rejection_not_recipe_specificity": sum(failed[m] for m, q in safe_events) / len(safe_events) if safe_events else None,
    }


def summarize_gate(results, values, cutoff, comparison, split, proxy=None):
    members = sorted(m for m, row in results["summary"]["members"].items() if row["kind"] == "RECONSTRUCTED" and row["eligible"])
    failed = {m: fail(values.get(m), cutoff, comparison) for m in results["summary"]["members"]}
    output = {"cutoff": cutoff, "comparison": comparison, **counts(results, members, failed, split), "passing_real_members": sum(not failed[m] for m in members)}
    output["failed_controls"] = [m for m, row in results["summary"]["members"].items() if row["kind"] == "SYNTHETIC_CONTROL" and failed[m]]
    attacks = [m for m, row in results["summary"]["members"].items() if row["kind"] == "ATTACK_CONSTRUCTION" and row["eligible"]]
    output["unsafe_adversarial_pass"] = [m for m in attacks if state(results, m, split) == "UNSAFE_OBSERVED" and not failed[m]]
    if proxy is not None:
        scores = [(-math.inf if failed[m] else proxy["score"][m]) for m in members]
        losses = [proxy["loss"][m] for m in members]
        ordered = sorted((m for m in members if not failed[m]), key=lambda m: (-proxy["score"][m], m))
        output["disjoint_D_proxy_AQ"] = {"tau_verification": tau(scores, losses), "top_member": ordered[0] if ordered else None,
            "top_loss": proxy["loss"][ordered[0]] if ordered else None,
            "top_member_unsafe_on_any_verification_question": state(results, ordered[0], "verification") == "UNSAFE_OBSERVED" if ordered else None,
            "none_eligible": not ordered}
    return output


def d_grid_rates(results):
    """JOINT false-feasible on D decision grids; NOT registered scoring-set G-FEAS."""
    out = {}
    for m in results["summary"]["members"]:
        by_temp = defaultdict(lambda: [0, 0])
        for q, r in results["references"].items():
            if r["split"] != "development":
                continue
            a = results["decisions"][m][q]["agreement"]
            # Joint feasibility agreement uses only reference-resolved candidates.
            if a is None or a.get("false_acceptances") is None:
                out[m] = {"pooled": None, "worst_temperature": None}
                break
            temp = q.split("-S")[0]
            by_temp[temp][0] += a["false_acceptances"]
            by_temp[temp][1] += r["status_counts"]["INFEASIBLE"]
        else:
            k, n = map(sum, zip(*by_temp.values()))
            out[m] = {"pooled": k / n if n else None,
                      "worst_temperature": max((a / b for a, b in by_temp.values() if b), default=None)}
    return out


def curve(results, values, split, proxy=None):
    observed = sorted({float(v) for v in values.values() if numeric(v)})
    cutoffs = sorted(set(GRID) | set(observed) | {math.nextafter(max(observed), math.inf)})
    # Both comparisons at every breakpoint give the COMPLETE empirical step curve.
    points, records, lookup = [], [], {}
    for t in cutoffs:
        for cmp in ("at_or_above", "exceeds"):
            row = summarize_gate(results, values, t, cmp, split, proxy)
            del row["cutoff"], row["comparison"]
            identity = json.dumps(row, sort_keys=True)
            if identity not in lookup:
                lookup[identity] = len(records)
                records.append(row)
            points.append({"cutoff": t, "comparison": cmp, "record": lookup[identity]})
    return {"points": points, "tradeoffs": records}


def run(data, provenance):
    ev5, analysis, run5, defences, report = [data[k] for k in INPUTS]
    if analysis["results_sha256"].removeprefix("sha256:") != provenance["ev5.json"]["sha256"]:
        raise ValueError("EV5 analysis/result binding mismatch")
    fa = {m: r["measurement"] for m, r in analysis["value"]["H3"]["report"]["members"].items()}
    fa.update(analysis["value"]["H3"]["report"]["controls"])
    near = {m: r["near_optimism_bands"] for m, r in analysis["gate"]["members"].items()}
    measures = {"near": near, "error": {m: c["E"] for m, c in ev5["components"].items()},
        "plating_fa": {m: r["constraints"]["no_plating_onset"]["false_acceptance_rate"] if r else None for m, r in fa.items()},
        "worst_constraint_fa": {m: r["worst_false_acceptance_rate"] if r else None for m, r in fa.items()}}
    d_rates = d_grid_rates(ev5)
    measures.update({"D_grid_joint_feasibility": {m: r["pooled"] for m, r in d_rates.items()}, "D_grid_worst_temperature": {m: r["worst_temperature"] for m, r in d_rates.items()}})
    real = sorted(m for m, s in ev5["summary"]["members"].items() if s["kind"] == "RECONSTRUCTED" and s["eligible"])
    proxy = proxy_aq(ev5, real)
    output = {"schema": "carbon.research.feasibility-gate-design.v1", "label": "PUBLIC DEVELOPMENT RESEARCH; NO QUALIFICATION", "sources": provenance,
        "numeric_policy": "Source counts/point estimates low=base=high; intervals supplied separately. Grids, iid-recipe assumption and 95% confidence are exploratory ASSUMPTION; production thresholds HUMAN_INPUT.",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "canonical": False},
        "inventory": {"eligible_real_members": len(real), "recipe_clusters": len({recipe(m) for m in real}), "verification_label_states": dict(Counter(state(ev5, m, "verification") for m in real))},
        "actual_AQ": {"status": "NOT_IDENTIFIABLE", "reason": "Committed public inputs have no member-wise Q3 regret leg. Historical D decision loss is NOT Q3."},
        "proxy": {"label": "DISJOINT_DEVELOPMENT_DECISION_LOSS_PROXY_NOT_Q3", "formula": "sqrt((1/(1+E))*(1/(1+mean_D_loss)))", "development_questions": proxy["development_questions"], "verification_questions": proxy["verification_questions"]},
        "ev5_curves_verification": {k: curve(ev5, v, "verification", proxy) for k, v in measures.items()},
        "ev5_member_measurements": {m: {"recipe": recipe(m), "verification_state": state(ev5, m, "verification"), **{k: v.get(m) for k, v in measures.items()}} for m in ev5["summary"]["members"]},
        "unmeasurable": {"scoring_set_joint_G_FEAS": "NOT_IDENTIFIABLE: constraint counts do not determine joint case counts", "calibrated_margin": "NOT_IDENTIFIABLE: no case-level prediction residuals", "conformal_abstention": "NOT_IDENTIFIABLE: no disjoint calibration/selection rows", "scoring_set_worst_stratum": "NOT_IDENTIFIABLE: H3 counts are not stratum-indexed"}}
    output["combinations_exploratory"] = []
    for p in (.005, .01, .02, .05, .1):
        for n in (.25, .5, 1.0, 2.0):
            # Derived OR gate: not representable by current registry-v5 single measure.
            values = {m: max(measures["plating_fa"].get(m, math.inf) / p, near.get(m, math.inf) / n) for m in ev5["summary"]["members"]}
            row = summarize_gate(ev5, values, 1.0, "exceeds", "verification", proxy)
            row.update({"plating_cutoff": p, "near_cutoff": n, "registry_v5_compatible": False})
            output["combinations_exploratory"].append(row)
    run5_fa = report["near_limit_false_acceptance"]["members"]
    rmeasures = {"near": {m: r["near_optimism_bands"] for m, r in defences["gate"]["members"].items()},
        "plating_fa": {m: r["constraints"]["no_plating_onset"]["false_acceptance_rate"] for m, r in run5_fa.items()},
        "worst_constraint_fa": {m: r["worst_false_acceptance_rate"] for m, r in run5_fa.items()},
        "error": {m: c["E"] for m, c in run5["components"].items()}}
    output["run5_curves_development_adaptively_seen"] = {k: curve(run5, v, "development") for k, v in rmeasures.items()}
    output["run5_member_measurements"] = {m: {"recipe_cluster": recipe(m), "development_state": state(run5, m, "development"), **{k: v.get(m) for k, v in rmeasures.items()}} for m in defences["gate"]["members"]}
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data, provenance = read_inputs(args.inputs)
    result = run(data, provenance)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["inventory"]))


if __name__ == "__main__":
    main()
