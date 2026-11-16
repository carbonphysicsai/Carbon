"""The slots=N GPU bench (`scripts/dev/gpu_slot_bench.py`; Lead, Mon 16 Nov 2026): N builds at once on one GPU, each
slot run as `carbon.reconstruction.remote_gpu_build` runs it, with build seconds, peak device memory and state-digest
equality. No docker, no GPU: every process boundary is faked and every device UUID is synthetic.
"""

from __future__ import annotations

import ast
import hashlib
import threading
from types import SimpleNamespace

import accelerator_host
import pytest

from carbon.reconstruction import accelerators, remote_gpu_build
from scripts.dev import gpu_slot_bench as bench

UUID = "GPU-a1a1a1a1-0000-1111-2222-333333333333"


@pytest.fixture
def record(tmp_path):
    return accelerator_host.installed(
        tmp_path / "record",
        "hosted_instance",
        device_uuid=UUID,
        device_kind="NVIDIA A100-SXM4-80GB",
    )


def _env(argv):
    return dict(
        value.split("=", 1)
        for index, value in enumerate(argv)
        if index and argv[index - 1] == "--env"
    )


def test_the_slots_list_is_ascending_from_one_within_the_maximum():
    assert bench.parse_slots("1,2,4") == (1, 2, 4)
    assert bench.parse_slots("1,2,4,7") == (1, 2, 4, 7)
    for bad in ("2,4", "1,1", "1,4,2", "1,9"):
        with pytest.raises(ValueError):
            bench.parse_slots(bad)
    assert bench.split_cpusets("0-3,4-7") == ["0-3", "4-7"]
    with pytest.raises(ValueError):
        bench.split_cpusets("0-3,3-6")


