"""The remote GPU build lane (`carbon.reconstruction.remote_gpu_build`; owner's order Mon 16 Nov 2026 via the Lead, TE3;
part 2, 17 Nov: on-demand boxes): a door's GPU BUILD ops run on a POOL of rented GPU boxes' ssh docker daemons in one of
N slots, inputs mirrored there, the door keeps the ledger and computes the state digest, and a link or GPU fault is
Carbon's (FAILED_INFRA), never the miner's. Boxes are box files read at every op: added, drained, refused, down or proven
without a restart. No ssh, no docker, no GPU: every process boundary is faked, and every device UUID is synthetic.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import threading
from pathlib import Path

import accelerator_host
import pytest

from carbon.development_session.profile import canonical
from carbon.reconstruction import (
    accelerators,
    host_execution,
    remote_gpu_build,
    remote_lane,
)
from carbon.reconstruction.host_inventory import tagged_sha256
from carbon.reconstruction.remote_lane import RemoteLaneDown
from carbon.reconstruction.worker import accelerator_runtime
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

HOST = "ssh://carbon-build@a100-1.example:2222"
STAGE = "/var/lib/carbon/doors"
KIND = "NVIDIA A100-SXM4-80GB"
UUID = "GPU-a1a1a1a1-0000-1111-2222-333333333333"
BUILD = "direct-" + "a" * 64 + "-build"
IMAGE = "sha256:" + "c" * 64
BOX = "a100-1"


def _host_key(docker_host=HOST, seed=0):
    """A well-formed ed25519 known_hosts line for ``docker_host`` (a synthetic key)."""
    _, name, port = remote_lane.parse_docker_host(docker_host)
    blob = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes(
        (seed + i) % 256 for i in range(32)
    )
    where = name if port == 22 else f"[{name}]:{port}"
    return f"{where} ssh-ed25519 " + base64.b64encode(blob).decode()


def _device(kind=KIND, uuid=UUID):
    return accelerator_host.document(
        "hosted_instance",
        device_uuid=uuid,
        device_kind=kind,
        device_memory_mib=81920,
        compute_capability="8.0",
    )


def box_document(name=BOX, *, kind=KIND, uuid=UUID, docker_host=HOST, images=(IMAGE,)):
    """A box file as `gpu_box_up.py door` writes it on PASS (`gpu_box_up.box_document`)."""
    device = _device(kind, uuid)
    return {
        "schema": remote_gpu_build.BOX_SCHEMA,
        "name": name,
        "docker_host": docker_host,
        "stage_root": STAGE,
        "slot_cpusets": list(remote_gpu_build.BOX_SLOT_CPUSETS),
        "device": device,
        "device_digest": tagged_sha256(canonical(device)),
        "driver_version": "580.65.06",
        "host_key": _host_key(docker_host),
        "images": list(images),
        "tree_commit": "0" * 40,
        "class_check_image_id": IMAGE,
        "class_check": {
            "case_digests": {},
            "class_record_sha256": "sha256:" + "1" * 64,
            "class_ops_record_sha256": "sha256:" + "2" * 64,
        },
        "check_output_sha256": "sha256:" + "3" * 64,
        "check_ops_record_sha256": "sha256:" + "4" * 64,
        "admitted_unix": 1763300000,
    }


def write_box(root, document=None, *, name=None, mode=0o600, **kwargs):
    """Install one box file in the door's boxes directory (0700), as the door phase does on PASS."""
    document = box_document(**kwargs) if document is None else document
    name = document["name"] if name is None else name
    directory = root / remote_gpu_build.BOXES_DIR
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    path = directory / f"{name}.json"
    if path.exists():
        path.chmod(0o600)
    path.write_text(json.dumps(document, indent=1, sort_keys=True))
    path.chmod(mode)
    return path


