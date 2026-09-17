"""Finite CPU fixture throughput experiment; no campaign, grant or scientific claim.

Run inside the numerical test environment with --output to retain measurements.
No accelerator is initialized by default: the environment pins JAX_PLATFORMS=cpu
before numerical imports. GPU/TPU benchmarking belongs inside admitted workers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new immutable observation file")
    os.environ["JAX_PLATFORMS"] = "cpu"
    import jax
    import numpy as np

    from carbon.reconstruction import compiled_updates
    from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
        environment,
        save_checkpoint,
        source_identity,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.config import (
        ModelConfig,
        TaskConfig,
        TrainConfig,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
    from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer

    fit_chunks = compiled_updates.fit_chunks

    rows = []
    for points in (16, 64, 128):
        x = np.arange(points, dtype=np.float64) / points
        initial = np.stack(
            [np.sin(2 * np.pi * x + phase) for phase in (0, 0.5, 1, 1.5)]
        )
        data = Trajectories(
            initial,
            np.full(4, 0.02),
            np.tile([0.05, 0.1], (4, 1)),
            np.stack([initial * 0.98, initial * 0.96], axis=1),
            x,
            "train",
            "synthetic_chunk_throughput_fixture",
        )
        for chunk in (0, 4, 16):
            started = time.monotonic()
            trainer = Trainer(
                ModelConfig(kind="fno1d", width=8, depth=1, n_modes=4),
                TaskConfig(),
                TrainConfig(
                    steps=16,
                    warmup_steps=0,
                    batch_size=2,
                    h1_weight=0.01,
                    pde_weight=0.001,
                ),
                data,
            )
            jax.block_until_ready((trainer.state, trainer.arrays))
            setup = time.monotonic() - started
            if chunk:
                timing = fit_chunks(trainer, chunk_size=chunk)
            else:
                before = time.monotonic()
                trainer.fit()
                timing = {
                    "compile_seconds": trainer.timing["compile_seconds"],
                    "execution_including_host_diagnostics_seconds": trainer.timing[
                        "train_execution_seconds"
                    ],
                    "total_seconds": time.monotonic() - before,
                }
            with tempfile.TemporaryDirectory(
                prefix="carbon-chunk-checkpoint-"
            ) as folder:
                checkpoint = Path(folder) / "state"
                before = time.monotonic()
                save_checkpoint(trainer, checkpoint)
                checkpoint_seconds = time.monotonic() - before
                checkpoint_bytes = sum(
                    item.stat().st_size
                    for item in checkpoint.rglob("*")
                    if item.is_file()
                )
            rows.append(
                {
                    "points": points,
                    "steps": 16,
                    "chunk_size": chunk or 1,
                    "route": "compiled_chunk" if chunk else "existing_per_update",
                    "setup_seconds": setup,
                    "timing": timing,
                    "last_loss": trainer.history[-1]["loss"],
                    "final_step": int(trainer.state.step),
                    "checkpoint_seconds": checkpoint_seconds,
                    "checkpoint_bytes": checkpoint_bytes,
                    "model": asdict(trainer.model_config),
                    "training": asdict(trainer.config),
                    "task": asdict(trainer.task_config),
                    "data_digest": data.fingerprint,
                }
            )
    record = {
        "schema": "carbon.compiled-updates.benchmark.v1",
        "scope": "SYNTHETIC_DEVELOPMENT_THROUGHPUT_ONLY",
        "backend": jax.default_backend(),
        "jax": jax.__version__,
        "environment": environment(),
        "trainer_source": source_identity(),
        "experiment_source_sha256": hashlib.sha256(
            Path(compiled_updates.__file__).read_bytes()
        ).hexdigest(),
        "benchmark_source_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "rows": rows,
        "qualification": False,
        "limitations": [
            "fixed-work microbenchmark, not quality-per-budget or autonomous research",
            "CPU only; no hardware comparison",
            "execution timing includes device synchronization; compile and setup reported separately",
            "warm executables and input shapes are bounded to this process",
            "single observation in fixed order; cache and order effects prevent statistical speedup claims",
            "max chunk execution time excludes compilation; independent worker supervision remains necessary",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
