"""Where the installer put this machine's pinned images (C-MLP-04).

`scripts/install_miner.sh` builds the worker and analysis images, and with
`--gpu` the GPU worker, on the miner's own machine. It records their manifest
paths here, owner-only, in the Control Center's state directory, so setup can
fill them in rather than asking a miner to find them. A record names local
paths only; nothing in it is secret, and setup still verifies every image.
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

SCHEMA = "carbon.launchpad.installed-images.v1"
FILE = "installed-images.json"
FIELDS = ("image_manifest", "analysis_image_manifest", "gpu_image_manifest")
#: Where `scripts/dev/accelerator_worker_image.sh` writes the GPU worker's
#: manifest by default. A miner whose controller has no GPU builds it with
#: that script for their remote setup (`install_miner.sh --gpu` checks for a
#: local NVIDIA driver first), and setup still finds it.
GPU_DEFAULT = ".carbon-artifacts/accelerator-worker-image.json"
#: The one command that builds each image, named when setup finds none: the
#: script in the checkout and its arguments.
BUILD = {
    "image_manifest": ("scripts/install_miner.sh", "--no-start"),
    "analysis_image_manifest": ("scripts/install_miner.sh", "--no-start"),
    "gpu_image_manifest": ("scripts/dev/accelerator_worker_image.sh",),
}


def write(
    state_dir, *, image_manifest, analysis_image_manifest, gpu_image_manifest=None
):
    from scripts.dev.miner_launchpad.environment_setup import write_private

    record = {"schema": SCHEMA}
    for field, value in zip(
        FIELDS, (image_manifest, analysis_image_manifest, gpu_image_manifest)
    ):
        if value is None:
            continue
        path = Path(value).resolve()
        if not path.is_file():
            raise SystemExit(f"{field}: no image manifest at {path}")
        record[field] = str(path)
    return write_private(
        Path(state_dir) / FILE, json.dumps(record, sort_keys=True).encode()
    )


def read(state_dir):
    """The recorded image manifests that still exist, or None."""
    path = Path(state_dir) / FILE
    try:
        if path.is_symlink() or path.stat().st_size > 8192:
            return None
        record = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    if type(record) is not dict or record.get("schema") != SCHEMA:
        return None
    found = {
        field: record[field]
        for field in FIELDS
        if type(record.get(field)) is str
        and Path(record[field]).is_absolute()
        and Path(record[field]).is_file()
    }
    return found or None


def found(state_dir, repo) -> dict:
    """Each image setup can fill in: its path and who recorded it, or none
    and the one command, from the checkout `repo`, that builds it.

    The installer's record comes first. Only the GPU worker is also looked
    for where its build script writes it; setup verifies every image anyway.
    """
    recorded = read(state_dir) or {}
    images = {}
    for field in FIELDS:
        path, by = recorded.get(field), "install_miner.sh"
        if path is None and field == "gpu_image_manifest":
            default = Path(repo) / GPU_DEFAULT
            if default.is_file() and not default.is_symlink():
                path, by = str(default), "accelerator_worker_image.sh"
        script, *arguments = BUILD[field]
        images[field] = {
            "path": path,
            "found_by": by if path else None,
            "build": " ".join([shlex.quote(str(Path(repo) / script)), *arguments]),
        }
    return images


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("write")
    record.add_argument("--state-dir", type=Path, required=True)
    record.add_argument("--image-manifest", required=True)
    record.add_argument("--analysis-image-manifest", required=True)
    record.add_argument("--gpu-image-manifest")
    args = parser.parse_args(argv)
    path = write(
        args.state_dir,
        image_manifest=args.image_manifest,
        analysis_image_manifest=args.analysis_image_manifest,
        gpu_image_manifest=args.gpu_image_manifest,
    )
    print(f"Recorded the installed images for setup: {path}")


if __name__ == "__main__":
    main()
