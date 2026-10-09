"""The `a40_acceptance` pod phase: pinned fresh-interpreter rebuilds with digests.

Shipped to the pod through the hash-pinned code manifest (`bootstrap.py`) and
selected with `PHASE_MODULE=scripts.dev.exam_design.runpod.a40_pod_phase`, so
the bootstrap runs

    python -m scripts.dev.exam_design.runpod.a40_pod_phase a40_acceptance --out OUT

with its configuration in `PHASE_CONFIG`. DEVELOPMENT evidence only: direct
execution inside the released image, not `validator_launch`, no scientific,
scoring, qualification or settlement authority, and no tolerance. It records
digests; the operator side compares them (`a40_acceptance.py`).

Order on the pod:

1. device identity (UUID, name, NVML driver build), refused when unreadable
   (`scripts/dev/gpu_determinism_study/device_identity.py`);
2. Carbon's GPU probe before any candidate code
   (`carbon.agent_campaign.graphite.pod_phase.probe_environment`, its schema);
   a failed probe stops everything else on the pod (stage `environment`,
   FAILED_INFRA, exit 6);
3. for each recipe, N repeats, each in a FRESH interpreter, rebuilding through
   the battery path (`carbon.battery.compile.compile_recipe` and `rebuild`, as
   `carbon.battery.torch_determinism` does) under the pinned environment, and
   hashing BOTH the weights (`params_sha256`) and the predictions
   (`predictions_sha256`) of every repeat.

4. the Level 4 B' leg (`PHASE1_PLAN.md` section 3), when the configuration
   carries one: for each pick, ONE rebuild in a fresh interpreter, under the
   same pinned environment, of that pick's B' documents. They were lowered on
   the CPU before any spend and arrive as data (`carbon.level4.staging`
   directories). Carbon verifies them (`submission.verify`), validates them
   (G4, the owner's caps), and trains them through Carbon's own loop
   (`carbon.level4.train`). Nothing is lowered or exported on a pod. The row
   records `params_sha256`, comparable with the native rebuild on the same
   host, and `outputs_sha256`, the graph's raw outputs on TRAIN, comparable
   B' to B' across hosts.

The same per-repeat flow runs on the CPU for `--local-cpu-dry-run`
(`JAX_PLATFORMS=cpu`, no device variables). No label, sealed or hidden
material is read: the only inputs are the public TRAIN v1 and OCV table.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PHASE = "a40_acceptance"
SCHEMA = "carbon.a40-acceptance.pod-results.v1"
IDENTITY_FILE, PROBE_FILE, RESULTS_FILE = "identity.json", "probe.json", "results.json"
EXIT_ENVIRONMENT, EXIT_REBUILD, EXIT_BARRIER = 6, 5, 7
#: The marker the bootstrap drops on an authenticated POST /go (port 8000).
GO_FILE = os.environ.get("GO_FILE", "/tmp/carbon-go")
#: Engineering allowance for one rebuild child. The pod's own watchdog
#: (`PROBE_DEADLINE`) is the real bound; this stops one hung child from
#: consuming it silently.
CHILD_SECONDS = 3600

#: One rebuild in a fresh interpreter. Weights and predictions are hashed
#: here, in the child, from the arrays themselves: `params_sha256` is the
#: battery recipe's own digest (`stats`), and `predictions_sha256` covers, per
#: output in sorted key order, the key, the shape and the float64 C-order
#: bytes of the model's predictions on the public TRAIN v1 inputs.
CHILD = """
import hashlib, json, sys, time
import numpy as np
from carbon.battery import challenge as ch
from carbon.battery.compile import compile_recipe, rebuild

