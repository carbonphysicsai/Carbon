"""Battery's Level 3 attack adapter: polish numerics (`battery-l3-numerics-v1`).

The Test Lead's L3 attack design (2026-10-08), on the shared declarative
pattern (`adapters.battery_declarative`). Level 3 is a declarative menu held
as data (OWNER-GRAPHITE-DEV-LEVELS-01 F2): no participant code runs.

* **N1, unbounded work** (`l3_unbounded_work`): a dense quasi-Newton choice
  whose inverse Hessian exceeds the worker's memory bound is refused at
  compile (`development.inverse_hessian_too_large`), and polish beyond the
  contract's step bound is refused by the contract. Line-search work is
  capped per choice by Carbon's constants, which no recipe can name.
* **Off lane** (`l3_off_lane`): a numerics choice on PyTorch until backend
  parity, or with no polish stage to apply to, is refused.
* **N3, cross-level smuggling** (`l3_cross_level_fields`): a Level 1, 2 or
  4 field inside a Level 3 recipe, or a value off the menu, is refused.
* **Permission ablation** (`l3_slot_ablation`): every Level 3 field fails
  the miner-facing contract; only the variant admits it.
* **Determinism** (`l3_rebuild_determinism`): the same recipe and seed
  rebuild bit-identically twice on CPU.
* **Seams.** N2, instability, found no unstable recipe in the surface on
  CPU (below); the cost calculator's finding is shared with Level 2.
"""

from __future__ import annotations

import functools

from carbon.agent_campaign.attack.adapters import battery_declarative as d

LEVEL = 3
#: The smallest polishing recipe the Level 3 tests rebuild.
SMALL = {"width": 16, "depth": 1, "steps": 48, "polish_steps": 6}
#: Battery's largest MLP (the contract's width and depth maxima).
LARGEST = {"width": 512, "depth": 6}


def _strategy(**parameters):
    return d.strategy(SMALL, **parameters)


def _rebuild_label():
    from carbon.battery import level3_worker

    return level3_worker.REBUILD_LABEL


def _version():
    from carbon.battery import level3

    return level3.VERSION


def _other_level_fields():
    from carbon.agent_campaign.attack.adapters import battery_level1
    from carbon.battery import level1, level4

    expression = battery_level1.strategy(next(iter(battery_level1.VALID.values())))
    return (
        (
            "level1_loss_expressions",
            {level1.FIELD: expression["parameters"][level1.FIELD]},
        ),
        ("level2_muon_spectral", {"optimizer_family": "muon", "muon_spectral": True}),
        ("level4_graph_slot", {level4.FIELD: "sha256:" + "ab" * 32}),
    )


def _cross_level_attacks():
    out = [
        (name, _strategy(quasi_newton_family="bfgs", **fields))
        for name, fields in _other_level_fields()
    ]
    for field, value in (
        ("quasi_newton_family", "newton"),
        ("quasi_newton_family", "lbfgs_b"),
        ("quasi_newton_family", 3),
        ("line_search", "exact"),
        ("line_search", None),
    ):
        out.append((f"off_menu_{field}_{value}", _strategy(**{field: value})))
    return tuple(out)


def _off_lane_attacks():
    return (
        ("bfgs_on_pytorch", _strategy(quasi_newton_family="bfgs", backend="pytorch")),
        ("bfgs_without_polish", _strategy(quasi_newton_family="bfgs", polish_steps=0)),
        (
            "backtracking_without_polish",
            _strategy(line_search="backtracking", polish_steps=0),
        ),
    )


def _unbounded_attacks():
    out = [
        (
            f"dense_{family}_at_largest_mlp",
            _strategy(quasi_newton_family=family, **LARGEST),
        )
        for family in ("bfgs", "ssbfgs", "ssbroyden")
    ]
    out.append(
        (
            "polish_beyond_the_contract",
            _strategy(steps=2048, polish_steps=2001, line_search="strong_wolfe"),
        )
    )
    return tuple(out)


def _ablation_attacks():
    return (
        ("quasi_newton_at_level_0", _strategy(quasi_newton_family="bfgs")),
        ("line_search_at_level_0", _strategy(line_search="backtracking")),
    )


