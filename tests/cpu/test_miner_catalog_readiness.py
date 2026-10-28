"""Synthetic closures exercise real miner cache/material validators.

Only daemon metadata and the image-build/verification boundary are simulated.
These records have no scientific, official-image or qualification authority.
"""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
import test_receiver_catalog as receiver_fixtures

from carbon.backbone_catalog import listing
from carbon.development_session import library_environment_cache as cache
from carbon.development_session.library_bundles import LibraryBundleRef
from carbon.reconstruction.worker import docker_runtime
from scripts.dev import library_bundle
from scripts.dev.miner_launchpad import capabilities, catalog_build, catalog_state

READ_PARENTS = catalog_state.parents


@pytest.fixture
def daemon(monkeypatch):
    return receiver_fixtures.daemon.__wrapped__(monkeypatch)


@pytest.fixture
def receiver(tmp_path, monkeypatch, daemon):
    return receiver_fixtures.receiver.__wrapped__(tmp_path, monkeypatch, daemon)


@pytest.fixture
def miner(receiver, tmp_path, monkeypatch):
    _config, root = receiver
    items = receiver_fixtures._entries()
    for item in items:
        item["challenges"] = [receiver_fixtures.MOTOR]
    monkeypatch.setattr(listing, "load", lambda: {"entries": items})
    monkeypatch.setattr(
        catalog_state, "parents", lambda cfg: dict(receiver_fixtures.CPU_PARENTS)
    )
    cfg = {"campaigns_root": str(root.parent.parent)}
    state = tmp_path / "miner-state"
    (state / "environment").mkdir(parents=True, mode=0o700)
    (state / "environment/runner-profile.json").write_text(json.dumps(cfg))
    return cfg, root, items, state


def install(root, item):
    reference = item["bundle_ref"]
    row = {
        "runtime": reference["runtime_profile_id"],
        "digest": reference["bundle_digest"],
    }
    receiver_fixtures._install(root, row)
    return row


def test_deleted_child_cannot_leave_complete_progress_or_picker(miner, daemon):
    cfg, root, items, state = miner
    for item in items:
        install(root, item)
    assert catalog_build.status(state)["state"] == "COMPLETE"
    assert capabilities._catalog_install(
        {"challenge_id": "electric-motor-magnetics", "version": "1.4"}, cfg
    )["installed"] == len(items)
    missing = items[0]
    daemon["images"].remove(missing["bundle_ref"]["bundle_digest"])
    assert catalog_state.state(cfg)["missing"] == [missing["catalog_id"]]
    assert catalog_state.progress(cfg)["installed"] == len(items) - 1
    assert catalog_build.status(state)["state"] == "INCOMPLETE"
    assert (
        capabilities._catalog_install(
            {"challenge_id": "electric-motor-magnetics", "version": "1.4"}, cfg
        )["installed"]
        == len(items) - 1
    )
    spawned = []
    catalog_build.start(state, spawn=lambda *args, **kwargs: spawned.append(args))
    assert len(spawned) == 1


@pytest.mark.parametrize(
    "fault",
    ["unreachable", "malformed_listing", "partial_inspection", "wrong_inspected_id"],
)
def test_unknown_image_observation_never_proves_ready(miner, daemon, fault):
    cfg, root, items, state = miner
    for item in items:
        install(root, item)
    daemon["fault"] = fault
    assert catalog_state.progress(cfg)["installed"] == 0
    assert catalog_build.status(state)["state"] == "INCOMPLETE"
    assert set(catalog_state.state(cfg)["missing"]) == {
        item["catalog_id"] for item in items
    }


@pytest.mark.parametrize("fault", ["receipt", "context", "material"])
def test_corrupt_cache_never_proves_installed(miner, fault):
    cfg, root, items, _state = miner
    item = items[0]
    row = install(root, item)
    receipt = receiver_fixtures._marker(root, row)
    if fault == "receipt":
        receipt.write_text("{}")
    elif fault == "context":
        context = cache.load_cached_library_worker_image(
            receipt,
            expected_bundle=LibraryBundleRef.from_dict(item["bundle_ref"]),
            expected_parent=receiver_fixtures.CPU_PARENTS[row["runtime"]],
            context_root=receipt.parent,
        ).provisioned.context
        context.chmod(0o700)
        (context / "unexpected").write_bytes(b"synthetic changed context")
    else:
        material = root / "materials" / row["digest"][7:] / "source.tar.gz"
        material.write_bytes(b"not the pinned source")
    assert item["catalog_id"] in catalog_state.state(cfg)["missing"]


def test_metadata_queries_are_deduplicated_and_status_never_starts_work(
    miner, daemon, monkeypatch
):
    _cfg, root, items, state = miner
    install(root, items[0])
    duplicate = {**items[0], "catalog_id": "synthetic.same.child"}
    monkeypatch.setattr(listing, "load", lambda: {"entries": [items[0], duplicate]})
    daemon["calls"].clear()
    monkeypatch.setattr(
        catalog_build,
        "start",
        lambda *args, **kwargs: pytest.fail("status started work"),
    )
    assert catalog_build.status(state)["state"] == "COMPLETE"
    assert len(daemon["calls"]) == 2
    assert daemon["calls"][1][2:-2] == [items[0]["bundle_ref"]["bundle_digest"]]


def test_zero_known_entries_cannot_report_complete(miner, monkeypatch):
    _cfg, _root, _items, state = miner
    monkeypatch.setattr(catalog_state, "parents", lambda cfg: {})
    assert catalog_build.status(state)["state"] == "INCOMPLETE"


