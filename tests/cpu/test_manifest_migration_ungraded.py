"""M2 narrowed (over-broad rules audit #12, owner 20 Nov 2026: only exam integrity, hidden values or funds justify a gate).

A switch that changes a grading or rebuild path migrated a carried owner's manifest only under a hand-declared exam change.
What that protects is the evidence a grade bound to the program that made it. Claims: an owner that holds NO grade
evidence (unbuilt tasks; a built task with no grade, or a FAILED / withdrawn marker, when the worker build inputs are
unchanged) migrates with no declaration and one counts-only line; an owner with any grade (or a marker that cannot be
read), a built state from changed build inputs, the crown's host owner, an unknown change, or doubt (no door markers, an
unreadable store) still needs the declared record exactly as before; the migration record names its basis. Synthetic
fixtures only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_owner_manifest_migration import (
    NEW,
    OLD,
    Ledger,
    _manifest,
    served,  # noqa: F401 - fixture
)

from carbon.challenge_validator import direct_receiver as dr

TOUCHED = ("carbon/scoring/pool_exam.py",)
WITH_BUILD = (dr.BUILD_INPUTS_CHANGED, "carbon/scoring/pool_exam.py")
T1, T2 = "rtsk_" + "1" * 64, "rtsk_" + "2" * 64


@pytest.fixture
def world(tmp_path, monkeypatch, served):  # noqa: F811
    monkeypatch.setattr(dr, "DECLARED_EXAM_CHANGE", None)
    monkeypatch.setattr(dr, "EARLIER_DECLARED_CHANGES", ())
    owner = tmp_path / "owner"
    (owner / "ledger").mkdir(parents=True)
    markers = tmp_path / "auto-grade" / "markers"
    markers.mkdir(parents=True)
    frozen, candidate = _manifest(OLD), _manifest(NEW)
    ledger = Ledger(owner / "ledger", frozen, [served])
    states = []
    monkeypatch.setattr(dr, "_owner_task_states", lambda owner_dir: list(states))

    def migrate(touched, *, markers_dir=markers, host=False):
        monkeypatch.setattr(dr, "_grading_change", lambda old, new, root=None: touched)
        return dr._migrate_owner_manifest(
            ledger,
            "5Owner",
            ledger.raw,
            frozen,
            candidate,
            markers_dir=markers_dir,
            host=host,
        )

    return ledger, frozen, candidate, markers, states, migrate


def _mark(markers, task_id, state):
    (markers / f"{task_id}.json").write_text(json.dumps({"state": state}))


def _events(capsys):
    return [json.loads(line) for line in capsys.readouterr().err.strip().splitlines()]


def _record(ledger):
    (line,) = (Path(ledger.root) / "manifest-migrations.jsonl").read_text().splitlines()
    return json.loads(line)


def test_an_owner_with_only_unbuilt_tasks_migrates_without_a_declaration(world, capsys):
    ledger, _frozen, candidate, _markers, states, migrate = world
    states += [(T1, "QUEUED"), (T2, "FAILED_INFRA")]
    assert migrate(TOUCHED) is True
    assert ledger.manifest() == candidate
    said = _events(capsys)
    assert said[0] == {
        "event": "owner_manifest_migration_ungraded",
        "from_revision": OLD,
        "to_revision": NEW,
        "paths": 1,
        "tasks": 2,
        "unbuilt": 2,
        "built_ungraded": 0,
    }  # counts only: no owner, no task id, no path
    assert "5Owner" not in json.dumps(said[0]) and T1 not in json.dumps(said[0])
    assert _record(ledger)["basis"] == "ungraded_owner"


def test_unbuilt_tasks_migrate_even_when_the_build_inputs_changed(world):
    ledger, _frozen, candidate, _markers, states, migrate = world
    states += [(T1, "QUEUED"), (T2, "RUNNING")]
    assert migrate(WITH_BUILD) is True and ledger.manifest() == candidate


def test_a_built_task_with_no_grade_migrates_only_while_the_build_inputs_are_unchanged(
    world, capsys
):
    ledger, frozen, candidate, _markers, states, migrate = world
    states.append((T1, "SUCCEEDED"))  # built, never graded
    assert migrate(WITH_BUILD) is False  # its state came from the old worker images
    assert ledger.manifest() == frozen
    assert _events(capsys)[-1]["reason"] == "grading_path_changed"
    assert migrate(TOUCHED) is True and ledger.manifest() == candidate
    assert _events(capsys)[0]["built_ungraded"] == 1


@pytest.mark.parametrize("state", ["GRADED", "CANDIDATE_FAILED", "PENDING"])
def test_an_owner_with_any_grade_evidence_still_needs_the_declaration(
    world, capsys, state
):
    ledger, frozen, _candidate, markers, states, migrate = world
    states += [(T1, "QUEUED"), (T2, "SUCCEEDED")]
    _mark(markers, T2, state)  # graded under the old program
    assert migrate(TOUCHED) is False
    assert ledger.manifest() == frozen  # nothing re-bound
    said = _events(capsys)
    assert [e["event"] for e in said] == ["owner_manifest_migration_refused"]
    assert said[0]["reason"] == "grading_path_changed"
    assert not (Path(ledger.root) / "manifest-migrations.jsonl").exists()


def test_a_marker_that_cannot_be_read_is_grade_evidence(world):
    ledger, frozen, _candidate, markers, states, migrate = world
    states.append((T1, "SUCCEEDED"))
    (markers / f"{T1}.json").write_text("{not json")
    assert migrate(TOUCHED) is False and ledger.manifest() == frozen


def test_a_failed_or_withdrawn_marker_carries_no_grade(world, capsys):
    ledger, _frozen, candidate, markers, states, migrate = world
    states += [(T1, "SUCCEEDED"), (T2, "SUCCEEDED")]
    _mark(
        markers, T1, "FAILED"
    )  # failed Carbon-side: no score accepted, graded again on the new program
    _mark(markers, T2, "WITHDRAWN_BY_MINER")  # never graded and never will be
    assert migrate(TOUCHED) is True and ledger.manifest() == candidate
    counts = _events(capsys)[0]
    assert (counts["built_ungraded"], counts["unbuilt"]) == (1, 1)


def test_the_crowns_host_owner_always_needs_the_declaration(world):
    ledger, frozen, _candidate, _markers, _states, migrate = world
    assert migrate(TOUCHED, host=True) is False  # its rebuilds are crown evidence
    assert ledger.manifest() == frozen


def test_doubt_keeps_the_declaration(world, monkeypatch):
    ledger, frozen, _candidate, _markers, _states, migrate = world
    assert migrate(TOUCHED, markers_dir=None) is False  # a door with no grade markers
    monkeypatch.setattr(dr, "_owner_task_states", lambda owner_dir: None)
    assert migrate(TOUCHED) is False  # an unreadable task store
    assert ledger.manifest() == frozen


def test_an_unknown_change_never_migrates_an_ungraded_owner(world, capsys):
    ledger, frozen, _candidate, _markers, states, migrate = world
    states.append((T1, "QUEUED"))
    assert migrate(None) is False and ledger.manifest() == frozen
    assert _events(capsys)[-1]["reason"] == "grading_change_unknown"


def test_no_grading_change_records_its_basis(world):
    ledger, _frozen, _candidate, markers, states, migrate = world
    states.append((T1, "SUCCEEDED"))
    _mark(markers, T1, "GRADED")
    assert (
        migrate(()) is True
    )  # no grading change: migrates as before, whatever was graded
    assert _record(ledger)["basis"] == "no_grading_change"


def test_a_declared_change_still_migrates_a_graded_owner(world):
    ledger, _frozen, candidate, markers, states, migrate = world
    states.append((T1, "SUCCEEDED"))
    _mark(markers, T1, "GRADED")
    dr.install_declared_change(
        {
            "declared_exam_change": {
                "from_revision": OLD,
                "to_revision": NEW,
                "paths": list(TOUCHED),
                "reason": "fixture",
                "evidence_sha256": "sha256:" + "e" * 64,
            }
        }
    )
    try:
        assert migrate(TOUCHED) is True and ledger.manifest() == candidate
        assert _record(ledger)["basis"] == "declared"
    finally:
        dr.install_declared_change({})


def test_the_task_store_reader_answers_none_without_a_store(tmp_path):
    assert dr._owner_task_states(tmp_path / "missing") is None
    assert dr._ungraded_owner(tmp_path, None, build_inputs_changed=False) is None
