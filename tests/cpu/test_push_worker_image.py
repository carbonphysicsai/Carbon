"""Pushing the pinned GPU worker to the miner's own registry (LINKONLY-D8).

OWNER-MINER-COMPUTE-LINK-ONLY-01, as amended on 2026-10-02: for a container
rental that pulls its image, the miner pushes the pinned GPU worker to a
repository they control and starts their container from it. Carbon publishes
no registry and holds no registry credential.

The helper runs in real bash from a copy of the checkout's layout, with a
fake `docker` that logs every call and a fake worker build. No registry is
reached. What is held:
- it pushes exactly the pinned GPU worker, by image ID, and prints the
  `repository@sha256` reference the registry gave it;
- with no manifest named, it builds the worker from the checkout first;
- it never logs in and passes no credential: the miner's own login is used;
- anything else (a tag or digest in the repository, a manifest that is not
  this checkout's GPU worker, an image not built here, a push the registry
  refused, no digest returned) is refused before or instead of a push.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
HELPER = REPOSITORY / "scripts" / "dev" / "push_worker_image.sh"
LOCK = b"jax[cuda13]==0 --hash=sha256:fixture\n"
IMAGE = "sha256:" + "9" * 64
SOURCE = "sha256:" + "a" * 64
PUSHED = "sha256:" + "5" * 64
REPO = "ghcr.io/miner/carbon-gpu-worker"

#: A fake docker: logs its argv; `image inspect` answers the image ID and the
#: RepoDigests the environment names; `push` fails when told to.
FAKE_DOCKER = r"""#!/bin/bash
printf '%s\n' "$*" >> "$CARBON_FAKE_LOG"
case "$1" in
  image)
    if [ "$5" = "$CARBON_FAKE_IMAGE" ] && [ "$4" = "{{.Id}}" ]; then
      printf '%s\n' "$5"; exit 0
    fi
    if [ "$5" = "$CARBON_FAKE_IMAGE" ]; then
      for digest in ${CARBON_FAKE_REPO_DIGESTS:-}; do printf '%s\n' "$digest"; done
      exit 0
    fi
    exit 1 ;;
  push)
    [ -z "${CARBON_FAKE_PUSH_FAILS:-}" ] || exit 1
    exit 0 ;;
esac
exit 0
"""

#: The checkout's worker build, here writing a manifest for IMAGE.
FAKE_BUILD = r"""#!/bin/bash
printf 'built\n' >> "$CARBON_FAKE_LOG"
mkdir -p "$(dirname -- "$1")"
cat > "$1" <<EOF
$CARBON_FAKE_MANIFEST
EOF
"""


def manifest(lock_digest):
    return {
        "schema": "carbon.c03.worker-image.v1",
        "image_id": IMAGE,
        "config_digest": IMAGE,
        "source_tree_digest": SOURCE,
        "wheel_digest": "sha256:" + "b" * 64,
        "lock_digest": lock_digest,
        "base_image_digest": "sha256:" + "1" * 64,
        "build_recipe_digest": "sha256:" + "d" * 64,
        "entrypoint_digest": "sha256:" + "e" * 64,
    }


def lock_digest():
    import hashlib

    return "sha256:" + hashlib.sha256(LOCK).hexdigest()


@pytest.fixture
def checkout(tmp_path):
    """The helper in a copy of the checkout's layout, with fakes beside it."""
    root = tmp_path / "checkout"
    scripts = root / "scripts" / "dev"
    scripts.mkdir(parents=True)
    shutil.copy2(HELPER, scripts / HELPER.name)
    (scripts / "accelerator_worker_image.sh").write_text(FAKE_BUILD)
    (root / ".devcontainer" / "accelerators").mkdir(parents=True)
    (root / ".devcontainer" / "accelerators" / "cuda13-py311.txt").write_bytes(LOCK)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "docker").write_text(FAKE_DOCKER)
    (tools / "docker").chmod(0o755)
    return root