@pytest.mark.parametrize("configured", [True, "/synthetic/missing-gpu-image.json"])
def test_unknown_configured_gpu_inventory_cannot_disappear(
    miner, monkeypatch, configured
):
    cfg, root, items, state = miner
    for item in items:
        install(root, item)
    cfg["gpu_image"] = configured
    monkeypatch.setattr(catalog_state, "parents", READ_PARENTS)
    (state / "environment/runner-profile.json").write_text(json.dumps(cfg))
    assert catalog_state.progress(cfg)["installed"] == 0
    assert catalog_build.status(state)["state"] == "INCOMPLETE"
    assert set(catalog_state.state(cfg)["missing"]) == {
        item["catalog_id"] for item in items
    }


@pytest.mark.parametrize(
    "implementation",
    [
        {"source_tree_digest": "sha256:" + "e" * 64},
        None,
        {},
        {"source_tree_digest": None},
        {"source_tree_digest": "unknown"},
    ],
)
def test_actual_cpu_parent_selector_requires_a_valid_source_identity(
    miner, monkeypatch, implementation
):
    cfg, root, items, state = miner
    for item in items:
        install(root, item)
    parent = receiver_fixtures.CPU_PARENTS["python-cpu-py311"]
    cfg.update(
        paths={"image_manifest": "/synthetic/canonical-cpu.json"},
        runtime={"implementation": implementation, "images": [parent.image_id]},
    )
    (state / "environment/runner-profile.json").write_text(json.dumps(cfg))
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda path: parent)
    monkeypatch.setattr(catalog_state, "parents", READ_PARENTS)
    if implementation == {"source_tree_digest": "sha256:" + "e" * 64}:
        assert READ_PARENTS(cfg) == {"python-cpu-py311": parent}
        assert catalog_state.progress(cfg)["installed"] > 0
        assert catalog_state.state(cfg)["missing"] == []
    else:
        assert catalog_state.progress(cfg)["installed"] == 0
        assert catalog_build.status(state)["state"] == "INCOMPLETE"
        assert set(catalog_state.state(cfg)["missing"]) == {
            item["catalog_id"] for item in items
        }


@pytest.mark.parametrize("kind", ["torch-cpu-py311", "python-cpu-py311"])
@pytest.mark.parametrize("binding", ["match", "mismatch", "missing", "empty", "not_list"])
def test_actual_parent_selector_matches_the_owner_install_profile(
    miner, monkeypatch, kind, binding
):
    cfg, root, items, _state = miner
    parent = receiver_fixtures.CPU_PARENTS[kind]
    item = next(item for item in items if item["bundle_ref"]["runtime_profile_id"] == kind)
    install(root, item)
    runtime = {"implementation": {"source_tree_digest": "sha256:" + "e" * 64}}
    if binding != "missing":
        runtime["images"] = {
            "match": [parent.image_id],
            "mismatch": ["sha256:" + "9" * 64],
            "empty": [],
            "not_list": parent.image_id,
        }[binding]
    cfg.update(paths={"image_manifest": "/synthetic/parent.json"}, runtime=runtime)
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda path: parent)
    monkeypatch.setattr(catalog_state, "parents", READ_PARENTS)
    if binding == "match":
        found = READ_PARENTS(cfg)
        assert found[kind] == parent
        assert catalog_state.readiness(cfg)[item["catalog_id"]] is True
    else:
        with pytest.raises(ValueError, match="differs from runner profile"):
            READ_PARENTS(cfg)
        assert catalog_state.readiness(cfg)[item["catalog_id"]] is False


def test_owner_catalog_retry_rebuilds_missing_child_then_reuses_it(
    miner, daemon, monkeypatch
):
    cfg, root, items, state = miner
    item = items[0]
    row = install(root, item)
    parent = receiver_fixtures.CPU_PARENTS[row["runtime"]]
    profile = {
        **cfg,
        "paths": {"image_manifest": "/synthetic/torch-parent.json"},
        "runtime": {"images": [parent.image_id]},
    }
    monkeypatch.setattr(
        library_bundle,
        "EnvironmentSetup",
        lambda *a, **k: SimpleNamespace(profile=lambda: profile),
    )
    monkeypatch.setattr(library_bundle, "load_image_identity", lambda path: parent)
    monkeypatch.setattr(library_bundle, "DockerCLI", docker_runtime.DockerCLI)
    receipt = receiver_fixtures._marker(root, row)
    original = receipt.read_bytes()
    cached = cache.load_cached_library_worker_image(
        receipt,
        expected_bundle=LibraryBundleRef.from_dict(item["bundle_ref"]),
        expected_parent=parent,
        context_root=receipt.parent,
    )
    daemon["images"].remove(cached.image_id)
    builds = []

    def provision(*args, cli):
        assert receipt.read_bytes() == original
        builds.append(args)
        return replace(cached.provisioned, image_id="sha256:" + "f" * 64)

    monkeypatch.setattr(cache, "provision_offline_bundle", provision)
    directory = receiver_fixtures._material_directory(root, row)
    assert (
        library_bundle.install_bundle(directory, state)["status"]
        == "INSTALLED_VERIFIED"
    )
    assert len(builds) == 1
    assert item["catalog_id"] not in catalog_state.state(cfg)["missing"]
    assert (
        library_bundle.install_bundle(directory, state)["status"]
        == "INSTALLED_VERIFIED"
    )
    assert len(builds) == 1
    receipt.write_text("{}")
    with pytest.raises(ValueError):
        library_bundle.install_bundle(directory, state)
    assert receipt.read_text() == "{}" and len(builds) == 1
