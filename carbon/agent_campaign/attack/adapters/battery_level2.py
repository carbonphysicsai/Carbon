"""Battery's Level 2 attack adapter: SpecMuon and pool selection (`battery-l2-v2`).

The Test Lead's L2 attack design (2026-10-08), on the shared declarative
pattern (`adapters.battery_declarative`): one family per row that Carbon can
refuse at its real boundary, each with an unchecked specimen that must fire;
the rest are seams, NOT_RUN, each saying why.

* **M3, off-family** (`l2_off_family`): `muon_spectral` on a non-Muon
  optimizer, with the plateau curve, or on PyTorch until backend parity is
  refused by the variant with its `development.*` code.
* **N3, cross-level smuggling** (`l2_cross_level_fields`): a Level 1, 3 or
  4 field inside a Level 2 recipe, or a non-boolean switch, is refused by the
  variant.
* **Permission ablation** (`l2_slot_ablation`): every Level 2 field fails
  the miner-facing contract, which signs on the Launchpad and admits on the
  validator; only the variant admits it.
* **P1 and P2, pool sources and weights** (`l2_pool_sources_and_weights`):
  a selection naming PRACTICE, an unregistered pool version, a part not in
  the version or cases themselves, or carrying weights outside [0, 2],
  non-numeric, negative or all zero, or an empty, oversized or malformed
  draw, is refused by the variant with its `pool.*` code before any rebuild
  (`carbon.battery.pools`, BATTERY-L2-POOL-SELECTION-01).
* **Determinism** (`l2_rebuild_determinism`): the same recipe and seed
  rebuild bit-identically twice on CPU, a pool-selection draw included.
* **Seams.** P3, budget evasion, is held by construction but its "charged in
  full" waits for the cost calculator; P4, distribution chasing, is a
  measurement, not a refusal (below). M1, the SVD's cost, is the cost
  calculator's finding (`battery_declarative.compute_accounting_seam`). M2,
  divergence, found no diverging recipe in the surface on CPU (below).
"""

from __future__ import annotations

import functools

from carbon.agent_campaign.attack.adapters import battery_declarative as d

LEVEL = 2
#: The smallest Muon recipe the Level 2 tests rebuild.
MUON = {"width": 16, "depth": 1, "steps": 48, "optimizer_family": "muon"}


def _strategy(**parameters):
    return d.strategy(MUON, **parameters)


def _rebuild_label():
    from carbon.battery import level2_worker

    return level2_worker.REBUILD_LABEL


def _version():
    from carbon.battery import level2

    return level2.VERSION


def _other_level_fields():
    from carbon.agent_campaign.attack.adapters import battery_level1
    from carbon.battery import level1, level4

    expression = battery_level1.strategy(next(iter(battery_level1.VALID.values())))
    return (
        (
            "level1_loss_expressions",
            {level1.FIELD: expression["parameters"][level1.FIELD]},
        ),
        ("level3_quasi_newton", {"polish_steps": 6, "quasi_newton_family": "bfgs"}),
        ("level3_line_search", {"polish_steps": 6, "line_search": "backtracking"}),
        ("level4_graph_slot", {level4.FIELD: "sha256:" + "ab" * 32}),
    )


def _pool(**changes):
    """A selection from battery's one registered pool version: TRAIN only,
    64 cases, uniform. Attacks change one part of it."""
    from carbon.battery import pools

    (version,) = pools.registered()
    return {"pool_version": version, "strata": {"train": 1.0}, "cases": 64, **changes}


def _pool_attacks():
    """P1 (forbidden sources) and P2 (malformed weights and draws)."""
    rows = (
        ("pool_practice_stratum", _pool(strata={"practice": 1.0})),
        ("pool_practice_beside_train", _pool(strata={"train": 1.0, "practice": 1.0})),
        ("pool_unregistered_version", _pool(pool_version="sha256:" + "0" * 64)),
        ("pool_part_not_in_version", _pool(strata={"bank": 1.0})),
        ("pool_names_its_cases", _pool(case_ids=["train-0001"])),
        ("pool_weight_above_two", _pool(strata={"train": 2.5})),
        ("pool_weight_negative", _pool(strata={"train": -0.5})),
        ("pool_weight_not_a_number", _pool(strata={"train": "1"})),
        ("pool_weight_boolean", _pool(strata={"train": True})),
        ("pool_weights_all_zero", _pool(strata={"train": 0})),
        ("pool_no_strata", _pool(strata={})),
        ("pool_no_cases", _pool(cases=0)),
        ("pool_more_cases_than_the_pool", _pool(cases=10**6)),
        ("pool_box_reversed", _pool(box={"c1": [3.0, 1.0]})),
        ("pool_box_unknown_input", _pool(box={"label": [0.0, 1.0]})),
    )
    return tuple((name, _strategy(pool_selection=value)) for name, value in rows)


def _cross_level_attacks():
    out = [
        (name, _strategy(muon_spectral=True, **fields))
        for name, fields in _other_level_fields()
    ]
    for label, value in (("string", "yes"), ("integer", 1), ("null", None)):
        out.append((f"switch_not_boolean_{label}", _strategy(muon_spectral=value)))
    return tuple(out)


def _off_family_attacks():
    out = [
        (
            f"muon_spectral_on_{family}",
            _strategy(muon_spectral=True, optimizer_family=family),
        )
        for family in ("adam", "lion", "sgd_momentum", "sam")
    ]
    out.append(
        (
            "muon_spectral_with_plateau_curve",
            _strategy(muon_spectral=True, learning_rate_curve="train_loss_plateau"),
        )
    )
    out.append(
        ("muon_spectral_on_pytorch", _strategy(muon_spectral=True, backend="pytorch"))
    )
    return tuple(out)


