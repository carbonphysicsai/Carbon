"""Offline dependency prep executes only trusted installer, never bundle code."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from carbon.development_session.bundle_construction_worker import (
    _checked_overlay_snapshot,
)
from carbon.development_session.library_bundles import (
    BUNDLE_SCHEMA,
    _environment_digest,
    bundle_ref,
)
from carbon.development_session.library_overlay_prep import prepare


def _digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _source() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, body in (
            ("source/candidate/__init__.py", b"raise RuntimeError('not imported')\n"),
            ("source/LICENSE", b"MIT\n"),
        ):
            item = tarfile.TarInfo(name)
            item.size = len(body)
            archive.addfile(item, io.BytesIO(body))
    return output.getvalue()


def _wheel() -> bytes:
    prefix = "overlaydep-1.dist-info/"
    files = {
        "overlaydep/__init__.py": b"VALUE = 1\n",
        prefix + "METADATA": b"Metadata-Version: 2.1\nName: overlaydep\nVersion: 1\n",
        prefix
        + "WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: carbon-test\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    rows = []
    for name, body in files.items():
        hashed = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=")
        rows.append(f"{name},sha256={hashed.decode()},{len(body)}")
    rows.append(prefix + "RECORD,,")
    files[prefix + "RECORD"] = ("\n".join(rows) + "\n").encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return output.getvalue()


@pytest.mark.skipif(os.name == "nt", reason="executable uv test uses POSIX mode")
def test_exact_offline_wheel_prep_exports_inert_bounded_overlay(tmp_path):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv binary unavailable in this diagnostic environment")
    source, wheel, license_text = _source(), _wheel(), b"MIT\n"
    wheel_name = "overlaydep-1-py3-none-any.whl"
    lock = (
        b"overlaydep==1 --hash=sha256:"
        + hashlib.sha256(wheel).hexdigest().encode()
        + b"\n"
    )
    base = "sha256:" + "c" * 64
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "name": "overlay-fixture",
        "language": "python",
        "source_sha256": _digest(source),
        "source_bytes": len(source),
        "runtime_profile_id": "torch-cu130-py311",
        "base_environment_digest": base,
        "environment_digest": _environment_digest(base, _digest(lock)),
        "os": "linux",
        "architecture": "amd64",
        "python_abi": "cp311",
        "accelerator": "cuda13",
        "lock_sha256": _digest(lock),
        "wheels": {wheel_name: _digest(wheel)},
        "license_sha256": _digest(license_text),
    }
    reference = bundle_ref(manifest, source, {wheel_name: wheel}, lock, license_text)
    inputs = tmp_path / "input"
    inputs.mkdir()
    for name, body in (
        ("bundle.json", json.dumps(manifest).encode()),
        ("source.tar.gz", source),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
        (wheel_name, wheel),
    ):
        (inputs / name).write_bytes(body)
    uv_bytes = Path(uv).read_bytes()
    (inputs / "uv-bin").write_bytes(uv_bytes)
    (inputs / "uv-bin").chmod(0o555)
    (inputs / "control.json").write_text(
        json.dumps(
            {
                "bundle_ref": reference.to_dict(),
                "parent_image_id": "sha256:" + "4" * 64,
                "uv_sha256": _digest(uv_bytes),
            }
        )
    )
    output = tmp_path / "output"
    output.mkdir()
    receipt = prepare(inputs, output, python_path=sys.executable)
    assert json.loads((output / "overlay.json").read_bytes()) == receipt
    assert receipt["bundle_ref"] == reference.to_dict()
    assert receipt["file_count"] >= 5
    assert receipt["archive_bytes"] == (output / "overlay.tar").stat().st_size
    with tarfile.open(output / "overlay.tar", "r:") as archive:
        names = {member.name for member in archive}
    assert "site-packages/overlaydep/__init__.py" in names
    assert "source/candidate/__init__.py" in names
    assert not (tmp_path / "not-imported").exists()
    assert (
        _checked_overlay_snapshot(output, reference.to_dict(), "sha256:" + "4" * 64)
        == receipt
    )
    tampered = {**receipt, "parent_image_id": "sha256:" + "5" * 64}
    (output / "overlay.json").write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="identity differs"):
        _checked_overlay_snapshot(output, reference.to_dict(), "sha256:" + "4" * 64)
