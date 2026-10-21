"""An F02 sealed exam batch as a private evaluation bank (OWNER-F02-F08-EXAM-DRAW-01).

Validator, 2026-10-20: a sealed batch becomes a private evaluation pack in
the development pack's format (its case_bank and reference rows, sealed, in
owner custody), graded by the existing dual adapter with no second scoring
path. This module is the batch-to-bank step: the sealed batch document and
its terminal records become a bank shaped exactly as
``physical_pack.development_bank`` returns it, and its private roles are
written as ``physical_pack._development_private_roles`` writes them.

It refuses, rather than drops, any case without an accepted reference: an
exam is the whole batch or nothing (the batch then fails QA and the backlog
serves another version). Its checks are the development bank's own: every
rung solved, B1-B5 passing at both refinements, the rungs agreeing on the
limit side, the analytic energy equal to the schedule's, and no case a TRAIN
action. A batch whose references do not straddle the limit is refused (the
registered decision coverage is ranking and feasibility straddle).

DEVELOPMENT only: it creates no qualification, weight, reward or LIVE
authority. The output is private; it is never written to a public surface.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

COHORT = "decision_cold_eight"
POPULATION = "SEALED_EXAM_BATCH_NEAR_LIMIT_S1"
DECISION_COVERAGE = "RANKING_AND_FEASIBILITY_STRADDLE"
EVIDENCE_SCHEMA = "carbon.f02.sealed-batch-evidence.v1"
RUNGS = ("primary", "mesh2", "dt0.5")
OBSERVED = (
    "peak_top_c",
    "extra_energy_j",
    "first_95c_crossing_s",
    "peak_time_s",
    "recovery_s",
)


class SealedPackRefused(ValueError):
    """A typed refusal; the code names the check, never the hidden content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value) -> bytes:
    """The development pack's own canonical form (byte identity is tested)."""
    from carbon.challenge_kit.physical_pack import _canonical as canonical

    return canonical(value)


def _finite(value):
    return type(value) is float and np.isfinite(value)


def _accepted(case_id, inputs, record, limit_c):
    """The development bank's acceptance of one reference record."""
    from carbon.challenge_validator import f02_hidden as hidden

    try:
        hidden.check_reference(record, inputs)
    except ValueError:
        raise SealedPackRefused("f02_sealed_record_malformed") from None
    if record["status"] != "OK" or record.get("case_id") != case_id:
        raise SealedPackRefused("f02_sealed_case_unresolved")
    peaks = [record["rung_peaks_c"][r] for r in RUNGS]
    compared = record["rung_comparison"]
    if (
        not all(_finite(v) for v in peaks)
        or compared.get("primary_peak_c") != peaks[0]
        or len({v <= limit_c for v in peaks}) != 1
    ):
        raise SealedPackRefused("f02_sealed_rungs_disagree")
    energy = record["outputs"]["extra_energy_j"]
    # The observer sums the energy in floating point, as the development bank's.
    if not _finite(energy) or not np.isclose(
        energy,
        (inputs["peak_w"] - 20) * inputs["on_time_s"],
        rtol=1e-12,
        atol=0.0,
    ):
        raise SealedPackRefused("f02_sealed_energy_differs")
    primary = record.get("rungs", {}).get("primary", {})
    wall_s = primary.get("wall_s")
    if primary.get("outcome") != "EXITED" or primary.get("exit") != 0:
        raise SealedPackRefused("f02_sealed_case_unresolved")
    if type(wall_s) not in (int, float) or not wall_s > 0:
        raise SealedPackRefused("f02_sealed_no_measured_primary")
    return peaks, float(wall_s)


