"""Prospective direct-construction identity for Battery public DEVELOPMENT.

The fixed TRAIN file, raw model I/O and public DEVELOPMENT construction limits
are Challenge-owned. Limits below reuse existing owner-accepted graph gates,
registered Battery training surfaces and the C-03 CPU worker envelope. A
miner's own host profile or observed device is separate run provenance. The
public graph worker uses this kit; it does not qualify an exam or serve bundles.
"""

from __future__ import annotations

import hashlib
import json

from . import challenge, domain


def interface_document() -> dict:
    """External raw Battery model boundary, independent of backbone family."""
    return {
        "schema": "carbon.battery.construction-interface.v1",
        "input": {
            "names": list(domain.INPUTS),
            "shape": [len(domain.INPUTS)],
            "preprocessing": "raw ordered TRAIN inputs; recipe-owned transforms stay inside the model",
        },
        "output": {
            "voltage_v": [domain.GRID_POINTS],
            "temperature_c": [domain.GRID_POINTS],
            "plating_margin_v": [],
            "capacity_ah": [len(domain.CAPACITY_CYCLES)],
        },
        "decoder": (
            "inverse TRAIN mean/std per output, then fixed voltage, temperature, "
            "plating and capacity split; no MLP or DeepONet scaffold"
        ),
    }


def interface_digest() -> str:
    body = json.dumps(interface_document(), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def construction_limits_document() -> dict:
    """Current bounded graph DEVELOPMENT envelope; no new numerical values."""
    from carbon.level4 import allowlist, intake
    from carbon.level4 import compile as graph_compile
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        catalog_surfaces,
    )
    from carbon.reconstruction.worker import model as worker

    surfaces = {
        name: {
            "kind": row[1],
            "low": list(row[2]) if type(row[2]) is tuple else row[2],
            "high": row[3],
            "default": row[4],
        }
        for name, row in catalog_surfaces(BATTERY_CHALLENGE).items()
        if row[0] == "train"
    }
    return {
        "schema": "carbon.battery.construction-limits.v1",
        "scope": "PUBLIC_DEVELOPMENT_GRAPH_CPU",
        "train_cases": challenge.TRAIN_V1_CASES,
        "train_surfaces": surfaces,
        "graph_intake": dict(intake.BOUNDS),
        "graph_caps": dict(allowlist.CAPS),
        "graph_compile_deadline_seconds": graph_compile.DEADLINE_SECONDS,
        "worker": {
            "profile_id": worker.PROFILE_ID,
            "profile_version": worker.PROFILE_VERSION,
            "cpu_count": worker.CPU_COUNT,
            "memory_bytes": worker.MEMORY_BYTES,
            "swap_bytes": worker.SWAP_BYTES,
            "pids_limit": worker.PIDS_LIMIT,
            "nofile_limit": worker.NOFILE_LIMIT,
            "productive_deadline_seconds": worker.PRODUCTIVE_DEADLINE_SECONDS,
            "scratch_bytes": worker.SCRATCH_BYTES,
            "input_bytes": worker.INPUT_BYTES,
            "output_bytes": worker.OUTPUT_BYTES,
        },
        "budget_status": "TRAINING_BUDGET_CALCULATOR_UNAVAILABLE_FOR_DIRECT_GRAPH",
    }


def construction_limits_digest() -> str:
    body = json.dumps(
        construction_limits_document(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def construction_kit() -> dict:
    """Exact five-field public DEVELOPMENT graph kit."""
    return {
        "id": challenge.CHALLENGE.challenge_id,
        "version": challenge.CHALLENGE.version,
        "train_digest": "sha256:" + challenge.TRAIN_V1_SHA256,
        "interface_digest": interface_digest(),
        "construction_limits_digest": construction_limits_digest(),
    }
