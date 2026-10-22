"""Registered public Battery material for prospective bundle construction.

This is a source selection boundary, not an exam or scoring registration. The
original gzip TRAIN bytes remain the identity used by the isolated worker.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from carbon.challenge_kit.served_versions import material_allowlist_bytes
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
    allowed = material_allowlist_bytes(
        challenge.CHALLENGE.challenge_id, challenge.CHALLENGE.version
    )
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


#: Battery's served construction versions, as `carbon.challenge_kit.
#: served_versions` registers them: 1.0 as above, unchanged; 2.0 the step-2
#: version (STEP2_BATCH_VERSIONS_20261020); 2.1 2.0's serving with allowlist
#: v7 (Validator, 2026-10-20); 2.2 2.1 plus the backbone catalog, served by its
#: own adapter (`catalog_version`; Validator, 2026-10-22).
VERSIONS = ("1.0", "2.0", "2.1", "2.2")
LIMITS_SCHEMA_V2 = "carbon.battery.bundle-construction-limits.v2"
PHYSICS_VERSION = "battery-physics-v2"


def _version(version: str) -> str:
    if version not in VERSIONS:
        raise challenge.MaterialMismatch(
            f"unregistered Battery construction version {version!r}"
        )
    return version


def construction_limits_document_for(version: str, rows: int | None = None) -> dict:
    """A version's limits: 1.0's bytes as above; 2.0 with no fixed training-step
    cap, the build wall time its only training limit (OWNER-REBUILD-TIME-
    LIMIT-01), and its graded query's row count. A catalog version's limits
    are its served material's (`catalog_version`)."""
    from . import catalog_version

    if version in catalog_version.VERSIONS:
        raise challenge.MaterialMismatch(
            f"Battery {version} limits are its served material's"
        )
    if _version(version) == "1.0":
        return construction_limits_document()
    if type(rows) is not int or rows <= 0:
        raise challenge.MaterialMismatch(
            f"Battery {version} limits need the bank's row count"
        )
    document = construction_limits_document()
    document["schema"] = LIMITS_SCHEMA_V2
    document["challenge"] = {"id": challenge.CHALLENGE.challenge_id, "version": version}
    document["practice_cases"] = rows
    document["training_step_cap"] = None
    document["training_limit"] = "build_wall_seconds_max"
    return document


def versioned_material(version: str, root: Path | None = None) -> dict:
    """The served construction material of an exact Battery version; no default.

    1.0 is `bundle_material` unchanged. 2.0 serves Data Collection's bank
    (`physical_pack.development_bank`, the reference_present mask interface
    §3): the graded query is the bank's rows in its order, absent references
    stay NaN beside the authoritative mask, the physics role is the
    {version, definition} envelope, and the allowlist is v6. 2.1 is 2.0's
    serving on its own bank label with allowlist v7. 2.2 is 2.1's material
    plus the backbone catalog binding, from its own adapter (`catalog_version`).
    """
    from carbon.challenge_kit import physical_pack
    from carbon.challenge_kit.served_versions import material_allowlist_bytes
    from carbon.registry import ChallengeKey

    from . import catalog_version

    if version in catalog_version.VERSIONS:
        return catalog_version.material(version, root)
    if _version(version) == "1.0":
        return bundle_material(root)
    material = bundle_material(root)
    bank = physical_pack.development_bank(challenge.CHALLENGE.challenge_id, version)
    inputs = np.array(bank["inputs"], dtype=np.float64)
    references = np.array(bank["references"], dtype=np.float64)
    present = tuple(bank["reference_present"])
    cohorts = tuple(bank["cohorts"])
    n = len(bank["case_ids"])
    if (
        inputs.shape != (n, len(domain.INPUTS))
        or references.shape != (n, construction_material.OUTPUT_WIDTH)
        or len(present) != n
        or len(cohorts) != n
        or not all(type(p) is bool for p in present)
        or not np.isfinite(inputs).all()
        or any(
            (p and not np.isfinite(row).all()) or (not p and not np.isnan(row).all())
            for p, row in zip(present, references, strict=True)
        )
    ):
        raise challenge.MaterialMismatch(
            f"reference_invalid: Battery {version} bank rows"
        )
    limits = construction_limits_document_for(version, rows=n)
    physics = {"version": PHYSICS_VERSION, "definition": material["physics_contract"]}
    allowed = material_allowlist_bytes(challenge.CHALLENGE.challenge_id, version)
    material.update(
        {
            "challenge_key": ChallengeKey(challenge.CHALLENGE.challenge_id, version),
            "construction_kit": {
                **material["construction_kit"],
                "version": version,
                "construction_limits_digest": digest(canonical(limits)),
            },
            "example": inputs.copy(),
            "practice_inputs": inputs,
            "practice_case_ids": tuple(bank["case_ids"]),
            "practice_reference": references,
            "reference_present": present,
            "practice_cohorts": cohorts,
            # What public practice feedback and fixture targets read: the
            # PRACTICE rows with a reference, the same 200 cases as 1.0.
            "public_practice_rows": tuple(
                i
                for i, (cohort, p) in enumerate(zip(cohorts, present, strict=True))
                if cohort == "practice" and p
            ),
            "expected_output_shape": references.shape,
            "allowlist_bytes": allowed,
            "allowlist_digest": Allowlist(allowed).digest,
            "construction_limits_document": limits,
            "physics_contract": physics,
            "physics_digest": digest(canonical(physics)),
        }
    )
    material["resource_facts"] = {
        **material["resource_facts"],
        "practice_input_bytes": int(inputs.nbytes),
        "practice_reference_bytes": int(references.nbytes),
    }
    return material