def sealed_bank(document, records, *, version="2.1") -> dict:
    """The sealed batch as a bank in ``physical_pack.development_bank``'s format.

    ``document`` is the sealed batch document; ``records`` its terminal
    reference records (one per case, from the sealed store).
    """
    from carbon.challenge_kit import f02_public, f02_train
    from carbon.challenge_validator import f02_hidden as hidden

    if version not in hidden.SERVED_VERSIONS:
        raise SealedPackRefused("f02_sealed_version")
    try:
        cases = hidden.check_document(document)
    except ValueError:
        raise SealedPackRefused("f02_sealed_document_malformed") from None
    by_case = {}
    for record in records:
        case_id = record.get("case_id") if type(record) is dict else None
        if case_id not in cases or case_id in by_case:
            raise SealedPackRefused("f02_sealed_records_mismatch")
        by_case[case_id] = record
    if set(by_case) != set(cases):
        raise SealedPackRefused("f02_sealed_case_unresolved")
    interface = f02_public.interface_document(hidden.CHALLENGE_ID, version)
    names = interface["input"]["names"]
    slices = interface["output"]["named_slices"]
    width = max(end for _, end in slices.values())
    limit_c = f02_train.LIMIT_C
    case_ids, rows, references, out_records, sides = [], [], [], [], set()
    for case_id in sorted(cases):
        inputs, record = cases[case_id], by_case[case_id]
        peaks, wall_s = _accepted(case_id, inputs, record, limit_c)
        sides.add(peaks[0] <= limit_c)
        target = [0.0] * width
        target[slice(*slices["peak_top_c"])] = [peaks[0]]
        case_ids.append(case_id)
        rows.append([float(inputs[n]) for n in names])
        references.append(target)
        out_records.append(
            {
                "status": "OK",
                "case_id": case_id,
                "design_id": case_id,
                "action": {
                    "peak_w": inputs["peak_w"],
                    "on_time_s": inputs["on_time_s"],
                },
                "context": dict(f02_train.CONTEXT),
                "image": record["image"],
                "wall_s": wall_s,
                "observed": {k: record["outputs"][k] for k in OBSERVED},
                "rung_peaks_c": dict(zip(RUNGS, peaks, strict=True)),
                "convergence": record["rung_comparison"],
            }
        )
    if sides != {True, False}:
        raise SealedPackRefused("f02_sealed_no_straddle")
    dtype = interface["train_dtype"]
    inputs_array = np.asarray(rows, dtype=dtype)
    targets = np.asarray(references, dtype=dtype)
    if inputs_array.shape != (hidden.BATCH_CASES, len(names)) or targets.shape != (
        hidden.BATCH_CASES,
        width,
    ):
        raise SealedPackRefused("f02_sealed_bank_shape")
    train = f02_train.load_public_train(version)["inputs"]
    seen = {tuple(row) for row in np.asarray(train, dtype=inputs_array.dtype).tolist()}
    if any(tuple(row) in seen for row in inputs_array.tolist()):
        raise SealedPackRefused("f02_sealed_train_action")
    inputs_array.setflags(write=False)
    targets.setflags(write=False)
    evidence = _canonical(
        {
            "schema": EVIDENCE_SCHEMA,
            "document": document,
            "records": [by_case[c] for c in case_ids],
        }
    )
    return {
        "case_ids": tuple(case_ids),
        "cohorts": (COHORT,) * len(case_ids),
        "inputs": inputs_array,
        "references": targets,
        "reference_records": out_records,
        "solver_evidence": evidence,
        "decision_coverage": DECISION_COVERAGE,
        "population": POPULATION,
    }


def private_roles(bank) -> dict[str, bytes]:
    """The bank's private roles, byte for byte as the development pack's."""
    from carbon.development_session.bundle_construction_worker import _tensors

    return {
        "case_bank": _tensors(inputs=np.array(bank["inputs"])),
        "reference_rows": _canonical(
            [
                {"row": i, "case_id": case_id, "cohort": cohort, "record": record}
                for i, (case_id, cohort, record) in enumerate(
                    zip(
                        bank["case_ids"],
                        bank["cohorts"],
                        bank["reference_records"],
                        strict=True,
                    )
                )
            ]
        ),
        "solver_evidence": bank["solver_evidence"],
    }


def write_private_roles(root, bank) -> dict:
    """Write the private roles under a new, empty, owner-only ``root``;
    returns the manifest's private entries ``{role: {"path"}}``."""
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SealedPackRefused("f02_sealed_pack_not_empty")
    (root / "private").mkdir(mode=0o700)
    entries = {}
    for role, body in private_roles(bank).items():
        name = f"private/{role}.{'npz' if role == 'case_bank' else 'json'}"
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
        entries[role] = {"path": name}
    return entries


__all__ = [
    "SealedPackRefused",
    "private_roles",
    "sealed_bank",
    "write_private_roles",
]
