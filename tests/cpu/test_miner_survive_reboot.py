"""A miner's Control Center comes back after a reboot (MINER-SURVIVE-REBOOT-01).

The owner, 2026-10-10: "I just want easy and efficient and reliable". These
tests hold:
- `install_miner.sh --service` makes sure the user lingers, so the enabled
  unit starts at boot without a login: linger already on is left alone; off
  is turned on with `loginctl enable-linger`; refused, the install still
  succeeds and prints the exact `sudo loginctl enable-linger` command. It
  prints the final state, and a WSL note on WSL. A plain install asks
  loginctl nothing;
- setup's status and Review warn `reboot_recovery_off`, additively, when this
  install's unit is not enabled or linger is off, with the exact command;
  enabled with linger, anything unreadable, off Linux, or checks without the
  probe warn of nothing. The probe is read only, with a timeout; its
  subprocess calls are stubbed here;
- the unit name setup probes is the one the installer writes.
No real systemctl or loginctl is run: both are stand-ins or stubs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from test_miner_install import Sandbox
from test_miner_launchpad_environment_setup import Checks, Onboarding

from scripts.dev.miner_launchpad import environment_setup
from scripts.dev.miner_launchpad.environment_setup import (
    EnvironmentSetup,
    LiveChecks,
    control_center_unit,
    reboot_recovery,
)
from scripts.dev.miner_launchpad.setup_operations import MCP, status

USER = "fixture-miner"
SUDO = f"sudo loginctl enable-linger {USER}"


# --- The installer ---------------------------------------------------------


@pytest.fixture
def sandbox(tmp_path):
    return Sandbox(tmp_path)


def linger(sandbox, state: str) -> dict:
    """The stand-in loginctl's linger state, starting at `state`, and its log."""
    file = sandbox.tmp / "linger"
    file.write_text(state + "\n")
    return {
        "USER": USER,
        "CARBON_TEST_LINGER_FILE": str(file),
        "CARBON_TEST_LINGER_LOG": str(sandbox.tmp / "loginctl.log"),
    }


def loginctl_calls(sandbox) -> list[str]:
    log = sandbox.tmp / "loginctl.log"
    return log.read_text().splitlines() if log.exists() else []


def test_linger_already_on_is_left_alone(sandbox):
    completed = sandbox.run("--service", **linger(sandbox, "yes"))
    assert completed.returncode == 0, completed.stderr
    calls = loginctl_calls(sandbox)
    assert calls and all(call.startswith("loginctl show-user") for call in calls)
    assert f"(linger) for {USER}: yes." in completed.stdout
    assert "sudo loginctl" not in completed.stdout


def test_linger_off_is_turned_on_without_sudo(sandbox):
    completed = sandbox.run("--service", **linger(sandbox, "no"))
    assert completed.returncode == 0, completed.stderr
    assert f"loginctl enable-linger {USER}" in loginctl_calls(sandbox)
    assert f"(linger) for {USER}: yes." in completed.stdout
    assert "sudo loginctl" not in completed.stdout


def test_a_refused_linger_prints_the_sudo_command_and_the_install_succeeds(sandbox):
    completed = sandbox.run(
        "--service", CARBON_TEST_ENABLE_LINGER="denied", **linger(sandbox, "no")
    )
    assert completed.returncode == 0, completed.stderr
    assert f"loginctl enable-linger {USER}" in loginctl_calls(sandbox)
    assert (
        f"The Control Center will not start after a reboot until you run: {SUDO}"
        in completed.stdout
    )
    assert f"(linger) for {USER}: no." in completed.stdout
    # The service itself was still written, enabled and started.
    assert (
        sandbox.logged()[-1] == "systemctl --user restart carbon-control-center.service"
    )


def test_the_wsl_note_is_printed_on_wsl_only(sandbox):
    completed = sandbox.run("--service", **linger(sandbox, "yes"))
    assert completed.returncode == 0, completed.stderr
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text().lower()
    except OSError:
        release = ""
    on_wsl = "microsoft" in release or "wsl" in release
    note = "Windows does not start WSL at boot"
    assert (note in completed.stdout) is on_wsl
    if on_wsl:
        assert "FRESH_MINER_JOURNEY.md" in completed.stdout


