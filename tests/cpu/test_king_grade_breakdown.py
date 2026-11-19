"""The king grade breakdown's output guard (scripts/dev/king_grade_breakdown.py): aggregates only, a self-check
before any write, an owner-only output directory. No sealed data and no key: numpy stand-ins only."""

from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "king_grade_breakdown", ROOT / "scripts/dev/king_grade_breakdown.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _good(tool):
    rng = np.random.default_rng(7)
    a_sets = [float(v) for v in rng.uniform(0.8, 1.0, size=3)]
    c, menu_d = 0.97, float(rng.uniform(0.6, 0.9))
    tasks = [
        {
            "task": i,
            "D": float(rng.uniform(0.0, 1.0)),
            "Z": float(rng.uniform(0.0, 0.5)),
            "oracle": float(rng.uniform(0.6, 1.0)),
            "zero_source": source,
        }
        for i, source in enumerate(("random", "classical_arm", "random"), start=1)
    ]
    a, d, w = float(np.mean(a_sets)), min(menu_d, c), 0.5
    return {
        "schema": tool.SCHEMA,
        "challenge": "electric-motor-magnetics",
        "version": "1.8",
        "epoch": "E1",
        "A": a,
        "D": d,
        "total": (1 - w) * a + w * d,
        "value_weight": w,
        "sets": [
            {"set": i, "A": v, "C": c, "D": min(menu_d, c)}
            for i, v in enumerate(a_sets, start=1)
        ],
        "tasks": tasks,
        "gates": {
            "native_motor_valid": "PASS",
            "complete_fixed_coverage": "PASS",
            "physics_pool": "PASS",
            "speed": "FAIL",
        },
        "menu_tasks_scored": len(tasks),
    }


def test_a_good_aggregates_document_passes():
    tool = _tool()
    doc = _good(tool)
    assert tool._checked_aggregates(doc) is doc


def _refused(tool, doc):
    with pytest.raises(tool.BreakdownRefused):
        tool._checked_aggregates(doc)


def test_an_extra_key_at_any_level_refuses():
    tool = _tool()
    for where in ("top", "set", "task"):
        doc = _good(tool)
        target = {"top": doc, "set": doc["sets"][0], "task": doc["tasks"][0]}[where]
        target["task_id"] = "t1"
        _refused(tool, doc)


def test_a_task_id_like_string_refuses():
    tool = _tool()
    doc = _good(tool)
    doc["tasks"][1]["zero_source"] = "task-3f9a1c0b7e2d4a65"
    _refused(tool, doc)
    doc = _good(tool)
    doc["gates"]["menu_3f9a1c0b7e2d4a65"] = "PASS"
    _refused(tool, doc)
    doc = _good(tool)
    doc["gates"]["speed"] = "sha256:" + "ab" * 32
    _refused(tool, doc)


def test_a_nested_per_cell_list_refuses():
    tool = _tool()
    cells = [float(v) for v in np.linspace(0.0, 1.0, 5)]
    for place in ("set", "task", "top"):
        doc = _good(tool)
        if place == "set":
            doc["sets"][0]["A"] = list(cells)
        elif place == "task":
            doc["tasks"][0]["D"] = list(cells)
        else:
            doc["sets"].append(list(cells))
        _refused(tool, doc)


def test_a_path_refuses():
    tool = _tool()
    doc = _good(tool)
    doc["epoch"] = "/srv/carbon/door/pack"
    _refused(tool, doc)
    doc = _good(tool)
    doc["gates"]["/srv/carbon/door/pack"] = "PASS"
    _refused(tool, doc)


def test_a_non_ordinal_or_bool_value_refuses():
    tool = _tool()
    doc = _good(tool)
    doc["tasks"][0]["task"] = 2
    _refused(tool, doc)
    doc = _good(tool)
    doc["A"] = True
    _refused(tool, doc)
    doc = _good(tool)
    doc["menu_tasks_scored"] = 7
    _refused(tool, doc)


def test_the_self_check_refuses_a_mismatch_beyond_5e_5():
    tool = _tool()
    doc = _good(tool)
    expected = {"A": doc["A"], "D": doc["D"], "total": doc["total"]}
    tool._self_check(doc, {k: v + 4e-5 for k, v in expected.items()})
    for name in ("A", "D", "total"):
        off = dict(expected)
        off[name] += 1e-4
        with pytest.raises(tool.SelfCheckFailed):
            tool._self_check(doc, off)
    missing = copy.deepcopy(doc)
    missing["total"] = None
    with pytest.raises(tool.SelfCheckFailed):
        tool._self_check(missing, expected)


@pytest.mark.skipif(os.name != "posix", reason="POSIX modes only")
def test_the_out_dir_must_be_owner_only(tmp_path):
    tool = _tool()
    out = tmp_path / "out"
    out.mkdir()
    out.chmod(0o750)
    with pytest.raises(tool.BreakdownRefused):
        tool._private_out_dir(out.resolve())
    out.chmod(0o700)
    assert tool._private_out_dir(out.resolve()) == out.resolve()
    digest = tool._write_once(out.resolve(), _good(tool))
    written = list(out.iterdir())
    assert len(written) == 1 and digest[:16] in written[0].name
    assert written[0].stat().st_mode & 0o777 == 0o600
