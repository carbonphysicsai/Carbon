"""carbon-mcp with a runner profile an update set aside serves setup (gate
round 2b).

An update set compute aside (three images rebuilt) and moved the profile to
runner-profile.stale.json; `carbon-mcp --configuration …` then exited
runner_profile_unusable, so an agent or a headless miner could not re-check
compute through its normal entry. Now carbon-mcp serves the setup tier, over
the same state directory, and says which call re-checks compute; a usable
profile serves every operation as before. The installer's Next lines name the
MCP call beside the page's step.
"""

from __future__ import annotations

import json

import pytest

from carbon.miner_mcp import standard_cli
from scripts.dev.miner_launchpad import environment_setup
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS


@pytest.fixture
def served(monkeypatch):
    """Which door main() serves, and over which state directory: the real
    operations door up to its campaign host, the setup door recorded."""
    calls = []

    async def open_tier(state_dir=None):
        calls.append(("setup", state_dir))

    monkeypatch.setattr(standard_cli, "serve_open_tier", open_tier)
    monkeypatch.setattr(standard_cli, "_serve_from_checkout", lambda: None)
    return calls


def test_a_profile_an_update_set_aside_serves_setup_and_names_recheck(
    tmp_path, served, capsys
):
    state = tmp_path / "state"
    environment = state / "environment"
    environment.mkdir(parents=True)
    # The update moved it aside: nothing at the path the client was given.
    (environment / "runner-profile.stale.json").write_text("{}")
    profile = environment / "runner-profile.json"
    assert standard_cli.main(["--configuration", str(profile)]) == 0
    assert served == [("setup", state)]
    told = capsys.readouterr().err
    assert "runner_profile_missing" in told
    assert "carbon_setup_recheck" in told and "carbon_setup_status" in told
    assert "runner_profile_missing" in NEXT_ACTIONS


def test_a_profile_that_no_longer_describes_the_install_serves_setup(
    tmp_path, served, capsys, monkeypatch
):
    from scripts.dev.miner_launchpad import runner
    from scripts.dev.miner_launchpad.controller import Rejected

    profile = tmp_path / "runner-profile.json"
    profile.write_text("{}")
    profile.chmod(0o600)
    monkeypatch.setattr(runner, "private_json", lambda _path: {"fixture": True})
    monkeypatch.setattr(runner, "validated_profile", lambda cfg: cfg)
    monkeypatch.setattr(
        runner,
        "install_refusal",
        lambda _path, _cfg: Rejected(runner.CARBON_UPDATED, 409),
    )
    assert standard_cli.main(["--configuration", str(profile)]) == 0
    # Not a setup-written path: the default state directory.
    assert served == [("setup", None)]
    told = capsys.readouterr().err
    assert runner.CARBON_UPDATED in told and "carbon_setup_recheck" in told


def test_an_unreadable_profile_is_named_by_its_code_and_serves_setup(
    tmp_path, served, capsys
):
    profile = tmp_path / "runner-profile.json"
    profile.write_text("not json")
    profile.chmod(0o600)
    assert standard_cli.main(["--configuration", str(profile)]) == 0
    assert served[0][0] == "setup"
    assert "Your runner profile cannot be used here (" in capsys.readouterr().err


def test_a_usable_profile_serves_every_operation_as_before(
    tmp_path, served, monkeypatch
):
    operations = []

    async def serve_operations(configuration, state_dir=None):
        operations.append(configuration)

    monkeypatch.setattr(standard_cli, "serve_operations", serve_operations)
    profile = tmp_path / "runner-profile.json"
    assert standard_cli.main(["--configuration", str(profile)]) == 0
    assert operations == [profile] and served == []


def test_the_unusable_code_is_closed(tmp_path):
    missing = standard_cli._unusable(tmp_path / "absent.json", OSError("PRIVATE"))
    assert missing.code == "runner_profile_missing"
    present = tmp_path / "present.json"
    present.write_text("{}")
    other = standard_cli._unusable(present, ValueError("PRIVATE"))
    assert other.code == "runner_profile_unusable" and "PRIVATE" not in str(other)


def test_the_install_s_next_lines_name_the_mcp_call_beside_the_page():
    report = {
        "revision": {"to": "a" * 40},
        "images": {},
        "compute": "set aside",
        "next_steps": [
            environment_setup.RECHECK_STEP,
            "review in setup to write your profile",
            environment_setup.REINSTALL_STEP,
        ],
    }
    lines = [
        line for line in environment_setup.describe_install(report) if "Next:" in line
    ]
    assert lines[0].startswith("Next: Check Compute again in setup")
    assert "carbon_setup_recheck {confirm: true}" in lines[0]
    assert "carbon_setup_review {confirm: true}" in lines[1]
    # A step only the installer takes names no setup call.
    assert "carbon_setup" not in lines[2]
    json.dumps(lines)
