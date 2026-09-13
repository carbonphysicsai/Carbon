"""Local public-research CLI. No network, Carbon registry, or reward integration."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .checkpoint import environment, load_checkpoint, save_checkpoint, source_identity
from .config import SUPPORTED_MODELS, ModelConfig, TaskConfig, TrainConfig
from .data import Trajectories
from .reference import generate_splits
from .training import CancelledTraining, NonFiniteTrainingError, Trainer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="create declared smooth public Burgers fixture")
    g.add_argument("--out", type=Path, required=True)
    g.add_argument("--seed", type=int, default=20260912)
    g.add_argument("--train-cases", type=int, default=64)
    g.add_argument("--validation-cases", type=int, default=16)
    g.add_argument("--audit-cases", type=int, default=16)
    g.add_argument("--points", type=int, default=64)
    g.add_argument("--times", type=int, default=9)
    t = sub.add_parser(
        "train", help="fixed-plan model reconstruction on TRAIN data only"
    )
    t.add_argument("--train", type=Path, required=True)
    t.add_argument("--audit", type=Path)
    t.add_argument("--out", type=Path, required=True)
    t.add_argument("--config", type=Path)
    t.add_argument("--model", choices=SUPPORTED_MODELS, default="fno1d")
    t.add_argument("--steps", type=int, default=300)
    t.add_argument("--seed", type=int, default=42)
    t.add_argument("--resume", type=Path)
    t.add_argument("--stop-at", type=int)
    t.add_argument("--wall-budget-seconds", type=float)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("output directory already exists; retained runs are immutable")
    if args.command == "generate":
        if args.points < 8 or args.points & (args.points - 1):
            parser.error("demo generation uses power-of-two points >=8")
        splits, meta = generate_splits(
            args.train_cases,
            args.validation_cases,
            args.audit_cases,
            args.points,
            args.times,
            args.seed,
        )
        args.out.mkdir(parents=True)
        for data in splits:
            data.save(args.out / (data.role + ".npz"))
        np.savez_compressed(args.out / "reference_parameters.npz", **meta)
        (args.out / "manifest.json").write_text(
            json.dumps(
                {
                    "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
                    "source_id": source_identity(),
                    "splits": {d.role: d.fingerprint for d in splits},
                    "population": "four decaying Gaussian Fourier modes; amplitude scale U(.25,.65); nu U(.03,.08); mean U(-.1,.1); x=[0,1); t=[0,.3]",
                },
                indent=2,
            )
        )
        print(args.out)
        return
    if args.config:
        spec = json.loads(args.config.read_text())
        if set(spec) != {"model", "task", "train"}:
            parser.error("config requires exactly model/task/train sections")
        mc, tc, rc = (
            ModelConfig(**spec["model"]),
            TaskConfig(**spec["task"]),
            TrainConfig(**spec["train"]),
        )
    else:
        mc, tc, rc = (
            ModelConfig(kind=args.model),
            TaskConfig(),
            TrainConfig(
                steps=args.steps,
                seed=args.seed,
                warmup_steps=min(10, max(0, args.steps - 1)),
            ),
        )
    data = Trajectories.load(args.train)
    tr = Trainer(mc, tc, rc, data)
    if args.resume:
        load_checkpoint(tr, args.resume)
    args.out.mkdir(parents=True)
    status = "COMPLETED_FIXED_PLAN"
    try:
        tr.fit(args.stop_at, wall_budget_seconds=args.wall_budget_seconds)
    except CancelledTraining:
        status = "INTERRUPTED_NO_SCIENTIFIC_RESULT"
    except NonFiniteTrainingError:
        status = "FAILED_NONFINITE_PREVIOUS_STATE_RETAINED"
    if int(tr.state.step) < rc.steps and status == "COMPLETED_FIXED_PLAN":
        status = "PARTIAL_PLAN"
    checkpoint = args.out / f"checkpoint-{int(tr.state.step):06d}"
    save_checkpoint(tr, checkpoint)
    result = {
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        "status": status,
        "step": int(tr.state.step),
        "config": {"model": asdict(mc), "task": asdict(tc), "train": asdict(rc)},
        "timing": tr.timing,
        "environment": environment(),
        "checkpoint": checkpoint.name,
    }
    if args.audit and status == "COMPLETED_FIXED_PLAN":
        result["audit"], pred = tr.audit(Trajectories.load(args.audit))
        np.savez_compressed(args.out / "predictions.npz", predictions=pred)
    (args.out / "history.json").write_text(
        json.dumps(tr.history, indent=2, allow_nan=False)
    )
    (args.out / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
