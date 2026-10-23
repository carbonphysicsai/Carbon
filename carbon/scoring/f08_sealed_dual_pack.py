"""F08 grades a sealed exam batch as one design x condition grid (Validator contract
VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022 sections 3 and 4; evaluation version
``f08-dual-sealed-grid-8x1-v1``; OWNER-F02-F08-EXAM-DRAW-01), and writes the batch's receiver pack.

A sealed F08 batch is 8 cells: 8 designs (the sealed geometries) x 1 condition (``condition-0``; F08 has one
operating condition, so the cases are the designs), in one cohort (``decision_sealed_grid``) whose reference
records carry ``design_id`` and ``condition_id``. It is graded with F08's registered dual measurement, unchanged
(`f08_dual_measurement.measure`), and the total is 0.5 A + 0.5 D:

- **A** is the minimum of the reciprocal benefits over the seven learned summary targets and the worst geometry.
- **D** is ``1/(1+regret/D_scale)`` for a predicted-feasible pick that the references verify feasible.
- Gates: the registered four, unchanged.
- The reference receipt is ``sha256(solver_evidence)`` of the batch's own family evidence.

What this module adds to the development grader is the sealed grid itself: the bank must be a complete grid of the
registered shape in the one cohort (refused otherwise), the definition registers the grid and the receipt, and no
leg minimum is carried (a sealed pack's minimums come from the baseline's own run on the same batch,
`physical.baseline_minimums`). It is its own adapter so ``f08_dual_pack.py`` and every pack bound to its producer
digest are unchanged; this adapter's producer identity covers F08's files, the shared grid grouping and this one.
Dispatch is by the bank's declared population (`adapter_for_bank`): the previous flat sealed format keeps F08's
own sealed adapter.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import hashlib
import sys

from carbon.scoring import critical_fidelity as critical
from carbon.scoring import f08_critical
from carbon.scoring import f08_dual_measurement as fdm
from carbon.scoring import f08_dual_pack as _f08
from carbon.scoring import f08_physics
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import sealed_grid_common as grid_common
from carbon.scoring import sealed_pack_writer

CHALLENGE = _f08.CHALLENGE
#: The first sealed Challenge version; 1.3 and 1.4 grade the same batches (they change only the construction source).
VERSION = "1.2"
#: v2: Design is D = min(V, C), the owner's rule (critical_fidelity); v1 graded V
#: alone and stays as history under its own evaluation version, never re-scored.
EVALUATION_VERSION = "f08-dual-sealed-grid-8x1-v2"
CASE_ID = "f08-sealed-batch-8"
VERSIONS = {version: (EVALUATION_VERSION, CASE_ID) for version in ("1.2", "1.3", "1.4")}
OUTPUT = _f08.OUTPUT
FILES = (
    *_f08.FILES,
    "sealed_grid_common.py",
    "sealed_pack_writer.py",
    "critical_fidelity.py",
    "design_fidelity.py",
    "f08_critical.py",
    "f08_physics.py",
    "physics_half.py",
    "f08_sealed_dual_pack.py",
)
MINIMUM_LEGS = _f08.MINIMUM_LEGS
MANIFEST_NAME = physical.MANIFEST_NAME
COHORT = grid_common.GRID_COHORT
CASES = 8
DESIGNS, CONDITIONS = 8, 1
METHOD = "f08-sealed-grid-dual-from-predictions.v1"
PACK_SUFFIX = "-sealed-batch-8"

Refused = fdm.F08MeasurementRefused
_ADAPTER = sys.modules[__name__]


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def input_names(version=VERSION):
    return _f08.input_names(version)


def physics_contract():
    return _f08.physics_contract()


def baseline_outputs(cases):
    """The baseline is graded as a submitted recipe on the judge image, not rebuilt here: refuse, never substitute."""
    raise Refused("f08_baseline_graded_not_rebuilt")


def definition(*, bank, train_raw):
    """F08's registered accuracy definition plus the sealed grid: the cohort count, the grid shape and the
    reference receipt (the shared module adds the producer, TRAIN and bank pins)."""
    evidence = bank.get("solver_evidence") if type(bank) is dict else None
    fdm._require(
        type(evidence) is bytes and evidence, "f08_sealed_evidence_unavailable"
    )
    base = _f08.definition(
        bank=bank, train_raw=train_raw, rule="baseline_legs", version=VERSION
    )
    return {
        **base,
        "method": fdm.METHOD,
        "sealed_method": METHOD,
        "cohort_counts": {COHORT: CASES},
        "grid": {"designs": DESIGNS, "conditions": CONDITIONS},
        "reference_receipt_sha256": _sha(evidence),
        "critical": f08_critical.block(base),
        "physics": f08_physics.block(),
    }


def validate_definition(definition):
    """The sealed grid definition, checked for every field used (F08's own checks, then the grid's)."""
    fdm.validate_definition(definition)
    fdm._require(
        definition.get("sealed_method") == METHOD
        and definition.get("geometry_count") == CASES
        and definition.get("cohort_counts") == {COHORT: CASES}
        and definition.get("grid") == {"designs": DESIGNS, "conditions": CONDITIONS}
        and type(definition.get("reference_receipt_sha256")) is str
        and definition["reference_receipt_sha256"].startswith("sha256:")
        and len(definition["reference_receipt_sha256"]) == 71,
        "f08_sealed_definition",
    )
    if "critical" in definition:
        try:
            critical.validate_block(definition["critical"])
        except critical.CriticalFidelityRefused as exc:
            raise Refused("f08_sealed_definition") from exc
    return definition


def applied_pack(**_):
    """F08's dual pack (0.5 A + 0.5 D and the four native gates) with no registered leg minimums: they are measured by
    the baseline's own run on the same batch (`physical.baseline_minimums`)."""
    from carbon.scoring import dual_score

    return {
        "schema": dual_score.PACK_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "challenge": CHALLENGE,
        "hard_gates": [*fdm.GATES, f08_physics.GATE],
        "legs": {
            leg: {
                "components": [
                    {
                        "metric": physical.METRICS[leg],
                        "unit": "1",
                        "transform": "unit_benefit",
                        "scale": None,
                        "weight": 1.0,
                    }
                ],
                "minimum": None,
            }
            for leg in ("A", "D")
        },
        "value_weight": 0.5,
        "combination": "weighted_arithmetic_mean",
        "decision_policy": {
            "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
            "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
            "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
        },
    }


