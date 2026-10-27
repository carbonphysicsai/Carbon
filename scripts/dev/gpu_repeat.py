# ruff: noqa: BLE001 - a failed entry is a result, not a crash
"""GPU smoke + GPU-vs-GPU repeat for catalog GPU builds (backbone-catalog lane, U58, 2026-10-22).

Per the Lead: CPU-vs-GPU parity is dropped; each GPU build needs (1) a smoke that it really runs on the GPU and
(2) a repeat on the same GPU that is byte-identical. This runs the entry's GPU bundle source
(`bundles/<id>/<torch-cu130-py311|jax-cuda13-py311>/`) twice from one seed on synthetic data of the entry's
Challenge shape, trains a few steps, and records per run: the device the framework used, the peak GPU memory, the
sha256 of the trained parameters and of the predictions. It is a structure/determinism smoke, not a score or a
pair-identity receipt on the real TRAIN.

    python gpu_repeat.py <carbon checkout> <out.json> [entries comma list] [--steps N] [--allow-cpu]
                         [--framework torch|jax] [--wheels DIR[,DIR]]
    python gpu_repeat.py compare <runA.json> <runB.json>

Run it twice on the GPU host (two separate processes, same checkout, same driver and GPU), then `compare`: an entry
passes when both runs used the GPU and every hash equals. A single run already contains an in-process repeat
(`repeat_identical`). `--allow-cpu` only exercises the mechanics on a CPU host and marks the entry `gpu: false`.

The environment is Carbon's, never the image's or the caller's: `run` sets it from
`carbon.reconstruction.accelerators.pinned_environment` (explicit `JAX_PLATFORMS`, the allocator, the
determinism XLA flags, cuBLAS, TF32) and applies `GPU_DETERMINISM_TORCH` to torch, then records the
environment's digest; `compare` refuses two runs whose environment digests differ. An entry whose backend is
not the GPU is the typed error `backend_not_gpu`, not a result. Memory use (`peak_gpu_bytes`) is reported but is
not part of what must repeat: it moves by a few KB between processes with identical parameters and predictions.
"""

import hashlib
import importlib
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path

#: Challenge id -> (inputs, outputs) of the packet each catalog entry is built for.
SHAPES = {
    "electric-motor-magnetics": (8, 60),
    "chip-cold-plate": (9, 32),
    "f08-ribbed-bracket": (6, 7),
    "f02": (2, 1),
    "battery-fastcharge-ageing-development-v1": (4, 247),
}
TWINS = {"torch-cu130-py311": "torch", "jax-cuda13-py311": "jax"}
#: Reported, not compared: allocator bookkeeping differs by a few KB between processes.
NOT_COMPARED = ("peak_gpu_bytes",)


def stable(run_record):
    """What must repeat bit for bit: a run without its memory bookkeeping."""
    return {k: v for k, v in run_record.items() if k not in NOT_COMPARED}


def pinned(repo, allow_cpu):
    """Set Carbon's pinned environment in this process, before any framework loads; return it."""
    sys.path.insert(0, str(repo))
    from carbon.reconstruction.accelerators import GPU_PROFILE, pinned_environment

    environment = pinned_environment(GPU_PROFILE)
    if allow_cpu:
        environment = {**environment, "JAX_PLATFORMS": "cpu"}
    os.environ.update(environment)
    return environment


def apply_torch_determinism(torch):
    """The torch half of the pinned configuration (`GPU_DETERMINISM_TORCH`)."""
    from carbon.reconstruction.accelerators import GPU_DETERMINISM_TORCH

    for name, value in GPU_DETERMINISM_TORCH:
        if name == "use_deterministic_algorithms":
            torch.use_deterministic_algorithms(value)
        elif name == "cudnn_deterministic":
            torch.backends.cudnn.deterministic = value
        elif name == "cudnn_benchmark":
            torch.backends.cudnn.benchmark = value


def sha(array):
    import numpy as np

    return hashlib.sha256(np.ascontiguousarray(np.asarray(array)).tobytes()).hexdigest()


def add_wheels(source_dir, wheel_dirs):
    """Unpack the entry's pinned pure-Python wheels (DeepXDE, torch-geometric, torch-harmonics, ...) onto sys.path."""
    import zipfile

    manifest = json.loads((source_dir / "bundle.json").read_bytes())
    site = tempfile.mkdtemp()
    for wheel in manifest.get("wheels", {}):
        found = next(
            (Path(d) / wheel for d in wheel_dirs if (Path(d) / wheel).is_file()), None
        )
        if found is None:
            raise FileNotFoundError(
                "wheel " + wheel + " not found in " + ", ".join(map(str, wheel_dirs))
            )
        with zipfile.ZipFile(found) as handle:
            handle.extractall(site)
    if site not in sys.path:
        sys.path.insert(0, site)


