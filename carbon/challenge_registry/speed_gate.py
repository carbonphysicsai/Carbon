"""The speed gate's registered numbers, in one place.

A model must answer each exam design in at most 1/RATIO of the time the reference
solver needs for one design. The solver seconds per design are the recorded
values for each Challenge; the ceilings are derived here and nowhere else. The
published exam block, `carbon_challenges_v1__scoring_rules` and the grader's
speed gate all read this module, so the page, the tool and the gate cannot drift.
Data only (standard library); registered values are the owner's, from
codex-queue/reports/EXAM_ADDITIONS_20261025.md.
"""

from __future__ import annotations

RATIO = 500

#: Seconds the reference solver needs for one design at the registered level.
SOLVER_SECONDS_PER_DESIGN = {
    "f02": 190,
    "f08-ribbed-bracket": 1040,
    "chip-cold-plate": 1420,
    "electric-motor-magnetics": 1650,
}

SOURCE = "codex-queue/reports/EXAM_ADDITIONS_20261025.md"


def ceiling_seconds(challenge_id: str) -> float:
    """The most seconds per design the speed gate allows for ``challenge_id``."""
    return round(SOLVER_SECONDS_PER_DESIGN[challenge_id] / RATIO, 2)


def ceilings() -> dict[str, float]:
    return {
        challenge_id: ceiling_seconds(challenge_id)
        for challenge_id in SOLVER_SECONDS_PER_DESIGN
    }
