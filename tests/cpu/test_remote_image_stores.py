"""The pinned worker under two Docker image stores (E2E R8-6, 2026-10-22).

A Docker 29 controller with the containerd image store names an image by its
manifest digest; an older rented box with the classic store names the same
image by its config digest. The image arrived, failed the ID check and lost
its tag. These tests hold:
- the same image under the other store's ID is found by its exact
  store-neutral fingerprint (layers and run configuration), never by a
  weaker check, and a job starts from the machine's own ID for it;
- an image whose fingerprint differs is still refused;
- the worker travels under its tag, which the machine keeps on a mismatch;
- a machine on the controller's own store is checked by ID, as before.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from carbon.compute import remote_machine as rm
from carbon.compute.remote_machine import (
    FINGERPRINT_FORMAT,
    RemoteMachineError,
    SSHClient,
    image_check_script,
    local_fingerprint,
    send_image,
    start_script,
    worker_reference,
)

#: The controller's ID (containerd: the manifest digest) and the box's ID
#: for the same image (classic: the config digest).
CONTROLLER_ID = "sha256:" + "7d" * 32
BOX_ID = "sha256:" + "f5" * 32
#: What `docker image inspect --format FINGERPRINT_FORMAT` prints for it.
FINGERPRINT_TEXT = '["sha256:aa","sha256:bb"] ["PATH=/opt/carbon-worker/bin"] {}'
FINGERPRINT = hashlib.sha256((FINGERPRINT_TEXT + "\n").encode()).hexdigest()
REFERENCE = worker_reference(CONTROLLER_ID)
NAME = "carbon-job-" + "0123456789abcdef01234567"
COMMAND = ("/opt/carbon-worker/bin/python", "-I", "-m", "carbon.compute.job_server")

#: A fake `docker` on a classic-store box (and, for `save`/`tag`, the
#: controller). It logs each call; what it holds is in `$log.loaded`.
FAKE_DOCKER = r"""#!/bin/bash
log="$CARBON_FAKE_LOG"
printf '%s\n' "$*" >> "$log"
loaded=""
[ -f "$log.loaded" ] && read -r loaded < "$log.loaded"
case "$1" in
  info) exit 0 ;;
  tag) exit 0 ;;
  save) printf 'IMAGE-TAR-%s' "$2"; exit 0 ;;
  load)
    IFS= read -r content || true
    printf '%s\n' "$content" > "$log.loaded"; exit 0 ;;
  image)
    [ "$loaded" = "IMAGE-TAR-$CARBON_FAKE_REFERENCE" ] || exit 1
    if [ "$4" = '{{.Id}}' ]; then
      case "$5" in
        "$CARBON_FAKE_REFERENCE"|"$CARBON_FAKE_BOX_ID") printf '%s\n' "$CARBON_FAKE_BOX_ID"; exit 0 ;;
      esac
      exit 1
    fi
    [ "$5" = "$CARBON_FAKE_BOX_ID" ] || exit 1
    printf '%s\n' "$CARBON_FAKE_FINGERPRINT_TEXT"; exit 0 ;;
  network) exit 0 ;;
  run) printf '%s\n' 4f3c2b1a; exit 0 ;;
  inspect) printf '172.30.0.2\n'; exit 0 ;;
