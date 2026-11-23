"""A pool grade keeps its OWN custody accuracy record and exam-total SE (door-code item 5, 19 Nov 2026).

On 116 the v6 ``gate_failures`` table was never written and the SE/accuracy sidecars were missing: the receiver looked the
version up through its development adapter (`_pool_graded`), which for Motor 1.8 is not the sealed pool adapter, so it never
wrote either sidecar and the gate-failure feedback never had an accuracy record. The receiver now stages a capture around
its producer call (`pool_exam.staged_capture`, never through a producer file) and writes both sidecars from the official
grade's own measure: no second measure, no extra work under the produce's lock, and never a change to the grade.
Synthetic toy Challenge values only (`test_pool_exam`, `test_pool_physics_score`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_exam import ARGUMENTS, CEILING, FAST, exam_rows, toy_binding
from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    geometric_v1_stand_in,
)
from test_pool_physics_score import _measure, _registered, _sets
from test_pool_plugin import fake_measure, good_serve

from carbon.challenge_validator import exam_rotation
from carbon.challenge_validator import gate_failure_feedback as gff
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import pool_exam

KEY = "sha256:" + "ab" * 32
SID = "rtsk_" + "1" * 64


def _plain(the_sets, policies, material):
    """The measure as the producer calls it: no ``capture`` argument (`test_pool_physics_score._measure` without it)."""
    rows = exam_rows(the_sets)
    outputs = good_serve([r["inputs"] for r in rows])
    return pool_exam.measure_pool(
        binding=toy_binding(),
        sets=the_sets,
        policies=policies,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
        **material,
    )


def _staged(the_sets, policies, material):
    """The same measure inside a receiver's staged capture."""
    with pool_exam.staged_capture() as captured:
        result = _plain(the_sets, policies, material)
    return result, captured


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_staged_capture_holds_the_official_grades_own_record_and_basis():
    the_sets = _sets(per_class=2)  # 6 targets per set (the SE needs at least 4)
    policies, material = _registered(the_sets, threshold=2.5)
    explicit_result, explicit = _measure(the_sets, policies, material)
    staged_result, captured = _staged(the_sets, policies, material)
    assert staged_result == explicit_result == _plain(the_sets, policies, material)
    assert captured["accuracy"] == explicit["accuracy"]
    # the scored basis is NOT derived inside the measure (never under the produce's lock): a function hands it back
    assert "se_basis" not in captured and callable(captured["se_basis_of"])
    basis = captured["se_basis_of"]()
    assert basis["total"] == pytest.approx(explicit["se_basis"]["total"], abs=1e-15)
    assert pool_exam.target_bootstrap_se(basis, KEY) == pool_exam.target_bootstrap_se(
        explicit["se_basis"], KEY
    )


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_gate_failed_grade_stages_its_record_and_a_gated_basis():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=1.5)
    result, captured = _staged(the_sets, policies, material)
    assert result["gates"][pool_exam.ACCURACY_GATE] is False
    assert captured["se_basis"] == {"gated": True}
    assert captured["accuracy"]["gate"]["passed"] is False
    # the record the v6 feedback derives from: a gate-failed grade names its failing outputs
    assert gff.valid(gff.derive(captured["accuracy"])) is True


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_only_the_first_measure_fills_the_stage_and_an_explicit_capture_ignores_it():
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=2.5)
    with pool_exam.staged_capture() as captured:
        _plain(the_sets, policies, material)
        first = captured["se_basis_of"]
        _plain(the_sets, policies, material)
        assert captured["se_basis_of"] is first
    with pool_exam.staged_capture() as untouched:
        _measure(the_sets, policies, material)  # the operator's explicit capture
    assert untouched == {}
    # outside a block nothing is staged
    assert pool_exam._STAGED_CAPTURE.get() is None


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_basis_that_cannot_be_derived_never_reaches_the_grade(monkeypatch):
    the_sets = _sets(per_class=2)
    policies, material = _registered(the_sets, threshold=2.5)
    plain = _plain(the_sets, policies, material)

    def broken(*args, **kwargs):
        raise RuntimeError("no")

    # used only to derive the SE basis, never by the grade
    monkeypatch.setattr(pool_exam, "_basis_regions", broken)
    result, captured = _staged(the_sets, policies, material)
    assert result == plain
    with pytest.raises(RuntimeError):
        captured["se_basis_of"]()
    with pytest.raises(
        RuntimeError
    ):  # the operator's explicit capture refuses, as before
        _measure(the_sets, policies, material)


