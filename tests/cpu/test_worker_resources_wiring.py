"""OWNER-WORKER-RESOURCES-LARGE-MODELS-01: a served v7 launch gets 2/4/16.

Security-sensitive (the C-03 worker sandbox and the bounded miner lane);
evidence for review, not a security audit.

Claims tested:

1. A v6 (or unknown, or absent) allowlist version resolves today's values
   exactly: profile body and digest are unchanged, the create line and the
   export command are as before.
2. A v7 launch resolves 2 GiB output / 4 GiB scratch / 16 GiB memory, plus the
   envelope extras (4 CPUs, 2 GiB shm) in its profile body, the create line,
   the exporter's command line and the decoder's bound; PIDs, nofile and
   scratch inodes stay as containment.
3. The real effective-controls inspection accepts each profile's own container
   and refuses a container created at the other profile's controls.
4. The miner lane's profile v2 carries scratch and output bytes; v1 is read
   unchanged and keeps the named 2 GiB cap; a malformed v2 refuses.
5. The measurement controller, the G5 lane and an unregistered version refuse
   the larger resources.
"""

from __future__ import annotations

import json

import pytest
import scripted_docker
from test_c03_worker_contract import _image

from carbon.development_session import miner_container as mc
from carbon.development_session import research_carrier as rc
from carbon.reconstruction.worker import docker_runtime
from carbon.reconstruction.worker.model import (
    LARGE_MODEL_RESOURCES,
    NOFILE_LIMIT,
    OUTPUT_BYTES,
    PIDS_LIMIT,
    SCRATCH_INODES,
    DevelopmentWorkerProfile,
    WorkerCode,
    WorkerFailure,
    worker_resources_for,
    worker_resources_version,
)
from carbon.reconstruction.worker.protocol import decode_output_stream


@pytest.fixture
def large_profile_applied(monkeypatch):
    """Apply the larger-resources profile for a test, independent of the
    gate's value in code (on: OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01)."""
    from carbon.reconstruction.worker import model

    monkeypatch.setattr(model, "LARGE_MODEL_PROFILE_APPLIED", True)


V6 = "level4-allowlist-v6"
V7 = "level4-allowlist-v7"
#: The C-03 CPU profile's digest before this change (pinned elsewhere too).
C03_CPU_DIGEST = (
    "sha256:0d1168fb5bbffde24617c54df2cedfcb092d73b97f88fa8aae400f430869347f"
)
GIB = 1024**3


def _profile(version):
    return rc._worker_profile(None, rc.LIBRARY_BUILD_PROVENANCE, version)


def test_a_v6_launch_resolves_todays_values_exactly(large_profile_applied):
    for version in (V6, None, "level4-allowlist-v99"):
        assert worker_resources_version(version) is None
    today = _profile(None)
    assert today.digest == C03_CPU_DIGEST
    assert "worker_resources" not in today.body
    assert today.body["cpu"] == {"count": 2, "quota_cpus": 2, "cpuset_count": 2}
    assert today.body["memory"]["bytes"] == 4 * GIB
    assert today.body["scratch"]["bytes"] == 512 * 1024**2
    assert today.effective_output_bytes == OUTPUT_BYTES == 128 * 1024**2
    assert today.effective_shm_bytes == 8 * 1024**2
    assert today.effective_scratch_tmpfs_bytes + today.effective_shm_bytes == (
        512 * 1024**2
    )


def test_a_v7_launch_resolves_2_4_16_and_the_extras(large_profile_applied):
    version = worker_resources_version(V7)
    assert version == V7
    large = _profile(version)
    assert large.digest != C03_CPU_DIGEST
    assert (
        large.effective_output_bytes == 2 * GIB == LARGE_MODEL_RESOURCES["output_bytes"]
    )
    assert large.effective_scratch_tmpfs_bytes == 4 * GIB
    assert large.effective_memory_bytes == 16 * GIB
    assert large.effective_cpu_count == 4
    assert large.effective_shm_bytes == 2 * GIB
    body = large.body
    assert body["memory"]["bytes"] == 16 * GIB
    assert body["scratch"]["bytes"] == 4 * GIB
    assert body["output"]["bytes"] == 2 * GIB
    assert body["cpu"] == {"count": 4, "quota_cpus": 4, "cpuset_count": 4}
    assert body["worker_resources"] == {
        "allowlist_version": V7,
        "scratch_tmpfs_bytes": 4 * GIB,
        "shm_bytes": 2 * GIB,
    }
    # Containment kept.
    assert body["pids"] == PIDS_LIMIT == 256
    assert body["nofile_per_process"] == NOFILE_LIMIT == 1024
    assert body["scratch"]["inodes"] == SCRATCH_INODES == 8192
    assert body["input"]["bytes"] == 128 * 1024**2
    assert body["output"]["members"] == 1024
    assert worker_resources_for(V7) == LARGE_MODEL_RESOURCES


