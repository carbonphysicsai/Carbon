"""D menu v1: design value graded with no runtime solve (spec D_MENU_SPEC_V1_20261107 §2-3, design-optimum = menu lead;
owner 7 Nov 13:45Z). Pure logic, custody only.

Per task, design-optimum seals a solved POOL (~1.5 M designs: the searched optimum, a band on both sides of the active
limit, regime-switch strata, other basins, a spread), each design's TRUTH, and the classical arms' predictions of every
pool design. Each epoch a custody key draws the epoch's menu (the optimum always, plus a registered quota per stratum).
The contender's model predicts every menu design ROW-INDEPENDENTLY (`RowIndependentPredict`), the designs are ranked by
those predictions on the limits backed off by U (Q1), with the driver's `_key` (model-feasible first by the objective,
then the least predicted violation, invalid predictions last), and the top five picks are looked up in the truths:

    d(pick)  = 0 if the pick is truly infeasible (a true margin < 0), else clip((s - s_zero) / (s_ref - s_zero), 0, 1)
    raw      = sum_i w_i d(pick_i), w = (0.4, 0.25, 0.15, 0.12, 0.08)
    Z        = max(each classical arm's raw on the same menu, the random-pick expectation = mean d over the menu)
    D_task   = clip((raw - Z) / (1 - Z), 0, 1)

s = +objective for sense "max", -objective for "min" (larger is better). s_ref = the searched optimum's truth (the
menu's 1); s_zero = the record's objective zero. Ties in the ranking (equal `_key`) are scored at the MEAN d of the
tied designs over the slots they share: exactly the expectation of a uniformly random tie-break, with no draw, so a
constant predictor's raw equals the random expectation and its D_task is 0.

Fail closed: a malformed record or rule raises `MenuRefused` with a closed snake_case code (Carbon's material, never the
candidate's). A model whose predictions change with the batch it is shown raises `ModelRowDependent` (a finding about
the candidate's model; the caller decides its consequence). Nothing here returns a design, a truth or a menu id to a
miner surface: `score_task` returns numbers and counts only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import random
import re
from dataclasses import dataclass, replace

from carbon.scoring.pool_grader import Limit, u_value
from carbon.scoring.pool_solver_reference import (
    DERIVE_REFUSED,
    OK,
    SolvedPoint,
    _check_problem,
    _key,
    _margins,
)

MENU_SCHEMA = "carbon.d-menu.v1"
METRIC = "menu_top5_v1"
WEIGHTS = (0.4, 0.25, 0.15, 0.12, 0.08)
TOP = len(WEIGHTS)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


class MenuRefused(ValueError):
    """A menu record, draw or rule cannot give a sound score: Carbon's material, never a candidate's."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class ModelRowDependent(Exception):
    """The candidate's model gave a row a different prediction depending on the other rows it was shown."""

    code = "menu_predict_not_row_independent"


def _require(condition, code):
    if not condition:
        raise MenuRefused(code)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _signed(problem, outputs):
    value = float(outputs[problem.objective])
    return value if problem.sense == "max" else -value


# --- the sealed record -----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MenuRecord:
    task_id: str
    s_ref: float
    s_zero: float
    optimum: str
    quotas: tuple  # sorted ((stratum, count), ...)
    pool: dict  # id -> {"stratum", "design", "truth"}
    arms: dict  # arm -> {id: outputs | None}
    sha256: str

    @property
    def size(self):
        return 1 + sum(count for _, count in self.quotas)


