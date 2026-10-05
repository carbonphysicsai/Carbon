"""B10: does a Level-1 loss rebuild bit for bit, and how long does it take?

GRAPHITE-L1-BUILD-01, Test Lead Q1. The shipped code end to end: random
expressions over battery's full valid operation set (`carbon.battery.level1`)
at a node limit, compiled, staged as canonical bytes, recompiled with
`loss_terms.load` and trained by Carbon's Level-1 trainer
(`level1_training.build`) on public TRAIN v1, in a fresh process. Two fresh processes must
give the same parameter digest. The fit's seconds are compared with the
practice worker's deadline.

CPU only (`JAX_PLATFORMS=cpu`). It enables nothing: 1024 nodes is measured
for a later version, the registered limit stays 512.

    python scripts/dev/l1_rebuild_measure.py run OUT.json [--nodes 512 1024]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")
REPOSITORY = Path(__file__).resolve().parents[2]
SEED = 20261005
#: The practice worker's deadline, in seconds (battery's PRACTICE_SECONDS).
DEADLINE = 600


def operation_set(nodes):
    from carbon.battery import level1

    full = level1.operation_set({level1.CORE, *level1.FAMILIES})
    return dataclasses.replace(full, max_nodes=nodes, max_depth=level1.MAX_DEPTH)


def _constant(rng, low, high):
    pick = rng.random()
    if pick < 0.15:
        return float(low)
    if pick < 0.3:
        return float(high)
    return float(rng.uniform(low, high))


def generate(rng, opset, sort, depth, budget):
    """A random well-sorted expression of at most `budget` nodes."""
    from carbon.reconstruction import loss_expressions as le

    names = opset.terms if sort == le.CASE else opset.time_terms
    if depth >= opset.max_depth - 1 or budget <= 1:
        return {"term": rng.choice(names)}, 1
    choices = [o for o in opset.operations if o != "const"]
    if sort == le.TIME:
        choices = [o for o in choices if o not in ("mean_t", "max_t")]
    branching = ("add", "max", "min", "mul", "div", "sub")
    unary = [o for o in choices if o not in branching]
    if budget == 2 or (unary and rng.random() < 0.3):
        choices = unary
    else:
        choices = [o for o in choices if o in branching]
    op = rng.choice(choices)
    if op in branching:
        # The children's budgets sum to this node's, so the tree uses the
        # whole budget (up to the depth limit).
        n = (
            2
            if op in ("mul", "div", "sub")
            else rng.randint(2, min(opset.max_arity, budget - 1))
        )
        cuts = sorted(rng.sample(range(1, budget - 1), n - 1))
        parts = [b - a for a, b in zip([0, *cuts], [*cuts, budget - 1])]
        args, used = [], 1
        for part in parts:
            arg, count = generate(rng, opset, sort, depth + 1, part)
            args.append(arg)
            used += count
        return {"op": op, "args": args}, used
    if op in ("mean_t", "max_t"):
        arg, count = generate(rng, opset, le.TIME, depth + 1, budget - 1)
        return {"op": op, "over": rng.choice(sorted(le.OVER)), "arg": arg}, count + 1
    arg, count = generate(rng, opset, sort, depth + 1, budget - 1)
    if op in ("log1p", "sqrt", "neg", "exp"):
        return {"op": op, "arg": arg}, count + 1
    field, bounds = {
        "scale": ("by", opset.scale),
        "pow": ("exponent", opset.exponent),
        "cap": ("at", opset.cap_at),
        "excess": ("over", opset.excess_over),
        "expm1": ("cap", opset.expm1_cap),
    }[op]
    return {"op": op, field: _constant(rng, *bounds), "arg": arg}, count + 1


def sample(nodes, count, seed):
    """`count` compiled expressions using at least 85 % of the node limit."""
    from carbon.reconstruction import loss_expressions as le

    opset = operation_set(nodes)
    rng = random.Random(seed)
    found = []
    while len(found) < count:
        tree, used = generate(rng, opset, le.CASE, 1, nodes)
        if used < 0.85 * nodes:
            continue
        try:
            found.append(le.compile_expression(tree, opset))
        except le.ExpressionRefused:
            continue
    return found


def fit(nodes, index, steps):
    """One fresh-process fit: the parameter digest and the seconds."""
    import numpy as np

    from carbon.battery import level1_training, loss_terms, recipes
    from carbon.battery.challenge import PublicMaterial
    from carbon.battery.compile import compile_recipe
    from carbon.battery.research import SCAFFOLD
    from carbon.reconstruction import loss_expressions as le

    compiled = sample(nodes, index + 1, SEED + nodes)[index]
    # The worker's path: canonical bytes and the set's document, recompiled.
    rebuilt = loss_terms.load(
        le, compiled.canonical_bytes(), compiled.operation_set.document()
    )
    strategy = json.loads(json.dumps(SCAFFOLD))
    strategy["parameters"]["steps"] = steps
    _, recipe = compile_recipe(strategy)
    material = PublicMaterial.load(REPOSITORY)
    model = level1_training.build(
        recipe.family, recipe.settings, loss_terms.factory(le, rebuilt)
    )
    started = time.perf_counter()
    stats = model.fit(
        material.train,
        recipes.Structure(np.asarray(material.ocv_soc), np.asarray(material.ocv_v)),
        7,
    )
    return {
        "nodes": sum(1 for _ in le.walk(rebuilt.expression)),
        "params_sha256": stats["params_sha256"],
        "final_loss": stats["final_loss"],
        "seconds": round(time.perf_counter() - started, 2),
        "steps": steps,
    }


def _fresh(nodes, index, steps):
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "fit",
        str(nodes),
        str(index),
        str(steps),
    ]
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "JAX_PLATFORMS": "cpu",
        "CUDA_VISIBLE_DEVICES": "",
        "PYTHONPATH": str(REPOSITORY),
    }
    done = subprocess.run(
        command, env=environment, capture_output=True, text=True, check=True
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def run(path, sizes, per_size, identity_steps, timing_steps):
    report = {
        "schema": "carbon.battery.level1-rebuild-measurement.v1",
        "platform": "cpu",
        "deadline_seconds": DEADLINE,
        "identity_steps": identity_steps,
        "timing_steps": timing_steps,
        "sizes": {},
    }
    for nodes in sizes:
        rows = []
        for index in range(per_size):
            first = _fresh(nodes, index, identity_steps)
            second = _fresh(nodes, index, identity_steps)
            rows.append(
                {
                    "nodes": first["nodes"],
                    "identical": first["params_sha256"] == second["params_sha256"],
                    "seconds": [first["seconds"], second["seconds"]],
                    "final_loss": first["final_loss"],
                }
            )
        timed = _fresh(nodes, 0, timing_steps)
        report["sizes"][str(nodes)] = {
            "identity": rows,
            "all_identical": all(r["identical"] for r in rows),
            "timing": timed,
            "inside_deadline": timed["seconds"] < DEADLINE,
        }
        print(nodes, report["sizes"][str(nodes)]["all_identical"], timed["seconds"])
    Path(path).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    go = sub.add_parser("run")
    go.add_argument("out")
    go.add_argument("--nodes", type=int, nargs="+", default=[512, 1024])
    go.add_argument("--per-size", type=int, default=3)
    go.add_argument("--identity-steps", type=int, default=64)
    go.add_argument("--timing-steps", type=int, default=2000)
    one = sub.add_parser("fit")
    one.add_argument("nodes", type=int)
    one.add_argument("index", type=int)
    one.add_argument("steps", type=int)
    args = parser.parse_args(argv)
    if args.command == "fit":
        print(json.dumps(fit(args.nodes, args.index, args.steps)))
        return 0
    run(args.out, args.nodes, args.per_size, args.identity_steps, args.timing_steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
