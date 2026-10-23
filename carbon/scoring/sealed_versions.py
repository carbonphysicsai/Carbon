"""Each construction version's sealed evaluation version, in one table.

The sealed graders each register which Challenge versions grade the same
sealed batches (Validator, 2026-10-20: a version that changes construction
only is graded from its predecessor's sealed batches; 2026-10-23: graph route
v2 keeps its predecessor's evaluation version). Readers that must not reset
across a construction-only version bump - the Ladder - key on the evaluation
version this returns, never on the construction version (Validator,
no-limits binding, KOTH and Ladder continuity).

Read-only: the graders' own tables are the authority. It sits outside every
producer's `FILES`, so reading here moves no producer identity.
"""

from __future__ import annotations


def evaluation_version(challenge_id: str, version: str) -> str | None:
    """The sealed evaluation version that grades (challenge_id, version), or
    None where no sealed exam is registered for it."""
    if type(challenge_id) is not str or type(version) is not str:
        return None
    from carbon.scoring import (
        battery_sealed_dual_pack,
        f02_dual_pack,
        f08_dual_pack,
        motor_sealed_dual_pack,
    )

    if challenge_id == f08_dual_pack.CHALLENGE:
        return f08_dual_pack.SEALED_VERSIONS.get(version)
    if challenge_id == f02_dual_pack.CHALLENGE:
        return f02_dual_pack.SEALED_VERSIONS.get(version)
    for module in (motor_sealed_dual_pack, battery_sealed_dual_pack):
        if challenge_id == module.CHALLENGE:
            entry = module.VERSIONS.get(version)
            return None if entry is None else entry[0]
    from carbon.challenge_validator import cooling_hidden

    if (challenge_id, version) == (
        cooling_hidden.CHALLENGE_ID,
        cooling_hidden.CHALLENGE_VERSION,
    ):
        return cooling_hidden.EVALUATION_VERSION
    return None


def ladder_key(challenge_id: str, version: str) -> str:
    """The Ladder's evaluation key for a construction version: its sealed
    evaluation version, or - where none is registered - the construction
    version itself, marked so it can never equal an evaluation version."""
    sealed = evaluation_version(challenge_id, version)
    return sealed if sealed is not None else "construction:" + version
