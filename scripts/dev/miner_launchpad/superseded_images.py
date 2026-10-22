"""Carbon's own images from earlier installs, which this install no longer
records (M1 E2E R6-1).

Every install builds or pulls new worker and analysis images and records
them; the earlier ones stay in Docker. Over a few updates they filled the
disk until an update stopped at its own space check. `scripts/install_miner.sh`
lists them here and removes them only on the miner's yes.

What counts, and nothing else:
- an image tagged in one of Carbon's own repositories (`REPOSITORIES`, or
  Carbon's release registry `RELEASE_PREFIX`);
- whose image ID no record of the current install names: not the images
  setup's installer record points to, not the manifests the installer
  writes under `.carbon-artifacts/`, and not any image either names as a
  parent.
Another program's image is never listed. A tag is removed with
`docker image rm` without force, so Docker refuses an image a container
still uses, and that refusal is reported, not overridden.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

#: The local repositories Carbon's image scripts tag (`c03_worker_image.sh`,
#: `torch_worker_image.sh`, `accelerator_worker_image.sh`,
#: `research_image.LOCAL_ANALYSIS_REPOSITORY` and its parent tag).
REPOSITORIES = (
    "carbon-c03-worker",
    "carbon-torch-worker",
    "carbon-gpu-worker",
    "carbon-analysis",
    "carbon-cw1d4-parent",
)
#: Carbon's released images (`worker_image_release.py pull`).
RELEASE_PREFIX = "ghcr.io/carbonphysicsai/"
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")


def _docker(*argv):
    return subprocess.run(
        ["docker", *argv], capture_output=True, text=True, timeout=120, check=False
    )


def kept(state_dir, repo) -> set[str]:
    """Every image ID a record of the current install names: the manifests
    setup's installer record points to and the installer's own manifests,
    with any parent image they name."""
    from scripts.dev.miner_launchpad import installed

    paths = [Path(p) for p in (installed.read(Path(state_dir)) or {}).values()]
    artifacts = Path(repo) / ".carbon-artifacts"
    if artifacts.is_dir():
        paths += sorted(artifacts.glob("*.json"))
        paths += sorted(artifacts.glob("*/*-worker-image.json"))
    ids = set()
    for path in paths:
        try:
            ids |= set(_IMAGE_ID.findall(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return ids


def ours(repository: str) -> bool:
    return repository in REPOSITORIES or repository.startswith(RELEASE_PREFIX)


def superseded(state_dir, repo, docker=_docker) -> list[dict]:
    """Carbon's tagged images the current install does not name, as
    [{ref, id, size}], in Docker's order. [] when Docker cannot list."""
    listed = docker("image", "ls", "--no-trunc", "--format", "{{json .}}")
    if listed.returncode != 0:
        return []
    keep = kept(state_dir, repo)
    found = []
    for line in listed.stdout.splitlines():
        try:
            image = json.loads(line)
        except ValueError:
            continue
        repository, tag = image.get("Repository", ""), image.get("Tag", "")
        if not ours(repository) or tag in ("", "<none>"):
            continue
        if image.get("ID") in keep:
            continue
        found.append(
            {
                "ref": repository + ":" + tag,
                "id": image.get("ID"),
                "size": image.get("Size", "?"),
            }
        )
    return found


def remove(images, docker=_docker) -> list[tuple[str, str | None]]:
    """Remove each tag, without force: [(ref, None)] when removed, or
    [(ref, why)] when Docker refused it."""
    done = []
    for image in images:
        result = docker("image", "rm", image["ref"])
        done.append(
            (
                image["ref"],
                None if result.returncode == 0 else result.stderr.strip()[:200],
            )
        )
    return done


def main(argv=None, docker=_docker) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("list", "remove"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args(argv)
    images = superseded(args.state_dir, args.repo, docker)
    if args.command == "list":
        for image in images:
            print(f"  {image['ref']}  ({image['size']})")
        return 0
    refused = 0
    for ref, why in remove(images, docker):
        if why is None:
            print(f"  removed {ref}")
        else:
            refused += 1
            print(f"  kept {ref}: {why}")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
