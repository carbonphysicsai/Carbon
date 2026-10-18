"""DEVELOPMENT image handoff refuses source, pair and byte substitution."""

import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session.profile import canonical, digest
from scripts.dev import development_image_artifact as handoff

COMMIT = "a" * 40
TREE = "b" * 40
SOURCE = "sha256:" + "c" * 64
C03 = "sha256:" + "d" * 64
ANALYSIS = "sha256:" + "e" * 64
ENTRYPOINT = [
    "/opt/carbon-worker/bin/python",
    "-I",
    "-m",
    "carbon.reconstruction.worker.entrypoint",
]


class FakeDocker:
    def __init__(self, runtime_digest):
        self.calls = []
        self.runtime_digest = runtime_digest

    def json(self, arguments):
        self.calls.append(arguments)
        if arguments[:2] == ["info", "--format"]:
            return {"DriverStatus": [["driver-type", "io.containerd.snapshotter.v1"]]}
        assert arguments[:2] == ["image", "inspect"]
        if arguments[2] == C03:
            return {"Id": C03, "RootFS": {"Layers": ["parent-layer"]}}
        assert arguments[2] == ANALYSIS
        return {
            "Id": ANALYSIS,
            "Os": "linux",
            "Architecture": "amd64",
            "Config": {
                "User": "65532:65532",
                "Entrypoint": ENTRYPOINT,
                "Labels": {
                    "org.opencontainers.image.carbon.d4.runtime": self.runtime_digest,
                    "org.opencontainers.image.carbon.d4.parent": C03,
                },
            },
            "RootFS": {"Layers": ["parent-layer", "analysis-layer"]},
        }


@pytest.fixture
def pair(tmp_path, monkeypatch):
    implementation = {
        "revision": COMMIT,
        "tree": TREE,
        "source_tree_digest": SOURCE,
        "source_authority": "DEVELOPMENT_CANDIDATE",
    }
    monkeypatch.setattr(handoff, "_source", lambda *args: implementation)
    monkeypatch.setattr(
        handoff, "doctor", lambda **kwargs: SimpleNamespace(eligible=True)
    )
    runtime_document = lambda parent: {"schema": "fixture-runtime", "parent": parent}
    monkeypatch.setattr(handoff, "runtime_document", runtime_document)
    monkeypatch.setattr(
        "carbon.development_session.research_image.runtime_document", runtime_document
    )
    runtime_digest = digest(canonical(runtime_document(C03)))
    c03_manifest = {
        "schema": "carbon.c03.worker-image.v1",
        "image_id": C03,
        "config_digest": C03,
        "source_tree_digest": SOURCE,
        "wheel_digest": "sha256:" + "1" * 64,
        "lock_digest": "sha256:" + "2" * 64,
        "base_image_digest": "sha256:" + "3" * 64,
        "build_recipe_digest": "sha256:" + "4" * 64,
        "entrypoint_digest": "sha256:" + "5" * 64,
    }
    analysis_manifest = {
        "schema": "carbon.autoresearch.analysis-image.v1",
        "image_id": ANALYSIS,
        "parent_image": C03,
        "runtime_digest": runtime_digest,
    }
    c03_path = tmp_path / "c03-worker-image.json"
    analysis_path = tmp_path / "analysis-image.json"
    c03_path.write_bytes(canonical(c03_manifest))
    analysis_path.write_bytes(canonical(analysis_manifest))
    return c03_path, analysis_path, FakeDocker(runtime_digest)


def _identity_args(tmp_path):
    return {
        "revision": COMMIT,
        "tree": TREE,
        "source_tree_digest": SOURCE,
        "repository": tmp_path,
    }


def test_pure_status_requires_both_real_images_and_never_builds(
    pair, tmp_path, monkeypatch
):
    c03_path, analysis_path, docker = pair
    root = tmp_path / "artifacts"
    root.mkdir()
    args = {**_identity_args(tmp_path), "artifacts_root": root, "cli": docker}
    assert handoff.installed_pair_status(**args) == "ABSENT"
    (root / c03_path.name).write_bytes(c03_path.read_bytes())
    assert handoff.installed_pair_status(**args) == "ABSENT"
    runtime = digest(canonical(handoff.runtime_document(C03))).removeprefix("sha256:")
    expected = root / "research-images" / runtime / "analysis-image.json"
    expected.parent.mkdir(parents=True)
    expected.write_bytes(analysis_path.read_bytes())
    assert handoff.installed_pair_status(**args) == "VERIFIED"
    assert handoff.verified_analysis_manifest(**args) == expected
    assert all(call[0] in {"info", "image"} for call in docker.calls)
    assert not any(path.name.startswith("images.tar") for path in root.rglob("*"))
    bad = json.loads(expected.read_bytes())
    bad["parent_image"] = "sha256:" + "f" * 64
    expected.write_bytes(canonical(bad))
    with pytest.raises((ValueError, RuntimeError)):
        handoff.installed_pair_status(**args)


