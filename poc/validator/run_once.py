"""Carbon PoC entry point: strategy handoff → procedural data → train → gates → card.

Exit codes:
  0  completed (card written even if gate failed / score 0)
  2  handoff / schema reject
  3  internal error

Submission rule: strategy JSON only. No weights, data, or seed overrides.
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

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from poc.generators.burgers1d import GENERATOR_VERSION, generate_batch
from poc.train.loop import train
from poc.eval.metrics import evaluate
from poc.eval.gates import run_gates
from poc.eval.score import score_run
from poc.validator.handoff import accept_submission
from carbon.common.model_card import build_model_card, write_model_card
from carbon.common.seeds import splitmix64, derive_master_seed


def run_once(
    strategy_path: str,
    local_nonce: int = 42,
    run_id: str = "poc_run",
    artifacts_dir: str | Path | None = None,
    fast: bool | None = None,
    block_hash: str = "local",
    local_mode: bool = True,
) -> dict:
    if fast is None:
        fast = os.environ.get("POC_FAST", "0") == "1"

    # --- Handoff: strategy-only acceptance ---
    envelope, err = accept_submission(
        strategy_path,
        block_hash=block_hash,
        run_nonce=local_nonce,
        fast=fast,
        local_mode=local_mode,
    )
    if err:
        print(f"HANDOFF REJECT: {err}", file=sys.stderr)
        sys.exit(2)

    strategy = envelope.strategy
    limits = envelope.limits
    artifacts_dir = Path(artifacts_dir or (_ROOT / "artifacts" / "model_cards"))
    ctx = envelope.seed_context

    # --- Procedural data (validator-owned seeds) ---
    gen_kw = dict(
        local_nonce=local_nonce,
        run_id=run_id,
        fast=fast,
        block_hash=ctx.block_hash,
        local_mode=ctx.local_mode,
        challenge_id=ctx.challenge_id,
    )
    train_batch = generate_batch("train", **gen_kw)
    eval_batch = generate_batch("eval", **gen_kw)
    stress_batch = generate_batch("stress", **gen_kw)

    # init seed from hierarchy (not miner-supplied)
    if ctx.local_mode:
        init_seed = int(local_nonce) % (2**31 - 1)
    else:
        master = derive_master_seed(ctx.challenge_id, ctx.block_hash, ctx.run_nonce)
        init_seed = splitmix64(master, 2)  # init stream

    params, cfg, train_info = train(
        strategy, train_batch, limits, init_seed=init_seed
    )

    eval_m = evaluate(params, cfg, eval_batch)
    stress_m = evaluate(params, cfg, stress_batch)
    eval_metrics = {k: v for k, v in eval_m.items() if k != "pred"}
    stress_metrics = {k: v for k, v in stress_m.items() if k != "pred"}

    gate_inputs = {
        "finite_ok": float(
            eval_metrics.get("finite_ok", 1.0) * stress_metrics.get("finite_ok", 1.0)
        ),
        "conservation_error": float(eval_metrics.get("conservation_error", 0.0)),
        "residual_mean": float(eval_metrics.get("residual_mean", 0.0)),
        "eval_rel_l2": float(eval_metrics.get("rel_l2", 1.0)),
        "rel_l2": float(eval_metrics.get("rel_l2", 1.0)),
    }
    gates = run_gates(gate_inputs, strategy=strategy)
    score = score_run(eval_metrics, stress_metrics, gates)

    seeds = {
        "train": train_batch.seed,
        "eval": eval_batch.seed,
        "stress": stress_batch.seed,
        "train_hash": train_batch.hash(),
        "eval_hash": eval_batch.hash(),
        "stress_hash": stress_batch.hash(),
        "init_seed": init_seed,
        "local_nonce": local_nonce,
        "run_id": run_id,
        "block_hash": ctx.block_hash,
        "local_mode": ctx.local_mode,
        "train_provenance": train_batch.provenance,
        "eval_provenance": eval_batch.provenance,
        "stress_provenance": stress_batch.provenance,
    }

    backend = train_info.get("backend", "unknown")
    train_quality_claim = bool(
        backend == "jax" and train_info.get("train_quality_claimable", False)
    )

    software = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "device": train_info.get("device", "cpu"),
        "backend": backend,
    }
    try:
        import jax

        software["jax"] = jax.__version__
    except ImportError:
        pass

    budget_used = {
        "steps": train_info["steps"],
        "wall_s": train_info["wall_s"],
        "first_loss": train_info.get("first_loss"),
        "last_loss": train_info.get("last_loss"),
        "loss_ratio": train_info.get("loss_ratio"),
        "loss_improved": train_info.get("loss_improved", False),
        "train_quality_claim": train_quality_claim,
        "backend": backend,
        "optimizer": train_info.get("optimizer"),
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
        budget_used=budget_used,
        generator_version=GENERATOR_VERSION,
        software=software,
        extra={
            "strategy_path": str(strategy_path),
            "strategy_hash": envelope.strategy_hash,
            "handoff": envelope.to_public_dict(),
        },
    )
    card["card_id"] = card.get("card_id") or str(uuid.uuid4())

    path = write_model_card(card, artifacts_dir)
    print(
        json.dumps(
            {
                "card_path": str(path),
                "strategy_hash": envelope.strategy_hash,
                "combined": score["combined"],
                "gate_failed": score["gate_failed"],
                "failures": score["hard_gate_failures"],
                "eval_rel_l2": eval_metrics.get("rel_l2"),
                "steps": train_info["steps"],
                "backend": backend,
                "first_loss": train_info.get("first_loss"),
                "last_loss": train_info.get("last_loss"),
                "loss_ratio": train_info.get("loss_ratio"),
                "train_quality_claim": train_quality_claim,
                "seeds": {
                    "train": seeds["train"],
                    "eval": seeds["eval"],
                    "stress": seeds["stress"],
                    "block_hash": ctx.block_hash,
                    "local_mode": ctx.local_mode,
                },
            },
            indent=2,
        )
    )
    if backend == "numpy_fd":
        print(
            "NOTE: backend=numpy_fd is PROTOCOL_ONLY — not train-quality evidence.",
            file=sys.stderr,
        )
    elif not train_quality_claim:
        print(
            "NOTE: train_quality_claim=false (loss did not drop ≥5%).",
            file=sys.stderr,
        )
    return card


def main(argv=None):
    p = argparse.ArgumentParser(description="Carbon Burgers×FNO PoC run_once")
    p.add_argument("strategy", help="Path to strategy JSON (strategy-only handoff)")
    p.add_argument("--local-nonce", type=int, default=42)
    p.add_argument("--run-id", default="poc_run")
    p.add_argument("--block-hash", default="local", help="Chain block hash (official eval)")
    p.add_argument(
        "--official",
        action="store_true",
        help="Official seed path (master from block_hash); default is local miner loop",
    )
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
            block_hash=args.block_hash,
            local_mode=not args.official,
        )
    except SystemExit:
        raise
    except Exception as e:
        print(f"INTERNAL ERROR: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
