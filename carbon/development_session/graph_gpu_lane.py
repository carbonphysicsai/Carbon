"""Which device the validator's graph-route rebuild runs on (GPU-1, GPU_REBUILD_RULINGS_20261026).

The graph route is JAX. A validator that holds a JAX GPU worker rebuilds a graph on it only when
EVERY op of the graph (forward, and so its gradient) is one the hardware class has shown to repeat
bit for bit under the pinned determinism flags (`scripts/dev/graph_ops_gpu_rerun.py`, ruling 1:
"an op that fails is admitted CPU-only"). The list of such ops is a record the class check writes
(`carbon.graph-gpu-ops.v1`); with no record, nothing is eligible and every graph rebuilds on the CPU
exactly as before. Fail closed: a graph this module cannot read is a CPU rebuild, never a GPU one.

This module chooses a device; it grades nothing, reads no private data and does not change what a
rebuild computes. The pinned flags themselves are applied by the carrier
(`accelerators.worker_environment`).
"""

from __future__ import annotations

import json

SCHEMA = "carbon.graph-gpu-ops.v1"
_KEYS = {"schema", "allowlist_digest", "class_record_digest", "ops"}


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
    """`MINER_GPU` when this rebuild may run on the GPU, else None (the CPU).

    The GPU needs a JAX GPU worker, a record of GPU-repeatable ops, and a graph whose every op is
    in it."""
    if gpu_image is None or not gpu_ops:
        return None
    from .gpu_practice import gpu_image_backend
    from .research_carrier import MINER_GPU

    if gpu_image_backend(gpu_image) != "jax":
        return None
    ops = submission_ops(source_envelope)
    if not ops or not ops <= gpu_ops:
        return None
    return MINER_GPU
