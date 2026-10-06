#!/usr/bin/env python3
"""The released worker images' capability matrix (IMAGE-RELEASE-01).

Runs after the release push, against the pulled released digests (each pulled
and verified by `worker_image_release.py pull`). Four cells - JAX CPU, JAX GPU,
PyTorch CPU and PyTorch GPU - each with these checks:

- `imports`: the stack imports inside the pinned image;
- `devices`: the devices the stack reports are the cell's;
- `lock_versions`: the installed versions are the ones `uv.lock` and the
  image's exact-hashed export pin (read from the files, never restated here);
- `rebuild`: one battery recipe rebuilds through the real worker entrypoint
  (the validator's isolated carrier, `CarrierBackend.reconstruct`);
- `determinism_config` (GPU and PyTorch cells): the pinned configuration is
  accepted or active.

Every check is VERIFIED, UNVERIFIED or FAILED. A check that needs hardware
this host does not have is UNVERIFIED with its reason, never passed: on a
GPU-less runner every GPU device and rebuild check is UNVERIFIED. A cell is
VERIFIED only when every one of its checks is. The command exits 1 when any
check FAILED.

The report states facts only. The reproducibility tolerance is the
owner's (HUMAN_INPUT) and nothing here sets it. The A40 determinism re-run is
granted (#681) and is reported as not yet run here.

    worker_image_capability.py --records DIR --manifests DIR --out REPORT \\
        [--gpus] [--expect-device-kind KIND]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "carbon.worker-image-capability.v1"
VERIFIED, UNVERIFIED, FAILED = "VERIFIED", "UNVERIFIED", "FAILED"
KINDS = ("c03", "accelerator", "torch", "torch-gpu")
#: The stack each cell's lock check reads, and the file pinning each name.
JAX_NAMES = ("jax", "jaxlib", "optax", "numpy")
CUDA_NAMES = ("jax-cuda13-plugin", "jax-cuda13-pjrt")
TORCH_NAMES = ("torch", "torchvision", "neuraloperator", "nvidia-physicsnemo")
ACCELERATOR_LOCK = ".devcontainer/accelerators/cuda13-py311.txt"
TORCH_EXPORT = ".devcontainer/torch/torch-cpu-py311.txt"
TORCH_GPU_LOCK = ".devcontainer/torch/torch-cu130-py311.txt"
#: The PyTorch GPU stack the GPU cell checks against its own lock.
TORCH_GPU_NAMES = (
    "torch",
    "neuraloperator",
    "nvidia-cublas",
    "nvidia-cudnn-cu13",
    "triton",
)
#: One small recipe per backend: a capability probe, not a study.
RECIPE = {"width": 16, "depth": 1, "steps": 32}
NO_GPU = "this host exposes no GPU to the probe (run with --gpus on a GPU host)"
NO_GPU_DISPATCH = (
    "the validator path's accelerator dispatch is disabled in this repository "
    "(accelerators.require_accelerator_admission); the granted A40 run (#681) "
    "establishes it"
)
NO_TORCH_GPU_REBUILD = (
    "the PyTorch CUDA rebuild path is battery implementation 2.0 "
    "(TORCH-GPU-01), but the validator path's accelerator dispatch is disabled "
    "in this repository (accelerators.require_accelerator_admission); the "
    "granted A40 run (#681) establishes it"
)
NO_TORCH_GPU_DETERMINISM = (
    "the GPU determinism (torch_profile.GPU_DETERMINISM, inside the image's "
    "carbon.accelerator.profile) is applied by "
    "carbon.reconstruction.torch_gpu only on a CUDA device"
)
#: The CPU profile settings the probe can observe inside the rebuild path
#: (`seed_source` is a property of the code, held by a unit test).
OBSERVED_CPU_DETERMINISM = ("use_deterministic_algorithms", "intra_op_threads")

#: Runs inside the pinned image with its own interpreter.
PROBE = r"""
import importlib.metadata as metadata, json, os, sys
mode, names = sys.argv[1], json.loads(sys.argv[2])
out = {"versions": {}}
for name in names:
    try:
        out["versions"][name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        out["versions"][name] = None
if mode == "jax":
    import jax, jaxlib, numpy, optax
    out["platform"] = jax.default_backend()
    out["devices"] = [d.platform + ":" + d.device_kind for d in jax.devices()]
    out["xla_flags"] = os.environ.get("XLA_FLAGS")
elif mode == "torch_gpu":
    import neuralop, torch
    out["cuda_available"] = torch.cuda.is_available()
    out["torch_cuda"] = torch.version.cuda
    out["devices"] = ["cpu"] + [
        "cuda:" + torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())
    ]
    if out["cuda_available"]:
        from carbon.reconstruction import torch_gpu
        try:
            with torch_gpu.deterministic_cuda() as active:
                out["determinism"] = active
        except torch_gpu.EnvironmentIneligible as refused:
            out["determinism_refused"] = str(refused)