esac
exit 0
"""
FAKE_SSH = r"""#!/bin/bash
while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do shift; done
shift 2
exec "$@"
"""


def _executable(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(0o755)
    return path


@pytest.fixture
def box(tmp_path, monkeypatch):
    """Tools for the scripts (the fake docker, the real sha256sum), with the
    classic box's state under `tmp_path/log`."""
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("bash", "sha256sum", "mktemp", "rm"):
        (tools / name).symlink_to(shutil.which(name))
    _executable(tools / "docker", FAKE_DOCKER)
    _executable(tools / "ssh", FAKE_SSH)
    _executable(tools / "nvidia-ctk", "#!/bin/bash\nexit 0\n")
    _executable(
        tools / "nvidia-smi",
        "#!/bin/bash\nprintf '%s\\n' GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81\n",
    )
    environment = {
        "PATH": str(tools),
        "TMPDIR": str(tmp_path),
        "CARBON_FAKE_LOG": str(tmp_path / "log"),
        "CARBON_FAKE_REFERENCE": REFERENCE,
        "CARBON_FAKE_BOX_ID": BOX_ID,
        "CARBON_FAKE_FINGERPRINT_TEXT": FINGERPRINT_TEXT,
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    return {"tools": tools, "log": tmp_path / "log", "env": environment}


def run(script, box, **changed):
    return subprocess.run(
        ["/bin/bash", "-s"],
        input=script.encode(),
        env={**box["env"], **changed},
        capture_output=True,
        check=False,
        timeout=60,
    )


def calls(box):
    return box["log"].read_text().splitlines() if box["log"].exists() else []


def send(box, fingerprint=FINGERPRINT):
    client = SSHClient("miner@gpu-box", binary=str(box["tools"] / "ssh"))
    return send_image(
        client,
        CONTROLLER_ID,
        docker=str(box["tools"] / "docker"),
        fingerprint=fingerprint,
    )


def test_the_worker_sent_to_another_image_store_is_found_by_its_fingerprint(box):
    assert send(box) == "sent"
    made = calls(box)
    # It travels under its tag, so the box's copy keeps a name.
    assert f"tag {CONTROLLER_ID} {REFERENCE}" in made
    assert f"save {REFERENCE}" in made
    assert box["log"].with_suffix(".loaded").read_text().strip() == (
        "IMAGE-TAR-" + REFERENCE
    )
    # Held now, under the box's own ID: nothing is sent again.
    assert send(box) == "present"
    assert calls(box).count(f"save {REFERENCE}") == 1


def test_an_image_whose_fingerprint_differs_is_still_refused_and_keeps_its_tag(
    box, monkeypatch
):
    monkeypatch.setenv("CARBON_FAKE_FINGERPRINT_TEXT", "another image")
    with pytest.raises(RemoteMachineError) as refused:
        send(box)
    assert refused.value.code == "worker_image_not_loaded"
    # Nothing removed or retagged what arrived.
    assert not any(call.startswith(("rmi", "image rm", "untag")) for call in calls(box))


def test_the_check_is_exact_under_either_id(box):
    # Nothing loaded yet: missing, whatever the fingerprint.
    assert run(image_check_script(CONTROLLER_ID, FINGERPRINT), box).returncode == (
        rm.NO_WORKER_IMAGE
    )
    box["log"].with_suffix(".loaded").write_text("IMAGE-TAR-" + REFERENCE + "\n")
    assert run(image_check_script(CONTROLLER_ID, FINGERPRINT), box).returncode == 0
    # Without the controller's fingerprint only the ID counts: refused.
    assert run(image_check_script(CONTROLLER_ID), box).returncode == (
        rm.NO_WORKER_IMAGE
    )
    # One character of the fingerprint off: refused.
    other = ("0" if FINGERPRINT[0] != "0" else "1") + FINGERPRINT[1:]
    assert run(image_check_script(CONTROLLER_ID, other), box).returncode == (
        rm.NO_WORKER_IMAGE
    )
    with pytest.raises(ValueError):
        image_check_script(CONTROLLER_ID, "not-hex")


def test_a_job_starts_from_the_boxs_own_id_for_the_pinned_worker(box):
    box["log"].with_suffix(".loaded").write_text("IMAGE-TAR-" + REFERENCE + "\n")
    script = start_script(
        image_id=CONTROLLER_ID,
        name=NAME,
        env=(("CARBON_JOB_PORT", "8000"),),
        command=COMMAND,
        fingerprint=FINGERPRINT,
    )
    completed = run(script, box)
    assert completed.returncode == 0, completed.stderr
    (started,) = [call for call in calls(box) if call.startswith("run ")]
    assert f"--entrypoint {COMMAND[0]} {BOX_ID} -I -m" in started


def test_the_same_store_is_checked_by_id_as_before(box):
    # A box on the controller's own store answers the controller's ID.
    box["log"].with_suffix(".loaded").write_text("IMAGE-TAR-" + REFERENCE + "\n")
    same = {"CARBON_FAKE_BOX_ID": CONTROLLER_ID}
    assert run(image_check_script(CONTROLLER_ID), box, **same).returncode == 0


def test_the_controllers_fingerprint_hashes_what_the_box_hashes(box):
    docker = _executable(
        box["tools"] / "docker-local",
        "#!/bin/bash\n"
        f'[ "$4" = {FINGERPRINT_FORMAT!r} ] || exit 1\n'
        f"printf '%s\\n' {FINGERPRINT_TEXT!r}\n",
    )
    assert local_fingerprint(CONTROLLER_ID, docker=str(docker)) == FINGERPRINT
    # Not readable here: no fingerprint, so only the ID counts.
    missing = _executable(box["tools"] / "docker-none", "#!/bin/bash\nexit 1\n")
    assert local_fingerprint(CONTROLLER_ID, docker=str(missing)) is None
    assert local_fingerprint(CONTROLLER_ID, docker="/nonexistent/docker") is None