strategy, seed, root = json.loads(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
started = time.perf_counter()
_, recipe = compile_recipe(strategy)
material = ch.PublicMaterial.load(root)
model, stats = rebuild(recipe, material, seed)
out = model.predict(material.train.x)
digest = hashlib.sha256()
for key in sorted(out):
    array = np.ascontiguousarray(np.asarray(out[key], dtype="<f8"))
    digest.update(key.encode() + b"\\0" + str(array.shape).encode() + b"\\0")
    digest.update(array.tobytes())
print(json.dumps({
    "params_sha256": stats["params_sha256"],
    "predictions_sha256": digest.hexdigest(),
    "backend": stats.get("backend", recipe.settings.get("backend", "jax")),
    "n_params": stats.get("n_params"),
    "seconds": round(time.perf_counter() - started, 3),
}))
"""

#: One Level 4 B' rebuild in a fresh interpreter: the pick's documents from
#: its staging directory, refused unless the submission digest is the run
#: record's. `params_sha256` is the battery recipe's own digest (the same
#: quantity as the native child's); `outputs_sha256` covers, per output in
#: order, the index, the shape and the float64 C-order bytes of the graph's
#: outputs on TRAIN's features.
CHILD_LEVEL4 = """
import hashlib, json, sys, time
import jax
import numpy as np
from carbon.battery import level4 as battery
from carbon.battery.recipes import features
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake, staging, submission, train, validate

strategy, seed, directory, expected = (
    json.loads(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
)
started = time.perf_counter()
allowlist = allowlist_module.load()
digest, raw_manifest, files = staging.read_directory(directory)
if digest != expected:
    raise SystemExit("the staged submission is not the run record's")
interface = battery.interface(strategy)
_, parsed = submission.verify(
    raw_manifest, files, allowlist=allowlist, challenge=battery.challenge_id(),
    interface=interface.digest(), max_bytes=intake.BOUNDS["document_bytes"],
)
verdict = validate.validate_submission(
    parsed, allowlist, interface=interface, batch=battery.training_batch(strategy)
)
prepared = train.prepare(parsed, allowlist, verdict=verdict)
result = train.train(battery, strategy, prepared, seed=seed)
material = battery.material()
_, model = battery._model(strategy, material.train)
wide = model.settings["precision"] == "float64"
f = features(material.train.x, model.rich).astype(np.float64 if wide else np.float32)
with jax.enable_x64(wide):
    outputs = prepared.predict([jax.numpy.asarray(a) for a in result["params"]], f)
out_digest = hashlib.sha256()
for index, value in enumerate(outputs):
    array = np.ascontiguousarray(np.asarray(value, dtype="<f8"))
    out_digest.update(str(index).encode() + b"\\0" + str(array.shape).encode() + b"\\0")
    out_digest.update(array.tobytes())
print(json.dumps({
    "params_sha256": result["params_sha256"],
    "outputs_sha256": out_digest.hexdigest(),
    "submission": digest,
    "status": verdict["status"],
    "path": result["path"],
    "seconds": round(time.perf_counter() - started, 3),
}))
"""

#: The PyTorch image's probe, run through `probe_environment(code=...)`. It
#: writes the same result keys as Carbon's JAX probe (`pod_phase.PROBE`), so
#: the record's schema is unchanged.
TORCH_PROBE = r"""
import json, os, sys
result = {"ok": False, "jax_platforms": os.environ.get("JAX_PLATFORMS")}
result["requires_gpu"] = "cuda" in (result["jax_platforms"] or "")


def done():
    with open(sys.argv[1], "w") as stream:
        json.dump(result, stream)


try:
    import torch

    result["jax"] = "torch " + torch.__version__
    available = torch.cuda.is_available()
    result["backend"] = "gpu" if available else "cpu"
    if available:
        result["devices"] = [
            {"platform": "gpu", "kind": torch.cuda.get_device_name(i)}
            for i in range(min(torch.cuda.device_count(), 16))
        ]
        x = torch.arange(8.0, device="cuda")
        result["checksum"] = float((x * 2.0).sum().item())
    result["ok"] = available and result.get("checksum") == 56.0
except BaseException as error:
    result["error_type"] = type(error).__name__
    done()
    raise
done()
"""


def pinned_environment(backend, *, device=None):
    """The environment every child of a GPU run is given.

    `device` is the device-identity record (`uuid`, `name`); None gives the
    CPU environment of `--local-cpu-dry-run`. The values are those of
    `carbon.reconstruction.accelerators.worker_environment` for the NVIDIA
    lane, read from its own constants so they cannot drift, plus the
    framework-independent pins the brief names.
    """
    env = {
        "JAX_ENABLE_X64": "false",
        "JAX_DEFAULT_MATMUL_PRECISION": "highest",
        "JAX_ENABLE_COMPILATION_CACHE": "false",
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
    }
    if device is None:
        env["JAX_PLATFORMS"] = "cpu"
        return env
    from carbon.reconstruction import accelerators

    env.update(
        {
            "JAX_PLATFORMS": "cuda",
            "CUDA_VISIBLE_DEVICES": device["uuid"],
            "CARBON_ACCELERATOR_DEVICE_KIND": device["name"],
            "XLA_PYTHON_CLIENT_ALLOCATOR": "platform",
            "XLA_FLAGS": " ".join(accelerators.GPU_DETERMINISM_XLA_FLAGS),
            **accelerators.GPU_DETERMINISM_ENVIRONMENT,
        }
    )
    return env


def wait_for_go(timeout, path=GO_FILE):
    """The preflight barrier: block until the operator, having seen BOTH pods'
    driver identities recorded and matching, POSTs /go to the bootstrap, which
    drops `path`. False on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if Path(path).exists():
            return True
        time.sleep(1)
    return False


def read_identity():
    """The one visible device's identity, or a refusal. Unreadable UUID, name or
    driver build is a refusal (FAILED_INFRA), never a guess."""
    from scripts.dev.gpu_determinism_study import device_identity

    devices = device_identity.device_uuids()
    if len(devices) != 1:
        return None, f"expected exactly one visible device, found {len(devices)}"
    device = devices[0]
    for key in ("uuid", "name", "driver_version"):
        if not isinstance(device.get(key), str) or not device[key]:
            return None, f"device {key} is unreadable"
    return device, None


def hexdigest_ok(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def run_repeat(strategy, seed, root, env, *, python=None, timeout=CHILD_SECONDS):
    """One rebuild in a fresh interpreter with `env` over this process's
    environment. Returns the child's record, or `{"error": ...}` (type only;
    the stderr tail is kept short, and carries no environment)."""
    full = dict(os.environ)
    full.update(env)
    try:
        done = subprocess.run(
            [
                python or sys.executable,
                "-c",
                CHILD,
                json.dumps(strategy),
                str(seed),
                str(root),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(root).resolve(),
            env=full,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": "ChildTimeout"}
    if done.returncode != 0:
        return {"error": f"exit {done.returncode}", "stderr_tail": done.stderr[-400:]}
    try:
        record = json.loads(done.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {"error": "child printed no record"}
    if not (
        hexdigest_ok(record.get("params_sha256"))
        and hexdigest_ok(record.get("predictions_sha256"))
    ):
        return {"error": "child record has no digests"}
    return record


def run_level4(entry, seed, root, env, *, python=None, timeout=CHILD_SECONDS):
    """One Level 4 B' rebuild of `entry` (a pick's staging directory under
    `root`) in a fresh interpreter with `env`. The child's record, or
    `{"error": ...}`."""
    full = dict(os.environ)
    full.update(env)
    try:
        done = subprocess.run(
            [
                python or sys.executable,
                "-c",
                CHILD_LEVEL4,
                json.dumps(entry["strategy"]),
                str(seed),
                str(Path(root).resolve() / entry["directory"]),
                entry["submission"],
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(root).resolve(),
            env=full,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": "ChildTimeout"}
    if done.returncode != 0:
        return {"error": f"exit {done.returncode}", "stderr_tail": done.stderr[-400:]}
    try:
        record = json.loads(done.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return {"error": "child printed no record"}
    if not (
        hexdigest_ok(record.get("params_sha256"))
        and hexdigest_ok(record.get("outputs_sha256"))
    ):
        return {"error": "child record has no digests"}
    return record


def run_recipes(config, root, env, *, out=None, python=None):
    """Every recipe, N repeats, each in a fresh interpreter, then each Level 4
    pick once (`leg: level4`). Writes progress to `out/progress.json` (the
    bootstrap serves it at /status) when given."""
    level4 = config.get("level4", [])
    rows = []
    total = len(config["recipes"]) * config["repeats"] + len(level4)
    for recipe in config["recipes"]:
        for repeat in range(config["repeats"]):
            started = time.monotonic()
            record = run_repeat(
                recipe["strategy"], config["seed"], root, env, python=python
            )
            rows.append(
                {
                    "recipe_id": recipe["id"],
                    "repeat": repeat,
                    "wall_seconds": round(time.monotonic() - started, 3),
                    **record,
                }
            )
            if out is not None:
                (Path(out) / "progress.json").write_text(
                    json.dumps({"done": len(rows), "total": total})
                )
    for entry in level4:
        started = time.monotonic()
        record = run_level4(entry, config["seed"], root, env, python=python)
        rows.append(
            {
                "recipe_id": entry["id"],
                "leg": "level4",
                "repeat": 0,
                "wall_seconds": round(time.monotonic() - started, 3),
                **record,
            }
        )
        if out is not None:
            (Path(out) / "progress.json").write_text(
                json.dumps({"done": len(rows), "total": total})
            )
    return rows


def results_document(config, rows, *, device, environment_pins):
    return {
        "schema": SCHEMA,
        "backend": config["backend"],
        "seed": config["seed"],
        "repeats": config["repeats"],
        "device": device,
        "environment_pins": environment_pins,
        "recipes": [r["id"] for r in config["recipes"]],
        "level4": [e["id"] for e in config.get("level4", [])],
        "rows": rows,
        "complete": all("error" not in row for row in rows) and len(rows) > 0,
    }


def _write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=1))


def _run(config, out, *, root="/tmp/carbon", python=None):
    """The pod phase. Returns the exit code."""
    from carbon.agent_campaign.graphite import pod_phase

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    device, refusal = read_identity()
    if device is None:
        _write(out / "failure.json", {"stage": "environment", "error": refusal})
        return EXIT_ENVIRONMENT
    _write(out / IDENTITY_FILE, device)
    env = pinned_environment(config["backend"], device=device)
    # The probe runs in a child of this interpreter with this process's
    # environment: give it the pinned environment, so it initialises the
    # backend exactly as the rebuilds will.
    os.environ.update(env)
    probe = pod_phase.probe_environment(
        TORCH_PROBE if config["backend"] == "pytorch" else None
    )
    _write(out / PROBE_FILE, probe)
    if not probe["ok"]:
        _write(
            out / "failure.json",
            {"stage": "environment", "error": probe.get("error_type", "probe")},
        )
        return EXIT_ENVIRONMENT
    if config.get("barrier") and not wait_for_go(
        config.get("go_timeout_seconds", 1800)
    ):
        _write(out / "failure.json", {"stage": "barrier", "error": "not released"})
        return EXIT_BARRIER
    rows = run_recipes(config, root, env, out=out, python=python)
    document = results_document(
        config, rows, device=device, environment_pins=sorted(env)
    )
    _write(out / RESULTS_FILE, document)
    if not document["complete"]:
        _write(out / "failure.json", {"stage": "rebuild", "error": "a rebuild failed"})
        return EXIT_REBUILD
    _write(out / "DONE.json", {"phase": PHASE, "exit": 0})
    return 0


def run(config, out, *, root="/tmp/carbon", python=None):
    """The pod phase. The pinned environment is applied to this process for the
    probe only and restored on return: nothing here may leak into a caller."""
    saved = dict(os.environ)
    try:
        return _run(config, out, root=root, python=python)
    finally:
        os.environ.clear()
        os.environ.update(saved)


def local_cpu_run(config, root, out, *, python=None):
    """The same per-repeat flow on the CPU (`--local-cpu-dry-run`): no device,
    no probe, `JAX_PLATFORMS=cpu`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    env = pinned_environment(config["backend"], device=None)
    rows = run_recipes(config, root, env, out=out, python=python)
    document = results_document(config, rows, device=None, environment_pins=sorted(env))
    _write(out / RESULTS_FILE, document)
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("phase")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cpu", action="store_true", help="local CPU dry run")
    parser.add_argument(
        "--root", default=os.environ.get("CARBON_MATERIAL_ROOT", "/tmp/carbon")
    )
    args = parser.parse_args(argv)
    if args.phase != PHASE:
        print(f"unknown phase {args.phase!r}", file=sys.stderr)
        return 2
    config = json.loads(os.environ["PHASE_CONFIG"])
    if args.cpu:
        document = local_cpu_run(config, args.root, args.out)
        return 0 if document["complete"] else EXIT_REBUILD
    return run(config, args.out, root=args.root)


if __name__ == "__main__":
    raise SystemExit(main())
