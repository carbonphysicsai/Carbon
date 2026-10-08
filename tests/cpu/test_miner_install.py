"""From a clean machine to the Control Center (C-MLP-04), and updating it
(LP-PROD-E).

`scripts/install_miner.sh` builds the pinned images on the miner's machine
and records where they are; setup fills them in, and a restart opens the
miner's own written profile. These tests hold the record and the script's
promises without running Docker:
- the record is owner-only, names existing absolute paths, and setup shows
  it; a missing or foreign record shows nothing;
- the script never asks for or reads a key, seed phrase or password, and
  passes `bash -n`;
- in a sandbox checkout with a local origin and stand-ins for Docker, uv,
  the environment and the image builds, the script stops before changing
  anything on a dirty checkout, a ref outside main, too little disk or a
  running Control Center; it syncs every group the documented commands use,
  always prints how to start the Control Center again, updates to the latest
  main without starting a second one, carries on with the installer of the
  revision it moved to, and rebuilds a GPU worker built before;
- after the 2026-10-03 review: a listing of thousands of local changes still
  ends with the stash command, one filesystem holding the checkout and
  Docker's images needs room for both, a plain reinstall rebuilds the GPU
  worker too, an `--update` to an installer without `--update` stops before
  the checkout moves, the service log is owner-only before the service
  starts, and the launcher's session token reaches a file while it runs;
- after the 2026-10-07 acceptance run (LA-F6): with the service, the
  systemd user manager itself must reach Docker, or the install stops in
  step 1 with the fix.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.dev.miner_launchpad import installed

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/install_miner.sh"


def test_the_installed_images_are_recorded_owner_only(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    worker, analysis = tmp_path / "worker.json", tmp_path / "analysis.json"
    worker.write_text("{}")
    analysis.write_text("{}")
    path = installed.write(
        state, image_manifest=worker, analysis_image_manifest=analysis
    )
    assert path.stat().st_mode & 0o777 == 0o600
    assert installed.read(state) == {
        "image_manifest": str(worker),
        "analysis_image_manifest": str(analysis),
    }
    worker.unlink()
    assert installed.read(state) == {"analysis_image_manifest": str(analysis)}
    path.write_text(json.dumps({"schema": "other", "image_manifest": str(analysis)}))
    assert installed.read(state) is None
    assert installed.read(tmp_path / "absent") is None


def test_setup_shows_what_the_installer_built(tmp_path):
    from test_miner_launchpad_environment_setup import Checks, Onboarding

    from scripts.dev.miner_launchpad.environment_setup import EnvironmentSetup

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    worker = tmp_path / "worker.json"
    worker.write_text("{}")
    installed.write(state, image_manifest=worker, analysis_image_manifest=worker)
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Checks())
    assert setup.state()["installed"]["image_manifest"] == str(worker)


def test_the_install_script_asks_for_no_secret():
    text = SCRIPT.read_text().lower()
    for forbidden in ("read -s", "read -p", "mnemonic", "seed phrase:", "password="):
        assert forbidden not in text
    assert subprocess.run(["bash", "-n", str(SCRIPT)], check=False).returncode == 0
    assert SCRIPT.stat().st_mode & 0o111


def test_the_install_script_refuses_off_linux_before_doing_anything(tmp_path):
    """Its first step checks the machine; on a refusal nothing is installed."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "uname").write_text("#!/bin/sh\necho Darwin\n")
    (fake / "uname").chmod(0o755)
    completed = subprocess.run(
        ["bash", str(SCRIPT), "--no-start"],
        env={"PATH": f"{fake}:/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "Linux is required" in completed.stderr
    assert not (tmp_path / ".local").exists()


# --- The script in a sandbox checkout (LP-PROD-E) ------------------------------

#: Stand-ins on PATH, ahead of the real tools: Docker answers without a
#: daemon, uv is the pinned version, curl, nvidia-smi and systemctl are
#: never the real ones, and df reports 1 TiB free on one filesystem, so no
#: test depends on the host's free disk.
FAKE_TOOLS = {
    "docker": (
        '#!/bin/sh\nif [ "$*" = "info --format {{.DockerRootDir}}" ]; then\n'
        '  echo "$CARBON_TEST_DOCKER_ROOT"\nfi\nexit 0\n'
    ),
    "uv": '#!/bin/sh\necho "uv 0.12.7"\n',
    "curl": '#!/bin/sh\necho "curl ran" >&2\nexit 9\n',
    "systemctl": '#!/bin/sh\necho "systemctl $*" >> "$CARBON_TEST_LOG"\n',
    # The user manager's own view of Docker (LA-F6): it reaches Docker unless
    # the test says the manager lacks the docker group.
    "systemd-run": (
        '#!/bin/sh\necho "systemd-run $*" >> "$CARBON_TEST_LOG"\n'
        'if [ "$CARBON_TEST_MANAGER_DOCKER" = "denied" ]; then\n'
        '  echo "permission denied while trying to connect to the docker API" >&2\n'
        "  exit 1\nfi\necho 27.0.0\n"
    ),
    "df": (
        "#!/bin/sh\necho 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
        "echo 'fixture 1073741824 0 1073741824 0% /'\n"
    ),
}


def fake_df(sandbox, free_kb: int, *, mount: str = "/", fails: bool = False):
    """df reporting `free_kb` free on one filesystem mounted at `mount`, or
    failing with no output."""
    df = sandbox.tools / "df"
    if fails:
        df.write_text("#!/bin/sh\nexit 1\n")
    else:
        df.write_text(
            "#!/bin/sh\necho 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
            f"echo 'fixture {2 * free_kb} {free_kb} {free_kb} 50% {mount}'\n"
        )
    df.chmod(0o755)


#: The checkout's own stand-ins: the environment sync writes a fake
#: interpreter and Control Center; each image build writes a manifest naming
#: the revision it was built at.
FAKE_CHECKOUT = {
    "scripts/dev/bootstrap.sh": (
        "#!/bin/sh\nset -e\n"
        'echo "bootstrap $CARBON_UV_GROUPS" >> "$CARBON_TEST_LOG"\n'
        "mkdir -p .venv/bin\n"
        'cp "$CARBON_TEST_PYTHON" .venv/bin/python\n'
        'cp "$CARBON_TEST_CONTROL_CENTER" .venv/bin/carbon-control-center\n'
    ),
    "scripts/dev/c03_worker_image.sh": (
        '#!/bin/sh\nmkdir -p "$(dirname "$1")"\n'
        'echo "{\\"image_id\\": \\"sha256:$(git rev-parse HEAD)\\"}" > "$1"\n'
        'echo "worker $(git rev-parse HEAD)" >> "$CARBON_TEST_LOG"\n'
    ),
    "scripts/dev/accelerator_worker_image.sh": (
        '#!/bin/sh\nmkdir -p "$(dirname "$1")"\necho "{}" > "$1"\n'
        'echo "gpu worker" >> "$CARBON_TEST_LOG"\n'
    ),
}
FAKE_PYTHON = """#!/bin/sh
echo "python $*" >> "$CARBON_TEST_LOG"
case "$1" in -c) exec "$CARBON_TEST_REAL_PYTHON" "$@" ;; esac
case "$2" in
  carbon.development_session.research_image)
    mkdir -p .carbon-artifacts/research-images
    echo '{}' > .carbon-artifacts/research-images/analysis.json
    echo "{\\"manifest\\": \\"$PWD/.carbon-artifacts/research-images/analysis.json\\"}" ;;
  scripts.dev.miner_launchpad.environment_setup)
    case "$3" in
      gpu-installed) echo "${CARBON_TEST_GPU_INSTALLED:-no}" ;;
      after-install) echo "What this install changed: (fixture)" ;;
      service-unit) echo "[Unit]" ;;
    esac ;;
esac
"""
FAKE_CONTROL_CENTER = '#!/bin/sh\necho "control center $*" >> "$CARBON_TEST_LOG"\n'


class Sandbox:
    """A Carbon checkout cloned from a local origin, with the stand-ins."""

    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.origin = tmp_path / "origin.git"
        self.work = tmp_path / "work"
        self.clone = tmp_path / "home" / "carbon"
        self.state = tmp_path / "home" / ".carbon" / "development-launchpad"
        self.log = tmp_path / "log.txt"
        self.tools = tmp_path / "tools"
        self.tools.mkdir()
        for name, text in FAKE_TOOLS.items():
            self._executable(self.tools / name, text)
        self._executable(tmp_path / "python", FAKE_PYTHON)
        self._executable(tmp_path / "control-center", FAKE_CONTROL_CENTER)
        (tmp_path / "docker-root").mkdir()
        self.git(
            "init",
            "--quiet",
            "--bare",
            "--initial-branch=main",
            str(self.origin),
            cwd=tmp_path,
        )
        self.git(
            "init", "--quiet", "--initial-branch=main", str(self.work), cwd=tmp_path
        )
        self._executable(self.work / "scripts" / "install_miner.sh", SCRIPT.read_text())
        for name, text in FAKE_CHECKOUT.items():
            self._executable(self.work / name, text)
        (self.work / ".gitignore").write_text(".venv/\n.carbon-artifacts/\n")
        self.commit("the first revision")
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "--quiet", "origin", "main")
        self.git("clone", "--quiet", str(self.origin), str(self.clone), cwd=tmp_path)

    @staticmethod
    def _executable(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)

    def git(self, *args, cwd=None):
        return subprocess.run(
            [
                "git",
                "-c",
                "user.name=fixture",
                "-c",
                "user.email=fixture@invalid",
                *args,
            ],
            cwd=cwd or self.work,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "--quiet", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def publish(self, message: str, *, branch: str = "main") -> str:
        """A new revision on origin's `branch`."""
        if branch != "main":
            self.git("checkout", "--quiet", "-B", branch)
        revision = self.commit(message)
        self.git("push", "--quiet", "origin", branch)
        if branch != "main":
            self.git("checkout", "--quiet", "main")
        return revision

    def head(self) -> str:
        return self.git("rev-parse", "HEAD", cwd=self.clone)

    def run(self, *args, **env):
        return subprocess.run(
            ["bash", str(self.clone / "scripts" / "install_miner.sh"), *args],
            cwd=self.tmp,
            env={
                "PATH": f"{self.tools}:/usr/bin:/bin",
                "HOME": str(self.tmp / "home"),
                "CARBON_STATE_DIR": str(self.state),
                "CARBON_TEST_LOG": str(self.log),
                "CARBON_TEST_PYTHON": str(self.tmp / "python"),
                # The canonical image's interpreter is not on /usr/bin.
                "CARBON_TEST_REAL_PYTHON": sys.executable,
                "CARBON_TEST_CONTROL_CENTER": str(self.tmp / "control-center"),
                "CARBON_TEST_DOCKER_ROOT": str(self.tmp / "docker-root"),
                **env,
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def logged(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []


@pytest.fixture
def sandbox(tmp_path):
    return Sandbox(tmp_path)


def test_a_dirty_checkout_stops_at_step_2_with_the_command_that_sets_it_aside(
    sandbox,
):
    """The image build refuses an untracked file; so does step 2, before
    anything is fetched, synced or built, and it names the command."""
    (sandbox.clone / "notes.txt").write_text("mine")
    before = sandbox.head()
    completed = sandbox.run("--no-start")
    assert completed.returncode == 2
    assert "notes.txt" in completed.stderr
    assert f"git -C {sandbox.clone} stash push --include-untracked" in completed.stderr
    assert sandbox.head() == before
    assert sandbox.logged() == []


def test_thousands_of_local_changes_still_end_with_the_stash_command(sandbox):
    """Review finding, 2026-10-03: a listing bigger than a pipe's buffer,
    piped into `head`, died of SIGPIPE under set -e and pipefail before the
    installer said what to do. 3,000 untracked paths list as about 94 KiB."""
    data = sandbox.clone / "data"
    data.mkdir()
    for number in range(3000):
        (data / f"untracked-file-{number:05d}.txt").write_text("")
    before = sandbox.head()
    completed = sandbox.run("--no-start")
    assert completed.returncode == 2
    assert "data/untracked-file-00000.txt" in completed.stderr
    assert "... and 2990 more." in completed.stderr
    assert f"git -C {sandbox.clone} stash push --include-untracked" in completed.stderr
    assert sandbox.head() == before
    assert sandbox.logged() == []


def test_a_ref_outside_main_is_refused_before_anything_moves(sandbox):
    """Setup accepts only a revision in main, so the installer checks that
    first rather than building images setup would then refuse."""
    before = sandbox.head()
    sandbox.publish("a branch revision", branch="feature")
    completed = sandbox.run("--ref", "feature", "--no-start")
    assert completed.returncode == 2
    assert "is not in Carbon's main" in completed.stderr
    assert "clean_accepted_checkout_required" in completed.stderr
    assert sandbox.head() == before
    assert sandbox.logged() == []


def test_too_little_disk_stops_the_install_before_it_builds(sandbox):
    df = sandbox.tools / "df"
    df.write_text(
        "#!/bin/sh\necho 'Filesystem 1024-blocks Used Available Capacity Mounted'\n"
        "echo 'fixture 2097152 1048576 1048576 50% /'\n"
    )
    df.chmod(0o755)
    completed = sandbox.run("--no-start")
    assert completed.returncode == 2
    assert "need 5 GiB free" in completed.stderr
    assert "1 GiB are free" in completed.stderr
    assert sandbox.logged() == []


def test_one_filesystem_for_the_checkout_and_images_needs_room_for_both(sandbox):
    """13 GiB passes each check alone (5 and 12 GiB), not both on one
    filesystem, as on WSL by default."""
    fake_df(sandbox, 13 * 1048576)
    completed = sandbox.run("--no-start")
    assert completed.returncode == 2
    assert "one filesystem holds both" in completed.stderr
    assert "need 17 GiB free" in completed.stderr
    assert "13 GiB are free" in completed.stderr
    assert sandbox.logged() == []


def test_two_filesystems_each_need_only_their_own_share(sandbox):
    df = sandbox.tools / "df"
    df.write_text(
        '#!/bin/sh\ncase "$3" in *docker-root*) m=/docker ;; *) m=/ ;; esac\n'
        "echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
        'echo "fixture 27262976 13631488 13631488 50% $m"\n'
    )
    df.chmod(0o755)
    completed = sandbox.run("--no-start")
    assert completed.returncode == 0, completed.stderr


def test_free_space_df_cannot_read_is_said_and_not_fatal(sandbox):
    """Review finding, 2026-10-03: a failing df ended the installer silently
    under set -e and pipefail; it now says what to make sure of."""
    fake_df(sandbox, 0, fails=True)
    completed = sandbox.run("--no-start")
    assert completed.returncode == 0, completed.stderr
    assert "Could not read the free space at" in completed.stdout


def test_a_running_control_center_is_never_moved_under(sandbox):
    """The Control Center holds its state directory's lock while it runs; an
    install would move the checkout it runs from, so it stops and says how
    to stop the Control Center first."""
    sandbox.state.mkdir(parents=True)
    with open(sandbox.state / "owner.lock", "a+b") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = sandbox.run("--no-start")
    assert completed.returncode == 2
    assert "a Control Center is running" in completed.stderr
    assert "Ctrl-C" in completed.stderr
    assert sandbox.logged() == []


def test_an_install_syncs_every_documented_group_and_prints_the_start_command(
    sandbox,
):
    completed = sandbox.run("--no-start")
    assert completed.returncode == 0, completed.stderr
    log = sandbox.logged()
    # Every group a documented `uv run --group ...` names, so none of those
    # commands re-syncs the environment the installer made.
    assert "bootstrap science-jax chain archive mcp" in log
    assert any("installed write" in line for line in log)
    assert any("environment_setup after-install --state-dir" in line for line in log)
    # Setup is checked against the images only once they are recorded. (Every
    # install asks `gpu-installed` before it builds, since a plain reinstall
    # rebuilds a GPU worker too, so the order is that of `after-install`.)
    recorded = next(i for i, line in enumerate(log) if "installed write" in line)
    checked = next(i for i, line in enumerate(log) if "after-install" in line)
    assert any("environment_setup gpu-installed" in line for line in log[:recorded])
    assert recorded < checked
    assert "What this install changed: (fixture)" in completed.stdout
    assert "Start it again later with:" in completed.stdout
    assert (
        f"{sandbox.clone}/.venv/bin/carbon-control-center --state-dir "
        f"{sandbox.state} --port 8788"
    ) in completed.stdout
    assert f"{sandbox.clone}/.venv/bin/carbon-miner-signer" in completed.stdout
    assert not any(line.startswith("control center") for line in log)


def test_an_install_prints_the_restart_command_before_it_starts(sandbox):
    completed = sandbox.run()
    assert completed.returncode == 0, completed.stderr
    assert "Start it again later with:" in completed.stdout
    assert sandbox.logged()[-1] == (
        f"control center --state-dir {sandbox.state} --port 8788"
    )


def test_an_update_moves_to_the_latest_main_and_starts_no_second_control_center(
    sandbox,
):
    first = sandbox.head()
    assert sandbox.run("--no-start").returncode == 0
    newer = sandbox.publish("a newer main")
    completed = sandbox.run("--update")
    assert completed.returncode == 0, completed.stderr
    assert sandbox.head() == newer
    assert f"Carbon moved from {first[:12]} to {newer[:12]}." in completed.stdout
    log = sandbox.logged()
    assert f"worker {newer}" in log
    assert log.count("bootstrap science-jax chain archive mcp") == 2
    assert "What this install changed: (fixture)" in completed.stdout
    assert "Start it again later with:" in completed.stdout
    assert not any(line.startswith("control center") for line in log)


def test_an_update_carries_on_with_the_installer_of_the_revision_it_moved_to(
    sandbox,
):
    assert sandbox.run("--no-start").returncode == 0
    script = sandbox.work / "scripts" / "install_miner.sh"
    script.write_text(
        script.read_text().replace(
            "set -euo pipefail\n", 'set -euo pipefail\necho "INSTALLER-B"\n', 1
        )
    )
    newer = sandbox.publish("a newer installer")
    completed = sandbox.run("--update")
    assert completed.returncode == 0, completed.stderr
    assert "The installer changed" in completed.stdout
    # The new installer ran once, from step 1, and did not move the checkout
    # again.
    assert completed.stdout.count("INSTALLER-B") == 1
    assert "with that revision's installer" in completed.stdout
    assert sandbox.head() == newer
    assert sandbox.logged().count(f"worker {newer}") == 1


def test_an_update_rebuilds_a_gpu_worker_built_before(sandbox):
    """An update keeps every image current, and the GPU worker needs no local
    GPU to build: a remote setup's worker is rebuilt too."""
    assert sandbox.run("--no-start").returncode == 0
    assert "gpu worker" not in sandbox.logged()
    completed = sandbox.run("--update", CARBON_TEST_GPU_INSTALLED="yes")
    assert completed.returncode == 0, completed.stderr
    assert "rebuilds it too" in completed.stdout
    assert "gpu worker" in sandbox.logged()


def test_a_plain_reinstall_rebuilds_a_gpu_worker_built_before(sandbox):
    """Review finding, 2026-10-03: a plain run also moves the checkout to the
    latest main, so it rebuilds the GPU worker too; before, only --update
    did, and setup checked the old GPU worker again beside the new images."""
    assert sandbox.run("--no-start").returncode == 0
    newer = sandbox.publish("a newer main")
    completed = sandbox.run("--no-start", CARBON_TEST_GPU_INSTALLED="yes")
    assert completed.returncode == 0, completed.stderr
    assert sandbox.head() == newer
    assert "this install rebuilds it too" in completed.stdout
    log = sandbox.logged()
    assert log.index("gpu worker") > log.index(f"worker {newer}")


def test_an_update_to_an_installer_without_update_stops_before_it_moves(sandbox):
    """An installer from before --update existed would be re-run with
    --update after the checkout had moved, and refuse it; the update stops
    first and says to run it without --update."""
    assert sandbox.run("--no-start").returncode == 0
    before = sandbox.head()
    built = len(sandbox.logged())
    script = sandbox.work / "scripts" / "install_miner.sh"
    script.write_text("#!/usr/bin/env bash\necho 'an installer without it'\nexit 2\n")
    older_kind = sandbox.publish("an installer without --update")
    completed = sandbox.run("--update")
    assert completed.returncode == 2
    assert f"the installer at {older_kind[:12]} has no --update" in completed.stderr
    assert "Run it without --update" in completed.stderr
    assert sandbox.head() == before
    assert len(sandbox.logged()) == built


def test_the_service_log_is_owner_only_before_the_service_starts(sandbox):
    """The log carries the session token. systemd leaves an existing file's
    mode alone, so the installer makes it owner-only itself, and refuses a
    log that is a symbolic link."""
    sandbox.state.mkdir(parents=True)
    log = sandbox.state / "control-center.log"
    log.write_text("an earlier run\n")
    log.chmod(0o644)
    completed = sandbox.run("--service")
    assert completed.returncode == 0, completed.stderr
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    assert log.read_text() == "an earlier run\n"
    log.unlink()
    log.symlink_to(sandbox.tmp / "elsewhere.log")
    completed = sandbox.run("--service")
    assert completed.returncode == 2
    assert "is a symbolic link" in completed.stderr
    assert not (sandbox.tmp / "elsewhere.log").exists()


def test_an_update_needs_an_install(sandbox):
    completed = sandbox.run("--update")
    assert completed.returncode == 2
    assert "run this without --update first" in completed.stderr
    assert sandbox.logged() == []


def test_the_service_option_writes_and_starts_the_user_unit(sandbox):
    """--service leaves the terminal free: the unit is written where systemd
    reads user units, enabled and started, and the restart command and where
    the session token is are printed. (systemctl is a stand-in here.)"""
    completed = sandbox.run("--service")
    assert completed.returncode == 0, completed.stderr
    unit = sandbox.tmp / "home/.config/systemd/user/carbon-control-center.service"
    assert unit.read_text() == "[Unit]\n"
    log = sandbox.logged()
    assert log[-3:] == [
        "systemctl --user daemon-reload",
        "systemctl --user enable --quiet carbon-control-center.service",
        "systemctl --user restart carbon-control-center.service",
    ]
    assert "systemctl --user restart carbon-control-center" in completed.stdout
    assert f"{sandbox.state}/control-center.log" in completed.stdout
    assert not any(line.startswith("control center") for line in log)
    # A later update finds the unit and restarts it, without --service.
    completed = sandbox.run("--update")
    assert completed.returncode == 0, completed.stderr
    assert (
        sandbox.logged()[-1] == "systemctl --user restart carbon-control-center.service"
    )


#: How the installer asks the user manager itself to reach Docker (LA-F6).
MANAGER_DOCKER_CHECK = "systemd-run --user --wait --quiet --collect --pipe"


def test_the_service_checks_docker_from_the_user_manager_before_anything(sandbox):
    """LA-F6: the service runs under the systemd user manager, so the
    installer asks the manager, not this shell, to reach Docker, in step 1
    before anything is synced or built. A plain install asks nothing."""
    assert sandbox.run("--no-start").returncode == 0
    assert not any(line.startswith("systemd-run") for line in sandbox.logged())
    completed = sandbox.run("--service")
    assert completed.returncode == 0, completed.stderr
    log = sandbox.logged()
    asked = [i for i, line in enumerate(log) if line.startswith(MANAGER_DOCKER_CHECK)]
    assert len(asked) == 1
    assert log[asked[0]].endswith("/docker info --format {{.ServerVersion}}")
    synced = [i for i, line in enumerate(log) if line.startswith("bootstrap")]
    assert asked[0] < synced[-1]


@pytest.mark.parametrize(
    "environment,fix",
    [
        (
            {"WSL_DISTRO_NAME": "carbon-fresh"},
            "From Windows, run: wsl --terminate carbon-fresh, then open the distro again",
        ),
        ({}, "sudo systemctl restart user@"),
    ],
)
def test_a_user_manager_without_docker_stops_the_service_install_first(
    sandbox, environment, fix
):
    """LA-F6, as the fresh WSL distro met it: the docker group was added after
    the user manager started, so this shell reaches Docker and the manager
    does not. The install stops in step 1 with the fix and what it stops;
    nothing is synced, built or written, and no unit is enabled or started."""
    before = sandbox.head()
    completed = sandbox.run(
        "--service", CARBON_TEST_MANAGER_DOCKER="denied", **environment
    )
    assert completed.returncode == 2
    assert "Docker answers this shell but not your systemd user manager" in (
        completed.stderr
    )
    assert fix in completed.stderr
    assert "That stops" in completed.stderr or "that stops" in completed.stderr
    assert "Nothing was changed" in completed.stderr
    assert sandbox.head() == before
    log = sandbox.logged()
    assert len(log) == 2
    assert log[0] == "systemctl --user show-environment"
    assert log[1].startswith(MANAGER_DOCKER_CHECK)
    unit = sandbox.tmp / "home/.config/systemd/user/carbon-control-center.service"
    assert not unit.exists()


# --- carbon-control-center (LP-PROD-E) -----------------------------------------


def test_the_control_center_is_one_installed_command(monkeypatch):
    """`carbon-control-center` runs this checkout's controller with the
    options it was given."""
    import tomllib

    import carbon_control_center
    from scripts.dev.miner_launchpad import controller

    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert scripts["carbon-control-center"] == "carbon_control_center:main"
    assert carbon_control_center.CONTROLLER == Path(controller.__file__).resolve()
    seen = []
    monkeypatch.setattr(controller, "main", lambda: seen.append(list(sys.argv[1:])))
    monkeypatch.setattr(sys, "argv", ["carbon-control-center"])
    carbon_control_center.main(["--port", "8790"])
    assert seen == [["--port", "8790"]]


def test_the_session_token_reaches_the_log_while_the_control_center_runs(tmp_path):
    """Review finding, 2026-10-03: as the user service, the Control Center's
    output goes to a file, which Python block-buffers, so the token line
    reached the log only at exit, and the miner reads it from the log. The
    real controller runs here on loopback, its output sent to a file, with
    no PYTHONUNBUFFERED from the environment: the launcher's own line
    buffering must carry the token there while it runs."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = dict(os.environ)
    environment.pop("PYTHONUNBUFFERED", None)
    environment.pop("PYTHONPATH", None)
    log, errors = tmp_path / "control-center.log", tmp_path / "errors.txt"
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "import carbon_control_center; carbon_control_center.main(sys.argv[2:])"
    )
    with open(log, "ab") as output, open(errors, "wb") as error:
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                code,
                str(ROOT),
                "--state-dir",
                str(tmp_path / "state"),
                "--port",
                str(port),
            ],
            cwd=tmp_path,
            env=environment,
            stdout=output,
            stderr=error,
        )
    try:
        deadline = time.monotonic() + 60
        while b"Local session token" not in log.read_bytes():
            if process.poll() is not None:
                pytest.fail(errors.read_text())
            if time.monotonic() > deadline:
                pytest.fail("no session token in the log while the Control Center ran")
            time.sleep(0.05)
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_the_service_unit_runs_unbuffered():
    from scripts.dev.miner_launchpad.environment_setup import service_unit

    text = service_unit(Path("/srv/miner/state"), 8788, Path("/srv/miner/carbon"))
    assert "Environment=PYTHONUNBUFFERED=1\n" in text
