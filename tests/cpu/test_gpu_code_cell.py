"""The GPU code cell, kept error output, and GPU shown (RSURF-D19 to D21).

OWNER-MINER-RESEARCH-SURFACE-04 (owner, 2026-10-03):
- "Yes, GPU code cell (Recommended)": the same isolation, network and file
  rules, with the GPU set up attached, chosen per run;
- "Keep both, capped (Recommended)": the last 64 KB of stdout and of stderr,
  for failed runs too;
- "where's the GPU option?": the page must not hide where a campaign runs.

This touches the sandbox. These tests are engineering evidence, not a
security audit (AGENTS.md section 13): a dedicated security review is
required before any use beyond DEVELOPMENT.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carbon.development_session import gpu_code_cell, research_carrier
from carbon.development_session.gpu_code_cell import GpuLane, refusal
from carbon.development_session.miner_container import (
    GPU_CAPABILITIES,
    MinerResearchLaunch,
    create_arguments,
    inspect_isolation,
)
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

UUID = "GPU-0123abcd-4567-89ef-0123-456789abcdef"
DIGEST = "sha256:" + "a" * 64


# ---- Kept output: the last 64 KiB of stdout and of stderr (RSURF-D21).


def run_kept(tmp_path, program, timeout=30):
    operation = tmp_path / "operation"
    operation.mkdir()
    cli = SimpleNamespace(executable=sys.executable)
    error = None
    try:
        research_carrier.stream_kept(cli, ["-c", program], operation, timeout=timeout)
    except WorkerFailure as failure:
        error = failure
    return (
        (operation / "stdout.txt").read_bytes(),
        (operation / "stderr.txt").read_bytes(),
        error,
    )


def test_a_successful_run_keeps_the_last_64_kib_of_each_stream(tmp_path):
    stdout, stderr, error = run_kept(
        tmp_path,
        "import sys\n"
        "sys.stdout.write('a' * 200000 + 'END-OUT')\n"
        "sys.stderr.write('b' * 100000 + 'END-ERR')\n",
    )
    assert error is None
    assert len(stdout) == research_carrier.KEPT_BYTES and stdout.endswith(b"END-OUT")
    assert len(stderr) == research_carrier.KEPT_BYTES and stderr.endswith(b"END-ERR")


def test_a_failed_run_keeps_both_and_is_classified_as_before(tmp_path):
    stdout, stderr, error = run_kept(
        tmp_path,
        "import sys\nprint('before the crash')\nraise KeyError('capacity_fade')\n",
    )
    assert stdout == b"before the crash\n"
    assert b"KeyError: 'capacity_fade'" in stderr
    assert error.code is WorkerCode.RUNTIME
    # The diagnostic the miner-failure classifier reads is unchanged.
    assert error.private_diagnostic.startswith(b"exit=1\nstderr:\nTraceback")


def test_a_large_stderr_no_longer_fails_a_run(tmp_path):
    _, stderr, error = run_kept(
        tmp_path, "import sys\nsys.stderr.write('x' * (2 * 1024 * 1024))\n"
    )
    assert error is None and len(stderr) == research_carrier.KEPT_BYTES


def test_a_timed_out_run_keeps_what_it_printed(tmp_path):
    stdout, _, error = run_kept(
        tmp_path,
        "import time\nprint('started', flush=True)\ntime.sleep(30)\n",
        timeout=2,
    )
    assert stdout == b"started\n"
    assert error.private_diagnostic == b"stream command timed out"


def test_no_controller_secret_reaches_the_command(tmp_path, monkeypatch):
    monkeypatch.setenv("CARBON_PROVIDER_API_KEY", "secret-provider-key")
    monkeypatch.setenv("BT_WALLET_HOTKEY", "secret-hotkey")
    stdout, _, error = run_kept(
        tmp_path, "import os, json\nprint(json.dumps(sorted(os.environ)))\n"
    )
    assert error is None
    names = json.loads(stdout)
    assert "CARBON_PROVIDER_API_KEY" not in names and "BT_WALLET_HOTKEY" not in names
    assert set(names) <= {
        "PATH",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
        "LC_CTYPE",
    }


# ---- Isolation: unchanged, except the one GPU device (RSURF-D20).


def launch(tmp_path, gpu=None):
    for name in ("input", "scratch"):
        (tmp_path / name).mkdir(exist_ok=True)
    return MinerResearchLaunch(
        "carbon-d4-" + "b" * 24,
        DIGEST,
        DIGEST,
        tmp_path / "input",
        tmp_path / "scratch",
        gpu_device=gpu,
    )


GPU_FLAGS = [
    "--runtime",
    "nvidia",
    "--gpus",
    f"device={UUID}",
    "--label",
    f"carbon.accelerator.device={UUID}",
    "--env",
    f"NVIDIA_VISIBLE_DEVICES={UUID}",
    "--env",
    f"NVIDIA_DRIVER_CAPABILITIES={GPU_CAPABILITIES}",
]


def test_the_gpu_container_adds_only_the_device(tmp_path):
    cpu = create_arguments(launch(tmp_path))
    gpu = create_arguments(launch(tmp_path, UUID))
    # Exactly the CPU container's arguments, with the device inserted before
    # the image: no network, mount, capability or limit changes.
    assert gpu == cpu[:-1] + GPU_FLAGS + cpu[-1:]
    for flag in ("--network", "none", "--read-only", "--cap-drop", "ALL"):
        assert flag in gpu
    assert "--gpus" not in cpu and "--runtime" not in cpu
    allowed = {
        "HOME",
        "TMPDIR",
        "XDG_CACHE_HOME",
        "JAX_COMPILATION_CACHE_DIR",
        "XLA_PYTHON_CLIENT_PREALLOCATE",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NVIDIA_VISIBLE_DEVICES",
        "NVIDIA_DRIVER_CAPABILITIES",
    }
    envs = {gpu[i + 1].split("=", 1)[0] for i, a in enumerate(gpu) if a == "--env"}
    assert envs <= allowed
    mounts = [gpu[i + 1] for i, a in enumerate(gpu) if a == "--mount"]
    assert len(mounts) == 2 and all(
        "target=/input" in m or "target=/scratch" in m for m in mounts
    )


def test_only_a_device_uuid_is_accepted(tmp_path):
    for bad in ("all", "0", "GPU-0;--privileged", "device=GPU-1234"):
        with pytest.raises(WorkerFailure):
            launch(tmp_path, bad)


def inspected(tmp_path, gpu, **changes):
    host = {
        "ReadonlyRootfs": True,
        "Privileged": False,
        "NetworkMode": "none",
        "IpcMode": "private",
        "PidMode": "",
        "CapAdd": None,
        "CapDrop": ["ALL"],
        "Devices": None,
        "DeviceRequests": None,
        "PortBindings": None,
        "PublishAllPorts": False,
        "SecurityOpt": ["no-new-privileges=true"],
        "Runtime": "runc",
    }
    env = ["HOME=/scratch/home"]
    labels = {
        "org.opencontainers.image.carbon.lane": "carbon.miner-research.unlimited.v1"
    }
    if gpu:
        host.update(
            Runtime="nvidia",
            DeviceRequests=[
                {
                    "Driver": "",
                    "Count": 0,
                    "DeviceIDs": [UUID],
                    "Capabilities": [["gpu"]],
                }
            ],
        )
        env += [
            f"NVIDIA_VISIBLE_DEVICES={UUID}",
            f"NVIDIA_DRIVER_CAPABILITIES={GPU_CAPABILITIES}",
        ]
        labels["carbon.accelerator.device"] = UUID
    run = launch(tmp_path, UUID if gpu else None)
    value = {
        "Image": DIGEST,
        "HostConfig": host,
        "Config": {"User": "65532:65532", "Labels": labels, "Env": env},
        "Mounts": [
            {"Destination": "/input", "Source": str(run.input_directory), "RW": False},
            {
                "Destination": "/scratch",
                "Source": str(run.scratch_directory),
                "RW": True,
            },
        ],
    }
    for change in changes.values():
        change(value)
    cli = SimpleNamespace(json=lambda arguments, **_: value)
    return inspect_isolation(cli, run)


def test_isolation_is_checked_with_the_gpu_attached(tmp_path):
    assert inspected(tmp_path, False)["gpu_device"] is None
    assert inspected(tmp_path, True)["gpu_device"] == UUID


@pytest.mark.parametrize(
    "name,change",
    [
        ("network", lambda v: v["HostConfig"].update(NetworkMode="bridge")),
        ("writable root", lambda v: v["HostConfig"].update(ReadonlyRootfs=False)),
        ("capability", lambda v: v["HostConfig"].update(CapAdd=["SYS_ADMIN"])),
        ("privileged", lambda v: v["HostConfig"].update(Privileged=True)),
        (
            "raw device",
            lambda v: v["HostConfig"].update(Devices=[{"PathOnHost": "/dev/mem"}]),
        ),
        (
            "all gpus",
            lambda v: v["HostConfig"]["DeviceRequests"][0].update(
                Count=-1, DeviceIDs=None
            ),
        ),
        (
            "other gpu",
            lambda v: v["HostConfig"]["DeviceRequests"][0].update(
                DeviceIDs=[UUID, "GPU-ffffffff-0000"]
            ),
        ),
        (
            "second request",
            lambda v: v["HostConfig"]["DeviceRequests"].append(
                {"DeviceIDs": ["GPU-1"]}
            ),
        ),
        ("runtime", lambda v: v["HostConfig"].update(Runtime="runc")),
        (
            "visible devices",
            lambda v: v["Config"].update(Env=["NVIDIA_VISIBLE_DEVICES=all"]),
        ),
        (
            "extra mount",
            lambda v: v["Mounts"].append({"Destination": "/home", "Source": "/home"}),
        ),
        ("port", lambda v: v["HostConfig"].update(PortBindings={"22/tcp": [{}]})),
    ],
)
def test_anything_beyond_the_one_gpu_is_refused(tmp_path, name, change):
    with pytest.raises(WorkerFailure):
        inspected(tmp_path, True, change=change)


def test_a_cpu_run_is_checked_exactly_as_before(tmp_path):
    with pytest.raises(WorkerFailure):
        inspected(
            tmp_path,
            False,
            change=lambda v: v["HostConfig"].update(
                DeviceRequests=[{"DeviceIDs": [UUID], "Capabilities": [["gpu"]]}]
            ),
        )


def test_the_carrier_admits_a_gpu_only_for_the_pinned_gpu_worker():
    from carbon.development_session.research_carrier import MINER_GPU, run_script

    with pytest.raises(ValueError, match="pinned GPU worker"):
        run_script(
            None,
            owner="alice",
            identity="t",
            source="print(1)",
            files={},
            image=SimpleNamespace(image_id=DIGEST),
            accelerator=MINER_GPU,
        )


# ---- The choice: offered only with a lane, refused before dispatch.


def lane(remote=None):
    return GpuLane(image=SimpleNamespace(image_id=DIGEST), remote=remote)


def test_a_device_choice_that_cannot_run_is_refused_before_dispatch():
    from carbon.development_session.research_tools import (
        TASK_CORRECTIONS,
        TaskContractMismatch,
    )

    remote = lane(
        SimpleNamespace(transport=SimpleNamespace(name="ssh-docker", sandboxed=True))
    )

    def container(opted_in):
        transport = SimpleNamespace(
            name="ssh-container", sandboxed=False, unsandboxed_code_cell=opted_in
        )
        return lane(SimpleNamespace(transport=transport))

    # A remote route with no sandbox runs agent-written code only on the
    # miner's own opt-in; a route that does not say it is sandboxed is not.
    unstated = lane(SimpleNamespace(transport=SimpleNamespace(name="ssh-docker")))
    opt_in = "remote_gpu_unsandboxed_opt_in_required"
    cases = [
        ("run_python", {"device": "gpu", "seconds": 600}, container(False), opt_in),
        ("run_python", {"device": "gpu", "seconds": 600}, container(True), None),
        ("run_python", {"device": "gpu", "seconds": 600}, unstated, opt_in),
        ("run_python", {"device": "tpu"}, lane(), "device_choice_invalid"),
        ("run_python", {"device": "gpu"}, None, "gpu_lane_not_configured"),
        ("run_julia", {"device": "gpu"}, lane(), "julia_gpu_unavailable"),
        ("run_python", {"device": "gpu"}, remote, "remote_gpu_seconds_required"),
        (
            "run_python",
            {"device": "gpu", "seconds": 10},
            remote,
            "remote_gpu_seconds_required",
        ),
        ("run_python", {"device": "gpu", "seconds": 600}, remote, None),
        ("run_python", {"device": "gpu"}, lane(), None),
        ("run_python", {"device": "cpu"}, None, None),
        ("run_python", {}, None, None),
    ]
    for action, arguments, choice, expected in cases:
        assert refusal(action, arguments, choice) == expected, (action, arguments)
        if expected is not None:
            # Each is a registered correction on a registered field.
            assert expected in TASK_CORRECTIONS
            TaskContractMismatch(expected, "arguments_json.device")
    TaskContractMismatch("remote_gpu_seconds_required", "arguments_json.seconds")


def test_both_doors_take_the_same_device_argument():
    from carbon.development_session.research_tasks import workspace_fields

    for action in ("run_python", "run_julia"):
        assert "device" in workspace_fields(action)[1]
    source = (
        Path(__file__).resolve().parents[2]
        / "scripts/dev/miner_launchpad/research_tools.js"
    ).read_text()
    # The page sends it inside the same tool arguments an agent sends.
    assert 'if (device.value === "gpu") args.device = "gpu";' in source
    assert "sys.stderr = sys.stdout" not in source


def test_the_lane_is_discovered_the_same_way_by_both_doors():
    import asyncio

    from carbon.miner_mcp.standard_server import GUIDANCE_URI, _create_server
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner
    from scripts.dev.miner_launchpad.tool_door import ToolDoor
    from scripts.dev.miner_launchpad.tool_fixture import FixtureTools, fixture_adapter

    runner = FixtureRunner()
    adapter = fixture_adapter(FixtureTools(runner), runner.principal)
    assert ToolDoor(adapter).describe()["gpu_lane"] == adapter.gpu_lane
    assert adapter.gpu_lane["kind"] == "local_gpu"
    guidance = asyncio.run(_create_server(adapter).read_resource(GUIDANCE_URI))
    text = "".join(getattr(part, "content", "") for part in guidance)
    assert "device=gpu" in text


def test_the_executor_refuses_a_gpu_run_without_a_lane(tmp_path):
    from test_cw1_research_tasks import compose

    _, _, executor = compose(tmp_path)
    assert executor.gpu is None
    from carbon.development_session.profile import canonical

    spec = SimpleNamespace(
        action="run_python",
        arguments_json=canonical(
            {
                "device": "gpu",
                "expected_effect": "e",
                "files": [],
                "hypothesis": "h",
                "source": "print(1)",
            }
        ).decode(),
    )
    with pytest.raises(ValueError, match="no GPU lane"):
        executor._workspace_action(spec, "rtsk_" + "0" * 64)


# ---- A GPU run, local and remote, records its device.


def executor_with(tmp_path, gpu):
    from test_cw1_research_tasks import compose

    _, _, executor = compose(tmp_path)
    executor.gpu = gpu
    return executor


def test_a_local_gpu_run_records_its_device(tmp_path, monkeypatch):
    calls = []
    device = SimpleNamespace(device_kind="NVIDIA L4", digest="sha256:" + "d" * 64)
    monkeypatch.setattr(research_carrier, "_gpu_device", lambda: device)

    def fake_run(ledger, **kwargs):
        calls.append(kwargs)
        operation = ledger.root / "operation-x"
        (operation / "snapshot").mkdir(parents=True)
        (operation / "snapshot" / "speed.json").write_bytes(b"{}")
        from carbon.development_session.profile import digest

        return {"operation": "operation-x", "files": {"speed.json": digest(b"{}")}}

    monkeypatch.setattr(research_carrier, "run_script", fake_run)
    executor = executor_with(tmp_path, lane())
    result = gpu_code_cell.run(
        executor,
        identity="rtsk_" + "1" * 64,
        args={"source": "print(1)", "files": [], "device": "gpu"},
        files={},
    )
    assert calls[0]["accelerator"] == research_carrier.MINER_GPU
    assert calls[0]["image"].image_id == DIGEST
    assert result["device"]["kind"] == "local_gpu"
    assert result["device"]["device_kind"] == "NVIDIA L4"
    assert result["workspace_exports"] == ["1" * 20 + "-speed.json"]

    def failing(ledger, **kwargs):
        raise research_carrier.MinerProgramFailure(
            {
                "schema": research_carrier.MINER_FAILURE_SCHEMA,
                "failure_code": WorkerCode.RUNTIME.value,
                "observation": "NONZERO_EXIT",
                "operation": "operation-y",
            }
        )

    monkeypatch.setattr(research_carrier, "run_script", failing)
    failed = gpu_code_cell.run(
        executor,
        identity="rtsk_" + "2" * 64,
        args={"source": "x", "files": [], "device": "gpu"},
        files={},
    )
    assert failed["outcome"] == "MINER_PROGRAM_FAILED"
    assert failed["device"]["kind"] == "local_gpu"


class FakeRemote:
    """The miner's remote route, as RemoteRunner is called: it records what
    it was given and returns what RemoteRunner returns. The job server's own
    result is not among the output files: RemoteJob takes it out and the
    runner records it under remote.job (the 2026-10-03 review found an
    earlier double that kept it in the files, which hid every remote run
    reading as failed)."""

    transport = SimpleNamespace(name="ssh-docker", sandboxed=True)

    def __init__(self, returncode=0):
        self.returncode, self.calls = returncode, []

    def __call__(self, ledger, **kwargs):
        from carbon.development_session.profile import digest

        self.calls.append(kwargs)
        operation = ledger.root / "operation-remote"
        snapshot = operation / "snapshot"
        snapshot.mkdir(parents=True)
        output = {
            "plot.png": b"\x89PNG\r\n\x1a\nfake",
            "carbon-stdout.txt": b"printed on the GPU\n",
            "carbon-job-stderr.txt": b"a warning\n",
        }
        for name, body in output.items():
            (snapshot / name).write_bytes(body)
        job = {
            "schema": "carbon.compute.rented-job.v1",
            "state": "DONE" if self.returncode == 0 else "FAILED",
            "returncode": self.returncode,
            "elapsed_s": 0.1,
            "timed_out": False,
        }
        return {
            "operation": "operation-remote",
            "files": {n: digest(b) for n, b in output.items()},
            "remote": {"transport": "ssh-docker", "cleanup": "confirmed", "job": job},
        }


def test_a_remote_gpu_run_uses_the_route_and_keeps_its_output(tmp_path):
    remote = FakeRemote()
    executor = executor_with(tmp_path, lane(remote))
    result = gpu_code_cell.run(
        executor,
        identity="rtsk_" + "3" * 64,
        args={"source": "print('hi')", "files": [], "device": "gpu", "seconds": 600},
        files={"data.json": b"{}"},
    )
    sent = remote.calls[0]
    # The program goes as Carbon's fixed wrapper plus the miner's source and
    # staged files: nothing else, and no key.
    assert sent["source"] == gpu_code_cell.WRAPPER
    assert set(sent["files"]) == {"data.json", gpu_code_cell.WRAPPED}
    assert sent["files"][gpu_code_cell.WRAPPED] == b"print('hi')"
    assert sent["seconds"] == 600 and sent["provenance"] == "MINER_SELF_REPORTED"
    operation = executor.ledger.root / "operation-remote"
    assert (operation / "stdout.txt").read_bytes() == b"printed on the GPU\n"
    assert (operation / "stderr.txt").read_bytes() == b"a warning\n"
    assert result["workspace_exports"] == ["3" * 20 + "-plot.png"]
    assert result["device"]["kind"] == "remote_gpu"
    assert result["device"]["transport"] == "ssh-docker"
    failed = gpu_code_cell.run(
        executor_with(tmp_path / "again", lane(FakeRemote(returncode=1))),
        identity="rtsk_" + "4" * 64,
        args={"source": "x", "files": [], "device": "gpu", "seconds": 600},
        files={},
    )
    assert failed["outcome"] == "MINER_PROGRAM_FAILED"
    assert failed["worker"]["failure_code"] == "RUNTIME"


def real_remote_lane(tmp_path):
    """The real RemoteRunner, RemoteJob and job server: only SSH is faked.
    test_remote_runner's machine runs the job server in a thread and answers
    the start script as a real ssh-docker machine does."""
    from test_remote_runner import FakeRemote as Machine
    from test_remote_runner import fast_job, gpu_worker, worker

    from carbon.compute.remote_runner import RemoteRunner
    from carbon.compute.remote_transport import SSHDocker

    (tmp_path / "machine").mkdir(mode=0o700, parents=True)
    machine = Machine(tmp_path / "machine")
    image = gpu_worker()
    runner = RemoteRunner(
        transport=SSHDocker(machine), worker=worker(image), job=fast_job
    )
    return GpuLane(image=image, remote=runner), machine


def test_a_real_remote_run_reads_the_job_result_where_the_runner_records_it(
    tmp_path, monkeypatch
):
    """Every remote GPU run used to read as MINER_PROGRAM_FAILED: RemoteJob
    takes the job server's result out of the output, and the code cell
    looked for it among the output files. Through the real runner, a program
    that succeeds is a success, and one that exits nonzero is the miner's."""
    from test_remote_runner import campaign_ledger

    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    gpu, machine = real_remote_lane(tmp_path)
    executor = executor_with(tmp_path / "campaign", gpu)
    # A frozen product campaign and its owner, as a real remote run reserves.
    executor.ledger, executor.owner = campaign_ledger(tmp_path / "frozen"), "miner"
    source = (
        "from pathlib import Path\n"
        "print('ran on the remote GPU')\n"
        "(Path('..').resolve() / 'output' / 'speed.json').write_text('{}')\n"
    )
    result = gpu_code_cell.run(
        executor,
        identity="rtsk_" + "5" * 64,
        args={"source": source, "files": [], "device": "gpu", "seconds": 60},
        files={},
    )
    assert "outcome" not in result, result
    assert result["worker"]["remote"]["job"]["returncode"] == 0
    assert result["workspace_exports"] == ["5" * 20 + "-speed.json"]
    operation = executor.ledger.root / result["worker"]["operation"]
    assert (operation / "stdout.txt").read_bytes() == b"ran on the remote GPU\n"
    assert result["device"]["isolation"] == gpu_code_cell.REMOTE_SANDBOX
    failed = gpu_code_cell.run(
        executor,
        identity="rtsk_" + "6" * 64,
        args={
            "source": "raise SystemExit(3)\n",
            "files": [],
            "device": "gpu",
            "seconds": 60,
        },
        files={},
    )
    assert failed["outcome"] == "MINER_PROGRAM_FAILED"
    assert failed["worker"]["failure_code"] == "RUNTIME"
    # Each run's container was removed.
    assert len(machine.started) == 2 and machine.removed == machine.started