def test_a_plain_install_asks_loginctl_nothing(sandbox):
    completed = sandbox.run("--no-start", **linger(sandbox, "no"))
    assert completed.returncode == 0, completed.stderr
    assert loginctl_calls(sandbox) == []
    assert "linger" not in completed.stdout


def test_setup_probes_the_unit_the_installer_writes(sandbox):
    """LA-F15's names, computed by setup the installer's way."""
    default = sandbox.tmp / "home/.carbon/development-launchpad"
    miner_a = sandbox.tmp / "home/.carbon/minerA"
    completed = sandbox.run(
        "--service", "--port", "8789", CARBON_STATE_DIR=str(miner_a)
    )
    assert completed.returncode == 0, completed.stderr
    (written,) = (sandbox.tmp / "home/.config/systemd/user").iterdir()
    assert control_center_unit(miner_a, default) == written.name
    assert control_center_unit(default, default) == "carbon-control-center.service"


# --- The read-only probe -----------------------------------------------------


def stub_commands(monkeypatch, answers, calls=None):
    """subprocess.run answering systemctl and loginctl: a string is its
    stdout; an exception is raised. Any other program runs as before."""
    real = subprocess.run

    def run(command, *args, **kwargs):
        if command[0] not in ("systemctl", "loginctl"):
            return real(command, *args, **kwargs)
        assert kwargs.get("timeout") == environment_setup.REBOOT_PROBE_TIMEOUT
        assert kwargs.get("check") is False
        if calls is not None:
            calls.append(command)
        answer = answers[command[0]]
        if isinstance(answer, BaseException):
            raise answer
        return subprocess.CompletedProcess(command, 0, stdout=answer, stderr="")

    monkeypatch.setattr(environment_setup.sys, "platform", "linux")
    monkeypatch.setattr(environment_setup.subprocess, "run", run)


def test_the_probe_reads_the_unit_and_linger_only(monkeypatch):
    calls = []
    stub_commands(monkeypatch, {"systemctl": "enabled\n", "loginctl": "yes\n"}, calls)
    assert reboot_recovery("carbon-control-center.service", USER) == {
        "unit_state": "enabled",
        "linger": True,
        "user": USER,
    }
    assert calls == [
        ["systemctl", "--user", "is-enabled", "carbon-control-center.service"],
        ["loginctl", "show-user", USER, "-p", "Linger", "--value"],
    ]


@pytest.mark.parametrize(
    "answers,expected",
    [
        ({"systemctl": "disabled\n", "loginctl": "no\n"}, ("disabled", False)),
        ({"systemctl": "not-found\n", "loginctl": "yes\n"}, ("not-found", True)),
        ({"systemctl": "", "loginctl": ""}, (None, None)),
        ({"systemctl": "static\n", "loginctl": "maybe\n"}, (None, None)),
        (
            {
                "systemctl": OSError("no systemctl"),
                "loginctl": subprocess.TimeoutExpired("loginctl", 3),
            },
            (None, None),
        ),
    ],
)
def test_the_probe_says_none_for_anything_unknown(monkeypatch, answers, expected):
    stub_commands(monkeypatch, answers)
    facts = reboot_recovery("carbon-control-center.service", USER)
    assert (facts["unit_state"], facts["linger"]) == expected


def test_the_probe_runs_nothing_off_linux(monkeypatch):
    def run(*args, **kwargs):
        raise AssertionError("nothing is run off Linux")

    monkeypatch.setattr(environment_setup.sys, "platform", "darwin")
    monkeypatch.setattr(environment_setup.subprocess, "run", run)
    facts = reboot_recovery("carbon-control-center.service")
    assert (facts["unit_state"], facts["linger"]) == (None, None)


# --- The warning ---------------------------------------------------------------


def a_setup(tmp_path, checks):
    state = tmp_path / "state"
    state.mkdir(mode=0o700, parents=True)
    return EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)


class Probed(Checks):
    """Fixture checks whose reboot probe answers `facts`."""

    def __init__(self, facts):
        super().__init__()
        self.facts = facts
        self.units = []

    def reboot_recovery(self, unit):
        self.units.append(unit)
        if isinstance(self.facts, BaseException):
            raise self.facts
        return self.facts


def facts(unit_state, linger) -> dict:
    return {"unit_state": unit_state, "linger": linger, "user": USER}