else:
    import neuralop, torch
    from carbon.battery.torch_training import deterministic
    out["cuda_available"] = torch.cuda.is_available()
    out["devices"] = ["cpu"] + [
        "cuda:" + torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())
    ]
    # What the rebuild path puts in force, read inside it.
    with deterministic():
        out["determinism"] = {
            "use_deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "intra_op_threads": torch.get_num_threads(),
        }
print(json.dumps(out))
"""


def check(status, detail=""):
    return {"status": status, "detail": detail}


def pinned_versions(root=REPOSITORY_ROOT):
    """Every version the checks compare: from `uv.lock` and the exports."""
    import tomllib

    lock = tomllib.loads((Path(root) / "uv.lock").read_text(encoding="utf-8"))
    found = {}
    for package in lock.get("package", []):
        if package.get("name") in JAX_NAMES:
            found.setdefault(package["name"], set()).add(package["version"])
    uv = {}
    for name in JAX_NAMES:
        if len(found.get(name, ())) != 1:
            raise ValueError(f"uv.lock pins {name} other than exactly once")
        (uv[name],) = found[name]
    return {
        "uv.lock": uv,
        ACCELERATOR_LOCK: _requirements(root, ACCELERATOR_LOCK),
        TORCH_EXPORT: _requirements(root, TORCH_EXPORT),
        TORCH_GPU_LOCK: _requirements(root, TORCH_GPU_LOCK),
    }


def _requirements(root, relative):
    pins = {}
    for line in (Path(root) / relative).read_text(encoding="utf-8").splitlines():
        matched = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)", line)
        if matched:
            pins[matched.group(1).lower()] = matched.group(2)
    return pins


def expected_for(cell, pins):
    """The exact versions a cell's image must carry, by source."""
    expected = dict(pins["uv.lock"])
    if cell == "jax_gpu":
        for name in (*JAX_NAMES, *CUDA_NAMES):
            expected[name] = pins[ACCELERATOR_LOCK].get(name)
    if cell == "pytorch_cpu":
        for name in (*TORCH_NAMES, "numpy"):
            expected[name] = pins[TORCH_EXPORT].get(name)
    if cell == "pytorch_gpu":
        for name in (*TORCH_GPU_NAMES, "numpy"):
            expected[name] = pins[TORCH_GPU_LOCK].get(name)
    if any(v is None for v in expected.values()):
        raise ValueError(f"a pin for {cell} is missing from its lock file")
    return expected


def compare_versions(expected, installed):
    differs = {
        name: {"pinned": version, "installed": installed.get(name)}
        for name, version in expected.items()
        if installed.get(name) != version
    }
    if differs:
        return check(FAILED, differs)
    return check(VERIFIED, expected)


