"""The Docker 29 parent alias, end to end (ship row 3 follow-up to
test_parent_alias_build.py): the install records the JAX CPU parent as well as the
Torch one, writes an owner-only registry of its aliases, and dispatch finds the
parent through it. Content-bound (the tag's image must have exactly the recorded
fingerprint), never the tag alone; no record or a different image fails closed
with a plain reason; the child keeps the recorded id."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from test_parent_alias_build import LAYERS, StoreCli, _fingerprint
from test_parent_image_fingerprint import IMAGE_ID, INDEX_ID, TAG, _identity

from carbon.reconstruction.worker import docker_runtime, image_fingerprint
from carbon.reconstruction.worker.docker_runtime import DockerCLI, WorkerFailure

ROOT = Path(__file__).resolve().parents[2]
OTHER = "sha256:" + "7" * 64


def test_the_registry_round_trips_merges_and_is_owner_only(tmp_path):
    first = image_fingerprint.write_alias(
        tmp_path, parent_image_id=IMAGE_ID, tag=TAG, value=_fingerprint()
    )
    second = image_fingerprint.write_alias(
        tmp_path,
        parent_image_id=OTHER,
        tag="carbon-c03-worker:0123456789abcdef",
        value=_fingerprint(("a",)),
    )
    assert first == second
    if os.name == "posix":
        assert stat.S_IMODE(second.stat().st_mode) == 0o600
    aliases = image_fingerprint.read_aliases(tmp_path)
    assert aliases[IMAGE_ID] == (TAG, _fingerprint())
    assert aliases[OTHER] == (
        "carbon-c03-worker:0123456789abcdef",
        _fingerprint(("a",)),
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"parent_image_id": "latest", "tag": TAG, "value": "0" * 64},
        {"parent_image_id": IMAGE_ID, "tag": "latest", "value": "0" * 64},
        {"parent_image_id": IMAGE_ID, "tag": TAG, "value": "short"},
    ],
)
def test_a_malformed_alias_is_refused_at_write(tmp_path, bad):
    with pytest.raises(ValueError):
        image_fingerprint.write_alias(tmp_path, **bad)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_a_loose_malformed_or_foreign_registry_vouches_for_nothing(tmp_path):
    path = image_fingerprint.write_alias(
        tmp_path, parent_image_id=IMAGE_ID, tag=TAG, value=_fingerprint()
    )
    path.chmod(0o644)  # group/other readable: not owner-only
    assert image_fingerprint.read_aliases(tmp_path) == {}
    path.chmod(0o600)
    assert image_fingerprint.read_aliases(tmp_path) == {IMAGE_ID: (TAG, _fingerprint())}
    path.write_text('{"schema": "x"}', encoding="utf-8")
    path.chmod(0o600)
    assert image_fingerprint.read_aliases(tmp_path) == {}
    path.write_text("not json", encoding="utf-8")
    path.chmod(0o600)
    assert image_fingerprint.read_aliases(tmp_path) == {}
    assert image_fingerprint.read_aliases(tmp_path / "absent") == {}


def _cli(store, tmp_path, **record):
    """A fake-store CLI whose installed aliases come from a registry in tmp_path."""
    if record:
        image_fingerprint.write_alias(tmp_path, **record)
    cli = StoreCli(store, "sha256:" + "9" * 64)
    cli._candidates = image_fingerprint.read_aliases(tmp_path)
    return cli


GOOD = {"parent_image_id": IMAGE_ID, "tag": TAG, "value": _fingerprint()}


def test_dispatch_finds_the_parent_through_the_installs_registry_on_docker_29(tmp_path):
    identity = _identity()
    cli = _cli("containerd", tmp_path, **GOOD)
    assert docker_runtime.doctor(
        image_id=IMAGE_ID, image_identity=identity, cli=cli
    ).eligible
    document, by_alias = docker_runtime.inspect_image(cli, IMAGE_ID)
    assert by_alias is True and document["Id"] == INDEX_ID


def test_docker_28_answers_the_recorded_id_and_never_consults_the_registry(tmp_path):
    identity = _identity()
    cli = _cli("classic", tmp_path, **GOOD)
    document, by_alias = docker_runtime.inspect_image(cli, IMAGE_ID)
    assert by_alias is False and document["Id"] == IMAGE_ID
    assert docker_runtime.doctor(
        image_id=IMAGE_ID, image_identity=identity, cli=cli
    ).eligible
    assert cli._aliases == {}


@pytest.mark.parametrize(
    "record",
    [
        {**GOOD, "value": _fingerprint(("l1", "swapped"))},  # the tag is another image
        {},  # no record at all
    ],
)
def test_a_different_image_or_no_record_fails_closed(tmp_path, record):
    identity = _identity()
    cli = _cli("containerd", tmp_path, **record)
    assert cli.alias_of(IMAGE_ID) is None
    assert not docker_runtime.doctor(
        image_id=IMAGE_ID, image_identity=identity, cli=cli
    ).eligible
    with pytest.raises(WorkerFailure):
        docker_runtime.inspect_image(cli, IMAGE_ID)


def test_the_tag_alone_is_never_enough(tmp_path):
    """A registry entry whose recorded fingerprint is not the live image's gives no alias, even
    though the tag exists and answers."""
    cli = _cli("containerd", tmp_path, **{**GOOD, "value": "0" * 64})
    assert cli.alias_of(IMAGE_ID) is None
    assert (
        cli.json(["image", "inspect", TAG, "--format", "{{json .}}"])["Id"] == INDEX_ID
    )


def test_from_installed_reads_the_registry_and_verifies_lazily(tmp_path, monkeypatch):
    image_fingerprint.write_alias(tmp_path, **GOOD)
    cli = DockerCLI.from_installed(tmp_path)
    assert cli._candidates == {IMAGE_ID: (TAG, _fingerprint())}
    assert cli._aliases == {}  # nothing is trusted until the store has been asked
    assert DockerCLI.from_installed(tmp_path / "none")._candidates == {}


def test_dispatch_uses_the_installs_aliases_by_default():
    source = (ROOT / "carbon" / "development_session" / "research_image.py").read_text(
        encoding="utf-8"
    )
    assert "cli = cli or DockerCLI.from_installed()" in source


def test_the_install_records_the_jax_cpu_parent_and_the_registry(tmp_path, monkeypatch):
    from carbon.development_session import gpu_practice
    from scripts.dev.miner_launchpad import installed

    manifest = tmp_path / "c03-worker-image.json"
    manifest.write_text("{}", encoding="utf-8")
    identity = _identity()
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda _path: identity)
    monkeypatch.setattr(gpu_practice, "direct_parent_backend", lambda _image: None)
    monkeypatch.setattr(
        image_fingerprint, "fingerprint", lambda _ref, **_: _fingerprint()
    )
    state = tmp_path / "state"
    assert installed.record_parent_fingerprint(manifest, state_dir=state) is True
    tag = "carbon-c03-worker:" + identity.source_tree_digest[7:23]
    assert image_fingerprint.read_sidecar(manifest, identity.image_id) == (
        tag,
        _fingerprint(),
    )
    assert image_fingerprint.read_aliases(state) == {
        identity.image_id: (tag, _fingerprint())
    }


def test_a_gpu_worker_is_not_recorded_as_a_cpu_parent(tmp_path, monkeypatch):
    from carbon.development_session import gpu_practice
    from scripts.dev.miner_launchpad import installed

    manifest = tmp_path / "gpu-worker-image.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        docker_runtime, "load_image_identity", lambda _path: _identity()
    )
    monkeypatch.setattr(gpu_practice, "direct_parent_backend", lambda _image: "jax")
    assert installed.record_parent_fingerprint(manifest, state_dir=tmp_path) is False
    assert image_fingerprint.read_aliases(tmp_path) == {}


def test_without_a_record_the_build_says_what_to_do(tmp_path):
    from test_library_bundles import fixture

    from carbon.development_session.library_bundles import (
        PARENT_GAP,
        build_offline_bundle,
        prepare_offline_context,
    )

    context, bundle, seal = prepare_offline_context(tmp_path, *fixture(), IMAGE_ID)
    cli = StoreCli("containerd", bundle)
    with pytest.raises(ValueError) as refused:
        build_offline_bundle(context, bundle, IMAGE_ID, seal, cli=cli)
    assert str(refused.value) == PARENT_GAP
    assert "run the installer again with --update" in PARENT_GAP
    assert LAYERS  # the fake store has layers; the record is what is missing


def test_the_pinned_uv_image_is_found_by_any_form_a_store_knows_it_by(tmp_path):
    """M1 rc26: a containerd store keeps the digest-pulled uv image with no tag, so the plain
    `name:tag@digest` form may not answer; the name@digest and bare digest forms name the same
    pinned bytes, and the RepoDigests check on the answer stays."""
    from test_library_bundles import fixture

    from carbon.development_session.library_bundles import (
        UV_IMAGE,
        build_offline_bundle,
        prepare_offline_context,
        uv_references,
    )

    name, _, digest = UV_IMAGE.partition("@")
    forms = uv_references()
    assert forms == (UV_IMAGE, name.rsplit(":", 1)[0] + "@" + digest, digest)
    context, bundle, seal = prepare_offline_context(tmp_path, *fixture(), IMAGE_ID)
    for answering in forms[1:]:
        cli = _UvOnly(answering, "classic", bundle)
        assert build_offline_bundle(context, bundle, IMAGE_ID, seal, cli=cli)
    # A form that is not one of the three never answers.
    cli = _UvOnly("ghcr.io/astral-sh/uv:latest", "classic", bundle)
    with pytest.raises(ValueError, match="required local image absent"):
        build_offline_bundle(context, bundle, IMAGE_ID, seal, cli=cli)


class _UvOnly(StoreCli):
    """A store that answers for the pinned uv image under exactly one reference form."""

    def __init__(self, answering, store, bundle):
        super().__init__(store, bundle)
        self.answering = answering

    def json(self, arguments, **kwargs):
        from carbon.development_session.library_bundles import UV_IMAGE

        if arguments[:2] == ["image", "inspect"] and arguments[2] in (
            UV_IMAGE,
            UV_IMAGE.partition("@")[0].rsplit(":", 1)[0]
            + "@"
            + UV_IMAGE.partition("@")[2],
            UV_IMAGE.partition("@")[2],
        ):
            if arguments[2] != self.answering:
                raise WorkerFailure(docker_runtime.WorkerCode.RUNTIME)
            return {"Id": "sha256:" + "d" * 64, "RepoDigests": [UV_IMAGE]}
        return super().json(arguments, **kwargs)