# --- the receiver's sidecars ------------------------------------------------------------------------------------------


def _legs(result):
    """A dual benchmark model's measurements as the producer writes them (`physical_dual_pack.METRICS`)."""
    return {
        physical.METRICS[name]: {
            "status": "RESOLVED",
            "value": result[name],
            "unit": "1",
        }
        for name in ("A", "D")
    }


def _write(directory, captured, gates, score=0.5, measured=None):
    directory.mkdir(exist_ok=True)
    model = {"gates": gates, **({} if measured is None else {"measurements": measured})}
    return retention._write_captured_exam_se(
        SID,
        SimpleNamespace(manifest_digest=KEY),
        directory,
        {"models": [{"score": score}]},
        {"models": [model]},
        captured,
    )


def _se(directory):
    return json.loads((directory / exam_rotation.SE_SIDECAR).read_bytes())


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_scored_pool_grade_writes_both_sidecars_from_its_own_measure(tmp_path):
    the_sets = _sets(per_class=2)
    policies, material = _registered(the_sets, threshold=2.5)
    result, captured = _staged(the_sets, policies, material)
    expected, sizes = pool_exam.target_bootstrap_se(
        captured["se_basis_of"](), KEY, resamples=200
    )
    gates = {"x": "PASS", "y": "PASS"}
    record = _write(tmp_path / "a", captured, gates, measured=_legs(result))
    assert record == captured["accuracy"]
    done = _se(tmp_path / "a")
    assert (done["status"], done["exam_key"], done["resamples"]) == (
        "MEASURED",
        KEY,
        200,
    )
    assert done["standard_error"] == pytest.approx(expected, abs=1e-15)
    assert done["n_targets"] == sizes and done["total"] == 0.5
    se, total = exam_rotation.read_se(tmp_path / "a" / exam_rotation.SE_SIDECAR)
    assert se == pytest.approx(expected, abs=1e-15) and total == 0.5
    kept = json.loads((tmp_path / "a" / exam_rotation.ACCURACY_SIDECAR).read_bytes())
    assert kept["schema"] == exam_rotation.ACCURACY_SIDECAR_SCHEMA
    assert kept["exam_key"] == KEY
    assert kept["record"] == json.loads(json.dumps(captured["accuracy"]))


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_any_failed_gate_gives_a_gated_se_and_still_keeps_the_accuracy_record(
    tmp_path,
):
    the_sets = _sets(per_class=2)
    policies, material = _registered(the_sets, threshold=2.5)
    _result, captured = _staged(the_sets, policies, material)
    # a gate the pool measure never saw (the subset repeat's own) failed: no total, so no SE
    record = _write(tmp_path / "a", captured, {"x": "PASS", "repeat": "FAIL"}, None)
    done = _se(tmp_path / "a")
    assert (done["status"], done["reason"]) == ("UNAVAILABLE", "gated")
    assert "standard_error" not in done
    assert record == captured["accuracy"]
    assert (tmp_path / "a" / exam_rotation.ACCURACY_SIDECAR).exists()
    # the measure's own gated basis reads the same
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=1.5)
    _result, captured = _staged(the_sets, policies, material)
    assert _write(tmp_path / "b", captured, {"x": "PASS"}, None) is not None
    assert _se(tmp_path / "b")["reason"] == "gated"