def _arguments(profile, tmp_path, cpuset=None):
    return docker_runtime.create_arguments(
        container_name="c03-test",
        image_id=_image().image_id,
        input_directory=tmp_path,
        cpuset=cpuset or ("0-3" if profile.large_model else "0-1"),
        launch_digest="sha256:" + "1" * 64,
        worker_profile=profile,
    )


def _flag(arguments, name):
    return arguments[arguments.index(name) + 1]


def test_the_create_line_follows_the_profile(tmp_path, large_profile_applied):
    today = _arguments(_profile(None), tmp_path)
    large = _arguments(_profile(V7), tmp_path)
    assert _flag(today, "--memory") == str(4 * GIB)
    assert _flag(today, "--cpus") == "2"
    assert _flag(today, "--shm-size") == str(8 * 1024**2)
    assert f"size={512 * 1024**2 - 8 * 1024**2}," in _flag(today, "--tmpfs")
    assert "OMP_NUM_THREADS=2" in today
    assert _flag(large, "--memory") == _flag(large, "--memory-swap") == str(16 * GIB)
    assert _flag(large, "--cpus") == "4"
    assert _flag(large, "--shm-size") == str(2 * GIB)
    assert f"size={4 * GIB}," in _flag(large, "--tmpfs")
    assert "nr_inodes=8192" in _flag(large, "--tmpfs")
    assert "OMP_NUM_THREADS=4" in large
    for same in ("--pids-limit", "--network"):
        assert _flag(large, same) == _flag(today, same)
    assert _flag(large, "--pids-limit") == "256"
    assert "nofile=1024:1024" in large


def _inspect(expected, created_with, tmp_path):
    cli = scripted_docker.ScriptedDocker(image=_image(), stage=tmp_path)
    cli.create_arguments = _arguments(created_with, tmp_path)
    cli.started = True
    return docker_runtime.inspect_effective_controls(
        cli=cli,
        container_name="c03-test",
        image_id=_image().image_id,
        input_directory=tmp_path,
        cpuset="0-3" if expected.large_model else "0-1",
        launch_digest="sha256:" + "1" * 64,
        worker_profile=expected,
    )


def test_inspection_accepts_each_profile_and_refuses_the_other(
    tmp_path, large_profile_applied
):
    today, large = _profile(None), _profile(V7)
    _inspect(today, today, tmp_path)
    _digest, evidence = _inspect(large, large, tmp_path)
    assert evidence["filesystem"]["scratch_bytes"] == 4 * GIB
    assert evidence["filesystem"]["shm_bytes"] == 2 * GIB
    assert evidence["daemon_host_config"]["memory"] == 16 * GIB
    assert evidence["daemon_host_config"]["nano_cpus"] == 4 * 10**9
    for expected, created in ((large, today), (today, large)):
        with pytest.raises(WorkerFailure) as refused:
            _inspect(expected, created, tmp_path)
        assert refused.value.code == WorkerCode.POLICY


def test_the_doctor_sizes_the_host_for_the_launch(large_profile_applied):
    class Cli:
        def __init__(self, ncpu, memory):
            self.info = {
                "NCPU": ncpu,
                "MemTotal": memory,
                "CgroupVersion": "2",
                "SecurityOptions": ["name=seccomp,profile=default"],
            }

        def json(self, arguments, **kwargs):
            if arguments[0] == "version":
                return {"Version": "x", "ApiVersion": "y"}
            return self.info

    small = docker_runtime.doctor(cli=Cli(2, 8 * GIB))
    assert small.eligible
    for ncpu, memory in ((2, 64 * GIB), (8, 16 * GIB)):
        assert not docker_runtime.doctor(
            cli=Cli(ncpu, memory), worker_profile=_profile(V7)
        ).eligible
    ready = docker_runtime.doctor(cli=Cli(8, 20 * GIB), worker_profile=_profile(V7))
    assert ready.eligible and ready.cpuset == "0,1,2,3"


