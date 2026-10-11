"""Offline public outcome analysis; no Carbon, solver, training or network imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

BASE = "7b8e89c34ca78711883b7157a3cd8225c618aa29"
INPUTS = {
    "ev4.json": (
        "docs/development/evidence/ev4-2026-10-01/results.json",
        "67ca13b966a2f6fb4b2e68b084e2909657e7ba7f",
    ),
    "ev5.json": (
        "docs/development/evidence/ev5-2026-10-03/results.json",
        "7d6ccf75a47c2df56c66d0b223300e5fd9398512",
    ),
    "ev4-contract.json": (
        "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json",
        "3961b89a98c8877190bc010579852497057d3518",
    ),
    "ev5-contract.json": (
        "carbon/battery/value/contracts/ev5-charge-protocol-selection.v1.json",
        "7cb89a3787a172427ae7024922a6e1641172eb91",
    ),
    "analysis.json": (
        "docs/development/evidence/ev5-2026-10-03/analysis.json",
        "c2131424a3d979b71b2881a114507c2b9dcd9bf6",
    ),
    "gate.json": (
        "docs/development/evidence/ev5-2026-10-03/gate.json",
        "df128cb7c30bfa679d85f537cfe3651fc9873463",
    ),
}
UNITS = (60.0, 120.0, 240.0)  # ASSUMPTION sensitivity; historical unit is 120 s.


def read_inputs(directory):
    data, sources = {}, {}
    for name, (path, expected) in INPUTS.items():
        raw = (directory / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != expected:
            raise ValueError(f"Public input digest mismatch: {name}")
        data[name] = json.loads(raw)
        sources[name] = {
            "path": path,
            "source_commit": BASE,
            "git_blob": blob,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    return data, sources


def recipe(member):
    return re.sub(r"-s[0-9]+$", "", member)


def numeric(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def return_loss(outcome, unit):
    """PROPOSED one-verification bounded service loss, not historical decision_loss.

    Already unresolved physical labels mean no VERIFIED return, hence full service
    loss. Reference unavailability means unmeasurable, never candidate failure.
    Settled NONE_FEASIBLE also has full service loss per the owner's requested
    convention; report that structural difficulty separately.
    """
    if not numeric(unit) or unit <= 0:
        raise ValueError("Positive research normalisation required")
    kind = outcome["kind"]
    if kind in {"SELECTED_REFERENCE_UNAVAILABLE", "MODEL_OUTPUT_MISSING"}:
        return None
    if kind == "SELECTED_FEASIBLE":
        gap = outcome["gap_to_best_in_set_s"]
        if not numeric(gap) or gap < -1e-8:
            raise ValueError("Invalid verified reference gap")
        return min(1.0, max(0.0, gap / unit))
    if kind in {
        "SELECTED_INFEASIBLE",
        "SELECTED_UNRESOLVED",
        "MISSED_OPPORTUNITY",
        "CORRECT_ABSTENTION",
        "ABSTENTION_UNRESOLVED",
    }:
        return 1.0
    raise ValueError(f"Unknown public outcome kind: {kind}")


def verify_list(order, references, k, budget, unit=120.0):
    """Synthetic contract checks ONLY. Budget is a complete-panel attempt cap.

    No real member orders are fabricated. Unknown reference availability withholds
    score. Band UNRESOLVED consumes a slot and cannot be returned.
    """
    if type(k) is not int or type(budget) is not int or min(k, budget) <= 0:
        raise ValueError("Positive integer k and budget required")
    if not numeric(unit) or unit <= 0:
        raise ValueError("Positive research normalisation required")
    for row in references.values():
        if row.get("status") not in {
            "FEASIBLE",
            "INFEASIBLE",
            "UNRESOLVED",
            "REFERENCE_UNAVAILABLE",
        }:
            raise ValueError("Unregistered reference status")
        if row["status"] == "FEASIBLE" and not numeric(row.get("value")):
            raise ValueError("Finite verified value required")
    if len(order) != len(set(order)) or any(x not in references for x in order):
        raise ValueError("Duplicate or out-of-family action")
    attempted = order[: min(k, budget)]
    rows = [references[x] for x in attempted]
    if any(r["status"] == "REFERENCE_UNAVAILABLE" for r in rows):
        return {"status": "INSUFFICIENT_REFERENCE", "loss": None, "attempts": len(rows)}
    feasible = [r["value"] for r in rows if r["status"] == "FEASIBLE"]
    oracle = [r["value"] for r in references.values() if r["status"] == "FEASIBLE"]
    if not feasible:
        return {"status": "NONE_VERIFIED", "loss": 1.0, "attempts": len(rows)}
    gap = min(feasible) - min(oracle)
    return {
        "status": "VERIFIED_RETURN",
        "loss": min(1.0, max(0.0, gap / unit)),
        "value": min(feasible),
        "attempts": len(rows),
    }


def tau(scores, losses):
    x, y = np.asarray(scores), np.asarray(losses)
    i, j = np.triu_indices(len(x), 1)
    dx = np.sign(x[i] - x[j])
    dy = np.sign(y[j] - y[i])
    den = math.sqrt(float(np.count_nonzero(dx) * np.count_nonzero(dy)))
    return None if not den else float((dx * dy).sum() / den)


def questions(results, members, split, leg):
    return sorted(
        q
        for q, r in results["references"].items()
        if r["split"] == split
        and all(numeric(leg(results["decisions"][m][q]["outcome"])) for m in members)
    )


def arrays(results, members, qs, leg):
    return np.array(
        [[leg(results["decisions"][m][q]["outcome"]) for q in qs] for m in members],
        dtype=float,
    )


def d_grid_rate(results, member):
    """Disjoint development decision-grid proxy, NOT registered scoring-set G-FEAS."""
    fail_count = accepted = 0
    for q, r in results["references"].items():
        if r["split"] != "development":
            continue
        a = results["decisions"][member][q]["agreement"]
        if a is None or a.get("false_acceptances") is None:
            return None
        fail_count += r["status_counts"]["INFEASIBLE"]
        accepted += a["false_acceptances"]
    return None if not fail_count else accepted / fail_count


def passing(values, cutoff, comparison):
    return np.array(
        [
            numeric(v) and (v <= cutoff if comparison == "exceeds" else v < cutoff)
            for v in values
        ]
    )


def summarize_rule(scores, losses, members, pass_mask, all_scores):
    effective = np.where(pass_mask, scores, -np.inf)
    # Sign comparisons avoid -inf - -inf warnings in tau.
    finite_effective = np.where(pass_mask, scores, -1.0)
    ordered = sorted(
        (i for i in range(len(members)) if pass_mask[i]),
        key=lambda i: (-scores[i], members[i]),
    )
    controls = {}
    for m, s in all_scores.items():
        if m in members:
            continue
        controls[m] = {
            "score": s,
            "rank_against_real": None if s is None else 1 + int(np.sum(effective > s)),
            "real_strictly_above": None if s is None else int(np.sum(effective > s)),
            "real_tied": None if s is None else int(np.sum(effective == s)),
        }
    return {
        "tau_b": tau(finite_effective, losses),
        "passing_real_members": int(pass_mask.sum()),
        "passing_recipes_any_seed": len({recipe(members[i]) for i in ordered}),
        "all_seed_passing_recipes": sum(
            all(pass_mask[i] for i, m in enumerate(members) if recipe(m) == r)
            for r in {recipe(m) for m in members}
        ),
        "top_member": members[ordered[0]] if ordered else None,
        "top_verification_mean_loss": float(losses[ordered[0]]) if ordered else None,
        "controls_and_attacks": controls,
    }


def bootstrap(members, scores, losses_by_q, qs, passes, replicates, seed):
    """Paired recipe bootstrap and crossed V-temperature-block sensitivity.

    Development scores/gates stay frozen. Seeds within a recipe move together.
    Physical D/V generation is not an iid future buyer sample; intervals are
    descriptive sensitivity conditional on this public panel, not power guarantees.
    """
    rng = np.random.default_rng(seed)
    groups = [
        np.array([i for i, m in enumerate(members) if recipe(m) == r])
        for r in sorted({recipe(m) for m in members})
    ]
    blocks = [
        np.array([j for j, q in enumerate(qs) if q.split("-S")[0] == t])
        for t in sorted({q.split("-S")[0] for q in qs})
    ]
    names = list(scores)
    draws = {
        mode: {name: [] for name in names}
        for mode in ("recipe_only", "recipe_x_V_temperature")
    }
    for _ in range(replicates):
        idx = np.concatenate(
            [groups[g] for g in rng.integers(len(groups), size=len(groups))]
        )
        qidx = np.concatenate(
            [blocks[b] for b in rng.integers(len(blocks), size=len(blocks))]
        )
        for mode, v in [
            ("recipe_only", losses_by_q.mean(axis=1)),
            ("recipe_x_V_temperature", losses_by_q[:, qidx].mean(axis=1)),
        ]:
            for name in names:
                value = tau(
                    np.where(passes[name][idx], scores[name][idx], -1.0), v[idx]
                )
                draws[mode][name].append(value)
    output = {}
    for mode, rules in draws.items():
        output[mode] = {}
        base = rules["VERIFY-R"]
        for name, values in rules.items():
            valid = [x for x in values if x is not None]
            paired = [
                x - y for x, y in zip(values, base) if x is not None and y is not None
            ]
            output[mode][name] = {
                "ci95_percentile": (
                    np.quantile(valid, [0.025, 0.975]).tolist()
                    if valid
                    else [None, None]
                ),
                "valid": len(valid),
                "undefined": replicates - len(valid),
                "delta_tau_vs_VERIFY_R_ci95": (
                    np.quantile(paired, [0.025, 0.975]).tolist()
                    if paired
                    else [None, None]
                ),
                "paired_valid": len(paired),
            }
    return output


def shortlist_bounds(results, members, split, attempt_cap, unit=120.0):
    """Rigorous but conservative hit bounds from first pick and aggregate counts.

    Applies ONLY to sorted predicted-feasible lists extending the historical first
    pick and constant complete-panel costs. No hidden orders reconstructed.
    """
    low = high = events = known_opportunity = opportunity_low = opportunity_high = 0
    loss_bounds = []
    for m in members:
        for q, r in results["references"].items():
            if r["split"] != split:
                continue
            d = results["decisions"][m][q]
            o, a = d["outcome"], d["agreement"]
            f = r["status_counts"]["FEASIBLE"]
            unknown = r["status_counts"].get("UNRESOLVED", 0) + r["status_counts"].get(
                "REFERENCE_UNAVAILABLE", 0
            )
            true_admitted = f - a["false_rejections"]
            nonfeasible_upper = a["false_acceptances"] + unknown
            first_hit = o["kind"] == "SELECTED_FEASIBLE"
            lo = int(
                first_hit
                or (
                    o["selected"] is not None
                    and true_admitted > 0
                    and attempt_cap > nonfeasible_upper
                )
            )
            hi = int(
                first_hit
                or (attempt_cap > 1 and o["selected"] is not None and true_admitted > 0)
            )
            if attempt_cap == 1:
                lo = hi = int(first_hit)
            first_loss = return_loss(o, unit)
            if numeric(first_loss):
                if attempt_cap == 1 or o["selected"] is None or true_admitted == 0:
                    loss_bounds.append([first_loss, first_loss])
                elif (
                    a["false_rejections"] == 0
                    and attempt_cap >= nonfeasible_upper + true_admitted
                ):
                    # Every reference-feasible action is admitted and must be
                    # verified, so the best known feasible design is returned.
                    loss_bounds.append([0.0, 0.0])
                else:
                    loss_bounds.append([0.0, first_loss])
            assert lo <= hi
            low += lo
            high += hi
            events += 1
            if f:
                known_opportunity += 1
                opportunity_low += lo
                opportunity_high += hi
    return {
        "attempt_cap": attempt_cap,
        "basis": "PARTIAL_IDENTIFICATION_BOUNDS_CONSTANT_COST_NOT_REAL_TOP_K_MEASUREMENT",
        "events": events,
        "feasible_return_fraction_bounds": [low / events, high / events],
        "known_opportunity_events": known_opportunity,
        "known_opportunity_return_fraction_bounds": (
            [opportunity_low / known_opportunity, opportunity_high / known_opportunity]
            if known_opportunity
            else [None, None]
        ),
        "mean_service_loss_bounds": (
            np.mean(loss_bounds, axis=0).tolist() if loss_bounds else [None, None]
        ),
        "loss_events_with_reference_available": len(loss_bounds),
    }


def analyze_panel(results, members, unit, plate=None, replicates=2000, seed=20261011):
    verify = lambda o: return_loss(o, unit)
    historical = lambda o: o.get("decision_loss")
    output = {
        "normalisation_s": unit,
        "real_members": len(members),
        "recipes": len({recipe(m) for m in members}),
        "splits": {},
    }
    for split in ("development", "verification"):
        qs = [q for q, r in results["references"].items() if r["split"] == split]
        counts = Counter(
            results["decisions"][m][q]["outcome"]["kind"] for m in members for q in qs
        )
        opportunity = [
            q for q in qs if results["references"][q]["status_counts"]["FEASIBLE"] > 0
        ]
        opportunity_hits = sum(
            results["decisions"][m][q]["outcome"]["kind"] == "SELECTED_FEASIBLE"
            for m in members
            for q in opportunity
        )
        output["splits"][split] = {
            "questions_offered": len(qs),
            "questions_with_known_feasible_action": len(opportunity),
            "questions_settled_NONE_FEASIBLE": sum(
                r["status_counts"]["INFEASIBLE"] == sum(r["status_counts"].values())
                for r in results["references"].values()
                if r["split"] == split
            ),
            "k1_outcome_events": dict(sorted(counts.items())),
            "known_opportunity_hits": opportunity_hits,
            "known_opportunity_events": len(members) * len(opportunity),
            "known_opportunity_hit_fraction": (
                opportunity_hits / (len(members) * len(opportunity))
                if opportunity
                else None
            ),
            "shortlist_hit_bounds": [
                shortlist_bounds(results, members, split, c, unit)
                for c in (1, 2, 3, 5, 10, 35)
            ],
        }
    all_members = [
        m for m, row in results["summary"]["members"].items() if row["eligible"]
    ]
    for cohort, leg in [
        ("all_available_verification_service", verify),
        ("matched_historical_numeric", historical),
    ]:
        dq = questions(results, members, "development", leg)
        vq = questions(results, members, "verification", leg)
        dnew = arrays(results, members, dq, verify).mean(axis=1)
        vnew = arrays(results, members, vq, verify)
        accuracy = np.array([1 / (1 + results["components"][m]["E"]) for m in members])
        scores = {
            "VERIFY-R": 1 / (1 + dnew),
            "A-VERIFY-R": np.sqrt(accuracy / (1 + dnew)),
            "CE": accuracy,
        }
        passes = {n: np.ones(len(members), dtype=bool) for n in scores}
        all_scores = {n: {} for n in scores}
        for m in all_members:
            if m in members:
                continue
            vals = [verify(results["decisions"][m][q]["outcome"]) for q in dq]
            if all(numeric(x) for x in vals):
                qleg = 1 / (1 + float(np.mean(vals)))
                aleg = 1 / (1 + results["components"][m]["E"])
                all_scores["VERIFY-R"][m] = qleg
                all_scores["A-VERIFY-R"][m] = math.sqrt(aleg * qleg)
                all_scores["CE"][m] = aleg
            else:
                for member_scores in all_scores.values():
                    member_scores[m] = None
        if cohort == "matched_historical_numeric":
            dold = arrays(results, members, dq, historical).mean(axis=1)
            scores["D_PROXY_A-Q_NOT_Q3"] = np.sqrt(accuracy / (1 + dold))
            passes["D_PROXY_A-Q_NOT_Q3"] = np.ones(len(members), dtype=bool)
            all_scores["D_PROXY_A-Q_NOT_Q3"] = {}
            for m in all_members:
                if m in members:
                    continue
                vals = [historical(results["decisions"][m][q]["outcome"]) for q in dq]
                all_scores["D_PROXY_A-Q_NOT_Q3"][m] = (
                    math.sqrt(
                        (1 / (1 + results["components"][m]["E"]))
                        / (1 + float(np.mean(vals)))
                    )
                    if all(numeric(x) for x in vals)
                    else None
                )
            gate_types = [
                (
                    "D_GRID_FEAS_PROXY",
                    [d_grid_rate(results, m) for m in members],
                    {m: d_grid_rate(results, m) for m in all_members},
                )
            ]
            if plate is not None:
                gate_types.append(
                    ("G_PLATE_MEASURE", [plate.get(m) for m in members], plate)
                )
            for gate, values, all_values in gate_types:
                for cutoff in (0.005, 0.01, 0.02, 0.05):
                    for comparison in ("at_least", "exceeds"):
                        name = f"{gate}@{cutoff}:{comparison}/D_PROXY_A-Q_NOT_Q3"
                        scores[name] = scores["D_PROXY_A-Q_NOT_Q3"]
                        passes[name] = passing(values, cutoff, comparison)
                        all_scores[name] = {
                            m: (
                                s
                                if passing([all_values.get(m)], cutoff, comparison)[0]
                                else None
                            )
                            for m, s in all_scores["D_PROXY_A-Q_NOT_Q3"].items()
                        }
        rules = {
            n: summarize_rule(
                scores[n], vnew.mean(axis=1), members, passes[n], all_scores[n]
            )
            for n in scores
        }
        for n, row in rules.items():
            oldvq = questions(results, members, "verification", historical)
            historical_v = arrays(results, members, oldvq, historical).mean(axis=1)
            row["tau_with_historical_decision_value_on_its_numeric_V_mask"] = tau(
                np.where(passes[n], scores[n], -1.0), historical_v
            )
            for m, control in row["controls_and_attacks"].items():
                vals = [verify(results["decisions"][m][q]["outcome"]) for q in vq]
                control["verification_mean_service_loss"] = (
                    float(np.mean(vals)) if all(numeric(x) for x in vals) else None
                )
                s, loss = control["score"], control["verification_mean_service_loss"]
                if s is not None and loss is not None:
                    better = passes[n] & (scores[n] <= s) & (vnew.mean(axis=1) < loss)
                    control[
                        "real_members_with_better_V_value_and_no_higher_D_score"
                    ] = int(np.sum(better))
                    control["max_V_loss_gap_in_inversions"] = (
                        float(np.max(loss - vnew.mean(axis=1)[better]))
                        if np.any(better)
                        else 0.0
                    )
                else:
                    control[
                        "real_members_with_better_V_value_and_no_higher_D_score"
                    ] = None
                    control["max_V_loss_gap_in_inversions"] = None
                control["inversion_basis"] = (
                    "RAW_POINT_DIAGNOSTIC_NO_ADOPTED_VALUE_NOISE_THRESHOLD"
                )
        eligible_by_member = {
            m: {
                "score": float(scores["VERIFY-R"][i]),
                "verification_mean_service_loss": float(vnew[i].mean()),
                "verified_return_questions": sum(
                    results["decisions"][m][q]["outcome"]["kind"] == "SELECTED_FEASIBLE"
                    for q in vq
                ),
            }
            for i, m in enumerate(members)
        }
        output[cohort] = {
            "development_questions": dq,
            "verification_questions": vq,
            "rules": rules,
            "real_member_values": eligible_by_member,
        }
        if unit == 120:
            output[cohort]["bootstrap"] = {
                "replicates": replicates,
                "seed": seed,
                "basis": "DESCRIPTIVE_CI_CONDITIONAL_PUBLIC_PANEL_FROZEN_D_SCORES",
                "intervals": bootstrap(
                    members, scores, vnew, vq, passes, replicates, seed
                ),
            }
        output[cohort]["score_only_accuracy_perturbation"] = {
            "basis": "SYNTHETIC_COUNTERFACTUAL_FIXED_PUBLIC_LISTS_NOT_MEASURED_NEW_MODEL",
            "error_retained_fraction_low_base_high": [0.0, 0.5, 1.0],
            "VERIFY_R_increases": 0,
            "A_VERIFY_R_increases_at_half_error": int(np.sum(accuracy < 1)),
            "max_A_VERIFY_R_gain_at_half_error": float(
                np.max(
                    np.sqrt(
                        (
                            1
                            / (
                                1
                                + np.array(
                                    [results["components"][m]["E"] for m in members]
                                )
                                * 0.5
                            )
                        )
                        / (1 + dnew)
                    )
                    - scores["A-VERIFY-R"]
                )
            ),
        }
    return output


def run(data, sources, replicates):
    output = {
        "schema": "carbon.research.verify-aware-score.v1",
        "scope": "PUBLIC_DEVELOPMENT_RESEARCH_ONLY",
        "source_commit": BASE,
        "sources": sources,
        "production_inputs": {
            "k": "HUMAN_INPUT",
            "attempt_cap": "HUMAN_INPUT",
            "wall_s": "HUMAN_INPUT",
            "core_s": "HUMAN_INPUT",
            "normalisation": "HUMAN_INPUT",
            "adoption": "HUMAN_INPUT",
        },
        "identifiability": {
            "real_top_k_order_k_gt_1": "NOT_IDENTIFIABLE",
            "actual_registry_Q3": "NOT_IDENTIFIABLE",
            "registered_scoring_set_G_FEAS": "NOT_IDENTIFIABLE",
            "equal_budget_measured_cost": "NOT_IDENTIFIABLE",
            "full_battery_v3_five_band_value": "NOT_IDENTIFIABLE",
        },
        "panels": {},
    }
    plate = {
        m: row["measurement"]["constraints"]["no_plating_onset"][
            "false_acceptance_rate"
        ]
        for m, row in data["analysis.json"]["value"]["H3"]["report"]["members"].items()
    }
    for panel in ("ev4", "ev5"):
        results = data[panel + ".json"]
        members = sorted(
            m
            for m, row in results["summary"]["members"].items()
            if row["kind"] == "RECONSTRUCTED" and row["eligible"]
        )
        output["panels"][panel] = {
            str(u): analyze_panel(
                results, members, u, plate if panel == "ev5" else None, replicates
            )
            for u in UNITS
        }
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=Path(__file__).parent / "inputs")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).parent / "results.json"
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    args = parser.parse_args()
    if args.bootstrap_replicates < 1:
        raise ValueError("Positive replicate count required")
    data, sources = read_inputs(args.inputs)
    result = run(data, sources, args.bootstrap_replicates)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
