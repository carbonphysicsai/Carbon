"""Level 4 Phase 1 design record (CPU only, development only).

Q1: every trainable family's gradients and training through B' with
allowlist v1's named functions; Q3: a PyTorch-authored graph initialized and
trained by Carbon; the Phase 0 equivalence re-run under v1; and the PyTorch
B' agreement under v1 (largest FNO excluded).

    python scripts/dev/level4_spike/run_design.py OUT.json --adapter NAME [--steps N]
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
REPOSITORY = Path(__file__).resolve().parents[3]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

SCHEMA = "carbon.development.level4-phase1-design-results.v0"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--init-steps", type=int, default=50)
    parser.add_argument("--max-bytes", type=int, default=1 << 30)
    args = parser.parse_args(argv)

    from level4_spike import allowlist as allowlist_module
    from level4_spike.run import environment, torch_section

    adapter = importlib.import_module(f"level4_spike.adapters.{args.adapter}")
    allowlist = allowlist_module.load()
    started = time.perf_counter()
    record = {
        "schema": SCHEMA,
        "status": "DEVELOPMENT. CPU only. No caps chosen; every cap is HUMAN_INPUT.",
        "adapter": args.adapter,
        "environment": environment(),
        "allowlist": {"version": allowlist.version, "digest": allowlist.digest},
    }
    gradients, training = {}, {}
    for label, strategy in adapter.gradient_cases():
        gradients[label] = adapter.gradient_equivalence(
            allowlist, strategy, max_bytes=args.max_bytes
        )
        training[label] = adapter.training_equivalence(
            allowlist, strategy, steps=args.steps, max_bytes=args.max_bytes
        )
    record["q1_gradients"] = gradients
    record["q1_training"] = training
    record["q3_carbon_init"] = {
        label: adapter.torch_carbon_init(
            allowlist, strategy, steps=args.init_steps, max_bytes=args.max_bytes
        )
        for label, strategy, largest in adapter.torch_cases()
        if not largest and label in ("default_fno", "torch_mlp", "torch_deeponet")
    }
    rows, _, _ = torch_section(
        adapter, allowlist, args.max_bytes, include_largest=False
    )
    record["torch_v1"] = {
        r["label"]: {"lowering": r["lowering"], "bprime_vs_torch": r["bprime_vs_torch"]}
        for r in rows
    }
    record["phase0_equivalence_v1"] = adapter.equivalence(
        allowlist, steps=args.steps, max_bytes=args.max_bytes
    )
    record["seconds"] = round(time.perf_counter() - started, 1)
    Path(args.out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"out": args.out, "seconds": record["seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
