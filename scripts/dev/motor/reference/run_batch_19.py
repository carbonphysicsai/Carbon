"""Run Motor 1.9 reference cases: `run_batch.py` with the two magnet material inputs.

    python scripts/dev/motor/reference/run_batch_19.py PLAN.json --out DIR [run_batch.py flags]

A 1.9 case's `inputs` are the eight Challenge inputs (`carbon.motor.domain`) plus
both magnet material inputs `br_t` and `mur_m` (`MATERIAL_INPUTS`; exam-motor
8545 step 2, names 8872). The host writes them into the case's params.json and
machine.pro (`getdp.pro_text` reads ``br`` and ``mur_m``); the container, the
image and every other step are `run_batch.py`'s own. A case with neither solves
with `domain.FIXED`, as `run_batch.py` does. One of the two alone, or a value no
solve can take, is a case not written (FAILED_INFRA). The boxes are the exam's
own input check, not this runner's. Every record keeps all ten inputs.

`run_batch.py` stays byte-identical: its bytes are bound by the committed motor
decision-study freezes (`customer_decision.CODE_PATHS`, the counted evidence
under docs/development/evidence/motor-decision-counted-v2), so this runner
reuses it unchanged and only gives its case step the eight Challenge inputs and
the material values (release g10200).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.motor import domain
from scripts.dev.motor.reference import run_batch

#: Motor 1.9 magnet material inputs -> the solve parameter each sets.
MATERIAL_INPUTS = {"br_t": "br", "mur_m": "mur_m"}


def split_material(inputs):
    """(the eight Challenge inputs, the material parameters it sets or {})."""
    present = [name for name in MATERIAL_INPUTS if name in inputs]
    if not present:
        return inputs, {}
    if len(present) != len(MATERIAL_INPUTS):
        raise ValueError("a case sets both br_t and mur_m or neither")
    material = {}
    for name, param in MATERIAL_INPUTS.items():
        value = inputs[name]
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be a finite positive number")
        material[param] = float(value)
    return {k: v for k, v in inputs.items() if k not in MATERIAL_INPUTS}, material


class _Domain:
    """`carbon.motor.domain` as `run_batch.py`'s case step sees it: the checks that
    take a case read its eight Challenge inputs; everything else is domain's own."""

    def __getattr__(self, name):
        return getattr(domain, name)

    def validity(self, inputs):
        return domain.validity(split_material(inputs)[0])

    def coil_area_mm2(self, inputs):
        return domain.coil_area_mm2(split_material(inputs)[0])


_CASE_PARAMS = run_batch.case_params


def case_params(inputs, options):
    """`run_batch.case_params` on the eight Challenge inputs, with the case's
    material values in place of `domain.FIXED`'s (same keys, same order)."""
    eight, material = split_material(inputs)
    return {**_CASE_PARAMS(eight, options), **material}


def install():
    """Point `run_batch.py`'s case step at the 1.9 inputs (this process only)."""
    run_batch.case_params = case_params
    run_batch.domain = _Domain()


def main(argv=None):
    install()
    return run_batch.main(argv)


if __name__ == "__main__":
    sys.exit(main())
