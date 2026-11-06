"""A finished operation's trusted stage items are reclaimed (GPUYard 6 Nov: Deploy 06:48, Lead 07:00).

Every grade and rebuild staged a fresh ~52 MB ``uv-bin`` (and a copied overlay tree) under ``ledger/operation-*/input``
and never reclaimed it: ~1.5 GB/h on the doors with crown averaging. These run the REAL `reclaim_trusted_stage` on real
files (the overlay staged by the carrier's own `_stage_verified_overlay`), and one full carrier run through the
fixed-practice harness: the uv binary is gone once the container is confirmed removed, its identity stays recorded,
and the caller's own input files (a build's ``example.npz``, which retention reads) stay.
"""

# ruff: noqa: F811 - the shared `harness` fixture is imported by name and used as an argument

from __future__ import annotations

import hashlib
import json
import os

import pytest
from test_fixed_practice_failure_diagnostics import harness  # noqa: F401
from test_research_carrier_overlay import _parent_build

from carbon.development_session import research_carrier as carrier
from carbon.development_session.library_bundles import UV_IMAGE
from carbon.development_session.profile import digest
from carbon.reconstruction.worker.model import WorkerImageIdentity

UV = b"\x7fELF fixture uv binary, never executed" * 1024


def _overlay(tmp_path, stage):
    """A sealed overlay staged exactly as the carrier stages it (read-only tree with its receipt)."""
    source = tmp_path / "cache-overlay"
    package = source / "site-packages" / "pkg"
    package.mkdir(parents=True)
    body = b"VALUE = 1\n"
    (package / "mod.py").write_bytes(body)
    row = [
        "site-packages/pkg/mod.py",
        len(body),
        "sha256:" + hashlib.sha256(body).hexdigest(),
    ]
    receipt = {
        "tree_digest": "sha256:"
        + hashlib.sha256(json.dumps([row], separators=(",", ":")).encode()).hexdigest(),
        "file_count": 1,
        "total_file_bytes": len(body),
    }
    (source / ".overlay.json").write_text(json.dumps(receipt))
    carrier._stage_verified_overlay(source, stage / "overlay", receipt)
    return receipt


def _stage(tmp_path, *, uv=True, overlay=True):
    stage = tmp_path / "operation-x" / "input"
    stage.mkdir(parents=True)
    (stage / "program.py").write_bytes(b"# fixed")
    (stage / "example.npz").write_bytes(b"caller example, read by retention")
    receipt = None
    if uv:
        (stage / "uv-bin").write_bytes(UV)
        (stage / "uv-bin").chmod(0o555)
    if overlay:
        receipt = _overlay(tmp_path, stage)
    for path in stage.iterdir():
        if path.is_file():
            path.chmod(0o555 if path.name == "uv-bin" else 0o444)
    stage.chmod(0o755)
    return stage, receipt


def test_the_uv_binary_and_overlay_are_reclaimed_and_their_identities_kept(tmp_path):
    stage, receipt = _stage(tmp_path)
    freed = carrier.reclaim_trusted_stage(stage)
    assert freed >= len(UV)
    assert not (stage / "uv-bin").exists()
    assert not (stage / "overlay").exists()
    assert (stage / "example.npz").read_bytes() == b"caller example, read by retention"
    assert (stage / "program.py").read_bytes() == b"# fixed"
    record = json.loads((stage / carrier.RECLAIMED_STAGE).read_bytes())
    assert record == {
        "schema": "carbon.autoresearch.reclaimed-stage.v1",
        "uv_sha256": digest(UV),
        "overlay_receipt": receipt,
    }


def test_reclaim_is_idempotent_and_never_rewrites_its_record(tmp_path):
    stage, _ = _stage(tmp_path)
    carrier.reclaim_trusted_stage(stage)
    before = (stage / carrier.RECLAIMED_STAGE).read_bytes()
    assert carrier.reclaim_trusted_stage(stage) == 0
    assert (stage / carrier.RECLAIMED_STAGE).read_bytes() == before


