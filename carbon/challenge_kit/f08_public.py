"""Prospective public f08 construction identity for its partial TRAIN bank.

The existing 255-row float32 artifact is reused byte-for-byte. This module
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
    if challenge_id != f08_train.CHALLENGE_ID or version != f08_train.CHALLENGE_VERSION:
        raise ValueError("unknown public f08 Challenge identity")
    return f08_train.load_public_train()["provenance"]


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
    return {
        "schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": challenge_id, "version": version},
        "train_cases": len(provenance["case_ids"]),
        "train_dtype": "<f4",
        "train_case_ids_sha256": _digest(provenance["case_ids"]),
        "train_provenance_sha256": "sha256:" + f08_train.PROVENANCE_SHA256,
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
