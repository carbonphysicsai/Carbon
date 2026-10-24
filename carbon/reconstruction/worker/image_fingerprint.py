"""A Docker image's store-neutral fingerprint, in one place (R8-6, and the C-03 parent on a containerd store).

A containerd image store (Docker 29) addresses an image by its manifest/index digest, a classic store by its config
digest, so one pinned image has two ids. Neither store's `docker image inspect` gives the other's id. Both give the layer
digests and the run configuration, and the sha256 of those identifies the image's bytes and its run configuration
exactly. The remote worker check and the local parent check use this one format and this one function: there is no second
fingerprint format.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

FINGERPRINT_FORMAT = (
    "{{json .RootFS.Layers}} {{json .Config.Env}} {{json .Config.Labels}} "
    "{{json .Config.Entrypoint}} {{json .Config.Cmd}} {{json .Config.User}} "
    "{{json .Config.WorkingDir}} {{.Os}} {{.Architecture}} {{.Created}}"
)
PARENT_TAG = re.compile(r"^carbon-c03-worker:[0-9a-f]{16}$")
SIDECAR_NAME = "store-fingerprint.json"
SIDECAR_SCHEMA = "carbon.worker-store-fingerprint.v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def fingerprint(reference: str, *, docker: str = "docker") -> str | None:
    """The fingerprint of the image `reference` names in this machine's Docker, or None when it cannot be read."""
    try:
        completed = subprocess.run(  # fixed argv, no shell
            [docker, "image", "inspect", "--format", FINGERPRINT_FORMAT, reference],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return hashlib.sha256(completed.stdout).hexdigest()


def fingerprint_of_output(stdout: bytes) -> str:
    """The same fingerprint from the bytes `docker image inspect --format FINGERPRINT_FORMAT` printed."""
    return hashlib.sha256(stdout).hexdigest()


def sidecar_path(manifest: Path) -> Path:
    """Where the install records a manifest's parent fingerprint: beside the manifest, never inside it."""
    return Path(manifest).with_name(SIDECAR_NAME)


def write_sidecar(
    manifest: Path, *, parent_image_id: str, tag: str, value: str
) -> Path:
    """Record, at install, the fingerprint of the parent image found under `tag`."""
    if not PARENT_TAG.fullmatch(tag) or not _HEX64.fullmatch(value):
        raise ValueError("a parent tag and a sha256 fingerprint are required")
    path = sidecar_path(manifest)
    path.write_text(
        json.dumps(
            {
                "schema": SIDECAR_SCHEMA,
                "parent_image_id": parent_image_id,
                "tag": tag,
                "fingerprint": value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def read_sidecar(manifest: Path, parent_image_id: str) -> tuple[str, str] | None:
    """(tag, fingerprint) recorded for `parent_image_id`, or None: absent, malformed or for another image."""
    try:
        value = json.loads(sidecar_path(manifest).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    if (
        type(value) is not dict
        or set(value) != {"schema", "parent_image_id", "tag", "fingerprint"}
        or value["schema"] != SIDECAR_SCHEMA
        or value["parent_image_id"] != parent_image_id
        or type(value["tag"]) is not str
        or not PARENT_TAG.fullmatch(value["tag"])
        or type(value["fingerprint"]) is not str
        or not _HEX64.fullmatch(value["fingerprint"])
    ):
        return None
    return value["tag"], value["fingerprint"]
