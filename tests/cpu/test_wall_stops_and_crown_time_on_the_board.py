"""Wall stops on the Ladder and the board, and the crown's decision time (Lead 15 Nov, one head for the next door switch).

Claims:
- a counted stop at the inference wall is a NOT_SCORED Ladder document with reason TIMED_OUT, and the registered early stop is
  NOT_SCORED / STOPPED_EARLY (v3 and v4 documents; the best is unchanged); the published exam card lists both reasons;
- the receiver files that document for both stops (`_record_stop_ladder`, from the served pack's own registration), its own
  failure never changing the settled outcome, and the early stop carries its submission's recipe digest;
- the v5 board (v3 plus the king's ``crowned_utc`` and a row ``reason``) names only those two reasons, null otherwise,
  verifies under its own domain only, and refuses a reason on a scored row or a malformed crown time;
- the operator's v5 run publishes a stopped hotkey's reason from the real Ladder and the crown's DECISION time from the pool
  store (never the submission epoch).
"""

# ruff: noqa: F811
from __future__ import annotations

import datetime
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts" / "dev"))

import launch_board_operator as operator
from test_launch_board_operator_official import _official
from test_launch_board_operator_v2 import (  # noqa: F401 - the fixtures and helpers
    COOLING,
    EXAM,
    GATES,
    KING,
    OTHER,
    _board_bytes,
    _v2_fixture,
    door,
    frozen,
)

from carbon.challenge_registry import published_exam
from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator import lean_recipe_retention as lrr
from carbon.challenge_validator.ladder_store import LadderStore
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.registry.model import ChallengeKey
from carbon.scoring import grade_feedback as gf

DIGEST = "sha256:" + "a" * 64


# --- the Ladder document ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "reason"),
    [(gf.WALL_STOP_STATUS, "TIMED_OUT"), (gf.EARLY_STOP_STATUS, "STOPPED_EARLY")],
)
def test_a_wall_stop_is_not_scored_with_its_reason_and_the_best_stands(status, reason):
    best = gf.ladder_feedback(
        {
            "status": "SCORED_DEVELOPMENT_CANDIDATE",
            "score": 0.61,
            "gates": {"g": "PASS"},
        },
        best=None,
        exam_version="exam-1",
        gate_registry={"g"},
        rebuild_noise=None,
        recipe_digest=DIGEST,
        epoch=1,
    )
    v3 = gf.ladder_feedback(
        {"status": status},
        best=best,
        exam_version="exam-1",
        gate_registry={"g"},
        rebuild_noise=None,
        recipe_digest=DIGEST,
        epoch=2,
    )
    assert v3["status"] == "NOT_SCORED" and v3["reason"] == reason and v3["leg"] is None
    assert v3["total"] is None and gf.shape(v3) == gf.SCHEMA_V3
    assert gf.next_best(best, v3) == best  # a stop never moves the best
    v4 = gf.ladder_feedback(
        {"status": status},
        best=None,
        exam_version="exam-1",
        gate_registry={"g"},
        rebuild_noise=None,
        recipe_digest=DIGEST,
        epoch=2,
        parts_registry={"A": ["a"], "D": ["d"]},
    )
    assert v4["reason"] == reason and gf.shape(v4) == gf.SCHEMA_V4
    assert reason in published_exam._GRADE["reasons"]
    assert published_exam._GRADE["reasons"] == list(gf.REASONS)


# --- the receiver files it -----------------------------------------------------------------------------------


class _Snapshot:
    manifest_digest = "sha256:" + "e" * 64

    def read_source_registration(self, root):
        return {"evaluation_version": "exam-1"}

    def read_json_role(self, root, kind, role, max_bytes):
        assert (kind, role) == ("private", "score_pack")
        return {"schema": "plain", "pack_digest": "x", "body": 1}


def _adapter():
    return SimpleNamespace(
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=_Snapshot(), evaluation_pack_private_root="root"
        )
    )


