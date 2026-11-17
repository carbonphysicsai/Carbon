"""Which device the validator's graph-route rebuild runs on (OWNER-GPU-REBUILD-RENTED-4090-01; GPU_REBUILD_RULINGS_20261026).

The graph route is JAX. A validator that holds a JAX GPU worker and its hardware class's passing class check (the
record it writes, `carbon.graph-gpu-ops.v1`) rebuilds EVERY graph on that GPU (OWNER-GPU-LANE-NO-OP-GATE-01, 17 Nov
2026: the per-op eligibility gate is dropped; builds on one GPU class are identical). With no record, every graph
rebuilds on the CPU exactly as before. One GPU build per task (owner, 17 Nov): a GPU build that fails is Carbon's
(FAILED_INFRA), and only a rented box's first build is shadowed once on a proven box
(`research_tasks._settle_first_build`). `cpu_forced_ops` and
`OPS_NOTE` remain only to read evidence retained before the gate was dropped.

This module chooses a device; it grades nothing, reads no private data and does not change what a
rebuild computes. The pinned flags themselves are applied by the carrier
(`accelerators.worker_environment`).
"""

from __future__ import annotations

import json

SCHEMA = "carbon.graph-gpu-ops.v1"
_KEYS = {"schema", "allowlist_digest", "class_record_digest", "ops"}

#: Why a graph rebuilt on the CPU under a configured lane because of its own ops (retained evidence).
OPS_NOTE = "graph_op_not_gpu_repeatable"

#: The one miner-visible sentence (wording is the Validator's to approve). Op names only.
FALLBACK_NOTICE = (
    "Rebuilt on CPU: the listed graph ops are not on the verified GPU op list."
)


class GpuOpsRecordInvalid(ValueError):
    """The record is not a well-formed `carbon.graph-gpu-ops.v1`."""


def load_record(raw: bytes, *, allowlist_digest: str) -> frozenset:
    """The ops a record admits on the GPU, or `GpuOpsRecordInvalid`.

    The record names the allowlist it was measured against; a record for another allowlist admits
    nothing, because an op's name means what its allowlist says."""
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise GpuOpsRecordInvalid("graph_gpu_ops_not_json") from None
    if (
        type(record) is not dict
        or set(record) != _KEYS
        or record["schema"] != SCHEMA
        or type(record["ops"]) is not list
        or any(type(op) is not str for op in record["ops"])
        or len(set(record["ops"])) != len(record["ops"])
        or type(record["class_record_digest"]) is not str
    ):
        raise GpuOpsRecordInvalid("graph_gpu_ops_malformed")
    if record["allowlist_digest"] != allowlist_digest:
        raise GpuOpsRecordInvalid("graph_gpu_ops_other_allowlist")
    return frozenset(record["ops"])


def submission_ops(source_envelope: bytes):
    """Every op a submitted graph uses, or None when it cannot be read.

    Reads names only, from the submission's graph documents; it is not the validation, which the
    build still performs."""
    from carbon.level4 import staging

    try:
        _, raw_manifest, files = staging.from_envelope(json.loads(source_envelope))
        manifest = json.loads(raw_manifest)
        ops = set()
        for slot, name in manifest["documents"].items():
            if slot == "init_spec":
                continue
            document = json.loads(files[name])
            for graph in document["graphs"].values():
                ops.update(node["op"] for node in graph["nodes"])
        return frozenset(ops)
    except Exception:  # noqa: BLE001 - anything unreadable is a CPU rebuild
        return None


def device_for(source_envelope: bytes, *, gpu_image, gpu_ops):
    """`MINER_GPU` when this rebuild runs on the GPU, else None (the CPU).

    OWNER-GPU-LANE-NO-OP-GATE-01 (17 Nov 2026): every graph rebuilds on a configured lane's GPU. The lane needs a JAX
    GPU worker and the class's own passing class check (its ops record, which the receiver loads and the door binds);
    a graph's own ops no longer gate it. A GPU build that fails, and a lost link or GPU, is Carbon's (FAILED_INFRA).
    """
    if gpu_image is None or not gpu_ops:
        return None
    from .gpu_practice import gpu_image_backend
    from .research_carrier import MINER_GPU

    if gpu_image_backend(gpu_image) != "jax":
        return None
    # a graph this module cannot read stays a CPU rebuild (fail closed); its own ops never gate it
    if not submission_ops(source_envelope):
        return None
    return MINER_GPU


def cpu_forced_ops(source_envelope: bytes, gpu_ops):
    """Always None: a graph's own ops no longer force the CPU (OWNER-GPU-LANE-NO-OP-GATE-01, 17 Nov 2026), so no new
    evidence carries `OPS_NOTE`. Kept, with `OPS_NOTE`, so retained evidence written before the gate was dropped still
    reads."""
    return


def public_lane_facts(gpu_ops, evidence):
    """The lane facts a graph practice result shows its miner: the verified GPU op list, the
    device that built the graph and, when the graph's own ops forced the CPU, those op names and
    the notice. A closed allow-list; every other field of the retained evidence stays private.
    """
    facts = {"gpu_ops": sorted(gpu_ops), "build_device": evidence.get("build_device")}
    if evidence.get("gpu_lane_note") == OPS_NOTE:
        facts["cpu_forced_ops"] = list(evidence["gpu_lane_ops"])
        facts["notice"] = FALLBACK_NOTICE
    return facts
