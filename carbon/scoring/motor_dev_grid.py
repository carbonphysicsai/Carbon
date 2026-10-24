"""Motor 1.4's dev-pack v2 (Validator 2026-10-23, M2): the practice grid plus the PRACTICE cohort.

The development bank of a Motor dev-grid version is the 30 public PRACTICE cases (cohort
``practice``, unchanged: the miner's practice view of those 30 cases and its scorer read them) followed by
the practice grid (`practice_grid.practice_bank`: the 8 x 6 decision cells plus public-seeded
probes, interleaved). One inference query covers both. The sealed v2 grader sees exactly the
grid cells and probes: this adapter selects the PRACTICE rows out BY COHORT NAME, never by
position, before it measures, and builds the definition from the grid alone, so the rows that
reach the sealed measurement are the practice-grid bank byte for byte. The sealed population
refuses any PRACTICE row (the sealed grader's own checks); only this development bank has them.

New module: the sealed grader and every existing producer file are untouched. This file is in
its own producer identity (``FILES``).
"""

from __future__ import annotations

PRACTICE = "practice"
CHALLENGE = "electric-motor-magnetics"
_PER_ROW = (
    "case_ids",
    "cohorts",
    "inputs",
    "references",
    "reference_records",
    "reference_present",
)


def _take(bank, keep):
    """``bank`` restricted to the rows ``keep`` (indexes), every per-row field alike."""
    import numpy as np

    out = dict(bank)
    for key in _PER_ROW:
        if key not in bank:
            continue
        value = bank[key]
        if isinstance(value, np.ndarray):
            out[key] = value[keep]
            out[key].setflags(write=False)
        else:
            picked = [value[i] for i in keep]
            out[key] = tuple(picked) if isinstance(value, tuple) else picked
    return out


def grid_bank(bank):
    """The practice-grid part of a dev bank: every row that is not PRACTICE, in order."""
    return _take(bank, [i for i, c in enumerate(bank["cohorts"]) if c != PRACTICE])


def bank(version):
    """The dev bank: the PRACTICE cohort, then the practice grid with probes."""
    import numpy as np

    from carbon.challenge_kit import physical_pack
    from carbon.scoring import practice_grid

    legacy = physical_pack.legacy_development_bank(CHALLENGE, version)
    keep = [i for i, c in enumerate(legacy["cohorts"]) if c == PRACTICE]
    if not keep:
        raise ValueError("motor_dev_grid_practice_missing")
    practice = _take(legacy, keep)
    grid = practice_grid.practice_bank("motor", version)
    present = tuple(grid.get("reference_present") or (True,) * len(grid["case_ids"]))
    if set(practice["case_ids"]) & set(grid["case_ids"]):
        raise ValueError("motor_dev_grid_case_ids_overlap")
    merged = {
        **grid,
        "case_ids": tuple(practice["case_ids"]) + tuple(grid["case_ids"]),
        "cohorts": (PRACTICE,) * len(keep) + tuple(grid["cohorts"]),
        "inputs": np.concatenate([practice["inputs"], grid["inputs"]]),
        "references": np.concatenate([practice["references"], grid["references"]]),
        "reference_records": list(practice["reference_records"])
        + list(grid["reference_records"]),
        "reference_present": (True,) * len(keep) + present,
    }
    merged["inputs"].setflags(write=False)
    merged["references"].setflags(write=False)
    return merged


def adapter(version):
    """The sealed Motor v2 grader as a development adapter under the new development
    evaluation version, selecting the PRACTICE rows out by cohort name."""
    from carbon.challenge_kit import version_registry
    from carbon.scoring import motor_sealed_dual_pack as sealed
    from carbon.scoring import physical_dual_pack as physical

    evaluation, case_id = version_registry.entry(
        CHALLENGE, version
    ).development_evaluation

    class _Adapter(physical.Variant):
        FILES = (*sealed.FILES, "motor_dev_grid.py")

        def definition(self, *, bank, train_raw):
            return sealed.definition(bank=grid_bank(bank), train_raw=train_raw)

        def measure(self, *, bank_rows, outputs, repeats, **rest):
            keep = [i for i, r in enumerate(bank_rows) if r["cohort"] != PRACTICE]
            if len(keep) == len(bank_rows) or len(outputs) != len(bank_rows):
                raise sealed.Refused("motor_dev_grid_practice_rows")
            return sealed.measure(
                bank_rows=[bank_rows[i] for i in keep],
                outputs=[outputs[i] for i in keep],
                repeats=[[row[i] for i in keep] for row in repeats],
                **rest,
            )

    return _Adapter(sealed, version, evaluation, case_id)
