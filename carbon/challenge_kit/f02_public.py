"""Prospective public f02 construction identity for TRAIN40-v2.

Describes a DEVELOPMENT-only numeric interface (one rectangular burst schedule
in the fixed cold context -> its spatial peak top temperature) and the actual
C-03 worker envelope. It provides no held-out references or evaluation
authority.
"""

from __future__ import annotations

import hashlib
import json

from . import f02_train

LIMITS_SCHEMA = "carbon.f02.bundle-construction-limits.v1"
SCOPE = "PUBLIC_F02_DEVELOPMENT_ONLY"
RESOURCE_SCHEMA = "carbon.f02.reconstruction-resources.v1"
INTERFACE_SCHEMA = "carbon.f02.construction-interface.v1"


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
    if challenge_id != f02_train.CHALLENGE_ID or version != f02_train.CHALLENGE_VERSION:
        raise ValueError("unknown public f02 Challenge identity")
    return f02_train.load_public_train(version)["provenance"]


def interface_document(challenge_id: str, version: str) -> dict:
    """One (peak power, on-time) row maps to one peak top temperature."""
    provenance = _check_identity(challenge_id, version)
    return {
        "schema": INTERFACE_SCHEMA,
        "challenge": {"id": challenge_id, "version": version},
        "train_dtype": "<f4",
        "context": dict(provenance["context"]),
        "input": {
            "names": list(f02_train.FIELDS),
            "units": ["W", "s"],
            "shape": [len(f02_train.FIELDS)],
        },
        "output": {
            "names": list(f02_train.TARGETS),
            "units": ["degC"],
            "shape": [len(f02_train.TARGETS)],
            "named_slices": {
                name: [index, index + 1] for index, name in enumerate(f02_train.TARGETS)
            },
        },
        "one_row_per_schedule": True,
        "analytic_extra_energy": provenance["analytic_extra_energy"],
        "learned_targets_only": True,
    }


def construction_limits_document(challenge_id: str, version: str) -> dict:
    """TRAIN40-v2 status and the currently enforced finite C-03 envelope."""
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
        "train_provenance_sha256": "sha256:" + f02_train.PROVENANCE_SHA256,
        "train_strata": provenance["strata"],
        "train_peak_std_c": dict(provenance["train_peak_std_c"]),
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
    """Five-field prospective kit bound to TRAIN40-v2's exact bytes."""
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
