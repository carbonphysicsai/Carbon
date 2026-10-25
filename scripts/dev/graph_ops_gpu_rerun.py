#!/usr/bin/env python3
"""Run every allowlist-v8 op specimen on the GPU twice, under Carbon's pinned JAX GPU
determinism environment, and say which are bit-identical and how far the GPU result
is from the CPU result (Validator VALIDATOR_GRAPH_OPS_V8_RULINGS_20261025, section 1:
"each op's specimen must rerun bit-identically ... on GPU under the pinned flags; an op
that fails is admitted CPU-only").

Needs an NVIDIA machine with a CUDA-enabled jaxlib (the jax-cuda13 worker image or an
environment from `.devcontainer/accelerators/cuda13-py311.txt`) and a Carbon checkout.
It reads no private data and starts nothing; it prints one JSON document to stdout and
writes it to `--out` when given.

    python scripts/dev/graph_ops_gpu_rerun.py --out graph-ops-gpu-rerun.json

Exit code 0 when every specimen reran bit-identically on the GPU, 1 otherwise (the
JSON still lists each one). Run it with the same command on a CPU-only machine to see
the harness work: every specimen is then compared with itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The pinned determinism environment (backbone_catalog/gpu_receipt.py): set before JAX loads.
os.environ.setdefault(
    "XLA_FLAGS",
    "--xla_gpu_deterministic_ops=true --xla_gpu_exclude_nondeterministic_ops=true "
    "--xla_gpu_autotune_level=0",
)
os.environ.setdefault("NVIDIA_TF32_OVERRIDE", "0")
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
os.environ.setdefault("JAX_DEFAULT_MATMUL_PRECISION", "highest")

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "cpu"))


def _cases(module):
    cases = {}
    for name, (_ops, fn, args, _diff) in module.CASES.items():
        cases[name] = (fn, args)
    for name, fn in module.SOLVES.items():
        cases["solve:" + name] = (fn, (module._spd(), module._signed((3, 2))))
    for name, fn in module.CUSTOM_RULES.items():
        cases["custom_rule:" + name] = (fn, (module._positive(),))
    return cases


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="also write the JSON here")
    parser.add_argument("--tolerance", type=float, default=1e-4, help="GPU vs CPU, relative")
    args = parser.parse_args(argv)

    import jax
    import numpy as np

    import test_level4_graph_ops_freedom as specimens

    gpus = [d for d in jax.devices() if d.platform == "gpu"]
    cpu = jax.devices("cpu")[0]
    device = gpus[0] if gpus else cpu
    report = {
        "schema": "carbon.graph-ops-gpu-rerun.v1",
        "jax": jax.__version__,
        "device": getattr(device, "device_kind", str(device)),
        "platform": device.platform,
        "xla_flags": os.environ["XLA_FLAGS"],
        "tolerance": args.tolerance,
        "specimens": {},
    }
    for name, (fn, inputs) in sorted(_cases(specimens).items()):
        entry = {}
        try:
            _doc, run = specimens._rebuilt(fn, inputs)
            with jax.default_device(device):
                placed = [jax.device_put(a, device) for a in inputs]
                first = np.asarray(run(*placed)[0])
                second = np.asarray(run(*placed)[0])
            with jax.default_device(cpu):
                reference = np.asarray(run(*[jax.device_put(a, cpu) for a in inputs])[0])
            entry["bit_identical"] = bool(first.tobytes() == second.tobytes())
            scale = max(float(np.max(np.abs(reference))), 1e-30)
            difference = float(
                np.max(np.abs(first.astype(np.float64) - reference.astype(np.float64)))
            )
            entry["max_abs_vs_cpu"] = difference
            entry["within_tolerance"] = bool(difference <= args.tolerance * scale)
        except Exception as error:  # noqa: BLE001 - a specimen that cannot run is a finding
            entry = {"bit_identical": False, "error": f"{type(error).__name__}: {error}"[:300]}
        report["specimens"][name] = entry
    failing = sorted(
        name
        for name, entry in report["specimens"].items()
        if not entry["bit_identical"] or entry.get("within_tolerance") is False
    )
    report["cpu_only_candidates"] = failing
    text = json.dumps(report, indent=1, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 1 if any(not e["bit_identical"] for e in report["specimens"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
