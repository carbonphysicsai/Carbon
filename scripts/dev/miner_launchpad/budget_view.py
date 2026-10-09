"""Whether a recipe is inside its Challenge's compute budget, on every door.

LAUNCHPAD-COMPUTE-BUDGET-STATUS-01. The status is admission's own
(`challenge_contracts.budget_status`, which `check_compute_budget` refuses
by), so what a miner is shown at practice, freeze, commit and submit is what
the submission compile decides on this host. The validator's figure on its
pinned image is the one that decides.

- `budget_status` is a free read on both doors (browser
  `POST /api/v1/operations/budget_status`, MCP `carbon_budget_status`).
- A practice result carries it for its recipe; practice is never refused by
  it.
- Freeze, commit and submit show it and refuse, before anything is signed or
  sent, a recipe a declared budget would refuse: over it
  (`over_compute_budget`), its cost not calculable in the budget's unit
  (`cost_unmeasurable`), or a malformed declaration
  (`compute_budget_malformed`).

Each Challenge's budget comes from its own training budget study and the
owner's decision on it; until then the contract declares none (NOT_SET), no
number is shown, and nothing is computed. This module chooses no budget, unit
or factor. It names no Challenge: the cost is reached through the training
budget adapter registry.
"""

from __future__ import annotations

import contextlib
import functools
import json

#: The refusals a declared budget gives, by status.
OVER = "over_compute_budget"
UNMEASURABLE = "cost_unmeasurable"
MALFORMED = "compute_budget_malformed"


@functools.lru_cache(maxsize=256)
def _status(canonical):
    from carbon.reconstruction.capability_registry import CONTRACTS
    from carbon.reconstruction.challenge_contracts import (
        BUDGET_STATUS_SCHEMA,
        BUDGET_UNMEASURABLE,
        budget_status,
        declared_compute_budget,
    )

    strategy = json.loads(canonical)
    try:
        return json.dumps(budget_status(strategy["challenge_id"], strategy))
    except Exception:  # noqa: BLE001 - the calculator failed on this recipe
        # Only a declared budget computes anything, so one is declared here.
        # Shown as not calculable: admission does not admit such a recipe.
        budget = None
        with contextlib.suppress(Exception):  # the unit is then unknown
            budget = declared_compute_budget(CONTRACTS[strategy["challenge_id"]])[1]
        return json.dumps(
            {
                "schema": BUDGET_STATUS_SCHEMA,
                "status": BUDGET_UNMEASURABLE,
                "unit": budget["unit"] if budget else None,
                "used": None,
                "allowed": budget["value"] if budget else None,
                "within": None,
            }
        )


def status(strategy):
    """The budget status of a recipe that names its Challenge, or None for
    anything else. Deterministic on one image, so it is computed once per
    recipe in this process."""
    if type(strategy) is not dict or type(strategy.get("challenge_id")) is not str:
        return None
    try:
        canonical = json.dumps(strategy, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return None
    return json.loads(_status(canonical))


def _number(value):
    if type(value) is float and value.is_integer() and abs(value) < 1e15:
        value = int(value)
    return format(value, ",") if type(value) is int else format(value, ".4g")


def refusal(value):
    """The `Rejected` a door raises for a recipe admission would refuse by
    its budget, carrying the numbers (`budget`) and its next step; None when
    there is no declared budget or the recipe is within it."""
    from scripts.dev.miner_launchpad.controller import Rejected

    if value is None or value["status"] == "NOT_SET":
        return None
    if value["status"] == "SET" and value["within"]:
        return None
    if value["status"] == "MALFORMED":
        refused = Rejected(MALFORMED, 409)
        refused.next_step = (
            "This Challenge's compute budget declaration is malformed, a "
            "repository defect: nothing can be frozen or submitted under it "
            "until Carbon fixes it. Your practice results are kept."
        )
        return refused
    unit = value["unit"] or "its unit"
    if value["status"] == "SET":
        refused = Rejected(OVER, 409)
        refused.next_step = (
            "This recipe's calculated cost is "
            + _number(value["used"])
            + " "
            + unit
            + ", over this Challenge's compute budget of "
            + _number(value["allowed"])
            + " "
            + unit
            + ". Make it cheaper (fewer steps, members or parameters), "
            "practise it, and freeze that recipe instead."
        )
    else:
        refused = Rejected(UNMEASURABLE, 409)
        refused.next_step = (
            "This recipe's cost cannot be calculated in this Challenge's "
            "budget unit (" + unit + "; " + value["status"] + "), and a cost "
            "that cannot be checked is refused. Choose a recipe "
            "carbon_budget_status shows as Within budget."
        )
    refused.budget = {key: value[key] for key in ("unit", "used", "allowed")}
    return refused


def require_within(strategy):
    """The recipe's budget status, or its refusal raised now."""
    value = status(strategy)
    refused = refusal(value)
    if refused is not None:
        raise refused
    return value


def for_request(request):
    """`budget_status`: one recipe against one Challenge's compute budget."""
    from carbon.challenge_registry.campaigns import challenge_ref
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.operations import strategy_value

    challenge = request["challenge"]
    if type(challenge) is not str:
        raise Rejected("challenge_required")
    if challenge_ref(challenge)["version"] is None:
        raise Rejected("challenge_unknown", 404)
    strategy = strategy_value(request)
    if strategy.get("challenge_id") != challenge:
        raise Rejected("strategy_names_another_challenge")
    return status(strategy)
