#!/usr/bin/env python3
"""Per-case processes bench on a LOOP-BOUND graph (Motor 1.8's graded program; Lead's ask, Mon 16 Nov 2026).

A bench, never a grade: synthetic seeded parameters, Carbon's own graded inference program run locally (no container,
no ledger, no pack). It answers four questions for one graph whose per-row cost is dominated by a loop (the class of
rtsk_90112009, ~0.23 s a row, which meets the wall):

1. the graded pass's wall in ONE process (`case_procs.serial_program`, A9's program) and with per-case processes over
   the cores given (`--cores`, default every core of this process's cpuset), and the per-row time of each;
2. whether the two passes' answers are bit-identical (predictions.json, byte for byte);
3. whether Validator-2 F1's worst-case gate (`case_procs.case_procs_deadline`) let the workers start, with the values
   the program itself measured (startup, first call, sampled per-row time, deadline, wall end): read from a SEPARATE,
   clearly labelled copy of the program with one added stderr line, so the timed run is the exact graded bytes;
4. any fallback line (``case_procs: ...``) either run wrote.

The loop: ``jax.lax.scan`` with a static length (allowlist v8 op ``scan``: "static length; the body is a nested graph
run once per step"; ``while`` is refused: no unbounded loops), its body one dense layer and ``tanh`` on a
(batch, width) carry, between an input and an output dense layer. ``--graph dense`` gives the dense MLP instead (one
wide hidden layer), for comparison with Runner-B's 08:33 run.

Linux only (worker processes pin by affinity), from the repo venv with JAX:

    .venv/bin/python scripts/dev/case_procs_bench.py --tiny                      # seconds: a dry run of every step
    .venv/bin/python scripts/dev/case_procs_bench.py --row-seconds 0.23 --rows 400
    .venv/bin/python scripts/dev/case_procs_bench.py --row-seconds 0.23 --rows 2564  # Motor 1.8's bank size

``--row-seconds`` calibrates the scan length so ONE per-case call takes about that long in this process (measured on a
compiled call, then scaled). Every number here is a bench setting, never a registered value.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MOTOR_18 = ("electric-motor-magnetics", "1.8")
#: The gate report line the labelled copy adds (never in the timed run).
_GATE_ANCHOR = "        if deadline is None:\n            slices = []\n"
_GATE_REPORT = (
    '        print("case_procs_bench_gate: " + json.dumps({"startup": startup, "first": first, "per_row": per_row,'
    ' "sampled": len(sample), "rows": rows, "cores": len(cores), "slices": len(slices),'
    ' "now": time.monotonic() - case_start, "wall_end": case_wall_end - case_start,'
    ' "deadline": None if deadline is None else deadline - case_start}), file=sys.stderr)\n'
)


def _forward(kind, steps):
    import jax
    import jax.numpy as jnp

    if kind == "dense":

        def forward(w1, b1, w2, b2, w3, b3, x):
            return jnp.tanh(jnp.tanh(x @ w1 + b1) @ w2 + b2) @ w3 + b3

        return forward

    def forward(w1, b1, w2, b2, w3, b3, x):
        def step(carry, _):
            return jnp.tanh(carry @ w2 + b2), None

        carry, _ = jax.lax.scan(step, jnp.tanh(x @ w1 + b1), None, length=steps)
        return carry @ w3 + b3

    return forward


def _build(kind, steps, width, batch, seed):
    """The graph document, its recipe and a frozen v2 state (one member, seeded synthetic parameters)."""
    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.development_session import graph_adapters, physical_graph_state_v2
    from carbon.development_session import physical_graph_adapter_v2 as adapter
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import graph, initializers, intake, submission
    from carbon.level4.tooling import through_bprime

    spec = adapter.SPECS[MOTOR_18]
    allowed = allowlist_module.Allowlist(adapter.served_allowlist_bytes(*MOTOR_18))
    with jax.enable_x64(spec.dtype == "float64"):
        dtype = jnp.float64 if spec.dtype == "float64" else jnp.float32
        shapes = [
            (spec.inputs, width),
            (width,),
            (width, width),
            (width,),
            (width, spec.outputs),
            (spec.outputs,),
        ]
        _, document, _ = through_bprime(
            _forward(kind, steps),
            tuple(jnp.zeros(shape, dtype) for shape in shapes)
            + (jnp.ones((batch, spec.inputs), dtype),),
            role="forward",
            allowlist=allowed,
            input_names=[f"params/{i}" for i in range(len(shapes))]
            + [adapter.INPUT_NAME],
            max_bytes=intake.BOUNDS["document_bytes"],
        )
        init_spec = {
            "schema": initializers.SCHEMA,
            "graph": graph.digest(document),
            "parameters": [
                {
                    "input": f"params/{i}",
                    "initializer": "glorot_normal" if len(shape) == 2 else "zeros",
                    "fan_in_axes": [0] if len(shape) == 2 else [],
                    "fan_out_axes": [1] if len(shape) == 2 else [],
                }
                for i, shape in enumerate(shapes)
            ],
        }
        manifest, _files = submission.build(
            challenge=spec.challenge_id,
            interface=adapter.graph_interface(spec).digest(),
            allowlist=allowed,
            forward=document,
            init_spec=init_spec,
        )
        raw = graph_adapters.graph_recipe(*MOTOR_18, submission.digest(manifest))
        recipe = ConstructionRecipe.from_dict(raw)
        rng = np.random.default_rng(seed)
        np_dtype = np.dtype(spec.dtype)
        parameters = [
            (
                (rng.standard_normal(shape) / np.sqrt(shape[0])).astype(np_dtype)
                if len(shape) == 2
                else (rng.standard_normal(shape) * 0.1).astype(np_dtype)
            )
            for shape in shapes
        ]
        state = physical_graph_state_v2.freeze(
            recipe,
            document,
            [parameters],
            allowed,
            np.zeros(spec.outputs, np_dtype),
            np.ones(spec.outputs, np_dtype),
            np.ones((1, spec.outputs), np_dtype),
        )
    return document, recipe, state, allowed, parameters, spec


def _one_call_seconds(document, allowed, parameters, spec, batch, repeats=3):
    """One compiled per-case call's seconds, in this process (the calibration of `--row-seconds`)."""
    import jax
    import jax.numpy as jnp
    import numpy as np

    from carbon.level4 import interpret

    with jax.enable_x64(spec.dtype == "float64"):
        fn = jax.jit(interpret.rebuild(document, allowed))
        args = [jnp.asarray(p) for p in parameters] + [
            jnp.zeros((batch, spec.inputs), np.dtype(spec.dtype))
        ]
        jax.block_until_ready(fn(*args))
        best = float("inf")
        for _ in range(repeats):
            started = time.perf_counter()
            jax.block_until_ready(fn(*args))
            best = min(best, time.perf_counter() - started)
    return best


