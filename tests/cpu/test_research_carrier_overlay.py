"""A sealed owner cache becomes readable only inside the fixed C03 input."""

import hashlib
import json
import os
import stat

import pytest

from carbon.development_session.library_bundles import UV_IMAGE
from carbon.development_session.research_carrier import (
    LIBRARY_PREP_PROVENANCE,
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


def test_pinned_uv_copy_does_not_run_before_ledger_reservation(tmp_path):
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
            },
            trusted_stage_provider=lambda _cli: called.append(True),
        )
    assert called == []
