"""CPU image identity checks execute without Docker or a numerical runtime."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from carbon.reconstruction import torch_profile
from carbon.reconstruction.worker.docker_runtime import load_image_identity

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "torch_cpu_image_identity", ROOT / ".devcontainer/torch/cpu_image_identity.py"
)
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


def sha(character):
    return "sha256:" + character * 64


@pytest.fixture
def parent_record(tmp_path, monkeypatch):
    document = {
        "schema": "carbon.c03.worker-image-build.v1",
        "source_tree_digest": sha("1"),
        "wheel_digest": sha("2"),
        "lock_digest": sha("3"),
        "base_image_digest": sha("4"),
        "build_recipe_digest": sha("5"),
        "entrypoint_digest": sha("6"),
    }
    path = tmp_path / "worker-image-build.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o444)
    for name, value in {
        "WORKER_IMAGE": sha("a"),
        "TORCH_RECIPE_DIGEST": sha("b"),
        "TORCH_LOCK_DIGEST": sha("c"),
    }.items():
        monkeypatch.setenv(name, value)
    return path, document


def test_child_record_replaces_parent_identity_and_preserves_source(
    parent_record, tmp_path
):
    path, parent = parent_record
    labels = {
        "base_image_digest": sha("a"),
        "build_recipe_digest": sha("b"),
        "lock_digest": sha("c"),
    }
    # A skipped rewrite leaves all three manifest fields inconsistent with labels.
    assert all(parent[name] != value for name, value in labels.items())
    HELPER.record(path)
    child = json.loads(path.read_bytes())
    assert child == {**parent, **labels}
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o444
    manifest = tmp_path / "torch-worker-image.json"
    manifest.write_text(
        json.dumps(
            {
                **child,
                "schema": "carbon.c03.worker-image.v1",
                "image_id": sha("d"),
                "config_digest": sha("d"),
            }
        ),
        encoding="utf-8",
    )
    loaded = load_image_identity(manifest)
    assert loaded.base_image_digest == labels["base_image_digest"]
    assert loaded.build_recipe_digest == labels["build_recipe_digest"]
    assert loaded.lock_digest == labels["lock_digest"]
    assert loaded.source_tree_digest == parent["source_tree_digest"]


@pytest.mark.parametrize(
    "name", ["WORKER_IMAGE", "TORCH_RECIPE_DIGEST", "TORCH_LOCK_DIGEST"]
)
@pytest.mark.parametrize("value", [None, "mutable:latest", "sha256:" + "g" * 64])
def test_bad_identity_refuses_before_rewriting_parent(
    parent_record, monkeypatch, name, value
):
    path, _ = parent_record
    original = path.read_bytes()
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(SystemExit, match="Exact immutable image identities required"):
        HELPER.record(path)
    assert path.read_bytes() == original


@pytest.fixture
def installed_pins(monkeypatch):
    pins = {name: version for name, version, _ in torch_profile.PINS}
    # The existing CPU check compares the locked version without its wheel build tag.
    pins["torch"] += "+cpu"
    monkeypatch.setattr(HELPER.metadata, "version", pins.__getitem__)
    monkeypatch.setenv("TORCH_DETERMINISM_DIGEST", torch_profile.CPU_DETERMINISM_DIGEST)
    return pins


def test_exact_installed_pins_and_determinism_pass(installed_pins):
    HELPER.verify()


@pytest.mark.parametrize("name", [name for name, _, _ in torch_profile.PINS])
def test_each_drifted_installed_pin_refuses(installed_pins, name):
    installed_pins[name] = "0.fixture-drift"
    with pytest.raises(SystemExit, match="is not the pinned"):
        HELPER.verify()


@pytest.mark.parametrize("value", [None, sha("f")])
def test_missing_or_wrong_determinism_refuses(installed_pins, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("TORCH_DETERMINISM_DIGEST")
    else:
        monkeypatch.setenv("TORCH_DETERMINISM_DIGEST", value)
    with pytest.raises(SystemExit, match="determinism label"):
        HELPER.verify()
