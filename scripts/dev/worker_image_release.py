#!/usr/bin/env python3
"""Released worker images: the release record, and the host pull (IMAGE-RELEASE-01).

A released worker image is built once, by the release workflow, from an exact
tag cut from main, and pushed to `ghcr.io/carbonphysicsai/...`. Every host then
pulls it by digest instead of rebuilding it. A deleted image is re-pulled,
never rebuilt.

Two commands:

    worker_image_release.py record --kind KIND --manifest PATH \\
        --repository REPO --tag TAG --commit SHA --out RECORD
    worker_image_release.py pull --record RECORD [--out MANIFEST]

`record` runs in the release workflow after the push. It reads the pushed
image's registry digest and labels from the local Docker, checks them against
the manifest the build script wrote, and writes the release record
(`carbon.worker-image-release.v1`): the registry reference, the expected
identity labels and the exact `carbon.c03.worker-image.v1` manifest.

Released images use the containerd image store (`IMAGE_STORE`), where an
image's ID is its registry digest, so one `image_id` names it on every host.

`pull` runs on a host. It pulls `repository@sha256:...`, then refuses unless
the pulled image is the manifest's image: the same image ID, the reference
among its repository digests, linux/amd64, the numeric non-root user, the fixed
entrypoint and every identity label equal. Only then does it write the
manifest, byte-for-byte the build's, where the validator's `image_manifest`,
the service's `practice_images` and the Launchpad read it
(`.carbon-artifacts/<kind>-worker-image.json` by default, or `--out`). An
existing different file is never overwritten: older manifests stay as history.

Nothing here builds, tags, pushes, removes or prunes an image, logs in, or
reads a credential; registry access is the host's own `docker login`. A
released image is UNQUALIFIED_PUBLIC_DEVELOPMENT: its security acceptance
before mainnet is the owner's (HUMAN_INPUT).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RECORD_SCHEMA = "carbon.worker-image-release.v1"
MANIFEST_SCHEMA = "carbon.c03.worker-image.v1"
SCOPE = "UNQUALIFIED_PUBLIC_DEVELOPMENT"
SECURITY_ACCEPTANCE = "HUMAN_INPUT"
#: A worker image's `image_id` is what `docker image inspect` reports as `Id`,
#: and that depends on the daemon's image store: the config digest with the
#: classic store, the registry manifest digest with the containerd image store.
#: Released images are built, pushed and pulled with the containerd image
#: store (as the operator host uses), so `image_id` is the registry digest and
#: is the same on every such host. A host on the classic store is refused.
IMAGE_STORE = "containerd"
#: The released kinds, their default manifest file (what the validator, the
#: battery service and the Launchpad already read) and the extra identity
#: labels each carries beyond the C-03 ones.
KINDS = {
    "c03": ("c03-worker-image.json", ()),
    "accelerator": (
        "accelerator-worker-image.json",
        (
            "org.opencontainers.image.carbon.accelerator.profile",
            "org.opencontainers.image.carbon.accelerator.environment",
        ),
    ),
    "torch": (
        "torch-worker-image.json",
        ("org.opencontainers.image.carbon.torch.determinism",),
    ),
    # Labelled as the JAX accelerator worker is: profile and environment.
    "torch-gpu": (
        "torch-gpu-worker-image.json",
        (
            "org.opencontainers.image.carbon.accelerator.profile",
            "org.opencontainers.image.carbon.accelerator.environment",
        ),
    ),
}
MANIFEST_FIELDS = (
    "image_id",
    "config_digest",
    "source_tree_digest",
    "wheel_digest",
    "lock_digest",
    "base_image_digest",
    "build_recipe_digest",
    "entrypoint_digest",
)
RECORD_FIELDS = frozenset(
    {
        "schema",
        "kind",
        "release_tag",
        "source_commit",
        "repository",
        "registry_digest",
        "reference",
        "scope",
        "security_acceptance",
        "image_store",
        "labels",
        "manifest",
    }
)
LABEL = "org.opencontainers.image.carbon."
ENTRYPOINT = [
    "/opt/carbon-worker/bin/python",
    "-I",
    "-m",
    "carbon.reconstruction.worker.entrypoint",
]
USER = "65532:65532"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_COMPONENT = r"[a-z0-9]+(?:[._-][a-z0-9]+)*"
REPOSITORY = re.compile(
    rf"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{{1,5}})?(?:/{_COMPONENT})+"
)


class Refused(Exception):
    """A named refusal; the CLI prints it and exits 2."""

    def __init__(self, code, detail=""):
        super().__init__(code)
        self.code, self.detail = code, detail


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def check_manifest(value):
    """An exact `carbon.c03.worker-image.v1` manifest, as the validator loads it."""
    if (
        type(value) is not dict
        or value.get("schema") != MANIFEST_SCHEMA
        or set(value) != {"schema", *MANIFEST_FIELDS}
    ):
        raise Refused("manifest_invalid", "not an exact worker image manifest")
    for field in MANIFEST_FIELDS:
        if type(value[field]) is not str or not DIGEST.fullmatch(value[field]):
            raise Refused("manifest_invalid", field)
    if value["config_digest"] != value["image_id"]:
        raise Refused("manifest_invalid", "config_digest")
    return value


def identity_labels(manifest):
    """The C-03 identity labels every released worker image carries, from its
    manifest (the same set the worker doctor checks)."""
    return {
        LABEL + "c03.scope": SCOPE,
        LABEL + "c03.source-tree": manifest["source_tree_digest"],
        LABEL + "c03.lock": manifest["lock_digest"],
        LABEL + "c03.base-image": manifest["base_image_digest"],
        LABEL + "c03.build-recipe": manifest["build_recipe_digest"],
        LABEL + "c03.entrypoint": manifest["entrypoint_digest"],
    }


def check_record(value):
    """A release record, every field checked; returns it."""
    if (
        type(value) is not dict
        or value.get("schema") != RECORD_SCHEMA
        or set(value) != RECORD_FIELDS
    ):
        missing = sorted(RECORD_FIELDS - set(value)) if type(value) is dict else []
        raise Refused("record_invalid", ",".join(missing) or "schema or fields")
    if value["kind"] not in KINDS:
        raise Refused("record_invalid", "kind")
    strings = ("release_tag", "source_commit", "repository", "registry_digest")
    if any(type(value[k]) is not str for k in (*strings, "reference")):
        raise Refused("record_invalid", "field types")
    if not TAG.fullmatch(value["release_tag"]):
        raise Refused("record_invalid", "release_tag")
    if not COMMIT.fullmatch(value["source_commit"]):
        raise Refused("record_invalid", "source_commit")
    if not REPOSITORY.fullmatch(value["repository"]):
        raise Refused("record_invalid", "repository")
    if not DIGEST.fullmatch(value["registry_digest"]):
        raise Refused("record_invalid", "registry_digest")
    if value["reference"] != value["repository"] + "@" + value["registry_digest"]:
        raise Refused("record_invalid", "reference")
    if value["scope"] != SCOPE or value["security_acceptance"] != SECURITY_ACCEPTANCE:
        raise Refused("record_invalid", "scope or security_acceptance")
    if value["image_store"] != IMAGE_STORE:
        raise Refused("record_invalid", "image_store")
    manifest = check_manifest(value["manifest"])
    if value["registry_digest"] != manifest["image_id"]:
        raise Refused(
            "record_invalid", "registry_digest is not the manifest's image_id"
        )
    labels = value["labels"]
    extras = KINDS[value["kind"]][1]
    expected = identity_labels(manifest)
    if (
        type(labels) is not dict
        or set(labels) != set(expected) | set(extras)
        or any(labels[k] != v for k, v in expected.items())
        or any(
            type(labels[k]) is not str or not DIGEST.fullmatch(labels[k])
            for k in extras
        )
    ):
        raise Refused("record_invalid", "labels")
    return value


def docker(*args, capture=True):
    try:
        done = subprocess.run(
            ["docker", *args],
            capture_output=capture,
            text=True,
            check=False,
            timeout=3600,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise Refused("docker_unavailable") from None
    return done


def inspect(reference):
    done = docker("image", "inspect", "--format", "{{json .}}", reference)
    if done.returncode != 0:
        raise Refused("image_missing", reference)
    try:
        value = json.loads(done.stdout)
    except ValueError:
        raise Refused("image_inspect_unreadable", reference) from None
    if type(value) is not dict:
        raise Refused("image_inspect_unreadable", reference)
    return value


def verify_image(value, record):
    """The inspected image is the record's image, or a named refusal."""
    manifest = record["manifest"]
    config = value.get("Config") or {}
    if value.get("Id") != manifest["image_id"]:
        # Another image, or this daemon is on the classic image store, where
        # `Id` is the config digest rather than the registry digest.
        raise Refused(
            "image_id_mismatch",
            f"{value.get('Id')} (released images need the containerd image store)",
        )
    if record["reference"] not in (value.get("RepoDigests") or []):
        raise Refused("registry_digest_mismatch", record["reference"])
    if (value.get("Os"), value.get("Architecture")) != ("linux", "amd64"):
        raise Refused("platform_mismatch")
    if config.get("User") != USER or config.get("Entrypoint") != ENTRYPOINT:
        raise Refused("runtime_mismatch")
    labels = config.get("Labels") or {}
    differs = sorted(k for k, v in record["labels"].items() if labels.get(k) != v)
    if differs:
        raise Refused("label_mismatch", ",".join(differs))


