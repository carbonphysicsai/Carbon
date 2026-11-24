"""The speed gate's registered numbers, in one place.

A model must answer each exam design in at most 1/RATIO of the time the reference
solver needs for one design. The solver seconds per design are the recorded
values for each Challenge; a version with its own value carries it in its exam
registry row (`exam_registry`, ``solver_seconds_per_design``), which is read
first. The ceilings are derived here and nowhere else. The published exam block,
`carbon_challenges_v1__scoring_rules` and the grader's speed gate all read this
module, so the page, the tool and the gate cannot drift.
Standard library only; registered values are the owner's, from
codex-queue/reports/EXAM_ADDITIONS_20261025.md.
"""

from __future__ import annotations

from carbon.challenge_registry import exam_registry

RATIO = 500

#: Seconds the reference solver needs for one design at the registered level.
SOLVER_SECONDS_PER_DESIGN = {
    "f02": 190,
    "f08-ribbed-bracket": 1040,
    "chip-cold-plate": 1420,
    "electric-motor-magnetics": 1650,
}

SOURCE = "codex-queue/reports/EXAM_ADDITIONS_20261025.md"


class SpeedGateUnregistered(KeyError):
    """No solver seconds are registered for the Challenge version (Carbon's gap, never the candidate's failure)."""

    code = "speed_gate_unregistered"


class SpeedGateRefused(ValueError):
    """The version's registry row is malformed: no value is read for it, its Challenge's included (Carbon's failure)."""

    code = "speed_gate_row_refused"


def solver_seconds(challenge_id: str, version: str | None = None) -> float:
    """The reference solver's seconds per design: the version's own registered value, else its Challenge's value above,
    else `SpeedGateUnregistered`. A version whose registry row is malformed is `SpeedGateRefused`.
    """
    if version is not None:
        try:
            own = exam_registry.require(
                challenge_id, version, "solver_seconds_per_design"
            )
        except exam_registry.ExamRowRefused as refused:
            raise SpeedGateRefused(str(refused)) from None
        if own is not None:
            return own["value"]
    try:
        return SOLVER_SECONDS_PER_DESIGN[challenge_id]
    except KeyError:
        raise SpeedGateUnregistered(challenge_id) from None


def ceiling_seconds(challenge_id: str, version: str | None = None) -> float:
    """The most seconds per design the speed gate allows for ``challenge_id`` (at ``version``, when it has its own value)."""
    return round(solver_seconds(challenge_id, version) / RATIO, 2)


def ceilings() -> dict[str, float]:
    return {
        challenge_id: ceiling_seconds(challenge_id)
        for challenge_id in SOLVER_SECONDS_PER_DESIGN
    }
