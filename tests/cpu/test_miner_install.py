"""From a clean machine to the Control Center (C-MLP-04).

`scripts/install_miner.sh` builds the pinned images on the miner's machine
and records where they are; setup fills them in, and a restart opens the
miner's own written profile. These tests hold the record and the script's
promises without running Docker:
- the record is owner-only, names existing absolute paths, and setup shows
  it; a missing or foreign record shows nothing;
- the script never asks for or reads a key, seed phrase or password, and
  passes `bash -n`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

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
