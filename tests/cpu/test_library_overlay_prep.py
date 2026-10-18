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
from dataclasses import replace
from pathlib import Path

import pytest

from carbon.development_session import bundle_construction_worker, library_overlay_prep
from carbon.development_session.bundle_construction_worker import (
    _checked_overlay_snapshot,
)
from carbon.development_session.library_bundles import (
    BUNDLE_SCHEMA,
    _environment_digest,
    bundle_ref,
    verify_bundle_parent_environment,
)
from carbon.development_session.library_overlay_prep import prepare
from carbon.reconstruction import torch_profile
from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.worker.model import WorkerImageIdentity


def _digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _parent_build(tmp_path: Path, monkeypatch, lock: bytes) -> dict:
    record = tmp_path / "worker-image-build.json"
    build = {
        "schema": "carbon.c03.worker-image-build.v1",
        "source_tree_digest": _digest(b"source"),
        "wheel_digest": _digest(b"wheels"),
        "lock_digest": _digest(lock),
        "base_image_digest": _digest(b"base image"),
        "build_recipe_digest": _digest(b"recipe"),
        "entrypoint_digest": _digest(b"entrypoint"),
    }
    record.write_text(json.dumps(build))
    monkeypatch.setattr(library_overlay_prep, "PARENT_BUILD_RECORD", record)
    return build


def _source(archive_root: str) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, body in (
            (
                f"{archive_root}/candidate/__init__.py",
                b"raise RuntimeError('not imported')\n",
            ),
            (f"{archive_root}/LICENSE", b"MIT\n"),
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


@pytest.mark.parametrize(
    "profile,lock,recipe",
    [
        ("python-cpu-py311", None, ".devcontainer/Dockerfile.reconstruction-worker"),
        (
            "jax-cuda13-py311",
            GPU_PROFILE.environment_lock_digest,
            ".devcontainer/accelerators/Dockerfile",
        ),
        (
            "torch-cu130-py311",
            torch_profile.GPU_LOCK_DIGEST,
            ".devcontainer/torch/Dockerfile.gpu",
        ),
    ],
)
def test_host_parent_requires_registered_lock_and_abi(profile, lock, recipe):
    root = Path(__file__).resolve().parents[2]
    lock = lock or _digest((root / "uv.lock").read_bytes())
    image = _digest(b"image")
    parent = WorkerImageIdentity(
        image_id=image,
        config_digest=image,
        source_tree_digest=_digest(b"source"),
        wheel_digest=_digest(b"wheels"),
        lock_digest=lock,
        base_image_digest=_digest(b"base image"),
        build_recipe_digest=_digest((root / recipe).read_bytes()),
        entrypoint_digest=_digest(
            (root / "carbon/reconstruction/worker/entrypoint.py").read_bytes()
        ),
    )
    manifest = {"runtime_profile_id": profile, "base_environment_digest": lock}
    verify_bundle_parent_environment(manifest, parent)
    with pytest.raises(ValueError, match="parent environment or ABI differs"):
        verify_bundle_parent_environment(
            {**manifest, "base_environment_digest": _digest(b"different")}, parent
        )
    with pytest.raises(ValueError, match="parent environment or ABI differs"):
        verify_bundle_parent_environment(
            manifest,
            replace(parent, build_recipe_digest=_digest(b"different recipe")),
        )


@pytest.mark.parametrize(
    "profile,lock_name",
    [
        ("python-cpu-py311", None),
        ("jax-cuda13-py311", "accelerator-requirements.txt"),
        ("torch-cu130-py311", "torch-gpu-requirements.txt"),
    ],
)
def test_parent_environment_requires_installed_base_lock(
    tmp_path, monkeypatch, profile, lock_name
):
    base_lock = b"installed base lock\n"
    build = _parent_build(tmp_path, monkeypatch, base_lock)
    manifest = {
        "runtime_profile_id": profile,
        "base_environment_digest": _digest(base_lock),
    }
    if lock_name is not None:
        lock_path = tmp_path / lock_name
        lock_path.write_bytes(base_lock)
        monkeypatch.setattr(
            library_overlay_prep, "GPU_BASE_LOCK_PATHS", {profile: lock_path}
        )
    library_overlay_prep._verify_parent_environment(manifest, build)

    with pytest.raises(ValueError, match="base environment differs"):
        library_overlay_prep._verify_parent_environment(
            {**manifest, "base_environment_digest": _digest(b"another base")}, build
        )
    with pytest.raises(ValueError, match="base environment differs"):
        library_overlay_prep._verify_parent_environment(
            manifest, {**build, "build_recipe_digest": _digest(b"other recipe")}
        )
    if lock_name is not None:
        lock_path.write_bytes(b"different installed lock\n")
        with pytest.raises(ValueError, match="accelerator lock differs"):
            library_overlay_prep._verify_parent_environment(manifest, build)


def test_parent_environment_requires_build_record(tmp_path, monkeypatch):
    monkeypatch.setattr(
        library_overlay_prep, "PARENT_BUILD_RECORD", tmp_path / "missing.json"
    )
    with pytest.raises(ValueError, match="parent build record unavailable"):
        library_overlay_prep._verify_parent_environment(
            {
                "runtime_profile_id": "python-cpu-py311",
                "base_environment_digest": _digest(b"base"),
            },
            {},
        )


@pytest.mark.skipif(os.name == "nt", reason="executable uv test uses POSIX mode")
@pytest.mark.parametrize(
    "archive_root", ["source", "transolver-original-stock-75e0f676-v1"]
)
def test_exact_offline_wheel_prep_exports_inert_bounded_overlay(
    tmp_path, archive_root, monkeypatch
):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv binary unavailable in this diagnostic environment")
    source, wheel, license_text = _source(archive_root), _wheel(), b"MIT\n"
    wheel_name = "overlaydep-1-py3-none-any.whl"
    lock = (
        b"overlaydep==1 --hash=sha256:"
        + hashlib.sha256(wheel).hexdigest().encode()
        + b"\n"
    )
    base_lock = b"torch base lock\n"
    base = _digest(base_lock)
    build = _parent_build(tmp_path, monkeypatch, base_lock)
    gpu_lock = tmp_path / "torch-gpu-requirements.txt"
    gpu_lock.write_bytes(base_lock)
    monkeypatch.setattr(
        library_overlay_prep,
        "GPU_BASE_LOCK_PATHS",
        {"torch-cu130-py311": gpu_lock},
    )
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
                "parent_build": build,
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

    class DeclaredArchive:
        def __init__(self, member):
            self.member = member

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def __iter__(self):
            yield self.member

        def extractfile(self, _):
            raise AssertionError("unsafe member must be refused before materializing")

    for kind, size in (
        (tarfile.GNUTYPE_SPARSE, 1),
        (tarfile.REGTYPE, 128 * 1024**2),
    ):
        member = tarfile.TarInfo("source/candidate.py")
        member.type = kind
        member.size = size
        with monkeypatch.context() as patch:
            patch.setattr(
                bundle_construction_worker.tarfile,
                "open",
                lambda *_args, member=member, **_kwargs: DeclaredArchive(member),
            )
            with pytest.raises(ValueError, match="member differs"):
                _checked_overlay_snapshot(
                    output, reference.to_dict(), "sha256:" + "4" * 64
                )

    tampered = {**receipt, "parent_image_id": "sha256:" + "5" * 64}
    (output / "overlay.json").write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="identity differs"):
        _checked_overlay_snapshot(output, reference.to_dict(), "sha256:" + "4" * 64)
