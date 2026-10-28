"""Day-one step 8a: the receiver installs EVERY served catalog entry and says so.

A submission naming a catalog entry that is not installed in the receiver's
library cache is refused (`direct_reference_not_found`). `install-catalog`
installs every served entry of the receiver's version (CPU builds, plus the
official-grade GPU twins' material), and `catalog-status` / `status` list every
served bundle, how many are missing and why, and are not "ready" / "healthy"
while any is missing. Synthetic closures and sealed contexts use the real pure
validators; only the image-build verification boundary is replaced. These
fixtures establish no runtime image eligibility or production qualification.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_direct_parents import torch_image
from test_library_bundles import cpu_fixture, fixture, torch_cpu_fixture

from carbon.backbone_catalog import gpu_receipt, listing, pipeline
from carbon.challenge_validator import direct_receiver, receiver_setup
from carbon.development_session import library_environment_cache as cache
from carbon.development_session.gpu_practice import derived_cpu_parent
from carbon.development_session.library_bundles import (
    ProvisionedLibraryEnvironment,
    bundle_ref,
    prepare_pinned_bundle_directory,
)
from carbon.development_session.research_image import LibraryWorkerImage
from scripts.dev import catalog_install, library_bundle, receiver_catalog

MOTOR = {"id": "electric-motor-magnetics", "version": "1.4"}
BCAT = "synthetic.receiver.0"
CPU_PARENTS = {
    "torch-cpu-py311": torch_image(),
    "python-cpu-py311": derived_cpu_parent(torch_image()),
}
REAL_ENTRIES = listing.entries
READ_PARENTS = receiver_catalog._served_parents
READ_GPU_RUNTIMES = receiver_catalog.gpu_runtimes


def _write_material(root, material):
    manifest, source, wheels, lock, license_text = material
    selected = bundle_ref(*material)
    directory = root / selected.bundle_digest[7:]
    (directory / "wheels").mkdir(parents=True)
    (directory / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, body in (
        ("source.tar.gz", source),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
        *(("wheels/" + name, body) for name, body in wheels.items()),
    ):
        (directory / name).write_bytes(body)
    return selected.to_dict()


@pytest.fixture
def receiver(tmp_path, monkeypatch):
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()
    profile = tmp_path / "runner-profile.json"
    profile.write_text(json.dumps({"campaigns_root": str(campaigns)}))
    config = {"challenge": MOTOR, "runner_profile": str(profile)}
    monkeypatch.setattr(
        receiver_catalog, "_served_parents", lambda c: dict(CPU_PARENTS)
    )
    monkeypatch.setattr(receiver_catalog, "gpu_runtimes", lambda c: [])
    root = campaigns / ".direct-development" / "library-cache"
    root.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    material_root = root.parent / "synthetic-material"
    items = []
    for index in range(16):
        material = (cpu_fixture if index % 2 else torch_cpu_fixture)()
        material[0]["name"] = f"synthetic-receiver-{index}"
        items.append(
            {
                "catalog_id": f"synthetic.receiver.{index}",
                "bundle_ref": _write_material(material_root, material),
            }
        )
    items[0]["bundle_refs"] = {
        "torch-cu130-py311": _write_material(material_root, fixture())
    }
    monkeypatch.setattr(listing, "entries", lambda *args: items)
    monkeypatch.setattr(cache, "verify_library_worker_image", lambda image, cli: image)
    return config, root


def _marker(root, row):
    parent = CPU_PARENTS[row["runtime"]]
    return root / row["digest"][7:] / (parent.image_id[7:] + ".image.json")


def _material_directory(root, row):
    return root.parent / "synthetic-material" / row["digest"][7:]


def _stage(root, row):
    cache.stage_pinned_bundle_material(_material_directory(root, row), root)


def _install(root, row):
    parent = CPU_PARENTS[row["runtime"]]
    selected, context, seal = prepare_pinned_bundle_directory(
        _material_directory(root, row), root, parent.image_id
    )
    image = LibraryWorkerImage(
        ProvisionedLibraryEnvironment(
            selected, parent.image_id, context, seal, "sha256:" + "4" * 64
        ),
        parent,
        selected.to_dict(),
    )
    cache.store_verified_library_worker_image(
        _marker(root, row), image, context_root=context.parent, cli=object()
    )
    _stage(root, row)


def _entries():
    return listing.entries(MOTOR["id"], MOTOR["version"])


def _twins(config):
    return [
        r for r in receiver_catalog.served_bundles(config) if r["kind"] == "gpu_twin"
    ]


def _official_bcat(monkeypatch):
    monkeypatch.setattr(
        receiver_catalog, "gpu_runtimes", lambda c: ["torch-cu130-py311"]
    )
    monkeypatch.setattr(
        gpu_receipt, "load", lambda cid, rt: {"x": 1} if cid == BCAT else None
    )
    monkeypatch.setattr(
        gpu_receipt,
        "official_grade_problem",
        lambda receipt, runtime: None if receipt else "it has no receipt",
    )


def test_every_served_entry_of_the_version_is_listed_and_none_is_installed(
    receiver, monkeypatch
):
    config, _root = receiver
    monkeypatch.setattr(listing, "entries", REAL_ENTRIES)
    found = receiver_catalog.verify(config)
    assert found["served"] == len(_entries()) > 40
    assert {row["catalog_id"] for row in found["bundles"]} == {
        item["catalog_id"] for item in _entries()
    }
    assert found["installed"] == 0 and found["ready"] is False
    assert {row["reason"] for row in found["missing"]} == {
        receiver_catalog.NOT_INSTALLED
    }
    assert len(found["missing"]) == found["served"]


def test_ready_only_when_every_bundle_is_there(receiver):
    config, root = receiver
    rows = receiver_catalog.served_bundles(config)
    for row in rows:
        _install(root, row)
    found = receiver_catalog.verify(config)
    assert found["ready"] is True and found["missing"] == []
    assert found["installed"] == found["served"] == len(rows)
    gone = rows[1]
    _marker(root, gone).unlink()
    found = receiver_catalog.verify(config)
    assert found["ready"] is False and found["installed"] == len(rows) - 1
    assert [m["catalog_id"] for m in found["missing"]] == [gone["catalog_id"]]


def test_a_runtime_the_receiver_does_not_serve_is_missing_with_its_reason(
    receiver, monkeypatch
):
    config, root = receiver
    monkeypatch.setattr(
        receiver_catalog,
        "_served_parents",
        lambda c: {"torch-cpu-py311": CPU_PARENTS["torch-cpu-py311"]},
    )
    for row in receiver_catalog.served_bundles(config):
        if row["runtime"] == "torch-cpu-py311":
            _install(root, row)
    found = receiver_catalog.verify(config)
    assert found["ready"] is False
    assert {m["reason"] for m in found["missing"]} == {
        receiver_catalog.RUNTIME_NOT_SERVED
    }
    assert {m["runtime"] for m in found["missing"]} == {"python-cpu-py311"}


def test_an_empty_catalog_is_never_ready(receiver, monkeypatch):
    config, _root = receiver
    monkeypatch.setattr(receiver_catalog, "served_bundles", lambda c: [])
    assert receiver_catalog.verify(config)["ready"] is False


@pytest.mark.parametrize(
    "damage",
    [
        "empty_record",
        "malformed_record",
        "wrong_bundle",
        "wrong_parent",
        "changed_context",
        "missing_context_file",
        "missing_material",
        "changed_material",
    ],
)
def test_a_marker_cannot_prove_a_corrupt_or_incomplete_installation(receiver, damage):
    config, root = receiver
    rows = receiver_catalog.served_bundles(config)
    for row in rows:
        _install(root, row)
    assert receiver_catalog.verify(config)["ready"] is True
    row = rows[0]
    marker = _marker(root, row)
    record = json.loads(marker.read_bytes())
    if damage == "empty_record":
        marker.write_text("{}")
    elif damage == "malformed_record":
        marker.write_text("{")
    elif damage in {"wrong_bundle", "wrong_parent"}:
        if damage == "wrong_bundle":
            record["bundle"]["environment_digest"] = "sha256:" + "9" * 64
        else:
            record["parent"]["source_tree_digest"] = "sha256:" + "9" * 64
        marker.write_text(json.dumps(record))
    elif damage in {"changed_context", "missing_context_file"}:
        source = Path(record["provisioned"]["context"]) / "source.tar.gz"
        if damage == "changed_context":
            source.chmod(0o600)
            source.write_bytes(b"changed synthetic context")
        else:
            source.unlink()
    else:
        license_file = root / "materials" / row["digest"][7:] / "LICENSE"
        if damage == "missing_material":
            license_file.unlink()
        else:
            license_file.write_text("changed synthetic license")
    found = receiver_catalog.verify(config)
    assert found["ready"] is False and found["installed"] == len(rows) - 1
    assert [(m["catalog_id"], m["reason"]) for m in found["missing"]] == [
        (row["catalog_id"], receiver_catalog.NOT_INSTALLED)
    ]


def test_readiness_uses_pure_validators_without_docker(receiver, monkeypatch):
    from carbon.reconstruction.worker import docker_runtime

    config, root = receiver
    for row in receiver_catalog.served_bundles(config):
        _install(root, row)

    def no_docker(*args, **kwargs):
        pytest.fail("readiness attempted runtime image verification or a Docker call")

    monkeypatch.setattr(cache, "verify_library_worker_image", no_docker)
    monkeypatch.setattr(cache, "DockerCLI", no_docker)
    monkeypatch.setattr(docker_runtime, "DockerCLI", no_docker)
    assert receiver_catalog.verify(config)["ready"] is True


def test_runtime_inventory_preserves_cpu_identities_and_does_not_label_a_gpu_cpu(
    receiver, monkeypatch
):
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.worker import docker_runtime

    config, _root = receiver
    profile_path = Path(config["runner_profile"])
    profile = json.loads(profile_path.read_bytes())
    profile["runtime"] = {"implementation": {"source_tree_digest": "sha256:" + "e" * 64}}
    profile_path.write_text(json.dumps(profile))
    config["construction_image_manifest"] = "/synthetic/torch-worker.json"
    monkeypatch.setattr(receiver_catalog, "_served_parents", READ_PARENTS)
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda path: torch_image())
    assert receiver_catalog.served_runtimes(config) == {
        "torch-cpu-py311": CPU_PARENTS["torch-cpu-py311"].image_id
    }
    config["construction_runtimes"] = direct_receiver.CONSTRUCTION_RUNTIMES
    assert receiver_catalog.served_runtimes(config) == {
        runtime: parent.image_id for runtime, parent in CPU_PARENTS.items()
    }
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: CPU_PARENTS["python-cpu-py311"],
    )
    assert receiver_catalog.served_runtimes(config) == {
        "python-cpu-py311": CPU_PARENTS["python-cpu-py311"].image_id
    }
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: replace(
            torch_image(), lock_digest=GPU_PROFILE.environment_lock_digest
        ),
    )
    assert receiver_catalog.served_runtimes(config) == {}


@pytest.mark.parametrize(
    "field", ["lock_digest", "entrypoint_digest", "build_recipe_digest"]
)
def test_an_unknown_cpu_identity_cannot_establish_inventory(receiver, monkeypatch, field):
    from carbon.reconstruction.worker import docker_runtime

    config, _root = receiver
    profile_path = Path(config["runner_profile"])
    profile = json.loads(profile_path.read_bytes())
    profile["runtime"] = {"implementation": {"source_tree_digest": "sha256:" + "e" * 64}}
    profile_path.write_text(json.dumps(profile))
    config["construction_image_manifest"] = "/synthetic/unknown-cpu.json"
    monkeypatch.setattr(receiver_catalog, "_served_parents", READ_PARENTS)
    parent = replace(CPU_PARENTS["python-cpu-py311"], **{field: "sha256:" + "9" * 64})
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda path: parent)
    assert receiver_catalog.served_runtimes(config) == {}
    assert receiver_setup.catalog_state(config) == {"status": "UNVERIFIED", "ready": None}


@pytest.mark.parametrize(
    "implementation", [None, {}, {"source_tree_digest": None}, {"source_tree_digest": "unknown"}]
)
def test_a_cpu_parent_with_unreadable_implementation_inventory_is_unverified(
    receiver, monkeypatch, implementation
):
    from carbon.reconstruction.worker import docker_runtime

    config, _root = receiver
    profile_path = Path(config["runner_profile"])
    profile = json.loads(profile_path.read_bytes())
    profile["runtime"] = {"implementation": implementation}
    profile_path.write_text(json.dumps(profile))
    config["construction_image_manifest"] = "/synthetic/cpu.json"
    monkeypatch.setattr(receiver_catalog, "_served_parents", READ_PARENTS)
    monkeypatch.setattr(
        docker_runtime, "load_image_identity", lambda path: CPU_PARENTS["python-cpu-py311"]
    )
    assert receiver_setup.catalog_state(config) == {"status": "UNVERIFIED", "ready": None}


@pytest.mark.parametrize(
    "inventory", ["absent", "empty", "valid", "unreadable", "unknown", "wrong_type", "duplicate"]
)
def test_declared_gpu_inventory_cannot_disappear_when_unreadable(
    receiver, monkeypatch, inventory
):
    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.worker import docker_runtime

    config, root = receiver
    for row in receiver_catalog.served_bundles(config):
        _install(root, row)
    monkeypatch.setattr(receiver_catalog, "gpu_runtimes", READ_GPU_RUNTIMES)
    if inventory != "absent":
        config["gpu_construction_images"] = (
            [] if inventory == "empty" else ["/synthetic/gpu-worker.json"]
        )
        if inventory == "wrong_type":
            config["gpu_construction_images"] = None
        elif inventory == "duplicate":
            config["gpu_construction_images"] *= 2

    def read(path):
        if inventory == "unreadable":
            raise OSError("synthetic GPU record unavailable")
        return replace(
            torch_image(),
            lock_digest=(
                torch_profile.GPU_LOCK_DIGEST
                if inventory in {"valid", "duplicate"}
                else "sha256:" + "9" * 64
            ),
        )

    monkeypatch.setattr(docker_runtime, "load_image_identity", read)
    shown = receiver_setup.catalog_state(config)
    if inventory in {"unreadable", "unknown", "wrong_type", "duplicate"}:
        assert shown == {"status": "UNVERIFIED", "ready": None}
        with pytest.raises(ValueError, match="configured GPU inventory"):
            receiver_catalog.verify(config)
    else:
        assert shown["status"] == "COMPLETE" and shown["ready"] is True
        assert receiver_catalog.gpu_runtimes(config) == (
            ["torch-cu130-py311"] if inventory == "valid" else []
        )


# --- official-grade GPU twins ---------------------------------------------------


def test_a_twin_is_served_with_an_official_receipt_and_a_gpu_worker(
    receiver, monkeypatch
):
    config, root = receiver
    monkeypatch.setattr(
        receiver_catalog, "gpu_runtimes", lambda c: ["torch-cu130-py311"]
    )
    # No official-grade receipt (today: no pinned image or host class yet).
    assert _twins(config) == []
    _official_bcat(monkeypatch)
    twins = _twins(config)
    assert [t["catalog_id"] for t in twins] == [BCAT]
    for row in receiver_catalog.served_bundles(config):
        if row["kind"] == "cpu":
            _install(root, row)
    found = receiver_catalog.verify(config)
    assert found["ready"] is False
    assert [(m["catalog_id"], m["reason"]) for m in found["missing"]] == [
        (BCAT, receiver_catalog.GPU_MATERIAL_NOT_STAGED)
    ]
    _stage(root, twins[0])
    assert receiver_catalog.verify(config)["ready"] is True


@pytest.mark.parametrize("damage", ["empty_directory", "changed_material"])
def test_a_twin_material_directory_does_not_prove_a_complete_closure(
    receiver, monkeypatch, damage
):
    config, root = receiver
    _official_bcat(monkeypatch)
    for row in receiver_catalog.served_bundles(config):
        if row["kind"] == "cpu":
            _install(root, row)
    (twin,) = _twins(config)
    directory = root / "materials" / twin["digest"][7:]
    if damage == "empty_directory":
        directory.mkdir(mode=0o700)
    else:
        _stage(root, twin)
        (directory / "LICENSE").write_text("changed synthetic license")
    found = receiver_catalog.verify(config)
    assert found["ready"] is False
    assert [(m["catalog_id"], m["reason"]) for m in found["missing"]] == [
        (BCAT, receiver_catalog.GPU_MATERIAL_NOT_STAGED)
    ]


def test_without_a_gpu_worker_no_twin_is_required(receiver, monkeypatch):
    config, _root = receiver
    monkeypatch.setattr(gpu_receipt, "load", lambda cid, rt: {"x": 1})
    monkeypatch.setattr(gpu_receipt, "official_grade_problem", lambda r, rt: None)
    assert all(r["kind"] == "cpu" for r in receiver_catalog.served_bundles(config))


# --- install --------------------------------------------------------------------


def _fake_install(root, config, failing=()):
    calls = []

    def install(ids, *, wheelhouse=None, receiver_config=None, skipped=None, **_):
        (catalog_id,) = ids
        calls.append(catalog_id)
        if catalog_id in failing:
            raise RuntimeError("build failed")
        row = next(
            r
            for r in receiver_catalog.served_bundles(config)
            if r["catalog_id"] == catalog_id and r["kind"] == "cpu"
        )
        _install(root, row)
        return [{"catalog_id": catalog_id}]

    return install, calls


def test_install_builds_every_missing_entry_and_reports_ready(
    receiver, monkeypatch, tmp_path
):
    config, root = receiver
    fake, calls = _fake_install(root, config)
    monkeypatch.setattr(catalog_install, "install", fake)
    result = receiver_catalog.install(config, tmp_path / "receiver.json")
    assert result["ready"] is True and result["skipped"] == []
    assert sorted(calls) == sorted(i["catalog_id"] for i in _entries())
    # Idempotent: a second run builds nothing.
    again = receiver_catalog.install(config, tmp_path / "receiver.json")
    assert again["ready"] is True and len(calls) == len(_entries())


def test_one_failing_entry_never_stops_the_rest_and_is_not_ready(
    receiver, monkeypatch, tmp_path
):
    config, root = receiver
    bad = _entries()[3]["catalog_id"]
    fake, calls = _fake_install(root, config, failing={bad})
    monkeypatch.setattr(catalog_install, "install", fake)
    result = receiver_catalog.install(config, tmp_path / "receiver.json")
    assert result["ready"] is False
    assert [m["catalog_id"] for m in result["missing"]] == [bad]
    assert [(s["catalog_id"], s["reason"]) for s in result["skipped"]] == [
        (bad, "install_failed")
    ]
    assert len(calls) == len(_entries())
    # Fixed, then installed: only the missing one is built.
    fake_again, calls_again = _fake_install(root, config)
    monkeypatch.setattr(catalog_install, "install", fake_again)
    final = receiver_catalog.install(config, tmp_path / "receiver.json")
    assert final["ready"] is True and calls_again == [bad]


def test_install_stages_an_official_twin_material(receiver, monkeypatch, tmp_path):
    config, root = receiver
    _official_bcat(monkeypatch)
    fake, _calls = _fake_install(root, config)
    monkeypatch.setattr(catalog_install, "install", fake)
    monkeypatch.setattr(
        pipeline,
        "twin_directory",
        lambda item, runtime, target, wheelhouse=None: (
            root.parent
            / "synthetic-material"
            / item["bundle_refs"][runtime]["bundle_digest"][7:]
        ),
    )
    staged = []
    stage_material = cache.stage_pinned_bundle_material

    def stage(directory, cache):
        staged.append(cache)
        return stage_material(directory, cache)

    monkeypatch.setattr(library_bundle, "stage_pinned_bundle_material", stage)
    result = receiver_catalog.install(config, tmp_path / "receiver.json")
    assert staged == [root] and result["ready"] is True


# --- receiver_setup: status and the commands -----------------------------------


def test_status_lists_the_catalog_and_is_not_healthy_while_any_is_missing(receiver):
    config, root = receiver
    shown = receiver_setup.catalog_state(config)
    assert shown["status"] == "INCOMPLETE" and shown["ready"] is False
    assert shown["missing_count"] == shown["served"]
    assert len(shown["missing"]) == receiver_setup.CATALOG_LISTED
    assert "install-catalog" in shown["next"]
    for row in receiver_catalog.served_bundles(config):
        _install(root, row)
    done = receiver_setup.catalog_state(config)
    assert done["status"] == "COMPLETE" and done["ready"] is True
    assert done["missing"] == []


def test_a_receiver_whose_parents_cannot_be_read_is_explicitly_unverified(
    receiver, monkeypatch
):
    config, _root = receiver
    monkeypatch.setattr(receiver_catalog, "served_runtimes", lambda c: {})
    assert receiver_setup.catalog_state(config) == {
        "status": "UNVERIFIED",
        "ready": None,
    }


@pytest.mark.parametrize("profile", [b"{", b"[]", b'{"campaigns_root":null}', None])
def test_unreadable_inventory_remains_explicitly_unverified(receiver, profile):
    config, _root = receiver
    path = Path(config["runner_profile"])
    if profile is None:
        path.unlink()
    else:
        path.write_bytes(profile)
    assert receiver_setup.catalog_state(config) == {
        "status": "UNVERIFIED",
        "ready": None,
    }


def test_the_commands_exit_non_zero_until_ready(
    receiver, monkeypatch, tmp_path, capsys
):
    config, root = receiver
    state = tmp_path / "receiver-state"
    (state / "receiver").mkdir(parents=True)
    monkeypatch.setattr(
        "carbon.challenge_validator.direct_receiver.load_config", lambda path: config
    )
    assert receiver_setup.main(["catalog-status", "--receiver-state", str(state)]) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["ready"] is False and out["served"] == len(_entries())
    for row in receiver_catalog.served_bundles(config):
        _install(root, row)
    assert receiver_setup.main(["catalog-status", "--receiver-state", str(state)]) == 0