def _rows(count):
    import numpy as np

    from carbon.challenge_kit import physical_material

    base = np.asarray(physical_material.bundle_material(*MOTOR_18)["practice_inputs"])
    rows = np.concatenate(
        [base * (1.0 + 0.004 * k) for k in range(-(-count // len(base)))]
    )
    return np.ascontiguousarray(rows[:count], dtype=base.dtype)


def _runner(root, cores, change, log):
    """Carbon's program run as the carrier runs it: an isolated interpreter over a program FILE (so the workers can
    re-run it), inside the given cpuset; ``change`` edits the program text (the labelled gate copy only).
    """
    count = itertools.count()

    def pin():
        os.sched_setaffinity(0, cores)

    def run(_ledger, *, source, files, output_validator, **_kw):
        name = f"operation-{next(count):064x}"
        home = root / name
        work = home / "workspace"
        work.mkdir(parents=True)
        (home / "output").mkdir()
        for filename, body in files.items():
            (work / filename).write_bytes(body)
        program = home / "program.py"
        program.write_text(change(source), encoding="utf-8")
        started = time.perf_counter()
        done = subprocess.run(
            [sys.executable, "-I", str(program)],
            cwd=work,
            env={**os.environ, "JAX_PLATFORMS": "cpu"},
            capture_output=True,
            text=True,
            check=False,
            preexec_fn=pin,
        )
        log.append(
            {
                "seconds": time.perf_counter() - started,
                "code": done.returncode,
                "stderr": done.stderr,
            }
        )
        if done.returncode != 0:
            raise RuntimeError(
                f"program exit {done.returncode}:\n{done.stderr[-4000:]}"
            )
        snapshot = home / "snapshot"
        (home / "output").rename(snapshot)
        output_validator(snapshot)
        return {
            "operation": name,
            "files": {
                path.name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                for path in snapshot.iterdir()
            },
        }

    return run


def _pass(label, query, contract, cores, change, root):
    """One graded pass through `_infer_state` (Carbon's own staging and output checks): (seconds, predictions bytes,
    stderr)."""
    from carbon.development_session.bundle_construction_worker import _infer_state

    log = []
    ledger_root = root / label
    ledger_root.mkdir()
    result = _infer_state(
        SimpleNamespace(root=ledger_root),
        owner="bench-owner",
        identity="bench-" + label,
        runner=_runner(ledger_root, cores, change, log),
        **query,
        **contract,
    )
    from carbon.development_session.data import read_raw

    raw = read_raw(
        ledger_root / result.worker_operation / "snapshot" / "predictions.json"
    )
    return log[-1]["seconds"], raw, log[-1]["stderr"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--graph", choices=("loop", "dense"), default="loop")
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--steps", type=int, default=20000, help="scan length")
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--batch", type=int, default=8, help="declared batch")
    parser.add_argument(
        "--row-seconds",
        type=float,
        default=None,
        help="calibrate the scan length to about this many seconds per per-case call",
    )
    parser.add_argument("--cores", type=int, default=None, help="cpuset size")
    parser.add_argument("--seed", type=int, default=18)
    parser.add_argument("--tiny", action="store_true", help="fast dry run")
    parser.add_argument("--keep", action="store_true", help="keep the work folder")
    args = parser.parse_args(argv)
    if args.tiny:
        args.rows, args.steps, args.width, args.row_seconds = 24, 64, 8, None
    if not hasattr(os, "sched_getaffinity"):
        print("Linux only: worker processes pin by affinity", file=sys.stderr)
        return 2

    from carbon.challenge_kit import physical_material
    from carbon.development_session import case_procs
    from carbon.development_session.direct_graph_construction_worker import (
        registered_inference_contract,
    )

    available = sorted(os.sched_getaffinity(0))
    cores = set(available[: args.cores or len(available)])
    steps = args.steps
    document, recipe, state, allowed, parameters, spec = _build(
        args.graph, steps, args.width, args.batch, args.seed
    )
    call = _one_call_seconds(document, allowed, parameters, spec, args.batch)
    if args.row_seconds and args.graph == "loop":
        steps = max(1, round(steps * args.row_seconds / call))
        document, recipe, state, allowed, parameters, spec = _build(
            args.graph, steps, args.width, args.batch, args.seed
        )
        call = _one_call_seconds(document, allowed, parameters, spec, args.batch)
    material = physical_material.bundle_material(*MOTOR_18)
    limits = material["construction_limits_document"]
    kit = material["construction_kit"]
    binding = {
        "challenge_id": MOTOR_18[0],
        "challenge_version": MOTOR_18[1],
        **{
            field: kit[field]
            for field in (
                "train_digest",
                "interface_digest",
                "construction_limits_digest",
            )
        },
    }
    _loader, contract, dtype = registered_inference_contract(
        binding, limits, recipe=recipe
    )
    procs = contract["program"]
    serial = case_procs.serial_program(procs)
    inputs = _rows(args.rows)
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    query = {
        "inference_image": WorkerImageIdentity(*(("sha256:" + "a" * 64,) * 8)),
        "recipe": recipe,
        "binding": binding,
        "state": state,
        "state_digest": "sha256:" + hashlib.sha256(state).hexdigest(),
        "inputs": inputs,
        "expected_output_shape": (len(inputs), spec.outputs),
        "expected_output_dtype": dtype,
        "allowlist_bytes": material["allowlist_bytes"],
        "seconds": limits["reconstruction_resource_policy"][
            "inference_wall_seconds_max"
        ],
    }
    if procs.count(_GATE_ANCHOR) != 1:
        raise SystemExit("gate anchor moved: update the bench")
    work = Path(tempfile.mkdtemp(prefix="case-procs-bench-"))
    try:
        one_s, one_raw, one_err = _pass(
            "one-process", query, contract, cores, case_procs.serial_program, work
        )
        procs_s, procs_raw, procs_err = _pass(
            "procs", query, contract, cores, lambda source: source, work
        )
        _s, gate_raw, gate_err = _pass(
            "gate-report",
            query,
            contract,
            cores,
            lambda source: source.replace(_GATE_ANCHOR, _GATE_REPORT + _GATE_ANCHOR),
            work,
        )
    finally:
        if not args.keep:
            import shutil

            shutil.rmtree(work, ignore_errors=True)
    gate = [
        json.loads(line.split("case_procs_bench_gate: ", 1)[1])
        for line in gate_err.splitlines()
        if line.startswith("case_procs_bench_gate: ")
    ]
    report = {
        "graph": args.graph,
        "loop_op": "scan (static length)" if args.graph == "loop" else None,
        "scan_length": steps if args.graph == "loop" else None,
        "width": args.width,
        "declared_batch": args.batch,
        "rows": len(inputs),
        "cores": len(cores),
        "one_compiled_call_seconds_in_process": call,
        "one_process": {
            "program_sha256": "sha256:" + hashlib.sha256(serial.encode()).hexdigest(),
            "wall_seconds": one_s,
            "per_row_seconds": one_s / len(inputs),
        },
        "per_case_processes": {
            "program_sha256": "sha256:" + hashlib.sha256(procs.encode()).hexdigest(),
            "wall_seconds": procs_s,
            "per_row_seconds": procs_s / len(inputs),
            "speedup": one_s / procs_s if procs_s else None,
        },
        "bit_identical": one_raw == procs_raw == gate_raw,
        "f1_gate": (
            gate[0]
            if gate
            else "no gate line: the process count was 1 (cores, memory or pids bound), so no worker was planned"
        ),
        "f1_gate_allowed_workers": bool(gate) and gate[0]["deadline"] is not None,
        "fallback_lines": {
            "one_process": [x for x in one_err.splitlines() if "case_procs:" in x],
            "per_case_processes": [
                x for x in procs_err.splitlines() if "case_procs:" in x
            ],
        },
        "note": "bench only: synthetic seeded parameters, local run (no container); not a grade, science or qualification",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["bit_identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