def _values(root, *, slots=2, memory=None, row=True, kind=KIND):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    values = root / "values.json"
    values.write_text(
        json.dumps(
            {
                "schema": remote_gpu_build.VALUES_SCHEMA,
                "rows": (
                    {
                        "electric-motor-magnetics 1.8": {
                            "device_kind": kind,
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
    """A synthetic operator install: one box file (or, ``local``, the old record's local slot lane with this host's own
    device record) and a values row naming the class. ``cpusets`` are a local lane's (a box's are always 4 x 4).
    """
    root.mkdir(
        mode=0o700, parents=True, exist_ok=True
    )  # the host root is private, as installed
    if local:
        (root / remote_gpu_build.RECORD).write_text(
            json.dumps(
                {
                    "schema": remote_gpu_build.SCHEMA,
                    "lanes": [
                        {
                            "docker_host": None,
                            "stage_root": None,
                            "slot_cpusets": list(cpusets),
                        }
                    ],
                }
            )
        )
        accelerator_host.install(root, _device(kind))
    else:
        write_box(root, kind=kind)
    if values is not None:
        return values
    return _values(root, slots=slots, memory=memory, row=row)


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "accelerators"
    monkeypatch.setattr(accelerator_runtime, "HOST_ROOT", root)
    monkeypatch.setattr(remote_gpu_build, "_docker_binary", lambda: "/usr/bin/docker")
    monkeypatch.setattr(remote_gpu_build, "_ssh_binary", lambda: "/usr/bin/ssh")
    # the slot machinery under test; the shipped value (False) refuses N > 1: test_n_slots_wait_for_a_jax_memory_cap
    monkeypatch.setattr(remote_gpu_build, "SLOT_PRELUDE_RULED", True)
    monkeypatch.setattr(remote_gpu_build, "_ENVIRONMENT_BINDING", [])
    monkeypatch.setattr(remote_gpu_build, "_PINNED", {})
    return root


def _pool(host, values):
    return remote_gpu_build.door_pool("electric-motor-magnetics", "1.8", values=values)


def _lane(host, **kwargs):
    """The one machine an install describes (its box, or its local lane), offered as a FIXED machine."""
    values = _install(host, **kwargs)
    pool = _pool(host, values)
    if pool.local is not None:
        return pool.local
    return remote_gpu_build.read_box(
        host / remote_gpu_build.BOXES_DIR / f"{BOX}.json",
        kind=pool.kind,
        slots=pool.slots,
        memory=pool.memory,
        root=host,
    )


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
    host.mkdir(parents=True)
    # a row with neither a boxes directory nor a local lane: today's path (this host's own GPU)
    assert _pool(host, _values(host)) is None
    values = _install(host, row=False)
    assert _pool(host, values) is None


def test_the_checked_in_values_file_names_motor_and_cooling_1_8_on_the_a100():
    """Lead, 16 Nov (for V2's read): Motor 1.8 builds on the Lambda A100 40GB, 4 shared slots to start; Cooling 1.8
    (C5g, 20 Nov) on the same class and shape. A door uses it only with the operator's boxes directory (or a local slot
    lane) installed."""
    document = json.loads(remote_gpu_build.VALUES.read_bytes())
    assert document["schema"] == remote_gpu_build.VALUES_SCHEMA
    assert set(document["rows"]) == {
        "electric-motor-magnetics 1.8",
        "chip-cold-plate 1.8",
        "electric-motor-magnetics 1.9",
    }
    # OWNER-RTX6000ADA-BUILD-CLASS-01 under INFRA-17 (21 Nov 2026): Motor 1.9 opens on the Lium RTX 6000 Ada, slots 4 at
    # the first admission (6 only after an S7 read on the real door; never 7 without it), shared memory
    assert remote_gpu_build.values_row("electric-motor-magnetics", "1.9") == {
        "device_kind": "NVIDIA RTX 6000 Ada Generation",
        "slots": 4,
        "memory": "shared",
    }
    # Lead pick (A), 20 Nov 2026 (owner's line replacing C8 / G19): 4 shared slots per box, same per-slot envelope
    assert remote_gpu_build.values_row("electric-motor-magnetics", "1.8") == {
        "device_kind": "NVIDIA A100-SXM4-40GB",
        "slots": 4,
        "memory": "shared",
    }
    assert remote_gpu_build.values_row("electric-motor-magnetics", "1.4") is None
    # owner, 17 Nov 2026: 7 slots of 4 vCPUs on the 30-vCPU Lambda A100 box
    assert len(remote_gpu_build.BOX_SLOT_CPUSETS) == 7
    assert remote_gpu_build.BOX_SLOT_CPUSETS[-1] == "24-27"


def test_a_well_formed_install_is_a_door_lane(host):
    lane = _lane(host)
    assert (
        lane.slots == 2
        and lane.device.device_uuid == UUID
        and lane.device.device_kind == KIND
    )
    assert lane.spec.slot_cpusets == remote_gpu_build.BOX_SLOT_CPUSETS
    assert lane.spec.docker_host == HOST and lane.spec.name == BOX
    assert lane.spec.host_key == _host_key() and lane.spec.images == (IMAGE,)
    assert Path(lane.lane_dir) == host / remote_gpu_build.BOX_DIR.format(name=BOX)


@pytest.mark.parametrize(
    "change",
    [
        {"docker_host": "tcp://10.0.0.2:2375"},
        {"docker_host": HOST, "stage_root": STAGE},  # a rented box is a box file now
        {"stage_root": "/"},
        {"slot_cpusets": []},
        {"slot_cpusets": ["0-3", "3-6"]},  # overlapping
        {"slot_cpusets": ["0-3", "4-5"]},  # unequal
        {"slot_cpusets": ["0-1"] * 5},
        {"extra": 1},
    ],
)
def test_a_malformed_record_refuses(host, change):
    _install(host, local=True)
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


@pytest.mark.parametrize("local", [False, True])
def test_a_device_of_another_kind_refuses(host, local):
    with pytest.raises(ValueError, match="device_kind"):
        _lane(host, kind="NVIDIA GeForce RTX 4090", local=local)


def test_more_slots_than_cpusets_refuses(host):
    with pytest.raises(ValueError, match="slots_exceed"):
        _lane(host, slots=3, local=True)
    with pytest.raises(ValueError, match="slots_exceed"):
        _lane(host, slots=5)  # a box has 4 slots of 4 cores


def test_a_missing_device_record_refuses(host):
    values = _install(host, local=True)
    (host / "host-device.json").unlink()
    with pytest.raises(ValueError, match="device_record"):
        _pool(host, values)


def test_a_lane_that_broke_since_start_is_carbons_at_the_build(host):
    values = _install(host, local=True)
    (host / "host-device.json").unlink()
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
        ("task-1~shadow", "MINER_OWN_GPU", "X", False, True),
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
        ("task-1~shadow2", "VALIDATOR_OWN_GPU", "X", False, False),
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
        # today's count on a 4-core slot: exactly 2 of its cores (the quota a default worker is created with)
        assert host_execution.resolve_cpuset(logical_cpus=16, count=2) == ",".join(
            str(core) for core in host_execution.parse_cpuset(binding.cpuset)[:2]
        )
        # a sized worker of fewer CPUs than the slot runs on exactly its own count of the slot's cores, the lowest
        # (switch 5); more CPUs than the slot has refuse
        assert host_execution.resolve_cpuset(logical_cpus=16, count=3) == ",".join(
            str(core) for core in host_execution.parse_cpuset(binding.cpuset)[:3]
        )
        with pytest.raises(WorkerFailure):
            host_execution.resolve_cpuset(logical_cpus=16, count=5)
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
    text = remote_gpu_build.wrapper_text(
        HOST, "/home/carbon", "/usr/bin/docker", "/x/box-a/bin"
    )
    assert "DOCKER_HOST=ssh://carbon-build@a100-1.example:2222\n" in text
    assert "PATH=/x/box-a/bin:/usr/local/bin:/usr/bin:/bin\n" in text
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
        remote_gpu_build,
        "_box_run",
        lambda binding, script, **kwargs: calls.append((script, binding, kwargs)),
    )
    remote_gpu_build.mirror(Path(STAGE) / "x" / "input")
    remote_gpu_build.discard(Path(STAGE) / "x" / "input")
    assert calls == []
    with remote_gpu_build.offered(lane), _op() as binding:
        remote_gpu_build.mirror(Path(STAGE) / "x" / "input")
        remote_gpu_build.discard(Path(STAGE) / "x" / "input")
    assert len(calls) == 2 and calls[0][1] is binding and calls[1][1] is binding
    assert "tar -x" in calls[0][0] and "feed" in calls[0][2]
    assert "find" in calls[1][0] and "/var/lib/carbon/doors/x/input" in calls[1][0]
    # only paths under the box's stage root
    with pytest.raises(RemoteLaneDown):
        remote_lane._remote_path(Path("/etc/passwd"), binding)
    # a gone box (its file removed) is never contacted
    remote_gpu_build.discard(
        Path(STAGE) / "x" / "input", remote_gpu_build.OpBinding(lane, 0, gone=True)
    )
    assert len(calls) == 2


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


def test_at_most_n_carbon_containers_share_the_device(host, monkeypatch):
    monkeypatch.setattr(remote_gpu_build, "CROWDED_WAIT_SECONDS", 0)
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
    monkeypatch.setattr(remote_gpu_build, "link_up", lambda b: True)
    monkeypatch.setattr(remote_gpu_build, "gpu_present", lambda b: True)
    assert remote_gpu_build.retyped(error, binding) is None
    monkeypatch.setattr(remote_gpu_build, "gpu_present", lambda b: False)
    down = remote_gpu_build.retyped(error, binding)
    assert isinstance(down, RemoteLaneDown) and down.code is WorkerCode.UNAVAILABLE
    monkeypatch.setattr(remote_gpu_build, "link_up", lambda b: False)
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


def test_an_unobserved_wall_stop_on_the_lane_is_never_the_candidates(host):
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
            "box": BOX,  # the box name, for the audit and for recovery
        }
    }
    recovered = remote_gpu_build.recorded(fields)
    assert (
        recovered.slot == binding.slot
        and recovered.lane.device.digest == lane.device.digest
        and not recovered.gone
    )
    with remote_gpu_build.bound(recovered):
        assert accelerator_runtime.host_device().digest == lane.device.digest
    assert remote_gpu_build.recorded({}) is None
    for broken in (
        {"remote_gpu_build": {"docker_host": HOST}},
        {"remote_gpu_build": {**fields["remote_gpu_build"], "slot": 9}},
        {"remote_gpu_build": {**fields["remote_gpu_build"], "box": "../x"}},
        {"remote_gpu_build": {**fields["remote_gpu_build"], "docker_host": "tcp://x"}},
    ):
        with pytest.raises(ValueError):
            remote_gpu_build.recorded(broken)
    # another daemon than the box copy names: never contacted (gone), never guessed
    other = remote_gpu_build.recorded(
        {
            "remote_gpu_build": {
                **fields["remote_gpu_build"],
                "docker_host": "ssh://x@other",
            }
        }
    )
    assert other.gone and other.lane.device is None


# -- a local slot lane (the GPUYard 4090: one design for both) --------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [{"docker_host": HOST}, {"stage_root": STAGE}],  # one without the other
)
def test_a_half_local_record_refuses(host, change):
    _install(host, local=True)
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
        remote_gpu_build, "link_up", lambda b: pytest.fail("a local lane has no link")
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


def test_a_class_that_differs_from_the_one_bound_at_start_refuses(host, monkeypatch):
    monkeypatch.setattr(remote_gpu_build, "_PINNED", {})
    values = _install(host)
    remote_gpu_build.pin(
        "electric-motor-magnetics", "1.8", None
    )  # started without a pool
    with (
        pytest.raises(RemoteLaneDown),
        remote_gpu_build.offered_for("electric-motor-magnetics", "1.8", values=values),
    ):
        pass
    pool = _pool(host, values)
    remote_gpu_build.pin("electric-motor-magnetics", "1.8", pool)
    with remote_gpu_build.offered_for(
        "electric-motor-magnetics", "1.8", values=values
    ) as offered:
        assert offered == pool and offered.kind == KIND
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
    # a remote lane defers to the box's own records (CV-Motor L12624: `remote_lane.wall_stop_observable` + the box guard)
    [(True, 1, True), (True, 2, False), (False, 1, True), (False, 2, True)],
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
        host / remote_gpu_build.BOXES_DIR / f"{BOX}.json"
    ).unlink()  # the box was drained after the op began
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


def test_a_class_edited_after_start_refuses_and_a_box_edit_needs_no_restart(host):
    values = _install(host)
    remote_gpu_build.pin("electric-motor-magnetics", "1.8", _pool(host, values))
    # a box swapped for another (other address, other GPU): the class is the same, the door goes on
    write_box(
        host,
        docker_host="ssh://carbon-build@a100-2.example",
        uuid="GPU-b2b2b2b2-0000-1111-2222-333333333333",
    )
    with (
        remote_gpu_build.offered_for("electric-motor-magnetics", "1.8", values=values),
        _op() as binding,
    ):
        assert binding.docker_host == "ssh://carbon-build@a100-2.example"
    _values(host, slots=3)  # the class's slots edited after start
    with (
        pytest.raises(RemoteLaneDown),
        remote_gpu_build.offered_for("electric-motor-magnetics", "1.8", values=values),
    ):
        pass


# -- CV-Motor L12624 on a remote GPU build slot (TE-B 8b20c190's rule, read on the GPU box) ------------------------------


class _AgeCLI:
    """The op's CLI as the box-clock read sees it: ``docker exec`` prints the program's age on the box."""

    def __init__(self, age):
        self.age, self.calls = age, []

    def run(self, arguments, timeout=30, accepted=(0,)):
        from types import SimpleNamespace

        self.calls.append(arguments)
        return SimpleNamespace(stdout=self.age.encode(), returncode=0, stderr=b"")


def _remote_wall(age, *, quiet, link=True, monkeypatch, host, binding_seen=None):
    """A remote GPU op's wall stop read through `_candidate_resource_stop`: the program ran 100 s of a 50 s wall."""
    import time

    from carbon.development_session import research_carrier

    lane = _lane(host, slots=1, cpusets=("0-3",))
    links = []
    monkeypatch.setattr(
        remote_gpu_build,
        "link_up",
        lambda lane=None, **k: links.append(lane) or link,
    )
    started = time.monotonic() - 100
    error = WorkerFailure(
        WorkerCode.DEADLINE, private_diagnostic=b"stream command timed out"
    )
    cli = _AgeCLI(age)
    factory = lambda binding: (lambda: quiet, lambda: None)
    token = research_carrier.REMOTE_BUILD_GUARD.set(factory)
    try:
        with (
            remote_gpu_build.offered(lane),
            _op() as binding,
            research_carrier._remote_build_guarded(binding),
        ):
            stop = research_carrier._candidate_resource_stop(
                cli,
                error,
                container_name="carbon-d4-" + "a" * 24,
                launch_digest="sha256:" + "d" * 64,
                image_id="sha256:" + "e" * 64,
                program_started=started,
                box_deadline=time.monotonic() + 30,
                program_timeout=50,
                setup_seconds=0,
                memory_limit_bytes=None,
                deadline=time.monotonic() + 1,
                observation={
                    "status": "OBSERVED",
                    "state": {"oom_killed": False},
                    "memory": None,
                },
                accelerated=True,
            )
    finally:
        research_carrier.REMOTE_BUILD_GUARD.reset(token)
    if binding_seen is not None:
        binding_seen.extend(links)
    return stop, binding, cli


def test_a_remote_wall_stop_counts_on_its_box_clock_quiet_box_and_live_link(
    host, monkeypatch
):
    seen = []
    stop, binding, cli = _remote_wall(
        "100.000", quiet=True, monkeypatch=monkeypatch, host=host, binding_seen=seen
    )
    assert stop is not None and stop[0] is WorkerCode.DEADLINE
    assert seen == [binding]  # the link checked is the GPU box's
    assert (
        cli.calls and cli.calls[0][0] == "exec"
    )  # the age read inside the container, on the box


@pytest.mark.parametrize(
    ("age", "quiet", "link"),
    [
        ("100.000", False, True),  # (b) a neighbour or foreign GPU compute on the box
        ("100.000", True, False),  # (c) the link is down at the stop
        (
            "10.000",
            True,
            True,
        ),  # (a) the box's clock says the program had not run its wall
        ("none", True, True),  # (a) no program running there (or ambiguous)
        (
            "999.000",
            True,
            True,
        ),  # (a) an age the controller could not have seen: not this program's clock
    ],
)
def test_anything_else_on_a_remote_box_is_carbons(host, monkeypatch, age, quiet, link):
    stop, _, _ = _remote_wall(
        age, quiet=quiet, link=link, monkeypatch=monkeypatch, host=host
    )
    assert stop is None


def test_a_remote_gpu_op_is_guarded_by_its_box_and_never_quiet_without_a_guard(
    host, monkeypatch
):
    from carbon.development_session import research_carrier

    lane = _lane(host, slots=1, cpusets=("0-3",))
    stopped, seen = [], []

    def run(ledger, **kwargs):
        seen.append(research_carrier._build_wall_quiet())
        return "done"

    monkeypatch.setattr(research_carrier, "_run_supervised", run)
    door_guard = research_carrier.BUILD_WALL_GUARD.set(
        lambda: True
    )  # this host is quiet...
    try:
        with remote_gpu_build.offered(lane):
            research_carrier._run(
                None, identity=BUILD, accelerator="VALIDATOR_OWN_GPU", provenance="X"
            )  # ...but no box guard installed: never quiet
            token = research_carrier.REMOTE_BUILD_GUARD.set(
                lambda binding: (
                    lambda: binding.lane is lane,
                    lambda: stopped.append(1),
                )
            )
            try:
                research_carrier._run(
                    None,
                    identity=BUILD,
                    accelerator="VALIDATOR_OWN_GPU",
                    provenance="X",
                )
            finally:
                research_carrier.REMOTE_BUILD_GUARD.reset(token)
            research_carrier._run(  # an op that stays here keeps this host's guard
                None, identity="direct-" + "a" * 64 + "-inference", provenance="X"
            )
    finally:
        research_carrier.BUILD_WALL_GUARD.reset(door_guard)
    assert seen == [False, True, True] and stopped == [1]


def test_the_build_round_samples_a_remote_gpu_ops_own_box(host, monkeypatch):
    import time

    from carbon.challenge_validator import host_quiet, lean_recipe
    from carbon.development_session import research_carrier

    lane = _lane(host, slots=1, cpusets=("0-3",))
    binding = remote_gpu_build.OpBinding(lane, 0)
    counts = {"containers": 1, "gpu": 0}
    watched = []

    def counters(box):
        watched.append(box)
        return (lambda: counts["containers"]), (lambda: counts["gpu"])

    monkeypatch.setattr(host_quiet, "box_counters", counters)
    monkeypatch.setattr(lean_recipe, "BUILD_PROBE_SECONDS", 0.01)
    with lean_recipe._build_wall_guard(
        None
    ):  # one build round, no claims: still installed
        factory = research_carrier.REMOTE_BUILD_GUARD.get()
        assert factory is not None
        quiet, stop = factory(binding)
        time.sleep(0.05)
        assert quiet() is True
        counts["containers"] = 2  # a neighbour slot's container on the box
        time.sleep(0.05)
        assert quiet() is False
        stop()
    assert watched == [binding]
    assert research_carrier.REMOTE_BUILD_GUARD.get() is None
    quiet, stop = None, None
    with lean_recipe._build_wall_guard(None):
        counts.update(containers=None, gpu=0)  # a sample the link could not deliver
        quiet, stop = research_carrier.REMOTE_BUILD_GUARD.get()(binding)
        time.sleep(0.05)
        assert quiet() is False
        stop()


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


def test_inside_a_remote_grade_round_a_gpu_slot_op_sees_only_its_own_machine(
    host, monkeypatch
):
    """A19 build rounds may hold a REMOTE grade lane: an op bound to a GPU slot never reaches the grade box (its
    daemon, its mirror, its link check), whether its slot is remote or this host's own.
    """
    from carbon.reconstruction import grade_lanes

    grade = grade_lanes.Lane(
        2, "0-3", str(host), "ssh://carbon-grade@grade-box.example", STAGE
    )
    for local, expected in ((False, HOST), (True, None)):
        lane = _lane(host, slots=1, cpusets=("0-3",), local=local)
        with grade_lanes.bound(grade):
            assert remote_lane.current() is grade
            with remote_gpu_build.offered(lane), _op():
                assert remote_lane.current() is None
                assert remote_lane.docker_host() == expected
                assert remote_lane.intent_fields() == {}
                links = []
                monkeypatch.setattr(
                    remote_gpu_build,
                    "link_up",
                    lambda lane=None, _seen=links, **k: _seen.append(lane) or True,
                )
                monkeypatch.setattr(
                    remote_lane,
                    "link_up",
                    lambda *a, **k: pytest.fail("the grade box's link is not read"),
                )
                remote_gpu_build.wall_stop_observable(
                    {"status": "OBSERVED"}, box_seconds=lambda: 100.0, needed=10
                )
                assert links == ([] if local else [remote_gpu_build.current_op()])
            assert remote_lane.current() is grade


def test_the_box_probe_stop_takes_no_more_samples(host, monkeypatch):
    import time

    from carbon.challenge_validator import host_quiet, lean_recipe

    lane = _lane(host, slots=1, cpusets=("0-3",))
    calls = []
    monkeypatch.setattr(
        host_quiet,
        "box_counters",
        lambda box: (
            (lambda: calls.append("c") or 1),
            (lambda: calls.append("g") or 0),
        ),
    )
    monkeypatch.setattr(lean_recipe, "BUILD_PROBE_SECONDS", 0.01)
    quiet, stop = lean_recipe._remote_gpu_build_guard(
        remote_gpu_build.OpBinding(lane, 0)
    )
    time.sleep(0.05)
    stop()
    time.sleep(0.05)
    before = len(calls)
    time.sleep(0.05)
    assert len(calls) == before and quiet() is True


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

    pool = _pool(host, _values(host, slots=4, memory="shared"))
    capped = dataclasses.replace(pool, memory="capped")
    assert remote_gpu_build.fingerprint(pool) != remote_gpu_build.fingerprint(capped)


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


# -- an uncounted wall stop's retry is an ordinary op (over-broad rules audit #7) ---------------------------------------------


def test_an_uncounted_wall_stops_retry_takes_any_free_slot_and_drains_no_box(host):
    """Over-broad rules audit #7, V2 timing ruling: the retry of a build whose wall stop was not counted is an ordinary
    op. Beside running ops on a multi-slot box it binds a free slot of that box at once and holds that slot only: no
    box gate, no alone mark, no box drained for it."""
    shared = _lane(host, slots=4, memory="shared")
    with remote_gpu_build.offered(shared), _op() as first, _op() as second:
        with _op() as retry:  # the same build again: its retry
            assert retry is not None and retry.lane.spec.name == BOX
            assert {first.slot, second.slot, retry.slot} == {0, 1, 2}
            # its own slot taken, the fourth still free: it holds no slot beyond its own
            assert remote_gpu_build._free_slots(shared) == 1
        assert remote_gpu_build._free_slots(shared) == 2
    written = {path.name for path in shared.pool_dir.rglob("*")}
    assert not written & {"alone", "alone.wanted", "gate.lock"}


def test_a_wall_counts_on_a_one_slot_local_lane_only_and_a_shared_one_owns_no_oom(
    host,
):
    """Over-broad rules audit #7, V2 timing ruling: no op holds a whole lane any more, so a local lane shared by more
    than one slot never counts a wall stop and a device memory exhaustion on it stays Carbon's; a one-slot local lane
    counts its wall and owns its memory, as a local GPU build's always did."""
    oom = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"RESOURCE_EXHAUSTED")
    markers = (b"RESOURCE_EXHAUSTED",)
    shared = _lane(host, local=True, slots=2, memory="shared")
    for slot in (0, 1):
        binding = remote_gpu_build.OpBinding(shared, slot)
        assert remote_gpu_build.wall_counts(binding) is False
        assert remote_gpu_build.shared_memory_exhausted(oom, markers, binding)
    one = _lane(host, local=True, slots=1, cpusets=("0-3",))
    binding = remote_gpu_build.OpBinding(one, 0)
    assert remote_gpu_build.wall_counts(binding) is True
    assert not remote_gpu_build.shared_memory_exhausted(oom, markers, binding)


