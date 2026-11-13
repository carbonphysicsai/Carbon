"""Menu D scores k of a version's registered tasks per epoch (owner's typed k; Carbon Validator-Motor 10 Nov ruling (i)).

Claims (the ruling's conditions):
(a) the epoch's draw is deterministic from (key, epoch id, the version's whole task registration), uniform k of N;
    a registered k is logged in the custody record;
(b) the drawn ids never reach `public`;
(c) every epoch scores its OWN draw, never mixed: a stored record re-scores each epoch on that epoch's draw;
(d) D = the mean over the k drawn tasks (equal to a k-task registration of exactly those tasks);
(e) the same epoch gives the same set, a new epoch can change it, and every k-subset appears over many epochs.
Also: k is registered with no default (HUMAN_INPUT, null, k < 3, k > N refuse) and absent means every task,
so every version without it scores exactly as before (the existing test_pool_menu suite, unchanged).

Every task, record, key and value here is a SYNTHETIC fixture (the analytic toy of test_menu_score).
"""

from __future__ import annotations

import collections
import copy
import dataclasses
import itertools
import json
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_menu_score import _document as menu_document
from test_pool_exam import POLICIES
from test_pool_menu import (
    FIXED,
    KEY,
    PROBLEM_DOC,
    ROWCHECK,
    _menu_grade,
    _truth_predict,
)
from test_pool_plugin import truth

from carbon.scoring import menu_score, pool_exam, pool_menu, pool_version

TASK_IDS = ("task-1", "task-2", "task-3", "task-4")
S_ZERO = {
    "task-1": 0.55,
    "task-2": 0.6,
    "task-3": 0.65,
    "task-4": 0.7,
}  # synthetic: tasks score differently
EPOCH = "fixture-epoch-1"


def _doc(task_id):
    document = menu_document()
    document["task_id"] = task_id
    document["s_zero"] = S_ZERO[task_id]
    return document


def _problem_doc(task_id):
    return {**copy.deepcopy(PROBLEM_DOC), "target_id": task_id}


def _material(ids=TASK_IDS):
    return {
        "tasks": [
            {
                "problem": _problem_doc(t),
                # each task its own duty value, so the bank's rows stay distinct (the real bank dedups)
                "duties": [["", {**FIXED, "cond": FIXED["cond"] + 0.25 * i}]],
                "record": _doc(t),
            }
            for i, t in enumerate(ids)
        ]
    }


def _shas(ids=TASK_IDS):
    return tuple(
        sorted(
            (
                t,
                menu_score.menu_record(
                    _doc(t), pool_menu._problem(_problem_doc(t))
                ).sha256,
            )
            for t in ids
        )
    )


def _rule(k=3, ids=TASK_IDS, epoch=EPOCH, shas=None):
    return pool_menu.MenuRule(
        records_sha256=_shas(ids) if shas is None else shas,
        epoch=epoch,
        aggregate="mean",
        rotation_days=7,
        rowcheck=ROWCHECK,
        tasks_per_epoch=k,
    )


def _tasks(ids=TASK_IDS, k=None):
    return pool_menu.load_tasks(
        _material(ids),
        _rule(k=k, ids=ids),
        input_names=("cond", "x", "y"),
        design_names=("x", "y"),
    )


def _fit_predict(rows):
    # a TRAIN-only-fit-like model: under-predicts g a little, so the tasks' D differ (synthetic)
    out = []
    for row in rows:
        f, g = truth(row)
        out.append({"f": f, "g": g - 0.03})
    return out


def _score(rule, tasks=None, predict=_fit_predict, **kw):
    return pool_menu.score(
        _tasks() if tasks is None else tasks,
        rule,
        predict,
        key=KEY,
        design_names=("x", "y"),
        **kw,
    )


# ---------------------------------------------------------------- registration


def _block(**over):
    block = {
        "records_sha256": dict(_shas()),
        "epoch": "e1",
        "aggregate": "mean",
        "rotation_days": 7,
        "rowcheck": {"rel_tol": 0.0, "abs_tol": 1e-12, "subset": 8},
    }
    block.update(over)
    return block


def test_k_is_registered_with_no_default_and_absent_means_every_task():
    assert pool_version._menu(_block()).tasks_per_epoch is None
    assert pool_version._menu(_block(tasks_per_epoch=3)).tasks_per_epoch == 3
    assert pool_version._menu(_block(tasks_per_epoch=4)).tasks_per_epoch == 4
    with pytest.raises(pool_version.PoolConstantsNotRegistered, match="not_registered"):
        pool_version._menu(_block(tasks_per_epoch=pool_version.HUMAN_INPUT))
    for bad in (None, 2, 5, 0, -3, 3.0, "3", True, [3]):
        with pytest.raises(pool_version.PoolConstantsNotRegistered, match="malformed"):
            pool_version._menu(_block(tasks_per_epoch=bad))


def test_check_rule_refuses_k_outside_min_tasks_and_the_task_count():
    for k in (3, 4):
        assert pool_menu.check_rule(_rule(k=k)).tasks_per_epoch == k
    for k in (2, 5, 0, 3.0, True):
        with pytest.raises(pool_exam.ExamRefused) as caught:
            pool_menu.check_rule(_rule(k=k))
        assert caught.value.code == "menu_tasks_per_epoch_invalid"


# ---------------------------------------------------------------- (a) + (e) the draw


def test_no_k_draws_every_task():
    assert pool_menu.draw_tasks(_rule(k=None), KEY, epoch=EPOCH) == TASK_IDS


