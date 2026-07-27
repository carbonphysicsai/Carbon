"""Lean emission scoring for Burgers PoC — Score Pack driven (Scoring.md).

Hard gates → S=0. Soft legs: physics margins 45% / robustness 30% / accuracy 25%.
Vectors (margins, per-category r_c) always returned for Model Cards / Landscape.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from carbon.common.scoring import compute_combined_score, margin_linear_clip
from poc.eval.gates import all_passed
from poc.generators.stress_categories import COVERAGE_THRESHOLD


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_score_pack(path: Path | None = None) -> dict:
    p = path or (_repo_root() / "poc" / "configs" / "scoring_burgers1d.yaml")
    with open(p) as f:
        pack = yaml.safe_load(f)
    if not pack.get("scoring_version"):
        raise ValueError("Score Pack missing scoring_version")
    return pack


def score_pack_hash(pack: dict | None = None, raw: bytes | None = None) -> str:
    if raw is None:
        p = _repo_root() / "poc" / "configs" / "scoring_burgers1d.yaml"
        raw = p.read_bytes()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _physics_score(
    errors: Dict[str, float], pack: dict
) -> Tuple[float, Dict[str, float]]:
    comps = pack.get("physics", {}).get("components", [])
    margins: Dict[str, float] = {}
    total = 0.0
    for c in comps:
        key = c["key"]
        tau = float(c["tau"])
        alpha = float(c["alpha"])
        e = float(errors.get(key, tau))  # missing → zero margin
        m = margin_linear_clip(e, tau)
        margins[key] = m
        total += alpha * m
    return total, margins


def _robustness_score(
    per_category_rel_l2: Dict[str, float],
    pack: dict,
) -> Tuple[float, Dict[str, Any], Optional[str]]:
    rob = pack.get("robustness", {})
    lam = float(rob.get("lambda_mean_tail", 0.5))
    beta = float(rob.get("beta_coverage_min", 0.6))
    tau = float(rob.get("tau_rob", 0.5))
    cat_ids = [c["id"] for c in rob.get("categories", [])]

    by_cat: Dict[str, Any] = {}
    r_list: List[float] = []
    for cid in cat_ids:
        if cid not in per_category_rel_l2:
            continue
        # PoC: one aggregate rel_l2 per category batch → mean == tail
        mean_e = float(per_category_rel_l2[cid])
        tail_e = mean_e
        blended = lam * mean_e + (1.0 - lam) * tail_e
        r_c = margin_linear_clip(blended, tau)
        by_cat[cid] = {"mean": mean_e, "tail": tail_e, "r": r_c}
        r_list.append(r_c)

    if not r_list:
        return 0.0, by_cat, None

    mean_r = sum(r_list) / len(r_list)
    min_r = min(r_list)
    s = beta * mean_r + (1.0 - beta) * min_r
    weakest = min(by_cat.items(), key=lambda kv: kv[1]["r"])[0]
    return s, by_cat, weakest


def score_run(
    eval_metrics: Dict[str, float],
    stress_metrics: Dict[str, float],
    gate_results: List[Dict[str, Any]],
    *,
    stress_coverage: Optional[float] = None,
    coverage_threshold: float = COVERAGE_THRESHOLD,
    pack: dict | None = None,
) -> Dict[str, Any]:
    pack = pack or load_score_pack()
    ok, failures = all_passed(gate_results)

    coverage_fail = False
    min_cov = float(
        pack.get("robustness", {}).get("min_category_coverage", coverage_threshold)
    )
    if stress_coverage is not None and stress_coverage < min_cov:
        coverage_fail = True
        failures = list(failures) + ["stress_coverage"]
        ok = False

    # Error keys aligned with Score Pack
    e_res = float(eval_metrics.get("residual_mean", 10.0))
    e_cons = float(eval_metrics.get("conservation_error", 1.0))
    e_acc = float(eval_metrics.get("rel_l2", 1.0))
    e_roll = float(stress_metrics.get("rel_l2", e_acc))

    physics, physics_margins = _physics_score(
        {"e_res": e_res, "e_cons": e_cons, "e_roll": e_roll}, pack
    )

    per_cat = dict(stress_metrics.get("per_category_rel_l2") or {})
    robustness, rob_by_cat, weakest = _robustness_score(per_cat, pack)

    tau_acc = float(pack.get("accuracy", {}).get("tau_acc", 0.5))
    accuracy = margin_linear_clip(e_acc, tau_acc)

    weights = pack.get("weights", {})
    w_p = float(weights.get("physics", 0.45))
    w_r = float(weights.get("robustness", 0.30))
    w_a = float(weights.get("accuracy", 0.25))

    scored = compute_combined_score(
        physics_fidelity=physics,
        robustness=robustness,
        accuracy=accuracy,
        hard_gate_failures=failures if not ok else [],
        weights=(w_p, w_r, w_a),
    )

    pack_path = _repo_root() / "poc" / "configs" / "scoring_burgers1d.yaml"
    return {
        "physics": scored["physics_fidelity"],
        "robustness": scored["robustness"],
        "accuracy": scored["accuracy"],
        "combined": scored["combined_score"],
        "gate_failed": scored["gate_failed"],
        "hard_gate_failures": scored["hard_gate_failures"],
        "weights": scored["weights"],
        "stress_coverage": stress_coverage,
        "coverage_fail": coverage_fail,
        # Card / Landscape vectors
        "physics_margins": physics_margins,
        "robustness_by_category": rob_by_cat,
        "weakest_category": weakest,
        "accuracy_eval": {"rel_l2_mean": e_acc, "S": accuracy},
        "errors": {"e_res": e_res, "e_cons": e_cons, "e_roll": e_roll, "e_acc": e_acc},
        "scoring_version": pack.get("scoring_version"),
        "scoring_pack_hash": score_pack_hash(raw=pack_path.read_bytes()),
        "challenge_id": pack.get("challenge_id"),
    }
