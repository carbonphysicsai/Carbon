"""Registered public Battery material for prospective bundle construction.

This is a source selection boundary, not an exam or scoring registration. The
original gzip TRAIN bytes remain the identity used by the isolated worker.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from carbon.challenge_kit.synthetic_linear_field_2d import (
    allowlist_v5_bytes,
)
from carbon.challenge_kit.synthetic_linear_field_2d import (
    construction_limits_document as c03_limits,
)
from carbon.development_session.profile import canonical, digest
from carbon.level4.allowlist import Allowlist

from . import challenge, construction_material, domain, practice

PHYSICS_PATH = "carbon/battery/physics_contract.v2.json"
PHYSICS_SHA256 = "7b46380e9a30e78107e4f198059f7a9705835b5bc8072117b8b00fd7590a5632"


def construction_limits_document() -> dict:
    """Reuse C03's enforced finite worker envelope, without a score gate."""
    policy = dict(c03_limits()["reconstruction_resource_policy"])
    policy["schema"] = "carbon.battery.bundle-reconstruction-resources.v1"
    return {
        "schema": "carbon.battery.bundle-construction-limits.v1",
        "scope": "PUBLIC_BATTERY_DEVELOPMENT_ONLY",
        "train_cases": challenge.TRAIN_V1_CASES,
        "practice_cases": practice.PRACTICE_CASES,
        "input_shape": [len(domain.INPUTS)],
        "output_shape": [construction_material.OUTPUT_WIDTH],
        "dtype": "float64",
        "reconstruction_resource_policy": policy,
        "accuracy_gate": None,
        "live_eligible": False,
    }


def interface_document() -> dict:
    """The established Battery raw input and flattened physical output order."""
    return {
        "schema": "carbon.battery.bundle-construction-interface.v1",
        "scope": "PUBLIC_BATTERY_DEVELOPMENT_ONLY",
        "inputs": {"names": list(domain.INPUTS), "dtype": "float64"},
        "outputs": {
            "names": list(domain.OUTPUTS),
            "flat_order": [
                "voltage_v",
                "temperature_c",
                "plating_margin_v",
                "capacity_ah",
            ],
            "width": construction_material.OUTPUT_WIDTH,
            "dtype": "float64",
        },
        "case_axis": "leading, variable positive count",
        "preprocessing": "recipe-owned transforms stay inside the model",
        "postprocessing": "none; raw physical outputs",
    }


def bundle_material(root: Path | None = None) -> dict:
    """Recheck the exact public TRAIN, PRACTICE and contract on every read."""
    repository = Path(__file__).resolve().parents[2] if root is None else Path(root)
    raw = (repository / challenge.TRAIN_V1_PATH).read_bytes()
    train = construction_material.decode_train(raw)
    public = practice.PracticeSet.load(repository)
    reference = domain.TrainingData.from_records(public.records)
    inputs = reference.x.copy()
    targets = np.column_stack((reference.v, reference.t, reference.eta, reference.q))
    if (
        inputs.shape != (practice.PRACTICE_CASES, len(domain.INPUTS))
        or targets.shape
        != (practice.PRACTICE_CASES, construction_material.OUTPUT_WIDTH)
        or not np.isfinite(inputs).all()
        or not np.isfinite(targets).all()
    ):
        raise challenge.MaterialMismatch("public practice tensors differ")
    physics_raw = (repository / PHYSICS_PATH).read_bytes()
    if hashlib.sha256(physics_raw).hexdigest() != PHYSICS_SHA256:
        raise challenge.MaterialMismatch("registered physics contract differs")
    physics = json.loads(physics_raw)
    if (
        type(physics) is not dict
        or physics.get("challenge") != challenge.CHALLENGE.challenge_id
        or physics.get("version") != "battery-physics-v2"
    ):
        raise challenge.MaterialMismatch("registered physics contract differs")
    allowed = allowlist_v5_bytes()
    limits = construction_limits_document()
    interface = interface_document()
    kit = {
        "id": challenge.CHALLENGE.challenge_id,
        "version": challenge.CHALLENGE.version,
        "train_digest": digest(raw),
        "interface_digest": digest(canonical(interface)),
        "construction_limits_digest": digest(canonical(limits)),
    }
    disclosure = {
        "scope": "PUBLIC_BATTERY_DEVELOPMENT_ONLY",
        "train_role": "PUBLIC_TRAIN",
        "practice_role": "PUBLIC_PRACTICE",
        "train_and_practice_labels_public": True,
        "hidden_evaluation": False,
        "official_reference": False,
        "scientifically_qualified": False,
        "live_eligible": False,
    }
    return {
        "challenge_key": challenge.CHALLENGE,
        "construction_kit": kit,
        "train": raw,
        "train_case_ids": train.case_ids,
        "example": inputs.copy(),
        "practice_inputs": inputs,
        "practice_case_ids": tuple(public.case_ids),
        "practice_reference": targets,
        "expected_output_shape": targets.shape,
        "allowlist_bytes": allowed,
        "allowlist_digest": Allowlist(allowed).digest,
        "interface_document": interface,
        "construction_limits_document": limits,
        "physics_contract": physics,
        "physics_digest": digest(canonical(physics)),
        "resource_facts": {
            "train_archive_bytes": len(raw),
            "train_tensor_bytes": int(
                train.x.nbytes
                + train.v.nbytes
                + train.t.nbytes
                + train.eta.nbytes
                + train.q.nbytes
            ),
            "practice_input_bytes": int(inputs.nbytes),
            "practice_reference_bytes": int(targets.nbytes),
            "wall_time_seconds": None,
            "provider_spend_usd": None,
        },
        "disclosure": disclosure,
    }
