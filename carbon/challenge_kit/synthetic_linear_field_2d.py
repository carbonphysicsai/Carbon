"""Public synthetic 2D field fixture for direct construction development.

The entire reference is the dimensionless pointwise map target = forcing / 4.
It is a toy numeric contract, not a Poisson solve, Battery reference, physical
qualification, or official/hidden evaluation pack. Campaign registration and
runtime admission are owned outside this module.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from carbon.registry.model import ChallengeKey

CHALLENGE = ChallengeKey("synthetic-linear-field-2d", "1.0")
TRAIN_CASES = 8
PRACTICE_CASES = 2
TRAIN_CASE_IDS = tuple(f"synthetic-train-{index:02d}" for index in range(TRAIN_CASES))
PRACTICE_CASE_IDS = tuple(
    f"synthetic-practice-{index:02d}" for index in range(PRACTICE_CASES)
)
FIELD_SHAPE = (8, 8, 1)
TRAIN_PATH = (
    Path(__file__).with_name("fixtures") / "synthetic_linear_field_2d_train_v1.npz"
)
TRAIN_SHA256 = "95aec24fe064b05bbb8750820c2c95bfac7117ba56496a58bdcc570b8438b867"
ALLOWLIST_V2_SHA256 = "12a9c047eb5c9e26bd48968ac9d8e2851f8abfc951616ff674eb3998c7e0ede0"
ALLOWLIST_V3_SHA256 = "fb52a96d4dc145a438970b33978e5487dad65ccb67c28081bffcf86c10510311"
ALLOWLIST_V4_SHA256 = "ffbe3d69ae1cefc2300a6b37b22dd28b74f5ed487158138e7db13b841c980eda"
ALLOWLIST_V5_SHA256 = "f26ea734d3078564b72fa30c66ab46cf4419a004ed249130481b517985af3122"


def _digest(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _numpy():
    import numpy as np

    return np


def _public_train_inputs():
    """Eight fixed spatial patterns; no random draw or protected data."""
    np = _numpy()
    row, col = np.indices((8, 8), dtype=np.int32)
    patterns = (
        row + col - 7,
        row - col,
        2 * row - col - 3,
        row + 2 * col - 10,
        (row - 3) * (col - 4),
        (row + col) % 4 * 4 - 6,
        ((row + col) % 2) * 8 - 4,
        (row == col).astype(np.int32) * 8 - 2,
    )
    return np.stack(patterns, axis=0).astype(np.float32)[..., None] / np.float32(8)


def practice_inputs():
    """Two fixed, published input fields for public practice and shape checks."""
    np = _numpy()
    row, col = np.indices((8, 8), dtype=np.int32)
    patterns = (row - 2 * col + 4, (row * 3 + col * 2) % 9 - 4)
    return np.stack(patterns, axis=0).astype(np.float32)[..., None] / np.float32(8)


def public_reference(forcing):
    """Exact declared synthetic target, with no solver or hidden comparison."""
    np = _numpy()
    if (
        type(forcing) is not np.ndarray
        or forcing.dtype != np.float32
        or forcing.ndim != 4
        or forcing.shape[1:] != FIELD_SHAPE
        or not np.isfinite(forcing).all()
    ):
        raise ValueError("finite float32 8x8x1 fields with a case axis required")
    return forcing * np.float32(0.25)


def train_bytes() -> bytes:
    """Return only the pinned public TRAIN archive after semantic verification."""
    np = _numpy()
    raw = TRAIN_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != TRAIN_SHA256:
        raise ValueError("synthetic TRAIN bytes differ from fixture version")
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        if set(data.files) != {"inputs", "targets"}:
            raise ValueError("synthetic TRAIN members differ")
        inputs, targets = data["inputs"], data["targets"]
    if (
        inputs.shape != (TRAIN_CASES, *FIELD_SHAPE)
        or targets.shape != inputs.shape
        or inputs.dtype != np.float32
        or targets.dtype != np.float32
        or not np.array_equal(inputs, _public_train_inputs())
        or not np.array_equal(targets, public_reference(inputs))
    ):
        raise ValueError("synthetic TRAIN tensor relation differs")
    return raw


def physics_contract() -> dict:
    """Versioned complete toy law for ScoreLab identity, never physics validity."""
    return {
        "version": "synthetic-linear-field-2d-v1",
        "definition": {
            "schema": "carbon.synthetic-linear-field-2d.physics.v1",
            "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
            "domain": "dimensionless 8x8 grid; one scalar forcing channel",
            "operator": "target[i,j,0] = 0.25 * forcing[i,j,0]",
            "scale": {"numerator": 1, "denominator": 4},
            "reference_kind": "closed-form pointwise synthetic relation",
            "boundary_conditions": "none; this is not a PDE",
            "dtype": "float32",
            "input_shape": list(FIELD_SHAPE),
            "output_shape": list(FIELD_SHAPE),
            "train_role": "PUBLIC_TRAIN",
            "practice_role": "PUBLIC_PRACTICE",
            "hidden_evaluation": False,
            "physical_qualification": False,
        },
    }


def interface_document() -> dict:
    return {
        "schema": "carbon.synthetic-linear-field-2d.interface.v1",
        "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
        "inputs": {"name": "forcing", "dtype": "float32", "shape": list(FIELD_SHAPE)},
        "outputs": {"name": "target", "dtype": "float32", "shape": list(FIELD_SHAPE)},
        "case_axis": "leading, variable positive count",
        "preprocessing": "none",
        "postprocessing": "none",
    }


def construction_limits_document() -> dict:
    """Versioned engineering limits for this public synthetic Challenge only.

    The CPU, memory, process, file and scratch ceilings match the maintained
    C-03 development worker profile, which the direct bundle's provenance
    actually selects. Each phase's 600-second watchdog matches that carrier's
    bounded worker call. The 1800-second total is the existing bounded
    local diagnostic task envelope: two phases plus finite collection and
    cleanup allowance. These are fixture acceptance maxima, not a private
    operator profile, available host capacity, a scientific threshold, or a
    production default. A direct caller must verify actual enforcement before
    it may advertise practice task admission.
    """
    return {
        "schema": "carbon.synthetic-linear-field-2d.construction-limits.v2",
        "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
        "train_cases": TRAIN_CASES,
        "practice_cases": PRACTICE_CASES,
        "field_shape": list(FIELD_SHAPE),
        "dtype": "float32",
        "reconstruction_resource_policy": {
            "schema": "carbon.synthetic-linear-field-2d.reconstruction-resources.v1",
            "cpu_count_max": 2,
            "memory_bytes_max": 4 * 1024**3,
            "swap_bytes_max": 0,
            "pids_max": 256,
            "nofile_max": 1024,
            "scratch_bytes_max": 512 * 1024**2,
            "scratch_inodes_max": 8192,
            "build_wall_seconds_max": 600,
            "inference_wall_seconds_max": 600,
            "total_reconstruction_wall_seconds_max": 1800,
            "network": "none",
            "cleanup_required": True,
        },
        "accuracy_gate": None,
        "live_eligible": False,
    }


def construction_limits_document_v3() -> dict:
    """Prospective graph adapter identity under the same resource ceilings."""
    document = construction_limits_document()
    document["schema"] = "carbon.synthetic-linear-field-2d.construction-limits.v3"
    document["graph_training_adapter"] = {
        "schema": "carbon.synthetic-linear-field-2d.graph-training-adapter.v1",
        "id": "synthetic-linear-field-2d-public-jax-graph-v1",
        "source_kind": "graph",
        "train_use_dataset": "synthetic-linear-field-2d-public-train",
        "procedure_schema": "carbon.construction-recipe.v1",
        "output_format": "carbon.numeric-graph.v1",
        "state_schema": "carbon.development.graph-source-state.v1",
    }
    return document


def construction_kit() -> dict:
    """Five-field identity consumed by the maintained normal bundle worker."""
    return {
        "id": CHALLENGE.challenge_id,
        "version": CHALLENGE.version,
        "train_digest": "sha256:" + TRAIN_SHA256,
        "interface_digest": _digest(interface_document()),
        "construction_limits_digest": _digest(construction_limits_document()),
    }


def allowlist_v2_bytes() -> bytes:
    from carbon.level4 import allowlist

    path = Path(allowlist.PATH).with_name("allowlist_v2.json")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ALLOWLIST_V2_SHA256:
        raise ValueError("trusted bundle allowlist-v2 bytes differ")
    return raw


def allowlist_v3_bytes() -> bytes:
    """Prospective JAX single-device material; prior material stays unchanged."""
    from carbon.level4 import allowlist

    path = Path(allowlist.PATH).with_name("allowlist_v3.json")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ALLOWLIST_V3_SHA256:
        raise ValueError("trusted bundle allowlist-v3 bytes differ")
    return raw


def allowlist_v4_bytes() -> bytes:
    """Prospective layer-normalization material; prior versions stay pinned."""
    from carbon.level4 import allowlist

    path = Path(allowlist.PATH).with_name("allowlist_v4.json")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ALLOWLIST_V4_SHA256:
        raise ValueError("trusted bundle allowlist-v4 bytes differ")
    return raw


def allowlist_v5_bytes() -> bytes:
    """Prospective observed math material; prior policy bytes stay pinned."""
    from carbon.level4 import allowlist

    path = Path(allowlist.PATH).with_name("allowlist_v5.json")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ALLOWLIST_V5_SHA256:
        raise ValueError("trusted bundle allowlist-v5 bytes differ")
    return raw


def bundle_material() -> dict:
    """Challenge-owned, public bytes and arrays for Lead's campaign adapter."""
    from carbon.level4.allowlist import Allowlist

    practice = practice_inputs()
    allowed = allowlist_v2_bytes()
    train = train_bytes()
    return {
        "challenge_key": CHALLENGE,
        "construction_kit": construction_kit(),
        "train": train,
        "train_case_ids": TRAIN_CASE_IDS,
        "example": practice.copy(),
        "practice_inputs": practice,
        "practice_case_ids": PRACTICE_CASE_IDS,
        "practice_reference": public_reference(practice),
        "expected_output_shape": practice.shape,
        "allowlist_bytes": allowed,
        "allowlist_digest": Allowlist(allowed).digest,
        "interface_document": interface_document(),
        "construction_limits_document": construction_limits_document(),
        "physics_contract": physics_contract(),
        "physics_digest": _digest(physics_contract()),
        "resource_facts": {
            "train_archive_bytes": len(train),
            "train_tensor_bytes": TRAIN_CASES * 8 * 8 * 1 * 4 * 2,
            "practice_input_bytes": int(practice.nbytes),
            "practice_reference_bytes": int(practice.nbytes),
            "wall_time_seconds": None,
            "provider_spend_usd": None,
        },
        "disclosure": {
            "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
            "train_role": "PUBLIC_TRAIN",
            "practice_role": "PUBLIC_PRACTICE",
            "train_and_practice_labels_public": True,
            "hidden_evaluation": False,
            "official_reference": False,
            "scientifically_qualified": False,
            "live_eligible": False,
        },
    }


