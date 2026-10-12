"""PLT-06: inspect hostile source text and test the guard; NEVER execute a model.

All container records and limits here are synthetic. No Docker, lowering,
model import, subprocess, fork, socket, flood or hostile loop is invoked.
"""

from __future__ import annotations

import ast
import copy
import hashlib

import pytest
from level4_hostile_fixtures import (
    BOUNDED_LANE,
    LANE_LABEL,
    PROBES,
    SOURCE_ROOT,
    UNLIMITED_LANE,
    ProbeRefused,
    prepare_probe_sources,
    require_probe_container,
)

IMAGE = "sha256:" + "1" * 64
CONTAINER = "2" * 64
IDENTITY = {"image_id": IMAGE, "container_id": CONTAINER, "wall_seconds": 30}
NAMES = {
    "memory",
    "time",
    "scratch_flood",
    "fork_bomb",
    "outside_scratch",
    "network_socket",
}


def inspection():
    """An inert example of the executor's required shape, not a deployed profile."""
    return {
        "Id": CONTAINER,
        "Image": IMAGE,
        "State": {"Running": True},
        "Config": {"User": "1001:1001", "Labels": {LANE_LABEL: BOUNDED_LANE}},
        "HostConfig": {
            "Memory": 128 * 1024**2,
            "MemorySwap": 128 * 1024**2,
            "NanoCpus": 10**9,
            "PidsLimit": 16,
            "ReadonlyRootfs": True,
            "Privileged": False,
            "NetworkMode": "none",
            "PidMode": "private",
            "IpcMode": "private",
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges=true"],
            "Tmpfs": {"/scratch": "rw,nosuid,nodev,noexec,size=64m,nr_inodes=1024"},
        },
        "Mounts": [
            {"Destination": "/input", "Type": "bind", "RW": False},
            {"Destination": "/scratch", "Type": "tmpfs", "RW": True},
        ],
    }


def test_unlimited_lane_is_refused_before_any_source_is_read(monkeypatch):
    record = inspection()
    record["Config"]["Labels"][LANE_LABEL] = UNLIMITED_LANE
    record["Config"]["Labels"]["carbon.resource-profile"] = "sha256:" + "3" * 64

    # Even a profile digest and all positive caps do not authorize this lane.
    def no_read(*args):
        raise AssertionError("an unlimited lane reached source preparation")

    monkeypatch.setattr(type(SOURCE_ROOT), "read_bytes", no_read)
    with pytest.raises(ProbeRefused) as refusal:
        prepare_probe_sources(record, **IDENTITY)
    assert refusal.value.code == "hostile_probe_unlimited_lane"


@pytest.mark.parametrize("lane", [None, "", "carbon.evaluator.v1", "unregistered"])
def test_another_or_unlabelled_lane_is_refused(lane):
    record = inspection()
    record["Config"]["Labels"][LANE_LABEL] = lane
    with pytest.raises(ProbeRefused, match="hostile_probe_bounded_lane_required"):
        require_probe_container(record, **IDENTITY)


@pytest.mark.parametrize("key", ["Memory", "NanoCpus", "PidsLimit"])
@pytest.mark.parametrize("value", [None, 0, -1, True, 1.5, "16"])
def test_every_resource_cap_is_a_positive_integer(key, value):
    record = inspection()
    record["HostConfig"][key] = value
    with pytest.raises(ProbeRefused, match="hostile_probe_resource_bounds_required"):
        require_probe_container(record, **IDENTITY)


@pytest.mark.parametrize("seconds", [None, 0, -1, True, 1.5, "30"])
def test_a_supervisor_deadline_must_be_supplied(seconds):
    with pytest.raises(ProbeRefused, match="hostile_probe_resource_bounds_required"):
        require_probe_container(inspection(), **{**IDENTITY, "wall_seconds": seconds})


@pytest.mark.parametrize("swap", [None, -1, 0, True, 256 * 1024**2])
def test_swap_cannot_bypass_the_memory_cap(swap):
    record = inspection()
    record["HostConfig"]["MemorySwap"] = swap
    with pytest.raises(ProbeRefused, match="hostile_probe_resource_bounds_required"):
        require_probe_container(record, **IDENTITY)


@pytest.mark.parametrize("damage", ["image", "container", "not_running", "short_id"])
def test_the_plan_is_bound_to_the_running_container_and_pinned_image(damage):
    record = inspection()
    if damage == "image":
        record["Image"] = "sha256:" + "4" * 64
    elif damage == "container":
        record["Id"] = "5" * 64
    elif damage == "not_running":
        record["State"]["Running"] = False
    else:
        record["Id"] = CONTAINER[:12]
    with pytest.raises(ProbeRefused, match="hostile_probe_container_identity"):
        require_probe_container(record, **IDENTITY)


@pytest.mark.parametrize(
    "field,value",
    [
        ("NetworkMode", "bridge"),
        ("ReadonlyRootfs", False),
        ("Privileged", True),
        ("PidMode", "host"),
        ("IpcMode", "host"),
        ("CapAdd", ["SYS_ADMIN"]),
        ("CapDrop", []),
        ("SecurityOpt", []),
        ("SecurityOpt", "no-new-privileges=true"),
        ("Devices", [{"PathOnHost": "/dev/sda"}]),
        ("DeviceRequests", [{}]),
        ("PortBindings", {"80/tcp": [{}]}),
        ("PublishAllPorts", True),
    ],
)
def test_weakened_isolation_is_refused(field, value):
    record = inspection()
    record["HostConfig"][field] = value
    with pytest.raises(ProbeRefused, match="hostile_probe_isolation_required"):
        require_probe_container(record, **IDENTITY)


