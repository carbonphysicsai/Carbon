"""The owner cache preserves a child image binding without granting runtime authority."""

import hashlib
import io
import json
import tarfile
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from carbon.development_session import library_environment_cache as cache
from carbon.development_session.direct_material_staging import _cache_lock
from carbon.development_session.library_bundles import (
    UV_IMAGE,
    LibraryBundleRef,
    ProvisionedLibraryEnvironment,
)
from carbon.development_session.research_image import LibraryWorkerImage
from carbon.reconstruction.worker.model import WorkerImageIdentity


def _sha(char):
    return "sha256:" + char * 64


def _image(context):
    parent = WorkerImageIdentity(
        _sha("a"),
        _sha("a"),
        _sha("b"),
        _sha("c"),
        _sha("d"),
        _sha("e"),
        _sha("f"),
        _sha("0"),
    )
    bundle = LibraryBundleRef(
        "carbon.library-bundle-ref.v1",
        _sha("1"),
        "python",
        "jax-cuda13-py311",
        _sha("2"),
    )
    environment = ProvisionedLibraryEnvironment(
        bundle, parent.image_id, context, _sha("3"), _sha("4")
    )
    return LibraryWorkerImage(environment, parent, bundle.to_dict())


def test_verified_overlay_seals_exact_archive_and_rejects_changed_cache(
    tmp_path, monkeypatch
):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    root = tmp_path / "private-cache"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    image = _image(tmp_path / "context")
    content = b"VALUE = 1\n"
    relative = "source/package.py"
    row = [relative, len(content), "sha256:" + hashlib.sha256(content).hexdigest()]
    with tarfile.open(
        snapshot / "overlay.tar", mode="w", format=tarfile.USTAR_FORMAT
    ) as archive:
        member = tarfile.TarInfo(relative)
        member.size = len(content)
        member.mode = 0o444
        archive.addfile(member, io.BytesIO(content))
    body = (snapshot / "overlay.tar").read_bytes()
    receipt = {
        "schema": cache.OVERLAY_SCHEMA,
        "bundle_ref": image.provisioned.bundle.to_dict(),
        "parent_image_id": image.parent.image_id,
        "archive_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
        "archive_bytes": len(body),
        "tree_digest": "sha256:"
        + hashlib.sha256(json.dumps([row], separators=(",", ":")).encode()).hexdigest(),
        "file_count": 1,
        "total_file_bytes": len(content),
    }
    (snapshot / "overlay.json").write_text(json.dumps(receipt), encoding="utf-8")
    args = {
        "expected_bundle": image.provisioned.bundle,
        "expected_parent": image.parent,
        "expected_receipt": receipt,
        "material_cache_bytes": 10 * 1024**2,
    }
    selected = cache.cache_verified_overlay(snapshot, root, **args)
    assert selected.path.name == receipt["tree_digest"][7:]
    assert (selected.path / relative).read_bytes() == content
    assert cache.cache_verified_overlay(snapshot, root, **args) == selected
    original_exists = type(selected.path).exists
    race = [2]

    def publish_race(path):
        if path == selected.path and race[0]:
            race[0] -= 1
            return False
        return original_exists(path)

    with monkeypatch.context() as patched:
        patched.setattr(type(selected.path), "exists", publish_race)
        assert cache.cache_verified_overlay(snapshot, root, **args) == selected
    second_parent = replace(image.parent, image_id=_sha("9"), config_digest=_sha("9"))
    second_receipt = {**receipt, "parent_image_id": second_parent.image_id}
    (snapshot / "overlay.json").write_text(json.dumps(second_receipt), encoding="utf-8")
    from carbon.development_session.direct_material_staging import _cache_bytes

    used = _cache_bytes(root)
    second_bytes = len(content) + len(
        json.dumps(second_receipt, sort_keys=True, separators=(",", ":")).encode()
    )
    with pytest.raises(ValueError, match="cache capacity exceeded"):
        cache.cache_verified_overlay(
            snapshot,
            root,
            expected_bundle=image.provisioned.bundle,
            expected_parent=second_parent,
            expected_receipt=second_receipt,
            material_cache_bytes=used + second_bytes - 1,
        )
    assert _cache_bytes(root) == used
    second = cache.cache_verified_overlay(
        snapshot,
        root,
        expected_bundle=image.provisioned.bundle,
        expected_parent=second_parent,
        expected_receipt=second_receipt,
        material_cache_bytes=10 * 1024**2,
    )
    assert second.path != selected.path
    assert (second.path / relative).read_bytes() == content
    (snapshot / "overlay.json").write_text(json.dumps(receipt), encoding="utf-8")
    changed = selected.path / relative
    changed.chmod(0o600)
    changed.write_bytes(b"VALUE = 2\n")
    with pytest.raises(ValueError, match="cached overlay content differs"):
        cache.cache_verified_overlay(snapshot, root, **args)
    with tarfile.open(
        snapshot / "overlay.tar", mode="w", format=tarfile.USTAR_FORMAT
    ) as archive:
        link = tarfile.TarInfo("source/bad.py")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        archive.addfile(link)
    body = (snapshot / "overlay.tar").read_bytes()
    receipt["archive_sha256"] = "sha256:" + hashlib.sha256(body).hexdigest()
    receipt["archive_bytes"] = len(body)
    (snapshot / "overlay.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="overlay archive member differs"):
        cache.cache_verified_overlay(
            snapshot, root, **{**args, "expected_receipt": receipt}
        )
    for unsafe in (r"source/..\..\outside", "source/C:outside"):
        with tarfile.open(
            snapshot / "overlay.tar", mode="w", format=tarfile.USTAR_FORMAT
        ) as archive:
            member = tarfile.TarInfo(unsafe)
            member.size = len(content)
            member.mode = 0o444
            archive.addfile(member, io.BytesIO(content))
        body = (snapshot / "overlay.tar").read_bytes()
        receipt["archive_sha256"] = "sha256:" + hashlib.sha256(body).hexdigest()
        receipt["archive_bytes"] = len(body)
        (snapshot / "overlay.json").write_text(json.dumps(receipt), encoding="utf-8")
        with pytest.raises(ValueError, match="overlay archive member differs"):
            cache.cache_verified_overlay(
                snapshot, root, **{**args, "expected_receipt": receipt}
            )
    assert not (tmp_path / "outside").exists()


def test_pinned_uv_copy_uses_local_digest_and_never_starts_container(tmp_path):
    uv = b"synthetic-uv-binary"
    container = "a" * 64
    calls = []
    timeouts = []

    class Docker:
        def __init__(self, *, malformed=False, slow_copy=False):
            self.create = None
            self.malformed = malformed
            self.slow_copy = slow_copy

        def json(self, arguments, *, timeout=30):
            timeouts.append((arguments[0], timeout))
            if arguments[:2] == ["image", "inspect"]:
                return {
                    "Id": "sha256:" + "b" * 64,
                    "RepoDigests": [
                        UV_IMAGE.split("@", 1)[0].rsplit(":", 1)[0]
                        + "@"
                        + UV_IMAGE.split("@", 1)[1]
                    ],
                }
            assert arguments == [
                "container",
                "inspect",
                self.create[2],
                "--format",
                "{{json .}}",
            ]
            label, intent = self.create[4].split("=", 1)
            return {
                "Id": container,
                "Name": "/" + self.create[2],
                "Image": "sha256:" + "b" * 64,
                "Config": {"Labels": {label: intent}},
            }

        def run(self, arguments, *, timeout=30):
            timeouts.append((arguments[0], timeout))
            calls.append(arguments)
            if arguments[0] == "create":
                self.create = arguments
                return SimpleNamespace(
                    stdout=("bad\n" if self.malformed else container + "\n").encode()
                )
            assert arguments == ["rm", "--force", container]
            return SimpleNamespace(stdout=b"")

        def stream_to_file(self, arguments, destination, **bounds):
            assert arguments == ["cp", f"{container}:/uv", "-"]
            assert bounds["maximum"] <= 65 * 1024**2
            timeouts.append(("cp", bounds["timeout"]))
            if self.slow_copy:
                time.sleep(0.04)
            with tarfile.open(
                destination, mode="w", format=tarfile.USTAR_FORMAT
            ) as archive:
                member = tarfile.TarInfo("uv")
                member.size = len(uv)
                archive.addfile(member, io.BytesIO(uv))

    assert cache.pinned_uv_bytes(Docker()) == uv
    assert calls[0][:2] == ["create", "--name"]
    assert calls[0][3] == "--label"
    assert calls[0][-5:] == [
        "--network",
        "none",
        "--entrypoint",
        "/bin/true",
        "sha256:" + "b" * 64,
    ]
    assert calls[1] == ["rm", "--force", container]
    with pytest.raises(ValueError, match="container identity invalid"):
        cache.pinned_uv_bytes(Docker(malformed=True))
    assert calls[-1] == ["rm", "--force", container]

    callbacks = []
    start = len(timeouts)
    assert (
        cache.pinned_uv_bytes(
            Docker(),
            deadline=time.monotonic() + 1.0,
            cancel=lambda: callbacks.append(True),
        )
        == uv
    )
    bounded = timeouts[start:]
    assert callbacks
    assert [name for name, _ in bounded] == [
        "image",
        "create",
        "container",
        "cp",
        "container",
        "rm",
    ]
    assert all(0 < value <= 1.0 for _, value in bounded[:4])
    assert bounded[-2:] == [("container", 30), ("rm", 30)]

    with pytest.raises(TimeoutError, match="pinned uv copy deadline exceeded"):
        cache.pinned_uv_bytes(Docker(slow_copy=True), deadline=time.monotonic() + 0.02)
    assert calls[-1] == ["rm", "--force", container]


def test_cache_round_trip_requires_verification_and_trusted_bindings(
    tmp_path, monkeypatch
):
    contexts = tmp_path / "contexts"
    context = contexts / "checked"
    context.mkdir(parents=True)
    image = _image(context)
    calls = []
    monkeypatch.setattr(cache, "_context_digest", lambda _: _sha("3"))
    monkeypatch.setattr(
        cache,
        "verify_library_worker_image",
        lambda candidate, cli: calls.append((candidate, cli)),
    )
    path = tmp_path / "image.json"
    adapter = object()

    cache.store_verified_library_worker_image(
        path, image, context_root=contexts, cli=adapter
    )
    assert calls == [(image, adapter)]
    assert (
        cache.load_cached_library_worker_image(
            path,
            expected_bundle=image.provisioned.bundle,
            expected_parent=image.parent,
            context_root=contexts,
        )
        == image
    )
    assert len(calls) == 1  # Cache loading does not claim Docker verification.

    record = json.loads(path.read_text(encoding="utf-8"))
    record["bundle"]["bundle_digest"] = _sha("9")
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="binding changed"):
        cache.load_cached_library_worker_image(
            path,
            expected_bundle=image.provisioned.bundle,
            expected_parent=image.parent,
            context_root=contexts,
        )


