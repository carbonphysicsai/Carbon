"""The remote GPU build lane (`carbon.reconstruction.remote_gpu_build`; owner's order Mon 16 Nov 2026 via the Lead, TE3):
a door's GPU BUILD ops run on a rented GPU's ssh docker daemon in one of N slots, inputs mirrored there, the door keeps the
ledger and computes the state digest, and a link or GPU fault is Carbon's (FAILED_INFRA), never the miner's. No ssh, no
docker, no GPU: every process boundary is faked, and every device UUID is synthetic.
"""

from __future__ import annotations

import ast
import json
import threading
from pathlib import Path

import accelerator_host
import pytest

from carbon.reconstruction import (
    accelerators,
    host_execution,
    remote_gpu_build,
    remote_lane,
)
from carbon.reconstruction.remote_lane import RemoteLaneDown
from carbon.reconstruction.worker import accelerator_runtime
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

HOST = "ssh://carbon-build@a100-1.example:2222"
STAGE = "/var/lib/carbon/doors"
KIND = "NVIDIA A100-SXM4-80GB"
UUID = "GPU-a1a1a1a1-0000-1111-2222-333333333333"
BUILD = "direct-" + "a" * 64 + "-build"


def _install(
    root,
    *,
    memory=None,
    slots=2,
    cpusets=("0-3", "4-7"),
    kind=KIND,
    row=True,
    values=None,
    local=False,
):
    """A synthetic operator install: the lane record, the lane machine's device record and a values row. ``local``: a
    local slot lane (this host's GPU, its record in the host root)."""
    root.mkdir(
        mode=0o700, parents=True, exist_ok=True
    )  # the host root is private, as installed
    (root / remote_gpu_build.RECORD).write_text(
        json.dumps(
            {
                "schema": remote_gpu_build.SCHEMA,
                "lanes": [
                    {
                        "docker_host": None if local else HOST,
                        "stage_root": None if local else STAGE,
                        "slot_cpusets": list(cpusets),
                    }
                ],
            }
        )
    )
    lane_dir = root / remote_gpu_build.LANE_DIR.format(index=0)
    accelerator_host.install(
        root if local else lane_dir,
        accelerator_host.document(
            "hosted_instance",
            device_uuid=UUID,
            device_kind=kind,
            device_memory_mib=81920,
            compute_capability="8.0",
        ),
    )
    values = root / "values.json" if values is None else values
    values.write_text(
        json.dumps(
            {
                "schema": remote_gpu_build.VALUES_SCHEMA,
                "rows": (
                    {
                        "electric-motor-magnetics 1.8": {
                            "device_kind": KIND,
                            "slots": slots,
                            **({} if memory is None else {"memory": memory}),
                        }
                    }
                    if row
                    else {}
                ),
            }
        )
    )
    return values


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "accelerators"
    monkeypatch.setattr(accelerator_runtime, "HOST_ROOT", root)
    monkeypatch.setattr(remote_gpu_build, "_docker_binary", lambda: "/usr/bin/docker")
    # the slot machinery under test; the shipped value (False) refuses N > 1: test_n_slots_wait_for_a_jax_memory_cap
    monkeypatch.setattr(remote_gpu_build, "SLOT_PRELUDE_RULED", True)
    monkeypatch.setattr(remote_gpu_build, "_ENVIRONMENT_BINDING", [])
    monkeypatch.setattr(remote_gpu_build, "_PINNED", {})
    return root


def _lane(host, **kwargs):
    values = _install(host, **kwargs)
    return remote_gpu_build.door_lane("electric-motor-magnetics", "1.8", values=values)


def _op(identity=BUILD, **kwargs):
    return remote_gpu_build.op(
        identity,
        accelerator=kwargs.pop("accelerator", "VALIDATOR_OWN_GPU"),
        provenance=kwargs.pop("provenance", "DIRECT_GRAPH_PUBLIC_BUILD"),
        timed=kwargs.pop("timed", False),
        **kwargs,
    )


# -- configuration ---------------------------------------------------------------------------------------------------------


def test_no_record_and_no_row_is_no_lane(host):
    assert remote_gpu_build.load(host) == ()
    values = _install(host, row=False)
    assert (
        remote_gpu_build.door_lane("electric-motor-magnetics", "1.8", values=values)
        is None
    )


def test_the_checked_in_values_file_names_only_motor_1_8_on_the_a100():
    """Lead, 16 Nov (for V2's read): Motor 1.8 builds on the Lambda A100 40GB, 4 shared slots to start. A door uses it
    only with the operator's lane record and the box's device record installed."""
    document = json.loads(remote_gpu_build.VALUES.read_bytes())
    assert document["schema"] == remote_gpu_build.VALUES_SCHEMA
    assert set(document["rows"]) == {"electric-motor-magnetics 1.8"}
    assert remote_gpu_build.values_row("electric-motor-magnetics", "1.8") == {
        "device_kind": "NVIDIA A100-SXM4-40GB",
        "slots": 4,
        "memory": "shared",
    }
    assert remote_gpu_build.values_row("electric-motor-magnetics", "1.4") is None


def test_a_well_formed_install_is_a_door_lane(host):
    lane = _lane(host)
    assert (
        lane.slots == 2
        and lane.device.device_uuid == UUID
        and lane.device.device_kind == KIND
    )
    assert lane.spec.slot_cpusets == ("0-3", "4-7") and lane.spec.docker_host == HOST


