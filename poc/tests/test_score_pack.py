"""Score Pack + lean scoring unit tests (Launch_Bar / Scoring.md)."""

from __future__ import annotations

from pathlib import Path

from carbon.common.scoring import margin_linear_clip
from poc.eval.score import load_score_pack, score_pack_hash, score_run
from poc.generators.stress_categories import CATEGORIES


def test_score_pack_loads_and_hashes():
    pack = load_score_pack()
    assert pack["challenge_id"] == "burgers1d_v0"
    assert pack["scoring_version"] == "1.0"
    w = pack["weights"]
    assert abs(w["physics"] + w["robustness"] + w["accuracy"] - 1.0) < 1e-9
    h = score_pack_hash()
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_score_pack_categories_align_with_generator():
    pack = load_score_pack()
    pack_ids = {c["id"] for c in pack["robustness"]["categories"]}
    gen_ids = set(CATEGORIES.keys())
    assert pack_ids <= gen_ids, f"pack categories not in generator: {pack_ids - gen_ids}"


def test_margin_linear_clip_monotonic():
    assert margin_linear_clip(0.0, 1.0) == 1.0
    assert margin_linear_clip(1.0, 1.0) == 0.0
    assert margin_linear_clip(2.0, 1.0) == 0.0
    assert margin_linear_clip(0.25, 1.0) == 0.75


def test_hard_gate_zeros_combined():
    pack = load_score_pack()
    eval_m = {
        "rel_l2": 0.05,
        "residual_mean": 0.1,
        "conservation_error": 0.01,
        "finite_ok": 1.0,
    }
    stress_m = {
        "rel_l2": 0.08,
        "per_category_rel_l2": {c: 0.08 for c in CATEGORIES},
    }
    gates = [
        {"id": "finite", "pass": True, "value": 1.0, "tau": 1.0},
        {"id": "conservation", "pass": False, "value": 0.5, "tau": 0.08},
    ]
    out = score_run(eval_m, stress_m, gates, stress_coverage=1.0, pack=pack)
    assert out["gate_failed"] is True
    assert out["combined"] == 0.0
    assert "conservation" in out["hard_gate_failures"]
    # Vectors still present for cards
    assert "e_res" in out["physics_margins"]
    assert out["scoring_pack_hash"].startswith("sha256:")


def test_soft_legs_rank_when_gates_pass():
    pack = load_score_pack()
    good_eval = {
        "rel_l2": 0.05,
        "residual_mean": 0.2,
        "conservation_error": 0.01,
        "finite_ok": 1.0,
    }
    bad_eval = {
        "rel_l2": 0.4,
        "residual_mean": 1.5,
        "conservation_error": 0.06,
        "finite_ok": 1.0,
    }
    stress_good = {
        "rel_l2": 0.1,
        "per_category_rel_l2": {c: 0.1 for c in CATEGORIES},
    }
    stress_bad = {
        "rel_l2": 0.45,
        "per_category_rel_l2": {c: 0.45 for c in CATEGORIES},
    }
    gates_ok = [
        {"id": "finite", "pass": True, "value": 1.0, "tau": 1.0},
        {"id": "conservation", "pass": True, "value": 0.01, "tau": 0.08},
        {"id": "residual_ceiling", "pass": True, "value": 0.2, "tau": 2.0},
        {"id": "accuracy_ceiling", "pass": True, "value": 0.05, "tau": 0.95},
    ]
    g = score_run(good_eval, stress_good, gates_ok, stress_coverage=1.0, pack=pack)
    b = score_run(bad_eval, stress_bad, gates_ok, stress_coverage=1.0, pack=pack)
    assert g["gate_failed"] is False
    assert b["gate_failed"] is False
    assert g["combined"] > b["combined"]
    assert g["physics"] >= b["physics"]
    assert g["robustness"] >= b["robustness"]


def test_weakest_category_pulls_robustness_down():
    pack = load_score_pack()
    eval_m = {
        "rel_l2": 0.05,
        "residual_mean": 0.2,
        "conservation_error": 0.01,
        "finite_ok": 1.0,
    }
    per = {c: 0.1 for c in CATEGORIES}
    per["low_viscosity"] = 0.9  # weak category
    stress_m = {"rel_l2": 0.2, "per_category_rel_l2": per}
    gates_ok = [
        {"id": "finite", "pass": True, "value": 1.0, "tau": 1.0},
        {"id": "conservation", "pass": True, "value": 0.01, "tau": 0.08},
        {"id": "residual_ceiling", "pass": True, "value": 0.2, "tau": 2.0},
    ]
    out = score_run(eval_m, stress_m, gates_ok, stress_coverage=1.0, pack=pack)
    assert out["weakest_category"] == "low_viscosity"
    assert out["robustness_by_category"]["low_viscosity"]["r"] < out[
        "robustness_by_category"
    ]["extended_envelope"]["r"]


def test_coverage_fail_zeros():
    pack = load_score_pack()
    eval_m = {
        "rel_l2": 0.05,
        "residual_mean": 0.1,
        "conservation_error": 0.01,
        "finite_ok": 1.0,
    }
    stress_m = {"rel_l2": 0.1, "per_category_rel_l2": {"extended_envelope": 0.1}}
    gates_ok = [{"id": "finite", "pass": True, "value": 1.0, "tau": 1.0}]
    out = score_run(eval_m, stress_m, gates_ok, stress_coverage=0.3, pack=pack)
    assert out["coverage_fail"] is True
    assert out["combined"] == 0.0
