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
  containment check's arguments digest covers them;
- the scratch floor: a Level 4-5 session refuses to start, typed
  `scratch_host_low_space`, when the filesystem holding its scratch has less
  than 15 GB free (`shutil.disk_usage` faked);
- the bounded lane (the Test Lead's ruling of 2026-10-12, replacing the
  polling watchdog): under a profile the container is labelled
  `carbon.miner-research.bounded.v1`, mounts only /input, and has a
  kernel-capped tmpfs scratch, which its inspection must read back exactly;
  its output is copied out as a bounded tar stream (directories and regular
  files only, nothing escapes); a program that fails with its tmpfs full
  settles typed `scratch_cap_exceeded`, never a score; with no profile the
  scratch stays a bind mount and nothing is measured or copied.

The profile values are synthetic test fixtures, not Carbon policy. Not
security acceptance.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
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
    # The campaign's scratch root, on a filesystem with room (faked).
    monkeypatch.setattr(phase3, "_scratch_root", lambda *a: tmp_path)
    free_space(monkeypatch, 100 * 10**9)

    def live_checks(*args, **kwargs):
        raise Started

    monkeypatch.setattr(phase4, "live_checks", live_checks)


def free_space(monkeypatch, free):
    """Fake `shutil.disk_usage` reporting `free` bytes free."""
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=free * 2, used=free, free=free),
    )


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
    # The cell's output is written to scratch: the host's bind mount, or under
    # a profile the container's own tmpfs, copied out before removal.
    fake = TmpfsDocker({cc.OUTPUT_NAME: b"{}"})
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


# -- the scratch floor ---------------------------------------------------------------------
def test_the_floor_refuses_below_15_gb_free(tmp_path, monkeypatch):
    assert mc.SCRATCH_HOST_FLOOR_BYTES == 15 * 10**9
    free_space(monkeypatch, 15 * 10**9 - 1)
    with pytest.raises(mc.ResourceProfileRefused) as low:
        mc.require_scratch_floor(tmp_path)
    assert low.value.code == mc.SCRATCH_HOST_LOW_SPACE == "scratch_host_low_space"
    free_space(monkeypatch, 15 * 10**9)
    assert mc.require_scratch_floor(tmp_path) == 15 * 10**9


def test_an_unmeasurable_filesystem_refuses_too(tmp_path, monkeypatch):
    def unreadable(path):
        raise PermissionError(path)

    monkeypatch.setattr(shutil, "disk_usage", unreadable)
    with pytest.raises(mc.ResourceProfileRefused) as low:
        mc.require_scratch_floor(tmp_path)
    assert low.value.code == mc.SCRATCH_HOST_LOW_SPACE


def test_the_floor_is_checked_only_at_level_4_and_above(tmp_path, monkeypatch):
    def no_root(*args):
        raise AssertionError("below Level 4 nothing is read")

    monkeypatch.setattr(phase3, "_scratch_root", no_root)
    free_space(monkeypatch, 1)
    for level in (0, 1, 2, 3):
        assert phase3.hostile_scratch_floor(level, "p.json", "c") is None
    monkeypatch.setattr(phase3, "_scratch_root", lambda *a: tmp_path)
    with pytest.raises(phase3.RunnerRefused):
        phase3.hostile_scratch_floor(4, "p.json", "c")


def test_a_level_4_attacker_session_refuses_a_host_low_on_space(
    tmp_path, phase4_live, monkeypatch, capsys
):
    install(tmp_path)
    free_space(monkeypatch, 14 * 10**9)
    with pytest.raises(phase3.RunnerRefused):
        phase4.command_run(_phase4_args(tmp_path, 4))
    assert _refusal(capsys)["reason_code"] == "scratch_host_low_space"
    assert not (tmp_path / "root").exists()