def _ablation_attacks():
    return (
        ("muon_spectral_on_at_level_0", _strategy(muon_spectral=True)),
        ("muon_spectral_off_at_level_0", _strategy(muon_spectral=False)),
    )


def _determinism_attacks():
    return (
        ("muon_spectral_mlp", _strategy(muon_spectral=True)),
        (
            "muon_spectral_constant_curve",
            _strategy(muon_spectral=True, learning_rate_curve="constant"),
        ),
        ("pool_selection_draw", _strategy(pool_selection=_pool())),
    )


@functools.lru_cache(maxsize=1)
def _families():
    gate = d.variant_gate(LEVEL)
    honest = _strategy(muon_spectral=True)
    honest_wider = _strategy(muon_spectral=True, width=32, depth=2)
    return {
        "l2_off_family": d.FamilyRow(
            check="construction_evaluation_isolation",
            words="SpecMuon only on the Muon family, never with the plateau curve, JAX only until backend parity",
            attacks=_off_family_attacks,
            boundary=gate,
            specimen=d.unchecked_gate,
            breached=d.accepted,
            control_ok=d.accepted,
            trained=honest,
            held_out=honest_wider,
        ),
        "l2_cross_level_fields": d.FamilyRow(
            check="artifact_and_dependency_attacks",
            words="a Level 2 recipe carries only Level 0 fields and the boolean switch; another level's field is refused",
            attacks=_cross_level_attacks,
            boundary=gate,
            specimen=d.unchecked_gate,
            breached=d.accepted,
            control_ok=d.accepted,
            trained=honest,
            held_out=_strategy(muon_spectral=False),
        ),
        "l2_pool_sources_and_weights": d.FamilyRow(
            check="artifact_and_dependency_attacks",
            words="a selection names only a registered pool version and its parts, never PRACTICE or a case, with weights in [0, 2] not all zero, and a draw the pool can fill",
            attacks=_pool_attacks,
            boundary=gate,
            specimen=d.unchecked_gate,
            breached=d.accepted,
            control_ok=d.accepted,
            trained=_strategy(pool_selection=_pool()),
            held_out=_strategy(pool_selection=_pool(strata={"train": 2.0}, cases=32)),
        ),
        "l2_slot_ablation": d.FamilyRow(
            check="baseline_and_permission_ablation",
            words="the miner-facing contract refuses the Level 2 field; only the variant admits it",
            attacks=_ablation_attacks,
            boundary=d.miner_contract_gate,
            specimen=d.variant_gate(LEVEL),
            breached=d.accepted,
            control_ok=d.accepted,
            trained=_strategy(),
            held_out=_strategy(width=32, depth=2),
        ),
        "l2_rebuild_determinism": d.FamilyRow(
            check="reconstruction_and_recipient_rebuild",
            words="the same recipe and seed rebuild bit-identically twice on CPU",
            attacks=_determinism_attacks,
            boundary=d.rebuilds_identically(LEVEL),
            specimen=d.unpinned_seed(LEVEL),
            breached=d.different,
            control_ok=d.same,
            trained=_strategy(),
            held_out=_strategy(muon_spectral=False, width=32),
        ),
    }


SEAMS = (
    (
        "l2_pool_budget_evasion",
        "resource_and_failure_accounting",
        (
            "P3: held by construction in battery-l2-v2: the draw is unique and "
            "never larger than the pool, and weights are normalised, so neither "
            "duplicates nor inflated weights can add training cases; `cases` "
            "counts as the recipe's train_cases (TRAINING-BUDGET-02). Whether "
            "it is charged in full is the cost calculator's, which refuses every "
            "development recipe (the M1 finding, owner Test Engineer); it runs "
            "when the calculator costs a pool-selection recipe"
        ),
    ),
    (
        "l2_pool_distribution_chasing",
        "adaptive_feedback_and_state_attacks",
        (
            "P4: weights that chase what public stratification says the current "
            "batch over-represents are admissible by design, so nothing refuses "
            "them; it is a measurement (the score must not beat the uniform-weight "
            "control beyond noise on a fresh batch), fed to leak detection (#737), "
            "and needs fresh cases (Phase 3)"
        ),
    ),
    (
        "l2_divergence",
        "score_exploitation_and_tail_failures",
        (
            "M2 HELD by bounds (Test Lead, 2026-10-08): no recipe in the surface "
            "diverged in CPU practice trials (learning rate 0.05 with SpecMuon, "
            "width 64), so no in-surface specimen can fire; the classification is "
            "proven by test-only fault injection outside the miner surface, an "
            "injected NaN or Inf being the candidate's own failure, never "
            "FAILED_INFRA (" + d.FAULT_INJECTION_TEST + ")"
        ),
    ),
    d.compute_accounting_seam(
        LEVEL,
        held=(
            "M1 HELD by construction (Test Lead, 2026-10-08): SpecMuon's rank and "
            "iterations are Carbon's fixed constants, not recipe settings, so no "
            "recipe can hide an SVD cost; separately, "
        ),
    ),
    d.fresh_cases_seam(LEVEL),
)

SPEC = d.LevelSpec(
    level=LEVEL,
    version=_version(),
    adapter_version="carbon.attack.adapter.battery-l2.v1",
    controls_version="carbon.attack.controls.battery-l2.v1",
    rebuild_label=_rebuild_label,
    families=_families,
    seams=SEAMS,
)
ADAPTER = d.BatteryDeclarativeAdapter(SPEC)
