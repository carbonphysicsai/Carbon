"""Released worker images: the release record and the host pull (IMAGE-RELEASE-01).

The owner (2026-10-06): one released image that every host, testnet and main,
pulls by digest; a deleted image is re-pulled, never rebuilt. The helper runs
as a real process with a fake `docker` first on PATH that logs every call. No
registry or Docker daemon is reached. What is held:
- a pull that matches writes the build's exact manifest, which the validator
  loads, and runs nothing but `pull` and `image inspect`;
- a label, image ID or registry digest that differs is refused, and nothing is
  written;
- a record missing a field is refused before Docker is called;
- an existing different manifest is never overwritten (history stays);
- the release side records only what the pushed image carries;
- a released manifest satisfies the validator service's image parity.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_service import (
    carrier,
    checks,
    fresh,  # noqa: F401 - autouse fixture
    rewrite,
)

HELPER = REPOSITORY / "scripts" / "dev" / "worker_image_release.py"
IMAGE = "sha256:" + "1" * 64
#: With the containerd image store the registry digest is the image ID.
PUSHED = IMAGE
REPO = "ghcr.io/carbonphysicsai/carbon-c03-worker"
REFERENCE = f"{REPO}@{PUSHED}"
ENTRYPOINT = [
    "/opt/carbon-worker/bin/python",
    "-I",
    "-m",
    "carbon.reconstruction.worker.entrypoint",
]

#: Logs its argv; `pull` exits as told; `image inspect` prints the inspect
#: document for the reference or image ID it was given.
FAKE_DOCKER = r"""#!/bin/bash
printf '%s\n' "$*" >> "$CARBON_FAKE_LOG"
case "$1" in
  pull) exit "${CARBON_FAKE_PULL_STATUS:-0}" ;;
  image)
    if [ "$2" = inspect ] && { [ "$5" = "$CARBON_FAKE_REF" ] || [ "$5" = "$CARBON_FAKE_ID" ]; }; then
      printf '%s\n' "$CARBON_FAKE_INSPECT"; exit 0
    fi
    exit 1 ;;