def test_a_level_4_constructor_session_refuses_a_host_low_on_space(
    tmp_path, phase3_live, monkeypatch, capsys
):
    install(tmp_path)
    grant = SimpleNamespace(provider="graphite")
    monkeypatch.setattr(phase3, "load_grant", lambda path: grant)
    monkeypatch.setattr(
        phase3.grant_binding, "check_phase3_grant", lambda *a, **k: None
    )
    monkeypatch.setattr(phase3.grant_binding, "model_provider_refusal", lambda *a: None)
    monkeypatch.setattr(phase3, "_scratch_root", lambda *a: tmp_path)
    args = _phase3_args(tmp_path, 4)
    args.__dict__.update(
        study=None,
        model_provider=None,
        credential_file=None,
        miner_profile="profile.json",
        miner_campaign="c" * 32,
        literature_snapshot=None,
    )
    free_space(monkeypatch, 14 * 10**9)
    with pytest.raises(phase3.RunnerRefused):
        phase3.command_run(args)
    assert _refusal(capsys)["reason_code"] == "scratch_host_low_space"
    # With room, the session goes on to its next check.
    free_space(monkeypatch, 15 * 10**9)
    with pytest.raises(phase3.RunnerRefused):
        phase3.command_run(args)
    assert _refusal(capsys)["reason_code"] == "live_run_needs_a_literature_snapshot"


# -- the bounded lane: a kernel-capped tmpfs scratch ---------------------------------------
def test_the_bounded_lane_mounts_a_capped_tmpfs_and_only_input(tmp_path):
    assert mc.BOUNDED_LANE == "carbon.miner-research.bounded.v1"
    assert mc.SCRATCH_TMPFS_OPTIONS == (
        "rw,nosuid,nodev,noexec,size=2147483648,nr_inodes=100000"
    )
    bounded = mc.create_arguments(launch(tmp_path, PROFILE))
    assert f"org.opencontainers.image.carbon.lane={mc.BOUNDED_LANE}" in bounded
    assert f"org.opencontainers.image.carbon.lane={mc.LANE}" not in bounded
    assert bounded[bounded.index("--tmpfs") + 1] == (
        "/scratch:" + mc.SCRATCH_TMPFS_OPTIONS
    )
    mounts = [bounded[i + 1] for i, a in enumerate(bounded) if a == "--mount"]
    assert len(mounts) == 1 and "target=/input," in mounts[0]
    assert not any("target=/scratch" in a for a in bounded)


def test_a_miners_lane_keeps_its_bind_mounted_scratch(tmp_path):
    unbounded = mc.create_arguments(launch(tmp_path))
    assert f"org.opencontainers.image.carbon.lane={mc.LANE}" in unbounded
    assert "--tmpfs" not in unbounded
    assert not any(mc.BOUNDED_LANE in a for a in unbounded)
    assert any(
        a.startswith("type=bind,") and "target=/scratch," in a for a in unbounded
    )


class Inspecting:
    def __init__(self, value):
        self.value = value

    def json(self, arguments, *, timeout=30):
        return self.value


def _inspected(run, *, lane, mounts, tmpfs):
    profile = run.resource_profile
    host = {
        "ReadonlyRootfs": True,
        "Privileged": False,
        "NetworkMode": "none",
        "IpcMode": "private",
        "PidMode": "",
        "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges=true"],
        "Tmpfs": tmpfs,
    }
    labels = {"org.opencontainers.image.carbon.lane": lane}
    if profile is not None:
        labels[mc._PROFILE_LABEL] = profile.digest()
        host.update(
            NanoCpus=profile.cpus * 10**9,
            Memory=profile.memory_bytes,
            MemorySwap=profile.memory_bytes,
            PidsLimit=profile.pids_limit,
            Ulimits=[
                {"Name": "nofile", "Soft": profile.nofile, "Hard": profile.nofile}
            ],
        )
    return {
        "Image": IMAGE_ID,
        "HostConfig": host,
        "Config": {"User": f"{mc.WORKER_UID}:{mc.WORKER_GID}", "Labels": labels},
        "Mounts": mounts,
    }


def _input(run):
    return {"Destination": "/input", "Source": str(run.input_directory), "RW": False}


def _bind_scratch(run):
    return {"Destination": "/scratch", "Source": str(run.scratch_directory), "RW": True}


