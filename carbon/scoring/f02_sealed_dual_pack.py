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

from carbon.scoring import critical_fidelity as critical
from carbon.scoring import f02_dual_pack as _f02
from carbon.scoring import f02_physics, probe_design
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import sealed_grid_common as grid_common
from carbon.scoring import sealed_pack_writer

CHALLENGE = _f02.CHALLENGE
#: The first sealed Challenge version; 2.2 and 2.3 grade the same batches (they change only the construction source).
VERSION = "2.1"
#: v2: Design V is the mean of pair-ordering, accept/reject and nearby-variant
#: measures (D = min(V, C) as before) and A is the physics half
#: (physics_half); v1 stays as history under its own evaluation version.
EVALUATION_VERSION = "f02-dual-sealed-grid-8x1-v2"
CASE_ID = "f02-sealed-batch-8"
VERSIONS = {
    version: (EVALUATION_VERSION, CASE_ID) for version in ("2.1", "2.2", "2.3", "2.4")
}
OUTPUT = _f02.OUTPUT
FILES = (
    *_f02.FILES,
    "sealed_grid_common.py",
    "sealed_pack_writer.py",
    "critical_fidelity.py",
    "design_fidelity.py",
    "physics_half.py",
    "probe_design.py",
    "f02_physics.py",
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


#: dev1 section 5 / section 7: the thermal margin is 1 C; the value scale is the
#: registered 100 J. The main limit shifted in the nearby-variant questions is the
#: 95 C ceiling.
MARGIN_SCALE_C = _f02.MARGIN_SCALE_C
ENERGY_SCALE_J = _f02.S_VALUE_J


def applied_pack(**kwargs):
    """F02 dual pack (0.5 A + 0.5 D, the native gates plus the physics-law gate); it carries no leg
    minimum."""
    pack = _f02.applied_pack(**kwargs)
    return {**pack, "hard_gates": [*pack["hard_gates"], f02_physics.GATE]}


def definition(*, bank, train_raw):
    """F02's registered accuracy definition for a sealed batch plus the sealed grid: the cohort count and the grid
    shape (the shared module adds the producer, TRAIN and bank pins)."""
    base = _f02.definition(
        bank=probe_design.cells_only(bank, by_case_id=True), train_raw=train_raw
    )
    _require(base["bank_kind"] == "sealed_batch", "f02_sealed_bank_kind")
    probes = sum(1 for c in bank["cohorts"] if c == probe_design.PROBE_COHORT)
    return {
        **base,
        "sealed_method": METHOD,
        "cohort_counts": {COHORT: CASES},
        "grid": {"designs": DESIGNS, "conditions": CONDITIONS},
        "probes": {"cohort": probe_design.PROBE_COHORT, "rows": probes},
        "critical": critical.block(
            [("thermal_margin", "margin", "thermal_margin_c", "C", MARGIN_SCALE_C)],
            ("J", "MAXIMIZE", ENERGY_SCALE_J),
            [("thermal_margin", 1)],
        ),
        **(
            {
                "physics": f02_physics.block(
                    __import__(
                        "carbon.challenge_kit.f02_train", fromlist=["x"]
                    ).load_public_train(_f02.VERSION)
                )
            }
            if probes
            else {}
        ),
    }


def validate_definition(definition):
    """The sealed grid definition, checked for every field used (F02's own checks, then the grid's)."""
    _f02.validate_definition(definition)
    _require(
        definition.get("bank_kind") == "sealed_batch"
        and definition.get("sealed_method") == METHOD
        and definition.get("cohort_counts") == {COHORT: CASES}
        and type(definition.get("probes")) is dict
        and definition["probes"].get("cohort") == probe_design.PROBE_COHORT
        and type(definition["probes"].get("rows")) is int
        and definition["probes"]["rows"] >= 0
        and definition.get("grid") == {"designs": DESIGNS, "conditions": CONDITIONS},
        "f02_sealed_definition",
    )
    if "critical" in definition:
        try:
            critical.validate_block(definition["critical"])
        except critical.CriticalFidelityRefused as exc:
            raise Refused("f02_sealed_definition") from exc
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
    cells = [i for i, row in enumerate(bank_rows) if row.get("cohort") == COHORT]
    probes = [
        i
        for i, row in enumerate(bank_rows)
        if row.get("cohort") == probe_design.PROBE_COHORT
    ]
    _require(
        len(cells) == CASES
        and len(cells) + len(probes) == len(bank_rows)
        and len(probes) == definition["probes"]["rows"]
        and len(outputs) == len(bank_rows)
        and all(len(r) == len(bank_rows) for r in repeats),
        "f02_bank_cohort",
    )
    # The delivered query interleaves probes among the cells; F02 measure reads its
    # eight actions in id order.
    cells = sorted(cells, key=lambda i: bank_rows[i]["case_id"])
    cell_rows = [bank_rows[i] for i in cells]
    probe_rows = [bank_rows[i] for i in probes]
    _layout(cell_rows)
    cell_outputs = [outputs[i] for i in cells]
    measured = _f02.measure(
        bank_rows=cell_rows,
        outputs=cell_outputs,
        repeats=[[r[i] for i in cells] for r in repeats],
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=train_raw,
        names=names,
    )
    measured = _mean_value(measured, cell_rows, cell_outputs, definition)
    return f02_physics.apply(
        measured,
        bank_rows=cell_rows,
        outputs=cell_outputs,
        definition=definition,
        train_std=definition["train_peak_std_c"],
        constraints={"maximum_c": definition["maximum_c"]},
        probe_rows=probe_rows,
        probe_outputs=[outputs[i] for i in probes],
    )


def _mean_value(measured, bank_rows, outputs, definition):
    """D = min(V, C) with V the mean of the pair-ordering, accept/reject and
    nearby-variant measures; C is the native reduction (unchanged)."""
    reduction = measured.get("reduction")
    if "critical" not in definition or reduction is None:
        return measured
    limit = definition["maximum_c"]
    ids = [row["case_id"] for row in bank_rows]
    peaks = [float(row[0]) for row in outputs]
    truth = [float(row["reference"][0]) for row in bank_rows]
    energy = {
        row["case_id"]: (
            (row["record"]["action"]["peak_w"] - 20)
            * row["record"]["action"]["on_time_s"]
        )
        for row in bank_rows
    }
    v, record = critical.value(
        definition["critical"],
        cells_of={cid: [cid] for cid in ids},
        reference={
            "cases": {
                cid: {"thermal_margin_c": limit - peak}
                for cid, peak in zip(ids, truth, strict=True)
            },
            "actions": {
                cid: {"feasible": peak <= limit, "objective": energy[cid]}
                for cid, peak in zip(ids, truth, strict=True)
            },
        },
        prediction={
            "cases": {
                cid: {"thermal_margin_c": limit - peak}
                for cid, peak in zip(ids, peaks, strict=True)
            },
            "selected": measured["selected_action"],
            "objective": dict(energy),
        },
        base_v=(reduction["V"] or {}).get("V"),
        limits={"thermal_margin": limit},
    )
    c = reduction["C"]
    d = None if v is None or c is None else min(v, c)
    return {**measured, "D": d, "design_fidelity": {**record, "C": c}}


def is_sealed_bank(bank) -> bool:
    """Whether a bank declares the sealed F02 grid: 8 cells, every cohort ``decision_sealed_grid``, each a distinct
    design x condition cell of the 8 x 1 grid."""
    if type(bank) is not dict:
        return False
    cohorts, records = bank.get("cohorts"), bank.get("reference_records")
    if (
        type(cohorts) not in (tuple, list)
        or type(records) not in (tuple, list)
        or len(cohorts) != len(records)
    ):
        return False
    keep = [i for i, c in enumerate(cohorts) if c != probe_design.PROBE_COHORT]
    return grid_common.is_grid_bank(
        [cohorts[i] for i in keep],
        [records[i] for i in keep],
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