def test_the_receiver_files_a_stop_from_the_served_packs_registration(monkeypatch):
    import carbon.scoring.solver_benchmark_v3 as sb3

    seen = {}
    monkeypatch.setattr(
        sb3,
        "register_pack",
        lambda body: {"hard_gates": ["g"], "legs": {"A": {"minimum": 0.1}}},
    )
    monkeypatch.setattr(
        lrr, "_record_ladder", lambda *a, **k: seen.update(args=a, **k) or "RECORDED"
    )
    state = lrr._record_stop_ladder(
        _adapter(), "rtsk_1", lrr.EARLY_STOP_STATUS, lambda: DIGEST
    )
    assert state == "RECORDED"
    assert seen["args"][1] == "rtsk_1"
    assert seen["graded"] == {"status": gf.EARLY_STOP_STATUS}
    assert seen["exam_version"] == "exam-1" and seen["gates"] == ["g"]
    assert seen["exam_key"] == _Snapshot.manifest_digest
    assert seen["recipe_digest"] == DIGEST and seen["leg_minimums"] == {"A": 0.1}
    assert lrr.WALL_STOP_STATUS == gf.WALL_STOP_STATUS
    assert lrr.EARLY_STOP_STATUS == gf.EARLY_STOP_STATUS


def test_a_failure_to_file_the_stop_never_changes_the_outcome():
    state = lrr._record_stop_ladder(
        SimpleNamespace(), "rtsk_1", lrr.WALL_STOP_STATUS, lambda: DIGEST
    )
    assert state.startswith("UNAVAILABLE: ladder_stop_")


def test_a_counted_early_stop_settles_as_before_and_files_its_ladder_row(
    tmp_path, monkeypatch
):
    from test_early_wall_stop import _Cap, _counted

    filed = []
    monkeypatch.setattr(
        lrr,
        "_record_stop_ladder",
        lambda adapter, sid, status, recipe_of: filed.append((sid, status, recipe_of()))
        or "RECORDED",
    )
    stopped = lrr.EarlyWallStop({"schema": "carbon.exam.early-wall-stop-record.v1"})
    stopped.recipe_digest = DIGEST
    result, _evaluation = _counted(tmp_path, monkeypatch, stopped)
    assert _Cap.settled == [("reservation-1", lrr.CANDIDATE_WALL_LIMIT_REACHED)]
    assert result["private_evaluation_state"] == "CANDIDATE_FAILED"
    assert result["ladder_feedback_state"] == "RECORDED"
    assert filed == [("rtsk_" + "2" * 64, lrr.EARLY_STOP_STATUS, DIGEST)]


def test_an_early_stop_has_no_recipe_until_it_is_raised():
    assert lrr.EarlyWallStop({}).recipe_digest is None


# --- the v5 board ---------------------------------------------------------------------------------------------


def _ladder_with_a_stop(
    root, reason_status, other_status="SCORED_DEVELOPMENT_CANDIDATE"
):
    ladder = LadderStore(AttemptLedger(root / "attempts.sqlite3"))
    key = ChallengeKey(COOLING["id"], COOLING["version"])
    common = {
        "exam_version": COOLING["exam_version_label"],
        "gates": GATES,
        "rebuild_noise": None,
        "recipe_digest": DIGEST,
        "epoch": 3,
    }
    ladder.record(OTHER, key, EXAM, {"status": reason_status}, **common)
    return ladder


def _v5(tmp_path, door, monkeypatch):
    _official(tmp_path, monkeypatch)
    config, pool = _v2_fixture(tmp_path / "b", door)
    config["board"] = "v5"
    return config, pool


