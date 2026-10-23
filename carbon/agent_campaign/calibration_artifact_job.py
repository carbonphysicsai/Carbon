"""Pod job: package one built model as a ``carbon.calibration-artifact.v1`` directory.

    python -m carbon.agent_campaign.calibration_artifact_job --out {out} \
        --recipe recipe.json --state state.npz --challenge-id f02 --version 2.3 \
        --bundle-ref catalog/x --bundle-sha256 sha256:... \
        --worker-image-digest sha256:... --parent-image-digest sha256:... \
        --runtime torch-cu130-py311 --train-sha256 sha256:... --seed 0 \
        --build-wall-s 812.5 --pod-id REF

It takes the files the pod's build step produced (the canonical recipe and the
trained state) and writes the artifact the calibration-grade tool verifies
(``carbon.challenge_validator.calibration_grade.load_artifact``): ``recipe.json``,
``state.npz``, ``manifest.json`` and ``SHA256SUMS``. The recipe's digest and the state's
sha256 are computed here from the bytes, never taken from a caller, so a manifest can
only describe the files beside it. The GPU model, driver and CUDA version are read from
``nvidia-smi`` when the runtime is a GPU one. The manifest carries no credentials,
account ids or balances: ``pod_id`` is a provider reference only, and every field is
closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "carbon.calibration-artifact.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PLAIN = re.compile(r"[A-Za-z0-9._:/+-]{1,128}")
_RUNTIMES = (
    "torch-cu130-py311",
    "jax-cuda13-py311",
    "torch-cpu-py311",
    "python-cpu-py311",
)
_GPU = ("torch-cu130-py311", "jax-cuda13-py311")


class ArtifactRefused(ValueError):
    pass


def _check(ok, code):
    if not ok:
        raise ArtifactRefused(code)


def gpu_facts(run=subprocess.run):
    """``(gpu_model, driver, cuda)`` from nvidia-smi, or refuses."""
    try:
        listed = run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout.splitlines()
        banner = run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=30, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ArtifactRefused("gpu_facts_unavailable") from exc
    name, _, driver = (listed[0] if listed else "").partition(",")
    found = re.search(r"CUDA Version:\s*([0-9.]+)", banner)
    _check(name.strip() and driver.strip() and found, "gpu_facts_unavailable")
    return name.strip(), driver.strip(), found.group(1)


def write_artifact(
    out,
    *,
    recipe_bytes,
    state_bytes,
    challenge_id,
    version,
    bundle_ref,
    bundle_sha256,
    worker_image_digest,
    parent_image_digest,
    runtime,
    train_sha256,
    seed,
    build_wall_s,
    pod_id,
    gpu=None,
    now=None,
):
    """Write the four files into the new directory ``out`` and return the manifest."""
    _check(runtime in _RUNTIMES, "runtime")
    for value, code in (
        (bundle_sha256, "bundle_sha256"),
        (worker_image_digest, "worker_image_digest"),
        (parent_image_digest, "parent_image_digest"),
        (train_sha256, "train_sha256"),
    ):
        _check(type(value) is str and _DIGEST.fullmatch(value), code)
    for value, code in (
        (challenge_id, "challenge_id"),
        (version, "version"),
        (bundle_ref, "bundle_ref"),
        (pod_id, "pod_id"),
    ):
        _check(type(value) is str and _PLAIN.fullmatch(value), code)
    _check(type(seed) is int and seed >= 0, "seed")
    _check(
        type(build_wall_s) in (int, float) and 0 <= build_wall_s < 10**7,
        "build_wall_s",
    )
    _check(
        type(recipe_bytes) is bytes
        and type(state_bytes) is bytes
        and recipe_bytes
        and state_bytes,
        "files",
    )
    json.loads(recipe_bytes)
    if runtime in _GPU:
        model, driver, cuda = gpu or gpu_facts()
    else:
        model, driver, cuda = "none", "none", "none"
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "schema": SCHEMA,
        "challenge_id": challenge_id,
        "version": version,
        "recipe_digest": "sha256:" + hashlib.sha256(recipe_bytes).hexdigest(),
        "state_sha256": "sha256:" + hashlib.sha256(state_bytes).hexdigest(),
        "bundle_ref": bundle_ref,
        "bundle_sha256": bundle_sha256,
        "worker_image_digest": worker_image_digest,
        "parent_image_digest": parent_image_digest,
        "runtime": runtime,
        "gpu_model": model,
        "driver": driver,
        "cuda": cuda,
        "train_sha256": train_sha256,
        "seed": seed,
        "build_wall_s": float(build_wall_s),
        "pod_id": pod_id,
        "built_at": stamp,
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    files = {
        "recipe.json": recipe_bytes,
        "state.npz": state_bytes,
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True).encode()
        + b"\n",
    }
    for name, raw in files.items():
        (out / name).write_bytes(raw)
    (out / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(r).hexdigest()}  {n}\n" for n, r in files.items()),
        encoding="utf-8",
    )
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    for name in (
        "challenge-id",
        "version",
        "bundle-ref",
        "bundle-sha256",
        "worker-image-digest",
        "parent-image-digest",
        "runtime",
        "train-sha256",
        "pod-id",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--build-wall-s", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = write_artifact(
            args.out,
            recipe_bytes=args.recipe.read_bytes(),
            state_bytes=args.state.read_bytes(),
            challenge_id=args.challenge_id,
            version=args.version,
            bundle_ref=args.bundle_ref,
            bundle_sha256=args.bundle_sha256,
            worker_image_digest=args.worker_image_digest,
            parent_image_digest=args.parent_image_digest,
            runtime=args.runtime,
            train_sha256=args.train_sha256,
            seed=args.seed,
            build_wall_s=args.build_wall_s,
            pod_id=args.pod_id,
        )
    except (ArtifactRefused, ValueError, OSError) as exc:
        print(f"calibration artifact refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"recipe_digest": manifest["recipe_digest"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
