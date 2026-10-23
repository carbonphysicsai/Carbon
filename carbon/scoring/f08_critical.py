"""F08's critical-prediction plugin for D = min(V, C) (``critical_fidelity``).

dev1 section 6 / section 7: the signed static margin, the three dynamic
margins and the three tip-resonance frequencies, on every geometry of the batch
including the unselected ones. Mass is analytic and earns no credit. The scales
are DEVELOPMENT normalisations (static margin 0.003 mm/N, each dynamic margin
0.015 mm/N, resonance 10 Hz), not physical thresholds; the value scale is the
registered ``D_scale_mm_per_n``.

Both sealed F08 graders (the flat near-limit batch and the 8 x 1 grid) use this
one module, so the rule is written once. DEVELOPMENT only.
"""

from __future__ import annotations

from carbon.scoring import critical_fidelity as critical

STATIC_MARGIN_SCALE = 0.003
DYNAMIC_MARGIN_SCALE = 0.015
RESONANCE_SCALE_HZ = 10.0


def block(base):
    """The definition's ``critical`` block, from F08's registered definition
    fields ``base`` (target names and the value scale)."""
    return critical.block(
        [
            ("static_margin", "margin", "static_margin", "mm/N", STATIC_MARGIN_SCALE),
            *(
                (
                    "dynamic_margin_" + name,
                    "margin",
                    "dynamic_margin_" + name,
                    "mm/N",
                    DYNAMIC_MARGIN_SCALE,
                )
                for name in base["tip_targets"]
            ),
            *(
                ("resonance_" + name, "resonance", name, "Hz", RESONANCE_SCALE_HZ)
                for name in base["frequency_targets"]
            ),
        ],
        ("mm/N", "MINIMIZE", base["D_scale_mm_per_n"]),
    )


def apply(measured, *, bank_rows, outputs, definition, constraints):
    """``measured`` (F08's native measurement) with D = min(V, C), when the
    definition registers the rule; unchanged otherwise (a v1 definition)."""
    if "critical" not in definition or not measured["D"]:
        return measured
    targets = definition["targets"]
    index = {name: j for j, name in enumerate(targets)}
    static, tips = definition["static_target"], list(definition["tip_targets"])
    frequencies = list(definition["frequency_targets"])

    def quantities(row):
        values = {
            "static_margin": constraints["static_tip_mm_per_n_max"] - row[index[static]]
        }
        for name in tips:
            values["dynamic_margin_" + name] = (
                constraints["dynamic_tip_mm_per_n_max"] - row[index[name]]
            )
        for name in frequencies:
            values[name] = row[index[name]]
        return values

    ids = [row["case_id"] for row in bank_rows]
    references = [[float(v) for v in row["reference"]] for row in bank_rows]
    predictions = [[float(v) for v in row] for row in outputs]
    reduction = critical.reduce(
        definition["critical"],
        case_ids=ids,
        action_ids=ids,
        reference={
            "cases": {
                cid: quantities(row) for cid, row in zip(ids, references, strict=True)
            },
            "actions": {
                cid: {
                    "feasible": row[index[static]]
                    <= constraints["static_tip_mm_per_n_max"]
                    and max(row[index[name]] for name in tips)
                    <= constraints["dynamic_tip_mm_per_n_max"]
                    and bank["record"]["cad_mass_kg"] <= constraints["mass_kg_max"],
                    "objective": max(row[index[name]] for name in tips),
                }
                for cid, row, bank in zip(ids, references, bank_rows, strict=True)
            },
        },
        prediction={
            "cases": {
                cid: quantities(row) for cid, row in zip(ids, predictions, strict=True)
            },
            "selected": measured["pick"],
        },
    )
    d, record = critical.design(measured["D"], reduction)
    return {**measured, "D": d, "design_fidelity": record}