def menu_record(document, problem):
    """Parse and check one task's sealed menu record against the task's grading `problem` (custody material).

    Refuses: unknown schema, a duplicate / malformed id, a design outside the box, a truth or an arm prediction missing
    an output or not finite, s_ref <= s_zero, the optimum's truth not s_ref, any feasible truth beating s_ref by more
    than U (a search failure: re-search, never raise the 1), a quota above its stratum's supply, a menu under 5.
    """
    _check_problem(problem)
    keys = {"schema", "task_id", "s_ref", "s_zero", "optimum", "quotas", "pool", "arms"}
    _require(type(document) is dict and set(document) == keys, "menu_record_malformed")
    _require(document["schema"] == MENU_SCHEMA, "menu_schema_unknown")
    _require(document["task_id"] == problem.target_id, "menu_task_id_mismatch")
    s_ref, s_zero = document["s_ref"], document["s_zero"]
    _require(_finite(s_ref) and _finite(s_zero), "menu_reference_values_not_finite")
    _require(s_ref > s_zero, "menu_s_ref_not_above_s_zero")
    names = set(problem.outputs)
    pool = {}
    _require(type(document["pool"]) is list and document["pool"], "menu_pool_malformed")
    for row in document["pool"]:
        _require(
            type(row) is dict and set(row) == {"id", "stratum", "design", "truth"},
            "menu_pool_malformed",
        )
        pid = row["id"]
        _require(
            type(pid) is str and _ID.fullmatch(pid) and pid not in pool,
            "menu_pool_id_invalid",
        )
        _require(
            type(row["stratum"]) is str and _ID.fullmatch(row["stratum"]),
            "menu_stratum_invalid",
        )
        design = row["design"]
        _require(
            type(design) is list
            and len(design) == len(problem.box)
            and all(_finite(x) for x in design)
            and all(lo <= x <= hi for x, (lo, hi) in zip(design, problem.box)),
            "menu_design_invalid",
        )
        _require(_outputs_ok(row["truth"], names), "menu_truth_invalid")
        pool[pid] = {
            "stratum": row["stratum"],
            "design": tuple(float(x) for x in design),
            "truth": dict(row["truth"]),
        }
    optimum = document["optimum"]
    _require(optimum in pool, "menu_optimum_not_in_pool")
    opt_truth = pool[optimum]["truth"]
    _require(
        all(m >= 0.0 for m in _margins(problem, opt_truth).values())
        and _signed(problem, opt_truth) == float(s_ref),
        "menu_optimum_truth_is_not_s_ref",
    )
    u_obj = u_value(problem.u[problem.objective], s_ref)
    for entry in pool.values():
        truth = entry["truth"]
        if all(m >= 0.0 for m in _margins(problem, truth).values()):
            _require(
                _signed(problem, truth) <= s_ref + u_obj,
                "menu_design_beats_s_ref_search_failure",
            )
    quotas = document["quotas"]
    _require(type(quotas) is dict and quotas, "menu_quotas_malformed")
    for stratum, count in quotas.items():
        supply = sum(
            1 for pid, e in pool.items() if e["stratum"] == stratum and pid != optimum
        )
        _require(type(count) is int and count >= 0, "menu_quota_invalid")
        _require(count <= supply, "menu_quota_above_stratum_supply")
    _require(1 + sum(quotas.values()) >= TOP, "menu_smaller_than_top_five")
    arms = document["arms"]
    _require(type(arms) is dict, "menu_arms_malformed")
    for arm, preds in arms.items():
        _require(
            type(arm) is str
            and _ID.fullmatch(arm)
            and type(preds) is dict
            and set(preds) == set(pool),
            "menu_arm_must_predict_every_pool_design",
        )
        for value in preds.values():
            _require(value is None or _outputs_ok(value, names), "menu_arm_invalid")
    try:
        sha = hashlib.sha256(_canonical(document)).hexdigest()
    except (TypeError, ValueError):
        raise MenuRefused("menu_record_malformed") from None
    return MenuRecord(
        task_id=document["task_id"],
        s_ref=float(s_ref),
        s_zero=float(s_zero),
        optimum=optimum,
        quotas=tuple(sorted(quotas.items())),
        pool=pool,
        arms={arm: dict(preds) for arm, preds in arms.items()},
        sha256=sha,
    )


def _outputs_ok(outputs, names):
    return (
        type(outputs) is dict
        and names <= set(outputs)
        and all(_finite(outputs[n]) for n in names)
    )


# --- the epoch's menu ------------------------------------------------------------------------------------------------


def _hmac_rank(key, domain, record, epoch, pid):
    return hmac.new(
        key, _canonical([domain, record.task_id, record.sha256, epoch, pid]), "sha256"
    ).digest()


def draw_menu(record, key, *, epoch):
    """The epoch's menu ids: the optimum always, plus each stratum's quota of its lowest HMAC ranks (custody key,
    >= 32 bytes, the Validator's). Returned sorted; the order shown to a model is irrelevant (row-independent).
    """
    _require(isinstance(record, MenuRecord), "menu_record_required")
    _require(type(key) is bytes and len(key) >= 32, "menu_draw_key_invalid")
    _require(type(epoch) is str and epoch, "menu_epoch_invalid")
    chosen = [record.optimum]
    for stratum, count in record.quotas:
        ids = [
            pid
            for pid, e in record.pool.items()
            if e["stratum"] == stratum and pid != record.optimum
        ]
        ids.sort(key=lambda pid: (_hmac_rank(key, "draw", record, epoch, pid), pid))
        chosen += ids[:count]
    return tuple(sorted(chosen))


