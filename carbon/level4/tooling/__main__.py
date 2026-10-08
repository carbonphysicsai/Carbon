"""Lower a Level 4 model into a submission, on the miner's own machine.

    python -m carbon.level4.tooling lower SPEC.py OUT_DIR \
        --challenge ID --interface sha256:... [--batch N]

`SPEC.py` is the miner's own module; this command runs it on the miner's
machine (the Launchpad's practice-side step), never on a Carbon host. It
defines:

* `FRAMEWORK`: "jax" or "torch";
* `INPUTS`: `{"inputs/<name>": (per-case shape tuple, dtype name)}`, the
  Challenge interface's inputs in order;
* JAX: `forward(params, *inputs)` and `init(key) -> params` (parameters
  only; Carbon supplies the key);
* PyTorch: `build() -> (params, apply)` with `apply(params, *inputs)`, and
  `INIT_SPEC`: one `{"initializer", "fan_in_axes", "fan_out_axes"}` per
  parameter (Carbon initializes PyTorch graphs itself, `initializers`).

It writes `OUT_DIR/manifest.json` and one `OUT_DIR/<hex>.json` per
document, all canonical bytes, and prints the submission digest. Carbon's
side reads them with `carbon.level4.submission.verify`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load(path):
    spec = importlib.util.spec_from_file_location("level4_submission_spec", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jax_documents(module, batch, allowlist, max_bytes):
    import jax

    from . import through_bprime

    key = jax.random.PRNGKey(0)
    example = jax.eval_shape(module.init, key)
    count = len(jax.tree_util.tree_leaves(example))
    inputs = [
        jax.ShapeDtypeStruct((batch, *shape), dtype)
        for shape, dtype in module.INPUTS.values()
    ]
    names = [f"params/{i}" for i in range(count)] + list(module.INPUTS)
    _, forward, _ = through_bprime(
        module.forward,
        (example, *inputs),
        role="forward",
        allowlist=allowlist,
        input_names=names,
        max_bytes=max_bytes,
    )
    _, init, _ = through_bprime(
        lambda k: jax.tree_util.tree_leaves(module.init(k)),
        (key,),
        role="init",
        allowlist=allowlist,
        input_names=["carbon/key"],
        max_bytes=max_bytes,
    )
    return {"forward": forward, "init": init}


def _torch_documents(module, batch, allowlist):
    import torch

    from .. import graph, initializers
    from . import lower_torch

    params, apply = module.build()
    examples = [
        torch.zeros((batch, *shape), dtype=getattr(torch, dtype))
        for shape, dtype in module.INPUTS.values()
    ]
    if len(examples) != 1:
        raise SystemExit("PyTorch lowering takes one input in this version")
    _, core = lower_torch.export(apply, params, examples[0])
    forward, _ = lower_torch.lower(core, allowlist=allowlist)
    entries = [
        {"input": f"params/{i}", **entry} for i, entry in enumerate(module.INIT_SPEC)
    ]
    spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(forward),
        "parameters": entries,
    }
    return {"forward": forward, "init_spec": spec}


def lower(spec_path, out_dir, *, challenge, interface, batch, max_bytes):
    from .. import allowlist as allowlist_module
    from .. import submission

    allowlist = allowlist_module.load()
    module = _load(spec_path)
    if module.FRAMEWORK == "jax":
        documents = _jax_documents(module, batch, allowlist, max_bytes)
    elif module.FRAMEWORK == "torch":
        documents = _torch_documents(module, batch, allowlist)
    else:
        raise SystemExit("FRAMEWORK must be 'jax' or 'torch'")
    manifest, files = submission.build(
        challenge=challenge, interface=interface, allowlist=allowlist, **documents
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_bytes(submission.canonical(manifest))
    for name, raw in files.items():
        (out / (name.split(":", 1)[1] + ".json")).write_bytes(raw)
    return submission.digest(manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.level4.tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    low = sub.add_parser("lower", help="lower a model spec into a Level 4 submission")
    low.add_argument("spec")
    low.add_argument("out")
    low.add_argument("--challenge", required=True)
    low.add_argument("--interface", required=True)
    low.add_argument("--batch", type=int, default=1)
    low.add_argument(
        "--max-bytes", type=int, default=1 << 30, help="this tool's own parse bound"
    )
    args = parser.parse_args(argv)
    digest = lower(
        args.spec,
        args.out,
        challenge=args.challenge,
        interface=args.interface,
        batch=args.batch,
        max_bytes=args.max_bytes,
    )
    print(json.dumps({"submission": digest, "out": args.out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
