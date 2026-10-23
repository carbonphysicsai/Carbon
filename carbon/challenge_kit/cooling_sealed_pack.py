"""A Cooling sealed exam batch (one 4 x 4 grid) as a private evaluation bank
(Validator, 2026-10-20; the F02/F08/Motor pattern).

The sealed batch document and its terminal records become a bank shaped
exactly as ``physical_pack.development_bank`` returns Cooling's: its six keys,
float64 inputs in the numeric interface's order, references laid out by the
interface's target slices, and the runner records carried as the development
bank carries them. Each record also names its grid cell, `design_id` (d1-d4)
and `condition_id` (c1-c4), in sorted input order, which the dual adapter's
decision rows read; the cohort is `decision_sealed_grid` (Validator's name),
graded by `cooling-dual-sealed-batch-16-v2`.

Whole batch or nothing: every one of the 16 cells must have exactly one `OK`
record accepted by `cooling_hidden.check_reference`; otherwise the pack is
refused. Limits, straddle, the within-U rule and spot-checks are the exam
QA's, not this module's.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority. The
output is private; it is never written to a public surface.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

COHORT = "decision_sealed_grid"
EVIDENCE_SCHEMA = "carbon.cold-plate.sealed-batch-evidence.v1"


class SealedPackRefused(ValueError):
    """A typed refusal; the code names the check, never the hidden content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value) -> bytes:
    from carbon.challenge_kit.physical_pack import _canonical as canonical

    return canonical(value)


#: Base points of the private probes (physics half v1); each carries the base,
#: two 1% moves per input (9 inputs) and the two law rows.
PROBE_BASES = 4


def _with_probes(bank, cases):
    """``bank`` with the private probes appended as unreferenced rows, seeded by
    the batch input content (never ids or order) inside the registered ranges."""
    from carbon.scoring import cooling_physics, probe_design

    return probe_design.with_probes(
        bank,
        list(cases.values()),
        challenge="cooling",
        bounds=list(cooling_physics.PROBE_BOUNDS),
        valid=lambda x: True,
        bases=PROBE_BASES,
        dtype="<f8",
        extra=cooling_physics.probe_extra(),
    )


def sealed_bank(document, records, *, version="1.1", probes=True) -> dict:
    """The sealed grid as a bank in Cooling's ``development_bank`` format."""
    from carbon.challenge_kit import physical_public_train
    from carbon.challenge_validator import cooling_hidden as hidden
    from carbon.cold_plate_exam.domain import CONDITION_INPUTS, DESIGN_INPUTS
    from carbon.cold_plate_exam.population import grid_of

    if version != hidden.CHALLENGE_VERSION:
        raise SealedPackRefused("cooling_sealed_version")
    try:
        cases = hidden.check_document(document)
    except ValueError:
        raise SealedPackRefused("cooling_sealed_document_malformed") from None
    by_case = {}
    for record in records:
        case_id = record.get("case_id") if type(record) is dict else None
        if case_id not in cases or case_id in by_case:
            raise SealedPackRefused("cooling_sealed_records_mismatch")
        by_case[case_id] = record
    if set(by_case) != set(cases):
        raise SealedPackRefused("cooling_sealed_case_unresolved")
    designs, conditions = grid_of(list(cases.values()))
    design_id = {d: f"d{i + 1}" for i, d in enumerate(designs)}
    condition_id = {c: f"c{i + 1}" for i, c in enumerate(conditions)}

    def cell(inputs):
        return (
            design_id[tuple(inputs[k] for k in DESIGN_INPUTS)],
            condition_id[tuple(inputs[k] for k in CONDITION_INPUTS)],
        )

    interface = physical_public_train.numeric_interface_document(hidden.CHALLENGE_ID)
    names, slices = interface["input_names"], interface["target_slices"]
    width = max(end for _, end in slices.values())
    case_ids, rows, references, out_records = [], [], [], []
    for case_id in sorted(cases, key=lambda c: cell(cases[c])):
        inputs, record = cases[case_id], by_case[case_id]
        try:
            hidden.check_reference(record, inputs)
        except ValueError:
            raise SealedPackRefused("cooling_sealed_record_malformed") from None
        if record["status"] != "OK":
            raise SealedPackRefused("cooling_sealed_case_unresolved")
        target = [0.0] * width
        for name, (start, end) in slices.items():
            value = record["outputs"][name]
            value = value if type(value) is list else [value]
            if len(value) != end - start:
                raise SealedPackRefused("cooling_sealed_bank_shape")
            target[start:end] = [float(v) for v in value]
        d, c = cell(inputs)
        case_ids.append(case_id)
        rows.append([float(inputs[n]) for n in names])
        references.append(target)
        out_records.append({**record, "design_id": d, "condition_id": c})
    inputs_array = np.asarray(rows, dtype="<f8")
    targets = np.asarray(references, dtype="<f8")
    if (
        inputs_array.shape != (hidden.BATCH_CASES, len(names))
        or targets.shape != (hidden.BATCH_CASES, width)
        or not np.isfinite(inputs_array).all()
        or not np.isfinite(targets).all()
    ):
        raise SealedPackRefused("cooling_sealed_bank_shape")
    inputs_array.setflags(write=False)
    targets.setflags(write=False)
    evidence = _canonical(
        {"schema": EVIDENCE_SCHEMA, "document": document, "records": out_records}
    )
    bank = {
        "case_ids": tuple(case_ids),
        "cohorts": (COHORT,) * len(case_ids),
        "inputs": inputs_array,
        "references": targets,
        "reference_records": out_records,
        "solver_evidence": evidence,
    }
    return _with_probes(bank, cases) if probes else bank


def private_roles(bank) -> dict[str, bytes]:
    """The bank's private roles, byte for byte as the development pack's."""
    from carbon.challenge_kit.f02_sealed_pack import private_roles as roles

    return roles(bank)


def write_private_roles(root, bank) -> dict:
    """Write the private roles under a new, empty, owner-only ``root``."""
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SealedPackRefused("cooling_sealed_pack_not_empty")
    (root / "private").mkdir(mode=0o700)
    entries = {}
    for role, body in private_roles(bank).items():
        name = f"private/{role}.{'npz' if role == 'case_bank' else 'json'}"
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
        entries[role] = {"path": name}
    return entries


__all__ = ["SealedPackRefused", "private_roles", "sealed_bank", "write_private_roles"]
