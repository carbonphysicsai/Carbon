"""A Battery sealed exam batch as a private evaluation bank (VALIDATOR_BATTERY_SEALED_RULINGS_20261022).

As F02's and F08's (`f02_sealed_pack`, `f08_sealed_pack`): the sealed batch
document and its terminal records become a bank shaped as
``battery_pack._bank_v2`` returns the 2.0 bank's decision rows (inputs, the
247-wide flattened references, one `reference_records` entry per row), and its
private roles are written as the development pack's. The sealed evaluation
version `battery-dual-sealed-batch-8-v1` grades it (no response pairs).

Whole batch or nothing: a case without an OK reference refuses the pack
(`reference_present` is then False for it, and a batch with any such case is
not packed). The checks are the family's own (`check_reference`: the pinned
image and overlay, finite outputs, a mesh-160 margin, the v2 label recomputed)
plus: every case is a hull draw not repeating the published cases (the
producer's draw), and the references straddle the plating-onset label (at least
one FEASIBLE and one INFEASIBLE; the exam QA applies the one-third rule with U).

DEVELOPMENT only: it creates no qualification, weight, reward or LIVE
authority. The output is private; it is never written to a public surface.
"""

from __future__ import annotations

COHORT = "decision_sealed_grid"
POPULATION = "SEALED_EXAM_BATCH_BATTERY_GRID_HULL"
EVIDENCE_SCHEMA = "carbon.battery.sealed-batch-evidence.v1"


class SealedPackRefused(ValueError):
    """A typed refusal; the code names the check, never the hidden content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value) -> bytes:
    from carbon.challenge_kit.physical_pack import _canonical as canonical

    return canonical(value)


def sealed_bank(document, records) -> dict:
    """The sealed batch as a bank in the 2.0 bank's decision-row format."""
    import numpy as np

    from carbon.battery import domain
    from carbon.challenge_kit.battery_pack import _flat
    from carbon.battery_sealed.population import candidates, scenarios_of
    from carbon.challenge_validator import battery_sealed_hidden as hidden

    try:
        cases = hidden.check_document(document)
    except ValueError:
        raise SealedPackRefused("battery_sealed_document_malformed") from None
    by_case = {}
    for record in records:
        case_id = record.get("case_id") if type(record) is dict else None
        if case_id not in cases or case_id in by_case:
            raise SealedPackRefused("battery_sealed_records_mismatch")
        by_case[case_id] = record
    if set(by_case) != set(cases):
        raise SealedPackRefused("battery_sealed_case_unresolved")
    # Bank rows are the grid cells, scenario-major over EV4's candidate order (the
    # grading producer orders the batch's scenarios by first appearance).
    scenario_of = {
        s: f"scenario-{i}" for i, s in enumerate(scenarios_of(list(cases.values())))
    }
    candidate_of = {(c["c1"], c["c2"]): c["id"] for c in candidates()}
    candidate_order = {c["id"]: i for i, c in enumerate(candidates())}

    def cell_key(case_id):
        x = cases[case_id]
        return (
            scenario_of[(x["t_amb_c"], x["soc0"])],
            candidate_order[candidate_of[(x["c1"], x["c2"])]],
        )

    case_ids, rows, references, sides = [], [], [], set()
    for case_id in sorted(cases, key=cell_key):
        inputs, record = cases[case_id], by_case[case_id]
        try:
            hidden.check_reference(record, inputs)
        except ValueError:
            raise SealedPackRefused("battery_sealed_record_malformed") from None
        if record["status"] != "OK":
            raise SealedPackRefused("battery_sealed_case_unresolved")
        label = record["plating"]["label"]
        if label != "UNRESOLVED":
            sides.add(label)
        case_ids.append(case_id)
        rows.append([float(inputs[n]) for n in domain.INPUTS])
        references.append(_flat(record["outputs"]))
    if sides != {"FEASIBLE", "INFEASIBLE"}:
        raise SealedPackRefused("battery_sealed_no_straddle")
    # each record names its grid cell, which the dual adapter's D groups by
    for case_id in case_ids:
        x = cases[case_id]
        by_case[case_id] = {
            **by_case[case_id],
            "scenario_id": scenario_of[(x["t_amb_c"], x["soc0"])],
            "candidate_id": candidate_of[(x["c1"], x["c2"])],
            # the measured reference run: both solves (standard 30-cycle and mesh 160)
            "wall_s": float(
                by_case[case_id]["solves"]["standard"]["wall_s"]
                + by_case[case_id]["solves"]["m160"]["wall_s"]
            ),
        }
    x = np.asarray(rows, dtype=np.float64)
    y = np.asarray(references, dtype=np.float64)
    if (
        x.shape != (hidden.BATCH_CASES, len(domain.INPUTS))
        or y.shape[0] != hidden.BATCH_CASES
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
    ):
        raise SealedPackRefused("battery_sealed_bank_shape")
    x.setflags(write=False)
    y.setflags(write=False)
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
        "inputs": x,
        "references": y,
        "reference_present": (True,) * len(case_ids),
        "reference_records": [by_case[c] for c in case_ids],
        "solver_evidence": evidence,
        "population": POPULATION,
    }


def private_roles(bank) -> dict[str, bytes]:
    """The bank's private roles, byte for byte as the development pack's."""
    from carbon.challenge_kit.f02_sealed_pack import private_roles as roles

    return roles(bank)


def write_private_roles(root, bank) -> dict:
    """Write the private roles under a new, empty, owner-only ``root``."""
    from carbon.challenge_kit import f02_sealed_pack

    try:
        return f02_sealed_pack.write_private_roles(root, bank)
    except f02_sealed_pack.SealedPackRefused:
        raise SealedPackRefused("battery_sealed_pack_not_empty") from None


__all__ = ["SealedPackRefused", "private_roles", "sealed_bank", "write_private_roles"]
