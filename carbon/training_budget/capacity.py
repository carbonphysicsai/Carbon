"""R11, cadence capacity: the GPUs one validator needs (TRAINING-BUDGET-01 slice 3).

`DECISION_RULES_R9_R11.md` R11, as written:

    G = (N · (t_s + t_e) + k · (t_L + t_e)) / (τ · u)

- N is submissions per tempo, at the owner's worst case (every registered
  miner once per tempo) and at the sheet's expected participation;
- τ is the tempo and u the sheet's target utilization;
- t_s and t_L are the measured rebuild times at s and at L (Phase E, alone on
  one GPU), and t_e the measured grading time per submission;
- s and k come from R10. With no safe screen, t_s = 0 and k = N.

G assumes no duplicate recipes: identical recipe digests are rebuilt once,
which only lowers the real load. If G exceeds the sheet's GPU ceiling the
owner chooses (more GPUs, a lower submission rate or a higher fee); L and D are
never lowered to fit. Validator operations reuse `gpus` to size hosts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: The owner's worst case (OWNER-TRAINING-BUDGET-STUDY-02): every registered
#: miner submits once per tempo.
WORST_CASE_SUBMISSIONS = 256
#: The tempo, in seconds (72 minutes; R11).
TEMPO_SECONDS = 72 * 60
SCHEMA = "carbon.training-budget.capacity.v1"


class CapacityRefused(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


@dataclass(frozen=True)
class Times:
    """Phase E's measured seconds, alone on one GPU."""

    rebuild_at_screen: float | None
    rebuild_at_limit: float
    grading: float


def _seconds(value, name, *, zero=False):
    if not (type(value) in (int, float) and math.isfinite(value)) or (
        value < 0 or (value == 0 and not zero)
    ):
        raise CapacityRefused("capacity_time_malformed", name)
    return float(value)


def gpus(submissions, times, survivors, *, utilization, tempo_seconds=TEMPO_SECONDS):
    """R11's G for N submissions. `survivors` is R10's k, or None when no
    screen is safe (then t_s = 0 and k = N)."""
    if type(submissions) is not int or submissions < 0:
        raise CapacityRefused("capacity_submissions_malformed")
    if not (type(utilization) in (int, float) and 0 < utilization <= 1):
        raise CapacityRefused("capacity_utilization_malformed")
    t_l = _seconds(times.rebuild_at_limit, "rebuild_at_limit")
    t_e = _seconds(times.grading, "grading", zero=True)
    if survivors is None:
        t_s, k = 0.0, submissions
    else:
        if type(survivors) is not int or survivors < 0:
            raise CapacityRefused("capacity_survivors_malformed")
        t_s = _seconds(times.rebuild_at_screen, "rebuild_at_screen")
        k = min(survivors, submissions)
    return (submissions * (t_s + t_e) + k * (t_l + t_e)) / (tempo_seconds * utilization)


def report(sheet, times, survivors):
    """G at the worst case and at the sheet's expected participation, against
    the sheet's GPU ceiling. Refused while the sheet's R11 values are unset."""
    sheet.require("R11")
    utilization = sheet.get("target_utilization")
    ceiling = sheet.get("gpu_ceiling")
    cases = {
        "worst_case": WORST_CASE_SUBMISSIONS,
        "expected": sheet.get("expected_participation"),
    }
    rows = {}
    for name, submissions in cases.items():
        if type(submissions) is not int:
            submissions = math.ceil(submissions)
        g = gpus(submissions, times, survivors, utilization=utilization)
        rows[name] = {
            "submissions_per_tempo": submissions,
            "G": g,
            "gpus": math.ceil(g),
            "exceeds_gpu_ceiling": math.ceil(g) > ceiling,
        }
    return {
        "schema": SCHEMA,
        "rule": "R11",
        "challenge": sheet.challenge_id,
        "tempo_seconds": TEMPO_SECONDS,
        "target_utilization": utilization,
        "gpu_ceiling": ceiling,
        "screen": "none" if survivors is None else {"survivors": survivors},
        "assumes_no_duplicates": True,
        **rows,
        "owner_chooses": any(r["exceeds_gpu_ceiling"] for r in rows.values()),
    }
