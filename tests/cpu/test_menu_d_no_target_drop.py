"""Losing a target can never raise menu D (the owner, Thu 12 Nov, before commit R: "once a crown_d block is registered
with min_targets < tasks_per_epoch, crown-time D can be raised by losing targets rather than solving them well").

Motor 1.8 and Cooling 1.8 register NO crown_d block: their D is the menu D (`pool_menu.score`), which runs no solve at
grade time, so there is no reference failure to drop. Every one of the epoch's k drawn tasks is scored and stays in the
mean; a task the model fails (every prediction invalid) scores 0 there, never leaves it. Synthetic fixtures only (the
toy two-duty menu of `test_pool_menu`, under four task ids, k = 3 as Motor 1.8 registers).
"""

from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from test_pool_menu import ROWCHECK, _do_pair_two_duties
from test_pool_plugin import truth

from carbon.scoring import pool_menu

KEY = b"m" * 32  # synthetic custody draw key
TASKS = ("task-1", "task-2", "task-3", "task-4")
K = 3
DESIGN = ("x", "y")


def _loaded():
    problem, record = _do_pair_two_duties()
    pairs = []
    for task in TASKS:
        pairs.append(
            (
                {**copy.deepcopy(problem), "target_id": task},
                {**copy.deepcopy(record), "task_id": task},
            )
        )
    material, shas = pool_menu.menu_material(
        pairs, input_names=("cond", *DESIGN), design_names=DESIGN
    )
    rule = pool_menu.MenuRule(
        records_sha256=tuple(sorted(shas.items())),
        epoch="fixture-epoch-1",
        aggregate="mean",
        rotation_days=7,
        rowcheck=ROWCHECK,
        tasks_per_epoch=K,
    )
    tasks = pool_menu.load_tasks(
        material, rule, input_names=("cond", *DESIGN), design_names=DESIGN
    )
    return tasks, rule


def _noisy(seed, scale):
    """Truth plus noise fixed per ROW (a function of the row alone), so answering or losing another task never changes
    this task's answers."""

    def predict(rows):
        out = []
        for r in rows:
            f, g = truth(r)
            rng = random.Random(json.dumps([seed, sorted(r.items())]))
            out.append({"f": f + rng.gauss(0.0, scale), "g": g + rng.gauss(0.0, scale)})
        return out

    return predict


def _losing(predict, lost_call):
    """``predict`` on every task but the ``lost_call``-th one asked (tasks are answered in order), where every
    prediction is invalid: the model 'loses' that task."""
    calls = []

    def wrapped(rows):
        calls.append(None)
        if len(calls) - 1 == lost_call:
            return [None] * len(rows)
        return predict(rows)

    return wrapped


@pytest.mark.parametrize("scale", [0.0, 0.05, 0.2])
def test_losing_any_drawn_task_never_raises_menu_d_and_never_drops_it(scale):
    tasks, rule = _loaded()
    drawn = set(pool_menu.draw_tasks(rule, KEY, epoch=rule.epoch))
    assert len(drawn) == K < len(tasks)
    base = pool_menu.score(tasks, rule, _noisy(7, scale), key=KEY, design_names=DESIGN)
    assert len(base["record"]["tasks"]) == K
    for n, task in enumerate(tasks):
        lost = pool_menu.score(
            tasks,
            rule,
            _losing(_noisy(7, scale), n),
            key=KEY,
            design_names=DESIGN,
        )
        scored = {t["task_id"]: t for t in lost["record"]["tasks"]}
        # the mean is always over all k drawn tasks: a lost task is never dropped from it
        assert set(scored) == drawn
        assert lost["D"] <= base["D"]
        if task.problem.target_id in drawn:
            # 0 up to the tied-mean rounding (`test_pool_menu`: a constant model's D is approx 0, ~1e-16 here)
            assert scored[task.problem.target_id]["d"] == pytest.approx(0.0, abs=1e-12)
            assert lost["D"] == pytest.approx(sum(t["d"] for t in scored.values()) / K)
        else:
            assert lost["D"] == base["D"]  # an undrawn task is answered, never scored


def test_the_1_8_registrations_carry_no_crown_d_block():
    """crown_d.decide drops REFERENCE_FAILED targets down to min_targets; no 1.8 row registers that path."""
    document = json.loads(
        (ROOT / "scripts/validator_host_classes/pool_constants.json").read_bytes()
    )
    for key in ("electric-motor-magnetics 1.8", "chip-cold-plate 1.8"):
        row = document["versions"][key]
        assert "crown_d" not in row
    assert (
        document["versions"]["electric-motor-magnetics 1.8"]["menu"]["tasks_per_epoch"]
        == K
    )