@pytest.mark.parametrize("user", [None, "root", "0", "0:1001", "1001:0"])
def test_root_or_unspecified_user_is_refused(user):
    record = inspection()
    record["Config"]["User"] = user
    with pytest.raises(ProbeRefused, match="hostile_probe_isolation_required"):
        require_probe_container(record, **IDENTITY)


@pytest.mark.parametrize(
    "options",
    [
        "rw,nosuid,nodev,noexec,nr_inodes=1024",
        "rw,nosuid,nodev,noexec,size=64m",
        "rw,nosuid,nodev,noexec,size=0,nr_inodes=1024",
        "rw,nosuid,nodev,noexec,size=64m,nr_inodes=0",
        "rw,nosuid,nodev,size=64m,nr_inodes=1024",
        "rw,nosuid,nodev,noexec,size=50%,nr_inodes=1024",
        "rw,nosuid,nodev,noexec,size=64m,size=1g,nr_inodes=1024",
        "rw,nosuid,nodev,noexec,size=64m,nr_inodes=1024,nr_inodes=1",
        None,
    ],
)
def test_both_scratch_bytes_and_inodes_are_capped(options):
    record = inspection()
    record["HostConfig"]["Tmpfs"]["/scratch"] = options
    with pytest.raises(ProbeRefused, match="hostile_probe_scratch_bounds_required"):
        require_probe_container(record, **IDENTITY)


@pytest.mark.parametrize(
    "damage", ["bind_scratch", "writable_input", "extra", "duplicate"]
)
def test_a_host_disk_scratch_or_other_mount_is_refused(damage):
    record = inspection()
    if damage == "bind_scratch":
        record["Mounts"][1]["Type"] = "bind"
    elif damage == "writable_input":
        record["Mounts"][0]["RW"] = True
    elif damage == "extra":
        record["Mounts"].append({"Destination": "/host", "Type": "bind", "RW": True})
    else:
        record["Mounts"].append(copy.deepcopy(record["Mounts"][1]))
    with pytest.raises(ProbeRefused, match="hostile_probe_scratch_bounds_required"):
        require_probe_container(record, **IDENTITY)


@pytest.mark.parametrize("malformed", [None, {}, {"Config": []}, {"HostConfig": []}])
def test_missing_inspection_is_a_typed_refusal(malformed):
    with pytest.raises(ProbeRefused, match="hostile_probe_inspection_required"):
        require_probe_container(malformed, **IDENTITY)


def test_a_checked_plan_contains_six_sources_and_expectations_but_no_result():
    plan = prepare_probe_sources(inspection(), **IDENTITY)
    assert plan["image_id"] == IMAGE and plan["container_id"] == CONTAINER
    assert plan["wall_seconds"] == IDENTITY["wall_seconds"]
    assert {row["probe"] for row in plan["sources"]} == NAMES == set(PROBES)
    assert len(plan["sources"]) == 6
    assert "status" not in plan and "results" not in plan and "score" not in plan
    for row in plan["sources"]:
        raw = (SOURCE_ROOT / (row["probe"] + ".py.txt")).read_bytes()
        assert row["source"] == raw.decode()
        assert row["source_digest"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        assert row["filename"] == row["probe"] + ".py"
        assert row["started_marker"] == "HOSTILE_L4_PROBE:" + row["probe"]
        assert (
            row["required_observations"]
            and "no submission" in row["required_observations"]
        )
        assert set(row["expected_outcomes"]) <= {
            "typed_refusal",
            "timeout",
            "bounds_held",
        }
        assert row["expected_outcomes"]


@pytest.mark.parametrize("name", sorted(NAMES))
def test_source_syntax_and_tooling_contract_are_checked_without_importing_it(name):
    # AST parsing is deliberately the only operation on the hostile Python text.
    tree = ast.parse((SOURCE_ROOT / (name + ".py.txt")).read_text())
    assert all(
        isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.FunctionDef))
        or (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
        for node in tree.body
    )
    data = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
    }
    assert data == {
        "FRAMEWORK": "jax",
        "INPUTS": {"inputs/features": ((3,), "float32")},
    }
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert set(functions) == {"init", "forward"}
    assert all(
        not node.decorator_list and not node.args.defaults
        for node in functions.values()
    )
    assert [arg.arg for arg in functions["forward"].args.args] == ["params", "x"]
    assert len(functions["init"].body) == 1
    assert ast.literal_eval(functions["init"].body[0].value) == []
    forward = functions["forward"]
    marker = forward.body[0].value
    assert isinstance(marker, ast.Call) and marker.func.id == "print"
    assert ast.literal_eval(marker.args[0]) == "HOSTILE_L4_PROBE:" + name
    assert [(kw.arg, ast.literal_eval(kw.value)) for kw in marker.keywords] == [
        ("flush", True)
    ]
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(forward)
        if isinstance(node, ast.Call)
    }
    expected_call = {
        "memory": "bytearray",
        "scratch_flood": "(scratch / str(n)).write_bytes",
        "fork_bomb": "os.fork",
        "outside_scratch": "Path('/hostile-l4-outside-scratch').write_bytes",
        "network_socket": "connection.connect",
    }.get(name)
    if expected_call is not None:
        assert expected_call in calls
    if name == "memory":
        allocation = next(
            node
            for node in ast.walk(forward)
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "bytearray"
        ).args[0]
        # Nonzero initialization touches the pages instead of relying on lazy zero allocation.
        assert isinstance(allocation, ast.BinOp) and isinstance(allocation.op, ast.Mult)
        assert isinstance(allocation.left, ast.Constant)
        assert isinstance(allocation.left.value, bytes) and any(allocation.left.value)
    if name in {"memory", "time", "scratch_flood", "fork_bomb"}:
        assert any(
            isinstance(node, ast.While)
            and isinstance(node.test, ast.Constant)
            and node.test.value is True
            for node in ast.walk(forward)
        )