def run(checkout, *args, manifest_value=None, **env):
    log = checkout.parent / "docker.log"
    completed = subprocess.run(
        ["bash", str(checkout / "scripts" / "dev" / HELPER.name), *args],
        env={
            # The fake docker first: no real Docker or registry is reached.
            "PATH": f"{checkout.parent / 'tools'}:{os.environ['PATH']}",
            "CARBON_FAKE_LOG": str(log),
            "CARBON_FAKE_IMAGE": IMAGE,
            "CARBON_FAKE_REPO_DIGESTS": f"other.io/x@{PUSHED} {REPO}@{PUSHED}",
            "CARBON_FAKE_MANIFEST": json.dumps(
                manifest_value or manifest(lock_digest())
            ),
            **env,
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return completed, calls


def write_manifest(checkout, value):
    path = checkout / "worker.json"
    path.write_text(json.dumps(value))
    return path


def test_it_pushes_the_pinned_worker_by_id_and_prints_its_digest(checkout):
    path = write_manifest(checkout, manifest(lock_digest()))
    completed, calls = run(checkout, "--manifest", str(path), REPO)
    assert completed.returncode == 0, completed.stderr
    tag = f"{REPO}:carbon-gpu-worker-{SOURCE[7:23]}"
    assert f"tag {IMAGE} {tag}" in calls
    assert f"push {tag}" in calls
    assert f"Start your container from: {REPO}@{PUSHED}" in completed.stdout
    # Never a login, never a credential: the miner's own login is used.
    joined = "\n".join(calls)
    for forbidden in ("login", "password", "--username", "-u ", "config.json"):
        assert forbidden not in joined
    assert "built" not in calls


def test_with_no_manifest_it_builds_the_worker_from_the_checkout_first(checkout):
    completed, calls = run(checkout, REPO)
    assert completed.returncode == 0, completed.stderr
    assert calls[0] == "built"
    built = checkout / ".carbon-artifacts" / "accelerator-worker-image.json"
    assert json.loads(built.read_text())["image_id"] == IMAGE


@pytest.mark.parametrize(
    "repository",
    [
        REPO + ":latest",
        REPO + "@" + PUSHED,
        "GHCR.io/miner/worker",
        "--config=/tmp/x",
        "ghcr.io",
        "ghcr.io/miner/worker; rm -rf ~",
        "",
    ],
)
def test_a_repository_with_a_tag_digest_or_anything_else_is_refused(
    checkout, repository
):
    path = write_manifest(checkout, manifest(lock_digest()))
    completed, calls = run(checkout, "--manifest", str(path), repository)
    assert completed.returncode == 2
    assert not [c for c in calls if c.startswith(("tag", "push"))]


def test_a_manifest_that_is_not_this_checkouts_gpu_worker_is_refused(checkout):
    cpu = write_manifest(checkout, manifest("sha256:" + "c" * 64))
    completed, calls = run(checkout, "--manifest", str(cpu), REPO)
    assert completed.returncode == 2
    assert "not this checkout's pinned GPU worker" in completed.stderr
    assert not [c for c in calls if c.startswith(("tag", "push"))]
    broken = write_manifest(checkout, {"schema": "x"})
    completed, _ = run(checkout, "--manifest", str(broken), REPO)
    assert completed.returncode == 2


def test_an_image_not_built_here_is_refused_before_any_push(checkout):
    path = write_manifest(checkout, manifest(lock_digest()))
    completed, calls = run(
        checkout, "--manifest", str(path), REPO, CARBON_FAKE_IMAGE="sha256:" + "0" * 64
    )
    assert completed.returncode == 2 and "is not built here" in completed.stderr
    assert not [c for c in calls if c.startswith(("tag", "push"))]


def test_a_refused_push_names_the_miners_own_login(checkout):
    path = write_manifest(checkout, manifest(lock_digest()))
    completed, _ = run(
        checkout, "--manifest", str(path), REPO, CARBON_FAKE_PUSH_FAILS="1"
    )
    assert completed.returncode == 2
    assert "docker login" in completed.stderr and "yourself" in completed.stderr


def test_no_digest_from_the_registry_is_refused(checkout):
    path = write_manifest(checkout, manifest(lock_digest()))
    completed, _ = run(
        checkout,
        "--manifest",
        str(path),
        REPO,
        CARBON_FAKE_REPO_DIGESTS=f"other.io/x@{PUSHED} {REPO}@sha256:short",
    )
    assert completed.returncode == 2
    assert "no digest" in completed.stderr