def _determinism_attacks():
    return (
        (
            "bfgs_backtracking",
            _strategy(quasi_newton_family="bfgs", line_search="backtracking"),
        ),
        (
            "ssbroyden_unit_step",
            _strategy(quasi_newton_family="ssbroyden", line_search="none"),
        ),
    )


@functools.lru_cache(maxsize=1)
def _families():
    gate = d.variant_gate(LEVEL)
    honest = _strategy(quasi_newton_family="bfgs")
    honest_largest = _strategy(quasi_newton_family="lbfgs", **LARGEST)
    return {
        "l3_unbounded_work": d.FamilyRow(
            check="resource_and_failure_accounting",
            words="dense inverse Hessians within the worker's memory bound; polish within the contract's step bound",
            attacks=_unbounded_attacks,
            boundary=gate,
            specimen=d.unchecked_gate,
            breached=d.accepted,
            control_ok=d.accepted,
            trained=honest,
            held_out=honest_largest,
        ),
        "l3_off_lane": d.FamilyRow(
            check="construction_evaluation_isolation",
            words="numerics choices only on JAX until backend parity, and only with a polish stage",
            attacks=_off_lane_attacks,
            boundary=gate,
            specimen=d.unchecked_gate,
            breached=d.accepted,
            control_ok=d.accepted,
            trained=honest,
            held_out=_strategy(line_search="backtracking"),
        ),
        "l3_cross_level_fields": d.FamilyRow(
            check="artifact_and_dependency_attacks",
            words="a Level 3 recipe carries only Level 0 fields and menu values; another level's field is refused",
            attacks=_cross_level_attacks,
            boundary=gate,
            specimen=d.unchecked_gate,
            breached=d.accepted,
            control_ok=d.accepted,
            trained=honest,
            held_out=_strategy(quasi_newton_family="ssbroyden", line_search="none"),
        ),
        "l3_slot_ablation": d.FamilyRow(
            check="baseline_and_permission_ablation",
            words="the miner-facing contract refuses the Level 3 fields; only the variant admits them",
            attacks=_ablation_attacks,
            boundary=d.miner_contract_gate,
            specimen=d.variant_gate(LEVEL),
            breached=d.accepted,
            control_ok=d.accepted,
            trained=_strategy(),
            held_out=_strategy(width=32, depth=2),
        ),
        "l3_rebuild_determinism": d.FamilyRow(
            check="reconstruction_and_recipient_rebuild",
            words="the same recipe and seed rebuild bit-identically twice on CPU",
            attacks=_determinism_attacks,
            boundary=d.rebuilds_identically(LEVEL),
            specimen=d.unpinned_seed(LEVEL),
            breached=d.different,
            control_ok=d.same,
            trained=_strategy(),
            held_out=_strategy(quasi_newton_family="lbfgs", width=32),
        ),
    }


SEAMS = (
    (
        "l3_instability",
        "score_exploitation_and_tail_failures",
        (
            "N2: no recipe in the surface went non-finite in CPU practice trials "
            "(ssbroyden, bfgs and lbfgs with unit steps, learning rate 0.05), so "
            "no specimen can fire; a non-finite polish is typed by the exam's "
            "finite-shape gate, the candidate's own (BATTERY-L3-NUMERICS-BUILD-01)"
        ),
    ),
    (
        "l3_no_state_path",
        "adaptive_feedback_and_state_attacks",
        (
            "Level 3 adds no feedback or state path: its menu is data and its "
            "polish runs inside Carbon's trainer; Level 0's "
            "practice_result_path_state seam covers the state path"
        ),
    ),
    d.compute_accounting_seam(LEVEL),
    d.fresh_cases_seam(LEVEL),
)

SPEC = d.LevelSpec(
    level=LEVEL,
    version=_version(),
    adapter_version="carbon.attack.adapter.battery-l3.v1",
    controls_version="carbon.attack.controls.battery-l3.v1",
    rebuild_label=_rebuild_label,
    families=_families,
    seams=SEAMS,
)
ADAPTER = d.BatteryDeclarativeAdapter(SPEC)
