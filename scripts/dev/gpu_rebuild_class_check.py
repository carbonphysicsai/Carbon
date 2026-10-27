#!/usr/bin/env python3
"""Does a GPU rebuild of the graph route repeat itself bit for bit, and how far is it from CPU?

The first evidence the GPU rebuild path needs (Validator GPU_REBUILD_RULINGS_20261026, rule 1:
"a GPU entry is offered only if two independent official rebuilds give a bit-identical
parameters-only state hash; otherwise it rebuilds on CPU"; owner parity tolerance 0.01).

For each launch Challenge's graph-route version (F08 1.5, F02 2.4, Motor 1.4, Cooling 1.4) it
rebuilds four fixed graphs (dense+tanh, layer norm+gelu+sigmoid gate, 1-d convolutions,
softmax gating: the op families miners' graphs use) from the version's own TRAIN, each in a
FRESH process each time
(as the isolated worker does), under Carbon's pinned determinism flags
(`carbon.reconstruction.accelerators.GPU_DETERMINISM_XLA_FLAGS` / `GPU_DETERMINISM_ENVIRONMENT`),
and compares the sha256 of the frozen parameters-only state (`model.frozen_state()`, the same
bytes the worker's build program writes as `state.npz`). One further rebuild on the CPU gives the
GPU-versus-CPU prediction difference. A small torch probe (conv + spectral layer, the pinned
torch settings) says whether the torch lane can repeat. It prints one JSON class record
(GPU, driver, library versions, flags, per-case digests and verdicts) and writes it to `--out`.
`--ops-record` also writes the `carbon.graph-gpu-ops.v1` record the validator's graph GPU lane
reads (`carbon.development_session.graph_gpu_lane`): the ops of every graph that repeated on the
GPU and of none that did not.

Needs a Carbon checkout with its dev environment, and for a real class check an NVIDIA machine
with a CUDA-enabled jaxlib (and torch) - the jax-cuda13 worker image or an environment from
`.devcontainer/accelerators/cuda13-py311.txt`. It reads no private data, uses no network and
starts nothing but its own child Python processes.

    python scripts/dev/gpu_rebuild_class_check.py --out class-check.json          # on the GPU host
    python scripts/dev/gpu_rebuild_class_check.py --device cpu --keys f08 --steps 8   # dry run

Exit code 0 when every case rebuilt bit-identically (and, without `--device cpu`, ran on a
GPU), 1 otherwise; the JSON still lists each case.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "carbon.gpu-rebuild.class-check.v1"

#: The four launch graph-route versions: short name -> (challenge id, version).
KEYS = {
    "f08": ("f08-ribbed-bracket", "1.5"),
    "f02": ("f02", "2.4"),
    "motor": ("electric-motor-magnetics", "1.4"),
    "cooling": ("chip-cold-plate", "1.4"),
}
#: Predictions compared between GPU and CPU: the first TRAIN rows.
PARITY_ROWS = 64


def _pinned_environment() -> dict[str, str]:
    """The environment of a GPU rebuild, from `accelerators.pinned_environment` and nowhere else:
    explicit `JAX_PLATFORMS`, the allocator, the determinism flags, cuBLAS and TF32. Nothing here
    relies on what the image or the caller exports."""
    sys.path.insert(0, str(ROOT))
    from carbon.reconstruction.accelerators import GPU_PROFILE, pinned_environment

    return pinned_environment(GPU_PROFILE)


def _sha(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


# ---- the child: one fresh rebuild ------------------------------------------------------


#: The fixed graphs the check rebuilds, each exercising a family of ops a miner's graph uses:
#: dense + tanh, layer norm + erf-gelu + sigmoid gate, 1-d convolutions, softmax gating.
ARCHITECTURES = ("mlp", "norm", "conv", "softmax")
WIDTH = 16
CHANNELS = 4
KERNEL = 3


def _architecture(name, inputs, outputs):
    """`(forward, parameters)` of one fixed graph: parameters are
    ``(shape, initializer, fan_in_axes, fan_out_axes)``; the forward takes them in order, then x.
    """
    import jax
    import jax.numpy as jnp
    from jax import lax

    glorot, zeros = "glorot_normal", "zeros"
    dense = ([0], [1])
    none = ([], [])
    if name == "mlp":
        parameters = [
            ((inputs, WIDTH), glorot, *dense),
            ((WIDTH,), zeros, *none),
            ((WIDTH, outputs), glorot, *dense),
            ((outputs,), zeros, *none),
        ]

        def forward(w1, b1, w2, b2, x):
            return jnp.tanh(x @ w1 + b1) @ w2 + b2

    elif name == "norm":
        parameters = [
            ((inputs, WIDTH), glorot, *dense),
            ((WIDTH,), zeros, *none),
            ((WIDTH,), zeros, *none),
            ((WIDTH,), zeros, *none),
            ((WIDTH, outputs), glorot, *dense),
            ((outputs,), zeros, *none),
            ((WIDTH, outputs), glorot, *dense),
        ]

        def forward(w1, b1, g, be, w2, b2, w3, x):
            h = x @ w1 + b1
            m = jnp.mean(h, axis=-1, keepdims=True)
            v = jnp.mean((h - m) ** 2, axis=-1, keepdims=True)
            h = (h - m) * lax.rsqrt(v + 1e-5) * (1.0 + g) + be
            h = jax.nn.gelu(h, approximate=False)
            return (h @ w2 + b2) * jax.nn.sigmoid(h @ w3)

    elif name == "conv":
        parameters = [
            ((CHANNELS, 1, KERNEL), glorot, [1, 2], [0]),
            ((CHANNELS, CHANNELS, KERNEL), glorot, [1, 2], [0]),
            ((CHANNELS * inputs, outputs), glorot, *dense),
            ((outputs,), zeros, *none),
        ]

        def forward(k1, k2, w, b, x):
            def conv(z, k):
                return lax.conv_general_dilated(
                    z, k, (1,), "SAME", dimension_numbers=("NCH", "OIH", "NCH")
                )

            z = jnp.maximum(conv(x[:, None, :], k1), 0.0)
            z = jnp.tanh(conv(z, k2))
            return z.reshape(z.shape[0], -1) @ w + b

    elif name == "softmax":
        parameters = [
            ((inputs, WIDTH), glorot, *dense),
            ((WIDTH,), zeros, *none),
            ((WIDTH, WIDTH), glorot, *dense),
            ((WIDTH, outputs), glorot, *dense),
            ((outputs,), zeros, *none),
        ]

        def forward(w1, b1, wq, w2, b2, x):
            h = jnp.tanh(x @ w1 + b1)
            p = jax.nn.softmax(h @ wq, axis=-1)
            return (p * h) @ w2 + b2

    else:
        raise ValueError("unknown architecture")
    return forward, parameters


def _case(route, key, name, steps):
    """`(recipe, raw manifest, files, staging)` of architecture `name` on the version `key`."""
    import jax.numpy as jnp

    from carbon.level4 import graph, initializers, intake, staging, submission
    from carbon.level4.tooling import through_bprime

    spec = route.adapter.SPECS[key]
    dtype = jnp.float64 if spec.dtype == "float64" else jnp.float32
    configuration = {"training": {"steps": steps}}
    batch = configuration["training"].get("batch_size", 8)
    allowed = route.allowlist_module.Allowlist(
        route.adapter.served_allowlist_bytes(*key)
    )
    forward, parameters = _architecture(name, spec.inputs, spec.outputs)
    _, document, _ = through_bprime(
        forward,
        (
            *[jnp.zeros(shape, dtype) for shape, *_ in parameters],
            jnp.ones((batch, spec.inputs), dtype),
        ),
        role="forward",
        allowlist=allowed,
        input_names=[f"params/{i}" for i in range(len(parameters))]
        + [route.adapter.INPUT_NAME],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(document),
        "parameters": [
            {
                "input": f"params/{i}",
                "initializer": initializer,
                "fan_in_axes": fan_in,
                "fan_out_axes": fan_out,
            }
            for i, (_shape, initializer, fan_in, fan_out) in enumerate(parameters)
        ],
    }
    manifest, files = submission.build(
        challenge=spec.challenge_id,
        interface=route.adapter.graph_interface(spec).digest(),
        allowlist=allowed,
        forward=document,
        init_spec=init_spec,
    )
    raw_manifest = submission.canonical(manifest)
    recipe = route._recipe(key, configuration, digest=submission.digest(manifest))
    return recipe, raw_manifest, files, staging


def _route():
    """What a rebuild needs from the repository, with no test framework: the v2 adapter, the
    allowlist module, a recipe builder, TRAIN, and the 64-bit context an interface may need.
    """
    import contextlib
    import io
    from types import SimpleNamespace

    import numpy as np

    sys.path.insert(0, str(ROOT))
    from carbon.challenge_kit import physical_material
    from carbon.development_session import graph_adapters
    from carbon.development_session import physical_graph_adapter_v2 as adapter
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.level4 import allowlist as allowlist_module

    def x64(key):
        if adapter.SPECS[key].dtype != "float64":
            return contextlib.nullcontext()
        import jax

        return jax.enable_x64(True)

    def recipe(key, configuration, *, digest):
        value = graph_adapters.graph_recipe(*key, digest, configuration=configuration)
        value["procedure"]["train_use"]["train_fraction"] = 1.0
        return ConstructionRecipe.from_dict(value)

    def train(key):
        raw = physical_material.bundle_material(*key)["train"]
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            return raw, archive["inputs"].copy(), archive["targets"].copy()

    return SimpleNamespace(
        adapter=adapter,
        allowlist_module=allowlist_module,
        _x64=x64,
        _recipe=recipe,
        _train=train,
    )


def _graph_child(args) -> dict:
    """One rebuild in this process: fit a fixed graph, hash the frozen state."""
    import numpy as np

    # A graph is lowered under JAX's default precision (a lowered matmul or convolution must carry
    # the default `precision` parameter); the worker's "highest" is set once it is built, as the
    # worker applies it to a graph it rebuilds.
    precision = os.environ.pop("JAX_DEFAULT_MATMUL_PRECISION", None)
    route = _route()
    from carbon.development_session import graph_gpu_lane
    from carbon.development_session.profile import canonical

    key = KEYS[args.key]
    import jax

    # A GPU lane that is not on the GPU is a typed refusal, never a CPU result under a GPU name.
    if os.environ.get("JAX_PLATFORMS") == "cuda":
        try:
            backend = jax.default_backend()
        except Exception:  # noqa: BLE001 - no CUDA backend at all is the same refusal
            backend = "unavailable"
        if backend != "gpu":
            print(json.dumps({"error": "backend_not_gpu", "backend": backend}))
            raise SystemExit(3)
    started = time.monotonic()
    with route._x64(key):
        recipe, raw_manifest, files, staging = _case(route, key, args.arch, args.steps)
        ops = sorted(
            graph_gpu_lane.submission_ops(
                canonical(staging.envelope(raw_manifest, files))
            )
            or ()
        )
        if precision is not None:
            jax.config.update("jax_default_matmul_precision", precision)
        _raw, inputs, targets = route._train(key)
        model = route.adapter.build_validated_graph(
            recipe,
            raw_manifest,
            files,
            allowlist_bytes=route.adapter.served_allowlist_bytes(*key),
            train_cases=route.adapter.SPECS[key].rows,
        )
        fit = model.fit(inputs, targets, seed=args.seed)
        state = model.frozen_state()
        predictions = np.asarray(model.predict(inputs[:PARITY_ROWS], isolated=True))
    np.save(args.predictions, predictions)
    return {
        "state_digest": _sha(state),
        "state_bytes": len(state),
        "predictions_digest": _sha(predictions.tobytes()),
        "backend": jax.default_backend(),
        "device": str(jax.devices()[0]),
        "seconds": round(time.monotonic() - started, 3),
        "fit_keys": sorted(fit) if isinstance(fit, dict) else None,
        "ops": ops,
    }


def _torch_child(args) -> dict:
    """One torch rebuild: a conv + spectral layer net, the pinned torch settings."""
    import numpy as np
    import torch

    sys.path.insert(0, str(ROOT))
    from carbon.reconstruction.accelerators import GPU_DETERMINISM_TORCH

    for name, value in GPU_DETERMINISM_TORCH:
        if name == "use_deterministic_algorithms":
            torch.use_deterministic_algorithms(value)
        elif name == "cudnn_deterministic":
            torch.backends.cudnn.deterministic = value
        elif name == "cudnn_benchmark":
            torch.backends.cudnn.benchmark = value
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if os.environ.get("JAX_PLATFORMS") == "cuda" and device != "cuda":
        print(json.dumps({"error": "backend_not_gpu", "backend": device}))
        raise SystemExit(3)
    started = time.monotonic()
    torch.manual_seed(args.seed)
    generator = torch.Generator().manual_seed(args.seed)

    class Spectral(torch.nn.Module):
        def __init__(self, width, modes):
            super().__init__()
            self.modes = modes
            self.weight = torch.nn.Parameter(
                torch.randn(width, width, modes, dtype=torch.cfloat) / width
            )

        def forward(self, x):
            freq = torch.fft.rfft(x, dim=-1)
            mixed = torch.einsum("bix,iox->box", freq[..., : self.modes], self.weight)
            out = torch.zeros_like(freq)
            out[..., : self.modes] = mixed
            return torch.fft.irfft(out, n=x.shape[-1], dim=-1)

    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lift = torch.nn.Conv1d(1, 16, 5, padding=2)
            self.spectral = Spectral(16, 8)
            self.mix = torch.nn.Conv1d(16, 16, 1)
            self.out = torch.nn.Conv1d(16, 1, 1)

        def forward(self, x):
            h = torch.nn.functional.gelu(self.lift(x))
            h = torch.nn.functional.gelu(self.spectral(h) + self.mix(h))
            return self.out(h)

    model = Net().to(device)
    x = torch.randn(64, 1, 64, generator=generator).to(device)
    y = torch.sin(3 * x)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    for _ in range(args.steps):
        optimizer.zero_grad()
        loss = torch.mean((model(x) - y) ** 2)
        loss.backward()
        optimizer.step()
    body = b"".join(
        value.detach().cpu().numpy().tobytes()
        for _, value in sorted(model.state_dict().items())
    )
    with torch.no_grad():
        predictions = model(x[:PARITY_ROWS]).cpu().numpy()
    np.save(args.predictions, predictions)
    return {
        "state_digest": _sha(body),
        "state_bytes": len(body),
        "predictions_digest": _sha(predictions.tobytes()),
        "backend": "gpu" if device == "cuda" else "cpu",
        "device": torch.cuda.get_device_name(0) if device == "cuda" else "cpu",
        "seconds": round(time.monotonic() - started, 3),
        "final_loss": float(loss),
    }


# ---- the parent: fresh children, verdicts -------------------------------------------


def _run_child(kind, key, arch, args, *, cpu, tmp, index):
    where = "cpu" if cpu else "dev"
    predictions = Path(tmp) / f"{kind}-{key}-{arch}-{where}-{index}.npy"
    env = {**os.environ, **_pinned_environment()}
    if cpu:
        env["JAX_PLATFORMS"] = "cpu"
        env["CUDA_VISIBLE_DEVICES"] = ""
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        kind,
        "--key",
        key,
        "--arch",
        arch,
        "--steps",
        str(args.steps),
        "--seed",
        str(args.seed),
        "--predictions",
        str(predictions),
    ]
    done = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        timeout=args.timeout,
        check=False,
    )
    if done.returncode != 0:
        typed = [ln for ln in done.stdout.splitlines() if ln.startswith('{"error"')]
        text = typed[-1] if typed else (done.stderr or done.stdout)[-600:]
        return {"error": text, "predictions": None}
    line = [ln for ln in done.stdout.splitlines() if ln.startswith("{")][-1]
    return {**json.loads(line), "predictions": str(predictions)}


def _parity(device_run, cpu_run):
    import numpy as np

    if not device_run.get("predictions") or not cpu_run.get("predictions"):
        return None
    a = np.load(device_run["predictions"]).astype(np.float64)
    b = np.load(cpu_run["predictions"]).astype(np.float64)
    scale = max(float(np.max(np.abs(b))), 1e-30)
    difference = float(np.max(np.abs(a - b)))
    return {
        "max_abs": difference,
        "max_relative_to_cpu_peak": difference / scale,
        "rows": int(a.shape[0]),
    }


def _check_case(kind, key, arch, args, tmp):
    runs = [
        _run_child(kind, key, arch, args, cpu=args.device == "cpu", tmp=tmp, index=i)
        for i in range(args.rebuilds)
    ]
    entry = {"kind": kind, "key": key, "arch": arch, "rebuilds": []}
    for run in runs:
        entry["rebuilds"].append({k: v for k, v in run.items() if k != "predictions"})
    digests = [r.get("state_digest") for r in runs]
    entry["bit_identical"] = bool(
        all(digests) and len(set(digests)) == 1 and len(digests) >= 2
    )
    entry["state_digest"] = digests[0] if entry["bit_identical"] else None
    entry["ran_on_gpu"] = all(r.get("backend") == "gpu" for r in runs)
    entry["ops"] = runs[0].get("ops")
    if args.device != "cpu" and not args.skip_cpu_parity:
        cpu = _run_child(kind, key, arch, args, cpu=True, tmp=tmp, index=99)
        entry["cpu_state_digest"] = cpu.get("state_digest")
        entry["parity_vs_cpu"] = _parity(runs[0], cpu)
        entry["cpu_error"] = cpu.get("error")
        # Whether the GPU is worth it for this graph at all: an interface in float64 runs at a
        # fraction of the card's float32 rate, and a tiny graph is bound by dispatch, not math.
        entry["seconds"] = {
            "gpu_first_rebuild": runs[0].get("seconds"),
            "cpu_rebuild": cpu.get("seconds"),
        }
    return entry


def _smi() -> dict:
    try:
        done = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,compute_cap",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        rows = [r.strip() for r in done.stdout.splitlines() if r.strip()]
        return {"gpus": rows, "returncode": done.returncode}
    except (OSError, subprocess.SubprocessError) as error:
        return {"gpus": [], "error": type(error).__name__}


def _versions() -> dict:
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for name in ("numpy", "jax", "jaxlib", "torch"):
        try:
            module = __import__(name)
            out[name] = getattr(module, "__version__", "?")
        except ImportError:
            out[name] = None
    try:
        import torch

        out["torch_cuda"] = torch.version.cuda
    except ImportError:
        pass
    return out


def class_record(args) -> dict:
    flags = _pinned_environment()
    record = {
        "schema": SCHEMA,
        "device_requested": args.device,
        "nvidia_smi": _smi(),
        "versions": _versions(),
        "flags": flags,
        "flags_digest": _sha(json.dumps(flags, sort_keys=True).encode()),
        "script_digest": _sha(Path(__file__).read_bytes()),
        "steps": args.steps,
        "seed": args.seed,
        "rebuilds_per_case": args.rebuilds,
        "cases": [],
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name in args.keys:
            for arch in args.archs:
                record["cases"].append(_check_case("graph", name, arch, args, tmp))
        if not args.no_torch:
            record["cases"].append(_check_case("torch", "probe", "spectral", args, tmp))
    gpu_needed = args.device != "cpu"
    record["all_bit_identical"] = all(c["bit_identical"] for c in record["cases"])
    record["all_on_gpu"] = all(c["ran_on_gpu"] for c in record["cases"])
    record["cpu_lane"] = sorted(
        f'{c["kind"]}:{c["key"]}/{c["arch"]}'
        for c in record["cases"]
        if not c["bit_identical"]
    )
    if not (record["all_bit_identical"] and (record["all_on_gpu"] or not gpu_needed)):
        record["verdict"] = "NOT_REPEATABLE_OR_NOT_GPU"
    else:
        record["verdict"] = "GPU_REPEATS" if gpu_needed else "REPEATS_ON_CPU_DRY_RUN"
    return record


def ops_record(record, allowlist_digest) -> dict:
    """The `carbon.graph-gpu-ops.v1` record this class check supports.

    An op is admitted when it appears in at least one graph that rebuilt bit-identically on a
    GPU and in NO graph that did not: absent evidence is not eligibility, and one failing graph
    keeps every op it used on the CPU until a narrower specimen clears it. Only a real GPU run
    can write one."""
    passed, failed = set(), set()
    for case in record["cases"]:
        if case["kind"] != "graph":
            continue
        (passed if case["bit_identical"] and case["ran_on_gpu"] else failed).update(
            case.get("ops") or ()
        )
    if not passed:
        raise ValueError("no graph rebuilt bit-identically on a GPU: nothing to admit")
    return {
        "schema": "carbon.graph-gpu-ops.v1",
        "allowlist_digest": allowlist_digest,
        "class_record_digest": _sha(json.dumps(record, sort_keys=True).encode()),
        "ops": sorted(passed - failed),
    }


def _served_allowlist_digest(keys) -> str:
    sys.path.insert(0, str(ROOT))
    from carbon.development_session import physical_graph_adapter_v2 as adapter
    from carbon.level4.allowlist import Allowlist

    digests = {
        Allowlist(adapter.served_allowlist_bytes(*KEYS[name])).digest for name in keys
    }
    if len(digests) != 1:
        raise ValueError("the versions checked serve different allowlists")
    return digests.pop()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="also write the JSON record here")
    parser.add_argument("--keys", nargs="+", choices=sorted(KEYS), default=sorted(KEYS))
    parser.add_argument(
        "--archs", nargs="+", choices=ARCHITECTURES, default=list(ARCHITECTURES)
    )
    parser.add_argument(
        "--ops-record",
        help="write the carbon.graph-gpu-ops.v1 record (the ops of every graph that "
        "rebuilt bit-identically on a GPU) here; refused for a CPU dry run",
    )
    parser.add_argument("--rebuilds", type=int, default=2)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--timeout", type=int, default=3600, help="per rebuild, seconds"
    )
    parser.add_argument("--device", choices=("auto", "cpu"), default="auto")
    parser.add_argument("--skip-cpu-parity", action="store_true")
    parser.add_argument("--no-torch", action="store_true")
    parser.add_argument("--child", choices=("graph", "torch"), help=argparse.SUPPRESS)
    parser.add_argument("--key", help=argparse.SUPPRESS)
    parser.add_argument("--arch", help=argparse.SUPPRESS)
    parser.add_argument("--predictions", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.rebuilds < 2:
        parser.error("--rebuilds must be at least 2")
    if args.child:
        child = _graph_child if args.child == "graph" else _torch_child
        print(json.dumps(child(args), sort_keys=True))
        return 0
    record = class_record(args)
    text = json.dumps(record, indent=1, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    if args.ops_record:
        if args.device == "cpu":
            parser.error("--ops-record needs a GPU run, not --device cpu")
        written = ops_record(record, _served_allowlist_digest(args.keys))
        Path(args.ops_record).write_text(
            json.dumps(written, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
    return 0 if record["verdict"] != "NOT_REPEATABLE_OR_NOT_GPU" else 1


if __name__ == "__main__":
    raise SystemExit(main())
