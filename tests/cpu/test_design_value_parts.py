"""The design-value parts tool (scripts/dev/design_value_parts.py): read-only, same scorer, exact recompute.

Run on the synthetic toy Challenge of `test_pool_exam` (every number there is a SYNTHETIC test value): the model's table
goes through `pool_exam.measure_pool` and the tool records what the grader returned, never a copy of its arithmetic.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_exam import CEILING, grade
from test_pool_plugin import U, truth

from carbon.scoring import pool_exam, pool_grader
from scripts.dev import design_value_parts as tool


def weak(rows):
    return [[v + 6 * U for v in truth(r)] for r in rows]


def report_for(serve, **kwargs):
    stored = grade(serve)[
        "D"
    ]  # the "stored" D: an earlier, unrecorded grade of the same model
    return tool.recompute(lambda: grade(serve), stored, **kwargs), stored


def test_the_recomputed_d_equals_the_stored_d_exactly_and_the_parts_are_the_graders():
    report, stored = report_for(weak)
    assert report["ok"] is True
    assert report["recomputed_d"] == report["measure_d"] == report["stored_d"] == stored
    sets = report["sets"]
    assert [len(s["targets"]) for s in sets] == [2, 2]
    for one in sets:
        assert one["min_mean_d_C"] == min(one["mean_d"], one["C"])
        assert one["mean_d"] == statistics.fmean(t["d"] for t in one["targets"])
        for target in one["targets"]:
            assert set(target) == {
                "target",
                "feasible",
                "reason",
                "d",
                "q",
                "e",
                "s_h",
                "h",
                "reached_reference",
                "queries",
                "regret",
            }
            if target["feasible"]:
                assert target["d"] == target["q"] * target["h"]
    assert stored == statistics.fmean(s["min_mean_d_C"] for s in sets)


def test_the_tool_uses_the_graders_own_functions_and_restores_them():
    real = (pool_grader.grade_set, pool_exam.measure_pool)
    report_for(weak)
    assert (pool_grader.grade_set, pool_exam.measure_pool) == real
    with pytest.raises(RuntimeError), tool.recording():
        raise RuntimeError
    assert (pool_grader.grade_set, pool_exam.measure_pool) == real


def test_a_stored_d_that_differs_in_the_last_bit_is_a_mismatch():
    stored = grade(weak)["D"]
    nudged = stored + 1e-15 * max(1.0, abs(stored))
    assert nudged != stored
    report = tool.recompute(lambda: grade(weak), nudged)
    assert report["ok"] is False and report["recomputed_d"] == stored


def test_the_binding_d_must_equal_it_too_and_a_binding_without_one_is_refused():
    stored = grade(weak)["D"]
    good = {"evidence": {"measurements": {tool.D_METRIC: {"value": stored}}}}
    assert tool.recompute(lambda: grade(weak), stored, binding=good)["ok"] is True
    also = {"model_p": {"design_benefit": stored}}
    assert tool.recompute(lambda: grade(weak), stored, binding=also)["ok"] is True
    off = {"model_p": {"design_benefit": stored + 1e-9}}
    report = tool.recompute(lambda: grade(weak), stored, binding=off)
    assert report["ok"] is False and report["binding_d"] == [stored + 1e-9]
    with pytest.raises(tool.PartsError, match="names no design_benefit"):
        tool.recompute(lambda: grade(weak), stored, binding={"other": 1})


def test_a_gated_model_has_no_pool_d_and_matches_only_a_stored_zero():
    slow = lambda: grade(weak, speed=[CEILING * 3] * 20)
    gated = tool.recompute(slow, 0.0)
    assert gated["gated"] is True and gated["sets"] == [] and gated["ok"] is True
    assert tool.recompute(slow, 0.25)["ok"] is False


def test_regret_is_derived_from_the_specs_own_reference_fields():
    stored = grade(weak)["D"]
    with tool.recording() as recorder:
        grade(weak)
    sets = tool.parts(recorder)
    index = 0
    for specs, setgrade, _honesty in recorder.sets:
        for spec, target in zip(specs, setgrade.targets, strict=True):
            expected = (
                None
                if target.pick is None
                else (spec.s_ref - spec.sign * spec.truths[target.pick][spec.objective])
                / (spec.s_ref - spec.s_low)
            )
            assert sets[index // 2]["targets"][index % 2]["regret"] == expected
            if target.feasible and 0.0 <= target.q <= 1.0 and expected is not None:
                assert target.q == pytest.approx(1.0 - expected, abs=1e-9) or (
                    target.q in (0.0, 1.0)
                )
            index += 1
    assert stored >= 0.0


ALLOWED = re.compile(
    r"^(set \d+: C=\S+ mean_d=\S+ min\(mean_d,C\)=\S+"
    r"|  target \d+\.\d+ \[[0-9a-f]{16}\]: feasible=(True|False) reason=\w+ d=\S+ q=\S+ e=\S+ s_h=\S+ h=\S+"
    r" reached_reference=(True|False) queries=\d+ regret=\S+ \(derived \(not a grader output\)\)"
    r"|gated: .*|stored D     = \S+|recomputed D = \S+|binding D    = .*|MATCH|MISMATCH)$"
)


def test_the_printout_carries_scalars_only(tmp_path, capsys, monkeypatch):
    stored = grade(weak)["D"]
    monkeypatch.setattr(
        tool,
        "load_run",
        lambda manifest, base=None: (lambda: grade(weak), stored),
    )
    inputs = tmp_path / "inputs.json"
    inputs.write_text("{}")
    assert tool.main(["--inputs", str(inputs)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "MATCH" and lines
    for line in lines:
        assert ALLOWED.match(line), line
    assert tool.main(["--inputs", str(inputs), "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["ok"] is True and set(document) >= {"sets", "stored_d"}


def test_a_mismatch_exits_one_and_an_unusable_input_exits_two(
    tmp_path, capsys, monkeypatch
):
    stored = grade(weak)["D"]
    monkeypatch.setattr(
        tool,
        "load_run",
        lambda manifest, base=None: (lambda: grade(weak), stored + 1e-6),
    )
    inputs = tmp_path / "inputs.json"
    inputs.write_text("{}")
    assert tool.main(["--inputs", str(inputs)]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "MISMATCH"
    assert tool.main(["--inputs", str(tmp_path / "absent.json")]) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_the_stored_d_is_read_from_the_dual_measurement_receipt():
    document = {
        "benchmark": {
            "models": [{"measurements": {tool.D_METRIC: {"value": 0.125}}}],
        }
    }
    assert tool.stored_d(document) == 0.125
    for broken in ({}, {"benchmark": {"models": []}}):
        with pytest.raises(tool.PartsError):
            tool.stored_d(broken)


def test_the_tool_writes_nothing_and_changes_no_carbon_module():
    source = Path(tool.__file__).read_text(encoding="utf-8")
    assert "write_text" not in source and "write_bytes" not in source
    assert not re.search(r"\bopen\([^)]*[\"'][wax]", source)