def test_an_unsandboxed_remote_code_cell_needs_the_miners_own_opt_in():
    """ssh-container runs a code cell inside the miner's own container with
    no sandbox and its network: only when the miner says so in their runner
    profile, never from an argument an agent could set."""
    from carbon.compute.remote_transport import (
        RemoteMachine,
        SSHContainer,
        SSHDocker,
        transport_for,
    )

    plain = {"transport": "ssh-container", "destination": "me@pod"}
    opted = {**plain, "unsandboxed_code_cell": True}
    assert RemoteMachine.from_document(plain).unsandboxed_code_cell is False
    assert RemoteMachine.from_document(opted).document() == opted
    for refused in (
        {**plain, "unsandboxed_code_cell": False},
        {**plain, "unsandboxed_code_cell": "true"},
        {
            "transport": "ssh-docker",
            "destination": "me@pod",
            "unsandboxed_code_cell": True,
        },
    ):
        with pytest.raises(ValueError, match="unsandboxed_code_cell"):
            RemoteMachine.from_document(refused)

    def fake_ssh(destination, port=None):
        return SimpleNamespace(destination=destination)

    container = transport_for(RemoteMachine.from_document(opted), ssh=fake_ssh)
    assert type(container) is SSHContainer and container.unsandboxed_code_cell
    assert not container.sandboxed
    docker = transport_for(
        RemoteMachine.from_document(
            {"transport": "ssh-docker", "destination": "me@pod"}
        ),
        ssh=fake_ssh,
    )
    assert type(docker) is SSHDocker and docker.sandboxed
    assert not docker.unsandboxed_code_cell

    # What the miner and their agent are told, per lane.
    def remote(transport):
        return lane(SimpleNamespace(transport=transport))

    assert remote(docker).describe()["isolation"] == gpu_code_cell.REMOTE_SANDBOX
    assert remote(container).describe()["isolation"] == gpu_code_cell.REMOTE_NO_SANDBOX
    assert lane().describe()["isolation"] == gpu_code_cell.LOCAL_ISOLATION
    args = {"device": "gpu", "seconds": 600}
    assert refusal("run_python", args, remote(container)) is None
    refused_container = SSHContainer(fake_ssh("me@pod"))
    assert (
        refusal("run_python", args, remote(refused_container))
        == "remote_gpu_unsandboxed_opt_in_required"
    )


