"""Hash-bound public summary audit, without Carbon or solver imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

BASE = "07d414638f1ede517d59cca2a30554360d934716"
INPUTS = {
    "ev4.json": (
        "docs/development/evidence/ev4-2026-10-01/results.json",
        "67ca13b966a2f6fb4b2e68b084e2909657e7ba7f",
    ),
    "ev5.json": (
        "docs/development/evidence/ev5-2026-10-03/results.json",
        "7d6ccf75a47c2df56c66d0b223300e5fd9398512",
    ),
    "analysis.json": (
        "docs/development/evidence/ev5-2026-10-03/analysis.json",
        "c2131424a3d979b71b2881a114507c2b9dcd9bf6",
    ),
}


def numeric(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def service_loss(outcome, unit):
    if not numeric(unit) or unit <= 0:
        raise ValueError("Positive normalization required")
    if outcome["kind"] == "SELECTED_FEASIBLE":
        gap = outcome["gap_to_best_in_set_s"]
        if not numeric(gap) or gap < 0:
            raise ValueError("Invalid reference gap")
        return min(1.0, gap / unit)
    if outcome["kind"] in {"SELECTED_REFERENCE_UNAVAILABLE", "MODEL_OUTPUT_MISSING"}:
        return None
    if outcome["kind"] in {
        "SELECTED_INFEASIBLE",
        "SELECTED_UNRESOLVED",
        "MISSED_OPPORTUNITY",
        "CORRECT_ABSTENTION",
        "ABSTENTION_UNRESOLVED",
    }:
        return 1.0
    raise ValueError("Unknown outcome")


def interval_rank(score, real_scores):
    above = sum(s > score for s in real_scores)
    equal = sum(s == score for s in real_scores)
    return [1 + above, 1 + above + equal]


def tau(scores, losses):
    concordance = sx = sy = 0
    for i in range(len(scores)):
        for j in range(i):
            dx = (scores[i] > scores[j]) - (scores[i] < scores[j])
            dy = (losses[i] < losses[j]) - (losses[i] > losses[j])
            concordance += dx * dy
            sx += bool(dx)
            sy += bool(dy)
    return concordance / math.sqrt(sx * sy) if sx and sy else None


def audit_panel(data, unit):
    real = [
        m
        for m, row in data["summary"]["members"].items()
        if row["eligible"] and row["kind"] == "RECONSTRUCTED"
    ]
    all_members = [
        m for m, row in data["summary"]["members"].items() if row["eligible"]
    ]
    questions = {
        s: [q for q, r in data["references"].items() if r["split"] == s]
        for s in ("development", "verification")
    }

    def mean_loss(member, split):
        vals = [
            service_loss(data["decisions"][member][q]["outcome"], unit)
            for q in questions[split]
        ]
        return sum(vals) / len(vals) if vals and all(numeric(v) for v in vals) else None

    losses = {m: mean_loss(m, "verification") for m in all_members}
    a = {m: 1 / (1 + data["components"][m]["E"]) for m in all_members}
    v = {m: mean_loss(m, "development") for m in all_members}
    scores = {
        "A": a,
        "VERIFY-R_k1": {
            m: 1 / (1 + z) if z is not None else None for m, z in v.items()
        },
    }
    result = {"real_members": len(real), "questions": questions, "rules": {}}
    for name, mapping in scores.items():
        usable = [m for m in real if numeric(mapping[m]) and numeric(losses[m])]
        vals = [mapping[m] for m in usable]
        row = {
            "tau_against_full_V_service": tau(vals, [losses[m] for m in usable]),
            "real_members_measurable": len(usable),
            "controls_and_attacks": {},
        }
        for m in all_members:
            if m in real:
                continue
            score = mapping[m]
            loss = losses[m]
            inversions = (
                [u for u in usable if mapping[u] <= score and losses[u] < loss]
                if numeric(score) and numeric(loss)
                else []
            )
            row["controls_and_attacks"][m] = {
                "score": score,
                "rank_against_real_plus_this_member": (
                    interval_rank(score, vals) if numeric(score) else None
                ),
                "V_mean_service_loss": loss,
                "V_unsafe_single_picks": sum(
                    data["decisions"][m][q]["outcome"]["kind"] == "SELECTED_INFEASIBLE"
                    for q in questions["verification"]
                ),
                "better_value_real_members_with_no_higher_score": len(inversions),
                "maximum_V_loss_gap": max(
                    (loss - losses[u] for u in inversions), default=0
                ),
                "whole_error": data["components"][m]["E"],
            }
        result["rules"][name] = row
    result["fixed_list_error_reduction_counterfactual"] = []
    for retained in (0.0, 0.5, 1.0):
        gain = [1 / (1 + data["components"][m]["E"] * retained) - a[m] for m in real]
        result["fixed_list_error_reduction_counterfactual"].append(
            {
                "error_retained": retained,
                "A_increased_count": sum(g > 0 for g in gain),
                "A_gain_low_base_high_min_median_max": [
                    min(gain),
                    sorted(gain)[len(gain) // 2],
                    max(gain),
                ],
                "VERIFY_R_gain": 0,
                "basis": "ASSUMPTION aggregate perturbation, decisions frozen; not a trained attack",
            }
        )
    return result


def count_allowance(n, cutoff, strict=True):
    """Maximum integer false accepts passing a rate gate."""
    if n <= 0 or not 0 <= cutoff <= 1:
        raise ValueError("Invalid gate inputs")
    return max(
        (k for k in range(n + 1) if (k / n <= cutoff if strict else k / n < cutoff)),
        default=-1,
    )


def run(directory):
    data, sources = {}, {}
    for name, (path, expected) in INPUTS.items():
        raw = (directory / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != expected:
            raise ValueError(f"Public input mismatch: {name}")
        data[name] = json.loads(raw)
        sources[name] = {
            "path": path,
            "commit": BASE,
            "git_blob": blob,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    near = data["analysis.json"]["value"]["H3"]["report"]["members"]
    return {
        "schema": "carbon.research.score-candidate-attacks.v1",
        "maturity": "DEVELOPMENT_PUBLIC_DIAGNOSTICS",
        "sources": sources,
        "normalization_s_low_base_high": [60, 120, 240],
        "normalization_basis": "ASSUMPTION sensitivity; 120 is historical minimum-useful improvement",
        "panels": {
            name: {str(u): audit_panel(data[name + ".json"], u) for u in (60, 120, 240)}
            for name in ("ev4", "ev5")
        },
        "EV5_near_constraint_measurements": {m: near[m]["measurement"] for m in near},
        "discrete_gate_allowances": [
            {
                "reference_fail": n,
                "cutoff": c,
                "reject_if": op,
                "largest_passing_FA_count": count_allowance(n, c, op == ">"),
            }
            for n in (74, 67)
            for c in (0.005, 0.01, 0.02, 0.05)
            for op in (">", ">=")
        ],
        "unidentified": [
            "raw score-set Q3 q",
            "scoring-set joint G-FEAS",
            "prediction-margin perturbations",
            "real top-k orders",
            "causal easy-region-only change",
            "copying prevalence",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=Path(__file__).parent / "inputs")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).parent / "results.json"
    )
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(run(args.inputs), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
