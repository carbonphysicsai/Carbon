"""Battery construction Level 1, bounded loss expressions: an engineering draft.

GRAPHITE-ADMISSION-01 slice B. Battery is the first Challenge to climb the
ladder (OWNER-CHALLENGE-ROADMAP-03 item 2). This module is battery's adapter
for the Challenge-neutral Level-1 machinery:

- `OPERATIONS`: battery's bounded operation set
  (`carbon.reconstruction.loss_expressions.OperationSet`). Its terms are the
  per-case quantities battery's registered objective menu already computes in
  `carbon/battery/training.py` (`train.case_loss`). Its bounds are proposed
  engineering bounds, accepted or changed with the proposal.
- `terms`: those per-case quantities, computed as `training.case_loss`
  computes them, from network outputs, targets, output weights and the
  trajectory map.
- `menu_expression`: the expression that restates a registered objective
  menu setting, so today's Level 0 objective is one Level-1 expression. It is
  the ablation baseline of the climb.
- `DRAFT`: the surface, shaped like a level proposal. It is the implementing
  agent's engineering draft, not Graphite's proposal and not a decision.
- `development_profile`: the expanded profile's identity, for the climb
  harness (`carbon.agent_campaign.climb`).

**Nothing here is open.** Battery's construction contract is unchanged:
`objective.loss_expressions` stays excluded, so a miner path refuses the field
by name. Nothing in this module is wired to the trainer.

**Superseded for development use** by `carbon.battery.level1`
(GRAPHITE-L1-BUILD-01). That module holds the registered development-only
variants and Carbon's reconstruction, which the trainer reads. This module
stays as the GA-D6 draft record: its operation set is a version-1 set whose
digest the loss-expression tests pin, and the Level-0 attack adapter's draft
climb still uses it. Opening Level 1 to miners still follows the owner's
acceptance of a Level-1 proposal, by the climb procedure
(`challenge_pipeline.ladder`).
"""

from __future__ import annotations

from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from carbon.reconstruction.capability_registry import contract as _contract
from carbon.reconstruction.loss_expressions import OperationSet, digest_of

CHALLENGE = BATTERY_CHALLENGE
LEVEL = 1
DRAFT_SCHEMA = "carbon.battery.level1-draft.v1"
PROFILE_SCHEMA = "carbon.construction-development-profile.v1"
#: The permission the draft adds: the registry's excluded id, which the
#: accepted level would move to rebuildable with a new expression surface.
PERMISSION = "objective.loss_expressions"

#: Battery's per-case terms, each non-negative, as `training.case_loss`
#: computes them.
TERMS = {
    "sq_error": "sum over outputs of the output-weighted squared error",
    "target_energy": "sum over outputs of the output-weighted squared target",
    "traj_ramp_early": "trajectory squared error under the 2-to-0 time ramp",
    "traj_ramp_late": "trajectory squared error under the 0-to-2 time ramp",
    "traj_d1": "squared first time-difference of the trajectory error",
    "traj_d2": "squared second time-difference of the trajectory error",
    "traj_spectral": "frequency-weighted trajectory error spectrum",
}

#: Proposed engineering bounds. The scale range is the registered objective
#: weights' range (0-10); epsilon is `training.case_loss`'s relative-loss
#: epsilon (1e-6).
OPERATIONS = OperationSet(
    name="battery-level1-draft",
    terms=tuple(TERMS),
    max_depth=4,
    max_nodes=16,
    max_arity=8,
    scale=(0.0, 10.0),
    exponent=(0.5, 2.0),
    epsilon=1e-6,
)


def terms(xp, zhat, zt, gw, trajectory):
    """Battery's per-case terms for outputs `zhat` against targets `zt`.

    `gw` weights the outputs; `trajectory(z)` returns the normalized voltage
    and temperature trajectories (cases x times). Each term is the quantity
    `training.case_loss` computes for its registered surface."""
    error = zhat - zt
    pairs = [a - b for a, b in zip(trajectory(zhat), trajectory(zt))]

    def summed(per_trajectory):
        total = 0.0
        for e in pairs:
            total = total + per_trajectory(e)
        return total

    def spectral(e):
        spectrum = xp.abs(xp.fft.rfft(e, axis=1)) ** 2
        k = xp.linspace(0.0, 1.0, spectrum.shape[1])
        return xp.mean(k * spectrum, axis=1) / e.shape[1]

    return {
        "sq_error": xp.sum(error**2 * gw[None, :], axis=1),
        "target_energy": xp.sum(zt**2 * gw[None, :], axis=1),
        "traj_ramp_early": summed(
            lambda e: xp.mean(xp.linspace(2.0, 0.0, e.shape[1]) * e**2, axis=1)
        ),
        "traj_ramp_late": summed(
            lambda e: xp.mean(xp.linspace(0.0, 2.0, e.shape[1]) * e**2, axis=1)
        ),
        "traj_d1": summed(lambda e: xp.mean(xp.diff(e, axis=1) ** 2, axis=1)),
        "traj_d2": summed(lambda e: xp.mean(xp.diff(e, n=2, axis=1) ** 2, axis=1)),
        "traj_spectral": summed(spectral),
    }