def bundle_material_v3() -> dict:
    """Prospective version with v3 decoding and the same public TRAIN bytes."""
    from carbon.level4.allowlist import Allowlist

    material = bundle_material()
    allowed = allowlist_v3_bytes()
    challenge = ChallengeKey(CHALLENGE.challenge_id, "1.1")
    material["challenge_key"] = challenge
    material["construction_kit"] = {
        **material["construction_kit"],
        "version": challenge.version,
    }
    material["allowlist_bytes"] = allowed
    material["allowlist_digest"] = Allowlist(allowed).digest
    return material


def bundle_material_v4() -> dict:
    """Prospective v4 graph policy with the same exact public TRAIN bytes."""
    from carbon.level4.allowlist import Allowlist

    material = bundle_material_v3()
    allowed = allowlist_v4_bytes()
    challenge = ChallengeKey(CHALLENGE.challenge_id, "1.2")
    material["challenge_key"] = challenge
    material["construction_kit"] = {
        **material["construction_kit"],
        "version": challenge.version,
    }
    material["allowlist_bytes"] = allowed
    material["allowlist_digest"] = Allowlist(allowed).digest
    return material


def bundle_material_v5() -> dict:
    """Prospective math and graph-training contract on the same public data."""
    from carbon.level4.allowlist import Allowlist

    material = bundle_material_v4()
    allowed = allowlist_v5_bytes()
    limits = construction_limits_document_v3()
    challenge = ChallengeKey(CHALLENGE.challenge_id, "1.3")
    material["challenge_key"] = challenge
    material["construction_kit"] = {
        **material["construction_kit"],
        "version": challenge.version,
        "construction_limits_digest": _digest(limits),
    }
    material["construction_limits_document"] = limits
    material["allowlist_bytes"] = allowed
    material["allowlist_digest"] = Allowlist(allowed).digest
    return material
