"""Prospective public Motor/Cooling construction identities and finite limits.

This source-owned DEVELOPMENT selector only describes real pinned TRAIN tensors
and the existing C-03 worker envelope. It has no evaluation or LIVE authority.
"""

from __future__ import annotations

import hashlib
import json

from . import physical_public_train

LIMITS_SCHEMA = "carbon.physical-public.bundle-construction-limits.v1"
SCOPE = "PUBLIC_PHYSICAL_DEVELOPMENT_ONLY"
RESOURCE_SCHEMA = "carbon.physical-public.reconstruction-resources.v1"


def _digest(value: dict) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def _identity(challenge_id: str, version: str):
    challenge, domain, count = physical_public_train._source(challenge_id)
    if version != challenge.CHALLENGE.version:
        raise ValueError("unknown public physical Challenge version")
    return challenge, domain, count


def interface_document(challenge_id: str, version: str) -> dict:
    """Checked numeric boundary; native named output slices remain explicit."""
    _identity(challenge_id, version)
    return physical_public_train.numeric_interface_document(challenge_id)


def construction_limits_document(challenge_id: str, version: str) -> dict:
    """Exact current C-03 bounds, with no inferred scientific limits."""
    from carbon.development_session.local_diagnostic_plan import MAX_TASK_WALL_SECONDS
    from carbon.development_session.research_carrier import (
        LIBRARY_BUILD_PROVENANCE,
        _worker_profile,
    )

    _, _, count = _identity(challenge_id, version)
    profile = _worker_profile(None, LIBRARY_BUILD_PROVENANCE).body
    return {
        "schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": challenge_id, "version": version},
        "train_cases": count,
        "train_dtype": "<f8",
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
    """Five-field prospective normal binding, only for verified public TRAIN."""
    _identity(challenge_id, version)
    provenance = physical_public_train.load_public_train(challenge_id)["provenance"]
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
    """Fresh source-owned selector content for the worker guard to compare."""
    limits = construction_limits_document(challenge_id, version)
    return {
        "limits_document": limits,
        "limits_schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "resource_schema": RESOURCE_SCHEMA,
    }
