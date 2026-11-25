"""LL2: every pool grade with an accuracy record writes its per-case errors beside it (owner LL-A, 23 Nov 2026).

Claims:
1. The per-case errors come from the grade's OWN measure (no second inference): the accuracy record, the gates and the
   result are identical with or without the collector, and the collector holds exactly the errors the record reduced.
2. Each case carries the bank row it was answered from (``row_index``, door-code 5141), so the bank joins it to the
   grade's retained positional predictions; a key two bank rows share maps to its first row and is counted.
3. The file is deterministic, loads without pickles, and carries no case or draw id.
4. The receiver writes it once beside the accuracy record; a grade whose measure kept none, or whose file cannot be
   written, is one journal line and never the grade's failure. The archive keeps it local like the record.

Every value is a SYNTHETIC fixture (`test_pool_physics_score`, `test_pool_exam`), never a production value.
"""

from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_captured_exam_se import KEY, SID, _plain, _staged, _write
from test_pool_exam import toy_binding
from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    geometric_v1_stand_in,
)
from test_pool_physics_score import (
    _measure,
    _registered,
    _sets,
    attached,
    model,
    stand_set,
)

from carbon.challenge_validator import exam_rotation, grade_archive
from carbon.scoring import case_errors, pool_plugin
from carbon.scoring import pool_physics_score as pps

# ---------------------------------------------------------------- 1. the collector reads the grade's own measure


def test_the_record_is_identical_with_the_collector_and_it_holds_every_case():
    specs, plan = stand_set()
    rule = attached(specs, plan)
    plain = pps.accuracy_record(specs, model(specs), plan, rule)
    sink = case_errors.Sink()
    assert pps.accuracy_record(specs, model(specs), plan, rule, None, sink) == plain
    # one case per answered (reserved) point, in the order asked: i0 (5), e0 (2), s0 (1), x0 (1)
    assert [(c.spec_index, c.case_index) for c in sink.cases] == [
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3),
        (0, 4),
        (1, 0),
        (1, 1),
        (2, 0),
        (3, 0),
    ]
    first = sink.cases[1]
    assert first.source == case_errors.SOURCE_TARGET and not first.bad
    # S2 (case-errors v2): the answer is kept beside the error, so the file can carry its sign
    error, u, truth, answer = first.outputs["f"]
    assert (error, u, truth) == (pytest.approx(0.2), 0.5, 0.0)
    assert abs(answer - truth) == pytest.approx(error)
    # the record's i0 median |err|/U is the median of these cases' ratios
    by_case = [c.outputs["f"][0] / c.outputs["f"][1] for c in sink.cases[:5]]
    row = next(
        r for r in plain["rows"] if r["class"] == "fixture:in" and r["output"] == "f"
    )
    assert row["median"] == pytest.approx(sorted(by_case)[2])


def test_an_invalid_answer_is_a_case_with_no_error():
    specs, plan = stand_set()
    rule = attached(specs, plan)
    good = model(specs)

    def one_bad(conditions, designs):
        out = good(conditions, designs)
        if conditions["case"] == "e0":
            out[0] = {"f": math.nan, "g": 0.0}
        return out

    sink = case_errors.Sink()
    record = pps.accuracy_record(specs, one_bad, plan, rule, None, sink)
    assert record == pps.accuracy_record(specs, one_bad, plan, rule)
    bad = [c for c in sink.cases if c.bad]
    assert [(c.spec_index, c.case_index, c.outputs) for c in bad] == [(1, 0, {})]


