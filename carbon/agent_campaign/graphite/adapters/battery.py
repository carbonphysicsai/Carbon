"""Battery's adapter: the first instance of `challenge.py`'s functions.

Each function wraps battery code that already exists, so battery's step 4
behaves exactly as it did before the step 4 code was generalized:
- the permission inventory is `study.permission_inventory()` (Level 0);
- the admission gate is #504's reconstruction gate, `experiment.admit`
  (PROTO4-D7);
- a sandbox code run is bounded like a practice run, by the practice worker's
  wall allowance (`battery.research.PRACTICE_SECONDS`, PROTO4-D6).
"""

from __future__ import annotations


def permission_inventory():
    from carbon.agent_campaign import study

    return study.permission_inventory()


def public_identity():
    from carbon.battery.challenge import CHALLENGE

    return {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}


def admission_refusals(strategy):
    """Carbon's own admission of a recipe: #504's reconstruction gate, which
    compiles it exactly as Carbon would rebuild it inside the recorded battery
    construction contract. Empty when Carbon would rebuild it."""
    from .. import experiment

    try:
        experiment.admit(strategy, 0)
    except experiment.Unrebuildable as refused:
        return [refused.code] + sorted({code for code, _path in refused.issues})
    except experiment.NotServed:
        return []  # Carbon rebuilds it; only #504's pods do not serve it
    return []


def code_run_seconds():
    from carbon.battery.research import PRACTICE_SECONDS

    return PRACTICE_SECONDS


def recipe_outside_contract():
    """The pinned scaffold with a model family the contract does not admit."""
    from carbon.battery.research import SCAFFOLD

    return {**SCAFFOLD, "backbone": "transolver"}