def test_the_remote_wrapper_runs_the_program_and_keeps_its_stdout(tmp_path):
    import subprocess

    work, output = tmp_path / "workspace", tmp_path / "output"
    work.mkdir()
    output.mkdir()
    (work / gpu_code_cell.WRAPPED).write_text("print('x' * 70000 + 'END')\n")
    (tmp_path / "program.py").write_text(gpu_code_cell.WRAPPER)
    done = subprocess.run(
        [sys.executable, "-I", str(tmp_path / "program.py")], cwd=work, check=False
    )
    assert done.returncode == 0
    kept = (output / gpu_code_cell.STDOUT_EXPORT).read_bytes()
    assert len(kept) == 64 * 1024 and kept.endswith(b"END\n")


# ---- GPU shown (RSURF-D19).


def test_the_campaign_record_says_where_it_runs():
    from scripts.dev.miner_launchpad.projection import _compute

    assert _compute({}) == "local-isolated-cpu"
    assert _compute({"gpu_research": [{}]}) == "local-isolated-gpu"
    assert (
        _compute({"gpu_research": [{}], "remote_gpu": [{"transport": "ssh-docker"}]})
        == "remote-gpu:ssh-docker"
    )


def test_the_toolbox_shows_where_practice_and_the_code_cell_run():
    from scripts.dev.miner_launchpad import toolbox

    battery = {"id": "battery-fastcharge-ageing-development-v1", "version": "1.0"}
    lanes = {
        "gpu": {"availability": "unavailable", "reason": "no_gpu_runtime_declared"},
        "remote_gpu": {"availability": "configured"},
    }
    remote = toolbox.campaign_compute(
        "remote-gpu:ssh-docker", {"transport": "ssh-docker", "destination": "me@pod"}
    )
    assert remote["label"] == "your remote GPU (ssh-docker, me@pod)"
    tb = toolbox.build(battery, lanes=lanes, compute=remote)
    runs = {r["id"]: r["runs_on"] for r in tb["runtimes"]}
    assert runs["jax"] == remote["label"]
    assert runs["pytorch"].startswith("not served on this campaign's GPU")
    assert tb["where"]["code_cell"]["gpu"] == remote["label"]
    assert (
        "jax-cpu" in tb["where"]["validator"]
        and "own research only" in tb["where"]["validator"]
    )
    cpu = toolbox.build(
        battery,
        lanes={"gpu": lanes["gpu"], "remote_gpu": lanes["gpu"]},
        compute=toolbox.campaign_compute("local-isolated-cpu"),
    )
    assert cpu["where"]["code_cell"]["gpu"] is None
    assert cpu["where"]["set_up_gpu"] == "#setup/compute"
    assert cpu["where"]["lanes"]["gpu"]["reason"] == "no_gpu_runtime_declared"
    assert {r["runs_on"] for r in cpu["runtimes"]} == {
        cpu["where"]["practice"]["label"]
    }


