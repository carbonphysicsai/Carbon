"""A Motor 1.1 sealed exam batch as a private evaluation bank (Validator,
2026-10-20; the F02/F08 pattern).

The sealed batch document and its terminal records become a bank shaped
exactly as ``physical_pack.development_bank`` returns Motor's (its six keys,
float64 inputs in the interface's order, the 60-angle torque curve laid out by
the interface's slice, and the runner records carried verbatim as the
development bank carries them). Its private roles are written as the
development pack writes them.

Whole batch or nothing: every case must have exactly one `OK` record from the
pinned image with a finite curve of the exam's length; otherwise the pack is
refused (the batch fails QA and the backlog serves another version). The
cohort is `screening`, the family's own kind; how the sealed evaluation
version grades it is the scoring producer's (`motor-dual-sealed-batch-30-v2`).
Limits, straddle and spot-checks are the exam-batch QA's, not this module's.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority. The
output is private; it is never written to a public surface.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

COHORT = "screening"
EVIDENCE_SCHEMA = "carbon.motor.sealed-batch-evidence.v1"


class SealedPackRefused(ValueError):
    """A typed refusal; the code names the check, never the hidden content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value) -> bytes:
    from carbon.challenge_kit.physical_pack import _canonical as canonical

    return canonical(value)


def sealed_bank(document, records, *, version="1.1") -> dict:
    """The sealed batch as a bank in Motor's ``development_bank`` format."""
    from carbon.challenge_kit import physical_public_train
    from carbon.challenge_validator import motor_sealed as sealed

    if version not in sealed.SERVED_VERSIONS:
        raise SealedPackRefused("motor_sealed_version")
    try:
        cases = sealed.check_document(document)
    except ValueError:
        raise SealedPackRefused("motor_sealed_document_malformed") from None
    by_case = {}
    for record in records:
        case_id = record.get("case_id") if type(record) is dict else None
        if case_id not in cases or case_id in by_case:
            raise SealedPackRefused("motor_sealed_records_mismatch")
        by_case[case_id] = record
    if set(by_case) != set(cases):
        raise SealedPackRefused("motor_sealed_case_unresolved")
    interface = physical_public_train.numeric_interface_document(sealed.CHALLENGE_ID)
    names, slices = interface["input_names"], interface["target_slices"]
    width = max(end for _, end in slices.values())
    case_ids, rows, references, out_records = [], [], [], []
    for case_id in sorted(cases):
        inputs, record = cases[case_id], by_case[case_id]
        try:
            sealed.check_reference(record, inputs)
        except ValueError:
            raise SealedPackRefused("motor_sealed_record_malformed") from None
        if record["status"] != "OK":
            raise SealedPackRefused("motor_sealed_case_unresolved")
        target = [0.0] * width
        for name, (start, end) in slices.items():
            value = record["outputs"][name]
            value = value if type(value) is list else [value]
            if len(value) != end - start:
                raise SealedPackRefused("motor_sealed_bank_shape")
            target[start:end] = [float(v) for v in value]
        case_ids.append(case_id)
        rows.append([float(inputs[n]) for n in names])
        references.append(target)
        out_records.append(record)
    inputs_array = np.asarray(rows, dtype="<f8")
    targets = np.asarray(references, dtype="<f8")
    if (
        inputs_array.shape != (sealed.BATCH_CASES, len(names))
        or targets.shape != (sealed.BATCH_CASES, width)
        or not np.isfinite(inputs_array).all()
        or not np.isfinite(targets).all()
    ):
        raise SealedPackRefused("motor_sealed_bank_shape")
    inputs_array.setflags(write=False)
    targets.setflags(write=False)
    evidence = _canonical(
        {"schema": EVIDENCE_SCHEMA, "document": document, "records": out_records}
    )
    return {
        "case_ids": tuple(case_ids),
        "cohorts": (COHORT,) * len(case_ids),
        "inputs": inputs_array,
        "references": targets,
        "reference_records": out_records,
        "solver_evidence": evidence,
    }


GRID_COHORT = "decision_sealed_grid"
GRID_EVIDENCE_SCHEMA = "carbon.motor.sealed-grid-batch-evidence.v1"


def grid_bank(document, records, *, version="1.1") -> dict:
    """A sealed grid batch (OWNER-MOTOR-EXAM-GRID-01) as a bank: the placed
    bank's checks and shape, one cohort `decision_sealed_grid` for all 30 cells
    and each record naming its grid cell, `design_id` (`design-0..4`) and
    `condition_id` (`condition-0..5`), in sorted input order, as Cooling's sealed
    grid does (VALIDATOR_RULING_MOTOR_GRID_SPLIT_20261022). The dual adapter's D
    groups by `condition_id`."""
    from carbon.challenge_validator import motor_sealed_grid as grid
    from carbon.motor_grid_exam.domain import CONDITION_INPUTS, DESIGN_INPUTS
    from carbon.motor_grid_exam.population import grid_of

    try:
        cases = grid.check_document(document)
    except ValueError:
        raise SealedPackRefused("motor_sealed_document_malformed") from None
    bank = sealed_bank(
        dict(document, schema=grid.motor_sealed.DOCUMENT_SCHEMA),
        records,
        version=version,
    )
    designs, conditions = grid_of(list(cases.values()))
    design_id = {d: f"design-{i}" for i, d in enumerate(designs)}
    condition_id = {c: f"condition-{i}" for i, c in enumerate(conditions)}
    out_records = []
    for case_id, record in zip(
        bank["case_ids"], bank["reference_records"], strict=True
    ):
        inputs = cases[case_id]
        out_records.append(
            {
                **record,
                "design_id": design_id[tuple(inputs[k] for k in DESIGN_INPUTS)],
                "condition_id": condition_id[
                    tuple(inputs[k] for k in CONDITION_INPUTS)
                ],
            }
        )
    evidence = _canonical(
        {"schema": GRID_EVIDENCE_SCHEMA, "document": document, "records": out_records}
    )
    return {
        **bank,
        "cohorts": (GRID_COHORT,) * len(bank["case_ids"]),
        "reference_records": out_records,
        "solver_evidence": evidence,
    }


def private_roles(bank) -> dict[str, bytes]:
    """The bank's private roles, byte for byte as the development pack's."""
    from carbon.challenge_kit.f02_sealed_pack import private_roles as roles

    return roles(bank)


def write_private_roles(root, bank) -> dict:
    """Write the private roles under a new, empty, owner-only ``root``."""
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SealedPackRefused("motor_sealed_pack_not_empty")
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
