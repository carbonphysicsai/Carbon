"""The practice grid: a Challenge's FULL exposed public bank, shaped as the exam's
sealed grid, with public-seeded probes (Validator, practice dual v2).

Practice feedback must match the exam (owner rule "practice must match"): the
practice dual runs the very same sealed v2 grader (`<challenge>_sealed_dual_pack`)
on this bank, so there is one scoring code path. The bank is the public
development bank: F08 and F02 as the 8 x 1 grid of their 8 exposed cells, Motor
and Cooling as the 8 x 6 grid of their exposed decision rows (the other exposed
rows are not part of the grid). Its probes are the exam's design drawn from a
PUBLIC seed (the public bank content under a ``<challenge>-practice`` label), so
every miner sees the same probe points; interleaved among the cells as in the exam.

It is labelled "practice (public bank)" (`LABEL`), reads no sealed or hidden
material, and is never comparable with a sealed grade. DEVELOPMENT only.
"""

from __future__ import annotations

import json

from carbon.scoring import physical_dual_pack as physical

LABEL = "practice (public bank)"
GRID_COHORT = "decision_sealed_grid"
POPULATION = "PRACTICE_PUBLIC_BANK"
KINDS = ("f08", "f02", "motor", "cooling")


class PracticeGridRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _modules(kind):
    # Static dispatch: the code-authority inventory forbids a computed import.
    if kind == "f08":
        from carbon.challenge_kit import f08_sealed_pack as kit
        from carbon.scoring import f08_dual_pack as dev
        from carbon.scoring import f08_sealed_dual_pack as sealed
    elif kind == "f02":
        from carbon.challenge_kit import f02_sealed_pack as kit
        from carbon.scoring import f02_dual_pack as dev
        from carbon.scoring import f02_sealed_dual_pack as sealed
    elif kind == "motor":
        from carbon.challenge_kit import motor_sealed_pack as kit
        from carbon.scoring import motor_dual_pack as dev
        from carbon.scoring import motor_sealed_dual_pack as sealed
    elif kind == "cooling":
        from carbon.challenge_kit import cooling_sealed_pack as kit
        from carbon.scoring import cooling_dual_pack as dev

        sealed = dev
    else:
        raise PracticeGridRefused("practice_kind_unregistered")
    return kit, dev, sealed


def adapter(kind, version):
    """The sealed v2 adapter that grades this Challenge version's practice grid
    (the exam's own), or None when the version has no sealed v2 grader."""
    _kit, _dev, sealed = _modules(kind)
    if kind == "cooling":
        chosen = sealed.sealed_adapter(version)
        if chosen is None:
            # Cooling 1.4 (graph route v2) is graded as 1.3 is: the encoded sealed adapter.
            from carbon.scoring import cooling_encoded_dual_pack

            chosen = cooling_encoded_dual_pack.sealed_adapter(version)
        return _native(chosen)
    return _native(sealed.adapter(version))


def _native(chosen):
    """A pool-graded version's practice grid has no pool: its native grader, same versions."""
    if not getattr(chosen, "POOL_GRADED", False):
        return chosen
    from carbon.scoring import physical_dual_pack as physical

    return physical.Variant(
        chosen._module, chosen.VERSION, chosen.EVALUATION_VERSION, chosen.CASE_ID
    )


def _canonical(value) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def practice_bank(kind, version):
    """The practice grid bank of a Challenge version: public cells in the grid
    cohort with design and condition ids, plus the public-seeded probes."""
    import numpy as np

    kit, dev, _sealed = _modules(kind)
    from carbon.challenge_kit import physical_pack

    source = physical_pack.legacy_development_bank(dev.CHALLENGE, version)
    if kind in ("f08", "f02"):
        keep = list(range(len(source["case_ids"])))
    else:
        keep = [i for i, c in enumerate(source["cohorts"]) if c.startswith("decision_")]
    if not keep:
        raise PracticeGridRefused("practice_bank_has_no_decision_rows")
    records = []
    for i in keep:
        record = dict(source["reference_records"][i])
        if kind in ("f08", "f02"):
            record["design_id"] = source["case_ids"][i]
            record["condition_id"] = "condition-0"
        if "design_id" not in record or "condition_id" not in record:
            raise PracticeGridRefused("practice_bank_cells_unnamed")
        records.append(record)
    inputs = np.asarray(source["inputs"])[keep]
    references = np.asarray(source["references"])[keep]
    bank = {
        "case_ids": tuple(source["case_ids"][i] for i in keep),
        "cohorts": (GRID_COHORT,) * len(keep),
        "inputs": inputs,
        "references": references,
        "reference_records": records,
        # The public bank's own digest stands in for a sealed batch's solver
        # evidence (the definition binds a receipt).
        "solver_evidence": _canonical(
            {"practice_public_bank": physical.bank_digest(source)}
        ),
        "decision_coverage": source.get("decision_coverage"),
        "population": (
            "SEALED_EXAM_BATCH_NEAR_LIMIT_S1" if kind == "f02" else POPULATION
        ),
    }
    names = input_names(kind, version)
    cases = {
        bank["case_ids"][i]: {n: float(v) for n, v in zip(names, row, strict=True)}
        for i, row in enumerate(bank["inputs"])
    }
    label = kind + "-practice"
    if kind == "f08" or kind == "f02":
        bank = kit._with_probes(bank, cases, names, inputs.dtype, challenge=label)
    elif kind == "motor":
        bank = kit._with_probes(bank, cases, inputs.dtype, challenge=label)
    else:
        bank = kit._with_probes(bank, cases, challenge=label)
    return bank


def input_names(kind, version):
    """The Challenge version's ordered input names."""
    _kit, dev, _sealed = _modules(kind)
    if kind == "f08":
        return dev.input_names(version)
    if kind == "f02":
        return dev.input_names()
    return physical.input_names(dev)