@pytest.mark.parametrize("uv,overlay", [(True, False), (False, True)])
def test_either_item_alone_is_reclaimed(tmp_path, uv, overlay):
    stage, receipt = _stage(tmp_path, uv=uv, overlay=overlay)
    carrier.reclaim_trusted_stage(stage)
    record = json.loads((stage / carrier.RECLAIMED_STAGE).read_bytes())
    assert record["uv_sha256"] == (digest(UV) if uv else None)
    assert record["overlay_receipt"] == receipt
    assert not (stage / "uv-bin").exists() and not (stage / "overlay").exists()


def test_a_stage_without_trusted_items_is_left_exactly_as_it_is(tmp_path):
    stage, _ = _stage(tmp_path, uv=False, overlay=False)
    before = sorted(p.name for p in stage.iterdir())
    assert carrier.reclaim_trusted_stage(stage) == 0
    assert sorted(p.name for p in stage.iterdir()) == before
    assert carrier.reclaim_trusted_stage(tmp_path / "missing") == 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlinks")
def test_a_symlinked_stage_or_item_is_never_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_bytes(b"x")
    stage, _ = _stage(tmp_path, uv=False, overlay=False)
    (stage / "overlay").symlink_to(outside)
    assert carrier.reclaim_trusted_stage(stage) == 0
    assert (outside / "keep").exists()
    link = tmp_path / "linked-input"
    link.symlink_to(stage)
    assert carrier.reclaim_trusted_stage(link) == 0


def _prep(harness, files=None):
    parent_id = "sha256:" + "4" * 64
    parent = WorkerImageIdentity(*(parent_id for _ in range(8)))
    identity = {
        "schema": "carbon.development.pinned-uv-stage.v1",
        "uv_image": UV_IMAGE,
        "bundle_ref": {},
        "parent_image_id": parent_id,
        "parent_build": _parent_build(parent_id),
    }
    control = {
        "bundle_ref": {},
        "parent_image_id": parent_id,
        "uv_sha256": digest(UV),
        "parent_build": _parent_build(parent_id),
    }
    return {
        "files": files or {"example.npz": b"caller example"},
        "image": parent,
        "seconds": 600,
        "provenance": carrier.LIBRARY_PREP_PROVENANCE,
        "executable_files": ("uv-bin",),
        "trusted_stage_identity": identity,
        "trusted_stage_provider": lambda _cli: {
            "uv-bin": UV,
            "control.json": json.dumps(control).encode(),
        },
    }


def _input(harness):
    operations = list(harness.ledger.root.glob("operation-*"))
    assert len(operations) == 1
    return operations[0] / "input"


def test_a_finished_prep_operation_keeps_no_uv_binary(harness):
    seen = {}
    original = carrier.reclaim_trusted_stage

    def spy(stage):
        seen["events_before"] = list(harness.events)
        return original(stage)

    carrier.reclaim_trusted_stage = spy
    try:
        harness.run(**_prep(harness))
    finally:
        carrier.reclaim_trusted_stage = original
    stage = _input(harness)
    assert not (stage / "uv-bin").exists()
    assert (stage / "example.npz").read_bytes() == b"caller example"
    assert json.loads((stage / carrier.RECLAIMED_STAGE).read_bytes())[
        "uv_sha256"
    ] == digest(UV)
    # only after the container is confirmed removed, and before the result is associated
    assert "CLEANUP" in seen["events_before"]
    assert "ASSOCIATE" not in seen["events_before"]
    assert harness.ledger.status(owner="alice")["operations"][0]["state"] == "SUCCEEDED"


def test_a_failing_reclaim_never_changes_the_operations_outcome(harness, monkeypatch):
    def broken(stage):
        raise PermissionError("fixture: cannot remove")

    monkeypatch.setattr(carrier, "reclaim_trusted_stage", broken)
    harness.run(**_prep(harness))
    assert harness.ledger.status(owner="alice")["operations"][0]["state"] == "SUCCEEDED"
    assert (_input(harness) / "uv-bin").exists()