def test_every_practice_run_says_cpu_or_gpu():
    from scripts.dev.miner_launchpad.campaign_view import ran_on

    assert ran_on({"kind": "ISOLATED_CARRIER"}) == "CPU (isolated sandbox)"
    assert ran_on({"kind": "ISOLATED_CARRIER_GPU", "device_kind": "NVIDIA L4"}) == (
        "GPU (this machine) · NVIDIA L4"
    )
    assert ran_on({"kind": "REMOTE_GPU", "transport": "ssh-container"}) == (
        "GPU (your remote setup) · ssh-container"
    )
    assert ran_on({"kind": "SOMETHING_ELSE"}) is None


def test_the_demo_shows_a_gpu_campaign_a_gpu_run_and_a_failed_run():
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner
    from scripts.dev.miner_launchpad.tool_fixture import FAILED_TASK, GPU_TASK

    runner = FixtureRunner()
    doc = runner.view_document()
    assert doc["toolbox"]["where"]["practice"]["kind"] == "local_gpu"
    assert all(row["ran_on"].startswith("GPU") for row in doc["experiments"]["rows"])
    gpu = runner.run_output_admitted(None, {"task": GPU_TASK})
    assert gpu["ran_on"]["kind"] == "local_gpu"
    failed = runner.run_output_admitted(None, {"task": FAILED_TASK})
    assert failed["outcome"] == "MINER_PROGRAM_FAILED"
    assert "KeyError" in failed["stderr"] and failed["stdout"]


