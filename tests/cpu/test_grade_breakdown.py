"""The private grade breakdown (`carbon.scoring.grade_breakdown`, schema carbon.exam.grade-breakdown.v1): a closed,
checked document, written once and owner-only, plus the recipe measures read from a retained state. Fixture values only.
"""

from __future__ import annotations

import io
import json
import math
import os
import stat

import numpy as np
import pytest

from carbon.level4 import graph
from carbon.scoring import grade_breakdown as gb

TASK = "rtsk_" + "a" * 64
EXAM = "sha256:" + "1" * 64
NOW = 1_800_000_000.0


def _inputs(**change):
    return {
        "challenge_id": "electric-motor-magnetics",
        "challenge_version": "1.9",
        "submission_id": TASK,
        "exam_key": EXAM,
        "contract_ids": {"score_pack": "sha256:" + "2" * 64, "scorer": "motor-v9"},
        "sets": {
            "cells": {"A": 0.25, "D": 0.5, "rows": 30},
            "pool-1": {"A": None, "D": None, "rows": 0},
        },
        "halves": {"A": 0.25, "D": 0.5},
        "outputs": [
            {"class": "H-1", "output": "torque_pkpk", "range": "in", "n": 16, "median": 0.4, "p90": 1.1},
            {"class": "H-3", "output": "ke_ll", "range": "out", "n": 0, "median": None, "p90": None},
        ],
        "speed": {
            "call_seconds": [0.01] * 20,
            "median_seconds": 0.01,
            "ceiling_seconds": 0.5,
            "passed": True,
        },
        "tasks": [
            {"task": "pool-1/d0001", "D": 0.5, "Z": 0.1, "oracle": 0.9},
            {"task": "pool-1/d0002", "D": None, "Z": 0.2, "oracle": 0.8},
        ],
        "rule_flags": {"rough_solver_zero": True, "in_range": False},
        "recipe": {
            "recipe_info_bytes": 1234,
            "trained_arrays": {"count": 2, "bytes": 354_999},
        },
        "clock": NOW,
        **change,
    }


def test_the_document_is_the_closed_field_set():
    document = gb.breakdown(**_inputs())
    assert set(document) == gb.FIELDS and document["schema"] == gb.SCHEMA
    assert document["written_at"] == "2027-01-15T08:00:00Z"
    # not measured: null, never a stand-in
    assert document["sets"]["pool-1"] == {"A": None, "D": None, "rows": 0}
    assert document["tasks"][1] == {
        "task": "pool-1/d0002",
        "D": None,
        "Z": 0.2,
        "oracle": 0.8,
    }
    assert document["recipe"]["trained_arrays"] == {"count": 2, "bytes": 354_999}
    assert gb.breakdown(**_inputs(recipe=None))["recipe"] == {
        "recipe_info_bytes": None,
        "trained_arrays": None,
    }


@pytest.mark.parametrize(
    "change, code",
    [
        ({"exam_key": "not-a-digest"}, "grade_breakdown_exam_key_invalid"),
        (
            {"sets": {"cells": {"A": math.nan, "D": 0.1, "rows": 1}}},
            "grade_breakdown_sets_invalid",
        ),
        (
            {"sets": {"cells": {"A": True, "D": 0.1, "rows": 1}}},
            "grade_breakdown_sets_invalid",
        ),
        (
            {"sets": {"cells": {"A": 0.1, "D": 0.1, "rows": 1, "margin": 0.2}}},
            "grade_breakdown_sets_invalid",
        ),
        (
            {"tasks": [{"task": "t", "D": 1.0, "Z": 0.0, "oracle": 2.0, "x": 1}]},
            "grade_breakdown_tasks_invalid",
        ),
        (
            {"tasks": [{"task": "t", "D": math.inf, "Z": 0.0, "oracle": 2.0}]},
            "grade_breakdown_tasks_invalid",
        ),
        (
            {
                "tasks": [
                    {"task": "t", "D": 1.0, "Z": 0.0, "oracle": 2.0},
                    {"task": "t", "D": 1.0, "Z": 0.0, "oracle": 2.0},
                ]
            },
            "grade_breakdown_task_repeated",
        ),
        ({"rule_flags": {"in_range": 1}}, "grade_breakdown_rule_flags_invalid"),
        (
            {"recipe": {"recipe_info_bytes": -1, "trained_arrays": None}},
            "grade_breakdown_recipe_invalid",
        ),
        ({"submission_id": "../escape"}, "grade_breakdown_submission_invalid"),
        ({"submission_id": "a/b"}, "grade_breakdown_submission_invalid"),
        ({"sets": {"cells": {"A": 0.1, "rows": 1}}}, "grade_breakdown_sets_invalid"),
        ({"halves": {"A": 0.1}}, "grade_breakdown_halves_invalid"),
        ({"halves": {"A": math.nan, "D": 0.1}}, "grade_breakdown_halves_invalid"),
        (
            {"outputs": [{"class": "H-1", "output": "t", "range": "in", "n": 1}]},
            "grade_breakdown_outputs_invalid",
        ),
        (
            {
                "outputs": [
                    {"class": "H-1", "output": "t", "range": "in", "n": 1, "median": 0.1, "p90": 0.2},
                    {"class": "H-1", "output": "t", "range": "in", "n": 1, "median": 0.1, "p90": 0.2},
                ]
            },
            "grade_breakdown_outputs_invalid",
        ),
        (
            {"outputs": [{"class": "H-1", "output": "t", "range": "in", "n": 1, "median": 0.1, "p90": 0.2, "case": "c1"}]},
            "grade_breakdown_outputs_invalid",
        ),
        (
            {"speed": {"call_seconds": [], "median_seconds": 0.1, "ceiling_seconds": 1.0, "passed": True}},
            "grade_breakdown_speed_invalid",
        ),
        (
            {"speed": {"call_seconds": [None], "median_seconds": 0.1, "ceiling_seconds": 1.0, "passed": True}},
            "grade_breakdown_speed_invalid",
        ),
        (
            {"speed": {"call_seconds": [0.1], "median_seconds": 0.1, "ceiling_seconds": 1.0, "passed": 1}},
            "grade_breakdown_speed_invalid",
        ),
    ],
)
def test_anything_outside_the_closed_document_refuses(change, code):
    with pytest.raises(gb.GradeBreakdownRefused) as refused:
        gb.breakdown(**_inputs(**change))
    assert refused.value.code == code


def test_a_document_past_the_bound_refuses():
    tasks = [
        {"task": f"pool/d{i:04d}-" + "x" * 60, "D": 0.1, "Z": 0.2, "oracle": 0.3}
        for i in range(gb.MAX_ENTRIES)
    ]
    with pytest.raises(gb.GradeBreakdownRefused) as refused:
        gb.breakdown(**_inputs(tasks=tasks))
    assert refused.value.code == "grade_breakdown_too_large"


def _private_dir(tmp_path):
    directory = tmp_path / "custody"
    directory.mkdir(mode=0o700)
    return directory


def test_write_is_once_owner_only_and_refuses_a_change(tmp_path):
    directory = _private_dir(tmp_path)
    document = gb.breakdown(**_inputs())
    path = gb.write(directory, document)
    assert path.name == TASK + gb.SUFFIX
    assert json.loads(path.read_bytes()) == document
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert (
        gb.write(directory, document) == path
    )  # the same bytes again: nothing changes
    changed = gb.breakdown(**_inputs(rule_flags={"in_range": True}))
    with pytest.raises(gb.GradeBreakdownRefused) as refused:
        gb.write(directory, changed)
    assert refused.value.code == "grade_breakdown_conflict"
    assert json.loads(path.read_bytes()) == document


def test_write_refuses_a_document_that_is_not_checked(tmp_path):
    directory = _private_dir(tmp_path)
    document = gb.breakdown(**_inputs())
    for broken in (
        {**document, "margin": 0.1},
        {**document, "tasks": [{"task": "t", "D": "x", "Z": 0.0, "oracle": 1.0}]},
        {**document, "schema": "carbon.exam.grade-breakdown.v0"},
    ):
        with pytest.raises(gb.GradeBreakdownRefused):
            gb.write(directory, broken)
    assert not list(directory.iterdir())


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_write_refuses_a_directory_others_can_read(tmp_path):
    directory = tmp_path / "shared"
    directory.mkdir()
    directory.chmod(0o755)
    with pytest.raises(gb.GradeBreakdownRefused) as refused:
        gb.write(directory, gb.breakdown(**_inputs()))
    assert refused.value.code == "grade_breakdown_directory_not_private"


def _graph():
    return {
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {
                        "value": 0,
                        "name": "params/0",
                        "dtype": "float32",
                        "shape": [10, 20],
                    },
                    {
                        "value": 1,
                        "name": "params/1",
                        "dtype": "float64",
                        "shape": [5],
                    },
                    {
                        "value": 2,
                        "name": "inputs/x",
                        "dtype": "float32",
                        "shape": [1, 20],
                    },
                ],
                "constants": [],
                "nodes": [],
                "outputs": [2],
            }
        },
    }


def _state(document):
    raw = graph.dumps(document)
    out = io.BytesIO()
    np.savez(
        out,
        __header__=np.frombuffer(b'{"schema":"x"}', dtype=np.uint8),
        graph=np.frombuffer(raw, dtype=np.uint8),
        parameter0000=np.zeros((10, 20), dtype=np.float32),
        parameter0001=np.zeros(5, dtype=np.float64),
    )
    return out.getvalue()


def test_recipe_measures_charge_the_graph_and_count_the_trained_arrays_apart():
    document = _graph()
    measures = gb.recipe_measures(_state(document))
    assert measures == {
        "recipe_info_bytes": graph.recipe_info_bytes(document),
        "trained_arrays": {"count": 2, "bytes": 10 * 20 * 4 + 5 * 8},
    }
    # the measures go straight into a breakdown
    assert gb.breakdown(**_inputs(recipe=measures))["recipe"] == measures


@pytest.mark.parametrize("raw", [b"", b"not a zip", None])
def test_recipe_measures_refuse_anything_but_a_state(raw):
    with pytest.raises(gb.GradeBreakdownRefused) as refused:
        gb.recipe_measures(raw)
    assert refused.value.code == "grade_breakdown_state_invalid"


def test_recipe_measures_refuse_a_state_without_a_graph():
    out = io.BytesIO()
    np.savez(out, parameter0000=np.zeros(3, dtype=np.float32))
    with pytest.raises(gb.GradeBreakdownRefused):
        gb.recipe_measures(out.getvalue())
