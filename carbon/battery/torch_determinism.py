# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Repeat-and-compare evidence for the PyTorch backend (RECON-TORCH-01).

The owner sets the PyTorch backend's reproducibility tolerance
(OWNER-PYTORCH-BACKEND-01, human-reserved). This harness produces the evidence
for that decision and decides nothing: it rebuilds one compiled recipe N times
with the same reconstruction seed, each in a fresh interpreter, and reports
exactly how the weights and predictions differ.

    python -m carbon.battery.torch_determinism --recipe recipe.json \\
        --repeats 5 --seed 0 --out report.json

`recipe.json` is a battery strategy (the document a miner submits). The report
records the host facts the result depends on (CPU model, thread count, torch
and numpy versions), so reports from different hosts can be compared. It
names no threshold, and no field in it is a pass or a fail.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

SCHEMA = "carbon.battery.pytorch-determinism-report.v1"

#: One rebuild in a fresh interpreter: the weights digest and predictions on
#: the fixed PRACTICE inputs, as JSON on stdout.
_CHILD = """
import json, sys
import numpy as np
from carbon.battery import challenge as ch
from carbon.battery.compile import compile_recipe, rebuild
from carbon.battery.practice import PracticeSet

strategy, seed, root = json.loads(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
_, recipe = compile_recipe(strategy)
material = ch.PublicMaterial.load(root)
model, stats = rebuild(recipe, material, seed)
practice = PracticeSet.load(root)
x = np.array([[c["inputs"][k] for k in ch.INPUTS] for c in practice.inputs_document()["cases"]], float)
out = model.predict(x)
print(json.dumps({
    "params_sha256": stats["params_sha256"],
    "backend": stats.get("backend", "jax"),
    "predictions": {k: np.asarray(v, float).tolist() for k, v in out.items()},
}))
"""


def _host():
    import numpy

    facts = {
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "cpu_count": os.cpu_count(),
    }
    try:
        import torch

        facts["torch"] = torch.__version__
        facts["torch_threads_default"] = torch.get_num_threads()
    except ImportError:
        facts["torch"] = None
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                facts["cpu_model"] = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return facts


def _rebuild(strategy, seed, root):
    result = subprocess.run(
        [sys.executable, "-c", _CHILD, json.dumps(strategy), str(seed), str(root)],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(root).resolve(),
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def compare(runs):
    """Exact differences of every run against the first; no threshold."""
    import numpy as np

    first = runs[0]
    rows = []
    for i, run in enumerate(runs[1:], start=1):
        diff = {}
        for key, values in first["predictions"].items():
            a, b = np.asarray(values, float), np.asarray(run["predictions"][key], float)
            diff[key] = {
                "max_abs": float(np.max(np.abs(a - b))),
                "identical": bool(np.array_equal(a, b)),
            }
        rows.append(
            {
                "run": i,
                "weights_identical": run["params_sha256"] == first["params_sha256"],
                "predictions": diff,
            }
        )
    return rows


def study(strategy, *, repeats, seed, root="."):
    if repeats < 2:
        raise ValueError("a comparison needs at least two rebuilds")
    runs = [_rebuild(strategy, seed, root) for _ in range(repeats)]
    rows = compare(runs)
    return {
        "schema": SCHEMA,
        "authority": "evidence for OWNER-PYTORCH-BACKEND-01; sets no tolerance",
        "strategy": strategy,
        "seed": seed,
        "repeats": repeats,
        "backend": runs[0]["backend"],
        "host": _host(),
        "weights_sha256": [r["params_sha256"] for r in runs],
        "all_weights_identical": all(r["weights_identical"] for r in rows),
        "comparisons": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = study(
        json.loads(args.recipe.read_text()),
        repeats=args.repeats,
        seed=args.seed,
        root=args.root,
    )
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        f"{report['repeats']} rebuilds; weights identical: "
        f"{report['all_weights_identical']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
