"""A sealed owner cache becomes readable only inside the fixed C03 input."""

import hashlib
import json
import os
import stat

import pytest

from carbon.development_session.research_carrier import _stage_verified_overlay


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