def test_cache_refuses_changed_context_and_unverified_write(tmp_path, monkeypatch):
    contexts = tmp_path / "contexts"
    context = contexts / "checked"
    context.mkdir(parents=True)
    image = _image(context)
    path = tmp_path / "image.json"
    monkeypatch.setattr(cache, "_context_digest", lambda _: _sha("3"))

    def refuse(_image, _cli):
        raise ValueError("child image unavailable")

    monkeypatch.setattr(cache, "verify_library_worker_image", refuse)
    with pytest.raises(ValueError, match="child image unavailable"):
        cache.store_verified_library_worker_image(
            path, image, context_root=contexts, cli=object()
        )
    assert not path.exists()

    monkeypatch.setattr(cache, "verify_library_worker_image", lambda _image, _cli: None)
    cache.store_verified_library_worker_image(
        path, image, context_root=contexts, cli=object()
    )
    monkeypatch.setattr(cache, "_context_digest", lambda _: _sha("8"))
    with pytest.raises(ValueError, match="invalid cached library worker image"):
        cache.load_cached_library_worker_image(
            path,
            expected_bundle=image.provisioned.bundle,
            expected_parent=image.parent,
            context_root=contexts,
        )


def test_admitted_install_reuses_verified_hit_and_reprovisions_for_new_parent(
    tmp_path, monkeypatch
):
    import_path = tmp_path / "user-input"
    cache_root = tmp_path / "owner-cache"
    cache_root.mkdir(mode=0o700)
    cache_root.chmod(0o700)
    image = _image(tmp_path / "placeholder")
    selected = image.provisioned.bundle
    material = ({"language": "python"}, b"source", {}, b"lock", b"license")
    provisions = []
    verifications = []
    monkeypatch.setattr(cache, "load_pinned_bundle_directory", lambda _: material)
    monkeypatch.setattr(cache, "bundle_ref", lambda *args: selected)
    monkeypatch.setattr(cache, "_context_digest", lambda _: _sha("3"))

    def prepare(root, *args):
        parent_id = args[-1]
        context = root / selected.bundle_digest[7:] / parent_id[7:]
        context.mkdir(parents=True, exist_ok=True, mode=0o700)
        context.parent.chmod(0o700)
        return context, selected.bundle_digest, _sha("3")

    def provision(root, expected_ref, *args, cli):
        parent_id = args[-1]
        provisions.append((expected_ref, parent_id, cli))
        context, _, digest = prepare(root, *args)
        return ProvisionedLibraryEnvironment(
            selected, parent_id, context, digest, _sha("4")
        )

    def verify(candidate, cli):
        verifications.append((candidate, cli))
        return candidate

    monkeypatch.setattr(cache, "prepare_offline_context", prepare)
    monkeypatch.setattr(cache, "provision_offline_bundle", provision)
    monkeypatch.setattr(cache, "verify_library_worker_image", verify)
    adapter = object()

    wrong_bundle = LibraryBundleRef(
        selected.schema,
        _sha("8"),
        selected.language,
        selected.runtime_profile_id,
        selected.environment_digest,
    )
    with pytest.raises(ValueError, match="recipe bundle reference differs"):
        cache.install_pinned_library_worker_image(
            import_path,
            cache_root,
            image.parent,
            expected_bundle=wrong_bundle,
            cli=adapter,
        )
    assert not provisions

    first = cache.install_pinned_library_worker_image(
        import_path, cache_root, image.parent, expected_bundle=selected, cli=adapter
    )
    receipt_path, context_path = cache.library_image_cache_paths(
        cache_root, selected, image.parent
    )
    assert context_path == first.provisioned.context
    assert receipt_path.is_file()
    second = cache.install_pinned_library_worker_image(
        import_path, cache_root, image.parent, expected_bundle=selected, cli=adapter
    )
    assert first == second
    assert len(provisions) == 1
    assert verifications == [(first, adapter), (second, adapter)]

    changed_parent = WorkerImageIdentity(
        _sha("9"),
        _sha("9"),
        _sha("b"),
        _sha("c"),
        _sha("d"),
        _sha("e"),
        _sha("f"),
        _sha("0"),
    )
    third = cache.install_pinned_library_worker_image(
        import_path,
        cache_root,
        changed_parent,
        expected_bundle=selected,
        cli=adapter,
    )
    assert third.parent == changed_parent
    assert len(provisions) == 2
    assert third.provisioned.context != first.provisioned.context

    receipt = receipt_path
    record = json.loads(receipt.read_text(encoding="utf-8"))
    record["parent"]["image_id"] = _sha("8")
    receipt.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):
        cache.install_pinned_library_worker_image(
            import_path, cache_root, image.parent, expected_bundle=selected, cli=adapter
        )
    assert len(provisions) == 2  # A corrupt hit never silently rebuilds.


def test_overlay_cache_lock_obeys_contended_deadline_and_task_cancel(
    tmp_path, monkeypatch
):
    root = tmp_path / "private-cache"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    called = []
    monkeypatch.setattr(
        cache,
        "_cache_verified_overlay_locked",
        lambda *args, **kwargs: called.append(True),
    )
    args = {
        "expected_bundle": None,
        "expected_parent": None,
        "expected_receipt": {},
        "material_cache_bytes": 1024,
    }
    with _cache_lock(root):
        start = time.monotonic()
        with pytest.raises(TimeoutError, match="material cache lock deadline exceeded"):
            cache.cache_verified_overlay(
                tmp_path / "unused",
                root,
                deadline=start + 0.12,
                **args,
            )
        assert 0.10 <= time.monotonic() - start < 1.0

        callbacks = []

        def cancelled():
            callbacks.append(True)
            if len(callbacks) == 3:
                raise InterruptedError("task cancelled")

        with pytest.raises(InterruptedError, match="task cancelled"):
            cache.cache_verified_overlay(
                tmp_path / "unused", root, cancel=cancelled, **args
            )
        assert len(callbacks) == 3
    assert not called
