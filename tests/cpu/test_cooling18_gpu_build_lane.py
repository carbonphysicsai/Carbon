"""Cooling 1.8 graph builds on the A100 GPU build lane (C5g; exam-cooling 20 Nov 2026, was TE3's 19 Nov plan): the
SAME class and per-box shape as Motor 1.8, so the owner's A100 acceptance and the A100 ops record serve it unchanged and
the receiver binds the class (`graph_gpu_lane`) exactly as Motor's door does. No ssh, no docker, no GPU.
"""

from __future__ import annotations

import json

import pytest

from carbon.challenge_kit import served_versions
from carbon.development_session import graph_gpu_lane
from carbon.level4.allowlist import Allowlist
from carbon.reconstruction import hardware_acceptance, remote_gpu_build
from carbon.reconstruction.worker import accelerator_runtime

A100 = "NVIDIA A100-SXM4-40GB"
COOLING = ("chip-cold-plate", "1.8")
MOTOR = ("electric-motor-magnetics", "1.8")


def test_cooling_1_8_has_motor_1_8s_values_row():
    row = remote_gpu_build.values_row(*COOLING)
    assert row == {"device_kind": A100, "slots": 4, "memory": "shared"}
    assert row == remote_gpu_build.values_row(*MOTOR)
    # other Cooling versions keep today's path (no row: no lane)
    assert remote_gpu_build.values_row("chip-cold-plate", "1.6") is None


def test_the_a100_ops_record_measured_for_motor_admits_cooling_graphs():
    """The ops record names the allowlist it was measured against (`graph_gpu_lane.load_record`); both versions serve
    the same graph allowlist, so the record the A100 class check wrote for Motor 1.8 is valid for Cooling 1.8.
    """
    motor = Allowlist(served_versions.material_allowlist_bytes(*MOTOR)).digest
    cooling = Allowlist(served_versions.material_allowlist_bytes(*COOLING)).digest
    assert cooling == motor
    raw = json.dumps(
        {
            "allowlist_digest": motor,
            "class_record_digest": "sha256:" + "1" * 64,
            "ops": ["add"],
            "schema": graph_gpu_lane.SCHEMA,
        }
    ).encode()
    assert graph_gpu_lane.load_record(raw, allowlist_digest=cooling) == {"add"}


def test_the_owner_a100_acceptance_covers_the_class_on_finney_only():
    entry = hardware_acceptance.require_accepted(
        A100, hardware_acceptance.JAX_GPU, "finney"
    )
    assert entry["record"] == "OWNER-A100-40GB-BUILD-CLASS-01"
    # a rehearsal door on another network refuses at start: the acceptance names finney only
    with pytest.raises(hardware_acceptance.DeviceClassNotAccepted):
        hardware_acceptance.require_accepted(
            A100, hardware_acceptance.JAX_GPU, "testnet"
        )


def test_a_cooling_door_with_a_boxes_directory_binds_the_a100_class(
    tmp_path, monkeypatch
):
    root = tmp_path / "accelerators"
    monkeypatch.setattr(accelerator_runtime, "HOST_ROOT", root)
    # no boxes directory and no local lane: today's path (graphs build where they build today)
    assert remote_gpu_build.door_pool(*COOLING) is None
    (root / remote_gpu_build.BOXES_DIR).mkdir(parents=True)
    pool = remote_gpu_build.door_pool(*COOLING)
    assert (pool.kind, pool.slots, pool.memory, pool.local) == (
        A100,
        4,
        "shared",
        None,
    )
    assert remote_gpu_build.GpuClass(pool.kind).door_binding() == {
        "kind": A100,
        "class": True,
    }
    # the same class fingerprint as a Motor door on the same host: one pool of boxes
    assert remote_gpu_build.fingerprint(pool) == remote_gpu_build.fingerprint(
        remote_gpu_build.door_pool(*MOTOR)
    )
    assert remote_gpu_build.door_build_slots(*COOLING) == 4 * remote_gpu_build.MAX_BOXES
