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
    version_registry,
)

SCOPE = physical_public.SCOPE
#: Registered public physical Challenges, by (id, version): every Motor,
#: Cooling, F08 and F02 version the version registry declares
#: (`version_registry`), each with its own explicit entry.
REGISTERED = tuple(
    sorted(
        key
        for key in version_registry.VERSIONS
        if key[0]
        in (
            motor.CHALLENGE.challenge_id,
            cooling.CHALLENGE.challenge_id,
            f08_train.CHALLENGE_ID,
            f02_train.CHALLENGE_ID,
        )
    )
)


def is_registered(challenge_id: str, version: str) -> bool:
    return (challenge_id, version) in REGISTERED


def _public(challenge_id: str):
    # F08 (v1: 255 rows, v2: 287) and F02 (40 rows) keep their own public module and float32
    # TRAIN; the rest shares one.
    if challenge_id == f08_train.CHALLENGE_ID:
        return f08_public
    if challenge_id == f02_train.CHALLENGE_ID:
        return f02_public
    return physical_public


def construction_kit(challenge_id: str, version: str) -> dict:
    """The registered five-field construction kit, from the same public module
    `bundle_material` reads it from, without building the practice bank."""
    if not is_registered(challenge_id, version):
        raise ValueError("unregistered public physical Challenge")
    return _public(challenge_id).construction_kit(challenge_id, version)


def bundle_material(
    challenge_id: str = motor.CHALLENGE.challenge_id,
    version: str = motor.CHALLENGE.version,
) -> dict:
    """Challenge-owned public bytes and arrays for the direct receiver."""
    from carbon.challenge_kit.served_versions import material_allowlist_bytes
    from carbon.level4.allowlist import Allowlist

    if not is_registered(challenge_id, version):
        raise ValueError("unregistered public physical Challenge")
    f08 = challenge_id == f08_train.CHALLENGE_ID
    f02 = challenge_id == f02_train.CHALLENGE_ID
    public = _public(challenge_id)
    if f08:
        source = f08_train.load_public_train(version)
    elif f02:
        source = f02_train.load_public_train(version)
    else:
        source = physical_public_train.load_public_train(challenge_id, version)
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
