"""The synthetic exam's build module (X1): what a family no code names serves to a build. Synthetic, public, no science.

Eight rows of y = x0 + x1. Imported as ``carbon.zz_synthetic_build`` only by the conformance test, which adds this directory to
the package's search path; no code in ``carbon`` names it.
"""

from __future__ import annotations

import hashlib

import numpy as np

from carbon.development_session.profile import canonical, digest

SCOPE = "PUBLIC_ZZ_SYNTHETIC_DEVELOPMENT_ONLY"
LIMITS_SCHEMA = "carbon.zz-synthetic.bundle-construction-limits.v1"
RESOURCE_SCHEMA = "carbon.zz-synthetic.reconstruction-resources.v1"
ROWS, INPUTS, OUTPUTS = 8, 2, 1


def _arrays():
    inputs = np.arange(ROWS * INPUTS, dtype="<f4").reshape(ROWS, INPUTS)
    return inputs, inputs.sum(axis=1, keepdims=True)


def train_bytes() -> bytes:
    from carbon.challenge_kit import physical_public_train

    return physical_public_train._npz(*_arrays())


def graph_spec() -> dict:
    """The version's ``graph_spec`` (`exam_build.SPEC_FIELDS`)."""
    return {
        "train_sha256": hashlib.sha256(train_bytes()).hexdigest(),
        "rows": ROWS,
        "inputs": INPUTS,
        "outputs": OUTPUTS,
        "dtype": "float32",
        "trainer": "v2",
        "layout": None,
        "trust_outputs": 0,
    }


def load_public_train(challenge_id: str, version: str) -> dict:
    inputs, targets = _arrays()
    return {
        "train": train_bytes(),
        "inputs": inputs,
        "targets": targets,
        "case_ids": tuple(f"train-{index:04d}" for index in range(ROWS)),
        "provenance": {"train_sha256": "sha256:" + graph_spec()["train_sha256"]},
    }


def interface_document(challenge_id: str, version: str) -> dict:
    return {
        "schema": "carbon.zz-synthetic.construction-interface.v1",
        "challenge": {"id": challenge_id, "version": version},
        "train_dtype": "<f4",
        "input": {"names": ["x0", "x1"], "units": ["1", "1"], "shape": [INPUTS]},
        "output": {"names": ["y"], "units": ["1"], "shape": [OUTPUTS]},
    }


def construction_limits_document(challenge_id: str, version: str) -> dict:
    from carbon.challenge_kit import served_versions, version_registry
    from carbon.challenge_kit.task_wall_overrides import total_wall_seconds
    from carbon.development_session import graph_adapters
    from carbon.development_session.research_carrier import (
        LIBRARY_BUILD_PROVENANCE,
        _worker_profile,
    )

    wall = version_registry.entry(challenge_id, version).rebuild_wall_seconds
    profile = _worker_profile(
        None,
        LIBRARY_BUILD_PROVENANCE,
        served_versions.worker_resources(challenge_id, version),
        rebuild_wall_seconds=wall,
    ).body
    return {
        "schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "challenge": {"id": challenge_id, "version": version},
        "train_cases": ROWS,
        "train_dtype": "<f4",
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
            "total_reconstruction_wall_seconds_max": total_wall_seconds(
                challenge_id, version, wall
            ),
            "network": profile["security"]["network"],
            "cleanup_required": True,
        },
        "graph_training_adapter": graph_adapters.adapter_block(challenge_id, version),
        "training_step_cap": None,
        "training_limit": "build_wall_seconds_max",
        "accuracy_gate": None,
        "live_eligible": False,
    }


def construction_kit(challenge_id: str, version: str) -> dict:
    return {
        "id": challenge_id,
        "version": version,
        "train_digest": "sha256:" + graph_spec()["train_sha256"],
        "interface_digest": digest(
            canonical(interface_document(challenge_id, version))
        ),
        "construction_limits_digest": digest(
            canonical(construction_limits_document(challenge_id, version))
        ),
    }


def trusted_material(challenge_id: str, version: str) -> dict:
    return {
        "limits_document": construction_limits_document(challenge_id, version),
        "limits_schema": LIMITS_SCHEMA,
        "scope": SCOPE,
        "resource_schema": RESOURCE_SCHEMA,
    }


def development_bank(challenge_id: str, version: str) -> dict:
    inputs, references = _arrays()
    return {
        "case_ids": tuple(f"practice-{index:04d}" for index in range(ROWS)),
        "cohorts": ("practice",) * ROWS,
        "inputs": inputs + 0.5,
        "references": references + INPUTS * 0.5,
        "reference_records": [{"status": "OK"}] * ROWS,
        "solver_evidence": b"{}\n",
    }


def physics_contract(challenge_id: str, version: str) -> dict:
    return {"version": "zz-synthetic-physics-v1", "definition": {"law": "y = x0 + x1"}}


def public_roles(challenge_id: str, version: str) -> dict:
    return {
        "construction_kit": canonical(construction_kit(challenge_id, version)),
        "interface": canonical(interface_document(challenge_id, version)),
        "train": train_bytes(),
        "physics_contract": canonical(physics_contract(challenge_id, version)),
    }


# -- the practice measurement (`direct_campaign.registered`): what its research campaign reports. Synthetic scale 1.

PRACTICE_COMPONENTS = (("mean", "Mean error"), ("worst", "Worst error"))


def train_facts(challenge_id: str, version: str) -> dict:
    return {
        "train_cases": ROWS,
        "train_dtype": "<f4",
        "train_provenance_sha256": "sha256:" + graph_spec()["train_sha256"],
        "file": "train.npz",
        "format": "npz: inputs and targets, float32",
    }


def error_scale(challenge_id: str, version: str) -> dict:
    return {
        "record": "synthetic",
        "scales": {"y": {"value": 1.0, "unit": "1"}},
        "error": "abs(prediction - reference) / scale",
        "aggregation": "max(mean, worst) over the bank",
        "direction": "lower_is_better",
    }


def practice_summary(challenge_id: str, version: str, rows, material: dict) -> dict:
    errors = np.abs(np.asarray(rows) - material["practice_reference"])
    components = {"mean": float(errors.mean()), "worst": float(errors.max())}
    return {
        "cases": len(rows),
        "outputs": ["y"],
        "score": components["worst"],
        "aggregate_error": components["worst"],
        "components": components,
        "error_scale": error_scale(challenge_id, version),
        "status": "aggregate_on_registered_scale",
    }
