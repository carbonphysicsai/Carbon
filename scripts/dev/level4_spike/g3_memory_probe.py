"""G3's isolated parse under a range of address-space limits (CPU, development).

Runs the real intake (`carbon.level4.intake.intake`, isolated parse worker)
on a Challenge adapter's largest legitimate submissions (its
`largest_strategies`, lowered through JAX where the adapter can, and its
largest PyTorch exports) at each limit, and records the verdict and wall
time. The bounds other than memory are this probe's own, far above every
measured size; nothing here chooses a value
(`docs/development/graphite/level4/LEVEL4_VALUES_PROPOSAL.md` reads it).

Usage: python scripts/dev/level4_spike/g3_memory_probe.py --adapter NAME --out FILE
(NAME selects the Challenge's adapter module, `carbon.<NAME>.level4`.)
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
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
LIMITS_MIB = (96, 128, 192, 256, 384, 512)
PROBE_BOUNDS = {
    "manifest_bytes": 1 << 20,
    "document_bytes": 1 << 26,
    "submission_bytes": 1 << 27,
    "parse_seconds": 60,
}


def _submissions(adapter, allowlist):
    from carbon.level4 import submission
    from carbon.level4.tooling import lower_torch

    out, not_lowered = {}, {}
    for label, strategy in getattr(adapter, "largest_strategies", dict)().items():
        try:
            out[label] = adapter.lower_recipe(strategy, allowlist, max_bytes=1 << 30)
        except Exception as error:  # noqa: BLE001 - not lowerable through JAX
            not_lowered[label] = type(error).__name__
    for label, strategy, largest in getattr(adapter, "torch_cases", tuple)():
        if not largest or label in out:
            continue
        (params, net, _), _reference, f = adapter.torch_build(strategy)
        _raw, core = lower_torch.export(net, params, f)
        doc, _ = lower_torch.lower(core, allowlist=allowlist)
        out[label] = submission.build(
            challenge=adapter.challenge_id(),
            interface="sha256:" + "0" * 64,  # size only; not admitted here
            allowlist=allowlist,
            forward=doc,
            init_spec=adapter.torch_init_spec(doc),
        )
        not_lowered.pop(label, None)
    return out, not_lowered


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import graph, intake, submission

    adapter = importlib.import_module(f"carbon.{args.adapter}.level4")
    allowlist = allowlist_module.load()
    rows = {}
    submissions, not_lowered = _submissions(adapter, allowlist)
    for label, (manifest, files) in submissions.items():
        raw = submission.canonical(manifest)
        for mib in LIMITS_MIB:
            started = time.perf_counter()
            try:
                intake.intake(
                    raw,
                    files,
                    allowlist=allowlist,
                    challenge=manifest["challenge"],
                    interface=manifest["interface"],
                    bounds={**PROBE_BOUNDS, "parse_memory_bytes": mib << 20},
                )
                verdict = "ok"
            except graph.GraphRefused as refused:
                verdict = refused.code
            rows[f"{label}@{mib}MiB"] = {
                "verdict": verdict,
                "wall_seconds": round(time.perf_counter() - started, 3),
                "submission_bytes": len(raw) + sum(len(b) for b in files.values()),
            }
    report = {
        "schema": "carbon.development.level4-g3-memory-probe.v1",
        "adapter": args.adapter,
        "limits_mib": list(LIMITS_MIB),
        "not_lowered": not_lowered,
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
