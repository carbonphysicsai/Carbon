#!/usr/bin/env python3
"""Credential-free native macOS diagnostics and one-update C-02 smoke run."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))


def _doctor() -> int:
    report: dict[str, object] = {
        "schema": "carbon.c02.macos-doctor.v1",
        "platform": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_ok": sys.version_info[:2] == (3, 11),
        "disk_free_gib": round(shutil.disk_usage(Path.cwd()).free / 2**30, 2),
        "credentials_required": False,
    }
    try:
        memory = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            text=True,
        )
        report["memory_gib"] = round(int(memory.stdout.strip()) / 2**30, 2)
    except (OSError, ValueError, subprocess.CalledProcessError):
        report["memory_gib"] = None
    try:
        import jax
        import jaxlib
        import numpy
        import scipy

        report["runtime"] = {
            "jax": jax.__version__,
            "jaxlib": jaxlib.__version__,
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "backend": jax.default_backend(),
        }
    except ImportError as error:
        report["runtime_error"] = error.name
    ok = (
        report["platform"] == "Darwin"
        and report["machine"] == "arm64"
        and report["python_ok"] is True
        and report["disk_free_gib"] >= 5.0
        and "runtime_error" not in report
    )
    report["status"] = "READY" if ok else "NOT_READY"
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if ok else 2


def _smoke() -> int:
    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.reconstruction._vendor.carbon_jax_lab.checkpoint import (
        load_inference,
        save_checkpoint,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.config import (
        ModelConfig,
        TaskConfig,
        TrainConfig,
    )
    from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
    from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer

    points = 16
    positions = np.arange(points, dtype=np.float64) / points
    initial = np.stack((np.sin(2 * np.pi * positions), np.cos(2 * np.pi * positions)))
    times = np.array([[0.05, 0.1], [0.05, 0.1]], dtype=np.float64)
    # Preserve [case,time,point] ordering explicitly.
    solution = np.stack((initial * 0.98, initial * 0.96), axis=1)
    data = Trajectories(
        initial,
        np.array([0.01, 0.02]),
        times,
        solution,
        positions,
        "train",
        "carbon_c02_native_smoke",
    )
    trainer = Trainer(
        ModelConfig(width=8, depth=1, heads=2, n_modes=8),
        TaskConfig(),
        TrainConfig(steps=1, warmup_steps=0, batch_size=2),
        data,
        runtime_key_material=bytes(range(32)),
    )
    started = time.perf_counter()
    trainer.fit()
    with tempfile.TemporaryDirectory(prefix="carbon-c02-smoke-") as directory:
        checkpoint = Path(directory) / "checkpoint"
        save_checkpoint(trainer, checkpoint)
        predictor, parameters, _ = load_inference(checkpoint)
        prediction = predictor(
            parameters,
            jnp.asarray(initial, jnp.float32),
            jnp.asarray(data.viscosity, jnp.float32),
            jnp.asarray(times[:, 0], jnp.float32),
            jnp.asarray(positions, jnp.float32),
        )
        jax.block_until_ready(prediction)
    result = {
        "schema": "carbon.c02.macos-smoke.v1",
        "status": "PASS",
        "steps": int(trainer.state.step),
        "compile_seconds": trainer.timing["compile_seconds"],
        "train_execution_seconds": trainer.timing["train_execution_seconds"],
        "total_seconds": time.perf_counter() - started,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"doctor", "smoke"}:
        print("usage: jax_macos_diagnostic.py {doctor|smoke}", file=sys.stderr)
        return 2
    return _doctor() if sys.argv[1] == "doctor" else _smoke()


if __name__ == "__main__":
    raise SystemExit(main())