def test_export_then_verify_detects_archive_and_receipt_tamper(
    pair, tmp_path, monkeypatch
):
    c03_path, analysis_path, docker = pair

    def fake_save(path, c03_id, analysis_id):
        assert (c03_id, analysis_id) == (C03, ANALYSIS)
        path.write_bytes(b"one compressed archive")
        return handoff._sha_file(path), path.stat().st_size, 100

    monkeypatch.setattr(handoff, "_save_compressed", fake_save)
    bundle = tmp_path / "bundle"
    result = handoff.export_bundle(
        bundle_dir=bundle,
        c03_manifest=c03_path,
        analysis_manifest=analysis_path,
        cli=docker,
        **_identity_args(tmp_path),
    )
    expected_digest = (
        "sha256:" + hashlib.sha256((bundle / "bundle.json").read_bytes()).hexdigest()
    )
    assert result["receipt_sha256"] == expected_digest
    assert (
        handoff.verify_bundle(
            bundle_dir=bundle,
            receipt_sha256=expected_digest,
            **_identity_args(tmp_path),
        )["analysis_parent_image"]
        == C03
    )
    (bundle / "images.tar.gz").write_bytes(b"substituted archive")
    with pytest.raises(handoff.Refused, match="archive_receipt_mismatch"):
        handoff.verify_bundle(
            bundle_dir=bundle,
            receipt_sha256=expected_digest,
            **_identity_args(tmp_path),
        )
    (bundle / "images.tar.gz").write_bytes(b"one compressed archive")
    (bundle / "unexpected-secret").write_bytes(b"must never be in the handoff")
    with pytest.raises(handoff.Refused, match="bundle_file_set_invalid"):
        handoff.verify_bundle(
            bundle_dir=bundle,
            receipt_sha256=expected_digest,
            **_identity_args(tmp_path),
        )


def test_relabelled_source_fails_before_export(pair, tmp_path):
    c03_path, analysis_path, docker = pair
    # The source label is checked before an archive can be exported.
    bad = json.loads(c03_path.read_bytes())
    bad["source_tree_digest"] = "sha256:" + "0" * 64
    c03_path.write_bytes(canonical(bad))
    with pytest.raises(ValueError, match="trusted worker"):
        handoff.export_bundle(
            bundle_dir=tmp_path / "bundle",
            c03_manifest=c03_path,
            analysis_manifest=analysis_path,
            cli=docker,
            **_identity_args(tmp_path),
        )
    assert not (tmp_path / "bundle").exists()


