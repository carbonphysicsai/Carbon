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
OVERRIDES = {
    ("electric-motor-magnetics", "1.8"): int(
        math.ceil(1.5 * MOTOR_18_QUIET_FULL_PAIR_SECONDS / 10) * 10
    ),
}


def total_wall_seconds(challenge_id, version, rebuild_wall_seconds):
    """The version's whole-task wall: its own override, else `version_registry.task_wall_seconds`."""
    from .version_registry import task_wall_seconds

    own = OVERRIDES.get((challenge_id, version))
    return own if own is not None else task_wall_seconds(rebuild_wall_seconds)
