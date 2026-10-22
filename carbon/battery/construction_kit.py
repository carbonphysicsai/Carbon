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


def _train_surfaces(version: str | None = None) -> dict:
    """The registered training surfaces an exact version serves
    (`capability_registry.catalog_surfaces`; None: the published contract)."""
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        catalog_surfaces,
    )

    return {
        name: {
            "kind": row[1],
            "low": list(row[2]) if type(row[2]) is tuple else row[2],
            "high": row[3],
            "default": row[4],
        }
        for name, row in catalog_surfaces(BATTERY_CHALLENGE, version).items()
        if row[0] == "train"
    }


def construction_limits_document() -> dict:
    """Current bounded graph DEVELOPMENT envelope; no new numerical values."""
    from carbon.level4 import allowlist, intake
    from carbon.level4 import compile as graph_compile
    from carbon.reconstruction.worker import model as worker

    surfaces = _train_surfaces()
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


#: The graph kit's registered versions: 1.0 above, unchanged; 2.0 the step-2
#: version (STEP2_BATCH_VERSIONS_20261020), with no fixed training-step caps;
#: 2.1 the catalog version, 2.0's limits under its own version binding.
VERSIONS = ("1.0", "2.0", "2.1")
#: The training surfaces whose upper bound was a fixed step cap; for 2.0 they
#: keep only their lower bounds and dependency rules (warmup below the main
#: steps, polish leaving 16 main steps: `battery.compile.rebuild_issues`).
STEP_SURFACES = ("steps", "warmup_steps", "polish_steps")


def _version(version: str) -> str:
    if version not in VERSIONS:
        raise challenge.MaterialMismatch(
            f"unregistered Battery construction version {version!r}"
        )
    return version


def construction_limits_document_for(version: str) -> dict:
    """1.0's limits as above; 2.0 with the step surfaces uncapped and the
    worker's productive deadline named as the only training limit
    (OWNER-REBUILD-TIME-LIMIT-01); 2.1 also publishes its allowlist v7's caps
    and intake bounds (`allowlist.caps_for`, `intake.bounds_for`)."""
    if _version(version) == "1.0":
        return construction_limits_document()
    from carbon.level4 import allowlist, intake

    from .direct_graph import graph_allowlist

    document = construction_limits_document()
    document["schema"] = "carbon.battery.construction-limits.v2"
    document["challenge"] = {"id": challenge.CHALLENGE.challenge_id, "version": version}
    document["train_surfaces"] = _train_surfaces(version)
    # The caps and intake bounds the version's graph allowlist is measured
    # against: the owner's CAPS and BOUNDS under v6 (2.0, unchanged), and
    # containment only under v7 (2.1; owner, 2026-10-21: no model-size caps).
    served = graph_allowlist(version)
    document["graph_caps"] = allowlist.caps_for(served)
    document["graph_intake"] = intake.bounds_for(served)
    for name in STEP_SURFACES:
        document["train_surfaces"][name]["high"] = None
    document["training_step_cap"] = None
    document["training_limit"] = "worker.productive_deadline_seconds"
    return document


def construction_kit_for(version: str) -> dict:
    """The exact five-field graph kit of a registered Battery version."""
    if _version(version) == "1.0":
        return construction_kit()
    body = json.dumps(
        construction_limits_document_for(version),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return {
        **construction_kit(),
        "version": version,
        "construction_limits_digest": "sha256:"
        + hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }
