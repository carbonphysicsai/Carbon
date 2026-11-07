"""Menu D on the door grade path (design codex-queue/reports/GRAPHITE_B_MENU_DOOR_D_DESIGN_20261107.md; Validator-2B
7 Nov rulings (a) menu rows in the bank, (b) draw after the predictions, (c) declared change).

A version that registers a ``menu`` block (`pool_version`) is graded on D by `menu_score` instead of the per-target
optimizer pick. Everything else in `pool_exam.measure_pool` (gates, A, C) is unchanged; a version without the block
never reaches this module.

Transport is today's pool transport: every (pool design x duty) of every registered task is a plain ``pool_design``
bank row, inputs only, deduplicated and in the bank's canonical content order (`pool_version.rows_from_material`), so
no row names its task, stratum or the optimum. The model answers every bank row once; this module reads those answers
from the same one table, merges the duties per design, and scores each task's epoch menu AFTER the predictions (the
model cannot know which rows count).

Custody material (private definition): ``definition["pool"]["menu"] = {"tasks": [{"problem", "duties", "record"}]}``.
The draw key is ``crown_d.derive_key(K_crown, "d-menu-sample")``, installed on the validator host at receiver start
(`install_key`, called by `crown_average_host.install`) or by a custody build script; it is never in the bank, the
configuration or a record. The epoch is the version's registered epoch id (E1): every grade of the version draws the
same menu, so a king and a challenger are always scored on the same draw.

Fail closed: anything wrong with Carbon's material, registration or key raises `pool_exam.ExamRefused` with a closed
snake_case code (Carbon's gap, never a candidate failure and never D = 0).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from carbon.scoring import menu_score
from carbon.scoring.pool_grader import Limit
from carbon.scoring.pool_solver_reference import Problem

#: Material key under ``definition["pool"]``.
MENU_KEY = "menu"
#: The registered aggregations of D_task into the version's D.
AGGREGATES = ("mean",)
#: The purpose label of the menu draw key (`crown_d.derive_key`; Validator 7 Nov 08:18).
KEY_LABEL = "d-menu-sample"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_PREFIX = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_PROBLEM_KEYS = {"target_id", "outputs", "objective", "sense", "limits", "u", "box"}

#: The validator host's menu draw key (bytes) or None: set only by `install_key` (receiver start / custody build).
_ACTIVE_KEY = None


def _refuse(code):
    from carbon.scoring import pool_exam

    raise pool_exam.ExamRefused(code)


def _require(condition, code):
    if not condition:
        _refuse(code)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class MenuRule:
    """A version's registered menu block (all owner / Validator values; `pool_version._menu` parses it)."""

    records_sha256: tuple  # sorted ((task_id, sha256), ...)
    epoch: str
    aggregate: str


def check_rule(rule):
    _require(isinstance(rule, MenuRule), "menu_rule_required")
    _require(
        type(rule.records_sha256) is tuple
        and rule.records_sha256
        and all(
            type(t) is str
            and _ID.fullmatch(t)
            and type(s) is str
            and _SHA256.fullmatch(s)
            for t, s in rule.records_sha256
        )
        and len({t for t, _ in rule.records_sha256}) == len(rule.records_sha256)
        and list(rule.records_sha256) == sorted(rule.records_sha256),
        "menu_records_sha256_invalid",
    )
    _require(
        type(rule.epoch) is str and _ID.fullmatch(rule.epoch), "menu_epoch_invalid"
    )
    _require(rule.aggregate in AGGREGATES, "menu_aggregate_unregistered")
    return rule


def install_key(k_crown):
    """Install the menu draw key from the validator host's K_crown (receiver start, or a custody build script).
    ``None`` turns it off. The key is held in this process only, never written."""
    global _ACTIVE_KEY
    if k_crown is None:
        _ACTIVE_KEY = None
        return
    from carbon.scoring import crown_d

    try:
        _ACTIVE_KEY = crown_d.derive_key(k_crown, KEY_LABEL)
    except crown_d.CrownDRefused:
        _refuse("menu_draw_key_invalid")