def test_a_slot_runs_with_the_pinned_environment_its_cores_and_its_share(record):
    lane = bench.lane_for(record, 2, ["0-3", "4-7"], None, "capped")
    argv = bench.run_argv(
        "sha256:" + "c" * 64, record, remote_gpu_build.OpBinding(lane, 1), "n"
    )
    environment = _env(argv)
    assert argv[argv.index("--gpus") + 1] == f"driver=nvidia,device={UUID}"
    assert argv[argv.index("--cpuset-cpus") + 1] == "4-7"
    assert argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--entrypoint") + 1] == bench.WORKER_PYTHON
    assert argv[-3:] == ["sha256:" + "c" * 64, "-I", "-"]
    assert environment["XLA_FLAGS"] == " ".join(accelerators.GPU_DETERMINISM_XLA_FLAGS)
    assert environment["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert environment["CUDA_VISIBLE_DEVICES"] == UUID
    assert environment["XLA_PYTHON_CLIENT_ALLOCATOR"] == "platform"
    assert environment[remote_gpu_build.SLOT_FRACTION_ENV] == "0.45"
    one = bench.lane_for(record, 1, ["0-3"], None)
    single = _env(
        bench.run_argv(
            "sha256:" + "c" * 64, record, remote_gpu_build.OpBinding(one, 0), "n"
        )
    )
    assert "XLA_PYTHON_CLIENT_MEM_FRACTION" not in single
    assert single["XLA_PYTHON_CLIENT_ALLOCATOR"] == "platform"


def test_the_default_program_is_valid_python_that_writes_its_state():
    module = ast.parse(bench.DEFAULT_PROGRAM)
    assert "stdout.buffer.write" in bench.DEFAULT_PROGRAM and module.body


def _fake_runner(digests, seen):
    lock = threading.Lock()

    def runner(run, *, argv, program, docker_host):
        with lock:
            seen.append((run.slots, run.slot, program, argv))
        state = digests(run).encode()
        run.seconds, run.exit_code = 1.0 + run.slot, 0
        run.state_sha256 = "sha256:" + hashlib.sha256(state).hexdigest()
        run.state_bytes = len(state)
        return run

    return runner


def test_identical_states_at_every_n_is_the_identical_verdict(record):
    seen = []
    report = bench.bench(
        image_id="sha256:" + "c" * 64,
        record=record,
        slots_list=(1, 2, 4),
        cpusets=["0-1", "2-3", "4-5", "6-7"],
        docker_host=None,
        program=bench.DEFAULT_PROGRAM,
        memory="capped",
        runner=_fake_runner(lambda run: "state", seen),
        query=lambda: [1000, 2000],
        interval=0.01,
    )
    assert report["verdict"] == "IDENTICAL"
    assert [group["slots"] for group in report["groups"]] == [1, 2, 4]
    assert [len(group["runs"]) for group in report["groups"]] == [1, 2, 4]
    assert report["groups"][2]["seconds_max"] == 4.0
    assert report["groups"][1]["slot_memory"] == "capped"
    assert report["groups"][1]["memory_fraction"] == 0.45
    assert report["groups"][0]["baseline_device_memory_mib"] == 3000
    assert report["groups"][0]["peak_device_memory_mib"] == 3000
    assert report["groups"][0]["peak_process_memory_mib"] == 2000
    # the torch prelude rides only the N > 1 programs, as a slot lane runs them
    for slots, _, program, _ in seen:
        assert (remote_gpu_build.SLOT_PRELUDE in program) is (slots > 1)


def test_a_state_that_moves_with_n_or_a_failed_build_is_not_identical(record):
    report = bench.bench(
        image_id="sha256:" + "c" * 64,
        record=record,
        slots_list=(1, 2),
        cpusets=["0-1", "2-3"],
        docker_host=None,
        program=bench.DEFAULT_PROGRAM,
        runner=_fake_runner(lambda run: f"state-{run.slots}", []),
        query=list,
        interval=0.01,
    )
    assert report["verdict"] == "DIFFERS_OR_FAILED"
    assert report["groups"][1]["states_identical"] is True
    assert report["groups"][1]["identical_to_one_slot"] is False


def test_one_build_runs_docker_with_the_program_on_stdin(record):
    calls = []

    class Process:
        returncode = 0

        def communicate(self, data, timeout=None):
            calls.append(data)
            return b"\x00\x01", b""

    def popen(command, **kwargs):
        calls.append((command, kwargs["env"]))
        return Process()

    run = bench.run_one(
        bench.Run(1, 0),
        argv=["run", "x"],
        program="print(1)",
        docker_host="ssh://carbon@a100-1.example",
        popen=popen,
        clock=iter([0.0, 2.5]).__next__,
    )
    assert calls[0][0] == ["docker", "run", "x"]
    assert calls[0][1]["DOCKER_HOST"] == "ssh://carbon@a100-1.example"
    assert calls[1] == b"print(1)"
    assert run.seconds == 2.5 and run.exit_code == 0
    assert run.state_sha256 == "sha256:" + hashlib.sha256(b"\x00\x01").hexdigest()


def test_a_failed_build_keeps_its_error(record):
    class Process:
        returncode = 1

        def communicate(self, data, timeout=None):
            return b"", b"CUDA error: out of memory"

    run = bench.run_one(
        bench.Run(2, 1),
        argv=["run"],
        program="",
        docker_host=None,
        popen=lambda *a, **k: Process(),
        clock=iter([0.0, 1.0]).__next__,
    )
    assert run.state_sha256 is None and "out of memory" in run.error


def test_the_memory_probe_reads_only_the_bench_device(record, monkeypatch):
    def run(argv, **kwargs):
        assert argv[0] == "nvidia-smi"
        return SimpleNamespace(
            stdout=f"{UUID}, 1200\nGPU-other, 9000\n{UUID}, 800\n".encode()
        )

    monkeypatch.setattr(bench.subprocess, "run", run)
    assert bench._gpu_query(record, None)() == [1200, 800]


def test_a_slot_runs_as_the_worker_user_on_its_cores_and_refuses_an_option_like_image(
    record,
):
    lane = bench.lane_for(record, 2, ["0-3", "4-7"], None)
    binding = remote_gpu_build.OpBinding(lane, 0)
    argv = bench.run_argv("sha256:" + "c" * 64, record, binding, "n")
    assert argv[argv.index("--user") + 1] == "65532:65532"
    assert argv[argv.index("--cpus") + 1] == "4"
    assert "NVIDIA_DRIVER_CAPABILITIES=compute,utility" in argv
    for bad in ("--privileged", "-v/:/host", "sha256:xyz"):
        with pytest.raises(ValueError):
            bench.run_argv(bad, record, binding, "n")


def test_a_stuck_build_is_killed_and_recorded(record):
    killed = []

    class Process:
        returncode = -9

        def communicate(self, data=None, timeout=None):
            if data is not None:
                raise bench.subprocess.TimeoutExpired("docker", timeout)
            return b"", b""

        def kill(self):
            killed.append(True)

    run = bench.run_one(
        bench.Run(1, 0),
        argv=["run"],
        program="",
        docker_host=None,
        popen=lambda *a, **k: Process(),
        clock=iter([0.0, 1.0]).__next__,
        timeout=5,
    )
    assert killed and run.state_sha256 is None and "timed out" in run.error


def test_the_shared_mode_runs_the_program_and_env_unchanged(record):
    seen = []
    report = bench.bench(
        image_id="sha256:" + "c" * 64,
        record=record,
        slots_list=(1, 4),
        cpusets=["0-1", "2-3", "4-5", "6-7"],
        docker_host=None,
        program=bench.DEFAULT_PROGRAM,
        runner=_fake_runner(lambda run: "state", seen),
        query=lambda: [500],
        interval=0.01,
    )
    assert report["verdict"] == "IDENTICAL"
    assert report["groups"][1]["slot_memory"] == "shared"
    assert report["groups"][1]["memory_fraction"] is None
    for _, _, program, argv in seen:
        assert program == bench.DEFAULT_PROGRAM
        assert not any(
            value.startswith(remote_gpu_build.SLOT_FRACTION_ENV) for value in argv
        )
