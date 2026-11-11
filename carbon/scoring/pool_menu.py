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

A version may register ``tasks_per_epoch`` k (the owner's number; Carbon Validator-Motor 10 Nov ruling (i)): each
epoch then scores ONE secret draw of k of its registered tasks (`draw_tasks`: the k lowest HMAC ranks under the same
menu key, domain ``task-draw``, bound to the epoch id and the version's whole task registration), the same k for every
grade of the epoch, and D is the mean over those k. The model still answers every task's rows (the bank never shows
which tasks count) and the custody record keeps every task's full-pool predictions, so a later epoch re-scores on its
own draw without inference. Absent (None), every registered task is scored, exactly as before.

Fail closed: anything wrong with Carbon's material, registration or key raises `pool_exam.ExamRefused` with a closed
snake_case code (Carbon's gap, never a candidate failure and never D = 0).
"""

from __future__ import annotations

import contextlib
import contextvars
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
#: The purpose label of the row-independence re-check's subset and order (Carbon Validator-B, 7 Nov).
ROWCHECK_LABEL = "d-menu-rowcheck"
#: Carbon Validator-B 7 Nov (4): crown_d's minimum binds menu D (an owner exception names its decision id).
MIN_TASKS = 3
#: The state of a model whose re-check answers differ from its graded answers (Carbon Validator-B 7 Nov (1)): D = 0.
MODEL_ROW_DEPENDENT = menu_score.MODEL_ROW_DEPENDENT

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_PREFIX = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_PROBLEM_KEYS = {"target_id", "outputs", "objective", "sense", "limits", "u", "box"}

#: The validator host's menu draw key (bytes) or None: set only by `install_key` (receiver start / custody build).
_ACTIVE_KEY = None
#: The row-independence re-check key (bytes) or None: set with the draw key by `install_key`.
_ROWCHECK_KEY = None


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
    epoch: str  # E1: one registered epoch id per version (Carbon Validator-B 7 Nov (3))
    aggregate: str
    rotation_days: int  # the owner's rotation cadence, inside the same sealed pool
    rowcheck: tuple  # (rel_tol, abs_tol, subset): the re-check's tolerance and size (the Validator's values)
    min_tasks_exception: str | None = (
        None  # an owner decision id allowing fewer than MIN_TASKS tasks
    )
    tasks_per_epoch: int | None = (
        None  # k of the registered tasks scored per epoch (the owner's number); None = every task
    )


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
    _require(
        type(rule.rotation_days) is int and rule.rotation_days > 0,
        "menu_rotation_days_invalid",
    )
    _require(
        type(rule.rowcheck) is tuple
        and len(rule.rowcheck) == 3
        and all(_finite(t) and t >= 0 for t in rule.rowcheck[:2])
        and type(rule.rowcheck[2]) is int
        and rule.rowcheck[2] > 0,
        "menu_rowcheck_invalid",
    )
    _require(
        rule.min_tasks_exception is None
        or (
            type(rule.min_tasks_exception) is str
            and _ID.fullmatch(rule.min_tasks_exception)
        ),
        "menu_min_tasks_exception_invalid",
    )
    _require(
        len(rule.records_sha256) >= MIN_TASKS or rule.min_tasks_exception is not None,
        "menu_tasks_below_minimum",
    )
    _require(
        rule.tasks_per_epoch is None
        or (
            type(rule.tasks_per_epoch) is int
            and MIN_TASKS <= rule.tasks_per_epoch <= len(rule.records_sha256)
        ),
        "menu_tasks_per_epoch_invalid",
    )
    return rule


#: The HMAC domain of the per-epoch task draw (under the menu draw key; distinct from `menu_score`'s ``draw``).
TASK_DRAW_DOMAIN = "task-draw"


def draw_tasks(rule, key, *, epoch):
    """The epoch's scored task ids, sorted: every registered task when ``rule.tasks_per_epoch`` is None, else the k
    with the lowest HMAC(key, [``task-draw``, epoch, the version's whole task registration, task id]) ranks. The same
    (key, epoch, registration) always gives the same set. Custody only: never in a public record.
    """
    import hashlib
    import hmac
    import json

    check_rule(rule)
    _require(type(key) is bytes and len(key) >= 32, "menu_draw_key_invalid")
    _require(type(epoch) is str and _ID.fullmatch(epoch), "menu_epoch_invalid")
    ids = [task_id for task_id, _sha in rule.records_sha256]
    if rule.tasks_per_epoch is None:
        return tuple(ids)
    registration = [list(pair) for pair in rule.records_sha256]

    def rank(task_id):
        message = json.dumps(
            [TASK_DRAW_DOMAIN, epoch, registration, task_id],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hmac.new(key, message, hashlib.sha256).digest()

    chosen = sorted(ids, key=lambda t: (rank(t), t))[: rule.tasks_per_epoch]
    return tuple(sorted(chosen))


def install_key(k_crown):
    """Install the menu draw key from the validator host's K_crown (receiver start, or a custody build script).
    ``None`` turns it off. The key is held in this process only, never written."""
    global _ACTIVE_KEY, _ROWCHECK_KEY
    if k_crown is None:
        _ACTIVE_KEY = _ROWCHECK_KEY = None
        return
    from carbon.scoring import crown_d

    try:
        _ACTIVE_KEY = crown_d.derive_key(k_crown, KEY_LABEL)
        _ROWCHECK_KEY = crown_d.derive_key(k_crown, ROWCHECK_LABEL)
    except crown_d.CrownDRefused:
        _ACTIVE_KEY = _ROWCHECK_KEY = None
        _refuse("menu_draw_key_invalid")


def active_key():
    """The installed menu draw key, or `ExamRefused("menu_draw_unavailable")` (Carbon's gap)."""
    _require(
        type(_ACTIVE_KEY) is bytes and len(_ACTIVE_KEY) >= 32, "menu_draw_unavailable"
    )
    return _ACTIVE_KEY


def rowcheck_key():
    """The installed re-check key, or `ExamRefused("menu_rowcheck_unavailable")` (Carbon's gap)."""
    _require(
        type(_ROWCHECK_KEY) is bytes and len(_ROWCHECK_KEY) >= 32,
        "menu_rowcheck_unavailable",
    )
    return _ROWCHECK_KEY


def rowcheck_plan(row_count, subset, key, *, epoch):
    """The re-check's bank positions IN QUERY ORDER: a keyed subset of ``subset`` positions of the graded query's
    ``row_count`` rows, in a keyed permuted order (HMAC(key, purpose | epoch | position)); a fresh model instance
    answers them in this order (Carbon Validator-B 7 Nov (1)). Custody only: never in a public record.
    """
    import hashlib
    import hmac

    _require(type(key) is bytes and len(key) >= 32, "menu_rowcheck_unavailable")
    _require(type(epoch) is str and _ID.fullmatch(epoch), "menu_epoch_invalid")
    _require(
        type(row_count) is int and type(subset) is int and 0 < subset <= row_count,
        "menu_rowcheck_subset_above_the_bank",
    )

    def rank(position, purpose):
        message = b"\x00".join([purpose, epoch.encode(), str(position).encode()])
        return hmac.new(key, message, hashlib.sha256).digest()

    chosen = sorted(range(row_count), key=lambda i: rank(i, b"subset"))[:subset]
    return sorted(chosen, key=lambda i: rank(i, b"order"))


ROWCHECK_SCHEMA = "carbon.menu-rowcheck.v1"

# --- custody: design-optimum's menus -> the door's sealed material (G1/G2, Graphite-B 7 Nov) -------------------------

#: design-optimum's per-task problem file (written beside each carbon.d-menu.v1 record by its menu stage): its own
#: naming, ``<output>@<duty>`` (custody_solve.MultiDuty), with the duties' fixed conditions.
DO_PROBLEM_KEYS = {
    "target_id",
    "outputs",
    "objective",
    "sense",
    "limits",
    "u",
    "box",
    "duties",
}


def _door_name(name, duties):
    """``<output>@<duty>`` -> the door's ``<duty>/<output>`` (`menu_score.merge_duties`); a one-duty task keeps the
    bare output name. Anything else refuses (never guessed)."""
    _require(
        type(name) is str and name.count("@") == 1,
        "menu_custody_name_not_output_at_duty",
    )
    output, duty = name.split("@")
    _require(output and duty in duties, "menu_custody_name_not_output_at_duty")
    return output if len(duties) == 1 else f"{duty}/{output}"


def _rename(mapping, duties):
    return {_door_name(k, duties): v for k, v in mapping.items()}


def door_task(problem_doc, record_doc):
    """One sealed menu task in the door's form (``{"problem", "duties", "record"}``, `load_tasks`) from design-optimum's
    problem file and record. Only NAMES change: every ``<output>@<duty>`` becomes the door's name, in the problem
    (outputs, objective, limits, u) and in the record (every truth, every arm prediction); values, ids, strata, quotas,
    designs and the reference values are copied as they are. The door's record sha is the sha of the RENAMED record,
    the one the door reads, so it is the sha to register."""
    _require(
        type(problem_doc) is dict and set(problem_doc) == DO_PROBLEM_KEYS,
        "menu_custody_problem_malformed",
    )
    duties = problem_doc["duties"]
    _require(
        type(duties) is dict
        and duties
        and all(type(v) is dict for v in duties.values()),
        "menu_custody_duties_malformed",
    )
    _require(
        type(problem_doc["limits"]) is list
        and all(type(l) is list and len(l) == 3 for l in problem_doc["limits"]),
        "menu_custody_problem_malformed",
    )
    problem = {
        "target_id": problem_doc["target_id"],
        "outputs": [_door_name(o, duties) for o in problem_doc["outputs"]],
        "objective": _door_name(problem_doc["objective"], duties),
        "sense": problem_doc["sense"],
        "limits": [
            {"output": _door_name(o, duties), "kind": k, "bound": b}
            for o, k, b in problem_doc["limits"]
        ],
        "u": _rename(problem_doc["u"], duties),
        "box": problem_doc["box"],
    }
    _require(
        type(record_doc) is dict and type(record_doc.get("pool")) is list,
        "menu_custody_record_malformed",
    )
    record = {
        **record_doc,
        "pool": [
            {**row, "truth": _rename(row["truth"], duties)}
            for row in record_doc["pool"]
        ],
        "arms": {
            arm: {
                pid: (None if out is None else _rename(out, duties))
                for pid, out in preds.items()
            }
            for arm, preds in record_doc["arms"].items()
        },
    }
    door_duties = (
        [["", dict(next(iter(duties.values())))]]
        if len(duties) == 1
        else [[name, dict(fixed)] for name, fixed in sorted(duties.items())]
    )
    return {"problem": problem, "duties": door_duties, "record": record}


def menu_material(pairs, *, input_names, design_names):
    """``(material, {task_id: record sha})``: the sealed ``definition["pool"]["menu"]`` of design-optimum's
    ``[(problem_doc, record_doc), ...]``, checked through the door's own `load_tasks` against the shas it computes (so
    a material that would refuse at grade time refuses here, at build). The shas are the ones to register.
    """
    tasks = [door_task(problem, record) for problem, record in pairs]
    material = {"tasks": tasks}
    shas = {}
    for task in tasks:
        problem = _problem(task["problem"])
        try:
            shas[problem.target_id] = menu_score.menu_record(
                task["record"], problem
            ).sha256
        except menu_score.MenuRefused as exc:
            _refuse(exc.code)
    probe = MenuRule(
        records_sha256=tuple(sorted(shas.items())),
        epoch="custody-build-check",
        aggregate="mean",
        rotation_days=1,
        rowcheck=(0.0, 0.0, 1),
        min_tasks_exception="custody-build-check",  # the count is checked against the REGISTRATION at grade time
    )
    load_tasks(material, probe, input_names=input_names, design_names=design_names)
    return material, shas


#: The re-check staged for the grade being produced in THIS context (`staged_rowcheck`): set by the receiver around its
#: producer call, never through a producer file (Validator-2B 7 Nov must-fix 1: producer bytes never move).
_STAGED = contextvars.ContextVar("carbon_menu_rowcheck", default=None)


@contextlib.contextmanager
def staged_rowcheck(source):
    """Stage the re-check for the measure called inside this block: the receiver's side-file bytes, or (a custody
    pack build only) ``source(positions) -> raw answers`` for Carbon's own in-pack baseline. Cleared on exit.
    """
    _require(
        source is None or type(source) is bytes or callable(source),
        "menu_rowcheck_side_file_invalid",
    )
    token = _STAGED.set(source)
    try:
        yield
    finally:
        _STAGED.reset(token)


def take_rowcheck(bank_rows, rule, key, *, names=None):
    """``{"positions", "outputs"}`` of the staged re-check for the measure's ``bank_rows``, or None when nothing is
    staged (the measure then refuses ``menu_rowcheck_unavailable``, Carbon's gap). A staged callable (custody pack
    builds only, for Carbon's own in-pack baseline) is called as ``source(positions, bank_rows, names)`` and returns a
    FRESH run's raw answers to those rows in that order."""
    source = _STAGED.get()
    if source is None:
        return None
    if type(source) is bytes:
        return read_rowcheck_side_file(source)
    positions = rowcheck_plan(len(bank_rows), rule.rowcheck[2], key, epoch=rule.epoch)
    outputs = source(list(positions), bank_rows, names)
    _require(
        type(outputs) is list and len(outputs) == len(positions),
        "menu_rowcheck_count_mismatch",
    )
    return {"positions": positions, "outputs": [list(row) for row in outputs]}


def rowcheck_side_file(positions, outputs):
    """The receiver's host-private re-check side file: the planned positions and the fresh instance's raw answers in
    that order (custody only; never copied into a receipt or a public record)."""
    _require(
        type(positions) is list
        and all(type(i) is int and i >= 0 for i in positions)
        and type(outputs) is list
        and len(outputs) == len(positions),
        "menu_rowcheck_side_file_invalid",
    )
    body = {
        "schema": ROWCHECK_SCHEMA,
        "positions": positions,
        "outputs": [[float(v) for v in row] for row in outputs],
    }
    import json

    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def read_rowcheck_side_file(raw):
    """``{"positions", "outputs"}`` of a re-check side file, or `ExamRefused` (Carbon's gap)."""
    import json

    try:
        body = json.loads(raw)
    except (TypeError, ValueError, UnicodeError):
        _refuse("menu_rowcheck_side_file_invalid")
    _require(
        type(body) is dict
        and set(body) == {"schema", "positions", "outputs"}
        and body["schema"] == ROWCHECK_SCHEMA
        and type(body["positions"]) is list
        and all(type(i) is int and i >= 0 for i in body["positions"])
        and type(body["outputs"]) is list
        and len(body["outputs"]) == len(body["positions"])
        and all(
            type(row) is list and all(type(v) in (int, float) for v in row)
            for row in body["outputs"]
        ),
        "menu_rowcheck_side_file_invalid",
    )
    return {"positions": body["positions"], "outputs": body["outputs"]}


def rowcheck_differs(graded, recheck, positions, rule):
    """True when any re-check answer differs from the graded answer at the same bank position beyond the registered
    tolerance (|a - b| > abs_tol + rel_tol |a|, or a non-finite value on one side only). ``graded``: the graded raw
    answers by bank position; ``recheck``: the fresh instance's raw answers in ``positions`` order.
    """
    check_rule(rule)
    rel_tol, abs_tol, _subset = rule.rowcheck
    _require(
        type(recheck) is list and len(recheck) == len(positions),
        "menu_rowcheck_count_mismatch",
    )
    for position, again in zip(positions, recheck, strict=True):
        first = graded[position]
        _require(
            type(again) in (list, tuple) and len(again) == len(first),
            "menu_rowcheck_shape_mismatch",
        )
        for a, b in zip(first, again, strict=True):
            fa, fb = _finite(a), _finite(b)
            if fa != fb:
                return True
            if fa and abs(a - b) > abs_tol + rel_tol * abs(a):
                return True
    return False


def rescore(tasks, rule, predictions, *, key, epochs):
    """The menu D re-scored from STORED full-pool predictions (a custody record's ``predictions``) on each of
    ``epochs`` (keyed draw ids), with no inference: the mean over the epochs of the registered aggregate (Carbon
    Validator-B 7 Nov (2): a close crown change is re-scored for both on 2 more keyed draws, mean of 3).
    """
    check_rule(rule)
    _require(
        type(epochs) in (list, tuple)
        and epochs
        and all(type(e) is str and _ID.fullmatch(e) for e in epochs),
        "menu_epoch_invalid",
    )
    _require(type(predictions) is dict, "menu_stored_predictions_incomplete")
    per_epoch = []
    for task in tasks:
        stored = predictions.get(task.problem.target_id)
        _require(
            type(stored) is dict and set(stored) == set(task.record.pool),
            "menu_stored_predictions_incomplete",
        )
    for epoch in epochs:
        ds = []
        drawn = set(draw_tasks(rule, key, epoch=epoch))
        for task in tasks:
            if task.problem.target_id not in drawn:
                continue  # each epoch scores its own draw (never mixed across epochs)
            stored = predictions[task.problem.target_id]
            try:
                ds.append(
                    menu_score.score_task(
                        task.problem, task.record, stored, key=key, epoch=epoch
                    )["d"]
                )
            except menu_score.MenuRefused as exc:
                _refuse(exc.code)
        per_epoch.append(math.fsum(ds) / len(ds))
    return math.fsum(per_epoch) / len(per_epoch)


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


def score(tasks, rule, predict_rows, *, key, design_names, row_dependent=False):
    """The version's menu D. ``predict_rows(rows) -> [derived outputs dict | None]`` reads the model's one table.

    Returns ``{"D", "record"}``: ``D`` the registered aggregate of the tasks' D_task; ``record`` the custody record
    (epoch, per task: record sha, state, d, menu size, and the model's FULL-POOL merged predictions so a king can be
    re-scored on a later draw without inference). It never holds the drawn ids.
    """
    check_rule(rule)
    results, predictions = [], {}
    drawn = set(draw_tasks(rule, key, epoch=rule.epoch))
    # a registered k is logged in the custody record; with none the record is exactly as before
    drawn_note = (
        {}
        if rule.tasks_per_epoch is None
        else {"tasks_per_epoch": rule.tasks_per_epoch}
    )
    if row_dependent:
        # Carbon Validator-B 7 Nov (1): the fresh re-check answered differently, so the model's ranking is not a
        # function of each design alone. D = 0 for this grade, typed (the candidate's finding).
        return {
            "D": 0.0,
            "record": {
                "schema": "carbon.menu-grade.v1",
                "metric": menu_score.METRIC,
                "epoch": rule.epoch,
                "aggregate": rule.aggregate,
                **drawn_note,
                "state": MODEL_ROW_DEPENDENT,
                "tasks": [
                    {
                        "task_id": t.problem.target_id,
                        "record_sha256": t.record.sha256,
                        "state": MODEL_ROW_DEPENDENT,
                        "d": 0.0,
                    }
                    for t in tasks
                    if t.problem.target_id in drawn
                ],
                "predictions": {},
            },
        }
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
        predictions[task.problem.target_id] = {
            pid: (None if out is None else {k: out[k] for k in sorted(names)})
            for pid, out in sorted(merged.items())
        }
        if task.problem.target_id not in drawn:
            continue  # answered and kept (a later epoch may draw it), not scored this epoch
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
    d = math.fsum(r["d"] for r in results) / len(results)
    return {
        "D": d,
        "record": {
            "schema": "carbon.menu-grade.v1",
            "metric": menu_score.METRIC,
            "epoch": rule.epoch,
            "aggregate": rule.aggregate,
            **drawn_note,
            "tasks": results,
            "predictions": predictions,
        },
    }
