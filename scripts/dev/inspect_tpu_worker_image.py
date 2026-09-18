"""Bounded local package inspection, never a TPU execution/acceptance instrument."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

from carbon.reconstruction.accelerators import TPU_PROFILE
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    doctor,
    load_image_identity,
)
from carbon.reconstruction.worker.model import WorkerFailure

_PROGRAM = r"""
import hashlib, importlib.metadata, json, pathlib, platform, re, stat, sys
import carbon.reconstruction.service
import carbon.reconstruction.worker.protocol
from carbon.reconstruction.accelerators import TPU_PROFILE
assert not {"torch", "jax", "jaxlib", "libtpu"} & sys.modules.keys()
assert platform.python_version() == "3.11.16"
for name in ("worker-image-build.json", "accelerator-requirements.txt"):
    assert stat.S_IMODE(pathlib.Path("/opt/carbon", name).stat().st_mode) == 0o444
lock = pathlib.Path("/opt/carbon/accelerator-requirements.txt").read_bytes()
assert "sha256:" + hashlib.sha256(lock).hexdigest() == TPU_PROFILE.environment_lock_digest
pins = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([0-9.]+)", lock.decode(), re.MULTILINE))
assert pins and pins["libtpu"] == "0.0.42" and pins["jax"] == "0.10.2"
observed = {name: importlib.metadata.version(name) for name in pins}
assert observed == pins
assert not pathlib.Path("/scratch/cache").exists()
print(json.dumps({"python": platform.python_version(),
    "profile_digest": TPU_PROFILE.digest,
    "environment_lock_digest": TPU_PROFILE.environment_lock_digest,
    "distributions": observed, "numerical_backends_imported": False,
    "tpu_execution": "NOT_EXECUTED", "host_dispatch": "UNAVAILABLE",
    "build": json.loads(pathlib.Path("/opt/carbon/worker-image-build.json").read_bytes())},
    sort_keys=True))
"""


def _cleanup_instrument(cli, name):
    """Reconcile even an uncertain create response; never remove another owner."""
    try:
        value = cli.json(["inspect", name, "--format", "{{json .}}"])
    except WorkerFailure:
        remaining = cli.run(["ps", "--all", "--quiet", "--filter", f"name=^/{name}$"])
        if remaining.stdout.strip():
            raise ValueError("package container cleanup is uncertain") from None
        return
    if (
        value.get("Config", {}).get("Labels", {}).get("carbon.package.instrument")
        != name
    ):
        raise ValueError("package container ownership mismatch")
    cli.run(["rm", "--force", name], timeout=15)
    remaining = cli.run(["ps", "--all", "--quiet", "--filter", f"name=^/{name}$"])
    if remaining.stdout.strip():
        raise ValueError("package container release not confirmed")


def inspect(root: Path) -> dict:
    """Inspect one exact source build and remove only this diagnostic container."""
    manifest = root / ".carbon-artifacts/tpu-worker-image.json"
    identity = load_image_identity(manifest)
    cli = DockerCLI()
    checked = doctor(image_id=identity.image_id, image_identity=identity, cli=cli)
    if not checked.eligible:
        raise ValueError(f"base container doctor rejected: {checked.code}")
    source = subprocess.run(
        ["git", "-C", str(root), "archive", "--format=tar", "HEAD"],
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout
    if (
        identity.source_tree_digest != "sha256:" + hashlib.sha256(source).hexdigest()
        or identity.lock_digest != TPU_PROFILE.environment_lock_digest
    ):
        raise ValueError("source or TPU environment identity mismatch")
    name = "carbon-tpu-package-check-" + uuid.uuid4().hex
    try:
        cli.run(
            [
                "create",
                "--name",
                name,
                "--label",
                f"carbon.package.instrument={name}",
                "--network",
                "none",
                "--read-only",
                "--user",
                "65532:65532",
                "--memory",
                "512m",
                "--memory-swap",
                "512m",
                "--pids-limit",
                "64",
                "--cpus",
                "1",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges=true",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=64m",
                "--entrypoint",
                "/opt/carbon-worker/bin/python",
                identity.image_id,
                "-I",
                "-c",
                _PROGRAM,
            ],
            timeout=15,
        )
        controls = cli.json(["inspect", name, "--format", "{{json .}}"])
        host = controls["HostConfig"]
        if (
            host["NetworkMode"] != "none"
            or not host["ReadonlyRootfs"]
            or host["Privileged"]
            or host.get("DeviceRequests")
            or host.get("Devices")
            or host.get("Binds")
            or host["Memory"] != 512 * 1024**2
            or host["MemorySwap"] != 512 * 1024**2
            or host["PidsLimit"] != 64
            or controls["Config"]["User"] != "65532:65532"
        ):
            raise ValueError("package instrument controls mismatch")
        result = cli.run(["start", "--attach", name], timeout=30)
        report = json.loads(result.stdout)
        if report["profile_digest"] != TPU_PROFILE.digest:
            raise ValueError("installed profile mismatch")
        metadata = cli.json(
            ["image", "inspect", identity.image_id, "--format", "{{json .}}"]
        )
        report.update(
            image_identity=json.loads(manifest.read_bytes()),
            base_container_doctor=checked.code,
            image_size_bytes=metadata["Size"],
            instrument_controls={
                "network": "none",
                "read_only": True,
                "uid": 65532,
                "memory_bytes": host["Memory"],
                "pids": host["PidsLimit"],
                "devices": [],
                "deadline_seconds": 30,
            },
        )
    finally:
        _cleanup_instrument(cli, name)
    report["container_cleanup"] = "EXACT_CONTAINER_REMOVED_AND_ABSENCE_VERIFIED"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_checkout", type=Path)
    args = parser.parse_args(argv)
    root = args.source_checkout.resolve(strict=True)
    report = inspect(root)
    destination = root / ".carbon-artifacts/tpu-image-inspection.json"
    destination.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
