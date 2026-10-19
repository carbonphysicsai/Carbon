"""A sealed owner cache becomes readable only inside the fixed C03 input."""

import hashlib
import json
import os
import stat

import pytest

from carbon.development_session.library_bundles import UV_IMAGE
from carbon.development_session.research_carrier import (
    LIBRARY_PREP_PROVENANCE,
    _checked_pinned_uv_stage,
    _run_locked,
    _stage_verified_overlay,
)
from carbon.reconstruction.worker.model import WorkerImageIdentity


@pytest.mark.skipif(os.name == "nt", reason="POSIX container UID mode check")
def test_stage_overlay_preserves_private_cas_and_verifies_readable_copy(tmp_path):
    source = tmp_path / "private-cache"
    package = source / "source"
    package.mkdir(parents=True)
    body = b"VALUE = 1\n"
    (package / "candidate.py").write_bytes(body)
    row = [
        "source/candidate.py",
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
    (package / "candidate.py").chmod(0o400)
    (source / ".overlay.json").chmod(0o400)
    package.chmod(0o500)
    source.chmod(0o500)

    copied = tmp_path / "operation-input" / "overlay"
    copied.parent.mkdir()
    _stage_verified_overlay(source, copied, receipt)
    assert (copied / "source" / "candidate.py").read_bytes() == body
    assert stat.S_IMODE(source.stat().st_mode) == 0o500
    assert stat.S_IMODE((package / "candidate.py").stat().st_mode) == 0o400
    assert stat.S_IMODE(copied.stat().st_mode) == 0o555
    assert stat.S_IMODE((copied / "source").stat().st_mode) == 0o555
    assert stat.S_IMODE((copied / "source" / "candidate.py").stat().st_mode) == 0o444
    assert stat.S_IMODE((copied / ".overlay.json").stat().st_mode) == 0o444

    (copied / "source" / "candidate.py").chmod(0o644)
    (copied / "source" / "candidate.py").write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="cached overlay content differs"):
        _stage_verified_overlay(copied, tmp_path / "bad-copy", receipt)


@pytest.mark.parametrize("bind_parent", [False, True])
def test_pinned_uv_copy_does_not_run_before_ledger_reservation(tmp_path, bind_parent):
    class RefusingLedger:
        root = tmp_path

        def reserve(self, *_args, **_kwargs):
            raise ValueError("ledger admission refused")

    called = []
    parent_id = "sha256:" + "4" * 64
    parent = WorkerImageIdentity(*(parent_id for _ in range(8)))
    with pytest.raises(ValueError, match="ledger admission refused"):
        _run_locked(
            RefusingLedger(),
            owner="miner",
            identity="direct-prep-fixture",
            source="print('fixed')",
            files={},
            image=parent,
            seconds=600,
            provenance=LIBRARY_PREP_PROVENANCE,
            extra_resources={},
            executable_files=("uv-bin",),
            trusted_stage_identity={
                "schema": "carbon.development.pinned-uv-stage.v1",
                "uv_image": UV_IMAGE,
                "bundle_ref": {},
                "parent_image_id": parent_id,
                **({"parent_build": _parent_build(parent_id)} if bind_parent else {}),
            },
            trusted_stage_provider=lambda _cli: called.append(True),
        )
    assert called == []


def _parent_build(value):
    return {
        "schema": "carbon.c03.worker-image-build.v1",
        **{
            name: value
            for name in (
                "source_tree_digest",
                "wheel_digest",
                "lock_digest",
                "base_image_digest",
                "build_recipe_digest",
                "entrypoint_digest",
            )
        },
    }


@pytest.mark.parametrize(
    "field", ["parent_image_id", "lock_digest", "entrypoint_digest"]
)
def test_prep_rejects_parent_metadata_drift_before_reservation(tmp_path, field):
    class PoisonLedger:
        root = tmp_path

        def reserve(self, *_args, **_kwargs):
            raise AssertionError("invalid parent reached resource reservation")

    parent_id = "sha256:" + "4" * 64
    parent = WorkerImageIdentity(*(parent_id for _ in range(8)))
    binding = {
        "schema": "carbon.development.pinned-uv-stage.v1",
        "uv_image": UV_IMAGE,
        "bundle_ref": {},
        "parent_image_id": parent_id,
        "parent_build": _parent_build(parent_id),
    }
    if field == "parent_image_id":
        binding[field] = "sha256:" + "5" * 64
    else:
        binding["parent_build"][field] = "sha256:" + "5" * 64
    with pytest.raises(ValueError, match="pinned UV stage parent differs"):
        _run_locked(
            PoisonLedger(),
            owner="miner",
            identity="direct-prep-fixture",
            source="print('fixed')",
            files={},
            image=parent,
            seconds=600,
            provenance=LIBRARY_PREP_PROVENANCE,
            extra_resources={},
            executable_files=("uv-bin",),
            trusted_stage_identity=binding,
            trusted_stage_provider=lambda _cli: pytest.fail(
                "copied UV before admission"
            ),
        )


@pytest.mark.parametrize("bind_parent", [False, True])
def test_uv_stage_control_preserves_frozen_parent_binding(bind_parent):
    parent_id = "sha256:" + "4" * 64
    uv = b"pinned-binary-fixture"
    identity = {
        "schema": "carbon.development.pinned-uv-stage.v1",
        "uv_image": UV_IMAGE,
        "bundle_ref": {},
        "parent_image_id": parent_id,
    }
    control = {
        "bundle_ref": {},
        "parent_image_id": parent_id,
        "uv_sha256": "sha256:" + hashlib.sha256(uv).hexdigest(),
    }
    if bind_parent:
        identity["parent_build"] = _parent_build(parent_id)
        control["parent_build"] = _parent_build(parent_id)
    added = {"uv-bin": uv, "control.json": json.dumps(control).encode()}
    assert _checked_pinned_uv_stage(added, identity) == added
    if bind_parent:
        control["parent_build"]["lock_digest"] = "sha256:" + "5" * 64
    else:
        control["parent_build"] = _parent_build(parent_id)
    added["control.json"] = json.dumps(control).encode()
    with pytest.raises(ValueError, match="pinned UV stage control differs"):
        _checked_pinned_uv_stage(added, identity)