# --- ranking and scoring ---------------------------------------------------------------------------------------------


def backed_off(problem):
    """The task's limits moved inward by U at the bound (Q1): a pick must clear each limit by U on the model."""
    limits = []
    for limit in problem.limits:
        u = u_value(problem.u[limit.output], limit.bound)
        bound = limit.bound - u if limit.kind == "<=" else limit.bound + u
        limits.append(Limit(limit.output, limit.kind, bound))
    return replace(problem, limits=tuple(limits))


def _point(problem, outputs):
    if outputs is None:
        return SolvedPoint(
            design=(),
            phase="menu",
            status=DERIVE_REFUSED,
            outputs=None,
            margins=None,
            attempts=1,
        )
    return SolvedPoint(
        design=(),
        phase="menu",
        status=OK,
        outputs=outputs,
        margins=_margins(problem, outputs),
        attempts=1,
    )


def pick_d(problem, record, pid):
    """One pick's d from its sealed truth (original limits: a true margin < 0 scores 0)."""
    truth = record.pool[pid]["truth"]
    if any(m < 0.0 for m in _margins(problem, truth).values()):
        return 0.0
    share = (_signed(problem, truth) - record.s_zero) / (record.s_ref - record.s_zero)
    return min(1.0, max(0.0, share))


def raw_score(problem, record, menu, predictions):
    """sum_i w_i d(pick_i) over the top five of `menu` ranked by `predictions` ({id: outputs | None}) on the
    backed-off limits; tied keys share the mean d of their group over the slots they occupy.
    """
    _require(set(predictions) >= set(menu), "menu_predictions_missing_a_design")
    names = set(problem.outputs)
    ranked_problem = backed_off(problem)
    keyed = []
    for pid in menu:
        outputs = predictions[pid]
        if outputs is not None and not _outputs_ok(outputs, names):
            outputs = None  # a missing / non-finite prediction is the model's invalid prediction: ranks last
        keyed.append((_key(ranked_problem, _point(ranked_problem, outputs)), pid))
    keyed.sort(key=lambda item: item[0])
    total, slot, i = 0.0, 0, 0
    while slot < TOP:
        j = i
        while j < len(keyed) and keyed[j][0] == keyed[i][0]:
            j += 1
        group = [pick_d(problem, record, pid) for _, pid in keyed[i:j]]
        mean = math.fsum(group) / len(group)
        for _ in range(min(j - i, TOP - slot)):
            total += WEIGHTS[slot] * mean
            slot += 1
        i = j
    return total


def score_task(problem, record, predictions, *, key, epoch):
    """The contender's D for one task this epoch (see the module docstring). ``predictions``: {menu id: outputs |
    None} for every id of the epoch's menu. Returns numbers and counts only."""
    menu = draw_menu(record, key, epoch=epoch)
    raw = raw_score(problem, record, menu, predictions)
    random_zero = math.fsum(pick_d(problem, record, pid) for pid in menu) / len(menu)
    zero, source = random_zero, "random"
    for arm in sorted(record.arms):
        arm_raw = raw_score(problem, record, menu, record.arms[arm])
        if arm_raw > zero:
            zero, source = arm_raw, "classical_arm"
    _require(zero < 1.0, "menu_zero_at_one_task_has_no_room")
    return {
        "metric": METRIC,
        "d": min(1.0, max(0.0, (raw - zero) / (1.0 - zero))),
        "raw": raw,
        "zero": zero,
        "zero_source": source,
        "menu_size": len(menu),
    }


def menu_rows(record, menu, duties, input_names, design_names):
    """Model input rows for every (menu design, duty), in a fixed order: ``duties`` = ((prefix, fixed), ...); each
    row is ``input_names`` filled from the duty's fixed conditions and the design. Returns (rows, index) where index
    maps each row back to (id, prefix)."""
    rows, index = [], []
    for pid in menu:
        design = dict(zip(design_names, record.pool[pid]["design"]))
        for prefix, fixed in duties:
            values = {**fixed, **design}
            _require(set(input_names) <= set(values), "menu_row_inputs_incomplete")
            rows.append([float(values[n]) for n in input_names])
            index.append((pid, prefix))
    return rows, index