def run_probe(reference, mode, names, *, env=None, gpus=False):
    """The probe inside the pinned image: no network, the worker's user."""
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--user",
        "65532:65532",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/scratch",
        "--cpus",
        "2",
        "--memory",
        "4g",
        "--entrypoint",
        "/opt/carbon-worker/bin/python",
    ]
    for key, value in sorted((env or {}).items()):
        command += ["--env", f"{key}={value}"]
    if gpus:
        command += ["--gpus", "all"]
    command += [reference, "-I", "-c", PROBE, mode, json.dumps(list(names))]
    done = subprocess.run(
        command, capture_output=True, text=True, timeout=900, check=False
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip()[-400:] or "probe failed")
    return json.loads(done.stdout.strip().splitlines()[-1])


def carrier_rebuild(manifests, backend):
    """One recipe rebuilt through the validator's isolated carrier."""
    import os

    from carbon.battery import worker
    from carbon.battery.compile import compile_recipe
    from carbon.battery.pool_store import PoolStore
    from carbon.reconstruction import capability_registry as registry
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    jax_image = load_image_identity(Path(manifests["c03"]))
    torch_image = (
        load_image_identity(Path(manifests["torch"])) if backend == "pytorch" else None
    )
    parameters = dict(
        RECIPE, **({"backend": "pytorch"} if backend == "pytorch" else {})
    )
    recipe = compile_recipe(
        {
            "schema_version": "1.0",
            "challenge_id": registry.BATTERY_CHALLENGE,
            "backbone": "mlp",
            "parameters": parameters,
        }
    )[1]
    with tempfile.TemporaryDirectory() as folder:
        os.chmod(folder, 0o700)
        ledger = worker.WorkLedger(
            PoolStore(Path(folder) / "state.sqlite3"), Path(folder) / "work"
        )
        carrier = worker.CarrierBackend(
            ledger, jax_image, torch_image=torch_image, root=REPOSITORY_ROOT
        )
        state, fit = carrier.reconstruct("capability-" + backend, recipe, 0)
    return {
        "state_sha256": "sha256:" + hashlib.sha256(state).hexdigest(),
        "fit_backend": fit.get("backend", "jax") if type(fit) is dict else None,
    }


def guarded(function):
    """A check that raised is FAILED, named by its type."""
    try:
        return function()
    except Exception as failure:  # noqa: BLE001 - every failure is reported
        return check(FAILED, f"{type(failure).__name__}: {str(failure)[:400]}")


def jax_cpu(references, manifests, pins):
    probe = {}

    def imports():
        probe.update(run_probe(references["c03"], "jax", JAX_NAMES))
        return check(VERIFIED, "jax, jaxlib, optax, numpy")

    def devices():
        if not probe:
            return check(FAILED, "no probe result")
        ok = probe["platform"] == "cpu" and probe["devices"]
        return check(VERIFIED if ok else FAILED, probe["devices"])

    def rebuild():
        result = carrier_rebuild(manifests, "jax")
        ok = result["fit_backend"] == "jax"
        return check(VERIFIED if ok else FAILED, result)

    return {
        "imports": guarded(imports),
        "devices": guarded(devices),
        "lock_versions": guarded(
            lambda: compare_versions(expected_for("jax_cpu", pins), probe["versions"])
        ),
        "rebuild": guarded(rebuild),
    }


def gpu_environment(*, gpus, expect_kind):
    """The accelerator overlay both GPU cells run under - the controller's
    `accelerators.worker_environment` values that do not name one host: the
    platform, the bound device kind (when given), the XLA flags and the CUDA
    library controls. One overlay, so JAX and PyTorch are probed alike."""
    from carbon.reconstruction.accelerators import (
        GPU_DETERMINISM_ENVIRONMENT,
        GPU_DETERMINISM_XLA_FLAGS,
    )

    env = {
        **GPU_DETERMINISM_ENVIRONMENT,
        "XLA_FLAGS": " ".join(GPU_DETERMINISM_XLA_FLAGS),
        "JAX_PLATFORMS": "cuda" if gpus else "cpu",
        "JAX_DEFAULT_MATMUL_PRECISION": "highest",
    }
    if expect_kind:
        env["CARBON_ACCELERATOR_DEVICE_KIND"] = expect_kind
    return env