# ---------------------------------------------------------------- 2. the official grade: same result, rows joined


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_grade_is_unchanged_and_each_case_names_its_bank_row():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    plain = _plain(the_sets, policies, material)
    result, capture = _measure(the_sets, policies, material)
    assert result == plain
    assert "case_errors_unavailable" not in capture
    # the capture holds plain data: two identical grades compare equal (`test_pool_accuracy_only` compares captures)
    assert _measure(the_sets, policies, material)[1] == capture
    arrays = case_errors.to_arrays(capture["case_errors"])
    # 8 reserved points per in-range target x 2 sets, plus the out-of-range targets' reserved points
    n = len(arrays["row_index"])
    assert n > 0 and arrays["abs_error"].shape == (n, len(arrays["output_names"]))
    assert set(arrays["output_names"]) == {"f", "g"}
    assert int(arrays["n_duplicate_keys"]) == 0
    # every case's row is the bank row holding the design it was asked about
    from test_pool_exam import exam_rows

    rows = exam_rows(the_sets)
    specs = [spec for group in the_sets for spec in group]
    binding = toy_binding()
    for k in range(n):
        spec = specs[arrays["spec_index"][k]]
        asked = pool_plugin.model_input_row(
            binding, spec.conditions, list(spec.designs[arrays["case_index"][k]])
        )
        held = rows[arrays["row_index"][k]]["inputs"]
        assert all(
            held[name] == pytest.approx(asked[name]) for name in binding.input_names
        )
    # good_serve is off by exactly 2 U on every in-range case (`test_pool_physics_score`)
    names = list(arrays["class_names"])
    inside = arrays["class_index"] == names.index("fixture:in")
    assert np.median(arrays["ratio"][inside]) == pytest.approx(2.0)


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_collector_failure_is_recorded_and_never_reaches_the_grade(monkeypatch):
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    plain = _plain(the_sets, policies, material)

    def broken(*args, **kwargs):
        raise case_errors.CaseErrorsRefused("case_errors_served_rows_misaligned")

    monkeypatch.setattr(case_errors, "assemble", broken)
    result, capture = _measure(the_sets, policies, material)
    assert result == plain
    assert "case_errors" not in capture
    assert capture["case_errors_unavailable"] == "case_errors_served_rows_misaligned"


def test_a_key_two_bank_rows_share_maps_to_its_first_row_and_is_counted():
    sink = case_errors.Sink()
    sink.case(0, 0, 0, "c").output("f", 1.0, 2.0, 4.0)
    sink.case(1, -1, 0, "c").output("f", -3.0, 0.0, 0.0)
    content = case_errors.assemble(sink, [(2.0,), (1.0,)], [(1.0,), (2.0,), (2.0,)])
    assert content["ratio"] == [[0.5], [None]] and content["pct"] == [[25.0], [None]]
    arrays = case_errors.to_arrays(content)
    assert arrays["row_index"].tolist() == [1, 0]
    assert int(arrays["n_duplicate_keys"]) == 1
    assert arrays["abs_error"][:, 0].tolist() == [1.0, 3.0]
    # U = 0: no ratio; truth 0: no percent
    assert arrays["ratio"][0, 0] == 0.5 and math.isnan(arrays["ratio"][1, 0])
    assert arrays["pct"][0, 0] == 25.0 and math.isnan(arrays["pct"][1, 0])
    assert arrays["source"].tolist() == [0, 1]
    assert arrays["spec_index"].tolist() == [0, -1]


def test_an_empty_grade_still_has_well_shaped_members():
    content = case_errors.assemble(case_errors.Sink(), [], [(1.0,)])
    arrays = case_errors.to_arrays(content)
    assert set(arrays) == set(case_errors.DTYPES)
    assert arrays["abs_error"].shape == (0, 0) and arrays["typed_ratio"].shape == (0, 0)


def test_the_subset_repeat_producer_file_is_untouched():
    """door-code 5194 asked to hand the file on in `subset_repeat_produce`; that file is in Motor 1.8's producer digest
    (`motor18_dual_pack._SUBSET_FILES`), so it is NOT edited here (that would re-pin the live sealed pack): its
    re-measured SE path journals ``grade_case_errors_unavailable`` instead, and the staged capture covers live grades.
    """
    from carbon.scoring import motor18_dual_pack, subset_repeat_produce

    assert "subset_repeat_produce.py" in motor18_dual_pack._SUBSET_FILES
    text = Path(subset_repeat_produce.__file__).read_text(encoding="utf-8")
    assert "case_errors" not in text