def test_the_same_epoch_gives_the_same_set_and_the_draw_is_k_of_the_registration():
    first = pool_menu.draw_tasks(_rule(), KEY, epoch=EPOCH)
    assert (
        len(first) == 3 and set(first) < set(TASK_IDS) and list(first) == sorted(first)
    )
    for _ in range(5):
        assert pool_menu.draw_tasks(_rule(), KEY, epoch=EPOCH) == first


def test_a_new_epoch_can_change_the_set_and_every_subset_appears_about_uniformly():
    epochs = [f"e{i}" for i in range(800)]
    counts = collections.Counter(
        pool_menu.draw_tasks(_rule(), KEY, epoch=e) for e in epochs
    )
    subsets = {tuple(c) for c in itertools.combinations(TASK_IDS, 3)}
    assert set(counts) == subsets  # all 4 subsets appear
    # uniform 3 of 4: expected 200 each; 4.5 sigma of a binomial(800, 1/4) is about 55
    assert all(145 <= n <= 255 for n in counts.values()), counts


def test_the_draw_is_bound_to_the_key_and_the_versions_registration():
    epochs = [f"e{i}" for i in range(64)]
    base = [pool_menu.draw_tasks(_rule(), KEY, epoch=e) for e in epochs]
    other_key = [pool_menu.draw_tasks(_rule(), b"q" * 32, epoch=e) for e in epochs]
    shas = tuple((t, ("b" * 64 if t == "task-4" else s)) for t, s in _shas())
    other_version = [
        pool_menu.draw_tasks(_rule(shas=shas), KEY, epoch=e) for e in epochs
    ]
    assert base != other_key and base != other_version
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_menu.draw_tasks(_rule(), b"short", epoch=EPOCH)
    assert caught.value.code == "menu_draw_key_invalid"


# ---------------------------------------------------------------- (d) D over the drawn tasks + the custody record


def test_d_is_the_mean_over_the_drawn_tasks_and_equals_a_registration_of_just_those():
    graded = _score(_rule())
    drawn = pool_menu.draw_tasks(_rule(), KEY, epoch=EPOCH)
    record = graded["record"]
    assert [t["task_id"] for t in record["tasks"]] == list(drawn)
    assert graded["D"] == pytest.approx(
        math.fsum(t["d"] for t in record["tasks"]) / 3, abs=0
    )
    # the same model on a 3-task registration of exactly the drawn tasks (no k) scores the same D, bit for bit
    alone = _score(_rule(k=None, ids=drawn), tasks=_tasks(ids=drawn))
    assert graded["D"] == alone["D"]
    # the tasks really differ, so the draw matters: the all-4 mean is not the drawn mean
    every = _score(_rule(k=None))
    assert len({round(t["d"], 12) for t in every["record"]["tasks"]}) == 4
    assert every["D"] != graded["D"]


def test_the_custody_record_logs_k_keeps_every_tasks_predictions_and_no_menu_ids():
    record = _score(_rule())["record"]
    assert record["tasks_per_epoch"] == 3 and record["epoch"] == EPOCH
    assert set(record["predictions"]) == set(
        TASK_IDS
    )  # a later epoch may draw any task
    assert all("menu" not in t and "ids" not in t for t in record["tasks"])
    assert (
        "tasks_per_epoch" not in _score(_rule(k=None))["record"]
    )  # no k: the record is as before


def test_a_row_dependent_model_scores_zero_on_the_drawn_tasks():
    graded = _score(_rule(), row_dependent=True)
    drawn = pool_menu.draw_tasks(_rule(), KEY, epoch=EPOCH)
    assert graded["D"] == 0.0
    assert [t["task_id"] for t in graded["record"]["tasks"]] == list(drawn)
    assert graded["record"]["tasks_per_epoch"] == 3


# ---------------------------------------------------------------- (c) never mixed across epochs


def test_a_stored_record_rescores_each_epoch_on_its_own_draw():
    graded = _score(_rule())
    stored = graded["record"]["predictions"]
    tasks = _tasks()
    assert (
        pool_menu.rescore(tasks, _rule(), stored, key=KEY, epochs=[EPOCH])
        == graded["D"]
    )
    epochs = [EPOCH, "e2", "e3"]
    per_epoch = [_score(_rule(epoch=e))["D"] for e in epochs]
    mean3 = pool_menu.rescore(tasks, _rule(), stored, key=KEY, epochs=epochs)
    assert mean3 == pytest.approx(math.fsum(per_epoch) / 3, abs=1e-15)
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_menu.rescore(
            tasks,
            _rule(),
            {t: v for t, v in stored.items() if t != "task-4"},
            key=KEY,
            epochs=["e2"],
        )
    assert caught.value.code == "menu_stored_predictions_incomplete"


# ---------------------------------------------------------------- the official grade, end to end (fixture)


def test_the_official_grade_scores_the_drawn_tasks_and_public_shows_none_of_it():
    tasks = _tasks()
    rule = _rule()
    result, capture = _menu_grade(
        tasks=tasks, policies=dataclasses.replace(POLICIES, menu=rule)
    )
    menu = result["pool"]["menu"]
    drawn = pool_menu.draw_tasks(rule, KEY, epoch=EPOCH)
    assert [t["task_id"] for t in menu["tasks"]] == list(drawn)
    assert menu["tasks_per_epoch"] == 3 and menu is capture["menu"]
    assert result["D"] <= result["design_fidelity"]["C"]
    shown = json.dumps(pool_exam.public(result))
    assert "menu" not in shown and "fixture-epoch" not in shown
    assert not any(t in shown for t in TASK_IDS)


def test_a_truthful_model_scores_one_on_any_draw():
    assert _score(_rule(), predict=_truth_predict)["D"] == pytest.approx(1.0)
