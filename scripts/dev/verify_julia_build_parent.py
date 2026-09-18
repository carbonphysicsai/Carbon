"""Verify local parent identity and inherited content before publishing a build.

Local Docker image IDs identify image configuration, not registry manifests.
The builder uses a local tag with pull disabled, checks its exact ID before and
after build, then checks inherited layers/configuration and build provenance.
This trusted-host build check is not worker or production security attestation.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_DIGEST = re.compile(r"sha256:[a-f0-9]{64}")


def verify_parent(manifest, parent):
    identity = manifest.get("image_id")
    layers = parent.get("RootFS", {}).get("Layers")
    if (
        type(identity) is not str
        or _DIGEST.fullmatch(identity) is None
        or parent.get("Id") != identity
        or parent.get("Os") != "linux"
        or parent.get("Architecture") != "amd64"
        or type(layers) is not list
        or not layers
        or any(
            type(item) is not str or _DIGEST.fullmatch(item) is None for item in layers
        )
    ):
        raise ValueError("exact local Julia parent differs")


def verify_child(manifest, parent, child, identity, build, recipe):
    verify_parent(manifest, parent)
    layers = parent["RootFS"]["Layers"]
    config = child.get("Config", {})
    original = parent.get("Config", {})
    if (
        type(identity) is not str
        or _DIGEST.fullmatch(identity) is None
        or child.get("Id") != identity
        or child.get("Os") != "linux"
        or child.get("Architecture") != "amd64"
        or child.get("RootFS", {}).get("Layers", [])[: len(layers)] != layers
        or config.get("Entrypoint") != original.get("Entrypoint")
        or config.get("User") != "65532:65532"
        or config.get("Labels", {}).get(
            "org.opencontainers.image.carbon.c03.base-image"
        )
        != manifest["image_id"]
        or type(recipe) is not str
        or _DIGEST.fullmatch(recipe) is None
        or build.get("base_image_digest") != manifest["image_id"]
        or build.get("build_recipe_digest") != recipe
        or any(
            build.get(key) != manifest.get(key) or key not in manifest
            for key in (
                "source_tree_digest",
                "wheel_digest",
                "lock_digest",
                "entrypoint_digest",
            )
        )
    ):
        raise ValueError("Julia child does not retain its bound parent")


def main(argv):
    if len(argv) not in {2, 6}:
        raise SystemExit(
            "parent-manifest parent-inspect [child-inspect image build recipe]"
        )
    manifest, parent = (json.loads(Path(value).read_bytes()) for value in argv[:2])
    verify_parent(manifest, parent)
    if len(argv) == 6:
        verify_child(
            manifest,
            parent,
            json.loads(Path(argv[2]).read_bytes()),
            argv[3],
            json.loads(Path(argv[4]).read_bytes()),
            argv[5],
        )


if __name__ == "__main__":
    main(sys.argv[1:])
