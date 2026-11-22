"""Motor 1.9's development bank and adapter: the practice grid at 1.9's width (model-eval 22 Nov 01:59:08Z: 1.9 serves
a practice grid).

Motor 1.9's model row is 241 wide (`carbon.motor.row19`: 1.8's 240 columns, then ``magnet_min_b_t``). The graph route,
the served material and the public fixture all read the development bank's references, so the 1.9 bank is Motor 1.8's
development bank (`motor18_dev_grid.bank`: 1.6's dev bank widened to 240 with the pinned record-now linkages), with ONE
more column per reference row:

- columns 0..239 are 1.8's development references, unchanged (no rescore of any earlier version);
- column 240 is the public case's ``magnet_min_b_t`` (T), read from one pinned data file (`MAGNET_FILE`,
  `MAGNET_SHA256`), built from public solves of the SAME public cases (exam-motor names the source);
- a probe row (no reference) stays all-NaN, now 241 wide (the fixture drops it, as before).

Until the data file is pinned (`MAGNET_SHA256` None) the bank refuses (HUMAN_INPUT), never a 240-wide one. The
development adapter grades with Motor 1.9's own module (`motor19_dual_pack`: the torque slice to Motor's sealed grader),
selecting the PRACTICE rows out by cohort name exactly as `motor_dev_grid` does. Registered by the 1.9 dispatch
(`dev_grid.register`); no existing producer file moves.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CHALLENGE = "electric-motor-magnetics"
VERSION = "1.9"
SCHEMA = "carbon.motor.dev-bank-1p9-magnet.v1"
MAGNET_FILE = (
    Path(__file__).resolve().parents[1]
    / "challenge_kit"
    / "data"
    / "motor-dev-bank-1p9-magnet-v1.json"
)
#: The pinned sha256 of `MAGNET_FILE`: the public re-solves of the 78 reference cases at the TRAIN magnet knobs on the
#: digest-pinned image (model-eval V-B, 22 Nov 2026; custody-ops 08:39:18Z: 78 / 78 OK, determinism 0.0; built by
#: exam-motor's build_magnet_file.py f6d19f8c); None refuses.
MAGNET_SHA256 = "0260cdf87b52cf030f8c5e16518e73820632f797ccc9e3d8d3712331983710b4"


class DevBankUnavailable(ValueError):
    """The 1.9 development bank cannot be served (the Challenge's material, never a candidate's)."""


def canonical(document):
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )


def load_magnets(raw=None, *, pinned=None):
    """``{case_id: magnet_min_b_t}`` from the pinned data file (or ``raw`` bytes, for a builder's own check), refusing a
    missing pin, other bytes, or a malformed document (each value one finite number)."""
    pinned = MAGNET_SHA256 if pinned is None else pinned
    if pinned is None:
        raise DevBankUnavailable("motor19_dev_bank_magnet_not_pinned")
    if raw is None:
        try:
            raw = MAGNET_FILE.read_bytes()
        except OSError:
            raise DevBankUnavailable("motor19_dev_bank_magnet_missing") from None
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise DevBankUnavailable("motor19_dev_bank_magnet_differs")
    try:
        document = json.loads(raw)
    except ValueError:
        raise DevBankUnavailable("motor19_dev_bank_magnet_invalid") from None
    cases = document.get("cases") if type(document) is dict else None
    if (
        document.get("schema") != SCHEMA
        or type(cases) is not dict
        or not cases
        or not all(
            type(case_id) is str
            and case_id
            and type(value) in (int, float)
            and not isinstance(value, bool)
            and math.isfinite(value)
            for case_id, value in cases.items()
        )
    ):
        raise DevBankUnavailable("motor19_dev_bank_magnet_invalid")
    return {case_id: float(value) for case_id, value in cases.items()}


def widen(bank, magnets):
    """``bank`` (1.8's 240-wide development bank) with every reference widened to the 1.9 row: its own 240 columns, then
    its case's magnet value; a row with no reference stays all-NaN. Every reference row needs its case's magnet value
    (a missing one refuses)."""
    import numpy as np

    from carbon.motor import row18, row19

    references = np.asarray(bank["references"], dtype=float)
    present = tuple(bank.get("reference_present") or (True,) * len(bank["case_ids"]))
    if references.ndim != 2 or references.shape[1] != row18.WIDTH:
        raise DevBankUnavailable("motor19_dev_bank_base_not_1p8_wide")
    wide = np.full((len(references), row19.WIDTH), np.nan)
    for i, (case_id, has) in enumerate(zip(bank["case_ids"], present, strict=True)):
        if not has:
            continue
        if case_id not in magnets:
            raise DevBankUnavailable("motor19_dev_bank_case_without_magnet")
        wide[i, : row18.WIDTH] = references[i]
        wide[i, row18.WIDTH] = magnets[case_id]
        if not np.isfinite(wide[i]).all():
            raise DevBankUnavailable("motor19_dev_bank_reference_invalid")
    wide.setflags(write=False)
    evidence = bank.get("solver_evidence") or b""
    return {
        **bank,
        "references": wide,
        # the magnet file joins the bank's identity: the definition's receipt binds it
        "solver_evidence": evidence
        + b"|motor19-magnet:"
        + hashlib.sha256(canonical({"cases": magnets})).hexdigest().encode("ascii"),
    }


def bank(version=VERSION):
    """Motor 1.9's development bank (see the module docstring)."""
    from carbon.scoring import motor18_dev_grid

    if version != VERSION:
        raise DevBankUnavailable("motor19_dev_bank_is_for_1.9_only")
    magnets = load_magnets()
    return widen(motor18_dev_grid.bank("1.8"), magnets)


def adapter(version=VERSION):
    """Motor 1.9's development adapter: `motor19_dual_pack` (the torque slice to Motor's sealed grader) under the 1.9
    entry's development evaluation, the PRACTICE rows selected out by cohort name (`motor_dev_grid`'s rule).
    """
    from carbon.challenge_kit import version_registry
    from carbon.scoring import motor19_dual_pack as m19
    from carbon.scoring import motor_dev_grid
    from carbon.scoring import physical_dual_pack as physical

    if version != VERSION:
        raise DevBankUnavailable("motor19_dev_adapter_is_for_1.9_only")
    evaluation, case_id = version_registry.entry(
        CHALLENGE, version
    ).development_evaluation

    class _Adapter(physical.Variant):
        FILES = (
            *m19.FILES,
            "motor_dev_grid.py",
            "motor18_dev_grid.py",
            "motor19_dev_grid.py",
        )

        def definition(self, *, bank, train_raw):
            return m19.definition(
                bank=motor_dev_grid.grid_bank(bank), train_raw=train_raw
            )

        def measure(self, *, bank_rows, outputs, repeats, **rest):
            keep = [
                i
                for i, r in enumerate(bank_rows)
                if r["cohort"] != motor_dev_grid.PRACTICE
            ]
            if len(keep) == len(bank_rows) or len(outputs) != len(bank_rows):
                raise m19.Refused("motor_dev_grid_practice_rows")
            return m19.measure(
                bank_rows=[bank_rows[i] for i in keep],
                outputs=[outputs[i] for i in keep],
                repeats=[[row[i] for i in keep] for row in repeats],
                **rest,
            )

    return _Adapter(m19, version, evaluation, case_id)
