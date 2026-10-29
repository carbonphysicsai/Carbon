"""The owner cache preserves a child image binding without granting runtime authority."""

import hashlib
import io
import json
import tarfile
import time
from dataclasses import replace
from pathlib import Path
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
from carbon.reconstruction.worker.model import (
    WorkerCode,
    WorkerFailure,
    WorkerImageIdentity,
)


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


class _Inspector:
    """A fake daemon for `image inspect`: it prints the requested ids it holds and, for each it does not, Docker's own
    "No such image" line on stderr with rc 1 (the real daemon's behaviour, probed on Docker 29.9.2).
    """

    def __init__(self, held, *, drop=None, raise_on=None, stderr_extra=b"", rc=None):
        self.held = set(held)
        self.drop, self.raise_on = drop, raise_on
        self.stderr_extra, self.rc = stderr_extra, rc
        self.calls = []
        self.active = self.peak = 0
        import threading

        self._lock = threading.Lock()

    def run(self, arguments, *, accepted=(0,)):
        with self._lock:
            self.calls.append(list(arguments))
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(0.01)
            assert arguments[:2] == ["image", "inspect"]
            assert arguments[-2:] == ["--format", "{{json .Id}}"]
            selected = arguments[2:-2]
            if self.raise_on is not None and self.raise_on in selected:
                raise WorkerFailure(WorkerCode.RUNTIME)
            shown = [value for value in selected if value in self.held]
            if self.drop is not None and self.drop in shown:
                shown.remove(self.drop)
            absent = [value for value in selected if value not in self.held]
            code = (1 if absent else 0) if self.rc is None else self.rc
            if code not in accepted:
                raise WorkerFailure(WorkerCode.RUNTIME)
            lines = [
                f"Error response from daemon: No such image: {value}"
                for value in absent
            ]
            # The real daemon prints one blank line on stdout when every requested id is absent.
            printed = "\n".join(json.dumps(value) for value in shown).encode()
            return SimpleNamespace(
                stdout=b"\n" if absent and not shown else printed,
                stderr=("\n".join(lines).encode() + self.stderr_extra),
                returncode=code,
            )
        finally:
            with self._lock:
                self.active -= 1


def test_presence_batches_exact_immutable_ids_without_building_or_listing():
    daemon = _Inspector({_sha("4")})
    assert cache.present_library_worker_images(
        [_sha("4"), _sha("4"), _sha("5")], cli=daemon
    ) == frozenset({_sha("4")})
    assert daemon.calls == [
        ["image", "inspect", _sha("4"), _sha("5"), "--format", "{{json .Id}}"]
    ]


def test_presence_includes_untagged_and_intermediate_children_by_exact_id():
    tagged, untagged, intermediate, missing = (_sha(char) for char in "4567")
    daemon = _Inspector({tagged, untagged, intermediate})
    found = cache.present_library_worker_images(
        [untagged, intermediate, tagged, missing, untagged], cli=daemon
    )
    assert found == frozenset({tagged, untagged, intermediate})
    assert len(daemon.calls) == 1 and daemon.calls[0][2:-2] == sorted(
        [tagged, untagged, intermediate, missing]
    )


def test_presence_of_only_missing_children_reads_absence_from_the_daemons_own_line():
    daemon = _Inspector(set())
    assert (
        cache.present_library_worker_images([_sha("5"), _sha("5")], cli=daemon)
        == frozenset()
    )
    assert len(daemon.calls) == 1
    nothing = _Inspector(set())
    assert cache.present_library_worker_images([], cli=nothing) == frozenset()
    # With nothing to find it still checks the daemon answers an exact query (an id none can hold).
    assert nothing.calls == [
        ["image", "inspect", "sha256:" + "0" * 64, "--format", "{{json .Id}}"]
    ]
    with pytest.raises(WorkerFailure):
        cache.present_library_worker_images(
            [], cli=_Inspector(set(), raise_on="sha256:" + "0" * 64)
        )


