"""Carbon's own images and containers from earlier installs, which this
install no longer uses (M1 E2E R6-1, R11-2).

Every install builds or pulls new worker and analysis images and records
them; the earlier ones stay in Docker, and so do the catalog images built
over an earlier worker and the containers finished practice jobs leave.
Over a few updates they filled the disk until an update stopped at its own
space check. `scripts/install_miner.sh` lists them here, with how much each
kind frees, and removes them only on the miner's yes.

What counts, and nothing else:
- an image tagged in one of Carbon's own repositories (`REPOSITORIES`, or
  Carbon's release registry `RELEASE_PREFIX`) whose image ID no record of
  the current install names: not the images setup's installer record points
  to, not the manifests the installer writes under `.carbon-artifacts/`, and
  not any image either names as a parent;
- a catalog image (labelled `LIBRARY_LABEL`, as the catalog install builds
  it) built over a construction parent the current install no longer names
  (`PARENT_LABEL`); the update builds the catalog again over the new one;
- an exited container of a Carbon practice job (labelled `JOB_LABEL`).
Another program's image or container is never listed. Each is removed
without force: Docker refuses an image a container still uses, and that
refusal is reported, not overridden. A running container is never listed.

The catalog images the current install DOES name are a separate offer (`current_catalog`,
`--remove-catalog-images`): an update builds them again over the new worker, so a space-short
update may remove them first, on its own yes, and they are built again afterwards.

Docker's own build cache is never touched here: it is shared by every Docker build on this machine, and
Carbon never removes anything it did not tag.
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
#: `torch_gpu_worker_image.sh`, `research_image.LOCAL_ANALYSIS_REPOSITORY`
#: and its parent tag, and the catalog build's parent stage tag).
REPOSITORIES = (
    "carbon-c03-worker",
    "carbon-torch-worker",
    "carbon-gpu-worker",
    "carbon-torch-gpu-worker",
    "carbon-analysis",
    "carbon-cw1d4-parent",
    "carbon-library-parent",
)
#: Carbon's released images (`worker_image_release.py pull`).
RELEASE_PREFIX = "ghcr.io/carbonphysicsai/"
#: The labels the catalog install puts on each catalog image
#: (`library_bundles`): the bundle, and the construction parent it is built
#: over.
LIBRARY_LABEL = "org.opencontainers.image.carbon.development.library-bundle"
PARENT_LABEL = "org.opencontainers.image.carbon.development.parent"
#: The label every Carbon practice job's container carries
#: (`docker_runtime`'s worker containers).
JOB_LABEL = "org.opencontainers.image.carbon.c03.launch"
#: Each kind, in the order it is removed (containers first: they hold images).
KINDS = {
    "container": "practice job containers that finished",
    "catalog": "catalog images built over an earlier worker",
    "image": "Carbon images from earlier installs",
}
#: The catalog images the current install names, which an update builds again: its own kind and its own offer.
CURRENT_CATALOG_WORDS = "catalog images this update builds again"
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_SIZE = re.compile(r"([0-9.]+)\s*([kKMGT]?B)")
_UNITS = {"B": 1, "kB": 1e3, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}


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


def size_bytes(text) -> int:
    """Docker's human size ("1.2GB"; a container's "0B (virtual 1GB)" is its
    own first part), in bytes; 0 when unreadable."""
    found = _SIZE.search(str(text or ""))
    if found is None:
        return 0
    return int(float(found.group(1)) * _UNITS.get(found.group(2), 0))


def human(count) -> str:
    for unit, scale in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if count >= scale:
            return f"{count / scale:.1f}{unit}"
    return f"{count}B"


def _lines(result):
    if result.returncode != 0:
        return []
    found = []
    for line in result.stdout.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if type(value) is dict:
            found.append(value)
    return found


def superseded(state_dir, repo, docker=_docker) -> list[dict]:
    """Carbon's images and containers the current install does not use, as
    [{kind, ref, id, size}] in removal order; [] when Docker cannot list."""
    keep = kept(state_dir, repo)
    found = []
    containers = _lines(
        docker(
            "ps",
            "--all",
            "--no-trunc",
            "--size",
            "--filter",
            "label=" + JOB_LABEL,
            "--filter",
            "status=exited",
            "--format",
            "{{json .}}",
        )
    )
    for container in containers:
        found.append(
            {
                "kind": "container",
                "ref": container.get("Names") or container.get("ID"),
                "id": container.get("ID"),
                "size": container.get("Size", "0B"),
            }
        )
    catalog = _lines(
        docker(
            "image",
            "ls",
            "--no-trunc",
            "--filter",
            "label=" + LIBRARY_LABEL,
            "--format",
            "{{json .}}",
        )
    )
    seen = set()
    for image in catalog:
        image_id = image.get("ID")
        if image_id in seen or image_id in keep:
            continue
        seen.add(image_id)
        inspected = docker(
            "image", "inspect", "--format", "{{json .Config.Labels}}", image_id
        )
        try:
            labels = json.loads(inspected.stdout) if inspected.returncode == 0 else {}
        except ValueError:
            labels = {}
        parent = (labels or {}).get(PARENT_LABEL)
        if type(labels) is not dict or not labels.get(LIBRARY_LABEL) or parent in keep:
            continue
        found.append(
            {
                "kind": "catalog",
                "ref": image_id,
                "id": image_id,
                "size": image.get("Size", "?"),
            }
        )
    for image in _lines(docker("image", "ls", "--no-trunc", "--format", "{{json .}}")):
        repository, tag = image.get("Repository", ""), image.get("Tag", "")
        if not ours(repository) or tag in ("", "<none>"):
            continue
        if image.get("ID") in keep or image.get("ID") in seen:
            continue
        found.append(
            {
                "kind": "image",
                "ref": repository + ":" + tag,
                "id": image.get("ID"),
                "size": image.get("Size", "?"),
            }
        )
    return found


def current_catalog(state_dir, repo, docker=_docker) -> list[dict]:
    """The catalog images (labelled `LIBRARY_LABEL`) that `superseded` does not list because the current install names
    them or their parent: [{kind: "catalog_current", ref, id, size}]. An update builds them again over the new worker;
    only the miner's own yes removes them, never `superseded`'s offer."""
    listed = {item["id"] for item in superseded(state_dir, repo, docker)}
    found, seen = [], set()
    for image in _lines(
        docker(
            "image",
            "ls",
            "--no-trunc",
            "--filter",
            "label=" + LIBRARY_LABEL,
            "--format",
            "{{json .}}",
        )
    ):
        image_id = image.get("ID")
        if not image_id or image_id in seen or image_id in listed:
            continue
        seen.add(image_id)
        found.append(
            {
                "kind": "catalog_current",
                "ref": image_id,
                "id": image_id,
                "size": image.get("Size", "?"),
            }
        )
    return found


def totals(found) -> dict:
    """{kind: (count, bytes)} of what `superseded` lists."""
    result = {}
    for item in found:
        count, total = result.get(item["kind"], (0, 0))
        result[item["kind"]] = (count + 1, total + size_bytes(item["size"]))
    return result


def remove(found, docker=_docker) -> list[tuple[str, str | None]]:
    """Remove each, without force: [(ref, None)] when removed, or
    [(ref, why)] when Docker refused it."""
    done = []
    for item in found:
        if item["kind"] == "container":
            command = ("rm", item["id"])
        else:
            command = ("image", "rm", item["ref"])
        result = docker(*command)
        done.append(
            (
                item["ref"],
                None if result.returncode == 0 else result.stderr.strip()[:200],
            )
        )
    return done


def main(argv=None, docker=_docker) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "command", choices=("list", "remove", "catalog-list", "catalog-remove")
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command in ("catalog-list", "catalog-remove"):
        current = current_catalog(args.state_dir, args.repo, docker)
        if args.command == "catalog-list":
            if current:
                total = sum(size_bytes(item["size"]) for item in current)
                print(
                    f"  {CURRENT_CATALOG_WORDS}: {len(current)}, frees about {human(total)}"
                )
            return 0
        refused = 0
        for ref, why in remove(current, docker):
            if why is None:
                print(f"  removed {ref}")
            else:
                refused += 1
                print(f"  kept {ref}: {why}")
        return 1 if refused else 0
    found = superseded(args.state_dir, args.repo, docker)
    if args.command == "list":
        for item in found:
            print(f"  {item['ref']}  ({item['size']})")
        summary = totals(found)
        for kind, words in KINDS.items():
            if kind in summary:
                count, total = summary[kind]
                print(f"  {words}: {count}, frees about {human(total)}")
        return 0
    refused = 0
    for ref, why in remove(found, docker):
        if why is None:
            print(f"  removed {ref}")
        else:
            refused += 1
            print(f"  kept {ref}: {why}")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