def menu_expression(settings):
    """The Level-1 expression that restates a registered objective menu
    setting (`relative_loss`, `time_weighting`, `h1_weight`, `h2_weight`,
    `spectral_weight`)."""
    base = {"term": "sq_error"}
    if settings["relative_loss"]:
        base = {"op": "div", "args": [base, {"term": "target_energy"}]}
    parts = [base]
    if settings["time_weighting"] != "uniform":
        parts.append({"term": "traj_ramp_" + settings["time_weighting"]})
    for weight, term in (
        ("h1_weight", "traj_d1"),
        ("h2_weight", "traj_d2"),
        ("spectral_weight", "traj_spectral"),
    ):
        if settings[weight]:
            parts.append({"op": "scale", "by": settings[weight], "arg": {"term": term}})
    return parts[0] if len(parts) == 1 else {"op": "add", "args": parts}


DRAFT = {
    "schema": DRAFT_SCHEMA,
    "challenge": CHALLENGE,
    "level": LEVEL,
    "status": "ENGINEERING_DRAFT",
    "drafted_by": (
        "the implementing agent, GRAPHITE-ADMISSION-01 slice B; not a Graphite "
        "proposal and not a decision"
    ),
    "capabilities": [
        {
            "id": PERMISSION,
            "adds": (
                "the per-case training loss as a bounded expression over battery's "
                "registered loss terms, in place of the fixed objective menu"
            ),
            "bounds": (
                "operations add, mul, div, scale, pow, log1p and sqrt; terms "
                + ", ".join(TERMS)
                + "; depth at most 4, at most 16 nodes, add arity at most 8; "
                "scale in [0, 10]; exponent in [0.5, 2]; epsilon 1e-6. Proposed "
                "engineering bounds, accepted or changed with the proposal"
            ),
            "rationale": (
                "the Level-0 menu fixes how the registered terms combine; Level 1 "
                "lets a recipe choose the combination within a closed, "
                "non-negative operation set, so Carbon still rebuilds every loss "
                "with its own code"
            ),
            "sources": [
                "Design_Specs/Challenge_Admission.md §3, Level 1",
                "carbon/battery/training.py train.case_loss, the registered menu",
                "OWNER-CHALLENGE-ROADMAP-03 item 2, battery's first climb",
            ],
            "reconstruction": (
                "carbon/reconstruction/loss_expressions.py validates, "
                "canonicalizes and pins the expression and evaluates it with "
                "Carbon's code; this module computes the terms as "
                "training.case_loss does. Wiring the trainer to read an "
                "expression ships with the climb, with its own rebuild control"
            ),
            "attack_surface": (
                "loss shaping toward the scored outputs; numerically degenerate "
                "combinations such as division by a near-zero term; expressions "
                "that recreate an excluded behaviour; refused: any term or "
                "operation outside the set and any nonfinite or out-of-range "
                "constant"
            ),
        }
    ],
    "left_out": [
        "losses supplied as code or as free-form text",
        (
            "terms reading anything but TRAIN outputs and targets: no reference "
            "solver, no labels beyond TRAIN, no evaluation material"
        ),
        (
            "per-case weights chosen by final labels "
            "(inference.final_label_selection stays excluded)"
        ),
        "operations outside the closed set: no exp, min, max or conditionals",
        "any change to the score, the exam, the evaluation or the disclosure rule",
    ],
}


def development_profile():
    """The identity of the expanded development profile: today's contract plus
    the draft surface. It is not a construction contract, is not registered in
    `capability_registry.CONTRACTS`, and no miner path reads it."""
    base = _contract(CHALLENGE)
    document = {
        "schema": PROFILE_SCHEMA,
        "challenge": CHALLENGE,
        "level": LEVEL,
        "scope": "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS",
        "base_contract_digest": base.digest,
        "added": [PERMISSION],
        "operation_set": OPERATIONS.digest,
        "draft": digest_of(DRAFT),
    }
    return {**document, "digest": digest_of(document)}


def climb_plan(*, panel, attacks, attack_budget, combined, promising):
    """Battery's Level-1 climb plan for the Challenge-neutral harness. The
    panel, the attacks, the budget and the promising rule are the climb's own,
    declared before it runs; the attack budget is the owner's."""
    from carbon.agent_campaign import climb
    from carbon.reconstruction.capability_registry import Status

    base = _contract(CHALLENGE)
    level0 = frozenset(
        c.capability_id
        for c in base.capabilities
        if c.status is Status.REBUILDABLE_DEVELOPMENT
    )
    return climb.ClimbPlan(
        challenge=CHALLENGE,
        level=LEVEL,
        previous=climb.profile("level-0", base=base.digest, permissions=level0),
        expanded=climb.profile(
            "level-1-draft",
            base=base.digest,
            permissions=level0 | {PERMISSION},
            extra=development_profile()["digest"],
        ),
        new_permissions=(PERMISSION,),
        panel=tuple(panel),
        attacks=tuple(attacks),
        attack_budget=attack_budget,
        combined=tuple(combined),
        promising=promising,
    )
