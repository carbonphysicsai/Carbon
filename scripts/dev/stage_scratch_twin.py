"""Stage a catalog entry's GPU twin into a SCRATCH library cache, building and tagging nothing (owner-run).

    python -m scripts.dev.stage_scratch_twin --scratch-state-dir DIR --torch-gpu-manifest FILE
        [--gpu-manifest FILE] [--wheelhouse DIR] CATALOG_ID...

For measurement on a host that already has a recorded install (the 4090 validator): the GPU practice prepares an
entry's GPU overlay from the twin's pinned material in the cache it is given (`gpu_practice.gpu_overlay`), so all it needs
is that material staged. This command copies exactly that, inertly, into a NEW scratch state directory and prints the
cache root to pass to `practice_grade_entry.py --gpu-cache-root`. It uses the GPU worker identities the install already
recorded (the manifests you name; their runtimes decide which twin is staged) and nothing else:

- it builds no worker, parent or child image and runs no `docker` command (it reads two manifest files and copies
  files; the test holds that by making any subprocess or `os.system` call fail);
- it creates and moves no tag, so a second install of the same source tree on the same daemon cannot collide with it;
- it writes only under the scratch directory (refused if that is a link or an existing non-directory).

Reads no sealed material. The overlay itself is prepared later, by the practice, in a controlled operation on the GPU
and sealed in this scratch cache (never in the install's own cache).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from carbon.backbone_catalog import pipeline
from scripts.dev import catalog_wheelhouse, library_bundle

CACHE_PARTS = ("environment", "campaigns", ".direct-development", "library-cache")


def cache_root_of(scratch_state_dir):
    """Where `library_bundle.stage_bundle` puts material for this state directory."""
    return Path(scratch_state_dir).joinpath(*CACHE_PARTS)


def runtimes_of(manifests, *, load_identity=None, runtime_of=None):
    """The GPU runtimes of the recorded worker manifests, in the order given."""
    if load_identity is None:
        from carbon.reconstruction.worker.docker_runtime import load_image_identity

        def load_identity(path):
            return load_image_identity(Path(path))

    if runtime_of is None:
        from carbon.development_session.gpu_practice import gpu_runtime

        runtime_of = gpu_runtime
    found = []
    for path in manifests:
        runtime = runtime_of(load_identity(path))
        if runtime is None:
            raise ValueError(f"{path} names no registered GPU worker")
        if runtime not in found:
            found.append(runtime)
    return found


def stage(
    catalog_ids,
    *,
    scratch_state_dir,
    runtimes,
    wheelhouse=None,
    catalog=None,
    stage_bundle=None,
):
    """Stage each entry's twin material for each runtime it has a build for; returns the report."""
    if not catalog_ids:
        raise ValueError("name at least one catalog entry")
    scratch = Path(scratch_state_dir)
    if scratch.is_symlink() or (scratch.exists() and not scratch.is_dir()):
        raise ValueError("the scratch state directory must be a directory, not a link")
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    catalog = catalog if catalog is not None else pipeline.load()["entries"]
    stage_bundle = stage_bundle or library_bundle.stage_bundle
    if wheelhouse is None and catalog_wheelhouse.DEFAULT_DIRECTORY.is_dir():
        wheelhouse = catalog_wheelhouse.DEFAULT_DIRECTORY
    by_id = {item["catalog_id"]: item for item in catalog}
    unknown = sorted(set(catalog_ids) - set(by_id))
    if unknown:
        raise ValueError("not in the catalog: " + ", ".join(unknown))
    staged, skipped = [], []
    for catalog_id in catalog_ids:
        item = by_id[catalog_id]
        for runtime in runtimes:
            if runtime not in (item.get("bundle_refs") or {}):
                skipped.append(
                    {
                        "catalog_id": catalog_id,
                        "runtime": runtime,
                        "reason": "no_twin_for_runtime",
                    }
                )
                continue
            with tempfile.TemporaryDirectory() as work:
                directory = pipeline.twin_directory(
                    item, runtime, Path(work) / "twin", wheelhouse=wheelhouse
                )
                result = stage_bundle(directory, state_dir=scratch)
            staged.append(
                {
                    "catalog_id": catalog_id,
                    "runtime": runtime,
                    "bundle_digest": result["bundle_ref"]["bundle_digest"],
                    "image_status": result["image_status"],
                }
            )
    return {
        "scratch_state_dir": str(scratch),
        "cache_root": str(cache_root_of(scratch)),
        "staged": staged,
        "skipped": skipped,
        "docker_commands_run": 0,
        "images_built": 0,
        "tags_created_or_moved": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("catalog_id", nargs="+")
    parser.add_argument("--scratch-state-dir", type=Path, required=True)
    parser.add_argument("--torch-gpu-manifest", type=Path)
    parser.add_argument(
        "--gpu-manifest", type=Path, help="the JAX accelerator worker's manifest"
    )
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args(argv)
    manifests = [m for m in (args.torch_gpu_manifest, args.gpu_manifest) if m]
    if not manifests:
        parser.error(
            "name --torch-gpu-manifest and/or --gpu-manifest (the install's recorded GPU workers)"
        )
    report = stage(
        args.catalog_id,
        scratch_state_dir=args.scratch_state_dir,
        runtimes=runtimes_of(manifests),
        wheelhouse=args.wheelhouse,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if not report["staged"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
