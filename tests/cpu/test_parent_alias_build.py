"""The catalog build on a containerd image store (Docker 29): ship row 3 (110 JAX installs failed with
'required local image absent').

The C-03 CPU parent is recorded by its config digest. A containerd store does not answer to that id, only to the
exact tag, so the offline library build, which looked the parent up by the recorded id, refused. The install's
record (tag + store-neutral fingerprint, verified) now lets `DockerCLI.register_parent_alias` find the same image,
and the build tags the store's own id while the child keeps the recorded id as its identity. Without a verified
record nothing changes: the strict lookup stands.

A fake Docker stands in for both stores; no engine is reached.
"""

from __future__ import annotations

import hashlib
import json
from subprocess import CompletedProcess

import pytest
from test_library_bundles import fixture
from test_parent_image_fingerprint import (
    GIB,
    IMAGE_ID,
    INDEX_ID,
    TAG,
    _document,
    _identity,
)

from carbon.development_session.library_bundles import (
    UV_IMAGE,
    build_offline_bundle,
    prepare_offline_context,
)
from carbon.reconstruction.worker import docker_runtime, image_fingerprint
from carbon.reconstruction.worker.docker_runtime import DockerCLI, WorkerFailure
from carbon.reconstruction.worker.model import WorkerCode

LAYERS = ("l1", "l2")
UV_ID = "sha256:" + "d" * 64
BUILT_ID = "sha256:" + "e" * 64


def _fingerprint(layers=LAYERS):
    return hashlib.sha256(json.dumps(list(layers)).encode()).hexdigest()


class StoreCli(DockerCLI):
    """`store` is "classic" (answers the recorded id) or "containerd" (answers only the tag and the index id)."""

    def __init__(self, store, bundle):
        super().__init__()
        self.store, self.bundle = store, bundle
        self.tags, self.calls = {}, []
        self.identity = _identity()

    def _parent_doc(self, id_value):
        document = _document(self.identity, id_value=id_value, layers=LAYERS)
        document["RootFS"] = {"Layers": list(LAYERS)}
        return document

    def run(self, arguments, **kwargs):
        self.calls.append(list(arguments))
        if arguments[:3] == ["image", "inspect", "--format"]:
            if (
                arguments[3] == image_fingerprint.FINGERPRINT_FORMAT
                and arguments[4] == TAG
                and self.store == "containerd"
            ):
                return CompletedProcess(
                    arguments, 0, json.dumps(list(LAYERS)).encode(), b""
                )
            raise WorkerFailure(WorkerCode.RUNTIME)
        if arguments[0] == "tag":
            source, destination = arguments[1], arguments[2]
            known = {INDEX_ID: INDEX_ID, UV_ID: UV_ID}
            if self.store == "classic":
                known[IMAGE_ID] = IMAGE_ID
            if source not in known:
                raise WorkerFailure(
                    WorkerCode.RUNTIME
                )  # `docker tag <config digest>` fails on containerd
            self.tags[destination] = known[source]
            return CompletedProcess(arguments, 0, b"", b"")
        if arguments[0] == "build":
            return CompletedProcess(arguments, 0, BUILT_ID.encode(), b"")
        raise AssertionError(arguments)

    def json(self, arguments, **kwargs):
        if arguments[0] == "version":
            return {"Version": "x", "ApiVersion": "y"}
        if arguments[0] == "info":
            return {
                "NCPU": 64,
                "MemTotal": 256 * GIB,
                "CgroupVersion": "2",
                "SecurityOptions": ["name=seccomp,profile=default"],
            }
        reference = arguments[2]
        if reference == IMAGE_ID and self.store == "classic":
            return self._parent_doc(IMAGE_ID)
        if self.store == "containerd" and reference in (TAG, INDEX_ID):
            return self._parent_doc(INDEX_ID)
        if reference == UV_IMAGE:
            return {"Id": UV_ID, "RepoDigests": [UV_IMAGE]}
        if reference in self.tags:
            return {"Id": self.tags[reference]}
        if reference == BUILT_ID:
            return {
                "Id": BUILT_ID,
                "Os": "linux",
                "Architecture": "amd64",
                "Config": {
                    "User": "65532:65532",
                    "Labels": {
                        "org.opencontainers.image.carbon.development.library-bundle": self.bundle,
                        # The identity the receipt binds: the RECORDED parent id, never the store's own.
                        "org.opencontainers.image.carbon.development.parent": IMAGE_ID,
                    },
                },
                "RootFS": {"Layers": [*LAYERS, "new-layer"]},
            }
        raise WorkerFailure(WorkerCode.RUNTIME)


