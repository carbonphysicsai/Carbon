"""Day-one step 8a: the receiver installs EVERY served catalog entry and says so.

A submission naming a catalog entry that is not installed in the receiver's
library cache is refused (`direct_reference_not_found`). `install-catalog`
installs every served entry of the receiver's version (CPU builds, plus the
official-grade GPU twins' material), and `catalog-status` / `status` list every
served bundle, how many are missing and why, and are not "ready" / "healthy"
while any is missing. $0: the Docker builds are replaced by their cache marker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.backbone_catalog import gpu_receipt, listing, pipeline
from carbon.challenge_validator import receiver_setup
from scripts.dev import catalog_install, library_bundle, receiver_catalog

MOTOR = {"id": "electric-motor-magnetics", "version": "1.4"}
BCAT = "v2.motor.jno.bcat"
CPU_PARENTS = {
    "torch-cpu-py311": "sha256:" + "a" * 64,
    "python-cpu-py311": "sha256:" + "b" * 64,
}


@pytest.fixture
def receiver(tmp_path, monkeypatch):
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()
    profile = tmp_path / "runner-profile.json"
    profile.write_text(json.dumps({"campaigns_root": str(campaigns)}))
    config = {"challenge": MOTOR, "runner_profile": str(profile)}
    monkeypatch.setattr(
        receiver_catalog, "served_runtimes", lambda c: dict(CPU_PARENTS)
    )
    monkeypatch.setattr(receiver_catalog, "gpu_runtimes", lambda c: [])
    root = campaigns / ".direct-development" / "library-cache"
    root.mkdir(parents=True)
    return config, root


def _marker(root, row):
    parent = CPU_PARENTS[row["runtime"]]
    return root / row["digest"][7:] / (parent[7:] + ".image.json")


def _install(root, row):
    marker = _marker(root, row)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}")


def _entries():
    return listing.entries(MOTOR["id"], MOTOR["version"])


def _twins(config):
    return [r for r in receiver_catalog.served_bundles(config) if r["kind"] == "gpu_twin"]


def _official_bcat(monkeypatch):
    monkeypatch.setattr(
        receiver_catalog, "gpu_runtimes", lambda c: ["jax-cuda13-py311"]
    )
    monkeypatch.setattr(
        gpu_receipt, "load", lambda cid, rt: {"x": 1} if cid == BCAT else None
    )
    monkeypatch.setattr(
        gpu_receipt,
        "official_grade_problem",
        lambda receipt, runtime: None if receipt else "it has no receipt",
    )


def test_every_served_entry_of_the_version_is_listed_and_none_is_installed(receiver):
    config, _root = receiver
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
    gone = rows[7]
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
        "served_runtimes",
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


# --- official-grade GPU twins ---------------------------------------------------


def test_a_twin_is_served_with_an_official_receipt_and_a_gpu_worker(
    receiver, monkeypatch
):
    config, root = receiver
    monkeypatch.setattr(
        receiver_catalog, "gpu_runtimes", lambda c: ["jax-cuda13-py311"]
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
    (root / "materials" / twins[0]["digest"][7:]).mkdir(parents=True)
    assert receiver_catalog.verify(config)["ready"] is True


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
        lambda item, runtime, target, wheelhouse=None: Path(target),
    )
    staged = []

    def stage(directory, cache):
        staged.append(cache)
        (cache / "materials" / _twins(config)[0]["digest"][7:]).mkdir(parents=True)

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


def test_a_receiver_whose_parents_cannot_be_read_is_unverified_not_blocked(
    receiver, monkeypatch
):
    config, _root = receiver
    monkeypatch.setattr(receiver_catalog, "served_runtimes", lambda c: {})
    assert receiver_setup.catalog_state(config) == {
        "status": "UNVERIFIED",
        "ready": None,
    }


def test_the_commands_exit_non_zero_until_ready(receiver, monkeypatch, tmp_path, capsys):
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