def test_only_the_miners_own_code_cell_may_ask_for_a_gpu_in_the_miner_lane():
    with pytest.raises(ValueError, match="unsupported accelerator request"):
        research_carrier._run_locked(
            None,
            owner="alice",
            identity="t",
            source="print(1)",
            files={},
            image=SimpleNamespace(image_id=DIGEST),
            seconds=60,
            provenance="MINER_SELF_REPORTED",
            extra_resources={},
            miner_authored=False,
            accelerator=research_carrier.MINER_GPU,
        )


# ---- The local lane's device, locks and settlement (2026-10-03 review).

GPU_UUID = "GPU-31e88d04-75ff-89b2-9160-4b923dd7eb81"
MIG_UUID = "MIG-1b2c3d4e-5f60-7182-93a4-b5c6d7e8f901"


def miner_lane(tmp_path, cli, device, *, ledger=None):
    """One miner-lane run up to its container, with doubles for the host."""
    operation = tmp_path / "operation-x"
    operation.mkdir()
    (operation / "input").mkdir()
    return research_carrier._run_miner_lane(
        ledger or SimpleNamespace(root=tmp_path),
        guard=None,
        owner="alice",
        identity="rtsk_" + "7" * 64,
        operation=operation,
        stage=operation / "input",
        name="carbon-d4-" + "c" * 24,
        cli=cli,
        image=SimpleNamespace(image_id=DIGEST),
        launch="sha256:" + "b" * 64,
        request={},
        seconds=None,
        started=0.0,
        started_unix=0.0,
        bootstrap="pass",
        output_validator=None,
        provenance="MINER_SELF_REPORTED",
        resources={},
        miner_authored=True,
        before_finish=lambda: None,
        device=device,
    )