def active_key():
    """The installed menu draw key, or `ExamRefused("menu_draw_unavailable")` (Carbon's gap)."""
    _require(
        type(_ACTIVE_KEY) is bytes and len(_ACTIVE_KEY) >= 32, "menu_draw_unavailable"
    )
    return _ACTIVE_KEY


@dataclass(frozen=True)
class MenuTask:
    problem: Problem
    duties: tuple  # ((prefix, fixed dict), ...)
    record: menu_score.MenuRecord


def _problem(document):
    _require(
        type(document) is dict and set(document) == _PROBLEM_KEYS,
        "menu_problem_malformed",
    )
    outputs = document["outputs"]
    _require(
        type(outputs) is list
        and outputs
        and all(type(o) is str and o for o in outputs)
        and len(set(outputs)) == len(outputs),
        "menu_problem_outputs_invalid",
    )
    limits = document["limits"]
    _require(type(limits) is list, "menu_problem_limits_invalid")
    parsed = []
    for limit in limits:
        _require(
            type(limit) is dict
            and set(limit) == {"output", "kind", "bound"}
            and type(limit["output"]) is str
            and type(limit["kind"]) is str
            and _finite(limit["bound"]),
            "menu_problem_limits_invalid",
        )
        parsed.append(Limit(limit["output"], limit["kind"], float(limit["bound"])))
    box = document["box"]
    _require(
        type(box) is list
        and box
        and all(
            type(b) is list and len(b) == 2 and all(_finite(x) for x in b) for b in box
        ),
        "menu_problem_box_invalid",
    )
    _require(type(document["u"]) is dict, "menu_problem_u_invalid")
    # start and seed are the optimizer's and unused by menu scoring: fixed, never a science value.
    problem = Problem(
        target_id=document["target_id"],
        fixed={},
        outputs=tuple(outputs),
        objective=document["objective"],
        sense=document["sense"],
        limits=tuple(parsed),
        u=dict(document["u"]),
        box=tuple((float(lo), float(hi)) for lo, hi in box),
        start=tuple(0.5 for _ in box),
        seed=0,
    )
    try:
        menu_score._check_problem(problem)
    except menu_score.MenuRefused as exc:
        _refuse("menu_problem_" + exc.code)
    return problem


def _duties(value, input_names, design_names, problem):
    _require(type(value) is list and value, "menu_duties_malformed")
    duties = []
    for duty in value:
        _require(
            type(duty) is list
            and len(duty) == 2
            and type(duty[0]) is str
            and type(duty[1]) is dict,
            "menu_duties_malformed",
        )
        prefix, fixed = duty
        _require(
            prefix == "" if len(value) == 1 else bool(_PREFIX.fullmatch(prefix)),
            "menu_duty_prefix_invalid",
        )
        _require(
            all(type(k) is str and _finite(v) for k, v in fixed.items())
            and not set(fixed) & set(design_names)
            and set(fixed) | set(design_names) == set(input_names),
            "menu_duty_inputs_do_not_complete_the_model_row",
        )
        duties.append((prefix, {k: float(v) for k, v in fixed.items()}))
    _require(len({p for p, _ in duties}) == len(duties), "menu_duty_prefix_invalid")
    if len(duties) > 1:
        prefixes = {p for p, _ in duties}
        _require(
            all("/" in o and o.split("/", 1)[0] in prefixes for o in problem.outputs),
            "menu_problem_outputs_not_per_duty",
        )
    return tuple(duties)