@pytest.mark.parametrize(
    "fault",
    [
        "unreachable",
        "tag",
        "partial",
        "wrong_id",
        "duplicate",
        "unknown_error",
        "rc0_with_missing_line",
        "rc1_without_line",
        "missing_line_for_other_id",
        "unlisted_rc",
    ],
)
def test_image_presence_never_accepts_unknown_or_partial_metadata(fault):
    class CLI:
        def run(self, arguments, *, accepted=(0,)):
            if fault == "unreachable":
                raise WorkerFailure(WorkerCode.RUNTIME)
            absent = "Error response from daemon: No such image: " + _sha("5")
            both = [_sha("4"), _sha("5")]
            table = {
                "tag": ("not-an-image-id", "", 0),
                "partial": (json.dumps(_sha("4")), "", 0),
                "wrong_id": (
                    "\n".join(json.dumps(v) for v in [_sha("4"), _sha("9")]),
                    "",
                    0,
                ),
                "duplicate": (
                    "\n".join(json.dumps(v) for v in [_sha("4"), _sha("4")]),
                    "",
                    0,
                ),
                "unknown_error": (
                    json.dumps(_sha("4")),
                    "Cannot connect to the Docker daemon",
                    1,
                ),
                "rc0_with_missing_line": (
                    "\n".join(json.dumps(v) for v in both),
                    absent,
                    0,
                ),
                "rc1_without_line": (json.dumps(_sha("4")), "", 1),
                "missing_line_for_other_id": (
                    json.dumps(_sha("4")),
                    "Error response from daemon: No such image: " + _sha("9"),
                    1,
                ),
                "unlisted_rc": ("\n".join(json.dumps(v) for v in both), "", 2),
            }
            out, err, code = table[fault]
            if code not in accepted:
                raise WorkerFailure(WorkerCode.RUNTIME)
            return SimpleNamespace(
                stdout=out.encode(), stderr=err.encode(), returncode=code
            )

    with pytest.raises((ValueError, WorkerFailure)):
        cache.present_library_worker_images([_sha("4"), _sha("5")], cli=CLI())


