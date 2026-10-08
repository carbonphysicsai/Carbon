"""Battery's Level 2 attack adapter: SpecMuon (`battery-l2-spectral-v1`).

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
* **Determinism** (`l2_rebuild_determinism`): the same recipe and seed
  rebuild bit-identically twice on CPU.
* **Seams.** `data.pool_selection` (P1-P4) is not in the registered
  variant, so it has nothing to attack. M1, the SVD's cost, is the cost
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
        "l2_pool_selection",
        "adaptive_feedback_and_state_attacks",
        (
            "data.pool_selection (P1 forbidden sources, P2 malformed weights, P3 "
            "budget evasion, P4 distribution chasing) was accepted with changes "
            "at level-climb-1 but is not in the registered variant "
            "battery-l2-spectral-v1, so there is nothing to attack; it needs its "
            "own variant build on the published pool (OWNER-BANK-ARCHITECTURE-01), "
            "and P4 is a measurement for leak detection (#737), not a refusal"
        ),
    ),
    (
        "l2_divergence",
        "score_exploitation_and_tail_failures",
        (
            "M2: no recipe in the surface diverged in CPU practice trials "
            "(learning rate 0.05 with SpecMuon, width 64), so no specimen can "
            "fire; a non-finite result is typed by the same pod-phase path whose "
            "candidate attribution Level 1's trial family proves (R1)"
        ),
    ),
    d.compute_accounting_seam(LEVEL),
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