def merge_duties(index, predictions, duties):
    """{id: outputs | None} from per-row predictions (dicts of derived outputs, or None): one duty's outputs carry
    the name ``prefix/output`` (a single unnamed duty, prefix "", keeps the names); any invalid duty makes the
    design's prediction invalid."""
    _require(len(index) == len(predictions), "menu_prediction_count_mismatch")
    merged = {}
    for (pid, prefix), outputs in zip(index, predictions):
        current = merged.setdefault(pid, {})
        if current is None:
            continue
        if outputs is None or type(outputs) is not dict:
            merged[pid] = None
            continue
        for name, value in outputs.items():
            current[f"{prefix}/{name}" if prefix else name] = value
    _require(len(duties) >= 1, "menu_duties_required")
    return merged


# --- row independence ------------------------------------------------------------------------------------------------


class RowIndependentPredict:
    """Wrap a model's ``predict(rows)`` so a row's prediction can never depend on the other rows it is shown.

    ``batch_size`` 1: one row per call (independent by construction). ``batch_size`` > 1: rows go in a random order in
    small batches, then ``recheck`` randomly chosen rows are predicted again ALONE and in a reshuffled batch; any
    difference beyond ``abs_tol + rel_tol * |value|`` raises `ModelRowDependent`. ``seed`` is per epoch (custody), so
    the order and the re-checked rows are unknown in advance. Predictions are returned in the caller's order.
    """

    def __init__(self, predict, *, batch_size, recheck, seed, rel_tol, abs_tol):
        _require(callable(predict), "menu_predict_required")
        _require(type(batch_size) is int and batch_size >= 1, "menu_batch_size_invalid")
        _require(type(recheck) is int and recheck >= 0, "menu_recheck_invalid")
        _require(batch_size == 1 or recheck >= 1, "menu_batched_without_recheck")
        _require(type(seed) is int, "menu_seed_invalid")
        _require(
            _finite(rel_tol) and rel_tol >= 0 and _finite(abs_tol) and abs_tol >= 0,
            "menu_tolerance_invalid",
        )
        self._predict, self.batch_size, self.recheck = predict, batch_size, recheck
        self._rng = random.Random(seed)
        self.rel_tol, self.abs_tol = float(rel_tol), float(abs_tol)
        self.calls = 0

    def _batches(self, rows, order):
        out = [None] * len(rows)
        for start in range(0, len(order), self.batch_size):
            chunk = order[start : start + self.batch_size]
            got = self._predict([rows[i] for i in chunk])
            self.calls += 1
            _require(
                isinstance(got, list) and len(got) == len(chunk),
                "model_returned_wrong_count",
            )
            for i, value in zip(chunk, got):
                out[i] = value
        return out

    def __call__(self, rows):
        rows = [list(r) for r in rows]
        order = list(range(len(rows)))
        self._rng.shuffle(order)
        out = self._batches(rows, order)
        if self.batch_size == 1 or not rows:
            return out
        picked = self._rng.sample(order, min(self.recheck, len(rows)))
        for i in picked:
            alone = self._predict([rows[i]])
            self.calls += 1
            _require(
                isinstance(alone, list) and len(alone) == 1,
                "model_returned_wrong_count",
            )
            if not self._same(out[i], alone[0]):
                raise ModelRowDependent()
        reshuffled = list(order)
        self._rng.shuffle(reshuffled)
        again = self._batches(rows, reshuffled)
        if not all(self._same(a, b) for a, b in zip(out, again)):
            raise ModelRowDependent()
        return out

    def _same(self, a, b):
        if a is None or b is None:
            return a is None and b is None
        if isinstance(a, dict) and isinstance(b, dict):
            return set(a) == set(b) and all(self._same(a[k], b[k]) for k in a)
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return len(a) == len(b) and all(self._same(x, y) for x, y in zip(a, b))
        if _finite(a) and _finite(b):
            return abs(a - b) <= self.abs_tol + self.rel_tol * abs(a)
        return a == b or (
            type(a) is float and type(b) is float and math.isnan(a) and math.isnan(b)
        )


__all__ = [
    "MENU_SCHEMA",
    "METRIC",
    "WEIGHTS",
    "MenuRecord",
    "MenuRefused",
    "ModelRowDependent",
    "RowIndependentPredict",
    "backed_off",
    "draw_menu",
    "menu_record",
    "menu_rows",
    "merge_duties",
    "pick_d",
    "raw_score",
    "score_task",
]
