"""Level 4 Phase 0 spike runner (CPU only, development only).

Runs every Phase 0 deliverable for one Challenge adapter and writes one JSON
record: primitive and Core ATen inventories, allowlist coverage, D6
measurements, serialization probes, the B' equivalence check, the PyTorch B'
path and the refusal specimens.

    python scripts/dev/level4_spike/run.py OUT.json --adapter NAME [--steps N]

`--steps` shortens every equivalence fit (tests use it); the recorded run
uses each recipe's own steps. `--max-bytes` bounds the spike's own parser and
is not a G3 limit (that stays HUMAN_INPUT).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
import time
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
REPOSITORY = Path(__file__).resolve().parents[3]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

SCHEMA = "carbon.development.level4-phase0-results.v0"
#: The Phase 0 record was made with allowlist v0.
PATH_V0 = REPOSITORY / "docs/development/graphite/level4/allowlist_v0.json"


def environment():
    import jax
    import jaxlib

    out = {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "jax": jax.__version__,
        "jaxlib": jaxlib.__version__,
        "jax_platforms": os.environ.get("JAX_PLATFORMS"),
    }
    try:
        import neuralop
        import torch

        out.update(torch=torch.__version__, neuraloperator=neuralop.__version__)
    except ImportError:
        out.update(torch=None, neuraloperator=None)
    return out


def jax_section(adapter, allowlist):
    import jax

    from carbon.level4 import graph, interpret
    from carbon.level4.tooling import lower_jax
    from level4_spike import probes

    rows, union = [], {}
    first_forward = None
    for label, role, fn, args, names, extra in adapter.jax_cases():
        with jax.enable_x64(extra.get("x64", False)):
            closed = lower_jax.trace(fn, *args)
            row = {
                "label": label,
                "role": role,
                "inventory": lower_jax.inventory(closed),
            }
            if role != "carbon_train_step":
                for name, count in row["inventory"]["primitives"].items():
                    union.setdefault(name, {}).setdefault(role, 0)
                    union[name][role] += count
                doc = lower_jax.lower(
                    closed, role=role, allowlist=allowlist, input_names=names
                )
                row["graph"] = graph.measure(doc)
                if role == "forward" and first_forward is None:
                    first_forward = (fn, args)
            if extra.get("largest") or role == "carbon_train_step":
                row["compile_native"] = probes.compile_measure(fn, args)
                if role == "forward":
                    rebuilt = interpret.rebuild(doc, allowlist)
                    flat = jax.tree_util.tree_leaves(args)
                    row["compile_bprime"] = probes.compile_measure(
                        lambda *a, _r=rebuilt: _r(*a), flat
                    )
        rows.append(row)
    classified = {
        name: {
            "roles": roles,
            "allowlist": allowlist.ops.get(name, {}).get("default", "unlisted"),
            "category": allowlist.ops.get(name, {}).get("category"),
        }
        for name, roles in sorted(union.items())
    }
    return rows, classified, first_forward


def torch_section(adapter, allowlist, max_bytes, *, include_largest=True):
    import jax
    import jax.numpy as jnp
    import numpy as np
    import torch

    from carbon.level4 import graph, interpret
    from carbon.level4.tooling import lower_torch
    from level4_spike import probes

    rows, union, serialization = [], {}, None
    for label, strategy, largest in adapter.torch_cases():
        if largest and not include_largest:
            continue
        (params, net, _), (rparams, rnet, _), f = adapter.torch_build(strategy)
        started = time.perf_counter()
        raw_program, core = lower_torch.export(net, params, f)
        export_seconds = time.perf_counter() - started
        row = {
            "label": label,
            "export_seconds": round(export_seconds, 3),
            "raw_inventory": lower_torch.inventory(raw_program),
            "core_inventory": lower_torch.inventory(core),
            "parameter_bytes": int(sum(p.numel() * p.element_size() for p in params)),
        }
        for name, count in row["core_inventory"].items():
            union[name] = union.get(name, 0) + count
        doc, lowering = lower_torch.lower(core, allowlist=allowlist)
        doc = graph.parse(graph.dumps(doc), max_bytes=max_bytes)
        row["graph"] = graph.measure(doc)
        row["lowering"] = lowering
        rebuilt = interpret.rebuild(doc, allowlist)
        jp = [jnp.asarray(p.detach().numpy()) for p in rparams]
        jf = jnp.asarray(f.numpy())
        out_j = np.asarray(jax.jit(lambda *a, _r=rebuilt: _r(*a)[0])(*jp, jf))
        with torch.no_grad():
            out_t = rnet(rparams, f).detach().as_subclass(torch.Tensor).numpy()
        tp = [p.detach().clone().requires_grad_(True) for p in rparams]
        (rnet(tp, f) ** 2).mean().backward()
        grad_t = [p.grad.as_subclass(torch.Tensor).numpy() for p in tp]
        grad_j = jax.jit(
            jax.grad(lambda ps, _r=rebuilt, _f=jf: jnp.mean(_r(*ps, _f)[0] ** 2))
        )(jp)
        row["bprime_vs_torch"] = {
            "forward_max_abs_difference": float(np.max(np.abs(out_j - out_t))),
            "forward_max_abs_value": float(np.max(np.abs(out_t))),
            "gradient_max_relative_difference": max(
                float(np.max(np.abs(np.asarray(a) - b)) / (np.max(np.abs(b)) + 1e-30))
                for a, b in zip(grad_j, grad_t)
            ),
            "bit_identical": bool(np.array_equal(out_j, out_t)),
        }
        if largest:
            row["compile_bprime"] = probes.compile_measure(
                lambda *a, _r=rebuilt: _r(*a), [*jp, jf]
            )
        if serialization is None:
            serialization = probes.torch_export_probe(core)
        rows.append(row)
        del params, rparams, net, rnet, core, raw_program, rebuilt, jp
    classified = {
        name: {
            "count": count,
            "allowlist": allowlist.aten.get(name, {}).get("default", "unlisted"),
            "lowering": allowlist.aten.get(name, {}).get("lowering"),
        }
        for name, count in sorted(union.items())
    }
    return rows, classified, serialization


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--max-bytes", type=int, default=1 << 30)
    parser.add_argument("--skip-torch", action="store_true")
    args = parser.parse_args(argv)

    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import specimens
    from level4_spike import probes

    adapter = importlib.import_module(f"carbon.{args.adapter}.level4")
    allowlist = allowlist_module.load(PATH_V0)  # the Phase 0 record
    started = time.perf_counter()
    record = {
        "schema": SCHEMA,
        "status": "DEVELOPMENT SPIKE. CPU only. No caps chosen; every cap is HUMAN_INPUT.",
        "adapter": args.adapter,
        "environment": environment(),
        "allowlist": {"version": allowlist.version, "digest": allowlist.digest},
        "caps": allowlist_module.CAPS,
    }
    rows, classified, first_forward = jax_section(adapter, allowlist)
    record["jax"] = {"graphs": rows, "primitive_union": classified}
    record["serialization"] = {"jax_export": probes.jax_export_probe(*first_forward)}
    if not args.skip_torch:
        rows, aten, torch_probe = torch_section(adapter, allowlist, args.max_bytes)
        record["torch"] = {"programs": rows, "core_aten_union": aten}
        record["serialization"]["torch_export"] = torch_probe
    record["equivalence"] = adapter.equivalence(
        allowlist, steps=args.steps, max_bytes=args.max_bytes
    )
    record["specimens"] = {
        "programs": specimens.run_programs(allowlist),
        "documents": specimens.run_documents(allowlist, args.max_bytes),
        "constants": specimens.run_constants(allowlist),
    }
    record["seconds"] = round(time.perf_counter() - started, 1)
    Path(args.out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"out": args.out, "seconds": record["seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