def one_run(source_dir, entry, n_in, n_out, framework, steps, wheel_dirs=()):
    import numpy as np

    rng = np.random.default_rng(0)
    zi, zt = rng.normal(size=(24, n_in)), rng.normal(size=(24, n_out))
    add_wheels(source_dir, wheel_dirs)
    if framework == "torch":
        import torch

        apply_torch_determinism(torch)
    work = tempfile.mkdtemp()
    with tarfile.open(source_dir / "source.tar.gz") as archive:
        archive.extractall(work, filter="data")
    root = str(next(Path(work).iterdir()))
    sys.path.insert(0, root)
    for name in [
        m
        for m in sys.modules
        if m == "carbon_candidate" or m.startswith("carbon_candidate.")
    ]:
        del sys.modules[name]
    module = importlib.import_module(entry["entrypoint"]["module"])
    build = getattr(module, entry["entrypoint"]["name"])
    cfg = entry["defaults"]["configuration"]
    product = build(zi, zt, seed=1, configuration=cfg, train_use={"steps": steps})
    sys.path.remove(root)
    parameters = product["parameters"]
    if framework == "torch":
        import torch

        x = torch.as_tensor(zi[:8])
        pred = product["apply"](parameters, x)
        peak = torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0
        device = "cuda" if torch.cuda.is_available() else "cpu"
        pred = pred.detach().cpu().numpy()
        flat = [p.detach().cpu().numpy() for p in parameters]
    else:
        import jax
        import jax.numpy as jnp

        pred = np.asarray(
            product["apply"]([jnp.asarray(p) for p in parameters], jnp.asarray(zi[:8]))
        )
        device = jax.default_backend()
        stats = jax.devices()[0].memory_stats() or {}
        peak = int(stats.get("peak_bytes_in_use", 0))
        flat = [np.asarray(p) for p in parameters]
    return {
        "device": device,
        "peak_gpu_bytes": int(peak),
        "parameters_sha256": hashlib.sha256(
            b"".join(sha(p).encode() for p in flat)
        ).hexdigest(),
        "predictions_sha256": sha(pred),
        "output_shape": list(pred.shape),
        "finite": bool(np.isfinite(pred).all()),
    }


def run(repo, out, wanted, steps, allow_cpu, only_framework=None, wheel_dirs=()):
    repo = Path(repo).resolve()
    manifest = json.loads((repo / "carbon/backbone_catalog/manifest.json").read_bytes())
    environment = pinned(repo, allow_cpu)
    report = {
        "entries": {},
        "steps": steps,
        "environment": environment,
        "environment_digest": hashlib.sha256(
            json.dumps(environment, sort_keys=True).encode()
        ).hexdigest(),
    }
    for entry in manifest["entries"]:
        catalog_id = entry["catalog_id"]
        runtimes = [r for r in (entry.get("bundle_refs") or {}) if r in TWINS]
        if not runtimes or (wanted and catalog_id not in wanted):
            continue
        runtime = runtimes[0]
        framework = TWINS[runtime]
        if only_framework and framework != only_framework:
            continue
        if framework == "jax":
            os.environ["JAX_ENABLE_X64"] = "1"
        shape = SHAPES.get(entry["challenges"][0]["id"])
        if shape is None:
            report["entries"][catalog_id] = {
                "error": "no shape for " + entry["challenges"][0]["id"]
            }
            continue
        try:
            first = one_run(
                repo / "carbon/backbone_catalog/bundles" / catalog_id / runtime,
                entry,
                *shape,
                framework,
                steps,
                wheel_dirs,
            )
            second = one_run(
                repo / "carbon/backbone_catalog/bundles" / catalog_id / runtime,
                entry,
                *shape,
                framework,
                steps,
                wheel_dirs,
            )
        except Exception as error:  # a failed entry is a result, not a crash
            report["entries"][catalog_id] = {
                "runtime": runtime,
                "error": f"{type(error).__name__}: {str(error)[:300]}",
            }
            continue
        on_gpu = first["device"] in ("cuda", "gpu")
        report["entries"][catalog_id] = {
            "runtime": runtime,
            "gpu": on_gpu,
            "first": first,
            "repeat_identical": stable(first) == stable(second),
        }
        if not on_gpu and not allow_cpu:
            report["entries"][catalog_id]["error"] = "backend_not_gpu"
    Path(out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    bad = [
        k
        for k, v in report["entries"].items()
        if v.get("error") or not v.get("repeat_identical")
    ]
    print(json.dumps({"entries": len(report["entries"]), "not_ok": bad}, indent=1))


def compare(a, b):
    ra, rb = (json.loads(Path(p).read_bytes()) for p in (a, b))
    if ra.get("environment_digest") != rb.get("environment_digest") or not ra.get(
        "environment_digest"
    ):
        print(
            json.dumps(
                {"error": "runs were not made under the same pinned environment"}
            )
        )
        return 1
    verdict = {}
    for key in sorted(set(ra["entries"]) | set(rb["entries"])):
        x, y = ra["entries"].get(key), rb["entries"].get(key)
        if not x or not y or x.get("error") or y.get("error"):
            verdict[key] = "NOT_OK: " + str(
                (x or {}).get("error") or (y or {}).get("error") or "missing"
            )
        elif not (x["gpu"] and y["gpu"]):
            verdict[key] = "NOT_OK: no GPU"
        elif (
            x["repeat_identical"]
            and y["repeat_identical"]
            and stable(x["first"]) == stable(y["first"])
        ):
            verdict[key] = "PASS"
        else:
            verdict[key] = "DIFFER"
    print(json.dumps(verdict, indent=1, sort_keys=True))
    return 0 if all(v == "PASS" for v in verdict.values()) else 1


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args and args[0] == "compare":
        raise SystemExit(compare(args[1], args[2]))
    steps = (
        int(sys.argv[sys.argv.index("--steps") + 1]) if "--steps" in sys.argv else 20
    )
    args = [a for a in args if not a.isdigit()]
    framework = (
        sys.argv[sys.argv.index("--framework") + 1]
        if "--framework" in sys.argv
        else None
    )
    wheels = (
        sys.argv[sys.argv.index("--wheels") + 1].split(",")
        if "--wheels" in sys.argv
        else [str(Path.home() / ".carbon/catalog-wheelhouse")]
    )
    args = [a for a in args if a not in (framework, ",".join(wheels))]
    run(
        args[0],
        args[1],
        args[2].split(",") if len(args) > 2 else [],
        steps,
        "--allow-cpu" in sys.argv,
        framework,
        wheels,
    )
