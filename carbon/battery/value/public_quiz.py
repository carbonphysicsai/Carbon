"""Quiz Q3's scenario and measures, importable by a miner-reachable module
(Phase A; Validator ruling on Battery's public measure).

``quiz`` imports ``false_acceptance``, which imports the battery panel and so its
attack harness (OWNER-GRAPHITE-ATTACKER-01); the two functions Battery's decision
value needs do not. They are copied here with identical logic;
``tests/cpu/test_battery_public_dual.py`` pins each equal (as syntax trees, and on
fixtures) to ``quiz``'s. DEVELOPMENT only.
"""

from __future__ import annotations

import statistics

from . import contract as ev


def q3_scenario(scenario_id, condition):
    """A Q3 scenario: one opaque id and one (t_amb_c, soc0) condition."""
    t_amb_c, soc0 = condition
    return {"id": scenario_id, "conditions": [[float(t_amb_c), float(soc0)]]}


def q3_measures(outcomes, contract=None):
    """Over a model's outcomes on feasible scenarios (quiz-registry-v7).
    UNRESOLVED is never clean:
    - `regret`: mean decision loss, where an UNRESOLVED pick takes its
      band-pessimistic value (a SELECTED_UNRESOLVED pick costs the false
      acceptance cost, an ABSTENTION_UNRESOLVED the missed-opportunity cost);
    - `false_feasible` (the gate default, variant (i)): picks the reference
      shows infeasible or cannot clear, over all outcomes;
      `false_feasible_resolved_only` (variant (ii)) excludes UNRESOLVED, for
      sensitivity;
    - `over_caution`: missed opportunities (an ABSTENTION_UNRESOLVED counts),
      over all outcomes;
    - `unresolved`: the share of outcomes that are UNRESOLVED (diagnostic
      (e)).
    `contract` supplies the mistake costs (EV4's when omitted)."""
    if contract is None:
        from pathlib import Path

        contract, _ = ev.load(
            Path(__file__).resolve().parent
            / "contracts/ev4-charge-protocol-selection.v1.json"
        )
    costs = contract["mistake_costs"]
    if not outcomes:
        return {
            "false_feasible": None,
            "false_feasible_resolved_only": None,
            "regret": None,
            "over_caution": None,
            "unresolved": None,
        }

    def loss(o):
        if o["decision_loss"] is not None:
            return o["decision_loss"]
        if o["kind"] == "ABSTENTION_UNRESOLVED":
            return costs["missed_opportunity"]
        return costs["false_acceptance"]

    n = len(outcomes)
    unresolved = [o for o in outcomes if o["decision_loss"] is None]
    resolved = [o for o in outcomes if o["decision_loss"] is not None]
    infeasible = sum(o["kind"] == "SELECTED_INFEASIBLE" for o in outcomes)
    selected_unresolved = sum(o["kind"] == "SELECTED_UNRESOLVED" for o in outcomes)
    return {
        "false_feasible": (infeasible + selected_unresolved) / n,
        "false_feasible_resolved_only": (
            sum(o["kind"] == "SELECTED_INFEASIBLE" for o in resolved) / len(resolved)
            if resolved
            else None
        ),
        "regret": statistics.fmean(loss(o) for o in outcomes),
        "over_caution": sum(
            o["kind"] in ("MISSED_OPPORTUNITY", "ABSTENTION_UNRESOLVED")
            for o in outcomes
        )
        / n,
        "unresolved": len(unresolved) / n,
    }
