"""The early wall stop of the counted bank grade (Bundle A, 14 Nov 2026; shipped dark, switched ON for Motor 1.8 on 14 Nov).

A counted graded pass whose STRICT LOWER BOUND from the origin's own measured practice pass already exceeds the published
inference wall is settled as the candidate's wall stop without running. OFF unless the host registry has an enabled row; every
doubt fails open (the pass runs and the wall kills it as before). The registry tests pin the committed production row
(Motor 1.8: s_max 54.828 s, margin 1.5, and its decision record); every other test uses synthetic numbers and ids.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from typing import ClassVar

import pytest

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator import lean_recipe_retention as lrr

EVIDENCE = "sha256:" + "ab" * 32
KEY = "ch 9.9"


def _write(tmp_path, rows):
    path = tmp_path / "early_wall_stop.json"
    path.write_text(json.dumps({"schema": lrr.EARLY_WALL_STOP_SCHEMA, "rows": rows}))
    return path


def _row(**changes):
    row = {
        "enabled": True,
        "s_max_seconds": 5.0,
        "margin": 1.0,
        "evidence_sha256": EVIDENCE,
    }
    row.update(changes)
    return row


# --- the registry ---------------------------------------------------------------------------------------------


def test_the_committed_registry_enables_exactly_motor_1_8_at_cv_motor_cs_values():
    """The early stop is ON for Motor 1.8 only (owner, 14 Nov 2026: 'Switch it on now'; skips count): s_max_seconds = the max
    finished op A over 36 of 36 grades, margin = the owner's 1.5x, evidence = the sha of Deploy-C's private list (Validator-Motor-C
    board 18:21, Deploy-C 18:23). Every other version stays OFF."""
    from carbon.challenge_validator import registry_version

    document = json.loads(lrr.EARLY_WALL_STOP_REGISTRY.read_text())
    assert document == {
        "rows": {
            "electric-motor-magnetics 1.8": {
                "enabled": True,
                "evidence_sha256": "sha256:f6cf433e3c57fa7b1d8b9ca5a9955f593cf28516c25e5b388b14a10bf5fd4ae5",
                "margin": 1.5,
                "s_max_seconds": 54.828,
            }
        },
        "schema": lrr.EARLY_WALL_STOP_SCHEMA,
    }
    for key in document["rows"]:
        assert registry_version.known_key(key, exam_cap.registered_challenges()), key
    assert lrr.early_wall_stop_rule("electric-motor-magnetics", "1.8") == {
        "s_max_seconds": 54.828,
        "margin": 1.5,
    }
    for challenge, version in (
        ("electric-motor-magnetics", "1.7"),
        ("electric-motor-magnetics", "1.9"),
        ("f08-ribbed-bracket", "1.8"),
        ("chip-cold-plate", "1.8"),
    ):
        assert lrr.early_wall_stop_rule(challenge, version) is None


def test_at_the_committed_values_the_projection_skips_only_what_cannot_finish():
    """The rule's own arithmetic at the registered values (2611 bank rows, 154 practice rows, wall 648 s, margin 1.5: skip when
    2611 x (op A - s_max) / 154 > 972 s, i.e. op A > 54.828 + 57.33...): a 55 s op A never skips, a 120 s one does.
    """
    rule = lrr.early_wall_stop_rule("electric-motor-magnetics", "1.8")
    assert lrr.early_wall_stop_decision(55.0, 154, 2611, 648.0, rule)[0] is False
    assert lrr.early_wall_stop_decision(100.0, 154, 2611, 648.0, rule)[0] is False
    assert lrr.early_wall_stop_decision(120.0, 154, 2611, 648.0, rule)[0] is True
    threshold = 54.828 + 972.0 * 154 / 2611
    assert (
        lrr.early_wall_stop_decision(threshold - 0.01, 154, 2611, 648.0, rule)[0]
        is False
    )
    assert (
        lrr.early_wall_stop_decision(threshold + 0.01, 154, 2611, 648.0, rule)[0]
        is True
    )


def test_the_decision_record_matches_the_row_and_both_ride_a_values_only_roll():
    """The decision record (docs/records/2026-11-14-motor18-early-wall-stop.json) carries EXACTLY the registry row's values and
    evidence, quotes the owner's words verbatim with where they were typed, and both files are paths a values-only descendant
    may change (research_campaign.descendant_path_allowed), so the live door takes them by an in-place values roll.
    """
    from pathlib import Path

    from carbon.development_session.research_campaign import descendant_path_allowed

    root = Path(lrr.EARLY_WALL_STOP_REGISTRY).resolve().parents[2]
    record_path = "docs/records/2026-11-14-motor18-early-wall-stop.json"
    record = json.loads((root / record_path).read_text())
    row = json.loads(lrr.EARLY_WALL_STOP_REGISTRY.read_text())["rows"][
        "electric-motor-magnetics 1.8"
    ]
    assert (record["challenge"], record["version"]) == (
        "electric-motor-magnetics",
        "1.8",
    )
    assert record["values"] == {
        k: row[k] for k in ("enabled", "margin", "s_max_seconds")
    }
    assert record["evidence"]["evidence_sha256"] == row["evidence_sha256"]
    quotes = {w["verbatim"] for w in record["owner_words"]}
    assert "Switch it on now" in quotes
    assert all(
        w["typed_in"] and w["typed_at"] and w["source"] for w in record["owner_words"]
    )
    registry_path = (
        Path(lrr.EARLY_WALL_STOP_REGISTRY).resolve().relative_to(root).as_posix()
    )
    assert descendant_path_allowed(registry_path) and descendant_path_allowed(
        record_path
    )


def test_an_enabled_well_formed_row_is_read(tmp_path):
    path = _write(tmp_path, {KEY: _row(s_max_seconds=7, margin=1.25)})
    assert lrr.early_wall_stop_rule("ch", "9.9", path=path) == {
        "s_max_seconds": 7.0,
        "margin": 1.25,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"enabled": False},
        {"enabled": 1},
        {"margin": 0.99},
        {"margin": True},
        {"margin": float("nan")},
        {"s_max_seconds": -1},
        {"s_max_seconds": "5"},
        {"evidence_sha256": "x"},
        {"extra": 1},
    ],
)
def test_a_malformed_or_disabled_row_is_off(tmp_path, changes):
    path = _write(tmp_path, {KEY: _row(**changes)})
    assert lrr.early_wall_stop_rule("ch", "9.9", path=path) is None


def test_a_missing_row_file_or_schema_is_off_and_never_raises(tmp_path):
    assert lrr.early_wall_stop_rule("ch", "9.9", path=tmp_path / "absent.json") is None
    other = tmp_path / "other.json"
    other.write_text('{"schema":"nope","rows":{"ch 9.9":{}}}')
    assert lrr.early_wall_stop_rule("ch", "9.9", path=other) is None
    garbage = tmp_path / "garbage.json"
    garbage.write_bytes(b"\xff\x00{")
    assert lrr.early_wall_stop_rule("ch", "9.9", path=garbage) is None
    assert (
        lrr.early_wall_stop_rule(
            "ch", "other-version", path=_write(tmp_path, {KEY: _row()})
        )
        is None
    )


# --- the rule's math (strict lower bound) ---------------------------------------------------------------------

RULE = {"s_max_seconds": 5.0, "margin": 1.0}


def test_the_lower_bound_is_rows_times_the_per_row_cost_with_the_largest_startup_removed():
    # A = 25 s over 100 rows, start-up at most 5 s => c >= 0.2 s/row => 1000 rows >= 200 s
    stop, lower = lrr.early_wall_stop_decision(25.0, 100, 1000, 199.0, RULE)
    assert lower == pytest.approx(200.0) and stop is True


def test_it_stops_only_strictly_above_the_wall_times_the_margin():
    assert (
        lrr.early_wall_stop_decision(25.0, 100, 1000, 200.0, RULE)[0] is False
    )  # equal: not strictly above
    wide = {**RULE, "margin": 1.2}
    assert lrr.early_wall_stop_decision(25.0, 100, 1000, 180.0, wide)[0] is False
    assert lrr.early_wall_stop_decision(25.0, 100, 1000, 160.0, wide)[0] is True


@pytest.mark.parametrize(
    "args",
    [
        (5.0, 100, 1000, 10.0),  # A <= s_max: the whole measurement may be start-up
        (4.0, 100, 1000, 10.0),
        (0.0, 100, 1000, 10.0),
        (-3.0, 100, 1000, 10.0),
        (25.0, 0, 1000, 10.0),
        (25.0, 100, 0, 10.0),
        (25.0, 100, 1000, 0.0),
        (float("nan"), 100, 1000, 10.0),
        (None, 100, 1000, 10.0),
    ],
)
def test_every_doubt_is_a_pass_that_runs(args):
    assert lrr.early_wall_stop_decision(*args, RULE)[0] is False


def test_no_rule_never_stops():
    assert lrr.early_wall_stop_decision(1e9, 1, 10**6, 1.0, None) == (False, None)


# --- reading the origin's op A ---------------------------------------------------------------------------------


class _Ledger:
    def __init__(self, rows):
        self._db = sqlite3.connect(":memory:")
        self._db.execute(
            "CREATE TABLE operations (id TEXT, owner TEXT, state TEXT, actual TEXT)"
        )
        for row in rows:
            self._db.execute("INSERT INTO operations VALUES (?,?,?,?)", row)

    @contextmanager
    def db(self):
        yield self._db


def _identity(origin):
    from carbon.development_session.bundle_construction_worker import (
        direct_child_identity,
    )

    return direct_child_identity(origin, "inference")


ORIGIN = "rtsk_" + "1" * 64


def _provider(*rows):
    return SimpleNamespace(ledger=_Ledger(rows))


def test_the_origin_op_a_seconds_are_its_measured_elapsed():
    actual = json.dumps({"numerical_milliseconds": 25000})
    provider = _provider((_identity(ORIGIN), "owner", "SUCCEEDED", actual))
    assert lrr._origin_inference_seconds(provider, "owner", ORIGIN) == 25.0


@pytest.mark.parametrize(
    "row",
    [
        None,
        ("SUCCEEDED", "owner", "{}"),
        ("FAILED_MINER", "owner", json.dumps({"numerical_milliseconds": 25000})),
        ("SUCCEEDED", "other-owner", json.dumps({"numerical_milliseconds": 25000})),
        ("SUCCEEDED", "owner", json.dumps({"numerical_milliseconds": 0})),
        ("SUCCEEDED", "owner", json.dumps({"numerical_milliseconds": "25000"})),
        ("SUCCEEDED", "owner", "not json"),
        ("SUCCEEDED", "owner", None),
    ],
)
def test_a_missing_or_unusable_op_a_is_none(row):
    rows = [] if row is None else [(_identity(ORIGIN), row[1], row[0], row[2])]
    assert lrr._origin_inference_seconds(_provider(*rows), "owner", ORIGIN) is None


# --- the check ------------------------------------------------------------------------------------------------


def _check(
    tmp_path,
    monkeypatch,
    *,
    practice=100,
    a_ms=25000,
    wall=180.0,
    enabled=True,
    bank=1000,
):
    path = _write(tmp_path, {KEY: _row()} if enabled else {})
    monkeypatch.setattr(lrr, "EARLY_WALL_STOP_REGISTRY", path)
    provider = _provider(
        (
            _identity(ORIGIN),
            "owner",
            "SUCCEEDED",
            json.dumps({"numerical_milliseconds": a_ms}),
        )
    )
    adapter = SimpleNamespace(challenge_id="ch", challenge_version="9.9")
    material = {"practice_inputs": [0] * practice}
    return lrr._check_early_wall_stop(
        adapter, provider, "owner", ORIGIN, material, bank, wall
    )


def test_a_provable_wall_miss_raises_with_a_counts_and_seconds_record_only(
    tmp_path, monkeypatch
):
    with pytest.raises(lrr.EarlyWallStop) as stopped:
        _check(tmp_path, monkeypatch)
    record = stopped.value.record
    assert record["bank_rows"] == 1000 and record["origin_op_a_rows"] == 100
    assert record["lower_bound_seconds"] == pytest.approx(200.0)
    assert set(record) == {
        "schema",
        "origin_op_a_seconds",
        "origin_op_a_rows",
        "bank_rows",
        "inference_wall_seconds",
        "s_max_seconds",
        "margin",
        "lower_bound_seconds",
    }
    assert isinstance(stopped.value, lrr.RetentionUnavailable)


def test_off_without_a_row_and_when_the_pass_could_fit(tmp_path, monkeypatch):
    assert _check(tmp_path, monkeypatch, enabled=False) is None  # no row, no stop
    assert _check(tmp_path, monkeypatch, wall=400.0) is None  # could finish inside
    assert _check(tmp_path, monkeypatch, a_ms=5000) is None  # A <= s_max


def test_an_unreadable_practice_bank_is_a_pass_that_runs(tmp_path, monkeypatch):
    path = _write(tmp_path, {KEY: _row()})
    monkeypatch.setattr(lrr, "EARLY_WALL_STOP_REGISTRY", path)
    provider = _provider(
        (
            _identity(ORIGIN),
            "owner",
            "SUCCEEDED",
            json.dumps({"numerical_milliseconds": 25000}),
        )
    )
    adapter = SimpleNamespace(challenge_id="ch", challenge_version="9.9")
    assert (
        lrr._check_early_wall_stop(adapter, provider, "owner", ORIGIN, {}, 1000, 180.0)
        is None
    )


# --- the settle path ------------------------------------------------------------------------------------------


class _Cap:
    settled: ClassVar[list] = []

    def __init__(self, ledger, cadence=None):
        pass

    def reserve(self, **kwargs):
        return "reservation-1"

    def settle(self, reservation, outcome):
        _Cap.settled.append((reservation, outcome))


def _counted(tmp_path, monkeypatch, raised):
    _Cap.settled = []
    monkeypatch.setattr(exam_cap, "ExamCap", _Cap)
    monkeypatch.setattr(exam_cap, "submission_block", lambda *a, **k: 1)
    evaluation = tmp_path / "evaluation"
    evaluation.mkdir()
    monkeypatch.setattr(
        lrr, "_private_evaluation_directory", lambda result, submission_id: evaluation
    )

    def regrade(*args, **kwargs):
        raise raised

    monkeypatch.setattr(lrr, "regrade_retained_entry", regrade)
    adapter = SimpleNamespace(
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=SimpleNamespace(manifest_digest="d")
        ),
        owner=lambda submission_id: "owner",
        ledger=object(),
        contract_digest="c",
        challenge_id="ch",
        challenge_version="9.9",
    )
    result = lrr._counted_bank_grade(
        adapter,
        "rtsk_" + "2" * 64,
        {"entry_id": "e", "artifact_path": "x"},
        pool_store=None,
        artifact_directory=None,
        entry_directory=None,
    )
    return result, evaluation


def test_an_early_stop_settles_as_the_candidates_wall_stop_and_keeps_a_private_record(
    tmp_path, monkeypatch
):
    record = {"schema": "carbon.exam.early-wall-stop-record.v1", "bank_rows": 1000}
    result, evaluation = _counted(tmp_path, monkeypatch, lrr.EarlyWallStop(record))
    # COUNTED, never given back
    assert _Cap.settled == [("reservation-1", lrr.CANDIDATE_WALL_LIMIT_REACHED)]
    assert result["private_evaluation_state"] == "CANDIDATE_FAILED"
    assert result["private_evaluation_reason"] == lrr.CANDIDATE_WALL_LIMIT_REACHED
    assert json.loads((evaluation / "early-wall-stop.json").read_text()) == record


def test_any_other_failure_still_gives_the_slot_back(tmp_path, monkeypatch):
    with pytest.raises(lrr.RetentionUnavailable):
        _counted(tmp_path, monkeypatch, lrr.RetentionUnavailable("something_else"))
    assert _Cap.settled == [("reservation-1", "UNAVAILABLE")]