@pytest.fixture
def host(monkeypatch):
    """The device lease, the shared Carbon slot and the retained-container
    check as recorded events; nothing touches a real device or Docker."""
    from contextlib import contextmanager

    from carbon.reconstruction.worker import accelerator_runtime as runtime

    events = []

    @contextmanager
    def held(name):
        events.append(name + "+")
        try:
            yield
        finally:
            events.append(name + "-")

    monkeypatch.setattr(runtime, "miner_device_lease", lambda uuid: held("device"))
    monkeypatch.setattr(runtime, "shared_host_lease", lambda: held("slot"))
    monkeypatch.setattr(
        runtime, "reject_existing_device_containers", lambda cli: events.append("check")
    )
    monkeypatch.setattr(
        research_carrier.liveness_reaper, "spawn_liveness_reaper", lambda **_: None
    )
    monkeypatch.setattr(
        research_carrier, "remove_exact_container", lambda **_: events.append("remove")
    )

    class Cli:
        def run(self, arguments, timeout=30):
            events.append(arguments[0])
            if arguments[0] == "start":
                raise WorkerFailure(WorkerCode.UNAVAILABLE)
            return SimpleNamespace(stdout=b"")

    return SimpleNamespace(events=events, cli=Cli(), runtime=runtime)


def test_the_miner_gpu_run_holds_the_shared_carbon_slot_across_check_and_create(
    tmp_path, host
):
    """Validator GPU work holds the shared slot for its whole run and checks
    for labelled device containers under it. The miner's run holds the same
    slot from its own check until its create, so neither side can pass its
    check while the other is between check and create; once created, the
    run's device label is what the validator's check sees."""
    with pytest.raises(WorkerFailure):
        miner_lane(tmp_path, host.cli, SimpleNamespace(device_uuid=GPU_UUID))
    events = host.events
    assert events[:6] == ["device+", "slot+", "check", "create", "slot-", "start"]
    assert events[-1] == "device-" and "remove" in events


