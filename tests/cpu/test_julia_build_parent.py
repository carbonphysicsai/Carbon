"""Local parent/config IDs must not be mistaken for registry manifest digests."""

import copy
from pathlib import Path

import pytest

from scripts.dev.verify_julia_build_parent import verify_child, verify_parent


def material():
    parent_id = "sha256:" + "a" * 64
    child_id = "sha256:" + "b" * 64
    recipe = "sha256:" + "c" * 64
    manifest = {
        "image_id": parent_id,
        **{
            key: "sha256:" + "d" * 64
            for key in (
                "source_tree_digest",
                "wheel_digest",
                "lock_digest",
                "entrypoint_digest",
            )
        },
    }
    parent = {
        "Id": parent_id,
        "Os": "linux",
        "Architecture": "amd64",
        "RootFS": {"Layers": ["sha256:" + "e" * 64]},
        "Config": {"Entrypoint": ["/entrypoint"], "User": "65532:65532"},
    }
    child = copy.deepcopy(parent)
    child["Id"] = child_id
    child["RootFS"]["Layers"].append("sha256:" + "f" * 64)
    child["Config"]["Labels"] = {
        "org.opencontainers.image.carbon.c03.base-image": parent_id
    }
    build = {**manifest, "base_image_digest": parent_id, "build_recipe_digest": recipe}
    return manifest, parent, child, child_id, build, recipe


def test_local_parent_and_child_provenance():
    values = material()
    verify_parent(*values[:2])
    verify_child(*values)


@pytest.mark.parametrize("changed", ["identity", "platform", "layers"])
def test_parent_tag_rebinding_or_invalid_local_parent_rejected(changed):
    manifest, parent, *_ = material()
    if changed == "identity":
        parent["Id"] = "sha256:" + "1" * 64
    elif changed == "platform":
        parent["Architecture"] = "arm64"
    else:
        parent["RootFS"]["Layers"] = []
    with pytest.raises(ValueError):
        verify_parent(manifest, parent)


@pytest.mark.parametrize(
    "changed", ["layers", "entrypoint", "user", "parent", "source", "recipe"]
)
def test_child_must_retain_exact_parent_inputs(changed):
    manifest, parent, child, identity, build, recipe = material()
    if changed == "layers":
        child["RootFS"]["Layers"].reverse()
    elif changed == "entrypoint":
        child["Config"]["Entrypoint"] = ["/different"]
    elif changed == "user":
        child["Config"]["User"] = "0:0"
    elif changed == "parent":
        build["base_image_digest"] = identity
    elif changed == "source":
        build["source_tree_digest"] = identity
    else:
        build["build_recipe_digest"] = identity
    with pytest.raises(ValueError):
        verify_child(manifest, parent, child, identity, build, recipe)


def test_builder_keeps_local_resolution_and_verifies_before_publication():
    source = (
        Path(__file__).resolve().parents[2] / "scripts/dev/julia_worker_image.sh"
    ).read_text()
    assert "@${parent}" not in source
    assert "docker build --pull=false" in source
    assert source.index("parent-before.json") < source.index(
        "docker build --pull=false"
    )
    assert source.index("parent-after.json") < source.index('docker create "${image}"')
    assert source.index('"${temporary}/child.json" "${image}"') < source.index(
        'mkdir -p "$(dirname'
    )