@pytest.mark.parametrize(
    "change",
    [
        {"docker_host": "tcp://10.0.0.2:2375"},
        {"stage_root": "/"},
        {"slot_cpusets": []},
        {"slot_cpusets": ["0-3", "3-6"]},  # overlapping
        {"slot_cpusets": ["0-3", "4-5"]},  # unequal
        {"slot_cpusets": ["0-1"] * 5},
        {"extra": 1},
    ],
)
def test_a_malformed_record_refuses(host, change):
    _install(host)
    document = json.loads((host / remote_gpu_build.RECORD).read_text())
    document["lanes"][0].update(change)
    (host / remote_gpu_build.RECORD).write_text(json.dumps(document))
    with pytest.raises(ValueError):
        remote_gpu_build.load(host)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (
            {"device_kind": KIND},
            {"device_kind": KIND, "slots": 1, "memory": "capped"},
        ),
        (
            {"device_kind": KIND, "slots": 4},
            {"device_kind": KIND, "slots": 4, "memory": "capped"},
        ),
        (
            {"device_kind": KIND, "slots": 4, "memory": "shared"},
            {"device_kind": KIND, "slots": 4, "memory": "shared"},
        ),
        ({"device_kind": KIND, "slots": 4, "memory": "loose"}, None),
        ({"device_kind": KIND, "slots": 0}, None),
        ({"device_kind": KIND, "slots": 9}, None),
        ({"device_kind": KIND, "slots": True}, None),
        ({"device_kind": "x; rm -rf /"}, None),
        ({"slots": 2}, None),
        ({"device_kind": KIND, "other": 1}, None),
    ],
)
def test_the_values_row_defaults_to_one_slot_and_refuses_anything_else(
    tmp_path, row, expected
):
    path = tmp_path / "values.json"
    path.write_text(
        json.dumps({"schema": remote_gpu_build.VALUES_SCHEMA, "rows": {"c 1": row}})
    )
    assert remote_gpu_build.values_row("c", "1", path=path) == expected
    assert remote_gpu_build.values_row("c", "2", path=path) is None
    assert remote_gpu_build.values_row("c", "1", path=tmp_path / "missing.json") is None


def test_a_device_of_another_kind_refuses(host):
    with pytest.raises(ValueError, match="device_kind"):
        _lane(host, kind="NVIDIA GeForce RTX 4090")


def test_more_slots_than_cpusets_refuses(host):
    with pytest.raises(ValueError, match="slots_exceed"):
        _lane(host, slots=3)


def test_a_missing_device_record_refuses(host):
    values = _install(host)
    (host / remote_gpu_build.LANE_DIR.format(index=0) / "host-device.json").unlink()
    with pytest.raises(ValueError, match="device_record"):
        remote_gpu_build.door_lane("electric-motor-magnetics", "1.8", values=values)


def test_a_lane_that_broke_since_start_is_carbons_at_the_build(host):
    values = _install(host)
    (host / remote_gpu_build.LANE_DIR.format(index=0) / "host-device.json").unlink()
    with (
        pytest.raises(RemoteLaneDown) as raised,
        remote_gpu_build.offered_for("electric-motor-magnetics", "1.8", values=values),
    ):
        pass
    assert raised.value.code is WorkerCode.UNAVAILABLE


# -- which ops go ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("identity", "accelerator", "provenance", "timed", "expected"),
    [
        (BUILD, "VALIDATOR_OWN_GPU", "X", False, True),
        ("task-1~gpu1", "MINER_OWN_GPU", "X", False, True),
        ("task-1~gpu2", "MINER_OWN_GPU", "X", False, True),
        (BUILD, None, "X", False, False),  # a CPU build
        (
            BUILD,
            "VALIDATOR_OWN_GPU",
            "MINER_SELF_REPORTED",
            False,
            False,
        ),  # the miner's own lane
        (BUILD, "VALIDATOR_OWN_GPU", "X", True, False),  # a timing measurement
        ("direct-" + "a" * 64 + "-inference", "VALIDATOR_OWN_GPU", "X", False, False),
        ("direct-" + "a" * 64 + "-timed", "VALIDATOR_OWN_GPU", "X", False, False),
        ("single-call-abc", "VALIDATOR_OWN_GPU", "X", False, False),
        ("task-1~gpu3", "VALIDATOR_OWN_GPU", "X", False, False),
    ],
)
def test_only_gpu_builds_are_eligible(
    identity, accelerator, provenance, timed, expected
):
    assert (
        remote_gpu_build.eligible(
            identity, accelerator=accelerator, provenance=provenance, timed=timed
        )
        is expected
    )


def test_an_op_outside_an_offer_or_ineligible_is_unchanged(host):
    lane = _lane(host)
    with _op() as binding:
        assert binding is None and remote_gpu_build.current_op() is None
    with remote_gpu_build.offered(lane), _op(accelerator=None) as binding:
        assert binding is None and remote_gpu_build.device() is None
        assert remote_gpu_build.cli() is None and remote_gpu_build.intent_fields() == {}


def test_n_slots_run_at_once_and_the_next_build_waits_then_is_carbons(
    host, monkeypatch
):
    lane = _lane(host, slots=2)
    held, release, seen = threading.Barrier(3), threading.Event(), []

    def build():
        with remote_gpu_build.offered(lane), _op() as binding:
            seen.append(binding.slot)
            held.wait(5)
            release.wait(5)

    threads = [threading.Thread(target=build) for _ in range(2)]
    for thread in threads:
        thread.start()
    held.wait(5)
    assert sorted(seen) == [0, 1]
    monkeypatch.setattr(remote_gpu_build, "SLOT_WAIT_SECONDS", 0)
    with (
        pytest.raises(RemoteLaneDown) as raised,
        remote_gpu_build.offered(lane),
        _op(poll_s=0, sleep=lambda _: None),
    ):
        pass
    assert raised.value.code is WorkerCode.UNAVAILABLE
    release.set()
    for thread in threads:
        thread.join(5)
    with remote_gpu_build.offered(lane), _op() as binding:
        assert binding.slot == 0  # freed


# -- what a bound op runs with ----------------------------------------------------------------------------------------------


def test_a_bound_op_uses_the_lane_machines_device_cores_and_allocation_record(host):
    lane = _lane(host)
    with remote_gpu_build.offered(lane), _op() as binding:
        assert accelerator_runtime.host_device().digest == lane.device.digest
        assert accelerator_runtime.miner_host_device().digest == lane.device.digest
        assert host_execution.resolve_cpuset(logical_cpus=16, count=4) == binding.cpuset
        # read as an installed record is (the receiver's start checks at today's count on a 4-core slot)
        assert host_execution.resolve_cpuset(logical_cpus=16, count=2) == binding.cpuset
        with pytest.raises(WorkerFailure):
            host_execution.resolve_cpuset(logical_cpus=16, count=3)
        with pytest.raises(WorkerFailure):
            # cores the machine lacks
            host_execution.resolve_cpuset(logical_cpus=2, count=4)
        assert remote_lane.docker_host() == HOST
        assert remote_lane.current_environment()["DOCKER_HOST"] == HOST
        from carbon.reconstruction.worker.model import MINER_HOST_AUTHORITY

        launch = "sha256:" + "b" * 64
        accelerator_runtime.mark_device_allocation(
            container_name="c", launch_digest=launch, authority=MINER_HOST_AUTHORITY
        )
        assert (binding.slot_dir / "active-allocation.json").exists()
        assert not (host / "active-allocation.json").exists()
        assert accelerator_runtime.owns_device_allocation(
            container_name="c", launch_digest=launch
        )
        accelerator_runtime.finish_local_device_allocation(
            container_name="c", launch_digest=launch
        )
        assert not (binding.slot_dir / "active-allocation.json").exists()
    assert remote_lane.docker_host() is None