def _layout(bank_rows):
    return grid_common.grid_layout(
        bank_rows,
        design_of=lambda row: row["record"].get("design_id"),
        condition_of=lambda row: row["record"].get("condition_id"),
        shape=(DESIGNS, CONDITIONS),
        refuse=lambda code: fdm._require(False, "f08_sealed_grid"),
    )


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """A, D, native gates and the decision outcome for one model on a sealed grid, by F08's registered dual
    measurement (see the module docstring)."""
    validate_definition(definition)
    fdm._require(
        len(bank_rows) == CASES
        and all(row.get("cohort") == COHORT for row in bank_rows),
        "f08_bank_cohort",
    )
    _layout(bank_rows)
    measured = _f08.measure(
        bank_rows=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=train_raw,
        names=names,
    )
    constraints = fdm._limits(limits)
    measured = f08_critical.apply(
        measured,
        bank_rows=bank_rows,
        outputs=outputs,
        definition=definition,
        constraints=constraints,
    )
    return f08_physics.apply(
        measured,
        bank_rows=bank_rows,
        outputs=outputs,
        definition=definition,
        train_rows=_f08._train_targets(train_raw),
        constraints=constraints,
    )


def is_sealed_bank(bank) -> bool:
    """Whether a bank declares the sealed F08 grid: 8 cells, every cohort ``decision_sealed_grid``, each a distinct
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
    """Dispatch by the bank's declared population: a sealed grid bank gets this adapter, a development bank F08's
    own, the previous flat sealed format F08's own sealed adapter, any other refuses."""
    if is_sealed_bank(bank):
        return adapter(version)
    cohorts = set(bank.get("cohorts", ())) if type(bank) is dict else set()
    if cohorts == {"decision_near_limit"}:
        if bank.get("population") == "SEALED_EXAM_BATCH_NEAR_LIMIT_N1R":
            return _f08.sealed_adapter(version)
        return _f08.adapter(version=version)
    raise Refused("f08_bank_population")


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(**kwargs):
    return physical.pack_documents(_ADAPTER, **kwargs)


def produce(**kwargs):
    return physical.produce(_ADAPTER, **kwargs)


def write_sealed_pack(root, bank, *, version=VERSION, **platform):
    """Write a sealed batch's complete receiver pack (see `sealed_pack_writer.write`)."""
    from carbon.challenge_kit import f08_sealed_pack

    return sealed_pack_writer.write(
        adapter(version),
        f08_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=version,
        is_sealed_bank=is_sealed_bank,
        refusal=Refused("f08_bank_population"),
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
