"""PLT-06 fixture preparation only: validate isolation, read sources as data, never run them.

The Graphite executor supplies fresh Docker inspection of its own bounded
Launchpad probe container. These checks do not constitute security acceptance.
No container is created, no model imported and no readiness result written here.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

UNLIMITED_LANE = "carbon.miner-research.unlimited.v1"
# Prospective fixture contract, not a lane installed or activated by this module.
BOUNDED_LANE = "carbon.miner-research.bounded.v1"
LANE_LABEL = "org.opencontainers.image.carbon.lane"
SOURCE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures/level4_staging/hostile_models"
)
PROBES = {
    "memory": {
        "expected": ("typed_refusal", "bounds_held"),
        "observe": "memory-limit enforcement, whole-container cleanup, no submission",
    },
    "time": {
        "expected": ("timeout",),
        "observe": "supervisor deadline, whole-container cleanup, no submission",
    },
    "scratch_flood": {
        "expected": ("typed_refusal", "bounds_held"),
        "observe": "scratch byte/inode limit enforcement, no host-disk flood, no submission",
    },
    "fork_bomb": {
        "expected": ("timeout", "bounds_held"),
        "observe": "PID limit enforcement, whole-process-tree cleanup, no submission",
    },
    "outside_scratch": {
        "expected": ("typed_refusal",),
        "observe": "write denied; outside-scratch marker absent; no submission",
    },
    "network_socket": {
        "expected": ("typed_refusal", "timeout"),
        "observe": "socket connection denied, network none, no submission",
    },
}


class ProbeRefused(ValueError):
    """A non-echoing refusal before source preparation or lowering."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _positive(value):
    return type(value) is int and value > 0


def _tmpfs_limit(options, name):
    entries = [part for part in options if part.startswith(name + "=")]
    pattern = (
        r"size=[1-9][0-9]*[kKmMgG]?" if name == "size" else r"nr_inodes=[1-9][0-9]*"
    )
    return len(entries) == 1 and re.fullmatch(pattern, entries[0]) is not None


def require_probe_container(inspected, *, image_id, container_id, wall_seconds):
    """Check the executor's fresh inspection, pinned identity and explicit deadline.

    The deadline is returned in the plan for the Launchpad supervisor to enforce.
    A resource-profile label alone never suffices; scratch must be capped tmpfs.
    """
    if type(inspected) is not dict:
        raise ProbeRefused("hostile_probe_inspection_required")
    config = inspected.get("Config")
    host = inspected.get("HostConfig")
    if type(config) is not dict or type(host) is not dict:
        raise ProbeRefused("hostile_probe_inspection_required")
    labels = config.get("Labels")
    lane = labels.get(LANE_LABEL) if type(labels) is dict else None
    if lane == UNLIMITED_LANE:
        raise ProbeRefused("hostile_probe_unlimited_lane")
    if lane != BOUNDED_LANE:
        raise ProbeRefused("hostile_probe_bounded_lane_required")
    if (
        type(image_id) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None
        or type(container_id) is not str
        or re.fullmatch(r"[0-9a-f]{64}", container_id) is None
        or inspected.get("Image") != image_id
        or inspected.get("Id") != container_id
        or type(inspected.get("State")) is not dict
        or inspected["State"].get("Running") is not True
    ):
        raise ProbeRefused("hostile_probe_container_identity")
    if (
        not _positive(wall_seconds)
        or any(
            not _positive(host.get(key)) for key in ("Memory", "NanoCpus", "PidsLimit")
        )
        or type(host.get("MemorySwap")) is not int
        or host["MemorySwap"] != host["Memory"]
    ):
        raise ProbeRefused("hostile_probe_resource_bounds_required")
    if (
        host.get("NetworkMode") != "none"
        or host.get("ReadonlyRootfs") is not True
        or host.get("Privileged") is not False
        or host.get("PidMode") not in ("", "private")
        or host.get("IpcMode") not in ("", "private")
        or host.get("CapAdd")
        or host.get("CapDrop") != ["ALL"]
        or type(host.get("SecurityOpt")) is not list
        or "no-new-privileges=true" not in host["SecurityOpt"]
        or host.get("Devices")
        or host.get("DeviceRequests")
        or host.get("PortBindings")
        or host.get("PublishAllPorts")
        or re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", str(config.get("User"))) is None
    ):
        raise ProbeRefused("hostile_probe_isolation_required")
    mounts = inspected.get("Mounts")
    if type(mounts) is not list or any(
        type(row) is not dict or type(row.get("Destination")) is not str
        for row in mounts
    ):
        raise ProbeRefused("hostile_probe_scratch_bounds_required")
    by_target = {row.get("Destination"): row for row in mounts}
    tmpfs = host.get("Tmpfs")
    scratch_options = tmpfs.get("/scratch") if type(tmpfs) is dict else None
    options = scratch_options.split(",") if type(scratch_options) is str else []
    if (
        len(mounts) != 2
        or set(by_target) != {"/input", "/scratch"}
        or by_target["/input"].get("RW") is not False
        or by_target["/scratch"].get("Type") != "tmpfs"
        or by_target["/scratch"].get("RW") is not True
        or not {"rw", "nosuid", "nodev", "noexec"} <= set(options)
        or not _tmpfs_limit(options, "size")
        or not _tmpfs_limit(options, "nr_inodes")
    ):
        raise ProbeRefused("hostile_probe_scratch_bounds_required")


def prepare_probe_sources(inspected, *, image_id, container_id, wall_seconds):
    """Return source text and expectations only after the guard; never execute it."""
    require_probe_container(
        inspected,
        image_id=image_id,
        container_id=container_id,
        wall_seconds=wall_seconds,
    )
    sources = []
    for name, expectation in PROBES.items():
        raw = (SOURCE_ROOT / (name + ".py.txt")).read_bytes()
        sources.append(
            {
                "probe": name,
                "filename": name + ".py",
                "source": raw.decode("utf-8"),
                "source_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "started_marker": "HOSTILE_L4_PROBE:" + name,
                "expected_outcomes": list(expectation["expected"]),
                "required_observations": expectation["observe"],
            }
        )
    return {
        "schema": "carbon.level4.hostile-probe-sources.v1",
        "lane": BOUNDED_LANE,
        "image_id": image_id,
        "container_id": container_id,
        "wall_seconds": wall_seconds,
        "sources": sources,
    }