def test_the_writer_never_raises(tmp_path, capsys):
    def broken():
        raise RuntimeError("no")

    record = {"rows": [], "gate": {"statistic": "p90", "passed": True}}
    failing = {"accuracy": record, "se_basis_of": broken}
    assert _write(tmp_path / "a", failing, {"x": "PASS"}) == record
    done = _se(tmp_path / "a")
    assert (done["status"], done["reason"]) == (
        "UNAVAILABLE",
        "bootstrap_failed:RuntimeError",
    )
    # too few targets: the measure's own refusal code; no record, no accuracy sidecar
    few = {
        "gated": False,
        "a_bank": 0.7,
        "c": 1.0,
        "a_rule": {"kind": "mean"},
        "sets": [[{"d": 0.4, "agen": 0.9}]],
    }
    assert _write(tmp_path / "b", {"se_basis": few}, {"x": "PASS"}) is None
    assert _se(tmp_path / "b")["reason"] == "too_few_targets"
    assert not (tmp_path / "b" / exam_rotation.ACCURACY_SIDECAR).exists()
    # a sidecar that cannot be written (an earlier, different one) is one journal line, never the grade's failure
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / exam_rotation.SE_SIDECAR).write_bytes(b"{}")
    capsys.readouterr()
    assert _write(tmp_path / "c", failing, {"x": "PASS"}) == record
    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [line["event"] for line in lines] == [
        "grade_sidecar_unwritten",
        "grade_case_errors_unavailable",  # LL2: this stand-in measure kept no per-case errors
        "grade_exam_se",
    ]
    assert lines[0]["sidecar"] == exam_rotation.SE_SIDECAR
    assert lines[0]["error"] == "ValueError"
    assert lines[1]["status"] == "UNAVAILABLE" and lines[1]["accuracy"] is True
    assert type(lines[1]["seconds"]) is float and lines[1]["seconds"] >= 0
    assert (tmp_path / "c" / exam_rotation.ACCURACY_SIDECAR).exists()


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_gate_failed_pool_grade_stores_its_gate_failures(tmp_path):
    """The receiver's side end to end: the staged record reaches the v6 table (never written on 116 before)."""
    the_sets = _sets()
    policies, material = _registered(the_sets, threshold=1.5)
    _result, captured = _staged(the_sets, policies, material)
    record = _write(tmp_path / "a", captured, {"x": "FAIL"}, None)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    ledger = AttemptLedger(state / "attempts.sqlite3")
    adapter = SimpleNamespace(ledger=ledger)
    shown = {"status": "GATE_FAILED"}
    assert retention._record_gate_failures(adapter, SID, KEY, shown, record) == ""
    failures = gff.derive(record)
    assert failures is not None and gff.read(ledger, SID, KEY) == failures


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_basis_that_is_not_the_scored_measures_is_never_used(tmp_path):
    """V2 on d31ca579 (evidence A): the captured basis must be the OFFICIAL grade's; its total must be the benchmark's
    own 0.5 A + 0.5 D, else UNAVAILABLE capture_not_official (the accuracy record is still kept).
    """
    the_sets = _sets(per_class=2)
    policies, material = _registered(the_sets, threshold=2.5)
    result, captured = _staged(the_sets, policies, material)
    other = {**result, "D": result["D"] + 0.25}
    record = _write(tmp_path / "a", captured, {"x": "PASS"}, measured=_legs(other))
    done = _se(tmp_path / "a")
    assert (done["status"], done["reason"]) == ("UNAVAILABLE", "capture_not_official")
    assert record == captured["accuracy"]
    basis = retention._official_basis(
        captured, {"models": [{"gates": {"x": "PASS"}, "measurements": _legs(result)}]}
    )
    assert basis["total"] == pytest.approx(0.5 * result["A"] + 0.5 * result["D"])


def test_a_broken_stderr_or_a_malformed_capture_never_stops_the_grade(
    tmp_path, monkeypatch
):
    class Broken:
        def write(self, *args):
            raise OSError("stderr gone")

        def flush(self):
            raise OSError("stderr gone")

    record = {"rows": [], "gate": {"statistic": "p90", "passed": True}}
    monkeypatch.setattr(sys, "stderr", Broken())
    few = {"gated": False, "sets": [[{"d": 0.4}]]}
    assert _write(tmp_path / "a", {"accuracy": record, "se_basis": few}, {}) == record
    assert _write(tmp_path / "b", None, {"x": "PASS"}) is None  # not a capture at all
    monkeypatch.undo()
    retention._journal("grade_exam_se", task=SID, status="MEASURED")
