"""Carbon's own host may bound the miner lane; a miner's machine never is.

INTERNAL-RESOURCE-PROFILE-01: an operator's resource profile, read only from
an owner-only file the host names in `CARBON_RESEARCH_RESOURCE_PROFILE`, adds
CPU, memory, process and open-file bounds to the miner lane on Carbon's own
operator host. With no profile named, every argument is exactly as before
(the owner's 23 September 2026 direction: the miner's research is unlimited).
The profile values below are synthetic test fixtures, not Carbon policy.
"""

import json
import os

import pytest

from carbon.development_session import miner_container as mc
from carbon.reconstruction.worker.model import (
    WORKER_GID,
    WORKER_UID,
    WorkerCode,
    WorkerFailure,
)

LAUNCH = "sha256:" + "a" * 64
IMAGE = "sha256:" + "b" * 64
PROFILE = mc.ResourceProfile(
    cpus=4, memory_bytes=8 * 1024**3, pids_limit=512, nofile=4096
)


def launch(tmp_path, profile=None):
    stage = tmp_path / "input"
    stage.mkdir(exist_ok=True)
    return mc.MinerResearchLaunch(
        "carbon-d4-" + "c" * 24,
        IMAGE,
        LAUNCH,
        stage,
        mc.prepare_scratch(tmp_path / ("s" if profile is None else "p")),
        **({} if profile is None else {"resource_profile": profile}),
    )


def flag(arguments, name):
    return arguments[arguments.index(name) + 1]


# -- the arguments -------------------------------------------------------------------------------
def test_no_profile_leaves_every_argument_exactly_as_before(tmp_path):
    arguments = mc.create_arguments(launch(tmp_path))
    for cap in ("--memory", "--memory-swap", "--cpus", "--pids-limit"):
        assert cap not in arguments
    assert not any(a.startswith(mc._PROFILE_LABEL) for a in arguments)
    assert flag(arguments, "--shm-size") == str(mc._host_memory_bytes())
    assert f"OMP_NUM_THREADS={os.cpu_count() or 1}" in arguments


def test_a_profile_adds_exactly_its_bounds_and_keeps_isolation(tmp_path):
    plain = mc.create_arguments(launch(tmp_path))
    bounded = mc.create_arguments(launch(tmp_path, PROFILE))
    assert flag(bounded, "--cpus") == "4"
    assert (
        flag(bounded, "--memory") == flag(bounded, "--memory-swap") == str(8 * 1024**3)
    )
    assert flag(bounded, "--pids-limit") == "512"
    assert "nofile=4096:4096" in bounded
    assert f"{mc._PROFILE_LABEL}={PROFILE.digest()}" in bounded
    assert int(flag(bounded, "--shm-size")) <= PROFILE.memory_bytes
    assert f"OMP_NUM_THREADS={min(os.cpu_count() or 1, 4)}" in bounded
    # Isolation is untouched.
    for item in ("--read-only", "ALL", "no-new-privileges=true", "none"):
        assert item in bounded and item in plain


@pytest.mark.parametrize(
    "fields",
    [
        {"cpus": 0},
        {"memory_bytes": -1},
        {"pids_limit": True},
        {"nofile": 1.5},
        {"cpus": "4"},
    ],
)
def test_a_profile_value_is_a_positive_integer(fields):
    values = {"cpus": 4, "memory_bytes": 1024, "pids_limit": 8, "nofile": 64, **fields}
    with pytest.raises(WorkerFailure):
        mc.ResourceProfile(**values)


def test_a_launch_takes_only_a_registered_profile(tmp_path):
    with pytest.raises(WorkerFailure):
        launch(tmp_path, {"cpus": 4})


# -- the host's file -----------------------------------------------------------------------------
def profile_file(tmp_path, document=None, mode=0o600):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(PROFILE.record() if document is None else document))
    path.chmod(mode)
    return path


def test_no_named_file_means_no_profile():
    assert mc.load_host_profile({}) is None
    assert mc.load_host_profile({mc.RESOURCE_PROFILE_ENV: ""}) is None


def test_an_owner_only_v1_file_is_read(tmp_path):
    path = profile_file(tmp_path)
    assert mc.load_host_profile({mc.RESOURCE_PROFILE_ENV: str(path)}) == PROFILE


@pytest.mark.parametrize(
    "spoil",
    ["group_readable", "symlink", "missing", "unknown_key", "old_schema", "relative"],
)
def test_a_named_file_that_is_not_exactly_right_refuses_the_launch(tmp_path, spoil):
    path = profile_file(tmp_path)
    named = str(path)
    if spoil == "group_readable":
        path.chmod(0o640)
    elif spoil == "symlink":
        link = tmp_path / "link.json"
        link.symlink_to(path)
        named = str(link)
    elif spoil == "missing":
        named = str(tmp_path / "absent.json")
    elif spoil == "unknown_key":
        profile_file(tmp_path, {**PROFILE.record(), "gpus": 1})
    elif spoil == "old_schema":
        profile_file(tmp_path, {**PROFILE.record(), "schema": "v0"})
    elif spoil == "relative":
        named = "profile.json"
    with pytest.raises(WorkerFailure) as refused:
        mc.load_host_profile({mc.RESOURCE_PROFILE_ENV: named})
    assert refused.value.code is WorkerCode.POLICY


# -- the inspect gate ----------------------------------------------------------------------------
class Inspector:
    def __init__(self, value):
        self.value = value

    def json(self, _arguments):
        return self.value


def inspected(run, **host):
    labels = {"org.opencontainers.image.carbon.lane": mc.LANE}
    profile = run.resource_profile
    if profile is not None:
        labels[mc._PROFILE_LABEL] = profile.digest()
        host = {
            "NanoCpus": profile.cpus * 10**9,
            "Memory": profile.memory_bytes,
            "MemorySwap": profile.memory_bytes,
            "PidsLimit": profile.pids_limit,
            "Ulimits": [
                {"Name": "core", "Soft": 0, "Hard": 0},
                {"Name": "nofile", "Soft": profile.nofile, "Hard": profile.nofile},
            ],
            **host,
        }
    return {
        "Image": run.image_id,
        "Config": {"User": f"{WORKER_UID}:{WORKER_GID}", "Labels": labels, "Env": []},
        "HostConfig": {
            "ReadonlyRootfs": True,
            "NetworkMode": "none",
            "IpcMode": "private",
            "PidMode": "private",
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges=true"],
            **host,
        },
        "Mounts": [
            {
                "Destination": "/input",
                "Source": str(run.input_directory),
                "RW": False,
            },
            {"Destination": "/scratch", "Source": str(run.scratch_directory)},
        ],
    }


def test_the_gate_checks_the_profile_was_applied_exactly(tmp_path):
    run = launch(tmp_path, PROFILE)
    record = mc.inspect_isolation(Inspector(inspected(run)), run)
    assert record["resource_profile"] == PROFILE.digest()
    for spoiled in ({"Memory": 0}, {"PidsLimit": None}, {"NanoCpus": 2 * 10**9}):
        with pytest.raises(WorkerFailure):
            mc.inspect_isolation(Inspector(inspected(run, **spoiled)), run)


def test_the_gate_asserts_no_size_without_a_profile(tmp_path):
    run = launch(tmp_path)
    record = mc.inspect_isolation(Inspector(inspected(run)), run)
    assert "resource_profile" not in record


# -- each guard, disabled, turns its test red ------------------------------------------------------
def test_disabling_the_applied_profile_check_fails_its_test(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_profile_exactly", lambda *args: True)
    with pytest.raises(pytest.fail.Exception):
        test_the_gate_checks_the_profile_was_applied_exactly(tmp_path)


def test_disabling_the_owner_only_check_fails_its_test(tmp_path, monkeypatch):
    real = mc.load_host_profile

    def lenient(environ=None):
        try:
            return real(environ)
        except WorkerFailure:
            return None

    monkeypatch.setattr(mc, "load_host_profile", lenient)
    with pytest.raises(pytest.fail.Exception):
        test_a_named_file_that_is_not_exactly_right_refuses_the_launch(
            tmp_path, "group_readable"
        )