def test_status_cli_prints_closed_word_and_nonzero_invalid(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(handoff, "installed_pair_status", lambda **kwargs: "ABSENT")
    args = [
        "verify-installed",
        "--artifacts-root",
        str(tmp_path),
        "--revision",
        COMMIT,
        "--tree",
        TREE,
        "--source-tree-digest",
        SOURCE,
    ]
    assert handoff.main(args) == 0
    assert capsys.readouterr().out == "ABSENT\n"
    monkeypatch.setattr(
        handoff,
        "installed_pair_status",
        lambda **kwargs: (_ for _ in ()).throw(handoff.Refused("malformed_pair")),
    )
    assert handoff.main(args) == 2
    output = capsys.readouterr()
    assert output.out == "INVALID\n"
    assert "malformed_pair" in output.err
    monkeypatch.setattr(
        handoff,
        "_installed_pair",
        lambda **kwargs: ("VERIFIED", tmp_path / "analysis-image.json"),
    )
    assert handoff.main([*args, "--print-analysis-manifest"]) == 0
    assert capsys.readouterr().out == str(tmp_path / "analysis-image.json") + "\n"
    monkeypatch.setattr(handoff, "_installed_pair", lambda **kwargs: ("ABSENT", None))
    assert handoff.main([*args, "--print-analysis-manifest"]) == 2
    assert capsys.readouterr().out == "ABSENT\n"


def test_import_requires_capacity_before_load_and_writes_only_verified_pair(
    pair, tmp_path, monkeypatch
):
    c03_path, analysis_path, docker = pair

    def fake_save(path, *_):
        path.write_bytes(b"archive")
        return handoff._sha_file(path), 7, 10

    monkeypatch.setattr(handoff, "_save_compressed", fake_save)
    bundle = tmp_path / "bundle"
    export = handoff.export_bundle(
        bundle_dir=bundle,
        c03_manifest=c03_path,
        analysis_manifest=analysis_path,
        cli=docker,
        **_identity_args(tmp_path),
    )
    root = tmp_path / "installed"
    root.mkdir()
    loaded = []
    monkeypatch.setattr(
        handoff,
        "_docker_load",
        lambda archive, size: loaded.append((archive.read(), size)),
    )
    args = {
        "bundle_dir": bundle,
        "receipt_sha256": export["receipt_sha256"],
        "artifacts_root": root,
        "cli": docker,
        **_identity_args(tmp_path),
    }

    if os.name != "posix":
        with pytest.raises(handoff.Refused, match="posix_nofollow_install_required"):
            handoff.import_bundle(before_load=lambda required: None, **args)
        assert loaded == []
        assert list(root.iterdir()) == []
        return

    def deny(required):
        assert required == 7 + 3 * 10 + 1024**3
        raise handoff.Refused("physical_capacity_insufficient")

    with pytest.raises(handoff.Refused, match="physical_capacity_insufficient"):
        handoff.import_bundle(before_load=deny, **args)
    assert loaded == []
    assert list(root.iterdir()) == []
    claims = []
    result = handoff.import_bundle(before_load=claims.append, **args)
    assert claims == [7 + 3 * 10 + 1024**3]
    assert loaded == [(b"archive", 10)]
    assert result["status"] == "VERIFIED_IMPORT"
    assert Path(result["c03_manifest"]).read_bytes() == c03_path.read_bytes()
    assert Path(result["analysis_manifest"]).read_bytes() == analysis_path.read_bytes()
    assert (
        handoff.installed_pair_status(
            artifacts_root=root, cli=docker, **_identity_args(tmp_path)
        )
        == "VERIFIED"
    )


@pytest.mark.skipif(os.name != "posix", reason="no-follow directory fds need POSIX")
@pytest.mark.parametrize("swapped_parent", ["root", "research-images"])
def test_import_refuses_post_load_parent_swap_without_external_manifest_write(
    pair, tmp_path, monkeypatch, swapped_parent
):
    c03_path, analysis_path, docker = pair

    def fake_save(path, *_):
        path.write_bytes(b"archive")
        return handoff._sha_file(path), 7, 10

    monkeypatch.setattr(handoff, "_save_compressed", fake_save)
    bundle = tmp_path / "bundle"
    export = handoff.export_bundle(
        bundle_dir=bundle,
        c03_manifest=c03_path,
        analysis_manifest=analysis_path,
        cli=docker,
        **_identity_args(tmp_path),
    )
    root = tmp_path / "installed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    def swap_after_load(*_):
        if swapped_parent == "root":
            root.rename(tmp_path / "old-installed")
            root.symlink_to(outside, target_is_directory=True)
        else:
            (root / "research-images").symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(handoff, "_docker_load", swap_after_load)
    with pytest.raises(handoff.Refused):
        handoff.import_bundle(
            bundle_dir=bundle,
            receipt_sha256=export["receipt_sha256"],
            artifacts_root=root,
            cli=docker,
            before_load=lambda required: None,
            **_identity_args(tmp_path),
        )
    assert list(outside.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="private import staging needs POSIX")
@pytest.mark.parametrize(
    "member", ["images.tar.gz", "c03-worker-image.json", "analysis-image.json"]
)
def test_import_refuses_bundle_member_replaced_during_capacity_callback(
    pair, tmp_path, monkeypatch, member
):
    c03_path, analysis_path, docker = pair

    def fake_save(path, *_):
        path.write_bytes(b"archive")
        return handoff._sha_file(path), 7, 10

    monkeypatch.setattr(handoff, "_save_compressed", fake_save)
    bundle = tmp_path / "bundle"
    export = handoff.export_bundle(
        bundle_dir=bundle,
        c03_manifest=c03_path,
        analysis_manifest=analysis_path,
        cli=docker,
        **_identity_args(tmp_path),
    )
    root = tmp_path / "installed"
    root.mkdir()
    loaded = []
    monkeypatch.setattr(handoff, "_docker_load", lambda *_: loaded.append(True))

    def swap(required):
        assert required == 7 + 3 * 10 + 1024**3
        target = bundle / member
        target.rename(bundle / "saved-member")
        target.write_bytes(b"X" * (bundle / "saved-member").stat().st_size)

    with pytest.raises(
        handoff.Refused, match="archive_receipt_mismatch|manifest_receipt_mismatch"
    ):
        handoff.import_bundle(
            bundle_dir=bundle,
            receipt_sha256=export["receipt_sha256"],
            artifacts_root=root,
            cli=docker,
            before_load=swap,
            **_identity_args(tmp_path),
        )
    assert loaded == []
    assert list(root.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="private import staging needs POSIX")
def test_import_loads_pinned_copy_after_original_archive_path_changes(
    pair, tmp_path, monkeypatch
):
    c03_path, analysis_path, docker = pair

    def fake_save(path, *_):
        path.write_bytes(b"archive")
        return handoff._sha_file(path), 7, 10

    monkeypatch.setattr(handoff, "_save_compressed", fake_save)
    bundle = tmp_path / "bundle"
    export = handoff.export_bundle(
        bundle_dir=bundle,
        c03_manifest=c03_path,
        analysis_manifest=analysis_path,
        cli=docker,
        **_identity_args(tmp_path),
    )
    root = tmp_path / "installed"
    root.mkdir()
    staged = handoff._stage_verified_archive

    def stage_then_replace(path, receipt, destination):
        staged(path, receipt, destination)
        path.rename(bundle / "old-images.tar.gz")
        path.write_bytes(b"X" * 7)

    monkeypatch.setattr(handoff, "_stage_verified_archive", stage_then_replace)
    loaded = []
    monkeypatch.setattr(
        handoff,
        "_docker_load",
        lambda stream, size: loaded.append((stream.read(), size)),
    )
    result = handoff.import_bundle(
        bundle_dir=bundle,
        receipt_sha256=export["receipt_sha256"],
        artifacts_root=root,
        cli=docker,
        before_load=lambda required: None,
        **_identity_args(tmp_path),
    )
    assert result["status"] == "VERIFIED_IMPORT"
    assert loaded == [(b"archive", 10)]


@pytest.mark.skipif(os.name != "posix", reason="private import staging needs POSIX")
def test_import_cache_path_uses_pinned_manifest_after_early_swap(
    pair, tmp_path, monkeypatch
):
    c03_path, analysis_path, docker = pair

    def fake_save(path, *_):
        path.write_bytes(b"archive")
        return handoff._sha_file(path), 7, 10

    monkeypatch.setattr(handoff, "_save_compressed", fake_save)
    bundle = tmp_path / "bundle"
    export = handoff.export_bundle(
        bundle_dir=bundle,
        c03_manifest=c03_path,
        analysis_manifest=analysis_path,
        cli=docker,
        **_identity_args(tmp_path),
    )
    target = bundle / "analysis-image.json"
    original = target.read_bytes()
    original_digest = json.loads(original)["runtime_digest"]
    false_digest = "sha256:" + "f" * 64
    false_manifest = dict(json.loads(original), runtime_digest=false_digest)
    verified = handoff.verify_bundle

    def verified_then_swap(**kwargs):
        receipt = verified(**kwargs)
        target.write_bytes(canonical(false_manifest))
        return receipt

    monkeypatch.setattr(handoff, "verify_bundle", verified_then_swap)
    loaded = []
    monkeypatch.setattr(
        handoff,
        "_docker_load",
        lambda stream, size: loaded.append((stream.read(), size)),
    )
    root = tmp_path / "installed"
    root.mkdir()

    result = handoff.import_bundle(
        bundle_dir=bundle,
        receipt_sha256=export["receipt_sha256"],
        artifacts_root=root,
        cli=docker,
        before_load=lambda required: target.write_bytes(original),
        **_identity_args(tmp_path),
    )
    expected = root / "research-images" / original_digest[7:] / "analysis-image.json"
    false_path = root / "research-images" / false_digest[7:] / "analysis-image.json"
    assert result["analysis_manifest"] == str(expected)
    assert expected.read_bytes() == original
    assert not false_path.exists()
    assert loaded == [(b"archive", 10)]


def test_stream_load_refuses_gzip_expansion_beyond_receipt(tmp_path, monkeypatch):
    archive = tmp_path / "images.tar.gz"
    payload = b"oci-image-bytes" * 4096
    with gzip.open(archive, "wb") as stream:
        stream.write(payload)
    real_popen = subprocess.Popen

    def fake_popen(args, **kwargs):
        assert args == ["docker", "image", "load"]
        return real_popen(
            [sys.executable, "-c", "import sys; sys.stdin.buffer.read()"], **kwargs
        )

    monkeypatch.setattr(handoff.subprocess, "Popen", fake_popen)
    with archive.open("rb") as source:
        handoff._docker_load(source, len(payload))
    with (
        pytest.raises(handoff.Refused, match="archive_expanded_beyond_receipt"),
        archive.open("rb") as source,
    ):
        handoff._docker_load(source, len(payload) - 1)


def test_export_stream_is_one_bounded_compressed_archive(tmp_path, monkeypatch):
    payload = b"oci-image-bytes" * 4096
    real_popen = subprocess.Popen

    def fake_save_process(args, **kwargs):
        assert args == ["docker", "image", "save", C03, ANALYSIS]
        return real_popen(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'oci-image-bytes'*4096)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(handoff.subprocess, "Popen", fake_save_process)
    archive = tmp_path / "images.tar.gz"
    archive_sha, compressed_size, raw_size = handoff._save_compressed(
        archive, C03, ANALYSIS
    )
    assert archive_sha == handoff._sha_file(archive)
    assert compressed_size == archive.stat().st_size
    assert raw_size == len(payload)
    with gzip.open(archive, "rb") as stream:
        assert stream.read() == payload
