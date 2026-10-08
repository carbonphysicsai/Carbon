"""Evidence for the Level 4 values the owner sets (CPU, development only).

For every recipe a Challenge's Level 4 adapter can lower, this measures what
each HUMAN_INPUT value bounds:

* G0 intake: manifest, document and whole-submission bytes;
* G3 parse: seconds and peak Python allocation per document (in process;
  the real G3 runs `carbon.level4._parse_worker` under rlimits);
* G4: the graph counts the caps bound (`graph.measure`) and validation time;
* G5: Carbon's own lane program (`carbon.level4.compile.PROGRAM`) run on the
  staged bytes in an isolated (`python -I`) subprocess, as the G5 test does:
  wall seconds, the child's peak resident memory, and the program's own
  compile seconds, forward temporaries and FLOPs.

Nothing here chooses a value. `docs/development/graphite/level4/
LEVEL4_VALUES_PROPOSAL.md` reads this file's output and proposes them.

Usage: python scripts/dev/level4_spike/values_evidence.py --adapter battery
       [--adapter motor] --out FILE
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")
REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))
#: This script's own parser bound, far above every measured size; not a G3 limit.
MAX_BYTES = 1 << 30
LANE_SECONDS = 1800


def _parse(raw):
    from carbon.level4 import graph

    tracemalloc.start()
    started = time.perf_counter()
    doc = graph.parse(raw, max_bytes=MAX_BYTES)
    seconds = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return doc, {"parse_seconds": seconds, "parse_peak_bytes": peak}


def _lane(parsed, allowlist):
    """G5's program on staged bytes, isolated, with the child's peak RSS."""
    from carbon.level4 import compile as g5

    files = g5.staged_files(parsed, allowlist, max_bytes=MAX_BYTES)
    with tempfile.TemporaryDirectory() as directory:
        work, output = Path(directory) / "work", Path(directory) / "output"
        work.mkdir()
        output.mkdir()
        for name, body in files.items():
            (work / name).write_bytes(body)
        before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        started = time.perf_counter()
        run = subprocess.run(
            [sys.executable, "-I", "-c", g5.PROGRAM],
            cwd=work,
            capture_output=True,
            timeout=LANE_SECONDS,
            check=False,
            env={"JAX_PLATFORMS": "cpu", "PATH": "/usr/bin:/bin"},
        )
        wall = time.perf_counter() - started
        peak_kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        if run.returncode:
            return {"failed": run.stderr.decode(errors="replace")[-400:]}
        result = json.loads((output / "compile.json").read_text())
    return {
        **result,
        "lane_wall_seconds": wall,
        # ru_maxrss is the largest child so far, in KiB on Linux.
        "lane_peak_rss_bytes": peak_kib * 1024 if peak_kib > before else None,
    }


def _measure(label, manifest, files, allowlist, *, interface=None):
    from carbon.level4 import graph, submission, validate

    raw_manifest = submission.canonical(manifest)
    row = {
        "label": label,
        "manifest_bytes": len(raw_manifest),
        "documents": {},
        "submission_bytes": len(raw_manifest) + sum(len(b) for b in files.values()),
    }
    parsed = {}
    for slot, name in sorted(manifest["documents"].items()):
        if slot not in submission.SLOTS:  # init_spec is a spec, not a graph
            row["documents"][slot] = {"document_bytes": len(files[name])}
            continue
        doc, parse = _parse(files[name])
        parsed[slot] = doc
        started = time.perf_counter()
        validate.validate(doc, allowlist, caps={})
        row["documents"][slot] = {
            "document_bytes": len(files[name]),
            **parse,
            "validate_seconds": time.perf_counter() - started,
            **graph.measure(doc),
        }
        row["documents"][slot].pop("op_counts", None)
    row["g5"] = _lane(parsed, allowlist)
    return row


def _jax_cases(adapter):
    cases = {}
    for name in ("level0_strategies", "largest_strategies"):
        if hasattr(adapter, name):
            cases.update(getattr(adapter, name)())
    if hasattr(adapter, "level0_strategy"):
        cases["level0"] = adapter.level0_strategy()
    return cases


def _rows(adapter_name):
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import submission

    adapter = importlib.import_module(f"carbon.{adapter_name}.level4")
    allowlist = allowlist_module.load()
    rows = []
    for label, strategy in _jax_cases(adapter).items():
        try:
            manifest, files = adapter.lower_recipe(
                strategy, allowlist, max_bytes=MAX_BYTES
            )
        # A family this lowering does not cover (KNN, the PyTorch FNO) is
        # recorded, never measured here.
        except Exception as error:  # noqa: BLE001
            rows.append({"label": label, "not_lowered": type(error).__name__})
            continue
        rows.append(_measure(label, manifest, files, allowlist))
    if hasattr(adapter, "torch_cases"):
        from carbon.level4.tooling import lower_torch

        for label, strategy, _largest in adapter.torch_cases():
            if "fno" not in label:
                continue  # the MLP and DeepONet are measured through JAX above
            (params, net, _), _reference, f = adapter.torch_build(strategy)
            _raw, core = lower_torch.export(net, params, f)
            doc, _lowering = lower_torch.lower(core, allowlist=allowlist)
            manifest, files = submission.build(
                challenge=adapter.challenge_id(),
                interface="sha256:" + "0" * 64,  # size only; not admitted here
                allowlist=allowlist,
                forward=doc,
                init_spec=adapter.torch_init_spec(doc),
            )
            rows.append(_measure(label, manifest, files, allowlist))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", action="append", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    import jax

    started = time.perf_counter()
    report = {
        "schema": "carbon.development.level4-values-evidence.v1",
        "environment": {
            "machine": platform.machine(),
            "python": platform.python_version(),
            "jax": jax.__version__,
            "cpus": os.cpu_count(),
            "jax_platforms": os.environ.get("JAX_PLATFORMS"),
        },
        "adapters": {name: _rows(name) for name in args.adapter},
    }
    report["seconds"] = time.perf_counter() - started
    Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