def jax_gpu(references, pins, *, gpus, expect_kind):
    from carbon.reconstruction.accelerators import (
        GPU_DETERMINISM_ENVIRONMENT,
        GPU_DETERMINISM_XLA_FLAGS,
    )

    flags = " ".join(GPU_DETERMINISM_XLA_FLAGS)
    env = gpu_environment(gpus=gpus, expect_kind=expect_kind)
    probe = {}
    names = (*JAX_NAMES, *CUDA_NAMES)

    def imports():
        probe.update(
            run_probe(references["accelerator"], "jax", names, env=env, gpus=gpus)
        )
        return check(VERIFIED, "jax with the CUDA 13 plugin")

    def determinism():
        # XLA parses XLA_FLAGS when the backend starts and refuses an unknown
        # flag, so a started backend under the pinned flags accepted them.
        if probe.get("xla_flags") != flags:
            return check(FAILED, "the pinned XLA_FLAGS were not in force")
        if not gpus:
            return check(
                UNVERIFIED,
                "pinned flags accepted by the image's jaxlib on CPU; active on a "
                "CUDA device: " + NO_GPU,
            )
        return check(VERIFIED, {"xla_flags": flags, **GPU_DETERMINISM_ENVIRONMENT})

    def devices():
        if not gpus:
            return check(UNVERIFIED, NO_GPU)
        kinds = [d for d in probe.get("devices", []) if d.startswith("gpu:")]
        if probe.get("platform") != "gpu" or not kinds:
            return check(FAILED, probe.get("devices"))
        if expect_kind and any(k != "gpu:" + expect_kind for k in kinds):
            return check(FAILED, {"expected": expect_kind, "reported": kinds})
        return check(VERIFIED, kinds)

    return {
        "imports": guarded(imports),
        "devices": guarded(devices),
        "lock_versions": guarded(
            lambda: compare_versions(expected_for("jax_gpu", pins), probe["versions"])
        ),
        "determinism_config": guarded(determinism),
        "rebuild": check(UNVERIFIED, NO_GPU_DISPATCH),
    }


def pytorch_cpu(references, manifests, pins):
    from carbon.reconstruction.torch_profile import CPU_DETERMINISM

    probe = {}
    names = (*JAX_NAMES, *TORCH_NAMES)

    def imports():
        probe.update(run_probe(references["torch"], "torch", names))
        return check(VERIFIED, "torch, neuralop and the carbon PyTorch backend")

    def devices():
        ok = probe.get("devices") == ["cpu"] and probe.get("cuda_available") is False
        return check(VERIFIED if ok else FAILED, probe.get("devices"))

    def determinism():
        # The CPU profile must be in force in the rebuild path. The GPU
        # profile's CUDA-only settings are the PyTorch GPU cell's.
        active = probe.get("determinism") or {}
        observed = OBSERVED_CPU_DETERMINISM
        pinned = {k: v for k, v in CPU_DETERMINISM if k in observed}
        differs = {k: active.get(k) for k, v in pinned.items() if active.get(k) != v}
        return check(FAILED, differs) if differs else check(VERIFIED, pinned)

    def rebuild():
        result = carrier_rebuild(manifests, "pytorch")
        ok = result["fit_backend"] == "pytorch"
        return check(VERIFIED if ok else FAILED, result)

    return {
        "imports": guarded(imports),
        "devices": guarded(devices),
        "lock_versions": guarded(
            lambda: compare_versions(
                expected_for("pytorch_cpu", pins), probe["versions"]
            )
        ),
        "determinism_config": guarded(determinism),
        "rebuild": guarded(rebuild),
    }