def test_a_unit_not_installed_warns_with_the_install_command(tmp_path):
    checks = Probed(facts("not-found", True))
    setup = a_setup(tmp_path, checks)
    (warning,) = setup.reboot_warnings()
    unit = control_center_unit(tmp_path / "state")
    assert checks.units == [unit]
    assert warning["code"] == "reboot_recovery_off"
    assert warning["unit"] == unit.removesuffix(".service")
    assert (warning["unit_state"], warning["linger"]) == ("not-found", True)
    assert "does not run as a service" in warning["message"]
    assert warning["next_step"] == (
        "install again with the service: "
        f"CARBON_STATE_DIR={tmp_path / 'state'} "
        f"{environment_setup.REPO / 'scripts/install_miner.sh'} --service"
    )


def test_a_disabled_unit_and_linger_off_warn_with_both_commands(tmp_path):
    setup = a_setup(tmp_path, Probed(facts("disabled", False)))
    (warning,) = setup.reboot_warnings()
    unit = control_center_unit(tmp_path / "state").removesuffix(".service")
    assert f"its service {unit} is not enabled" in warning["message"]
    assert "linger is off" in warning["message"]
    assert f"systemctl --user enable {unit}" in warning["next_step"]
    assert f"loginctl enable-linger {USER}" in warning["next_step"]
    assert SUDO in warning["next_step"]


def test_linger_off_alone_warns(tmp_path):
    setup = a_setup(tmp_path, Probed(facts("enabled", False)))
    (warning,) = setup.reboot_warnings()
    assert warning["next_step"].startswith("let your services start at boot")
    assert "systemctl" not in warning["next_step"]


@pytest.mark.parametrize(
    "probe",
    [
        facts("enabled", True),
        facts(None, None),
        facts("enabled", None),
        facts(None, True),
        None,
        RuntimeError("probe failed"),
    ],
)
def test_recovery_on_or_unknown_warns_of_nothing(tmp_path, probe):
    assert a_setup(tmp_path, Probed(probe)).reboot_warnings() == []


def test_checks_without_the_probe_warn_of_nothing(tmp_path):
    assert a_setup(tmp_path, Checks()).reboot_warnings() == []


def test_status_warns_through_the_live_probe(tmp_path, monkeypatch):
    """The live checks' probe, its commands stubbed: status carries the
    warning beside everything it said before."""
    stub_commands(monkeypatch, {"systemctl": "disabled\n", "loginctl": "no\n"})
    setup = a_setup(tmp_path, LiveChecks())
    unprobed = EnvironmentSetup(
        setup.root.parent, onboarding=Onboarding(), checks=Checks()
    )
    before = status(unprobed, door=MCP)
    result = status(setup, door=MCP)
    assert [w["code"] for w in result["warnings"]] == ["reboot_recovery_off"]
    assert {k: v for k, v in result.items() if k != "warnings"} == {
        k: v for k, v in before.items() if k != "warnings"
    }
    assert before["warnings"] == []


def test_status_has_no_warning_when_recovery_is_on(tmp_path, monkeypatch):
    stub_commands(monkeypatch, {"systemctl": "enabled\n", "loginctl": "yes\n"})
    assert status(a_setup(tmp_path, LiveChecks()), door=MCP)["warnings"] == []


def test_review_adds_the_warning_after_its_own(tmp_path, monkeypatch):
    """Additive: Review's own warnings and fields stay as they were, and the
    recorded profile's warnings never hold this live one."""
    own = {"code": "no_evaluation_endpoint", "challenge": "x", "message": "m"}
    monkeypatch.setattr(
        EnvironmentSetup,
        "_review",
        lambda self, value: {"attached": False, "warnings": [own]},
    )
    setup = a_setup(tmp_path, Probed(facts("enabled", False)))
    reviewed = setup.review({"confirm": True})
    assert reviewed["attached"] is False
    assert reviewed["warnings"][0] == own
    assert [w["code"] for w in reviewed["warnings"]] == [
        "no_evaluation_endpoint",
        "reboot_recovery_off",
    ]
    quiet = a_setup(tmp_path / "quiet", Probed(facts("enabled", True)))
    assert quiet.review({"confirm": True})["warnings"] == [own]