def test_the_worker_environment_is_the_pinned_deterministic_one_on_the_lane_device(
    host,
):
    lane = _lane(host)
    environment = accelerators.worker_environment(
        accelerators.GPU_PROFILE,
        accelerators.AcceleratorRole.VALIDATOR_RECONSTRUCTION,
        host_device=lane.device,
    )
    assert environment["CUDA_VISIBLE_DEVICES"] == UUID
    assert environment["CARBON_ACCELERATOR_DEVICE_KIND"] == KIND
    assert environment["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert environment["NVIDIA_TF32_OVERRIDE"] == "0"
    for flag in accelerators.GPU_DETERMINISM_XLA_FLAGS:
        assert flag in environment["XLA_FLAGS"]
    assert environment["XLA_PYTHON_CLIENT_PREALLOCATE"] == "false"


def _argv():
    return [
        "create",
        "--env",
        "XLA_PYTHON_CLIENT_PREALLOCATE=false",
        "--env",
        "XLA_PYTHON_CLIENT_ALLOCATOR=platform",
        "--env",
        "XLA_FLAGS=" + " ".join(accelerators.GPU_DETERMINISM_XLA_FLAGS),
        "--env",
        "CUBLAS_WORKSPACE_CONFIG=:4096:8",
        "sha256:" + "c" * 64,
    ]


def test_one_slot_changes_nothing(host):
    lane = _lane(host, slots=1, cpusets=("0-3",))
    source = '"""doc"""\nfrom __future__ import annotations\nx = 1\n'
    with remote_gpu_build.offered(lane), _op():
        assert remote_gpu_build.slot_environment() == {}
        assert remote_gpu_build.with_slot_environment(_argv()) == _argv()
        assert remote_gpu_build.with_slot_prelude(source) == source
        assert remote_gpu_build.request_fields() == {}


def test_n_slots_cap_each_processs_device_memory_and_keep_determinism(host):
    lane = _lane(host, slots=2)
    with remote_gpu_build.offered(lane), _op():
        argv = remote_gpu_build.with_slot_environment(_argv())
        assert remote_gpu_build.request_fields() == {
            "remote_gpu_slots": 2,
            "slot_memory": {
                "fraction": "0.45",
                "jax": {
                    "XLA_PYTHON_CLIENT_ALLOCATOR": "bfc",
                    "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
                },
                "torch": "set_per_process_memory_fraction",
            },
        }
    environment = dict(
        value.split("=", 1)
        for index, value in enumerate(argv)
        if index and argv[index - 1] == "--env"
    )
    assert argv[-1] == _argv()[-1] and argv[0] == "create"
    assert environment["XLA_PYTHON_CLIENT_PREALLOCATE"] == "false"
    # the pinned (image-input) environment keeps JAX on the on-demand platform allocator: no BFC fraction
    assert environment["XLA_PYTHON_CLIENT_ALLOCATOR"] == "platform"
    assert "XLA_PYTHON_CLIENT_MEM_FRACTION" not in environment
    assert environment[remote_gpu_build.SLOT_FRACTION_ENV] == "0.45"
    assert environment["XLA_FLAGS"] == " ".join(accelerators.GPU_DETERMINISM_XLA_FLAGS)
    assert environment["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert argv.count("--env") == len(environment)


@pytest.mark.parametrize(
    ("slots", "fraction"), [(1, 0.9), (2, 0.45), (3, 0.3), (4, 0.22)]
)
def test_the_slot_fraction(slots, fraction):
    assert remote_gpu_build.slot_fraction(slots) == fraction
    assert (
        remote_gpu_build.slot_fraction(slots) * slots <= remote_gpu_build.MEMORY_SHARE
    )


def test_the_torch_prelude_follows_the_docstring_and_future_imports(host):
    lane = _lane(host, slots=2)
    source = (
        '"""doc\nmore"""\n\nfrom __future__ import annotations\n\nimport os\nx = 1\n'
    )
    with remote_gpu_build.offered(lane), _op():
        changed = remote_gpu_build.with_slot_prelude(source)
    module = ast.parse(changed)
    assert ast.get_docstring(module) == "doc\nmore"
    assert (
        isinstance(module.body[1], ast.ImportFrom)
        and module.body[1].module == "__future__"
    )
    assert remote_gpu_build.SLOT_PRELUDE in changed
    assert changed.index(remote_gpu_build.SLOT_PRELUDE) > changed.index("annotations")
    assert changed.endswith("import os\nx = 1\n")
    compile(changed, "program.py", "exec")


def test_the_prelude_runs_before_any_import_in_the_carriers_real_build_programs(host):
    """The cap binds only if it is set before JAX is imported: in every real build program a slot may run, the prelude
    is the first code after the docstring and ``__future__`` imports, ahead of every import.
    """
    from carbon.development_session import (
        bundle_construction_worker,
        direct_graph_construction_worker,
    )

    lane = _lane(host, slots=2)
    programs = (
        bundle_construction_worker.BUILD_PROGRAM,
        direct_graph_construction_worker.BUILD_PROGRAM,
        direct_graph_construction_worker.PHYSICAL_BUILD_PROGRAM,
    )
    prelude_first = ast.parse(remote_gpu_build.SLOT_PRELUDE).body[0]
    with remote_gpu_build.offered(lane), _op():
        for program in programs:
            changed = remote_gpu_build.with_slot_prelude(program)
            compile(changed, "program.py", "exec")
            body = [
                node
                for node in ast.parse(changed).body
                if not (
                    isinstance(node, ast.ImportFrom) and node.module == "__future__"
                )
                and not (
                    isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                )
            ]
            assert ast.dump(body[0]) == ast.dump(prelude_first)
            first_import = next(
                index
                for index, node in enumerate(body)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                and node is not body[0]
                and not ast.dump(node).count("_carbon_")
            )
            prelude_length = len(ast.parse(remote_gpu_build.SLOT_PRELUDE).body)
            assert first_import >= prelude_length


def test_the_prelude_caps_jax_and_torch_and_leaves_a_jax_only_image_alone(monkeypatch):
    calls = []

    class Cuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def set_per_process_memory_fraction(fraction, device):
            calls.append((fraction, device))

    import os
    import sys
    import types

    for key in (
        "XLA_PYTHON_CLIENT_ALLOCATOR",
        "XLA_PYTHON_CLIENT_PREALLOCATE",
        "XLA_PYTHON_CLIENT_MEM_FRACTION",
    ):
        monkeypatch.setenv(key, "pinned")  # restored after the test
    fake = types.ModuleType("torch")
    fake.cuda = Cuda
    monkeypatch.setitem(sys.modules, "torch", fake)
    monkeypatch.setenv(remote_gpu_build.SLOT_FRACTION_ENV, "0.45")
    prelude = compile(remote_gpu_build.SLOT_PRELUDE, "prelude", "exec")
    exec(prelude, {})  # noqa: S102 - the prelude itself
    assert calls == [(0.45, 0)]
    assert os.environ["XLA_PYTHON_CLIENT_ALLOCATOR"] == "bfc"
    assert os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] == "false"
    assert os.environ["XLA_PYTHON_CLIENT_MEM_FRACTION"] == "0.45"
    monkeypatch.setitem(sys.modules, "torch", None)  # a JAX-only image: no torch
    exec(prelude, {})  # noqa: S102 - the prelude itself
    assert calls == [(0.45, 0)]
    # no share in the environment (one slot): nothing is touched
    monkeypatch.delenv(remote_gpu_build.SLOT_FRACTION_ENV)
    monkeypatch.setenv("XLA_PYTHON_CLIENT_ALLOCATOR", "platform")
    exec(prelude, {})  # noqa: S102 - the prelude itself
    assert os.environ["XLA_PYTHON_CLIENT_ALLOCATOR"] == "platform"


def test_n_slots_need_validator_2s_ruling(host, monkeypatch):
    monkeypatch.setattr(remote_gpu_build, "SLOT_PRELUDE_RULED", False)
    with pytest.raises(ValueError, match="jax_memory_cap"):
        _lane(host, slots=2)


# -- the remote machine ----------------------------------------------------------------------------------------------------


def test_the_wrapper_is_the_docker_cli_with_the_lanes_daemon(host):
    lane = _lane(host)
    text = remote_gpu_build.wrapper_text(HOST, "/home/carbon", "/usr/bin/docker")
    assert "DOCKER_HOST=ssh://carbon-build@a100-1.example:2222\n" in text
    assert text.endswith('exec /usr/bin/docker "$@"\n')
    with pytest.raises(ValueError):
        remote_gpu_build.wrapper_text(
            "ssh://x@h -oProxyCommand=y", "/home/carbon", "/usr/bin/docker"
        )
    with pytest.raises(RemoteLaneDown):
        remote_gpu_build.wrapper_text(HOST, "/home/$(id)", "/usr/bin/docker")
    with remote_gpu_build.offered(lane), _op():
        cli = remote_gpu_build.cli()
    path = Path(cli.executable)
    assert (
        path == Path(lane.lane_dir) / "docker" and path.stat().st_mode & 0o777 == 0o500
    )
    assert cli.docker_host == HOST


def test_inputs_mirror_to_the_lane_machine_only_inside_a_bound_op(host, monkeypatch):
    lane = _lane(host)
    calls = []
    monkeypatch.setattr(
        remote_lane,
        "mirror",
        lambda stage, binding: calls.append(("mirror", stage, binding)),
    )
    monkeypatch.setattr(
        remote_lane,
        "discard",
        lambda stage, binding: calls.append(("discard", stage, binding)),
    )
    remote_gpu_build.mirror(Path(STAGE) / "x" / "input")
    remote_gpu_build.discard(Path(STAGE) / "x" / "input")
    assert calls == []
    with remote_gpu_build.offered(lane), _op() as binding:
        remote_gpu_build.mirror(Path(STAGE) / "x" / "input")
        remote_gpu_build.discard(Path(STAGE) / "x" / "input")
    assert [call[0] for call in calls] == ["mirror", "discard"] and calls[0][
        2
    ] is binding
    # remote_lane's own guards apply: only paths under the lane's stage root
    with pytest.raises(RemoteLaneDown):
        remote_lane._remote_path(Path("/etc/passwd"), binding)


def test_the_gpu_probe_names_the_recorded_device(host, monkeypatch):
    lane = _lane(host)
    binding = remote_gpu_build.OpBinding(lane, 0)
    rows = {"value": f"{UUID}, {KIND}\n".encode()}
    monkeypatch.setattr(remote_gpu_build, "_ssh_capture", lambda *a, **k: rows["value"])
    assert remote_gpu_build.gpu_present(binding)
    rows["value"] = b"GPU-other, NVIDIA A100-SXM4-80GB\n"
    assert not remote_gpu_build.gpu_present(binding)

    def down(*a, **k):
        raise RemoteLaneDown(b"x")

    monkeypatch.setattr(remote_gpu_build, "_ssh_capture", down)
    assert not remote_gpu_build.gpu_present(binding)


class _FakeCLI:
    def __init__(self, stdout=b""):
        self.stdout, self.calls = stdout, []

    def run(self, arguments, timeout=30, accepted=(0,)):
        from types import SimpleNamespace

        self.calls.append(arguments)
        return SimpleNamespace(stdout=self.stdout, returncode=0, stderr=b"")


def test_at_most_n_carbon_containers_share_the_device(host):
    lane = _lane(host, slots=2)
    with remote_gpu_build.offered(lane), _op() as binding:
        accelerator_runtime.reject_existing_device_containers(
            cli=_FakeCLI(b'"a"\n'), device_uuid=UUID
        )
        with pytest.raises(WorkerFailure) as raised:
            accelerator_runtime.reject_existing_device_containers(
                cli=_FakeCLI(b'"a"\n"b"\n'), device_uuid=UUID
            )
        assert raised.value.code is WorkerCode.CONFLICT
        (binding.slot_dir / "active-allocation.json").write_text("{}")
        with pytest.raises(WorkerFailure):
            accelerator_runtime.reject_existing_device_containers(
                cli=_FakeCLI(), device_uuid=UUID
            )


def test_a_changed_device_record_refuses_at_dispatch(host):
    lane = _lane(host)
    with remote_gpu_build.offered(lane), _op(), pytest.raises(RemoteLaneDown):
        remote_gpu_build.check_host(_FakeCLI(), None, None)


# -- failure typing --------------------------------------------------------------------------------------------------------


def test_a_failure_with_the_link_or_gpu_down_is_carbons(host, monkeypatch):
    lane = _lane(host)
    binding = remote_gpu_build.OpBinding(lane, 0)
    error = WorkerFailure(WorkerCode.RUNTIME)
    monkeypatch.setattr(remote_lane, "link_up", lambda b: True)
    monkeypatch.setattr(remote_gpu_build, "gpu_present", lambda b: True)
    assert remote_gpu_build.retyped(error, binding) is None
    monkeypatch.setattr(remote_gpu_build, "gpu_present", lambda b: False)
    down = remote_gpu_build.retyped(error, binding)
    assert isinstance(down, RemoteLaneDown) and down.code is WorkerCode.UNAVAILABLE
    monkeypatch.setattr(remote_lane, "link_up", lambda b: False)
    assert isinstance(remote_gpu_build.retyped(error, binding), RemoteLaneDown)
    assert remote_gpu_build.retyped(RemoteLaneDown(b"x"), binding) is None
    assert (
        remote_gpu_build.retyped(error, None) is None
    )  # outside a remote op: as before


def test_the_carrier_retypes_a_remote_build_failure_and_leaves_other_ops_alone(
    host, monkeypatch
):
    from carbon.development_session import research_carrier

    lane = _lane(host)

    def failing(ledger, **kwargs):
        assert (remote_gpu_build.current_op() is not None) is kwargs["expect_remote"]
        raise WorkerFailure(WorkerCode.RUNTIME)

    monkeypatch.setattr(research_carrier, "_run_supervised", failing)
    monkeypatch.setattr(remote_gpu_build, "healthy", lambda binding=None: False)
    with remote_gpu_build.offered(lane):
        with pytest.raises(RemoteLaneDown):
            research_carrier._run(
                None,
                identity=BUILD,
                accelerator="VALIDATOR_OWN_GPU",
                provenance="X",
                expect_remote=True,
            )
        inference = "direct-" + "a" * 64 + "-inference"
        with pytest.raises(WorkerFailure) as raised:
            research_carrier._run(
                None, identity=inference, provenance="X", expect_remote=False
            )
        assert (
            type(raised.value) is WorkerFailure
            and raised.value.code is WorkerCode.RUNTIME
        )
    monkeypatch.setattr(remote_gpu_build, "healthy", lambda binding=None: True)
    with remote_gpu_build.offered(lane):
        with pytest.raises(WorkerFailure) as raised:
            research_carrier._run(
                None,
                identity=BUILD,
                accelerator="VALIDATOR_OWN_GPU",
                provenance="X",
                expect_remote=True,
            )
        assert (
            type(raised.value) is WorkerFailure
        )  # a healthy lane: the failure stands as it is


_WALL = {
    "container_name": "c",
    "launch_digest": "sha256:" + "d" * 64,
    "image_id": "sha256:" + "e" * 64,
    "program_started": 0.0,
    "program_timeout": 1,
    "setup_seconds": 0,
    "memory_limit_bytes": None,
    "deadline": 0.0,
    "observation": {"status": "UNOBSERVED"},
    "accelerated": True,
}


def test_a_wall_stop_on_the_lane_is_never_the_candidates(host):
    from carbon.development_session import research_carrier

    lane = _lane(host)
    stop = _WALL
    error = WorkerFailure(
        WorkerCode.DEADLINE, private_diagnostic=b"stream command timed out"
    )
    assert (
        research_carrier._candidate_resource_stop(None, error, **stop)[0]
        is WorkerCode.DEADLINE
    )
    with remote_gpu_build.offered(lane), _op():
        assert research_carrier._candidate_resource_stop(None, error, **stop) is None


def test_the_carriers_device_record_is_the_lane_machines_inside_a_bound_op(host):
    from carbon.development_session import research_carrier

    lane = _lane(host)
    with remote_gpu_build.offered(lane), _op():
        assert research_carrier._gpu_device().digest == lane.device.digest


# -- recovery --------------------------------------------------------------------------------------------------------------


def test_an_intent_records_the_slot_and_recovery_rebinds_it(host):
    lane = _lane(host)
    with remote_gpu_build.offered(lane), _op() as binding:
        fields = remote_gpu_build.intent_fields()
    assert fields == {
        "remote_gpu_build": {
            "docker_host": HOST,
            "stage_root": STAGE,
            "lane": 0,
            "slot": binding.slot,
        }
    }
    recovered = remote_gpu_build.recorded(fields)
    assert (
        recovered.slot == binding.slot
        and recovered.lane.device.digest == lane.device.digest
    )
    with remote_gpu_build.bound(recovered):
        assert accelerator_runtime.host_device().digest == lane.device.digest
    assert remote_gpu_build.recorded({}) is None
    for broken in (
        {"remote_gpu_build": {"docker_host": HOST}},
        {
            "remote_gpu_build": {
                **fields["remote_gpu_build"],
                "docker_host": "ssh://x@other",
            }
        },
        {"remote_gpu_build": {**fields["remote_gpu_build"], "slot": 9}},
    ):
        with pytest.raises(ValueError):
            remote_gpu_build.recorded(broken)


# -- a local slot lane (the GPUYard 4090: one design for both) --------------------------------------------------------------


@pytest.mark.parametrize(
    "change", [{"docker_host": None}, {"stage_root": None}]  # one without the other
)
def test_a_half_local_record_refuses(host, change):
    _install(host)
    document = json.loads((host / remote_gpu_build.RECORD).read_text())
    document["lanes"][0].update(change)
    (host / remote_gpu_build.RECORD).write_text(json.dumps(document))
    with pytest.raises(ValueError):
        remote_gpu_build.load(host)


def test_a_local_slot_lane_uses_this_hosts_gpu_daemon_and_record_with_the_same_slots(
    host, monkeypatch
):
    lane = _lane(host, local=True)
    assert lane.spec.local and lane.device.device_uuid == UUID
    assert not (Path(lane.lane_dir) / "host-device.json").exists()
    mirrored = []
    monkeypatch.setattr(remote_lane, "mirror", lambda *a: mirrored.append(a))
    with remote_gpu_build.offered(lane), _op() as binding:
        assert (
            remote_gpu_build.cli() is None
        )  # the caller's own DockerCLI: this host's daemon
        assert (
            remote_gpu_build.docker_host() is None and remote_lane.docker_host() is None
        )
        remote_gpu_build.mirror(Path(STAGE) / "x" / "input")
        assert mirrored == []
        assert accelerator_runtime.host_device().digest == lane.device.digest
        assert host_execution.resolve_cpuset(logical_cpus=16, count=4) == binding.cpuset
        assert remote_gpu_build.slot_environment() == {
            remote_gpu_build.SLOT_FRACTION_ENV: "0.45"
        }
        assert remote_gpu_build.request_fields() == {
            "remote_gpu_slots": 2,
            "slot_memory": {
                "fraction": "0.45",
                "jax": {
                    "XLA_PYTHON_CLIENT_ALLOCATOR": "bfc",
                    "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
                },
                "torch": "set_per_process_memory_fraction",
            },
        }
        assert (
            remote_gpu_build.intent_fields()["remote_gpu_build"]["docker_host"] is None
        )
        recovered = remote_gpu_build.recorded(remote_gpu_build.intent_fields())
        assert recovered.lane.spec.local and recovered.slot == binding.slot
    assert not (Path(lane.lane_dir) / "docker").exists()  # no wrapper for a local lane


def test_a_local_slot_waits_for_the_hosts_other_carbon_gpu_work(host):
    lane = _lane(host, local=True)
    with remote_gpu_build.offered(lane), _op():
        accelerator_runtime.reject_existing_device_containers(
            cli=_FakeCLI(), device_uuid=UUID
        )
        (host / "active-allocation.json").write_text("{}")
        with pytest.raises(WorkerFailure) as raised:
            accelerator_runtime.reject_existing_device_containers(
                cli=_FakeCLI(), device_uuid=UUID
            )
        assert raised.value.code is WorkerCode.CONFLICT


def test_a_local_gpu_fault_after_a_failed_build_is_carbons_without_ssh(
    host, monkeypatch
):
    lane = _lane(host, local=True)
    binding = remote_gpu_build.OpBinding(lane, 0)
    seen = []

    def run(command, **kwargs):
        from types import SimpleNamespace

        seen.append(command)
        return SimpleNamespace(returncode=0, stdout=b"GPU-gone, X\n", stderr=b"")

    monkeypatch.setattr(remote_gpu_build.subprocess, "run", run)
    monkeypatch.setattr(
        remote_lane, "link_up", lambda b: pytest.fail("a local lane has no link")
    )
    assert isinstance(
        remote_gpu_build.retyped(WorkerFailure(WorkerCode.RUNTIME), binding),
        RemoteLaneDown,
    )
    assert seen and seen[0][0] == "nvidia-smi"


def test_a_local_slot_lanes_wall_stop_is_read_as_before(host):
    from carbon.development_session import research_carrier

    lane = _lane(host, local=True, slots=1, cpusets=("0-3",))
    error = WorkerFailure(
        WorkerCode.DEADLINE, private_diagnostic=b"stream command timed out"
    )
    with remote_gpu_build.offered(lane), _op():
        assert (
            research_carrier._candidate_resource_stop(None, error, **_WALL)[0]
            is WorkerCode.DEADLINE
        )


# -- review fixes (TE3 review, Mon 16 Nov) ------------------------------------------------------------------------------------


def test_a_slot_container_passes_the_controls_environment_check(host):
    """`docker_runtime.inspect_effective_controls` requires every pinned worker-environment value exactly: a slot's
    create arguments keep every one of them (extras are allowed)."""
    lane = _lane(host, slots=4, cpusets=("0-1", "2-3", "4-5", "6-7"))
    required = accelerators.worker_environment(
        accelerators.GPU_PROFILE,
        accelerators.AcceleratorRole.VALIDATOR_RECONSTRUCTION,
        host_device=lane.device,
    )
    argv = ["create"]
    for key, value in required.items():
        argv.extend(["--env", f"{key}={value}"])
    argv.append("sha256:" + "c" * 64)
    with remote_gpu_build.offered(lane), _op():
        changed = remote_gpu_build.with_slot_environment(argv)
    environment = dict(
        value.split("=", 1)
        for index, value in enumerate(changed)
        if index and changed[index - 1] == "--env"
    )
    assert all(environment.get(key) == value for key, value in required.items())
    assert environment[remote_gpu_build.SLOT_FRACTION_ENV] == "0.22"


def test_a_settled_candidate_failure_is_never_retyped(host, monkeypatch):
    from carbon.development_session import research_carrier

    lane = _lane(host)

    def settled(ledger, **kwargs):
        raise research_carrier.MinerProgramFailure(
            {
                "schema": research_carrier.MINER_FAILURE_SCHEMA,
                "failure_code": next(iter(research_carrier.MINER_FAILURE_CODES)).value,
                "observation": "settled as the candidate's",
            }
        )

    monkeypatch.setattr(research_carrier, "_run_supervised", settled)
    monkeypatch.setattr(remote_gpu_build, "healthy", lambda binding=None: False)
    with (
        remote_gpu_build.offered(lane),
        pytest.raises(research_carrier.MinerProgramFailure),
    ):
        research_carrier._run(
            None, identity=BUILD, accelerator="VALIDATOR_OWN_GPU", provenance="X"
        )


def test_a_replay_of_a_settled_op_takes_no_slot(host, monkeypatch):
    from carbon.development_session import research_carrier

    lane = _lane(host)
    seen = []

    class Ledger:
        def operation_state(self, identity, *, owner):
            return "SUCCEEDED"

    def replay(ledger, **kwargs):
        seen.append(remote_gpu_build.current_op())
        return "recorded"

    monkeypatch.setattr(research_carrier, "_run_supervised", replay)
    with remote_gpu_build.offered(lane):
        assert (
            research_carrier._run(
                Ledger(),
                owner="o",
                identity=BUILD,
                accelerator="VALIDATOR_OWN_GPU",
                provenance="X",
            )
            == "recorded"
        )
    # bound to the lane (its request, device and program are the lane's, so the replay matches what was reserved)...
    assert len(seen) == 1 and seen[0].lane.device.digest == lane.device.digest
    assert seen[0].lane.slots == 2


def test_a_waiting_build_sees_its_cancellation(host):
    lane = _lane(host, slots=1, cpusets=("0-3",))

    def cancelled():
        raise ValueError("research operation cancelled")

    # the one slot is held; the second build waits and sees its cancellation
    with (
        remote_gpu_build.offered(lane),
        _op(),
        pytest.raises(ValueError, match="cancelled"),
        _op(check=cancelled, poll_s=0, sleep=lambda _: None),
    ):
        pass


def test_a_slot_with_a_lost_controllers_record_is_passed_over(host):
    lane = _lane(host, slots=2)
    stale = Path(lane.lane_dir) / "slot-0"
    stale.mkdir(parents=True, exist_ok=True)
    (stale / "active-allocation.json").write_text("{}")
    with remote_gpu_build.offered(lane), _op() as binding:
        assert binding.slot == 1


def test_a_host_private_build_is_withheld_from_a_configured_lane(host):
    values = _install(host)
    with remote_gpu_build.offered_for(
        "electric-motor-magnetics", "1.8", values=values, withhold=True
    ):
        with pytest.raises(RemoteLaneDown) as raised, _op():
            pass
        assert raised.value.code is WorkerCode.UNAVAILABLE
        with _op(accelerator=None) as binding:  # a CPU build is unaffected
            assert binding is None
    # no lane configured: nothing is withheld and nothing changes
    no_row = _install(host, row=False)
    with (
        remote_gpu_build.offered_for(
            "electric-motor-magnetics", "1.8", values=no_row, withhold=True
        ),
        _op() as binding,
    ):
        assert binding is None


def test_a_lane_that_differs_from_the_one_bound_at_start_refuses(host, monkeypatch):
    monkeypatch.setattr(remote_gpu_build, "_PINNED", {})
    values = _install(host)
    remote_gpu_build.pin(
        "electric-motor-magnetics", "1.8", None
    )  # started without a lane
    with (
        pytest.raises(RemoteLaneDown),
        remote_gpu_build.offered_for("electric-motor-magnetics", "1.8", values=values),
    ):
        pass
    lane = remote_gpu_build.door_lane("electric-motor-magnetics", "1.8", values=values)
    remote_gpu_build.pin("electric-motor-magnetics", "1.8", lane)
    with remote_gpu_build.offered_for(
        "electric-motor-magnetics", "1.8", values=values
    ) as offered:
        assert offered.device.digest == lane.device.digest
    no_row = _install(host, row=False)  # the row removed after start
    with (
        pytest.raises(RemoteLaneDown),
        remote_gpu_build.offered_for("electric-motor-magnetics", "1.8", values=no_row),
    ):
        pass


def test_the_watchdog_is_handed_the_slot_and_finishes_its_record(host, monkeypatch):
    lane = _lane(host)
    spawned = []

    class Popen:
        def __init__(self, argv, **kwargs):
            spawned.append(kwargs["env"])

    monkeypatch.setattr(remote_gpu_build.subprocess, "Popen", Popen)
    import time as clock

    with remote_gpu_build.offered(lane), _op() as binding:
        remote_gpu_build.spawn_watchdog(
            container_name="c",
            launch_digest="sha256:" + "b" * 64,
            deadline_unix=clock.time() + 60,
        )
    env = spawned[0]
    assert env["DOCKER_HOST"] == HOST
    # in the watchdog process: no context binding, the handed one
    monkeypatch.setattr(remote_gpu_build, "_ENVIRONMENT_BINDING", [])
    monkeypatch.setenv(remote_gpu_build.ENVIRONMENT, env[remote_gpu_build.ENVIRONMENT])
    assert remote_gpu_build.current_op().slot == binding.slot
    assert accelerator_runtime._allocation_dir() == binding.slot_dir
    assert accelerator_runtime.host_device().digest == lane.device.digest
    monkeypatch.setattr(remote_gpu_build, "_ENVIRONMENT_BINDING", [])
    monkeypatch.setenv(remote_gpu_build.ENVIRONMENT, "{not json")
    # unreadable: binds nothing, so the watchdog still removes the container (the record is left to recovery)
    assert remote_gpu_build.current_op() is None


def test_a_probe_that_loses_the_lane_is_carbons_not_a_cpu_rebuild(monkeypatch):
    """`_graph_gpu_repeats`: a RemoteLaneDown re-raises (FAILED_INFRA) after settling the probes; any other device
    failure keeps the ruling's CPU rebuild."""
    from types import SimpleNamespace

    from carbon.development_session import direct_graph_construction_worker as graph
    from carbon.development_session import research_tasks

    reconciled = []
    provider = SimpleNamespace(
        discovery=SimpleNamespace(
            _material={
                "construction_limits_document": {
                    "reconstruction_resource_policy": {"build_wall_seconds_max": 60}
                },
                "train": None,
                "allowlist_bytes": b"",
            },
            graph_adapter_for=lambda key: None,
        ),
        ledger=None,
        owner="o",
        graph_gpu_image=object(),
        _seed_for=lambda value: 0,
        _probe_children=lambda task_id: ("t~gpu1", "t~gpu2"),
        _reconcile_probes=lambda task_id: reconciled.append(task_id),
    )
    request = SimpleNamespace(challenge_key=None)
    task = SimpleNamespace(value="t")

    def lost(*a, **k):
        raise RemoteLaneDown(b"link")

    monkeypatch.setattr(graph, "reconstruct_public_graph", lost)
    with pytest.raises(RemoteLaneDown):
        research_tasks.DirectDevelopmentTasksV3._graph_gpu_repeats(
            provider, task, request, None, None, b"", "VALIDATOR_OWN_GPU"
        )
    assert reconciled == [task]

    def device(*a, **k):
        raise WorkerFailure(WorkerCode.RUNTIME)

    monkeypatch.setattr(graph, "reconstruct_public_graph", device)
    assert research_tasks.DirectDevelopmentTasksV3._graph_gpu_repeats(
        provider, task, request, None, None, b"", "VALIDATOR_OWN_GPU"
    ) == (False, "graph_gpu_attempt_failed")


def test_a_settled_replay_takes_no_slot_even_when_every_slot_is_held(host):
    lane = _lane(host, slots=1, cpusets=("0-3",))
    with (
        remote_gpu_build.offered(lane),
        _op(),
        _op(
            settled=True, poll_s=0, sleep=lambda _: pytest.fail("a replay never waits")
        ) as replay,
    ):
        assert replay.lane is lane


def test_n_slots_wait_for_a_jax_memory_cap(host, monkeypatch):
    monkeypatch.setattr(remote_gpu_build, "SLOT_PRELUDE_RULED", False)
    with pytest.raises(ValueError, match="jax_memory_cap"):
        _lane(host, slots=2)
    assert _lane(host, slots=1).slots == 1


def test_the_shipped_lane_refuses_more_than_one_slot():
    assert remote_gpu_build.SLOT_PRELUDE_RULED is False


@pytest.mark.parametrize(
    ("local", "slots", "counts"),
    [(True, 1, True), (True, 2, False), (False, 1, False), (False, 2, False)],
)
def test_a_wall_counts_only_on_a_one_slot_local_lane(host, local, slots, counts):
    lane = _lane(host, local=local, slots=slots, cpusets=("0-3", "4-7")[:slots])
    assert remote_gpu_build.wall_counts(remote_gpu_build.OpBinding(lane, 0)) is counts
    assert remote_gpu_build.wall_counts(None) is True


def test_the_watchdog_handoff_needs_no_operator_record(host):
    lane = _lane(host)
    binding = remote_gpu_build.OpBinding(lane, 1)
    raw = remote_gpu_build._handoff(binding)
    (
        host / remote_gpu_build.RECORD
    ).unlink()  # the operator's record changed after the op began
    back = remote_gpu_build._from_handoff(raw)
    assert back.slot == 1 and back.slot_dir == binding.slot_dir
    assert back.lane.device.digest == lane.device.digest and back.docker_host == HOST
    tampered = json.loads(raw)
    tampered["device"]["device_uuid"] = "GPU-other-0000"
    assert remote_gpu_build._from_handoff(json.dumps(tampered)) is None
    assert (
        remote_gpu_build._from_handoff(json.dumps({**json.loads(raw), "slot": 7}))
        is None
    )


def test_a_lane_edited_after_start_with_the_same_device_refuses(host):
    values = _install(host)
    lane = remote_gpu_build.door_lane("electric-motor-magnetics", "1.8", values=values)
    remote_gpu_build.pin("electric-motor-magnetics", "1.8", lane)
    _install(host, cpusets=("0-3", "8-11"))  # same device record, other cores
    with (
        pytest.raises(RemoteLaneDown),
        remote_gpu_build.offered_for("electric-motor-magnetics", "1.8", values=values),
    ):
        pass


def test_the_prelude_is_never_placed_inside_a_docstring(host):
    """Line ends as the parser counts them: a docstring holding a form feed or a line separator does not move it."""
    lane = _lane(host, slots=2)
    source = '"""a\x0cb\u2028c"""\nx = 1\n'
    with remote_gpu_build.offered(lane), _op():
        changed = remote_gpu_build.with_slot_prelude(source)
    module = ast.parse(changed)
    assert ast.get_docstring(module, clean=False) == "a\x0cb\u2028c"
    assert ast.dump(module.body[1]) == ast.dump(
        ast.parse(remote_gpu_build.SLOT_PRELUDE).body[0]
    )


def test_only_a_python_program_can_carry_the_slot_cap(host):
    lane = _lane(host, slots=2)
    with remote_gpu_build.offered(lane), _op(), pytest.raises(RemoteLaneDown):
        remote_gpu_build.with_slot_prelude("x = 1\n", program_name="program.jl")
    one = _lane(host, slots=1, cpusets=("0-3",))
    with remote_gpu_build.offered(one), _op():
        assert (
            remote_gpu_build.with_slot_prelude("x\n", program_name="program.jl")
            == "x\n"
        )


# -- N > 1 with no cap ("memory": "shared"; Lead + owner, 16 Nov) -------------------------------------------------------------


def test_shared_slots_need_no_ruling_and_change_nothing_in_the_program_or_env(
    host, monkeypatch
):
    monkeypatch.setattr(remote_gpu_build, "SLOT_PRELUDE_RULED", False)
    with pytest.raises(ValueError, match="jax_memory_cap"):
        _lane(host, slots=4, cpusets=("0-3", "4-7", "8-11", "12-15"))  # capped: waits
    lane = _lane(
        host, slots=4, cpusets=("0-3", "4-7", "8-11", "12-15"), memory="shared"
    )
    assert lane.slots == 4 and lane.memory == "shared"
    source = '"""doc"""\nimport jax\n'
    with remote_gpu_build.offered(lane), _op() as binding:
        assert remote_gpu_build.slot_environment() == {}
        assert remote_gpu_build.with_slot_environment(_argv()) == _argv()
        assert remote_gpu_build.with_slot_prelude(source) == source
        assert remote_gpu_build.request_fields() == {
            "remote_gpu_slots": 4,
            "slot_memory": "shared",
        }
        handed = remote_gpu_build._from_handoff(remote_gpu_build._handoff(binding))
        assert handed.lane.memory == "shared"
    import dataclasses

    capped = dataclasses.replace(lane, memory="capped")
    assert remote_gpu_build.fingerprint(lane) != remote_gpu_build.fingerprint(capped)


def test_a_device_oom_on_a_shared_gpu_is_carbons_not_a_cpu_rebuild(host, monkeypatch):
    from carbon.development_session import research_carrier

    shared = _lane(
        host, slots=4, cpusets=("0-3", "4-7", "8-11", "12-15"), memory="shared"
    )
    one = _lane(host, slots=1, cpusets=("0-3",))
    oom = WorkerFailure(
        WorkerCode.RUNTIME,
        private_diagnostic=b"exit=1\nstderr:\nXlaRuntimeError: RESOURCE_EXHAUSTED: Out of memory",
    )

    def failing(ledger, **kwargs):
        raise oom

    monkeypatch.setattr(research_carrier, "_run_supervised", failing)
    monkeypatch.setattr(remote_gpu_build, "healthy", lambda binding=None: True)
    with remote_gpu_build.offered(shared), pytest.raises(RemoteLaneDown):
        research_carrier._run(
            None, identity="t~gpu1", accelerator="VALIDATOR_OWN_GPU", provenance="X"
        )
    with remote_gpu_build.offered(one), pytest.raises(WorkerFailure) as raised:
        research_carrier._run(
            None, identity="t~gpu1", accelerator="VALIDATOR_OWN_GPU", provenance="X"
        )
    assert type(raised.value) is WorkerFailure  # one build on the GPU: as before
    other = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\nValueError")
    assert not remote_gpu_build.shared_memory_exhausted(
        other,
        research_carrier._MEMORY_EXHAUSTED_MARKERS,
        remote_gpu_build.OpBinding(shared, 0),
    )
