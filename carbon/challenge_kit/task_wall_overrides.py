"""Per-version whole-task walls that differ from `version_registry.task_wall_seconds`. HOST-SIDE ONLY.

`version_registry.py` and `version_overlay.py` are worker-image inputs (`carbon/reconstruction/worker/build_inputs.txt`).
A wall that differs for ONE version therefore lives here, so no image identity moves. It is read by the two places
that state a version's `total_reconstruction_wall_seconds_max`:
- the published construction-limits document (`physical_public`);
- the served-policy check that matches it (`bundle_construction_worker.verify_direct_resource_policy`).

Every consumer of the wall (the rebuild task, the repeat pair, the menu re-check, the recovery deadline) reads it from
that document. Every version not named here keeps `task_wall_seconds` exactly, so its kit bytes do not move.
"""

from __future__ import annotations

import math

#: Motor 1.8 (owner, typed in mc-exam-C, Thu 12 Nov 2026 ~21:00 CST): "raise only the walls the quiet MGN measurement
#: fails (Test Lead-C, 12 Nov) to 1.5 x the measured quiet time, rounded up to the next 10 s; every other limit and the
#: 2564-row bank stay as they are". Test Lead-C's quiet MGN read (board 20:24, run line bcdbc0b2):
#: - the 648 s inference wall PASSES (quiet primary instance ~527.9 s, 81 %) and stays;
#: - the 947 s whole-task wall FAILS (quiet full repeat pair ~1,058 s, 112 %).
#: So only the total rises: ceil(1.5 x 1058 / 10) x 10 = 1590 s. Build and inference stay capped at 648 s each.
MOTOR_18_QUIET_FULL_PAIR_SECONDS = 1058
#: Motor 1.9 (owner line MOTOR19-BUILD-WALL, typed in model-eval 21 Nov 2026 23:52Z): "Motor 1.9 opens at build wall
#: 648 s / rebuild total 1,590 s on the RTX 6000 Ada class; raised to 880 s / 1,822 s with the D1 worker image rebuild or
#: sooner ...; never lowered". Its build and inference walls are the 648 s every graph route v2 version serves; the total
#: is 1.8's, so a full 1.9 repeat pair has the same room.
MOTOR_19_REBUILD_TOTAL_SECONDS = 1590
OVERRIDES = {
    ("electric-motor-magnetics", "1.8"): int(
        math.ceil(1.5 * MOTOR_18_QUIET_FULL_PAIR_SECONDS / 10) * 10
    ),
    ("electric-motor-magnetics", "1.9"): MOTOR_19_REBUILD_TOTAL_SECONDS,
}


def total_wall_seconds(challenge_id, version, rebuild_wall_seconds):
    """The version's whole-task wall: its own override, else its registry build row's (`exam_build`, raise-only), else
    `version_registry.task_wall_seconds`."""
    from carbon.challenge_registry import exam_build

    from .version_registry import task_wall_seconds

    own = OVERRIDES.get((challenge_id, version))
    if own is not None:
        return own
    registered = exam_build.total_wall_seconds(challenge_id, version)
    if registered is not None:
        return registered
    return task_wall_seconds(rebuild_wall_seconds)
