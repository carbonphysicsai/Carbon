"""Carbon's side of a Graphite selection (CHALLENGE-PROTOCOL-04 slice 4).

After a Constructor session selects a recipe, Carbon, not the agent, does
four things:
1. **Checks the contract record.** No construction contract may differ from
   its newest record (`expansion_record.unrecorded`), and the selection must
   carry the live battery contract's digest. Step 4 records no expansion, so
   this is the Level 0 contract.
2. **Rebuilds.** It compiles the recipe (`battery.compile.compile_recipe`)
   and rebuilds it with a recorded development seed.
3. **Rebuilds again from the package alone.** The package is the selection's
   strategy and contract digest. The model bytes must match: Carbon can
   rebuild what Graphite constructed (OWNER-GRAPHITE-02).
4. **Scores.** It scores on the development scoring set under the deciding
   rule (`battery.value.scoring.components`), and with an incumbent compares
   the two case by case. This is a report only. No margin is applied,
   because the margin is the science owner's.

A selection that fails steps 1 to 3 is refused with a typed reason, returned
as a finding (`FAILING_TRIGGER`, OWNER-CHALLENGE-STEP4-01: a reproduced
fail-open), and never scored.

The scoring set is the committed development set the engineering-value
studies use (`scoring.SCORING_REFERENCES`). Graphite's checkout boundaries
deny it, and nothing here returns it to an agent. Which set is final is the
science owner's decision. This one is provisional.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from carbon.reconstruction import expansion_record
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE, contract

SCHEMA = "carbon.graphite.selection-score.v1"
#: Carbon's development reconstruction seed: seed 0, as in the EV panels.
DEVELOPMENT_SEED = 0
FINDING = "FAILING_TRIGGER"


class SelectionRefused(ValueError):
    """A selection Carbon will not score. `code` is typed; `finding` says
    whether it is a reproduced fail-open."""

    def __init__(self, code, *, finding):
        super().__init__(code)
        self.code, self.finding = code, finding


def load_selection(run_dir):
    """The selected candidate record a Constructor session wrote."""
    path = Path(run_dir) / "ledger" / "epoch-1" / "selected-recipe.json"
    if not path.is_file():
        raise SelectionRefused("no_selection", finding=False)
    record = json.loads(path.read_bytes())
    if record.get("status") != "SELECTED":
        raise SelectionRefused("no_selection", finding=False)
    return record


def check_contract(selection, *, root=expansion_record.ROOT):
    """Step 1: the live contracts are their records, and the selection was
    compiled under the live battery contract."""
    if (selection.get("strategy") or {}).get("challenge_id") != BATTERY_CHALLENGE:
        raise SelectionRefused("not_a_battery_selection", finding=False)
    if expansion_record.unrecorded(root):
        raise SelectionRefused("unrecorded_contract_change", finding=True)
    newest = expansion_record.records(BATTERY_CHALLENGE, root)[-1]["contract_digest"]
    if (
        selection.get("contract_digest") != newest
        or newest != contract(BATTERY_CHALLENGE).digest
    ):
        raise SelectionRefused("selection_contract_not_current", finding=True)


def _rebuild(backend, label, strategy, seed):
    from carbon.battery.compile import RecipeRejected, compile_recipe

    try:
        _, recipe = compile_recipe(strategy)
    except RecipeRejected:
        raise SelectionRefused("selection_does_not_compile", finding=True) from None
    state, stats = backend.reconstruct(label, recipe, seed)
    return recipe, state, stats


def score_selection(
    selection,
    *,
    backend,
    repository=".",
    seed=DEVELOPMENT_SEED,
    incumbent=None,
    scoring=None,
):
    """Steps 1 to 4. Returns the report; raises `SelectionRefused`.

    `incumbent` is an optional strategy to compare with, case by case.
    `scoring` replaces the development scoring set `(store, case_ids,
    identity)` for bounded tests."""
    from carbon.battery.value import scoring as value_scoring

    check_contract(selection)
    strategy = selection["strategy"]
    recipe, state, stats = _rebuild(backend, "graphite-rebuild", strategy, seed)
    if (selection.get("strategy_hash"), selection.get("construction_plan_digest")) != (
        recipe.strategy_hash,
        recipe.plan_digest,
    ):
        # The agent's own compile recorded another design than Carbon's.
        raise SelectionRefused("selection_plan_mismatch", finding=True)
    # Step 3: the package alone: the strategy as JSON, compiled afresh.
    package = json.loads(json.dumps(strategy, sort_keys=True))
    _, again, _ = _rebuild(backend, "graphite-clean-rebuild", package, seed)
    first, second = (hashlib.sha256(s).hexdigest() for s in (state, again))
    if first != second:
        raise SelectionRefused("clean_rebuild_differs", finding=True)
    store, case_ids, identity = scoring or value_scoring.scoring_set(repository)
    inputs = {
        c: dict(store.refs[c]["inputs"])
        for c in case_ids
        if store.refs[c].get("inputs")
    }
    predictions = backend.infer("graphite-infer", state, inputs)
    candidate = value_scoring.components(predictions, case_ids, store)
    report = {
        "schema": SCHEMA,
        "selection": {
            "strategy_hash": selection.get("strategy_hash"),
            "contract_digest": selection["contract_digest"],
            "recipe_digest": recipe.recipe_digest,
        },
        "rebuild": {
            "seed": seed,
            "state_sha256": first,
            "clean_rebuild_identical": True,
            "fit": stats,
            "backend": dict(getattr(backend, "identity", {}) or {}),
        },
        "scoring_set": identity,
        "rule": value_scoring.CONTROL,
        "candidate": candidate,
        "incumbent": None,
        "comparison": None,
        "margin": None,
        "authority": {"grade": False, "evaluator": False, "reward": False},
    }
    if incumbent is not None:
        _, inc_state, _ = _rebuild(backend, "graphite-incumbent", incumbent, seed)
        inc_predictions = backend.infer("graphite-incumbent-infer", inc_state, inputs)
        report["incumbent"] = value_scoring.components(inc_predictions, case_ids, store)
        report["comparison"] = _case_by_case(
            predictions, inc_predictions, case_ids, store
        )
    return report


def _case_by_case(candidate, incumbent, case_ids, store):
    """How many scorable cases each has the lower exam error on. A report: no
    margin, no verdict; cases either fails or leaves unscored are not counted."""
    from carbon.battery import exam

    rows_a, _ = exam.evaluate(candidate, case_ids, store)
    rows_b, _ = exam.evaluate(incumbent, case_ids, store)
    better = worse = tied = 0
    for a, b in zip(rows_a, rows_b, strict=True):
        sa, sb = a.get("error"), b.get("error")
        if sa is None or sb is None:
            continue
        if sa < sb:
            better += 1
        elif sa > sb:
            worse += 1
        else:
            tied += 1
    return {"candidate_better": better, "candidate_worse": worse, "tied": tied}
