"""Carbon PoC entry point: strategy.json → train → gates → score → Model Card.

Exit codes:
  0  completed (card written even if gate failed / score 0)
  2  schema reject
  3  internal error
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import uuid
from pathlib import Path

import numpy as np

# Ensure repo root on path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from poc.generators.burgers1d import GENERATOR_VERSION, generate_batch
from poc.models.fno1d import forward
from poc.train.loop import train
from poc.eval.metrics import evaluate
from poc.eval.gates import run_gates
from poc.eval.score import score_run
from poc.validator.schema_check import load_limits, load_strategy_file
from carbon.common.model_card import build_model_card, write_model_card, strategy_hash


def run_once(
    strategy_path: str,
    local_nonce: int = 42,
    run_id: str = "poc_run",
    artifacts_dir: str | Path | None = None,
    fast: bool | None = None,
) -> dict:
    if fast is None:
        fast = os.environ.get("POC_FAST", "0") == "1"

    strategy, err = load_strategy_file(strategy_path, fast=fast)
    if err:
        print(f"SCHEMA REJECT: {err}", file=sys.stderr)
        sys.exit(2)

    limits = load_limits(fast=fast)
    artifacts_dir = Path(artifacts_dir or (_ROOT / "artifacts" / "model_cards"))

    # --- Data (role-separated seeds) ---
    train_batch = generate_batch("train", local_nonce, run_id, fast=fast)
    eval_batch = generate_batch("eval", local_nonce, run_id, fast=fast)
    stress_batch = generate_batch("stress", local_nonce, run_id, fast=fast)

    # --- Train ---
    params, cfg, train_info = train(
        strategy, train_batch, limits, init_seed=local_nonce
    )

    # --- Eval + stress ---
    eval_m = evaluate(params, cfg, eval_batch)
    stress_m = evaluate(params, cfg, stress_batch)
    # Drop large arrays before card
    eval_metrics = {k: v for k, v in eval_m.items() if k != "pred"}
    stress_metrics = {k: v for k, v in stress_m.items() if k != "pred"}

    # --- Gates (fp32 / float64 diagnostics already) ---
    # Use eval residual/conservation for gate inputs; finite from both
    gate_inputs = {
        "finite_ok": float(
            eval_metrics.get("finite_ok", 1.0) * stress_metrics.get("finite_ok", 1.0)
        ),
        "conservation_error": float(eval_metrics.get("conservation_error", 0.0)),
        "residual_mean": float(eval_metrics.get("residual_mean", 0.0)),
    }
    gates = run_gates(gate_inputs)
    score = score_run(eval_metrics, stress_metrics, gates)

    seeds = {
        "train": train_batch.seed,
        "eval": eval_batch.seed,
        "stress": stress_batch.seed,
        "train_hash": train_batch.hash(),
        "eval_hash": eval_batch.hash(),
        "stress_hash": stress_batch.hash(),
        "local_nonce": local_nonce,
        "run_id": run_id,
    }

    card = build_model_card(
        challenge_id=strategy["challenge_id"],
        backbone=strategy["backbone"],
        strategy=strategy,
        seeds=seeds,
        metrics={
            "eval_rel_l2": eval_metrics.get("rel_l2", 0.0),
            "stress_rel_l2": stress_metrics.get("rel_l2", 0.0),
            "residual_mean": eval_metrics.get("residual_mean", 0.0),
            "conservation_error": eval_metrics.get("conservation_error", 0.0),
        },
        gates=gates,
        score={
            "physics": score["physics"],
            "robustness": score["robustness"],
            "accuracy": score["accuracy"],
            "combined": score["combined"],
            "gate_failed": score["gate_failed"],
            "hard_gate_failures": score["hard_gate_failures"],
        },
        budget_used={
            "steps": train_info["steps"],
            "wall_s": train_info["wall_s"],
            "last_loss": train_info["last_loss"],
        },
        generator_version=GENERATOR_VERSION,
        software={
            "python": platform.python_version(),
            "numpy": np.__version__,
            "device": train_info.get("device", "cpu"),
        },
        extra={"strategy_path": str(strategy_path)},
    )
    # Align card_id with uuid for PoC
    card["card_id"] = card.get("card_id") or str(uuid.uuid4())

    path = write_model_card(card, artifacts_dir)
    print(json.dumps({
        "card_path": str(path),
        "combined": score["combined"],
        "gate_failed": score["gate_failed"],
        "failures": score["hard_gate_failures"],
        "eval_rel_l2": eval_metrics.get("rel_l2"),
        "steps": train_info["steps"],
        "seeds": {
            "train": seeds["train"],
            "eval": seeds["eval"],
            "stress": seeds["stress"],
        },
    }, indent=2))
    return card


def main(argv=None):
    p = argparse.ArgumentParser(description="Carbon Burgers×FNO PoC run_once")
    p.add_argument("strategy", help="Path to strategy JSON")
    p.add_argument("--local-nonce", type=int, default=42)
    p.add_argument("--run-id", default="poc_run")
    p.add_argument("--artifacts", default=None)
    p.add_argument("--fast", action="store_true", help="CI fast profile")
    args = p.parse_args(argv)

    try:
        run_once(
            args.strategy,
            local_nonce=args.local_nonce,
            run_id=args.run_id,
            artifacts_dir=args.artifacts,
            fast=args.fast or os.environ.get("POC_FAST") == "1",
        )
    except SystemExit:
        raise
    except Exception as e:
        print(f"INTERNAL ERROR: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