def write_new(path, body):
    """Write `body` at `path` unless a different file is there already."""
    path = Path(path)
    if path.is_symlink():
        raise Refused("out_is_symlink", str(path))
    if path.exists():
        if path.read_text(encoding="utf-8") == body:
            return False
        raise Refused(
            "out_exists_differs",
            f"{path} holds another manifest; it is kept as history - name --out",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".release-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(body)
        os.chmod(temporary, 0o644)
        os.link(temporary, path)
    finally:
        os.unlink(temporary)
    return True


def record(args):
    if args.kind not in KINDS:
        raise Refused("kind_unknown", args.kind)
    if not REPOSITORY.fullmatch(args.repository):
        raise Refused("repository_invalid", args.repository)
    if not TAG.fullmatch(args.tag) or not COMMIT.fullmatch(args.commit):
        raise Refused("release_invalid", "tag or commit")
    try:
        manifest = check_manifest(json.loads(Path(args.manifest).read_text("utf-8")))
    except (OSError, ValueError):
        raise Refused("manifest_invalid", str(args.manifest)) from None
    value = inspect(manifest["image_id"])
    pushed = [
        d
        for d in value.get("RepoDigests") or []
        if d.startswith(args.repository + "@")
        and DIGEST.fullmatch(d[len(args.repository) + 1 :])
    ]
    if len(pushed) != 1:
        raise Refused("registry_digest_missing", args.repository)
    if pushed[0] != args.repository + "@" + manifest["image_id"]:
        raise Refused(
            "image_store_not_containerd",
            "the pushed digest is not the image ID: build with the containerd image store",
        )
    labels = value.get("Config", {}).get("Labels") or {}
    extras = KINDS[args.kind][1]
    released = {
        "schema": RECORD_SCHEMA,
        "kind": args.kind,
        "release_tag": args.tag,
        "source_commit": args.commit,
        "repository": args.repository,
        "registry_digest": pushed[0][len(args.repository) + 1 :],
        "reference": pushed[0],
        "scope": SCOPE,
        "security_acceptance": SECURITY_ACCEPTANCE,
        "image_store": IMAGE_STORE,
        "labels": {**identity_labels(manifest), **{k: labels.get(k) for k in extras}},
        "manifest": manifest,
    }
    check_record(released)
    verify_image(value, released)
    write_new(args.out, canonical(released))
    return {"record": str(args.out), "reference": released["reference"]}


def pull(args):
    try:
        released = check_record(json.loads(Path(args.record).read_text("utf-8")))
    except (OSError, ValueError):
        raise Refused("record_invalid", str(args.record)) from None
    out = (
        Path(args.out)
        if args.out
        else REPOSITORY_ROOT / ".carbon-artifacts" / KINDS[released["kind"]][0]
    )
    if docker("pull", released["reference"]).returncode != 0:
        raise Refused(
            "pull_failed",
            released["reference"] + " (the host's own `docker login` may be needed)",
        )
    verify_image(inspect(released["reference"]), released)
    written = write_new(out, canonical(released["manifest"]))
    return {
        "kind": released["kind"],
        "reference": released["reference"],
        "image_id": released["manifest"]["image_id"],
        "manifest": str(out),
        "written": written,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    made = sub.add_parser("record")
    made.add_argument("--kind", required=True)
    made.add_argument("--manifest", required=True)
    made.add_argument("--repository", required=True)
    made.add_argument("--tag", required=True)
    made.add_argument("--commit", required=True)
    made.add_argument("--out", required=True)
    pulled = sub.add_parser("pull")
    pulled.add_argument("--record", required=True)
    pulled.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        result = record(args) if args.command == "record" else pull(args)
    except Refused as refused:
        print(
            json.dumps({"refused": refused.code, "detail": refused.detail}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