TMPFS = {"/scratch": mc.SCRATCH_TMPFS_OPTIONS}


def test_inspection_reads_back_the_bounded_lane_exactly(tmp_path):
    run = launch(tmp_path, PROFILE)
    good = _inspected(run, lane=mc.BOUNDED_LANE, mounts=[_input(run)], tmpfs=TMPFS)
    record = mc.inspect_isolation(Inspecting(good), run)
    assert record["lane"] == mc.BOUNDED_LANE
    assert record["scratch_tmpfs"] == mc.SCRATCH_TMPFS_OPTIONS
    assert record["resource_profile"] == PROFILE.digest()


@pytest.mark.parametrize(
    "spoil",
    [
        "unlimited_label",
        "scratch_bind_too",
        "no_tmpfs",
        "larger",
        "no_inode_cap",
        "exec",
    ],
)
def test_inspection_refuses_a_bounded_container_that_is_not_exact(tmp_path, spoil):
    run = launch(tmp_path, PROFILE)
    lane, mounts, tmpfs = mc.BOUNDED_LANE, [_input(run)], dict(TMPFS)
    if spoil == "unlimited_label":
        lane = mc.LANE
    elif spoil == "scratch_bind_too":
        mounts.append(_bind_scratch(run))
    elif spoil == "no_tmpfs":
        tmpfs = None
    elif spoil == "larger":
        tmpfs["/scratch"] = tmpfs["/scratch"].replace("size=2147483648", "size=4g")
    elif spoil == "no_inode_cap":
        tmpfs["/scratch"] = tmpfs["/scratch"].replace(",nr_inodes=100000", "")
    elif spoil == "exec":
        tmpfs["/scratch"] = tmpfs["/scratch"].replace("noexec,", "")
    inspected = _inspected(run, lane=lane, mounts=mounts, tmpfs=tmpfs)
    with pytest.raises(WorkerFailure) as refused:
        mc.inspect_isolation(Inspecting(inspected), run)
    assert refused.value.code is WorkerCode.POLICY


def test_inspection_of_a_miners_lane_is_unchanged(tmp_path):
    run = launch(tmp_path)
    mounts = [_input(run), _bind_scratch(run)]
    good = _inspected(run, lane=mc.LANE, mounts=mounts, tmpfs=None)
    assert mc.inspect_isolation(Inspecting(good), run)["lane"] == mc.LANE
    bounded_label = _inspected(run, lane=mc.BOUNDED_LANE, mounts=mounts, tmpfs=None)
    with pytest.raises(WorkerFailure):
        mc.inspect_isolation(Inspecting(bounded_label), run)


# -- copying a tmpfs scratch's output out ----------------------------------------------------
def _export(source, archive):
    """Run the worker's own export script over `source` instead of /scratch."""
    script = mc.SCRATCH_EXPORT.replace("/scratch/output", str(source))
    with open(archive, "wb") as out:
        subprocess.run([sys.executable, "-I", "-c", script], stdout=out, check=True)
    return archive


def test_the_export_round_trips_regular_files_and_directories(tmp_path):
    source = tmp_path / "container" / "output"
    (source / "nested" / "deeper").mkdir(parents=True)
    (source / "model.json").write_text("{}")
    (source / "nested" / "deeper" / "w.bin").write_bytes(b"\x00\x01" * 1000)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    out = mc.unpack_outputs(_export(source, tmp_path / "o.tar"), scratch)
    assert out == scratch / "output"
    assert (out / "model.json").read_text() == "{}"
    assert (out / "nested" / "deeper" / "w.bin").read_bytes() == b"\x00\x01" * 1000
    assert mc.collect_outputs(scratch, tmp_path / "snapshot") == {
        "model.json": 2,
        "nested/deeper/w.bin": 2000,
    }


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_the_export_refuses_links_and_special_files(tmp_path, kind):
    source = tmp_path / "container" / "output"
    source.mkdir(parents=True)
    (source / "a.txt").write_text("a")
    if kind == "symlink":
        (source / "link").symlink_to("/etc/passwd")
    elif kind == "hardlink":
        os.link(source / "a.txt", source / "b.txt")
    else:
        os.mkfifo(source / "pipe")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    with pytest.raises(mc.MinerOutputRefused):
        mc.unpack_outputs(_export(source, tmp_path / "o.tar"), scratch)


