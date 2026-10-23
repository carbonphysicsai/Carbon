"""An F08 sealed exam batch as a private evaluation bank (OWNER-F02-F08-EXAM-DRAW-01).

As F02's (`f02_sealed_pack`; Validator, 2026-10-20): the sealed batch
document and its terminal records become a bank shaped exactly as
``physical_pack.development_bank`` returns F08's, and its private roles are
written as ``physical_pack._development_private_roles`` writes them. The
sealed evaluation version grades it (no response pairs; the interval
receipt is the batch's own solver evidence).

Whole batch or nothing: a case without an accepted reference refuses the
pack (the batch then fails QA and the backlog serves another version). The
checks are the development bank's own (asymptotic, every rung comparison
PASS, the reference rung's mode ladder PASS, the solver build pinned) plus:
the three rungs agree on the side of the 0.15 mm/N limit, no case is a
TRAIN geometry, and the references straddle the limit (the registered
decision coverage is ranking and feasibility straddle).

DEVELOPMENT only: it creates no qualification, weight, reward or LIVE
authority. The output is private; it is never written to a public surface.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

#: The one cohort a sealed grid's cells carry (C3); the development bank's `decision_near_limit` is not used.
COHORT = "decision_sealed_grid"
#: The pack rule's version, recorded in the pack summary and beside the pack
#: (Validator, VALIDATOR_F08_SEALED_STOP_20261022). v1 required all three rungs
#: to agree on the 0.15 mm/N side; h = 3 is biased about 1e-4 below the reference
#: rung, so a draw near the limit could be refused although U and the QA
#: spot-check, defined on h = 2.25 and h = 1.7, are met. v2 requires agreement of
#: those two only; h = 3 stays in the records as evidence. Packs made under v1
#: keep their meaning.
PACK_RULE_V1 = "f08-sealed-pack-rule-v1"
PACK_RULE_V2 = "f08-sealed-pack-rule-v2"
PACK_RULE = PACK_RULE_V2
AGREEING_RUNGS = {
    PACK_RULE_V1: ("h3", "h2.25", "h1.7"),
    PACK_RULE_V2: ("h2.25", "h1.7"),
}
POPULATION = "SEALED_EXAM_BATCH_NEAR_LIMIT_N1R"
DECISION_COVERAGE = "RANKING_AND_FEASIBILITY_STRADDLE"
EVIDENCE_SCHEMA = "carbon.f08.sealed-batch-evidence.v1"
TARGETS = (
    ("static_tip_mm_per_n", None, None),
    ("peak_tip_z005_mm_per_n", "zeta_0.005", "worst_mm_per_n"),
    ("peak_frequency_z005_hz", "zeta_0.005", "worst_hz"),
    ("peak_tip_z010_mm_per_n", "zeta_0.01", "worst_mm_per_n"),
    ("peak_frequency_z010_hz", "zeta_0.01", "worst_hz"),
    ("peak_tip_z020_mm_per_n", "zeta_0.02", "worst_mm_per_n"),
    ("peak_frequency_z020_hz", "zeta_0.02", "worst_hz"),
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


def _accepted(case_id, inputs, record, limit, rule=PACK_RULE):
    from carbon.challenge_validator import f08_hidden as hidden

    try:
        hidden.check_reference(record, inputs)
    except ValueError:
        raise SealedPackRefused("f08_sealed_record_malformed") from None
    if record["status"] != "OK" or record.get("case_id") != case_id:
        raise SealedPackRefused("f08_sealed_case_unresolved")
    rungs = record["rung_worst_dynamic_mm_per_n"]
    if len({rungs[name] <= limit for name in AGREEING_RUNGS[rule]}) != 1:
        raise SealedPackRefused("f08_sealed_rungs_disagree")
    wall_s = (record.get("rungs") or {}).get("h1.7", {}).get("wall_s")
    if type(wall_s) not in (int, float) or not wall_s > 0:
        raise SealedPackRefused("f08_sealed_no_measured_reference_rung")
    return float(wall_s)


#: Base points of the private response probes (physics half v1); each carries 13
#: rows (the base and two moves per input), so a batch adds 52 unreferenced rows.
PROBE_BASES = 4


def _valid_geometry(x) -> bool:
    """The packet shape rule (structures_readiness): the same buildable region the
    exam cases are drawn from."""
    length, width, _, _, rib, relief = x
    return width / 4 - rib / 2 > 10 and min((length - relief) / 2, width / 2 - 10) >= 6


def _with_probes(bank, cases, names, dtype):
    """``bank`` with the private response probes appended as unreferenced rows.
    The seed is the batch input content (never its ids or order), so every
    validator copy of one exam gets the same probes."""
    from carbon.challenge_pipeline import structures_readiness
    from carbon.scoring import probe_design

    if list(names) != list(structures_readiness.FIELDS):
        raise SealedPackRefused("f08_sealed_probe_interface")
    return probe_design.with_probes(
        bank,
        list(cases.values()),
        challenge="f08",
        bounds=[(float(lo), float(hi)) for lo, hi in structures_readiness.BOUNDS],
        valid=_valid_geometry,
        bases=PROBE_BASES,
        dtype=dtype,
    )


def sealed_bank(document, records, *, version="1.2", rule=PACK_RULE, probes=True) -> dict:
    """The sealed batch as a bank in ``physical_pack.development_bank``'s format,
    with (default) the private response probes of physics half v1 appended."""
    from carbon.challenge_kit import f08_public, physical_pack
    from carbon.challenge_validator import f08_hidden as hidden
    from carbon.f08.domain import LIMIT_MM_PER_N

    if version not in hidden.SERVED_VERSIONS:
        raise SealedPackRefused("f08_sealed_version")
    if rule not in AGREEING_RUNGS:
        raise SealedPackRefused("f08_sealed_pack_rule")
    try:
        cases = hidden.check_document(document)
    except ValueError:
        raise SealedPackRefused("f08_sealed_document_malformed") from None
    by_case = {}
    for record in records:
        case_id = record.get("case_id") if type(record) is dict else None
        if case_id not in cases or case_id in by_case:
            raise SealedPackRefused("f08_sealed_records_mismatch")
        by_case[case_id] = record
    if set(by_case) != set(cases):
        raise SealedPackRefused("f08_sealed_case_unresolved")
    interface = f08_public.interface_document(hidden.CHALLENGE_ID, version)
    names = interface["input"]["names"]
    slices = interface["output"]["named_slices"]
    if set(slices) != {name for name, _, _ in TARGETS}:
        raise SealedPackRefused("f08_sealed_interface_differs")
    width = max(end for _, end in slices.values())
    case_ids, rows, references, out_records, sides = [], [], [], [], set()
    for case_id in sorted(cases):
        inputs, record = cases[case_id], by_case[case_id]
        wall_s = _accepted(case_id, inputs, record, LIMIT_MM_PER_N, rule)
        outputs, damping = record["outputs"], record["damping"]
        sides.add(outputs["worst_dynamic_mm_per_n"] <= LIMIT_MM_PER_N)
        target = [0.0] * width
        for name, zeta, key in TARGETS:
            value = outputs[name] if zeta is None else damping[zeta][key]
            start, end = slices[name]
            target[start:end] = [float(value)]
        case_ids.append(case_id)
        rows.append([float(inputs[n]) for n in names])
        references.append(target)
        out_records.append(
            {
                "status": "OK",
                "case_id": case_id,
                "design_id": case_id,
                # a one-condition grid (C2/C3, VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022): the cases are the designs
                "condition_id": "condition-0",
                "reference_rung_h_mm": record["reference_rung_h_mm"],
                "wall_s": wall_s,
                "image": {
                    "kind": record["solvers"]["kind"],
                    "solvers": record["solvers"]["solvers"],
                },
                "cad_mass_kg": outputs["cad_mass_kg"],
                "observed": {
                    k: outputs[k]
                    for k in (
                        "static_tip_mm_per_n",
                        "worst_dynamic_mm_per_n",
                        "mass_kg",
                        "modes",
                        "mode_ladder",
                        "in_band_modes_hz",
                    )
                },
                "damping": {
                    zeta: {k: damping[zeta][k] for k in ("worst_mm_per_n", "worst_hz")}
                    for zeta in damping
                },
                "convergence": record["convergence"],
            }
        )
    if sides != {True, False}:
        raise SealedPackRefused("f08_sealed_no_straddle")
    dtype = interface["train_dtype"]
    inputs_array = np.asarray(rows, dtype=dtype)
    targets = np.asarray(references, dtype=dtype)
    if (
        inputs_array.shape != (hidden.BATCH_CASES, len(names))
        or targets.shape != (hidden.BATCH_CASES, width)
        or not np.isfinite(inputs_array).all()
        or not np.isfinite(targets).all()
    ):
        raise SealedPackRefused("f08_sealed_bank_shape")
    try:
        physical_pack._f08_refuse_train_overlap(inputs_array, version)
    except ValueError:
        raise SealedPackRefused("f08_sealed_train_geometry") from None
    inputs_array.setflags(write=False)
    targets.setflags(write=False)
    evidence = _canonical(
        {
            "schema": EVIDENCE_SCHEMA,
            "document": document,
            "records": [by_case[c] for c in case_ids],
        }
    )
    bank = {
        "case_ids": tuple(case_ids),
        "cohorts": (COHORT,) * len(case_ids),
        "inputs": inputs_array,
        "references": targets,
        "reference_records": out_records,
        "solver_evidence": evidence,
        "decision_coverage": DECISION_COVERAGE,
        "population": POPULATION,
    }
    return _with_probes(bank, cases, names, dtype) if probes else bank


def private_roles(bank) -> dict[str, bytes]:
    """The bank's private roles, byte for byte as the development pack's."""
    from carbon.challenge_kit.f02_sealed_pack import private_roles as roles

    return roles(bank)


def write_private_roles(root, bank) -> dict:
    """Write the private roles under a new, empty, owner-only ``root``."""
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SealedPackRefused("f08_sealed_pack_not_empty")
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
