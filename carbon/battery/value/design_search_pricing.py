"""Battery's verification-budget and grid choices, priced for the owner.

Handoff §11: "PB-ADV's K beyond EV4, grid resolution and acceptance policies
stay owner-reserved: price concrete choices and present them." This module
prices battery's choices; it chooses nothing.
`docs/development/graphite/OPTIMIZER_CHOICES.md` presents `render()`. A second
Challenge prices its own choices on its own measured basis.

**Basis.** EV1 measured about 65 s per pinned-PyBaMM reference solve with 4
workers on the lead host's CPU (`DESIGN_OPTIMIZER_SCOPE.md` §2). Model
predictions take seconds and are counted, not timed. The reference solve
time on the approved reference hardware (`runpod-cpu5c-16vcpu`) has not been
benchmarked, so a time there is not claimed. Money is the owner's: a cost
appears only from an owner-supplied rate, and is HUMAN_INPUT otherwise.

**Development material.** A Mode X condition grid that overlaps EV4's
protected conditions cannot be a development grid: `search_commitment`
refuses every protected condition. The overlap is reported for each grid.
"""

from __future__ import annotations

from .ev4_protected_conditions import is_protected

HUMAN = "HUMAN_INPUT"
#: The measured basis (DESIGN_OPTIMIZER_SCOPE.md §2).
SECONDS_PER_SOLVE = 65
WORKERS = 4
#: EV4's panel of members (optimizer.MEMBER_ROLES), as the example panel size.
PANEL = 5


def _axis(start, step, count):
    return tuple(round(start + step * i, 6) for i in range(count))


#: Design grids over c1 in [0.5, 2.0] and c2 in [0.2, 1.0] (generator bounds).
DESIGN_GRIDS = {
    "coarse 16 x 17 (c1 step 0.1, c2 step 0.05)": (
        _axis(0.5, 0.1, 16),
        _axis(0.2, 0.05, 17),
    ),
    "EV3/EV4 31 x 33 (c1 step 0.05, c2 step 0.025)": (
        _axis(0.5, 0.05, 31),
        _axis(0.2, 0.025, 33),
    ),
    "fine 61 x 65 (c1 step 0.025, c2 step 0.0125)": (
        _axis(0.5, 0.025, 61),
        _axis(0.2, 0.0125, 65),
    ),
}
#: Mode X condition grids over the envelope t_amb 5-40 C, soc0 0.05-0.5.
CONDITION_GRIDS = {
    "EV4 model grid 8 x 4": (_axis(5.0, 5.0, 8), (0.05, 0.2, 0.35, 0.5)),
    "offset 7 x 3 (cell midpoints)": (_axis(7.5, 5.0, 7), (0.125, 0.275, 0.425)),
    "dense 15 x 10 (t step 2.5, soc0 step 0.05)": (
        _axis(5.0, 2.5, 15),
        _axis(0.05, 0.05, 10),
    ),
}
K_CHOICES = (50, 100, 200)


def _usd(cpu_hours, usd_per_cpu_hour):
    return HUMAN if usd_per_cpu_hour is None else round(cpu_hours * usd_per_cpu_hour, 2)


def k_choices(*, members=PANEL, usd_per_cpu_hour=None):
    """PB-ADV verification budget K: reference solves and time per panel."""
    rows = []
    for k in K_CHOICES:
        cpu_hours = k * members * SECONDS_PER_SOLVE / 3600
        rows.append(
            {
                "k": k,
                "note": "EV4's K" if k == 50 else "beyond EV4: owner-reserved",
                "solves_per_member": k,
                "solves_per_panel": k * members,
                "cpu_hours_per_panel": round(cpu_hours, 2),
                "wall_hours_per_panel": round(cpu_hours / WORKERS, 2),
                "usd_per_panel": _usd(cpu_hours, usd_per_cpu_hour),
            }
        )
    return rows


def grid_choices():
    """Design and Mode X condition grids: model queries per member, and the
    conditions EV4 protects."""
    rows = []
    for design_name, (c1, c2) in DESIGN_GRIDS.items():
        for condition_name, (t_amb, soc0) in CONDITION_GRIDS.items():
            conditions = [(t, s) for t in t_amb for s in soc0]
            protected = sum(is_protected(t, s) for t, s in conditions)
            rows.append(
                {
                    "design_grid": design_name,
                    "designs": len(c1) * len(c2),
                    "condition_grid": condition_name,
                    "conditions": len(conditions),
                    "model_queries_per_member": len(c1) * len(c2) * len(conditions),
                    "protected_conditions": protected,
                    "usable_for_development": protected == 0,
                }
            )
    return rows


def render(usd_per_cpu_hour=None):
    """The priced choices as Markdown tables."""
    lines = [
        (
            "| K | Note | Solves per member | Solves per panel of 5 | CPU hours | "
            "Wall hours on 4 workers | USD |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in k_choices(usd_per_cpu_hour=usd_per_cpu_hour):
        lines.append(
            f"| {r['k']} | {r['note']} | {r['solves_per_member']} | "
            f"{r['solves_per_panel']} | {r['cpu_hours_per_panel']} | "
            f"{r['wall_hours_per_panel']} | {r['usd_per_panel']} |"
        )
    lines += [
        "",
        (
            "| Design grid | Designs | Mode X condition grid | Conditions | "
            "Model queries per member | EV4-protected conditions | "
            "Usable for development |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in grid_choices():
        lines.append(
            f"| {r['design_grid']} | {r['designs']} | {r['condition_grid']} | "
            f"{r['conditions']} | {r['model_queries_per_member']} | "
            f"{r['protected_conditions']} | "
            f"{'yes' if r['usable_for_development'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"