esac
exit 3
"""


def manifest(tag="1", **changes):
    """The manifest a build script writes (fixture identity, never built)."""
    return {
        "schema": "carbon.c03.worker-image.v1",
        "image_id": "sha256:" + tag * 64,
        "config_digest": "sha256:" + tag * 64,
        "source_tree_digest": "sha256:" + "a" * 64,
        "wheel_digest": "sha256:" + "b" * 64,
        "lock_digest": "sha256:" + "c" * 64,
        "base_image_digest": "sha256:" + "0" * 64,
        "build_recipe_digest": "sha256:" + "d" * 64,
        "entrypoint_digest": "sha256:" + "e" * 64,
        **changes,
    }


def labels(value, **extra):
    prefix = "org.opencontainers.image.carbon."
    return {
        prefix + "c03.scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        prefix + "c03.source-tree": value["source_tree_digest"],
        prefix + "c03.lock": value["lock_digest"],
        prefix + "c03.base-image": value["base_image_digest"],
        prefix + "c03.build-recipe": value["build_recipe_digest"],
        prefix + "c03.entrypoint": value["entrypoint_digest"],
        **extra,
    }


def record(value=None, kind="c03", repository=REPO, digest=None, **extra):
    value = value or manifest()
    digest = digest or value["image_id"]
    return {
        "schema": "carbon.worker-image-release.v1",
        "kind": kind,
        "release_tag": "worker-images-v1",
        "source_commit": "f" * 40,
        "repository": repository,
        "registry_digest": digest,
        "reference": f"{repository}@{digest}",
        "scope": "UNQUALIFIED_PUBLIC_DEVELOPMENT",
        "security_acceptance": "HUMAN_INPUT",
        "image_store": "containerd",
        "labels": labels(value, **extra),
        "manifest": value,
    }


def inspected(value=None, *, image_labels=None, repo_digests=None, **changes):
    value = value or manifest()
    return {
        "Id": value["image_id"],
        "RepoDigests": [REFERENCE] if repo_digests is None else repo_digests,
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {
            "User": "65532:65532",
            "Entrypoint": ENTRYPOINT,
            "Labels": labels(value) if image_labels is None else image_labels,
        },
        **changes,
    }


@pytest.fixture
def tools(tmp_path):
    folder = tmp_path / "tools"
    folder.mkdir()
    (folder / "docker").write_text(FAKE_DOCKER)
    (folder / "docker").chmod(0o755)
    return folder


def run(tools, *args, inspect=None, **env):
    log = tools.parent / "docker.log"
    completed = subprocess.run(
        [sys.executable, str(HELPER), *args],
        env={
            # The fake docker first: no real Docker or registry is reached.
            "PATH": f"{tools}:{os.environ['PATH']}",
            "CARBON_FAKE_LOG": str(log),
            "CARBON_FAKE_REF": REFERENCE,
            "CARBON_FAKE_ID": IMAGE,
            "CARBON_FAKE_INSPECT": json.dumps(
                inspected() if inspect is None else inspect
            ),
            **env,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return completed, calls


def write(path, value):
    path.write_text(json.dumps(value))
    return path


def refused(completed):
    assert completed.returncode == 2, completed
    return json.loads(completed.stderr.strip().splitlines()[-1])["refused"]


def test_a_matching_pull_writes_the_builds_exact_manifest(tmp_path, tools):
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    rec = write(tmp_path / "c03.release.json", record())
    out = tmp_path / "images" / "c03-worker-image.json"
    completed, calls = run(tools, "pull", "--record", str(rec), "--out", str(out))
    assert completed.returncode == 0, completed.stderr
    # Byte-for-byte what the build script writes, and the validator loads it.
    assert (
        out.read_text()
        == json.dumps(manifest(), sort_keys=True, separators=(",", ":")) + "\n"
    )
    assert load_image_identity(out).image_id == IMAGE
    assert json.loads(completed.stdout)["reference"] == REFERENCE
    # Pulled by digest, then inspected; nothing built, tagged, pushed or removed.
    assert calls == [
        f"pull {REFERENCE}",
        f"image inspect --format {{{{json .}}}} {REFERENCE}",
    ]
    # Pulling again is idempotent: the same manifest is already there.
    again, _ = run(tools, "pull", "--record", str(rec), "--out", str(out))
    assert again.returncode == 0 and json.loads(again.stdout)["written"] is False


def test_a_label_mismatch_is_refused_and_nothing_written(tmp_path, tools):
    rec = write(tmp_path / "r.json", record())
    out = tmp_path / "m.json"
    other = labels(
        manifest(), **{"org.opencontainers.image.carbon.c03.lock": "sha256:" + "9" * 64}
    )
    completed, _ = run(
        tools,
        "pull",
        "--record",
        str(rec),
        "--out",
        str(out),
        inspect=inspected(image_labels=other),
    )
    assert refused(completed) == "label_mismatch"
    assert "c03.lock" in completed.stderr
    assert not out.exists()


def test_an_image_or_registry_digest_mismatch_is_refused(tmp_path, tools):
    rec = write(tmp_path / "r.json", record())
    out = tmp_path / "m.json"
    # Another image under the reference (or a containerd-store Id).
    completed, _ = run(
        tools,
        "pull",
        "--record",
        str(rec),
        "--out",
        str(out),
        inspect=inspected(Id="sha256:" + "2" * 64),
    )
    assert refused(completed) == "image_id_mismatch"
    # The image, but not from the released registry digest.
    completed, _ = run(
        tools,
        "pull",
        "--record",
        str(rec),
        "--out",
        str(out),
        inspect=inspected(repo_digests=[f"{REPO}@sha256:" + "6" * 64]),
    )
    assert refused(completed) == "registry_digest_mismatch"
    # A refused pull is named, with the host's own login as the next step.
    completed, _ = run(
        tools,
        "pull",
        "--record",
        str(rec),
        "--out",
        str(out),
        CARBON_FAKE_PULL_STATUS="1",
    )
    assert refused(completed) == "pull_failed"
    assert not out.exists()


@pytest.mark.parametrize("field", ["registry_digest", "manifest", "labels", "kind"])
def test_a_record_missing_a_field_is_refused_before_docker(tmp_path, tools, field):
    value = record()
    del value[field]
    completed, calls = run(
        tools, "pull", "--record", str(write(tmp_path / "r.json", value))
    )
    assert refused(completed) == "record_invalid"
    assert field in completed.stderr
    assert calls == []


def test_a_manifest_missing_a_field_is_refused_before_docker(tmp_path, tools):
    value = record()
    del value["manifest"]["wheel_digest"]
    completed, calls = run(
        tools, "pull", "--record", str(write(tmp_path / "r.json", value))
    )
    assert refused(completed) == "manifest_invalid"
    assert calls == []


def test_an_existing_different_manifest_is_kept_as_history(tmp_path, tools):
    rec = write(tmp_path / "r.json", record())
    out = tmp_path / "c03-worker-image.json"
    out.write_text("old\n")
    completed, _ = run(tools, "pull", "--record", str(rec), "--out", str(out))
    assert refused(completed) == "out_exists_differs"
    assert out.read_text() == "old\n"


def test_the_release_side_records_what_the_pushed_image_carries(tmp_path, tools):
    path = write(tmp_path / "manifest.json", manifest())
    out = tmp_path / "c03.release.json"
    common = ["--repository", REPO, "--tag", "worker-images-v1", "--commit", "f" * 40]
    completed, calls = run(
        tools,
        "record",
        "--kind",
        "c03",
        "--manifest",
        str(path),
        *common,
        "--out",
        str(out),
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(out.read_text()) == record()
    assert calls == [f"image inspect --format {{{{json .}}}} {IMAGE}"]
    # A torch image must carry its determinism label, or nothing is recorded.
    completed, _ = run(
        tools,
        "record",
        "--kind",
        "torch",
        "--manifest",
        str(path),
        *common,
        "--out",
        str(tmp_path / "torch.release.json"),
    )
    assert refused(completed) == "record_invalid"
    determinism = {
        "org.opencontainers.image.carbon.torch.determinism": "sha256:" + "7" * 64
    }
    completed, _ = run(
        tools,
        "record",
        "--kind",
        "torch",
        "--manifest",
        str(path),
        *common,
        "--out",
        str(tmp_path / "torch.release.json"),
        inspect=inspected(image_labels=labels(manifest(), **determinism)),
    )
    assert completed.returncode == 0, completed.stderr
    released = json.loads((tmp_path / "torch.release.json").read_text())
    assert released["labels"]["org.opencontainers.image.carbon.torch.determinism"] == (
        "sha256:" + "7" * 64
    )
    # No registry digest for the repository: nothing to release.
    completed, _ = run(
        tools,
        "record",
        "--kind",
        "c03",
        "--manifest",
        str(path),
        *common,
        "--out",
        str(tmp_path / "none.json"),
        inspect=inspected(repo_digests=[]),
    )
    assert refused(completed) == "registry_digest_missing"
    # Built on the classic image store, the pushed digest is not the image ID:
    # no host could pull it under the manifest's identity, so it is refused.
    completed, _ = run(
        tools,
        "record",
        "--kind",
        "c03",
        "--manifest",
        str(path),
        *common,
        "--out",
        str(tmp_path / "classic.json"),
        inspect=inspected(repo_digests=[f"{REPO}@sha256:" + "6" * 64]),
    )
    assert refused(completed) == "image_store_not_containerd"


def test_a_released_manifest_satisfies_image_parity(tmp_path, tools, monkeypatch):
    """The validator's `image_manifest` and the service's `practice_images`
    each pulled from the same release record are the same image to parity,
    though they are two files; a practice image from another build is not."""
    from scripts.dev.battery_validator_service import service as svc

    (tmp_path / "svc").mkdir(mode=0o700)
    made, images = carrier(tmp_path / "svc", monkeypatch, practice=False)
    rec = write(tmp_path / "r.json", record())
    # The deployment's `image_manifest` path, now written by the pull.
    (images / "worker-image.json").unlink()
    for out in (images / "worker-image.json", images / "practice.json"):
        completed, _ = run(tools, "pull", "--record", str(rec), "--out", str(out))
        assert completed.returncode == 0, completed.stderr
    rewrite(
        made.service, practice_images={"image_manifest": str(images / "practice.json")}
    )
    report = svc.parity_report(made.service, repository=REPOSITORY)
    assert report["ready"], report
    assert checks(report)["parity"]["detail"]["images"] == {"jax": IMAGE}
    # A practice image released from another build is not the validator's.
    other_digest = "sha256:" + "2" * 64
    other = write(tmp_path / "other.json", record(manifest("2")))
    completed, _ = run(
        tools,
        "pull",
        "--record",
        str(other),
        "--out",
        str(images / "other.json"),
        inspect=inspected(manifest("2"), repo_digests=[f"{REPO}@{other_digest}"]),
        CARBON_FAKE_REF=f"{REPO}@{other_digest}",
    )
    assert completed.returncode == 0, completed.stderr
    rewrite(
        made.service, practice_images={"image_manifest": str(images / "other.json")}
    )
    differs = checks(svc.parity_report(made.service, repository=REPOSITORY))["parity"]
    assert differs["refused"] == "practice_image_differs"
    assert differs["fields"] == ["image_id", "config_digest"]
