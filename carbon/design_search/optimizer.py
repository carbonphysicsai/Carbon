"""Development-only, model-family-neutral execution of registered design tasks."""

from __future__ import annotations

from carbon.design_search import tasks as dt


def _neighbors(grammar, action):
    """v1 frozen order: registration order, lower neighbor before upper."""
    for var in grammar["variables"]:
        name = var["name"]
        if var["type"] == "enum":
            index = var["values"].index(action[name])
            values = [
                var["values"][index + delta]
                for delta in (-1, 1)
                if 0 <= index + delta < len(var["values"])
            ]
        else:
            step = float(dt._number(var["step"], "step"))
            values = [action[name] - step, action[name] + step]
        for value in values:
            yield {**action, name: value}


def _better(task, left, right):
    """Whether the first candidate is strictly preferable under the tie rule."""
    if left is None or left[1]["feasible"] is not True:
        return False
    if right is None or right[1]["feasible"] is not True:
        return True
    order = {candidate: i for i, candidate in enumerate(task["candidates"])}

    def key(item):
        candidate, row = item
        secondary = task["secondary"]
        tie = 0 if secondary is None else dt._signed(secondary, row["secondary"])
        return (
            dt._signed(task["objective"], row["objective"]),
            tie,
            order[candidate],
        )

    return key(left) < key(right)


def run_optimizer(task, predictor, *, model_id):
    """Run the registered exhaustive or multi-start path with a hard budget.

    The callback receives copies of a canonical action and one condition.
    Starts, seed and neighbor order never come from the caller. Every attempted
    condition call, invalid proposal and model failure consumes budget.
    """
    if task.get("schema") != dt.RUNNABLE_SCHEMA:
        raise dt.TaskError("run_optimizer requires a registered runnable task")
    dt._verify_task_digest(task)
    grammar = task["identity"]["action_grammar"]
    optimizer = task["identity"]["optimizer"]
    budget = task["identity"]["query_budget"]
    conditions = task["conditions"]
    index = {
        dt.digest(action): candidate for candidate, action in task["actions"].items()
    }
    attempted = 0
    invalid = 0
    model_failures = 0
    panels = set()
    seen = set()
    predicted = {}
    stopped_for_budget = False
    needed = {task["objective"]["quantity"]}
    needed.update(limit["quantity"] for limit in task["limits"])
    if task["secondary"] is not None:
        needed.add(task["secondary"]["quantity"])

    def proposal(action):
        nonlocal attempted, invalid, model_failures, stopped_for_budget
        raw_key = dt.digest(action)
        if raw_key in seen:
            return index.get(raw_key)
        seen.add(raw_key)
        try:
            canonical = dt.snap_action(grammar, action)
            candidate = index.get(dt.digest(canonical))
            if candidate is None:
                raise dt.TaskError("action is outside registered bank")
        except dt.TaskError:
            if attempted >= budget:
                stopped_for_budget = True
                return None
            attempted += 1
            invalid += 1
            return None
        canonical_key = dt.digest(canonical)
        if canonical_key != raw_key and canonical_key in seen:
            return candidate
        seen.add(canonical_key)
        if candidate in panels:
            return candidate
        if budget - attempted < len(conditions):
            stopped_for_budget = True
            return None
        rows = {}
        for condition in conditions:
            attempted += 1
            try:
                value = predictor(dict(canonical), dict(condition))
                if not isinstance(value, dict) or not needed <= set(value):
                    raise ValueError("model result lacks quantities")
                if any(
                    isinstance(value[q], bool)
                    or not isinstance(value[q], (int, float))
                    or not dt._number(value[q], q).is_finite()
                    for q in needed
                ):
                    raise ValueError("model result lacks finite quantities")
                rows[condition["id"]] = {q: value[q] for q in needed}
            except Exception:  # noqa: BLE001 - untrusted model failures are counted
                model_failures += 1
                break
        else:
            panels.add(candidate)
            for condition_id, value in rows.items():
                predicted[(candidate, condition_id)] = value
        return candidate

    if optimizer["class"] == "exhaustive":
        for candidate in task["candidates"]:
            proposal(task["actions"][candidate])
            if stopped_for_budget:
                break
    else:
        starts = sorted(
            optimizer["starts"],
            key=lambda candidate: dt.digest([task["identity"]["seed"], candidate]),
        )
        for start in starts:
            proposal(task["actions"][start])
            if stopped_for_budget:
                break
            current = start
            while current in panels:
                current_row = dt.assess(task, predicted)[current]
                improved = False
                for neighbor in _neighbors(grammar, task["actions"][current]):
                    candidate = proposal(neighbor)
                    if stopped_for_budget:
                        break
                    if candidate in panels:
                        row = dt.assess(task, predicted)[candidate]
                        if _better(task, (candidate, row), (current, current_row)):
                            current = candidate
                            improved = True
                            break
                if stopped_for_budget or not improved:
                    break
            if stopped_for_budget:
                break

    selected = dt.select(task, dt.assess(task, predicted))
    complete = optimizer["class"] == "exhaustive" and len(panels) == len(
        task["candidates"]
    )
    accounting = {
        "attempted_queries": attempted,
        "query_budget": budget,
        "invalid_queries": invalid,
        "model_failures": model_failures,
        "complete_panels": len(panels),
        "exhaustive_coverage": complete,
        "stopped_for_budget": stopped_for_budget,
    }
    body = {
        "schema": dt.COMMIT_SCHEMA,
        "task_digest": task["task_digest"],
        "model_id": model_id,
        "selected": selected,
        "predictions_digest": dt.digest(
            sorted([list(k), v] for k, v in predicted.items())
        ),
        "execution": accounting,
    }
    return {
        "commitment": {**body, "commitment_digest": dt.digest(body)},
        "accounting": accounting,
    }


def audit_optimizer(primary_task, audit_task, predictor, *, model_id):
    """Equal-budget path diagnostic; audit never substitutes its pick."""
    if (
        primary_task.get("schema") != dt.RUNNABLE_SCHEMA
        or audit_task.get("schema") != dt.RUNNABLE_SCHEMA
    ):
        raise dt.TaskError("audit requires two runnable tasks")

    def comparable(task):
        return {
            k: v for k, v in task.items() if k not in ("task_digest", "identity")
        } | {
            "identity": {k: v for k, v in task["identity"].items() if k != "optimizer"}
        }

    if comparable(primary_task) != comparable(audit_task):
        raise dt.TaskError("audit tasks must share the decision and query budget")
    primary = run_optimizer(primary_task, predictor, model_id=model_id)
    audit = run_optimizer(audit_task, predictor, model_id=model_id)
    return {
        "primary": primary,
        "audit": audit,
        "same_pick": primary["commitment"]["selected"]
        == audit["commitment"]["selected"],
    }
