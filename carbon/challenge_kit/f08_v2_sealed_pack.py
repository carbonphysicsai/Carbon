"""A Ribbed Bracket 2.0 sealed batch as an ALL-POOL private evaluation bank (head B2; spec RB20_HEAD_B2_SPEC_20261122).

RB 2.0 is pool-only (model-eval 22 Nov 2026 04:23:00Z / 04:41:52Z). In the pool grade, the truths never sit in the
bank. The bank's rows are the pool material's design-search rows: inputs only, cohort `pool_exam.POOL_COHORT`, no
reference, in `pool_version.rows_from_material`'s canonical order. The truths ride inside the material's per-target
pool documents, carried as the batch document's ``"pool"`` (`sealed_batch_source._build`). So this module does three
things:

- `truths_from_record`: ONE mapping from a custody RESULTS record (one JSON line per job; exam-rb 04:22:13Z) to the 22
  graded outputs. The record keys are the source; bracket strings are never parsed:
  - ``outputs.<7 deck keys>``;
  - ``auxiliary.modes_hz[1..10]`` (0-based);
  - ``auxiliary.patch["2.0"].<3 names>``;
  - ``auxiliary.tip_static_displacement_mm_per_n[0, 1]``.

  The custody pool-source builder and this pack read the same mapping.
- `sealed_bank(document, records, version="2.0", pool=material)`: the all-pool bank. It CHECKS that every pool truth
  in the material equals its design's OK record, so the material cannot drift from the custody records. The records
  stay as the batch's solver evidence (the definition's reference receipt).
- `private_roles`: the private roles, written as every F08 pack writes them.

The batch document is the draw's designs with their ONE production job each, already resolved in custody by
rb20_records_query's REV 3 rule (the mesh-rule production job; not re-derived here):
``{"schema": DOCUMENT_SCHEMA, "designs": [{"design_id", "class", "job_id", "inputs": {12 interface inputs}}]}``.

Whole batch or nothing. A design whose job is missing, not OK, typed twice or not finite refuses the pack (a
reference failure is never a candidate failure; the batch then fails QA). So do a duplicate design or job, an
alloy_index outside 0 / 1 / 2, and a record mass off the closed form.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority. The output is private and never public.
"""

from __future__ import annotations

import math

DOCUMENT_SCHEMA = "carbon.f08.sealed-batch-2p0.v1"
EVIDENCE_SCHEMA = "carbon.f08.sealed-batch-evidence-2p0.v1"
POPULATION = "SEALED_EXAM_POOL_ONLY_2P0"
DECISION_COVERAGE = "POOL_EXAM_AND_MENUS"
VERSION = "2.0"
#: The relative agreement a record's ``cad_mass_kg`` must have with the closed form (the spec's golden bound, met at
#: 8.0e-16 on all 240 public TRAIN rows).
MASS_REL = 1e-12


