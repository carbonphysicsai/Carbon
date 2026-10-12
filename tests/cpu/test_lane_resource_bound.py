"""LANE-RESOURCE-BOUND-01: Carbon-operated lanes are bounded; a miner's is not.

Claims tested:

- the well-known fallback, `~/.config/carbon/research-resource-profile.json`:
  absent means no profile and every argument exactly as before; present and
  valid means the lane is bounded; a fallback file that is not owner-only,
  not a regular file, or not exactly the v1 schema refuses (POLICY), the same
  rules as a named file;
- `CARBON_RESEARCH_RESOURCE_PROFILE` still takes precedence: a named file is
  the only one read, and a bad named file never falls back;
- the process's own environment resolves the fallback under its home, so a
  door started without the variable is bounded too;
- the Level 4-5 live sessions (the hostile-model probe and staging path,
  `phase3 run` and `phase4 run`) refuse to start, typed
  `resource_profile_required`, with no profile in force, and start with one;
  below Level 4 nothing is checked;
- end to end through the real carrier code (Docker replaced): with nothing
  installed the miner lane's create arguments carry no caps, exactly as
  before; with the fallback installed they carry its bounds, and the
  containment check's arguments digest covers them.

The profile values are synthetic test fixtures, not Carbon policy. Not
security acceptance.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.agent_campaign.graphite import phase3, phase4
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session import containment_check as cc
from carbon.development_session import miner_container as mc
from carbon.development_session import research_carrier as carrier
from carbon.development_session import research_image
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_image import ResearchImageIdentity
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

#: Captured at import, before the suite's isolation replaces it per test.
REAL_PROCESS_HOME = mc._process_home
LAUNCH = "sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
CAPS = ("--memory", "--memory-swap", "--cpus", "--pids-limit")
PROFILE = mc.ResourceProfile(
    cpus=2, memory_bytes=3 * 1024**3, pids_limit=96, nofile=512
)
OTHER = mc.ResourceProfile(cpus=1, memory_bytes=1024**3, pids_limit=32, nofile=256)


def install(home, document=None, mode=0o600):
    """Write the well-known fallback file under `home`."""
    path = home / mc.RESOURCE_PROFILE_FALLBACK
    path.parent.mkdir(parents=True, exist_ok=True)
    body = PROFILE.record() if document is None else document
    path.write_text(json.dumps(body))
    path.chmod(mode)
    return path


def launch(tmp_path, profile=None):
    stage = tmp_path / "input"
    stage.mkdir(exist_ok=True)
    return mc.MinerResearchLaunch(
        "carbon-d4-" + "c" * 24,
        IMAGE_ID,
        LAUNCH,
        stage,
        mc.prepare_scratch(tmp_path / ("s" if profile is None else "p")),
        **({} if profile is None else {"resource_profile": profile}),
    )


# -- the fallback --------------------------------------------------------------------------
def test_the_fallback_is_the_well_known_home_path():
    assert mc.RESOURCE_PROFILE_FALLBACK == Path(
        ".config/carbon/research-resource-profile.json"
    )


def test_no_installed_fallback_means_no_profile_and_unlimited_arguments(tmp_path):
    assert mc.load_host_profile({"HOME": str(tmp_path)}) is None
    assert mc.load_host_profile({"HOME": str(tmp_path / "absent")}) is None
    # No home, or a relative one, has no fallback to read.
    assert mc.load_host_profile({}) is None
    assert mc.load_host_profile({"HOME": "relative/home"}) is None
    arguments = mc.create_arguments(launch(tmp_path))
    for cap in CAPS:
        assert cap not in arguments
    assert not any(a.startswith(mc._PROFILE_LABEL) for a in arguments)


def test_an_installed_fallback_bounds_the_lane(tmp_path):
    install(tmp_path)
    profile = mc.load_host_profile({"HOME": str(tmp_path)})
    assert profile == PROFILE
    arguments = mc.create_arguments(launch(tmp_path, profile))
    assert arguments[arguments.index("--memory") + 1] == str(PROFILE.memory_bytes)
    assert arguments[arguments.index("--pids-limit") + 1] == str(PROFILE.pids_limit)
    assert arguments[arguments.index("--cpus") + 1] == str(PROFILE.cpus)
    assert f"nofile={PROFILE.nofile}:{PROFILE.nofile}" in arguments
    # An empty variable is an unset one: the installed file still applies.
    environ = {"HOME": str(tmp_path), mc.RESOURCE_PROFILE_ENV: ""}
    assert mc.load_host_profile(environ) == PROFILE


@pytest.mark.parametrize(
    "spoil",
    [
        "group_readable",
        "world_readable",
        "symlink",
        "dangling_symlink",
        "directory",
        "unknown_key",
        "missing_key",
        "old_schema",
        "not_json",
        "not_positive",
    ],
)
def test_a_fallback_that_is_not_exactly_right_refuses(tmp_path, spoil):
    path = install(tmp_path)
    if spoil == "group_readable":
        path.chmod(0o640)
    elif spoil == "world_readable":
        path.chmod(0o604)
    elif spoil in ("symlink", "dangling_symlink"):
        real = tmp_path / "real.json"
        path.rename(real)
        if spoil == "dangling_symlink":
            real.unlink()
        path.symlink_to(real)
    elif spoil == "directory":
        path.unlink()
        path.mkdir(mode=0o700)
    elif spoil == "unknown_key":
        install(tmp_path, {**PROFILE.record(), "scratch_bytes": 1})
    elif spoil == "missing_key":
        record = PROFILE.record()
        del record["nofile"]
        install(tmp_path, record)
    elif spoil == "old_schema":
        install(tmp_path, {**PROFILE.record(), "schema": "v0"})
    elif spoil == "not_json":
        path.write_text("{")
    elif spoil == "not_positive":
        install(tmp_path, {**PROFILE.record(), "pids_limit": 0})
    with pytest.raises(WorkerFailure) as refused:
        mc.load_host_profile({"HOME": str(tmp_path)})
    assert refused.value.code in (WorkerCode.POLICY, WorkerCode.INVALID)
    if spoil != "not_positive":
        assert refused.value.code is WorkerCode.POLICY


def test_an_unreachable_fallback_refuses_rather_than_runs_unbounded(tmp_path):
    path = install(tmp_path)
    config = tmp_path / ".config"
    config.chmod(0)
    try:
        try:
            path.lstat()
        except PermissionError:
            pass
        else:
            pytest.skip("this user reads through a mode-0 directory")
        with pytest.raises(WorkerFailure) as refused:
            mc.load_host_profile({"HOME": str(tmp_path)})
        assert refused.value.code is WorkerCode.POLICY
    finally:
        config.chmod(0o700)


# -- precedence ----------------------------------------------------------------------------
def test_the_variable_takes_precedence_over_the_fallback(tmp_path):
    install(tmp_path)
    named = tmp_path / "named.json"
    named.write_text(json.dumps(OTHER.record()))
    named.chmod(0o600)
    environ = {"HOME": str(tmp_path), mc.RESOURCE_PROFILE_ENV: str(named)}
    assert mc.load_host_profile(environ) == OTHER


def test_a_bad_named_file_never_falls_back(tmp_path):
    install(tmp_path)
    for named in (str(tmp_path / "absent.json"), "relative.json"):
        environ = {"HOME": str(tmp_path), mc.RESOURCE_PROFILE_ENV: named}
        with pytest.raises(WorkerFailure) as refused:
            mc.load_host_profile(environ)
        assert refused.value.code is WorkerCode.POLICY


# -- the process environment ----------------------------------------------------------------
def test_the_process_environment_reads_the_fallback_under_its_home(
    tmp_path, monkeypatch
):
    monkeypatch.delenv(mc.RESOURCE_PROFILE_ENV, raising=False)
    monkeypatch.setattr(mc, "_process_home", lambda: str(tmp_path))
    assert mc.load_host_profile() is None
    install(tmp_path)
    assert mc.load_host_profile() == PROFILE


def test_the_process_home_is_home_else_the_password_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert REAL_PROCESS_HOME() == str(tmp_path)
    monkeypatch.delenv("HOME")
    pwd = pytest.importorskip("pwd")
    assert REAL_PROCESS_HOME() == pwd.getpwuid(os.getuid()).pw_dir


# -- the closed refusal --------------------------------------------------------------------
def test_require_host_profile_refuses_none_and_invalid_and_returns_one(tmp_path):
    with pytest.raises(mc.ResourceProfileRefused) as none:
        mc.require_host_profile({"HOME": str(tmp_path)})
    assert (
        none.value.code == mc.RESOURCE_PROFILE_REQUIRED == "resource_profile_required"
    )
    path = install(tmp_path)
    assert mc.require_host_profile({"HOME": str(tmp_path)}) == PROFILE
    path.chmod(0o644)
    with pytest.raises(mc.ResourceProfileRefused) as bad:
        mc.require_host_profile({"HOME": str(tmp_path)})
    assert bad.value.code == mc.RESOURCE_PROFILE_INVALID


def test_below_level_4_nothing_is_checked(tmp_path):
    for level in (0, 1, 2, 3):
        assert phase3.hostile_lane_bounds(level, {"HOME": str(tmp_path)}) is None
    install(tmp_path)
    assert phase3.hostile_lane_bounds(4, {"HOME": str(tmp_path)}) == PROFILE


# -- the Level 4 probe and staging sessions -----------------------------------------------
class Started(Exception):
    """The session got past the bounds check to its next step."""


def _refusal(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _phase3_args(tmp_path, level):
    return SimpleNamespace(
        challenge="challenge",
        level=level,
        score_variant=None,
        dry_run=False,
        root=str(tmp_path / "root"),
        grant="grant.json",
    )


@pytest.fixture
def phase3_live(monkeypatch, tmp_path):
    monkeypatch.delenv(mc.RESOURCE_PROFILE_ENV, raising=False)
    monkeypatch.setattr(mc, "_process_home", lambda: str(tmp_path))
    monkeypatch.setattr(challenge_scoring, "scoring_for", lambda challenge: object())
    monkeypatch.setattr(phase3, "development_variant_for", lambda *a: None)
    monkeypatch.setattr(phase3, "score_variant_for", lambda *a: None)

    def load_grant(path):
        raise Started

    monkeypatch.setattr(phase3, "load_grant", load_grant)


def test_a_level_4_constructor_session_refuses_to_start_unbounded(
    tmp_path, phase3_live, capsys
):
    for level in (4, 5):
        with pytest.raises(phase3.RunnerRefused):
            phase3.command_run(_phase3_args(tmp_path, level))
        assert _refusal(capsys)["reason_code"] == "resource_profile_required"
    # Nothing was created: refused before the root or the grant.
    assert not (tmp_path / "root").exists()


def test_a_level_4_constructor_session_starts_with_a_profile(
    tmp_path, phase3_live, capsys
):
    install(tmp_path)
    with pytest.raises(Started):
        phase3.command_run(_phase3_args(tmp_path, 4))


def test_a_level_3_session_is_not_checked(tmp_path, phase3_live):
    with pytest.raises(Started):
        phase3.command_run(_phase3_args(tmp_path, 3))


def test_an_invalid_installed_profile_refuses_typed(tmp_path, phase3_live, capsys):
    install(tmp_path, mode=0o644)
    with pytest.raises(phase3.RunnerRefused):
        phase3.command_run(_phase3_args(tmp_path, 4))
    assert _refusal(capsys)["reason_code"] == "resource_profile_invalid"


@pytest.fixture
def phase4_live(monkeypatch, tmp_path):
    monkeypatch.delenv(mc.RESOURCE_PROFILE_ENV, raising=False)
    monkeypatch.setattr(mc, "_process_home", lambda: str(tmp_path))
    monkeypatch.setattr(challenge_scoring, "scoring_for", lambda challenge: object())
    monkeypatch.setattr(phase4, "attack_modules", dict)
    monkeypatch.setattr(phase4, "adapter_for", lambda *a: (object(), None))

    def live_checks(*args, **kwargs):
        raise Started

    monkeypatch.setattr(phase4, "live_checks", live_checks)


def _phase4_args(tmp_path, level):
    return SimpleNamespace(
        score_variant=None,
        challenge="challenge",
        level=level,
        dry_run=False,
        grant="grant.json",
        credential_file="credential",
        miner_profile="profile.json",
        miner_campaign="campaign",
        root=str(tmp_path / "root"),
    )


def test_a_level_4_attacker_session_refuses_to_start_unbounded(
    tmp_path, phase4_live, capsys
):
    with pytest.raises(phase3.RunnerRefused):
        phase4.command_run(_phase4_args(tmp_path, 4))
    assert _refusal(capsys)["reason_code"] == "resource_profile_required"
    assert not (tmp_path / "root").exists()


def test_a_level_4_attacker_session_starts_with_a_profile(tmp_path, phase4_live):
    install(tmp_path)
    with pytest.raises(Started):
        phase4.command_run(_phase4_args(tmp_path, 4))


def test_a_level_0_attacker_session_is_not_checked(tmp_path, phase4_live):
    with pytest.raises(Started):
        phase4.command_run(_phase4_args(tmp_path, None))


# -- end to end through the real carrier code ----------------------------------------------
IMAGE = ResearchImageIdentity(IMAGE_ID, "sha256:" + "c" * 64, "sha256:" + "d" * 64)


class RecordingDocker:
    """Records every command; the cell writes an empty observation."""

    def __init__(self):
        self.commands = []

    def run(self, arguments, *, timeout=30, accepted=(0,)):
        self.commands.append(list(arguments))
        return SimpleNamespace(stdout=b"", stderr=b"", returncode=0)

    def json(self, arguments, *, timeout=30):
        self.commands.append(list(arguments))
        if arguments[0] == "version":
            return {"Version": "fake"}
        return {"Running": True, "OOMKilled": False}

    def stream_kept(self, arguments, operation, *, timeout):
        self.commands.append(list(arguments))
        (operation / "stdout.txt").write_bytes(b"")
        (operation / "stderr.txt").write_bytes(b"")
        output = operation / "scratch" / "output"
        output.mkdir(exist_ok=True)
        (output / cc.OUTPUT_NAME).write_text("{}")

    def created(self):
        (create,) = [c for c in self.commands if c and c[0] == "create"]
        return create


def _through_the_carrier(tmp_path, monkeypatch, home):
    fake = RecordingDocker()
    monkeypatch.delenv(mc.RESOURCE_PROFILE_ENV, raising=False)
    monkeypatch.setattr(mc, "_process_home", lambda: str(home))
    monkeypatch.setattr(carrier, "DockerCLI", lambda: fake)
    monkeypatch.setattr(
        carrier, "doctor", lambda **kwargs: SimpleNamespace(eligible=True, cpuset="0")
    )
    monkeypatch.setattr(research_image, "verify_image", lambda image, cli: image)
    monkeypatch.setattr(carrier, "spawn_watchdog", lambda **kwargs: None)
    monkeypatch.setattr(carrier, "remove_exact_container", lambda **kwargs: None)
    monkeypatch.setattr(
        mc, "inspect_isolation", lambda cli, run: {"lane": mc.LANE, "network": "none"}
    )
    parent = tmp_path / "canaries"
    parent.mkdir(exist_ok=True)
    report = cc.containment_check(
        root=tmp_path / "gate", image=IMAGE, canary_parent=parent, host_home="/h"
    )
    return fake.created(), report


def test_a_miners_research_with_nothing_installed_is_unchanged(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    created, report = _through_the_carrier(tmp_path, monkeypatch, home)
    for cap in CAPS:
        assert cap not in created
    assert not any(a.startswith(mc._PROFILE_LABEL) for a in created)
    assert report["create_arguments_digest"] == digest(canonical(created))


def test_the_installed_fallback_bounds_the_carriers_container(tmp_path, monkeypatch):
    home = tmp_path / "home"
    install(home)
    created, report = _through_the_carrier(tmp_path, monkeypatch, home)
    assert created[created.index("--memory") + 1] == str(PROFILE.memory_bytes)
    assert created[created.index("--memory-swap") + 1] == str(PROFILE.memory_bytes)
    assert created[created.index("--pids-limit") + 1] == str(PROFILE.pids_limit)
    assert created[created.index("--cpus") + 1] == str(PROFILE.cpus)
    assert f"nofile={PROFILE.nofile}:{PROFILE.nofile}" in created
    assert f"{mc._PROFILE_LABEL}={PROFILE.digest()}" in created
    # The containment check's digest covers the bounds the container was given.
    assert report["create_arguments_digest"] == digest(canonical(created))