@pytest.mark.parametrize("local", [False, True])
def test_a_build_round_gives_its_local_lane_back_only_for_an_op_on_the_remote_box(
    host, monkeypatch, tmp_path, local
):
    """Option A (Lead 17 Nov 2026), through the carrier: an op on a REMOTE GPU build box runs, and waits for its slot,
    with the round's local lane given back, and the next op holds a lane again; inference and a local slot lane's
    build keep the lane. A remote build that fails while its link is down stays Carbon's (`RemoteLaneDown`), with a
    lane held again before the error leaves the carrier."""
    pytest.importorskip("fcntl")
    import fcntl
    import os

    from carbon.challenge_validator.direct_intake import _WorkLock
    from carbon.development_session import research_carrier
    from carbon.reconstruction import grade_lanes

    lock_dir = tmp_path / "locks"
    lock_dir.mkdir(mode=0o700)
    work = _WorkLock(lock_dir, poll_s=0.02, lanes=("0-3", "4-7"))
    work.overlap_kinds = True

    def lanes_free():
        free = []
        for index in (0, 1):
            fd = os.open(
                lock_dir / grade_lanes.lane_lock_name(index),
                os.O_RDWR | os.O_CREAT,
                0o600,
            )
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
                free.append(True)
            except BlockingIOError:
                free.append(False)
            finally:
                os.close(fd)
        return all(free)

    seen = []

    def supervised(ledger, **kwargs):
        seen.append(lanes_free())
        if kwargs.get("fail"):
            raise WorkerFailure(WorkerCode.RUNTIME)
        return "ok"

    monkeypatch.setattr(research_carrier, "_run_supervised", supervised)
    inference = "direct-" + "a" * 64 + "-inference"
    lane = _lane(host, local=local)
    with work.taking("advance"), remote_gpu_build.offered(lane):
        research_carrier._run(
            None, identity=BUILD, accelerator="VALIDATOR_OWN_GPU", provenance="X"
        )
        assert not lanes_free()
        research_carrier._run(None, identity=inference, provenance="X")
        monkeypatch.setattr(remote_gpu_build, "healthy", lambda binding=None: False)
        with pytest.raises((RemoteLaneDown, WorkerFailure)) as raised:
            research_carrier._run(
                None,
                identity=BUILD,
                accelerator="VALIDATOR_OWN_GPU",
                provenance="X",
                fail=True,
            )
        assert not lanes_free() and grade_lanes.current() is not None
    if local:
        # this host's own GPU: the build keeps its lane (its container runs here)
        assert seen == [False, False, False]
    else:
        assert type(raised.value) is RemoteLaneDown
        assert seen == [True, False, True]


