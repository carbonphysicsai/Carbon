"""Public Motor, Cooling, F08 and F02 construction material for the direct receiver (DEVELOPMENT only).

The receiver serves a registered Challenge's fixed public TRAIN, interface, limits
and physics contract, and runs the miner's recipe through the normal fresh build
and frozen inference. Every document here comes from the source-owned functions
the evaluation pack is built from (`physical_public`, `physical_pack`), so the
pack's public roles and this material can only agree. The practice query is the
exposed DEVELOPMENT decision bank, so the scored query equals the pack's case
bank byte for byte. Nothing here is a hidden-evaluation role, an official
reference, a qualification or LIVE authority.
"""

from __future__ import annotations

from carbon.cold_plate import challenge as cooling
from carbon.development_session.profile import canonical, digest
from carbon.motor import challenge as motor
from carbon.research import ChallengeKey

from . import (
    f02_public,
    f02_train,
    f08_public,
    f08_train,
    physical_pack,
    physical_public,
    physical_public_train,
)

SCOPE = physical_public.SCOPE
#: Registered public physical Challenges, by (id, version).
REGISTERED = (
    (motor.CHALLENGE.challenge_id, motor.CHALLENGE.version),
    (cooling.CHALLENGE.challenge_id, cooling.CHALLENGE.version),
    # The step-2 versions (STEP2_BATCH_VERSIONS_20261020): served v6, no step caps.
    (motor.CHALLENGE.challenge_id, "1.1"),
    (cooling.CHALLENGE.challenge_id, "1.1"),
    # The backbone-catalog version (OWNER-BACKBONE-CATALOG-01): step-2 serving
    # plus Carbon's tested backbones by catalog id.
    (motor.CHALLENGE.challenge_id, "1.2"),
    # The catalog versions serving allowlist v7 (Validator, 2026-10-20): Motor
    # 1.3 is 1.2 plus v7; Cooling 1.2 serves v7 and no catalog yet.
    (motor.CHALLENGE.challenge_id, "1.3"),
    (cooling.CHALLENGE.challenge_id, "1.2"),
    # Both F08 versions: 1.0 (255-row TRAIN v1) and 1.1 (287-row TRAIN v2, the straddling bank).
    *((f08_train.CHALLENGE_ID, version) for version in f08_train.CHALLENGE_VERSIONS),
    # F02 2.0 (TRAIN40-v2): its own public module and float32 TRAIN, like F08. Named explicitly,
    # so a future version bump in the loader cannot silently move what is served.
    ("f02", "2.0"),
    # F02 2.1 (step 2) and 2.2 (its catalog version, allowlist v7), receivable with their
    # approved packs (Validator, 2026-10-20).
    ("f02", "2.1"),
    ("f02", "2.2"),
)


def is_registered(challenge_id: str, version: str) -> bool:
    return (challenge_id, version) in REGISTERED


def bundle_material(
    challenge_id: str = motor.CHALLENGE.challenge_id,
    version: str = motor.CHALLENGE.version,
) -> dict:
    """Challenge-owned public bytes and arrays for the direct receiver."""
    from carbon.challenge_kit.served_versions import material_allowlist_bytes
    from carbon.level4.allowlist import Allowlist

    if not is_registered(challenge_id, version):
        raise ValueError("unregistered public physical Challenge")
    # F08 (v1: 255 rows, v2: 287) and F02 (40 rows) keep their own public module and float32
    # TRAIN; the rest shares one.
    f08 = challenge_id == f08_train.CHALLENGE_ID
    f02 = challenge_id == f02_train.CHALLENGE_ID
    public = f08_public if f08 else f02_public if f02 else physical_public
    if f08:
        source = f08_train.load_public_train(version)
    elif f02:
        source = f02_train.load_public_train(version)
    else:
        source = physical_public_train.load_public_train(challenge_id)
    train_case_ids = tuple(source["case_ids"])
    if f02:
        # F02's provenance ids carry the stratum and decimals ("c30-i40-s0.5-...-v2s1"), which
        # the receiver's canonical identifier does not allow. The receiver names TRAIN rows by
        # position; the provenance ids stay bound in the kit through the limits document.
        train_case_ids = tuple(
            f"train-{index:04d}" for index in range(len(train_case_ids))
        )
    bank = physical_pack.development_bank(challenge_id, version)
    inputs, reference = bank["inputs"].copy(), bank["references"].copy()
    kit = public.construction_kit(challenge_id, version)
    interface = public.interface_document(challenge_id, version)
    limits = public.construction_limits_document(challenge_id, version)
    physics = physical_pack.physics_contract(challenge_id, version)
    allowed = material_allowlist_bytes(challenge_id, version)
    return {
        "challenge_key": ChallengeKey(challenge_id, version),
        "construction_kit": kit,
        "train": source["train"],
        "train_case_ids": train_case_ids,
        "example": inputs.copy(),
        "practice_inputs": inputs,
        "practice_case_ids": tuple(bank["case_ids"]),
        "practice_reference": reference,
        "expected_output_shape": reference.shape,
        "allowlist_bytes": allowed,
        "allowlist_digest": Allowlist(allowed).digest,
        "interface_document": interface,
        "construction_limits_document": limits,
        "physics_contract": physics,
        "physics_digest": digest(canonical(physics)),
        "resource_facts": {
            "train_archive_bytes": len(source["train"]),
            "train_tensor_bytes": int(
                source["inputs"].nbytes + source["targets"].nbytes
            ),
            "practice_input_bytes": int(inputs.nbytes),
            "practice_reference_bytes": int(reference.nbytes),
            "wall_time_seconds": None,
            "provider_spend_usd": None,
        },
        "disclosure": {
            "scope": public.SCOPE,
            "train_role": "PUBLIC_TRAIN",
            "practice_role": "EXPOSED_DEVELOPMENT_DECISION_BANK",
            "train_and_practice_labels_public": True,
            "hidden_evaluation": False,
            "official_reference": False,
            "scientifically_qualified": False,
            "live_eligible": False,
        },
    }
