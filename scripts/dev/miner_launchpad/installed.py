"""Where the installer put this machine's pinned images (C-MLP-04).

`scripts/install_miner.sh` builds the worker and analysis images, and with
`--gpu` the GPU worker, on the miner's own machine. It records their manifest
paths here, owner-only, in the Control Center's state directory, so setup can
fill them in rather than asking a miner to find them. A record names local
paths only; nothing in it is secret, and setup still verifies every image.

With `--release TAG` the installer pulls Carbon's released images by digest
instead of building them (OWNER-WORKER-IMAGES-V2-01), and also records the
GPU worker's release record, so remote setup can name the released reference
a container is started from (`released_gpu`).
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

SCHEMA = "carbon.launchpad.installed-images.v1"
FILE = "installed-images.json"
FIELDS = ("image_manifest", "analysis_image_manifest", "gpu_image_manifest")
#: The released GPU worker's record (`carbon.worker-image-release.v1`), kept
#: beside the image manifests but never read as one: `read` returns FIELDS only.
GPU_RELEASE_RECORD = "gpu_release_record"
#: The release kind of the GPU worker remote setup uses.
GPU_RELEASE_KIND = "accelerator"
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
    state_dir,
    *,
    image_manifest,
    analysis_image_manifest,
    gpu_image_manifest=None,
    gpu_release_record=None,
):
    from scripts.dev.miner_launchpad.environment_setup import write_private

    record = {"schema": SCHEMA}
    for field, value in zip(
        (*FIELDS, GPU_RELEASE_RECORD),
        (
            image_manifest,
            analysis_image_manifest,
            gpu_image_manifest,
            gpu_release_record,
        ),
    ):
        if value is None:
            continue
        path = Path(value).resolve()
        if not path.is_file():
            raise SystemExit(f"{field}: no file at {path}")
        record[field] = str(path)
    return write_private(
        Path(state_dir) / FILE, json.dumps(record, sort_keys=True).encode()
    )


def _recorded(state_dir, fields):
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
        for field in fields
        if type(record.get(field)) is str
        and Path(record[field]).is_absolute()
        and Path(record[field]).is_file()
    }
    return found or None


def read(state_dir):
    """The recorded image manifests that still exist, or None."""
    return _recorded(state_dir, FIELDS)


def released_gpu(state_dir, gpu_manifest) -> dict | None:
    """The released GPU worker a container can be started from, or None.

    Named only when the installer recorded the GPU worker's release record,
    the record passes every check `worker_image_release` makes, and
    `gpu_manifest`, the GPU worker setup found, is byte-for-byte that
    release's manifest: so the reference names the very worker setup checks
    the container's build identity against. Anything else is None, and setup
    offers the push helper as before.
    """
    from scripts.dev import worker_image_release as release

    path = (_recorded(state_dir, (GPU_RELEASE_RECORD,)) or {}).get(GPU_RELEASE_RECORD)
    if path is None or gpu_manifest is None:
        return None
    try:
        record = release.check_record(json.loads(Path(path).read_text("utf-8")))
        manifest = Path(gpu_manifest).read_text("utf-8")
    except (OSError, ValueError, release.Refused):
        return None
    if record["kind"] != GPU_RELEASE_KIND or manifest != release.canonical(
        record["manifest"]
    ):
        return None
    return {"release_tag": record["release_tag"], "reference": record["reference"]}


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


#: The label every image built on the C-03 worker carries: the source tree it
#: was built from (`.devcontainer/Dockerfile.reconstruction-worker`). The GPU
#: worker inherits it from its parent.
SOURCE_TREE_LABEL = "org.opencontainers.image.carbon.c03.source-tree"


def current(manifest, *, implementation=None, cli=None) -> bool:
    """Whether the worker manifest `manifest` (the C-03 worker's or the GPU
    worker's) names an image built from this checkout's exact source tree
    that Docker still holds, so an install can use it again rather than
    build it again (LA-F16).

    Two installs share one checkout, and so its manifests at fixed paths. A
    rebuild at the same revision is a new image with a new id, so a second
    install that rebuilt would change the first one's record under it. The
    test is setup's own (`verify_current_worker`), plus the image itself:
    Docker holds that image id, and its source-tree label is the manifest's.
    Anything else, or any error, is False, and the install builds as before.
    `implementation` is `accepted_implementation` of this checkout's HEAD,
    worked out when not given.
    """
    from carbon.development_session.research_campaign import (
        accepted_implementation,
        verify_current_worker,
    )
    from carbon.reconstruction.worker.docker_runtime import (
        DockerCLI,
        load_image_identity,
    )

    path = Path(manifest)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
            return False
        image = load_image_identity(path)
        if implementation is None:
            import subprocess

            repo = Path(__file__).resolve().parents[3]
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True, timeout=30
            ).strip()
            implementation = accepted_implementation(head)
        verify_current_worker(image, implementation)
        metadata = (cli or DockerCLI()).json(
            ["image", "inspect", image.image_id, "--format", "{{json .}}"]
        )
        labels = (metadata.get("Config") or {}).get("Labels") or {}
        return (
            metadata.get("Id") == image.image_id
            and labels.get(SOURCE_TREE_LABEL) == image.source_tree_digest
        )
    except Exception:  # noqa: BLE001 - any doubt builds the image again.
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("write")
    record.add_argument("--state-dir", type=Path, required=True)
    record.add_argument("--image-manifest", required=True)
    record.add_argument("--analysis-image-manifest", required=True)
    record.add_argument("--gpu-image-manifest")
    record.add_argument("--gpu-release-record")
    reuse = commands.add_parser("current")
    reuse.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "current":
        print("yes" if current(args.manifest) else "no")
        return
    path = write(
        args.state_dir,
        image_manifest=args.image_manifest,
        analysis_image_manifest=args.analysis_image_manifest,
        gpu_image_manifest=args.gpu_image_manifest,
        gpu_release_record=args.gpu_release_record,
    )
    print(f"Recorded the installed images for setup: {path}")


if __name__ == "__main__":
    main()
