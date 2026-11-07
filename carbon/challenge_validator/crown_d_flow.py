"""Crown-time D, end to end for one contender (scope GRAPHITE_CROWN_D_SCOPE_20261105.md; interface
GRAPHITE_CROWN_D_INTERFACE_20261106.md). Custody only; off unless the version registers a `crown_d` block.

1. `request_contender`: the version's registered optimizer (`rule.optimizer`) picks ONE design per target on the contender's model (`crown_d.pick`) and
   each pick is queued for a COARSE-rung solve (`crown_d_queue`; a pick that matches an earlier solve within the dedupe
   grid is answered from the cache, at no budget).
2. The custody runner calls `CrownDQueue.run_once(solve, weekly_solves=rule.weekly_solves)` with design-optimum's
   `solve(target_id, fixed, design, rung)`: FIFO, the owner's weekly count, infrastructure faults re-queued in place.
3. `advance`: reads the queue; a coarse result within U of a limit or of the zero (`crown_d.needs_fine`) queues the
   FINE rung for that target; a target's final outputs are its fine result when one was needed, else its coarse one;
   each final result is scored (`crown_d.target_d`) and `crown_d.decide` returns SOLVED (with D), HOLD,
   CROWN_DEFERRED_D_BUDGET or FAILED_INFRA. HOLD and DEFERRED keep the king's crown; D is never scored as 0 while
   pending.

Cost shape (D_CROWN_COST_OPTIONS_20261107, design-optimum; C + B + A + D):
- C: picks come from ONE rebuild, the registered `pick_rebuild_seed`; a model from another rebuild refuses.
- B: the caller requests D as soon as that rebuild finishes, while the remaining rebuilds run; the crown decision
  still waits for both (HOLD).
- A: the custody runner drives `CrownDQueue.run_round(solve, weekly_solves=..., width=...)`, one parallel round.
- D: `request_contender` picks only the epoch's drawn k targets (`crown_d.draw_targets`, a custody key); a pick of an
  identical model + seed + target is read from the queue's pick cache (the king's picks are searched once).

Nothing here solves, writes a door or moves a crown: the crown hook reads the decision.
"""

from __future__ import annotations

from carbon.scoring import crown_d

QUEUED_STATES = ("QUEUED", "SOLVING")


def request_contender(
    queue,
    rule,
    zero,
    problems,
    evaluators,
    *,
    challenge,
    version,
    submission,
    host_class,
    model_sha256,
    rebuild_seed,
    epoch,
    draw_key,
):
    """Pick one design per DRAWN target and queue its coarse solve. ``problems``: {target_id: Problem} for every pool
    task of the version; ``evaluators``: {target_id: evaluator} or a callable ``target_id -> evaluator`` (built only
    for drawn targets whose pick is not cached), each a `pool_model_search.model_evaluator` over the contender's model
    rebuilt with ``rebuild_seed`` (sha256 ``model_sha256``). Returns ``{target_id: pick}`` for the drawn targets,
    which `advance` needs."""
    crown_d.check_rule(rule)
    if rebuild_seed != rule.pick_rebuild_seed or type(rebuild_seed) is not int:
        raise crown_d.CrownDRefused("crown_d_pick_not_from_the_registered_rebuild")
    drawn = crown_d.draw_targets(
        rule,
        draw_key,
        challenge_id=challenge,
        version=version,
        epoch=epoch,
        targets=list(problems),
    )
    picks = {}
    for target_id in drawn:
        problem = problems[target_id]
        zero.entry(target_id)  # a target without a zero is never queued
        key = crown_d.pick_key(
            challenge, version, target_id, problem, rule, model_sha256=model_sha256
        )
        cached = queue.cached_pick(key)
        if cached is None:
            evaluator = (
                evaluators(target_id) if callable(evaluators) else evaluators[target_id]
            )
            chosen = crown_d.pick(problem, evaluator, host_class=host_class, rule=rule)
            queue.store_pick(key, list(chosen.design), chosen.model_feasible)
        else:
            chosen = crown_d.Pick(
                target_id=target_id, design=cached[0], model_feasible=cached[1]
            )
        picks[target_id] = chosen
        _enqueue(
            queue,
            rule.coarse_rung,
            chosen,
            problem,
            rule,
            challenge,
            version,
            submission,
        )
    return picks


def _enqueue(queue, rung, chosen, problem, rule, challenge, version, submission):
    queue.enqueue(
        challenge=challenge,
        version=version,
        submission=submission,
        target=chosen.target_id,
        rung=rung,
        key=crown_d.dedupe_key(
            challenge,
            version,
            chosen.target_id,
            rung,
            problem,
            list(chosen.design),
            rule.dedupe_grid,
        ),
        fixed=dict(problem.fixed),
        design=[float(x) for x in chosen.design],
    )


def _final(entry):
    """A queue row as a decide() result state (outputs only for SOLVED)."""
    if entry is None or entry["state"] in QUEUED_STATES:
        return {"state": crown_d.PENDING}
    if entry["state"] == "REFERENCE_FAILED":
        return {"state": crown_d.REFERENCE_FAILED, "code": entry["code"]}
    return {"state": "SOLVED", "outputs": entry["outputs"]}


def advance(
    queue,
    rule,
    zero,
    problems,
    picks,
    *,
    challenge,
    version,
    submission,
    requested_at,
    now,
):
    """The contender's D decision now (see the module docstring); queues any fine rung the coarse results call for."""
    crown_d.check_rule(rule)
    rows = queue.results(submission)
    results = {}
    for target_id in sorted(picks):  # the drawn targets
        problem, entry = problems[target_id], zero.entry(target_id)
        coarse = _final(rows.get((target_id, rule.coarse_rung)))
        final = coarse
        if coarse["state"] == "SOLVED" and crown_d.needs_fine(
            problem, entry, coarse["outputs"]
        ):
            fine_row = rows.get((target_id, rule.fine_rung))
            if fine_row is None:
                _enqueue(
                    queue,
                    rule.fine_rung,
                    picks[target_id],
                    problem,
                    rule,
                    challenge,
                    version,
                    submission,
                )
            final = _final(fine_row)
        if final["state"] == "SOLVED":
            final = {
                **final,
                "d": crown_d.target_d(problem, entry, final["outputs"]),
            }
        results[target_id] = final
    deferred = any(row["deferred"] for row in queue.status(submission))
    return crown_d.decide(
        rule,
        results=results,
        expected_targets=sorted(picks),
        requested_at=requested_at,
        now=now,
        budget_deferred=deferred,
    )


__all__ = ["advance", "request_contender"]
