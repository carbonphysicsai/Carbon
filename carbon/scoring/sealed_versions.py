"""Each construction version's sealed evaluation version, in one table.

The sealed graders each register which Challenge versions grade the same
sealed batches (Validator, 2026-10-20: a version that changes construction
only is graded from its predecessor's sealed batches; 2026-10-23: graph route
v2 keeps its predecessor's evaluation version). Readers that must not reset
across a construction-only version bump - the Ladder - key on the evaluation
version this returns, never on the construction version (Validator,
no-limits binding, KOTH and Ladder continuity).

Read-only, from the version registry (`challenge_kit.version_registry`); the
graders' own tables stay the authority inside their producers, and a test holds
the two equal. It sits outside every producer's `FILES`.
"""

from __future__ import annotations


def evaluation_version(challenge_id: str, version: str) -> str | None:
    """The sealed evaluation version that grades (challenge_id, version), or
    None where no sealed exam is registered for it: the version registry's
    declaration, which a test holds equal to the sealed graders' own tables.
    Read there, not from the graders, so a miner-reachable reader (the
    Ladder) imports no grader (Battery's reach its panel's attack harness)."""
    if type(challenge_id) is not str or type(version) is not str:
        return None
    from carbon.challenge_kit.version_registry import find

    declared = find(challenge_id, version)
    return None if declared is None else declared.sealed_evaluation


def ladder_key(challenge_id: str, version: str) -> str:
    """The Ladder's evaluation key for a construction version: its sealed
    evaluation version, or - where none is registered - the construction
    version itself, marked so it can never equal an evaluation version."""
    sealed = evaluation_version(challenge_id, version)
    return sealed if sealed is not None else "construction:" + version