@pytest.mark.parametrize(
    "fault",
    [None, "build_failure", "verification_failure", "unreachable", "corrupt_cache"],
)
def test_receiver_opt_in_rebuilds_only_a_missing_child_and_preserves_failed_receipts(
    tmp_path, monkeypatch, fault
):
    root = tmp_path / "private-cache"
    context = root / _sha("1")[7:] / _sha("a")[7:]
    context.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    context.parent.chmod(0o700)
    image = _image(context)
    selected = image.provisioned.bundle
    receipt, _ = cache.library_image_cache_paths(root, selected, image.parent)
    state = {"images": {image.image_id}, "provisions": [], "queries": []}
    monkeypatch.setattr(cache, "_context_digest", lambda _: _sha("3"))

    def verify(candidate, cli):
        if candidate.image_id not in state["images"] or (
            fault == "verification_failure" and candidate.image_id == _sha("5")
        ):
            raise ValueError("synthetic child verification failed")
        return candidate

    monkeypatch.setattr(cache, "verify_library_worker_image", verify)
    cache.store_verified_library_worker_image(
        receipt, image, context_root=context.parent, cli=object()
    )
    if fault == "corrupt_cache":
        record = json.loads(receipt.read_bytes())
        record["parent"]["image_id"] = _sha("9")
        receipt.write_text(json.dumps(record))
    original = receipt.read_bytes()
    state["images"].clear()
    monkeypatch.setattr(cache, "load_pinned_bundle_directory", lambda _: (None,))
    monkeypatch.setattr(cache, "bundle_ref", lambda *args: selected)
    monkeypatch.setattr(
        cache,
        "prepare_offline_context",
        lambda *args: (context, selected.bundle_digest, _sha("3")),
    )

    class CLI:
        def run(self, arguments, *, accepted=(0,)):
            state["queries"].append(arguments)
            if fault == "unreachable":
                raise WorkerFailure(WorkerCode.RUNTIME)
            assert arguments[:2] == ["image", "inspect"]
            ids = arguments[2:-2]
            held = [value for value in ids if value in state["images"]]
            absent = [value for value in ids if value not in state["images"]]
            lines = [
                f"Error response from daemon: No such image: {value}"
                for value in absent
            ]
            # The daemon prints one blank line when every requested id is absent.
            printed = "\n".join(json.dumps(value) for value in held).encode()
            return SimpleNamespace(
                stdout=b"\n" if absent and not held else printed,
                stderr="\n".join(lines).encode(),
                returncode=1 if absent else 0,
            )

    def provision(*args, cli):
        assert receipt.read_bytes() == original
        state["provisions"].append(args)
        if fault == "build_failure":
            raise ValueError("synthetic build failed")
        state["images"].add(_sha("5"))
        return replace(image.provisioned, image_id=_sha("5"))

    monkeypatch.setattr(cache, "provision_offline_bundle", provision)

    def install():
        return cache.install_pinned_library_worker_image(
            tmp_path / "synthetic-source",
            root,
            image.parent,
            expected_bundle=selected,
            cli=CLI(),
            rebuild_missing=True,
        )

    if fault is not None:
        with pytest.raises((ValueError, WorkerFailure)):
            install()
        assert receipt.read_bytes() == original
        if fault in {"unreachable", "corrupt_cache"}:
            assert state["provisions"] == []
        if fault == "corrupt_cache":
            assert state["queries"] == []
    else:
        repaired = install()
        assert repaired.image_id == _sha("5") and len(state["provisions"]) == 1
        assert (
            cache.load_cached_library_worker_image(
                receipt,
                expected_bundle=selected,
                expected_parent=image.parent,
                context_root=context.parent,
            )
            == repaired
        )
        assert install() == repaired and len(state["provisions"]) == 1


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
    cache.hold(selected)  # in flight: nothing is evictable, so this still refuses
    with pytest.raises(ValueError, match="cache capacity exceeded"):
        cache.cache_verified_overlay(
            snapshot,
            root,
            expected_bundle=image.provisioned.bundle,
            expected_parent=second_parent,
            expected_receipt=second_receipt,
            material_cache_bytes=used + second_bytes - 1,
        )
    cache.release(selected)
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


