"""Motor 1.8's development bank and development adapter (mc-exam-B's H-a, option (a), 7 Nov 21:30): one width, one meaning.

Motor 1.8's model row is 240 wide (`carbon.motor.row18`: torque, then the phase flux linkages A, B, C). The graph route,
the served material (`physical_material`: ``expected_output_shape`` = the bank's reference shape) and the public fixture
all read the development bank's references, so the 1.8 bank is 1.6's dev bank (the 1.8 entry's development evaluation,
`motor_dev_grid.bank`: 30 PRACTICE cases, then the 8 x 6 practice grid with public-seeded probes) with each reference
WIDENED to 240:

- the torque slice is the bank's own pinned torque reference, unchanged (no rescore of any earlier version);
- the three linkage slices come from the record-now re-solves of the SAME public cases (M2 shards s07 / s08), read from
  one pinned data file (`LINKAGE_FILE`, `LINKAGE_SHA256`), built by ``scripts/dev/motor/build_dev_bank_1p8.py``;
- a probe row (no reference) stays all-NaN, 240 wide (the fixture drops it, as before).

Until the data file is pinned (`LINKAGE_SHA256` None) the bank refuses (HUMAN_INPUT), never a 60-wide one. The
development adapter grades with Motor 1.8's own module (`motor18_dual_pack`: the torque slice to Motor's sealed grader),
selecting the PRACTICE rows out by cohort name exactly as `motor_dev_grid` does. Registered by the 1.8 dispatch
(`dev_grid.register`); no existing producer file moves.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CHALLENGE = "electric-motor-magnetics"
VERSION = "1.8"
#: The development evaluation the 1.8 entry reuses (its predecessor's bank and cases).
BASE_VERSION = "1.6"
SCHEMA = "carbon.motor.dev-bank-1p8-linkage.v1"
LINKAGE_FILE = (
    Path(__file__).resolve().parents[1]
    / "challenge_kit"
    / "data"
    / "motor-dev-bank-1p8-linkage-v1.json"
)
#: The pinned sha256 of `LINKAGE_FILE` (set when it is built from the M2 s07 / s08 records); None refuses.
LINKAGE_SHA256 = None
PHASES = ("A", "B", "C")


class DevBankUnavailable(ValueError):
    """The 1.8 development bank cannot be served (the Challenge's material, never a candidate's)."""


def _base_bank():
    from carbon.scoring import motor_dev_grid

    return motor_dev_grid.bank(BASE_VERSION)


def canonical(document):
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )


def load_linkages(raw=None, *, pinned=None):
    """``{case_id: {"A", "B", "C": [60 floats]}}`` from the pinned data file (or ``raw`` bytes, for the builder's own
    check), refusing a missing pin, other bytes, or a malformed document."""
    from carbon.motor.domain import ANGLE_STEPS

    pinned = LINKAGE_SHA256 if pinned is None else pinned
    if pinned is None:
        raise DevBankUnavailable("motor18_dev_bank_linkage_not_pinned")
    if raw is None:
        try:
            raw = LINKAGE_FILE.read_bytes()
        except OSError:
            raise DevBankUnavailable("motor18_dev_bank_linkage_missing") from None
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise DevBankUnavailable("motor18_dev_bank_linkage_differs")
    document = json.loads(raw)
    cases = document.get("cases") if type(document) is dict else None
    if document.get("schema") != SCHEMA or type(cases) is not dict:
        raise DevBankUnavailable("motor18_dev_bank_linkage_invalid")
    for phases in cases.values():
        if type(phases) is not dict or set(phases) != set(PHASES):
            raise DevBankUnavailable("motor18_dev_bank_linkage_invalid")
        for values in phases.values():
            if type(values) is not list or len(values) != ANGLE_STEPS:
                raise DevBankUnavailable("motor18_dev_bank_linkage_invalid")
    return cases


def widen(bank, cases):
    """``bank`` with every reference widened to the 1.8 row: its own torque, then the linkages of ``cases``; a row with
    no reference stays all-NaN. Every reference row needs its case's linkages (a missing one refuses)."""
    import numpy as np

    from carbon.motor import row18
    from carbon.motor.domain import ANGLE_STEPS

    references = np.asarray(bank["references"], dtype=float)
    present = tuple(bank.get("reference_present") or (True,) * len(bank["case_ids"]))
    if references.ndim != 2 or references.shape[1] != ANGLE_STEPS:
        raise DevBankUnavailable("motor18_dev_bank_base_not_torque_wide")
    wide = np.full((len(references), row18.WIDTH), np.nan)
    for i, (case_id, has) in enumerate(zip(bank["case_ids"], present, strict=True)):
        if not has:
            continue
        phases = cases.get(case_id)
        if phases is None:
            raise DevBankUnavailable("motor18_dev_bank_case_without_linkage")
        wide[i] = np.concatenate(
            [references[i], *(np.asarray(phases[p], dtype=float) for p in PHASES)]
        )
        if not np.isfinite(wide[i]).all():
            raise DevBankUnavailable("motor18_dev_bank_linkage_invalid")
    wide.setflags(write=False)
    evidence = bank.get("solver_evidence") or b""
    return {
        **bank,
        "references": wide,
        # the linkage file joins the bank's identity: the definition's receipt binds it
        "solver_evidence": evidence
        + b"|motor18-linkage:"
        + hashlib.sha256(canonical({"cases": cases})).hexdigest().encode("ascii"),
    }


def bank(version=VERSION):
    """Motor 1.8's development bank (see the module docstring)."""
    if version != VERSION:
        raise DevBankUnavailable("motor18_dev_bank_is_for_1.8_only")
    return widen(_base_bank(), load_linkages())


def adapter(version=VERSION):
    """Motor 1.8's development adapter: `motor18_dual_pack` (the torque slice to Motor's sealed grader) under the 1.8
    entry's development evaluation, the PRACTICE rows selected out by cohort name (`motor_dev_grid`'s rule)."""
    from carbon.challenge_kit import version_registry
    from carbon.scoring import motor18_dual_pack as m18
    from carbon.scoring import motor_dev_grid
    from carbon.scoring import physical_dual_pack as physical

    if version != VERSION:
        raise DevBankUnavailable("motor18_dev_adapter_is_for_1.8_only")
    evaluation, case_id = version_registry.entry(
        CHALLENGE, version
    ).development_evaluation

    class _Adapter(physical.Variant):
        FILES = (*m18.FILES, "motor_dev_grid.py", "motor18_dev_grid.py")

        def definition(self, *, bank, train_raw):
            return m18.definition(
                bank=motor_dev_grid.grid_bank(bank), train_raw=train_raw
            )

        def measure(self, *, bank_rows, outputs, repeats, **rest):
            keep = [
                i
                for i, r in enumerate(bank_rows)
                if r["cohort"] != motor_dev_grid.PRACTICE
            ]
            if len(keep) == len(bank_rows) or len(outputs) != len(bank_rows):
                raise m18.Refused("motor_dev_grid_practice_rows")
            return m18.measure(
                bank_rows=[bank_rows[i] for i in keep],
                outputs=[outputs[i] for i in keep],
                repeats=[[row[i] for i in keep] for row in repeats],
                **rest,
            )

    return _Adapter(m18, version, evaluation, case_id)
