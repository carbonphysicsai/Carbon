"""Prospective public f08 construction identity for its partial TRAIN bank.

Version 1.0 reuses the existing 255-row float32 artifact byte-for-byte;
version 1.1 binds TRAIN v2 (those rows plus the 32 near-limit rows). This module
describes a DEVELOPMENT-only numeric interface and the actual C-03 worker
envelope; it does not provide held-out references or evaluation authority.
"""

from __future__ import annotations

import hashlib
import json

from . import f08_train

LIMITS_SCHEMA = "carbon.f08-ribbed-bracket.bundle-construction-limits.v1"
SCOPE = "PUBLIC_F08_DEVELOPMENT_ONLY"
RESOURCE_SCHEMA = "carbon.f08-ribbed-bracket.reconstruction-resources.v1"
INTERFACE_SCHEMA = "carbon.f08-ribbed-bracket.construction-interface.v1"


def _digest(document: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                document, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def _check_identity(challenge_id: str, version: str) -> dict:
    if (
        challenge_id != f08_train.CHALLENGE_ID
        or version not in f08_train.CHALLENGE_VERSIONS
    ):
        raise ValueError("unknown public f08 Challenge identity")
    return f08_train.load_public_train(version)["provenance"]


def interface_document(challenge_id: str, version: str) -> dict:
    """One ordered geometry row maps to seven learned summary outputs."""
    provenance = _check_identity(challenge_id, version)
    return {
        "schema": INTERFACE_SCHEMA,
        "challenge": {"id": challenge_id, "version": version},
        "train_dtype": "<f4",
        "input": {
            "names": list(f08_train.FIELDS),
            "units": ["mm"] * len(f08_train.FIELDS),
            "shape": [len(f08_train.FIELDS)],
        },
        "output": {
            "names": list(f08_train.TARGETS),
            "units": ["mm/N", "mm/N", "Hz", "mm/N", "Hz", "mm/N", "Hz"],
            "shape": [len(f08_train.TARGETS)],
            "named_slices": {
                name: [index, index + 1] for index, name in enumerate(f08_train.TARGETS)
            },
        },
        "one_row_per_geometry": True,
        "analytic_mass": provenance["analytic_mass"],
        "learned_targets_only": True,
    }


def construction_limits_document(challenge_id: str, version: str) -> dict:
    """Partial TRAIN status and the currently enforced finite C-03 envelope."""
    from carbon.development_session.local_diagnostic_plan import MAX_TASK_WALL_SECONDS
    from carbon.development_session.research_carrier import (
        LIBRARY_BUILD_PROVENANCE,
        _worker_profile,
    )

    provenance = _check_identity(challenge_id, version)
    profile = _worker_profile(None, LIBRARY_BUILD_PROVENANCE).body
    provenance_sha256 = (
        f08_train.PROVENANCE_SHA256
        if version == "1.0"
        else f08_train.PROVENANCE_V2_SHA256
    )
    document = {
        "schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": challenge_id, "version": version},
        "train_cases": len(provenance["case_ids"]),
        "train_dtype": "<f4",
        "train_case_ids_sha256": _digest(provenance["case_ids"]),
        "train_provenance_sha256": "sha256:" + provenance_sha256,
        "original_256_complete": provenance["original_256_complete"],
        "failed_case": dict(provenance["failed_case"]),
        "original_action_evaluation_role": provenance[
            "original_action_evaluation_role"
        ],
        "reconstruction_resource_policy": {
            "schema": RESOURCE_SCHEMA,
            "cpu_count_max": profile["cpu"]["count"],
            "memory_bytes_max": profile["memory"]["bytes"],
            "swap_bytes_max": profile["memory"]["swap_bytes"],
            "pids_max": profile["pids"],
            "nofile_max": profile["nofile_per_process"],
            "scratch_bytes_max": profile["scratch"]["bytes"],
            "scratch_inodes_max": profile["scratch"]["inodes"],
            "build_wall_seconds_max": profile["deadline_seconds"],
            "inference_wall_seconds_max": profile["deadline_seconds"],
            "total_reconstruction_wall_seconds_max": MAX_TASK_WALL_SECONDS,
            "network": profile["security"]["network"],
            "cleanup_required": True,
        },
        "accuracy_gate": None,
        "live_eligible": False,
    }
    if version != "1.0":
        # 1.0's document (and so its digest) is unchanged; 1.1 states the
        # near-limit stratum and the TRAIN-versus-exam mesh shift.
        stratum = provenance["near_limit_stratum"]
        document["near_limit_stratum"] = {
            "rows": dict(stratum["rows"]),
            "measured_split": dict(stratum["measured_split"]),
        }
        document["near_limit_action_evaluation_role"] = provenance[
            "near_limit_action_evaluation_role"
        ]
        document["train_mesh"] = dict(provenance["mesh"])
    from .served_versions import step_caps

    if not step_caps(challenge_id, version):
        # OWNER-REBUILD-TIME-LIMIT-01 (a step-2 version): no fixed training-step
        # cap; the build wall time above is the only training limit. Existing
        # versions keep their bytes (as physical_public).
        document["training_step_cap"] = None
        document["training_limit"] = "build_wall_seconds_max"
    _bind_catalog_and_graph_adapter(document, challenge_id, version)
    return document


def _bind_catalog_and_graph_adapter(document: dict, challenge_id: str, version: str):
    """F08 1.4 / F02 2.3 only (the Validator, 2026-10-20): the exact backbone
    catalog the version serves (as `physical_public`) and Carbon's graph
    training adapter, its surfaces and its pinned trainer's digest. Earlier
    versions keep their bytes."""
    from .served_versions import serves_catalog

    if not serves_catalog(challenge_id, version):
        return
    from carbon.backbone_catalog import served
    from carbon.development_session import graph_adapters

    document["backbone_catalog"] = {
        "schema": served.SCHEMA,
        "digest": served.digest(challenge_id, version),
    }
    # v1 on F08 1.4 / F02 2.3, v2 on their graph route v2 successors.
    document["graph_training_adapter"] = graph_adapters.adapter_block(
        challenge_id, version
    )


def construction_kit(challenge_id: str, version: str) -> dict:
    """Five-field prospective kit bound to Packets2's unchanged TRAIN bytes."""
    provenance = _check_identity(challenge_id, version)
    return {
        "id": challenge_id,
        "version": version,
        "train_digest": provenance["train_sha256"],
        "interface_digest": _digest(interface_document(challenge_id, version)),
        "construction_limits_digest": _digest(
            construction_limits_document(challenge_id, version)
        ),
    }


def trusted_material(challenge_id: str, version: str) -> dict:
    """Fresh source-owned selector content for the separate worker guard."""
    limits = construction_limits_document(challenge_id, version)
    return {
        "limits_document": limits,
        "limits_schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "resource_schema": RESOURCE_SCHEMA,
    }