def test_the_cpuset_follows_the_cpu_count(tmp_path, large_profile_applied):
    from carbon.reconstruction.host_execution import resolve_cpuset

    assert resolve_cpuset(logical_cpus=8) == "0,1"
    assert resolve_cpuset(logical_cpus=8, count=4) == "0,1,2,3"
    with pytest.raises(WorkerFailure):
        resolve_cpuset(logical_cpus=3, count=4)


def test_exporter_and_decoder_bound_by_the_launch_envelope(
    tmp_path, monkeypatch, large_profile_applied
):
    from carbon.reconstruction.worker import exporter

    assert exporter._output_bytes([]) == OUTPUT_BYTES
    assert exporter._output_bytes([str(2 * GIB)]) == 2 * GIB
    for bad in (["0"], ["-1"], ["1", "2"], ["x"], [str(1 << 41)], ["１２"]):
        assert exporter._output_bytes(bad) is None

    def stream(size):
        header = json.dumps({"schema": "carbon.c03.output-stream.v1"}).encode()
        member = json.dumps({"path": "a", "size": size}, sort_keys=True).encode()
        end = json.dumps(
            {"bytes": size, "end": True, "members": 1}, sort_keys=True
        ).encode()
        return header + b"\n" + member + b"\n" + b"x" * size + end + b"\n"

    big = OUTPUT_BYTES + 1
    source = tmp_path / "framed"
    source.write_bytes(stream(big))
    with pytest.raises(WorkerFailure):
        decode_output_stream(source, tmp_path / "default")
    decode_output_stream(source, tmp_path / "large", output_bytes=2 * GIB)
    assert (tmp_path / "large" / "a").stat().st_size == big


def test_other_lanes_refuse_the_larger_resources(tmp_path, large_profile_applied):
    from carbon.measurement_runtime.controller import (
        IsolatedBurgersMeasurementController as MeasurementController,
    )

    with pytest.raises(WorkerFailure) as refused:
        MeasurementController(
            state_root=tmp_path, image=_image(), worker_profile=_profile(V7)
        )
    assert refused.value.code == WorkerCode.UNSUPPORTED
    with pytest.raises(ValueError):
        rc._worker_profile(None, rc.G5_PROVENANCE, V7)
    with pytest.raises(ValueError):
        rc._worker_profile(None, rc.LIBRARY_BUILD_PROVENANCE, V6)
    with pytest.raises(WorkerFailure):
        DevelopmentWorkerProfile(
            "sha256:" + "a" * 64, "sha256:" + "b" * 64, worker_resources_version=V6
        )


def test_the_staged_worker_request_does_not_carry_large_resources(
    large_profile_applied,
):
    # The staged request has no field for them, so a v7 profile cannot be
    # rebuilt from one; the staging path refuses it by name (protocol.py).
    import inspect

    from carbon.reconstruction.worker import protocol

    assert "worker_resources_version" in inspect.getsource(protocol.stage_request)


def _write_profile(tmp_path, document):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(document))
    path.chmod(0o600)
    return path


V1 = {
    "schema": "carbon.miner-research.resource-profile.v1",
    "cpus": 4,
    "memory_bytes": 8 * GIB,
    "pids_limit": 512,
    "nofile": 8192,
}
V2 = {
    "schema": "carbon.miner-research.resource-profile.v2",
    "cpus": 4,
    "memory_bytes": 16 * GIB,
    "pids_limit": 512,
    "nofile": 8192,
    "scratch_bytes": 4 * GIB,
    "output_bytes": 2 * GIB,
}