def test_a_build_round_waits_for_a_busy_remote_slot_without_its_local_lane(
    host, monkeypatch, tmp_path
):
    """Option A: the round's local lane goes back BEFORE the op waits for a slot on the remote box, and a lane is held
    again only after the op (and its slot) has ended."""
    pytest.importorskip("fcntl")
    import fcntl
    import os
    import time

    from carbon.challenge_validator.direct_intake import _WorkLock
    from carbon.development_session import research_carrier
    from carbon.reconstruction import grade_lanes

    monkeypatch.setattr(remote_gpu_build, "POLL_S", 0.02)
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir(mode=0o700)
    work = _WorkLock(lock_dir, poll_s=0.02, lanes=("0-3", "4-7"))
    work.overlap_kinds = True

    def lanes_free():
        for index in (0, 1):
            fd = os.open(
                lock_dir / grade_lanes.lane_lock_name(index),
                os.O_RDWR | os.O_CREAT,
                0o600,
            )
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                return False
            finally:
                os.close(fd)
        return True

    lane = _lane(host, slots=1, cpusets=("0-3",))
    occupied, free_slot = threading.Event(), threading.Event()

    def neighbour():
        with remote_gpu_build.offered(lane), _op():
            occupied.set()
            assert free_slot.wait(10)

    ran, done = [], threading.Event()
    monkeypatch.setattr(
        research_carrier, "_run_supervised", lambda ledger, **k: ran.append(1) or "ok"
    )

    def build_round():
        with work.taking("advance"), remote_gpu_build.offered(lane):
            research_carrier._run(
                None, identity=BUILD, accelerator="VALIDATOR_OWN_GPU", provenance="X"
            )
            done.set()

    other = threading.Thread(target=neighbour, daemon=True)
    other.start()
    assert occupied.wait(5)
    from carbon.challenge_validator import direct_intake

    # the round's own release, not a lock poll: a poll could run before the round has taken its lane at all
    real_release, gave_back = direct_intake._Taking.release, threading.Event()

    def release(taking):
        real_release(taking)
        gave_back.set()

    monkeypatch.setattr(direct_intake._Taking, "release", release)
    builder = threading.Thread(target=build_round, daemon=True)
    builder.start()
    assert gave_back.wait(5)
    time.sleep(0.2)  # the op now waits for the busy slot
    assert lanes_free() and ran == []  # waiting for the slot, its lane already back
    free_slot.set()
    assert done.wait(5) and ran == [1]
    builder.join(5)
    other.join(5)
    assert lanes_free()


# -- on-demand boxes (owner, 17 Nov: add, swap or drop a box with no migration, no restart, no per-box door record) ------


def _offer(host, values=None):
    values = _values(host) if values is None else values
    return remote_gpu_build.offered_for(
        "electric-motor-magnetics", "1.8", values=values
    )


def _boxes_dir(host):
    return host / remote_gpu_build.BOXES_DIR


def test_the_pool_is_read_at_every_op_with_no_restart(host):
    host.mkdir(parents=True)
    _boxes_dir(host).mkdir(mode=0o700)
    values = _values(host)
    remote_gpu_build.pin("electric-motor-magnetics", "1.8", _pool(host, values))
    with _offer(host, values), pytest.raises(RemoteLaneDown) as raised, _op():
        pass
    # no eligible box: Carbon's at once (FAILED_INFRA, never charged), never a wait
    assert raised.value.code is WorkerCode.UNAVAILABLE
    assert raised.value.private_diagnostic == b"remote_gpu_build_no_box"
    write_box(host)  # gpu_box_up's door phase passed: the file appears
    with _offer(host, values), _op() as binding:
        assert binding.lane.spec.name == BOX and binding.docker_host == HOST
    write_box(
        host, box_document("a100-2", docker_host="ssh://carbon-build@a100-2.example")
    )
    names = {box.spec.name for box in remote_gpu_build.boxes(_pool(host, values))}
    assert names == {BOX, "a100-2"}
    # the class-check output files beside a box file are not boxes
    (_boxes_dir(host) / f"{BOX}.class-check.json").write_text("{}")
    (_boxes_dir(host) / f"{BOX}.class-check.json").chmod(0o600)
    assert len(remote_gpu_build.boxes(_pool(host, values))) == 2


def test_a_pool_with_no_box_up_builds_on_the_cpu(host):
    """Zero boxes (Lead + owner, 17 Nov): the graph builds on the CPU (`no_machine`), so every box may be released."""
    host.mkdir(parents=True)
    _boxes_dir(host).mkdir(mode=0o700)
    values = _values(host)
    # nothing offered: never "no machine" (a door with no pool calls as before)
    assert remote_gpu_build.no_machine() is False
    with _offer(host, values):
        assert remote_gpu_build.no_machine() is True
    write_box(host)
    with _offer(host, values):
        assert remote_gpu_build.no_machine() is False
        lane = _lane_named(host, values, BOX)
        remote_gpu_build.mark_down(lane, b"lost")
        # the only box is down: no machine up now
        assert remote_gpu_build.no_machine() is True
        remote_gpu_build.clear_down(lane)
        assert remote_gpu_build.no_machine() is False
    (_boxes_dir(host) / f"{BOX}.json").unlink()  # drained
    with _offer(host, values):
        assert remote_gpu_build.no_machine() is True
    # a withheld build keeps its own refusal (`op`): never sent to the CPU from here
    with remote_gpu_build.offered_for(
        "electric-motor-magnetics", "1.8", values=values, withhold=True
    ):
        assert remote_gpu_build.no_machine() is False


def test_the_door_sizes_its_build_rounds_for_the_most_boxes(host):
    host.mkdir(parents=True)
    values = _values(host, slots=4, memory="shared")
    assert (
        remote_gpu_build.door_build_slots(
            "electric-motor-magnetics", "1.8", values=values
        )
        == 0
    )
    _boxes_dir(host).mkdir(mode=0o700)
    # no box up yet: still sized for the most boxes (they come without a restart)
    assert (
        remote_gpu_build.door_build_slots(
            "electric-motor-magnetics", "1.8", values=values
        )
        == 4 * remote_gpu_build.MAX_BOXES
    )
    assert remote_gpu_build.door_build_slots("other", "1.0", values=values) == 0


def test_a_local_slot_lane_adds_no_build_rounds(host):
    values = _install(host, local=True)
    assert (
        remote_gpu_build.door_build_slots(
            "electric-motor-magnetics", "1.8", values=values
        )
        == 0
    )


def test_an_op_offered_a_box_pool_runs_off_this_host(host):
    """Option A's lane release reads the offer: a pool of boxes only is off this host; a pool that also holds this
    host's GPU lane, or nothing offered, is not."""
    assert remote_gpu_build.offered_off_host() is False
    host.mkdir(parents=True)
    _boxes_dir(host).mkdir(mode=0o700)
    values = _values(host)
    with _offer(host, values):
        assert remote_gpu_build.offered_off_host() is True
    with remote_gpu_build.offered_for(
        "electric-motor-magnetics", "1.8", values=values, withhold=True
    ):
        assert remote_gpu_build.offered_off_host() is False


def test_a_pool_with_this_host_s_lane_keeps_the_round_s_lane(host):
    values = _install(host, local=True)
    _boxes_dir(host).mkdir(mode=0o700)
    with _offer(host, values):
        assert remote_gpu_build.offered_off_host() is False


def test_a_box_admitted_with_another_image_is_skipped_never_refused(host):
    """After a door switches its graph GPU image, a box admitted with the earlier one takes none of its ops (no
    refusal), so with no box admitted with the new image the graph builds on the CPU (`no_machine`).
    """
    values = _install(host)
    admitted = _lane_named(host, values, BOX).spec.images
    with remote_gpu_build.offered_for(
        "electric-motor-magnetics", "1.8", values=values, image_id=admitted[0]
    ):
        assert remote_gpu_build.no_machine() is False
        with _op() as binding:
            assert binding.lane.spec.name == BOX
    with remote_gpu_build.offered_for(
        "electric-motor-magnetics", "1.8", values=values, image_id="sha256:" + "e" * 64
    ):
        assert remote_gpu_build.no_machine() is True
        with pytest.raises(RemoteLaneDown) as raised, _op():
            pass
        assert raised.value.private_diagnostic == b"remote_gpu_build_no_box"
    assert (_boxes_dir(host) / f"{BOX}.json").exists()


def test_a_box_link_uses_the_key_its_box_file_names_and_only_it(host, monkeypatch):
    """Live 116, 18 Nov 2026: a replacement box at a new address got "Permission denied (publickey)" for hours (only a
    hand-written ssh config block named the old address's key). A box file's ``ssh_key`` goes into every link to it,
    with IdentitiesOnly; a box file without one is linked as before; a malformed one is no box.
    """
    host.mkdir(parents=True)
    values = _values(host)
    key = str(host / "lane_key")
    write_box(host, {**box_document(), "ssh_key": key})
    (box,) = remote_gpu_build.boxes(_pool(host, values))
    shim = remote_gpu_build.ssh_shim_text(box, "/usr/bin/ssh")
    assert f"-i {key} -o IdentitiesOnly=yes" in shim
    home = host / "home"
    monkeypatch.setenv("HOME", str(home))
    write_box(host, box_document())
    (box,) = remote_gpu_build.boxes(_pool(host, values))
    assert "-i " not in remote_gpu_build.ssh_shim_text(box, "/usr/bin/ssh")
    # a box file without one: the door's lane key when present (Lead, 18 Nov 2026)
    default = home / remote_gpu_build.DEFAULT_LANE_KEY
    default.parent.mkdir(parents=True)
    default.write_text("key")
    shim = remote_gpu_build.ssh_shim_text(box, "/usr/bin/ssh")
    assert f"-i {default} -o IdentitiesOnly=yes" in shim
    write_box(host, {**box_document(), "ssh_key": "relative/key"})
    assert remote_gpu_build.boxes(_pool(host, values)) == ()


def test_a_box_passed_over_is_logged_with_why_once_per_change(host, monkeypatch):
    """Live 116, 18 Nov 2026: an admitted A100 ran no build for hours and nothing said why. Each box passed over is
    logged with its reason once per change (diagnostics only: the op's machine is unchanged), and logged kept again.
    """
    from carbon.battery import intake

    lines = []
    monkeypatch.setattr(
        intake, "log", lambda event, **fields: lines.append((event, fields))
    )
    monkeypatch.setattr(remote_gpu_build, "_SKIPPED", {})
    values = _install(host)
    admitted = _lane_named(host, values, BOX).spec.images
    other = "sha256:" + "e" * 64
    for _ in range(2):
        with remote_gpu_build.offered_for(
            "electric-motor-magnetics", "1.8", values=values, image_id=other
        ):
            assert remote_gpu_build.no_machine() is True
    skipped = [f for e, f in lines if e == "remote_gpu_build_box_skipped"]
    assert skipped == [{"box": BOX, "reason": "image_not_admitted"}]
    with (
        remote_gpu_build.offered_for(
            "electric-motor-magnetics", "1.8", values=values, image_id=admitted[0]
        ),
        _op() as binding,
    ):
        assert binding.lane.spec.name == BOX
    assert ("remote_gpu_build_box_kept", {"box": BOX}) in lines
    # a malformed box file is named, never silently dropped
    (_boxes_dir(host) / "broken.json").write_text("{}")
    (_boxes_dir(host) / "broken.json").chmod(0o600)
    remote_gpu_build.boxes(_pool(host, values))
    assert any(
        e == "remote_gpu_build_box_skipped" and f["box"] == "broken" for e, f in lines
    )