@pytest.mark.parametrize(
    "name", ["output/../escape", "other/x", "/output/x", "../output/x"]
)
def test_a_malformed_stream_is_refused_and_nothing_escapes(tmp_path, name):
    archive = tmp_path / "o.tar"
    with tarfile.open(archive, "w") as tar:
        info = tarfile.TarInfo(name)
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    with pytest.raises(ValueError):
        mc.unpack_outputs(archive, scratch)
    assert not (tmp_path / "escape").exists()
    assert not (scratch / "x").exists()


class Statvfs:
    def __init__(self, value):
        self.value = value

    def json(self, arguments, *, timeout=30):
        assert mc.SCRATCH_STATVFS in arguments
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


@pytest.mark.parametrize(
    "value, full",
    [
        ({"free_bytes": 0, "free_inodes": 5}, True),
        ({"free_bytes": 1024**2 - 1, "free_inodes": 5}, True),
        ({"free_bytes": 10 * 1024**2, "free_inodes": 0}, True),
        ({"free_bytes": 10 * 1024**2, "free_inodes": 5}, False),
        (WorkerFailure(WorkerCode.RUNTIME), False),
        ({"free_bytes": -1, "free_inodes": 5}, False),
        ({"free_bytes": 0}, False),
        ("full", False),
    ],
)
def test_a_full_scratch_is_bytes_or_inodes_and_unmeasured_is_not_full(value, full):
    assert mc.scratch_full(Statvfs(value), "c") is full


# -- end to end through the real carrier ------------------------------------------------------
class TmpfsDocker(RecordingDocker):
    """A container whose program writes `files` (name -> bytes, or a callable
    making something there) into its own scratch: the host's bind mount
    without a profile, the container's own tmpfs with one. A program told to
    `fill` writes, finds its tmpfs full, and exits 1."""

    def __init__(self, files, *, fill=False, free=0):
        super().__init__()
        self.files, self.fill, self.free = files, fill, free
        self.tmpfs = None
        self.inside = None

    def run(self, arguments, *, timeout=30, accepted=(0,)):
        if arguments[:1] == ["create"]:
            self.tmpfs = "--tmpfs" in arguments
        return super().run(arguments, timeout=timeout, accepted=accepted)

    def json(self, arguments, *, timeout=30):
        if mc.SCRATCH_STATVFS in arguments:
            self.commands.append(["exec", "<statvfs>"])
            return {"free_bytes": self.free, "free_inodes": 9}
        return super().json(arguments, timeout=timeout)

    def stream_kept(self, arguments, operation, *, timeout):
        self.commands.append(list(arguments))
        (operation / "stdout.txt").write_bytes(b"")
        (operation / "stderr.txt").write_bytes(b"")
        self.inside = operation / ("container-tmpfs" if self.tmpfs else "scratch")
        output = self.inside / "output"
        output.mkdir(parents=True, exist_ok=True)
        for name, body in self.files.items():
            if callable(body):
                body(output / name)
            else:
                (output / name).write_bytes(body)
        if self.fill:
            raise WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\n")

    def stream_to_file(self, arguments, destination, *, maximum, timeout):
        assert mc.SCRATCH_EXPORT in arguments and self.tmpfs
        assert maximum == mc.SCRATCH_EXPORT_MAX_BYTES
        self.commands.append(["exec", "<export>"])
        _export(self.inside / "output", destination)
        return destination.stat().st_size


def _through(tmp_path, monkeypatch, fake, *, profile):
    home = tmp_path / "home"
    home.mkdir()
    if profile:
        install(home)
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
        mc, "inspect_isolation", lambda cli, run: {"lane": mc.lane_of(run)}
    )
    ledger = cc._ledger(tmp_path / "ledger")
    return carrier.run_script(
        ledger,
        owner=cc.OWNER,
        identity="tmpfs-scratch-1",
        source="cell",
        files={},
        image=IMAGE,
        seconds=180,
    )