def test_miner_profile_v1_is_unchanged_and_v2_carries_scratch_and_output(tmp_path):
    one = mc.load_host_profile(
        {mc.RESOURCE_PROFILE_ENV: str(_write_profile(tmp_path, V1))}
    )
    assert not one.v2 and one.record() == V1
    assert one.tmpfs_options == mc.SCRATCH_TMPFS_OPTIONS
    assert one.export_max_bytes == mc.SCRATCH_EXPORT_MAX_BYTES
    two = mc.load_host_profile(
        {mc.RESOURCE_PROFILE_ENV: str(_write_profile(tmp_path, V2))}
    )
    assert two.v2 and two.record() == V2 and two.digest() != one.digest()
    assert f"size={4 * GIB}," in two.tmpfs_options
    assert two.export_max_bytes == 2 * GIB + mc.SCRATCH_CAP_INODES * 4096 + 1024**2
    for broken in (
        {**V2, "scratch_bytes": 0},
        {k: v for k, v in V2.items() if k != "output_bytes"},
        {**V2, "extra": 1},
        {**V1, "scratch_bytes": 4 * GIB},
        {**V2, "schema": "carbon.miner-research.resource-profile.v3"},
    ):
        with pytest.raises(WorkerFailure):
            mc.load_host_profile(
                {mc.RESOURCE_PROFILE_ENV: str(_write_profile(tmp_path, broken))}
            )


def test_the_miner_lane_mounts_and_checks_its_profiles_scratch(tmp_path):
    for document, size in ((V1, mc.SCRATCH_CAP_BYTES), (V2, 4 * GIB)):
        profile = mc.load_host_profile(
            {mc.RESOURCE_PROFILE_ENV: str(_write_profile(tmp_path, document))}
        )
        launch = mc.MinerResearchLaunch(
            "miner-test",
            "sha256:" + "2" * 64,
            "sha256:" + "3" * 64,
            tmp_path / "input",
            tmp_path / "scratch",
            resource_profile=profile,
        )
        arguments = mc.create_arguments(launch)
        tmpfs = arguments[arguments.index("--tmpfs") + 1]
        assert tmpfs == f"/scratch:{mc.scratch_tmpfs_options(size)}"
        assert _flag(arguments, "--memory") == str(document["memory_bytes"])


def test_battery_graph_intake_follows_the_versions_allowlist():
    from carbon.battery import direct_graph
    from carbon.level4 import intake

    # Registered versions on v1 and v6 keep the owner's bounds; 2.1 serves v7.
    for version in ("1.0", "2.0"):
        assert (
            direct_graph.submission_bytes(version) == intake.BOUNDS["submission_bytes"]
        )
    assert (
        direct_graph.submission_bytes("2.1")
        == intake.CONTAINMENT_BOUNDS["submission_bytes"]
    )
    with pytest.raises(Exception):
        direct_graph.submission_bytes("9.9")


def test_exactly_the_v7_versions_resolve_to_the_larger_resources():
    # The gate is on (OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01): the
    # profile applies to an allowlist version in LARGE_MODEL_ALLOWLIST_VERSIONS
    # and only there. Every version serving v7 resolves to it; every version
    # on an earlier allowlist keeps today's values.
    from carbon.challenge_kit import served_versions as sv
    from carbon.challenge_kit import version_registry as vr
    from carbon.level4.allowlist import Allowlist

    large = []
    for challenge_id, version in sorted(vr.VERSIONS):
        for raw in (
            sv.material_allowlist_bytes(challenge_id, version),
            sv.graph_allowlist_bytes(challenge_id, version),
        ):
            served = Allowlist(raw).version
            expected = V7 if served == V7 else None
            assert worker_resources_version(served) == expected, (
                challenge_id,
                version,
                served,
            )
        if worker_resources_version(served) is not None:
            large.append((challenge_id, version))
    assert set(large) == set(sv.V7)
    assert large and len(large) < len(vr.VERSIONS)


def test_the_gate_is_on_in_code_for_v7_only(tmp_path):
    from carbon.reconstruction.worker import model

    assert model.LARGE_MODEL_PROFILE_APPLIED is True
    assert worker_resources_version(V7) == V7
    assert worker_resources_version(V6) is None
    assert worker_resources_for(V7) != worker_resources_for(V6)
    DevelopmentWorkerProfile(
        "sha256:" + "a" * 64, "sha256:" + "b" * 64, worker_resources_version=V7
    )
    rc._worker_profile(None, rc.LIBRARY_BUILD_PROVENANCE, V7)
    with pytest.raises(WorkerFailure):
        DevelopmentWorkerProfile(
            "sha256:" + "a" * 64, "sha256:" + "b" * 64, worker_resources_version=V6
        )
    with pytest.raises(ValueError):
        rc._worker_profile(None, rc.LIBRARY_BUILD_PROVENANCE, V6)
    # Today's C-03 CPU profile keeps its digest.
    assert _profile(None).digest == C03_CPU_DIGEST
