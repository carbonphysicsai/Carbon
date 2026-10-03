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
  revision it moved to, and rebuilds a GPU worker built before.
"""

from __future__ import annotations

import fcntl
import json
import subprocess
import sys
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
#: daemon, uv is the pinned version, and curl, nvidia-smi and systemctl are
#: never the real ones.
FAKE_TOOLS = {
    "docker": (
        '#!/bin/sh\nif [ "$*" = "info --format {{.DockerRootDir}}" ]; then\n'
        '  echo "$CARBON_TEST_DOCKER_ROOT"\nfi\nexit 0\n'
    ),
    "uv": '#!/bin/sh\necho "uv 0.12.7"\n',
    "curl": '#!/bin/sh\necho "curl ran" >&2\nexit 9\n',
    "systemctl": '#!/bin/sh\necho "systemctl $*" >> "$CARBON_TEST_LOG"\n',
}
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
case "$1" in -c) exec python3 "$@" ;; esac
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
    # Setup is checked against the images only once they are recorded.
    order = [line.split()[2] if line.startswith("python -m") else line for line in log]
    assert order.index("scripts.dev.miner_launchpad.installed") < order.index(
        "scripts.dev.miner_launchpad.environment_setup"
    )
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
