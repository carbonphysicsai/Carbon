"""Prove the PoC pipeline stages are wired end-to-end (offline).

Contract chain:
  strategy file → schema → batches → train → eval metrics → gates → score → card
"""

from __future__ import annotations

import json
from pathlib import Path

from poc.validator.schema_check import load_strategy_file, load_limits
from poc.generators.burgers1d import generate_batch
from poc.train.loop import train
from poc.eval.metrics import evaluate
from poc.eval.gates import run_gates, all_passed
from poc.eval.score import score_run
from carbon.common.model_card import build_model_card, write_model_card

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "poc" / "fixtures"


def test_stages_talk_data_only(tmp_path):
    strategy, err = load_strategy_file(FIXTURES / "strategy_data_only.json", fast=True)
    assert err is None, err
    assert strategy["backbone"] == "fno1d"

    limits = load_limits(fast=True)
    assert limits["max_steps"] <= 100

    train_b = generate_batch("train", 1, "wire", fast=True)
    eval_b = generate_batch("eval", 1, "wire", fast=True)
    stress_b = generate_batch("stress", 1, "wire", fast=True)
    assert train_b.seed != eval_b.seed != stress_b.seed
    assert train_b.u0.shape[0] > 0 and train_b.uT.shape == train_b.u0.shape

    params, cfg, info = train(strategy, train_b, limits, init_seed=1)
    assert isinstance(params, dict) and "lift_w" in params
    assert info["steps"] >= 1
    assert info["backend"] in ("jax", "numpy_fd")

    eval_m = evaluate(params, cfg, eval_b)
    stress_m = evaluate(params, cfg, stress_b)
    for key in ("rel_l2", "residual_mean", "conservation_error", "finite_ok"):
        assert key in eval_m

    gate_inputs = {
        "finite_ok": float(eval_m["finite_ok"] * stress_m["finite_ok"]),
        "conservation_error": float(eval_m["conservation_error"]),
        "residual_mean": float(eval_m["residual_mean"]),
        "eval_rel_l2": float(eval_m["rel_l2"]),
        "rel_l2": float(eval_m["rel_l2"]),
    }
    gates = run_gates(gate_inputs, strategy=strategy)
    assert isinstance(gates, list) and len(gates) >= 3
    assert all("id" in g and "pass" in g for g in gates)

    score = score_run(
        {k: v for k, v in eval_m.items() if k != "pred"},
        {k: v for k, v in stress_m.items() if k != "pred"},
        gates,
    )
    assert "combined" in score and "gate_failed" in score
    ok, fails = all_passed(gates)
    if not ok:
        assert score["combined"] == 0.0
        assert score["gate_failed"] is True
        assert set(fails) <= set(score["hard_gate_failures"])

    card = build_model_card(
        challenge_id=strategy["challenge_id"],
        backbone=strategy["backbone"],
        strategy=strategy,
        seeds={"train": train_b.seed, "eval": eval_b.seed, "stress": stress_b.seed},
        metrics={
            "eval_rel_l2": eval_m["rel_l2"],
            "stress_rel_l2": stress_m["rel_l2"],
            "residual_mean": eval_m["residual_mean"],
            "conservation_error": eval_m["conservation_error"],
        },
        gates=gates,
        score=score,
        budget_used={"steps": info["steps"], "backend": info["backend"]},
        generator_version=train_b.generator_version,
    )
    path = write_model_card(card, tmp_path)
    assert path.exists()
    written = json.loads(path.read_text())
    assert written["score"]["combined"] == score["combined"]
    assert written["gates"] == gates

    reg = (tmp_path / "registry.jsonl").read_text().strip().splitlines()
    assert len(reg) == 1
    line = json.loads(reg[0])
    assert line["combined_score"] == score["combined"]
    assert line["card_id"] == card["card_id"]


def test_broken_strategy_zeros_via_wired_gates():
    strategy, err = load_strategy_file(FIXTURES / "strategy_broken.json", fast=True)
    assert err is None
    # loss_signal must fail without needing a full train
    gates = run_gates(
        {
            "finite_ok": 1.0,
            "conservation_error": 0.0,
            "residual_mean": 0.0,
            "eval_rel_l2": 0.1,
        },
        strategy=strategy,
    )
    ok, fails = all_passed(gates)
    assert not ok
    assert "loss_signal" in fails
    score = score_run(
        {"rel_l2": 0.1, "residual_mean": 0.0, "conservation_error": 0.0},
        {"rel_l2": 0.1},
        gates,
    )
    assert score["combined"] == 0.0
