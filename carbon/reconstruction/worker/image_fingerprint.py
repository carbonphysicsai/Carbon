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
import os
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
SIDECAR_SCHEMA = "carbon.worker-store-fingerprint.v2"
#: The install's parent aliases, readable at dispatch without the manifest's path: recorded image id ->
#: (exact tag, store-neutral fingerprint). Owner-only; it vouches for nothing by itself (the live image must
#: still have exactly the recorded fingerprint).
ALIASES_NAME = "parent-aliases.json"
ALIASES_SCHEMA = "carbon.worker-parent-aliases.v1"
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
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


def manifest_sha256(manifest: Path) -> str:
    """The sha256 of the identity manifest's exact bytes: what a sidecar is bound to."""
    return hashlib.sha256(Path(manifest).read_bytes()).hexdigest()


def _current_manifest_sha(manifest: Path) -> str | None:
    try:
        return manifest_sha256(manifest)
    except OSError:
        return None


def write_sidecar(
    manifest: Path, *, parent_image_id: str, tag: str, value: str
) -> Path:
    """Record, at install, the fingerprint of the parent image found under `tag`, bound to the exact manifest it vouches
    for (so a stale or copied sidecar cannot vouch for another image) and written owner-only (0600).
    """
    if not PARENT_TAG.fullmatch(tag) or not _HEX64.fullmatch(value):
        raise ValueError("a parent tag and a sha256 fingerprint are required")
    path = sidecar_path(manifest)
    document = (
        json.dumps(
            {
                "schema": SIDECAR_SCHEMA,
                "manifest_sha256": manifest_sha256(manifest),
                "parent_image_id": parent_image_id,
                "tag": tag,
                "fingerprint": value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    path.unlink(missing_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(document)
    return path


def read_sidecar(manifest: Path, parent_image_id: str) -> tuple[str, str] | None:
    """(tag, fingerprint) recorded for `parent_image_id` on exactly this manifest, or None: absent, malformed, for another
    image, or bound to a different manifest (a stale or copied sidecar vouches for nothing).
    """
    try:
        value = json.loads(sidecar_path(manifest).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    if (
        type(value) is not dict
        or set(value)
        != {"schema", "manifest_sha256", "parent_image_id", "tag", "fingerprint"}
        or value["schema"] != SIDECAR_SCHEMA
        or value["manifest_sha256"] != _current_manifest_sha(manifest)
        or value["parent_image_id"] != parent_image_id
        or type(value["tag"]) is not str
        or not PARENT_TAG.fullmatch(value["tag"])
        or type(value["fingerprint"]) is not str
        or not _HEX64.fullmatch(value["fingerprint"])
    ):
        return None
    return value["tag"], value["fingerprint"]


def default_state_dir() -> Path:
    """The miner's Launchpad state directory (the one Setup and the installer share)."""
    return Path.home() / ".carbon" / "development-launchpad"


def read_aliases(state_dir=None) -> dict[str, tuple[str, str]]:
    """Every recorded parent alias that is well formed: {image id: (tag, fingerprint)}. Anything absent, malformed or
    not owner-only is dropped (an alias nobody can vouch for is no alias)."""
    path = Path(state_dir or default_state_dir()) / ALIASES_NAME
    try:
        if path.is_symlink() or path.stat().st_mode & 0o077:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    if (
        type(value) is not dict
        or value.get("schema") != ALIASES_SCHEMA
        or type(value.get("aliases")) is not dict
    ):
        return {}
    found = {}
    for image_id, entry in value["aliases"].items():
        if (
            type(image_id) is str
            and _IMAGE_ID.fullmatch(image_id)
            and type(entry) is dict
            and set(entry) == {"tag", "fingerprint"}
            and type(entry["tag"]) is str
            and PARENT_TAG.fullmatch(entry["tag"])
            and type(entry["fingerprint"]) is str
            and _HEX64.fullmatch(entry["fingerprint"])
        ):
            found[image_id] = (entry["tag"], entry["fingerprint"])
    return found


def write_alias(state_dir, *, parent_image_id: str, tag: str, value: str) -> Path:
    """Record one parent alias (merging the others already recorded), owner-only (0600)."""
    if (
        not _IMAGE_ID.fullmatch(parent_image_id)
        or not PARENT_TAG.fullmatch(tag)
        or not _HEX64.fullmatch(value)
    ):
        raise ValueError(
            "an image id, a parent tag and a sha256 fingerprint are required"
        )
    directory = Path(state_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    aliases = {
        image_id: {"tag": recorded[0], "fingerprint": recorded[1]}
        for image_id, recorded in read_aliases(directory).items()
    }
    aliases[parent_image_id] = {"tag": tag, "fingerprint": value}
    path = directory / ALIASES_NAME
    document = (
        json.dumps(
            {"schema": ALIASES_SCHEMA, "aliases": aliases},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    path.unlink(missing_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(document)
    return path