def load_tasks(material, rule, *, input_names, design_names):
    """The version's menu tasks from its sealed material, checked against the registered rule (every registered task,
    no other, each record's sha equal to the registration's)."""
    check_rule(rule)
    _require(
        type(material) is dict and set(material) == {"tasks"}, "menu_material_malformed"
    )
    _require(
        type(material["tasks"]) is list and material["tasks"], "menu_material_malformed"
    )
    registered = dict(rule.records_sha256)
    tasks, seen = [], set()
    for entry in material["tasks"]:
        _require(
            type(entry) is dict and set(entry) == {"problem", "duties", "record"},
            "menu_task_malformed",
        )
        problem = _problem(entry["problem"])
        _require(problem.target_id not in seen, "menu_task_duplicate")
        seen.add(problem.target_id)
        _require(problem.target_id in registered, "menu_task_not_registered")
        _require(
            len(problem.box) == len(design_names),
            "menu_problem_box_does_not_match_design_names",
        )
        duties = _duties(entry["duties"], input_names, design_names, problem)
        try:
            record = menu_score.menu_record(entry["record"], problem)
        except menu_score.MenuRefused as exc:
            _refuse(exc.code)
        _require(
            record.sha256 == registered[problem.target_id],
            "menu_record_sha256_not_registered",
        )
        tasks.append(MenuTask(problem=problem, duties=duties, record=record))
    _require(seen == set(registered), "menu_registered_task_missing")
    return tuple(sorted(tasks, key=lambda t: t.problem.target_id))


def task_rows(task, design_names):
    """Every (pool design x duty) of one task as a model input dict, in the record's id order, with its (id, prefix)."""
    rows, index = [], []
    for pid in sorted(task.record.pool):
        design = dict(zip(design_names, task.record.pool[pid]["design"], strict=True))
        for prefix, fixed in task.duties:
            rows.append({**fixed, **design})
            index.append((pid, prefix))
    return rows, index


def bank_rows(tasks, design_names):
    """Every menu row of every task (model input dicts; the caller quantises and dedups with the pool rows)."""
    return [row for task in tasks for row in task_rows(task, design_names)[0]]


def score(tasks, rule, predict_rows, *, key, design_names):
    """The version's menu D. ``predict_rows(rows) -> [derived outputs dict | None]`` reads the model's one table.

    Returns ``{"D", "record"}``: ``D`` the registered aggregate of the tasks' D_task; ``record`` the custody record
    (epoch, per task: record sha, state, d, menu size, and the model's FULL-POOL merged predictions so a king can be
    re-scored on a later draw without inference). It never holds the drawn ids.
    """
    check_rule(rule)
    results, predictions = [], {}
    for task in tasks:
        rows, index = task_rows(task, design_names)
        derived = predict_rows(rows)
        _require(
            type(derived) is list and len(derived) == len(rows),
            "menu_prediction_count_mismatch",
        )
        merged = menu_score.merge_duties(index, derived, task.duties)
        names = set(task.problem.outputs)
        for outputs in merged.values():
            # A derived dict that lacks a task output is Carbon's wiring (the Challenge's derive vs the task's names).
            _require(
                outputs is None or names <= set(outputs),
                "menu_derived_outputs_do_not_cover_the_task",
            )
        try:
            result = menu_score.score_task(
                task.problem, task.record, merged, key=key, epoch=rule.epoch
            )
        except menu_score.MenuRefused as exc:
            _refuse(exc.code)
        results.append(
            {
                "task_id": task.problem.target_id,
                "record_sha256": task.record.sha256,
                "state": result["state"],
                "d": result["d"],
                "menu_size": result["menu_size"],
            }
        )
        predictions[task.problem.target_id] = {
            pid: (None if out is None else {k: out[k] for k in sorted(names)})
            for pid, out in sorted(merged.items())
        }
    d = math.fsum(r["d"] for r in results) / len(results)
    return {
        "D": d,
        "record": {
            "schema": "carbon.menu-grade.v1",
            "metric": menu_score.METRIC,
            "epoch": rule.epoch,
            "aggregate": rule.aggregate,
            "tasks": results,
            "predictions": predictions,
        },
    }