def test_a_held_carbon_slot_stops_the_miner_gpu_run_before_create(
    tmp_path, host, monkeypatch
):
    def contended():
        host.events.append("slot busy")
        raise WorkerFailure(WorkerCode.CONFLICT)

    monkeypatch.setattr(host.runtime, "shared_host_lease", contended)
    with pytest.raises(WorkerFailure) as refused:
        miner_lane(tmp_path, host.cli, SimpleNamespace(device_uuid=GPU_UUID))
    assert refused.value.code == WorkerCode.CONFLICT
    assert host.events == ["device+", "slot busy", "device-"]


def test_a_mig_instance_is_a_device_and_a_refused_launch_is_settled_at_once(tmp_path):
    """MIG instances are listed as MIG-<uuid>; the lane accepts them. A
    launch refused before any container command is settled there and then,
    as the prechecks settle, rather than left RESERVED."""
    stage = tmp_path / "stage"
    stage.mkdir()
    MinerResearchLaunch(
        "carbon-d4-" + "c" * 24,
        DIGEST,
        "sha256:" + "b" * 64,
        stage,
        stage,
        gpu_device=MIG_UUID,
    )
    finished = []
    ledger = SimpleNamespace(
        root=tmp_path, finish=lambda identity, **fields: finished.append(fields)
    )
    with pytest.raises(WorkerFailure):
        miner_lane(
            tmp_path, None, SimpleNamespace(device_uuid="GPU-$(id)"), ledger=ledger
        )
    (settled,) = finished
    assert settled["state"] == "FAILED_INFRA"
    assert settled["result"]["worker_created"] is False
