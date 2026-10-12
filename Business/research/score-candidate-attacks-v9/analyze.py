"""Digest-bound public aggregate diagnostics; no evaluator/solver imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

BASE = "fcab655b30f42d4e3a42786f22af8aa2b08402e2"
REGISTRY_HEAD = "e99881523712d2a8969a003a7ffcdd99641f1d01"
INPUTS = {
    "ev4.json": (
        BASE,
        "docs/development/evidence/ev4-2026-10-01/results.json",
        "67ca13b966a2f6fb4b2e68b084e2909657e7ba7f",
    ),
    "ev5.json": (
        BASE,
        "docs/development/evidence/ev5-2026-10-03/results.json",
        "7d6ccf75a47c2df56c66d0b223300e5fd9398512",
    ),
    "analysis.json": (
        BASE,
        "docs/development/evidence/ev5-2026-10-03/analysis.json",
        "c2131424a3d979b71b2881a114507c2b9dcd9bf6",
    ),
    "registry-v9.json": (
        REGISTRY_HEAD,
        "docs/development/evidence/battery-score-tuning/registry-v9.json",
        "698aa61873e6970039d0c8a9d76da21a4a269412",
    ),
    "public-dev-split-v1.json": (
        REGISTRY_HEAD,
        "docs/development/evidence/battery-score-tuning/public-dev-split-v1.json",
        "befed141a5fb6283a96722efb3862de12c29362f",
    ),
}
EXPECTED = {
    "A",
    "R",
    "P",
    "ARP",
    "V3",
    "ARP-V3",
    "ENV/ARP",
    "ENV/ARP-V3",
    "A-Q",
    "G-FEAS/A-Q>",
}
UNITS = (60, 120, 240, 1200)


def numeric(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def load_public(directory):
    data, provenance = {}, {}
    for name, (commit, path, expected) in INPUTS.items():
        raw = (directory / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != expected:
            raise ValueError(f"Public input digest mismatch: {name}")
        data[name] = json.loads(raw)
        provenance[name] = {
            "commit": commit,
            "path": path,
            "git_blob": blob,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    if {r["id"] for r in data["registry-v9.json"]["candidates"]} != EXPECTED:
        raise ValueError(
            "Registry changed: version the audit rather than silently extending it"
        )
    return data, provenance


def tau(scores, losses):
    x, y = np.asarray(scores), np.asarray(losses)
    i, j = np.triu_indices(len(x), 1)
    dx = np.sign(x[i] - x[j])
    dy = np.sign(y[j] - y[i])
    den = math.sqrt(float(np.count_nonzero(dx) * np.count_nonzero(dy)))
    return float(np.sum(dx * dy) / den) if den else None


def rank_interval(score, pool):
    above = sum(x > score for x in pool)
    equal = sum(x == score for x in pool)
    return [1 + above, 1 + above + equal]


def service_loss(outcome, unit):
    if not numeric(unit) or unit <= 0:
        raise ValueError("Positive diagnostic unit required")
    kind = outcome["kind"]
    if kind in {"MODEL_OUTPUT_MISSING", "SELECTED_REFERENCE_UNAVAILABLE"}:
        return None
    if kind == "SELECTED_FEASIBLE":
        gap = outcome["gap_to_best_in_set_s"]
        if not numeric(gap) or gap < 0:
            raise ValueError("Invalid reference gap")
        return min(1.0, gap / unit)
    if kind in {
        "SELECTED_INFEASIBLE",
        "SELECTED_UNRESOLVED",
        "MISSED_OPPORTUNITY",
        "CORRECT_ABSTENTION",
        "ABSTENTION_UNRESOLVED",
    }:
        return 1.0
    raise ValueError("Unknown outcome")


def real_members(data):
    return [
        m
        for m, r in data["summary"]["members"].items()
        if r["eligible"] and r["kind"] == "RECONSTRUCTED"
    ]


def score_maps(data):
    return {
        leg: {
            m: 1 / (1 + row[field])
            for m, row in data["components"].items()
            if row["eligible"] and numeric(row[field])
        }
        for leg, field in (("A", "E"), ("R", "E_important"))
    }


def condition_inside(qid):
    match = re.fullmatch(r"[DV]-T(-?[0-9.]+)-S([0-9.]+)", qid)
    if not match:
        return None
    temp, soc = map(float, match.groups())
    return 5 <= temp <= 34 and 0.12 <= soc <= 0.48


def reference_family_state(counts):
    if counts.get("REFERENCE_UNAVAILABLE", 0):
        return "REFERENCE_UNAVAILABLE"
    if counts.get("FEASIBLE", 0):
        return "HAS_CERTIFIED_FEASIBLE"
    if counts.get("UNRESOLVED", 0):
        return "UNRESOLVED_NO_CERTIFIED_FEASIBLE"
    if counts.get("INFEASIBLE", 0):
        return "SETTLED_NONE_FEASIBLE"
    return "NO_REFERENCE_EVIDENCE"


def measure_panel(data, unit):
    real = real_members(data)
    all_members = [
        m for m, row in data["summary"]["members"].items() if row["eligible"]
    ]
    questions = [
        q for q, row in data["references"].items() if row["split"] == "verification"
    ]
    kinds = {
        m: Counter(data["decisions"][m][q]["outcome"]["kind"] for q in questions)
        for m in all_members
    }
    losses = {}
    for m in all_members:
        values = [
            service_loss(data["decisions"][m][q]["outcome"], unit) for q in questions
        ]
        losses[m] = (
            sum(values) / len(values)
            if values and all(numeric(x) for x in values)
            else None
        )
    maps = score_maps(data)
    out = {
        "normalization_s": unit,
        "real_members": len(real),
        "eligible_members_including_controls_attacks": len(all_members),
        "verification_questions": len(questions),
        "reference_family_states": dict(
            Counter(
                reference_family_state(data["references"][q]["status_counts"])
                for q in questions
            )
        ),
        "rules": {},
    }
    for leg, mapping in maps.items():
        pool = [m for m in real if numeric(losses[m]) and m in mapping]
        attacks = {}
        for m in all_members:
            if m in real or m not in mapping:
                continue
            inv = (
                [u for u in pool if mapping[u] <= mapping[m] and losses[u] < losses[m]]
                if numeric(losses[m])
                else []
            )
            attacks[m] = {
                "score": mapping[m],
                "rank_vs_real_plus_this_control": rank_interval(
                    mapping[m], [mapping[u] for u in pool]
                ),
                "service_loss": losses[m],
                "outcomes": dict(kinds[m]),
                "value_inversions": len(inv),
                "max_loss_gap": max((losses[m] - losses[u] for u in inv), default=0),
                "E": data["components"][m]["E"],
                "E_important": data["components"][m]["E_important"],
            }
        historical = [
            m
            for m in real
            if numeric(data["summary"]["members"][m]["loss_verification"])
        ]
        out["rules"][leg] = {
            "real_measurable": len(pool),
            "tau_full_verified_service": tau(
                [mapping[m] for m in pool], [losses[m] for m in pool]
            ),
            "tau_historical_loss_available_members": tau(
                [mapping[m] for m in historical],
                [
                    data["summary"]["members"][m]["loss_verification"]
                    for m in historical
                ],
            ),
            "historical_loss_members": len(historical),
            "controls_and_attacks": attacks,
        }
    # Public conditions only: not a reconstruction of the scoring-set ENV gate.
    outside = [q for q in questions if condition_inside(q) is False]
    out["decision_conditions_outside_ENV_temperature_SOC"] = {
        "questions": len(outside),
        "unsafe_picks_all_eligible": sum(
            data["decisions"][m][q]["outcome"]["kind"] == "SELECTED_INFEASIBLE"
            for m in all_members
            for q in outside
        ),
        "unsafe_picks_all_verification": sum(
            kinds[m]["SELECTED_INFEASIBLE"] for m in all_members
        ),
        "unknown_condition_ids": sum(condition_inside(q) is None for q in questions),
        "basis": "Public question-name condition convention and b1.ENVELOPE; excludes c1/c2; not an ENV verdict",
    }
    out["fixed_decision_scalar_error_intervention"] = []
    for retained in (0.0, 0.5, 1.0):
        gains = [
            1 / (1 + data["components"][m]["E"] * retained) - maps["A"][m] for m in real
        ]
        out["fixed_decision_scalar_error_intervention"].append(
            {
                "retained_E": retained,
                "A_gain_min_median_max": [
                    min(gains),
                    float(np.median(gains)),
                    max(gains),
                ],
                "A_gain_count": sum(g > 0 for g in gains),
                "service_loss_delta": 0,
                "basis": "ASSUMPTION aggregate E intervention with decisions frozen; not an achievable easy-region transform or trained attack",
            }
        )
    # Clone public rows; neither original predictions nor decisions change.
    clone_member = "control-boundary_optimist"
    out["clone_pool_sensitivity"] = []
    for copies in (0, 10, 100):
        for leg, mapping in maps.items():
            pool = [m for m in real if numeric(losses[m])]
            original = pool + [clone_member]
            expanded = original + [clone_member] * copies
            out["clone_pool_sensitivity"].append(
                {
                    "additional_identical_rows": copies,
                    "rule": leg,
                    "tau_rows": tau(
                        [mapping[m] for m in expanded], [losses[m] for m in expanded]
                    ),
                    "tau_de_cloned_public_member_rows": tau(
                        [mapping[m] for m in original], [losses[m] for m in original]
                    ),
                    "individual_score_change": 0,
                    "original_member_value_change": 0,
                    "grouping_basis": "Original public member labels; only added toy clones removed. Exact artifact uniqueness/equivalence of original members is UNMEASURED.",
                    "basis": "ASSUMPTION row-cloning stress, not an observed Sybil/copying attack",
                }
            )
    return out


def geometric(legs, weights):
    if any(legs.get(k) is None for k, w in weights.items() if w > 0):
        return None
    if any(legs[k] <= 0 for k, w in weights.items() if w > 0):
        return 0.0
    return math.exp(sum(w * math.log(legs[k]) for k, w in weights.items() if w > 0))


def expanded_registry(registry):
    out = []
    known = {}
    for entry in registry["candidates"]:
        if entry.get("kind") == "gate_sweep":
            for cutoff in entry["grid"]:
                row = {
                    "id": f"{entry['id']}@{cutoff:g}",
                    "weights": known[entry["base"]]["weights"],
                    "gate": {
                        "measure": entry["measure"],
                        "cutoff": cutoff,
                        "comparison": entry.get("comparison", "at_or_above"),
                    },
                }
                out.append(row)
        else:
            known[entry["id"]] = entry
            out.append(entry)
    return out


def synthetic_scores(registry, legs, gates):
    out = {}
    for row in expanded_registry(registry):
        gate = row.get("gate")
        measured = gates.get(gate["measure"]) if gate else 0
        fail = gate and (
            measured is None
            or (
                measured > gate["cutoff"]
                if gate.get("comparison") == "exceeds"
                else measured >= gate["cutoff"]
            )
        )
        out[row["id"]] = {
            "raw_score": geometric(legs, row["weights"]),
            "admissible": not bool(fail),
        }
    return out


def verify_list(order, bank, k, unit):
    """PUBLIC TOY checker: fixed complete-attempt budget, no actual references."""
    if type(k) is not int or k <= 0 or not numeric(unit) or unit <= 0:
        raise ValueError("Positive toy budget and unit required")
    allowed = {"FEASIBLE", "INFEASIBLE", "UNRESOLVED", "REFERENCE_UNAVAILABLE"}
    if any(row.get("status") not in allowed for row in bank.values()):
        raise ValueError("Unknown toy reference state")
    if any(
        row["status"] == "FEASIBLE" and not numeric(row.get("value"))
        for row in bank.values()
    ):
        raise ValueError("Finite toy feasible value required")
    if (
        len(order) != len(set(order))
        or len(order) > k
        or any(x not in bank for x in order)
    ):
        return {"status": "REFUSED_COMMITMENT", "loss": None, "attempts": 0}
    values = [bank[x]["value"] for x in order if bank[x]["status"] == "FEASIBLE"]
    if any(row["status"] == "REFERENCE_UNAVAILABLE" for row in bank.values()):
        return {"status": "REFERENCE_UNAVAILABLE", "loss": None, "attempts": len(order)}
    oracle = [v["value"] for v in bank.values() if v["status"] == "FEASIBLE"]
    if not values:
        return {"status": "NONE_VERIFIED", "loss": 1.0, "attempts": len(order)}
    return {
        "status": "VERIFIED_FEASIBLE",
        "loss": min(1.0, (min(values) - min(oracle)) / unit),
        "attempts": len(order),
    }


def structural_attacks(registry):
    out = {
        "basis": "SYNTHETIC_ASSUMPTION_NON_PRODUCTION; arithmetic examples, no battery trajectory, solver or trained attack",
        "one_sided_pessimism": [],
        "boundary_gate": [],
        "fixed_list_blend": [],
        "list_padding": {},
    }
    for bias in (2, 4, 8):
        truth = np.array([1.0, 0.5, -0.5])
        predicted = truth - bias
        optimism = np.maximum(predicted - truth, 0)
        out["one_sided_pessimism"].append(
            {
                "bias_in_toy_bands": bias,
                "p": 1 / (1 + float(np.mean(optimism))),
                "envelope_optimism": float(np.mean(optimism)),
                "predicted_feasible_actions": int(np.sum(predicted >= 0)),
                "verified_service_loss": 1,
                "truthful_service_loss": 0,
            }
        )
    # 100 failed scoring cases + one safe fallback; 5 flip sign at the
    # strict 5% allowance. All inside the toy ENV, so its mean is measured.
    for eps in (0.01, 0.05, 0.1):
        truth = np.r_[np.full(100, -eps), eps]
        attacked = truth.copy()
        attacked[:5] = eps
        optimism = np.maximum(attacked - truth, 0)
        error = float(np.mean(np.abs(attacked - truth)))
        p = 1 / (1 + float(np.mean(optimism)))
        base = {"a": 1 / 1.1, "r": 1 / 1.1, "p": 1, "v3": 1, "q": 1}
        changed = {
            "a": 1 / (1 + error),
            "r": 1 / (1 + error),
            "p": p,
            "v3": 0.5,
            "q": 1 / 11,
        }
        gates = {"envelope": float(np.mean(optimism)), "feasibility": 0.05}
        b, a = synthetic_scores(
            registry, base, {"envelope": 0, "feasibility": 0}
        ), synthetic_scores(registry, changed, gates)
        out["boundary_gate"].append(
            {
                "epsilon_in_toy_bands": eps,
                "reference_failed_cases": 100,
                "flipped_failed_cases": 5,
                "total_cases": 101,
                "false_feasible_rate": 0.05,
                "envelope_mean": gates["envelope"],
                "base_service_loss": 0,
                "attack_service_loss": 1,
                "mechanism": "Remove harmless extra-field error (0.1) while flipping five close failed actions ahead of the safe fallback; three first actions all fail",
                "rules": {
                    k: {
                        "base": b[k],
                        "attack": a[k],
                        "score_delta": a[k]["raw_score"] - b[k]["raw_score"],
                    }
                    for k in b
                },
            }
        )
    # Improvement of an irrelevant output component with the exact ordered
    # actions and all verifier outcomes fixed. Component values are toys.
    for retained in (0, 0.5, 1):
        base = {"a": 1 / 1.4, "r": 0.8, "p": 0.8, "v3": 0.6, "q": 0.6}
        changed = {**base, "a": 1 / (1 + 0.4 * retained)}
        gates = {"envelope": 0.0, "feasibility": 0.0}
        b, a = synthetic_scores(registry, base, gates), synthetic_scores(
            registry, changed, gates
        )
        out["fixed_list_blend"].append(
            {
                "retained_toy_E": retained,
                "verified_value_delta": 0,
                "rules": {k: a[k]["raw_score"] - b[k]["raw_score"] for k in b},
            }
        )
    bank = {f"bad{i}": {"status": "INFEASIBLE", "value": None} for i in range(1, 4)}
    bank["safe"] = {"status": "FEASIBLE", "value": 100}
    out["list_padding"] = {
        "k": 3,
        "fixed_first_three": verify_list(["bad1", "bad2", "bad3"], bank, 3, 1200),
        "overlength_padding_refused": verify_list(
            ["bad1", "bad2", "bad3", "safe"], bank, 3, 1200
        ),
        "duplicates_refused": verify_list(["bad1", "bad1", "safe"], bank, 3, 1200),
        "naive_failure_skip_counterfactual": {
            "attempts": 4,
            "loss": 0,
            "violates_fixed_attempt_budget": True,
        },
        "valid_safe_first": verify_list(["safe", "bad1", "bad2"], bank, 3, 1200),
    }
    return out


def allowance(n, cutoff, strict=True):
    if n < 1 or not 0 <= cutoff <= 1:
        raise ValueError("Invalid count/cutoff")
    return max(
        (j for j in range(n + 1) if (j / n <= cutoff if strict else j / n < cutoff)),
        default=-1,
    )


def audit(directory):
    data, sources = load_public(directory)
    registry = data["registry-v9.json"]
    near = data["analysis.json"]["value"]["H3"]["report"]["members"]
    return {
        "schema": "carbon.research.score-attacks-v9.v1",
        "ticket": "RES-02 / SCORE-CANDIDATE-ATTACKS-01",
        "maturity": "DEVELOPMENT_PUBLIC_DESCRIPTIVE_NOT_QUALIFIED",
        "sources": sources,
        "registry_candidates": [r["id"] for r in registry["candidates"]],
        "panels": {
            p: {str(u): measure_panel(data[p + ".json"], u) for u in UNITS}
            for p in ("ev4", "ev5")
        },
        "near_constraint_counts": {
            m: r["measurement"]["constraints"] for m, r in near.items()
        },
        "finite_gate_allowance": [
            {
                "denominator": n,
                "cutoff": c,
                "fail_comparison": ">" if strict else ">=",
                "max_FA_passing": allowance(n, c, strict),
            }
            for n in (67, 74, 100)
            for c in (0.005, 0.01, 0.02, 0.05)
            for strict in (True, False)
        ],
        "synthetic_structural_attacks": structural_attacks(registry),
        "identifiability": {
            "A": "MEASURED_PUBLIC_COMPONENT",
            "R": "MEASURED_PUBLIC_COMPONENT",
            "P": "GAP_NO_PUBLIC_PER_CASE_OPTIMISM_OR_P_LEG_FOR_THESE_ARTIFACTS",
            "ARP": "GAP_P",
            "V3": "GAP_REAL_TOP3_Q3_ORDERS_AND_LEG_SPLIT",
            "ARP-V3": "GAP_P_AND_V3",
            "ENV/ARP": "GAP_P_AND_ENV_SCORING_MEASURE",
            "ENV/ARP-V3": "GAP_P_V3_ENV",
            "A-Q": "GAP_Q3_REGRET",
            "G-FEAS/A-Q>@0.05": "GAP_Q3_AND_JOINT_SCORING_FEASIBILITY",
        },
        "public_split": {
            "source": data["public-dev-split-v1.json"]["rule"],
            "applied_to_historical_EV_questions": False,
            "reason": "Existing EV D/V families and prior data reuse are not new D-0000 PUBLIC-DEV questions or untouched confirmation; no V3 proxy substituted",
        },
        "thresholds": "HUMAN_INPUT: detector tolerances, equivalence region, multiplicity/alpha, adoption; existing registered settings are source points only",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("results.json")
    )
    args = parser.parse_args()
    if args.output.resolve().parent != Path(__file__).resolve().parent:
        raise ValueError("Output must stay in the research directory")
    result = audit(args.inputs)
    args.output.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "written": str(args.output),
                "candidates": len(result["registry_candidates"]),
                "public_sources": len(result["sources"]),
                "qualified": False,
            }
        )
    )


if __name__ == "__main__":
    main()
