"""The C-03 parent on a containerd image store (Docker 29): the same image, found by its tag and its recorded
store-neutral fingerprint (Validator ruling, option A; fails closed without the record).

A fake Docker CLI stands in for both stores. The classic store answers `docker image inspect <config digest>`; the
containerd store does not (it knows the image by its index digest) but answers by tag.
"""

import dataclasses
import hashlib
import json
from subprocess import CompletedProcess

import pytest

from carbon.reconstruction.worker import docker_runtime, image_fingerprint
from carbon.reconstruction.worker.docker_runtime import WorkerFailure
from carbon.reconstruction.worker.model import WorkerCode, WorkerImageIdentity

GIB = 1024**3
IMAGE_ID = "sha256:" + "c6" * 32  # the recorded config digest
INDEX_ID = "sha256:" + "20" * 32  # what a containerd store calls the same image
TAG = "carbon-c03-worker:" + "ab12cd34ef56ab12"


def _identity():
    digest = lambda c: "sha256:" + c * 64  # noqa: E731
    return WorkerImageIdentity(
        image_id=IMAGE_ID,
        config_digest=IMAGE_ID,
        source_tree_digest=digest("1"),
        wheel_digest=digest("2"),
        lock_digest=digest("3"),
        base_image_digest=digest("4"),
        build_recipe_digest=digest("5"),
        entrypoint_digest=digest("6"),
    )


def _document(identity, *, id_value, layers=("l1", "l2")):
    return {
        "Id": id_value,
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {
            "User": f"{docker_runtime.WORKER_UID}:{docker_runtime.WORKER_GID}",
            "Entrypoint": [
                "/opt/carbon-worker/bin/python",
                "-I",
                "-m",
                "carbon.reconstruction.worker.entrypoint",
            ],
            "Labels": {
                "org.opencontainers.image.carbon.c03.scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
                "org.opencontainers.image.carbon.c03.source-tree": identity.source_tree_digest,
                "org.opencontainers.image.carbon.c03.lock": identity.lock_digest,
                "org.opencontainers.image.carbon.c03.base-image": identity.base_image_digest,
                "org.opencontainers.image.carbon.c03.build-recipe": identity.build_recipe_digest,
                "org.opencontainers.image.carbon.c03.entrypoint": identity.entrypoint_digest,
            },
        },
        "_layers": list(layers),
    }


class Cli:
    """`store` is "classic" (answers the config digest) or "containerd" (answers only the tag)."""

    def __init__(self, store, identity, *, layers=("l1", "l2")):
        self.store, self.identity, self.layers = store, identity, layers
        self.info = {
            "NCPU": 2,
            "MemTotal": 8 * GIB,
            "CgroupVersion": "2",
            "SecurityOptions": ["name=seccomp,profile=default"],
        }

    def _printed(self):
        return json.dumps(self.layers).encode()

    def run(self, arguments, **kwargs):
        if arguments[:3] == ["image", "inspect", "--format"] and arguments[3] == (
            image_fingerprint.FINGERPRINT_FORMAT
        ):
            if arguments[4] != TAG or self.store != "containerd":
                raise WorkerFailure(WorkerCode.RUNTIME)
            return CompletedProcess(arguments, 0, self._printed(), b"")
        raise WorkerFailure(WorkerCode.RUNTIME)

    def json(self, arguments, **kwargs):
        if arguments[0] == "version":
            return {"Version": "x", "ApiVersion": "y"}
        if arguments[0] == "info":
            return self.info
        reference = arguments[2]
        if self.store == "classic" and reference == IMAGE_ID:
            return _document(self.identity, id_value=IMAGE_ID)
        if self.store == "containerd" and reference == TAG:
            return _document(self.identity, id_value=INDEX_ID, layers=self.layers)
        raise WorkerFailure(WorkerCode.RUNTIME)


def _recorded(layers=("l1", "l2")):
    return hashlib.sha256(json.dumps(list(layers)).encode()).hexdigest()


def _doctor(cli, identity, **recorded):
    return docker_runtime.doctor(
        image_id=IMAGE_ID, image_identity=identity, cli=cli, **recorded
    )


def test_the_classic_store_is_unchanged_and_needs_no_record():
    identity = _identity()
    assert _doctor(Cli("classic", identity), identity).eligible


def test_the_containerd_store_with_the_recorded_fingerprint_passes():
    identity = _identity()
    cli = Cli("containerd", identity)
    verdict = _doctor(cli, identity, store_tag=TAG, store_fingerprint=_recorded())
    assert verdict.eligible and verdict.code == "worker.doctor.eligible"


def test_the_same_tag_with_a_different_layer_or_config_is_refused():
    identity = _identity()
    cli = Cli("containerd", identity, layers=("l1", "l2-swapped"))
    verdict = _doctor(cli, identity, store_tag=TAG, store_fingerprint=_recorded())
    assert not verdict.eligible and verdict.code == "worker.doctor.image_unavailable"


def test_a_missing_record_with_an_id_miss_fails_closed_without_a_label_fallback():
    identity = _identity()
    cli = Cli("containerd", identity)
    for recorded in ({}, {"store_tag": TAG}, {"store_fingerprint": _recorded()}):
        verdict = _doctor(cli, identity, **recorded)
        assert (
            not verdict.eligible and verdict.code == "worker.doctor.image_unavailable"
        )


def test_the_fallback_still_runs_the_label_user_and_entrypoint_checks():
    identity = _identity()
    other = dataclasses.replace(identity, lock_digest="sha256:" + "9" * 64)
    cli = Cli("containerd", other)  # the image on disk carries another lock label
    verdict = _doctor(cli, identity, store_tag=TAG, store_fingerprint=_recorded())
    assert (
        not verdict.eligible and verdict.code == "worker.doctor.image_binding_mismatch"
    )


def test_the_tag_must_be_the_exact_parent_tag_shape():
    identity = _identity()
    cli = Cli("containerd", identity)
    for tag in ("carbon-c03-worker:latest", "other:" + "ab12cd34ef56ab12", TAG + "x"):
        verdict = _doctor(cli, identity, store_tag=tag, store_fingerprint=_recorded())
        assert verdict.code == "worker.doctor.image_unavailable"


def test_the_sidecar_round_trips_and_refuses_another_image_or_a_malformed_record(
    tmp_path,
):
    manifest = tmp_path / "torch-worker-image.json"
    manifest.write_text("{}", encoding="utf-8")
    assert image_fingerprint.read_sidecar(manifest, IMAGE_ID) is None
    image_fingerprint.write_sidecar(
        manifest, parent_image_id=IMAGE_ID, tag=TAG, value=_recorded()
    )
    assert image_fingerprint.read_sidecar(manifest, IMAGE_ID) == (TAG, _recorded())
    assert image_fingerprint.read_sidecar(manifest, INDEX_ID) is None
    image_fingerprint.sidecar_path(manifest).write_text(
        '{"schema": "x"}', encoding="utf-8"
    )
    assert image_fingerprint.read_sidecar(manifest, IMAGE_ID) is None
    with pytest.raises(ValueError):
        image_fingerprint.write_sidecar(
            manifest, parent_image_id=IMAGE_ID, tag="latest", value="short"
        )


def test_the_remote_check_and_the_local_check_share_one_fingerprint_format():
    from carbon.compute import remote_machine

    assert remote_machine.FINGERPRINT_FORMAT is image_fingerprint.FINGERPRINT_FORMAT