@pytest.mark.parametrize(
    "repository_digest",
    [
        UV_IMAGE,
        "ghcr.io/astral-sh/uv@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945",
    ],
    ids=["actual-tag-qualified-digest", "repository-digest"],
)
def test_pinned_uv_copy_uses_local_digest_and_never_starts_container(
    tmp_path, repository_digest
):
    uv = b"synthetic-uv-binary"
    container = "a" * 64
    calls = []
    copies = []
    timeouts = []

    class Docker:
        def __init__(
            self,
            *,
            malformed=False,
            slow_copy=False,
            repo_digest=repository_digest,
            malformed_repo_digests=False,
        ):
            self.create = None
            self.malformed = malformed
            self.slow_copy = slow_copy
            self.repo_digest = repo_digest
            self.malformed_repo_digests = malformed_repo_digests

        def json(self, arguments, *, timeout=30):
            timeouts.append((arguments[0], timeout))
            if arguments[:2] == ["image", "inspect"]:
                return {
                    "Id": "sha256:" + "b" * 64,
                    "RepoDigests": (
                        self.repo_digest
                        if self.malformed_repo_digests
                        else [self.repo_digest]
                    ),
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
            if arguments[0] == "cp":
                # a file copy to an absolute path in a private directory, never to "-" (a Docker CLI
                # resolves "-" against its working directory)
                assert arguments[1] == f"{container}:/uv"
                assert arguments[2] != "-" and Path(arguments[2]).is_absolute()
                if self.slow_copy:
                    time.sleep(0.04)
                Path(arguments[2]).write_bytes(uv)
                copies.append(arguments)
                return SimpleNamespace(stdout=b"")
            calls.append(arguments)
            if arguments[0] == "create":
                self.create = arguments
                return SimpleNamespace(
                    stdout=("bad\n" if self.malformed else container + "\n").encode()
                )
            assert arguments == ["rm", "--force", container]
            return SimpleNamespace(stdout=b"")

    assert cache.pinned_uv_bytes(Docker()) == uv
    assert len(copies) == 1
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

    before = len(calls)
    for refused in (
        "ghcr.io/astral-sh/uv:0.12.7@sha256:" + "0" * 64,
        "ghcr.io/astral-sh/uv@sha256:" + "0" * 64,
        "ghcr.io/astral-sh/uv:0.12.7",
        UV_IMAGE.replace(":0.12.7@", ":different-tag@"),
        UV_IMAGE.replace("astral-sh/uv", "another-owner/uv"),
    ):
        with pytest.raises(ValueError, match="pinned local uv image differs"):
            cache.pinned_uv_bytes(Docker(repo_digest=refused))
    for malformed in (repository_digest, {repository_digest: True}, None):
        with pytest.raises(ValueError, match="pinned local uv image differs"):
            cache.pinned_uv_bytes(
                Docker(repo_digest=malformed, malformed_repo_digests=True)
            )
    assert len(calls) == before  # No create, copy or cleanup for an unpinned image.


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


def test_a_record_is_host_portable_and_still_refuses_a_tampered_one(
    tmp_path, monkeypatch
):
    """A record names its context relative to the context root, so it loads on a host whose state sits under
    another path; the digests and bindings still decide, and nothing escapes the new root.
    """
    old_root = tmp_path / "host-a" / "contexts"
    (old_root / "checked").mkdir(parents=True)
    image = _image(old_root / "checked")
    monkeypatch.setattr(cache, "_context_digest", lambda _: _sha("3"))
    monkeypatch.setattr(cache, "verify_library_worker_image", lambda *_: None)
    path = tmp_path / "image.json"
    cache.store_verified_library_worker_image(
        path, image, context_root=old_root, cli=object()
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["provisioned"]["context"] == "checked"  # no host path in the record

    new_root = tmp_path / "host-b" / "state" / "contexts"
    (new_root / "checked").mkdir(parents=True)
    loaded = cache.load_cached_library_worker_image(
        path,
        expected_bundle=image.provisioned.bundle,
        expected_parent=image.parent,
        context_root=new_root,
    )
    assert loaded.provisioned.context == new_root / "checked"
    assert loaded.provisioned.context_digest == image.provisioned.context_digest
    assert loaded.provisioned.image_id == image.provisioned.image_id

    def tampered(change):
        edited = json.loads(path.read_text(encoding="utf-8"))
        change(edited["provisioned"])
        other = tmp_path / "tampered.json"
        other.write_text(json.dumps(edited), encoding="utf-8")
        other.chmod(0o600)
        return other

    def refused(record_path, root=new_root):
        with pytest.raises(ValueError, match="invalid cached library worker image"):
            cache.load_cached_library_worker_image(
                record_path,
                expected_bundle=image.provisioned.bundle,
                expected_parent=image.parent,
                context_root=root,
            )

    monkeypatch.setattr(cache, "_context_digest", lambda _: _sha("8"))
    refused(path)  # the directory's content no longer matches the recorded digest
    monkeypatch.setattr(cache, "_context_digest", lambda _: _sha("3"))
    for escape in ("../checked", "/etc", "checked/../../x", "", "a\b"):
        refused(tampered(lambda p, e=escape: p.update(context=e)))
    refused(tampered(lambda p: p.update(context_digest=_sha("9"))))  # digest differs
    (tmp_path / "elsewhere").mkdir()
    (new_root / "link").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    refused(tampered(lambda p: p.update(context="link")))
    (new_root / "file").write_text("x")
    refused(tampered(lambda p: p.update(context="file")))


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


# --- eviction: least-recently-used overlays no in-flight build holds ---------------


def _prepared(tmp_path, tag, size):
    """A snapshot (overlay.tar + overlay.json) of one ``size``-byte file for a parent
    named by ``tag``, and the cache arguments for it."""
    image = _image(tmp_path / f"context-{tag}")
    parent = replace(image.parent, image_id=_sha(tag), config_digest=_sha(tag))
    snapshot = tmp_path / f"snapshot-{tag}"
    snapshot.mkdir()
    content = (tag * size).encode()[:size]
    relative = "source/big.bin"
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
        "parent_image_id": parent.image_id,
        "archive_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
        "archive_bytes": len(body),
        "tree_digest": "sha256:"
        + hashlib.sha256(json.dumps([row], separators=(",", ":")).encode()).hexdigest(),
        "file_count": 1,
        "total_file_bytes": len(content),
    }
    (snapshot / "overlay.json").write_text(json.dumps(receipt), encoding="utf-8")
    return snapshot, {
        "expected_bundle": image.provisioned.bundle,
        "expected_parent": parent,
        "expected_receipt": receipt,
    }


def _cache_root(tmp_path):
    root = tmp_path / "private-cache"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def test_two_max_size_overlays_in_sequence_both_build_by_evicting_the_idle_first(
    tmp_path,
):
    size = 40 * 1024**2
    capacity = 60 * 1024**2  # one overlay fits, two do not
    root = _cache_root(tmp_path)
    first_snapshot, first_args = _prepared(tmp_path, "1", size)
    second_snapshot, second_args = _prepared(tmp_path, "2", size)
    first = cache.cache_verified_overlay(
        first_snapshot, root, material_cache_bytes=capacity, **first_args
    )
    assert first.path.is_dir()
    second = cache.cache_verified_overlay(
        second_snapshot, root, material_cache_bytes=capacity, **second_args
    )
    assert second.path.is_dir()
    assert not first.path.exists()  # evicted: nothing held it
    from carbon.development_session.direct_material_staging import _cache_bytes

    assert _cache_bytes(root) <= capacity


def test_two_concurrent_overlays_still_refuse_typed(tmp_path):
    size = 40 * 1024**2
    capacity = 60 * 1024**2
    root = _cache_root(tmp_path)
    first_snapshot, first_args = _prepared(tmp_path, "1", size)
    second_snapshot, second_args = _prepared(tmp_path, "2", size)
    first = cache.cache_verified_overlay(
        first_snapshot, root, material_cache_bytes=capacity, **first_args
    )
    cache.hold(first)  # an in-flight build is using it
    try:
        with pytest.raises(cache.OverlayCacheCapacityExceeded) as refused:
            cache.cache_verified_overlay(
                second_snapshot, root, material_cache_bytes=capacity, **second_args
            )
        assert "cache capacity exceeded" in str(refused.value)
        assert first.path.is_dir()  # the held overlay was not touched
    finally:
        cache.release(first)
    # once the first build ends, the second can be built
    second = cache.cache_verified_overlay(
        second_snapshot, root, material_cache_bytes=capacity, **second_args
    )
    assert second.path.is_dir() and not first.path.exists()


def test_the_least_recently_used_idle_overlay_goes_first(tmp_path):
    size = 20 * 1024**2
    capacity = 50 * 1024**2  # two fit, three do not
    root = _cache_root(tmp_path)
    built = []
    for tag in ("1", "2"):
        snapshot, args = _prepared(tmp_path, tag, size)
        built.append(
            (
                snapshot,
                args,
                cache.cache_verified_overlay(
                    snapshot, root, material_cache_bytes=capacity, **args
                ),
            )
        )
    # touch the first again so the second is the older use
    cache.cache_verified_overlay(
        built[0][0], root, material_cache_bytes=capacity, **built[0][1]
    )
    third_snapshot, third_args = _prepared(tmp_path, "3", size)
    third = cache.cache_verified_overlay(
        third_snapshot, root, material_cache_bytes=capacity, **third_args
    )
    assert built[0][2].path.is_dir() and third.path.is_dir()
    assert not built[1][2].path.exists()


# ---- readiness latency: bounded exact queries and call-local reuse ----------------------------------------
def _ids(count):
    return [
        (
            _sha(format(index, "x").zfill(64)[-1])
            if False
            else "sha256:" + format(index, "064x")
        )
        for index in range(count)
    ]


def test_many_children_are_inspected_in_bounded_chunks_each_id_once_and_read_back_exactly():
    ids = _ids(236)
    daemon = _Inspector(ids)
    found = cache.present_library_worker_images(ids, cli=daemon)
    assert found == frozenset(ids)
    assert len(daemon.calls) == -(-236 // cache.INSPECT_CHUNK)
    assert all(len(call[2:-2]) <= cache.INSPECT_CHUNK for call in daemon.calls)
    asked = [value for call in daemon.calls for value in call[2:-2]]
    assert sorted(asked) == sorted(ids) and len(asked) == len(set(asked))
    assert daemon.peak <= cache.INSPECT_WORKERS


def test_a_chunk_that_returns_a_different_set_or_fails_makes_the_whole_read_fail_closed():
    ids = _ids(120)
    with pytest.raises(ValueError, match="inspection differs"):
        cache.present_library_worker_images(ids, cli=_Inspector(ids, drop=ids[77]))
    with pytest.raises(WorkerFailure):
        cache.present_library_worker_images(ids, cli=_Inspector(ids, raise_on=ids[99]))


def test_missing_ids_across_chunks_are_absent_and_the_rest_present():
    ids = _ids(120)
    held = set(ids) - {ids[3], ids[90]}
    found = cache.present_library_worker_images(ids, cli=_Inspector(held))
    assert found == frozenset(held)


def test_any_extra_stderr_text_fails_closed_even_when_every_id_is_accounted_for():
    ids = _ids(3)
    with pytest.raises(ValueError, match="unknown error"):
        cache.present_library_worker_images(
            ids, cli=_Inspector(ids, stderr_extra=b"\nWarning: something else")
        )


def test_a_blank_stdout_line_from_an_all_absent_inspect_is_not_an_id():
    """Probed on Docker 29.9.2 (containerd store): inspecting only absent ids prints one blank stdout line, which broke the
    rebuild of a missing child with `JSONDecodeError` (Test Runner, 2026-10-29). Only blank lines are skipped.
    """
    absent = _sha("7")

    class Daemon:
        def __init__(self, stdout):
            self.stdout = stdout

        def run(self, arguments, *, accepted=(0,)):
            return SimpleNamespace(
                stdout=self.stdout,
                stderr=f"Error response from daemon: No such image: {absent}\n".encode(),
                returncode=1,
            )

    assert (
        cache.present_library_worker_images([absent], cli=Daemon(b"\n")) == frozenset()
    )
    assert (
        cache.present_library_worker_images([absent], cli=Daemon(b"\n\n"))
        == frozenset()
    )
    with pytest.raises(ValueError):
        cache.present_library_worker_images([absent], cli=Daemon(b"not json\n"))
    # An id printed while another is reported absent still counts as present, blank lines or not.
    other = _sha("8")

    class Mixed:
        def run(self, arguments, *, accepted=(0,)):
            return SimpleNamespace(
                stdout=(json.dumps(other) + "\n\n").encode(),
                stderr=f"Error response from daemon: No such image: {absent}\n".encode(),
                returncode=1,
            )

    assert cache.present_library_worker_images(
        [absent, other], cli=Mixed()
    ) == frozenset({other})