def _operation(tmp_path):
    (operation,) = (tmp_path / "ledger").glob("operation-*")
    return operation


def test_a_bounded_runs_output_is_copied_out_of_its_tmpfs(tmp_path, monkeypatch):
    fake = TmpfsDocker({"model.json": b"{}", "w.bin": b"x" * 4096})
    run = _through(tmp_path, monkeypatch, fake, profile=True)
    assert fake.tmpfs is True
    assert set(run["files"]) == {"model.json", "w.bin"}
    assert ["exec", "<export>"] in fake.commands
    operation = _operation(tmp_path)
    assert (operation / "scratch" / "output" / "w.bin").read_bytes() == b"x" * 4096
    assert not (operation / "scratch-output.tar").exists()
    assert ["exec", "<statvfs>"] not in fake.commands


def test_a_bounded_runs_link_is_refused_as_its_own_output(tmp_path, monkeypatch):
    fake = TmpfsDocker({"a.txt": b"a", "link": lambda p: p.symlink_to("/etc/passwd")})
    with pytest.raises(carrier.MinerProgramFailure) as refused:
        _through(tmp_path, monkeypatch, fake, profile=True)
    assert refused.value.code is WorkerCode.OUTPUT
    assert refused.value.result["observation"] == "OUTPUT_NOT_REGULAR_FILES"
    assert not (_operation(tmp_path) / "snapshot").exists()


def test_a_scratch_flood_fills_the_tmpfs_and_settles_typed(tmp_path, monkeypatch):
    fake = TmpfsDocker({"flood.bin": b"x" * 1024}, fill=True, free=0)
    with pytest.raises(carrier.MinerProgramFailure) as refused:
        _through(tmp_path, monkeypatch, fake, profile=True)
    result = refused.value.result
    assert refused.value.code is WorkerCode.POLICY
    assert result["observation"] == mc.SCRATCH_CAP_EXCEEDED == "scratch_cap_exceeded"
    assert result["state"] == "FAILED_MINER"
    assert result["scientific_qualification"] is False
    assert result["official_eligible"] is False
    operation = _operation(tmp_path)
    cap = json.loads((operation / "scratch-cap.json").read_bytes())
    assert cap == {
        "refusal": "scratch_cap_exceeded",
        "cap_bytes": 2 * 1024**3,
        "cap_inodes": 100_000,
    }
    # The flood stayed in the container's tmpfs; nothing reached the host.
    assert not (operation / "scratch" / "output").exists()
    assert not (operation / "snapshot").exists()
    assert ["exec", "<export>"] not in fake.commands


def test_a_bounded_failure_with_room_left_keeps_its_own_type(tmp_path, monkeypatch):
    fake = TmpfsDocker({}, fill=True, free=10 * 1024**2)
    with pytest.raises(carrier.MinerProgramFailure) as refused:
        _through(tmp_path, monkeypatch, fake, profile=True)
    assert refused.value.result["observation"] == "NONZERO_EXIT"
    assert not (_operation(tmp_path) / "scratch-cap.json").exists()


def test_a_miners_research_with_no_profile_is_never_capped(tmp_path, monkeypatch):
    fake = TmpfsDocker({"flood.bin": b"x" * 64 * 1024})
    run = _through(tmp_path, monkeypatch, fake, profile=False)
    assert fake.tmpfs is False
    assert set(run["files"]) == {"flood.bin"}
    assert ["exec", "<export>"] not in fake.commands
    assert ["exec", "<statvfs>"] not in fake.commands


def test_a_miners_failing_research_is_never_measured(tmp_path, monkeypatch):
    fake = TmpfsDocker({}, fill=True, free=0)
    with pytest.raises(carrier.MinerProgramFailure) as refused:
        _through(tmp_path, monkeypatch, fake, profile=False)
    assert refused.value.result["observation"] == "NONZERO_EXIT"
    assert ["exec", "<statvfs>"] not in fake.commands