class _Stop(Exception):
    pass


def _waits(limit):
    seen = []

    def check():
        seen.append(1)
        if len(seen) > limit:
            raise _Stop

    return seen, check


@pytest.mark.parametrize("live", [True, False])
def test_a_pool_op_waits_behind_live_builds_past_the_slot_bound(
    host, monkeypatch, live
):
    """Build rounds are sized for the pool's most boxes: an op behind live builds on the boxes up waits (progress), and
    only slots no live op holds keep the wall-clock bound (`SLOT_WAIT_SECONDS`)."""
    host.mkdir(parents=True)
    values = _values(host, slots=1)
    write_box(host)
    import time

    monkeypatch.setattr(remote_gpu_build, "SLOT_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(remote_gpu_build, "_live_ops", lambda lane: live)
    seen, check = _waits(3)
    pause = lambda s: time.sleep(0.06)  # each wait outlasts the bound
    with _offer(host, values), _op():
        if live:
            with pytest.raises(_Stop), _op(check=check, sleep=pause):
                pass
            assert len(seen) == 4
        else:
            with pytest.raises(RemoteLaneDown) as raised, _op(check=check, sleep=pause):
                pass
            assert raised.value.private_diagnostic == b"remote_gpu_build_slots_busy"
            assert len(seen) == 2


def test_a_settled_build_on_an_unproven_box_is_still_its_first_build(host):
    values, proven = _two_boxes(host)
    new = _lane_named(host, values, "a100-0")
    assert not remote_gpu_build.is_proven(new)
    with _offer(host, values):
        with _op(settled=True, recorded=remote_gpu_build.OpBinding(new, 1)) as replay:
            assert replay.lane.spec.name == "a100-0" and replay.slot == 1
        # the replay took no claim file, yet the task shadows the box again
        assert remote_gpu_build.first_build_box().spec.name == "a100-0"
        assert not (Path(new.lane_dir) / remote_gpu_build.FIRST_BUILD).exists()
        with _op(settled=True, recorded=remote_gpu_build.OpBinding(proven, 0)):
            pass
        # a settled op whose box is unknown is never bound to a guessed box
        with pytest.raises(RemoteLaneDown) as raised, _op(settled=True, recorded=None):
            pass
        assert (
            raised.value.private_diagnostic == b"remote_gpu_build_settled_box_unknown"
        )


def test_a_local_slot_lane_is_always_a_machine(host):
    values = _install(host, local=True)
    with _offer(host, values):
        assert remote_gpu_build.no_machine() is False


def test_removing_a_box_file_drains_the_box(host):
    values = _install(host)
    with _offer(host, values), _op() as running:
        (_boxes_dir(host) / f"{BOX}.json").unlink()  # the operator drops the box
        # the running op keeps its binding to the end
        assert remote_gpu_build.current_op() is running
        assert remote_gpu_build.cli().docker_host == HOST
        assert remote_gpu_build.device().digest == running.lane.device.digest
        # no new op starts there
        with pytest.raises(RemoteLaneDown) as raised, _op():
            pass
        assert raised.value.private_diagnostic == b"remote_gpu_build_no_box"


def _refusal(path, **kwargs):
    with pytest.raises(ValueError) as raised:
        remote_gpu_build.read_box(path, kind=KIND, **kwargs)
    return str(raised.value)


def test_the_loader_refuses_a_wrong_mode_owner_or_shape(host, monkeypatch):
    host.mkdir(parents=True)
    path = write_box(host, mode=0o644)
    assert _refusal(path) == "remote_gpu_build_box_mode"
    path.chmod(0o600)
    assert remote_gpu_build.read_box(path, kind=KIND).spec.name == BOX
    real = os.geteuid()
    monkeypatch.setattr(remote_gpu_build.os, "geteuid", lambda: real + 1)
    assert _refusal(path) == "remote_gpu_build_box_owner"
    monkeypatch.setattr(remote_gpu_build.os, "geteuid", lambda: real)
    link = _boxes_dir(host) / "linked.json"
    link.symlink_to(path)
    assert _refusal(link) == "remote_gpu_build_box_unreadable"  # never followed
    elsewhere = _host_key("ssh://carbon-build@elsewhere.example:2222")
    for change, reason in (
        # over-broad rules audit S7 B2 270: any 1..MAX_SLOTS equal, disjoint >= 4-core sets; these still refuse
        ({"slot_cpusets": ["0-1", "2-3", "4-5", "6-7"]}, "remote_gpu_build_box_shape"),
        ({"slot_cpusets": ["0-3", "3-6"]}, "remote_gpu_build_box_shape"),
        ({"slot_cpusets": ["0-3", "4-8"]}, "remote_gpu_build_box_shape"),
        ({"slot_cpusets": []}, "remote_gpu_build_box_shape"),
        ({"slot_cpusets": ["0-3"] * 9}, "remote_gpu_build_box_shape"),
        ({"slot_cpusets": ["x"]}, "remote_gpu_build_box_shape"),
        (
            {"host_key": "a100-1.example ssh-ed25519 AAAA"},
            "remote_gpu_build_box_host_key",
        ),
        ({"host_key": elsewhere}, "remote_gpu_build_box_host_key"),
        (
            {"host_key": _host_key().replace("ssh-ed25519", "ssh-rsa")},
            "remote_gpu_build_box_host_key",
        ),
        ({"name": "a100-9"}, "remote_gpu_build_box_name"),
        ({"schema": "other"}, "remote_gpu_build_box_schema"),
        ({"images": []}, "remote_gpu_build_box_images"),
        ({"device_digest": "sha256:" + "0" * 64}, "remote_gpu_build_box_device"),
        ({"docker_host": "tcp://10.0.0.2:2375"}, "remote_lane_docker_host"),
    ):
        write_box(host, {**box_document(), **change}, name=BOX)
        assert _refusal(path) == reason, change
    write_box(host, kind="NVIDIA GeForce RTX 4090")
    assert _refusal(path) == "remote_gpu_build_box_device_kind"
    # a refused box is simply not in the pool
    pool = _pool(host, _values(host))
    assert remote_gpu_build.boxes(pool) == ()
    write_box(host)
    assert len(remote_gpu_build.boxes(pool)) == 1
    # a boxes directory that is not the door user's 0700 directory holds no box
    _boxes_dir(host).chmod(0o755)
    assert remote_gpu_build.boxes(pool) == ()
    _boxes_dir(host).chmod(0o700)


def test_each_box_pins_its_own_host_key_strictly_in_its_wrapper_and_ssh(
    host, monkeypatch
):
    values = _install(host)
    seen = []

    class Popen:
        def __init__(self, argv, **kwargs):
            seen.append((argv, kwargs["env"]))
            raise OSError("no ssh in tests")

    monkeypatch.setattr(remote_gpu_build.subprocess, "Popen", Popen)
    with _offer(host, values), _op() as binding:
        directory = Path(binding.lane.lane_dir)
        known = directory / "known_hosts"
        assert known.read_text() == _host_key() + "\n"
        assert known.stat().st_mode & 0o777 == 0o600
        shim = (directory / "bin" / "ssh").read_text()
        assert "StrictHostKeyChecking=yes" in shim
        assert f"UserKnownHostsFile={known}" in shim
        assert "GlobalKnownHostsFile=/dev/null" in shim
        assert shim.rstrip().endswith('"$@"')
        wrapper = Path(remote_gpu_build.cli().executable).read_text()
        # Docker's ssh:// helper runs `ssh` from PATH: the box's shim comes first
        assert f"PATH={directory / 'bin'}:/usr/local/bin:/usr/bin:/bin\n" in wrapper
        assert f"DOCKER_HOST={HOST}\n" in wrapper
        # every direct ssh to the box (mirror, discard, probes) carries the same pinned options
        argv = remote_gpu_build._box_ssh(binding)
        assert argv[0] == "/usr/bin/ssh"
        for option in (
            "StrictHostKeyChecking=yes",
            f"UserKnownHostsFile={known}",
            "GlobalKnownHostsFile=/dev/null",
            "BatchMode=yes",
        ):
            assert argv[argv.index(option) - 1] == "-o"
        assert argv[-3:] == ["2222", "carbon-build@a100-1.example", "--"]
        with pytest.raises(RemoteLaneDown):
            remote_gpu_build.discard(Path(STAGE) / "x" / "input")
        assert seen[0][0][: len(argv)] == argv
        # ~/.ssh/config is never edited: the environment names nothing but PATH and HOME
        assert set(seen[0][1]) <= {"PATH", "HOME"}
    # a second box has its own known_hosts with exactly its own key
    other = "ssh://carbon-build@a100-2.example"
    write_box(host, box_document("a100-2", docker_host=other))
    (_boxes_dir(host) / f"{BOX}.json").unlink()
    with _offer(host, values), _op() as binding:
        assert binding.lane.spec.name == "a100-2"
        assert (Path(binding.lane.lane_dir) / "known_hosts").read_text() == (
            _host_key(other) + "\n"
        )


def test_each_op_takes_the_box_with_the_most_free_slots_then_the_name(host):
    values = _values(host, slots=2, memory="shared")
    for name in ("a100-b", "a100-a", "a100-c"):
        write_box(
            host, box_document(name, docker_host=f"ssh://carbon-build@{name}.example")
        )
    with _offer(host, values):
        with _op() as first:
            assert first.lane.spec.name == "a100-a"  # all free: the name
            with _op() as second:
                # a100-a has one slot left, the others two
                assert second.lane.spec.name == "a100-b"
                with _op() as third:
                    assert third.lane.spec.name == "a100-c"
                    with _op() as fourth:
                        assert fourth.lane.spec.name == "a100-a"
        with _op() as again:
            assert again.lane.spec.name == "a100-a"


def test_a_lost_box_is_marked_down_skipped_and_back_after_a_healthy_probe(
    host, monkeypatch
):
    values = _values(host)
    for name in ("a100-a", "a100-b"):
        write_box(
            host, box_document(name, docker_host=f"ssh://carbon-build@{name}.example")
        )
    monkeypatch.setattr(remote_gpu_build, "healthy", lambda binding=None: False)
    with _offer(host, values):
        with pytest.raises(RemoteLaneDown), _op() as binding:
            assert binding.lane.spec.name == "a100-a"
            raise RemoteLaneDown(b"exit=255\nConnection reset")  # the link is lost
        lost = binding.lane
        mark = json.loads(
            (Path(lost.lane_dir) / remote_gpu_build.DOWN_MARKER).read_text()
        )
        # one loss: SUSPECT only, still offered (over-broad rules audit #13: one blip never idles a box)
        assert mark["losses"] == 1 and not remote_gpu_build.is_down(lost)
        with pytest.raises(RemoteLaneDown), _op() as again:
            assert again.lane.spec.name == "a100-a"
            raise RemoteLaneDown(b"exit=255\nConnection reset")  # lost again, in a row
        mark = json.loads(
            (Path(lost.lane_dir) / remote_gpu_build.DOWN_MARKER).read_text()
        )
        assert type(mark["unix"]) is float and "losses" not in mark
        assert remote_gpu_build.is_down(lost)
        # a 3rd loss inside DOWN_SECONDS (another op the dead box was running) keeps it DOWN, window unchanged
        assert remote_gpu_build.note_loss(lost, b"lost again")
        again_mark = json.loads(
            (Path(lost.lane_dir) / remote_gpu_build.DOWN_MARKER).read_text()
        )
        assert again_mark == mark and remote_gpu_build.is_down(lost)
        # the FAILED_INFRA task's retry lands on another box
        with _op() as retry:
            assert retry.lane.spec.name == "a100-b"
    # a failure that is not a loss (the box answers) marks nothing
    monkeypatch.setattr(remote_gpu_build, "healthy", lambda binding=None: True)
    with _offer(host, values):
        with pytest.raises(RemoteLaneDown), _op() as other:
            raise RemoteLaneDown(b"remote_gpu_build_shared_device_memory")
        assert not remote_gpu_build.is_down(other.lane)
    # after DOWN_SECONDS it is offered again ...
    old = {"unix": remote_gpu_build.time.time() - remote_gpu_build.DOWN_SECONDS - 1}
    (Path(lost.lane_dir) / remote_gpu_build.DOWN_MARKER).write_text(json.dumps(old))
    assert not remote_gpu_build.is_down(lost)
    # ... and its next successful health probe clears the mark at once
    remote_gpu_build.mark_down(lost)
    monkeypatch.undo()
    monkeypatch.setattr(accelerator_runtime, "HOST_ROOT", host)
    monkeypatch.setattr(remote_gpu_build, "link_up", lambda binding=None, **k: True)
    monkeypatch.setattr(remote_gpu_build, "gpu_present", lambda binding=None: True)
    assert remote_gpu_build.healthy(remote_gpu_build.OpBinding(lost, 0))
    assert not (Path(lost.lane_dir) / remote_gpu_build.DOWN_MARKER).exists()


def test_a_loss_long_after_the_last_is_a_first_loss_again(host):
    values = _values(host)
    write_box(host, box_document("a100-a", docker_host="ssh://carbon-build@a.example"))
    with _offer(host, values):
        (lane,) = remote_gpu_build.boxes(_pool(host, values))
        assert remote_gpu_build.note_loss(lane, b"lost")
        path = Path(lane.lane_dir) / remote_gpu_build.DOWN_MARKER
        old = json.loads(path.read_text())
        old["unix"] -= remote_gpu_build.DOWN_SECONDS + 1
        path.write_text(json.dumps(old))
        assert remote_gpu_build.note_loss(lane, b"lost")
        assert json.loads(path.read_text())["losses"] == 1
        assert not remote_gpu_build.is_down(lane)
        # a healthy probe clears a suspect mark too
        remote_gpu_build.clear_down(lane)
        assert not path.exists()


def test_an_empty_gpu_list_or_a_one_read_flicker_never_refuses_the_box(
    host, monkeypatch
):
    from carbon.reconstruction.worker import accelerator_runtime as runtime

    values = _install(host)
    path = _boxes_dir(host) / f"{BOX}.json"
    monkeypatch.setattr(runtime, "verify_image_and_toolkit", lambda **kw: None)
    monkeypatch.setattr(remote_gpu_build, "link_up", lambda binding=None, **k: True)
    reads = []

    def capture(*a, **k):
        return reads.pop(0)

    monkeypatch.setattr(remote_gpu_build, "_ssh_capture", capture)
    ours = f"{UUID}, {KIND}\n".encode()
    other = b"GPU-other, NVIDIA A100-SXM4-80GB\n"
    with _offer(host, values), _op() as binding:
        record = binding.lane.device
        # nvidia-smi names no GPU (the GPU fell off the bus): the box is lost, not refused
        reads[:] = [b""]
        with pytest.raises(RemoteLaneDown) as raised:
            remote_gpu_build.check_host(_FakeCLI(), _image(), record)
        assert raised.value.private_diagnostic == b"remote_gpu_build_device_absent"
        assert path.exists()
        # another GPU on the first read, ours on the second: a flicker, the build goes on
        reads[:] = [other, ours]
        remote_gpu_build.check_host(_FakeCLI(), _image(), record)
        assert path.exists() and not reads
        # another GPU on both reads: a verified identity change, refused
        reads[:] = [other, other]
        with pytest.raises(RemoteLaneDown) as raised:
            remote_gpu_build.check_host(_FakeCLI(), _image(), record)
        assert raised.value.private_diagnostic == b"remote_gpu_build_box_gpu_mismatch"
        # MISMATCHED (over-broad rules audit #13): the box file stays, the box is skipped until a re-probe reads it equal
        assert path.exists() and not Path(str(path) + ".refused").exists()
        assert remote_gpu_build.mismatched(binding.lane)


def _image(image_id=IMAGE):
    return type("Image", (), {"image_id": image_id})()


def test_a_per_build_re_read_that_differs_from_the_box_file_refuses_the_box(
    host, monkeypatch
):
    from carbon.reconstruction.worker import accelerator_runtime as runtime

    values = _install(host)
    path = _boxes_dir(host) / f"{BOX}.json"
    verified = []
    monkeypatch.setattr(
        runtime, "verify_image_and_toolkit", lambda **kw: verified.append(kw["image"])
    )
    monkeypatch.setattr(remote_gpu_build, "link_up", lambda binding=None, **k: True)
    rows = {"value": f"{UUID}, {KIND}\n".encode()}
    monkeypatch.setattr(remote_gpu_build, "_ssh_capture", lambda *a, **k: rows["value"])
    with _offer(host, values), _op() as binding:
        record = binding.lane.device
        remote_gpu_build.mark_down(binding.lane)
        remote_gpu_build.check_host(_FakeCLI(), _image(), record)  # the box as admitted
        assert verified and not remote_gpu_build.is_down(binding.lane)  # a health probe
        # another GPU on the box now
        rows["value"] = b"GPU-other, NVIDIA A100-SXM4-80GB\n"
        with pytest.raises(RemoteLaneDown) as raised:
            remote_gpu_build.check_host(_FakeCLI(), _image(), record)
        assert raised.value.code is WorkerCode.UNAVAILABLE
        assert raised.value.private_diagnostic == b"remote_gpu_build_box_gpu_mismatch"
        # MISMATCHED, never renamed (audit #13): the file stays; skipped until a re-probe reads it equal again
        assert path.exists() and not Path(str(path) + ".refused").exists()
        assert remote_gpu_build.mismatched(binding.lane)
    mismatch = Path(binding.lane.lane_dir) / remote_gpu_build.MISMATCH_NOTE

    calls = []

    def missing(**kw):
        calls.append(kw["image"])
        raise WorkerFailure(WorkerCode.POLICY)

    # an image the box file never admitted (a door switched its image since): Carbon's, the box is NOT refused
    mismatch.unlink()  # the box reads equal again (`reprobe`): offered again
    write_box(host)
    rows["value"] = f"{UUID}, {KIND}\n".encode()
    with (
        _offer(host, values),
        _op() as binding,
        pytest.raises(RemoteLaneDown) as raised,
    ):
        remote_gpu_build.check_host(
            _FakeCLI(), _image("sha256:" + "f" * 64), binding.lane.device
        )
    assert raised.value.private_diagnostic == b"remote_gpu_build_box_image_not_admitted"
    assert path.exists()
    # one the box's daemon no longer has as it was, read twice: the box is refused
    monkeypatch.setattr(runtime, "verify_image_and_toolkit", missing)
    with (
        _offer(host, values),
        _op() as binding,
        pytest.raises(RemoteLaneDown) as raised,
    ):
        remote_gpu_build.check_host(_FakeCLI(), _image(), binding.lane.device)
    assert raised.value.private_diagnostic.endswith(b"mismatch") and len(calls) == 2
    assert path.exists() and mismatch.exists()  # MISMATCHED, its file kept
    # a link that is down is the box DOWN, never refused
    mismatch.unlink()
    write_box(host)
    monkeypatch.setattr(remote_gpu_build, "link_up", lambda binding=None, **k: False)
    with (
        _offer(host, values),
        _op() as binding,
        pytest.raises(RemoteLaneDown) as raised,
    ):
        remote_gpu_build.check_host(_FakeCLI(), _image(), binding.lane.device)
    assert raised.value.private_diagnostic == b"remote_gpu_build_link_down"
    assert path.exists()


def _ledger(root, owner, identity, intent):
    from carbon.development_session.profile import digest

    request = {"identity": identity}
    launch = digest(
        canonical({"owner": owner, "identity": identity, "request": request})
    )
    operation = root / ("operation-" + launch[7:])
    operation.mkdir(parents=True)
    (operation / "intent.json").write_bytes(
        canonical(
            {
                "launch": launch,
                "container": "carbon-d4-" + launch[7:31],
                "request": request,
                "owner": owner,
                "identity": identity,
                "deadline_unix": None,
                **intent,
            }
        )
    )
    finished = []

    class Ledger:
        def status(self, owner):
            operation = {"id": identity, "state": "RESERVED", "reservation": {}}
            return {"operations": [{**operation, "result": None}]}

        def finish(self, identity, **kwargs):
            finished.append(kwargs)

    ledger = Ledger()
    ledger.root = root
    return ledger, finished


def test_recovery_finds_a_drained_box_by_its_name_and_settles_the_op_as_carbons(
    host, monkeypatch, tmp_path
):
    from carbon.development_session import research_carrier

    values = _install(host)
    with _offer(host, values), _op() as binding:
        intent = remote_gpu_build.intent_fields()
        record = binding.slot_dir / "active-allocation.json"
        record.write_text("{}")  # the lost controller's slot record
    assert intent["remote_gpu_build"]["box"] == BOX
    (_boxes_dir(host) / f"{BOX}.json").unlink()  # drained since
    recovered = remote_gpu_build.recorded(intent)
    assert recovered.gone and recovered.lane.spec.name == BOX
    assert recovered.slot_dir == binding.slot_dir
    # the box copy the op ran with still names its device (a settled replay's request)
    assert recovered.lane.device.digest == binding.lane.device.digest
    removed = []

    def unreachable(**k):
        removed.append(k["cli"].docker_host)
        raise RemoteLaneDown(b"remote_gpu_build_link_down")

    # a drained box that no longer answers: the op is Carbon's, its slot record stays (its container may still run)
    monkeypatch.setattr(research_carrier, "remove_exact_container", unreachable)
    ledger, finished = _ledger(tmp_path / "ledger", "o", BUILD, intent)
    result = research_carrier.reconcile_worker(ledger, owner="o", identity=BUILD)
    assert result["state"] == "FAILED_INFRA" and result["cleanup_observed"] is False
    assert finished[0]["state"] == "FAILED_INFRA"
    assert removed == [HOST] and record.exists()
    # one that still answers: its container is removed through the box copy's pinned wrapper, then the record cleared
    monkeypatch.setattr(
        research_carrier,
        "remove_exact_container",
        lambda **k: removed.append(k["cli"].docker_host),
    )
    assert research_carrier._clear_gone_box(recovered, "c", "l") is True
    assert removed == [HOST, HOST] and not record.exists()
    # the box comes back (same name, same admission): its op is recovered on it as before
    write_box(host)
    assert not remote_gpu_build.recorded(intent).gone
    # an intent of the old single remote lane: that lane is not installed any more
    old = {
        "remote_gpu_build": {
            "docker_host": HOST,
            "stage_root": STAGE,
            "lane": 0,
            "slot": 1,
        }
    }
    assert remote_gpu_build.recorded(old).gone


def test_a_settled_replay_binds_the_box_its_intent_recorded(
    host, monkeypatch, tmp_path
):
    from carbon.development_session import research_carrier

    values = _values(host)
    write_box(
        host, box_document("a100-a", docker_host="ssh://carbon-build@a100-a.example")
    )
    with _offer(host, values), _op() as ran:
        intent = remote_gpu_build.intent_fields()
    write_box(
        host,
        box_document(
            "a100-0",
            docker_host="ssh://carbon-build@a100-0.example",
            uuid="GPU-b2b2b2b2-0000-1111-2222-333333333333",
        ),
    )
    ledger, _ = _ledger(tmp_path / "ledger", "o", BUILD, intent)
    ledger.operation_state = lambda identity, *, owner: "SUCCEEDED"
    seen = []
    monkeypatch.setattr(
        research_carrier,
        "_run_supervised",
        lambda ledger, **k: seen.append(remote_gpu_build.current_op()) or "recorded",
    )
    with _offer(host, values):
        research_carrier._run(
            ledger,
            owner="o",
            identity=BUILD,
            accelerator="VALIDATOR_OWN_GPU",
            provenance="X",
        )
    # "a100-0" sorts first, but the replay's request names the box the op ran on
    assert seen[0].lane.spec.name == "a100-a"
    assert seen[0].lane.device.digest == ran.lane.device.digest


# -- proven boxes and the first-build shadow (Validator-2 (e)) -----------------------------------------------------------------


def test_the_first_box_is_proven_at_once_by_its_own_class_check(host):
    values = _install(host)
    lane = _lane(host)
    assert not remote_gpu_build.is_proven(lane)
    with _offer(host, values), _op():
        assert remote_gpu_build.first_build_box() is None  # no shadow
    assert remote_gpu_build.is_proven(lane)
    mark = json.loads(
        (Path(lane.lane_dir) / remote_gpu_build.PROVEN_MARKER).read_text()
    )
    assert mark["how"] == "first_box" and mark["box_digest"] == lane.spec.box_digest
    # a re-admitted box (a new box file under the same name) is not the box that was proven
    write_box(host, uuid="GPU-b2b2b2b2-0000-1111-2222-333333333333")
    assert not remote_gpu_build.is_proven(_lane_named(host, values, BOX))


def _two_boxes(host):
    values = _values(host)
    write_box(
        host, box_document("a100-a", docker_host="ssh://carbon-build@a100-a.example")
    )
    with _offer(host, values), _op() as first:
        pass
    assert remote_gpu_build.is_proven(first.lane)
    # a new box, first by name
    write_box(
        host, box_document("a100-0", docker_host="ssh://carbon-build@a100-0.example")
    )
    return values, first.lane


def _lane_named(host, values, name):
    pool = _pool(host, values)
    return next(box for box in remote_gpu_build.boxes(pool) if box.spec.name == name)


def test_a_new_box_s_first_build_is_claimed_and_shadowed_on_a_proven_box(host):
    values, proven = _two_boxes(host)
    with _offer(host, values):
        with _op() as first:
            new = first.lane
            assert new.spec.name == "a100-0" and not remote_gpu_build.is_proven(new)
            # while its first build runs, no other op starts on the new box
            with _op() as other:
                assert other.lane.spec.name == "a100-a"
        assert remote_gpu_build.first_build_box() == new
        assert remote_gpu_build.proven_elsewhere(new)
        # the shadow runs only on a proven box other than the new one
        with remote_gpu_build.shadowing(new), _op("t~shadow") as shadow:
            assert shadow.lane.spec.name == proven.spec.name
        with (
            remote_gpu_build.shadowing(proven),
            pytest.raises(RemoteLaneDown) as raised,
            _op("t~shadow"),
        ):
            pass
        assert raised.value.private_diagnostic == b"remote_gpu_build_no_proven_box"
    # the offer's end releases the claim: the next build may be the new box's first again
    assert not (Path(new.lane_dir) / remote_gpu_build.FIRST_BUILD).exists()


def _settle(shadow_digest, host, values):
    from types import SimpleNamespace

    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

    shadows = []

    def shadow(task_id, request, recipe, binding, envelope, device, new_box):
        shadows.append(new_box.spec.name)
        if isinstance(shadow_digest, BaseException):
            raise shadow_digest
        return shadow_digest

    provider = SimpleNamespace(_graph_gpu_shadow=shadow)
    with _offer(host, values):
        with _op() as built:
            pass
        DirectDevelopmentTasksV3._settle_first_build(
            provider, "task", None, None, None, b"", "VALIDATOR_OWN_GPU", "sha256:built"
        )
    return built.lane, shadows


def test_an_equal_shadow_proves_the_new_box(host):
    values, _ = _two_boxes(host)
    new, shadows = _settle("sha256:built", host, values)
    assert shadows == ["a100-0"] and remote_gpu_build.is_proven(new)
    mark = json.loads((Path(new.lane_dir) / remote_gpu_build.PROVEN_MARKER).read_text())
    assert mark["how"] == "shadow"
    # proven: its next build is not shadowed again
    _, again = _settle("sha256:other", host, values)
    assert again == []


def test_an_unequal_shadow_refuses_the_new_box_and_the_task_is_carbons(host):
    values, _ = _two_boxes(host)
    with pytest.raises(RemoteLaneDown) as raised:
        _settle("sha256:different", host, values)
    assert raised.value.code is WorkerCode.UNAVAILABLE  # FAILED_INFRA, never charged
    assert (
        raised.value.private_diagnostic
        == b"remote_gpu_build_shadow_state_digest_differs"
    )
    assert not (_boxes_dir(host) / "a100-0.json").exists()
    assert (_boxes_dir(host) / "a100-0.json.refused").exists()
    pool = _pool(host, values)
    assert [box.spec.name for box in remote_gpu_build.boxes(pool)] == ["a100-a"]


def test_a_shadow_that_cannot_run_leaves_the_new_box_unproven(host):
    values, _ = _two_boxes(host)
    with pytest.raises(RemoteLaneDown):
        _settle(RemoteLaneDown(b"remote_gpu_build_no_proven_box"), host, values)
    assert not remote_gpu_build.is_proven(_lane_named(host, values, "a100-0"))
    assert (_boxes_dir(host) / "a100-0.json").exists()


def test_with_no_other_proven_box_a_new_box_is_proven_at_once(host):
    values, proven = _two_boxes(host)
    (_boxes_dir(host) / f"{proven.spec.name}.json").unlink()  # the proven box dropped
    new, shadows = _settle("sha256:never-read", host, values)
    assert shadows == [] and remote_gpu_build.is_proven(new)


# -- every other reach of a box goes through its pinned ssh ---------------------------------------------------------------


def test_the_box_quiet_probe_reads_a_box_through_its_pinned_wrapper_and_ssh(
    host, monkeypatch
):
    from types import SimpleNamespace

    from carbon.challenge_validator import host_quiet

    values = _install(host)
    runs = []

    def run(argv, **kwargs):
        runs.append((argv, kwargs["env"]))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(host_quiet.subprocess, "run", run)
    monkeypatch.setattr(
        remote_lane, "box_output", lambda *a, **k: pytest.fail("the system ssh")
    )
    outputs = []
    monkeypatch.setattr(
        remote_gpu_build,
        "box_output",
        lambda binding, script, **k: outputs.append(binding) or b"",
    )
    with _offer(host, values), _op() as binding:
        assert host_quiet.box_worker_containers(binding) == []
        assert runs[0][0][0] == str(Path(binding.lane.lane_dir) / "docker")
        assert "DOCKER_HOST" not in runs[0][1]  # the wrapper names the box's daemon
        assert host_quiet.box_foreign_gpu(binding) == 0
        assert outputs == [binding]


def test_the_watchdog_watches_a_box_container_through_the_box_wrapper(
    host, monkeypatch
):
    from carbon.reconstruction.worker import watchdog

    values = _install(host)
    with _offer(host, values), _op() as binding:
        handed = remote_gpu_build._handoff(binding)
    monkeypatch.setattr(remote_gpu_build, "_ENVIRONMENT_BINDING", [])
    monkeypatch.setenv(remote_gpu_build.ENVIRONMENT, handed)
    monkeypatch.setenv("DOCKER_HOST", HOST)
    removed = []
    monkeypatch.setattr(
        watchdog,
        "remove_exact_container",
        lambda *, cli, container_name, launch_digest: removed.append(cli.executable),
    )
    assert watchdog.main(["carbon-d4-" + "a" * 24, "sha256:" + "b" * 64, "1.0"]) == 0
    assert removed == [str(Path(binding.lane.lane_dir) / "docker")]


def test_a_box_set_up_before_the_seven_slots_is_still_read_with_its_own_four(host):
    """A box file written by `gpu_box_up.py` before 17 Nov (4 x 4-core cpusets) stays in the pool until the script runs
    on it again: its lane offers its own 4 slots, never the values row's 7 (no build on cores the box never set up).
    """
    path = write_box(
        host,
        {
            **box_document(),
            "slot_cpusets": list(remote_gpu_build.LEGACY_BOX_SLOT_CPUSETS),
        },
        name=BOX,
    )
    lane = remote_gpu_build.read_box(
        path, kind=KIND, slots=7, memory="shared", root=host
    )
    assert lane.spec.slot_cpusets == remote_gpu_build.LEGACY_BOX_SLOT_CPUSETS
    assert lane.slots == 4
    current = write_box(host, box_document(), name=BOX)
    lane = remote_gpu_build.read_box(
        current, kind=KIND, slots=7, memory="shared", root=host
    )
    assert lane.spec.slot_cpusets == remote_gpu_build.BOX_SLOT_CPUSETS
    assert lane.slots == 7


def test_door_box_up_is_false_only_while_every_box_is_down(host):
    host.mkdir(parents=True)
    _boxes_dir(host).mkdir(mode=0o700)
    values = _values(host)
    assert (
        remote_gpu_build.door_box_up("electric-motor-magnetics", "1.8", values=values)
        is False
    )
    write_box(host)
    assert (
        remote_gpu_build.door_box_up("electric-motor-magnetics", "1.8", values=values)
        is True
    )
    (box,) = remote_gpu_build.boxes(_pool(host, values))
    remote_gpu_build.mark_down(box, b"test")
    assert (
        remote_gpu_build.door_box_up("electric-motor-magnetics", "1.8", values=values)
        is False
    )


# --- over-broad rules audit #13: an identity mismatch is re-probed, never a permanent rename ---------------------------


def _mismatched_box(host, monkeypatch, rows):
    values = _install(host)
    monkeypatch.setattr(remote_gpu_build, "_ssh_capture", lambda *a, **k: rows["value"])
    (box,) = remote_gpu_build.boxes(_pool(host, values))
    remote_gpu_build.refuse_identity(box, b"remote_gpu_build_box_gpu_mismatch")
    return values, box


def _usable(host, values, box):
    offer = type("Offer", (), {"serves": lambda self, lane: True})()
    return remote_gpu_build._usable_box(offer, box)


def test_a_mismatched_box_is_skipped_until_its_re_probe_is_due(host, monkeypatch):
    rows = {"value": b"GPU-other, NVIDIA A100-SXM4-80GB\n"}
    values, box = _mismatched_box(host, monkeypatch, rows)
    probes = []
    monkeypatch.setattr(
        remote_gpu_build, "reprobe", lambda lane: probes.append(lane) or True
    )
    assert remote_gpu_build.mismatched(box)
    assert (
        _usable(host, values, box) is False and probes == []
    )  # inside REPROBE_SECONDS
    assert (
        remote_gpu_build.door_box_up("electric-motor-magnetics", "1.8", values=values)
        is False
    )
    mark = Path(box.lane_dir) / remote_gpu_build.MISMATCH_NOTE
    old = json.loads(mark.read_text())
    old["unix"] -= remote_gpu_build.REPROBE_SECONDS + 1
    mark.write_text(json.dumps(old))
    # due: a round may start (the door counts the box), and taking the op reads the box again
    assert (
        remote_gpu_build.door_box_up("electric-motor-magnetics", "1.8", values=values)
        is True
    )
    assert _usable(host, values, box) is True and probes == [box]


def test_a_re_probe_that_reads_the_box_file_again_clears_the_mark(host, monkeypatch):
    rows = {"value": f"{UUID}, {KIND}\n".encode()}
    _, box = _mismatched_box(host, monkeypatch, rows)
    monkeypatch.setattr(remote_gpu_build, "_image_ids", lambda binding: [IMAGE])
    assert remote_gpu_build.reprobe(box) is True
    assert not remote_gpu_build.mismatched(box)
    assert (_boxes_dir(host) / f"{BOX}.json").exists()  # the box file never moved


def test_a_re_probe_that_still_differs_keeps_the_mark_and_renews_its_time(
    host, monkeypatch
):
    rows = {"value": b"GPU-other, NVIDIA A100-SXM4-80GB\n"}
    _, box = _mismatched_box(host, monkeypatch, rows)
    monkeypatch.setattr(remote_gpu_build, "_image_ids", lambda binding: [IMAGE])
    mark = Path(box.lane_dir) / remote_gpu_build.MISMATCH_NOTE
    old = json.loads(mark.read_text())
    old["unix"] -= remote_gpu_build.REPROBE_SECONDS + 1
    mark.write_text(json.dumps(old))
    assert remote_gpu_build.reprobe(box) is False
    assert remote_gpu_build.mismatched(box)
    assert (
        json.loads(mark.read_text())["unix"] > old["unix"]
    )  # the next read is a full spacing later
    # the GPU is ours again but an admitted image is gone or another id: still mismatched
    rows["value"] = f"{UUID}, {KIND}\n".encode()
    monkeypatch.setattr(remote_gpu_build, "_image_ids", lambda binding: None)
    assert remote_gpu_build.reprobe(box) is False and remote_gpu_build.mismatched(box)
    monkeypatch.setattr(
        remote_gpu_build, "_image_ids", lambda binding: ["sha256:" + "f" * 64]
    )
    assert remote_gpu_build.reprobe(box) is False and remote_gpu_build.mismatched(box)


def test_a_mismatch_mark_of_another_admission_is_not_this_boxs(host, monkeypatch):
    rows = {"value": b"GPU-other, NVIDIA A100-SXM4-80GB\n"}
    values, box = _mismatched_box(host, monkeypatch, rows)
    # the operator admits the box again with another document (gpu_box_up door PASS): a new digest, no mark
    write_box(host, box_document(images=(IMAGE, "sha256:" + "d" * 64)))
    (again,) = remote_gpu_build.boxes(_pool(host, values))
    assert again.spec.box_digest != box.spec.box_digest
    assert not remote_gpu_build.mismatched(again)


def test_an_identity_mismatch_is_never_a_loss_and_a_shadow_refusal_is_still_permanent(
    host, monkeypatch
):
    rows = {"value": b"GPU-other, NVIDIA A100-SXM4-80GB\n"}
    _, box = _mismatched_box(host, monkeypatch, rows)
    error = remote_gpu_build.refuse_identity(box, b"remote_gpu_build_box_gpu_mismatch")
    assert error.box_refused is True and error.code is WorkerCode.UNAVAILABLE
    assert not remote_gpu_build.is_down(box)
    # `refuse` (a box that BUILDS differently: an unequal first-build shadow) still renames its file for good
    path = _boxes_dir(host) / f"{BOX}.json"
    remote_gpu_build.refuse(box, b"remote_gpu_build_shadow_state_digest_differs")
    assert not path.exists() and Path(str(path) + ".refused").exists()


def test_an_a100_door_with_an_ada_box_file_in_its_dir_offers_no_ada_slot(host):
    """v2 21 Nov 03:30Z (Ada S6 finding: Ada vs A100 GPU state digests differ on layer-norm graphs): a door's pool is ONE
    class; a box of another class in the SAME boxes directory is never read into it, so no build, owed rebuild, crown
    re-measure or reproduce of an A100 door can land on an Ada box (a cross-class re-build is never compared).
    """
    ada = "NVIDIA RTX 6000 Ada Generation"
    write_box(host)
    write_box(
        host,
        box_document(
            "ada-1", kind=ada, docker_host="ssh://carbon-build@ada-1.example:2222"
        ),
    )
    # the pool is read once its boxes directory exists (`door_pool`: no directory, no lane)
    pool = _pool(host, _values(host))
    lanes = remote_gpu_build.boxes(pool)
    assert [lane.spec.name for lane in lanes] == [BOX]
    assert {lane.device.device_kind for lane in lanes} == {KIND}
    assert pool.kind == KIND


@pytest.mark.parametrize(
    "cpusets",
    [
        ["0-3", "4-7"],
        ["0-5", "6-11", "12-17"],
        ["8-15"],
        ["0-3", "4-7", "8-11", "12-15", "16-19"],
    ],
)
def test_a_box_of_another_slot_shape_is_read(host, cpusets):
    """Over-broad rules audit S7 B2 270: a rented box (a Lium pod of another vCPU count) is not refused for its shape;
    equal, disjoint sets of at least 4 cores each."""
    path = write_box(host, box_document() | {"slot_cpusets": cpusets})
    lane = remote_gpu_build.read_box(path, kind=KIND, slots=7)
    assert lane.spec.slot_cpusets == tuple(cpusets)
    assert lane.slots == len(cpusets)  # a box offers at most its own slots


class _CrowdCLI(_FakeCLI):
    def __init__(self, outputs):
        super().__init__()
        self.outputs = list(outputs)

    def run(self, arguments, timeout=30, accepted=(0,)):
        self.stdout = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        return super().run(arguments, timeout, accepted)


def test_a_crowded_device_is_read_again_before_conflict(host, monkeypatch):
    """Over-broad rules audit S7 B2 261: another slot's ending container frees its place within the wait; nothing is
    removed; a device still crowded at the bound is CONFLICT; this slot's own record is CONFLICT at once.
    """
    lane = _lane(host, slots=2)
    slept = []
    with remote_gpu_build.offered(lane), _op() as binding:
        cli = _CrowdCLI([b'"a"\n"b"\n', b'"a"\n"b"\n', b'"a"\n'])
        remote_gpu_build.reject_crowded(cli, binding, sleep=slept.append)
        assert len(cli.calls) == 3 and slept == [remote_gpu_build.POLL_S] * 2
        assert all(call[0] == "ps" for call in cli.calls)  # read only
        monkeypatch.setattr(remote_gpu_build, "CROWDED_WAIT_SECONDS", 0)
        with pytest.raises(WorkerFailure) as raised:
            remote_gpu_build.reject_crowded(
                _CrowdCLI([b'"a"\n"b"\n']), binding, sleep=slept.append
            )
        assert raised.value.code is WorkerCode.CONFLICT
        monkeypatch.setattr(remote_gpu_build, "CROWDED_WAIT_SECONDS", 3600)
        (binding.slot_dir / "active-allocation.json").write_text("{}")
        with pytest.raises(WorkerFailure):
            remote_gpu_build.reject_crowded(
                _CrowdCLI([b""]), binding, sleep=slept.append
            )