def pytorch_gpu(references, pins, *, gpus, expect_kind):
    from carbon.reconstruction.torch_profile import GPU_DETERMINISM

    probe = {}
    names = (*JAX_NAMES, *TORCH_GPU_NAMES)

    def imports():
        env = gpu_environment(gpus=gpus, expect_kind=expect_kind)
        probe.update(
            run_probe(references["torch-gpu"], "torch_gpu", names, env=env, gpus=gpus)
        )
        if probe.get("torch_cuda") is None:
            return check(FAILED, "torch is not a CUDA build")
        return check(
            VERIFIED, "torch (CUDA " + str(probe["torch_cuda"]) + "), neuralop"
        )

    def devices():
        if not gpus:
            return check(UNVERIFIED, NO_GPU)
        kinds = [d for d in probe.get("devices", []) if d.startswith("cuda:")]
        if not probe.get("cuda_available") or not kinds:
            return check(FAILED, probe.get("devices"))
        if expect_kind and any(k != "cuda:" + expect_kind for k in kinds):
            return check(FAILED, {"expected": expect_kind, "reported": kinds})
        return check(VERIFIED, kinds)

    def determinism():
        if not gpus:
            return check(UNVERIFIED, NO_TORCH_GPU_DETERMINISM + "; " + NO_GPU)
        if "determinism_refused" in probe:
            return check(FAILED, probe["determinism_refused"])
        active = probe.get("determinism") or {}
        differs = {k: active.get(k) for k, v in GPU_DETERMINISM if active.get(k) != v}
        if differs:
            return check(FAILED, differs)
        return check(VERIFIED, dict(GPU_DETERMINISM))

    return {
        "imports": guarded(imports),
        "devices": guarded(devices),
        "lock_versions": guarded(
            lambda: compare_versions(
                expected_for("pytorch_gpu", pins), probe["versions"]
            )
        ),
        "determinism_config": guarded(determinism),
        "rebuild": check(UNVERIFIED, NO_TORCH_GPU_REBUILD),
    }


def cell(image, checks):
    statuses = {c["status"] for c in checks.values()}
    status = UNVERIFIED
    if FAILED in statuses:
        status = FAILED
    elif statuses == {VERIFIED}:
        status = VERIFIED
    return {"image": image, "status": status, "checks": checks}


def matrix(records, manifests, *, gpus=False, expect_kind=None, pins=None):
    pins = pinned_versions() if pins is None else pins
    references = {kind: records[kind]["reference"] for kind in KINDS}
    return {
        "jax_cpu": cell("c03", jax_cpu(references, manifests, pins)),
        "jax_gpu": cell(
            "accelerator",
            jax_gpu(references, pins, gpus=gpus, expect_kind=expect_kind),
        ),
        "pytorch_cpu": cell("torch", pytorch_cpu(references, manifests, pins)),
        "pytorch_gpu": cell(
            "torch-gpu",
            pytorch_gpu(references, pins, gpus=gpus, expect_kind=expect_kind),
        ),
    }


def report(records, cells, *, gpus):
    first = records["c03"]
    return {
        "schema": SCHEMA,
        "release_tag": first["release_tag"],
        "source_commit": first["source_commit"],
        "gpu_host": gpus,
        "images": {kind: records[kind]["reference"] for kind in KINDS},
        "cells": cells,
        "reproducibility_tolerance": "HUMAN_INPUT",
        "a40_determinism_rerun": "GRANTED_NOT_RUN_HERE (#681)",
        "security_acceptance": "HUMAN_INPUT",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--gpus", action="store_true")
    parser.add_argument("--expect-device-kind")
    args = parser.parse_args(argv)
    records = {
        kind: json.loads(
            (args.records / f"{kind}-worker-image.release.json").read_text("utf-8")
        )
        for kind in KINDS
    }
    manifests = {kind: args.manifests / f"{kind}-worker-image.json" for kind in KINDS}
    cells = matrix(
        records, manifests, gpus=args.gpus, expect_kind=args.expect_device_kind
    )
    value = report(records, cells, gpus=args.gpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", "utf-8")
    for name, found in cells.items():
        print(f"{name}: {found['status']}")
    return 1 if any(c["status"] == FAILED for c in cells.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
