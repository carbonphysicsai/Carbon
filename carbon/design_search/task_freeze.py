"""Bind design-task code into the existing experiment freeze/pilot path.

The historical Track B adapters and their code pins stay byte-identical.
New design-task experiments opt into this adapter wrapper before calling
`experiment.freeze` and use the same wrapped adapter for `pilot`.
"""

from __future__ import annotations

from dataclasses import replace

from carbon.design_search import experiment, tasks

DESIGN_TASK_CODE = (
    "carbon/design_search/tasks.py",
    "carbon/design_search/indexed.py",
    "carbon/design_search/indexed_power.py",
    "carbon/design_search/score_bridge.py",
    "carbon/design_search/optimizer.py",
    "carbon/design_search/cost.py",
    "carbon/design_search/query_cost.py",
    "carbon/design_search/task_projection.py",
    "carbon/design_search/task_measures.py",
    "carbon/design_search/diversity.py",
    "carbon/design_search/controls.py",
    "carbon/design_search/power.py",
    "carbon/design_search/power_accumulation.py",
    "carbon/design_search/producer_panels.py",
    "carbon/design_search/reference_resolution.py",
    "carbon/design_search/__main__.py",
    "carbon/design_search/task_freeze.py",
)


def _with_design_task(adapter, registered_task):
    """Return an adapter whose contract and code pins include one task.

    `experiment.freeze` hashes every `code_path` and `pilot` rechecks those
    hashes before running. The task's private registration stays producer-side.
    """
    if (
        type(registered_task) is not dict
        or registered_task.get("schema")
        not in (tasks.SCHEMA, tasks.RUNNABLE_SCHEMA, tasks.INDEXED_SCHEMA)
        or tasks.digest(
            {k: v for k, v in registered_task.items() if k != "task_digest"}
        )
        != registered_task.get("task_digest")
    ):
        raise experiment.ExperimentError("registered_design_task_required")
    if registered_task["schema"] == tasks.INDEXED_SCHEMA:
        from carbon.design_search.indexed import validate_indexed

        validate_indexed(registered_task)
    if adapter.challenge != registered_task["identity"]["challenge"]:
        raise experiment.ExperimentError("task_challenge_mismatch")
    return replace(
        adapter,
        contract_digest=experiment.digest(
            {"adapter": adapter.contract_digest, "task": registered_task["task_digest"]}
        ),
        code_paths=tuple(dict.fromkeys((*adapter.code_paths, *DESIGN_TASK_CODE))),
    )


def freeze(adapter, registered_task, **kwargs):
    """Create a task-bound manifest through the existing experiment freeze."""
    return experiment.freeze(_with_design_task(adapter, registered_task), **kwargs)


def pilot(manifest, adapter, registered_task, **kwargs):
    """Verify the same task and all pinned code before the existing pilot."""
    bound = _with_design_task(adapter, registered_task)
    if manifest.get("decision_contract") != bound.contract_digest:
        raise experiment.ExperimentError("design_task_identity_changed")
    return experiment.pilot(manifest, bound, **kwargs)