def test_the_v5_board_names_a_stopped_hotkeys_reason_and_the_crowns_decision_time(
    tmp_path, door, frozen, monkeypatch
):
    config, pool = _v5(tmp_path, door, monkeypatch)
    root = Path(config["ledger"]).parent
    _ladder_with_a_stop(root, gf.WALL_STOP_STATUS)
    (row,) = operator.run_once(config, version=9)
    assert row["state"] == "WROTE" and row["board"] == "v5", row
    board = json.loads(_board_bytes(config, COOLING))
    assert board["schema"] == lb.SCHEMA_V5
    assert lb.verify(board, board["validator"]["feed_key"]) == board
    rows = {r["hotkey"]: r for r in board["ladder"]}
    assert (
        rows[OTHER]["status"] == "NOT_SCORED" and rows[OTHER]["reason"] == "TIMED_OUT"
    )
    assert rows[KING]["reason"] is None
    assert board["counts"]["not_scored"] == 1
    # the crown time is the incumbent row's DECISION time, to the second
    with sqlite3.connect(pool) as db:
        (since,) = db.execute("SELECT since FROM incumbent WHERE id=1").fetchone()
    want = datetime.datetime.fromtimestamp(int(since), datetime.UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert board["king"]["crowned_utc"] == want
    assert board["king"]["stability"] == "STABLE"


def test_any_other_not_scored_reason_stays_private_on_the_board(
    tmp_path, door, frozen, monkeypatch
):
    config, _pool = _v5(tmp_path, door, monkeypatch)
    root = Path(config["ledger"]).parent
    _ladder_with_a_stop(root, "FAILED_INFRA")
    operator.run_once(config, version=9)
    board = json.loads(_board_bytes(config, COOLING))
    rows = {r["hotkey"]: r for r in board["ladder"]}
    assert rows[OTHER]["status"] == "NOT_SCORED" and rows[OTHER]["reason"] is None


def _signed(body):
    key = lb.LaunchBoardKey(bytes(range(32)))
    body = {k: v for k, v in body.items() if k != "signature"}
    return key, {**body, "signature": key.sign(body)}


def test_v5_refuses_a_reason_on_a_scored_row_a_bad_reason_or_a_bad_crown_time(
    tmp_path, door, frozen, monkeypatch
):
    config, _pool = _v5(tmp_path, door, monkeypatch)
    _ladder_with_a_stop(Path(config["ledger"]).parent, gf.EARLY_STOP_STATUS)
    operator.run_once(config, version=9)
    board = json.loads(_board_bytes(config, COOLING))
    assert lb.check(board) == board
    for change in (
        lambda b: b["ladder"][0].__setitem__(
            "reason", "TIMED_OUT"
        ),  # the king's scored row
        lambda b: next(r for r in b["ladder"] if r["hotkey"] == OTHER).__setitem__(
            "reason", "FAILED_INFRA"
        ),
        lambda b: b["king"].__setitem__("crowned_utc", "15 Nov"),
        lambda b: b["ladder"][0].pop("reason"),
        lambda b: b["king"].pop("crowned_utc"),
    ):
        body = json.loads(json.dumps(board))
        change(body)
        key, signed = _signed(body)
        with pytest.raises(lb.BoardRefused):
            lb.verify(signed, key.public_key)


def test_a_v5_signature_never_verifies_under_another_domain(
    tmp_path, door, frozen, monkeypatch
):
    config, _pool = _v5(tmp_path, door, monkeypatch)
    operator.run_once(config, version=9)
    board = json.loads(_board_bytes(config, COOLING))
    key = board["validator"]["feed_key"]
    as_v3 = {**board, "schema": lb.SCHEMA_V3}
    with pytest.raises(lb.BoardRefused):
        lb.verify(as_v3, key)
    assert lb._domain(board) == lb.BOARD_DOMAIN_V5 != lb.BOARD_DOMAIN_V3


def test_v5_is_v3_plus_two_fields_never_v4():
    with pytest.raises(lb.BoardRefused, match="board_v5_is_v3_plus_two_fields"):
        lb.build(
            king_document=None,
            rows=[],
            network="testnet",
            key=lb.LaunchBoardKey(bytes(range(32))),
            version=1,
            crown_changes=[],
            exact_totals={},
            rebuild_noise=None,
            crowned_utc=None,
        )


def test_the_dashboards_reader_projects_the_reason_and_the_crown_time(
    tmp_path, door, frozen, monkeypatch
):
    from carbon.dashboard import board_v2, feed

    config, _pool = _v5(tmp_path, door, monkeypatch)
    _ladder_with_a_stop(Path(config["ledger"]).parent, gf.WALL_STOP_STATUS)
    operator.run_once(config, version=9)
    raw = _board_bytes(config, COOLING)
    board = json.loads(raw)
    trust = feed.Trust(keys=frozenset({board["validator"]["feed_key"]}))
    projected = feed.project(board, trust)
    launch = projected["launch"]
    assert launch["reasons"] == {OTHER: "TIMED_OUT"}
    assert launch["crowned_utc"] == board["king"]["crowned_utc"]
    v2 = board_v2.project(projected, 1_800_000_000)
    assert v2["launch"]["reasons"] == {OTHER: "TIMED_OUT"}
    assert v2["launch"]["crowned_utc"] == board["king"]["crowned_utc"]