class SealedPackRefused(ValueError):
    """A typed refusal; the code names the check, never the hidden content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise SealedPackRefused(code)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _train():
    from carbon.challenge_kit import f08_v2_train

    return f08_v2_train


def _record_value(record, source_key):
    """One graded value of a RESULTS record by its public source key (`f08_v2_train.SOURCE_KEYS`' values)."""
    outputs = record.get("outputs")
    auxiliary = record.get("auxiliary")
    if source_key.startswith("modes_hz["):
        index = int(source_key[len("modes_hz[") : -1])
        modes = auxiliary.get("modes_hz") if type(auxiliary) is dict else None
        return modes[index] if type(modes) is list and len(modes) > index else None
    if source_key.startswith("tip_static_displacement_mm_per_n["):
        index = int(source_key[len("tip_static_displacement_mm_per_n[") : -1])
        tip = (
            auxiliary.get("tip_static_displacement_mm_per_n")
            if type(auxiliary) is dict
            else None
        )
        return tip[index] if type(tip) is list and len(tip) > index else None
    if source_key.startswith("patch."):
        patch = auxiliary.get("patch") if type(auxiliary) is dict else None
        block = patch.get(VERSION) if type(patch) is dict else None
        return block.get(source_key[len("patch.") :]) if type(block) is dict else None
    return outputs.get(source_key) if type(outputs) is dict else None


def truths_from_record(record) -> dict:
    """The 22 graded truths of one OK RESULTS record, ``{interface name: value}`` in `GRADED_OUTPUTS` order. A record
    that is not OK, or misses a key, or holds a non-finite value refuses (the reference's fault, never a candidate's).
    """
    train = _train()
    _require(type(record) is dict, "f08_20_record_malformed")
    _require(record.get("status") == "OK", "f08_20_record_not_ok")
    truths = {}
    for name in train.GRADED_OUTPUTS:
        value = _record_value(record, train.SOURCE_KEYS[name])
        _require(_finite(value), "f08_20_record_value_missing")
        truths[name] = float(value)
    return truths


def _inputs(design):
    names = _train().INPUT_NAMES
    inputs = design.get("inputs") if type(design) is dict else None
    _require(
        type(inputs) is dict
        and set(inputs) == set(names)
        and all(_finite(inputs[n]) for n in names),
        "f08_20_design_inputs",
    )
    _require(float(inputs["alloy_index"]) in (0.0, 1.0, 2.0), "f08_20_alloy_index")
    return {n: float(inputs[n]) for n in names}


def _resolved(document, records):
    """``[(design_id, inputs, record)]`` of the batch: each design's ONE production job, OK and complete."""
    from carbon.scoring import f08_20_mass

    _require(
        type(document) is dict
        and document.get("schema") == DOCUMENT_SCHEMA
        and type(document.get("designs")) is list
        and document["designs"],
        "f08_20_document_malformed",
    )
    by_job = {}
    for record in records if type(records) in (list, tuple) else ():
        job = record.get("job_id") if type(record) is dict else None
        _require(type(job) is str and job, "f08_20_record_malformed")
        _require(job not in by_job, "f08_20_job_typed_twice")
        by_job[job] = record
    _require(by_job, "f08_20_records_missing")
    designs, seen_designs, seen_jobs = [], set(), set()
    for design in document["designs"]:
        _require(type(design) is dict, "f08_20_document_malformed")
        design_id, job = design.get("design_id"), design.get("job_id")
        _require(
            type(design_id) is str and design_id and type(job) is str and job,
            "f08_20_document_malformed",
        )
        _require(design_id not in seen_designs, "f08_20_duplicate_design")
        _require(job not in seen_jobs, "f08_20_duplicate_job")
        seen_designs.add(design_id)
        seen_jobs.add(job)
        _require(job in by_job, "f08_20_production_job_missing")
        record = by_job[job]
        inputs = _inputs(design)
        truths_from_record(record)  # every graded key present, finite, status OK
        mass = (record.get("outputs") or {}).get("cad_mass_kg")
        _require(_finite(mass), "f08_20_record_value_missing")
        closed = f08_20_mass.cad_mass_kg(inputs)
        _require(
            abs(mass - closed) <= MASS_REL * abs(closed), "f08_20_mass_not_closed_form"
        )
        designs.append((design_id, inputs, record))
    return designs


def _check_material_truths(material, designs, dtype):
    """Every pool truth in ``material`` equals its design's record at the record keys: the design is found by its model
    row, quantised to the bank's ``dtype`` exactly as the delivered query holds it. A pool design with no record, or a
    truth that differs, refuses."""
    import numpy as np

    from carbon.scoring import pool_grader

    kind = np.dtype(dtype)
    names = list(_train().INPUT_NAMES)
    _require(material.get("input_names") == names, "f08_20_material_interface")

    def key(row):
        return tuple(float(kind.type(row[n])) for n in names)

    by_row = {}
    for _design_id, inputs, record in designs:
        row = key(inputs)
        _require(row not in by_row, "f08_20_duplicate_design")
        by_row[row] = truths_from_record(record)
    graded = set(_train().GRADED_OUTPUTS)
    for group in material["sets"]:
        for document in group:
            spec = pool_grader.load_pool(document)
            fixed = spec.conditions["fixed"]
            for design, truth in zip(spec.designs, spec.truths, strict=True):
                row = {
                    **fixed,
                    **dict(zip(material["design_names"], design, strict=True)),
                }
                _require(set(row) == set(names), "f08_20_material_interface")
                record_truths = by_row.get(key(row))
                _require(record_truths is not None, "f08_20_pool_design_without_record")
                _require(type(truth) is dict, "f08_20_material_truth_malformed")
                for output, value in truth.items():
                    if output in graded:
                        _require(
                            value == record_truths[output],
                            "f08_20_material_truth_differs_from_record",
                        )


def sealed_bank(document, records, *, version=VERSION, pool=None) -> dict:
    """The 2.0 batch as an ALL-POOL bank (the development bank format, every row a pool row, inputs only), keeping the
    material as ``bank["pool"]`` and the records as the solver evidence."""
    import numpy as np

    from carbon.challenge_kit.physical_pack import _canonical
    from carbon.scoring import pool_exam, pool_version

    _require(version == VERSION, "f08_20_sealed_version")
    _require(pool is not None, "f08_20_pool_material_missing")
    try:
        pool_version.check_material(pool)
    except pool_exam.ExamRefused:
        raise SealedPackRefused("f08_20_pool_material_malformed") from None
    train = _train()
    dtype = pool["input_dtype"]
    designs = _resolved(document, records)
    _check_material_truths(pool, designs, dtype)
    rows = pool_version.rows_from_material(pool, dtype=dtype, challenge="f08")
    _require(rows, "f08_20_pool_rows_missing")
    width = len(train.INPUT_NAMES)
    inputs = np.asarray([x for _, _, x in rows], dtype=dtype).reshape(
        (len(rows), width)
    )
    references = np.full((len(rows), len(train.GRADED_OUTPUTS)), np.nan, dtype=dtype)
    inputs.setflags(write=False)
    references.setflags(write=False)
    evidence = _canonical(
        {
            "schema": EVIDENCE_SCHEMA,
            "document": document,
            "records": [record for _, _, record in designs],
        }
    )
    return {
        "case_ids": tuple(case_id for case_id, _, _ in rows),
        "cohorts": (pool_exam.POOL_COHORT,) * len(rows),
        "inputs": inputs,
        "references": references,
        "reference_records": [record for _, record, _ in rows],
        "reference_present": (False,) * len(rows),
        "solver_evidence": evidence,
        "decision_coverage": DECISION_COVERAGE,
        "population": POPULATION,
        "pool": pool,
    }


def private_roles(bank) -> dict[str, bytes]:
    """The bank's private roles, byte for byte as every F08 sealed pack's."""
    from carbon.challenge_kit.f08_sealed_pack import private_roles as roles

    return roles(bank)


__all__ = [
    "DOCUMENT_SCHEMA",
    "SealedPackRefused",
    "private_roles",
    "sealed_bank",
    "truths_from_record",
]
