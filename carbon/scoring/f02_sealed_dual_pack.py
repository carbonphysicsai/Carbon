"""F02 grades a sealed exam batch as one design x condition grid (Validator contract
VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022 sections 3 and 4; evaluation version
``f02-dual-sealed-grid-8x1-v1``; OWNER-F02-F08-EXAM-DRAW-01), and writes the batch's receiver pack.

A sealed F02 batch is 8 cells: 8 designs (the sealed actions) x 1 condition (``condition-0``; F02 has one
operating condition, so the cases are the designs), in one cohort (``decision_sealed_grid``) whose reference
records carry ``design_id`` and ``condition_id``. It is graded with F02's registered measurement for a sealed batch,
unchanged (`f02_dual_pack.measure`, bank kind ``sealed_batch``: no response pairs, the whole batch is the near
block, margin and decision only), and the total is 0.5 A + 0.5 D. The reference receipt is ``sha256(solver_evidence)``
of the batch's own family evidence.

What this module adds to the development grader is the sealed grid itself: the bank must be a complete grid of the
registered shape in the one cohort (refused otherwise), the definition registers the grid, and no leg minimum is
carried (a sealed pack's minimums come from the baseline's own run on the same batch,
`physical.baseline_minimums`). It is its own adapter so ``f02_dual_pack.py`` and every pack bound to its producer
digest are unchanged; this adapter's producer identity covers F02's file, the shared grid grouping and this one.
Dispatch is by the bank's declared population (`adapter_for_bank`): the previous flat sealed format keeps F02's own
sealed adapter.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import sys

from carbon.scoring import f02_dual_pack as _f02
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import sealed_grid_common as grid_common
from carbon.scoring import sealed_pack_writer

CHALLENGE = _f02.CHALLENGE
#: The first sealed Challenge version; 2.2 and 2.3 grade the same batches (they change only the construction source).
VERSION = "2.1"
EVALUATION_VERSION = "f02-dual-sealed-grid-8x1-v1"
CASE_ID = "f02-sealed-batch-8"
VERSIONS = {version: (EVALUATION_VERSION, CASE_ID) for version in ("2.1", "2.2", "2.3")}
OUTPUT = _f02.OUTPUT
FILES = (
    *_f02.FILES,
    "sealed_grid_common.py",
    "sealed_pack_writer.py",
    "f02_sealed_dual_pack.py",
)
MINIMUM_LEGS = _f02.MINIMUM_LEGS
MANIFEST_NAME = physical.MANIFEST_NAME
GATES = _f02.GATES
COHORT = grid_common.GRID_COHORT
CASES = 8
DESIGNS, CONDITIONS = 8, 1
METHOD = "f02-sealed-grid-dual-from-predictions.v1"
PACK_SUFFIX = "-sealed-batch-8"
Refused = _f02.F02MeasurementRefused
_ADAPTER = sys.modules[__name__]


def _require(ok, code):
    if not ok:
        raise Refused(code)


def input_names():
    return _f02.input_names()


def physics_contract():
    return _f02.physics_contract()


def baseline_outputs(cases):
    return _f02.baseline_outputs(cases)


def applied_pack(**kwargs):
    """F02's dual pack (0.5 A + 0.5 D and the four native gates); it carries no leg minimum."""
    return _f02.applied_pack(**kwargs)


def definition(*, bank, train_raw):
    """F02's registered accuracy definition for a sealed batch plus the sealed grid: the cohort count and the grid
    shape (the shared module adds the producer, TRAIN and bank pins)."""
    base = _f02.definition(bank=bank, train_raw=train_raw)
    _require(base["bank_kind"] == "sealed_batch", "f02_sealed_bank_kind")
    return {
        **base,
        "sealed_method": METHOD,
        "cohort_counts": {COHORT: CASES},
        "grid": {"designs": DESIGNS, "conditions": CONDITIONS},
    }


def validate_definition(definition):
    """The sealed grid definition, checked for every field used (F02's own checks, then the grid's)."""
    _f02.validate_definition(definition)
    _require(
        definition.get("bank_kind") == "sealed_batch"
        and definition.get("sealed_method") == METHOD
        and definition.get("cohort_counts") == {COHORT: CASES}
        and definition.get("grid") == {"designs": DESIGNS, "conditions": CONDITIONS},
        "f02_sealed_definition",
    )
    return definition


def _layout(bank_rows):
    return grid_common.grid_layout(
        bank_rows,
        design_of=lambda row: row["record"].get("design_id"),
        condition_of=lambda row: row["record"].get("condition_id"),
        shape=(DESIGNS, CONDITIONS),
        refuse=lambda code: _require(False, "f02_sealed_grid"),
    )


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """A, D, native gates and the decision outcome for one model on a sealed grid, by F02's registered measurement
    for a sealed batch (see the module docstring)."""
    validate_definition(definition)
    _require(
        len(bank_rows) == CASES
        and all(row.get("cohort") == COHORT for row in bank_rows),
        "f02_bank_cohort",
    )
    _layout(bank_rows)
    return _f02.measure(
        bank_rows=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=train_raw,
        names=names,
    )


def is_sealed_bank(bank) -> bool:
    """Whether a bank declares the sealed F02 grid: 8 cells, every cohort ``decision_sealed_grid``, each a distinct
    design x condition cell of the 8 x 1 grid."""
    if type(bank) is not dict:
        return False
    return grid_common.is_grid_bank(
        bank.get("cohorts"),
        bank.get("reference_records"),
        shape=(DESIGNS, CONDITIONS),
        design_of=lambda r: r.get("design_id"),
        condition_of=lambda r: r.get("condition_id"),
    )


def adapter(version):
    """The sealed adapter for exactly ``version``, or None."""
    return physical.versioned(_ADAPTER, version)


def adapter_for_bank(bank, version):
    """Dispatch by the bank's declared population: a sealed grid bank gets this adapter, the development bank
    F02's own, the previous flat sealed format F02's own sealed adapter, any other refuses.
    """
    if is_sealed_bank(bank):
        return adapter(version)
    cohorts = set(bank.get("cohorts", ())) if type(bank) is dict else set()
    if cohorts == {"decision_cold_eight"}:
        if _f02.BANK_KINDS.get(bank.get("population")) == "sealed_batch":
            return _f02.sealed_adapter(version)
        return physical.versioned(_f02, version)
    raise Refused("f02_bank_population")


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(**kwargs):
    return physical.pack_documents(_ADAPTER, **kwargs)


def produce(**kwargs):
    return physical.produce(_ADAPTER, **kwargs)


def write_sealed_pack(root, bank, *, version=VERSION, **platform):
    """Write a sealed batch's complete receiver pack (see `sealed_pack_writer.write`)."""
    from carbon.challenge_kit import f02_sealed_pack

    return sealed_pack_writer.write(
        adapter(version),
        f02_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=version,
        is_sealed_bank=is_sealed_bank,
        refusal=Refused("f02_bank_population"),
        pack_suffix=PACK_SUFFIX,
        **platform,
    )


__all__ = [
    "CASES",
    "COHORT",
    "EVALUATION_VERSION",
    "VERSIONS",
    "adapter",
    "adapter_for_bank",
    "definition",
    "is_sealed_bank",
    "measure",
    "producer_digest",
    "write_sealed_pack",
]