def _context(tmp_path):
    context, bundle, seal = prepare_offline_context(tmp_path, *fixture(), IMAGE_ID)
    return context, bundle, seal


def test_a_containerd_store_refuses_the_recorded_id_without_the_verified_record(
    tmp_path,
):
    """The bug: ship row 3. The parent is not found by its recorded config digest."""
    context, bundle, seal = _context(tmp_path)
    cli = StoreCli("containerd", bundle)
    with pytest.raises(ValueError, match="required local image absent"):
        build_offline_bundle(context, bundle, IMAGE_ID, seal, cli=cli)


def test_the_verified_alias_builds_on_the_stores_own_id_and_the_child_keeps_the_recorded_parent(
    tmp_path,
):
    context, bundle, seal = _context(tmp_path)
    cli = StoreCli("containerd", bundle)
    assert cli.register_parent_alias(IMAGE_ID, TAG, _fingerprint()) is True
    assert cli.alias_of(IMAGE_ID) == (TAG, _fingerprint())
    assert build_offline_bundle(context, bundle, IMAGE_ID, seal, cli=cli) == BUILT_ID
    tagged = [c for c in cli.calls if c[0] == "tag"]
    assert (
        tagged[0][1] == INDEX_ID
    ), "the store's own id is tagged, never the recorded config digest"
    assert tagged[1][1] == UV_ID
    assert [c[0] for c in cli.calls if c[0] == "build"] == ["build"]


def test_a_fingerprint_that_differs_or_no_record_registers_nothing_and_the_strict_lookup_stands(
    tmp_path,
):
    context, bundle, seal = _context(tmp_path)
    for tag, fingerprint in (
        (TAG, _fingerprint(("l1", "other"))),
        (TAG, None),
        (None, _fingerprint()),
        ("carbon-c03-worker:notahextagnotahex", _fingerprint()),
    ):
        cli = StoreCli("containerd", bundle)
        assert cli.register_parent_alias(IMAGE_ID, tag, fingerprint) is False
        assert cli.alias_of(IMAGE_ID) is None
        with pytest.raises(ValueError, match="required local image absent"):
            build_offline_bundle(context, bundle, IMAGE_ID, seal, cli=cli)


def test_a_classic_store_answers_the_recorded_id_and_needs_no_alias(tmp_path):
    context, bundle, seal = _context(tmp_path)
    cli = StoreCli("classic", bundle)
    assert cli.register_parent_alias(IMAGE_ID, TAG, _fingerprint()) is False
    assert build_offline_bundle(context, bundle, IMAGE_ID, seal, cli=cli) == BUILT_ID
    assert [c for c in cli.calls if c[0] == "tag"][0][1] == IMAGE_ID


def test_the_doctor_and_the_inspect_helper_use_the_alias_only_when_it_is_verified(
    tmp_path,
):
    identity = _identity()
    bare = StoreCli("containerd", "sha256:" + "9" * 64)
    assert not docker_runtime.doctor(
        image_id=IMAGE_ID, image_identity=identity, cli=bare
    ).eligible
    with pytest.raises(WorkerFailure):
        docker_runtime.inspect_image(bare, IMAGE_ID)
    aliased = StoreCli("containerd", "sha256:" + "9" * 64)
    assert aliased.register_parent_alias(IMAGE_ID, TAG, _fingerprint())
    assert docker_runtime.doctor(
        image_id=IMAGE_ID, image_identity=identity, cli=aliased
    ).eligible
    document, by_alias = docker_runtime.inspect_image(aliased, IMAGE_ID)
    assert by_alias is True and document["Id"] == INDEX_ID
    classic = StoreCli("classic", "sha256:" + "9" * 64)
    document, by_alias = docker_runtime.inspect_image(classic, IMAGE_ID)
    assert by_alias is False and document["Id"] == IMAGE_ID