def test_misaligned_or_foreign_rows_refuse():
    sink = case_errors.Sink()
    sink.case(0, 0, 0, "c")
    sink.case(0, 0, 1, "c")
    refused = case_errors.CaseErrorsRefused
    with pytest.raises(refused, match="served_rows_misaligned"):
        case_errors.assemble(sink, [(1.0,)], [(1.0,)])
    with pytest.raises(refused, match="served_row_not_in_the_bank"):
        case_errors.assemble(sink, [(1.0,), (9.0,)], [(1.0,)])


# ---------------------------------------------------------------- 3. the file


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_file_is_deterministic_loads_without_pickles_and_holds_no_ids():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    _result, capture = _measure(the_sets, policies, material)
    payload = case_errors.encode(capture["case_errors"], KEY)
    assert payload == case_errors.encode(capture["case_errors"], KEY)
    loaded = np.load(io.BytesIO(payload), allow_pickle=False)
    assert str(loaded["schema"]) == case_errors.SCHEMA
    assert str(loaded["exam_key"]) == KEY
    expected = sorted([*capture["case_errors"], "schema", "exam_key"])
    assert sorted(loaded.files) == expected
    for name in ("abs_error", "u", "ratio", "pct", "typed_ratio"):
        assert loaded[name].dtype == np.float64
    text = json.dumps({name: loaded[name].tolist() for name in loaded.files})
    assert "case_id" not in text and "extra:" not in text and "rtsk_" not in text


# ---------------------------------------------------------------- 4. the receiver's sidecar


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_receiver_writes_it_once_beside_the_accuracy_record(tmp_path):
    the_sets = _sets(per_class=2)
    policies, material = _registered(the_sets, threshold=2.5)
    _result, captured = _staged(the_sets, policies, material)
    assert _write(tmp_path / "a", captured, {"x": "PASS"}) is not None
    path = tmp_path / "a" / exam_rotation.CASE_ERRORS_SIDECAR
    assert (tmp_path / "a" / exam_rotation.ACCURACY_SIDECAR).exists() and path.exists()
    assert path.read_bytes() == case_errors.encode(captured["case_errors"], KEY)
    assert exam_rotation.CASE_ERRORS_SIDECAR == case_errors.SIDECAR
    assert grade_archive.kept_local(exam_rotation.CASE_ERRORS_SIDECAR) is True


def test_a_grade_without_per_case_errors_is_one_journal_line(tmp_path, capsys):
    record = {"rows": [], "gate": {"statistic": "p90", "passed": True}}
    captured = {"accuracy": record, "se_basis": {"gated": True}}
    capsys.readouterr()
    assert _write(tmp_path / "a", captured, {"x": "FAIL"}) == record
    assert not (tmp_path / "a" / exam_rotation.CASE_ERRORS_SIDECAR).exists()
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    (missing,) = [
        line for line in lines if line["event"] == "grade_case_errors_unavailable"
    ]
    assert (missing["task"], missing["reason"]) == (SID, "not_collected")


def test_a_file_that_cannot_be_written_is_one_journal_line(tmp_path, capsys):
    sink = case_errors.Sink()
    sink.case(0, 0, 0, "c").output("f", 1.0, 2.0, 4.0)
    content = case_errors.assemble(sink, [(1.0,)], [(1.0,)])
    record = {"rows": [], "gate": {"statistic": "p90", "passed": True}}
    captured = {"accuracy": record, "se_basis": {"gated": True}, "case_errors": content}
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / exam_rotation.CASE_ERRORS_SIDECAR).write_bytes(b"earlier")
    capsys.readouterr()
    assert _write(tmp_path / "a", captured, {"x": "FAIL"}) == record
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    (unwritten,) = [
        line
        for line in lines
        if line["event"] == "grade_sidecar_unwritten"
        and line["sidecar"] == exam_rotation.CASE_ERRORS_SIDECAR
    ]
    assert unwritten["error"] == "ValueError"
